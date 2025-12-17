from alphora.agent.base import BaseAgent
from alphora.models.llms.openai_like import OpenAILike
from alphora.server.stream_responser import DataStreamer
import asyncio
import time

llm_api_key: str = 'sk-68ac5f5ccf3540ba834deeeaecb48987'
llm_base_url: str = "https://dashscope.aliyuncs.com/compatible-mode/v1"
llm_model_name: str = "qwen-plus"


llm = OpenAILike(api_key=llm_api_key, base_url=llm_base_url, model_name='qwen-plus')


class Agent(BaseAgent):
    async def execute(self):
        prompt1 = "你是一个翻译官:{{ query }}，将翻译到{{ target_lang }}"
        prompt = self.create_prompt(prompt=prompt1)
        prompt.update_placeholder(target_lang='en')
        result = await prompt.acall(query='你好,中国移动是中国创办的一家中央企业', is_stream=True, force_json=True)

        self.stream.stream_message(content='aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa')
        pass


# ====================

from fastapi import FastAPI

app = FastAPI()

@app.get("/stream")
async def stream():
    streamer = DataStreamer(timeout=30)  # 30秒超时
    agent = Agent(llm=llm, callback=streamer)

    # 启动智能体
    asyncio.create_task(agent.execute())

    return streamer.start_non_streaming_openai()

    return streamer.start_streaming_openai()

import uvicorn


if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)