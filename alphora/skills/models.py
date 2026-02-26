# Copyright 2026 China Mobile Information Technology Co., Ltd.
# SPDX-License-Identifier: Apache-2.0

"""
Skills 数据模型
定义 Skill 的元数据、内容、资源等数据结构，
遵循 agentskills.io 规范。
"""

from pathlib import Path
from typing import Dict, List, Optional, Any
from enum import Enum

from pydantic import BaseModel, Field, field_validator

import re


NAME_PATTERN = re.compile(r"^[a-z0-9]([a-z0-9-]*[a-z0-9])?$")
NAME_MAX_LENGTH = 64
DESCRIPTION_MAX_LENGTH = 1024
COMPATIBILITY_MAX_LENGTH = 500
INSTRUCTIONS_RECOMMENDED_TOKENS = 5000
SKILL_MD_MAX_LINES = 500


class SkillStatus(str, Enum):
    """Skill 生命周期状态"""
    DISCOVERED = "discovered"       # 仅加载了元数据
    ACTIVATED = "activated"         # 已加载完整指令
    ERROR = "error"                 # 加载出错


class SkillProperties(BaseModel):
    """
    Skill 元数据，从 SKILL.md YAML frontmatter 解析

    对应渐进式披露的 Phase 1（约 50-100 tokens/skill）。
    启动时仅加载此信息用于 discovery 和 system prompt 注入。

    Attributes:
        name: Skill 名称，遵循 kebab-case 命名规范
        description: Skill 描述，说明功能和触发条件
        license: 许可证标识
        compatibility: 环境要求说明
        metadata: 自定义键值对元数据
        allowed_tools: 预授权工具列表（实验性）
        path: Skill 目录的绝对路径
    """

    name: str = Field(
        ...,
        min_length=1,
        max_length=NAME_MAX_LENGTH,
        description="Skill name in kebab-case"
    )
    description: str = Field(
        ...,
        min_length=1,
        max_length=DESCRIPTION_MAX_LENGTH,
        description="What the skill does and when to use it"
    )
    license: Optional[str] = Field(
        default=None,
        description="License identifier or file reference"
    )
    compatibility: Optional[str] = Field(
        default=None,
        max_length=COMPATIBILITY_MAX_LENGTH,
        description="Environment requirements"
    )
    metadata: Optional[Dict[str, Any]] = Field(
        default=None,
        description="Arbitrary key-value metadata"
    )
    allowed_tools: Optional[List[str]] = Field(
        default=None,
        description="Pre-approved tools (experimental)"
    )

    path: Path = Field(
        ...,
        description="Absolute path to skill directory",
        exclude=True  # 序列化时排除
    )
    status: SkillStatus = Field(
        default=SkillStatus.DISCOVERED,
        exclude=True
    )

    class Config:
        frozen = False  # 允许状态更新

    @field_validator("name")
    @classmethod
    def validate_name(cls, v: str) -> str:
        """
        校验名称格式（遵循 agentskills.io 规范）

        规则：
        - 仅允许小写字母、数字、连字符
        - 不以连字符开头或结尾
        - 不包含连续连字符
        """
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

    @property
    def skill_md_path(self) -> Path:
        """SKILL.md 文件的完整路径"""
        return self.path / "SKILL.md"

    @property
    def scripts_dir(self) -> Path:
        """scripts/ 目录路径"""
        return self.path / "scripts"

    @property
    def references_dir(self) -> Path:
        """references/ 目录路径"""
        return self.path / "references"

    @property
    def assets_dir(self) -> Path:
        """assets/ 目录路径"""
        return self.path / "assets"


class SkillContent(BaseModel):
    """
    完整的 Skill 内容，包含元数据和指令

    对应渐进式披露的 Phase 2（建议 < 5000 tokens）。
    仅在 Skill 被激活时加载。

    Attributes:
        properties: Skill 元数据
        instructions: Markdown 正文内容（指令部分）
        raw_content: SKILL.md 的完整原始内容
    """

    properties: SkillProperties
    instructions: str = Field(
        ...,
        description="Markdown body with skill instructions"
    )
    raw_content: str = Field(
        default="",
        description="Full raw content of SKILL.md"
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
