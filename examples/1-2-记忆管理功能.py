from alphora.agent.base import BaseAgent
from alphora.models.llms.openai_like import OpenAILike

# 配置LLM
llm_api_key: str = 'sk-68ac5f5ccf3540ba834deeeaecb48987'  # 替换为您的API密钥
llm_base_url: str = "https://dashscope.aliyuncs.com/compatible-mode/v1"
llm_model_name: str = "qwen-plus"

# 初始化LLM模型
llm = OpenAILike(
    api_key=llm_api_key,
    base_url=llm_base_url,
    model_name=llm_model_name
)


class MemoryAgent(BaseAgent):
    """
    记忆管理功能示例，展示如何使用记忆模块保存和检索对话历史
    """

    async def chat_with_memory(self, query: str) -> str:
        """
        带记忆功能的聊天方法
        Args:
            query: 用户的查询内容
        Returns:
            智能体的回复
        """
        # 构建历史对话
        history = self.memory.build_history(memory_id="default", max_round=5)

        # 创建包含历史对话的提示词
        prompt = self.create_prompt(
            prompt="你是一个友好的智能助手，请根据历史对话和当前问题用中文回答。\n\n" +
                   "历史对话：\n{{history}}\n\n" +
                   "当前问题：{{query}}"
        )

        # 更新提示词占位符
        prompt.update_placeholder(history=history)

        # 调用LLM获取回复
        response = await prompt.acall(query=query, is_stream=False)

        # 保存对话到记忆中
        self.memory.add_memory(role="用户", content=query)
        self.memory.add_memory(role="助手", content=response)

        return response

    def show_memory_info(self):
        """
        显示记忆信息
        """
        # 获取所有记忆
        all_memories = self.memory.get_memories(memory_id="default")
        print(f"总记忆数量：{len(all_memories)}")

        # 获取分数最高的3条记忆
        top_memories = self.memory.get_top_memories(memory_id="default", top_n=3)
        print("\n分数最高的3条记忆：")
        for i, memory in enumerate(top_memories):
            print(f"记忆 {i + 1} (分数: {memory.score:.2f}): {memory.content}")

        # 构建并显示历史对话
        history = self.memory.build_history(memory_id="default", max_round=5)
        print("\n格式化的历史对话：")
        print(history)


async def main():
    """
    主函数，演示记忆管理功能
    """
    # 初始化智能体，使用默认的短期记忆
    agent = MemoryAgent(llm=llm, verbose=True)

    print("=== 记忆管理功能示例 ===\n")

    # 测试多轮对话
    user_queries = [
        "你好，我叫小明。",
        "我叫什么？",
        "人工智能有哪些应用领域？用100个字简单描述",
        "你能举几个具体的例子吗？"
    ]

    for i, query in enumerate(user_queries):
        print(f"--- 对话轮次 {i + 1} ---")
        print(f"用户：{query}")
        response = await agent.chat_with_memory(query)
        print(f"助手：{response}\n")

        # 每两轮对话后显示记忆信息
        if (i + 1) % 2 == 0:
            print("--- 记忆信息 ---")
            agent.show_memory_info()
            print()


if __name__ == "__main__":
    import asyncio

    # 运行异步主函数
    asyncio.run(main())
