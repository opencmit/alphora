import logging
import mimetypes
import base64
import re
from datetime import datetime
from pathlib import Path
from typing import List, Literal, Optional
from urllib.parse import quote

from fastapi import FastAPI, APIRouter, HTTPException, Query, UploadFile, File, Form
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)

HIDDEN_PATTERNS = {'.git', '__pycache__', '.DS_Store', 'node_modules', '.alphora_mnt_'}

TEXT_MIMES = {
    'text', 'application/json', 'application/xml', 'application/javascript',
    'application/x-yaml', 'application/toml', 'application/x-sh',
    'application/sql', 'application/xhtml+xml', 'application/x-httpd-php',
}

MAX_INLINE_SIZE = 50 * 1024 * 1024  # 50 MB
MAX_UPLOAD_SIZE = 100 * 1024 * 1024  # 100 MB per file

MAX_LIST_DEPTH = 5
MAX_PAGE_SIZE = 1000
DEFAULT_PAGE_SIZE = 200

# session_id 允许字符：字母数字、下划线、连字符、点号；可选一个正斜杠分段（兼容 user/session 布局）
_SESSION_ID_RE = re.compile(r"^[A-Za-z0-9_\-.]+(?:/[A-Za-z0-9_\-.]+)?$")
_SESSION_ID_MAX_LEN = 128


class FileListRequest(BaseModel):
    session_id: str = ""
    dir: str = "/"
    recursive: bool = False
    max_depth: int = Field(1, ge=1, le=MAX_LIST_DEPTH)
    page: int = Field(1, ge=1)
    page_size: int = Field(DEFAULT_PAGE_SIZE, ge=1, le=MAX_PAGE_SIZE)
    sort_by: Literal["name", "size", "mtime"] = "name"
    order: Literal["asc", "desc"] = "asc"


class FileReadRequest(BaseModel):
    session_id: str = ""
    path: str


class FileDownloadRequest(BaseModel):
    session_id: str = ""
    path: str


def _validate_session_id(session_id: str, *, allow_empty: bool) -> None:
    """校验 session_id 合法性。非法直接 400，避免路径穿透。"""
    if not session_id:
        if allow_empty:
            return
        raise HTTPException(status_code=400, detail="session_id 不能为空")
    if len(session_id) > _SESSION_ID_MAX_LEN:
        raise HTTPException(status_code=400, detail="session_id 过长")
    if not _SESSION_ID_RE.match(session_id):
        raise HTTPException(status_code=400, detail="session_id 含非法字符")
    # regex 允许 . 但不允许 . / .. 作为独立段
    for seg in session_id.split("/"):
        if seg in ("", ".", ".."):
            raise HTTPException(status_code=400, detail="session_id 非法")


def _find_session_dir(base: Path, session_id: str) -> Path | None:
    """在 base 及其一级子目录中查找 session_id 目录。

    支持两种目录结构：
    - 扁平结构：{base}/{session_id}/
    - 多用户结构：{base}/{user_id}/{session_id}/
    """
    direct = base / session_id
    if direct.is_dir():
        return direct.resolve()
    # session_id 已经包含一段斜杠时，不再做子目录穷举（避免拼出无意义三级路径）
    if "/" in session_id:
        return None
    try:
        for sub in base.iterdir():
            if sub.is_dir() and not sub.name.startswith('.'):
                candidate = sub / session_id
                if candidate.is_dir():
                    return candidate.resolve()
    except (PermissionError, OSError):
        pass
    return None


def _resolve_root(base: Path, session_id: str, *, allow_empty: bool) -> Path:
    _validate_session_id(session_id, allow_empty=allow_empty)
    base_resolved = base.resolve()
    if not session_id:
        return base_resolved
    found = _find_session_dir(base_resolved, session_id)
    return found if found else (base_resolved / session_id).resolve()


def _resolve_root_or_create(base: Path, session_id: str, *, allow_empty: bool) -> Path:
    """Like _resolve_root but creates the session directory if it doesn't exist."""
    _validate_session_id(session_id, allow_empty=allow_empty)
    base_resolved = base.resolve()
    if not session_id:
        base_resolved.mkdir(parents=True, exist_ok=True)
        return base_resolved
    found = _find_session_dir(base_resolved, session_id)
    if found:
        return found
    session_dir = base_resolved / session_id
    session_dir.mkdir(parents=True, exist_ok=True)
    return session_dir.resolve()


def _safe_path(root: Path, rel: str) -> Path:
    """把相对 session root 的路径解析成绝对路径，拒绝越界。

    root 必须已经 resolve 过。rel 会被 normpath / resolve 规范化。
    """
    cleaned = (rel or "").lstrip("/")
    target = (root / cleaned).resolve()
    try:
        target.relative_to(root)
    except ValueError:
        raise HTTPException(status_code=403, detail="路径越界")
    return target


def _is_hidden(name: str) -> bool:
    for pat in HIDDEN_PATTERNS:
        if name == pat or name.startswith(pat):
            return True
    return False


def _is_text_mime(mime: str) -> bool:
    if not mime:
        return False
    if mime.startswith('text/'):
        return True
    return mime in TEXT_MIMES


