"""
03_prompter/basic_prompt.py
基础提示词示例

演示 BasePrompt 的各种用法
"""

import asyncio
from alphora.agent import BaseAgent
from alphora.models import OpenAILike
from alphora.prompter import BasePrompt


def create_llm():
    """创建 LLM 实例"""
    return OpenAILike(
        api_key="your-api-key",
        base_url="https://dashscope.aliyuncs.com/compatible-mode/v1",
        model_name="qwen-plus"
    )


# ============================================================
# 示例 1: 使用 system_prompt（新模式，推荐）
# ============================================================
async def example_system_prompt_mode():
    """使用 system_prompt 模式"""
    print("=" * 60)
    print("示例 1: 使用 system_prompt 模式（推荐）")
    print("=" * 60)

    llm = create_llm()
    agent = BaseAgent(llm=llm)

    # 创建提示词 - 新模式
    prompt = agent.create_prompt(
        system_prompt="你是一个专业的Python编程助手，回答要简洁准确。"
    )

    # 调用
    response = await prompt.acall(
        query="什么是装饰器？",
        is_stream=False
    )

    print(f"问题: 什么是装饰器？")
    print(f"回答: {response}")

    return response


# ============================================================
# 示例 2: 使用 prompt 参数（传统模式）
# ============================================================
async def example_prompt_mode():
    """使用 prompt 参数（传统模式）"""
    print("\n" + "=" * 60)
    print("示例 2: 使用 prompt 参数（传统模式）")
    print("=" * 60)

    llm = create_llm()
    agent = BaseAgent(llm=llm)

    # 创建提示词 - 传统模式
    prompt = agent.create_prompt(
        prompt="""你是一个翻译助手。

请将以下文本翻译成{{target_language}}：

{{query}}

只输出翻译结果，不要解释。"""
    )

    # 更新占位符
    prompt.update_placeholder(target_language="英文")

    # 调用
    response = await prompt.acall(
        query="人工智能正在改变世界",
        is_stream=False
    )

    print(f"原文: 人工智能正在改变世界")
    print(f"翻译: {response}")

    return response


# ============================================================
# 示例 3: 带占位符的 system_prompt
# ============================================================
async def example_placeholder_system_prompt():
    """带占位符的 system_prompt"""
    print("\n" + "=" * 60)
    print("示例 3: 带占位符的 system_prompt")
    print("=" * 60)

    llm = create_llm()
    agent = BaseAgent(llm=llm)

    # system_prompt 也支持占位符！
    prompt = agent.create_prompt(
        system_prompt="你是一个{{role}}，专长是{{specialty}}。你的回答风格是{{style}}。"
    )

    # 查看可用的占位符
    print(f"可用占位符: {prompt.placeholders}")

    # 更新占位符
    prompt.update_placeholder(
        role="资深架构师",
        specialty="分布式系统设计",
        style="专业严谨"
    )

    # 调用
    response = await prompt.acall(
        query="如何设计一个高可用的微服务架构？",
        is_stream=False
    )

    print(f"回答: {response[:200]}...")

    return response


# ============================================================
# 示例 4: 流式输出
# ============================================================
async def example_streaming():
    """流式输出示例"""
    print("\n" + "=" * 60)
    print("示例 4: 流式输出")
    print("=" * 60)

    llm = create_llm()
    agent = BaseAgent(llm=llm)

    prompt = agent.create_prompt(
        system_prompt="你是一个故事讲述者"
    )

    print("问题: 请讲一个简短的故事")
    print("回答: ", end="", flush=True)

    # 流式调用
    response = await prompt.acall(
        query="请讲一个简短的故事",
        is_stream=True
    )

    print(f"\n\n完整回答长度: {len(response)} 字符")

    return response


# ============================================================
# 示例 5: 返回生成器
# ============================================================
async def example_return_generator():
    """返回生成器而不是字符串"""
    print("\n" + "=" * 60)
    print("示例 5: 返回生成器")
    print("=" * 60)

    llm = create_llm()
    agent = BaseAgent(llm=llm)

    prompt = agent.create_prompt(
        system_prompt="你是一个编程助手"
    )

    # 返回生成器
    generator = await prompt.acall(
        query="用Python写一个Hello World",
        is_stream=True,
        return_generator=True
    )

    print("逐块处理生成器:")
    chunks = []
    async for chunk in generator:
        print(f"  [{chunk.content_type}] {chunk.content}", end="")
        chunks.append(chunk.content)

    print(f"\n\n总共 {len(chunks)} 个块")


