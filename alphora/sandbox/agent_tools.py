"""
Alphora 沙箱工具集

为 LLM Function Calling 提供统一的沙箱操作接口。
所有工具方法返回标准 Dict 格式：{"success": bool, "output": Any, "error": str}
"""
from typing import Optional, List, Dict, Any, Callable, Awaitable
import logging
import json

from alphora.sandbox.tools.editor.file_editor import sandbox_file_editor
from alphora.sandbox.tools.inspector import file_inspector
from alphora.sandbox.tools.analyzer import code_analyzer
from alphora.sandbox.tools.exporter import markdown_to_pdf as _markdown_to_pdf

logger = logging.getLogger(__name__)


class SandboxTools:
    """
    AI Agent 沙箱工具集 —— 提供代码执行、文件操作、包管理、环境控制等全套沙箱能力。

    所有工具方法返回统一的 Dict 格式，便于 LLM Function Calling 解析：
        {"success": bool, "output": Any, "error": str}

    工具分类:
        代码执行:  run_python_code, run_python_file, run_shell_command
        文件操作:  save_file, upload_file, read_file, delete_file, list_files, file_exists, copy_file, move_file
        文件编辑:  edit_file（增量搜索替换 或 全量重写）
        文件检查:  inspect_file（查看/搜索/大纲/对比/元信息，支持 Excel/PDF/PPT）
        代码分析:  analyze_code（lint 检查与自动修复）
        文件导出:  markdown_to_pdf（Markdown 报告转 PDF，自动内嵌本地图片）
        包管理:    install_pip_package, install_pip_packages, uninstall_pip_package, list_installed_packages, check_package_installed
        环境变量:  set_environment_variable, get_environment_variable
        沙箱管理:  get_sandbox_status, get_resource_usage, reset_sandbox

    用法:
        tools = SandboxTools(sandbox)

        # 按名称调用工具（适配 Function Calling）
        result = await tools.execute_tool("run_python_code", {"code": "print(1+1)"})

        # 直接调用方法
        result = await tools.run_python_code("print(1+1)")
    """
    
    def __init__(self, sandbox):
        """初始化工具集，绑定沙箱实例。"""
        self._sandbox = sandbox
        self._tool_registry: Dict[str, Callable[..., Awaitable[Dict[str, Any]]]] = {
            "run_python_code": self.run_python_code,
            "run_python_file": self.run_python_file,
            "run_shell_command": self.run_shell_command,
            "save_file": self.save_file,
            "upload_file": self.upload_file,
            "read_file": self.read_file,
            "delete_file": self.delete_file,
            "list_files": self.list_files,
            "file_exists": self.file_exists,
            "copy_file": self.copy_file,
            "move_file": self.move_file,
            "edit_file": self.edit_file,
            "inspect_file": self.inspect_file,
            "analyze_code": self.analyze_code,
            "install_pip_package": self.install_pip_package,
            "install_pip_packages": self.install_pip_packages,
            "uninstall_pip_package": self.uninstall_pip_package,
            "list_installed_packages": self.list_installed_packages,
            "check_package_installed": self.check_package_installed,
            "set_environment_variable": self.set_environment_variable,
            "get_environment_variable": self.get_environment_variable,
            "get_sandbox_status": self.get_sandbox_status,
            "get_resource_usage": self.get_resource_usage,
            "reset_sandbox": self.reset_sandbox,
            "markdown_to_pdf": self.markdown_to_pdf,
        }
    
    @property
    def sandbox(self):
        return self._sandbox

    def _success(self, output: Any, **extra) -> Dict[str, Any]:
        return {"success": True, "output": output, "error": "", **extra}

    def _error(self, error: str, output: Any = None) -> Dict[str, Any]:
        return {"success": False, "output": output, "error": str(error)}

    # ━━ 代码执行工具 ━━

    async def run_python_code(
        self,
        code: str,
        timeout: int = 60
    ) -> Dict[str, Any]:
        """
        在沙箱中执行 Python 代码。

        适用于运行计算逻辑、数据处理脚本、调试代码片段等场景。
        代码在隔离的沙箱环境中执行，可访问沙箱内已安装的所有包和文件。

        参数:
            code:    要执行的 Python 代码（支持多行，可包含 import、函数定义等）
            timeout: 执行超时时间（秒），默认 60。长耗时任务可适当增大

        返回:
            success:        bool，是否执行成功（return_code == 0）
            output:         str，标准输出（print 的内容）
            error:          str，标准错误输出（异常信息、warnings 等）
            execution_time: float，执行耗时（秒）
            return_code:    int，进程退出码（0=成功）
        """
        try:
            result = await self._sandbox.execute_code(code, timeout=timeout)
            return {
                "success": result.success,
                "output": result.stdout,
                "error": result.stderr,
                "execution_time": result.execution_time,
                "return_code": result.return_code,
            }
        except Exception as e:
            return self._error(str(e))
    
    async def run_python_file(
        self,
        file_path: str,
        args: Optional[List[str]] = None,
        timeout: int = 60
    ) -> Dict[str, Any]:
        """
        在沙箱中执行 Python 文件。

        与 run_python_code 的区别：执行的是沙箱内已保存的 .py 文件，可传入命令行参数。
        适用于运行完整脚本、带参数的数据处理任务等。

        参数:
            file_path: Python 文件路径（沙箱内路径），如 "scripts/analyze.py"
            args:      命令行参数列表，如 ["--input", "data.csv", "--output", "result.json"]
            timeout:   执行超时时间（秒），默认 60

        返回:
            success:        bool，是否执行成功
            output:         str，标准输出
            error:          str，标准错误输出
            execution_time: float，执行耗时（秒）
        """
        try:
            result = await self._sandbox.execute_file(file_path, args=args, timeout=timeout)
            return {
                "success": result.success,
                "output": result.stdout,
                "error": result.stderr,
                "execution_time": result.execution_time,
            }
        except Exception as e:
            return self._error(str(e))
    
    async def run_shell_command(
        self,
        command: str,
        timeout: int = 60
    ) -> Dict[str, Any]:
        """
        在沙箱中执行 Shell 命令。

        适用于文件系统操作（ls, find, wc）、数据处理（curl, jq）、系统工具调用等。
        支持管道和重定向，如 "cat data.csv | head -20" 或 "ls -la > filelist.txt"。

        参数:
            command: Shell 命令字符串，如 "ls -la /mnt/workspace"
            timeout: 执行超时时间（秒），默认 60

        返回:
            success:        bool，是否执行成功
            output:         str，标准输出
            error:          str，标准错误输出
            execution_time: float，执行耗时（秒）
        """
        try:
            result = await self._sandbox.execute_shell(command, timeout=timeout)
            return {
                "success": result.success,
                "output": result.stdout,
                "error": result.stderr,
                "execution_time": result.execution_time,
            }
        except Exception as e:
            return self._error(str(e))

    # ━━ 文件操作工具 ━━

    async def save_file(self, path: str, content: str) -> Dict[str, Any]:
        """
        将文本内容保存为文件。文件不存在则创建，已存在则覆盖。自动创建中间目录。

        参数:
            path:    文件路径（沙箱内路径），如 "scripts/main.py" 或 "data/config.json"
            content: 文件内容（字符串）

        返回:
            success:   bool
            output:    str，保存确认信息
            file_info: {path, size, ...}，文件元信息
        """
        try:
            file_info = await self._sandbox.save_file(path, content)
            return self._success(
                f"File saved: {path}",
                file_info=file_info.to_dict()
            )
        except Exception as e:
            return self._error(str(e))

    async def upload_file(self, file_name: str, base64_data: str) -> Dict[str, Any]:
        """
        上传文件到沙箱的 /mnt/workspace/uploads/ 目录。

        接收 Base64 编码的文件内容，适用于上传用户提供的二进制文件（Excel、图片、PDF 等）。

        参数:
            file_name:   目标文件名，如 "data.xlsx"、"image.png"
            base64_data: Base64 编码的文件内容（支持纯 Base64 或 data URL 格式）

        返回:
            success:   bool
            output:    str，上传确认信息
            file_info: {path, size, ...}，文件元信息（含完整路径）
        """
        try:
            file_info = await self._sandbox.upload_file(file_name, base64_data)
            return self._success(
                f"File uploaded: {file_info.path}",
                file_info=file_info.to_dict()
            )
        except Exception as e:
            return self._error(str(e))
    
    async def read_file(self, path: str) -> Dict[str, Any]:
        """
        读取文本文件的原始内容。

        返回文件的完整文本内容。仅适用于文本文件（.py .json .csv .txt 等）。
        如需读取 Excel/PDF/PPT 等二进制文件，请使用 inspect_file。

        参数:
            path: 文件路径（沙箱内路径）

        返回:
            success: bool
            output:  str，文件内容全文
        """
        try:
            content = await self._sandbox.read_file(path)
            return self._success(content)
        except Exception as e:
            return self._error(str(e))
    
    async def delete_file(self, path: str) -> Dict[str, Any]:
        """
        删除文件或目录。

        参数:
            path: 要删除的文件或目录路径

        返回:
            success: bool
            output:  str，删除确认信息（文件不存在时也返回成功）
        """
        try:
            deleted = await self._sandbox.delete_file(path)
            if deleted:
                return self._success(f"Deleted: {path}")
            else:
                return self._success(f"File not found: {path}")
        except Exception as e:
            return self._error(str(e))
    
    async def list_files(
        self,
        path: str = "",
        recursive: bool = False
    ) -> Dict[str, Any]:
        """
        列出目录下的文件和子目录。

        参数:
            path:      目录路径，默认为工作区根目录。如 "data/"、"src/components/"
            recursive: 是否递归列出子目录内容，默认 False（仅列出一层）

        返回:
            success: bool
            output:  [{name, path, size, is_directory, modified_time}, ...]，文件列表
        """
        try:
            files = await self._sandbox.list_files(path, recursive=recursive)
            file_list = [f.to_dict() for f in files]
            return self._success(file_list)
        except Exception as e:
            return self._error(str(e), [])
    
    async def file_exists(self, path: str) -> Dict[str, Any]:
        """
        检查文件是否存在。

        参数:
            path: 文件路径

        返回:
            success: bool
            output:  bool，True=文件存在，False=文件不存在
        """
        try:
            exists = await self._sandbox.file_exists(path)
            return self._success(exists)
        except Exception as e:
            return self._error(str(e), False)
    
    async def copy_file(self, source: str, dest: str) -> Dict[str, Any]:
        """
        复制文件。

        参数:
            source: 源文件路径
            dest:   目标文件路径（如目标已存在则覆盖）

        返回:
            success: bool
            output:  str，复制确认信息
        """
        try:
            await self._sandbox.copy_file(source, dest)
            return self._success(f"Copied {source} to {dest}")
        except Exception as e:
            return self._error(str(e))
    
    async def move_file(self, source: str, dest: str) -> Dict[str, Any]:
        """
        移动或重命名文件。

        参数:
            source: 源文件路径
            dest:   目标路径（可以是新目录路径或新文件名）

        返回:
            success: bool
            output:  str，移动确认信息
        """
        try:
            await self._sandbox.move_file(source, dest)
            return self._success(f"Moved {source} to {dest}")
        except Exception as e:
            return self._error(str(e))

    # ━━ 文件编辑工具 ━━

    async def edit_file(
        self,
        file_path: str,
        mode: str = "search_replace",
        edits: Optional[List[Dict[str, str]]] = None,
        new_content: Optional[str] = None,
        backup: bool = True,
        match_strategy: str = "fuzzy",
        fuzzy_threshold: float = 0.8,
    ) -> Dict[str, Any]:
        """
        增量编辑文件（搜索替换）或全量重写文件内容。

        ━━ 工作模式 ━━

        1. search_replace（默认）—— 精准定位并替换文件中的代码片段
           通过 edits 列表指定多个 {search, replace} 块，逐一应用。
           匹配策略采用 3 级降级：精确匹配 → 空白归一化匹配 → 模糊相似度匹配。
           适用于修改函数、修复 bug、添加代码等场景。

        2. full_rewrite —— 用 new_content 完全替换文件内容
           适用于文件较小或需要大幅重构的场景。

        ━━ 参数说明 ━━

        基础参数:
            file_path:       目标文件路径（沙箱内路径）
            mode:            编辑模式，"search_replace" 或 "full_rewrite"
            backup:          是否在编辑前创建 .bak 备份，默认 True

        search_replace 模式参数:
            edits:           编辑块列表，每个元素为 {"search": "要查找的代码", "replace": "替换为的代码"}
                             search 内容需与文件中的片段匹配（支持多行）
            match_strategy:  匹配策略，"exact"（严格精确）或 "fuzzy"（3 级降级，默认）
            fuzzy_threshold: 模糊匹配的相似度阈值（0.0~1.0），默认 0.8

        full_rewrite 模式参数:
            new_content:     完整的新文件内容

        ━━ 返回结构 ━━

            success:      bool，是否全部编辑成功
            mode:         str，实际使用的编辑模式
            file_path:    str，编辑的文件路径
            edit_results: [{search_preview, status, match_type, similarity}, ...]，每个编辑块的匹配结果
            stats:        {total, applied, failed}，编辑统计
            diff:         str，编辑前后的 unified diff
            error:        str，错误信息
            message:      str，结果摘要

        ━━ 典型用法 ━━

        # 替换函数实现
        edit_file("app.py", edits=[{
            "search": "def hello():\\n    return 'hi'",
            "replace": "def hello():\\n    return 'hello world'"
        }])

        # 全量重写配置文件
        edit_file("config.yaml", mode="full_rewrite", new_content="key: new_value\\n")
        """
        try:
            return await sandbox_file_editor(
                sandbox=self._sandbox,
                file_path=file_path,
                mode=mode,
                edits=edits,
                new_content=new_content,
                backup=backup,
                match_strategy=match_strategy,
                fuzzy_threshold=fuzzy_threshold,
            )
        except Exception as e:
            return self._error(str(e))

    # ━━ 文件检查工具 ━━
    async def inspect_file(
        self,
        path: str,
        search: Optional[str] = None,
        outline: bool = False,
        info_only: bool = False,
        diff_with: Optional[str] = None,
        start_line: Optional[int] = None,
        end_line: Optional[int] = None,
        max_lines: int = 100,
        regex: bool = False,
        context_lines: int = 3,
        max_matches: int = 20,
        glob_pattern: Optional[str] = None,
        max_files: int = 10,
        diff_context_lines: int = 3,
        line_numbers: bool = False,
        encoding: str = "utf-8",
        sheet: Optional[str] = None,
        page: Optional[int] = None,
    ) -> Dict[str, Any]:
        """
        沙箱文件检查工具 —— 查看、搜索、大纲、对比、元信息，一个入口覆盖全部操作。

        支持文本文件（.py .js .json .md .yaml 等）、Excel（.xlsx .xls .csv）、PDF、PPT。
        支持传入文件路径或目录路径。

        ━━ 工作模式（按优先级，同时传入多个时只执行最高优先级）━━

        1. info_only=True  → 元信息模式：仅返回文件/目录的大小、行数、类型等，不读取内容
        2. diff_with="B.py" → 对比模式：将 path 文件与 diff_with 文件做 unified diff
        3. outline=True     → 大纲模式：提取代码结构（class/function 签名），适合快速了解文件骨架
        4. search="关键词"   → 搜索模式：在文件内容中查找字符串或正则，返回匹配行及上下文
           - 对目录：递归搜索目录下所有可读文件
           - 对 Excel/PDF：先解析为文本再搜索，可搜索合并单元格内容
        5. 默认（查看模式） → 返回文件内容，可通过 start_line/end_line 指定行范围

        ━━ 参数说明 ━━

        路径与基础参数:
            path:             文件或目录路径（沙箱内路径）
            encoding:         文件编码，默认 "utf-8"

        查看模式参数:
            start_line:       起始行号（1-indexed），支持负数（-1=最后一行，-10=倒数第10行）
            end_line:         结束行号（1-indexed），支持负数
            max_lines:        单次最大返回行数，默认 100
            line_numbers:     是否在每行前添加行号，默认 False

        搜索模式参数:
            search:           搜索关键词（传入即激活搜索模式）
            regex:            是否将 search 作为正则表达式，默认 False
            context_lines:    每个匹配结果前后显示的上下文行数，默认 3
            max_matches:      最大返回匹配数，默认 20
            glob_pattern:     目录搜索时的文件名过滤，如 "*.py"、"*.xlsx"
            max_files:        目录搜索时最多扫描的文件数量，默认 10

        大纲模式参数:
            outline:          设为 True 激活大纲模式，提取 class/function/import 结构

        对比模式参数:
            diff_with:        对比目标文件路径（传入即激活对比模式）
            diff_context_lines: diff 输出中每个变更区域的上下文行数，默认 3

        元信息模式参数:
            info_only:        设为 True 激活元信息模式

        格式专用参数:
            sheet:            Excel sheet 名称。
                              - 不传：多 sheet 文件返回全部 sheet 索引概览（名称、行列数、合并区域数）
                              - 传入：返回该 sheet 的格式化表格内容（自动处理合并单元格、多级表头）
            page:             PDF/PPT 页码（1-indexed），不传则返回全部内容

        ━━ 返回结构 ━━

        所有模式统一返回 Dict，包含:
            success:    bool，操作是否成功
            error:      str，失败时的错误码（成功时为空字符串）
            message:    str，失败时的错误描述

        查看模式额外返回:
            file_info:  {path, size, size_human, total_lines, type, encoding, metadata}
            content:    str，文件内容（已按行范围截取）
            shown_range: [start, end]，实际显示的行范围
            truncated:  bool，是否因 max_lines 限制而截断

        搜索模式额外返回:
            file_info:  同上
            matches:    [{line, column, text, context}, ...]，匹配列表
            match_count: int，总匹配数
            shown_matches: int，实际返回的匹配数
            matches_truncated: bool，是否因 max_matches 限制而截断
            （目录搜索时额外有 file_matches, files_searched, files_with_matches）

        大纲模式额外返回:
            file_info:  同上
            outline:    str，代码结构大纲

        对比模式额外返回:
            file_info:  同上
            diff:       str，unified diff 文本
            has_changes: bool，两文件是否有差异
            stats:      {added, removed, changed_regions}

        元信息模式额外返回:
            file_info 或 dir_info（目录时包含 total_files, total_size, file_types 等）

        ━━ 典型用法 ━━

        # 查看文件前 50 行
        inspect_file("data/report.py", max_lines=50)

        # 查看文件末尾 20 行（带行号）
        inspect_file("logs/app.log", start_line=-20, line_numbers=True)

        # 搜索关键词
        inspect_file("src/main.py", search="def handle_request")

        # 正则搜索目录下所有 Python 文件
        inspect_file("src/", search="TODO|FIXME", regex=True, glob_pattern="*.py")

        # 查看 Excel 多 sheet 概览
        inspect_file("财务报表.xlsx")

        # 查看 Excel 指定 sheet
        inspect_file("财务报表.xlsx", sheet="利润表")

        # 在 Excel 中搜索关键词
        inspect_file("财务报表.xlsx", sheet="利润表", search="营运收入")

        # 提取代码大纲
        inspect_file("src/service.py", outline=True)

        # 对比两个文件
        inspect_file("v1/config.yaml", diff_with="v2/config.yaml")

        # 仅获取文件元信息
        inspect_file("data/large_file.csv", info_only=True)
        """
        try:
            return await file_inspector(
                sandbox=self._sandbox,
                path=path,
                search=search,
                outline=outline,
                info_only=info_only,
                diff_with=diff_with,
                start_line=start_line,
                end_line=end_line,
                max_lines=max_lines,
                regex=regex,
                context_lines=context_lines,
                max_matches=max_matches,
                glob_pattern=glob_pattern,
                max_files=max_files,
                diff_context_lines=diff_context_lines,
                line_numbers=line_numbers,
                encoding=encoding,
                sheet=sheet,
                page=page,
            )
        except Exception as e:
            return self._error(str(e))

    # ━━ 代码分析工具 ━━

    async def analyze_code(
        self,
        path: str,
        fix: bool = False,
        max_issues: int = 50,
        severity: str = "all",
    ) -> Dict[str, Any]:
        """
        对 Python 代码进行 lint 静态检查，发现语法错误、风格问题和潜在 bug。

        底层使用 ruff（Docker 镜像已预装），ruff 不可用时自动降级为 AST 语法检查。
        支持单文件或整个目录的批量检查。

        参数:
            path:       文件或目录路径（沙箱内路径），如 "src/main.py" 或 "src/"
            fix:        是否自动修复可修复的问题（仅 ruff 支持），默认 False
            max_issues: 最大返回问题数量，默认 50
            severity:   严重级别过滤，"all"（全部）| "error"（仅错误）| "warning"（仅警告）

        返回:
            success:       bool
            tool:          str，实际使用的检查工具名称（"ruff" 或 "ast"）
            issues:        [{file, line, column, code, message, severity, fixable}, ...]
            error_count:   int，错误数量
            warning_count: int，警告数量
            info_count:    int，提示数量
            truncated:     bool，是否因 max_issues 限制而截断
        """
        try:
            return await code_analyzer(
                sandbox=self._sandbox,
                path=path,
                fix=fix,
                max_issues=max_issues,
                severity=severity,
            )
        except Exception as e:
            return self._error(str(e))

    # ━━ 包管理工具 ━━

    async def install_pip_package(
        self,
        package: str,
        version: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        安装单个 pip 包。

        参数:
            package: 包名，如 "pandas"、"requests"
            version: 指定版本号（可选），如 "2.1.0"、">=1.0,<2.0"

        返回:
            success: bool
            output:  str，pip 安装输出日志
            error:   str，错误信息
        """
        try:
            result = await self._sandbox.install_package(package, version=version)
            return {
                "success": result.success,
                "output": result.stdout,
                "error": result.stderr,
            }
        except Exception as e:
            return self._error(str(e))
    
    async def install_pip_packages(self, packages: List[str]) -> Dict[str, Any]:
        """
        批量安装多个 pip 包。一次调用安装多个包比逐个安装更高效。

        参数:
            packages: 包名列表，如 ["pandas", "numpy", "matplotlib"]

        返回:
            success: bool
            output:  str，pip 安装输出日志
            error:   str，错误信息
        """
        try:
            result = await self._sandbox.install_packages(packages)
            return {
                "success": result.success,
                "output": result.stdout,
                "error": result.stderr,
            }
        except Exception as e:
            return self._error(str(e))
    
    async def uninstall_pip_package(self, package: str) -> Dict[str, Any]:
        """
        卸载 pip 包。

        参数:
            package: 要卸载的包名

        返回:
            success: bool
            output:  str，pip 卸载输出日志
            error:   str，错误信息
        """
        try:
            result = await self._sandbox.uninstall_package(package)
            return {
                "success": result.success,
                "output": result.stdout,
                "error": result.stderr,
            }
        except Exception as e:
            return self._error(str(e))
    
    async def list_installed_packages(self) -> Dict[str, Any]:
        """
        列出沙箱中已安装的所有 pip 包及其版本号。

        返回:
            success: bool
            output:  [{name, version}, ...]，已安装包列表
        """
        try:
            packages = await self._sandbox.list_packages()
            pkg_list = [p.to_dict() for p in packages]
            return self._success(pkg_list)
        except Exception as e:
            return self._error(str(e), [])
    
    async def check_package_installed(self, package: str) -> Dict[str, Any]:
        """
        检查指定包是否已安装。安装依赖前可先调用此方法避免重复安装。

        参数:
            package: 包名，如 "pandas"

        返回:
            success: bool
            output:  bool，True=已安装，False=未安装
        """
        try:
            installed = await self._sandbox.package_installed(package)
            return self._success(installed)
        except Exception as e:
            return self._error(str(e), False)

    # ━━ 环境变量工具 ━━

    async def set_environment_variable(self, key: str, value: str) -> Dict[str, Any]:
        """
        设置沙箱环境变量。设置后在后续的代码执行和 Shell 命令中均可通过 os.environ 访问。

        参数:
            key:   变量名，如 "API_KEY"、"DEBUG"
            value: 变量值

        返回:
            success: bool
            output:  str，设置确认信息
        """
        try:
            await self._sandbox.set_env(key, value)
            return self._success(f"Set {key}")
        except Exception as e:
            return self._error(str(e))
    
    async def get_environment_variable(self, key: str) -> Dict[str, Any]:
        """
        获取沙箱环境变量的值。

        参数:
            key: 变量名

        返回:
            success: bool
            output:  str | None，变量值（不存在时为 None）
        """
        try:
            value = await self._sandbox.get_env(key)
            return self._success(value)
        except Exception as e:
            return self._error(str(e))

    # ━━ 沙箱管理工具 ━━

    async def get_sandbox_status(self) -> Dict[str, Any]:
        """
        获取沙箱运行状态信息，包括运行时类型、启动时间、工作目录等。

        返回:
            success: bool
            output:  dict，沙箱状态信息
        """
        try:
            status = await self._sandbox.get_status()
            return self._success(status)
        except Exception as e:
            return self._error(str(e), {})
    
    async def get_resource_usage(self) -> Dict[str, Any]:
        """
        获取沙箱当前资源使用情况（CPU、内存、磁盘等）。可用于判断是否需要清理空间或优化内存。

        返回:
            success: bool
            output:  dict，资源使用信息
        """
        try:
            usage = await self._sandbox.get_resource_usage()
            return self._success(usage)
        except Exception as e:
            return self._error(str(e), {})
    
    async def reset_sandbox(self) -> Dict[str, Any]:
        """
        重置沙箱到初始状态。清除所有文件、已安装的包和环境变量。

        ⚠️ 此操作不可逆，所有沙箱内数据将丢失。仅在确实需要全新环境时使用。

        返回:
            success: bool
            output:  str，重置确认信息
        """
        try:
            await self._sandbox.restart()
            return self._success("Sandbox reset successfully")
        except Exception as e:
            return self._error(str(e))

    # ━━ 导出工具 ━━

    async def markdown_to_pdf(
        self,
        markdown_path: str,
        output_path: str = "",
        title: str = "",
        page_size: str = "A4",
        timeout: int = 120,
    ) -> Dict[str, Any]:
        """
        将 Markdown 报告转换为 PDF 文件，自动内嵌所有本地图片。

        Markdown 报告中引用的沙箱内图片（如 matplotlib 生成的图表、截图等）
        会被自动读取并以 base64 编码嵌入 PDF，确保用户下载后可离线查看完整报告。

        ━━ 适用场景 ━━

        - 数据分析报告：包含 matplotlib/seaborn 等生成的图表
        - 研究报告：包含多张插图和表格
        - 任何需要将沙箱内 Markdown + 图片打包为单一可分发文件的场景

        ━━ 参数说明 ━━

            markdown_path: Markdown 文件路径（沙箱内路径），如 "report/analysis.md"
            output_path:   PDF 输出路径，默认与 Markdown 文件同名同目录
                           例如 "report/analysis.md" → "report/analysis.pdf"
            title:         PDF 标题（显示在文档属性中），默认从 Markdown 的 H1 标题自动提取
            page_size:     页面大小，支持 "A4"（默认）/ "A3" / "Letter" / "Legal"
            timeout:       转换超时时间（秒），默认 120。图片较多时可适当增大

        ━━ 返回结构 ━━

            success:         bool，是否转换成功
            output:          str，结果摘要信息
            pdf_path:        str，生成的 PDF 文件路径
            pdf_size:        int，PDF 文件大小（字节）
            pdf_size_human:  str，PDF 文件大小（可读格式，如 "2.3 MB"）
            images_embedded: int，成功内嵌的图片数量
            title:           str，PDF 标题
            error:           str，错误信息（成功时为空）

        ━━ 典型用法 ━━

        # 将分析报告转为 PDF（自动同目录输出）
        markdown_to_pdf("report/analysis.md")

        # 指定输出路径和标题
        markdown_to_pdf("report/analysis.md", output_path="outputs/final_report.pdf", title="Q4 数据分析报告")

        # 使用 Letter 纸张大小
        markdown_to_pdf("report/analysis.md", page_size="Letter")
        """
        try:
            result = await _markdown_to_pdf(
                sandbox=self._sandbox,
                md_path=markdown_path,
                output_path=output_path,
                title=title,
                page_size=page_size,
                timeout=timeout,
            )
            if result.get("success"):
                pdf_path = result.get("pdf_path", "")
                size_human = result.get("pdf_size_human", "")
                images = result.get("images_embedded", 0)
                result["output"] = (
                    f"PDF saved: {pdf_path} ({size_human}, "
                    f"{images} image(s) embedded)"
                )
            return result
        except Exception as e:
            return self._error(str(e))

    # ━━ 工具调度 ━━

    async def execute_tool(
        self,
        tool_name: str,
        parameters: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        按工具名称动态调用工具 —— Function Calling 的统一入口。

        将 LLM 返回的 tool_name + parameters 直接传入即可执行对应工具。

        参数:
            tool_name:  工具名称，如 "run_python_code"、"save_file"、"inspect_file"
            parameters: 工具参数字典，键值对应目标工具方法的参数

        返回:
            对应工具的返回结果（格式参见各工具的 docstring）
            工具名不存在时返回 {success: False, error: "Unknown tool: xxx"}
        """
        if tool_name not in self._tool_registry:
            return self._error(f"Unknown tool: {tool_name}")
        
        try:
            tool_func = self._tool_registry[tool_name]
            return await tool_func(**parameters)
        except TypeError as e:
            return self._error(f"Invalid parameters: {e}")
        except Exception as e:
            return self._error(str(e))
    
    def get_available_tools(self) -> List[str]:
        """获取所有可用工具的名称列表。"""
        return list(self._tool_registry.keys())
