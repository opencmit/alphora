"""
文本文件查看器 - 处理 txt/md/json/xml/yaml/代码等文件
"""
import os
import json
from typing import Optional, List, Dict, Any, Tuple

from ..utils.common import get_file_info, truncate_text


class TextViewer:
    """文本文件查看器"""
    
    SUPPORTED_EXTENSIONS = {
        '.txt', '.md', '.markdown',
        '.json', '.xml', '.yaml', '.yml',
        '.log', '.ini', '.cfg', '.conf',
        '.py', '.js', '.ts', '.html', '.css', '.sql',
        '.java', '.c', '.cpp', '.h', '.go', '.rs',
        '.sh', '.bash', '.zsh',
        '.env', '.gitignore', '.dockerfile'
    }
    
    # 代码文件扩展名
    CODE_EXTENSIONS = {
        '.py', '.js', '.ts', '.html', '.css', '.sql',
        '.java', '.c', '.cpp', '.h', '.go', '.rs',
        '.sh', '.bash', '.zsh'
    }
    
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
        start_row: Optional[int] = None,
        end_row: Optional[int] = None,
    ) -> str:
        """
        查看文本文件内容
        
        Args:
            purpose: 查看目的（preview/structure/search/range）
            keyword: 搜索关键词
            max_lines: 最大返回行数
            start_row: 起始行号（从1开始）
            end_row: 结束行号
            
        Returns:
            格式化的文件内容字符串
        """
        # 智能参数推断
        purpose, warnings = self._infer_and_validate_params(
            purpose, keyword, start_row, end_row
        )
        
        # 读取文件内容
        content, error = self._read_file()
        if error:
            return error
        
        lines = content.split('\n')
        total_lines = len(lines)
        
        # JSON 特殊处理
        if self.ext == '.json' and purpose == "structure":
            return self._get_json_structure(content, warnings)
        
        if purpose == "structure":
            return self._get_structure(lines, total_lines, warnings)
        elif purpose == "search":
            return self._search(lines, keyword, max_lines, warnings)
        elif purpose == "range":
            return self._get_range(lines, total_lines, start_row, end_row, max_lines, warnings)
        else:  # preview
            return self._preview(lines, total_lines, max_lines, warnings)
    
    def _infer_and_validate_params(
        self,
        purpose: str,
        keyword: Optional[str],
        start_row: Optional[int],
        end_row: Optional[int]
    ) -> Tuple[str, List[str]]:
        """智能推断和校验参数"""
        warnings = []
        
        if keyword and purpose != "search":
            warnings.append(f"⚠️ 检测到 keyword='{keyword}'，已自动切换为 search 模式")
            purpose = "search"
        
        if (start_row is not None or end_row is not None) and purpose not in ("search", "range"):
            warnings.append(f"⚠️ 检测到行范围参数，已自动切换为 range 模式")
            purpose = "range"
        
        if purpose == "search" and not keyword:
            warnings.append("⚠️ search 模式需要 keyword 参数，已切换为 preview 模式")
            purpose = "preview"
            
        return purpose, warnings
    
    def _read_file(self) -> Tuple[str, Optional[str]]:
        """读取文件内容"""
        encodings = ['utf-8', 'gbk', 'gb2312', 'latin-1']
        
        for encoding in encodings:
            try:
                with open(self.file_path, 'r', encoding=encoding) as f:
                    return f.read(), None
            except UnicodeDecodeError:
                continue
            except Exception as e:
                return "", f"❌ 读取文件失败: {e}"
        
        return "", "❌ 无法识别文件编码"
    
    def _format_header(self, total_lines: int, warnings: List[str]) -> str:
        """格式化文件头信息"""
        # 判断文件类型
        if self.ext in self.CODE_EXTENSIONS:
            icon = "📝"
            file_type = f"代码文件 ({self.ext})"
        elif self.ext == '.json':
            icon = "📋"
            file_type = "JSON 数据"
        elif self.ext in {'.xml', '.yaml', '.yml'}:
            icon = "📋"
            file_type = f"配置文件 ({self.ext})"
        elif self.ext == '.md':
            icon = "📄"
            file_type = "Markdown 文档"
        else:
            icon = "📄"
            file_type = f"文本文件 ({self.ext})"
        
        lines = [
            f"{icon} 文件: {self.file_info['name']}",
            f"📦 大小: {self.file_info['size_human']}",
            f"📋 类型: {file_type} | 行数: {total_lines}",
        ]
        
        if warnings:
            lines.append("")
            for w in warnings:
                lines.append(w)
        
        return '\n'.join(lines)
    
    def _get_structure(
        self,
        lines: List[str],
        total_lines: int,
        warnings: List[str]
    ) -> str:
        """获取文件结构信息"""
        output = [
            self._format_header(total_lines, warnings),
            "",
        ]
        
        # 统计信息
        non_empty_lines = sum(1 for line in lines if line.strip())
        comment_lines = sum(1 for line in lines if line.strip().startswith(('#', '//', '/*', '*')))
        
        output.append("【文件统计】")
        output.append(f"  总行数: {total_lines}")
        output.append(f"  非空行: {non_empty_lines}")
        output.append(f"  空行: {total_lines - non_empty_lines}")
        if comment_lines > 0:
            output.append(f"  注释行: {comment_lines}")
        
        # 对于代码文件，尝试识别主要结构
        if self.ext == '.py':
            output.extend(self._analyze_python_structure(lines))
        elif self.ext in {'.js', '.ts'}:
            output.extend(self._analyze_js_structure(lines))
        elif self.ext == '.md':
            output.extend(self._analyze_markdown_structure(lines))
        
        return '\n'.join(output)
    
    def _analyze_python_structure(self, lines: List[str]) -> List[str]:
        """分析 Python 代码结构"""
        import re
        
        output = ["", "【代码结构】"]
        
        classes = []
        functions = []
        imports = []
        
        for i, line in enumerate(lines, 1):
            stripped = line.strip()
            if stripped.startswith('class '):
                match = re.match(r'class\s+(\w+)', stripped)
                if match:
                    classes.append((i, match.group(1)))
            elif stripped.startswith('def '):
                match = re.match(r'def\s+(\w+)', stripped)
                if match:
                    functions.append((i, match.group(1)))
            elif stripped.startswith(('import ', 'from ')):
                imports.append(stripped)
        
        if imports:
            output.append(f"  导入: {len(imports)} 条")
        if classes:
            output.append(f"  类定义: {len(classes)} 个")
            for line_no, name in classes[:10]:
                output.append(f"    L{line_no}: class {name}")
        if functions:
            # 过滤掉类方法（简单判断：缩进的 def）
            top_level_funcs = [(l, n) for l, n in functions if not lines[l-1].startswith(' ')]
            output.append(f"  函数定义: {len(top_level_funcs)} 个（顶层）")
            for line_no, name in top_level_funcs[:10]:
                output.append(f"    L{line_no}: def {name}")
        
        return output
    
    def _analyze_js_structure(self, lines: List[str]) -> List[str]:
        """分析 JavaScript/TypeScript 代码结构"""
        import re
        
        output = ["", "【代码结构】"]
        
        functions = []
        classes = []
        exports = []
        
        for i, line in enumerate(lines, 1):
            stripped = line.strip()
            if 'function ' in stripped:
                match = re.search(r'function\s+(\w+)', stripped)
                if match:
                    functions.append((i, match.group(1)))
            if 'class ' in stripped:
                match = re.search(r'class\s+(\w+)', stripped)
                if match:
                    classes.append((i, match.group(1)))
            if stripped.startswith('export '):
                exports.append(stripped[:50])
        
        if classes:
            output.append(f"  类定义: {len(classes)} 个")
            for line_no, name in classes[:5]:
                output.append(f"    L{line_no}: {name}")
        if functions:
            output.append(f"  函数定义: {len(functions)} 个")
            for line_no, name in functions[:5]:
                output.append(f"    L{line_no}: {name}")
        if exports:
            output.append(f"  导出: {len(exports)} 条")
        
        return output
    
    def _analyze_markdown_structure(self, lines: List[str]) -> List[str]:
        """分析 Markdown 文档结构"""
        output = ["", "【文档结构】"]
        
        headings = []
        for i, line in enumerate(lines, 1):
            if line.startswith('#'):
                level = len(line) - len(line.lstrip('#'))
                title = line.lstrip('#').strip()
                if title:
                    headings.append((level, title, i))
        
        if headings:
            for level, title, line_no in headings[:20]:
                indent = "  " * (level - 1)
                output.append(f"  {indent}L{line_no}: {'#'*level} {truncate_text(title, 40)}")
            if len(headings) > 20:
                output.append(f"  ... 还有 {len(headings) - 20} 个标题")
        else:
            output.append("  (没有标题结构)")
        
        return output
    
    def _preview(
        self,
        lines: List[str],
        total_lines: int,
        max_lines: int,
        warnings: List[str]
    ) -> str:
        """预览文件内容"""
        output = [
            self._format_header(total_lines, warnings),
            "",
            "【内容预览】",
            ""
        ]
        
        preview_lines = lines[:max_lines]
        for i, line in enumerate(preview_lines, 1):
            # 显示行号
            output.append(f"{i:4d} | {line}")
        
        if total_lines > max_lines:
            output.append(f"\n... 还有 {total_lines - max_lines} 行未显示")
        
        return '\n'.join(output)
    
    def _search(
        self,
        lines: List[str],
        keyword: str,
        max_lines: int,
        warnings: List[str]
    ) -> str:
        """搜索文件内容"""
        results = []
        keyword_lower = keyword.lower()
        
        for i, line in enumerate(lines, 1):
            if keyword_lower in line.lower():
                # 高亮显示（简单标记）
                results.append((i, line))
        
        output = [
            self._format_header(len(lines), warnings),
            "",
            f"🔍 搜索关键词: '{keyword}'",
            f"📋 找到 {len(results)} 行匹配"
        ]
        
        if not results:
            output.append("")
            output.append(f"未找到包含 '{keyword}' 的内容")
            return '\n'.join(output)
        
        output.append("")
        
        for line_no, line in results[:max_lines]:
            # 截断过长的行
            display_line = line[:150] + "..." if len(line) > 150 else line
            output.append(f"{line_no:4d} | {display_line}")
        
        if len(results) > max_lines:
            output.append(f"\n... 还有 {len(results) - max_lines} 行匹配未显示")
        
        return '\n'.join(output)
    
    def _get_range(
        self,
        lines: List[str],
        total_lines: int,
        start_row: Optional[int],
        end_row: Optional[int],
        max_lines: int,
        warnings: List[str]
    ) -> str:
        """获取指定范围的内容"""
        # 计算实际范围
        if end_row is not None and end_row < 0:
            # 负数表示最后 N 行
            display_lines = lines[end_row:]
            actual_start = total_lines + end_row + 1
            actual_end = total_lines
        elif start_row is not None:
            start_idx = max(0, start_row - 1)
            if end_row is not None:
                end_idx = min(total_lines, end_row)
            else:
                end_idx = min(total_lines, start_idx + max_lines)
            display_lines = lines[start_idx:end_idx]
            actual_start = start_row
            actual_end = end_idx
        else:
            display_lines = lines[:max_lines]
            actual_start = 1
            actual_end = min(max_lines, total_lines)
        
        output = [
            self._format_header(total_lines, warnings),
            "",
            f"📋 显示第 {actual_start}-{actual_end} 行（共 {total_lines} 行）",
            ""
        ]
        
        for i, line in enumerate(display_lines, actual_start):
            output.append(f"{i:4d} | {line}")
        
        return '\n'.join(output)
    
    def _get_json_structure(self, content: str, warnings: List[str]) -> str:
        """分析 JSON 结构"""
        output = [
            self._format_header(content.count('\n') + 1, warnings),
            ""
        ]
        
        try:
            data = json.loads(content)
        except json.JSONDecodeError as e:
            output.append(f"❌ JSON 解析错误: {e}")
            return '\n'.join(output)
        
        output.append("【JSON 结构】")
        output.extend(self._analyze_json_structure(data, "", 0))
        
        return '\n'.join(output)
    
    def _analyze_json_structure(
        self,
        obj: Any,
        prefix: str = "",
        depth: int = 0
    ) -> List[str]:
        """递归分析 JSON 结构"""
        if depth > 4:
            return [f"{'  ' * depth}{prefix}..."]
        
        result = []
        indent = "  " * depth
        
        if isinstance(obj, dict):
            result.append(f"{indent}{prefix}对象 ({len(obj)} 个字段)")
            for key, value in list(obj.items())[:15]:
                result.extend(self._analyze_json_structure(value, f"{key}: ", depth + 1))
            if len(obj) > 15:
                result.append(f"{'  ' * (depth + 1)}... 还有 {len(obj) - 15} 个字段")
        elif isinstance(obj, list):
            result.append(f"{indent}{prefix}数组 ({len(obj)} 个元素)")
            if obj:
                result.extend(self._analyze_json_structure(obj[0], "[0]: ", depth + 1))
                if len(obj) > 1:
                    result.append(f"{'  ' * (depth + 1)}... 还有 {len(obj) - 1} 个元素")
        else:
            type_name = type(obj).__name__
            value_preview = str(obj)
            if len(value_preview) > 50:
                value_preview = value_preview[:47] + "..."
            result.append(f"{indent}{prefix}{type_name} = {value_preview}")
        
        return result
