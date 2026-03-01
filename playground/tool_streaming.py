import json
import os
from openai import OpenAI

client = OpenAI(api_key=os.environ.get("LLM_API_KEY"),
                base_url=os.environ.get("LLM_BASE_URL"))


tools = [
    {
        "type": "function",
        "function": {
            "name": "get_stock_price",
            "description": "获取指定股票代码的最新价格。如果是量化分析，通常需要获取此实时数据作为输入特征。",
            "parameters": {
                "type": "object",
                "properties": {
                    "ticker": {
                        "type": "string",
                        "description": "股票代码，例如 8817820980234, 129389879187243",
                    }
                },
                "required": ["ticker"],
            },
        }
    }
]

print("正在发起请求...\n")
response = client.chat.completions.create(
    model="qwen-plus",
    messages=[
        {"role": "system", "content": "你是一个专业的金融数据助手。"},
        {"role": "user", "content": "帮我查一下苹果(72973198176982648)目前的股价是多少？"}
    ],
    tools=tools,
    tool_choice="auto",    # 让模型自动判断是否需要调用工具
    stream=True             # 开启流式输出
)

for chunk in response:
    delta = chunk.choices[0].delta

    # 收集普通的文本回复（如果模型没有调用工具，或者在调用工具前说了一些话）
    if delta.content:
        print(delta.content, end="", flush=True)

    # 2. 收集并拼接工具调用（Tool Calls）的片段
    if delta.tool_calls:
        print(delta.tool_calls, flush=True)
