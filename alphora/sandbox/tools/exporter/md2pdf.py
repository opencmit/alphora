"""
Markdown → PDF 转换核心逻辑

在沙箱内执行转换脚本：读取 Markdown → 内嵌本地图片 → 生成 HTML → WeasyPrint 输出 PDF。
"""

import json
import logging
import textwrap
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from alphora.sandbox.sandbox import Sandbox

logger = logging.getLogger(__name__)

# WeasyPrint 在沙箱 Docker 镜像中预装，此脚本通过 sandbox.execute_code() 执行
_CONVERSION_SCRIPT = textwrap.dedent(r'''
import json, os, re, sys, base64

params = json.loads(sys.argv[1]) if len(sys.argv) > 1 else json.loads(input())

md_path     = params["md_path"]
output_path = params["output_path"]
title       = params.get("title", "")
page_size   = params.get("page_size", "A4")

MIME_MAP = {
    ".png": "image/png", ".jpg": "image/jpeg", ".jpeg": "image/jpeg",
    ".gif": "image/gif", ".svg": "image/svg+xml", ".webp": "image/webp",
    ".bmp": "image/bmp",
}

with open(md_path, "r", encoding="utf-8") as f:
    md_content = f.read()

if not title:
    m = re.search(r"^#\s+(.+)$", md_content, re.MULTILINE)
    title = m.group(1).strip() if m else "Report"

base_dir = os.path.dirname(os.path.abspath(md_path))
images_embedded = 0

def _embed_image(match):
    global images_embedded
    alt, path = match.group(1), match.group(2)
    if path.startswith(("http://", "https://", "data:")):
        return match.group(0)
    abs_path = path if os.path.isabs(path) else os.path.join(base_dir, path)
    if not os.path.isfile(abs_path):
        return match.group(0)
    ext = os.path.splitext(abs_path)[1].lower()
    mime = MIME_MAP.get(ext, "application/octet-stream")
    with open(abs_path, "rb") as img_f:
        b64 = base64.b64encode(img_f.read()).decode()
    images_embedded += 1
    return f"![{alt}](data:{mime};base64,{b64})"

md_content = re.sub(r"!\[([^\]]*)\]\(([^)]+)\)", _embed_image, md_content)

# Markdown -> HTML (with <img> tags from data URIs)
try:
    import markdown
    html_body = markdown.markdown(
        md_content,
        extensions=["tables", "fenced_code", "toc", "attr_list"],
        output_format="html5",
    )
except ImportError:
    # basic fallback
    html_body = md_content
    html_body = re.sub(r"^### (.+)$", r"<h3>\1</h3>", html_body, flags=re.MULTILINE)
    html_body = re.sub(r"^## (.+)$", r"<h2>\1</h2>", html_body, flags=re.MULTILINE)
    html_body = re.sub(r"^# (.+)$", r"<h1>\1</h1>", html_body, flags=re.MULTILINE)
    html_body = re.sub(r"\*\*(.+?)\*\*", r"<strong>\1</strong>", html_body)
    html_body = re.sub(r"\*(.+?)\*", r"<em>\1</em>", html_body)
    html_body = re.sub(
        r"!\[([^\]]*)\]\(([^)]+)\)",
        r'<img src="\2" alt="\1" style="max-width:100%">',
        html_body,
    )
    html_body = re.sub(r"\[([^\]]+)\]\(([^)]+)\)", r'<a href="\2">\1</a>', html_body)

PAGE_CSS = {
    "A4": "210mm 297mm",
    "A3": "297mm 420mm",
    "Letter": "8.5in 11in",
    "Legal": "8.5in 14in",
}.get(page_size, "210mm 297mm")

html = f"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="utf-8">
<title>{title}</title>
<style>
  @page {{
    size: {PAGE_CSS};
    margin: 2cm 1.8cm;
  }}
  body {{
    font-family: 'Source Han Sans CN', 'Noto Sans CJK SC', 'Noto Sans SC',
                 -apple-system, 'Helvetica Neue', Arial, sans-serif;
    font-size: 11pt;
    line-height: 1.8;
    color: #333;
  }}
  h1 {{
    border-bottom: 2px solid #2c3e50;
    padding-bottom: 0.3em;
    color: #2c3e50;
    font-size: 20pt;
    margin-top: 0;
  }}
  h2 {{
    border-bottom: 1px solid #eee;
    padding-bottom: 0.2em;
    margin-top: 1.5em;
    color: #34495e;
    font-size: 15pt;
  }}
  h3 {{ color: #555; font-size: 13pt; }}
  table {{
    border-collapse: collapse;
    width: 100%;
    margin: 1em 0;
    font-size: 10pt;
  }}
  th, td {{
    border: 1px solid #ddd;
    padding: 6px 10px;
    text-align: left;
  }}
  th {{ background: #f5f7fa; font-weight: 600; }}
  tr:nth-child(even) {{ background: #fafbfc; }}
  img {{
    max-width: 100%;
    height: auto;
    margin: 0.8em 0;
    border-radius: 4px;
  }}
  blockquote {{
    border-left: 4px solid #3498db;
    margin: 1em 0;
    padding: 0.5em 1em;
    background: #f8f9fa;
    color: #555;
  }}
  code {{
    background: #f0f0f0;
    padding: 2px 5px;
    border-radius: 3px;
    font-size: 0.9em;
    font-family: 'Courier New', monospace;
  }}
  pre {{
    background: #f5f5f5;
    padding: 0.8em;
    border-radius: 6px;
    overflow-x: auto;
    font-size: 9pt;
    line-height: 1.5;
  }}
  pre code {{ background: transparent; padding: 0; }}
  a {{ color: #3498db; text-decoration: none; }}
  ul, ol {{ padding-left: 1.5em; }}
  li {{ margin-bottom: 0.3em; }}
  hr {{ border: none; border-top: 1px solid #ddd; margin: 1.5em 0; }}
</style>
</head>
<body>
{html_body}
</body>
</html>"""

os.makedirs(os.path.dirname(os.path.abspath(output_path)), exist_ok=True)

from weasyprint import HTML as WeasyprintHTML
WeasyprintHTML(string=html, base_url=base_dir).write_pdf(output_path)

pdf_size = os.path.getsize(output_path)

result = {
    "pdf_path": output_path,
    "pdf_size": pdf_size,
    "images_embedded": images_embedded,
    "title": title,
}
print("__MD2PDF_RESULT__" + json.dumps(result, ensure_ascii=False))
''')


