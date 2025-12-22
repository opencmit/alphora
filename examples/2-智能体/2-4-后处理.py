from typing import Dict

from alphora.agent.base import BaseAgent
# from alphora.agent.models import AgentInput, AgentOutput
from alphora.models.llms.openai_like import OpenAILike
from alphora.server.stream_responser import DataStreamer
import asyncio

from alphora.prompter.postprocess.json_key_extractor import JsonKeyExtractorPP

from alphora.server.openai_request_body import OpenAIRequest

llm_api_key: str = 'sk-68ac5f5ccf3540ba834deeeaecb48987'
llm_base_url: str = "https://dashscope.aliyuncs.com/compatible-mode/v1"
llm_model_name: str = "qwen-plus"


llm = OpenAILike(api_key=llm_api_key, base_url=llm_base_url, model_name='qwen-plus')


class TeacherAgent(BaseAgent):

    async def teacher(self, query):

        json_pp = JsonKeyExtractorPP(target_key='thinking')

        prompt = self.create_prompt(prompt="你是一个高中数学老师，目前正在回复学生的问题，请你准确的回复学生的问题，并且在回复之前先思考，输出格式需要是Json，包含 'thinking', 'response'这两个key。\n\n学生说:{{query}}")

        print(prompt.render())
        teacher_resp = await prompt.acall(query=query, is_stream=True, force_json=True, postprocessor=json_pp)
        print(teacher_resp)

        await self.stream.astop(stop_reason='111')

    async def api_logic(self, request: OpenAIRequest):
        query = request.get_user_query()
        await self.teacher(query)


if __name__ == '__main__':
    import uvicorn
    app = TeacherAgent(llm=llm).to_api(method='api_logic')
    uvicorn.run(app, host="0.0.0.0", port=8000)
