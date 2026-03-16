# Copyright 2026 China Mobile Information Technology Co., Ltd.
# SPDX-License-Identifier: Apache-2.0

"""
Skills 数据模型

定义 Skill 的核心数据结构，遵循 agentskills.io 规范。

核心类型:
    Skill               统一的 Skill 对象（元数据 + 懒加载指令）
    SkillResource       资源文件
    SkillDirectoryInfo  目录结构概览

向后兼容:
    SkillProperties     Skill 的别名（deprecated）
    SkillContent        包装类（deprecated）
"""

from pathlib import Path
from typing import Dict, List, Optional, Any
from enum import Enum
import warnings

from pydantic import BaseModel, Field, PrivateAttr, field_validator

import re


NAME_PATTERN = re.compile(r"^[a-z0-9]([a-z0-9-]*[a-z0-9])?$")
NAME_MAX_LENGTH = 64
DESCRIPTION_MAX_LENGTH = 1024
COMPATIBILITY_MAX_LENGTH = 500
INSTRUCTIONS_RECOMMENDED_TOKENS = 5000
SKILL_MD_MAX_LINES = 500


class SkillStatus(str, Enum):
    """Skill 生命周期状态"""
    DISCOVERED = "discovered"
    LOADED = "loaded"
    ERROR = "error"

    # deprecated aliases
    ACTIVATED = "loaded"


class Skill(BaseModel):
    """
    统一的 Skill 对象，包含元数据和懒加载的指令内容。

    discover 时仅填充元数据字段（name, description 等）；
    指令内容（instructions）在首次访问时自动从 SKILL.md 加载。

    Attributes:
        name: Skill 名称，kebab-case
        description: 功能描述与触发条件
        license: 许可证标识
        compatibility: 环境要求
        metadata: 自定义键值对
        allowed_tools: 预授权工具列表（实验性）
        path: Skill 目录绝对路径
        status: 生命周期状态
    """

    name: str = Field(
        ...,
        min_length=1,
        max_length=NAME_MAX_LENGTH,
        description="Skill name in kebab-case",
    )
    description: str = Field(
        ...,
        min_length=1,
        max_length=DESCRIPTION_MAX_LENGTH,
        description="What the skill does and when to use it",
    )
    license: Optional[str] = Field(
        default=None,
        description="License identifier or file reference",
    )
    compatibility: Optional[str] = Field(
        default=None,
        max_length=COMPATIBILITY_MAX_LENGTH,
        description="Environment requirements",
    )
    metadata: Optional[Dict[str, Any]] = Field(
        default=None,
        description="Arbitrary key-value metadata",
    )
    allowed_tools: Optional[List[str]] = Field(
        default=None,
        description="Pre-approved tools (experimental)",
    )

    path: Path = Field(
        ...,
        description="Absolute path to skill directory",
        exclude=True,
    )
    status: SkillStatus = Field(
        default=SkillStatus.DISCOVERED,
        exclude=True,
    )

    _instructions: Optional[str] = PrivateAttr(default=None)
    _raw_content: Optional[str] = PrivateAttr(default=None)

    class Config:
        frozen = False

    @field_validator("name")
    @classmethod
    def validate_name(cls, v: str) -> str:
        if not NAME_PATTERN.match(v):
            raise ValueError(
                f"Invalid skill name '{v}'. "
                f"Must contain only lowercase letters, numbers, and hyphens. "
                f"Must not start or end with a hyphen."
            )
        if "--" in v:
            raise ValueError(
                f"Invalid skill name '{v}'. Consecutive hyphens are not allowed."
            )
        return v

    # --- instructions 懒加载 ---

    @property
    def instructions(self) -> str:
        """SKILL.md 的 Markdown 正文（首次访问时自动加载）。"""
        if self._instructions is None:
            self._load_content()
        return self._instructions  # type: ignore[return-value]

    @property
    def raw_content(self) -> str:
        """SKILL.md 的完整原始内容（首次访问时自动加载）。"""
        if self._raw_content is None:
            self._load_content()
        return self._raw_content  # type: ignore[return-value]

    def _load_content(self) -> None:
        from .parser import parse_skill_md
        _, body = parse_skill_md(self.path)
        self._instructions = body
        self._raw_content = (self.path / "SKILL.md").read_text(encoding="utf-8")

    def _set_instructions(self, instructions: str, raw_content: str = "") -> None:
        """由 SkillManager 在显式 load() 时调用，避免重复 IO。"""
        self._instructions = instructions
        self._raw_content = raw_content

    def _clear_instructions(self) -> None:
        """由 SkillManager.unload() 调用，释放缓存。"""
        self._instructions = None
        self._raw_content = None

    @property
    def is_loaded(self) -> bool:
        return self._instructions is not None

    # --- 便捷路径属性 ---

    @property
    def skill_md_path(self) -> Path:
        return self.path / "SKILL.md"

    @property
    def scripts_dir(self) -> Path:
        return self.path / "scripts"

    @property
    def references_dir(self) -> Path:
        return self.path / "references"

    @property
    def assets_dir(self) -> Path:
        return self.path / "assets"

    def __str__(self) -> str:
        loaded = "loaded" if self.is_loaded else "discovered"
        return f"Skill(name='{self.name}', status={loaded})"

    def __repr__(self) -> str:
        return self.__str__()


