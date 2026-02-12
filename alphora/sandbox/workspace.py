"""
Workspace definition for sandbox path mapping.
"""
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class Workspace:
    """
    Workspace descriptor shared by host and sandbox.

    Args:
        host_root: Absolute root directory on host machine.
        sandbox_root: Workspace root path inside sandbox runtime.
    """

    host_root: Path
    sandbox_root: str = "/workspace"

    def __post_init__(self) -> None:
        host_root = Path(self.host_root).resolve()
        sandbox_root = self._normalize_sandbox_root(self.sandbox_root)
        object.__setattr__(self, "host_root", host_root)
        object.__setattr__(self, "sandbox_root", sandbox_root)

    @staticmethod
    def _normalize_sandbox_root(path: str) -> str:
        if not path:
            return "/workspace"
        normalized = str(path).replace("\\", "/").strip()
        if not normalized.startswith("/"):
            normalized = f"/{normalized}"
        return normalized.rstrip("/") or "/"
