"""
Alphora Sandbox - Exception Definitions

Complete exception hierarchy for the sandbox component.
"""

from typing import Optional, Dict, Any


class SandboxError(Exception):
    """
    Base exception for all sandbox errors.
    
    All sandbox exceptions inherit from this class.
    """
    error_code: str = "SANDBOX_ERROR"
    
    def __init__(
        self,
        message: str,
        details: Optional[Dict[str, Any]] = None,
        cause: Optional[Exception] = None
    ):
        super().__init__(message)
        self.message = message
        self.details = details or {}
        self.cause = cause
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert exception to dictionary for serialization"""
        return {
            "error_code": self.error_code,
            "message": self.message,
            "details": self.details,
            "cause": str(self.cause) if self.cause else None,
        }
    
    def __str__(self) -> str:
        if self.details:
            return f"{self.message} (details: {self.details})"
        return self.message


# Sandbox State Exceptions

class SandboxNotFoundError(SandboxError):
    """Raised when a sandbox cannot be found"""
    error_code = "SANDBOX_NOT_FOUND"


class SandboxAlreadyExistsError(SandboxError):
    """Raised when trying to create a sandbox that already exists"""
    error_code = "SANDBOX_ALREADY_EXISTS"


class SandboxNotRunningError(SandboxError):
    """Raised when an operation requires a running sandbox"""
    error_code = "SANDBOX_NOT_RUNNING"


class SandboxAlreadyRunningError(SandboxError):
    """Raised when trying to start an already running sandbox"""
    error_code = "SANDBOX_ALREADY_RUNNING"


class SandboxStateError(SandboxError):
    """Raised when sandbox is in an invalid state for the operation"""
    error_code = "SANDBOX_STATE_ERROR"


# Execution Exceptions
class ExecutionError(SandboxError):
    """Base exception for code execution errors"""
    error_code = "EXECUTION_ERROR"


class ExecutionTimeoutError(ExecutionError):
    """Raised when code execution times out"""
    error_code = "EXECUTION_TIMEOUT"
    
    def __init__(self, timeout: int, message: Optional[str] = None):
        msg = message or f"Execution timed out after {timeout} seconds"
        super().__init__(msg, details={"timeout": timeout})
        self.timeout = timeout


class ExecutionFailedError(ExecutionError):
    """Raised when code execution fails"""
    error_code = "EXECUTION_FAILED"
    
    def __init__(
        self,
        message: str,
        return_code: int = -1,
        stdout: str = "",
        stderr: str = ""
    ):
        super().__init__(message, details={
            "return_code": return_code,
            "stdout": stdout[:1000] if stdout else "",
            "stderr": stderr[:1000] if stderr else "",
        })
        self.return_code = return_code
        self.stdout = stdout
        self.stderr = stderr


class CodeSyntaxError(ExecutionError):
    """Raised when code has syntax errors"""
    error_code = "CODE_SYNTAX_ERROR"
    
    def __init__(self, message: str, line: Optional[int] = None, column: Optional[int] = None):
        details = {}
        if line is not None:
            details["line"] = line
        if column is not None:
            details["column"] = column
        super().__init__(message, details=details)
        self.line = line
        self.column = column


# File System Exceptions
class FileSystemError(SandboxError):
    """Base exception for file system errors"""
    error_code = "FILESYSTEM_ERROR"


class FileNotFoundError(FileSystemError):
    """Raised when a file cannot be found"""
    error_code = "FILE_NOT_FOUND"
    
    def __init__(self, path: str, message: Optional[str] = None):
        msg = message or f"File not found: {path}"
        super().__init__(msg, details={"path": path})
        self.path = path


class FileExistsError(FileSystemError):
    """Raised when a file already exists"""
    error_code = "FILE_EXISTS"
    
    def __init__(self, path: str, message: Optional[str] = None):
        msg = message or f"File already exists: {path}"
        super().__init__(msg, details={"path": path})
        self.path = path


class PathTraversalError(FileSystemError):
    """Raised when path traversal attack is detected"""
    error_code = "PATH_TRAVERSAL"
    
    def __init__(self, path: str, message: Optional[str] = None):
        msg = message or f"Path traversal detected: {path}"
        super().__init__(msg, details={"path": path})
        self.path = path


class FileSizeExceededError(FileSystemError):
    """Raised when file size exceeds limit"""
    error_code = "FILE_SIZE_EXCEEDED"
    
    def __init__(self, path: str, size: int, max_size: int):
        msg = f"File size ({size} bytes) exceeds limit ({max_size} bytes): {path}"
        super().__init__(msg, details={"path": path, "size": size, "max_size": max_size})
        self.path = path
        self.size = size
        self.max_size = max_size


class FileReadError(FileSystemError):
    """Raised when file cannot be read"""
    error_code = "FILE_READ_ERROR"


class FileWriteError(FileSystemError):
    """Raised when file cannot be written"""
    error_code = "FILE_WRITE_ERROR"


# Package Management Exceptions
class PackageError(SandboxError):
    """Base exception for package management errors"""
    error_code = "PACKAGE_ERROR"


class PackageInstallError(PackageError):
    """Raised when package installation fails"""
    error_code = "PACKAGE_INSTALL_ERROR"
    
    def __init__(self, package: str, message: Optional[str] = None, stderr: str = ""):
        msg = message or f"Failed to install package: {package}"
        super().__init__(msg, details={"package": package, "stderr": stderr[:500]})
        self.package = package
        self.stderr = stderr


class PackageNotFoundError(PackageError):
    """Raised when a package cannot be found"""
    error_code = "PACKAGE_NOT_FOUND"
    
    def __init__(self, package: str):
        super().__init__(f"Package not found: {package}", details={"package": package})
        self.package = package


class PackageVersionError(PackageError):
    """Raised when package version is incompatible"""
    error_code = "PACKAGE_VERSION_ERROR"


# Resource Exceptions
class ResourceLimitExceededError(SandboxError):
    """Base exception for resource limit errors"""
    error_code = "RESOURCE_LIMIT_EXCEEDED"


class MemoryLimitExceededError(ResourceLimitExceededError):
    """Raised when memory limit is exceeded"""
    error_code = "MEMORY_LIMIT_EXCEEDED"
    
    def __init__(self, used_mb: float, limit_mb: float):
        msg = f"Memory limit exceeded: {used_mb:.1f}MB used, {limit_mb:.1f}MB limit"
        super().__init__(msg, details={"used_mb": used_mb, "limit_mb": limit_mb})


class DiskLimitExceededError(ResourceLimitExceededError):
    """Raised when disk limit is exceeded"""
    error_code = "DISK_LIMIT_EXCEEDED"
    
    def __init__(self, used_mb: float, limit_mb: float):
        msg = f"Disk limit exceeded: {used_mb:.1f}MB used, {limit_mb:.1f}MB limit"
        super().__init__(msg, details={"used_mb": used_mb, "limit_mb": limit_mb})


class ProcessLimitExceededError(ResourceLimitExceededError):
    """Raised when process limit is exceeded"""
    error_code = "PROCESS_LIMIT_EXCEEDED"


# Security Exceptions
class SecurityViolationError(SandboxError):
    """Base exception for security violations"""
    error_code = "SECURITY_VIOLATION"


class BlockedImportError(SecurityViolationError):
    """Raised when a blocked import is attempted"""
    error_code = "BLOCKED_IMPORT"
    
    def __init__(self, module: str):
        super().__init__(f"Import of '{module}' is blocked by security policy",
                         details={"module": module})
        self.module = module


class NetworkAccessDeniedError(SecurityViolationError):
    """Raised when network access is denied"""
    error_code = "NETWORK_ACCESS_DENIED"
    
    def __init__(self, host: Optional[str] = None, port: Optional[int] = None):
        details = {}
        if host:
            details["host"] = host
        if port:
            details["port"] = port
        super().__init__("Network access is denied by security policy", details=details)


class ShellAccessDeniedError(SecurityViolationError):
    """Raised when shell access is denied"""
    error_code = "SHELL_ACCESS_DENIED"


# Backend Exceptions
class BackendError(SandboxError):
    """Base exception for backend errors"""
    error_code = "BACKEND_ERROR"


class BackendNotAvailableError(BackendError):
    """Raised when a backend is not available"""
    error_code = "BACKEND_NOT_AVAILABLE"
    
    def __init__(self, backend: str, message: Optional[str] = None):
        msg = message or f"Backend '{backend}' is not available"
        super().__init__(msg, details={"backend": backend})
        self.backend = backend


class DockerError(BackendError):
    """Raised when Docker operation fails"""
    error_code = "DOCKER_ERROR"


class ContainerError(BackendError):
    """Raised when container operation fails"""
    error_code = "CONTAINER_ERROR"
    
    def __init__(self, container_id: str, message: str):
        super().__init__(message, details={"container_id": container_id})
        self.container_id = container_id


class ContainerNotFoundError(ContainerError):
    """Raised when container is not found"""
    error_code = "CONTAINER_NOT_FOUND"


# Storage Exceptions
class StorageError(SandboxError):
    """Base exception for storage errors"""
    error_code = "STORAGE_ERROR"


class StorageConnectionError(StorageError):
    """Raised when storage connection fails"""
    error_code = "STORAGE_CONNECTION_ERROR"
    
    def __init__(self, endpoint: str, message: Optional[str] = None):
        msg = message or f"Failed to connect to storage: {endpoint}"
        super().__init__(msg, details={"endpoint": endpoint})
        self.endpoint = endpoint


class StorageUploadError(StorageError):
    """Raised when file upload fails"""
    error_code = "STORAGE_UPLOAD_ERROR"


class StorageDownloadError(StorageError):
    """Raised when file download fails"""
    error_code = "STORAGE_DOWNLOAD_ERROR"


class StorageNotFoundError(StorageError):
    """Raised when storage object is not found"""
    error_code = "STORAGE_NOT_FOUND"


class BucketNotFoundError(StorageError):
    """Raised when storage bucket is not found"""
    error_code = "BUCKET_NOT_FOUND"


# Configuration Exceptions
class ConfigurationError(SandboxError):
    """Base exception for configuration errors"""
    error_code = "CONFIGURATION_ERROR"


class InvalidConfigError(ConfigurationError):
    """Raised when configuration is invalid"""
    error_code = "INVALID_CONFIG"
    
    def __init__(self, field: str, message: str):
        super().__init__(f"Invalid configuration for '{field}': {message}",
                         details={"field": field})
        self.field = field


class MissingConfigError(ConfigurationError):
    """Raised when required configuration is missing"""
    error_code = "MISSING_CONFIG"
    
    def __init__(self, field: str):
        super().__init__(f"Missing required configuration: {field}",
                         details={"field": field})
        self.field = field


# Utility Functions
def wrap_exception(e: Exception, wrapper_class: type = SandboxError) -> SandboxError:
    """
    Wrap a standard exception in a SandboxError.
    
    Args:
        e: The exception to wrap
        wrapper_class: The class to wrap with
    
    Returns:
        SandboxError: Wrapped exception
    """
    if isinstance(e, SandboxError):
        return e
    return wrapper_class(str(e), cause=e)


def is_retryable(e: Exception) -> bool:
    """
    Check if an exception is retryable.
    
    Args:
        e: The exception to check
    
    Returns:
        bool: True if the exception is retryable
    """
    retryable_codes = {
        "STORAGE_CONNECTION_ERROR",
        "DOCKER_ERROR",
        "CONTAINER_ERROR",
        "EXECUTION_TIMEOUT",
    }
    if isinstance(e, SandboxError):
        return e.error_code in retryable_codes
    return False