# ---------------------------------------------------------------------------
# Deprecated aliases -- 保留向后兼容，1 个大版本周期后移除
# ---------------------------------------------------------------------------

# SkillProperties 现在就是 Skill（字段完全一致）
SkillProperties = Skill


class SkillContent(BaseModel):
    """
    .. deprecated::
        Use ``Skill`` directly. ``skill.instructions`` now lazy-loads content.

    保留此类仅为向后兼容，内部包装一个 Skill 对象。
    """

    properties: Skill
    instructions: str = Field(
        ...,
        description="Markdown body with skill instructions",
    )
    raw_content: str = Field(
        default="",
        description="Full raw content of SKILL.md",
    )

    class Config:
        arbitrary_types_allowed = True

    @property
    def name(self) -> str:
        return self.properties.name

    @property
    def description(self) -> str:
        return self.properties.description

    @property
    def path(self) -> Path:
        return self.properties.path

    def __str__(self) -> str:
        preview = self.instructions[:200]
        if len(self.instructions) > 200:
            preview += "..."
        return f"SkillContent(name='{self.name}', instructions='{preview}')"


class SkillResource(BaseModel):
    """
    Skill 资源文件

    对应渐进式披露的 Phase 3（按需加载）。
    包括 scripts/、references/、assets/ 下的文件。

    Attributes:
        skill_name: 所属 Skill 名称
        relative_path: 相对于 Skill 目录的路径
        content: 文件文本内容
        resource_type: 资源类型 (script / reference / asset / other)
    """

    skill_name: str
    relative_path: str
    content: str
    resource_type: str = Field(default="other")

    @property
    def filename(self) -> str:
        return Path(self.relative_path).name


class SkillDirectoryInfo(BaseModel):
    """
    Skill 目录结构概览

    用于 list_resources 等接口返回可读的目录信息。
    """

    skill_name: str
    files: List[str] = Field(default_factory=list)
    scripts: List[str] = Field(default_factory=list)
    references: List[str] = Field(default_factory=list)
    assets: List[str] = Field(default_factory=list)

    def to_display(self) -> str:
        """目录结构展示"""
        lines = [f"{self.skill_name}/"]
        lines.append("  └── SKILL.md")

        for category, items in [
            ("scripts", self.scripts),
            ("references", self.references),
            ("assets", self.assets),
        ]:
            if items:
                lines.append(f"  └── {category}/")
                for item in items:
                    lines.append(f"      └── {item}")

        for f in self.files:
            if f != "SKILL.md":
                lines.append(f"  └── {f}")

        return "\n".join(lines)
