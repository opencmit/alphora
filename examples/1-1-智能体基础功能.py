from alphora.agent.base import BaseAgent
from alphora.models.llms.openai_like import OpenAILike

# 配置LLM（使用阿里云通义千问作为示例）
llm_api_key: str = 'sk-xxx'  # 替换为您的API密钥
llm_base_url: str = "https://dashscope.aliyuncs.com/compatible-mode/v1"  # 通义千问兼容OpenAI的API地址
llm_model_name: str = "qwen-plus"

# 初始化LLM模型
llm = OpenAILike(
    api_key=llm_api_key,
    base_url=llm_base_url,
    model_name=llm_model_name
)


# 创建基础智能体
class SimpleAgent(BaseAgent):
    """
    简单的智能体示例，展示智能体的基本功能
    """
    async def chat(self, query: str) -> str:
        """
        处理用户查询的主要方法
        Args:
            query: 用户的查询内容
        Returns:
            智能体的回复
        """
        # 创建简单的提示词
        prompt = self.create_prompt(
            prompt="你是一个友好的智能助手，请用中文简洁地回答用户的问题。\n\n用户：{{query}}"
        )
        
        # 调用LLM获取回复
        response = await prompt.acall(query=query, is_stream=False)
        
        return response


async def main():
    """
    主函数，演示智能体的基本使用
    """
    # 初始化智能体
    agent = SimpleAgent(llm=llm, verbose=True)
    
    # 测试对话
    user_queries = [
        "什么是人工智能？",
        "请解释机器学习的基本概念",
        "AI有哪些应用领域？"
    ]
    
    for query in user_queries:
        print(f"用户：{query}")
        response = await agent.chat(query)
        print(f"智能助手：{response}\n")

if __name__ == "__main__":
    import asyncio
    # 运行异步主函数
    asyncio.run(main())