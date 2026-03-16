"""
Tutorial 18: Skills 组件深度教程。

本教程面向基于 BaseAgent 开发自定义 Agent 的开发者，完整讲解 Skills 组件的
使用方式、底层 API 及集成模式，让你能在自己的 Agent 中快速接入 Skills 能力。

SkillAgent 也是继承 BaseAgent 并集成 Skills 组件开发的，本教程帮助你掌握
同样的集成方式，从而构建自己的 Skill-aware Agent。

本教程共 6 个 Section：
  1) Skill 目录结构与 SKILL.md 规范
  2) SkillManager 完整 API（渐进式披露三阶段）
  3) Skill 工具创建（两种模式）
  4) setup_skills() 一站式集成
  5) Skills + Sandbox 集成（路径映射与脚本执行）
  6) 在自定义 Agent 中集成 Skills（核心重点）

Section 1-5 无需 LLM 即可运行；Section 6 需要 LLM 环境变量。

Prerequisites (set these env vars for Section 6):
  - LLM_API_KEY
  - LLM_BASE_URL
  - DEFAULT_LLM

Run:
  python tutorials/18_skills.py
"""

import asyncio
import json
import os
from pathlib import Path

from alphora.skills import (
    SkillManager,
    create_skill_tools,
    create_filesystem_skill_tools,
    setup_skills,
)
from alphora.skills.parser import parse_properties, parse_content, validate_skill


SKILL_EXAMPLE_DIR = Path(__file__).parent / "skill_example"
PDF_SKILL_DIR = SKILL_EXAMPLE_DIR / "pdf"


# ═══════════════════════════════════════════════════════════════════
# Section 1: Skill 目录结构与 SKILL.md 规范
# ═══════════════════════════════════════════════════════════════════

def section_1_skill_structure() -> None:
    """
    一个合法的 Skill 目录结构如下：

        my-skill/
        ├── SKILL.md          # 必需：YAML frontmatter + Markdown 指令
        ├── scripts/          # 可选：可执行脚本
        ├── references/       # 可选：参考文档（如 FORMS.md）
        └── assets/           # 可选：静态资源（图片、模板等）

    SKILL.md 的 YAML frontmatter 必须包含 name 和 description 字段：

        ---
        name: pdf                        # kebab-case, 需与目录名一致
        description: Use this skill ...  # 描述功能和触发条件
        license: Apache-2.0              # 可选
        metadata:                        # 可选：自定义键值对
          author: your-name
          version: "1.0"
        ---
        (Markdown 正文：详细的操作指令)

    以下演示如何用底层解析函数解析 SKILL.md。
    """

    print("=" * 60)
    print("Section 1: Skill 目录结构与 SKILL.md 规范")
    print("=" * 60)

    # 1.1 用底层解析器获取元数据（Phase 1 级别，仅 frontmatter）
    print("\n--- 1.1 parse_properties() ---")
    props = parse_properties(PDF_SKILL_DIR)
    print(f"  name:        {props.name}")
    print(f"  description: {props.description[:80]}...")
    print(f"  license:     {props.license}")
    print(f"  path:        {props.path}")
    print(f"  skill_md:    {props.skill_md_path}")

    # 1.2 用底层解析器获取完整内容（Phase 2 级别，含 Markdown 正文）
    print("\n--- 1.2 parse_content() ---")
    content = parse_content(PDF_SKILL_DIR)
    print(f"  instructions length: {len(content.instructions)} chars")
    print(f"  first 3 lines:")
    for line in content.instructions.splitlines()[:3]:
        print(f"    {line}")

    # 1.3 校验是否符合 agentskills.io 规范
    print("\n--- 1.3 validate_skill() ---")
    issues = validate_skill(PDF_SKILL_DIR)
    if not issues:
        print("  PASS: pdf skill 完全符合规范")
    else:
        for issue in issues:
            print(f"  WARN: {issue}")


# ═══════════════════════════════════════════════════════════════════
# Section 2: SkillManager 完整 API
# ═══════════════════════════════════════════════════════════════════

