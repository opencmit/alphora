"""
Alphora Sandbox - Storage Base

Abstract base class for storage backends.
"""
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Optional, List, Dict, Any, AsyncIterator, Union, BinaryIO
from datetime import datetime
from pathlib import Path

from alphora.sandbox.config import StorageConfig
from alphora.sandbox.types import StorageType


@dataclass
class StorageObject:
    """
    Storage object metadata.
    
    Represents an object stored in the storage backend.
    """
    key: str
    size: int = 0
    last_modified: Optional[datetime] = None
    etag: Optional[str] = None
    content_type: Optional[str] = None
    metadata: Dict[str, str] = field(default_factory=dict)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary"""
        return {
            "key": self.key,
            "size": self.size,
            "last_modified": self.last_modified.isoformat() if self.last_modified else None,
            "etag": self.etag,
            "content_type": self.content_type,
            "metadata": self.metadata,
        }
    
    @property
    def name(self) -> str:
        """Get object name (last part of key)"""
        return Path(self.key).name
    
    @property
    def is_directory(self) -> bool:
        """Check if object represents a directory (key ends with /)"""
        return self.key.endswith("/")


class StorageBackend(ABC):
    """
    Abstract base class for storage backends.
    
    All storage backends (local, S3, MinIO, etc.) must implement this interface.
    
    Usage:
        ```python
        async with LocalStorage(config) as storage:
            await storage.put("file.txt", b"content")
            data = await storage.get("file.txt")
        ```
    """
    
    def __init__(self, config: StorageConfig):
        """
        Initialize storage backend.
        
        Args:
            config: Storage configuration
        """
        self._config = config
        self._initialized = False
    
    @property
    def config(self) -> StorageConfig:
        """Get storage configuration"""
        return self._config
    
    @property
    def storage_type(self) -> StorageType:
        """Get storage type"""
        return self._config.storage_type
    
    @property
    def is_initialized(self) -> bool:
        """Check if storage is initialized"""
        return self._initialized

    # Lifecycle Methods
    async def initialize(self) -> None:
        """
        Initialize the storage backend.
        
        Called automatically when entering async context.
        """
        self._initialized = True
    
    async def close(self) -> None:
        """
        Close the storage backend.
        
        Called automatically when exiting async context.
        """
        self._initialized = False
    
    async def __aenter__(self) -> "StorageBackend":
        await self.initialize()
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb) -> None:
        await self.close()

    # Core Operations
    @abstractmethod
    async def put(
        self,
        key: str,
        data: Union[bytes, BinaryIO],
        content_type: Optional[str] = None,
        metadata: Optional[Dict[str, str]] = None
    ) -> StorageObject:
        """
        Put an object into storage.
        
        Args:
            key: Object key (path)
            data: Object data (bytes or file-like object)
            content_type: MIME content type
            metadata: Optional metadata dictionary
        
        Returns:
            StorageObject: Stored object metadata
        
        Raises:
            StorageUploadError: If upload fails
        """
        pass
    
    @abstractmethod
    async def get(self, key: str) -> bytes:
        """
        Get an object from storage.
        
        Args:
            key: Object key (path)
        
        Returns:
            bytes: Object data
        
        Raises:
            StorageNotFoundError: If object doesn't exist
            StorageDownloadError: If download fails
        """
        pass
    
    @abstractmethod
    async def delete(self, key: str) -> bool:
        """
        Delete an object from storage.
        
        Args:
            key: Object key (path)
        
        Returns:
            bool: True if deleted, False if not found
        
        Raises:
            StorageError: If deletion fails
        """
        pass
    
    @abstractmethod
    async def exists(self, key: str) -> bool:
        """
        Check if an object exists.
        
        Args:
            key: Object key (path)
        
        Returns:
            bool: True if object exists
        """
        pass
    
    @abstractmethod
    async def list(
        self,
        prefix: str = "",
        recursive: bool = False,
        max_keys: int = 1000
    ) -> List[StorageObject]:
        """
        List objects in storage.
        
        Args:
            prefix: Key prefix to filter by
            recursive: Include objects in subdirectories
            max_keys: Maximum number of keys to return
        
        Returns:
            List[StorageObject]: List of storage objects
        """
        pass

    # Convenience Methods
    async def put_text(
        self,
        key: str,
        text: str,
        encoding: str = "utf-8",
        metadata: Optional[Dict[str, str]] = None
    ) -> StorageObject:
        """
        Put text content into storage.
        
        Args:
            key: Object key (path)
            text: Text content
            encoding: Text encoding
            metadata: Optional metadata
        
        Returns:
            StorageObject: Stored object metadata
        """
        return await self.put(
            key,
            text.encode(encoding),
            content_type=f"text/plain; charset={encoding}",
            metadata=metadata
        )
    
    async def get_text(self, key: str, encoding: str = "utf-8") -> str:
        """
        Get text content from storage.
        
        Args:
            key: Object key (path)
            encoding: Text encoding
        
        Returns:
            str: Text content
        """
        data = await self.get(key)
        return data.decode(encoding)
    
    async def copy(self, source_key: str, dest_key: str) -> StorageObject:
        """
        Copy an object within storage.
        
        Args:
            source_key: Source object key
            dest_key: Destination object key
        
        Returns:
            StorageObject: Copied object metadata
        """
        data = await self.get(source_key)
        return await self.put(dest_key, data)
    
    async def move(self, source_key: str, dest_key: str) -> StorageObject:
        """
        Move an object within storage.
        
        Args:
            source_key: Source object key
            dest_key: Destination object key
        
        Returns:
            StorageObject: Moved object metadata
        """
        obj = await self.copy(source_key, dest_key)
        await self.delete(source_key)
        return obj
    
    async def get_info(self, key: str) -> Optional[StorageObject]:
        """
        Get object metadata without downloading content.
        
        Args:
            key: Object key (path)
        
        Returns:
            StorageObject: Object metadata, or None if not found
        """
        objects = await self.list(prefix=key, max_keys=1)
        for obj in objects:
            if obj.key == key:
                return obj
        return None
    
    async def delete_prefix(self, prefix: str) -> int:
        """
        Delete all objects with a given prefix.
        
        Args:
            prefix: Key prefix to delete
        
        Returns:
            int: Number of objects deleted
        """
        objects = await self.list(prefix=prefix, recursive=True)
        count = 0
        for obj in objects:
            if await self.delete(obj.key):
                count += 1
        return count
    
    async def get_size(self, prefix: str = "") -> int:
        """
        Get total size of objects with prefix.
        
        Args:
            prefix: Key prefix to filter by
        
        Returns:
            int: Total size in bytes
        """
        objects = await self.list(prefix=prefix, recursive=True)
        return sum(obj.size for obj in objects)
    
    async def health_check(self) -> bool:
        """
        Check if storage is healthy.
        
        Returns:
            bool: True if storage is accessible
        """
        try:
            await self.list(max_keys=1)
            return True
        except Exception:
            return False


class StorageFactory:
    """
    Factory for creating storage backends.
    
    Usage:
        ```python
        config = StorageConfig.local("/data")
        storage = StorageFactory.create(config)
        ```
    """
    
    @classmethod
    def create(cls, config: StorageConfig) -> StorageBackend:
        """
        Create a storage backend from configuration.
        
        Args:
            config: Storage configuration
        
        Returns:
            StorageBackend: Storage backend instance
        
        Raises:
            ValueError: If storage type is not supported
        """
        from alphora.sandbox.storage.local import LocalStorage
        
        if config.storage_type == StorageType.LOCAL:
            return LocalStorage(config)
        
        elif config.storage_type in (StorageType.S3, StorageType.MINIO):
            from alphora.sandbox.storage.s3 import S3Storage
            return S3Storage(config)
        
        else:
            raise ValueError(f"Unsupported storage type: {config.storage_type}")
    
    @classmethod
    def local(cls, path: str, prefix: str = "") -> StorageBackend:
        """Create local storage backend"""
        config = StorageConfig.local(path)
        config.prefix = prefix
        return cls.create(config)
    
    @classmethod
    def minio(
        cls,
        endpoint: str,
        access_key: str,
        secret_key: str,
        bucket: str,
        secure: bool = False,
        prefix: str = ""
    ) -> StorageBackend:
        """Create MinIO storage backend"""
        config = StorageConfig.minio(
            endpoint=endpoint,
            access_key=access_key,
            secret_key=secret_key,
            bucket=bucket,
            secure=secure,
            prefix=prefix,
        )
        return cls.create(config)
    
    @classmethod
    def s3(
        cls,
        access_key: str,
        secret_key: str,
        bucket: str,
        region: str = "us-east-1",
        prefix: str = ""
    ) -> StorageBackend:
        """Create S3 storage backend"""
        config = StorageConfig.s3(
            access_key=access_key,
            secret_key=secret_key,
            bucket=bucket,
            region=region,
            prefix=prefix,
        )
        return cls.create(config)
