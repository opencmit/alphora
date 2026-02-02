"""
Alphora Sandbox - Sandbox Manager

Multi-sandbox lifecycle management.
"""
import asyncio
import logging
from typing import Optional, List, Dict, Any, Union
from pathlib import Path
from datetime import datetime

from alphora.sandbox.sandbox import Sandbox
from alphora.sandbox.types import (
    BackendType,
    SandboxStatus,
    ResourceLimits,
    SecurityPolicy,
    SandboxInfo,
)
from alphora.sandbox.config import SandboxConfig
from alphora.sandbox.exceptions import (
    SandboxNotFoundError,
    SandboxAlreadyExistsError,
)

logger = logging.getLogger(__name__)


class SandboxManager:
    """
    Sandbox Manager for multi-sandbox lifecycle management.
    
    Manages multiple sandboxes with automatic cleanup, pooling,
    and resource management.
    
    Features:
        - Create and manage multiple sandboxes
        - Automatic cleanup on shutdown
        - Sandbox lookup by ID or name
        - Batch operations
        - Resource monitoring across sandboxes
    
    Usage:
        ```python
        manager = SandboxManager(base_path="/data/sandboxes")
        
        # Create sandbox
        sandbox = await manager.create_sandbox("my-sandbox")
        await sandbox.execute_code("print('Hello')")
        
        # Get existing sandbox
        sandbox = manager.get_sandbox("my-sandbox")
        
        # List all sandboxes
        sandboxes = manager.list_sandboxes()
        
        # Cleanup
        await manager.shutdown()
        ```
    
    Context Manager:
        ```python
        async with SandboxManager() as manager:
            sandbox = await manager.create_sandbox("test")
            await sandbox.run("print('Hello')")
        # All sandboxes automatically stopped
        ```
    """
    
    def __init__(
        self,
        base_path: str = "/tmp/sandboxes",
        default_backend: BackendType = BackendType.LOCAL,
        default_limits: Optional[ResourceLimits] = None,
        default_policy: Optional[SecurityPolicy] = None,
        max_sandboxes: int = 100,
        auto_cleanup: bool = True,
    ):
        """
        Initialize sandbox manager.
        
        Args:
            base_path: Base directory for all sandbox workspaces
            default_backend: Default backend type for new sandboxes
            default_limits: Default resource limits
            default_policy: Default security policy
            max_sandboxes: Maximum number of concurrent sandboxes
            auto_cleanup: Automatically cleanup sandboxes on stop
        """
        self._base_path = Path(base_path)
        self._default_backend = default_backend
        self._default_limits = default_limits or ResourceLimits()
        self._default_policy = default_policy or SecurityPolicy()
        self._max_sandboxes = max_sandboxes
        self._auto_cleanup = auto_cleanup
        
        self._sandboxes: Dict[str, Sandbox] = {}
        self._lock = asyncio.Lock()
        self._running = False
    
    @property
    def base_path(self) -> Path:
        """Get base directory path"""
        return self._base_path
    
    @property
    def sandbox_count(self) -> int:
        """Get number of managed sandboxes"""
        return len(self._sandboxes)
    
    @property
    def is_running(self) -> bool:
        """Check if manager is running"""
        return self._running

    # Lifecycle Management
    async def start(self) -> "SandboxManager":
        """
        Start the manager.
        
        Returns:
            SandboxManager: Self for chaining
        """
        self._base_path.mkdir(parents=True, exist_ok=True)
        self._running = True
        logger.info(f"SandboxManager started: {self._base_path}")
        return self
    
    async def shutdown(self, force: bool = False) -> None:
        """
        Shutdown the manager and all sandboxes.
        
        Args:
            force: Force stop even if sandboxes are busy
        """
        logger.info(f"Shutting down SandboxManager with {len(self._sandboxes)} sandboxes")
        
        # Stop all sandboxes
        tasks = []
        for sandbox in list(self._sandboxes.values()):
            if force:
                tasks.append(sandbox.destroy())
            else:
                tasks.append(sandbox.stop())
        
        if tasks:
            await asyncio.gather(*tasks, return_exceptions=True)
        
        self._sandboxes.clear()
        self._running = False
        logger.info("SandboxManager shutdown complete")
    
    async def __aenter__(self) -> "SandboxManager":
        await self.start()
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb) -> None:
        await self.shutdown()

    # Sandbox Creation
    async def create_sandbox(
        self,
        name: Optional[str] = None,
        sandbox_id: Optional[str] = None,
        backend_type: Optional[BackendType] = None,
        resource_limits: Optional[ResourceLimits] = None,
        security_policy: Optional[SecurityPolicy] = None,
        docker_image: str = "python:3.11-slim",
        auto_start: bool = True,
        **kwargs
    ) -> Sandbox:
        """
        Create a new sandbox.
        
        Args:
            name: Human-readable name
            sandbox_id: Unique ID (auto-generated if not provided)
            backend_type: Backend type (uses default if not specified)
            resource_limits: Resource limits (uses default if not specified)
            security_policy: Security policy (uses default if not specified)
            docker_image: Docker image for Docker backend
            auto_start: Automatically start the sandbox
            **kwargs: Additional sandbox options
        
        Returns:
            Sandbox: Created sandbox instance
        
        Raises:
            SandboxAlreadyExistsError: If sandbox with ID already exists
        """
        async with self._lock:
            # Check limits
            if len(self._sandboxes) >= self._max_sandboxes:
                raise RuntimeError(f"Maximum sandbox limit ({self._max_sandboxes}) reached")
            
            # Create sandbox
            sandbox = Sandbox(
                backend_type=backend_type or self._default_backend,
                sandbox_id=sandbox_id,
                name=name,
                base_path=str(self._base_path),
                docker_image=docker_image,
                resource_limits=resource_limits or self._default_limits,
                security_policy=security_policy or self._default_policy,
                auto_cleanup=self._auto_cleanup,
                **kwargs
            )
            
            # Check for duplicate
            if sandbox.sandbox_id in self._sandboxes:
                raise SandboxAlreadyExistsError(
                    f"Sandbox with ID '{sandbox.sandbox_id}' already exists"
                )
            
            # Start if requested
            if auto_start:
                await sandbox.start()
            
            # Register
            self._sandboxes[sandbox.sandbox_id] = sandbox
            logger.info(f"Created sandbox: {sandbox.sandbox_id}")
            
            return sandbox
    
    async def create_local_sandbox(
        self,
        name: Optional[str] = None,
        **kwargs
    ) -> Sandbox:
        """Create a local sandbox."""
        return await self.create_sandbox(
            name=name,
            backend_type=BackendType.LOCAL,
            **kwargs
        )
    
    async def create_docker_sandbox(
        self,
        name: Optional[str] = None,
        docker_image: str = "python:3.11-slim",
        **kwargs
    ) -> Sandbox:
        """Create a Docker sandbox."""
        return await self.create_sandbox(
            name=name,
            backend_type=BackendType.DOCKER,
            docker_image=docker_image,
            **kwargs
        )
    
    async def get_or_create(
        self,
        sandbox_id: str,
        **kwargs
    ) -> Sandbox:
        """
        Get existing sandbox or create new one.
        
        Args:
            sandbox_id: Sandbox ID
            **kwargs: Creation options if sandbox doesn't exist
        
        Returns:
            Sandbox: Existing or new sandbox
        """
        if sandbox_id in self._sandboxes:
            return self._sandboxes[sandbox_id]
        return await self.create_sandbox(sandbox_id=sandbox_id, **kwargs)

    # Sandbox Access
    def get_sandbox(self, sandbox_id: str) -> Sandbox:
        """
        Get sandbox by ID.
        
        Args:
            sandbox_id: Sandbox ID
        
        Returns:
            Sandbox: Sandbox instance
        
        Raises:
            SandboxNotFoundError: If sandbox not found
        """
        if sandbox_id not in self._sandboxes:
            raise SandboxNotFoundError(f"Sandbox not found: {sandbox_id}")
        return self._sandboxes[sandbox_id]
    
    def get_sandbox_by_name(self, name: str) -> Optional[Sandbox]:
        """
        Get sandbox by name.
        
        Args:
            name: Sandbox name
        
        Returns:
            Sandbox or None if not found
        """
        for sandbox in self._sandboxes.values():
            if sandbox.name == name:
                return sandbox
        return None
    
    def has_sandbox(self, sandbox_id: str) -> bool:
        """Check if sandbox exists."""
        return sandbox_id in self._sandboxes
    
    def list_sandboxes(
        self,
        status: Optional[SandboxStatus] = None,
        backend_type: Optional[BackendType] = None
    ) -> List[Sandbox]:
        """
        List sandboxes with optional filtering.
        
        Args:
            status: Filter by status
            backend_type: Filter by backend type
        
        Returns:
            List of sandboxes
        """
        sandboxes = list(self._sandboxes.values())
        
        if status:
            sandboxes = [s for s in sandboxes if s.status == status]
        
        if backend_type:
            sandboxes = [s for s in sandboxes if s.backend_type == backend_type]
        
        return sandboxes
    
    def list_running(self) -> List[Sandbox]:
        """List running sandboxes."""
        return self.list_sandboxes(status=SandboxStatus.RUNNING)
    
    async def list_info(self) -> List[SandboxInfo]:
        """Get info for all sandboxes."""
        return [await s.get_info() for s in self._sandboxes.values()]

    # Sandbox Operations
    async def stop_sandbox(self, sandbox_id: str) -> None:
        """
        Stop a sandbox.
        
        Args:
            sandbox_id: Sandbox ID
        """
        sandbox = self.get_sandbox(sandbox_id)
        await sandbox.stop()
    
    async def destroy_sandbox(self, sandbox_id: str) -> None:
        """
        Destroy a sandbox and remove from manager.
        
        Args:
            sandbox_id: Sandbox ID
        """
        sandbox = self.get_sandbox(sandbox_id)
        await sandbox.destroy()
        
        async with self._lock:
            del self._sandboxes[sandbox_id]
        
        logger.info(f"Destroyed sandbox: {sandbox_id}")
    
    async def restart_sandbox(self, sandbox_id: str) -> Sandbox:
        """
        Restart a sandbox.
        
        Args:
            sandbox_id: Sandbox ID
        
        Returns:
            Restarted sandbox
        """
        sandbox = self.get_sandbox(sandbox_id)
        await sandbox.restart()
        return sandbox

    # Batch Operations
    async def stop_all(self) -> Dict[str, bool]:
        """
        Stop all sandboxes.
        
        Returns:
            Dict of sandbox_id to success status
        """
        results = {}
        for sandbox_id, sandbox in self._sandboxes.items():
            try:
                await sandbox.stop()
                results[sandbox_id] = True
            except Exception as e:
                logger.error(f"Failed to stop {sandbox_id}: {e}")
                results[sandbox_id] = False
        return results
    
    async def destroy_all(self) -> Dict[str, bool]:
        """
        Destroy all sandboxes.
        
        Returns:
            Dict of sandbox_id to success status
        """
        results = {}
        sandbox_ids = list(self._sandboxes.keys())
        
        for sandbox_id in sandbox_ids:
            try:
                await self.destroy_sandbox(sandbox_id)
                results[sandbox_id] = True
            except Exception as e:
                logger.error(f"Failed to destroy {sandbox_id}: {e}")
                results[sandbox_id] = False
        
        return results
    
    async def health_check_all(self) -> Dict[str, bool]:
        """
        Health check all sandboxes.
        
        Returns:
            Dict of sandbox_id to health status
        """
        results = {}
        for sandbox_id, sandbox in self._sandboxes.items():
            try:
                results[sandbox_id] = await sandbox.health_check()
            except Exception:
                results[sandbox_id] = False
        return results
    
    # ==========================================================================
    # Resource Monitoring
    # ==========================================================================
    
    async def get_total_resource_usage(self) -> Dict[str, Any]:
        """
        Get total resource usage across all sandboxes.
        
        Returns:
            Aggregated resource usage
        """
        total = {
            "sandbox_count": len(self._sandboxes),
            "running_count": len(self.list_running()),
            "total_memory_mb": 0,
            "total_cpu_percent": 0,
            "sandboxes": {},
        }
        
        for sandbox_id, sandbox in self._sandboxes.items():
            if sandbox.is_running:
                try:
                    usage = await sandbox.get_resource_usage()
                    total["sandboxes"][sandbox_id] = usage
                    total["total_memory_mb"] += usage.get("memory_mb", 0)
                    total["total_cpu_percent"] += usage.get("cpu_percent", 0)
                except Exception:
                    pass
        
        return total
    
    async def get_status(self) -> Dict[str, Any]:
        """
        Get manager status.
        
        Returns:
            Manager status information
        """
        return {
            "base_path": str(self._base_path),
            "default_backend": self._default_backend.value,
            "max_sandboxes": self._max_sandboxes,
            "sandbox_count": len(self._sandboxes),
            "running_count": len(self.list_running()),
            "sandboxes": {
                sid: {
                    "name": s.name,
                    "status": s.status.value,
                    "backend": s.backend_type.value,
                }
                for sid, s in self._sandboxes.items()
            }
        }
    
    # ==========================================================================
    # Cleanup
    # ==========================================================================
    
    async def cleanup_stopped(self) -> int:
        """
        Cleanup stopped sandboxes.
        
        Returns:
            Number of sandboxes cleaned up
        """
        stopped = [
            sid for sid, s in self._sandboxes.items()
            if s.status in (SandboxStatus.STOPPED, SandboxStatus.ERROR)
        ]
        
        for sandbox_id in stopped:
            try:
                await self.destroy_sandbox(sandbox_id)
            except Exception as e:
                logger.error(f"Failed to cleanup {sandbox_id}: {e}")
        
        return len(stopped)
    
    async def cleanup_idle(self, max_idle_seconds: int = 3600) -> int:
        """
        Cleanup sandboxes idle for too long.
        
        Args:
            max_idle_seconds: Maximum idle time before cleanup
        
        Returns:
            Number of sandboxes cleaned up
        """
        now = datetime.now()
        cleaned = 0
        
        for sandbox_id in list(self._sandboxes.keys()):
            sandbox = self._sandboxes.get(sandbox_id)
            if not sandbox:
                continue
            
            # Check if sandbox has been idle
            info = await sandbox.get_info()
            if info.started_at:
                idle_time = (now - info.started_at).total_seconds()
                if idle_time > max_idle_seconds and info.execution_count == 0:
                    try:
                        await self.destroy_sandbox(sandbox_id)
                        cleaned += 1
                    except Exception as e:
                        logger.error(f"Failed to cleanup idle sandbox {sandbox_id}: {e}")
        
        return cleaned
