"""
Alphora Sandbox - Configuration Management

Unified configuration system for sandbox component.
"""
import os
import json
from dataclasses import dataclass, field
from typing import Optional, Dict, Any, Union
from pathlib import Path

from alphora.sandbox.types import (
    BackendType,
    StorageType,
    ResourceLimits,
    SecurityPolicy,
)
from alphora.sandbox.exceptions import (
    ConfigurationError,
    InvalidConfigError,
    MissingConfigError,
)


# ============================ <<< Storage Configuration >>> =================================================
@dataclass
class StorageConfig:
    """
    Storage backend configuration.
    
    Supports local filesystem, S3, and MinIO storage backends.
    """
    storage_type: StorageType = StorageType.LOCAL
    
    # Local storage settings
    local_path: Optional[str] = None
    
    # S3/MinIO settings
    endpoint: Optional[str] = None
    access_key: Optional[str] = None
    secret_key: Optional[str] = None
    bucket: Optional[str] = None
    region: Optional[str] = None
    secure: bool = True
    
    # Common settings
    prefix: str = ""
    auto_create_bucket: bool = True
    
    def validate(self) -> None:
        """Validate configuration"""
        if self.storage_type == StorageType.LOCAL:
            if not self.local_path:
                raise MissingConfigError("local_path")
        elif self.storage_type in (StorageType.S3, StorageType.MINIO):
            if not self.endpoint and self.storage_type == StorageType.MINIO:
                raise MissingConfigError("endpoint")
            if not self.access_key:
                raise MissingConfigError("access_key")
            if not self.secret_key:
                raise MissingConfigError("secret_key")
            if not self.bucket:
                raise MissingConfigError("bucket")
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary"""
        return {
            "storage_type": self.storage_type.value,
            "local_path": self.local_path,
            "endpoint": self.endpoint,
            "access_key": self.access_key,
            "secret_key": "***" if self.secret_key else None,
            "bucket": self.bucket,
            "region": self.region,
            "secure": self.secure,
            "prefix": self.prefix,
            "auto_create_bucket": self.auto_create_bucket,
        }
    
    @classmethod
    def local(cls, path: str) -> "StorageConfig":
        """Create local storage configuration"""
        return cls(storage_type=StorageType.LOCAL, local_path=path)
    
    @classmethod
    def s3(
        cls,
        access_key: str,
        secret_key: str,
        bucket: str,
        region: str = "us-east-1",
        prefix: str = ""
    ) -> "StorageConfig":
        """Create S3 storage configuration"""
        return cls(
            storage_type=StorageType.S3,
            access_key=access_key,
            secret_key=secret_key,
            bucket=bucket,
            region=region,
            prefix=prefix,
            secure=True,
        )
    
    @classmethod
    def minio(
        cls,
        endpoint: str,
        access_key: str,
        secret_key: str,
        bucket: str,
        secure: bool = False,
        prefix: str = ""
    ) -> "StorageConfig":
        """Create MinIO storage configuration"""
        return cls(
            storage_type=StorageType.MINIO,
            endpoint=endpoint,
            access_key=access_key,
            secret_key=secret_key,
            bucket=bucket,
            secure=secure,
            prefix=prefix,
        )


# Docker Configuration

@dataclass
class DockerConfig:
    """
    Docker backend configuration.
    
    Settings for Docker container execution.
    """
    # image: str = "python:3.11-slim"
    image: str = "alphora-sandbox:latest"
    network_mode: str = "none"  # none, bridge, host
    auto_remove: bool = True
    privileged: bool = False
    user: Optional[str] = "1000:1000"
    working_dir: str = "/workspace"
    
    # Resource limits
    memory_limit: str = "512m"
    cpu_period: int = 100000
    cpu_quota: int = 100000  # 1 CPU
    pids_limit: int = 100
    
    # Security
    read_only_root: bool = False
    cap_drop: list = field(default_factory=lambda: ["ALL"])
    cap_add: list = field(default_factory=lambda: ["CHOWN", "SETUID", "SETGID"])
    security_opt: list = field(default_factory=lambda: ["no-new-privileges:true"])
    
    # Volumes
    volumes: Dict[str, Dict[str, str]] = field(default_factory=dict)
    
    # Environment
    environment: Dict[str, str] = field(default_factory=lambda: {
        "PYTHONUNBUFFERED": "1",
        "PYTHONDONTWRITEBYTECODE": "1",
    })
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary"""
        return {
            "image": self.image,
            "network_mode": self.network_mode,
            "auto_remove": self.auto_remove,
            "privileged": self.privileged,
            "user": self.user,
            "working_dir": self.working_dir,
            "memory_limit": self.memory_limit,
            "cpu_period": self.cpu_period,
            "cpu_quota": self.cpu_quota,
            "pids_limit": self.pids_limit,
            "read_only_root": self.read_only_root,
            "cap_drop": self.cap_drop,
            "cap_add": self.cap_add,
            "security_opt": self.security_opt,
            "volumes": self.volumes,
            "environment": self.environment,
        }


