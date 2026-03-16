# Copyright 2026 China Mobile Information Technology Co., Ltd.
# SPDX-License-Identifier: Apache-2.0

"""
Skill 内置工具集

提供 LLM 可调用的工具函数，用于在 ReAct 循环中与 Skills 交互：

- read_skill: 加载 Skill 完整指令
- read_skill_resource: 读取资源文件
- list_skill_resources: 列出资源目录

工具创建方式::

    tools = create_skill_tools(manager)
"""

from typing import List, Optional, TYPE_CHECKING
import logging

from .manager import SkillManager
from .exceptions import SkillError
from alphora.tools.decorators import Tool

logger = logging.getLogger(__name__)


def create_skill_tools(
    manager: SkillManager,
) -> list:
    """
    创建 Skill 交互工具集

    生成一组可被 LLM 调用的工具，用于发现和读取 Skills。
    这些工具会被注册到 ToolRegistry，通过 OpenAI Function Calling 协议暴露给 LLM。

    Skill 脚本的执行不由这些工具负责——LLM 读取 SKILL.md 后，
    自主推理出沙箱内路径并通过 run_shell_command 执行。

    Args:
        manager: SkillManager 实例，提供 Skill 数据访问

    Returns:
        Tool 实例列表，可直接注册到 ToolRegistry

    Example:
        >>> manager = SkillManager(["./skills"])
        >>> tools = create_skill_tools(manager)
        >>> registry = ToolRegistry()
        >>> for t in tools:
        ...     registry.register(t)
    """
    from alphora.tools.decorators import tool

    # Tool 1: 读取并激活 Skill

    @tool(
        name="read_skill",
        description=(
            "Load the full instructions of a specific skill. "
            "Call this when you need to use a skill's expertise to complete a task. "
            "Returns the complete SKILL.md content with step-by-step instructions."
        )
    )
    def read_skill(skill_name: str) -> str:
        """
        读取并激活指定的 Skill，返回其完整指令内容。

        Args:
            skill_name: Skill 名称（如 'pdf-processing'、'data-analysis'）

        Returns:
            Skill 的完整 Markdown 指令内容
        """
        try:
            skill = manager.load(skill_name)
            return skill.instructions
        except SkillError as e:
            return f"Error: {e}"

    # Tool 2: 读取资源文件
    @tool(
        name="read_skill_resource",
        description=(
            "Read a specific resource file from a skill's directory. "
            "Use this to access reference documentation, templates, or script source code "
            "within a skill. Provide the skill name and the relative file path."
        )
    )
    def read_skill_resource(skill_name: str, resource_path: str) -> str:
        """
        读取 Skill 中的资源文件内容。

        Args:
            skill_name: Skill 名称
            resource_path: 相对于 Skill 目录的文件路径（如 'references/FORMS.md'、'scripts/extract.py'）

        Returns:
            资源文件的文本内容
        """
        try:
            resource = manager.read_resource(skill_name, resource_path)
            return resource.content
        except SkillError as e:
            return f"Error: {e}"

    # Tool 3: 列出资源目录
    @tool(
        name="list_skill_resources",
        description=(
            "List all available resource files in a skill's directory. "
            "Use this to explore what scripts, references, and assets a skill provides "
            "before deciding which ones to read."
        )
    )
    def list_skill_resources(skill_name: str) -> str:
        """
        列出 Skill 目录下的所有资源文件。

        Args:
            skill_name: Skill 名称

        Returns:
            格式化的目录结构字符串
        """
        try:
            info = manager.list_resources(skill_name)
            return info.to_display()
        except SkillError as e:
            return f"Error: {e}"

    return [read_skill, read_skill_resource, list_skill_resources]


def create_filesystem_skill_tools(manager: SkillManager) -> list:
    """
    创建基于文件系统的 Skill 工具（适用于有 bash 能力的 Agent）

    与 create_skill_tools 不同，这组工具不封装 SkillManager 的方法，
    而是直接提供文件路径信息，让 LLM 通过 bash/shell 工具自行读取文件。
    更接近 Claude Code 的原生 Skill 使用方式。

    Args:
        manager: SkillManager 实例

    Returns:
        Tool 实例列表
    """
    from alphora.tools.decorators import tool

    @tool(
        name="get_skill_path",
        description=(
            "Get the filesystem path to a skill's SKILL.md file. "
            "Use this to locate a skill so you can read it with bash commands. "
            "Returns the absolute path."
        )
    )
    def get_skill_path(skill_name: str) -> str:
        """
        获取 Skill 的 SKILL.md 文件路径。

        Args:
            skill_name: Skill 名称

        Returns:
            SKILL.md 的绝对路径（沙箱环境下返回沙箱内路径）
        """
        try:
            return str(manager.resolve_skill_md_path(skill_name))
        except SkillError as e:
            return f"Error: {e}"

    @tool(
        name="get_skill_directory",
        description=(
            "Get the filesystem path to a skill's root directory. "
            "Returns the absolute path to the skill directory "
            "that contains SKILL.md, scripts/, references/, and assets/."
        )
    )
    def get_skill_directory(skill_name: str) -> str:
        """
        获取 Skill 的目录路径。

        Args:
            skill_name: Skill 名称

        Returns:
            Skill 目录的绝对路径（沙箱环境下返回沙箱内路径）
        """
        try:
            return str(manager.resolve_skill_path(skill_name))
        except SkillError as e:
            return f"Error: {e}"

    return [get_skill_path, get_skill_directory]
