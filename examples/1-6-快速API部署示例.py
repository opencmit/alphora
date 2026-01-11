from typing import List
import json
from functools import reduce
from alphora.agent.base_agent import BaseAgent
from alphora.models.llms.openai_like import OpenAILike
from alphora.server.openai_request_body import OpenAIRequest
from alphora.postprocess.json_key_extractor import JsonKeyExtractorPP
from alphora.postprocess.replace import ReplacePP

llm_api_key: str = 'sk-xxx'
llm_base_url: str = "https://dashscope.aliyuncs.com/compatible-mode/v1"

llm1 = OpenAILike(api_key=llm_api_key, base_url=llm_base_url, model_name='qwen-plus', max_tokens=8000)
llm2 = OpenAILike(api_key=llm_api_key, base_url=llm_base_url, model_name='qwen-max', max_tokens=8000)

llm = llm1 + llm2  # 特性1：支持多模型负载均衡，并且支持自动根据消息类型调用不同模型

# 特性：支持Jinja语法，动态Prompt
PROMPT_GUIDE = """你是一个专业的导游，请用专业的态度和中文回复旅客的问题。在每次回答之前，请你先思考一段再回复。
请你按照以下Json格式输出:
{
    "thinking": "<你对于游客的问题的思考>",
    "response": "<你给游客的回复>"
}
---
{% if history %}
历史对话: 
{{ history }} 
{% endif %}

当前所在城市:
{{ city }}

天气情况:
{{ weather }}

游客:
{{ query }}
"""

PROMPT_TRANS = """你是一个专业的翻译家，请将以下内容翻译为 {{ target_lang }}。
{{ content }}
请你翻译
"""


class TransAgent(BaseAgent):
    async def translate(self, content: str, target_langs: List[str]) -> None:
        # 多语言同时翻译
        prompter = reduce(lambda a, b: a | b,
                          (self.create_prompt(PROMPT_TRANS, content_type=lang).update_placeholder(target_lang=lang, content=content)
                           for lang in target_langs))

        _ = await prompter.acall(is_stream=True, force_json=False)
        return


class WeatherTool(BaseAgent):
    async def get_weather(self, city: str) -> str:
        # 这里模仿查询天气的结果，实际调用工具
        await self.stream.astream_message(content=f'稍等，正在为您查询{city}的天气状况', content_type='status',
                                          interval=0.01)  # 特性2: 支持自定义向接口输出任意内容
        weather = f"{city}的天气是26摄氏度，晴天"
        await self.stream.astream_message(content=weather, content_type='tool', interval=0.01)  # 特性2: 支持自定义向接口输出任意内容
        return weather


class MyAgent(BaseAgent):

    async def guide(self, query: str, city: str) -> None:
        # 派生2个智能体
        trans_agent = self.derive(TransAgent)
        weather_agent = self.derive(WeatherTool)

        # 首先查询天气
        weather = await weather_agent.get_weather(city=city)

        json_pp = JsonKeyExtractorPP(target_key='thinking')  # 这里创建的后处理器，只会输出大模型输出Json中的response部分
        # replace_pp = ReplacePP(replace_map={'北京': '******'})  # 这里假设有若干敏感词，也会在API接口中被替换、屏蔽

        history = self.memory.build_history()  # 构建历史对话

        prompter = self.create_prompt(prompt=PROMPT_GUIDE)  # 创建prompter
        prompter.update_placeholder(history=history, city=city, weather=weather)  # 更新占位符

        guide_resp = await prompter.acall(query=query,
                                          is_stream=True,  # 指定流式输出
                                          force_json=True,  # 可以强制输出Json
                                          postprocessor=json_pp)  # 后处理器

        print('debug', guide_resp)
        self.memory.add_memory(role='游客', content=query)
        self.memory.add_memory(role='导游', content=guide_resp)

        # 因为指定了强制Json，所以解析得到回复内容
        resp_str = json.loads(guide_resp).get('response', '')

        # 然后翻译，并行翻译
        await trans_agent.translate(content=resp_str, target_langs=['en', 'jp', 'es', 'ko'])

        # 结束
        await self.stream.astop(stop_reason=f'end')

    async def api_logic(self, request: OpenAIRequest):
        query = request.get_user_query()
        await self.guide(query=query, city='北京')


if __name__ == '__main__':
    import uvicorn
    from alphora.server.quick_api import publish_agent_api, APIPublisherConfig

    agent = MyAgent(llm=llm)

    # 发布 API（传入 Agent 类 + 初始化参数）的配置信息
    config = APIPublisherConfig(
        memory_ttl=7200,  # 2小时
        max_memory_items=2000,
        auto_clean_interval=300,  # 5分钟
        api_title="{agent_name} API Service",
        api_description="Auto-generated API for {agent_name} (method: {method_name})"
    )

    # 发布API
    app = publish_agent_api(
        agent=agent,
        method="api_logic",
        config=config
    )

    uvicorn.run(app, host="0.0.0.0", port=8002)
