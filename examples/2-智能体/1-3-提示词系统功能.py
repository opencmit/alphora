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


class PromptAgent(BaseAgent):
    """
    提示词系统功能示例，展示如何使用提示词模板
    """
    async def chat_with_file_template(self, query: str, profession: str, language: str) -> str:
        """
        使用文件模板进行对话
        Args:
            query: 用户的查询内容
            profession: 职业角色
            language: 回答语言
        Returns:
            智能体的回复
        """
        # 构建历史对话
        history = self.memory.build_history(memory_id="file_template", max_round=3)
        
        # 从文件加载提示词模板
        prompt = self.create_prompt(
            template_path="prompt_template.tmpl",
            template_desc="通用职业角色回答模板"
        )
        
        # 更新提示词占位符
        prompt.update_placeholder(
            profession=profession,
            language=language,
            history=history
        )
        
        # 渲染提示词（用于调试）
        if self.verbose:
            print("渲染后的提示词：")
            print(prompt.render())
            print()
        
        # 调用LLM获取回复
        response = await prompt.acall(query=query, is_stream=False)
        
        # 保存对话到记忆中
        self.memory.add_memory(role="用户", content=query, memory_id="file_template")
        self.memory.add_memory(role=profession, content=response, memory_id="file_template")
        
        return response
    
    async def chat_with_string_template(self, query: str, topic: str) -> str:
        """
        使用字符串模板进行对话
        Args:
            query: 用户的查询内容
            topic: 主题领域
        Returns:
            智能体的回复
        """
        # 构建历史对话
        history = self.memory.build_history(memory_id="string_template", max_round=3)
        
        # 从字符串创建提示词模板
        template_str = f"你是一个{topic}专家，请用中文回答用户的问题。\n\n历史对话：\n{{history}}\n\n用户问题：\n{{query}}"
        
        prompt = self.create_prompt(prompt=template_str)
        
        # 更新提示词占位符
        prompt.update_placeholder(history=history)
        
        # 调用LLM获取回复
        response = await prompt.acall(query=query, is_stream=False)
        
        # 保存对话到记忆中
        self.memory.add_memory(role="用户", content=query, memory_id="string_template")
        self.memory.add_memory(role=f"{topic}专家", content=response, memory_id="string_template")
        
        return response


async def main():
    """
    主函数，演示提示词系统功能
    """
    # 初始化智能体
    agent = PromptAgent(llm=llm, verbose=True)
    
    print("=== 提示词系统功能示例 ===\n")
    
    # 测试1：使用文件模板
    print("--- 测试1：使用文件模板（作为医生，用中文回答） ---")
    response1 = await agent.chat_with_file_template(
        query="我经常头痛，应该怎么办？",
        profession="医生",
        language="中文"
    )
    print(f"用户：我经常头痛，应该怎么办？")
    print(f"医生：{response1}\n")
    
    # 测试2：使用文件模板（作为程序员，用英文回答）
    print("--- 测试2：使用文件模板（作为程序员，用英文回答） ---")
    response2 = await agent.chat_with_file_template(
        query="What is the best way to learn Python?",
        profession="程序员",
        language="英文"
    )
    print(f"用户：What is the best way to learn Python?")
    print(f"程序员：{response2}\n")
    
    # 测试3：使用字符串模板
    print("--- 测试3：使用字符串模板（作为历史专家） ---")
    response3 = await agent.chat_with_string_template(
        query="请介绍一下秦始皇的主要功绩。",
        topic="历史"
    )
    print(f"用户：请介绍一下秦始皇的主要功绩。")
    print(f"历史专家：{response3}\n")


if __name__ == "__main__":
    import asyncio
    # 运行异步主函数
    asyncio.run(main())