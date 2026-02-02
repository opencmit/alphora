"""
Alphora Sandbox - Storage Module

Storage backends for persisting sandbox files.

Supports:
    - Local filesystem storage
    - AWS S3 storage
    - MinIO storage (S3-compatible)

Usage:
    ```python
    from alphora.sandbox.storage import StorageFactory, LocalStorage, S3Storage
    
    # Local storage
    storage = StorageFactory.local("/data/storage")
    
    # MinIO storage
    storage = StorageFactory.minio(
        endpoint="http://localhost:9000",
        access_key="minioadmin",
        secret_key="minioadmin123",
        bucket="sandboxes"
    )
    
    async with storage:
        await storage.put("file.txt", b"content")
        data = await storage.get("file.txt")
    ```
"""
from alphora.sandbox.storage.base import (
    StorageBackend,
    StorageObject,
    StorageFactory,
)
from alphora.sandbox.storage.local import LocalStorage
from alphora.sandbox.storage.s3 import S3Storage

__all__ = [
    "StorageBackend",
    "StorageObject",
    "StorageFactory",
    "LocalStorage",
    "S3Storage",
]
