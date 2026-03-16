"""
Tutorial 18: Skills 组件深度教程

本教程面向基于 BaseAgent 开发自定义 Agent 的开发者，完整讲解 Skills 组件的
使用方式和集成模式，让你能在自己的 Agent 中快速接入 Skills 能力。

本教程共 5 个 Section：
  1) SkillManager 完整 API
  2) Skill 工具创建（两种模式）
  3) setup_skills() 一站式集成（含 Sandbox 自动配置）
  4) load_skill() 极简用法
  5) 在自定义 Agent 中集成 Skills（核心重点）

Section 1-4 无需 LLM 即可运行；Section 5 需要 LLM 环境变量。

SKILL.md 文件格式：

    一个合法的 Skill 目录结构如下：

        my-skill/
        ├── SKILL.md          # 必需：YAML frontmatter + Markdown 指令
        ├── scripts/          # 可选：可执行脚本
        ├── references/       # 可选：参考文档
        └── assets/           # 可选：静态资源

    SKILL.md 格式：

        ---
        name: pdf                        # kebab-case, 需与目录名一致
        description: Use this skill ...  # 描述功能和触发条件
        ---
        (Markdown 正文：详细的操作指令)

Prerequisites (set these env vars for Section 5):
  - LLM_API_KEY
  - LLM_BASE_URL
  - DEFAULT_LLM

Run:
  python tutorials/18_skills.py
"""

import asyncio
import os
from pathlib import Path

from alphora.skills import (
    Skill,
    SkillManager,
    create_skill_tools,
    create_filesystem_skill_tools,
    setup_skills,
    load_skill,
)


SKILL_EXAMPLE_DIR = Path(__file__).parent / "skill_example"
PDF_SKILL_DIR = SKILL_EXAMPLE_DIR / "pdf"


# Section 1: SkillManager 完整 API
def section_1_skill_manager_api() -> None:
    """
    SkillManager 是 Skills 组件的核心。

    路径自动检测：构造函数接受搜索目录和 skill 目录的混合列表，
    如果路径下直接有 SKILL.md 则视为 skill 目录，否则扫描其子目录。
    """

    print("=" * 60)
    print("Section 1: SkillManager 完整 API")
    print("=" * 60)

    # 1.1 创建与发现（自动检测路径类型）
    print("\n--- 1.1 创建 & 路径自动检测 ---")
    manager = SkillManager(auto_discover=False)
    manager.add_path(SKILL_EXAMPLE_DIR)
    discovered = manager.discover()
    print(f"  search_paths: {manager.search_paths}")
    print(f"  discovered: {len(discovered)} skill(s) -> {manager.skill_names}")

    # 也可以直接传 skill 目录
    manager2 = SkillManager([PDF_SKILL_DIR])
    print(f"  直接传 skill 目录: {manager2.skill_names}")

    # 1.2 查看 Skill（返回 Skill 对象）
    print("\n--- 1.2 Skill 对象 ---")
    skill = manager.get_skill("pdf")
    print(f"  type:        {type(skill).__name__}")
    print(f"  name:        {skill.name}")
    print(f"  description: {skill.description}")
    print(f"  path:        {skill.path}")

    # 1.3 load() —— 显式加载完整指令
    print("\n--- 1.3 load() ---")
    skill = manager.load("pdf")
    print(f"  status:   {skill.status}")
    print(f"  loaded_skills: {manager.loaded_skills}")
    print(f"  instructions: {len(skill.instructions)} chars")

    # 1.4 懒加载 vs 显式 load
    print("\n--- 1.4 instructions 懒加载 ---")
    manager3 = SkillManager([SKILL_EXAMPLE_DIR])
    s = manager3.get_skill("pdf")
    print(f"  is_loaded before access: {s.is_loaded}")
    _ = s.instructions  # 触发懒加载
    print(f"  is_loaded after access:  {s.is_loaded}")
    print(f"  loaded_skills (not via load()): {manager3.loaded_skills}")

    # 1.5 资源访问
    print("\n--- 1.5 资源访问 ---")
    dir_info = manager.list_resources("pdf")
    print(f"  scripts:    {dir_info.scripts}")
    resource = manager.read_resource("pdf", "scripts/check_fillable_fields.py")
    print(f"  resource_type: {resource.resource_type}")
    print('---'*10)
    print(f"  content: \n{resource.content}")
    print('---'*10)

    script_path = manager.get_script_path("pdf", "check_fillable_fields.py")
    print(f"  script abs path: {script_path}")

    # 1.6 unload & 缓存管理
    print("\n--- 1.6 unload() & 缓存管理 ---")
    print(f"  loaded before unload: {manager.loaded_skills}")
    manager.unload("pdf")
    print(f"  loaded after unload:  {manager.loaded_skills}")

    # 1.7 Prompt 生成
    print("\n--- 1.7 Prompt 生成 ---")
    print("  XML format:")
    print(f"    {manager.to_prompt(format='xml')[:200]}...")
    print("  System Prompt:")
    sp = manager.to_system_prompt()
    print(f"    {sp[:200]}...")
    print(f"    ... ({len(sp)} chars total)")