def _fmt_size(n: int) -> str:
    f = float(n)
    for unit in ('B', 'KB', 'MB', 'GB'):
        if f < 1024:
            return f"{int(f)} B" if unit == 'B' else f"{f:.1f} {unit}"
        f /= 1024
    return f"{f:.1f} TB"


def _build_file_info(p: Path, root: Path) -> dict:
    is_symlink = p.is_symlink()
    stat = p.stat()  # follow symlink
    is_dir = p.is_dir()
    rel = str(p.relative_to(root))
    return {
        "name": p.name,
        "path": "/" + rel,
        "type": "directory" if is_dir else "file",
        "size": 0 if is_dir else stat.st_size,
        "size_display": "" if is_dir else _fmt_size(stat.st_size),
        "mtime": datetime.fromtimestamp(stat.st_mtime).strftime("%Y-%m-%d %H:%M:%S"),
        "mtime_ts": stat.st_mtime,
        "extension": "" if is_dir else (p.suffix.lstrip('.') or ""),
        "is_symlink": is_symlink,
    }


def _walk_entries(target: Path, *, recursive: bool, max_depth: int) -> list[Path]:
    """收集 target 下的条目。非递归只看一层；递归时以 max_depth 为硬上限。"""
    depth_limit = max_depth if recursive else 1
    result: list[Path] = []

    def visit(cur: Path, depth: int) -> None:
        try:
            entries = list(cur.iterdir())
        except (PermissionError, OSError):
            return
        for e in entries:
            if _is_hidden(e.name):
                continue
            result.append(e)
            if e.is_dir() and not e.is_symlink() and depth < depth_limit:
                visit(e, depth + 1)

    visit(target, 1)
    return result


def _sort_and_paginate(
    infos: list[dict],
    *,
    sort_by: str,
    order: str,
    page: int,
    page_size: int,
) -> tuple[list[dict], int]:
    key_map = {
        "name": lambda x: x["name"].lower(),
        "size": lambda x: x["size"],
        "mtime": lambda x: x["mtime_ts"],
    }
    sort_key = key_map.get(sort_by, key_map["name"])
    reverse = (order == "desc")

    # 稳定排序：先按主键排，再让目录置顶（目录内部和文件内部都保留主键顺序）
    infos.sort(key=sort_key, reverse=reverse)
    infos.sort(key=lambda x: x["type"] != "directory")

    total = len(infos)
    start = (page - 1) * page_size
    end = start + page_size
    return infos[start:end], total


def _content_disposition(filename: str, *, attachment: bool) -> str:
    """构造 RFC 5987 兼容的 Content-Disposition，中文文件名也不会乱码。"""
    prefix = "attachment" if attachment else "inline"
    ascii_fallback = filename.encode("ascii", "ignore").decode("ascii") or "file"
    quoted = quote(filename, safe="")
    return f'{prefix}; filename="{ascii_fallback}"; filename*=UTF-8\'\'{quoted}'


