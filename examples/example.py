
from alphora.agent.base_agent import BaseAgent
from alphora.models.llms.openai_like import OpenAILike

# 配置LLM（使用阿里云通义千问作为示例）
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


class MultiRoleBot(BaseAgent):
    async def as_translator(self, text: str, session_id: str):
        prompt = self.create_prompt(
            system_prompt="你是翻译专家",
            enable_memory=True,
            memory_id=session_id
        )
        return await prompt.acall(query=f"翻译：{text}", is_stream=True)

    async def as_teacher(self, topic: str, session_id: str):
        prompt = self.create_prompt(
            system_prompt="你是老师",
            enable_memory=True,
            memory_id=session_id  # 同一个 session，共享历史
        )
        return await prompt.acall(query=f"解释刚才翻译的内容", is_stream=True)


async def main(query: str):
    """
    主函数，演示智能体的基本使用
    """
    # 初始化智能体
    bot = MultiRoleBot(llm=llm, verbose=True)
    await bot.as_translator("今天天气很好", session_id="lesson_001")
    await bot.as_teacher("语法", session_id="lesson_001")  # 能看到翻译历史


if __name__ == '__main__':
    import asyncio
    asyncio.run(main(query='我叫啥'))
