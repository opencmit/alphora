"""
Alphora Sandbox - Type Definitions

Complete type definitions for the sandbox component.
"""
from enum import Enum
from dataclasses import dataclass, field
from typing import Optional, Dict, Any, List, Union
from datetime import datetime
from pathlib import Path


# =============================================================================
# Enums
# =============================================================================

class BackendType(Enum):
    """Execution backend type"""
    LOCAL = "local"
    DOCKER = "docker"
    
    @classmethod
    def from_string(cls, value: str) -> "BackendType":
        return cls(value.lower())


class StorageType(Enum):
    """Storage backend type"""
    LOCAL = "local"
    S3 = "s3"
    MINIO = "minio"
    
    @classmethod
    def from_string(cls, value: str) -> "StorageType":
        return cls(value.lower())


class SandboxStatus(Enum):
    """Sandbox status"""
    CREATED = "created"
    STARTING = "starting"
    RUNNING = "running"
    STOPPING = "stopping"
    STOPPED = "stopped"
    ERROR = "error"
    DESTROYED = "destroyed"


class ExecutionStatus(Enum):
    """Code execution status"""
    PENDING = "pending"
    RUNNING = "running"
    SUCCESS = "success"
    FAILED = "failed"
    TIMEOUT = "timeout"
    CANCELLED = "cancelled"


class FileType(Enum):
    """File type enumeration"""
    TEXT = "text"
    PYTHON = "python"
    JAVASCRIPT = "javascript"
    TYPESCRIPT = "typescript"
    HTML = "html"
    CSS = "css"
    EXCEL = "excel"
    CSV = "csv"
    JSON = "json"
    YAML = "yaml"
    XML = "xml"
    MARKDOWN = "markdown"
    PDF = "pdf"
    IMAGE = "image"
    ARCHIVE = "archive"
    BINARY = "binary"
    UNKNOWN = "unknown"
    
    @classmethod
    def from_extension(cls, path: str) -> "FileType":
        """Determine file type from extension"""
        ext = Path(path).suffix.lower()
        mapping = {
            ".py": cls.PYTHON, ".pyw": cls.PYTHON,
            ".js": cls.JAVASCRIPT, ".mjs": cls.JAVASCRIPT,
            ".ts": cls.TYPESCRIPT, ".tsx": cls.TYPESCRIPT,
            ".html": cls.HTML, ".htm": cls.HTML,
            ".css": cls.CSS, ".scss": cls.CSS, ".sass": cls.CSS,
            ".xlsx": cls.EXCEL, ".xls": cls.EXCEL, ".xlsm": cls.EXCEL,
            ".csv": cls.CSV, ".tsv": cls.CSV,
            ".json": cls.JSON,
            ".yaml": cls.YAML, ".yml": cls.YAML,
            ".xml": cls.XML,
            ".md": cls.MARKDOWN, ".markdown": cls.MARKDOWN, ".rst": cls.MARKDOWN,
            ".pdf": cls.PDF,
            ".txt": cls.TEXT, ".log": cls.TEXT, ".cfg": cls.TEXT, ".ini": cls.TEXT,
            ".png": cls.IMAGE, ".jpg": cls.IMAGE, ".jpeg": cls.IMAGE,
            ".gif": cls.IMAGE, ".bmp": cls.IMAGE, ".svg": cls.IMAGE, ".webp": cls.IMAGE,
            ".zip": cls.ARCHIVE, ".tar": cls.ARCHIVE, ".gz": cls.ARCHIVE, ".7z": cls.ARCHIVE,
        }
        return mapping.get(ext, cls.UNKNOWN)


# =============================================================================
# Configuration Dataclasses
# =============================================================================

@dataclass
class ResourceLimits:
    """Resource limits configuration"""
    timeout_seconds: int = 300
    memory_mb: int = 512
    cpu_cores: float = 1.0
    disk_mb: int = 1024
    max_processes: int = 10
    max_threads: int = 50
    max_open_files: int = 1024
    network_enabled: bool = False
    max_output_size: int = 10 * 1024 * 1024
    max_file_size: int = 100 * 1024 * 1024
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "timeout_seconds": self.timeout_seconds,
            "memory_mb": self.memory_mb,
            "cpu_cores": self.cpu_cores,
            "disk_mb": self.disk_mb,
            "max_processes": self.max_processes,
            "max_threads": self.max_threads,
            "max_open_files": self.max_open_files,
            "network_enabled": self.network_enabled,
            "max_output_size": self.max_output_size,
            "max_file_size": self.max_file_size,
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "ResourceLimits":
        return cls(**{k: v for k, v in data.items() if k in cls.__dataclass_fields__})
    
    @classmethod
    def minimal(cls) -> "ResourceLimits":
        """Minimal resource limits for quick tasks"""
        return cls(timeout_seconds=30, memory_mb=128, cpu_cores=0.5, disk_mb=256, max_processes=5)
    
    @classmethod
    def standard(cls) -> "ResourceLimits":
        """Standard resource limits"""
        return cls()
    
    @classmethod
    def high_performance(cls) -> "ResourceLimits":
        """High performance resource limits"""
        return cls(timeout_seconds=600, memory_mb=4096, cpu_cores=4.0, disk_mb=10240,
                   max_processes=50, max_threads=200, network_enabled=True)


