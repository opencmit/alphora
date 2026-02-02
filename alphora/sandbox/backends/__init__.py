"""
Alphora Sandbox - Backends Module

Execution backends for running code in sandboxes.

Supports:
    - Local: Direct Python interpreter execution
    - Docker: Container-based isolated execution

Usage:
    ```python
    from alphora.sandbox.backends import BackendFactory, LocalBackend, DockerBackend
    
    # Create via factory
    backend = BackendFactory.create("local", sandbox_id="test", workspace_path="/data")
    
    # Or directly
    backend = LocalBackend(sandbox_id="test", workspace_path="/data")
    ```
"""
from alphora.sandbox.backends.base import ExecutionBackend, BackendFactory
from alphora.sandbox.backends.local import LocalBackend
from alphora.sandbox.backends.docker import DockerBackend, is_docker_available

__all__ = [
    "ExecutionBackend",
    "BackendFactory",
    "LocalBackend",
    "DockerBackend",
    "is_docker_available",
]
