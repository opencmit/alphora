"""
FileViewerAgent - 通用文件查看器 Agent

提供给 AI Agent 使用的文件查看工具，支持多种文件格式的智能查看。

主要特性：
1. 智能参数推断 - 有 keyword 自动切换 search 模式，有行范围自动切换 range 模式
2. 清晰的输出格式 - 表格类文件显示行号和列字母坐标
3. 完善的错误提示 - 参数校验、文件不存在提示等
4. 多种文件格式支持 - Excel、CSV、Word、PPT、PDF、文本等
"""
import os
from typing import Optional

from alphora.sandbox import Sandbox

from .viewers.tabular import TabularViewer
from .viewers.document import DocumentViewer
from .viewers.presentation import PresentationViewer
from .viewers.pdf import PDFViewer
from .viewers.text import TextViewer
from .utils.common import find_file, list_available_files, get_file_info


class FileViewerAgent:
    """
    通用文件查看器 Agent

    为 AI Agent 提供统一的文件查看接口，支持多种文件格式。

    使用示例：
        agent = FileViewerAgent(base_dir="/path/to/sandbox")

        # 预览 Excel 文件
        result = agent.view_file("销售数据.xlsx")

        # 搜索包含"北京"的行
        result = agent.view_file("销售数据.xlsx", keyword="北京")

        # 查看 Excel 结构
        result = agent.view_file("销售数据.xlsx", purpose="structure")
    """

    # 文件类型分类
    TABULAR_EXTENSIONS = TabularViewer.SUPPORTED_EXTENSIONS
    DOCUMENT_EXTENSIONS = DocumentViewer.SUPPORTED_EXTENSIONS
    PRESENTATION_EXTENSIONS = PresentationViewer.SUPPORTED_EXTENSIONS
    PDF_EXTENSIONS = PDFViewer.SUPPORTED_EXTENSIONS
    TEXT_EXTENSIONS = TextViewer.SUPPORTED_EXTENSIONS

    def __init__(self, sandbox: Sandbox, **kwargs):
        """
        初始化 FileViewerAgent

        Args:
            sandbox: Sandbox
        """
        super().__init__(**kwargs)
        self._sandbox = sandbox

    @property
    def base_dir(self) -> str:
        """获取基础目录"""
        if self._sandbox:
            return str(self._sandbox.workspace_path)

        raise ValueError("Sandbox未传入")

    async def view_file(
            self,
            file_name: str,
            purpose: str = "preview",
            keyword: Optional[str] = None,
            max_lines: int = 50,
            columns: Optional[str] = None,
            start_row: Optional[int] = None,
            end_row: Optional[int] = None,
            sheet_name: Optional[str] = None,
            page_number: Optional[int] = None,
    ) -> str:
        """
        通用文件查看工具，支持查看各种格式的文件内容。

        【核心功能】
        此工具会自动根据参数智能推断查看模式：
        - 提供了 keyword → 自动进入搜索模式
        - 提供了 start_row/end_row → 自动进入范围查看模式
        - 无额外参数 → 预览模式

        【支持的文件格式】
        - 表格类：Excel (.xlsx/.xls)、CSV、TSV
        - 文档类：Word (.docx)、PDF、Markdown、TXT
        - 演示类：PowerPoint (.pptx)
        - 数据类：JSON、XML、YAML
        - 代码类：Python、JavaScript、SQL、HTML 等

        Args:
            file_name (str): 要查看的文件名。必填参数。
                支持模糊匹配，可只提供部分文件名。

            purpose (str): 查看目的。可选值：
                - "preview"：预览文件内容（默认）
                - "structure"：查看文件结构（列名、类型、目录等）
                - "search"：搜索关键词（自动根据 keyword 推断）
                - "range"：查看指定范围（自动根据 start_row/end_row 推断）
                - "stats"：统计信息（仅表格类文件）

            keyword (str): 搜索关键词。
                ⚠️ 提供此参数会自动切换为 search 模式，无需设置 purpose="search"

            max_lines (int): 最大返回行数，默认 100。

            columns (str): 【表格类】要查看的列，逗号分隔。
                示例："姓名,年龄" 或 "A,B,C"

            start_row (int): 【表格/文本】起始行号（从1开始）。
                ⚠️ 提供此参数会自动切换为 range 模式

            end_row (int): 【表格/文本】结束行号。
                填负数如 -10 表示最后 10 行。

            sheet_name (str): 【Excel】工作表名称。
                - 不填：查看默认工作表
                - 填 "__all__"：列出所有工作表

            page_number (int): 【PPT/PDF】页码（从1开始）。

        Returns:
            str: 格式化的文件内容。
                - 表格类文件返回带行号和列字母的 CSV 格式
                - 其他文件返回结构化文本

        Examples:
            # 预览 Excel（自动显示所有 Sheet 名称）
            >>> view_file("销售数据.xlsx")

            # 搜索"北京"（自动进入搜索模式，无需设置 purpose）
            >>> view_file("销售数据.xlsx", keyword="北京")

            # 查看 Excel 结构
            >>> view_file("销售数据.xlsx", purpose="structure")

            # 查看第 10-20 行
            >>> view_file("销售数据.xlsx", start_row=10, end_row=20)

            # 查看最后 10 行
            >>> view_file("销售数据.xlsx", end_row=-10)

            # 查看指定 Sheet
            >>> view_file("销售数据.xlsx", sheet_name="月度汇总")

            # 列出所有 Sheet
            >>> view_file("销售数据.xlsx", sheet_name="__all__")

            # 查看 PDF 第 5 页
            >>> view_file("报告.pdf", page_number=5)

            # 在 Word 中搜索
            >>> view_file("合同.docx", keyword="甲方")
        """
        # 查找文件
        try:
            base = self.base_dir
        except ValueError as e:
            return f"❌ 配置错误: {e}"

        file_path = find_file(base, file_name)
        if not file_path:
            available = list_available_files(base)
            return f"❌ 找不到文件 '{file_name}'\n\n当前目录下的文件：\n{available}"

        # 获取文件扩展名
        ext = os.path.splitext(file_path)[1].lower()

        # 根据文件类型分发到对应查看器
        try:
            if ext in self.TABULAR_EXTENSIONS:
                viewer = TabularViewer(file_path)
                contents = viewer.view(
                    purpose=purpose,
                    keyword=keyword,
                    max_rows=max_lines,
                    columns=columns,
                    start_row=start_row,
                    end_row=end_row,
                    sheet_name=sheet_name
                )

                # await self.stream.astream_message(content_type='stdout', content=contents)

                return contents

            elif ext in self.DOCUMENT_EXTENSIONS:
                viewer = DocumentViewer(file_path)
                contents = viewer.view(
                    purpose=purpose,
                    keyword=keyword,
                    max_lines=max_lines,
                    page_number=page_number
                )

                # await self.stream.astream_message(content_type='stdout', content=contents)

                return contents

            elif ext in self.PRESENTATION_EXTENSIONS:
                viewer = PresentationViewer(file_path)
                contents = viewer.view(
                    purpose=purpose,
                    keyword=keyword,
                    max_lines=max_lines,
                    page_number=page_number
                )

                # await self.stream.astream_message(content_type='stdout', content=contents)

                return contents

            elif ext in self.PDF_EXTENSIONS:
                viewer = PDFViewer(file_path)
                contents = viewer.view(
                    purpose=purpose,
                    keyword=keyword,
                    max_lines=max_lines,
                    page_number=page_number
                )

                # await self.stream.astream_message(content_type='stdout', content=contents)

                return contents

            elif ext in self.TEXT_EXTENSIONS:
                viewer = TextViewer(file_path)
                contents = viewer.view(
                    purpose=purpose,
                    keyword=keyword,
                    max_lines=max_lines,
                    start_row=start_row,
                    end_row=end_row
                )

                # await self.stream.astream_message(content_type='stdout', content=contents)

                return contents

            else:
                # 尝试作为文本文件处理
                try:
                    viewer = TextViewer(file_path)
                    result = viewer.view(
                        purpose=purpose,
                        keyword=keyword,
                        max_lines=max_lines,
                        start_row=start_row,
                        end_row=end_row
                    )
                    contents = f"⚠️ 未知文件类型 {ext}，尝试作为文本文件处理\n\n{result}"
                    # await self.stream.astream_message(content_type='stdout', content=contents)
                    return contents

                except Exception:
                    supported = ", ".join(sorted(
                        self.TABULAR_EXTENSIONS |
                        self.DOCUMENT_EXTENSIONS |
                        self.PRESENTATION_EXTENSIONS |
                        self.PDF_EXTENSIONS |
                        self.TEXT_EXTENSIONS
                    ))
                    contents = f"❌ 不支持的文件类型: {ext}\n\n支持的格式: {supported}"
                    # await self.stream.astream_message(content_type='stdout', content=contents)
                    return contents
        except Exception as e:
            contents = f"❌ 查看文件时出错: {str(e)}"
            # await self.stream.astream_message(content_type='stdout', content=contents)
            return contents

    def list_files(self, max_files: int = 50) -> str:
        """
        列出当前目录下的所有文件

        Args:
            max_files: 最大显示文件数

        Returns:
            格式化的文件列表
        """
        try:
            base = self.base_dir
        except ValueError as e:
            return f"❌ 配置错误: {e}"

        files = list_available_files(base, max_files)
        return f"📁 目录: {base}\n\n{files}"

    def get_file_info(self, file_name: str) -> str:
        """
        获取文件的基本信息

        Args:
            file_name: 文件名

        Returns:
            文件信息字符串
        """
        try:
            base = self.base_dir
        except ValueError as e:
            return f"❌ 配置错误: {e}"

        file_path = find_file(base, file_name)
        if not file_path:
            return f"❌ 找不到文件 '{file_name}'"

        info = get_file_info(file_path)

        lines = [
            f"📄 文件名: {info['name']}",
            f"📁 路径: {info['path']}",
            f"📦 大小: {info['size_human']}",
            f"🕐 修改时间: {info['modified_str']}",
            f"📋 类型: {info['extension']}",
        ]

        return '\n'.join(lines)