def section_2_skill_manager_api() -> None:
    """
    SkillManager 是 Skills 组件的核心，实现 agentskills.io 标准的
    渐进式披露（Progressive Disclosure）模式：

      Phase 1 - Discovery : 仅加载元数据（~100 tokens/skill），用于 system prompt 注入
      Phase 2 - Activation: 按需加载完整 SKILL.md 指令（由 LLM 通过 read_skill 工具触发）
      Phase 3 - Resources : 按需加载 scripts/ references/ assets/（由 LLM 按需读取）

    这种设计确保 system prompt 不会因为 Skill 数量增加而膨胀，
    LLM 只在需要时才加载完整指令和资源。
    """

    print("\n" + "=" * 60)
    print("Section 2: SkillManager 完整 API")
    print("=" * 60)

    # 2.1 创建与发现
    print("\n--- 2.1 创建 & discover() ---")
    manager = SkillManager(auto_discover=False)
    manager.add_path(SKILL_EXAMPLE_DIR)
    discovered = manager.discover()
    print(f"  search_paths: {manager.search_paths}")
    print(f"  discovered: {len(discovered)} skill(s) -> {manager.skill_names}")

    # 2.2 Phase 1: 查看元数据
    print("\n--- 2.2 Phase 1: 元数据 (SkillProperties) ---")
    pdf_props = manager.get_skill("pdf")
    print(f"  name:        {pdf_props.name}")
    print(f"  description: {pdf_props.description[:60]}...")
    print(f"  status:      {pdf_props.status}")  # DISCOVERED

    # 2.3 Phase 2: 激活（加载完整指令）
    print("\n--- 2.3 Phase 2: activate() ---")
    pdf_content = manager.activate("pdf")
    print(f"  status after activate: {pdf_content.properties.status}")  # ACTIVATED
    print(f"  instructions: {len(pdf_content.instructions)} chars")
    print(f"  activated_skills: {manager.activated_skills}")

    # 2.4 Phase 3: 资源访问
    print("\n--- 2.4 Phase 3: list_resources() & read_resource() ---")
    dir_info = manager.list_resources("pdf")
    print(f"  scripts:    {dir_info.scripts}")
    print(f"  files:      {dir_info.files}")

    resource = manager.read_resource("pdf", "scripts/check_fillable_fields.py")
    print(f"  read_resource type: {resource.resource_type}")
    print(f"  first line: {resource.content.splitlines()[0]}")

    # 2.5 get_script_path（用于 Sandbox 执行）
    print("\n--- 2.5 get_script_path() ---")
    script_path = manager.get_script_path("pdf", "check_fillable_fields.py")
    print(f"  absolute path: {script_path}")

    # 2.6 缓存管理
    print("\n--- 2.6 缓存管理 ---")
    print(f"  activated before deactivate: {manager.activated_skills}")
    manager.deactivate("pdf")
    print(f"  activated after deactivate:  {manager.activated_skills}")
    manager.activate("pdf")
    print(f"  activated after re-activate: {manager.activated_skills}")

    # 2.7 动态添加 Skill 目录
    print("\n--- 2.7 add_skill_dir() ---")
    manager2 = SkillManager(auto_discover=False)
    props = manager2.add_skill_dir(PDF_SKILL_DIR)
    print(f"  直接注册: {props.name} (无需 discover)")
    print(f"  skill_names: {manager2.skill_names}")

    # 2.8 Prompt 生成
    print("\n--- 2.8 Prompt 生成 ---")
    print("  XML format:")
    print(f"    {manager.to_prompt(format='xml')[:200]}...")
    print("  Markdown format:")
    print(f"    {manager.to_prompt(format='markdown')[:200]}...")
    print("  System Instruction (完整版，含使用说明):")
    si = manager.to_system_instruction()
    print(f"    {si[:200]}...")
    print(f"    ... ({len(si)} chars total)")


# ═══════════════════════════════════════════════════════════════════
# Section 3: Skill 工具创建 -- 两种模式
# ═══════════════════════════════════════════════════════════════════

