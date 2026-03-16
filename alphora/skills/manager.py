# Copyright 2026 China Mobile Information Technology Co., Ltd.
# SPDX-License-Identifier: Apache-2.0

"""
SkillManager - 核心 Skill 管理器

负责 Skill 的发现、加载、资源访问和 prompt 生成。
兼容 agentskills.io 开放标准，可直接使用社区发布的 Skill。

基础用法::

    manager = SkillManager(["./skills"])
    print(manager.skill_names)

    skill = manager.load("pdf")
    print(skill.instructions)

一站式集成::

    from alphora.skills import setup_skills
    setup = setup_skills(paths=["./skills"], sandbox=sandbox)
"""

from pathlib import Path
from typing import Dict, List, Optional, Union
import logging
import warnings

from .models import (
    Skill,
    SkillContent,
    SkillResource,
    SkillDirectoryInfo,
    SkillStatus,
)
from .parser import parse_properties, parse_content, validate_skill
from .exceptions import (
    SkillError,
    SkillParseError,
    SkillNotFoundError,
    SkillLoadError,
    SkillResourceError,
)

logger = logging.getLogger(__name__)

_MAX_RESOURCE_SIZE = 5 * 1024 * 1024


class SkillManager:
    """
    Skill 管理器

    负责 Skill 的发现、加载、资源访问和 prompt 生成。

    ``paths`` 支持自动检测：
    - 如果路径下直接有 ``SKILL.md`` -> 视为 skill 目录，直接注册
    - 否则视为搜索目录，扫描子目录

    Args:
        paths: 路径列表（搜索目录或 skill 目录均可，自动检测）
        auto_discover: 初始化时是否自动执行 discover()
        sandbox_skill_root: 沙箱内的 skill 挂载路径（如 '/mnt/skills'）

    Example::

        manager = SkillManager(["./skills", "./my-custom-skill"])
        skill = manager.load("pdf")
        print(skill.instructions)
    """

    def __init__(
        self,
        paths: Optional[List[Union[str, Path]]] = None,
        auto_discover: bool = True,
        sandbox_skill_root: Optional[str] = None,
        # deprecated alias
        skill_paths: Optional[List[Union[str, Path]]] = None,
    ):
        self._search_paths: List[Path] = []
        self._discovered: Dict[str, Skill] = {}
        self._loaded_set: set = set()
        self._discovery_errors: List[str] = []
        self._sandbox_skill_root: Optional[str] = sandbox_skill_root

        effective_paths = paths or skill_paths
        if effective_paths:
            for p in effective_paths:
                resolved = Path(p).expanduser().resolve()
                if (resolved / "SKILL.md").exists():
                    self._register_skill_dir(resolved)
                elif resolved.is_dir():
                    self.add_path(resolved)
                else:
                    logger.debug(f"Skill path does not exist, skipping: {resolved}")

        if auto_discover and self._search_paths:
            self.discover()

    # ------------------------------------------------------------------
    # Path management
    # ------------------------------------------------------------------

    def add_path(self, path: Union[str, Path]) -> "SkillManager":
        """添加 Skill 搜索路径（链式调用）。"""
        resolved = Path(path).expanduser().resolve()

        if not resolved.exists():
            logger.debug(f"Skill path does not exist, skipping: {resolved}")
            return self

        if not resolved.is_dir():
            logger.warning(f"Skill path is not a directory, skipping: {resolved}")
            return self

        if resolved not in self._search_paths:
            self._search_paths.append(resolved)
            logger.debug(f"Added skill search path: {resolved}")

        return self

    @property
    def search_paths(self) -> List[Path]:
        """当前配置的搜索路径列表"""
        return list(self._search_paths)

    @property
    def sandbox_skill_root(self) -> Optional[str]:
        """Sandbox-internal skill mount path (e.g. '/mnt/skills'), or None."""
        return self._sandbox_skill_root

    @sandbox_skill_root.setter
    def sandbox_skill_root(self, value: Optional[str]) -> None:
        self._sandbox_skill_root = value

    # ------------------------------------------------------------------
    # Discovery
    # ------------------------------------------------------------------

    def discover(self) -> List[Skill]:
        """
        扫描所有搜索路径，发现可用的 Skill。

        仅加载 YAML frontmatter 元数据，指令内容在首次访问或显式
        ``load()`` 时才会加载。

        Returns:
            已发现的 Skill 列表
        """
        self._discovered.clear()
        self._loaded_set.clear()
        self._discovery_errors.clear()

        for search_path in self._search_paths:
            self._scan_directory(search_path)

        count = len(self._discovered)
        if count > 0:
            names = ", ".join(self._discovered.keys())
            logger.info(f"Discovered {count} skill(s): {names}")
        else:
            logger.debug("No skills discovered from search paths")

        if self._discovery_errors:
            logger.warning(
                f"{len(self._discovery_errors)} skill(s) failed to load: "
                f"{'; '.join(self._discovery_errors)}"
            )

        return list(self._discovered.values())

    def _scan_directory(self, directory: Path) -> None:
        """扫描单个目录下的所有 Skill 子目录"""
        try:
            entries = sorted(directory.iterdir())
        except PermissionError:
            logger.warning(f"Permission denied: {directory}")
            return

        for entry in entries:
            if not entry.is_dir():
                continue
            if entry.name.startswith((".", "_", "__")):
                continue

            skill_md = entry / "SKILL.md"
            if not skill_md.exists():
                continue

            actual_dir = entry.resolve() if entry.is_symlink() else entry

            try:
                skill = parse_properties(actual_dir)

                if skill.name != entry.name:
                    logger.warning(
                        f"Skill name '{skill.name}' does not match "
                        f"directory name '{entry.name}' (at {entry}). "
                        f"Using directory name as key."
                    )

                if skill.name in self._discovered:
                    existing = self._discovered[skill.name]
                    logger.warning(
                        f"Duplicate skill name '{skill.name}': "
                        f"'{existing.path}' will be overridden by '{actual_dir}'"
                    )

                self._discovered[skill.name] = skill

            except (SkillParseError, SkillError) as e:
                self._discovery_errors.append(f"{entry.name}: {e}")
                logger.debug(f"Failed to parse skill at {entry}: {e}")

    def _register_skill_dir(self, resolved: Path) -> Skill:
        """直接注册一个 skill 目录（内部用，已验证 SKILL.md 存在）。"""
        skill = parse_properties(resolved)
        self._discovered[skill.name] = skill
        logger.info(f"Registered skill: {skill.name} ({resolved})")
        return skill

    def add_skill_dir(self, skill_dir: Union[str, Path]) -> Skill:
        """
        直接注册一个 Skill 目录（无需搜索路径扫描）。

        Args:
            skill_dir: Skill 目录路径

        Returns:
            解析得到的 Skill 对象
        """
        resolved = Path(skill_dir).expanduser().resolve()

        if not resolved.is_dir():
            raise SkillParseError(f"Not a directory: {resolved}")
        if not (resolved / "SKILL.md").exists():
            raise SkillParseError(f"SKILL.md not found in {resolved}")

        return self._register_skill_dir(resolved)

    # ------------------------------------------------------------------
    # Load / Unload (formerly activate / deactivate)
    # ------------------------------------------------------------------

    def load(self, name: str) -> Skill:
        """
        显式加载 Skill 的完整指令内容并加入追踪列表。

        Args:
            name: Skill 名称

        Returns:
            Skill 对象（instructions 已填充）

        Raises:
            SkillNotFoundError: 未发现该 Skill
            SkillLoadError: 加载内容失败
        """
        if name not in self._discovered:
            raise SkillNotFoundError(
                name, available=list(self._discovered.keys())
            )

        skill = self._discovered[name]

        if name not in self._loaded_set:
            try:
                from .parser import parse_skill_md
                _, body = parse_skill_md(skill.path)
                raw = (skill.path / "SKILL.md").read_text(encoding="utf-8")
                skill._set_instructions(body, raw)
            except SkillParseError as e:
                raise SkillLoadError(
                    f"Failed to load skill '{name}': {e}"
                )

            skill.status = SkillStatus.LOADED
            self._loaded_set.add(name)

            logger.info(
                f"Loaded skill '{name}' "
                f"({len(skill.instructions)} chars, "
                f"~{len(skill.instructions) // 4} tokens)"
            )

        return skill

    def unload(self, name: str) -> None:
        """
        卸载 Skill，释放缓存的指令内容。

        Args:
            name: Skill 名称
        """
        if name in self._discovered:
            self._discovered[name]._clear_instructions()
            self._discovered[name].status = SkillStatus.DISCOVERED
        self._loaded_set.discard(name)
        # also clean legacy _activated if present
        self._activated.pop(name, None)
        logger.debug(f"Unloaded skill '{name}'")

    @property
    def loaded_skills(self) -> List[str]:
        """已加载的 Skill 名称列表"""
        return list(self._loaded_set)

    # --- deprecated aliases ---

    def activate(self, name: str) -> SkillContent:
        """
        .. deprecated:: Use ``load()`` instead.
        """
        warnings.warn(
            "activate() is deprecated, use load() instead.",
            DeprecationWarning,
            stacklevel=2,
        )
        skill = self.load(name)
        content = SkillContent(
            properties=skill,
            instructions=skill.instructions,
            raw_content=skill.raw_content,
        )
        self._activated[name] = content
        return content

    def deactivate(self, name: str) -> None:
        """
        .. deprecated:: Use ``unload()`` instead.
        """
        warnings.warn(
            "deactivate() is deprecated, use unload() instead.",
            DeprecationWarning,
            stacklevel=2,
        )
        self.unload(name)

    @property
    def activated_skills(self) -> List[str]:
        """
        .. deprecated:: Use ``loaded_skills`` instead.
        """
        return self.loaded_skills

    @property
    def _activated(self) -> Dict[str, SkillContent]:
        """Legacy cache for backward compat (used by deprecated activate())."""
        if not hasattr(self, "_activated_cache"):
            self._activated_cache: Dict[str, SkillContent] = {}
        return self._activated_cache

    # ------------------------------------------------------------------
    # Resource Access
    # ------------------------------------------------------------------

    def read_resource(
        self,
        skill_name: str,
        relative_path: str,
    ) -> SkillResource:
        """
        读取 Skill 的资源文件。

        支持 scripts/、references/、assets/ 等目录下的文件。
        内置路径遍历攻击防护。
        """
        skill_dir = self._resolve_skill_dir(skill_name)
        target = (skill_dir / relative_path).resolve()

        try:
            target.relative_to(skill_dir)
        except ValueError:
            raise SkillResourceError(
                f"Path traversal detected: '{relative_path}' escapes "
                f"skill directory '{skill_dir}'. Access denied."
            )

        if not target.exists():
            raise SkillResourceError(
                f"Resource not found: '{relative_path}' in skill '{skill_name}'"
            )

        if not target.is_file():
            raise SkillResourceError(
                f"Not a file: '{relative_path}' in skill '{skill_name}'"
            )

        size = target.stat().st_size
        if size > _MAX_RESOURCE_SIZE:
            raise SkillResourceError(
                f"Resource '{relative_path}' is too large "
                f"({size / 1024 / 1024:.1f} MB, max {_MAX_RESOURCE_SIZE / 1024 / 1024:.0f} MB)"
            )

        try:
            content = target.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            raise SkillResourceError(
                f"Resource '{relative_path}' is not valid UTF-8 text"
            )

        parts = Path(relative_path).parts
        if parts and parts[0] == "scripts":
            resource_type = "script"
        elif parts and parts[0] == "references":
            resource_type = "reference"
        elif parts and parts[0] == "assets":
            resource_type = "asset"
        else:
            resource_type = "other"

        return SkillResource(
            skill_name=skill_name,
            relative_path=relative_path,
            content=content,
            resource_type=resource_type,
        )

    def list_resources(self, skill_name: str) -> SkillDirectoryInfo:
        """列出 Skill 目录下的所有资源文件。"""
        skill_dir = self._resolve_skill_dir(skill_name)

        info = SkillDirectoryInfo(skill_name=skill_name)

        for item in sorted(skill_dir.rglob("*")):
            if not item.is_file():
                continue

            rel = item.relative_to(skill_dir)

            if any(part.startswith(".") for part in rel.parts):
                continue

            parts = rel.parts
            if len(parts) >= 2 and parts[0] == "scripts":
                info.scripts.append(str(Path(*parts[1:])))
            elif len(parts) >= 2 and parts[0] == "references":
                info.references.append(str(Path(*parts[1:])))
            elif len(parts) >= 2 and parts[0] == "assets":
                info.assets.append(str(Path(*parts[1:])))
            else:
                info.files.append(str(rel))

        return info

    def get_script_path(self, skill_name: str, script_name: str) -> Path:
        """获取 Skill 脚本路径（沙箱上下文下返回沙箱路径）。"""
        host_dir = self._resolve_skill_dir(skill_name)

        if not script_name.startswith("scripts/"):
            script_name = f"scripts/{script_name}"

        target = (host_dir / script_name).resolve()

        try:
            target.relative_to(host_dir)
        except ValueError:
            raise SkillResourceError(
                f"Path traversal detected in script path: '{script_name}'"
            )

        if not target.exists():
            raise SkillResourceError(
                f"Script not found: '{script_name}' in skill '{skill_name}'"
            )

        return self.resolve_skill_path(skill_name) / script_name

    # ------------------------------------------------------------------
    # Context-aware path resolution
    # ------------------------------------------------------------------

    def resolve_skill_path(self, skill_name: str) -> Path:
        """Return the skill directory path, adapted to sandbox context if set."""
        if skill_name not in self._discovered:
            raise SkillNotFoundError(
                skill_name, available=list(self._discovered.keys())
            )
        skill = self._discovered[skill_name]
        if self._sandbox_skill_root:
            return Path(self._sandbox_skill_root) / skill.name
        return skill.path

    def resolve_skill_md_path(self, skill_name: str) -> Path:
        """Return the SKILL.md path, adapted to sandbox context if set."""
        return self.resolve_skill_path(skill_name) / "SKILL.md"

    # ------------------------------------------------------------------
    # Prompt generation
    # ------------------------------------------------------------------

    def to_prompt(self, format: str = "xml") -> str:
        """
        生成可注入 system prompt 的 Skill 清单。

        Args:
            format: "xml"（默认，推荐）或 "markdown"
        """
        if not self._discovered:
            return ""

        if format == "xml":
            return self._to_xml_prompt()
        elif format == "markdown":
            return self._to_markdown_prompt()
        else:
            raise ValueError(f"Unsupported prompt format: '{format}'. Use 'xml' or 'markdown'.")

    def _skill_location(self, skill: Skill) -> str:
        return str(self.resolve_skill_md_path(skill.name))

    def _to_xml_prompt(self) -> str:
        lines = ["<available_skills>"]
        for skill in self._discovered.values():
            lines.append("<skill>")
            lines.append(f"<name>{skill.name}</name>")
            lines.append(f"<description>{skill.description}</description>")
            lines.append(f"<location>{self._skill_location(skill)}</location>")
            lines.append("</skill>")
        lines.append("</available_skills>")
        return "\n".join(lines)

    def _to_markdown_prompt(self) -> str:
        lines = ["## Available Skills", ""]
        for skill in self._discovered.values():
            location = self._skill_location(skill)
            lines.append(f"- **{skill.name}**: {skill.description}")
            lines.append(f"  Location: `{location}`")
        return "\n".join(lines)

    def to_system_prompt(self, format: str = "xml") -> str:
        """
        生成完整的 Skill 系统指令（含使用说明 + Skill 清单）。

        适合直接拼接到 system prompt 末尾。
        """
        if not self._discovered:
            return ""

        skill_list = self.to_prompt(format=format)

        return (
            "You have access to a set of specialized skills. "
            "Each skill contains instructions, scripts, and resources "
            "for performing specific tasks.\n\n"
            "When a user's request matches a skill's description, "
            "use the `read_skill` tool to load its full instructions, "
            "then follow those instructions to complete the task.\n\n"
            "If a skill references scripts or resources, "
            "use `read_skill_resource` or `list_skill_resources` to access them.\n\n"
            f"{skill_list}"
        )

    def to_system_instruction(self, format: str = "xml") -> str:
        """
        .. deprecated:: Use ``to_system_prompt()`` instead.
        """
        warnings.warn(
            "to_system_instruction() is deprecated, use to_system_prompt() instead.",
            DeprecationWarning,
            stacklevel=2,
        )
        return self.to_system_prompt(format=format)

    # ------------------------------------------------------------------
    # Query interface
    # ------------------------------------------------------------------

    def get_skill(self, name: str) -> Optional[Skill]:
        """获取指定 Skill 对象，不存在返回 None。"""
        return self._discovered.get(name)

    @property
    def skills(self) -> Dict[str, Skill]:
        """所有已发现的 Skill（只读视图）"""
        return dict(self._discovered)

    @property
    def skill_names(self) -> List[str]:
        """所有已发现的 Skill 名称列表"""
        return list(self._discovered.keys())

    @property
    def discovery_errors(self) -> List[str]:
        """最近一次 discover() 遇到的错误"""
        return list(self._discovery_errors)

    def __len__(self) -> int:
        return len(self._discovered)

    def __contains__(self, name: str) -> bool:
        return name in self._discovered

    def __iter__(self):
        return iter(self._discovered.values())

    def __repr__(self) -> str:
        return (
            f"SkillManager("
            f"discovered={len(self._discovered)}, "
            f"loaded={len(self._loaded_set)}, "
            f"paths={len(self._search_paths)})"
        )

    # ------------------------------------------------------------------
    # Validation
    # ------------------------------------------------------------------

    def validate(self, name: str) -> List[str]:
        """校验指定 Skill 是否符合 agentskills.io 规范。"""
        skill_dir = self._resolve_skill_dir(name)
        return validate_skill(skill_dir)

    def validate_all(self) -> Dict[str, List[str]]:
        """校验所有已发现的 Skill，返回 {name: [violations]}。"""
        results = {}
        for name, skill in self._discovered.items():
            issues = validate_skill(skill.path)
            if issues:
                results[name] = issues
        return results

    # ------------------------------------------------------------------
    # Cache management
    # ------------------------------------------------------------------

    def refresh(self) -> List[Skill]:
        """清除所有缓存并重新发现。"""
        self._loaded_set.clear()
        self._activated_cache = {}
        return self.discover()

    def clear(self) -> None:
        """清除所有状态（发现缓存、加载缓存、搜索路径）。"""
        self._discovered.clear()
        self._loaded_set.clear()
        self._search_paths.clear()
        self._discovery_errors.clear()
        self._activated_cache = {}

    def _resolve_skill_dir(self, name: str) -> Path:
        if name not in self._discovered:
            raise SkillNotFoundError(
                name, available=list(self._discovered.keys())
            )
        return self._discovered[name].path
