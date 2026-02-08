"""
Tutorial 04: MemoryManager basics + tool-chain validation.

Run:
  python tutorials/04_memory_basic_history.py
"""

import json

from alphora.memory import MemoryManager
from alphora.memory.history_payload import ToolChainError
from alphora.tools.executor import ToolExecutionResult


def build_valid_tool_chain(memory: MemoryManager, session_id: str) -> None:
    memory.add_user("Search the docs for 'sandbox'.", session_id=session_id)

    tool_calls = [
        {
            "id": "call_1",
            "type": "function",
            "function": {
                "name": "search_docs",
                "arguments": json.dumps({"query": "sandbox"}),
            },
        }
    ]
    memory.add_assistant(tool_calls=tool_calls, session_id=session_id)

    result = ToolExecutionResult(
        tool_call_id="call_1",
        tool_name="search_docs",
        content=json.dumps({"hits": 3}),
    )
    memory.add_tool_result(result, session_id=session_id)

    memory.add_assistant("Found 3 docs about sandbox.", session_id=session_id)


def build_invalid_tool_chain(memory: MemoryManager, session_id: str) -> None:
    memory.add_user("Search the docs for 'memory'.", session_id=session_id)
    tool_calls = [
        {
            "id": "call_99",
            "type": "function",
            "function": {
                "name": "search_docs",
                "arguments": json.dumps({"query": "memory"}),
            },
        }
    ]
    memory.add_assistant(tool_calls=tool_calls, session_id=session_id)
    # Missing tool result on purpose


def main() -> None:
    memory = MemoryManager()

    build_valid_tool_chain(memory, session_id="ok")
    history = memory.build_history(session_id="ok", max_rounds=3)

    print("=== Valid Tool Chain ===")
    print("message_count:", history.message_count)
    print("tool_chain_valid:", history.tool_chain_valid)
    for msg in history.messages:
        print(msg)

    build_invalid_tool_chain(memory, session_id="bad")
    print("\n=== Invalid Tool Chain (expect error) ===")
    try:
        memory.build_history(session_id="bad")
    except ToolChainError as exc:
        print("ToolChainError:", exc)


if __name__ == "__main__":
    main()
