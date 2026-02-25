# Copyright 2026 China Mobile Information Technology Co., Ltd.
# SPDX-License-Identifier: Apache-2.0

"""
SkillManager - 核心 Skill 管理器

实现 agentskills.io 标准的渐进式披露（Progressive Disclosure）模式：
- Phase 1 Discovery: 扫描目录，仅加载元数据（~100 tokens/skill）
- Phase 2 Activation: 按需加载完整 SKILL.md 指令内容
- Phase 3 Resources: 按需加载 scripts/、references/、assets/ 资源

基础用法：
    manager = SkillManager(["./skills", "~/.alphora/skills"])
    skills = manager.discover()

    # 注入 system prompt
    prompt_xml = manager.to_prompt()

    # 激活指定 skill
    content = manager.activate("pdf-processing")

与 Agent 集成：
    agent = SkillAgent(
        llm=llm,
        skill_manager=manager,
    )
"""

from pathlib import Path
from typing import Dict, List, Optional, Union, Set
import logging
import os

from .models import (
    SkillProperties,
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
    SkillActivationError,
    SkillResourceError,
)

logger = logging.getLogger(__name__)

# 资源文件大小上限5 MB
_MAX_RESOURCE_SIZE = 5 * 1024 * 1024


class SkillManager:
    """
    Skill 管理器

    负责 Skill 的发现、激活、资源访问和 prompt 生成。
    完全兼容 agentskills.io 开放标准，可直接使用社区发布的 Skill。

    Args:
        skill_paths: Skill 目录搜索路径列表，支持字符串或 Path 对象
        auto_discover: 初始化时是否自动执行 discover()

    Example:
        >>> manager = SkillManager(["./skills"])
        >>> for skill in manager.discover():
        ...     print(f"{skill.name}: {skill.description}")
        >>> content = manager.activate("pdf-processing")
        >>> print(content.instructions)
    """

    def __init__(
        self,
        skill_paths: Optional[List[Union[str, Path]]] = None,
        auto_discover: bool = True,
        sandbox_skill_root: Optional[str] = None,
    ):
        # 搜索路径列表
        self._search_paths: List[Path] = []

        # Phase 1 缓存：name -> SkillProperties
        self._discovered: Dict[str, SkillProperties] = {}

        # Phase 2 缓存：name -> SkillContent
        self._activated: Dict[str, SkillContent] = {}

        # 记录发现过程中遇到的错误（不中断整体流程）
        self._discovery_errors: List[str] = []

        # When set, to_prompt() outputs sandbox-internal paths instead of host
        # paths, enabling LLM to construct valid commands for in-sandbox execution.
        self._sandbox_skill_root: Optional[str] = sandbox_skill_root

        if skill_paths:
            for p in skill_paths:
                self.add_path(p)

        if auto_discover and self._search_paths:
            self.discover()

    # 路径管理
    def add_path(self, path: Union[str, Path]) -> "SkillManager":
        """
        添加 Skill 搜索路径

        Args:
            path: 目录路径，支持 ~ 展开

        Returns:
            self（支持链式调用）

        Example:
            >>> manager = SkillManager()
            >>> manager.add_path("./skills").add_path("~/.alphora/skills")
        """
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
        """Sandbox-internal skill mount path (e.g. '/mnt/skills'), or None for host paths."""
        return self._sandbox_skill_root

    @sandbox_skill_root.setter
    def sandbox_skill_root(self, value: Optional[str]) -> None:
        self._sandbox_skill_root = value

    #  Discovery
    def discover(self) -> List[SkillProperties]:
        """
        扫描所有搜索路径，发现可用的 Skill（Phase 1）

        遍历搜索路径下的子目录，解析每个包含 SKILL.md 的目录。
        仅加载 YAML frontmatter 元数据，不加载正文内容。

        解析失败的 Skill 会记录警告日志但不会中断整体流程。

        Returns:
            已发现的 SkillProperties 列表

        Example:
            >>> manager = SkillManager(["./skills"])
            >>> skills = manager.discover()
            >>> print(f"Found {len(skills)} skills")
        """
        self._discovered.clear()
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

            # 跳过隐藏目录和常见非 skill 目录
            if entry.name.startswith((".", "_", "__")):
                continue

            skill_md = entry / "SKILL.md"
            if not skill_md.exists():
                continue

            # 支持 symlink
            actual_dir = entry.resolve() if entry.is_symlink() else entry

            try:
                props = parse_properties(actual_dir)

                # 校验：name 应与目录名匹配
                if props.name != entry.name:
                    logger.warning(
                        f"Skill name '{props.name}' does not match "
                        f"directory name '{entry.name}' (at {entry}). "
                        f"Using directory name as key."
                    )

                # 重名检测
                if props.name in self._discovered:
                    existing = self._discovered[props.name]
                    logger.warning(
                        f"Duplicate skill name '{props.name}': "
                        f"'{existing.path}' will be overridden by '{actual_dir}'"
                    )

                self._discovered[props.name] = props

            except (SkillParseError, SkillError) as e:
                self._discovery_errors.append(f"{entry.name}: {e}")
                logger.debug(f"Failed to parse skill at {entry}: {e}")

    def add_skill_dir(self, skill_dir: Union[str, Path]) -> SkillProperties:
        """
        直接注册一个 Skill 目录（无需经过搜索路径扫描）

        适用于动态添加单个 Skill 的场景。

        Args:
            skill_dir: Skill 目录路径

        Returns:
            解析得到的 SkillProperties

        Raises:
            SkillParseError: 解析失败

        Example:
            >>> props = manager.add_skill_dir("/path/to/my-skill")
            >>> print(props.name)
        """
        resolved = Path(skill_dir).expanduser().resolve()

        if not resolved.is_dir():
            raise SkillParseError(f"Not a directory: {resolved}")
        if not (resolved / "SKILL.md").exists():
            raise SkillParseError(f"SKILL.md not found in {resolved}")

        props = parse_properties(resolved)
        self._discovered[props.name] = props

        logger.info(f"Registered skill: {props.name} ({resolved})")
        return props

    # Activation
    def activate(self, name: str) -> SkillContent:
        """
        激活指定 Skill，加载完整指令内容（Phase 2）

        首次激活会读取 SKILL.md 全文并缓存，后续调用返回缓存内容。

        Args:
            name: Skill 名称

        Returns:
            SkillContent，包含元数据和完整指令

        Raises:
            SkillNotFoundError: 指定名称的 Skill 未被发现
            SkillActivationError: 加载内容失败

        Example:
            >>> content = manager.activate("pdf-processing")
            >>> print(content.instructions)
        """
        # 缓存命中
        if name in self._activated:
            logger.debug(f"Skill '{name}' activated from cache")
            return self._activated[name]

        # 检查是否已 discover
        if name not in self._discovered:
            raise SkillNotFoundError(
                name, available=list(self._discovered.keys())
            )

        props = self._discovered[name]

        try:
            content = parse_content(props.path)
        except SkillParseError as e:
            raise SkillActivationError(
                f"Failed to activate skill '{name}': {e}"
            )

        # 更新状态
        content.properties.status = SkillStatus.ACTIVATED

        # 缓存
        self._activated[name] = content

        logger.info(
            f"Activated skill '{name}' "
            f"({len(content.instructions)} chars, "
            f"~{len(content.instructions) // 4} tokens)"
        )

        return content

    def deactivate(self, name: str) -> None:
        """
        反激活 Skill，释放缓存的完整内容

        Args:
            name: Skill 名称
        """
        if name in self._activated:
            self._activated[name].properties.status = SkillStatus.DISCOVERED
            del self._activated[name]
            logger.debug(f"Deactivated skill '{name}'")

    # Resource Access
    def read_resource(
        self,
        skill_name: str,
        relative_path: str,
    ) -> SkillResource:
        """
        读取 Skill 的资源文件（Phase 3）

        支持读取 scripts/、references/、assets/ 等目录下的文件。
        内置路径遍历攻击防护。

        Args:
            skill_name: Skill 名称
            relative_path: 相对于 Skill 目录的文件路径

        Returns:
            SkillResource 实例

        Raises:
            SkillNotFoundError: Skill 不存在
            SkillResourceError: 资源文件不存在或路径非法

        Example:
            >>> ref = manager.read_resource("pdf-processing", "references/FORMS.md")
            >>> print(ref.content)
        """
        skill_dir = self._resolve_skill_dir(skill_name)
        target = (skill_dir / relative_path).resolve()

        # 安全检查：防止路径遍历
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

        # 大小检查
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

        # 判断资源类型
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
        """
        列出 Skill 目录下的所有资源文件

        Args:
            skill_name: Skill 名称

        Returns:
            SkillDirectoryInfo 实例

        Example:
            >>> info = manager.list_resources("pdf-processing")
            >>> print(info.to_display())
        """
        skill_dir = self._resolve_skill_dir(skill_name)

        info = SkillDirectoryInfo(skill_name=skill_name)

        for item in sorted(skill_dir.rglob("*")):
            if not item.is_file():
                continue

            rel = item.relative_to(skill_dir)
            rel_str = str(rel)

            # 跳过隐藏文件
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
                info.files.append(rel_str)

        return info

    def get_script_path(self, skill_name: str, script_name: str) -> Path:
        """
        获取 Skill 脚本的绝对路径（用于沙箱执行）

        Args:
            skill_name: Skill 名称
            script_name: 脚本文件名或相对路径

        Returns:
            脚本的绝对路径

        Raises:
            SkillResourceError: 脚本不存在或路径非法
        """
        skill_dir = self._resolve_skill_dir(skill_name)

        # 如果 script_name 不带 scripts/ 前缀，自动补上
        if not script_name.startswith("scripts/"):
            script_name = f"scripts/{script_name}"

        target = (skill_dir / script_name).resolve()

        # 安全检查
        try:
            target.relative_to(skill_dir)
        except ValueError:
            raise SkillResourceError(
                f"Path traversal detected in script path: '{script_name}'"
            )

        if not target.exists():
            raise SkillResourceError(
                f"Script not found: '{script_name}' in skill '{skill_name}'"
            )

        return target

    # Prompt 生成
    def to_prompt(self, format: str = "xml") -> str:
        """
        生成可注入 system prompt 的 Skill 清单

        遵循 agentskills.io 推荐的 <available_skills> XML 格式，
        也支持 Markdown 格式。

        Args:
            format: 输出格式，"xml"（默认，推荐）或 "markdown"

        Returns:
            格式化的 Skill 清单字符串

        Example:
            >>> prompt = manager.to_prompt()
            >>> # 注入到 system prompt
            >>> system = f"你是一个助手。\\n\\n{prompt}"
        """
        if not self._discovered:
            return ""

        if format == "xml":
            return self._to_xml_prompt()
        elif format == "markdown":
            return self._to_markdown_prompt()
        else:
            raise ValueError(f"Unsupported prompt format: '{format}'. Use 'xml' or 'markdown'.")

    def _skill_location(self, props: SkillProperties) -> str:
        """Return the display location for a skill (sandbox path or host path)."""
        if self._sandbox_skill_root:
            root = self._sandbox_skill_root.rstrip("/")
            return f"{root}/{props.name}/SKILL.md"
        return str(props.skill_md_path)

    def _to_xml_prompt(self) -> str:
        """生成 XML 格式的 available_skills 提示词（agentskills.io 推荐）"""
        lines = ["<available_skills>"]

        for props in self._discovered.values():
            lines.append("<skill>")
            lines.append(f"<name>{props.name}</name>")
            lines.append(f"<description>{props.description}</description>")
            lines.append(f"<location>{self._skill_location(props)}</location>")
            lines.append("</skill>")

        lines.append("</available_skills>")
        return "\n".join(lines)

    def _to_markdown_prompt(self) -> str:
        """生成 Markdown 格式的 Skill 清单"""
        lines = ["## Available Skills", ""]

        for props in self._discovered.values():
            location = self._skill_location(props)
            lines.append(f"- **{props.name}**: {props.description}")
            lines.append(f"  Location: `{location}`")

        return "\n".join(lines)

    def to_system_instruction(self, format: str = "xml") -> str:
        """
        生成完整的 Skill 系统指令（包含使用说明和 Skill 清单）

        比 to_prompt() 更完整，包含了指导 LLM 如何使用 Skills 的说明。
        适合直接拼接到 system prompt 末尾。

        Args:
            format: Skill 清单格式

        Returns:
            完整的系统指令字符串
        """
        if not self._discovered:
            return ""

        skill_list = self.to_prompt(format=format)

        instruction = (
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

        return instruction

    # 查询接口
    def get_skill(self, name: str) -> Optional[SkillProperties]:
        """获取指定 Skill 的元数据，不存在返回 None"""
        return self._discovered.get(name)

    @property
    def skills(self) -> Dict[str, SkillProperties]:
        """所有已发现的 Skill（只读视图）"""
        return dict(self._discovered)

    @property
    def skill_names(self) -> List[str]:
        """所有已发现的 Skill 名称列表"""
        return list(self._discovered.keys())

    @property
    def activated_skills(self) -> List[str]:
        """已激活的 Skill 名称列表"""
        return list(self._activated.keys())

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
            f"activated={len(self._activated)}, "
            f"paths={len(self._search_paths)})"
        )

    # 校验
    def validate(self, name: str) -> List[str]:
        """
        校验指定 Skill 是否符合 agentskills.io 规范

        Args:
            name: Skill 名称

        Returns:
            违规描述列表，空表示通过

        Example:
            >>> issues = manager.validate("my-skill")
            >>> if issues:
            ...     print("Validation failed:", issues)
        """
        skill_dir = self._resolve_skill_dir(name)
        return validate_skill(skill_dir)

    def validate_all(self) -> Dict[str, List[str]]:
        """
        校验所有已发现的 Skill

        Returns:
            {skill_name: [violations]} 字典，仅包含有问题的 Skill
        """
        results = {}
        for name, props in self._discovered.items():
            issues = validate_skill(props.path)
            if issues:
                results[name] = issues
        return results

    # 缓存管理
    def refresh(self) -> List[SkillProperties]:
        """
        刷新：清除所有缓存并重新发现

        Returns:
            重新发现的 SkillProperties 列表
        """
        self._activated.clear()
        return self.discover()

    def clear(self) -> None:
        """清除所有状态（发现缓存、激活缓存、搜索路径）"""
        self._discovered.clear()
        self._activated.clear()
        self._search_paths.clear()
        self._discovery_errors.clear()

    def _resolve_skill_dir(self, name: str) -> Path:
        """根据名称获取 Skill 目录路径，不存在则抛异常"""
        if name not in self._discovered:
            raise SkillNotFoundError(
                name, available=list(self._discovered.keys())
            )
        return self._discovered[name].path
