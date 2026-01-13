"""
03_prompter/memory_prompt.py - 带记忆功能的提示词

演示如何使用新模式（system_prompt）实现自动记忆管理，
包括多轮对话、会话隔离、历史记录查看等功能。
"""

import asyncio
import os

# ============================================================
# 环境配置
# ============================================================
os.environ.setdefault("LLM_API_KEY", "your-api-key")
os.environ.setdefault("LLM_BASE_URL", "https://dashscope.aliyuncs.com/compatible-mode/v1")


# ============================================================
# 示例 1: 基础记忆功能
# ============================================================
async def example_1_basic_memory():
    """
    最简单的记忆功能使用方式

    关键点：
    - 使用 system_prompt 参数（新模式）
    - enable_memory=True 启用记忆
    - memory_id 区分不同会话
    """
    print("=" * 60)
    print("示例 1: 基础记忆功能")
    print("=" * 60)

    from alphora.agent import BaseAgent
    from alphora.models import OpenAILike

    llm = OpenAILike(
        api_key=os.environ["LLM_API_KEY"],
        base_url=os.environ["LLM_BASE_URL"],
        model_name="qwen-plus"
    )

    agent = BaseAgent(llm=llm, verbose=True)

    # 使用新模式创建带记忆的 Prompt
    prompt = agent.create_prompt(
        system_prompt="你是一个友好的助手，会记住用户说过的话。",
        enable_memory=True,
        memory_id="user_001"  # 用户唯一标识
    )

    # 第一轮对话
    print("\n--- 第一轮对话 ---")
    response1 = await prompt.acall(query="我叫小明，今年25岁", is_stream=False)
    print(f"用户: 我叫小明，今年25岁")
    print(f"助手: {response1}")

    # 第二轮对话 - 模型会记住之前的内容
    print("\n--- 第二轮对话 ---")
    response2 = await prompt.acall(query="我叫什么名字？", is_stream=False)
    print(f"用户: 我叫什么名字？")
    print(f"助手: {response2}")

    # 查看会话信息
    print("\n--- 会话信息 ---")
    info = agent.get_session_info("user_001")
    print(f"会话轮数: {info.get('rounds', 0)}")
    print(f"总消息数: {info.get('total_messages', 0)}")
    print()


# ============================================================
# 示例 2: 多会话隔离
# ============================================================
async def example_2_multiple_sessions():
    """
    演示不同 memory_id 之间的会话隔离
    """
    print("=" * 60)
    print("示例 2: 多会话隔离")
    print("=" * 60)

    from alphora.agent import BaseAgent
    from alphora.models import OpenAILike

    llm = OpenAILike(
        api_key=os.environ["LLM_API_KEY"],
        base_url=os.environ["LLM_BASE_URL"],
        model_name="qwen-plus"
    )

    agent = BaseAgent(llm=llm)

    # 用户A的会话
    prompt_a = agent.create_prompt(
        system_prompt="你是一个助手。",
        enable_memory=True,
        memory_id="user_a"
    )

    # 用户B的会话
    prompt_b = agent.create_prompt(
        system_prompt="你是一个助手。",
        enable_memory=True,
        memory_id="user_b"
    )

    # 用户A说话
    await prompt_a.acall(query="我喜欢蓝色", is_stream=False)
    print("用户A: 我喜欢蓝色")

    # 用户B说话
    await prompt_b.acall(query="我喜欢红色", is_stream=False)
    print("用户B: 我喜欢红色")

    # 分别询问
    response_a = await prompt_a.acall(query="我喜欢什么颜色？", is_stream=False)
    response_b = await prompt_b.acall(query="我喜欢什么颜色？", is_stream=False)

    print(f"\n询问用户A喜欢的颜色: {response_a}")
    print(f"询问用户B喜欢的颜色: {response_b}")

    # 列出所有会话
    print(f"\n当前所有会话: {agent.list_sessions()}")
    print()


