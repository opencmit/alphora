"""
Alphora Sandbox - Local Execution Backend

Local Python interpreter execution backend.
"""
import asyncio
import os
import sys
import tempfile
import time
import json
import logging
from pathlib import Path
from typing import Optional, List, Dict, Any
from datetime import datetime

from alphora.sandbox.backends.base import ExecutionBackend, BackendFactory
from alphora.sandbox.types import (
    ExecutionResult,
    ResourceLimits,
    SecurityPolicy,
    PackageInfo,
    FileInfo,
    FileType,
)
from alphora.sandbox.exceptions import (
    FileNotFoundError as SandboxFileNotFoundError,
    PathTraversalError,
    ExecutionTimeoutError,
    ShellAccessDeniedError,
)

logger = logging.getLogger(__name__)


@BackendFactory.register("local")
class LocalBackend(ExecutionBackend):
    """
    Local execution backend.
    
    Executes code directly using the local Python interpreter.
    Suitable for development and testing environments.
    
    Features:
        - Direct Python execution
        - File system isolation within workspace
        - Environment variable management
        - Package management via pip
        - Resource monitoring via psutil
    
    Security Note:
        This backend provides limited isolation. For production use
        with untrusted code, use the Docker backend instead.
    
    Usage:
        ```python
        backend = LocalBackend(
            sandbox_id="test",
            workspace_path="/data/sandbox/test",
            resource_limits=ResourceLimits(timeout_seconds=60)
        )
        await backend.initialize()
        await backend.start()
        
        result = await backend.execute_code("print('Hello')")
        print(result.stdout)  # Hello
        
        await backend.stop()
        ```
    """
    
    def __init__(
        self,
        sandbox_id: str,
        workspace_path: str,
        resource_limits: Optional[ResourceLimits] = None,
        security_policy: Optional[SecurityPolicy] = None,
        python_path: Optional[str] = None,
        **kwargs
    ):
        """
        Initialize local backend.
        
        Args:
            sandbox_id: Unique sandbox identifier
            workspace_path: Path to workspace directory
            resource_limits: Resource limits configuration
            security_policy: Security policy configuration
            python_path: Path to Python interpreter (default: current)
            **kwargs: Additional options
        """
        super().__init__(
            sandbox_id=sandbox_id,
            workspace_path=workspace_path,
            resource_limits=resource_limits,
            security_policy=security_policy,
            **kwargs
        )
        self._env_vars: Dict[str, str] = {}
        self._python_path = python_path or sys.executable
        self._process_pool: List[asyncio.subprocess.Process] = []
    
    def _validate_path(self, path: str) -> Path:
        """
        Validate and resolve a file path.
        
        Ensures the path is within the workspace directory.
        
        Args:
            path: File path (absolute or relative)
        
        Returns:
            Path: Resolved absolute path
        
        Raises:
            PathTraversalError: If path escapes workspace
        """
        # Handle absolute and relative paths
        if path.startswith("/"):
            full_path = Path(path)
        else:
            full_path = self._workspace_path / path
        
        # Resolve to absolute path
        try:
            resolved = full_path.resolve()
        except Exception:
            raise PathTraversalError(f"Invalid path: {path}")
        
        # Security check: ensure within workspace
        try:
            resolved.relative_to(self._workspace_path.resolve())
        except ValueError:
            raise PathTraversalError(f"Path escapes workspace: {path}")
        
        return resolved
    
    def _get_execution_env(self) -> Dict[str, str]:
        """Get environment variables for execution"""
        env = os.environ.copy()
        env.update(self._env_vars)
        env["PYTHONPATH"] = str(self._workspace_path)
        env["PYTHONUNBUFFERED"] = "1"
        return env

    # Lifecycle Methods
    async def initialize(self) -> None:
        """Initialize the backend"""
        # Create workspace directory
        self._workspace_path.mkdir(parents=True, exist_ok=True)
        logger.info(f"LocalBackend initialized: {self._workspace_path}")
    
    async def start(self) -> None:
        """Start the backend"""
        self._running = True
        logger.info(f"LocalBackend started: {self.sandbox_id}")
    
    async def stop(self) -> None:
        """Stop the backend"""
        # Terminate any running processes
        for process in self._process_pool:
            try:
                process.terminate()
                await asyncio.wait_for(process.wait(), timeout=5)
            except Exception:
                try:
                    process.kill()
                except Exception:
                    pass
        self._process_pool.clear()
        
        self._running = False
        logger.info(f"LocalBackend stopped: {self.sandbox_id}")
    
    async def destroy(self) -> None:
        """Destroy the backend"""
        await self.stop()
        self._running = False
        logger.info(f"LocalBackend destroyed: {self.sandbox_id}")
    
    async def health_check(self) -> bool:
        """Check if backend is healthy"""
        return self._running and self._workspace_path.exists()

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
        timeout = timeout or self.resource_limits.timeout_seconds
        
        # Create temporary file for code
        with tempfile.NamedTemporaryFile(
            mode="w",
            suffix=".py",
            dir=str(self._workspace_path),
            delete=False,
            encoding="utf-8"
        ) as f:
            f.write(code)
            temp_file = f.name
        
        try:
            result = await self._run_python_file(temp_file, timeout=timeout)
            return result
        finally:
            # Cleanup temp file
            try:
                os.unlink(temp_file)
            except Exception:
                pass
    
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
            file_path: Path to Python file
            args: Command line arguments
            timeout: Execution timeout
            **kwargs: Additional options
        
        Returns:
            ExecutionResult: Execution result
        """
        full_path = self._validate_path(file_path)
        
        if not full_path.exists():
            raise SandboxFileNotFoundError(str(file_path))
        
        timeout = timeout or self.resource_limits.timeout_seconds
        return await self._run_python_file(str(full_path), args=args, timeout=timeout)
    
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
        # Check security policy
        if not self.security_policy.allow_shell:
            raise ShellAccessDeniedError("Shell access is disabled")
        
        timeout = timeout or self.resource_limits.timeout_seconds
        start_time = time.time()
        
        try:
            env = self._get_execution_env()
            
            process = await asyncio.create_subprocess_shell(
                command,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                cwd=str(self._workspace_path),
                env=env
            )
            
            self._process_pool.append(process)
            
            try:
                stdout, stderr = await asyncio.wait_for(
                    process.communicate(),
                    timeout=timeout
                )
            finally:
                if process in self._process_pool:
                    self._process_pool.remove(process)
            
            execution_time = time.time() - start_time
            
            return ExecutionResult(
                success=process.returncode == 0,
                stdout=stdout.decode("utf-8", errors="replace"),
                stderr=stderr.decode("utf-8", errors="replace"),
                return_code=process.returncode or 0,
                execution_time=execution_time
            )
        
        except asyncio.TimeoutError:
            return ExecutionResult.timeout_result(timeout)
        except Exception as e:
            return ExecutionResult.error_result(str(e))
    
    async def _run_python_file(
        self,
        file_path: str,
        args: Optional[List[str]] = None,
        timeout: int = 300
    ) -> ExecutionResult:
        """Run a Python file"""
        start_time = time.time()
        
        cmd = [self._python_path, file_path]
        if args:
            cmd.extend(args)
        
        try:
            env = self._get_execution_env()
            
            process = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                cwd=str(self._workspace_path),
                env=env
            )
            
            self._process_pool.append(process)
            
            try:
                stdout, stderr = await asyncio.wait_for(
                    process.communicate(),
                    timeout=timeout
                )
            finally:
                if process in self._process_pool:
                    self._process_pool.remove(process)
            
            execution_time = time.time() - start_time
            
            return ExecutionResult(
                success=process.returncode == 0,
                stdout=stdout.decode("utf-8", errors="replace"),
                stderr=stderr.decode("utf-8", errors="replace"),
                return_code=process.returncode or 0,
                execution_time=execution_time
            )
        
        except asyncio.TimeoutError:
            # Try to terminate the process
            try:
                process.kill()
            except Exception:
                pass
            return ExecutionResult.timeout_result(timeout)
        
        except Exception as e:
            return ExecutionResult.error_result(str(e))

    # File Operations
    async def read_file(self, path: str) -> str:
        """Read file content"""
        full_path = self._validate_path(path)
        
        if not full_path.exists():
            raise SandboxFileNotFoundError(path)
        
        return full_path.read_text(encoding="utf-8")
    
    async def read_file_bytes(self, path: str) -> bytes:
        """Read file as bytes"""
        full_path = self._validate_path(path)
        
        if not full_path.exists():
            raise SandboxFileNotFoundError(path)
        
        return full_path.read_bytes()
    
    async def write_file(self, path: str, content: str) -> None:
        """Write text to file"""
        full_path = self._validate_path(path)
        full_path.parent.mkdir(parents=True, exist_ok=True)
        full_path.write_text(content, encoding="utf-8")
    
    async def write_file_bytes(self, path: str, content: bytes) -> None:
        """Write bytes to file"""
        full_path = self._validate_path(path)
        full_path.parent.mkdir(parents=True, exist_ok=True)
        full_path.write_bytes(content)
    
    async def delete_file(self, path: str) -> bool:
        """Delete file or directory"""
        full_path = self._validate_path(path)
        
        if not full_path.exists():
            return False
        
        if full_path.is_dir():
            import shutil
            shutil.rmtree(full_path)
        else:
            full_path.unlink()
        
        return True
    
    async def file_exists(self, path: str) -> bool:
        """Check if file exists"""
        try:
            full_path = self._validate_path(path)
            return full_path.exists()
        except PathTraversalError:
            return False
    
    async def list_directory(
        self,
        path: str = "",
        recursive: bool = False
    ) -> List[Dict[str, Any]]:
        """List directory contents"""
        full_path = self._validate_path(path) if path else self._workspace_path
        
        if not full_path.exists():
            return []
        
        results = []
        
        if recursive:
            iterator = full_path.rglob("*")
        else:
            iterator = full_path.iterdir()
        
        for item in iterator:
            try:
                stat = item.stat()
                rel_path = item.relative_to(self._workspace_path)
                
                results.append({
                    "name": item.name,
                    "path": str(rel_path),
                    "size": stat.st_size if item.is_file() else 0,
                    "is_directory": item.is_dir(),
                    "modified_time": datetime.fromtimestamp(stat.st_mtime).isoformat(),
                    "created_time": datetime.fromtimestamp(stat.st_ctime).isoformat(),
                    "file_type": FileType.from_extension(item.name).value,
                })
            except Exception:
                continue
        
        return sorted(results, key=lambda x: (not x["is_directory"], x["name"]))

    # Package Management
    async def install_package(
        self,
        package: str,
        version: Optional[str] = None,
        upgrade: bool = False
    ) -> ExecutionResult:
        """Install a Python package"""
        cmd = f"{self._python_path} -m pip install"
        
        if upgrade:
            cmd += " --upgrade"
        
        if version:
            cmd += f" {package}=={version}"
        else:
            cmd += f" {package}"
        
        return await self.execute_shell(cmd)
    
    async def uninstall_package(self, package: str) -> ExecutionResult:
        """Uninstall a Python package"""
        cmd = f"{self._python_path} -m pip uninstall -y {package}"
        return await self.execute_shell(cmd)
    
    async def list_packages(self) -> List[PackageInfo]:
        """List installed packages"""
        result = await self.execute_shell(
            f"{self._python_path} -m pip list --format=json"
        )
        
        if not result.success:
            return []
        
        try:
            packages = json.loads(result.stdout)
            return [
                PackageInfo(name=p["name"], version=p.get("version"))
                for p in packages
            ]
        except Exception:
            return []

    # Environment Variables
    async def set_env_var(self, key: str, value: str) -> None:
        """Set environment variable"""
        self._env_vars[key] = value
    
    async def get_env_var(self, key: str) -> Optional[str]:
        """Get environment variable"""
        return self._env_vars.get(key) or os.environ.get(key)

    # Resource Monitoring
    async def get_resource_usage(self) -> Dict[str, Any]:
        """Get resource usage"""
        try:
            import psutil
            
            process = psutil.Process()
            memory_info = process.memory_info()
            
            # Get disk usage
            disk = psutil.disk_usage(str(self._workspace_path))
            
            return {
                "memory_mb": memory_info.rss / (1024 * 1024),
                "memory_percent": process.memory_percent(),
                "cpu_percent": process.cpu_percent(),
                "num_threads": process.num_threads(),
                "num_fds": process.num_fds() if hasattr(process, "num_fds") else 0,
                "disk_used_mb": disk.used / (1024 * 1024),
                "disk_free_mb": disk.free / (1024 * 1024),
                "disk_percent": disk.percent,
            }
        except ImportError:
            return {"error": "psutil not installed"}
        except Exception as e:
            return {"error": str(e)}
    
    async def get_disk_usage(self) -> Dict[str, Any]:
        """Get disk usage for workspace"""
        try:
            import shutil
            total, used, free = shutil.disk_usage(str(self._workspace_path))
            
            # Calculate workspace size
            workspace_size = sum(
                f.stat().st_size for f in self._workspace_path.rglob("*") if f.is_file()
            )
            
            return {
                "total_mb": total / (1024 * 1024),
                "used_mb": used / (1024 * 1024),
                "free_mb": free / (1024 * 1024),
                "workspace_mb": workspace_size / (1024 * 1024),
            }
        except Exception as e:
            return {"error": str(e)}
