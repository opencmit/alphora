# Copyright 2026 China Mobile Information Technology Co., Ltd.
# SPDX-License-Identifier: Apache-2.0

"""
Skills 一站式集成

将 SkillManager 创建、sandbox 路径映射、工具生成、系统指令生成
封装为一个 setup_skills() 调用，方便自定义 Agent 快速接入 Skills。

用法：
    from alphora.skills import setup_skills

    setup = setup_skills(skill_paths=["./skills"], sandbox=sandbox)
    registry.register_many(setup.tools)
    full_prompt = MY_PROMPT + "\\n\\n" + setup.system_instruction
"""

from dataclasses import dataclass, field
from typing import List, Optional, Union, TYPE_CHECKING
from pathlib import Path
import logging

from alphora.tools.core import Tool
from .manager import SkillManager

if TYPE_CHECKING:
    from alphora.sandbox import Sandbox

logger = logging.getLogger(__name__)


@dataclass
class SkillSetup:
    """setup_skills() 的返回结果，包含集成 Skills 所需的一切。

    Attributes:
        tools: 可直接注册到 ToolRegistry 的 Skill 工具列表
        system_instruction: 可拼接到 system prompt 末尾的指令字符串
        manager: 底层 SkillManager 实例，供高级场景使用
    """

    tools: List[Tool] = field(default_factory=list)
    system_instruction: str = ""
    manager: SkillManager = field(default_factory=lambda: SkillManager(auto_discover=False))


def setup_skills(
    skill_paths: Optional[List[Union[str, Path]]] = None,
    skill_manager: Optional[SkillManager] = None,
    sandbox: Optional["Sandbox"] = None,
    filesystem_mode: bool = False,
    prompt_format: str = "xml",
) -> SkillSetup:
    """
    一站式配置 Skills，返回工具列表和系统指令。

    自动处理 SkillManager 创建、sandbox 路径映射、工具生成和
    系统指令生成，将原本分散的 6 步操作合为 1 次调用。

    Args:
        skill_paths: Skill 目录搜索路径列表（与 skill_manager 二选一）
        skill_manager: 已创建的 SkillManager 实例（与 skill_paths 二选一）
        sandbox: 可选的 Sandbox 实例，传入后自动配置路径映射
        filesystem_mode: 为 True 时生成文件系统工具（适合有 bash 能力的 Agent），
                        为 False 时生成标准 read_skill 系列工具
        prompt_format: 系统指令中 Skill 清单的格式，"xml" 或 "markdown"

    Returns:
        SkillSetup 实例，包含 tools、system_instruction 和 manager

    Example::

        # 最简用法
        setup = setup_skills(skill_paths=["./skills"])

        # 带沙箱
        setup = setup_skills(skill_paths=["./skills"], sandbox=sandbox)

        # 在自定义 Agent 中使用
        registry = ToolRegistry()
        registry.register_many([
            sandbox_tools.save_file,
            sandbox_tools.list_files,
            *setup.tools,
        ])
        prompt = self.create_prompt(
            system_prompt=MY_PROMPT + "\\n\\n" + setup.system_instruction
        )
    """
    if skill_manager is not None:
        manager = skill_manager
    elif skill_paths:
        manager = SkillManager(skill_paths=skill_paths, auto_discover=True)
    else:
        manager = SkillManager(auto_discover=False)

    if sandbox is not None:
        _configure_sandbox_paths(manager, sandbox)

    if filesystem_mode:
        from .tools import create_filesystem_skill_tools
        tools = create_filesystem_skill_tools(manager)
    else:
        from .tools import create_skill_tools
        tools = create_skill_tools(manager)

    system_instruction = manager.to_system_instruction(format=prompt_format)

    logger.info(
        "setup_skills: %d skill(s) discovered, %d tool(s) created",
        len(manager), len(tools),
    )

    return SkillSetup(
        tools=tools,
        system_instruction=system_instruction,
        manager=manager,
    )


def _configure_sandbox_paths(manager: SkillManager, sandbox: "Sandbox") -> None:
    """自动配置 SkillManager 与 Sandbox 之间的路径映射。"""
    from alphora.sandbox.config import SANDBOX_SKILLS_MOUNT

    if not manager.sandbox_skill_root:
        manager.sandbox_skill_root = SANDBOX_SKILLS_MOUNT

    if not getattr(sandbox, "skill_host_path", None) and manager.search_paths:
        sandbox._skill_host_path = manager.search_paths[0]
        logger.debug(
            "Auto-configured sandbox skill_host_path: %s",
            sandbox._skill_host_path,
        )