# ============================================================
# 示例 3: 控制历史轮数
# ============================================================
async def example_3_max_history():
    """
    使用 max_history_rounds 控制发送给模型的历史轮数
    """
    print("=" * 60)
    print("示例 3: 控制历史轮数")
    print("=" * 60)

    from alphora.agent import BaseAgent
    from alphora.models import OpenAILike

    llm = OpenAILike(
        api_key=os.environ["LLM_API_KEY"],
        base_url=os.environ["LLM_BASE_URL"],
        model_name="qwen-plus"
    )

    agent = BaseAgent(llm=llm)

    # 只保留最近3轮对话
    prompt = agent.create_prompt(
        system_prompt="你是一个助手，请记住用户告诉你的数字。",
        enable_memory=True,
        memory_id="history_test",
        max_history_rounds=3  # 只发送最近3轮
    )

    # 模拟多轮对话
    numbers = ["一", "二", "三", "四", "五"]
    for num in numbers:
        response = await prompt.acall(query=f"记住数字{num}", is_stream=False)
        print(f"告诉助手: 数字{num}")

    # 询问记住了哪些数字
    response = await prompt.acall(query="你记住了哪些数字？", is_stream=False)
    print(f"\n助手回答: {response}")
    print("(由于 max_history_rounds=3，只能记住最近3轮的内容)")
    print()


# ============================================================
# 示例 4: 手动管理记忆
# ============================================================
async def example_4_manual_memory():
    """
    手动添加、查看、清空记忆
    """
    print("=" * 60)
    print("示例 4: 手动管理记忆")
    print("=" * 60)

    from alphora.agent import BaseAgent
    from alphora.models import OpenAILike

    llm = OpenAILike(
        api_key=os.environ["LLM_API_KEY"],
        base_url=os.environ["LLM_BASE_URL"],
        model_name="qwen-plus"
    )

    agent = BaseAgent(llm=llm)

    # 手动向会话添加历史记录
    session_id = "manual_session"

    # 手动添加用户消息
    agent.add_to_session(
        role="user",
        content="我的生日是1月1日",
        session_id=session_id
    )

    # 手动添加助手消息
    agent.add_to_session(
        role="assistant",
        content="好的，我记住了，您的生日是1月1日。",
        session_id=session_id
    )

    print("已手动添加对话历史")

    # 查看历史记录
    history_text = agent.get_session_history(
        session_id=session_id,
        format="text"
    )
    print(f"\n历史记录（文本格式）:\n{history_text}")

    # 获取 messages 格式
    history_messages = agent.get_session_history(
        session_id=session_id,
        format="messages"
    )
    print(f"历史记录（messages格式）: {history_messages}")

    # 创建 Prompt 继续对话
    prompt = agent.create_prompt(
        system_prompt="你是一个助手。",
        enable_memory=True,
        memory_id=session_id
    )

    response = await prompt.acall(query="我的生日是哪天？", is_stream=False)
    print(f"\n询问生日: {response}")

    # 清空会话
    agent.clear_session(session_id)
    print(f"\n已清空会话 {session_id}")
    print()


# ============================================================
# 示例 5: 获取 Prompt 级别的历史
# ============================================================
async def example_5_prompt_history():
    """
    通过 Prompt 实例直接获取和管理历史
    """
    print("=" * 60)
    print("示例 5: Prompt 级别的历史管理")
    print("=" * 60)

    from alphora.agent import BaseAgent
    from alphora.models import OpenAILike

    llm = OpenAILike(
        api_key=os.environ["LLM_API_KEY"],
        base_url=os.environ["LLM_BASE_URL"],
        model_name="qwen-plus"
    )

    agent = BaseAgent(llm=llm)

    prompt = agent.create_prompt(
        system_prompt="你是一个助手。",
        enable_memory=True,
        memory_id="prompt_history_test"
    )

    # 进行几轮对话
    await prompt.acall(query="你好", is_stream=False)
    await prompt.acall(query="今天天气真好", is_stream=False)

    # 通过 Prompt 获取历史
    history = prompt.get_history(format="messages")
    print(f"历史消息数: {len(history)}")

    # 获取关联的 MemoryManager
    memory = prompt.get_memory()
    print(f"Memory实例: {memory}")
    print(f"Memory ID: {prompt.memory_id}")

    # 清空当前 Prompt 的记忆
    prompt.clear_memory()
    print("\n已通过 Prompt 清空记忆")

    new_history = prompt.get_history(format="messages")
    print(f"清空后历史消息数: {len(new_history)}")
    print()


