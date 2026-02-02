"""
Alphora Sandbox - Execution Backend Base

Abstract base class for execution backends.
"""
from abc import ABC, abstractmethod
from typing import Optional, List, Dict, Any, Type
from pathlib import Path

from alphora.sandbox.types import (
    ExecutionResult,
    ResourceLimits,
    SecurityPolicy,
    PackageInfo,
    FileInfo,
)


class ExecutionBackend(ABC):
    """
    Abstract base class for execution backends.
    
    All execution backends (Local, Docker, etc.) must implement this interface.
    
    Usage:
        ```python
        class MyBackend(ExecutionBackend):
            async def execute_code(self, code, timeout=None, **kwargs):
                # Implementation
                pass
            # ... other methods
        
        # Register with factory
        BackendFactory.register("my_backend")(MyBackend)
        ```
    """

    def __init__(
            self,
            sandbox_id: str,
            workspace_path: str,
            resource_limits: Optional[ResourceLimits] = None,
            security_policy: Optional[SecurityPolicy] = None,
            **kwargs
    ):
        """
        Initialize execution backend.
        
        Args:
            sandbox_id: Unique sandbox identifier
            workspace_path: Path to workspace directory
            resource_limits: Resource limits configuration
            security_policy: Security policy configuration
            **kwargs: Additional backend-specific options
        """
        self.sandbox_id = sandbox_id
        self._workspace_path = Path(workspace_path)
        self.resource_limits = resource_limits or ResourceLimits()
        self.security_policy = security_policy or SecurityPolicy()
        self._running = False
        self._extra_kwargs = kwargs

    @property
    def workspace_path(self) -> Path:
        """Get workspace directory path"""
        return self._workspace_path

    @property
    def is_running(self) -> bool:
        """Check if backend is running"""
        return self._running

    # Lifecycle Methods

    @abstractmethod
    async def initialize(self) -> None:
        """
        Initialize the backend environment.
        
        Called once before the backend is started.
        Should set up any required resources.
        """
        pass

    @abstractmethod
    async def start(self) -> None:
        """
        Start the backend.
        
        Called to make the backend ready for execution.
        """
        pass

    @abstractmethod
    async def stop(self) -> None:
        """
        Stop the backend.
        
        Called to gracefully stop the backend.
        Should preserve state for potential restart.
        """
        pass

    @abstractmethod
    async def destroy(self) -> None:
        """
        Destroy the backend.
        
        Called to completely clean up all resources.
        After this, the backend cannot be restarted.
        """
        pass

    async def reset(self) -> None:
        """
        Reset the backend to initial state.
        
        Default implementation stops and restarts.
        """
        await self.stop()
        await self.start()

    @abstractmethod
    async def health_check(self) -> bool:
        """
        Check if the backend is healthy.
        
        Returns:
            bool: True if backend is healthy and ready
        """
        pass

    # Code Execution
    @abstractmethod
    async def execute_code(
            self,
            code: str,
            timeout: Optional[int] = None,
            **kwargs
    ) -> ExecutionResult:
        """
        Execute Python code.
        
        Args:
            code: Python code to execute
            timeout: Execution timeout in seconds
            **kwargs: Additional execution options
        
        Returns:
            ExecutionResult: Execution result with stdout, stderr, etc.
        """
        pass

    @abstractmethod
    async def execute_file(
            self,
            file_path: str,
            args: Optional[List[str]] = None,
            timeout: Optional[int] = None,
            **kwargs
    ) -> ExecutionResult:
        """
        Execute a Python file.
        
        Args:
            file_path: Path to the Python file (relative to workspace)
            args: Command line arguments
            timeout: Execution timeout in seconds
            **kwargs: Additional execution options
        
        Returns:
            ExecutionResult: Execution result
        """
        pass

    @abstractmethod
    async def execute_shell(
            self,
            command: str,
            timeout: Optional[int] = None,
            **kwargs
    ) -> ExecutionResult:
        """
        Execute a shell command.
        
        Args:
            command: Shell command to execute
            timeout: Execution timeout in seconds
            **kwargs: Additional execution options
        
        Returns:
            ExecutionResult: Execution result
        """
        pass

    async def execute_script(
            self,
            script: str,
            interpreter: str = "python",
            timeout: Optional[int] = None,
            **kwargs
    ) -> ExecutionResult:
        """
        Execute a script with specified interpreter.
        
        Args:
            script: Script content
            interpreter: Interpreter to use (python, bash, etc.)
            timeout: Execution timeout
            **kwargs: Additional options
        
        Returns:
            ExecutionResult: Execution result
        """
        if interpreter == "python":
            return await self.execute_code(script, timeout=timeout, **kwargs)
        else:
            # For other interpreters, use shell
            return await self.execute_shell(
                f'{interpreter} -c "{script}"',
                timeout=timeout,
                **kwargs
            )

    # File Operations
    @abstractmethod
    async def read_file(self, path: str) -> str:
        """
        Read file content as text.
        
        Args:
            path: File path (relative to workspace)
        
        Returns:
            str: File content
        
        Raises:
            FileNotFoundError: If file doesn't exist
        """
        pass

    async def read_file_bytes(self, path: str) -> bytes:
        """
        Read file content as bytes.
        
        Args:
            path: File path (relative to workspace)
        
        Returns:
            bytes: File content
        """
        content = await self.read_file(path)
        return content.encode("utf-8")

    @abstractmethod
    async def write_file(self, path: str, content: str) -> None:
        """
        Write text content to file.
        
        Args:
            path: File path (relative to workspace)
            content: Text content to write
        """
        pass

    async def write_file_bytes(self, path: str, content: bytes) -> None:
        """
        Write binary content to file.
        
        Args:
            path: File path (relative to workspace)
            content: Binary content to write
        """
        # Default implementation - backends can override for better performance
        await self.write_file(path, content.decode("utf-8", errors="replace"))

    @abstractmethod
    async def delete_file(self, path: str) -> bool:
        """
        Delete a file or directory.
        
        Args:
            path: File path (relative to workspace)
        
        Returns:
            bool: True if deleted, False if not found
        """
        pass

    @abstractmethod
    async def file_exists(self, path: str) -> bool:
        """
        Check if file exists.
        
        Args:
            path: File path (relative to workspace)
        
        Returns:
            bool: True if file exists
        """
        pass

    @abstractmethod
    async def list_directory(
            self,
            path: str = "",
            recursive: bool = False
    ) -> List[Dict[str, Any]]:
        """
        List directory contents.
        
        Args:
            path: Directory path (relative to workspace)
            recursive: Include subdirectories
        
        Returns:
            List of file info dictionaries
        """
        pass

    async def copy_file(self, source: str, dest: str) -> None:
        """
        Copy a file within workspace.
        
        Args:
            source: Source file path
            dest: Destination file path
        """
        content = await self.read_file(source)
        await self.write_file(dest, content)

    async def move_file(self, source: str, dest: str) -> None:
        """
        Move a file within workspace.
        
        Args:
            source: Source file path
            dest: Destination file path
        """
        await self.copy_file(source, dest)
        await self.delete_file(source)

    async def get_file_info(self, path: str) -> Optional[FileInfo]:
        """
        Get detailed file information.
        
        Args:
            path: File path
        
        Returns:
            FileInfo or None if not found
        """
        files = await self.list_directory(path)
        for f in files:
            if f.get("path") == path or f.get("name") == Path(path).name:
                return FileInfo.from_dict(f)
        return None

    # Package Management

    @abstractmethod
    async def install_package(
            self,
            package: str,
            version: Optional[str] = None,
            upgrade: bool = False
    ) -> ExecutionResult:
        """
        Install a Python package.
        
        Args:
            package: Package name
            version: Specific version (optional)
            upgrade: Upgrade if already installed
        
        Returns:
            ExecutionResult: Installation result
        """
        pass

    @abstractmethod
    async def uninstall_package(self, package: str) -> ExecutionResult:
        """
        Uninstall a Python package.
        
        Args:
            package: Package name
        
        Returns:
            ExecutionResult: Uninstallation result
        """
        pass

    @abstractmethod
    async def list_packages(self) -> List[PackageInfo]:
        """
        List installed packages.
        
        Returns:
            List of PackageInfo objects
        """
        pass

    async def package_installed(self, package: str) -> bool:
        """
        Check if a package is installed.
        
        Args:
            package: Package name
        
        Returns:
            bool: True if installed
        """
        packages = await self.list_packages()
        return any(p.name.lower() == package.lower() for p in packages)

    async def install_requirements(self, requirements_path: str) -> ExecutionResult:
        """
        Install packages from requirements file.
        
        Args:
            requirements_path: Path to requirements.txt
        
        Returns:
            ExecutionResult: Installation result
        """
        return await self.execute_shell(f"pip install -r {requirements_path}")

    # Environment Variables
    @abstractmethod
    async def set_env_var(self, key: str, value: str) -> None:
        """
        Set an environment variable.
        
        Args:
            key: Variable name
            value: Variable value
        """
        pass

    @abstractmethod
    async def get_env_var(self, key: str) -> Optional[str]:
        """
        Get an environment variable.
        
        Args:
            key: Variable name
        
        Returns:
            Variable value or None
        """
        pass

    async def set_env_vars(self, env_vars: Dict[str, str]) -> None:
        """
        Set multiple environment variables.
        
        Args:
            env_vars: Dictionary of variable names to values
        """
        for key, value in env_vars.items():
            await self.set_env_var(key, value)

    async def get_env_vars(self, keys: List[str]) -> Dict[str, Optional[str]]:
        """
        Get multiple environment variables.
        
        Args:
            keys: List of variable names
        
        Returns:
            Dictionary of variable names to values
        """
        return {key: await self.get_env_var(key) for key in keys}

    # Resource Monitoring
    @abstractmethod
    async def get_resource_usage(self) -> Dict[str, Any]:
        """
        Get current resource usage.
        
        Returns:
            Dictionary with resource usage info
        """
        pass

    async def get_disk_usage(self) -> Dict[str, Any]:
        """
        Get disk usage information.
        
        Returns:
            Dictionary with disk usage info
        """
        # Default implementation using shell
        try:
            result = await self.execute_shell("df -h .")
            return {"output": result.stdout}
        except Exception as e:
            return {"error": str(e)}


