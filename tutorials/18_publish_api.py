"""
Tutorial 18: Publish agent as OpenAI-compatible API.

Run:
  python tutorials/18_publish_api.py
"""

import os

from alphora.agent import BaseAgent
from alphora.models import OpenAILike
from alphora.server.quick_api import publish_agent_api, APIPublisherConfig
from alphora.server.openai_request_body import OpenAIRequest


class MyAgent(BaseAgent):
    async def run(self, request: OpenAIRequest):
        query = request.get_user_query() or ""
        session_id = request.session_id or "default"

        if not self.llm:
            await self.stream.send("text", "LLM not configured.")
            await self.stream.stop()
            return

        if request.stream:
            await self.stream.send("thinking", f"session={session_id}")

        prompt = self.create_prompt(
            system_prompt="You are a helpful assistant.",
            user_prompt="{{query}}",
        )
        result = await prompt.acall(query=query)

        await self.stream.send("text", str(result))
        await self.stream.stop()


def build_agent() -> MyAgent:
    if not os.getenv("LLM_API_KEY") or not os.getenv("LLM_BASE_URL") or not os.getenv("DEFAULT_LLM"):
        return MyAgent(llm=None)

    llm = OpenAILike()
    return MyAgent(llm=llm)


agent = build_agent()
config = APIPublisherConfig(
    path="/chat",
    api_title="Alphora Agent API",
    api_description="OpenAI-compatible API for MyAgent",
)

app = publish_agent_api(agent=agent, method="run", config=config)


if __name__ == "__main__":
    try:
        import uvicorn
    except ImportError:
        print("uvicorn is not installed. Run: pip install uvicorn fastapi")
    else:
        uvicorn.run(app, host="0.0.0.0", port=8000)
