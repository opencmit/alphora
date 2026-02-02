"""
Alphora Sandbox - AI Agent Tools

Simplified interfaces for LLM Function Calling.
"""
from typing import Optional, List, Dict, Any, Callable, Awaitable
import logging
import json

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
        
        async with Sandbox.create_local() as sandbox:
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
            "read_file": self.read_file,
            "delete_file": self.delete_file,
            "list_files": self.list_files,
            "file_exists": self.file_exists,
            "copy_file": self.copy_file,
            "move_file": self.move_file,
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
    
    # ==========================================================================
    # Code Execution Tools
    # ==========================================================================
    
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
    
    # ==========================================================================
    # File Operation Tools
    # ==========================================================================
    
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
    
    # ==========================================================================
    # Package Management Tools
    # ==========================================================================
    
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
    
    # ==========================================================================
    # Environment Variable Tools
    # ==========================================================================
    
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
    
    # ==========================================================================
    # Status Tools
    # ==========================================================================
    
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
    
    # ==========================================================================
    # Tool Execution
    # ==========================================================================
    
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
    
    # ==========================================================================
    # Tool Definitions
    # ==========================================================================
    
    def get_tool_definitions(self) -> Dict[str, Dict]:
        """
        Get all tool definitions.
        
        Returns:
            Dict of tool name to definition
        """
        return TOOL_DEFINITIONS.copy()
    
    def get_openai_tools(self) -> List[Dict[str, Any]]:
        """
        Get tool definitions in OpenAI function calling format.
        
        Returns:
            List of tool definitions for OpenAI API
        """
        return [
            {
                "type": "function",
                "function": {
                    "name": name,
                    "description": defn["description"],
                    "parameters": defn["parameters"],
                }
            }
            for name, defn in TOOL_DEFINITIONS.items()
        ]
    
    def get_anthropic_tools(self) -> List[Dict[str, Any]]:
        """
        Get tool definitions in Anthropic tool use format.
        
        Returns:
            List of tool definitions for Anthropic API
        """
        return [
            {
                "name": name,
                "description": defn["description"],
                "input_schema": defn["parameters"],
            }
            for name, defn in TOOL_DEFINITIONS.items()
        ]


# =============================================================================
# Tool Definitions
# =============================================================================

