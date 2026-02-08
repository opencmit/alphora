"""
Tutorial 11: Streaming output from LLM (content types + thinking).

Run:
  python tutorials/11_streaming_output.py
"""

import os

from alphora.models import OpenAILike
from alphora.agent import BaseAgent


def main() -> None:
    if not os.getenv("LLM_API_KEY") or not os.getenv("LLM_BASE_URL") or not os.getenv("DEFAULT_LLM"):
        print("Missing env vars. Please set LLM_API_KEY, LLM_BASE_URL, DEFAULT_LLM.")
        return

    llm = OpenAILike()
    gen = llm.get_streaming_response(
        "Explain Alphora in 2 sentences.",
        content_type="char",
        enable_thinking=True,
    )

    print("=== Streaming ===")
    for chunk in gen:
        print(f"[{chunk.content_type}]{chunk.content}", end="", flush=True)
    print()

    # Stream passthrough (BaseAgent.afetch_stream)
    # Requires an external SSE endpoint; set EXTERNAL_STREAM_URL to enable.
    url = os.getenv("EXTERNAL_STREAM_URL")
    if url:
        agent = BaseAgent(llm=llm)
        payload = {
            "model": os.getenv("DEFAULT_LLM"),
            "messages": [{"role": "user", "content": "Hello"}],
            "stream": True,
        }
        print("\n=== Passthrough Streaming ===")
        # This will forward SSE chunks to agent.stream and return full content
        import asyncio
        asyncio.run(agent.afetch_stream(url=url, payload=payload))


if __name__ == "__main__":
    main()
