"""
Alphora API Mock 示例

启动：
    python mock.py

前端联调：
    Endpoint: /v1/chat/completions
"""

import asyncio
import uvicorn
from alphora.server.quick_api import publish_agent_api, APIPublisherConfig
from alphora.models.llms import OpenAILike
from alphora.server.openai_request_body import OpenAIRequest
from alphora.agent import BaseAgent


class MockAgent(BaseAgent):

    async def start(self, request: OpenAIRequest):
        query = request.get_user_query()

        prompter = self.create_prompt(system_prompt="你是Alphora，一个由中国移动数智化部开发的AI智能体")

        await prompter.acall(query=query,
                             is_stream=True)

        await self.stream.astop()

        pass


llm = OpenAILike(
    max_tokens=8000
)


agent = MockAgent(llm=llm)


# API发布配置信息
config = APIPublisherConfig(
    path='/v1',
)

# 4. 发布 API
app = publish_agent_api(
    agent=agent,
    method="start",
    config=config
)


if __name__ == "__main__":
    uvicorn.run(
        app,
        host='127.0.0.1',
        port=8000
    )