@dataclass
class SecurityPolicy:
    """Security policy configuration"""
    allow_shell: bool = True
    allow_network: bool = False
    allow_file_write: bool = True
    allow_subprocess: bool = False
    blocked_imports: List[str] = field(default_factory=lambda: [
        "os.system", "subprocess", "shutil.rmtree", "ctypes", "multiprocessing"
    ])
    allowed_imports: List[str] = field(default_factory=list)
    allowed_paths: List[str] = field(default_factory=list)
    blocked_paths: List[str] = field(default_factory=lambda: ["/etc", "/usr", "/bin", "/sbin", "/root"])
    max_file_size_mb: int = 100
    max_files_count: int = 1000
    audit_enabled: bool = True
    read_only_mode: bool = False
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "allow_shell": self.allow_shell,
            "allow_network": self.allow_network,
            "allow_file_write": self.allow_file_write,
            "allow_subprocess": self.allow_subprocess,
            "blocked_imports": self.blocked_imports,
            "allowed_imports": self.allowed_imports,
            "allowed_paths": self.allowed_paths,
            "blocked_paths": self.blocked_paths,
            "max_file_size_mb": self.max_file_size_mb,
            "max_files_count": self.max_files_count,
            "audit_enabled": self.audit_enabled,
            "read_only_mode": self.read_only_mode,
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "SecurityPolicy":
        return cls(**{k: v for k, v in data.items() if k in cls.__dataclass_fields__})
    
    @classmethod
    def strict(cls) -> "SecurityPolicy":
        """Strict security policy"""
        return cls(allow_shell=False, allow_network=False, allow_subprocess=False,
                   blocked_imports=["os", "subprocess", "shutil", "ctypes", "multiprocessing", "socket"])
    
    @classmethod
    def permissive(cls) -> "SecurityPolicy":
        """Permissive security policy (for trusted environments)"""
        return cls(allow_shell=True, allow_network=True, allow_subprocess=True, blocked_imports=[])


# =============================================================================
# Result Dataclasses
# =============================================================================

@dataclass
class ExecutionResult:
    """Code execution result"""
    success: bool
    stdout: str = ""
    stderr: str = ""
    return_code: int = 0
    execution_time: float = 0.0
    memory_used_mb: Optional[float] = None
    cpu_time: Optional[float] = None
    error: Optional[str] = None
    error_type: Optional[str] = None
    traceback: Optional[str] = None
    output_files: List[str] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "success": self.success,
            "stdout": self.stdout,
            "stderr": self.stderr,
            "return_code": self.return_code,
            "execution_time": self.execution_time,
            "memory_used_mb": self.memory_used_mb,
            "cpu_time": self.cpu_time,
            "error": self.error,
            "error_type": self.error_type,
            "traceback": self.traceback,
            "output_files": self.output_files,
            "metadata": self.metadata,
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "ExecutionResult":
        return cls(**{k: v for k, v in data.items() if k in cls.__dataclass_fields__})
    
    @classmethod
    def success_result(cls, stdout: str = "", execution_time: float = 0.0, **kwargs) -> "ExecutionResult":
        return cls(success=True, stdout=stdout, execution_time=execution_time, **kwargs)
    
    @classmethod
    def error_result(cls, error: str, stderr: str = "", error_type: str = "ExecutionError", **kwargs) -> "ExecutionResult":
        return cls(success=False, error=error, stderr=stderr or error, error_type=error_type, return_code=-1, **kwargs)
    
    @classmethod
    def timeout_result(cls, timeout: int) -> "ExecutionResult":
        return cls(success=False, error=f"Execution timed out after {timeout} seconds",
                   error_type="TimeoutError", stderr=f"Timeout after {timeout}s", return_code=-1, execution_time=float(timeout))
    
    @property
    def output(self) -> str:
        return self.stdout if self.success else (self.error or self.stderr)
    
    def __bool__(self) -> bool:
        return self.success


