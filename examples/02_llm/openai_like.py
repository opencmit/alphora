"""
02_llm/openai_like.py
OpenAI 兼容接口示例

演示 OpenAILike 类的各种用法
"""

import asyncio
from alphora.models import OpenAILike
from alphora.models.message import Message


def create_llm():
    """创建 LLM 实例"""
    return OpenAILike(
        api_key="your-api-key",
        base_url="https://dashscope.aliyuncs.com/compatible-mode/v1",
        model_name="qwen-plus",
        temperature=0.7,
        max_tokens=2048,
        top_p=0.9
    )


# ============================================================
# 示例 1: 基本初始化
# ============================================================
def example_initialization():
    """LLM 初始化示例"""
    print("=" * 60)
    print("示例 1: LLM 初始化")
    print("=" * 60)

    # 方式一：直接传参
    llm1 = OpenAILike(
        api_key="your-api-key",
        base_url="https://dashscope.aliyuncs.com/compatible-mode/v1",
        model_name="qwen-plus"
    )
    print(f"LLM1: {llm1}")

    # 方式二：使用环境变量（需要设置 LLM_API_KEY, LLM_BASE_URL, DEFAULT_LLM）
    # llm2 = OpenAILike()
    # print(f"LLM2: {llm2}")

    # 方式三：使用自定义 header
    llm3 = OpenAILike(
        api_key="your-api-key",
        base_url="https://dashscope.aliyuncs.com/compatible-mode/v1",
        model_name="qwen-plus",
        header={"X-Custom-Header": "value"}
    )
    print(f"LLM3: {llm3}")

    return llm1


# ============================================================
# 示例 2: 同步调用
# ============================================================
def example_sync_invoke():
    """同步调用示例"""
    print("\n" + "=" * 60)
    print("示例 2: 同步调用")
    print("=" * 60)

    llm = create_llm()

    # 简单字符串输入
    response = llm.invoke("什么是人工智能？请用一句话回答。")
    print(f"回答: {response}")

    return response


# ============================================================
# 示例 3: 异步调用
# ============================================================
async def example_async_invoke():
    """异步调用示例"""
    print("\n" + "=" * 60)
    print("示例 3: 异步调用")
    print("=" * 60)

    llm = create_llm()

    # 异步调用
    response = await llm.ainvoke("什么是机器学习？请用一句话回答。")
    print(f"回答: {response}")

    return response


# ============================================================
# 示例 4: 带 system prompt 的调用
# ============================================================
async def example_with_system_prompt():
    """带 system prompt 的调用"""
    print("\n" + "=" * 60)
    print("示例 4: 带 system prompt 的调用")
    print("=" * 60)

    llm = create_llm()

    # 使用 system_prompt 参数
    response = await llm.aget_non_stream_response(
        message="请帮我写一首关于春天的诗",
        system_prompt="你是一位著名的诗人，擅长写古诗词。"
    )
    print(f"诗歌:\n{response}")

    return response


# ============================================================
# 示例 5: 流式输出
# ============================================================
async def example_streaming():
    """流式输出示例"""
    print("\n" + "=" * 60)
    print("示例 5: 流式输出")
    print("=" * 60)

    llm = create_llm()

    print("生成中: ", end="", flush=True)

    # 获取流式生成器
    generator = await llm.aget_streaming_response(
        message="请介绍一下 Python 的主要特点",
        content_type="text"
    )

    full_response = ""
    async for chunk in generator:
        print(chunk.content, end="", flush=True)
        full_response += chunk.content

    print(f"\n\n完整回答长度: {len(full_response)} 字符")
    print(f"结束原因: {generator.finish_reason}")

    return full_response


# ============================================================
# 示例 6: 参数动态调整
# ============================================================
def example_parameter_adjustment():
    """参数动态调整"""
    print("\n" + "=" * 60)
    print("示例 6: 参数动态调整")
    print("=" * 60)

    llm = create_llm()

    print(f"初始配置:")
    print(f"  temperature: {llm.temperature}")
    print(f"  max_tokens: {llm.max_tokens}")
    print(f"  top_p: {llm.top_p}")
    print(f"  model: {llm.model_name}")

    # 动态调整参数
    llm.set_temperature(0.9)
    llm.set_max_tokens(4096)
    llm.set_top_p(0.95)
    llm.set_model_name("qwen-max")

    print(f"\n调整后配置:")
    print(f"  temperature: {llm.temperature}")
    print(f"  max_tokens: {llm.max_tokens}")
    print(f"  top_p: {llm.top_p}")
    print(f"  model: {llm.model_name}")


# ============================================================
# 示例 7: 负载均衡（多模型）
# ============================================================
def example_load_balancing():
    """负载均衡示例"""
    print("\n" + "=" * 60)
    print("示例 7: 负载均衡（多模型）")
    print("=" * 60)

    # 创建多个 LLM 实例
    llm1 = OpenAILike(
        api_key="your-api-key",
        base_url="https://dashscope.aliyuncs.com/compatible-mode/v1",
        model_name="qwen-plus"
    )

    llm2 = OpenAILike(
        api_key="your-api-key",
        base_url="https://dashscope.aliyuncs.com/compatible-mode/v1",
        model_name="qwen-max"
    )

    # 使用 + 运算符合并（负载均衡）
    combined_llm = llm1 + llm2

    print(f"合并后的后端数量: {combined_llm._balancer.size()}")

    # 现在调用 combined_llm 会自动轮询两个模型
    # response = combined_llm.invoke("你好")

    return combined_llm


# ============================================================
# 示例 8: 使用 Message 对象
# ============================================================
async def example_with_message():
    """使用 Message 对象"""
    print("\n" + "=" * 60)
    print("示例 8: 使用 Message 对象")
    print("=" * 60)

    llm = create_llm()

    # 创建 Message 对象
    message = Message()
    message.add_text("请用JSON格式列出3种编程语言的特点")

    print(f"Message 信息: {message}")

    response = await llm.ainvoke(message)
    print(f"回答:\n{response}")

    return response


# ============================================================
# 示例 9: messages 列表格式
# ============================================================
async def example_messages_list():
    """使用 messages 列表格式"""
    print("\n" + "=" * 60)
    print("示例 9: messages 列表格式")
    print("=" * 60)

    llm = create_llm()

    # 构建 messages 列表（OpenAI 格式）
    messages = [
        {"role": "system", "content": "你是一个专业的翻译，只输出翻译结果。"},
        {"role": "user", "content": "Hello, how are you?"},
        {"role": "assistant", "content": "你好，你好吗？"},
        {"role": "user", "content": "I'm fine, thank you!"}
    ]

    response = await llm.ainvoke(messages)
    print(f"翻译结果: {response}")

    return response


# ============================================================
# 示例 10: 连通性测试
# ============================================================
async def example_ping():
    """连通性测试"""
    print("\n" + "=" * 60)
    print("示例 10: 连通性测试")
    print("=" * 60)

    llm = create_llm()

    # 同步测试
    sync_result = llm.ping()
    print(f"同步测试结果: {'成功' if sync_result else '失败'}")

    # 异步测试
    async_result = await llm.aping()
    print(f"异步测试结果: {'成功' if async_result else '失败'}")


# ============================================================
# 主函数
# ============================================================
async def main():
    """运行所有示例"""
    # 同步示例
    example_initialization()
    example_sync_invoke()
    example_parameter_adjustment()
    example_load_balancing()

    # 异步示例
    await example_async_invoke()
    await example_with_system_prompt()
    await example_streaming()
    await example_with_message()
    await example_messages_list()
    await example_ping()


if __name__ == "__main__":
    asyncio.run(main())