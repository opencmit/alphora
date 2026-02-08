"""
Tutorial 06: Jinja2 templates + runtime system prompts + force_json.

Run:
  python tutorials/06_prompter_templates.py
"""

import os

from alphora.prompter import BasePrompt
from alphora.models import OpenAILike
from alphora.tools import tool
from alphora.postprocess.replace import ReplacePP
from alphora.postprocess.filter import FilterPP


def main() -> None:
    prompt = BasePrompt(
        system_prompt="You are {{role}}. Be concise.",
        user_prompt="Hello {{name}}. Task: {{query}}",
    )

    prompt.update_placeholder(role="a helpful assistant", name="Alice")
    print("=== Placeholders ===")
    print(prompt.placeholders)

    messages = prompt.build_messages(
        query="Summarize Alphora in one sentence.",
        runtime_system_prompt="Use simple words.",
    )

    print("\n=== Rendered Messages ===")
    for msg in messages:
        print(msg)

    if not os.getenv("LLM_API_KEY") or not os.getenv("LLM_BASE_URL") or not os.getenv("DEFAULT_LLM"):
        print("\nSkip LLM call (missing env vars).")
        return

    llm = OpenAILike()
    prompt.add_llm(llm)
    result = prompt.call(
        query="Summarize Alphora in one sentence as JSON with keys: summary, audience.",
        force_json=True,
        runtime_system_prompt="Return valid JSON only.",
    )
    print("\n=== LLM Result (force_json) ===")
    print(result)

    # Tool calling + streaming + postprocessor
    @tool
    def add(a: int, b: int) -> int:
        """Add two numbers."""
        return a + b

    tools = [add.openai_schema]
    pp = ReplacePP({"Alphora": "ALPHORA"}) >> FilterPP(filter_chars="!")

    print("\n=== Streaming + postprocessor + tools ===")
    resp = prompt.call(
        query="Compute 2+3, then mention Alphora!",
        is_stream=True,
        tools=tools,
        postprocessor=pp,
        long_response=False,
        enable_thinking=True,
    )
    # If tools were called, resp is ToolCall; otherwise PrompterOutput
    print("\n\nResponse type:", type(resp))

    print("\n=== long_response (may trigger continuation) ===")
    _ = prompt.call(
        query="Write a long explanation about Alphora.",
        is_stream=True,
        long_response=True,
    )


if __name__ == "__main__":
    main()