@dataclass
class FileInfo:
    """File information"""
    name: str
    path: str
    size: int = 0
    file_type: FileType = FileType.UNKNOWN
    mime_type: Optional[str] = None
    created_time: Optional[datetime] = None
    modified_time: Optional[datetime] = None
    is_directory: bool = False
    is_symlink: bool = False
    permissions: Optional[str] = None
    checksum: Optional[str] = None
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "path": self.path,
            "size": self.size,
            "file_type": self.file_type.value,
            "mime_type": self.mime_type,
            "created_time": self.created_time.isoformat() if self.created_time else None,
            "modified_time": self.modified_time.isoformat() if self.modified_time else None,
            "is_directory": self.is_directory,
            "is_symlink": self.is_symlink,
            "permissions": self.permissions,
            "checksum": self.checksum,
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "FileInfo":
        data = data.copy()
        if "file_type" in data and isinstance(data["file_type"], str):
            data["file_type"] = FileType(data["file_type"])
        for tf in ["created_time", "modified_time"]:
            if data.get(tf) and isinstance(data[tf], str):
                data[tf] = datetime.fromisoformat(data[tf])
        return cls(**{k: v for k, v in data.items() if k in cls.__dataclass_fields__})
    
    @property
    def extension(self) -> str:
        return Path(self.name).suffix.lower()
    
    @property
    def size_human(self) -> str:
        size = self.size
        for unit in ["B", "KB", "MB", "GB", "TB"]:
            if size < 1024:
                return f"{size:.1f} {unit}"
            size /= 1024
        return f"{size:.1f} PB"


@dataclass
class PackageInfo:
    """Package information"""
    name: str
    version: Optional[str] = None
    summary: Optional[str] = None
    homepage: Optional[str] = None
    location: Optional[str] = None
    requires: List[str] = field(default_factory=list)
    
    def to_dict(self) -> Dict[str, Any]:
        return {"name": self.name, "version": self.version, "summary": self.summary,
                "homepage": self.homepage, "location": self.location, "requires": self.requires}
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "PackageInfo":
        return cls(**{k: v for k, v in data.items() if k in cls.__dataclass_fields__})
    
    def __str__(self) -> str:
        return f"{self.name}=={self.version}" if self.version else self.name


@dataclass
class SandboxInfo:
    """Sandbox information"""
    sandbox_id: str
    name: str
    status: SandboxStatus
    backend_type: BackendType
    workspace_path: str
    created_at: datetime
    started_at: Optional[datetime] = None
    stopped_at: Optional[datetime] = None
    resource_limits: Optional[ResourceLimits] = None
    security_policy: Optional[SecurityPolicy] = None
    file_count: int = 0
    total_size_mb: float = 0.0
    execution_count: int = 0
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "sandbox_id": self.sandbox_id,
            "name": self.name,
            "status": self.status.value,
            "backend_type": self.backend_type.value,
            "workspace_path": self.workspace_path,
            "created_at": self.created_at.isoformat(),
            "started_at": self.started_at.isoformat() if self.started_at else None,
            "stopped_at": self.stopped_at.isoformat() if self.stopped_at else None,
            "resource_limits": self.resource_limits.to_dict() if self.resource_limits else None,
            "security_policy": self.security_policy.to_dict() if self.security_policy else None,
            "file_count": self.file_count,
            "total_size_mb": self.total_size_mb,
            "execution_count": self.execution_count,
            "metadata": self.metadata,
        }


@dataclass
class ResourceUsage:
    """Resource usage information"""
    memory_mb: float = 0.0
    memory_percent: float = 0.0
    cpu_percent: float = 0.0
    disk_used_mb: float = 0.0
    disk_total_mb: float = 0.0
    disk_percent: float = 0.0
    num_processes: int = 0
    num_threads: int = 0
    timestamp: datetime = field(default_factory=datetime.now)
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "memory_mb": self.memory_mb,
            "memory_percent": self.memory_percent,
            "cpu_percent": self.cpu_percent,
            "disk_used_mb": self.disk_used_mb,
            "disk_total_mb": self.disk_total_mb,
            "disk_percent": self.disk_percent,
            "num_processes": self.num_processes,
            "num_threads": self.num_threads,
            "timestamp": self.timestamp.isoformat(),
        }


# Type Aliases
PathLike = Union[str, Path]
JsonDict = Dict[str, Any]
