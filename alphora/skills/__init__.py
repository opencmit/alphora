# Copyright 2026 China Mobile Information Technology Co., Ltd.
# SPDX-License-Identifier: Apache-2.0

"""
Alphora Skills - Agent Skills 标准兼容组件

兼容 agentskills.io 开放标准的 Skill 管理模块，支持渐进式披露、
资源按需加载、自动 prompt 注入等能力。可与社区发布的 Skill 无缝配合。

快速开始：
    from alphora.skills import SkillManager

    manager = SkillManager(["./skills"])
    print(manager.skill_names)           # 查看可用 skill
    prompt = manager.to_prompt()         # 生成 system prompt 注入内容
    content = manager.activate("pdf")    # 激活指定 skill

与 Agent 集成：
    from alphora.skills import SkillManager, create_skill_tools

    manager = SkillManager(["./skills"])
    tools = create_skill_tools(manager)  # 生成 LLM 可调用的工具
"""

from .manager import SkillManager
from .models import (
    SkillProperties,
    SkillContent,
    SkillResource,
    SkillDirectoryInfo,
    SkillStatus,
)
from .parser import (
    parse_frontmatter,
    parse_properties,
    parse_content,
    validate_skill,
)
from .tools import (
    create_skill_tools,
    create_filesystem_skill_tools,
)
from .setup import (
    setup_skills,
    SkillSetup,
)
from .exceptions import (
    SkillError,
    SkillParseError,
    SkillValidationError,
    SkillNotFoundError,
    SkillActivationError,
    SkillResourceError,
)

__all__ = [
    # 核心管理器
    "SkillManager",

    # 数据模型
    "SkillProperties",
    "SkillContent",
    "SkillResource",
    "SkillDirectoryInfo",
    "SkillStatus",

    # 解析器
    "parse_frontmatter",
    "parse_properties",
    "parse_content",
    "validate_skill",

    # 工具创建
    "create_skill_tools",
    "create_filesystem_skill_tools",

    # 一站式集成
    "setup_skills",
    "SkillSetup",

    # 异常
    "SkillError",
    "SkillParseError",
    "SkillValidationError",
    "SkillNotFoundError",
    "SkillActivationError",
    "SkillResourceError",
]
