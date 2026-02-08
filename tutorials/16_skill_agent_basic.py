"""
Tutorial 16: SkillAgent + SkillManager (discover/activate/resources/validate).

Run:
  python tutorials/16_skill_agent_basic.py
"""

import asyncio
import os
import tempfile
from pathlib import Path

from alphora.agent import SkillAgent
from alphora.models import OpenAILike
from alphora.skills import SkillManager


def create_demo_skill(root: Path) -> Path:
    skill_dir = root / "hello-skill"
    skill_dir.mkdir(parents=True, exist_ok=True)
    skill_md = skill_dir / "SKILL.md"
    (skill_dir / "references").mkdir(parents=True, exist_ok=True)
    (skill_dir / "references" / "REFERENCE.md").write_text(
        "# Reference\nUse this to greet politely."
    )

    skill_md.write_text(
        "---\n"
        "name: hello-skill\n"
        "description: Say hello and explain what you can do.\n"
        "license: Apache-2.0\n"
        "metadata:\n"
        "  author: demo\n"
        "  version: \"1.0\"\n"
        "---\n\n"
        "# Hello Skill\n"
        "Use this skill when the user asks for a greeting.\n"
    )
    return skill_dir


async def main() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        create_demo_skill(root)

        manager = SkillManager([root])
        manager.discover()

        print("=== Discovered Skills ===")
        print(manager.skill_names)

        print("\n=== Prompt Injection Preview ===")
        print(manager.to_prompt(format="xml"))

        print("\n=== System Instruction Preview ===")
        print(manager.to_system_instruction(format="xml"))

        print("\n=== Validate Skills ===")
        print(manager.validate("hello-skill") or "ok")

        print("\n=== Activate Skill (progressive disclosure) ===")
        content = manager.activate("hello-skill")
        print(content.instructions[:60] + "...")

        print("\n=== Read Resource ===")
        ref = manager.read_resource("hello-skill", "references/REFERENCE.md")
        print(ref.content)

        if not os.getenv("LLM_API_KEY") or not os.getenv("LLM_BASE_URL") or not os.getenv("DEFAULT_LLM"):
            print("\nSkip SkillAgent run (missing env vars).")
            return

        agent = SkillAgent(
            llm=OpenAILike(),
            skill_paths=[root],
            system_prompt="You can use skills if helpful.",
            max_iterations=20,
        )

        # Filesystem mode: return paths to LLM (useful with sandbox tools)
        fs_agent = SkillAgent(
            llm=OpenAILike(),
            skill_paths=[root],
            filesystem_mode=True,
            system_prompt="You can read skills by path if needed.",
            max_iterations=5,
        )

        result = await agent.run("Say hello and mention your main capabilities.")
        print("\n=== SkillAgent Result ===")
        print(result)

        fs_result = await fs_agent.run("Say hello using filesystem skills if needed.")
        print("\n=== Filesystem Mode Result ===")
        print(fs_result)


if __name__ == "__main__":
    asyncio.run(main())
