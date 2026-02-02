"""
Alphora Sandbox - Local Storage Backend

Local filesystem storage implementation.
"""
import os
import json
import hashlib
import mimetypes
import aiofiles
import aiofiles.os
from pathlib import Path
from datetime import datetime
from typing import Optional, List, Dict, Any, Union, BinaryIO

from alphora.sandbox.storage.base import StorageBackend, StorageObject
from alphora.sandbox.config import StorageConfig
from alphora.sandbox.exceptions import (
    StorageError,
    StorageNotFoundError,
    StorageUploadError,
    StorageDownloadError,
)


class LocalStorage(StorageBackend):
    """
    Local filesystem storage backend.
    
    Stores files on the local filesystem with optional metadata files.
    
    Usage:
        ```python
        config = StorageConfig.local("/data/storage")
        async with LocalStorage(config) as storage:
            await storage.put("myfile.txt", b"Hello World")
            content = await storage.get("myfile.txt")
        ```
    """
    
    def __init__(self, config: StorageConfig):
        """
        Initialize local storage.
        
        Args:
            config: Storage configuration with local_path set
        """
        super().__init__(config)
        self._base_path = Path(config.local_path) if config.local_path else Path("/tmp/storage")
        self._prefix = config.prefix or ""
    
    @property
    def base_path(self) -> Path:
        """Get base storage path"""
        return self._base_path
    
    def _get_full_path(self, key: str) -> Path:
        """Get full filesystem path for a key"""
        # Apply prefix if set
        if self._prefix:
            key = f"{self._prefix.strip('/')}/{key}"
        
        # Normalize and validate path
        normalized = Path(key).as_posix().lstrip("/")
        full_path = self._base_path / normalized
        
        # Security check: ensure path is within base path
        try:
            full_path.resolve().relative_to(self._base_path.resolve())
        except ValueError:
            raise StorageError(f"Path traversal detected: {key}")
        
        return full_path
    
    def _get_metadata_path(self, path: Path) -> Path:
        """Get metadata file path for an object"""
        return path.parent / f".{path.name}.meta"
    
    async def _save_metadata(
        self,
        path: Path,
        content_type: Optional[str],
        metadata: Optional[Dict[str, str]]
    ) -> None:
        """Save object metadata to file"""
        meta_path = self._get_metadata_path(path)
        meta_data = {
            "content_type": content_type,
            "metadata": metadata or {},
            "created": datetime.now().isoformat(),
        }
        async with aiofiles.open(meta_path, "w", encoding="utf-8") as f:
            await f.write(json.dumps(meta_data))
    
    async def _load_metadata(self, path: Path) -> Dict[str, Any]:
        """Load object metadata from file"""
        meta_path = self._get_metadata_path(path)
        if meta_path.exists():
            try:
                async with aiofiles.open(meta_path, "r", encoding="utf-8") as f:
                    content = await f.read()
                    return json.loads(content)
            except Exception:
                pass
        return {}

    # Lifecycle Methods
    async def initialize(self) -> None:
        """Initialize local storage"""
        await super().initialize()
        # Create base directory if it doesn't exist
        self._base_path.mkdir(parents=True, exist_ok=True)

    # Core Operations
    async def put(
        self,
        key: str,
        data: Union[bytes, BinaryIO],
        content_type: Optional[str] = None,
        metadata: Optional[Dict[str, str]] = None
    ) -> StorageObject:
        """
        Put an object into local storage.
        
        Args:
            key: Object key (relative path)
            data: Object data
            content_type: MIME content type
            metadata: Optional metadata
        
        Returns:
            StorageObject: Stored object metadata
        """
        try:
            full_path = self._get_full_path(key)
            
            # Create parent directories
            full_path.parent.mkdir(parents=True, exist_ok=True)
            
            # Get bytes from data
            if hasattr(data, "read"):
                content = data.read()
            else:
                content = data
            
            # Write file
            async with aiofiles.open(full_path, "wb") as f:
                await f.write(content)
            
            # Detect content type if not provided
            if not content_type:
                content_type = mimetypes.guess_type(key)[0] or "application/octet-stream"
            
            # Save metadata
            await self._save_metadata(full_path, content_type, metadata)
            
            # Get file stats
            stat = full_path.stat()
            
            return StorageObject(
                key=key,
                size=stat.st_size,
                last_modified=datetime.fromtimestamp(stat.st_mtime),
                etag=hashlib.md5(content).hexdigest(),
                content_type=content_type,
                metadata=metadata or {},
            )
        
        except StorageError:
            raise
        except Exception as e:
            raise StorageUploadError(f"Failed to upload {key}: {e}")
    
    async def get(self, key: str) -> bytes:
        """
        Get an object from local storage.
        
        Args:
            key: Object key (relative path)
        
        Returns:
            bytes: Object data
        """
        try:
            full_path = self._get_full_path(key)
            
            if not full_path.exists():
                raise StorageNotFoundError(f"Object not found: {key}")
            
            if full_path.is_dir():
                raise StorageError(f"Cannot get directory as object: {key}")
            
            async with aiofiles.open(full_path, "rb") as f:
                return await f.read()
        
        except (StorageNotFoundError, StorageError):
            raise
        except Exception as e:
            raise StorageDownloadError(f"Failed to download {key}: {e}")
    
    async def delete(self, key: str) -> bool:
        """
        Delete an object from local storage.
        
        Args:
            key: Object key (relative path)
        
        Returns:
            bool: True if deleted, False if not found
        """
        try:
            full_path = self._get_full_path(key)
            
            if not full_path.exists():
                return False
            
            if full_path.is_dir():
                import shutil
                shutil.rmtree(full_path)
            else:
                full_path.unlink()
                
                # Also delete metadata file
                meta_path = self._get_metadata_path(full_path)
                if meta_path.exists():
                    meta_path.unlink()
            
            return True
        
        except Exception as e:
            raise StorageError(f"Failed to delete {key}: {e}")
    
    async def exists(self, key: str) -> bool:
        """
        Check if an object exists.
        
        Args:
            key: Object key (relative path)
        
        Returns:
            bool: True if object exists
        """
        try:
            full_path = self._get_full_path(key)
            return full_path.exists()
        except Exception:
            return False
    
    async def list(
        self,
        prefix: str = "",
        recursive: bool = False,
        max_keys: int = 1000
    ) -> List[StorageObject]:
        """
        List objects in local storage.
        
        Args:
            prefix: Key prefix to filter by
            recursive: Include objects in subdirectories
            max_keys: Maximum number of keys to return
        
        Returns:
            List[StorageObject]: List of storage objects
        """
        try:
            if prefix:
                base_path = self._get_full_path(prefix)
            else:
                base_path = self._base_path
                if self._prefix:
                    base_path = base_path / self._prefix
            
            if not base_path.exists():
                return []
            
            objects = []
            
            if recursive:
                iterator = base_path.rglob("*")
            else:
                iterator = base_path.iterdir()
            
            for path in iterator:
                # Skip metadata files
                if path.name.startswith(".") and path.name.endswith(".meta"):
                    continue
                
                # Skip hidden files
                if path.name.startswith("."):
                    continue
                
                try:
                    # Calculate relative key
                    if self._prefix:
                        rel_path = path.relative_to(self._base_path / self._prefix)
                    else:
                        rel_path = path.relative_to(self._base_path)
                    
                    key = rel_path.as_posix()
                    
                    stat = path.stat()
                    
                    # Load metadata
                    meta = await self._load_metadata(path)
                    
                    objects.append(StorageObject(
                        key=key + ("/" if path.is_dir() else ""),
                        size=0 if path.is_dir() else stat.st_size,
                        last_modified=datetime.fromtimestamp(stat.st_mtime),
                        content_type=meta.get("content_type"),
                        metadata=meta.get("metadata", {}),
                    ))
                    
                    if len(objects) >= max_keys:
                        break
                
                except Exception:
                    continue
            
            return sorted(objects, key=lambda x: x.key)
        
        except Exception as e:
            raise StorageError(f"Failed to list objects: {e}")

    # Additional Methods
    async def get_info(self, key: str) -> Optional[StorageObject]:
        """
        Get object metadata without content.
        
        Args:
            key: Object key
        
        Returns:
            StorageObject: Object metadata, or None if not found
        """
        try:
            full_path = self._get_full_path(key)
            
            if not full_path.exists():
                return None
            
            stat = full_path.stat()
            meta = await self._load_metadata(full_path)
            
            return StorageObject(
                key=key,
                size=0 if full_path.is_dir() else stat.st_size,
                last_modified=datetime.fromtimestamp(stat.st_mtime),
                content_type=meta.get("content_type"),
                metadata=meta.get("metadata", {}),
            )
        
        except Exception:
            return None
    
    async def get_disk_usage(self) -> Dict[str, Any]:
        """
        Get disk usage information.
        
        Returns:
            Dict containing used, free, and total space in bytes
        """
        try:
            import shutil
            total, used, free = shutil.disk_usage(self._base_path)
            
            # Also calculate storage directory size
            storage_size = 0
            for path in self._base_path.rglob("*"):
                if path.is_file():
                    storage_size += path.stat().st_size
            
            return {
                "total_bytes": total,
                "used_bytes": used,
                "free_bytes": free,
                "storage_bytes": storage_size,
                "total_mb": total / (1024 * 1024),
                "used_mb": used / (1024 * 1024),
                "free_mb": free / (1024 * 1024),
                "storage_mb": storage_size / (1024 * 1024),
            }
        
        except Exception as e:
            return {"error": str(e)}
    
    async def create_directory(self, key: str) -> bool:
        """
        Create a directory.
        
        Args:
            key: Directory key (path)
        
        Returns:
            bool: True if created
        """
        try:
            full_path = self._get_full_path(key)
            full_path.mkdir(parents=True, exist_ok=True)
            return True
        except Exception:
            return False
