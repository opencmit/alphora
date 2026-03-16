"""
Tutorial 16: SkillAgent 快速上手。

SkillAgent 是框架内置的支持 Agent Skills 标准的智能体，
内置 SkillManager 和工具调用循环，可直接加载符合 agentskills.io 标准的 Skill 目录。

本教程分两部分：
  1) SkillManager 基础操作（无需 LLM，本地即可运行）
  2) SkillAgent 完整运行（需要 LLM 环境变量）

如需深入了解 Skills 组件的底层 API 及如何在自定义 Agent 中集成 Skills，
请参考 tutorials/18_skills.py。

Prerequisites (set these env vars for Section 2):
  - LLM_API_KEY
  - LLM_BASE_URL
  - DEFAULT_LLM

Run:
  python tutorials/16_skill_agent_basic.py
"""

import asyncio
import os
from pathlib import Path

from alphora.skills import SkillManager


# ─── Section 1: SkillManager 基础（无需 LLM） ─────────────────────

def section_1_skill_manager_basics() -> None:
    """演示 SkillManager 的核心操作：发现、加载、资源访问、Prompt 生成。"""

    # SkillManager 自动检测：搜索目录和 skill 目录均可传入
    skill_search_path = Path(__file__).parent / "skill_example"
    manager = SkillManager([skill_search_path])

    print("=== 1.1 Discovered Skills ===")
    print("skill_names:", manager.skill_names)
    for name, skill in manager.skills.items():
        print(f"  [{name}] {skill.description[:80]}...")

    print("\n=== 1.2 Validate ===")
    issues = manager.validate("pdf")
    print("pdf validation:", "PASS" if not issues else issues)

    print("\n=== 1.3 Load（加载完整指令） ===")
    skill = manager.load("pdf")
    preview = skill.instructions.splitlines()[:3]
    print("instructions preview:")
    for line in preview:
        print(f"  {line}")
    print(f"  ... ({len(skill.instructions)} chars total)")

    print("\n=== 1.4 List Resources ===")
    print(manager.list_resources("pdf").to_display())

    print("\n=== 1.5 Read Resource ===")
    script = manager.read_resource("pdf", "scripts/check_fillable_fields.py")
    print(f"resource_type: {script.resource_type}")
    print(f"first line: {script.content.splitlines()[0]}")

    print("\n=== 1.6 Prompt Generation ===")
    print("--- XML format ---")
    print(manager.to_prompt(format="xml"))
    print("\n--- System Prompt (truncated) ---")
    instruction = manager.to_system_prompt()
    print(instruction[:300] + "...")


# ─── Section 2: SkillAgent 完整运行（需要 LLM） ─────────────────────

async def section_2_skill_agent_run() -> None:
    """演示 SkillAgent 的完整运行：自动发现 Skill、LLM 按需加载、工具调用循环。"""

    if not os.getenv("LLM_API_KEY") or not os.getenv("LLM_BASE_URL") or not os.getenv("DEFAULT_LLM"):
        print("\n[Skip Section 2] Missing LLM env vars (LLM_API_KEY, LLM_BASE_URL, DEFAULT_LLM).")
        return

    from alphora.agent import SkillAgent
    from alphora.models import OpenAILike
    from alphora.sandbox import Sandbox

    skill_search_path = Path(__file__).parent / "skill_example"

    print("\n=== 2.1 SkillAgent + run() ===")
    async with Sandbox(runtime="docker", workspace_root='/Users/tiantiantian/其他/sb') as sandbox:
        agent = SkillAgent(
            llm=OpenAILike(),
            skill_paths=[skill_search_path],
            sandbox=sandbox,
            system_prompt="你是一个文档处理助手，可以使用 Skills 完成 PDF 相关任务。你必须遵循Skill里面的步骤来处理任务，如果遇到环境依赖不满足，请你优先安装该依赖而不是寻求其他解决方案",
            max_iterations=30,
        )

        print("registered tools:", [t.name for t in agent.tools])
        print("available skills:", agent.skills)

        result = await agent.run("帮我添加水印：中国移动版权所有")
        print("\nAgent result:")
        print(result[:500])
    #
    # print("\n=== 2.2 SkillAgent + run_steps() ===")
    # async with Sandbox(runtime="local") as sandbox:
    #     agent = SkillAgent(
    #         llm=OpenAILike(),
    #         skill_paths=[skill_search_path],
    #         sandbox=sandbox,
    #         max_iterations=10,
    #     )
    #
    #     async for step in agent.run_steps("用 pypdf 拆分一个 PDF 的代码怎么写？"):
    #         print(f"  step {step.iteration}: action={step.action}, final={step.is_final}")
    #         if step.activated_skills:
    #             print(f"    activated_skills: {step.activated_skills}")
    #         if step.is_final:
    #             print(f"    result: {step.content[:200]}...")


async def main() -> None:
    # section_1_skill_manager_basics()
    await section_2_skill_agent_run()


if __name__ == "__main__":
    asyncio.run(main())
