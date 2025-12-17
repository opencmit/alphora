from alphora.agent.base import BaseAgent
from alphora.models.llms.openai_like import OpenAILike
from alphora.server.stream_responser import DataStreamer
import asyncio

llm_api_key: str = 'sk-68ac5f5ccf3540ba834deeeaecb48987'
llm_base_url: str = "https://dashscope.aliyuncs.com/compatible-mode/v1"
llm_model_name: str = "qwen-plus"


llm = OpenAILike(api_key=llm_api_key, base_url=llm_base_url, model_name='qwen-plus')


class TransAgent(BaseAgent):
    async def translate(self, query, target_lang):
        prompt = self.create_prompt(prompt="你是一个翻译官:{{ query }}，将翻译到{{ target_lang }}")
        prompt.update_placeholder(target_lang=target_lang)
        _ = await prompt.acall(query=query, is_stream=True, force_json=False)


class GuideAgent(BaseAgent):
    async def execute(self, query):
        trans_agent = self.derive(TransAgent)  # 派生出一个智能体
        prompt = self.create_prompt(prompt="你是一个导游，目前正在带领一个美国旅行团，游客说:{{query}}，你用中文回答")
        _ = await prompt.acall(query=query, is_stream=True, force_json=False)
        _ = await trans_agent.translate(query=query, target_lang='en')
        await self.stream.astop(stop_reason='111')


# ====================

from fastapi import FastAPI

app = FastAPI()

@app.get("/stream")
async def stream():
    streamer = DataStreamer(timeout=30)  # 30秒超时
    agent = GuideAgent(llm=llm, callback=streamer)

    # 启动智能体
    asyncio.create_task(agent.execute(query='介绍下故宫'))

    # 阻塞式输出
    # return await streamer.start_non_streaming_openai()
    # 流式输出
    return streamer.start_streaming_openai()


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)