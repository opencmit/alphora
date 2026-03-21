"""
Centralized path resolver for host/sandbox/workspace paths.
"""
from pathlib import Path
from typing import Optional

from alphora.sandbox.exceptions import PathTraversalError
from alphora.sandbox.workspace import Workspace


class PathResolver:
    """
    Resolve any supported path expression to workspace-safe paths.

    Supports three input styles:
    - workspace-relative path, e.g. "src/main.py"
    - host absolute path, must stay inside workspace root
    - sandbox absolute path, e.g. "/mnt/workspace/src/main.py"

    Optionally supports a read-only skills mount:
    - skills sandbox path, e.g. "/mnt/skills/xlsx/scripts/recalc.py"
    """

    def __init__(
        self,
        workspace: Workspace,
        skills_host_root: Optional[Path] = None,
        skills_sandbox_root: str = "/mnt/skills",
    ):
        self._host_root = workspace.host_root.resolve()
        self._sandbox_root = workspace.sandbox_root
        self._skills_host_root = skills_host_root.resolve() if skills_host_root else None
        self._skills_sandbox_root = skills_sandbox_root

    @property
    def host_root(self) -> Path:
        return self._host_root

    @property
    def sandbox_root(self) -> str:
        return self._sandbox_root

    @property
    def skills_host_root(self) -> Optional[Path]:
        return self._skills_host_root

    @skills_host_root.setter
    def skills_host_root(self, value: Optional[Path]) -> None:
        self._skills_host_root = value.resolve() if value else None

    def is_skills_path(self, path: str) -> bool:
        """Check whether *path* refers to a location under the skills mount."""
        if not self._skills_host_root:
            return False
        normalized = str(path).replace("\\", "/").strip()
        return (
            normalized == self._skills_sandbox_root
            or normalized.startswith(f"{self._skills_sandbox_root}/")
        )

    # ------------------------------------------------------------------
    # Workspace path resolution (existing behaviour, unchanged)
    # ------------------------------------------------------------------

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
        """Resolve *path* to a host-absolute path.

        Works for both workspace and skills paths.  Skills paths are
        resolved against ``skills_host_root`` instead of the workspace.
        """
        if self.is_skills_path(path):
            return self._skills_to_host(path)
        rel = self.to_relative(path)
        resolved = self._resolve_and_check(self._host_root / rel, original=path)
        return resolved

    def to_sandbox(self, path: str) -> str:
        if self.is_skills_path(path):
            return str(path).replace("\\", "/").strip()
        rel = self.to_relative(path)
        if not rel:
            return self._sandbox_root
        return f"{self._sandbox_root}/{rel}"

    # ------------------------------------------------------------------
    # Skills path resolution
    # ------------------------------------------------------------------

    def _skills_to_host(self, path: str) -> Path:
        """Resolve a skills sandbox path to its host-absolute equivalent."""
        if not self._skills_host_root:
            raise PathTraversalError(
                str(path), message=f"Skills mount not configured: {path}"
            )
        normalized = str(path).replace("\\", "/").strip()
        suffix = normalized[len(self._skills_sandbox_root):].lstrip("/")
        candidate = self._skills_host_root / suffix if suffix else self._skills_host_root
        try:
            resolved = candidate.resolve()
        except Exception as exc:
            raise PathTraversalError(
                str(path), message=f"Invalid skills path: {path}"
            ) from exc
        try:
            resolved.relative_to(self._skills_host_root)
        except ValueError as exc:
            raise PathTraversalError(
                str(path), message=f"Path escapes skills directory: {path}"
            ) from exc
        return resolved

    def skills_to_sandbox(self, host_path: Path) -> str:
        """Convert a host-absolute skills path back to a sandbox display path."""
        if not self._skills_host_root:
            return str(host_path)
        try:
            rel = host_path.relative_to(self._skills_host_root)
            rel_str = rel.as_posix()
            if rel_str == ".":
                return self._skills_sandbox_root
            return f"{self._skills_sandbox_root}/{rel_str}"
        except ValueError:
            return str(host_path)

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

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