# Section 2: Skill 工具创建 -- 两种模式
def section_2_skill_tools() -> None:
    """
    Skills 组件提供两种工具创建方式：

    1. 标准模式 (create_skill_tools):
       生成 read_skill / read_skill_resource / list_skill_resources 三个工具。
       适合通过 Function Calling 交互的 Agent。

    2. 文件系统模式 (create_filesystem_skill_tools):
       生成 get_skill_path / get_skill_directory 两个工具。
       适合有 bash/shell 能力的 Agent。
    """

    print("\n" + "=" * 60)
    print("Section 2: Skill 工具创建")
    print("=" * 60)

    manager = SkillManager([SKILL_EXAMPLE_DIR])

    # 2.1 标准模式
    print("\n--- 2.1 create_skill_tools() [标准模式] ---")
    std_tools = create_skill_tools(manager)
    print(f"  生成 {len(std_tools)} 个工具:")
    for t in std_tools:
        print(f"    - {t.name}: {t.description[:60]}...")

    from alphora.tools import ToolRegistry
    registry = ToolRegistry()
    registry.register_many(std_tools)
    schema = registry.get_openai_tools_schema()
    print(f"\n  OpenAI Function Schema ({len(schema)} tools):")
    for tool_schema in schema:
        func = tool_schema["function"]
        print(f"    {func['name']}: params={list(func['parameters'].get('properties', {}).keys())}")

    print("\n  模拟调用 read_skill('pdf'):")
    result = std_tools[0].run(skill_name="pdf")
    print(f"    返回 {len(result)} chars 的指令内容")

    # 2.2 文件系统模式
    print("\n--- 2.2 create_filesystem_skill_tools() [文件系统模式] ---")
    fs_tools = create_filesystem_skill_tools(manager)
    print(f"  生成 {len(fs_tools)} 个工具:")
    for t in fs_tools:
        print(f"    - {t.name}: {t.description[:60]}...")


# Section 3: setup_skills() 一站式集成
async def section_3_setup_skills() -> None:
    """
    setup_skills() 将 SkillManager 创建、工具生成、system prompt 生成
    封装为一次调用。当传入 sandbox 时还会自动注册 SandboxTools。

    返回 SkillSetup 对象::

        setup.tools              # skill 工具 + sandbox 工具（如果有）
        setup.system_instruction # 可拼接到 system prompt 的指令
        setup.manager            # 底层 SkillManager 实例
    """

    print("\n" + "=" * 60)
    print("Section 3: setup_skills() 一站式集成")
    print("=" * 60)

    # 3.1 基础用法
    print("\n--- 3.1 基础用法 ---")
    setup = setup_skills(paths=[SKILL_EXAMPLE_DIR])
    print(f"  tools:              {[t.name for t in setup.tools]}")
    print(f"  system_instruction: {len(setup.system_instruction)} chars")

    # 3.2 使用已有 SkillManager
    print("\n--- 3.2 使用已有 SkillManager ---")
    manager = SkillManager([SKILL_EXAMPLE_DIR])
    setup2 = setup_skills(skill_manager=manager)
    print(f"  tools: {[t.name for t in setup2.tools]}")
    print(f"  same manager: {setup2.manager is manager}")

    # 3.3 带 Sandbox（自动双向绑定 + SandboxTools 自动注册）
    print("\n--- 3.3 带 Sandbox（双向绑定） ---")
    from alphora.sandbox import Sandbox

    async with Sandbox(runtime="docker") as sandbox:
        # setup_skills 内部调用 sandbox.mount_skill(manager)，完成：
        #   1) sandbox 获得 skill 宿主路径（动态挂载）
        #   2) manager 自动感知沙箱环境，所有路径输出切换为 /mnt/skills/...
        #   3) SandboxTools 自动注册
        setup3 = setup_skills(paths=[SKILL_EXAMPLE_DIR], sandbox=sandbox)
        tool_names = [t.name for t in setup3.tools]
        print(f"  tools: {tool_names}")
        print(f"  包含 sandbox 工具: {'run_shell_command' in tool_names}")
        print(f"  sandbox_skill_root: {setup3.manager.sandbox_skill_root}")
        print(f"  sandbox.skill_host_path: {sandbox.skill_host_path}")

        # manager 的路径输出已自动适配为沙箱路径
        print(f"  resolve_skill_path('pdf'): {setup3.manager.resolve_skill_path('pdf')}")
        prompt_xml = setup3.manager.to_prompt(format="xml")
        for line in prompt_xml.splitlines():
            if "<location>" in line:
                print(f"  prompt location: {line.strip()}")

        res = await sandbox.execute_shell(command='cd skills && ls')
        print(res)

        from alphora.sandbox import SandboxTools
        sbt = SandboxTools(sandbox=sandbox)
        res = await sbt.run_shell_command(command='python /mnt/workspace/skills/pdf/scripts/hello_world.py')
        print(res)

    # 3.4 手动调用 sandbox.mount_skill()（高级）
    print("\n--- 3.4 sandbox.mount_skill() 手动绑定 ---")
    manager = SkillManager([SKILL_EXAMPLE_DIR])
    sandbox2 = Sandbox(runtime="docker")
    sandbox2.mount_skill(manager)
    print(f"  sandbox.skill_host_path: {sandbox2.skill_host_path}")
    print(f"  manager.sandbox_skill_root: {manager.sandbox_skill_root}")
    print(f"  resolve_skill_path('pdf'): {manager.resolve_skill_path('pdf')}")

    # 也能直接传路径（不绑定 manager）
    sandbox3 = Sandbox(runtime="local")
    sandbox3.mount_skill(SKILL_EXAMPLE_DIR)
    print(f"  mount_skill(path): sandbox.skill_host_path = {sandbox3.skill_host_path}")

    # 3.5 不需要 sandbox 工具时
    print("\n--- 3.5 include_sandbox_tools=False ---")
    setup4 = setup_skills(paths=[SKILL_EXAMPLE_DIR], include_sandbox_tools=False)
    print(f"  tools: {[t.name for t in setup4.tools]}")


