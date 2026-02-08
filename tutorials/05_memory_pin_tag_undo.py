"""
Tutorial 05: Pin/Tag + apply/remove/inject + processors + undo/redo.

Run:
  python tutorials/05_memory_pin_tag_undo.py
"""

from alphora.memory import MemoryManager
from alphora.memory.processors import (
    chain,
    exclude_roles,
    keep_last,
    keep_rounds,
    keep_roles,
    keep_pinned,
    keep_tagged,
    keep_important_and_last,
    summarize_tool_calls,
    remove_tool_details,
    keep_final_tool_result,
    token_budget,
)


def rough_tokenizer(text: str) -> int:
    # Simple tokenizer for demo: 1 token ~= 4 chars
    return max(1, len(text) // 4)


def main() -> None:
    memory = MemoryManager(enable_undo=True)

    m1 = memory.add_user("I like coffee.")
    memory.add_assistant("Noted. You like coffee.")
    m3 = memory.add_user("My favorite city is Shanghai.")
    memory.add_assistant("Got it. Favorite city: Shanghai.")

    # Pin and tag
    memory.pin(m1.id)
    memory.tag("profile", lambda m: "favorite" in (m.content or "").lower())

    # Inject a system hint before last user
    memory.inject("System hint: keep answers short.", position="before_last_user")

    # Apply and remove
    memory.apply(
        fn=lambda m: m.with_content(m.content[:20] + "..."),
        predicate=lambda m: (m.content or "").startswith("Got it"),
    )
    memory.remove(lambda m: (m.content or "").startswith("Noted"))

    # Build history with processors
    processor = chain(
        exclude_roles("system"),
        keep_roles("user", "assistant", "tool"),
        summarize_tool_calls(),
        remove_tool_details(),
        keep_final_tool_result(),
        keep_rounds(3),
        keep_pinned(),
        keep_tagged("profile"),
        keep_important_and_last(6),
        keep_last(6),
        token_budget(max_tokens=120, tokenizer=rough_tokenizer, reserve_for_response=20),
    )
    history = memory.build_history(keep_pinned=True, keep_tagged=["profile"], processor=processor)

    print("=== Processed History ===")
    for msg in history.messages:
        print(msg)

    # Undo/redo
    ok = memory.undo()
    print("\nUndo:", ok)
    ok = memory.redo()
    print("Redo:", ok)


if __name__ == "__main__":
    main()
