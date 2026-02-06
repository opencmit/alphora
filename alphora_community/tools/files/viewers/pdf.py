"""
PDF 文件查看器 - 处理 .pdf 文件
"""
import os
from typing import Optional, List, Dict, Any, Tuple

from ..utils.common import get_file_info, truncate_text


class PDFViewer:
    """PDF 文件查看器"""
    
    SUPPORTED_EXTENSIONS = {'.pdf'}
    
    def __init__(self, file_path: str):
        """
        初始化查看器
        
        Args:
            file_path: 文件路径
        """
        self.file_path = file_path
        self.file_info = get_file_info(file_path)
        self.ext = self.file_info['extension']
        
    def view(
        self,
        purpose: str = "preview",
        keyword: Optional[str] = None,
        max_lines: int = 100,
        page_number: Optional[int] = None,
    ) -> str:
        """
        查看 PDF 内容
        
        Args:
            purpose: 查看目的（preview/structure/search）
            keyword: 搜索关键词
            max_lines: 最大返回行数
            page_number: 指定页码（从1开始）
            
        Returns:
            格式化的 PDF 内容字符串
        """
        # 智能参数推断
        purpose, warnings = self._infer_and_validate_params(purpose, keyword, page_number)
        
        # 尝试使用 PyMuPDF
        try:
            import fitz
            return self._view_with_pymupdf(purpose, keyword, max_lines, page_number, warnings)
        except ImportError:
            pass
        
        # 尝试使用 pdfplumber
        try:
            import pdfplumber
            return self._view_with_pdfplumber(purpose, keyword, max_lines, page_number, warnings)
        except ImportError:
            return "❌ 需要安装 PDF 处理库：pip install pymupdf 或 pip install pdfplumber"
    
    def _infer_and_validate_params(
        self,
        purpose: str,
        keyword: Optional[str],
        page_number: Optional[int]
    ) -> Tuple[str, List[str]]:
        """智能推断和校验参数"""
        warnings = []
        
        if keyword and purpose != "search":
            warnings.append(f"⚠️ 检测到 keyword='{keyword}'，已自动切换为 search 模式")
            purpose = "search"
        
        if purpose == "search" and not keyword:
            warnings.append("⚠️ search 模式需要 keyword 参数，已切换为 preview 模式")
            purpose = "preview"
            
        return purpose, warnings
    
    def _format_header(self, total_pages: int, warnings: List[str]) -> str:
        """格式化文件头信息"""
        lines = [
            f"📕 文件: {self.file_info['name']}",
            f"📦 大小: {self.file_info['size_human']}",
            f"📋 页数: {total_pages}",
        ]
        
        if warnings:
            lines.append("")
            for w in warnings:
                lines.append(w)
        
        return '\n'.join(lines)
    
    # ==================== PyMuPDF 实现 ====================
    
    def _view_with_pymupdf(
        self,
        purpose: str,
        keyword: Optional[str],
        max_lines: int,
        page_number: Optional[int],
        warnings: List[str]
    ) -> str:
        """使用 PyMuPDF 处理 PDF"""
        import fitz
        
        try:
            doc = fitz.open(self.file_path)
        except Exception as e:
            return f"❌ 无法打开 PDF: {e}"
        
        total_pages = len(doc)
        
        try:
            if purpose == "structure":
                return self._get_structure_pymupdf(doc, total_pages, warnings)
            elif purpose == "search":
                return self._search_pymupdf(doc, keyword, max_lines, warnings)
            elif page_number is not None:
                return self._view_page_pymupdf(doc, page_number, total_pages, warnings)
            else:  # preview
                return self._preview_pymupdf(doc, total_pages, max_lines, warnings)
        finally:
            doc.close()
    
    def _get_structure_pymupdf(self, doc, total_pages: int, warnings: List[str]) -> str:
        """获取 PDF 结构（PyMuPDF）"""
        lines = [
            self._format_header(total_pages, warnings),
            ""
        ]
        
        # 获取目录
        toc = doc.get_toc()
        if toc:
            lines.append("【目录结构】")
            for level, title, page in toc[:30]:
                indent = "  " * (level - 1)
                lines.append(f"{indent}• {title} (第{page}页)")
            
            if len(toc) > 30:
                lines.append(f"  ... 还有 {len(toc) - 30} 个目录项")
        else:
            lines.append("【目录结构】")
            lines.append("  (PDF 没有目录信息)")
        
        # 各页概览
        lines.append("")
        lines.append("【各页概览】")
        for i in range(min(15, total_pages)):
            page = doc[i]
            text = page.get_text()
            char_count = len(text)
            # 获取首行作为预览
            first_line = text.split('\n')[0].strip()[:50] if text.strip() else "(无文本)"
            lines.append(f"  第{i+1}页: 约{char_count}字 - {first_line}...")
        
        if total_pages > 15:
            lines.append(f"  ... 还有 {total_pages - 15} 页")
        
        return '\n'.join(lines)
    
    def _preview_pymupdf(
        self,
        doc,
        total_pages: int,
        max_lines: int,
        warnings: List[str]
    ) -> str:
        """预览 PDF 内容（PyMuPDF）"""
        lines = [
            self._format_header(total_pages, warnings),
            "",
            "【内容预览】"
        ]
        
        char_count = 0
        max_chars = 4000  # 限制总字符数
        pages_shown = 0
        
        for i, page in enumerate(doc):
            if char_count > max_chars:
                break
            
            text = page.get_text().strip()
            if text:
                lines.append(f"\n━━━ 第{i+1}页 ━━━")
                # 限制每页显示长度
                page_text = text[:1500] if len(text) > 1500 else text
                lines.append(page_text)
                char_count += len(page_text)
                pages_shown = i + 1
        
        if pages_shown < total_pages:
            lines.append(f"\n... 还有 {total_pages - pages_shown} 页未显示")
        
        return '\n'.join(lines)
    
    def _view_page_pymupdf(
        self,
        doc,
        page_number: int,
        total_pages: int,
        warnings: List[str]
    ) -> str:
        """查看指定页（PyMuPDF）"""
        if page_number < 1 or page_number > total_pages:
            return f"❌ 页码超出范围。该 PDF 共有 {total_pages} 页，请输入 1-{total_pages} 之间的数字"
        
        page = doc[page_number - 1]
        text = page.get_text()
        
        lines = [
            f"📕 文件: {self.file_info['name']}",
            f"📋 第 {page_number}/{total_pages} 页",
        ]
        
        if warnings:
            lines.append("")
            for w in warnings:
                lines.append(w)
        
        lines.append("")
        lines.append("【页面内容】")
        
        if text.strip():
            # 限制长度
            if len(text) > 5000:
                lines.append(text[:5000])
                lines.append(f"\n... 本页还有约 {len(text) - 5000} 字未显示")
            else:
                lines.append(text)
        else:
            lines.append("(此页没有可提取的文本，可能是扫描图片)")
        
        # 导航提示
        lines.append("")
        if page_number > 1:
            lines.append(f"💡 上一页: page_number={page_number - 1}")
        if page_number < total_pages:
            lines.append(f"💡 下一页: page_number={page_number + 1}")
        
        return '\n'.join(lines)
    
    def _search_pymupdf(
        self,
        doc,
        keyword: str,
        max_lines: int,
        warnings: List[str]
    ) -> str:
        """搜索 PDF 内容（PyMuPDF）"""
        results = []
        keyword_lower = keyword.lower()
        
        for i, page in enumerate(doc, 1):
            text = page.get_text()
            if keyword_lower in text.lower():
                # 找到关键词上下文
                idx = text.lower().find(keyword_lower)
                start = max(0, idx - 50)
                end = min(len(text), idx + len(keyword) + 80)
                context = text[start:end].replace('\n', ' ')
                if start > 0:
                    context = "..." + context
                if end < len(text):
                    context = context + "..."
                
                results.append({
                    'page': i,
                    'content': context
                })
        
        lines = [
            self._format_header(len(doc), warnings),
            "",
            f"🔍 搜索关键词: '{keyword}'",
            f"📋 找到 {len(results)} 页包含匹配"
        ]
        
        if not results:
            lines.append("")
            lines.append(f"未找到包含 '{keyword}' 的内容")
            return '\n'.join(lines)
        
        lines.append("")
        
        for i, r in enumerate(results[:max_lines], 1):
            lines.append(f"[第{r['page']}页] {r['content']}")
        
        if len(results) > max_lines:
            lines.append(f"\n... 还有 {len(results) - max_lines} 处匹配未显示")
        
        return '\n'.join(lines)
    
    # ==================== pdfplumber 实现（备用） ====================
    
    def _view_with_pdfplumber(
        self,
        purpose: str,
        keyword: Optional[str],
        max_lines: int,
        page_number: Optional[int],
        warnings: List[str]
    ) -> str:
        """使用 pdfplumber 处理 PDF（备用方案）"""
        import pdfplumber
        
        try:
            with pdfplumber.open(self.file_path) as pdf:
                total_pages = len(pdf.pages)
                
                if purpose == "structure":
                    return self._get_structure_pdfplumber(pdf, total_pages, warnings)
                elif purpose == "search":
                    return self._search_pdfplumber(pdf, keyword, max_lines, warnings)
                elif page_number is not None:
                    return self._view_page_pdfplumber(pdf, page_number, total_pages, warnings)
                else:  # preview
                    return self._preview_pdfplumber(pdf, total_pages, max_lines, warnings)
        except Exception as e:
            return f"❌ 无法打开 PDF: {e}"
    
    def _get_structure_pdfplumber(self, pdf, total_pages: int, warnings: List[str]) -> str:
        """获取 PDF 结构（pdfplumber）"""
        lines = [
            self._format_header(total_pages, warnings),
            "",
            "【各页概览】"
        ]
        
        for i, page in enumerate(pdf.pages[:15], 1):
            text = page.extract_text() or ""
            char_count = len(text)
            first_line = text.split('\n')[0].strip()[:50] if text.strip() else "(无文本)"
            lines.append(f"  第{i}页: 约{char_count}字 - {first_line}...")
        
        if total_pages > 15:
            lines.append(f"  ... 还有 {total_pages - 15} 页")
        
        return '\n'.join(lines)
    
    def _preview_pdfplumber(
        self,
        pdf,
        total_pages: int,
        max_lines: int,
        warnings: List[str]
    ) -> str:
        """预览 PDF 内容（pdfplumber）"""
        lines = [
            self._format_header(total_pages, warnings),
            "",
            "【内容预览】"
        ]
        
        char_count = 0
        max_chars = 4000
        
        for i, page in enumerate(pdf.pages[:10], 1):
            if char_count > max_chars:
                break
            
            text = page.extract_text()
            if text and text.strip():
                lines.append(f"\n━━━ 第{i}页 ━━━")
                page_text = text[:1500] if len(text) > 1500 else text
                lines.append(page_text)
                char_count += len(page_text)
        
        return '\n'.join(lines)
    
    def _view_page_pdfplumber(
        self,
        pdf,
        page_number: int,
        total_pages: int,
        warnings: List[str]
    ) -> str:
        """查看指定页（pdfplumber）"""
        if page_number < 1 or page_number > total_pages:
            return f"❌ 页码超出范围。该 PDF 共有 {total_pages} 页"
        
        page = pdf.pages[page_number - 1]
        text = page.extract_text() or "(无法提取文本)"
        
        lines = [
            f"📕 文件: {self.file_info['name']}",
            f"📋 第 {page_number}/{total_pages} 页",
        ]
        
        if warnings:
            for w in warnings:
                lines.append(w)
        
        lines.append("")
        lines.append(text[:5000])
        
        return '\n'.join(lines)
    
    def _search_pdfplumber(
        self,
        pdf,
        keyword: str,
        max_lines: int,
        warnings: List[str]
    ) -> str:
        """搜索 PDF 内容（pdfplumber）"""
        results = []
        keyword_lower = keyword.lower()
        
        for i, page in enumerate(pdf.pages, 1):
            text = page.extract_text() or ""
            if keyword_lower in text.lower():
                idx = text.lower().find(keyword_lower)
                start = max(0, idx - 50)
                end = min(len(text), idx + len(keyword) + 80)
                context = text[start:end].replace('\n', ' ')
                
                results.append({
                    'page': i,
                    'content': context
                })
        
        lines = [
            self._format_header(len(pdf.pages), warnings),
            "",
            f"🔍 搜索: '{keyword}' | 找到 {len(results)} 处"
        ]
        
        if results:
            lines.append("")
            for r in results[:max_lines]:
                lines.append(f"[第{r['page']}页] ...{r['content']}...")
        else:
            lines.append(f"\n未找到包含 '{keyword}' 的内容")
        
        return '\n'.join(lines)
