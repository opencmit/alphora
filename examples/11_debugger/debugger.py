"""
Alphora Debugger 使用示例
"""

import asyncio
import os
from alphora.agent import BaseAgent
from alphora.debugger import tracer


class TransAgent(BaseAgent):
    async def run(self, query: str):
        prompt = self.create_prompt(
            prompt="你是一个翻译专家，负责把用户问题翻译为{{target_lang}}，用户:{{query}}"
        )

        prompt.update_placeholder(target_lang="en")
        return await prompt.acall(query=query, is_stream=True)


class MyAgent(BaseAgent):
    async def run(self, query: str):
        prompt = self.create_prompt(
            system_prompt="你是一个{{personality}}助手",
            enable_memory=True
        )

        prompt.update_placeholder(personality="友善的")

        resp = await prompt.acall(query=query, is_stream=True)

        trans_agent = self.derive(TransAgent)
        trans_agent2 = self.derive(TransAgent)
        await trans_agent.run(query=resp)
        pass


async def main(query: str):
    """
    主函数，演示智能体的基本使用
    """
    from alphora.models import OpenAILike
    llm_api_key: str = "sk-68ac5f5ccf3540ba834deeeaecb48987"  # 替换为您的API密钥
    llm_base_url: str = "https://dashscope.aliyuncs.com/compatible-mode/v1"  # 通义千问兼容OpenAI的API地址
    llm_model_name: str = "qwen-plus"

    # 初始化LLM模型
    llm = OpenAILike(
        api_key=llm_api_key,
        base_url=llm_base_url,
        model_name=llm_model_name,
        max_tokens=8000
    )

    # 初始化智能体
    bot = MyAgent(llm=llm, verbose=True, debugger=True)
    await bot.run(query)
    print('111')


if __name__ == '__main__':
    import asyncio
    asyncio.run(main(query='我叫啥'))
