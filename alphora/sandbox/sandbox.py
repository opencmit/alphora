"""
Alphora Sandbox - Core Sandbox Class

Main sandbox class providing unified interface for code execution.
"""
import uuid
import asyncio
import logging
from pathlib import Path
from datetime import datetime
from typing import Optional, List, Dict, Any, Union, Type, TypeVar, TYPE_CHECKING
from contextlib import asynccontextmanager

from alphora.sandbox.types import (
    BackendType,
    SandboxStatus,
    ExecutionResult,
    ResourceLimits,
    SecurityPolicy,
    FileInfo,
    FileType,
    PackageInfo,
    SandboxInfo,
)
from alphora.sandbox.backends.base import ExecutionBackend, BackendFactory
from alphora.sandbox.config import SandboxConfig
from alphora.sandbox.exceptions import (
    SandboxError,
    SandboxNotRunningError,
    SandboxAlreadyRunningError,
    ConfigurationError,
)

from alphora.sandbox.storage.base import StorageBackend

logger = logging.getLogger(__name__)

T = TypeVar("T", bound="Sandbox")


class Sandbox:
    """
    Sandbox Core Class

    Provides a secure, isolated code execution environment.

    Features:
        - Multiple backend support (Local, Docker)
        - File operations within sandbox
        - Package management
        - Environment variable management
        - Resource monitoring
        - Async context manager support
        - Storage backend mounting for persistent workspaces

    Usage - Direct:
        ```python
        sandbox = Sandbox.create_local("/data/sandboxes")
        await sandbox.start()
        result = await sandbox.execute_code("print('Hello')")
        print(result.stdout)  # Hello
        await sandbox.stop()
        ```

    Usage - Context Manager:
        ```python
        async with Sandbox.create_local() as sandbox:
            result = await sandbox.execute_code("print('Hello')")
            print(result.stdout)
        ```

    Usage - From Config:
        ```python
        config = SandboxConfig.docker(image="python:3.11")
        async with Sandbox.from_config(config) as sandbox:
            result = await sandbox.run("print('Hello')")
        ```

    Usage - With Storage Backend (Persistent Workspace):
        ```python
        from alphora.sandbox.storage import LocalStorage, StorageConfig

        # Create storage backend
        storage_config = StorageConfig.local("/data/storage")
        storage = LocalStorage(storage_config)

        # Create sandbox with mounted storage
        async with storage:
            sandbox = Sandbox.create_local(storage=storage)
            async with sandbox:
                # Files are stored in /data/storage/<sandbox_id>/
                await sandbox.write_file("data.txt", "persistent data")
        ```

    Extensibility - Subclass:
        ```python
        class MySandbox(Sandbox):
            async def my_custom_method(self):
                return await self.execute_code("print('custom')")

        sandbox = MySandbox.create_local()
        ```
    """

    def __init__(
            self,
            backend_type: Union[str, BackendType] = BackendType.LOCAL,
            sandbox_id: Optional[str] = None,
            name: Optional[str] = None,
            base_path: str = "/tmp/sandboxes",
            docker_image: str = "python:3.11-slim",
            resource_limits: Optional[ResourceLimits] = None,
            security_policy: Optional[SecurityPolicy] = None,
            auto_cleanup: bool = False,
            storage: Optional[StorageBackend] = None,
            **kwargs
    ):
        """
        Initialize sandbox.

        Args:
            backend_type: Backend type ("local" or "docker")
            sandbox_id: Unique identifier (auto-generated if not provided)
            name: Human-readable name
            base_path: Base path for sandbox workspaces (ignored if storage is provided)
            docker_image: Docker image (for Docker backend)
            resource_limits: Resource limits configuration
            security_policy: Security policy configuration
            auto_cleanup: Cleanup workspace on stop
            storage: Storage backend for persistent workspace. When provided,
                     workspace will be at storage_path/<sandbox_id>/
            **kwargs: Additional backend-specific options
        """
        # Handle backend type
        if isinstance(backend_type, str):
            backend_type = BackendType(backend_type.lower())

        self._backend_type = backend_type
        self._sandbox_id = sandbox_id or str(uuid.uuid4())[:8]
        self._name = name or f"sandbox-{self._sandbox_id}"
        self._docker_image = docker_image
        self._resource_limits = resource_limits or ResourceLimits()
        self._security_policy = security_policy or SecurityPolicy()
        self._auto_cleanup = auto_cleanup
        self._extra_kwargs = kwargs

        # Storage backend support
        self._storage = storage

        # Determine workspace path
        if storage is not None:
            # Use storage backend's path as workspace base
            self._base_path = storage.base_path if hasattr(storage, 'base_path') else Path(storage._config.local_path or "/tmp/sandboxes")
            self._workspace_path = self._base_path / self._sandbox_id
            self._using_storage = True
        else:
            self._base_path = Path(base_path)
            self._workspace_path = self._base_path / self._sandbox_id
            self._using_storage = False

        # State
        self._status = SandboxStatus.CREATED
        self._backend: Optional[ExecutionBackend] = None
        self._lock = asyncio.Lock()
        self._created_at = datetime.now()
        self._started_at: Optional[datetime] = None
        self._stopped_at: Optional[datetime] = None
        self._execution_count = 0

    # Factory Methods
    @classmethod
    def create_local(
            cls: Type[T],
            base_path: str = "/tmp/sandboxes",
            resource_limits: Optional[ResourceLimits] = None,
            security_policy: Optional[SecurityPolicy] = None,
            storage: Optional["StorageBackend"] = None,
            **kwargs
    ) -> T:
        """
        Create a local sandbox.

        Args:
            base_path: Base path for sandbox workspace (ignored if storage is provided)
            resource_limits: Resource limits
            security_policy: Security policy
            storage: Optional storage backend for persistent workspace
            **kwargs: Additional options

        Returns:
            Sandbox: Local sandbox instance

        Example with storage:
            ```python
            from alphora.sandbox.storage import LocalStorage, StorageConfig

            storage = LocalStorage(StorageConfig.local("/data/storage"))
            async with storage:
                sandbox = Sandbox.create_local(storage=storage)
                async with sandbox:
                    await sandbox.write_file("test.txt", "hello")
                    # File persists at /data/storage/<sandbox_id>/test.txt
            ```
        """
        return cls(
            backend_type=BackendType.LOCAL,
            base_path=base_path,
            resource_limits=resource_limits,
            security_policy=security_policy,
            storage=storage,
            **kwargs
        )

    @classmethod
    def create_docker(
            cls: Type[T],
            base_path: str = "/tmp/sandboxes",
            docker_image: str = "alphora-sandbox:latest",
            resource_limits: Optional[ResourceLimits] = None,
            security_policy: Optional[SecurityPolicy] = None,
            storage: Optional["StorageBackend"] = None,
            **kwargs
    ) -> T:
        """
        Create a Docker sandbox.

        Args:
            base_path: Base path for sandbox workspace (ignored if storage is provided)
            docker_image: Docker image to use
            resource_limits: Resource limits
            security_policy: Security policy
            storage: Optional storage backend for persistent workspace
            **kwargs: Additional options

        Returns:
            Sandbox: Docker sandbox instance
        """
        return cls(
            backend_type=BackendType.DOCKER,
            base_path=base_path,
            docker_image=docker_image,
            resource_limits=resource_limits,
            security_policy=security_policy,
            storage=storage,
            **kwargs
        )

    @classmethod
    def from_config(cls: Type[T], config: SandboxConfig, storage: Optional["StorageBackend"] = None, **kwargs) -> T:
        """
        Create sandbox from configuration.

        Args:
            config: Sandbox configuration
            storage: Optional storage backend (overrides config.storage)
            **kwargs: Override options

        Returns:
            Sandbox: Configured sandbox instance
        """
        return cls(
            backend_type=config.backend_type,
            base_path=config.base_path,
            docker_image=config.docker.image if config.docker else "python:3.11-slim",
            resource_limits=config.resource_limits,
            security_policy=config.security_policy,
            auto_cleanup=config.auto_cleanup,
            storage=storage,
            **kwargs
        )

    @classmethod
    @asynccontextmanager
    async def create(
            cls: Type[T],
            backend_type: Union[str, BackendType] = BackendType.LOCAL,
            **kwargs
    ):
        """
        Create sandbox as async context manager.

        Args:
            backend_type: Backend type
            **kwargs: Sandbox options

        Yields:
            Sandbox: Running sandbox instance
        """
        sandbox = cls(backend_type=backend_type, **kwargs)
        try:
            await sandbox.start()
            yield sandbox
        finally:
            await sandbox.stop()

    @classmethod
    @asynccontextmanager
    async def create_with_storage(
            cls: Type[T],
            storage: "StorageBackend",
            backend_type: Union[str, BackendType] = BackendType.LOCAL,
            **kwargs
    ):
        """
        Create sandbox with storage backend as async context manager.

        This is a convenience method that ensures storage is properly initialized.

        Args:
            storage: Storage backend (must be initialized)
            backend_type: Backend type
            **kwargs: Sandbox options

        Yields:
            Sandbox: Running sandbox instance with mounted storage

        Example:
            ```python
            from alphora.sandbox.storage import LocalStorage, StorageConfig

            storage = LocalStorage(StorageConfig.local("/data/storage"))
            async with storage:
                async with Sandbox.create_with_storage(storage) as sandbox:
                    await sandbox.write_file("data.txt", "persistent!")
            ```
        """
        sandbox = cls(backend_type=backend_type, storage=storage, **kwargs)
        try:
            await sandbox.start()
            yield sandbox
        finally:
            await sandbox.stop()

    @property
    def sandbox_id(self) -> str:
        """Get sandbox ID"""
        return self._sandbox_id

    @property
    def name(self) -> str:
        """Get sandbox name"""
        return self._name

    @property
    def status(self) -> SandboxStatus:
        """Get current status"""
        return self._status

    @property
    def is_running(self) -> bool:
        """Check if sandbox is running"""
        return self._status == SandboxStatus.RUNNING

    @property
    def backend_type(self) -> BackendType:
        """Get backend type"""
        return self._backend_type

    @property
    def workspace_path(self) -> Path:
        """Get workspace directory path"""
        return self._workspace_path

    @property
    def resource_limits(self) -> ResourceLimits:
        """Get resource limits"""
        return self._resource_limits

    @property
    def security_policy(self) -> SecurityPolicy:
        """Get security policy"""
        return self._security_policy

    @property
    def backend(self) -> Optional[ExecutionBackend]:
        """Get execution backend"""
        return self._backend

    @property
    def storage(self) -> Optional["StorageBackend"]:
        """Get associated storage backend (if any)"""
        return self._storage

    @property
    def using_storage(self) -> bool:
        """Check if sandbox is using a storage backend"""
        return self._using_storage

    # Lifecycle Management
    async def start(self) -> "Sandbox":
        """
        Start the sandbox.

        Returns:
            Sandbox: Self for chaining

        Raises:
            SandboxAlreadyRunningError: If already running
        """
        async with self._lock:
            if self._status == SandboxStatus.RUNNING:
                raise SandboxAlreadyRunningError(f"Sandbox {self._sandbox_id} is already running")

            self._status = SandboxStatus.STARTING
            logger.info(f"Starting sandbox {self._sandbox_id}")

            try:
                # Create workspace directory
                self._workspace_path.mkdir(parents=True, exist_ok=True)

                # If using storage, ensure the sandbox directory exists in storage
                if self._using_storage and self._storage:
                    await self._ensure_storage_directory()

                # Create backend
                self._backend = self._create_backend()

                # Initialize and start
                await self._backend.initialize()
                await self._backend.start()

                self._status = SandboxStatus.RUNNING
                self._started_at = datetime.now()
                logger.info(f"Sandbox {self._sandbox_id} started")
                return self

            except Exception as e:
                self._status = SandboxStatus.ERROR
                logger.error(f"Failed to start sandbox: {e}")
                raise

    async def _ensure_storage_directory(self) -> None:
        """Ensure sandbox directory exists in storage backend"""
        if self._storage and hasattr(self._storage, 'create_directory'):
            try:
                await self._storage.create_directory(self._sandbox_id)
            except Exception:
                # Directory might already exist or method not supported
                pass

    async def stop(self) -> None:
        """Stop the sandbox."""
        async with self._lock:
            if self._status not in (SandboxStatus.RUNNING, SandboxStatus.STARTING):
                return

            self._status = SandboxStatus.STOPPING
            logger.info(f"Stopping sandbox {self._sandbox_id}")

            try:
                if self._backend:
                    await self._backend.stop()

                self._status = SandboxStatus.STOPPED
                self._stopped_at = datetime.now()

                if self._auto_cleanup:
                    await self._cleanup()

                logger.info(f"Sandbox {self._sandbox_id} stopped")

            except Exception as e:
                self._status = SandboxStatus.ERROR
                logger.error(f"Error stopping sandbox: {e}")
                raise

    async def restart(self) -> "Sandbox":
        """Restart the sandbox."""
        await self.stop()
        return await self.start()

    async def destroy(self) -> None:
        """Destroy the sandbox completely."""
        await self.stop()

        if self._backend:
            await self._backend.destroy()
            self._backend = None

        await self._cleanup()
        self._status = SandboxStatus.DESTROYED
        logger.info(f"Sandbox {self._sandbox_id} destroyed")

    async def _cleanup(self) -> None:
        """Clean up workspace directory"""
        # Skip cleanup if using storage backend (files should persist)
        if self._using_storage:
            logger.debug(f"Skipping cleanup for storage-backed sandbox {self._sandbox_id}")
            return

        import shutil
        if self._workspace_path.exists():
            try:
                shutil.rmtree(self._workspace_path)
            except Exception as e:
                logger.warning(f"Failed to cleanup workspace: {e}")

    async def cleanup_storage(self, force: bool = False) -> bool:
        """
        Explicitly cleanup files in storage backend.

        This method is only effective when using a storage backend.
        Use with caution as it will delete all sandbox files from storage.

        Args:
            force: Force cleanup even if sandbox is running

        Returns:
            bool: True if cleanup was performed
        """
        if not self._using_storage:
            logger.warning("cleanup_storage called but sandbox is not using storage backend")
            return False

        if self._status == SandboxStatus.RUNNING and not force:
            logger.warning("Cannot cleanup storage while sandbox is running. Use force=True to override.")
            return False

        if self._storage:
            try:
                deleted = await self._storage.delete(self._sandbox_id + "/")
                if deleted:
                    logger.info(f"Cleaned up storage for sandbox {self._sandbox_id}")
                return deleted
            except Exception as e:
                logger.error(f"Failed to cleanup storage: {e}")
                return False

        return False

    def _create_backend(self) -> ExecutionBackend:
        """Create execution backend instance"""
        backend_kwargs = {
            "sandbox_id": self._sandbox_id,
            "workspace_path": str(self._workspace_path),
            "resource_limits": self._resource_limits,
            "security_policy": self._security_policy,
        }

        if self._backend_type == BackendType.DOCKER:
            backend_kwargs["docker_image"] = self._docker_image

        backend_kwargs.update(self._extra_kwargs)

        return BackendFactory.create(self._backend_type.value, **backend_kwargs)

    def _ensure_running(self) -> None:
        """Ensure sandbox is running"""
        if self._status != SandboxStatus.RUNNING:
            raise SandboxNotRunningError(
                f"Sandbox {self._sandbox_id} is not running. Call 'await sandbox.start()' first."
            )

    # Code Execution
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
            **kwargs: Additional options

        Returns:
            ExecutionResult: Execution result
        """
        self._ensure_running()
        timeout = timeout or self._resource_limits.timeout_seconds
        result = await self._backend.execute_code(code, timeout=timeout, **kwargs)
        self._execution_count += 1
        return result

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
            file_path: Path to the file (relative to workspace)
            args: Command line arguments
            timeout: Execution timeout
            **kwargs: Additional options

        Returns:
            ExecutionResult: Execution result
        """
        self._ensure_running()
        timeout = timeout or self._resource_limits.timeout_seconds
        result = await self._backend.execute_file(file_path, args=args, timeout=timeout, **kwargs)
        self._execution_count += 1
        return result

    async def execute_shell(
            self,
            command: str,
            timeout: Optional[int] = None,
            **kwargs
    ) -> ExecutionResult:
        """
        Execute a shell command.

        Args:
            command: Shell command
            timeout: Execution timeout
            **kwargs: Additional options

        Returns:
            ExecutionResult: Execution result
        """
        self._ensure_running()
        timeout = timeout or self._resource_limits.timeout_seconds
        result = await self._backend.execute_shell(command, timeout=timeout, **kwargs)
        self._execution_count += 1
        return result

    async def run(self, code: str, timeout: Optional[int] = None) -> ExecutionResult:
        """
        Shorthand for execute_code.

        Args:
            code: Python code to execute
            timeout: Execution timeout

        Returns:
            ExecutionResult: Execution result
        """
        return await self.execute_code(code, timeout=timeout)

    # File Operations
    async def read_file(self, path: str) -> str:
        """Read file content as text."""
        self._ensure_running()
        return await self._backend.read_file(path)

    async def read_file_bytes(self, path: str) -> bytes:
        """Read file content as bytes."""
        self._ensure_running()
        return await self._backend.read_file_bytes(path)

    async def write_file(self, path: str, content: str) -> None:
        """Write text content to file."""
        self._ensure_running()
        await self._backend.write_file(path, content)

    async def write_file_bytes(self, path: str, content: bytes) -> None:
        """Write binary content to file."""
        self._ensure_running()
        await self._backend.write_file_bytes(path, content)

    async def save_file(self, path: str, content: str) -> FileInfo:
        """
        Save file and return file info.

        Args:
            path: File path
            content: File content

        Returns:
            FileInfo: File information
        """
        self._ensure_running()
        await self._backend.write_file(path, content)

        return FileInfo(
            name=Path(path).name,
            path=path,
            size=len(content.encode("utf-8")),
            file_type=FileType.from_extension(path),
        )

    async def delete_file(self, path: str) -> bool:
        """Delete a file or directory."""
        self._ensure_running()
        return await self._backend.delete_file(path)

    async def file_exists(self, path: str) -> bool:
        """Check if file exists."""
        self._ensure_running()
        return await self._backend.file_exists(path)

    async def list_files(
            self,
            path: str = "",
            recursive: bool = False,
            pattern: Optional[str] = None
    ) -> List[FileInfo]:
        """
        List files in directory.

        Args:
            path: Directory path
            recursive: Include subdirectories
            pattern: Filename pattern filter (glob)

        Returns:
            List of FileInfo objects
        """
        self._ensure_running()

        files = await self._backend.list_directory(path, recursive=recursive)

        result = []
        for f in files:
            if pattern:
                import fnmatch
                if not fnmatch.fnmatch(f.get("name", ""), pattern):
                    continue

            result.append(FileInfo(
                name=f.get("name", ""),
                path=f.get("path", ""),
                size=f.get("size", 0),
                file_type=FileType.from_extension(f.get("name", "")),
                is_directory=f.get("is_directory", False),
            ))

        return result

    async def download_file(self, path: str) -> bytes:
        """Download file as bytes."""
        return await self.read_file_bytes(path)

    async def copy_file(self, source: str, dest: str) -> None:
        """Copy a file within sandbox."""
        self._ensure_running()
        await self._backend.copy_file(source, dest)

    async def move_file(self, source: str, dest: str) -> None:
        """Move a file within sandbox."""
        self._ensure_running()
        await self._backend.move_file(source, dest)

    # Package Management
    async def install_package(
            self,
            package: str,
            version: Optional[str] = None,
            upgrade: bool = False
    ) -> ExecutionResult:
        """Install a Python package."""
        self._ensure_running()
        return await self._backend.install_package(package, version=version, upgrade=upgrade)

    async def install_packages(self, packages: List[str]) -> ExecutionResult:
        """Install multiple packages."""
        self._ensure_running()
        cmd = f"pip install {' '.join(packages)}"
        return await self.execute_shell(cmd)

    async def uninstall_package(self, package: str) -> ExecutionResult:
        """Uninstall a package."""
        self._ensure_running()
        return await self._backend.uninstall_package(package)

    async def list_packages(self) -> List[PackageInfo]:
        """List installed packages."""
        self._ensure_running()
        return await self._backend.list_packages()

    async def package_installed(self, package: str) -> bool:
        """Check if package is installed."""
        packages = await self.list_packages()
        return any(p.name.lower() == package.lower() for p in packages)

    async def install_requirements(self, requirements_path: str) -> ExecutionResult:
        """Install packages from requirements file."""
        self._ensure_running()
        return await self._backend.install_requirements(requirements_path)

    # Environment Variables
    async def set_env(self, key: str, value: str) -> None:
        """Set environment variable."""
        self._ensure_running()
        await self._backend.set_env_var(key, value)

    async def get_env(self, key: str) -> Optional[str]:
        """Get environment variable."""
        self._ensure_running()
        return await self._backend.get_env_var(key)

    async def set_env_vars(self, env_vars: Dict[str, str]) -> None:
        """Set multiple environment variables."""
        self._ensure_running()
        await self._backend.set_env_vars(env_vars)

    # Monitoring
    async def get_resource_usage(self) -> Dict[str, Any]:
        """Get current resource usage."""
        self._ensure_running()
        return await self._backend.get_resource_usage()

    async def health_check(self) -> bool:
        """Check if sandbox is healthy."""
        if not self._backend:
            return False
        return await self._backend.health_check()

    async def get_status(self) -> Dict[str, Any]:
        """Get sandbox status dictionary."""
        return {
            "sandbox_id": self._sandbox_id,
            "name": self._name,
            "status": self._status.value,
            "backend_type": self._backend_type.value,
            "is_running": self.is_running,
            "workspace_path": str(self._workspace_path),
            "using_storage": self._using_storage,
            "created_at": self._created_at.isoformat(),
            "started_at": self._started_at.isoformat() if self._started_at else None,
            "execution_count": self._execution_count,
        }

    async def get_info(self) -> SandboxInfo:
        """Get complete sandbox information."""
        return SandboxInfo(
            sandbox_id=self._sandbox_id,
            name=self._name,
            status=self._status,
            backend_type=self._backend_type,
            workspace_path=str(self._workspace_path),
            created_at=self._created_at,
            started_at=self._started_at,
            stopped_at=self._stopped_at,
            resource_limits=self._resource_limits,
            security_policy=self._security_policy,
            execution_count=self._execution_count,
        )

    def to_host_path(self, path: str) -> Path:
        """
        2026-02-06 update
        转换至宿主机的绝对路径
        """
        return self._workspace_path / path.lstrip("/")

    # Context Manager
    async def __aenter__(self: T) -> T:
        await self.start()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb) -> None:
        await self.stop()

    def __repr__(self) -> str:
        storage_info = ", storage=True" if self._using_storage else ""
        return f"Sandbox(id={self._sandbox_id!r}, backend={self._backend_type.value!r}, status={self._status.value!r}{storage_info})"