# Main Sandbox Configuration
@dataclass
class SandboxConfig:
    """
    Main sandbox configuration.
    
    Unified configuration for all sandbox components.
    """
    # Basic settings
    base_path: str = "/tmp/sandboxes"
    backend_type: BackendType = BackendType.LOCAL
    
    # Resource and security
    resource_limits: ResourceLimits = field(default_factory=ResourceLimits)
    security_policy: SecurityPolicy = field(default_factory=SecurityPolicy)
    
    # Storage
    storage: Optional[StorageConfig] = None
    
    # Docker (only for docker backend)
    docker: Optional[DockerConfig] = None
    
    # Behavior settings
    auto_cleanup: bool = False
    persist_files: bool = True
    enable_logging: bool = True
    log_level: str = "INFO"
    
    # Timeouts
    startup_timeout: int = 30
    shutdown_timeout: int = 10
    
    def validate(self) -> None:
        """Validate configuration"""
        if not self.base_path:
            raise MissingConfigError("base_path")
        
        if self.backend_type == BackendType.DOCKER and not self.docker:
            self.docker = DockerConfig()
        
        if self.storage:
            self.storage.validate()
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary"""
        return {
            "base_path": self.base_path,
            "backend_type": self.backend_type.value,
            "resource_limits": self.resource_limits.to_dict(),
            "security_policy": self.security_policy.to_dict(),
            "storage": self.storage.to_dict() if self.storage else None,
            "docker": self.docker.to_dict() if self.docker else None,
            "auto_cleanup": self.auto_cleanup,
            "persist_files": self.persist_files,
            "enable_logging": self.enable_logging,
            "log_level": self.log_level,
            "startup_timeout": self.startup_timeout,
            "shutdown_timeout": self.shutdown_timeout,
        }

    # Factory Methods
    @classmethod
    def local(
        cls,
        path: str = "/tmp/sandboxes",
        resource_limits: Optional[ResourceLimits] = None,
        security_policy: Optional[SecurityPolicy] = None,
        **kwargs
    ) -> "SandboxConfig":
        """
        Create local backend configuration.
        
        Args:
            path: Base path for sandboxes
            resource_limits: Resource limits
            security_policy: Security policy
            **kwargs: Additional configuration options
        
        Returns:
            SandboxConfig: Configuration for local backend
        """
        return cls(
            base_path=path,
            backend_type=BackendType.LOCAL,
            resource_limits=resource_limits or ResourceLimits(),
            security_policy=security_policy or SecurityPolicy(),
            storage=StorageConfig.local(path),
            **kwargs
        )
    
    @classmethod
    def docker(
        cls,
        path: str = "/tmp/sandboxes",
        image: str = "python:3.11-slim",
        resource_limits: Optional[ResourceLimits] = None,
        security_policy: Optional[SecurityPolicy] = None,
        network_enabled: bool = False,
        **kwargs
    ) -> "SandboxConfig":
        """
        Create Docker backend configuration.
        
        Args:
            path: Base path for sandboxes
            image: Docker image to use
            resource_limits: Resource limits
            security_policy: Security policy
            network_enabled: Enable network access
            **kwargs: Additional configuration options
        
        Returns:
            SandboxConfig: Configuration for Docker backend
        """
        docker_config = DockerConfig(
            image=image,
            network_mode="bridge" if network_enabled else "none",
        )
        
        limits = resource_limits or ResourceLimits()
        limits.network_enabled = network_enabled
        
        return cls(
            base_path=path,
            backend_type=BackendType.DOCKER,
            resource_limits=limits,
            security_policy=security_policy or SecurityPolicy(),
            storage=StorageConfig.local(path),
            docker=docker_config,
            **kwargs
        )
    
    @classmethod
    def minio(
        cls,
        endpoint: str,
        access_key: str,
        secret_key: str,
        bucket: str,
        base_path: str = "/tmp/sandboxes",
        backend_type: BackendType = BackendType.LOCAL,
        **kwargs
    ) -> "SandboxConfig":
        """
        Create configuration with MinIO storage.
        
        Args:
            endpoint: MinIO endpoint URL
            access_key: Access key
            secret_key: Secret key
            bucket: Bucket name
            base_path: Base path for local workspace
            backend_type: Execution backend type
            **kwargs: Additional configuration options
        
        Returns:
            SandboxConfig: Configuration with MinIO storage
        """
        return cls(
            base_path=base_path,
            backend_type=backend_type,
            storage=StorageConfig.minio(
                endpoint=endpoint,
                access_key=access_key,
                secret_key=secret_key,
                bucket=bucket,
            ),
            **kwargs
        )
    
    @classmethod
    def s3(
        cls,
        access_key: str,
        secret_key: str,
        bucket: str,
        region: str = "us-east-1",
        base_path: str = "/tmp/sandboxes",
        backend_type: BackendType = BackendType.LOCAL,
        **kwargs
    ) -> "SandboxConfig":
        """
        Create configuration with S3 storage.
        
        Args:
            access_key: AWS access key
            secret_key: AWS secret key
            bucket: S3 bucket name
            region: AWS region
            base_path: Base path for local workspace
            backend_type: Execution backend type
            **kwargs: Additional configuration options
        
        Returns:
            SandboxConfig: Configuration with S3 storage
        """
        return cls(
            base_path=base_path,
            backend_type=backend_type,
            storage=StorageConfig.s3(
                access_key=access_key,
                secret_key=secret_key,
                bucket=bucket,
                region=region,
            ),
            **kwargs
        )


# Configuration Loading Functions

def config_from_env(prefix: str = "SANDBOX_") -> SandboxConfig:
    """
    Load configuration from environment variables.
    
    Environment variables:
        SANDBOX_BASE_PATH: Base path for sandboxes
        SANDBOX_BACKEND: Backend type (local, docker)
        SANDBOX_STORAGE_TYPE: Storage type (local, s3, minio)
        SANDBOX_S3_ENDPOINT: S3/MinIO endpoint
        SANDBOX_S3_ACCESS_KEY: S3/MinIO access key
        SANDBOX_S3_SECRET_KEY: S3/MinIO secret key
        SANDBOX_S3_BUCKET: S3/MinIO bucket
        SANDBOX_S3_REGION: S3 region
        SANDBOX_DOCKER_IMAGE: Docker image
        SANDBOX_TIMEOUT: Execution timeout
        SANDBOX_MEMORY_MB: Memory limit in MB
        SANDBOX_NETWORK_ENABLED: Enable network (true/false)
    
    Args:
        prefix: Environment variable prefix
    
    Returns:
        SandboxConfig: Configuration loaded from environment
    """
    def get_env(key: str, default: Any = None) -> Any:
        return os.environ.get(f"{prefix}{key}", default)
    
    def get_bool(key: str, default: bool = False) -> bool:
        val = get_env(key, str(default)).lower()
        return val in ("true", "1", "yes", "on")
    
    def get_int(key: str, default: int) -> int:
        try:
            return int(get_env(key, default))
        except (TypeError, ValueError):
            return default
    
    # Base configuration
    base_path = get_env("BASE_PATH", "/tmp/sandboxes")
    backend_str = get_env("BACKEND", "local").lower()
    backend_type = BackendType.from_string(backend_str)
    
    # Resource limits
    resource_limits = ResourceLimits(
        timeout_seconds=get_int("TIMEOUT", 300),
        memory_mb=get_int("MEMORY_MB", 512),
        cpu_cores=float(get_env("CPU_CORES", "1.0")),
        disk_mb=get_int("DISK_MB", 1024),
        network_enabled=get_bool("NETWORK_ENABLED", False),
    )
    
    # Storage configuration
    storage_type_str = get_env("STORAGE_TYPE", "local").lower()
    storage_config = None
    
    if storage_type_str == "local":
        storage_config = StorageConfig.local(get_env("STORAGE_PATH", base_path))
    elif storage_type_str in ("s3", "minio"):
        endpoint = get_env("S3_ENDPOINT")
        access_key = get_env("S3_ACCESS_KEY")
        secret_key = get_env("S3_SECRET_KEY")
        bucket = get_env("S3_BUCKET", "sandboxes")
        region = get_env("S3_REGION", "us-east-1")
        secure = get_bool("S3_SECURE", True)
        
        if storage_type_str == "minio" and endpoint:
            storage_config = StorageConfig.minio(
                endpoint=endpoint,
                access_key=access_key or "",
                secret_key=secret_key or "",
                bucket=bucket,
                secure=secure,
            )
        elif storage_type_str == "s3":
            storage_config = StorageConfig.s3(
                access_key=access_key or "",
                secret_key=secret_key or "",
                bucket=bucket,
                region=region,
            )
    
    # Docker configuration
    docker_config = None
    if backend_type == BackendType.DOCKER:
        docker_config = DockerConfig(
            image=get_env("DOCKER_IMAGE", "python:3.11-slim"),
            network_mode="bridge" if resource_limits.network_enabled else "none",
            memory_limit=f"{resource_limits.memory_mb}m",
        )
    
    return SandboxConfig(
        base_path=base_path,
        backend_type=backend_type,
        resource_limits=resource_limits,
        storage=storage_config,
        docker=docker_config,
        auto_cleanup=get_bool("AUTO_CLEANUP", False),
        enable_logging=get_bool("ENABLE_LOGGING", True),
        log_level=get_env("LOG_LEVEL", "INFO"),
    )


def config_from_file(path: Union[str, Path]) -> SandboxConfig:
    """
    Load configuration from a JSON or YAML file.
    
    Args:
        path: Path to configuration file
    
    Returns:
        SandboxConfig: Configuration loaded from file
    
    Raises:
        ConfigurationError: If file cannot be loaded
    """
    path = Path(path)
    
    if not path.exists():
        raise ConfigurationError(f"Configuration file not found: {path}")
    
    try:
        content = path.read_text(encoding="utf-8")
        
        if path.suffix.lower() in (".yaml", ".yml"):
            try:
                import yaml
                data = yaml.safe_load(content)
            except ImportError:
                raise ConfigurationError("PyYAML is required to load YAML files")
        else:
            data = json.loads(content)
        
        return _config_from_dict(data)
    
    except json.JSONDecodeError as e:
        raise ConfigurationError(f"Invalid JSON in configuration file: {e}")
    except Exception as e:
        raise ConfigurationError(f"Failed to load configuration: {e}")


def _config_from_dict(data: Dict[str, Any]) -> SandboxConfig:
    """Create configuration from dictionary"""
    backend_type = BackendType.from_string(data.get("backend_type", "local"))
    
    resource_limits = ResourceLimits.from_dict(data.get("resource_limits", {}))
    security_policy = SecurityPolicy.from_dict(data.get("security_policy", {}))
    
    storage_config = None
    if "storage" in data:
        storage_data = data["storage"]
        storage_type = StorageType.from_string(storage_data.get("storage_type", "local"))
        storage_config = StorageConfig(
            storage_type=storage_type,
            **{k: v for k, v in storage_data.items() if k != "storage_type"}
        )
    
    docker_config = None
    if "docker" in data:
        docker_config = DockerConfig(**data["docker"])
    
    return SandboxConfig(
        base_path=data.get("base_path", "/tmp/sandboxes"),
        backend_type=backend_type,
        resource_limits=resource_limits,
        security_policy=security_policy,
        storage=storage_config,
        docker=docker_config,
        auto_cleanup=data.get("auto_cleanup", False),
        persist_files=data.get("persist_files", True),
        enable_logging=data.get("enable_logging", True),
        log_level=data.get("log_level", "INFO"),
        startup_timeout=data.get("startup_timeout", 30),
        shutdown_timeout=data.get("shutdown_timeout", 10),
    )