def section_3_skill_tools() -> None:
    """
    Skills 组件提供两种工具创建方式，适配不同 Agent 架构：

    1. 标准模式 (create_skill_tools):
       生成 read_skill / read_skill_resource / list_skill_resources 三个工具。
       工具内部封装了 SkillManager 的方法调用。
       适合：通过 Function Calling 协议与 LLM 交互的 Agent。

    2. 文件系统模式 (create_filesystem_skill_tools):
       生成 get_skill_path / get_skill_directory 两个工具。
       只返回文件路径，LLM 自行通过 bash/cat 命令读取。
       适合：有 bash/shell 能力的 Agent（类似 Claude Code 的模式）。
    """

    print("\n" + "=" * 60)
    print("Section 3: Skill 工具创建")
    print("=" * 60)

    manager = SkillManager([SKILL_EXAMPLE_DIR])

    # 3.1 标准模式
    print("\n--- 3.1 create_skill_tools() [标准模式] ---")
    std_tools = create_skill_tools(manager)
    print(f"  生成 {len(std_tools)} 个工具:")
    for t in std_tools:
        print(f"    - {t.name}: {t.description[:60]}...")

    # 展示 OpenAI Function Schema
    from alphora.tools import ToolRegistry
    registry = ToolRegistry()
    registry.register_many(std_tools)
    schema = registry.get_openai_tools_schema()
    print(f"\n  OpenAI Function Schema ({len(schema)} tools):")
    for tool_schema in schema:
        func = tool_schema["function"]
        print(f"    {func['name']}: params={list(func['parameters'].get('properties', {}).keys())}")

    # 模拟 LLM 调用 read_skill
    print("\n  模拟调用 read_skill('pdf'):")
    result = std_tools[0].run(skill_name="pdf")
    print(f"    返回 {len(result)} chars 的指令内容")

    # 3.2 文件系统模式
    print("\n--- 3.2 create_filesystem_skill_tools() [文件系统模式] ---")
    fs_tools = create_filesystem_skill_tools(manager)
    print(f"  生成 {len(fs_tools)} 个工具:")
    for t in fs_tools:
        print(f"    - {t.name}: {t.description[:60]}...")

    # 模拟调用
    print("\n  模拟调用 get_skill_path('pdf'):")
    path_result = fs_tools[0].run(skill_name="pdf")
    print(f"    返回路径: {path_result}")

    print("\n  模拟调用 get_skill_directory('pdf'):")
    dir_result = fs_tools[1].run(skill_name="pdf")
    print(f"    返回路径: {dir_result}")


# ═══════════════════════════════════════════════════════════════════
# Section 4: setup_skills() 一站式集成
# ═══════════════════════════════════════════════════════════════════

def section_4_setup_skills() -> None:
    """
    setup_skills() 将 SkillManager 创建、工具生成、system instruction 生成
    封装为一次调用，返回 SkillSetup 对象，包含集成所需的一切：

        setup = setup_skills(skill_paths=["./skills"])
        setup.tools              # 可注册到 ToolRegistry 的工具列表
        setup.system_instruction  # 可拼接到 system prompt 的指令
        setup.manager            # 底层 SkillManager 实例

    这是在自定义 Agent 中集成 Skills 的推荐入口。
    """

    print("\n" + "=" * 60)
    print("Section 4: setup_skills() 一站式集成")
    print("=" * 60)

    # 4.1 基础用法
    print("\n--- 4.1 基础用法 ---")
    setup = setup_skills(skill_paths=[SKILL_EXAMPLE_DIR])
    print(f"  tools:              {[t.name for t in setup.tools]}")
    print(f"  system_instruction: {len(setup.system_instruction)} chars")
    print(f"  manager:            {setup.manager}")

    # 4.2 使用已有 SkillManager
    print("\n--- 4.2 使用已有 SkillManager ---")
    manager = SkillManager([SKILL_EXAMPLE_DIR])
    setup2 = setup_skills(skill_manager=manager)
    print(f"  tools: {[t.name for t in setup2.tools]}")
    print(f"  same manager: {setup2.manager is manager}")

    # 4.3 文件系统模式
    print("\n--- 4.3 filesystem_mode=True ---")
    setup3 = setup_skills(skill_paths=[SKILL_EXAMPLE_DIR], filesystem_mode=True)
    print(f"  tools: {[t.name for t in setup3.tools]}")

    # 4.4 setup 的 system_instruction 内容预览
    print("\n--- 4.4 system_instruction 内容 ---")
    lines = setup.system_instruction.splitlines()
    for line in lines[:8]:
        print(f"  {line}")
    if len(lines) > 8:
        print(f"  ... (共 {len(lines)} 行)")


