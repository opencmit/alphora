"""
Exporter — 沙箱文件导出工具

将沙箱内的 Markdown 报告（含本地图片引用）转换为 PDF，
图片自动内嵌，用户下载 PDF 即可离线查看完整报告。
"""

from typing import TYPE_CHECKING

from alphora.sandbox.tools.exporter.md2pdf import run_md2pdf

if TYPE_CHECKING:
    from alphora.sandbox.sandbox import Sandbox

__all__ = ["markdown_to_pdf"]


async def markdown_to_pdf(
    sandbox: "Sandbox",
    md_path: str,
    output_path: str = "",
    title: str = "",
    page_size: str = "A4",
    timeout: int = 120,
) -> dict:
    """
    将沙箱内的 Markdown 文件转换为 PDF。

    自动将 Markdown 中引用的本地图片以 base64 内嵌到 PDF，
    解决用户下载报告后图片路径失效的问题。

    Args:
        sandbox:     Sandbox 实例
        md_path:     Markdown 文件路径（沙箱内），如 "report/report.md"
        output_path: PDF 输出路径，默认与 md 同名同目录（"report/report.pdf"）
        title:       PDF 标题，默认从 Markdown 的 H1 标题提取
        page_size:   页面大小 ("A4" / "A3" / "Letter" / "Legal")，默认 "A4"
        timeout:     转换超时（秒），默认 120

    Returns:
        {
            "success": bool,
            "pdf_path": str,
            "pdf_size": int,
            "pdf_size_human": str,
            "images_embedded": int,
            "title": str,
            "error": str,
        }
    """
    if not await _file_exists(sandbox, md_path):
        return {
            "success": False,
            "error": f"Markdown file not found: {md_path}",
        }

    try:
        result = await run_md2pdf(
            sandbox, md_path,
            output_path=output_path,
            title=title,
            page_size=page_size,
            timeout=timeout,
        )
        return {"success": True, "error": "", **result}
    except Exception as e:
        return {"success": False, "error": str(e)}


async def _file_exists(sandbox: "Sandbox", path: str) -> bool:
    try:
        return await sandbox.file_exists(path)
    except Exception:
        return False