TOOL_DEFINITIONS = {
    "run_python_code": {
        "name": "run_python_code",
        "description": "Execute Python code in an isolated sandbox environment. Use this to run Python scripts, perform calculations, data analysis, or test code.",
        "parameters": {
            "type": "object",
            "properties": {
                "code": {
                    "type": "string",
                    "description": "The Python code to execute"
                },
                "timeout": {
                    "type": "integer",
                    "description": "Maximum execution time in seconds",
                    "default": 60
                }
            },
            "required": ["code"]
        }
    },
    "run_python_file": {
        "name": "run_python_file",
        "description": "Execute a Python file that exists in the sandbox workspace.",
        "parameters": {
            "type": "object",
            "properties": {
                "file_path": {
                    "type": "string",
                    "description": "Path to the Python file to execute"
                },
                "args": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "Command line arguments to pass to the script"
                },
                "timeout": {
                    "type": "integer",
                    "description": "Maximum execution time in seconds",
                    "default": 60
                }
            },
            "required": ["file_path"]
        }
    },
    "run_shell_command": {
        "name": "run_shell_command",
        "description": "Execute a shell command in the sandbox. Use for system operations, file manipulation, or running non-Python programs.",
        "parameters": {
            "type": "object",
            "properties": {
                "command": {
                    "type": "string",
                    "description": "The shell command to execute"
                },
                "timeout": {
                    "type": "integer",
                    "description": "Maximum execution time in seconds",
                    "default": 60
                }
            },
            "required": ["command"]
        }
    },
    "save_file": {
        "name": "save_file",
        "description": "Save content to a file in the sandbox workspace. Creates parent directories if needed.",
        "parameters": {
            "type": "object",
            "properties": {
                "path": {
                    "type": "string",
                    "description": "File path relative to the workspace"
                },
                "content": {
                    "type": "string",
                    "description": "Content to write to the file"
                }
            },
            "required": ["path", "content"]
        }
    },
    "read_file": {
        "name": "read_file",
        "description": "Read the content of a file from the sandbox workspace.",
        "parameters": {
            "type": "object",
            "properties": {
                "path": {
                    "type": "string",
                    "description": "File path to read"
                }
            },
            "required": ["path"]
        }
    },
    "delete_file": {
        "name": "delete_file",
        "description": "Delete a file or directory from the sandbox workspace.",
        "parameters": {
            "type": "object",
            "properties": {
                "path": {
                    "type": "string",
                    "description": "File or directory path to delete"
                }
            },
            "required": ["path"]
        }
    },
    "list_files": {
        "name": "list_files",
        "description": "List files and directories in the sandbox workspace.",
        "parameters": {
            "type": "object",
            "properties": {
                "path": {
                    "type": "string",
                    "description": "Directory path to list (empty for workspace root)",
                    "default": ""
                },
                "recursive": {
                    "type": "boolean",
                    "description": "Include files in subdirectories",
                    "default": False
                }
            }
        }
    },
    "file_exists": {
        "name": "file_exists",
        "description": "Check if a file or directory exists in the sandbox workspace.",
        "parameters": {
            "type": "object",
            "properties": {
                "path": {
                    "type": "string",
                    "description": "File path to check"
                }
            },
            "required": ["path"]
        }
    },
    "copy_file": {
        "name": "copy_file",
        "description": "Copy a file within the sandbox workspace.",
        "parameters": {
            "type": "object",
            "properties": {
                "source": {
                    "type": "string",
                    "description": "Source file path"
                },
                "dest": {
                    "type": "string",
                    "description": "Destination file path"
                }
            },
            "required": ["source", "dest"]
        }
    },
    "move_file": {
        "name": "move_file",
        "description": "Move or rename a file within the sandbox workspace.",
        "parameters": {
            "type": "object",
            "properties": {
                "source": {
                    "type": "string",
                    "description": "Source file path"
                },
                "dest": {
                    "type": "string",
                    "description": "Destination file path"
                }
            },
            "required": ["source", "dest"]
        }
    },
    "install_pip_package": {
        "name": "install_pip_package",
        "description": "Install a Python package using pip.",
        "parameters": {
            "type": "object",
            "properties": {
                "package": {
                    "type": "string",
                    "description": "Package name to install"
                },
                "version": {
                    "type": "string",
                    "description": "Specific version to install (optional)"
                }
            },
            "required": ["package"]
        }
    },
    "install_pip_packages": {
        "name": "install_pip_packages",
        "description": "Install multiple Python packages at once.",
        "parameters": {
            "type": "object",
            "properties": {
                "packages": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "List of package names to install"
                }
            },
            "required": ["packages"]
        }
    },
    "uninstall_pip_package": {
        "name": "uninstall_pip_package",
        "description": "Uninstall a Python package.",
        "parameters": {
            "type": "object",
            "properties": {
                "package": {
                    "type": "string",
                    "description": "Package name to uninstall"
                }
            },
            "required": ["package"]
        }
    },
    "list_installed_packages": {
        "name": "list_installed_packages",
        "description": "List all installed Python packages in the sandbox.",
        "parameters": {
            "type": "object",
            "properties": {}
        }
    },
    "check_package_installed": {
        "name": "check_package_installed",
        "description": "Check if a specific Python package is installed.",
        "parameters": {
            "type": "object",
            "properties": {
                "package": {
                    "type": "string",
                    "description": "Package name to check"
                }
            },
            "required": ["package"]
        }
    },
    "set_environment_variable": {
        "name": "set_environment_variable",
        "description": "Set an environment variable in the sandbox.",
        "parameters": {
            "type": "object",
            "properties": {
                "key": {
                    "type": "string",
                    "description": "Environment variable name"
                },
                "value": {
                    "type": "string",
                    "description": "Environment variable value"
                }
            },
            "required": ["key", "value"]
        }
    },
    "get_environment_variable": {
        "name": "get_environment_variable",
        "description": "Get the value of an environment variable.",
        "parameters": {
            "type": "object",
            "properties": {
                "key": {
                    "type": "string",
                    "description": "Environment variable name"
                }
            },
            "required": ["key"]
        }
    },
    "get_sandbox_status": {
        "name": "get_sandbox_status",
        "description": "Get the current status and information about the sandbox.",
        "parameters": {
            "type": "object",
            "properties": {}
        }
    },
    "get_resource_usage": {
        "name": "get_resource_usage",
        "description": "Get current resource usage (CPU, memory, disk) of the sandbox.",
        "parameters": {
            "type": "object",
            "properties": {}
        }
    },
    "reset_sandbox": {
        "name": "reset_sandbox",
        "description": "Reset the sandbox to its initial state. This will restart the sandbox and clear any runtime state.",
        "parameters": {
            "type": "object",
            "properties": {}
        }
    },
}


def get_tool_definitions() -> Dict[str, Dict]:
    """Get all tool definitions (legacy function)."""
    return TOOL_DEFINITIONS.copy()


def get_openai_tools() -> List[Dict[str, Any]]:
    """Get tools in OpenAI format (legacy function)."""
    return [
        {
            "type": "function",
            "function": {
                "name": name,
                "description": defn["description"],
                "parameters": defn["parameters"],
            }
        }
        for name, defn in TOOL_DEFINITIONS.items()
    ]
