"""
Tutorial 09: Multimodal Message (text + image) and OpenAI format.

Run:
  python tutorials/09_multimodal_message.py
"""

import asyncio
import os

from alphora.models import OpenAILike
from alphora.models.message import Message


async def main() -> None:
    if not os.getenv("LLM_API_KEY") or not os.getenv("LLM_BASE_URL") or not os.getenv("DEFAULT_LLM"):
        print("Missing env vars. Please set LLM_API_KEY, LLM_BASE_URL, DEFAULT_LLM.")
        return

    # 1x1 transparent PNG (base64)
    tiny_png = (
        "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR4nGNgYAAAAAMA"
        "ASsJTYQAAAAASUVORK5CYII="
    )

    msg = Message()
    msg.add_text("What is in this image? Answer briefly.")
    msg.add_image(tiny_png, format="png")

    print("=== OpenAI Format Preview ===")
    print(msg.to_openai_format(role="user"))

    # is_multimodal=True will route to a multimodal-capable backend
    llm = OpenAILike(is_multimodal=True)
    result = await llm.ainvoke(msg)

    print("=== LLM Result ===")
    print(result)


if __name__ == "__main__":
    asyncio.run(main())