# ═══════════════════════════════════════════════════════════════════
# Section 5: Skills + Sandbox 集成
# ═══════════════════════════════════════════════════════════════════

async def section_5_sandbox_integration() -> None:
    """
    Skills 与 Sandbox 结合使用时，框架自动处理路径映射，让 LLM 能在
    沙箱内正确定位和执行 Skill 脚本。

    核心机制：
      - 宿主机: skill 目录在 /home/user/skills/pdf/scripts/...
      - 沙箱内: 挂载到 /mnt/skills/pdf/scripts/...
      - setup_skills(sandbox=sandbox) 自动配置路径映射
      - LLM 在 system prompt 中看到的是沙箱内路径 /mnt/skills/...
      - LLM 通过 run_shell_command 在沙箱内执行脚本

    沙箱内的文件系统布局：

        /mnt/workspace/          <-- 工作目录 (cwd)
        ├── uploads/             <-- 用户上传的文件
        ├── outputs/             <-- 最终输出文件
        └── ...
        /mnt/skills/             <-- Skill 目录（只读挂载）
        └── pdf/
            ├── SKILL.md
            ├── scripts/
            │   ├── check_fillable_fields.py
            │   └── ...
            └── forms.md
    """

    print("\n" + "=" * 60)
    print("Section 5: Skills + Sandbox 集成")
    print("=" * 60)

    from alphora.sandbox import Sandbox, SandboxTools
    from alphora.sandbox.config import SANDBOX_SKILLS_MOUNT

    # 5.1 sandbox_skill_root：路径映射的关键
    print("\n--- 5.1 sandbox_skill_root 路径映射 ---")
    print(f"  SANDBOX_SKILLS_MOUNT 常量: {SANDBOX_SKILLS_MOUNT}")

    manager = SkillManager([SKILL_EXAMPLE_DIR])

    print(f"\n  未配置 sandbox 时的 prompt（使用宿主机路径）:")
    prompt_before = manager.to_prompt(format="xml")
    for line in prompt_before.splitlines():
        if "<location>" in line:
            print(f"    {line.strip()}")

    manager.sandbox_skill_root = SANDBOX_SKILLS_MOUNT
    print(f"\n  配置 sandbox_skill_root='{SANDBOX_SKILLS_MOUNT}' 后的 prompt:")
    prompt_after = manager.to_prompt(format="xml")
    for line in prompt_after.splitlines():
        if "<location>" in line:
            print(f"    {line.strip()}")

    # 5.2 setup_skills(sandbox=...) 自动配置
    print("\n--- 5.2 setup_skills(sandbox=...) 自动配置 ---")
    print("  当传入 sandbox 参数时，setup_skills() 自动完成：")
    print("    1. 设置 manager.sandbox_skill_root = '/mnt/skills'")
    print("    2. 设置 sandbox._skill_host_path 指向宿主机 skill 目录")
    print("    3. prompt 中的路径自动切换为沙箱内路径")
    print()
    print("  代码示例：")
    print("    setup = setup_skills(skill_paths=['./skills'], sandbox=sandbox)")
    print("    # prompt 中会显示 /mnt/skills/pdf/SKILL.md 而非宿主机绝对路径")

    # 5.3 SandboxTools 与 Skill Tools 协同注册
    print("\n--- 5.3 SandboxTools + Skill Tools 协同注册 ---")
    print("  在自定义 Agent 中，需要同时注册两类工具：")
    print("    - Skill 工具: read_skill, read_skill_resource, list_skill_resources")
    print("    - Sandbox 工具: run_shell_command, save_file, list_files, ...")
    print()
    print("  LLM 的典型调用链路：")
    print("    1. LLM 调用 read_skill('pdf') -> 获取 SKILL.md 指令")
    print("    2. 指令中提到 scripts/check_fillable_fields.py")
    print("    3. LLM 调用 run_shell_command('python /mnt/skills/pdf/scripts/check_fillable_fields.py input.pdf')")
    print("    4. 脚本在沙箱内执行，结果返回给 LLM")
    print()
    print("  注册代码示例：")
    print("    skill_setup = setup_skills(skill_paths=['./skills'], sandbox=sandbox)")
    print("    sandbox_tools = SandboxTools(sandbox)")
    print("    registry = ToolRegistry()")
    print("    registry.register_many(skill_setup.tools)")
    print("    registry.register(sandbox_tools.save_file)")
    print("    registry.register(sandbox_tools.list_files)")
    print("    registry.register(sandbox_tools.run_shell_command)")

    # 5.4 实际验证（使用 local sandbox）
    print("\n--- 5.4 实际验证（Local Sandbox） ---")
    async with Sandbox(runtime="local") as sandbox:
        setup = setup_skills(
            skill_paths=[SKILL_EXAMPLE_DIR],
            sandbox=sandbox,
        )

        print(f"  sandbox_skill_root: {setup.manager.sandbox_skill_root}")
        print(f"  tools: {[t.name for t in setup.tools]}")

        prompt_xml = setup.manager.to_prompt(format="xml")
        for line in prompt_xml.splitlines():
            if "<location>" in line:
                print(f"  prompt location: {line.strip()}")

        sandbox_tools = SandboxTools(sandbox)
        result = await sandbox_tools.run_shell_command("echo 'Skill scripts can run here'")
        print(f"  sandbox exec test: {result.get('output', '').strip()}")

    # 5.5 Docker Sandbox 说明
    print("\n--- 5.5 Docker Sandbox 补充说明 ---")
    print("  使用 Docker 后端时，skill 目录会自动挂载到容器内：")
    print("    宿主机: ./skills/pdf/scripts/xxx.py")
    print("    容器内: /mnt/skills/pdf/scripts/xxx.py")
    print()
    print("  代码与 local 完全一致，只需切换 runtime：")
    print("    async with Sandbox(runtime='docker') as sandbox:")
    print("        setup = setup_skills(skill_paths=['./skills'], sandbox=sandbox)")
    print("        # 后续代码不变")


