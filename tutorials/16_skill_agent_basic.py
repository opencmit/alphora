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
    """演示 SkillManager 的核心操作：发现、校验、激活、资源访问、Prompt 生成。"""

    skill_search_path = Path(__file__).parent / "skill_example"
    manager = SkillManager([skill_search_path])

    # 1.1 发现 Skill
    print("=== 1.1 Discovered Skills ===")
    print("skill_names:", manager.skill_names)
    for name, props in manager.skills.items():
        print(f"  [{name}] {props.description[:80]}...")

    # 1.2 校验 Skill 是否符合 agentskills.io 规范
    print("\n=== 1.2 Validate ===")
    issues = manager.validate("pdf")
    print("pdf validation:", "PASS" if not issues else issues)

    # 1.3 激活 Skill（Phase 2：加载完整 SKILL.md 指令）
    print("\n=== 1.3 Activate (Phase 2) ===")
    content = manager.activate("pdf")
    preview = content.instructions.splitlines()[:3]
    print("instructions preview:")
    for line in preview:
        print(f"  {line}")
    print(f"  ... ({len(content.instructions)} chars total)")

    # 1.4 列出资源目录（Phase 3：按需访问 scripts / references）
    print("\n=== 1.4 List Resources (Phase 3) ===")
    print(manager.list_resources("pdf").to_display())

    # 1.5 读取资源文件
    print("\n=== 1.5 Read Resource ===")
    script = manager.read_resource("pdf", "scripts/check_fillable_fields.py")
    print(f"resource_type: {script.resource_type}")
    print(f"first line: {script.content.splitlines()[0]}")

    # 1.6 Prompt 生成预览
    print("\n=== 1.6 Prompt Generation ===")
    print("--- XML format ---")
    print(manager.to_prompt(format="xml"))
    print("\n--- System Instruction (truncated) ---")
    instruction = manager.to_system_instruction()
    print(instruction[:300] + "...")


# ─── Section 2: SkillAgent 完整运行（需要 LLM） ─────────────────────

async def section_2_skill_agent_run() -> None:
    """演示 SkillAgent 的完整运行：自动发现 Skill、LLM 按需激活、工具调用循环。"""

    if not os.getenv("LLM_API_KEY") or not os.getenv("LLM_BASE_URL") or not os.getenv("DEFAULT_LLM"):
        print("\n[Skip Section 2] Missing LLM env vars (LLM_API_KEY, LLM_BASE_URL, DEFAULT_LLM).")
        return

    from alphora.agent import SkillAgent
    from alphora.models import OpenAILike
    from alphora.sandbox import Sandbox

    skill_search_path = Path(__file__).parent / "skill_example"

    print("\n=== 2.1 SkillAgent + run() ===")
    async with Sandbox(runtime="local") as sandbox:
        agent = SkillAgent(
            llm=OpenAILike(),
            skill_paths=[skill_search_path],
            sandbox=sandbox,
            system_prompt="你是一个文档处理助手，可以使用 Skills 完成 PDF 相关任务。",
            max_iterations=10,
        )

        print("registered tools:", [t.name for t in agent.tools])
        print("available skills:", agent.skills)

        result = await agent.run("请告诉我如何使用 Python 合并多个 PDF 文件？")
        print("\nAgent result:")
        print(result[:500])

    print("\n=== 2.2 SkillAgent + run_steps() ===")
    async with Sandbox(runtime="local") as sandbox:
        agent = SkillAgent(
            llm=OpenAILike(),
            skill_paths=[skill_search_path],
            sandbox=sandbox,
            max_iterations=10,
        )

        async for step in agent.run_steps("用 pypdf 拆分一个 PDF 的代码怎么写？"):
            print(f"  step {step.iteration}: action={step.action}, final={step.is_final}")
            if step.activated_skills:
                print(f"    activated_skills: {step.activated_skills}")
            if step.is_final:
                print(f"    result: {step.content[:200]}...")


async def main() -> None:
    section_1_skill_manager_basics()
    await section_2_skill_agent_run()


if __name__ == "__main__":
    asyncio.run(main())
