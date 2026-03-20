# Copyright 2026 China Mobile Information Technology Co., Ltd.
# SPDX-License-Identifier: Apache-2.0

"""
Skills 一站式集成

将 SkillManager 创建、sandbox 路径映射、工具生成、系统指令生成
封装为一个 setup_skills() 调用，方便自定义 Agent 快速接入 Skills。

用法::

    from alphora.skills import setup_skills

    setup = setup_skills(paths=["./skills"], sandbox=sandbox)
    registry.register_many(setup.tools)   # 已含 sandbox tools
    full_prompt = MY_PROMPT + "\\n\\n" + setup.system_instruction
"""

from dataclasses import dataclass, field
from typing import List, Optional, Union, TYPE_CHECKING
from pathlib import Path
import logging

from alphora.tools.core import Tool
from .manager import SkillManager
from .models import Skill

if TYPE_CHECKING:
    from alphora.sandbox import Sandbox

logger = logging.getLogger(__name__)


@dataclass
class SkillSetup:
    """setup_skills() 的返回结果。

    Attributes:
        tools: 可直接注册到 ToolRegistry 的工具列表（含 skill 工具和可选的 sandbox 工具）
        system_instruction: 可拼接到 system prompt 末尾的指令字符串
        manager: 底层 SkillManager 实例
    """

    tools: List[Tool] = field(default_factory=list)
    system_instruction: str = ""
    manager: SkillManager = field(default_factory=lambda: SkillManager(auto_discover=False))


def setup_skills(
    paths: Optional[List[Union[str, Path]]] = None,
    skill_manager: Optional[SkillManager] = None,
    sandbox: Optional["Sandbox"] = None,
    filesystem_mode: bool = False,
    prompt_format: str = "xml",
    include_sandbox_tools: bool = True,
    # deprecated alias
    skill_paths: Optional[List[Union[str, Path]]] = None,
) -> SkillSetup:
    """
    一站式配置 Skills，返回工具列表和系统指令。

    自动处理 SkillManager 创建、sandbox 路径映射、工具生成和
    系统指令生成。当传入 ``sandbox`` 时默认也会注册 SandboxTools。

    Args:
        paths: 路径列表（搜索目录或 skill 目录均可，自动检测）
        skill_manager: 已创建的 SkillManager（与 paths 二选一）
        sandbox: Sandbox 实例，传入后自动配置路径映射并注册 sandbox 工具
        filesystem_mode: True 时生成文件系统工具（适合有 bash 能力的 Agent）
        prompt_format: 系统指令中 Skill 清单的格式，"xml" 或 "markdown"
        include_sandbox_tools: sandbox 非 None 时是否自动注册 SandboxTools（默认 True）
        skill_paths: deprecated, 用 paths 替代

    Returns:
        SkillSetup 实例

    Example::

        setup = setup_skills(paths=["./skills"], sandbox=sandbox)
        registry.register_many(setup.tools)
    """
    effective_paths = paths or skill_paths

    if skill_manager is not None:
        manager = skill_manager
    elif effective_paths:
        manager = SkillManager(paths=effective_paths, auto_discover=True)
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

    if sandbox is not None and include_sandbox_tools:
        tools = list(tools)
        try:
            from alphora.sandbox import SandboxTools
            sbt = SandboxTools(sandbox)
            sandbox_methods = [sbt.run_shell_command, sbt.save_file, sbt.list_files, sbt.markdown_to_pdf]
            for m in sandbox_methods:
                tools.append(Tool.from_function(m))
        except ImportError:
            logger.debug("Sandbox module not available, skipping sandbox tools")

    system_instruction = manager.to_system_prompt(format=prompt_format)

    logger.info(
        "setup_skills: %d skill(s) discovered, %d tool(s) created",
        len(manager), len(tools),
    )

    return SkillSetup(
        tools=tools,
        system_instruction=system_instruction,
        manager=manager,
    )


def load_skill(path: Union[str, Path]) -> Skill:
    """
    加载单个 Skill 的极简入口。

    Args:
        path: skill 目录路径（包含 SKILL.md 的目录）

    Returns:
        Skill 对象（instructions 懒加载）

    Example::

        from alphora.skills import load_skill

        skill = load_skill("./skills/pdf")
        print(skill.name)
        print(skill.instructions)
    """
    resolved = Path(path).expanduser().resolve()

    if not resolved.is_dir():
        from .exceptions import SkillParseError
        raise SkillParseError(f"Not a directory: {resolved}")

    manager = SkillManager(paths=[resolved], auto_discover=True)

    if not manager.skill_names:
        from .exceptions import SkillParseError
        raise SkillParseError(
            f"No skill found at '{resolved}'. "
            f"Make sure the directory contains a SKILL.md file, "
            f"or is a parent directory containing skill subdirectories."
        )

    name = manager.skill_names[0]
    return manager.load(name)


def _configure_sandbox_paths(manager: SkillManager, sandbox: "Sandbox") -> None:
    """Establish the bidirectional binding between SkillManager and Sandbox."""
    if not sandbox.skill_host_path:
        sandbox.mount_skill(manager)
    elif not manager.sandbox_skill_root:
        from alphora.sandbox.config import SANDBOX_SKILLS_MOUNT
        manager.sandbox_skill_root = SANDBOX_SKILLS_MOUNT
