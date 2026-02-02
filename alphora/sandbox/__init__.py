"""
Alphora Sandbox - Secure Code Execution Environment

A production-ready sandbox component for executing code in isolated environments.

Features:
    - Multiple execution backends (Local, Docker)
    - Storage backends (Local, S3, MinIO)
    - Resource limits and security policies
    - AI Agent tool integrations
    - Async context manager support

Quick Start:
    ```python
    from alphora.sandbox import Sandbox
    
    async with Sandbox.create_local() as sandbox:
        result = await sandbox.run("print('Hello, World!')")
        print(result.stdout)  # Hello, World!
    ```

Docker Backend:
    ```python
    from alphora.sandbox import Sandbox
    
    async with Sandbox.create_docker(docker_image="python:3.11") as sandbox:
        result = await sandbox.run("import sys; print(sys.version)")
        print(result.stdout)
    ```

With AI Agent Tools:
    ```python
    from alphora.sandbox import Sandbox, SandboxTools
    
    async with Sandbox.create_local() as sandbox:
        tools = SandboxTools(sandbox)
        
        # Get tool definitions for OpenAI/Anthropic
        openai_tools = tools.get_openai_tools()
        anthropic_tools = tools.get_anthropic_tools()
        
        # Execute tools
        result = await tools.run_python_code("print(1+1)")
    ```

Multi-Sandbox Management:
    ```python
    from alphora.sandbox import SandboxManager
    
    async with SandboxManager() as manager:
        sandbox1 = await manager.create_sandbox("worker-1")
        sandbox2 = await manager.create_sandbox("worker-2")
        
        # Run code in parallel
        results = await asyncio.gather(
            sandbox1.run("print('worker 1')"),
            sandbox2.run("print('worker 2')")
        )
    ```
"""
from alphora.sandbox.sandbox import Sandbox
from alphora.sandbox.manager import SandboxManager
from alphora.sandbox.agent_tools import SandboxTools, get_tool_definitions, get_openai_tools

from alphora.sandbox.types import (
    BackendType,
    StorageType,
    SandboxStatus,
    ExecutionStatus,
    FileType,
    ResourceLimits,
    SecurityPolicy,
    ExecutionResult,
    FileInfo,
    PackageInfo,
    SandboxInfo,
    ResourceUsage,
)

from alphora.sandbox.config import (
    SandboxConfig,
    StorageConfig,
    DockerConfig,
    config_from_env,
    config_from_file,
)

from alphora.sandbox.exceptions import (
    SandboxError,
    SandboxNotFoundError,
    SandboxAlreadyExistsError,
    SandboxNotRunningError,
    SandboxAlreadyRunningError,
    ExecutionError,
    ExecutionTimeoutError,
    ExecutionFailedError,
    FileSystemError,
    FileNotFoundError,
    PathTraversalError,
    PackageError,
    PackageInstallError,
    SecurityViolationError,
    BackendError,
    DockerError,
    StorageError,
    ConfigurationError,
)

from alphora.sandbox.backends import (
    ExecutionBackend,
    BackendFactory,
    LocalBackend,
    DockerBackend,
    is_docker_available,
)

from alphora.sandbox.storage import (
    StorageBackend,
    StorageObject,
    StorageFactory,
    LocalStorage,
    S3Storage,
)

__all__ = [
    "Sandbox",
    "SandboxManager",
    "SandboxTools",
    "get_tool_definitions",
    "get_openai_tools",
    "BackendType",
    "StorageType",
    "SandboxStatus",
    "ExecutionStatus",
    "FileType",
    "ResourceLimits",
    "SecurityPolicy",
    "ExecutionResult",
    "FileInfo",
    "PackageInfo",
    "SandboxInfo",
    "ResourceUsage",
    "SandboxConfig",
    "StorageConfig",
    "DockerConfig",
    "config_from_env",
    "config_from_file",
    "SandboxError",
    "SandboxNotFoundError",
    "SandboxAlreadyExistsError",
    "SandboxNotRunningError",
    "SandboxAlreadyRunningError",
    "ExecutionError",
    "ExecutionTimeoutError",
    "ExecutionFailedError",
    "FileSystemError",
    "FileNotFoundError",
    "PathTraversalError",
    "PackageError",
    "PackageInstallError",
    "SecurityViolationError",
    "BackendError",
    "DockerError",
    "StorageError",
    "ConfigurationError",
    "ExecutionBackend",
    "BackendFactory",
    "LocalBackend",
    "DockerBackend",
    "is_docker_available",
    "StorageBackend",
    "StorageObject",
    "StorageFactory",
    "LocalStorage",
    "S3Storage",
]
