"""
01_quickstart/basic_agent.py
基础智能体示例

演示如何创建和使用 BaseAgent
"""

import asyncio
from alphora.agent import BaseAgent
from alphora.models import OpenAILike


def create_llm():
    """创建 LLM 实例"""
    return OpenAILike(
        api_key="your-api-key",  # 替换为你的 API Key
        base_url="https://dashscope.aliyuncs.com/compatible-mode/v1",
        model_name="qwen-plus",
        temperature=0.7,
        max_tokens=2048
    )


# ============================================================
# 示例 1: 创建基础智能体
# ============================================================
def example_basic_agent():
    """创建基础智能体"""
    print("=" * 60)
    print("示例 1: 创建基础智能体")
    print("=" * 60)

    llm = create_llm()

    # 创建智能体
    agent = BaseAgent(
        llm=llm,
        verbose=True,  # 开启详细日志
        agent_id="my-first-agent"
    )

    print(f"智能体 ID: {agent.agent_id}")
    print(f"智能体类型: {agent.agent_type}")
    print(f"LLM 模型: {agent.llm.model_name}")

    return agent


# ============================================================
# 示例 2: 使用智能体创建提示词
# ============================================================
async def example_create_prompt():
    """使用智能体创建提示词"""
    print("\n" + "=" * 60)
    print("示例 2: 使用智能体创建提示词")
    print("=" * 60)

    llm = create_llm()
    agent = BaseAgent(llm=llm)

    # 方式一：使用 system_prompt（推荐，支持记忆）
    prompt = agent.create_prompt(
        system_prompt="你是一个专业的Python编程助手，擅长解释代码和编程概念。"
    )

    # 调用提示词
    response = await prompt.acall(
        query="请解释什么是列表推导式？",
        is_stream=False
    )

    print(f"回答: {response}")

    return response


# ============================================================
# 示例 3: 智能体配置管理
# ============================================================
def example_agent_config():
    """智能体配置管理"""
    print("\n" + "=" * 60)
    print("示例 3: 智能体配置管理")
    print("=" * 60)

    llm = create_llm()
    agent = BaseAgent(llm=llm)

    # 设置配置
    agent.update_config("max_retries", 3)
    agent.update_config("timeout", 30)
    agent.update_config("custom_setting", {"key": "value"})

    # 获取配置
    print(f"max_retries: {agent.get_config('max_retries')}")
    print(f"timeout: {agent.get_config('timeout')}")
    print(f"custom_setting: {agent.get_config('custom_setting')}")


# ============================================================
# 示例 4: 智能体派生
# ============================================================
def example_agent_derive():
    """智能体派生"""
    print("\n" + "=" * 60)
    print("示例 4: 智能体派生")
    print("=" * 60)

    # 自定义智能体类
    class TranslatorAgent(BaseAgent):
        agent_type = "TranslatorAgent"

        async def translate(self, text: str, target_lang: str = "English"):
            prompt = self.create_prompt(
                system_prompt=f"你是一个专业的翻译，请将用户输入翻译为{target_lang}。只输出翻译结果，不要解释。"
            )
            return await prompt.acall(query=text, is_stream=False)

    llm = create_llm()
    base_agent = BaseAgent(llm=llm)

    # 从基础智能体派生出翻译智能体
    translator = base_agent.derive(TranslatorAgent)

    print(f"派生智能体类型: {translator.agent_type}")
    print(f"派生智能体 ID: {translator.agent_id}")
    print(f"共享 LLM: {translator.llm.model_name}")

    return translator


# ============================================================
# 示例 5: 会话管理
# ============================================================
async def example_session_management():
    """会话管理"""
    print("\n" + "=" * 60)
    print("示例 5: 会话管理")
    print("=" * 60)

    llm = create_llm()
    agent = BaseAgent(llm=llm, verbose=True)

    # 创建带记忆的提示词
    prompt = agent.create_prompt(
        system_prompt="你是一个友好的助手，请记住用户告诉你的信息。",
        enable_memory=True,
        memory_id="session_001",
        max_history_rounds=10
    )

    # 多轮对话
    print("开始多轮对话...")

    response1 = await prompt.acall(query="我叫张三，今年25岁", is_stream=False)
    print(f"用户: 我叫张三，今年25岁")
    print(f"助手: {response1}")

    response2 = await prompt.acall(query="我喜欢编程和音乐", is_stream=False)
    print(f"\n用户: 我喜欢编程和音乐")
    print(f"助手: {response2}")

    response3 = await prompt.acall(query="你还记得我叫什么名字吗？", is_stream=False)
    print(f"\n用户: 你还记得我叫什么名字吗？")
    print(f"助手: {response3}")

    # 查看会话信息
    print("\n会话信息:")
    sessions = agent.list_sessions()
    print(f"所有会话: {sessions}")

    session_info = agent.get_session_info("session_001")
    print(f"session_001 详情: {session_info}")


# ============================================================
# 示例 6: 记忆状态查看
# ============================================================
def example_memory_status():
    """记忆状态查看"""
    print("\n" + "=" * 60)
    print("示例 6: 记忆状态查看")
    print("=" * 60)

    llm = create_llm()
    agent = BaseAgent(llm=llm)

    # 手动添加记忆
    agent.add_to_session("user", "你好，我想了解Python", session_id="demo")
    agent.add_to_session("assistant", "你好！Python是一门优秀的编程语言...", session_id="demo")
    agent.add_to_session("user", "它有什么特点？", session_id="demo")
    agent.add_to_session("assistant", "Python的主要特点包括...", session_id="demo")

    # 查看记忆状态
    status = agent.memory_status()
    print(status)

    # 获取历史记录
    history = agent.get_session_history("demo", format="messages")
    print(f"\n历史记录 (messages 格式):")
    for msg in history:
        print(f"  {msg}")

    history_text = agent.get_session_history("demo", format="text")
    print(f"\n历史记录 (text 格式):\n{history_text}")


# ============================================================
# 主函数
# ============================================================
async def main():
    """运行所有示例"""
    # 同步示例
    example_basic_agent()
    example_agent_config()
    example_agent_derive()
    example_memory_status()

    # 异步示例
    await example_create_prompt()
    await example_session_management()


if __name__ == "__main__":
    asyncio.run(main())

