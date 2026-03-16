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


async def skill_agent_run() -> None:
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

        result = await agent.run("帮我把图片提取出来")
        print("\nAgent result:")
        print(result[:500])


async def main() -> None:
    await skill_agent_run()


if __name__ == "__main__":
    asyncio.run(main())