def create_file_router(
    sandbox_workspace: str,
    api_path: str,
    *,
    upload_enabled: bool = False,
    allow_empty_session: bool = False,
) -> APIRouter:
    router = APIRouter()
    base = Path(sandbox_workspace)

    prefix = api_path.rstrip("/")
    list_path = f"{prefix}/files/list"
    read_path = f"{prefix}/files/read"
    download_path = f"{prefix}/files/download"
    upload_path = f"{prefix}/files/upload"
    serve_path = f"{prefix}/files/serve/{{file_path:path}}"

    @router.post(list_path)
    async def files_list(req: FileListRequest):
        root = _resolve_root(base, req.session_id, allow_empty=allow_empty_session)
        if not root.is_dir():
            return {
                "files": [],
                "cwd": "/",
                "exists": False,
                "total": 0,
                "page": req.page,
                "page_size": req.page_size,
            }
        target = _safe_path(root, req.dir)
        if not target.is_dir():
            raise HTTPException(status_code=404, detail="目录不存在")

        try:
            entries = _walk_entries(target, recursive=req.recursive, max_depth=req.max_depth)
        except PermissionError:
            raise HTTPException(status_code=403, detail="无权访问该目录")

        infos: list[dict] = []
        for entry in entries:
            try:
                infos.append(_build_file_info(entry, root))
            except (PermissionError, OSError):
                continue

        page_items, total = _sort_and_paginate(
            infos,
            sort_by=req.sort_by,
            order=req.order,
            page=req.page,
            page_size=req.page_size,
        )

        cwd = "/" + str(target.relative_to(root))
        if cwd == "/.":
            cwd = "/"

        return {
            "files": page_items,
            "cwd": cwd,
            "exists": True,
            "total": total,
            "page": req.page,
            "page_size": req.page_size,
        }

    @router.post(read_path)
    async def files_read(req: FileReadRequest):
        root = _resolve_root(base, req.session_id, allow_empty=allow_empty_session)
        target = _safe_path(root, req.path)
        if not target.is_file():
            raise HTTPException(status_code=404, detail="文件不存在")

        stat = target.stat()
        if stat.st_size > MAX_INLINE_SIZE:
            raise HTTPException(status_code=413, detail="文件过大，请使用下载接口")

        mime = mimetypes.guess_type(str(target))[0] or 'application/octet-stream'

        if _is_text_mime(mime):
            raw = target.read_bytes()
            for enc in ("utf-8", "gbk"):
                try:
                    content = raw.decode(enc)
                except UnicodeDecodeError:
                    continue
                return {
                    "content": content,
                    "mime": mime,
                    "size": stat.st_size,
                    "encoding": enc,
                    "name": target.name,
                }
            content = base64.b64encode(raw).decode('ascii')
            return {
                "content": content,
                "mime": mime,
                "size": stat.st_size,
                "encoding": "base64",
                "name": target.name,
            }

        content = base64.b64encode(target.read_bytes()).decode('ascii')
        return {
            "content": content,
            "mime": mime,
            "size": stat.st_size,
            "encoding": "base64",
            "name": target.name,
        }

    @router.post(download_path)
    async def files_download(req: FileDownloadRequest):
        root = _resolve_root(base, req.session_id, allow_empty=allow_empty_session)
        target = _safe_path(root, req.path)
        if not target.is_file():
            raise HTTPException(status_code=404, detail="文件不存在")

        mime = mimetypes.guess_type(str(target))[0] or 'application/octet-stream'
        # FileResponse 支持 Range，断点续传/大文件都 OK
        return FileResponse(
            target,
            media_type=mime,
            headers={"Content-Disposition": _content_disposition(target.name, attachment=True)},
        )

    if upload_enabled:
        @router.post(upload_path)
        async def files_upload(
            files: List[UploadFile] = File(...),
            session_id: str = Form(""),
            dir: str = Form("/"),
        ):
            root = _resolve_root_or_create(base, session_id, allow_empty=allow_empty_session)
            target_dir = _safe_path(root, dir)
            target_dir.mkdir(parents=True, exist_ok=True)

            uploaded: list[dict] = []
            skipped: list[dict] = []
            for f in files:
                if not f.filename:
                    skipped.append({"name": "", "reason": "empty_filename"})
                    continue
                safe_name = Path(f.filename).name
                if not safe_name:
                    skipped.append({"name": f.filename, "reason": "invalid_name"})
                    continue
                if safe_name.startswith('.'):
                    skipped.append({"name": safe_name, "reason": "hidden_name"})
                    continue

                dest = target_dir / safe_name
                size = 0
                with open(dest, 'wb') as out:
                    while True:
                        chunk = await f.read(64 * 1024)
                        if not chunk:
                            break
                        size += len(chunk)
                        if size > MAX_UPLOAD_SIZE:
                            out.close()
                            dest.unlink(missing_ok=True)
                            raise HTTPException(
                                status_code=413,
                                detail=f"文件 {safe_name} 超过大小限制 ({_fmt_size(MAX_UPLOAD_SIZE)})",
                            )
                        out.write(chunk)

                rel = str(dest.relative_to(root))
                uploaded.append({"name": safe_name, "path": "/" + rel, "size": size})

            return {"uploaded": uploaded, "skipped": skipped, "session_id": session_id}

    @router.get(serve_path)
    async def files_serve(file_path: str, sid: str = Query("")):
        root = _resolve_root(base, sid, allow_empty=allow_empty_session)
        target = _safe_path(root, "/" + file_path)
        if not target.is_file():
            raise HTTPException(status_code=404, detail="文件不存在")
        mime = mimetypes.guess_type(str(target))[0] or 'application/octet-stream'
        return FileResponse(
            target,
            media_type=mime,
            headers={"Content-Disposition": _content_disposition(target.name, attachment=False)},
        )

    return router


def publish_file_server(
    app: FastAPI,
    sandbox_workspace: str,
    path: str = "/alphadata",
    *,
    upload_enabled: bool = False,
    allow_empty_session: bool = False,
) -> None:
    """
    将文件服务路由挂载到已有的 FastAPI 应用上。

    Args:
        app: FastAPI 应用实例
        sandbox_workspace: 沙箱宿主机工作目录
        path: API 基础路径（与 APIPublisherConfig.path 一致）
        upload_enabled: 是否暴露 POST /files/upload，默认 False（只读）
        allow_empty_session: 是否允许 session_id 为空回退到 workspace 根目录，默认 False
    """
    ws = Path(sandbox_workspace)
    if not ws.exists():
        logger.warning(
            f"sandbox_workspace 路径不存在: {sandbox_workspace}，文件服务仍将挂载（目录可能稍后创建）"
        )

    router = create_file_router(
        sandbox_workspace,
        path,
        upload_enabled=upload_enabled,
        allow_empty_session=allow_empty_session,
    )
    app.include_router(router)
    routes = "list|read|download" + ("|upload" if upload_enabled else "")
    logger.info(
        f"文件服务已挂载: POST {path}/files/{{{routes}}}, "
        f"GET {path}/files/serve/*, workspace={sandbox_workspace}, "
        f"upload_enabled={upload_enabled}, allow_empty_session={allow_empty_session}"
    )