# Section 4: load_skill() 极简用法
def section_4_load_skill() -> None:
    """
    load_skill() 是加载单个 Skill 的最简方式：

        skill = load_skill("./skills/pdf")
        print(skill.instructions)
    """

    print("\n" + "=" * 60)
    print("Section 4: load_skill() 极简用法")
    print("=" * 60)

    skill = load_skill(PDF_SKILL_DIR)
    print(f"  name: {skill.name}")
    print(f"  description: {skill.description[:60]}...")
    print(f"  instructions: {len(skill.instructions)} chars")
    print(f"  first 3 lines:")
    for line in skill.instructions.splitlines()[:3]:
        print(f"    {line}")


# Section 5: 在自定义 Agent 中集成 Skills（核心重点）
from alphora.agent import BaseAgent
from alphora.models.llms.openai_like import OpenAILike
from alphora.tools.registry import ToolRegistry
from alphora.tools.executor import ToolExecutor
from alphora.tools.decorators import tool
from typing import List, Union, Optional, Callable
from alphora.tools.decorators import Tool


class MySkillAwareAgent(BaseAgent):
    """
    自定义 Skill-aware Agent 示例。

    核心集成只需 3 步：
    1. setup_skills(paths=..., sandbox=...) 获取工具和系统指令
    2. 注册所有工具到 ToolRegistry
    3. 拼接 system prompt
    """

    agent_type: str = "MySkillAwareAgent"

    def __init__(
        self,
        llm: OpenAILike,
        skill_paths: List[Union[str, Path]],
        tools: Optional[List[Union[Tool, Callable]]] = None,
        system_prompt: str = "",
        max_iterations: int = 20,
        sandbox=None,
        **kwargs,
    ):
        super().__init__(llm=llm, **kwargs)

        # --- 步骤 1: 一站式配置（含 sandbox 工具自动注册） ---
        setup = setup_skills(paths=skill_paths, sandbox=sandbox)
        self._skill_manager = setup.manager

        # --- 步骤 2: 注册所有工具 ---
        self._registry = ToolRegistry()
        if tools:
            self._registry.register_many(tools)
        self._registry.register_many(setup.tools)
        self._executor = ToolExecutor(self._registry)

        # --- 步骤 3: 拼接 system prompt ---
        parts = [system_prompt] if system_prompt else ["你是一个 AI 助手。"]
        if setup.system_instruction:
            parts.append(setup.system_instruction)
        self._prompt = self.create_prompt(system_prompt="\n\n".join(parts))
        self._max_iterations = max_iterations

    async def run(self, task: str) -> str:
        """标准 ReAct 循环。"""

        self.memory.add_user(content=task)
        tools_schema = self._registry.get_openai_tools_schema()

        for iteration in range(self._max_iterations):
            history = self.memory.build_history()

            response = await self._prompt.acall(
                query=task if iteration == 0 else None,
                history=history,
                tools=tools_schema,
                is_stream=True,
            )

            self.memory.add_assistant(content=response)

            if not response.has_tool_calls:
                return response.content

            tool_results = await self._executor.execute(response.tool_calls)
            self.memory.add_tool_result(result=tool_results)

        return "达到最大迭代次数，任务未完成。"


async def main() -> None:
    section_1_skill_manager_api()
    section_2_skill_tools()
    await section_3_setup_skills()
    section_4_load_skill()


if __name__ == "__main__":
    asyncio.run(main())
