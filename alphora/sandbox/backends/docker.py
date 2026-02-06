"""
Alphora Sandbox - Docker Execution Backend

Docker container-based execution backend.
"""
import asyncio
import json
import logging
import time
from pathlib import Path
from typing import Optional, List, Dict, Any

from alphora.sandbox.backends.base import ExecutionBackend, BackendFactory
from alphora.sandbox.types import (
    ExecutionResult,
    ResourceLimits,
    SecurityPolicy,
    PackageInfo,
    FileInfo,
    FileType,
)
from alphora.sandbox.config import DockerConfig
from alphora.sandbox.exceptions import (
    DockerError,
    ContainerError,
    ContainerNotFoundError,
    FileNotFoundError as SandboxFileNotFoundError,
    ExecutionTimeoutError,
)

logger = logging.getLogger(__name__)


def is_docker_available() -> bool:
    """Check if Docker is available"""
    try:
        import docker
        client = docker.from_env()
        client.ping()
        return True
    except Exception:
        return False


@BackendFactory.register("docker")
class DockerBackend(ExecutionBackend):
    """
    Docker execution backend.
    
    Executes code in isolated Docker containers.
    Provides strong isolation and resource limits.
    
    Features:
        - Full container isolation
        - Resource limits (CPU, memory)
        - Network isolation
        - Volume mounting for workspace
        - Security options (no-new-privileges, etc.)
    
    Requirements:
        pip install docker
    
    Usage:
        ```python
        backend = DockerBackend(
            sandbox_id="test",
            workspace_path="/data/sandbox/test",
            docker_image="python:3.11-slim",
            resource_limits=ResourceLimits(memory_mb=512)
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
        docker_image: str = "alphora-sandbox:latest",
        docker_config: Optional[DockerConfig] = None,
        **kwargs
    ):
        """
        Initialize Docker backend.
        
        Args:
            sandbox_id: Unique sandbox identifier
            workspace_path: Path to workspace directory
            resource_limits: Resource limits configuration
            security_policy: Security policy configuration
            docker_image: Docker image to use
            docker_config: Docker-specific configuration
            **kwargs: Additional options
        """
        super().__init__(
            sandbox_id=sandbox_id,
            workspace_path=workspace_path,
            resource_limits=resource_limits,
            security_policy=security_policy,
            **kwargs
        )

        self._docker_image = docker_image
        self._docker_config = docker_config or DockerConfig(image=docker_image)

        self._docker_dir = Path(__file__).parent.parent / "docker"

        self._container = None
        self._client = None
        self._container_workspace = "/workspace"
        self._env_vars: Dict[str, str] = {}
    
    @property
    def container_id(self) -> Optional[str]:
        """Get container ID"""
        return self._container.id if self._container else None
    
    @property
    def container_name(self) -> str:
        """Get container name"""
        return f"sandbox-{self.sandbox_id}"

    async def initialize(self) -> None:
        """检查镜像，不存在则构建"""
        try:
            import docker
            self._client = docker.from_env()
        except ImportError:
            raise DockerError("docker package not installed. Install with: pip install docker")

        try:
            self._client.images.get(self._docker_image)
            logger.info(f"Using existing sandbox image: {self._docker_image}")

        except Exception:
            # if self._docker_image == "alphora-sandbox:latest":
            if self._docker_image.startswith('alphora'):
                await self._build_custom_image()
            else:
                logger.info(f"Pulling image {self._docker_image}...")
                self._client.images.pull(self._docker_image)

        self._workspace_path.mkdir(parents=True, exist_ok=True)

    async def _build_custom_image(self) -> None:
        """执行本地 Dockerfile 构建"""

        logger.info(f"Image {self._docker_image} not found. Performing first-time setup; please be patient as the build process completes (this may take a few minutes) ...")

        if not self._docker_dir.exists():
            raise DockerError(f"Docker build directory not found at {self._docker_dir}")

        try:
            image, logs = self._client.images.build(
                path=str(self._docker_dir),
                tag=self._docker_image,
                rm=True,
                target="base"    # 对应 Dockerfile 中 AS base
            )

            for line in logs:
                if 'stream' in line:
                    logger.debug(line['stream'].strip())

            logger.info(f"Successfully built {self._docker_image}")

        except Exception as e:
            raise DockerError(f"Failed to build custom sandbox image: {e}")
    
    async def start(self) -> None:
        """Start the Docker container"""
        if self._container:
            # Container already exists, just start it
            try:
                self._container.start()
                self._running = True
                return
            except Exception:
                pass
        
        # Build container configuration
        container_config = self._build_container_config()
        
        try:
            # Create and start container
            self._container = self._client.containers.run(**container_config)
            self._running = True
            
            # Wait for container to be ready
            await self._wait_for_ready()
            
            logger.info(f"Container {self.container_name} started: {self.container_id[:12]}")
        
        except Exception as e:
            self._running = False
            raise ContainerError(self.container_name, f"Failed to start container: {e}")
    
    async def stop(self) -> None:
        """Stop the Docker container"""
        if not self._container:
            self._running = False
            return
        
        try:
            self._container.stop(timeout=10)
            logger.info(f"Container {self.container_name} stopped")
        except Exception as e:
            logger.warning(f"Error stopping container: {e}")
        
        self._running = False
    
    async def destroy(self) -> None:
        """Destroy the Docker container"""
        await self.stop()
        
        if self._container:
            try:
                self._container.remove(force=True)
                logger.info(f"Container {self.container_name} removed")
            except Exception as e:
                logger.warning(f"Error removing container: {e}")
            finally:
                self._container = None
        
        self._running = False
    
    async def reset(self) -> None:
        """Reset container to initial state"""
        await self.destroy()
        await self.initialize()
        await self.start()
    
    async def health_check(self) -> bool:
        """Check if container is healthy"""
        if not self._container:
            return False
        
        try:
            self._container.reload()
            return self._container.status == "running"
        except Exception:
            return False
    
    def _build_container_config(self) -> Dict[str, Any]:
        """Build Docker container configuration"""
        config = self._docker_config
        limits = self.resource_limits
        
        # Network mode
        network_mode = "none"
        if limits.network_enabled:
            network_mode = config.network_mode if config.network_mode != "none" else "bridge"
        
        container_config = {
            "image": self._docker_image,
            "name": self.container_name,
            "detach": True,
            "tty": True,
            "stdin_open": True,
            "working_dir": self._container_workspace,
            "network_mode": network_mode,
            
            # Resource limits
            "mem_limit": f"{limits.memory_mb}m",
            "cpu_period": config.cpu_period,
            "cpu_quota": int(config.cpu_period * limits.cpu_cores),
            "pids_limit": config.pids_limit,
            
            # Security
            "security_opt": config.security_opt,
            "cap_drop": config.cap_drop,
            "cap_add": config.cap_add,
            "privileged": config.privileged,
            "read_only": config.read_only_root,
            
            # Volumes
            "volumes": {
                str(self._workspace_path.resolve()): {
                    "bind": self._container_workspace,
                    "mode": "rw"
                }
            },
            
            # Environment
            "environment": {
                **config.environment,
                **self._env_vars,
                "SANDBOX_ID": self.sandbox_id,
            },
            
            # Keep container running
            "command": "tail -f /dev/null",
        }
        
        # Add user if specified
        if config.user:
            container_config["user"] = config.user
        
        return container_config
    
    async def _wait_for_ready(self, timeout: int = 30) -> None:
        """Wait for container to be ready"""
        start = time.time()
        while time.time() - start < timeout:
            try:
                self._container.reload()
                if self._container.status == "running":
                    # Test with simple command
                    result = self._container.exec_run("python --version")
                    if result.exit_code == 0:
                        return
            except Exception:
                pass
            await asyncio.sleep(0.5)
        
        raise ContainerError(self.container_name, "Container failed to become ready")
    

    # Code Execution
    async def execute_code(
        self,
        code: str,
        timeout: Optional[int] = None,
        **kwargs
    ) -> ExecutionResult:
        """Execute Python code in container"""
        if not self._container:
            raise ContainerNotFoundError(self.container_name, "Container not running")
        
        timeout = timeout or self.resource_limits.timeout_seconds
        
        # Escape code for shell
        escaped_code = code.replace("'", "'\"'\"'")
        cmd = f"python -c '{escaped_code}'"
        
        return await self._exec_in_container(cmd, timeout)
    
    async def execute_file(
        self,
        file_path: str,
        args: Optional[List[str]] = None,
        timeout: Optional[int] = None,
        **kwargs
    ) -> ExecutionResult:
        """Execute Python file in container"""
        if not self._container:
            raise ContainerNotFoundError(self.container_name, "Container not running")
        
        timeout = timeout or self.resource_limits.timeout_seconds
        
        # Build command
        container_path = f"{self._container_workspace}/{file_path.lstrip('/')}"
        cmd = f"python {container_path}"
        if args:
            cmd += " " + " ".join(args)
        
        return await self._exec_in_container(cmd, timeout)
    
    async def execute_shell(
        self,
        command: str,
        timeout: Optional[int] = None,
        **kwargs
    ) -> ExecutionResult:
        """Execute shell command in container"""
        if not self._container:
            raise ContainerNotFoundError(self.container_name, "Container not running")
        
        timeout = timeout or self.resource_limits.timeout_seconds
        return await self._exec_in_container(command, timeout)
    
    async def _exec_in_container(
        self,
        command: str,
        timeout: int
    ) -> ExecutionResult:
        """Execute command in container"""
        start_time = time.time()
        
        try:
            # Run in thread pool to avoid blocking
            loop = asyncio.get_event_loop()
            
            def run_exec():
                return self._container.exec_run(
                    ["sh", "-c", command],
                    workdir=self._container_workspace,
                    environment=self._env_vars,
                    demux=True,
                )
            
            # Execute with timeout
            try:
                result = await asyncio.wait_for(
                    loop.run_in_executor(None, run_exec),
                    timeout=timeout
                )
            except asyncio.TimeoutError:
                return ExecutionResult.timeout_result(timeout)
            
            execution_time = time.time() - start_time
            
            stdout = result.output[0].decode("utf-8", errors="replace") if result.output[0] else ""
            stderr = result.output[1].decode("utf-8", errors="replace") if result.output[1] else ""
            
            return ExecutionResult(
                success=result.exit_code == 0,
                stdout=stdout,
                stderr=stderr,
                return_code=result.exit_code,
                execution_time=execution_time,
            )
        
        except asyncio.TimeoutError:
            return ExecutionResult.timeout_result(timeout)
        except Exception as e:
            return ExecutionResult.error_result(str(e))

    # File Operations
    async def read_file(self, path: str) -> str:
        """Read file from container workspace"""
        full_path = self._workspace_path / path.lstrip("/")
        
        if not full_path.exists():
            raise SandboxFileNotFoundError(path)
        
        return full_path.read_text(encoding="utf-8")
    
    async def write_file(self, path: str, content: str) -> None:
        """Write file to container workspace"""
        full_path = self._workspace_path / path.lstrip("/")
        full_path.parent.mkdir(parents=True, exist_ok=True)
        full_path.write_text(content, encoding="utf-8")
    
    async def delete_file(self, path: str) -> bool:
        """Delete file from container workspace"""
        full_path = self._workspace_path / path.lstrip("/")
        
        if not full_path.exists():
            return False
        
        if full_path.is_dir():
            import shutil
            shutil.rmtree(full_path)
        else:
            full_path.unlink()
        
        return True
    
    async def file_exists(self, path: str) -> bool:
        """Check if file exists in workspace"""
        full_path = self._workspace_path / path.lstrip("/")
        return full_path.exists()
    
    async def list_directory(
        self,
        path: str = "",
        recursive: bool = False
    ) -> List[Dict[str, Any]]:
        """List directory contents"""
        full_path = self._workspace_path / path.lstrip("/") if path else self._workspace_path
        
        if not full_path.exists():
            return []
        
        results = []
        iterator = full_path.rglob("*") if recursive else full_path.iterdir()
        
        for item in iterator:
            try:
                stat = item.stat()
                rel_path = item.relative_to(self._workspace_path)
                
                results.append({
                    "name": item.name,
                    "path": str(rel_path),
                    "size": stat.st_size if item.is_file() else 0,
                    "is_directory": item.is_dir(),
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
        """Install package in container"""
        cmd = "pip install"
        if upgrade:
            cmd += " --upgrade"
        if version:
            cmd += f" {package}=={version}"
        else:
            cmd += f" {package}"
        
        return await self.execute_shell(cmd)
    
    async def uninstall_package(self, package: str) -> ExecutionResult:
        """Uninstall package from container"""
        return await self.execute_shell(f"pip uninstall -y {package}")
    
    async def list_packages(self) -> List[PackageInfo]:
        """List installed packages in container"""
        result = await self.execute_shell("pip list --format=json")
        
        if not result.success:
            return []
        
        try:
            packages = json.loads(result.stdout)
            return [PackageInfo(name=p["name"], version=p.get("version")) for p in packages]
        except Exception:
            return []
    
    async def set_env_var(self, key: str, value: str) -> None:
        """Set environment variable"""
        self._env_vars[key] = value
    
    async def get_env_var(self, key: str) -> Optional[str]:
        """Get environment variable"""
        if key in self._env_vars:
            return self._env_vars[key]
        
        result = await self.execute_shell(f"echo ${key}")
        if result.success:
            return result.stdout.strip() or None
        return None

    # Resource Monitoring
    async def get_resource_usage(self) -> Dict[str, Any]:
        """Get container resource usage"""
        if not self._container:
            return {"error": "Container not running"}
        
        try:
            self._container.reload()
            stats = self._container.stats(stream=False)
            
            # Calculate CPU usage
            cpu_delta = stats["cpu_stats"]["cpu_usage"]["total_usage"] - \
                        stats["precpu_stats"]["cpu_usage"]["total_usage"]
            system_delta = stats["cpu_stats"]["system_cpu_usage"] - \
                           stats["precpu_stats"]["system_cpu_usage"]
            cpu_percent = (cpu_delta / system_delta) * 100 if system_delta > 0 else 0
            
            # Memory usage
            memory_usage = stats["memory_stats"].get("usage", 0)
            memory_limit = stats["memory_stats"].get("limit", 1)
            memory_percent = (memory_usage / memory_limit) * 100
            
            return {
                "cpu_percent": round(cpu_percent, 2),
                "memory_mb": round(memory_usage / (1024 * 1024), 2),
                "memory_limit_mb": round(memory_limit / (1024 * 1024), 2),
                "memory_percent": round(memory_percent, 2),
                "container_status": self._container.status,
            }
        
        except Exception as e:
            return {"error": str(e)}
    
    async def get_logs(self, tail: int = 100) -> str:
        """Get container logs"""
        if not self._container:
            return ""
        
        try:
            logs = self._container.logs(tail=tail)
            return logs.decode("utf-8", errors="replace")
        except Exception as e:
            return f"Error getting logs: {e}"