# ============================================================
# 示例 6: 禁用自动保存
# ============================================================
async def example_6_disable_auto_save():
    """
    在某些场景下可能不想自动保存对话到记忆
    """
    print("=" * 60)
    print("示例 6: 禁用自动保存")
    print("=" * 60)

    from alphora.agent import BaseAgent
    from alphora.models import OpenAILike

    llm = OpenAILike(
        api_key=os.environ["LLM_API_KEY"],
        base_url=os.environ["LLM_BASE_URL"],
        model_name="qwen-plus"
    )

    agent = BaseAgent(llm=llm)

    # 禁用自动保存
    prompt = agent.create_prompt(
        system_prompt="你是一个助手。",
        enable_memory=True,
        memory_id="no_auto_save",
        auto_save_memory=False  # 禁用自动保存
    )

    # 这次对话不会被保存
    response = await prompt.acall(query="这条消息不会被保存", is_stream=False)
    print(f"响应: {response}")

    # 手动决定是否保存
    # prompt.acall(..., save_to_memory=True)  # 单次强制保存

    history = prompt.get_history(format="messages")
    print(f"历史消息数（应该为0）: {len(history)}")
    print()


# ============================================================
# 示例 7: 记忆状态查看
# ============================================================
async def example_7_memory_status():
    """
    查看 Agent 的记忆系统状态
    """
    print("=" * 60)
    print("示例 7: 记忆状态查看")
    print("=" * 60)

    from alphora.agent import BaseAgent
    from alphora.models import OpenAILike

    llm = OpenAILike(
        api_key=os.environ["LLM_API_KEY"],
        base_url=os.environ["LLM_BASE_URL"],
        model_name="qwen-plus"
    )

    agent = BaseAgent(llm=llm)

    # 创建多个会话
    for i in range(3):
        prompt = agent.create_prompt(
            system_prompt="你是助手。",
            enable_memory=True,
            memory_id=f"session_{i}"
        )
        await prompt.acall(query=f"这是会话{i}的消息", is_stream=False)

    # 查看记忆状态
    status = agent.memory_status()
    print(status)
    print()


# ============================================================
# 示例 8: system_prompt 中使用占位符
# ============================================================
async def example_8_system_prompt_placeholders():
    """
    system_prompt 也支持占位符，可以动态定制角色
    """
    print("=" * 60)
    print("示例 8: system_prompt 中使用占位符")
    print("=" * 60)

    from alphora.agent import BaseAgent
    from alphora.models import OpenAILike

    llm = OpenAILike(
        api_key=os.environ["LLM_API_KEY"],
        base_url=os.environ["LLM_BASE_URL"],
        model_name="qwen-plus"
    )

    agent = BaseAgent(llm=llm)

    # system_prompt 中的占位符
    prompt = agent.create_prompt(
        system_prompt="""你是一个{{role}}，专长是{{specialty}}。
你的说话风格是{{style}}。
请记住用户的偏好并提供个性化建议。""",
        enable_memory=True,
        memory_id="personalized_session"
    )

    # 查看占位符
    print(f"占位符: {prompt.placeholders}")

    # 更新占位符
    prompt.update_placeholder(
        role="健身教练",
        specialty="力量训练",
        style="专业但友好"
    )

    # 预览渲染后的 system_prompt
    print(f"\n渲染后的 system_prompt:\n{prompt._render_system_prompt()}")

    # 进行对话
    response = await prompt.acall(query="我想增肌，有什么建议？", is_stream=False)
    print(f"\n助手回复: {response}")
    print()


# ============================================================
# 主函数
# ============================================================
def main():
    """运行所有示例"""
    print("\n" + "=" * 60)
    print("Alphora 记忆功能提示词示例")
    print("=" * 60 + "\n")

    # 示例 1: 基础记忆功能
    asyncio.run(example_1_basic_memory())

    # 示例 2: 多会话隔离
    asyncio.run(example_2_multiple_sessions())

    # 示例 3: 控制历史轮数
    asyncio.run(example_3_max_history())

    # 示例 4: 手动管理记忆
    asyncio.run(example_4_manual_memory())

    # 示例 5: Prompt 级别的历史
    asyncio.run(example_5_prompt_history())

    # 示例 6: 禁用自动保存
    asyncio.run(example_6_disable_auto_save())

    # 示例 7: 记忆状态查看
    asyncio.run(example_7_memory_status())

    # 示例 8: system_prompt 占位符
    asyncio.run(example_8_system_prompt_placeholders())

    print("\n" + "=" * 60)
    print("所有示例执行完成!")
    print("=" * 60)


if __name__ == "__main__":
    main()