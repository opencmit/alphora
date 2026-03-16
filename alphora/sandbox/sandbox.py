"""
Sandbox 提供一个隔离的 Python 代码执行环境，支持本地进程和 Docker 容器两种运行时。所有操作均为异步接口

创建沙箱
1. 本地模式::
    async with Sandbox(runtime="local") as sb:
        result = await sb.execute_code("print(1 + 1)")
        print(result.stdout)

2. Docker 模式::
    async with Sandbox(
        workspace_root="/data/sandboxes",
        runtime="docker",
        image="alphora-sandbox:latest",
    ) as sb:
        result = await sb.execute_code("import pandas; print(pandas.__version__)")


工作目录模式 (mount_mode)
- direct: workspace_root 直接作为工作目录，适合每个请求/会话自行管理子目录的场景。
- isolated: 自动创建 workspace_root/<sandbox_id> 子目录，适合多租户或并发场景，每个沙箱互不影响。


Docker 容器化部署 (DooD)
当服务本身运行在 Docker 容器中，同时又需要 Docker 沙箱执行代码时，
需要挂载宿主机的 Docker Socket，让沙箱容器作为 兄弟容器 运行在宿主机上。
部署时保持路径一致即可，无需额外参数:

    # docker-compose.yml
    services:
      agent:
        volumes:
          - /var/run/docker.sock:/var/run/docker.sock
          - /data/sandboxes:/data/sandboxes   # 路径一致

    # Python 代码——和本地开发完全一样
    Sandbox(workspace_root="/data/sandboxes", runtime="docker")


远程 Docker (TCP + TLS)
通过 docker_host 连接远程 Docker daemon，workspace_root 指向远程服务器路径。

**重要：** 不要使用未加密的 2375 端口暴露 Docker daemon，否则任何人都可远程
控制你的服务器。请始终使用 TLS (端口 2376) 并配置客户端证书认证::

    from alphora.sandbox import Sandbox, DockerHost

    Sandbox(
        runtime="docker",
        docker_host=DockerHost(
            url="tcp://remote-host:2376",
            tls_verify=True,
            tls_ca_cert="/path/to/ca.pem",
            tls_client_cert="/path/to/cert.pem",
            tls_client_key="/path/to/key.pem",
        ),
        workspace_root="/data/sandboxes",        # 远程服务器上的路径
        skill_host_path="/opt/skills",           # 远程服务器上的路径
        image="alphora-sandbox:latest",
    )

也接受纯字符串（向后兼容，无 TLS）::
    Sandbox(
        runtime="docker",
        docker_host="unix:///var/run/docker.sock",
    )

相关环境变量（不传 docker_host 时自动读取）:
    - ``SANDBOX_DOCKER_HOST``: Docker daemon 连接地址 (如 tcp://host:2376)
    - ``SANDBOX_DOCKER_TLS_VERIFY``: 启用 TLS 验证 (true/false)
    - ``SANDBOX_DOCKER_TLS_CA_CERT``: CA 证书路径 (ca.pem)
    - ``SANDBOX_DOCKER_TLS_CLIENT_CERT``: 客户端证书路径 (cert.pem)
    - ``SANDBOX_DOCKER_TLS_CLIENT_KEY``: 客户端私钥路径 (key.pem)


生命周期钩子 (Hooks)
通过 hooks 参数注册回调，支持字符串别名和 HookEvent 枚举两种 key::

    async def log_start(ctx):
        print(f"沙箱 {ctx.data['sandbox_id']} 启动中...")

    async def log_result(ctx):
        print(f"执行结果: {ctx.data['result'].stdout}")

    Sandbox(
        runtime="docker",
        hooks={
            "before_start": log_start,
            "after_execute": log_result,
        },
    )

支持的钩子名称:
    ``before_start``, ``after_start``, ``before_stop``, ``after_stop``,
    ``before_execute``, ``after_execute``, ``before_write_file``, ``after_write_file``


文件与包管理
    async with Sandbox(runtime="docker") as sb:
        # 写入文件
        await sb.write_file("data.csv", "a,b\\n1,2\\n3,4")

        # 执行脚本文件
        await sb.write_file("main.py", "print(open('data.csv').read())")
        result = await sb.execute_file("main.py")

        # 安装 Python 包
        await sb.install_package("httpx")

        # 列出文件
        files = await sb.list_files()
"""
import os
import uuid
import asyncio
import logging
import base64
import binascii
from pathlib import Path
from datetime import datetime
from typing import Optional, List, Dict, Any, Union, TypeVar, Literal

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
from alphora.sandbox.config import DockerHost
from alphora.sandbox.path_resolver import PathResolver
from alphora.sandbox.workspace import Workspace
from alphora.sandbox.exceptions import (
    SandboxError,
    SandboxNotRunningError,
    SandboxAlreadyRunningError,
)
from alphora.hooks import HookEvent, HookContext, HookManager, build_manager

