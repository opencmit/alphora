import logging
import mimetypes
import base64
import os
from datetime import datetime
from pathlib import Path
from typing import Optional, List

from fastapi import FastAPI, APIRouter, HTTPException, Query, UploadFile, File, Form
from fastapi.responses import StreamingResponse, FileResponse
from pydantic import BaseModel

logger = logging.getLogger(__name__)

HIDDEN_PATTERNS = {'.git', '__pycache__', '.DS_Store', 'node_modules', '.alphora_mnt_'}

TEXT_MIMES = {
    'text', 'application/json', 'application/xml', 'application/javascript',
    'application/x-yaml', 'application/toml', 'application/x-sh',
    'application/sql', 'application/xhtml+xml', 'application/x-httpd-php',
}

MAX_INLINE_SIZE = 50 * 1024 * 1024  # 50 MB
MAX_UPLOAD_SIZE = 100 * 1024 * 1024  # 100 MB per file


class FileListRequest(BaseModel):
    session_id: str = ""
    dir: str = "/"


class FileReadRequest(BaseModel):
    session_id: str = ""
    path: str


class FileDownloadRequest(BaseModel):
    session_id: str = ""
    path: str


def _find_session_dir(base: Path, session_id: str) -> Path | None:
    """在 base 及其一级子目录中查找 session_id 目录。

    支持两种目录结构：
    - 扁平结构：{base}/{session_id}/
    - 多用户结构：{base}/{user_id}/{session_id}/
    """
    direct = base / session_id
    if direct.is_dir():
        return direct.resolve()
    try:
        for sub in base.iterdir():
            if sub.is_dir() and not sub.name.startswith('.'):
                candidate = sub / session_id
                if candidate.is_dir():
                    return candidate.resolve()
    except (PermissionError, OSError):
        pass
    return None


def _resolve_root(base: Path, session_id: str) -> Path:
    if session_id:
        found = _find_session_dir(base, session_id)
        return found if found else (base / session_id).resolve()
    return base.resolve()


def _resolve_root_or_create(base: Path, session_id: str) -> Path:
    """Like _resolve_root but creates the session directory if it doesn't exist."""
    if session_id:
        found = _find_session_dir(base, session_id)
        if found:
            return found
        session_dir = base / session_id
        session_dir.mkdir(parents=True, exist_ok=True)
        return session_dir.resolve()
    base.mkdir(parents=True, exist_ok=True)
    return base.resolve()


def _safe_path(root: Path, rel: str) -> Path:
    cleaned = rel.lstrip("/")
    target = (root / cleaned).resolve()
    root_str = str(root)
    if not str(target).startswith(root_str):
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
    for unit in ('B', 'KB', 'MB', 'GB'):
        if n < 1024:
            return f"{n:.1f} {unit}" if unit != 'B' else f"{n} {unit}"
        n /= 1024
    return f"{n:.1f} TB"


def _build_file_info(p: Path, root: Path) -> dict:
    stat = p.stat()
    is_dir = p.is_dir()
    rel = str(p.relative_to(root))
    return {
        "name": p.name,
        "path": "/" + rel,
        "type": "directory" if is_dir else "file",
        "size": 0 if is_dir else stat.st_size,
        "size_display": "" if is_dir else _fmt_size(stat.st_size),
        "mtime": datetime.fromtimestamp(stat.st_mtime).strftime("%Y-%m-%d %H:%M:%S"),
        "extension": "" if is_dir else (p.suffix.lstrip('.') or ""),
    }


