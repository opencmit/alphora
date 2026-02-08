"""
Tutorial 10: LLM load balancing + Qwen/DeepSeek specifics.

Run:
  python tutorials/10_llm_load_balancer.py
"""

import asyncio
import os

from alphora.models import OpenAILike, Qwen
from alphora.models.llms.deepseek.dpsk import DeepSeek


async def main() -> None:
    if not os.getenv("LLM_API_KEY") or not os.getenv("LLM_BASE_URL") or not os.getenv("DEFAULT_LLM"):
        print("Missing env vars. Please set LLM_API_KEY, LLM_BASE_URL, DEFAULT_LLM.")
        return

    llm1 = OpenAILike(
        api_key=os.getenv("LLM_API_KEY"),
        base_url=os.getenv("LLM_BASE_URL"),
        model_name=os.getenv("DEFAULT_LLM"),
    )

    # Optional backup endpoint (fallback to primary if not provided)
    llm2 = OpenAILike(
        api_key=os.getenv("LLM_API_KEY_2") or os.getenv("LLM_API_KEY"),
        base_url=os.getenv("LLM_BASE_URL_2") or os.getenv("LLM_BASE_URL"),
        model_name=os.getenv("DEFAULT_LLM_2") or os.getenv("DEFAULT_LLM"),
    )

    llm = llm1 + llm2

    print("=== Two calls to show round-robin ===")
    r1 = await llm.ainvoke("Say hello in one short sentence.")
    r2 = await llm.ainvoke("Say hello again, slightly different.")

    print("Result 1:", r1)
    print("Result 2:", r2)

    # Optional: Qwen / DeepSeek wrappers (OpenAI-compatible)
    qwen_model = os.getenv("QWEN_MODEL")
    if qwen_model:
        qwen = Qwen(model_name=qwen_model, api_key=os.getenv("LLM_API_KEY"))
        qwen_resp = await qwen.ainvoke("Hello from Qwen.")
        print("Qwen:", qwen_resp)

        # Qwen3 thinking mode (only for qwen3-* and non-jz models)
        gen = qwen.get_streaming_response(
            "Explain briefly with thinking.",
            enable_thinking=True,
        )
        for chunk in gen:
            print(f"[qwen/{chunk.content_type}] {chunk.content}", end="")
        print()

    deepseek_model = os.getenv("DEEPSEEK_MODEL")
    if deepseek_model:
        dpsk = DeepSeek(model_name=deepseek_model, api_key=os.getenv("LLM_API_KEY"))
        dpsk_resp = await dpsk.ainvoke("Hello from DeepSeek.")
        print("DeepSeek:", dpsk_resp)


if __name__ == "__main__":
    asyncio.run(main())
