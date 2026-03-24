"""
Centralized path resolver for host/sandbox/workspace paths.
"""
from pathlib import Path
from typing import Optional

from alphora.sandbox.exceptions import PathTraversalError
from alphora.sandbox.workspace import Workspace
from alphora.sandbox.config import (
    SANDBOX_UPLOADS_MOUNT,
    SANDBOX_OUTPUTS_MOUNT,
)


class PathResolver:
    """
    Resolve any supported path expression to workspace-safe paths.

    Supports three input styles:
    - workspace-relative path, e.g. "src/main.py"
    - host absolute path, must stay inside workspace root
    - sandbox absolute path, e.g. "/mnt/workspace/src/main.py"

    Optionally supports read-only mounts:
    - skills sandbox path, e.g. "/mnt/skills/xlsx/scripts/recalc.py"
    - uploads sandbox path, e.g. "/mnt/uploads/data.xlsx"
    - outputs sandbox path, e.g. "/mnt/outputs/report.pdf"
    """

    def __init__(
        self,
        workspace: Workspace,
        skills_host_root: Optional[Path] = None,
        skills_sandbox_root: str = "/mnt/skills",
        uploads_host_root: Optional[Path] = None,
        uploads_sandbox_root: str = SANDBOX_UPLOADS_MOUNT,
        outputs_host_root: Optional[Path] = None,
        outputs_sandbox_root: str = SANDBOX_OUTPUTS_MOUNT,
    ):
        self._host_root = workspace.host_root.resolve()
        self._sandbox_root = workspace.sandbox_root
        self._skills_host_root = skills_host_root.resolve() if skills_host_root else None
        self._skills_sandbox_root = skills_sandbox_root
        self._uploads_host_root = uploads_host_root.resolve() if uploads_host_root else None
        self._uploads_sandbox_root = uploads_sandbox_root
        self._outputs_host_root = outputs_host_root.resolve() if outputs_host_root else None
        self._outputs_sandbox_root = outputs_sandbox_root

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

    @property
    def uploads_host_root(self) -> Optional[Path]:
        return self._uploads_host_root

    @uploads_host_root.setter
    def uploads_host_root(self, value: Optional[Path]) -> None:
        self._uploads_host_root = value.resolve() if value else None

    @property
    def outputs_host_root(self) -> Optional[Path]:
        return self._outputs_host_root

    @outputs_host_root.setter
    def outputs_host_root(self, value: Optional[Path]) -> None:
        self._outputs_host_root = value.resolve() if value else None

    # ------------------------------------------------------------------
    # Path type detection
    # ------------------------------------------------------------------

    def is_skills_path(self, path: str) -> bool:
        """Check whether *path* refers to a location under the skills mount."""
        if not self._skills_host_root:
            return False
        return self._matches_mount(path, self._skills_sandbox_root)

    def is_uploads_path(self, path: str) -> bool:
        """Check whether *path* refers to a location under the uploads mount."""
        return self._matches_mount(path, self._uploads_sandbox_root)

    def is_outputs_path(self, path: str) -> bool:
        """Check whether *path* refers to a location under the outputs mount."""
        return self._matches_mount(path, self._outputs_sandbox_root)

    def is_readonly_path(self, path: str) -> bool:
        """Check whether *path* refers to a read-only mount (skills or uploads)."""
        return self.is_skills_path(path) or self.is_uploads_path(path)

    @staticmethod
    def _matches_mount(path: str, mount_root: str) -> bool:
        normalized = str(path).replace("\\", "/").strip()
        return normalized == mount_root or normalized.startswith(f"{mount_root}/")

    # ------------------------------------------------------------------
    # Workspace path resolution
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

        Works for workspace, skills, uploads, and outputs paths.
        Non-workspace paths are resolved against their respective host roots.
        """
        if self.is_skills_path(path):
            return self._extra_mount_to_host(
                path, self._skills_host_root, self._skills_sandbox_root, "skills"
            )
        if self.is_uploads_path(path):
            return self._extra_mount_to_host(
                path, self._uploads_host_root, self._uploads_sandbox_root, "uploads"
            )
        if self.is_outputs_path(path):
            return self._extra_mount_to_host(
                path, self._outputs_host_root, self._outputs_sandbox_root, "outputs"
            )
        rel = self.to_relative(path)
        resolved = self._resolve_and_check(self._host_root / rel, original=path)
        return resolved

    def to_sandbox(self, path: str) -> str:
        if self.is_skills_path(path):
            return str(path).replace("\\", "/").strip()
        if self.is_uploads_path(path):
            return str(path).replace("\\", "/").strip()
        if self.is_outputs_path(path):
            return str(path).replace("\\", "/").strip()
        rel = self.to_relative(path)
        if not rel:
            return self._sandbox_root
        return f"{self._sandbox_root}/{rel}"

    # ------------------------------------------------------------------
    # Extra-mount path resolution (skills / uploads / outputs)
    # ------------------------------------------------------------------

    def _extra_mount_to_host(
        self, path: str, host_root: Optional[Path], sandbox_root: str, label: str
    ) -> Path:
        """Resolve a sandbox path under an extra mount to its host-absolute equivalent."""
        if not host_root:
            raise PathTraversalError(
                str(path), message=f"{label.capitalize()} mount not configured: {path}"
            )
        normalized = str(path).replace("\\", "/").strip()
        suffix = normalized[len(sandbox_root):].lstrip("/")
        candidate = host_root / suffix if suffix else host_root
        try:
            resolved = candidate.resolve()
        except Exception as exc:
            raise PathTraversalError(
                str(path), message=f"Invalid {label} path: {path}"
            ) from exc
        try:
            resolved.relative_to(host_root)
        except ValueError as exc:
            raise PathTraversalError(
                str(path), message=f"Path escapes {label} directory: {path}"
            ) from exc
        return resolved

    def _skills_to_host(self, path: str) -> Path:
        """Resolve a skills sandbox path to its host-absolute equivalent."""
        return self._extra_mount_to_host(
            path, self._skills_host_root, self._skills_sandbox_root, "skills"
        )

    def skills_to_sandbox(self, host_path: Path) -> str:
        """Convert a host-absolute skills path back to a sandbox display path."""
        return self._host_to_sandbox_display(
            host_path, self._skills_host_root, self._skills_sandbox_root
        )

    def uploads_to_sandbox(self, host_path: Path) -> str:
        """Convert a host-absolute uploads path back to a sandbox display path."""
        return self._host_to_sandbox_display(
            host_path, self._uploads_host_root, self._uploads_sandbox_root
        )

    def outputs_to_sandbox(self, host_path: Path) -> str:
        """Convert a host-absolute outputs path back to a sandbox display path."""
        return self._host_to_sandbox_display(
            host_path, self._outputs_host_root, self._outputs_sandbox_root
        )

    @staticmethod
    def _host_to_sandbox_display(
        host_path: Path, host_root: Optional[Path], sandbox_root: str
    ) -> str:
        if not host_root:
            return str(host_path)
        try:
            rel = host_path.relative_to(host_root)
            rel_str = rel.as_posix()
            if rel_str == ".":
                return sandbox_root
            return f"{sandbox_root}/{rel_str}"
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
