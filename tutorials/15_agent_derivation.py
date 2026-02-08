"""
Tutorial 15: Agent derivation and shared context.

Run:
  python tutorials/15_agent_derivation.py
"""

from alphora.agent import BaseAgent
from alphora.memory import MemoryManager


class TagAgent(BaseAgent):
    def __init__(self, tag: str, **kwargs):
        super().__init__(**kwargs)
        self.tag = tag
        self.local_only = "keep_me"

    def describe(self) -> str:
        return f"TagAgent(tag={self.tag})"


def main() -> None:
    memory = MemoryManager()
    parent = BaseAgent(memory=memory, config={"project": "alphora-demo"})

    child_a = parent.derive(TagAgent, tag="research")
    child_b = parent.derive(TagAgent, tag="analysis")

    # Derive from an instance (keeps instance-specific attributes)
    custom = TagAgent(tag="custom")
    custom.local_only = "local_state"
    child_c = parent.derive(custom)

    parent.memory.add_user("Shared memory works.")

    print(child_a.describe(), "config:", child_a.config)
    print(child_b.describe(), "config:", child_b.config)
    print(child_c.describe(), "local_only:", child_c.local_only)
    print("Memory shared:", child_a.memory is parent.memory, child_b.memory is parent.memory)
    print("History count:", parent.memory.build_history().message_count)


if __name__ == "__main__":
    main()