# ============================================================
# 示例 6: JSON 输出
# ============================================================
async def example_json_output():
    """强制 JSON 输出"""
    print("\n" + "=" * 60)
    print("示例 6: JSON 输出")
    print("=" * 60)

    llm = create_llm()
    agent = BaseAgent(llm=llm)

    prompt = agent.create_prompt(
        system_prompt="你是一个数据助手，请用JSON格式回答问题。"
    )

    # 使用 force_json 参数
    response = await prompt.acall(
        query="列出3种编程语言及其特点",
        is_stream=False,
        force_json=True
    )

    print(f"JSON 回答:\n{response}")

    # 尝试解析
    import json
    try:
        data = json.loads(response)
        print(f"\n解析成功，类型: {type(data)}")
    except json.JSONDecodeError as e:
        print(f"\n解析失败: {e}")

    return response


# ============================================================
# 示例 7: 长响应模式
# ============================================================
async def example_long_response():
    """长响应模式（自动续写）"""
    print("\n" + "=" * 60)
    print("示例 7: 长响应模式")
    print("=" * 60)

    llm = create_llm()
    agent = BaseAgent(llm=llm)

    prompt = agent.create_prompt(
        system_prompt="你是一个技术文档作者"
    )

    # 启用长响应模式
    response = await prompt.acall(
        query="详细介绍Python的10个高级特性，每个特性都要有示例代码",
        is_stream=True,
        long_response=True  # 自动续写
    )

    print(f"\n回答长度: {len(response)} 字符")
    print(f"续写次数: {response.continuation_count}")


# ============================================================
# 示例 8: 启用思考模式
# ============================================================
async def example_thinking_mode():
    """启用思考模式"""
    print("\n" + "=" * 60)
    print("示例 8: 启用思考模式")
    print("=" * 60)

    llm = create_llm()
    agent = BaseAgent(llm=llm)

    prompt = agent.create_prompt(
        system_prompt="你是一个数学老师"
    )

    # 启用思考模式
    response = await prompt.acall(
        query="计算 (3 + 4) * 5 - 2 的结果",
        is_stream=True,
        enable_thinking=True  # 显示思考过程
    )

    print(f"\n\n最终答案: {response}")
    print(f"思考过程: {response.reasoning[:200]}..." if response.reasoning else "无思考过程")


# ============================================================
# 示例 9: PrompterOutput 对象
# ============================================================
async def example_prompter_output():
    """PrompterOutput 对象"""
    print("\n" + "=" * 60)
    print("示例 9: PrompterOutput 对象")
    print("=" * 60)

    llm = create_llm()
    agent = BaseAgent(llm=llm)

    prompt = agent.create_prompt(
        system_prompt="你是一个助手"
    )

    response = await prompt.acall(
        query="你好",
        is_stream=False
    )

    # PrompterOutput 继承自 str，但有额外属性
    print(f"回答（作为字符串）: {response}")
    print(f"类型: {type(response)}")
    print(f"finish_reason: {response.finish_reason}")
    print(f"reasoning: {response.reasoning}")
    print(f"continuation_count: {response.continuation_count}")


# ============================================================
# 示例 10: 渲染和查看提示词
# ============================================================
def example_render_prompt():
    """渲染和查看提示词"""
    print("\n" + "=" * 60)
    print("示例 10: 渲染和查看提示词")
    print("=" * 60)

    llm = create_llm()
    agent = BaseAgent(llm=llm)

    # 传统模式
    prompt = agent.create_prompt(
        prompt="""【角色】{{role}}

【任务】{{task}}

【约束】
- {{constraint1}}
- {{constraint2}}

【用户输入】
{{query}}"""
    )

    # 查看占位符
    print(f"占位符: {prompt.placeholders}")

    # 更新部分占位符
    prompt.update_placeholder(
        role="数据分析师",
        task="分析用户提供的数据"
    )

    # 渲染查看
    rendered = prompt.render()
    print(f"\n渲染后的提示词:\n{rendered}")

    # 查看完整提示词（__str__）
    print(f"\n提示词字符串:\n{str(prompt)}")


# ============================================================
# 主函数
# ============================================================
async def main():
    """运行所有示例"""
    # 同步示例
    example_render_prompt()

    # 异步示例
    await example_system_prompt_mode()
    await example_prompt_mode()
    await example_placeholder_system_prompt()
    await example_streaming()
    await example_return_generator()
    await example_json_output()
    # await example_long_response()  # 较慢，可选
    await example_thinking_mode()
    await example_prompter_output()


if __name__ == "__main__":
    asyncio.run(main())