logger = logging.getLogger(__name__)

T = TypeVar("T", bound="Sandbox")


class Sandbox:
    """代码执行沙箱，详细使用说明见模块顶部文档。"""

    def __init__(
            self,
            workspace_root: str = "/tmp/sandboxes",
            mount_mode: Literal["direct", "isolated"] = "direct",
            runtime: Literal["docker", "local"] = "docker",
            image: str = "alphora-sandbox:latest",
            allow_network: bool = True,
            sandbox_id: Optional[str] = None,
            name: Optional[str] = None,
            resource_limits: Optional[ResourceLimits] = None,
            security_policy: Optional[SecurityPolicy] = None,
            auto_cleanup: bool = False,
            skill_host_path: Optional[str] = None,
            docker_host: Optional[Union[str, DockerHost]] = None,
            hooks: Optional[Union[HookManager, Dict[Any, Any]]] = None,
            **kwargs
    ):
        """
        Initialize sandbox.

        Args:
            workspace_root: Host path used as workspace mount root/path
            mount_mode: "direct" uses workspace_root directly, "isolated" uses workspace_root/<sandbox_id>
            runtime: Execution runtime ("local" or "docker")
            image: Docker image when backend is docker
            allow_network: Enable outbound network access
            sandbox_id: Unique identifier (auto-generated if not provided)
            name: Human-readable name
            resource_limits: Resource limits configuration
            security_policy: Security policy configuration
            auto_cleanup: Cleanup workspace on stop
            skill_host_path: Host path to skills directory, mounted read-only at /mnt/skills in Docker.
                For remote Docker (tcp://), this should be a path on the remote server.
            docker_host: Docker daemon connection. Accepts:

                - A :class:`DockerHost` object (recommended for TLS)::

                      DockerHost(
                          url="tcp://host:2376",
                          tls_verify=True,
                          tls_ca_cert="/certs/ca.pem",
                          tls_client_cert="/certs/cert.pem",
                          tls_client_key="/certs/key.pem",
                      )

                - A plain URL string (backward-compatible, no TLS)::

                      "tcp://host:2376"
                      "unix:///var/run/docker.sock"

                - ``None`` — auto-detects from ``SANDBOX_DOCKER_*`` env vars,
                  then falls back to the platform default.
            hooks: Hook callbacks. Accepts a :class:`HookManager` instance or a
                dict mapping hook names to callables. Supported string keys:
                ``before_start``, ``after_start``, ``before_stop``,
                ``after_stop``, ``before_execute``, ``after_execute``,
                ``before_write_file``, ``after_write_file``.
                :class:`HookEvent` enum values are also accepted as keys.
            **kwargs: Additional backend-specific options
        """
        # Handle runtime type
        runtime = BackendType(runtime.lower())

        if mount_mode not in ("direct", "isolated"):
            raise ValueError(f"Invalid mount_mode: {mount_mode}. Expected 'direct' or 'isolated'.")

        self._backend_type = runtime
        self._sandbox_id = sandbox_id or str(uuid.uuid4())[:8]
        self._name = name or f"sandbox-{self._sandbox_id}"
        self._mount_mode = mount_mode
        self._docker_image = image
        self._resource_limits = resource_limits or ResourceLimits()
        self._security_policy = security_policy or SecurityPolicy()

        # Simple and explicit: network flag always mirrors into limits + policy
        self._resource_limits.network_enabled = allow_network
        self._security_policy.allow_network = allow_network
        self._skill_host_path = Path(skill_host_path) if skill_host_path else None
        self._auto_cleanup = auto_cleanup
        self._extra_kwargs = kwargs

        if isinstance(docker_host, str):
            self._docker_host: Optional[DockerHost] = DockerHost.from_url(docker_host)
        elif isinstance(docker_host, DockerHost):
            self._docker_host = docker_host
        else:
            self._docker_host = DockerHost.from_env()

        self._hooks = build_manager(
            hooks,
            short_map={
                "before_start": HookEvent.SANDBOX_BEFORE_START,
                "after_start": HookEvent.SANDBOX_AFTER_START,
                "before_stop": HookEvent.SANDBOX_BEFORE_STOP,
                "after_stop": HookEvent.SANDBOX_AFTER_STOP,
                "before_execute": HookEvent.SANDBOX_BEFORE_EXECUTE,
                "after_execute": HookEvent.SANDBOX_AFTER_EXECUTE,
                "before_write_file": HookEvent.SANDBOX_BEFORE_WRITE_FILE,
                "after_write_file": HookEvent.SANDBOX_AFTER_WRITE_FILE,
            },
        )

        self._base_path = Path(workspace_root)
        if self._mount_mode == "direct":
            self._workspace_path = self._base_path
        else:
            self._workspace_path = self._base_path / self._sandbox_id
        self._path_resolver = PathResolver(Workspace(host_root=self._workspace_path))

        # State
        self._status = SandboxStatus.CREATED
        self._backend: Optional[ExecutionBackend] = None
        self._lock = asyncio.Lock()
        self._created_at = datetime.now()
        self._started_at: Optional[datetime] = None
        self._stopped_at: Optional[datetime] = None
        self._execution_count = 0

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
    def skill_host_path(self) -> Optional[Path]:
        """Get host path to skills directory (None if not configured)"""
        return self._skill_host_path

    def mount_skill(self, source: Union[str, Path, Any]) -> None:
        """Mount skills into the sandbox. Can be called before or after start().

        Args:
            source: Skill source -- either a host path (str/Path) containing
                skill subdirectories, or a ``SkillManager`` instance.
                When a SkillManager is passed, the host path is inferred
                automatically and the manager is configured to use sandbox
                paths for all subsequent output.
        """
        from alphora.skills.manager import SkillManager

        if isinstance(source, SkillManager):
            host_path = self._infer_skill_host_path(source)
            if host_path is None:
                return
            from alphora.sandbox.config import SANDBOX_SKILLS_MOUNT
            source.sandbox_skill_root = SANDBOX_SKILLS_MOUNT
        else:
            host_path = Path(source).expanduser().resolve()

        self._skill_host_path = host_path

        if self.is_running and self._backend:
            self._backend.mount_skill_path(str(host_path))

    @staticmethod
    def _infer_skill_host_path(manager: Any) -> Optional[Path]:
        """Infer the single host directory to mount from a SkillManager."""
        if manager.search_paths:
            if len(manager.search_paths) > 1:
                logger.warning(
                    "Multiple skill search paths but sandbox supports one mount. "
                    "Using the first: %s", manager.search_paths[0],
                )
            return manager.search_paths[0]

        parents = {skill.path.parent for skill in manager.skills.values()}
        if len(parents) == 1:
            return parents.pop()
        if len(parents) > 1:
            logger.warning(
                "Skills come from multiple parent directories %s. "
                "Pass skill_host_path to Sandbox() explicitly.", parents,
            )
        return None

    @property
    def mount_mode(self) -> str:
        """Get workspace mount mode."""
        return self._mount_mode

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
                await self._hooks.emit(
                    HookEvent.SANDBOX_BEFORE_START,
                    HookContext(
                        event=HookEvent.SANDBOX_BEFORE_START,
                        component="sandbox",
                        data={
                            "sandbox_id": self._sandbox_id,
                            "backend_type": self._backend_type,
                        },
                    ),
                )
                is_remote_docker = (
                    self._backend_type == BackendType.DOCKER
                    and self._docker_host
                    and self._docker_host.is_tcp
                )
                if not is_remote_docker:
                    self._workspace_path.mkdir(parents=True, exist_ok=True)

                # Create backend
                self._backend = self._create_backend()

                # Initialize and start
                await self._backend.initialize()
                await self._backend.start()

                self._status = SandboxStatus.RUNNING
                self._started_at = datetime.now()
                logger.info(f"Sandbox {self._sandbox_id} started")
                await self._hooks.emit(
                    HookEvent.SANDBOX_AFTER_START,
                    HookContext(
                        event=HookEvent.SANDBOX_AFTER_START,
                        component="sandbox",
                        data={
                            "sandbox_id": self._sandbox_id,
                            "backend_type": self._backend_type,
                            "status": self._status,
                        },
                    ),
                )
                return self

            except Exception as e:
                self._status = SandboxStatus.ERROR
                logger.error(f"Failed to start sandbox: {e}")
                raise

    async def stop(self) -> None:
        """Stop the sandbox."""
        async with self._lock:
            if self._status not in (SandboxStatus.RUNNING, SandboxStatus.STARTING):
                return

            self._status = SandboxStatus.STOPPING
            logger.info(f"Stopping sandbox {self._sandbox_id}")

            try:
                await self._hooks.emit(
                    HookEvent.SANDBOX_BEFORE_STOP,
                    HookContext(
                        event=HookEvent.SANDBOX_BEFORE_STOP,
                        component="sandbox",
                        data={
                            "sandbox_id": self._sandbox_id,
                            "backend_type": self._backend_type,
                        },
                    ),
                )
                if self._backend:
                    await self._backend.stop()

                self._status = SandboxStatus.STOPPED
                self._stopped_at = datetime.now()

                if self._auto_cleanup:
                    await self._cleanup()

                logger.info(f"Sandbox {self._sandbox_id} stopped")
                await self._hooks.emit(
                    HookEvent.SANDBOX_AFTER_STOP,
                    HookContext(
                        event=HookEvent.SANDBOX_AFTER_STOP,
                        component="sandbox",
                        data={
                            "sandbox_id": self._sandbox_id,
                            "backend_type": self._backend_type,
                            "status": self._status,
                        },
                    ),
                )

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
        # Never remove user-provided workspace root in direct mode.
        if self._mount_mode == "direct":
            return

        import shutil
        if self._workspace_path.exists():
            try:
                shutil.rmtree(self._workspace_path)
            except Exception as e:
                logger.warning(f"Failed to cleanup workspace: {e}")

    def _create_backend(self) -> ExecutionBackend:
        """Create execution backend instance"""
        backend_kwargs = {
            "sandbox_id": self._sandbox_id,
            "workspace_path": str(self._workspace_path),
            "resource_limits": self._resource_limits,
            "security_policy": self._security_policy,
        }

        if self._skill_host_path:
            backend_kwargs["skill_host_path"] = str(self._skill_host_path)

        if self._backend_type == BackendType.DOCKER:
            backend_kwargs["docker_image"] = self._docker_image
            if self._docker_host:
                backend_kwargs["docker_host"] = self._docker_host

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
        before_ctx = HookContext(
            event=HookEvent.SANDBOX_BEFORE_EXECUTE,
            component="sandbox",
            data={
                "operation": "execute_code",
                "code": code,
                "timeout": timeout,
                "kwargs": kwargs,
                "sandbox_id": self._sandbox_id,
            },
        )
        before_ctx = await self._hooks.emit(HookEvent.SANDBOX_BEFORE_EXECUTE, before_ctx)
        code = before_ctx.data.get("code", code)
        timeout = before_ctx.data.get("timeout", timeout)
        result = await self._backend.execute_code(code, timeout=timeout, **kwargs)
        self._execution_count += 1
        await self._hooks.emit(
            HookEvent.SANDBOX_AFTER_EXECUTE,
            HookContext(
                event=HookEvent.SANDBOX_AFTER_EXECUTE,
                component="sandbox",
                data={
                    "operation": "execute_code",
                    "code": code,
                    "timeout": timeout,
                    "result": result,
                    "sandbox_id": self._sandbox_id,
                },
            ),
        )
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
        before_ctx = HookContext(
            event=HookEvent.SANDBOX_BEFORE_EXECUTE,
            component="sandbox",
            data={
                "operation": "execute_file",
                "file_path": file_path,
                "args": args,
                "timeout": timeout,
                "kwargs": kwargs,
                "sandbox_id": self._sandbox_id,
            },
        )
        before_ctx = await self._hooks.emit(HookEvent.SANDBOX_BEFORE_EXECUTE, before_ctx)
        file_path = before_ctx.data.get("file_path", file_path)
        args = before_ctx.data.get("args", args)
        timeout = before_ctx.data.get("timeout", timeout)
        result = await self._backend.execute_file(file_path, args=args, timeout=timeout, **kwargs)
        self._execution_count += 1
        await self._hooks.emit(
            HookEvent.SANDBOX_AFTER_EXECUTE,
            HookContext(
                event=HookEvent.SANDBOX_AFTER_EXECUTE,
                component="sandbox",
                data={
                    "operation": "execute_file",
                    "file_path": file_path,
                    "args": args,
                    "timeout": timeout,
                    "result": result,
                    "sandbox_id": self._sandbox_id,
                },
            ),
        )
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
        before_ctx = HookContext(
            event=HookEvent.SANDBOX_BEFORE_EXECUTE,
            component="sandbox",
            data={
                "operation": "execute_shell",
                "command": command,
                "timeout": timeout,
                "kwargs": kwargs,
                "sandbox_id": self._sandbox_id,
            },
        )
        before_ctx = await self._hooks.emit(HookEvent.SANDBOX_BEFORE_EXECUTE, before_ctx)
        command = before_ctx.data.get("command", command)
        timeout = before_ctx.data.get("timeout", timeout)
        result = await self._backend.execute_shell(command, timeout=timeout, **kwargs)
        self._execution_count += 1
        await self._hooks.emit(
            HookEvent.SANDBOX_AFTER_EXECUTE,
            HookContext(
                event=HookEvent.SANDBOX_AFTER_EXECUTE,
                component="sandbox",
                data={
                    "operation": "execute_shell",
                    "command": command,
                    "timeout": timeout,
                    "result": result,
                    "sandbox_id": self._sandbox_id,
                },
            ),
        )
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
        before_ctx = HookContext(
            event=HookEvent.SANDBOX_BEFORE_WRITE_FILE,
            component="sandbox",
            data={
                "path": path,
                "content": content,
                "sandbox_id": self._sandbox_id,
            },
        )
        before_ctx = await self._hooks.emit(HookEvent.SANDBOX_BEFORE_WRITE_FILE, before_ctx)
        path = before_ctx.data.get("path", path)
        content = before_ctx.data.get("content", content)
        await self._backend.write_file(path, content)
        await self._hooks.emit(
            HookEvent.SANDBOX_AFTER_WRITE_FILE,
            HookContext(
                event=HookEvent.SANDBOX_AFTER_WRITE_FILE,
                component="sandbox",
                data={
                    "path": path,
                    "size": len(content.encode("utf-8")),
                    "sandbox_id": self._sandbox_id,
                },
            ),
        )

    async def write_file_bytes(self, path: str, content: bytes) -> None:
        """Write binary content to file."""
        self._ensure_running()
        before_ctx = HookContext(
            event=HookEvent.SANDBOX_BEFORE_WRITE_FILE,
            component="sandbox",
            data={
                "path": path,
                "content": content,
                "sandbox_id": self._sandbox_id,
            },
        )
        before_ctx = await self._hooks.emit(HookEvent.SANDBOX_BEFORE_WRITE_FILE, before_ctx)
        path = before_ctx.data.get("path", path)
        content = before_ctx.data.get("content", content)
        await self._backend.write_file_bytes(path, content)
        await self._hooks.emit(
            HookEvent.SANDBOX_AFTER_WRITE_FILE,
            HookContext(
                event=HookEvent.SANDBOX_AFTER_WRITE_FILE,
                component="sandbox",
                data={
                    "path": path,
                    "size": len(content),
                    "sandbox_id": self._sandbox_id,
                },
            ),
        )

    async def upload_file(self, file_name: str, base64_data: str) -> FileInfo:
        """
        Upload a file to /mnt/workspace/uploads/.

        Supports raw Base64 strings and data URLs (data:*;base64,...).

        Usage::

            info = await sb.upload_file("report.xlsx", base64_string)
            # info.path == "/mnt/workspace/uploads/report.xlsx"

        Args:
            file_name: Target file name, e.g. ``"data.xlsx"``.
                       Subdirectories are allowed, e.g. ``"sub/data.xlsx"``.
            base64_data: Base64-encoded content (raw or data URL)

        Returns:
            FileInfo with ``path`` set to the sandbox-convention path.
        """
        self._ensure_running()
        if not base64_data:
            raise ValueError("base64_data is empty")

        base64_str = base64_data
        if ',' in base64_data:
            base64_str = base64_data.split(',')[1]

        clean_name = file_name.lstrip("/")
        sandbox_path = f"/mnt/workspace/uploads/{clean_name}"

        decoded_data = base64.urlsafe_b64decode(base64_str)
        await self._backend.write_file_bytes(sandbox_path, decoded_data)

        return FileInfo(
            name=Path(sandbox_path).name,
            path=sandbox_path,
            size=len(decoded_data),
            file_type=FileType.from_extension(sandbox_path),
        )

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
        before_ctx = HookContext(
            event=HookEvent.SANDBOX_BEFORE_WRITE_FILE,
            component="sandbox",
            data={
                "path": path,
                "content": content,
                "sandbox_id": self._sandbox_id,
            },
        )
        before_ctx = await self._hooks.emit(HookEvent.SANDBOX_BEFORE_WRITE_FILE, before_ctx)
        path = before_ctx.data.get("path", path)
        content = before_ctx.data.get("content", content)
        await self._backend.write_file(path, content)

        file_info = FileInfo(
            name=Path(path).name,
            path=path,
            size=len(content.encode("utf-8")),
            file_type=FileType.from_extension(path),
        )
        await self._hooks.emit(
            HookEvent.SANDBOX_AFTER_WRITE_FILE,
            HookContext(
                event=HookEvent.SANDBOX_AFTER_WRITE_FILE,
                component="sandbox",
                data={
                    "path": path,
                    "size": len(content.encode("utf-8")),
                    "file_info": file_info,
                    "sandbox_id": self._sandbox_id,
                },
            ),
        )
        return file_info

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
            path: Optional[str] = None,
            recursive: bool = False,
            pattern: Optional[str] = None
    ) -> List[FileInfo]:
        """
        List files in directory.

        Args:
            path: Directory path. If None, list all files recursively from workspace root.
            recursive: Include subdirectories
            pattern: Filename pattern filter (glob)

        Returns:
            List of FileInfo objects
        """
        self._ensure_running()

        if path is None:
            path = ""
            recursive = True

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
            "mount_mode": self._mount_mode,
            "workspace_path": str(self._workspace_path),
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
        转换至宿主机的绝对路径
        """
        return self._path_resolver.to_host(path)

    # Context Manager
    async def __aenter__(self: T) -> T:
        await self.start()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb) -> None:
        await self.stop()

    def __repr__(self) -> str:
        return f"Sandbox(id={self._sandbox_id!r}, runtime={self._backend_type.value!r}, mount_mode={self._mount_mode!r}, status={self._status.value!r})"

