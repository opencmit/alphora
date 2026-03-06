"""
Alphora Sandbox - AI Agent Tools

Simplified interfaces for LLM Function Calling.
"""
from typing import Optional, List, Dict, Any, Callable, Awaitable
import logging
import json

from alphora.sandbox.tools.editor.file_editor import sandbox_file_editor
from alphora.sandbox.tools.inspector import file_inspector
from alphora.sandbox.tools.analyzer import code_analyzer

logger = logging.getLogger(__name__)


class SandboxTools:
    """
    Sandbox Tool Collection for AI Agents.
    
    Provides simplified, consistent interfaces for all sandbox operations.
    All methods return a standard response format for easy LLM integration.
    
    Response Format:
        {
            "success": bool,
            "output": Any,
            "error": str
        }
    
    Usage:
        ```python
        from alphora.sandbox import Sandbox, SandboxTools
        
        async with Sandbox(runtime="local") as sandbox:
            tools = SandboxTools(sandbox)
            
            # Execute code
            result = await tools.run_python_code("print('Hello')")
            print(result)  # {'success': True, 'output': 'Hello', ...}
            
            # Save file
            result = await tools.save_file("script.py", "print('test')")
            
            # Install package
            result = await tools.install_pip_package("requests")
        ```
    
    With OpenAI Function Calling:
        ```python
        tools = SandboxTools(sandbox)
        
        # Get tool definitions
        definitions = tools.get_openai_tools()
        
        # Execute tool call
        result = await tools.execute_tool("run_python_code", {"code": "print(1+1)"})
        ```
    """
    
    def __init__(self, sandbox):
        """
        Initialize tool collection.
        
        Args:
            sandbox: Sandbox instance
        """
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
        }
    
    @property
    def sandbox(self):
        """Get sandbox instance"""
        return self._sandbox
    
    def _success(self, output: Any, **extra) -> Dict[str, Any]:
        """Create success response"""
        return {"success": True, "output": output, "error": "", **extra}
    
    def _error(self, error: str, output: Any = None) -> Dict[str, Any]:
        """Create error response"""
        return {"success": False, "output": output, "error": str(error)}

    # Code Execution Tools
    async def run_python_code(
        self,
        code: str,
        timeout: int = 60
    ) -> Dict[str, Any]:
        """
        Execute Python code in the sandbox.
        
        Args:
            code: Python code to execute
            timeout: Execution timeout in seconds (default: 60)
        
        Returns:
            Dict with success, output, error, and execution_time
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
        Execute a Python file in the sandbox.
        
        Args:
            file_path: Path to the Python file
            args: Command line arguments (optional)
            timeout: Execution timeout in seconds
        
        Returns:
            Dict with execution results
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
        Execute a shell command in the sandbox.
        
        Args:
            command: Shell command to execute
            timeout: Execution timeout in seconds
        
        Returns:
            Dict with execution results
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

    # File Operation Tools
    async def save_file(self, path: str, content: str) -> Dict[str, Any]:
        """
        Save content to a file.
        
        Args:
            path: File path (relative to workspace)
            content: File content
        
        Returns:
            Dict with success status and file info
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
        Upload a file to /mnt/workspace/uploads/.

        Args:
            file_name: Target file name, e.g. "data.xlsx"
            base64_data: Base64-encoded content (raw or data URL)

        Returns:
            Dict with success status and file info
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
        Read content from a file.
        
        Args:
            path: File path (relative to workspace)
        
        Returns:
            Dict with file content
        """
        try:
            content = await self._sandbox.read_file(path)
            return self._success(content)
        except Exception as e:
            return self._error(str(e))
    
    async def delete_file(self, path: str) -> Dict[str, Any]:
        """
        Delete a file or directory.
        
        Args:
            path: File path to delete
        
        Returns:
            Dict with deletion status
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
        List files in a directory.
        
        Args:
            path: Directory path (default: workspace root)
            recursive: Include subdirectories
        
        Returns:
            Dict with list of files
        """
        try:
            files = await self._sandbox.list_files(path, recursive=recursive)
            file_list = [f.to_dict() for f in files]
            return self._success(file_list)
        except Exception as e:
            return self._error(str(e), [])
    
    async def file_exists(self, path: str) -> Dict[str, Any]:
        """
        Check if a file exists.
        
        Args:
            path: File path to check
        
        Returns:
            Dict with existence status
        """
        try:
            exists = await self._sandbox.file_exists(path)
            return self._success(exists)
        except Exception as e:
            return self._error(str(e), False)
    
    async def copy_file(self, source: str, dest: str) -> Dict[str, Any]:
        """
        Copy a file.
        
        Args:
            source: Source file path
            dest: Destination file path
        
        Returns:
            Dict with copy status
        """
        try:
            await self._sandbox.copy_file(source, dest)
            return self._success(f"Copied {source} to {dest}")
        except Exception as e:
            return self._error(str(e))
    
    async def move_file(self, source: str, dest: str) -> Dict[str, Any]:
        """
        Move a file.
        
        Args:
            source: Source file path
            dest: Destination file path
        
        Returns:
            Dict with move status
        """
        try:
            await self._sandbox.move_file(source, dest)
            return self._success(f"Moved {source} to {dest}")
        except Exception as e:
            return self._error(str(e))

    # File Editing Tools
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
        Incrementally edit a file using search-and-replace blocks, or fully rewrite it.

        Supports two modes:
        - "search_replace": Apply targeted edits via search/replace blocks.
          Uses a 3-tier matching strategy (exact → whitespace-normalized → fuzzy).
        - "full_rewrite": Replace the entire file content.

        Args:
            file_path: Path to the target file (relative to workspace)
            mode: "search_replace" or "full_rewrite"
            edits: List of {"search": str, "replace": str} blocks (search_replace mode)
            new_content: Complete new file content (full_rewrite mode)
            backup: Whether to create a .bak backup before editing
            match_strategy: "exact" (strict) or "fuzzy" (exact → whitespace → similarity)
            fuzzy_threshold: Similarity threshold for fuzzy matching (0.0 ~ 1.0, default 0.8)

        Returns:
            Dict with success, mode, file_path, edit_results, stats, diff, error, message
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

    # File Inspection Tools
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
        Inspect files in the sandbox: view content, search, outline, diff, or get metadata.
        Supports text files, Excel, PDF, and PowerPoint. Accepts both file and directory paths.

        Modes (priority: info_only > diff_with > outline > search > view):
        - Default (view): Show file content with optional line range.
        - search: Find a string or regex pattern in a file or across a directory.
        - outline: Extract structural overview (class/function signatures).
        - diff_with: Compare with another file (unified diff).
        - info_only: Return only file/directory metadata (size, lines, type).

        Args:
            path: File or directory path in the sandbox
            search: Search pattern (activates search mode)
            outline: If True, show structural outline only
            info_only: If True, return metadata only (no content)
            diff_with: Path to a second file for comparison
            start_line: Start line for viewing (1-indexed, negative = from end)
            end_line: End line for viewing (1-indexed, negative = from end)
            max_lines: Maximum lines to return (default 100)
            regex: Treat search pattern as regex
            context_lines: Context lines around each search match (default 3)
            max_matches: Maximum search matches to return (default 20)
            glob_pattern: Filename filter for directory search (e.g. "*.py")
            max_files: Maximum files to search in directory mode (default 10)
            diff_context_lines: Context lines in diff output (default 3)
            line_numbers: Show line numbers (default False)
            encoding: File encoding (default utf-8)
            sheet: Excel sheet name (Excel files only)
            page: Page number, 1-indexed (PDF/PPT only)

        Returns:
            Dict with success, file_info/dir_info, content/matches/diff, and error
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

    # Code Analysis Tools
    async def analyze_code(
        self,
        path: str,
        fix: bool = False,
        max_issues: int = 50,
        severity: str = "all",
    ) -> Dict[str, Any]:
        """
        Run lint check on Python files or directories in the sandbox.

        Uses ruff (pre-installed in Docker image). Falls back to AST-based checks
        when ruff is unavailable.

        Args:
            path: File or directory path in the sandbox
            fix: Auto-fix lint issues (ruff only)
            max_issues: Maximum issues to return (default 50)
            severity: Filter by severity ("all" | "error" | "warning")

        Returns:
            Dict with success, tool, issues, error_count, warning_count, info_count, truncated
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

    # Package Management Tools
    async def install_pip_package(
        self,
        package: str,
        version: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Install a pip package.
        
        Args:
            package: Package name
            version: Specific version (optional)
        
        Returns:
            Dict with installation result
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
        Install multiple pip packages.
        
        Args:
            packages: List of package names
        
        Returns:
            Dict with installation result
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
        Uninstall a pip package.
        
        Args:
            package: Package name
        
        Returns:
            Dict with uninstallation result
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
        List all installed pip packages.
        
        Returns:
            Dict with list of packages
        """
        try:
            packages = await self._sandbox.list_packages()
            pkg_list = [p.to_dict() for p in packages]
            return self._success(pkg_list)
        except Exception as e:
            return self._error(str(e), [])
    
    async def check_package_installed(self, package: str) -> Dict[str, Any]:
        """
        Check if a package is installed.
        
        Args:
            package: Package name
        
        Returns:
            Dict with installation status
        """
        try:
            installed = await self._sandbox.package_installed(package)
            return self._success(installed)
        except Exception as e:
            return self._error(str(e), False)

    # Environment Variable Tools
    async def set_environment_variable(self, key: str, value: str) -> Dict[str, Any]:
        """
        Set an environment variable.
        
        Args:
            key: Variable name
            value: Variable value
        
        Returns:
            Dict with set status
        """
        try:
            await self._sandbox.set_env(key, value)
            return self._success(f"Set {key}")
        except Exception as e:
            return self._error(str(e))
    
    async def get_environment_variable(self, key: str) -> Dict[str, Any]:
        """
        Get an environment variable.
        
        Args:
            key: Variable name
        
        Returns:
            Dict with variable value
        """
        try:
            value = await self._sandbox.get_env(key)
            return self._success(value)
        except Exception as e:
            return self._error(str(e))

    # Status Tools
    async def get_sandbox_status(self) -> Dict[str, Any]:
        """
        Get sandbox status information.
        
        Returns:
            Dict with sandbox status
        """
        try:
            status = await self._sandbox.get_status()
            return self._success(status)
        except Exception as e:
            return self._error(str(e), {})
    
    async def get_resource_usage(self) -> Dict[str, Any]:
        """
        Get current resource usage.
        
        Returns:
            Dict with resource usage information
        """
        try:
            usage = await self._sandbox.get_resource_usage()
            return self._success(usage)
        except Exception as e:
            return self._error(str(e), {})
    
    async def reset_sandbox(self) -> Dict[str, Any]:
        """
        Reset the sandbox to initial state.
        
        Returns:
            Dict with reset status
        """
        try:
            await self._sandbox.restart()
            return self._success("Sandbox reset successfully")
        except Exception as e:
            return self._error(str(e))

    # Tool Execution
    async def execute_tool(
        self,
        tool_name: str,
        parameters: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Execute a tool by name.
        
        Args:
            tool_name: Name of the tool to execute
            parameters: Tool parameters
        
        Returns:
            Dict with tool result
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
        """Get list of available tool names."""
        return list(self._tool_registry.keys())