def create_file_router(sandbox_workspace: str, api_path: str) -> APIRouter:
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
        root = _resolve_root(base, req.session_id)
        if not root.is_dir():
            return {"files": [], "cwd": "/", "exists": False}
        target = _safe_path(root, req.dir)
        if not target.is_dir():
            raise HTTPException(status_code=404, detail="目录不存在")

        items = []
        try:
            entries = sorted(target.iterdir(), key=lambda x: (not x.is_dir(), x.name.lower()))
        except PermissionError:
            raise HTTPException(status_code=403, detail="无权访问该目录")

        for entry in entries:
            if _is_hidden(entry.name):
                continue
            try:
                items.append(_build_file_info(entry, root))
            except (PermissionError, OSError):
                continue

        cwd = "/" + str(target.relative_to(root))
        if cwd == "/.":
            cwd = "/"

        return {"files": items, "cwd": cwd, "exists": True}

    @router.post(read_path)
    async def files_read(req: FileReadRequest):
        root = _resolve_root(base, req.session_id)
        target = _safe_path(root, req.path)
        if not target.is_file():
            raise HTTPException(status_code=404, detail="文件不存在")

        stat = target.stat()
        if stat.st_size > MAX_INLINE_SIZE:
            raise HTTPException(status_code=413, detail="文件过大，请使用下载接口")

        mime = mimetypes.guess_type(str(target))[0] or 'application/octet-stream'

        if _is_text_mime(mime):
            try:
                content = target.read_text(encoding='utf-8')
            except UnicodeDecodeError:
                content = base64.b64encode(target.read_bytes()).decode('ascii')
                return {
                    "content": content,
                    "mime": mime,
                    "size": stat.st_size,
                    "encoding": "base64",
                    "name": target.name,
                }
            return {
                "content": content,
                "mime": mime,
                "size": stat.st_size,
                "encoding": "utf-8",
                "name": target.name,
            }
        else:
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
        root = _resolve_root(base, req.session_id)
        target = _safe_path(root, req.path)
        if not target.is_file():
            raise HTTPException(status_code=404, detail="文件不存在")

        mime = mimetypes.guess_type(str(target))[0] or 'application/octet-stream'

        def _iter_file():
            with open(target, 'rb') as f:
                while True:
                    chunk = f.read(64 * 1024)
                    if not chunk:
                        break
                    yield chunk

        return StreamingResponse(
            _iter_file(),
            media_type=mime,
            headers={
                "Content-Disposition": f'attachment; filename="{target.name}"',
                "Content-Length": str(target.stat().st_size),
            }
        )

    @router.post(upload_path)
    async def files_upload(
        files: List[UploadFile] = File(...),
        session_id: str = Form(""),
        dir: str = Form("/"),
    ):
        root = _resolve_root_or_create(base, session_id)
        target_dir = _safe_path(root, dir)
        target_dir.mkdir(parents=True, exist_ok=True)

        uploaded = []
        for f in files:
            if not f.filename:
                continue
            safe_name = Path(f.filename).name
            if not safe_name or safe_name.startswith('.'):
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
                        raise HTTPException(status_code=413, detail=f"文件 {safe_name} 超过大小限制 ({_fmt_size(MAX_UPLOAD_SIZE)})")
                    out.write(chunk)

            rel = str(dest.relative_to(root))
            uploaded.append({"name": safe_name, "path": "/" + rel, "size": size})

        return {"uploaded": uploaded, "session_id": session_id}

    @router.get(serve_path)
    async def files_serve(file_path: str, sid: str = Query("")):
        root = _resolve_root(base, sid)
        target = _safe_path(root, "/" + file_path)
        if not target.is_file():
            raise HTTPException(status_code=404, detail="文件不存在")
        mime = mimetypes.guess_type(str(target))[0] or 'application/octet-stream'
        return FileResponse(target, media_type=mime)

    return router


def publish_file_server(app: FastAPI, sandbox_workspace: str, path: str = "/alphadata") -> None:
    """
    将文件服务路由挂载到已有的 FastAPI 应用上。

    Args:
        app: FastAPI 应用实例
        sandbox_workspace: 沙箱宿主机工作目录
        path: API 基础路径（与 APIPublisherConfig.path 一致）
    """
    ws = Path(sandbox_workspace)
    if not ws.exists():
        logger.warning(f"sandbox_workspace 路径不存在: {sandbox_workspace}，文件服务仍将挂载（目录可能稍后创建）")

    router = create_file_router(sandbox_workspace, path)
    app.include_router(router)
    logger.info(f"文件服务已挂载: POST {path}/files/{{list|read|download|upload}}, GET {path}/files/serve/*, workspace={sandbox_workspace}")