def _build_script(
    md_path: str,
    output_path: str,
    title: str,
    page_size: str,
) -> str:
    """构建在沙箱内执行的转换脚本。"""
    params = json.dumps({
        "md_path": md_path,
        "output_path": output_path,
        "title": title,
        "page_size": page_size,
    }, ensure_ascii=False)
    return f"import sys; sys.argv = ['md2pdf', {json.dumps(params)}]\n" + _CONVERSION_SCRIPT


def _human_size(n: int) -> str:
    for unit in ("B", "KB", "MB", "GB"):
        if abs(n) < 1024:
            return f"{n:.1f} {unit}"
        n /= 1024
    return f"{n:.1f} TB"


async def run_md2pdf(
    sandbox: "Sandbox",
    md_path: str,
    output_path: str = "",
    title: str = "",
    page_size: str = "A4",
    timeout: int = 120,
) -> dict:
    """
    在沙箱内将 Markdown 文件转换为 PDF。

    Args:
        sandbox:     Sandbox 实例
        md_path:     Markdown 文件路径（沙箱内）
        output_path: 输出 PDF 路径，默认与 md 同名
        title:       PDF 标题，默认从 Markdown H1 提取
        page_size:   页面大小 (A4 / A3 / Letter / Legal)
        timeout:     执行超时（秒）

    Returns:
        {
            "pdf_path": str,
            "pdf_size": int,
            "pdf_size_human": str,
            "images_embedded": int,
            "title": str,
        }
    """
    if not output_path:
        if md_path.lower().endswith(".md"):
            output_path = md_path[:-3] + ".pdf"
        elif md_path.lower().endswith(".markdown"):
            output_path = md_path[:-9] + ".pdf"
        else:
            output_path = md_path + ".pdf"

    script = _build_script(md_path, output_path, title, page_size)
    result = await sandbox.execute_code(script, timeout=timeout)

    if not result.success:
        error_msg = result.stderr.strip() or result.stdout.strip() or "Unknown error"
        raise RuntimeError(f"PDF conversion failed: {error_msg}")

    marker = "__MD2PDF_RESULT__"
    for line in result.stdout.splitlines():
        if line.startswith(marker):
            data = json.loads(line[len(marker):])
            data["pdf_size_human"] = _human_size(data["pdf_size"])
            return data

    raise RuntimeError(
        f"PDF conversion produced no result marker. stdout={result.stdout[:500]}, "
        f"stderr={result.stderr[:500]}"
    )