# Backend Factory
class BackendFactory:
    """
    Factory for creating execution backends.
    
    Usage:
        ```python
        # Register a backend
        @BackendFactory.register("my_backend")
        class MyBackend(ExecutionBackend):
            pass
        
        # Create a backend
        backend = BackendFactory.create("my_backend", sandbox_id="test", ...)
        ```
    """

    _backends: Dict[str, Type[ExecutionBackend]] = {}

    @classmethod
    def register(cls, name: str):
        """
        Register a backend class.
        
        Args:
            name: Backend name
        
        Returns:
            Decorator function
        """

        def decorator(backend_class: Type[ExecutionBackend]):
            cls._backends[name] = backend_class
            return backend_class

        return decorator

    @classmethod
    def create(cls, name: str, **kwargs) -> ExecutionBackend:
        """
        Create a backend instance.
        
        Args:
            name: Backend name
            **kwargs: Backend constructor arguments
        
        Returns:
            ExecutionBackend instance
        
        Raises:
            ValueError: If backend is not registered
        """
        if name not in cls._backends:
            available = list(cls._backends.keys())
            raise ValueError(f"Unknown backend: {name}. Available: {available}")
        return cls._backends[name](**kwargs)

    @classmethod
    def available_backends(cls) -> List[str]:
        """
        Get list of available backends.
        
        Returns:
            List of backend names
        """
        return list(cls._backends.keys())

    @classmethod
    def is_available(cls, name: str) -> bool:
        """
        Check if a backend is available.
        
        Args:
            name: Backend name
        
        Returns:
            bool: True if backend is registered
        """
        return name in cls._backends
