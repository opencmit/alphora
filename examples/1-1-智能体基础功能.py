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
        response = await prompt.acall(query=query, is_stream=True, long_response=True)
        
        return response


async def main():
    """
    主函数，演示智能体的基本使用
    """
    # 初始化智能体
    agent = SimpleAgent(llm=llm, verbose=True)
    
    # 测试对话
    user_queries = [
        """**目标**：我需要你写一本《现代通信详细知识结构》的书，对"现代通信"进行微米级的知识解构。

**执行策略**：
你不仅仅是在写书，你是在对通信技术进行"逆向工程"。对于你提到的每一个名词（例如"光纤"），你都要立刻展开它的：
1.  材料物理特性（能级结构、折射率公式）。
2.  制造工艺流程（化学气相沉积的具体步骤）。
3.  数学传输模型（非线性薛定谔方程的完整解）。
4.  工程损耗计算。

**注意**：
- 请先列出这本书的详细目录
- 哪怕是解释"电荷"这个概念，也要详尽的介绍。
- 永远不要试图总结，永远不要试图转场到下一章，除非当前概念已经解释得无法再详细为止。
- 忽略时间，忽略篇幅，像一台永不停歇的打字机一样输出。

开始："""
           ]
    
    for query in user_queries:
        print(f"用户：{query}")
        response = await agent.chat(query)
        print(f"智能助手：{response}\n")

    return response

if __name__ == "__main__":
    import asyncio
    # 运行异步主函数
    resp = asyncio.run(main())