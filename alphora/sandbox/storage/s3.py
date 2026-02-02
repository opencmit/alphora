"""
Alphora Sandbox - S3/MinIO Storage Backend

AWS S3 and MinIO compatible storage implementation.
"""
import asyncio
import hashlib
import mimetypes
from datetime import datetime, timedelta
from typing import Optional, List, Dict, Any, Union, BinaryIO
from io import BytesIO

from alphora.sandbox.storage.base import StorageBackend, StorageObject
from alphora.sandbox.config import StorageConfig
from alphora.sandbox.types import StorageType
from alphora.sandbox.exceptions import (
    StorageError,
    StorageNotFoundError,
    StorageUploadError,
    StorageDownloadError,
    StorageConnectionError,
    BucketNotFoundError,
)


class S3Storage(StorageBackend):
    """
    S3/MinIO storage backend.
    
    Compatible with AWS S3 and MinIO object storage.
    
    Requirements:
        pip install aioboto3
    
    Usage:
        ```python
        # MinIO
        config = StorageConfig.minio(
            endpoint="http://localhost:9000",
            access_key="minioadmin",
            secret_key="minioadmin123",
            bucket="sandboxes"
        )
        
        # AWS S3
        config = StorageConfig.s3(
            access_key="AKIAXXXXXXXXXX",
            secret_key="xxxxxxxxxxxxx",
            bucket="my-bucket",
            region="us-west-2"
        )
        
        async with S3Storage(config) as storage:
            await storage.put("myfile.txt", b"Hello World")
            content = await storage.get("myfile.txt")
        ```
    """
    
    def __init__(self, config: StorageConfig):
        """
        Initialize S3 storage.
        
        Args:
            config: Storage configuration with S3/MinIO settings
        """
        super().__init__(config)
        self._bucket = config.bucket or "sandboxes"
        self._prefix = config.prefix.strip("/") if config.prefix else ""
        self._session = None
        self._client = None
    
    def _get_full_key(self, key: str) -> str:
        """Get full S3 key with prefix"""
        if self._prefix:
            return f"{self._prefix}/{key.lstrip('/')}"
        return key.lstrip("/")
    
    def _strip_prefix(self, key: str) -> str:
        """Remove prefix from key"""
        if self._prefix and key.startswith(self._prefix + "/"):
            return key[len(self._prefix) + 1:]
        return key
    
    @property
    def bucket(self) -> str:
        """Get bucket name"""
        return self._bucket

    # Lifecycle Methods
    async def initialize(self) -> None:
        """Initialize S3 client"""
        await super().initialize()
        
        try:
            import aioboto3
        except ImportError:
            raise StorageError("aioboto3 is required for S3 storage. Install with: pip install aioboto3")
        
        self._session = aioboto3.Session()
        
        # Build endpoint URL
        endpoint_url = None
        if self._config.storage_type == StorageType.MINIO:
            endpoint = self._config.endpoint or ""
            if not endpoint.startswith(("http://", "https://")):
                protocol = "https" if self._config.secure else "http"
                endpoint_url = f"{protocol}://{endpoint}"
            else:
                endpoint_url = endpoint
        
        # Client configuration
        client_config = {
            "service_name": "s3",
            "aws_access_key_id": self._config.access_key,
            "aws_secret_access_key": self._config.secret_key,
            "region_name": self._config.region or "us-east-1",
        }
        
        if endpoint_url:
            client_config["endpoint_url"] = endpoint_url
        
        # Create client context manager
        self._client_ctx = self._session.client(**client_config)
        self._client = await self._client_ctx.__aenter__()
        
        # Ensure bucket exists
        if self._config.auto_create_bucket:
            await self._ensure_bucket()
    
    async def close(self) -> None:
        """Close S3 client"""
        if self._client_ctx:
            await self._client_ctx.__aexit__(None, None, None)
            self._client = None
            self._client_ctx = None
        await super().close()
    
    async def _ensure_bucket(self) -> None:
        """Ensure bucket exists, create if needed"""
        try:
            await self._client.head_bucket(Bucket=self._bucket)
        except Exception:
            try:
                # Try to create bucket
                if self._config.region and self._config.region != "us-east-1":
                    await self._client.create_bucket(
                        Bucket=self._bucket,
                        CreateBucketConfiguration={
                            "LocationConstraint": self._config.region
                        }
                    )
                else:
                    await self._client.create_bucket(Bucket=self._bucket)
            except Exception as e:
                raise BucketNotFoundError(f"Bucket '{self._bucket}' not found and could not be created: {e}")

    # Core Operations
    async def put(
        self,
        key: str,
        data: Union[bytes, BinaryIO],
        content_type: Optional[str] = None,
        metadata: Optional[Dict[str, str]] = None
    ) -> StorageObject:
        """
        Put an object into S3 storage.
        
        Args:
            key: Object key
            data: Object data
            content_type: MIME content type
            metadata: Optional metadata
        
        Returns:
            StorageObject: Stored object metadata
        """
        try:
            full_key = self._get_full_key(key)
            
            # Get bytes from data
            if hasattr(data, "read"):
                content = data.read()
            else:
                content = data
            
            # Detect content type
            if not content_type:
                content_type = mimetypes.guess_type(key)[0] or "application/octet-stream"
            
            # Build put parameters
            put_params = {
                "Bucket": self._bucket,
                "Key": full_key,
                "Body": content,
                "ContentType": content_type,
            }
            
            if metadata:
                put_params["Metadata"] = metadata
            
            # Upload
            response = await self._client.put_object(**put_params)
            
            # Calculate ETag if not returned
            etag = response.get("ETag", "").strip('"')
            if not etag:
                etag = hashlib.md5(content).hexdigest()
            
            return StorageObject(
                key=key,
                size=len(content),
                last_modified=datetime.now(),
                etag=etag,
                content_type=content_type,
                metadata=metadata or {},
            )
        
        except StorageError:
            raise
        except Exception as e:
            raise StorageUploadError(f"Failed to upload {key}: {e}")
    
    async def get(self, key: str) -> bytes:
        """
        Get an object from S3 storage.
        
        Args:
            key: Object key
        
        Returns:
            bytes: Object data
        """
        try:
            full_key = self._get_full_key(key)
            
            response = await self._client.get_object(
                Bucket=self._bucket,
                Key=full_key
            )
            
            async with response["Body"] as stream:
                return await stream.read()
        
        except self._client.exceptions.NoSuchKey:
            raise StorageNotFoundError(f"Object not found: {key}")
        except Exception as e:
            if "NoSuchKey" in str(e) or "404" in str(e):
                raise StorageNotFoundError(f"Object not found: {key}")
            raise StorageDownloadError(f"Failed to download {key}: {e}")
    
    async def delete(self, key: str) -> bool:
        """
        Delete an object from S3 storage.
        
        Args:
            key: Object key
        
        Returns:
            bool: True if deleted
        """
        try:
            full_key = self._get_full_key(key)
            
            # Check if exists first
            exists = await self.exists(key)
            if not exists:
                return False
            
            await self._client.delete_object(
                Bucket=self._bucket,
                Key=full_key
            )
            return True
        
        except Exception as e:
            raise StorageError(f"Failed to delete {key}: {e}")
    
    async def exists(self, key: str) -> bool:
        """
        Check if an object exists.
        
        Args:
            key: Object key
        
        Returns:
            bool: True if object exists
        """
        try:
            full_key = self._get_full_key(key)
            
            await self._client.head_object(
                Bucket=self._bucket,
                Key=full_key
            )
            return True
        
        except Exception:
            return False
    
    async def list(
        self,
        prefix: str = "",
        recursive: bool = False,
        max_keys: int = 1000
    ) -> List[StorageObject]:
        """
        List objects in S3 storage.
        
        Args:
            prefix: Key prefix to filter by
            recursive: Include objects in subdirectories
            max_keys: Maximum number of keys to return
        
        Returns:
            List[StorageObject]: List of storage objects
        """
        try:
            # Build full prefix
            if prefix:
                full_prefix = self._get_full_key(prefix)
            elif self._prefix:
                full_prefix = self._prefix + "/"
            else:
                full_prefix = ""
            
            objects = []
            continuation_token = None
            
            while len(objects) < max_keys:
                # Build list parameters
                list_params = {
                    "Bucket": self._bucket,
                    "MaxKeys": min(1000, max_keys - len(objects)),
                }
                
                if full_prefix:
                    list_params["Prefix"] = full_prefix
                
                if not recursive:
                    list_params["Delimiter"] = "/"
                
                if continuation_token:
                    list_params["ContinuationToken"] = continuation_token
                
                # List objects
                response = await self._client.list_objects_v2(**list_params)
                
                # Process objects
                for obj in response.get("Contents", []):
                    key = self._strip_prefix(obj["Key"])
                    if key:  # Skip empty keys
                        objects.append(StorageObject(
                            key=key,
                            size=obj["Size"],
                            last_modified=obj["LastModified"],
                            etag=obj.get("ETag", "").strip('"'),
                        ))
                
                # Process common prefixes (directories) if not recursive
                if not recursive:
                    for prefix_obj in response.get("CommonPrefixes", []):
                        key = self._strip_prefix(prefix_obj["Prefix"])
                        if key:
                            objects.append(StorageObject(
                                key=key,
                                size=0,
                            ))
                
                # Check for more results
                if response.get("IsTruncated"):
                    continuation_token = response.get("NextContinuationToken")
                else:
                    break
            
            return sorted(objects, key=lambda x: x.key)
        
        except Exception as e:
            raise StorageError(f"Failed to list objects: {e}")

    # S3-Specific Methods
    async def get_presigned_url(
        self,
        key: str,
        expires_in: int = 3600,
        method: str = "get_object"
    ) -> str:
        """
        Generate a presigned URL for an object.
        
        Args:
            key: Object key
            expires_in: URL expiration time in seconds
            method: S3 method (get_object or put_object)
        
        Returns:
            str: Presigned URL
        """
        try:
            full_key = self._get_full_key(key)
            
            url = await self._client.generate_presigned_url(
                method,
                Params={
                    "Bucket": self._bucket,
                    "Key": full_key,
                },
                ExpiresIn=expires_in
            )
            return url
        
        except Exception as e:
            raise StorageError(f"Failed to generate presigned URL: {e}")
    
    async def get_presigned_upload_url(
        self,
        key: str,
        content_type: str = "application/octet-stream",
        expires_in: int = 3600
    ) -> str:
        """
        Generate a presigned URL for uploading.
        
        Args:
            key: Object key
            content_type: Expected content type
            expires_in: URL expiration time in seconds
        
        Returns:
            str: Presigned upload URL
        """
        try:
            full_key = self._get_full_key(key)
            
            url = await self._client.generate_presigned_url(
                "put_object",
                Params={
                    "Bucket": self._bucket,
                    "Key": full_key,
                    "ContentType": content_type,
                },
                ExpiresIn=expires_in
            )
            return url
        
        except Exception as e:
            raise StorageError(f"Failed to generate presigned upload URL: {e}")
    
    async def copy(self, source_key: str, dest_key: str) -> StorageObject:
        """
        Copy an object within S3.
        
        Args:
            source_key: Source object key
            dest_key: Destination object key
        
        Returns:
            StorageObject: Copied object metadata
        """
        try:
            full_source = self._get_full_key(source_key)
            full_dest = self._get_full_key(dest_key)
            
            copy_source = {"Bucket": self._bucket, "Key": full_source}
            
            response = await self._client.copy_object(
                Bucket=self._bucket,
                Key=full_dest,
                CopySource=copy_source
            )
            
            # Get object info
            head = await self._client.head_object(
                Bucket=self._bucket,
                Key=full_dest
            )
            
            return StorageObject(
                key=dest_key,
                size=head["ContentLength"],
                last_modified=head["LastModified"],
                etag=head.get("ETag", "").strip('"'),
                content_type=head.get("ContentType"),
            )
        
        except Exception as e:
            raise StorageError(f"Failed to copy {source_key} to {dest_key}: {e}")
    
    async def get_bucket_info(self) -> Dict[str, Any]:
        """
        Get bucket information.
        
        Returns:
            Dict with bucket metadata
        """
        try:
            # Get bucket location
            try:
                location = await self._client.get_bucket_location(Bucket=self._bucket)
                region = location.get("LocationConstraint") or "us-east-1"
            except Exception:
                region = "unknown"
            
            # Count objects and size
            total_size = 0
            total_count = 0
            
            prefix = f"{self._prefix}/" if self._prefix else ""
            continuation_token = None
            
            while True:
                list_params = {"Bucket": self._bucket}
                if prefix:
                    list_params["Prefix"] = prefix
                if continuation_token:
                    list_params["ContinuationToken"] = continuation_token
                
                response = await self._client.list_objects_v2(**list_params)
                
                for obj in response.get("Contents", []):
                    total_count += 1
                    total_size += obj["Size"]
                
                if not response.get("IsTruncated"):
                    break
                continuation_token = response.get("NextContinuationToken")
            
            return {
                "bucket": self._bucket,
                "region": region,
                "prefix": self._prefix,
                "object_count": total_count,
                "total_size_bytes": total_size,
                "total_size_mb": total_size / (1024 * 1024),
            }
        
        except Exception as e:
            return {"error": str(e)}
    
    async def health_check(self) -> bool:
        """Check if S3 storage is healthy"""
        try:
            await self._client.head_bucket(Bucket=self._bucket)
            return True
        except Exception:
            return False
