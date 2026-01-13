"""
01_quickstart/simple_chat.py
简单对话示例

演示最简单的对话实现方式
"""

import asyncio
from alphora.agent import BaseAgent
from alphora.models import OpenAILike


def create_llm():
    """创建 LLM 实例"""
    return OpenAILike(
        api_key="your-api-key",
        base_url="https://dashscope.aliyuncs.com/compatible-mode/v1",
        model_name="qwen-plus"
    )


# ============================================================
# 示例 1: 最简单的对话
# ============================================================
async def simple_chat():
    """最简单的对话示例"""
    print("=" * 60)
    print("示例 1: 最简单的对话")
    print("=" * 60)

    llm = create_llm()
    agent = BaseAgent(llm=llm)

    # 创建提示词
    prompt = agent.create_prompt(
        system_prompt="你是一个友好的助手"
    )

    # 发起对话
    response = await prompt.acall(query="你好！", is_stream=False)
    print(f"用户: 你好！")
    print(f"助手: {response}")


# ============================================================
# 示例 2: 流式对话
# ============================================================
async def streaming_chat():
    """流式对话示例"""
    print("\n" + "=" * 60)
    print("示例 2: 流式对话")
    print("=" * 60)

    llm = create_llm()
    agent = BaseAgent(llm=llm)

    prompt = agent.create_prompt(
        system_prompt="你是一个知识渊博的助手"
    )

    print("用户: 请简单介绍一下人工智能")
    print("助手: ", end="", flush=True)

    # 流式输出
    response = await prompt.acall(
        query="请简单介绍一下人工智能",
        is_stream=True
    )

    print(f"\n\n完整回答: {response}")


# ============================================================
# 示例 3: 带占位符的提示词
# ============================================================
async def template_chat():
    """带占位符的提示词"""
    print("\n" + "=" * 60)
    print("示例 3: 带占位符的提示词")
    print("=" * 60)

    llm = create_llm()
    agent = BaseAgent(llm=llm)

    # 使用传统模式（prompt 参数）
    prompt = agent.create_prompt(
        prompt="""你是一个{{role}}，专长是{{specialty}}。

用户问题：{{query}}

请根据你的专长回答用户的问题。"""
    )

    # 更新占位符
    prompt.update_placeholder(
        role="资深程序员",
        specialty="Python 后端开发"
    )

    response = await prompt.acall(
        query="如何设计一个高并发的API？",
        is_stream=False
    )

    print(f"回答: {response}")


# ============================================================
# 示例 4: 多轮对话（带记忆）
# ============================================================
async def multi_turn_chat():
    """多轮对话示例"""
    print("\n" + "=" * 60)
    print("示例 4: 多轮对话（带记忆）")
    print("=" * 60)

    llm = create_llm()
    agent = BaseAgent(llm=llm)

    # 创建带记忆的提示词
    prompt = agent.create_prompt(
        system_prompt="你是一个友好的助手，请记住对话上下文。",
        enable_memory=True,
        memory_id="chat_demo",
        max_history_rounds=5
    )

    # 模拟多轮对话
    conversations = [
        "我想学习机器学习",
        "有什么好的入门资源吗？",
        "那Python库呢？推荐哪些？",
        "你之前说我想学什么来着？"
    ]

    for user_input in conversations:
        print(f"\n用户: {user_input}")
        response = await prompt.acall(query=user_input, is_stream=False)
        print(f"助手: {response}")

    # 清除记忆
    agent.clear_session("chat_demo")
    print("\n记忆已清除")


# ============================================================
# 示例 5: 交互式对话
# ============================================================
async def interactive_chat():
    """交互式对话示例"""
    print("\n" + "=" * 60)
    print("示例 5: 交互式对话")
    print("=" * 60)

    llm = create_llm()
    agent = BaseAgent(llm=llm)

    prompt = agent.create_prompt(
        system_prompt="你是一个智能助手，可以回答各种问题。",
        enable_memory=True,
        memory_id="interactive"
    )

    print("开始交互式对话（输入 'quit' 退出）")
    print("-" * 40)

    while True:
        user_input = input("\n你: ").strip()

        if user_input.lower() in ['quit', 'exit', 'q']:
            print("再见！")
            break

        if not user_input:
            continue

        print("助手: ", end="", flush=True)
        response = await prompt.acall(query=user_input, is_stream=True)
        print()  # 换行


# ============================================================
# 示例 6: 角色扮演对话
# ============================================================
async def roleplay_chat():
    """角色扮演对话"""
    print("\n" + "=" * 60)
    print("示例 6: 角色扮演对话")
    print("=" * 60)

    llm = create_llm()
    agent = BaseAgent(llm=llm)

    # 创建角色扮演提示词
    prompt = agent.create_prompt(
        system_prompt="""你是一位名叫"艾丽丝"的中世纪魔法师，性格特点：
- 说话优雅，喜欢用古典的方式表达
- 对魔法知识非常精通
- 有时会用"吾"自称
- 会适当使用魔法术语

请保持这个角色进行对话。""",
        enable_memory=True,
        memory_id="roleplay"
    )

    conversations = [
        "你好，魔法师！",
        "你会什么魔法？",
        "能教我一个简单的咒语吗？"
    ]

    for user_input in conversations:
        print(f"\n旅行者: {user_input}")
        response = await prompt.acall(query=user_input, is_stream=False)
        print(f"艾丽丝: {response}")


# ============================================================
# 主函数
# ============================================================
async def main():
    """运行所有示例"""
    await simple_chat()
    await streaming_chat()
    await template_chat()
    await multi_turn_chat()
    await roleplay_chat()

    # 交互式对话（可选，取消注释以启用）
    # await interactive_chat()


if __name__ == "__main__":
    asyncio.run(main())
    