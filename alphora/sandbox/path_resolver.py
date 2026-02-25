"""
Centralized path resolver for host/sandbox/workspace paths.
"""
from pathlib import Path

from alphora.sandbox.exceptions import PathTraversalError
from alphora.sandbox.workspace import Workspace


class PathResolver:
    """
    Resolve any supported path expression to workspace-safe paths.

    Supports three input styles:
    - workspace-relative path, e.g. "src/main.py"
    - host absolute path, must stay inside workspace root
    - sandbox absolute path, e.g. "/mnt/workspace/src/main.py"
    """

    def __init__(self, workspace: Workspace):
        self._host_root = workspace.host_root.resolve()
        self._sandbox_root = workspace.sandbox_root

    @property
    def host_root(self) -> Path:
        return self._host_root

    @property
    def sandbox_root(self) -> str:
        return self._sandbox_root

    def to_relative(self, path: str) -> str:
        raw = "" if path is None else str(path).strip()
        if not raw or raw == ".":
            return ""

        normalized = raw.replace("\\", "/")

        if self._is_sandbox_path(normalized):
            suffix = normalized[len(self._sandbox_root):].lstrip("/")
            resolved = self._resolve_and_check(self._host_root / suffix, original=path)
            return self._to_rel_posix(resolved)

        path_obj = Path(raw)
        if path_obj.is_absolute():
            resolved = self._resolve_and_check(path_obj, original=path)
            return self._to_rel_posix(resolved)

        resolved = self._resolve_and_check(self._host_root / normalized.lstrip("/"), original=path)
        return self._to_rel_posix(resolved)

    def to_host(self, path: str) -> Path:
        rel = self.to_relative(path)
        resolved = self._resolve_and_check(self._host_root / rel, original=path)
        return resolved

    def to_sandbox(self, path: str) -> str:
        rel = self.to_relative(path)
        if not rel:
            return self._sandbox_root
        return f"{self._sandbox_root}/{rel}"

    def _resolve_and_check(self, candidate: Path, original: str) -> Path:
        try:
            resolved = candidate.resolve()
        except Exception as exc:
            raise PathTraversalError(str(original), message=f"Invalid path: {original}") from exc

        try:
            resolved.relative_to(self._host_root)
        except ValueError as exc:
            raise PathTraversalError(str(original), message=f"Path escapes workspace: {original}") from exc

        return resolved

    def _to_rel_posix(self, path: Path) -> str:
        rel = path.relative_to(self._host_root)
        rel_str = rel.as_posix()
        return "" if rel_str == "." else rel_str

    def _is_sandbox_path(self, path: str) -> bool:
        if path == self._sandbox_root:
            return True
        return path.startswith(f"{self._sandbox_root}/")
