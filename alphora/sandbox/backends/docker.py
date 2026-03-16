"""
Alphora Sandbox - Docker Execution Backend

Docker container-based execution backend.
"""
import asyncio
import io
import json
import logging
import os
import tarfile
import time
from pathlib import Path, PurePosixPath
from typing import Optional, List, Dict, Any

from alphora.sandbox.backends.base import ExecutionBackend, BackendFactory
from alphora.sandbox.path_resolver import PathResolver
from alphora.sandbox.types import (
    ExecutionResult,
    ResourceLimits,
    SecurityPolicy,
    PackageInfo,
    FileInfo,
    FileType,
)
from alphora.sandbox.workspace import Workspace
from alphora.sandbox.config import (
    DockerHost,
    DockerConfig,
    SANDBOX_SKILLS_MOUNT,
)
from alphora.sandbox.exceptions import (
    DockerError,
    ContainerError,
    ContainerNotFoundError,
    FileNotFoundError as SandboxFileNotFoundError,
    ExecutionTimeoutError,
    PathTraversalError,
)

logger = logging.getLogger(__name__)


def _is_running_in_docker() -> bool:
    """Detect if the current process is running inside a Docker container."""
    if Path("/.dockerenv").exists():
        return True
    try:
        with open("/proc/1/cgroup", "r") as f:
            content = f.read()
            return "docker" in content or "containerd" in content
    except Exception:
        return False


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
        - Remote Docker daemon support (tcp://)
    
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
        skill_host_path: Optional[str] = None,
        docker_host: Optional[DockerHost] = None,
        **kwargs
    ):
        """
        Initialize Docker backend.
        
        Args:
            sandbox_id: Unique sandbox identifier
            workspace_path: Path to workspace directory. For local Docker this
                is a local path; for remote Docker (tcp://) this must be an
                absolute path on the remote server.
            resource_limits: Resource limits configuration
            security_policy: Security policy configuration
            docker_image: Docker image to use
            docker_config: Docker-specific configuration
            skill_host_path: Path to skills directory (mounted read-only at
                /mnt/skills). For remote Docker, this should be a path on the
                remote server.
            docker_host: Docker daemon connection configuration. A
                :class:`DockerHost` instance that encapsulates the URL
                and optional TLS settings. When ``None``, falls back to
                ``DockerConfig.docker_host``, then ``docker.from_env()``.
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
        self._skill_host_path = Path(skill_host_path) if skill_host_path else None
        self._docker_host: Optional[DockerHost] = docker_host or self._docker_config.docker_host

        self._docker_dir = Path(__file__).parent.parent / "docker"

        self._container = None
        self._client = None
        self._container_workspace = self._docker_config.working_dir
        self._env_vars: Dict[str, str] = {}
        self._path_resolver = PathResolver(
            Workspace(host_root=self._workspace_path, sandbox_root=self._container_workspace)
        )

    @property
    def _is_remote(self) -> bool:
        """Whether the Docker daemon is a remote TCP connection."""
        return bool(self._docker_host and self._docker_host.is_tcp)
    
    @property
    def container_id(self) -> Optional[str]:
        """Get container ID"""
        return self._container.id if self._container else None
    
    @property
    def container_name(self) -> str:
        """Get container name"""
        return f"sandbox-{self.sandbox_id}"

    # ------------------------------------------------------------------ #
    # Lifecycle
    # ------------------------------------------------------------------ #

    def _build_tls_config(self):
        """Build TLS configuration for Docker client if enabled.

        Returns ``None`` when TLS is not requested; otherwise returns a
        ``docker.tls.TLSConfig`` instance suitable for passing to
        ``DockerClient``.

        Raises:
            DockerError: when required certificate files are missing.
        """
        dh = self._docker_host
        if not dh or not dh.tls_verify:
            return None

        import docker

        if dh.tls_client_cert and dh.tls_client_key:
            for label, path in [
                ("CA cert", dh.tls_ca_cert),
                ("client cert", dh.tls_client_cert),
                ("client key", dh.tls_client_key),
            ]:
                if path and not Path(path).exists():
                    raise DockerError(f"TLS {label} file not found: {path}")

            return docker.tls.TLSConfig(
                ca_cert=dh.tls_ca_cert,
                client_cert=(dh.tls_client_cert, dh.tls_client_key),
                verify=True,
            )

        if dh.tls_ca_cert:
            if not Path(dh.tls_ca_cert).exists():
                raise DockerError(f"TLS CA cert file not found: {dh.tls_ca_cert}")
            return docker.tls.TLSConfig(ca_cert=dh.tls_ca_cert, verify=True)

        return docker.tls.TLSConfig(verify=True)

    async def initialize(self) -> None:
        """Initialize the backend: connect to daemon, validate image."""
        try:
            import docker
            if self._docker_host:
                tls_config = self._build_tls_config()
                if self._is_remote and not tls_config:
                    logger.warning(
                        "Connecting to remote Docker daemon WITHOUT TLS. "
                        "This is insecure — the daemon is exposed to the network without "
                        "encryption or authentication. Use DockerHost(tls_verify=True, ...) "
                        "or set SANDBOX_DOCKER_TLS_VERIFY=true."
                    )
                kwargs = {"base_url": self._docker_host.url}
                if tls_config:
                    kwargs["tls"] = tls_config
                self._client = docker.DockerClient(**kwargs)
                proto = "TLS" if tls_config else "plain"
                logger.info(f"Connected to Docker daemon at {self._docker_host.url} ({proto})")
            else:
                self._client = docker.from_env()
        except ImportError:
            raise DockerError("docker package not installed. Install with: pip install docker")

        if self._is_remote:
            await self._initialize_remote()
        else:
            await self._initialize_local()

    async def _initialize_remote(self) -> None:
        """Remote-specific initialization: validate paths and image."""
        if not self._workspace_path.is_absolute():
            raise DockerError(
                f"Remote Docker (tcp://) requires an absolute workspace_root, "
                f"got relative path: '{self._workspace_path}'"
            )

        try:
            self._client.images.get(self._docker_image)
            logger.info(f"Using existing remote image: {self._docker_image}")
        except Exception:
            available = self._list_remote_images()
            img_list = "\n".join(f"  - {t}" for t in available) if available else "  (none)"
            raise DockerError(
                f"Image '{self._docker_image}' not found on remote Docker daemon "
                f"{self._docker_host.url}.\n\nAvailable images:\n{img_list}"
            )

    def _list_remote_images(self) -> List[str]:
        """Return a sorted list of image:tag strings from the remote daemon."""
        try:
            images = self._client.images.list()
            tags: List[str] = []
            for img in images:
                tags.extend(img.tags)
            return sorted(tags)
        except Exception:
            return []

    async def _initialize_local(self) -> None:
        """Local/DooD initialization: check image, create directories."""
        try:
            self._client.images.get(self._docker_image)
            logger.info(f"Using existing sandbox image: {self._docker_image}")
        except Exception:
            if self._docker_image.startswith("alphora"):
                await self._build_custom_image()
            else:
                logger.info(f"Pulling image {self._docker_image}...")
                self._client.images.pull(self._docker_image)

        self._workspace_path.mkdir(parents=True, exist_ok=True)
        (self._workspace_path / "uploads").mkdir(parents=True, exist_ok=True)
        (self._workspace_path / "outputs").mkdir(parents=True, exist_ok=True)

    async def _build_custom_image(self) -> None:
        """Build custom image from local Dockerfile."""
        logger.info(
            f"Image {self._docker_image} not found. Performing first-time setup; "
            "please be patient as the build process completes (this may take a few minutes) ..."
        )

        if not self._docker_dir.exists():
            raise DockerError(f"Docker build directory not found at {self._docker_dir}")

        try:
            image, logs = self._client.images.build(
                path=str(self._docker_dir),
                tag=self._docker_image,
                rm=True,
                target="base",
            )
            for line in logs:
                if "stream" in line:
                    logger.debug(line["stream"].strip())
            logger.info(f"Successfully built {self._docker_image}")
        except Exception as e:
            build_log = ""
            if hasattr(e, "build_log"):
                build_log = "\n".join(
                    line.get("stream", line.get("error", "")).rstrip()
                    for line in e.build_log
                    if line.get("stream") or line.get("error")
                )
            detail = f"\n\nBuild log:\n{build_log}" if build_log else ""
            raise DockerError(
                f"Failed to build custom sandbox image: {e}{detail}"
            )
    
    async def start(self) -> None:
        """Start the Docker container"""
        if self._container:
            try:
                self._container.start()
                self._running = True
                return
            except Exception:
                pass
        
        container_config = self._build_container_config()
        
        try:
            self._container = self._client.containers.run(**container_config)
            self._running = True
            await self._wait_for_ready()
            self._init_workspace_dirs()
            if self._skill_host_path:
                if self._is_remote:
                    self._sync_skills_to_container()
                self._create_skills_symlink()
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

    # ------------------------------------------------------------------ #
    # Container helpers
    # ------------------------------------------------------------------ #
    
    def _build_container_config(self) -> Dict[str, Any]:
        """Build Docker container configuration"""
        config = self._docker_config
        limits = self.resource_limits
        
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
            "mem_limit": f"{limits.memory_mb}m",
            "cpu_period": config.cpu_period,
            "cpu_quota": int(config.cpu_period * limits.cpu_cores),
            "pids_limit": config.pids_limit,
            "security_opt": config.security_opt,
            "cap_drop": config.cap_drop,
            "cap_add": config.cap_add,
            "privileged": config.privileged,
            "read_only": config.read_only_root,
            "volumes": self._build_volumes(),
            "environment": {
                **config.environment,
                **self._env_vars,
                "SANDBOX_ID": self.sandbox_id,
            },
            "command": "tail -f /dev/null",
        }
        
        if config.user:
            container_config["user"] = config.user
        
        return container_config

    def _build_volumes(self) -> Dict[str, Dict[str, str]]:
        """Build volume mount configuration.

        ``workspace_path`` is always the Docker-host path used as volume source.
        uploads/ and outputs/ live inside workspace, no separate mounts needed.
        For remote mode, skills are NOT bind-mounted (local path doesn't exist
        on the remote server); they are copied into the container after start.
        """
        volumes = {
            str(self._workspace_path.resolve()): {
                "bind": self._container_workspace,
                "mode": "rw",
            },
        }
        if self._skill_host_path and not self._is_remote and self._skill_host_path.is_dir():
            volumes[str(self._skill_host_path.resolve())] = {
                "bind": SANDBOX_SKILLS_MOUNT,
                "mode": "ro",
            }
        return volumes

    def _resolve_path(self, path: str) -> Path:
        """Resolve file path to host path inside workspace boundaries."""
        return self._path_resolver.to_host(path)

    def _to_container_path(self, path: str) -> str:
        """Convert any supported path to a container-absolute path."""
        return self._path_resolver.to_sandbox(path)
    
    async def _wait_for_ready(self, timeout: int = 30) -> None:
        """Wait for container to be ready"""
        start = time.time()
        while time.time() - start < timeout:
            try:
                self._container.reload()
                if self._container.status == "running":
                    result = self._container.exec_run("python --version")
                    if result.exit_code == 0:
                        return
            except Exception:
                pass
            await asyncio.sleep(0.5)
        raise ContainerError(self.container_name, "Container failed to become ready")

    def _init_workspace_dirs(self) -> None:
        """Create standard workspace subdirectories (uploads, outputs)."""
        ws = self._container_workspace
        self._container.exec_run(
            ["sh", "-c", f"mkdir -p {ws}/uploads {ws}/outputs"],
            user="root",
        )

    def mount_skill_path(self, host_path: str) -> None:
        """Dynamically mount a skill directory into a running container.

        For local Docker: recreates the container with a proper ``-v``
        bind-mount so that ``/mnt/skills`` and the workspace symlink
        work reliably on all platforms (including macOS VirtioFS).

        For remote Docker: copies files via tar + put_archive and creates
        a symlink, since the host path does not exist on the remote server.
        """
        self._skill_host_path = Path(host_path)

        if self._is_remote:
            self._sync_skills_to_container()
            self._create_skills_symlink()
        else:
            self._recreate_with_skill_volume()

    def _sync_skills_to_container(self) -> None:
        """Copy local skills directory into the container at /mnt/skills."""
        skill_path = self._skill_host_path
        if not skill_path or not skill_path.is_dir():
            logger.warning(f"Skills path not found locally: {skill_path}")
            return

        self._container.exec_run(
            ["sh", "-c", f"mkdir -p {SANDBOX_SKILLS_MOUNT}"],
            user="root",
        )

        buf = io.BytesIO()
        with tarfile.open(fileobj=buf, mode="w") as tar:
            for root, dirs, files in os.walk(skill_path):
                for fname in files:
                    full = os.path.join(root, fname)
                    arcname = os.path.relpath(full, skill_path)
                    tar.add(full, arcname=arcname)
                for dname in dirs:
                    full = os.path.join(root, dname)
                    arcname = os.path.relpath(full, skill_path)
                    tar.add(full, arcname=arcname, recursive=False)
        buf.seek(0)
        self._container.put_archive(SANDBOX_SKILLS_MOUNT, buf)
        logger.info(
            f"Synced local skills ({skill_path}) to container at {SANDBOX_SKILLS_MOUNT}"
        )

    def _create_skills_symlink(self) -> None:
        """Create /mnt/workspace/skills -> /mnt/skills symlink in the container.

        Used for remote Docker where volumes cannot be bind-mounted from
        the local host. On local Docker, prefer ``_recreate_with_skill_volume``.
        """
        ws = self._container_workspace
        script = (
            f"ln -sfn {SANDBOX_SKILLS_MOUNT} {ws}/skills"
        )
        result = self._container.exec_run(["sh", "-c", script], user="root")
        if result.exit_code != 0:
            logger.warning(
                "Failed to create skills symlink in container: %s",
                result.output.decode(errors="replace") if result.output else "unknown",
            )

    def _recreate_with_skill_volume(self) -> None:
        """Recreate the container with a proper Docker bind-mount for skills.

        Docker does not allow adding volumes to a running container, so we
        stop, remove, and recreate it with the updated volume configuration.
        This is the reliable approach for local Docker (including macOS
        with VirtioFS) where symlinks inside bind-mounted directories
        pointing to container-internal paths do not resolve correctly.
        """
        logger.info(
            "Recreating container with skill volume: %s -> %s",
            self._skill_host_path, SANDBOX_SKILLS_MOUNT,
        )

        try:
            self._container.stop(timeout=5)
        except Exception:
            pass
        try:
            self._container.remove(force=True)
        except Exception:
            pass

        config = self._build_container_config()
        self._container = self._client.containers.run(**config)
        self._running = True

        start = time.time()
        while time.time() - start < 30:
            try:
                self._container.reload()
                if self._container.status == "running":
                    result = self._container.exec_run("echo ok")
                    if result.exit_code == 0:
                        break
            except Exception:
                pass
            time.sleep(0.5)

        self._init_workspace_dirs()
        self._create_skills_symlink()
        logger.info(
            "Container %s restarted with skill volume: %s",
            self.container_name, self._skill_host_path,
        )

    # ------------------------------------------------------------------ #
    # Code Execution
    # ------------------------------------------------------------------ #

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
        container_path = self._to_container_path(file_path)
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
            loop = asyncio.get_event_loop()
            
            def run_exec():
                return self._container.exec_run(
                    ["sh", "-c", command],
                    workdir=self._container_workspace,
                    environment=self._env_vars,
                    demux=True,
                )
            
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

    # ------------------------------------------------------------------ #
    # File Operations
    # ------------------------------------------------------------------ #

    async def read_file(self, path: str) -> str:
        """Read file from container workspace"""
        if self._is_remote:
            return (await self._remote_read_file(path)).decode("utf-8")
        full_path = self._resolve_path(path)
        if not full_path.exists():
            raise SandboxFileNotFoundError(path)
        return full_path.read_text(encoding="utf-8")

    async def read_file_bytes(self, path: str) -> bytes:
        """Read file as bytes from container workspace"""
        if self._is_remote:
            return await self._remote_read_file(path)
        full_path = self._resolve_path(path)
        if not full_path.exists():
            raise SandboxFileNotFoundError(path)
        return full_path.read_bytes()
    
    async def write_file(self, path: str, content: str) -> None:
        """Write file to container workspace"""
        if self._is_remote:
            await self._remote_write_file(path, content.encode("utf-8"))
            return
        full_path = self._resolve_path(path)
        full_path.parent.mkdir(parents=True, exist_ok=True)
        full_path.write_text(content, encoding="utf-8")

    async def write_file_bytes(self, path: str, content: bytes) -> None:
        """Write bytes to file in container workspace"""
        if self._is_remote:
            await self._remote_write_file(path, content)
            return
        full_path = self._resolve_path(path)
        full_path.parent.mkdir(parents=True, exist_ok=True)
        full_path.write_bytes(content)
    
    async def delete_file(self, path: str) -> bool:
        """Delete file from container workspace"""
        if self._is_remote:
            container_path = self._to_container_path(path)
            result = self._container.exec_run(["sh", "-c", f"rm -rf '{container_path}'"])
            return result.exit_code == 0
        full_path = self._resolve_path(path)
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
        if self._is_remote:
            container_path = self._to_container_path(path)
            result = self._container.exec_run(["sh", "-c", f"test -e '{container_path}'"])
            return result.exit_code == 0
        try:
            full_path = self._resolve_path(path)
        except PathTraversalError:
            return False
        return full_path.exists()
    
    async def list_directory(
        self,
        path: str = "",
        recursive: bool = False
    ) -> List[Dict[str, Any]]:
        """List directory contents"""
        if self._is_remote:
            return await self._remote_list_directory(path, recursive)
        full_path = self._resolve_path(path) if path else self._workspace_path
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

    # ---- Remote file helpers (via Docker API) ---- #

    async def _remote_read_file(self, path: str) -> bytes:
        """Read a file from the container using get_archive."""
        container_path = self._to_container_path(path)
        try:
            stream, stat = self._container.get_archive(container_path)
        except Exception:
            raise SandboxFileNotFoundError(path)
        tar_bytes = b"".join(chunk for chunk in stream)
        with tarfile.open(fileobj=io.BytesIO(tar_bytes), mode="r") as tar:
            member = tar.getmembers()[0]
            f = tar.extractfile(member)
            if f is None:
                raise SandboxFileNotFoundError(path)
            return f.read()

    async def _remote_write_file(self, path: str, content: bytes) -> None:
        """Write a file into the container using put_archive."""
        container_path = self._to_container_path(path)
        posix = PurePosixPath(container_path)
        parent_dir = str(posix.parent)
        file_name = posix.name

        self._container.exec_run(["sh", "-c", f"mkdir -p '{parent_dir}'"])

        buf = io.BytesIO()
        with tarfile.open(fileobj=buf, mode="w") as tar:
            info = tarfile.TarInfo(name=file_name)
            info.size = len(content)
            tar.addfile(info, io.BytesIO(content))
        buf.seek(0)
        self._container.put_archive(parent_dir, buf)

    async def _remote_list_directory(
        self, path: str = "", recursive: bool = False
    ) -> List[Dict[str, Any]]:
        """List directory inside the container via exec."""
        container_path = self._to_container_path(path) if path else self._container_workspace

        script = (
            "import os, json, sys\n"
            f"root = '{container_path}'\n"
            f"workspace = '{self._container_workspace}'\n"
            f"recursive = {recursive}\n"
            "results = []\n"
            "if not os.path.isdir(root):\n"
            "    json.dump([], sys.stdout); sys.exit(0)\n"
            "if recursive:\n"
            "    for dirpath, dirnames, filenames in os.walk(root):\n"
            "        for name in dirnames + filenames:\n"
            "            full = os.path.join(dirpath, name)\n"
            "            rel = os.path.relpath(full, workspace)\n"
            "            is_dir = os.path.isdir(full)\n"
            "            size = 0 if is_dir else os.path.getsize(full)\n"
            "            results.append({'name': name, 'path': rel, 'size': size, 'is_directory': is_dir})\n"
            "else:\n"
            "    for name in os.listdir(root):\n"
            "        full = os.path.join(root, name)\n"
            "        rel = os.path.relpath(full, workspace)\n"
            "        is_dir = os.path.isdir(full)\n"
            "        size = 0 if is_dir else os.path.getsize(full)\n"
            "        results.append({'name': name, 'path': rel, 'size': size, 'is_directory': is_dir})\n"
            "results.sort(key=lambda x: (not x['is_directory'], x['name']))\n"
            "json.dump(results, sys.stdout)\n"
        )
        result = self._container.exec_run(
            ["python", "-c", script],
            workdir=self._container_workspace,
            demux=True,
        )
        stdout = result.output[0].decode("utf-8") if result.output[0] else "[]"
        try:
            items = json.loads(stdout)
            for item in items:
                item.setdefault("file_type", FileType.from_extension(item.get("name", "")).value)
            return items
        except Exception:
            return []

    # ------------------------------------------------------------------ #
    # Package Management
    # ------------------------------------------------------------------ #

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

    # ------------------------------------------------------------------ #
    # Resource Monitoring
    # ------------------------------------------------------------------ #

    async def get_resource_usage(self) -> Dict[str, Any]:
        """Get container resource usage"""
        if not self._container:
            return {"error": "Container not running"}
        try:
            self._container.reload()
            stats = self._container.stats(stream=False)
            cpu_delta = stats["cpu_stats"]["cpu_usage"]["total_usage"] - \
                        stats["precpu_stats"]["cpu_usage"]["total_usage"]
            system_delta = stats["cpu_stats"]["system_cpu_usage"] - \
                           stats["precpu_stats"]["system_cpu_usage"]
            cpu_percent = (cpu_delta / system_delta) * 100 if system_delta > 0 else 0
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
