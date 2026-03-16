# Copyright 2026 China Mobile Information Technology Co., Ltd.
# SPDX-License-Identifier: Apache-2.0

"""
Alphora Skills - Agent Skills 标准兼容组件

快速开始::

    from alphora.skills import load_skill

    skill = load_skill("./skills/pdf")
    print(skill.instructions)

多 Skill 管理::

    from alphora.skills import SkillManager

    manager = SkillManager(["./skills"])
    skill = manager.load("pdf")

一站式 Agent 集成::

    from alphora.skills import setup_skills

    setup = setup_skills(paths=["./skills"], sandbox=sandbox)
    registry.register_many(setup.tools)
"""

from .models import (
    Skill,
    SkillProperties,
    SkillContent,
    SkillResource,
    SkillDirectoryInfo,
    SkillStatus,
)
from .manager import SkillManager
from .tools import (
    create_skill_tools,
    create_filesystem_skill_tools,
)
from .setup import (
    setup_skills,
    load_skill,
    SkillSetup,
)
from .exceptions import (
    SkillError,
    SkillParseError,
    SkillValidationError,
    SkillNotFoundError,
    SkillLoadError,
    SkillActivationError,
    SkillResourceError,
)

# parser functions kept importable via alphora.skills.parser but not in __all__
from .parser import (
    parse_frontmatter,
    parse_properties,
    parse_content,
    validate_skill,
)

__all__ = [
    # Core
    "Skill",
    "SkillManager",
    "setup_skills",
    "load_skill",
    "SkillSetup",

    # Tool creation (advanced)
    "create_skill_tools",
    "create_filesystem_skill_tools",

    # Exceptions
    "SkillError",
    "SkillNotFoundError",
    "SkillLoadError",

    # Backward compat (deprecated)
    "SkillProperties",
    "SkillContent",
    "SkillActivationError",
]
