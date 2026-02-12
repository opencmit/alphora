"""
Tutorial 16: SkillAgent + SkillManager + Skills 组件（工具化）。

Run:
  python tutorials/16_skill_agent_basic.py
"""

import asyncio
import os
from pathlib import Path

from alphora.agent import SkillAgent
from alphora.models import OpenAILike
from alphora.skills import SkillManager, create_skill_tools, create_filesystem_skill_tools

from alphora.sandbox import Sandbox

from alphora_community.tools import ArxivSearchTool
from alphora_community.tools import WebBrowser
from alphora_community.tools import FileViewer

from alphora.hooks import HookEvent
from alphora.hooks.builtins import log_tool_execution


async def main() -> None:
    repo_root = Path(__file__).resolve().parents[1]
    community_skills = repo_root / "alphora_community" / "skills"
    skill_name = "deep-research"

    manager = SkillManager([community_skills])
    manager.discover()

    print("=== Discovered Skills ===")
    print(manager.skill_names)

    print("\n=== Prompt Injection Preview ===")
    print(manager.to_prompt(format="xml"))

    print("\n=== System Instruction Preview ===")
    print(manager.to_system_instruction(format="xml"))

    print("\n=== Validate Skill ===")
    print(manager.validate(skill_name) or "ok")

    print("\n=== Activate Skill (progressive disclosure) ===")
    content = manager.activate(skill_name)
    print(content.instructions.splitlines()[0])

    print("\n=== List Resources ===")
    print(manager.list_resources(skill_name).to_display())

    print("\n=== Read Resource ===")
    ref = manager.read_resource(skill_name, "references/QUESTION_FRAMEWORK.md")
    print(ref.content.splitlines()[0])

    print("\n=== Skills 组件：Tool 模式 ===")
    skill_tools = create_skill_tools(manager)
    print([tool.name for tool in skill_tools])

    print("\n=== Skills 组件：Filesystem 模式 ===")
    fs_tools = create_filesystem_skill_tools(manager)
    print([tool.name for tool in fs_tools])

    if not os.getenv("LLM_API_KEY") or not os.getenv("LLM_BASE_URL") or not os.getenv("DEFAULT_LLM"):
        print("\nSkip SkillAgent run (missing env vars).")
        return

    sandbox = Sandbox(runtime="docker")

    await sandbox.start()

    arxiv_search = ArxivSearchTool()
    web_browser = WebBrowser()
    file_viewer = FileViewer(sandbox=sandbox)

    agent = SkillAgent(
        llm=OpenAILike(),
        tools=[arxiv_search.arxiv_search,
               web_browser.fetch_url,
               file_viewer.view_file],
        hooks={
            HookEvent.TOOLS_AFTER_EXECUTE: log_tool_execution(include_args=True, include_result=True),
        },
        sandbox=sandbox,
        skill_paths=[community_skills],
        system_prompt="You can use skills if helpful.",
        max_iterations=20,
    )

    result = await agent.run("研究一下NL2SQL领域最新进展")
    print("\n=== SkillAgent Result ===")
    print(result)


if __name__ == "__main__":
    asyncio.run(main())