# ═══════════════════════════════════════════════════════════════════
# Section 6: 在自定义 Agent 中集成 Skills（核心重点）
# ═══════════════════════════════════════════════════════════════════

# 以下展示如何在继承 BaseAgent 的自定义 Agent 中手动集成 Skills 组件。
# 这与 SkillAgent 的内部实现模式一致（参见 alphora/agent/skill_agent.py），
# 但你可以完全控制 prompt 构造、工具注册和执行循环。

from alphora.agent import BaseAgent
from alphora.models.llms.openai_like import OpenAILike
from alphora.tools.registry import ToolRegistry
from alphora.tools.executor import ToolExecutor
from alphora.tools.decorators import tool
from typing import List, Union, Optional, Callable
from alphora.tools.decorators import Tool


class MySkillAwareAgent(BaseAgent):
    """
    自定义的 Skill-aware Agent 示例。

    演示如何将 Skills 组件集成到你自己的 BaseAgent 子类中：
    1. 使用 setup_skills() 获取 Skill 工具和系统指令
    2. 将 Skill 工具与自定义工具合并注册到 ToolRegistry
    3. 可选集成 Sandbox，让 LLM 能执行 Skill 脚本
    4. 将 Skill 系统指令拼接到 system prompt
    5. 在 run() 的 ReAct 循环中驱动 LLM 自主选择和使用 Skills
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
        self._sandbox = sandbox

        # --- 核心步骤 1: 一站式 Skill 配置（传入 sandbox 自动处理路径映射） ---
        skill_setup = setup_skills(skill_paths=skill_paths, sandbox=sandbox)
        self._skill_manager = skill_setup.manager

        # --- 核心步骤 2: 合并注册 Skill 工具 + 自定义工具 + Sandbox 工具 ---
        self._registry = ToolRegistry()
        if tools:
            self._registry.register_many(tools)
        self._registry.register_many(skill_setup.tools)

        if sandbox is not None:
            from alphora.sandbox import SandboxTools
            sandbox_tools = SandboxTools(sandbox)
            for t in [sandbox_tools.save_file, sandbox_tools.list_files, sandbox_tools.run_shell_command]:
                try:
                    self._registry.register(t)
                except Exception:
                    pass

        self._executor = ToolExecutor(self._registry)

        # --- 核心步骤 3: 拼接 system prompt ---
        parts = [system_prompt] if system_prompt else ["你是一个 AI 助手。"]
        if skill_setup.system_instruction:
            parts.append(skill_setup.system_instruction)
        full_prompt = "\n\n".join(parts)

        self._prompt = self.create_prompt(system_prompt=full_prompt)
        self._max_iterations = max_iterations

    async def run(self, task: str) -> str:
        """ReAct 循环：LLM 推理 -> 工具调用 -> 结果回写 -> 循环。"""

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


async def section_6_custom_agent() -> None:
    """演示 MySkillAwareAgent 的使用。"""

    print("\n" + "=" * 60)
    print("Section 6: 在自定义 Agent 中集成 Skills")
    print("=" * 60)

    if not os.getenv("LLM_API_KEY") or not os.getenv("LLM_BASE_URL") or not os.getenv("DEFAULT_LLM"):
        print("\n[Skip] Missing LLM env vars (LLM_API_KEY, LLM_BASE_URL, DEFAULT_LLM).")

        print("\n以下是 MySkillAwareAgent 的集成要点（无需运行即可参考）：")
        print("""
    class MySkillAwareAgent(BaseAgent):
        def __init__(self, llm, skill_paths, tools=None, system_prompt="",
                     sandbox=None, ...):
            super().__init__(llm=llm, ...)

            # 1. 一站式 Skill 配置（传入 sandbox 自动处理路径映射）
            skill_setup = setup_skills(skill_paths=skill_paths, sandbox=sandbox)

            # 2. 合并注册工具
            self._registry = ToolRegistry()
            self._registry.register_many(skill_setup.tools)  # Skill 工具
            if tools:
                self._registry.register_many(tools)           # 自定义工具
            if sandbox:                                       # Sandbox 工具
                sandbox_tools = SandboxTools(sandbox)
                self._registry.register(sandbox_tools.run_shell_command)
                self._registry.register(sandbox_tools.save_file)
                self._registry.register(sandbox_tools.list_files)
            self._executor = ToolExecutor(self._registry)

            # 3. 拼接 system prompt
            full_prompt = system_prompt + "\\n\\n" + skill_setup.system_instruction
            self._prompt = self.create_prompt(system_prompt=full_prompt)

        async def run(self, task: str) -> str:
            # 4. 标准 ReAct 循环（与 ReActAgent 相同）
            self.memory.add_user(content=task)
            tools_schema = self._registry.get_openai_tools_schema()
            for iteration in range(self._max_iterations):
                history = self.memory.build_history()
                response = await self._prompt.acall(
                    history=history, tools=tools_schema, is_stream=True,
                )
                self.memory.add_assistant(content=response)
                if not response.has_tool_calls:
                    return response.content
                tool_results = await self._executor.execute(response.tool_calls)
                self.memory.add_tool_result(result=tool_results)
            return "max iterations reached"
        """)
        return

    # --- 实际运行 ---

    @tool
    def get_current_date() -> str:
        """获取当前日期。"""
        from datetime import date
        return str(date.today())

    llm = OpenAILike()

    agent = MySkillAwareAgent(
        llm=llm,
        skill_paths=[SKILL_EXAMPLE_DIR],
        tools=[get_current_date],
        system_prompt="你是一个文档处理助手，擅长 PDF 相关操作。请用中文回答。",
        max_iterations=10,
    )

    print(f"\n  agent type:   {agent.agent_type}")
    print(f"  skill_names:  {agent._skill_manager.skill_names}")
    print(f"  all tools:    {[t.name for t in agent._registry.get_all_tools()]}")

    print("\n  Running agent...")
    result = await agent.run("请告诉我如何用 Python 从 PDF 中提取表格数据？")
    print(f"\n  Agent result:")
    print(f"  {result[:500]}")


# ═══════════════════════════════════════════════════════════════════

async def main() -> None:
    section_1_skill_structure()
    section_2_skill_manager_api()
    section_3_skill_tools()
    section_4_setup_skills()
    await section_5_sandbox_integration()
    await section_6_custom_agent()


if __name__ == "__main__":
    asyncio.run(main())
