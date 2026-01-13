"""
03_prompter/parallel_prompt.py - 并行提示词执行

演示如何使用 ParallelPrompt 同时执行多个提示词，
实现并发调用以提高效率。
"""

import asyncio
import os
import time

# ============================================================
# 环境配置
# ============================================================
os.environ.setdefault("LLM_API_KEY", "your-api-key")
os.environ.setdefault("LLM_BASE_URL", "https://dashscope.aliyuncs.com/compatible-mode/v1")


# ============================================================
# 示例 1: 使用 | 操作符创建并行 Prompt
# ============================================================
async def example_1_parallel_operator():
    """
    使用 | 操作符将多个 Prompt 组合成 ParallelPrompt
    """
    print("=" * 60)
    print("示例 1: 使用 | 操作符创建并行 Prompt")
    print("=" * 60)

    from alphora.agent import BaseAgent
    from alphora.models import OpenAILike

    llm = OpenAILike(
        api_key=os.environ["LLM_API_KEY"],
        base_url=os.environ["LLM_BASE_URL"],
        model_name="qwen-plus"
    )

    agent = BaseAgent(llm=llm)

    # 创建三个不同角色的 Prompt
    prompt_translator = agent.create_prompt(
        system_prompt="你是一个中英翻译专家，只输出翻译结果。"
    )

    prompt_summarizer = agent.create_prompt(
        system_prompt="你是一个文本摘要专家，用一句话概括内容。"
    )

    prompt_sentiment = agent.create_prompt(
        system_prompt="你是情感分析专家，分析文本是积极、消极还是中性，只输出一个词。"
    )

    # 使用 | 操作符组合成并行 Prompt
    parallel_prompt = prompt_translator | prompt_summarizer | prompt_sentiment

    print(f"并行 Prompt 类型: {type(parallel_prompt).__name__}")
    print(f"包含 {len(parallel_prompt.prompts)} 个子 Prompt")

    # 并行调用
    text = "人工智能正在改变我们的生活方式，带来前所未有的便利。"

    start_time = time.time()
    results = await parallel_prompt.acall(query=text, is_stream=False)
    elapsed = time.time() - start_time

    print(f"\n输入文本: {text}")
    print(f"\n并行执行结果（耗时 {elapsed:.2f}s）:")
    print(f"  翻译: {results[0]}")
    print(f"  摘要: {results[1]}")
    print(f"  情感: {results[2]}")
    print()


# ============================================================
# 示例 2: 串行 vs 并行对比
# ============================================================
async def example_2_serial_vs_parallel():
    """
    对比串行执行和并行执行的效率差异
    """
    print("=" * 60)
    print("示例 2: 串行 vs 并行对比")
    print("=" * 60)

    from alphora.agent import BaseAgent
    from alphora.models import OpenAILike

    llm = OpenAILike(
        api_key=os.environ["LLM_API_KEY"],
        base_url=os.environ["LLM_BASE_URL"],
        model_name="qwen-plus"
    )

    agent = BaseAgent(llm=llm)

    # 创建多个 Prompt
    prompts = []
    for i in range(3):
        prompt = agent.create_prompt(
            system_prompt=f"你是助手{i+1}，简短回答问题。"
        )
        prompts.append(prompt)

    query = "1+1等于几？"

    # 串行执行
    print("串行执行...")
    start_serial = time.time()
    serial_results = []
    for p in prompts:
        result = await p.acall(query=query, is_stream=False)
        serial_results.append(result)
    serial_time = time.time() - start_serial
    print(f"  串行耗时: {serial_time:.2f}s")

    # 并行执行
    print("\n并行执行...")
    parallel_prompt = prompts[0] | prompts[1] | prompts[2]
    start_parallel = time.time()
    parallel_results = await parallel_prompt.acall(query=query, is_stream=False)
    parallel_time = time.time() - start_parallel
    print(f"  并行耗时: {parallel_time:.2f}s")

    print(f"\n效率提升: {(serial_time / parallel_time):.1f}x")
    print()


# ============================================================
# 示例 3: 多角度分析
# ============================================================
async def example_3_multi_perspective():
    """
    使用并行 Prompt 从多个角度分析同一问题
    """
    print("=" * 60)
    print("示例 3: 多角度分析")
    print("=" * 60)

    from alphora.agent import BaseAgent
    from alphora.models import OpenAILike

    llm = OpenAILike(
        api_key=os.environ["LLM_API_KEY"],
        base_url=os.environ["LLM_BASE_URL"],
        model_name="qwen-plus"
    )

    agent = BaseAgent(llm=llm)

    # 创建不同视角的分析师
    perspectives = [
        ("技术专家", "从技术可行性和实现难度角度分析"),
        ("商业分析师", "从市场需求和商业价值角度分析"),
        ("风险评估师", "从潜在风险和挑战角度分析"),
        ("用户体验师", "从用户需求和体验角度分析"),
    ]

    prompts = []
    for role, focus in perspectives:
        prompt = agent.create_prompt(
            system_prompt=f"你是一位{role}。{focus}。请用3-5句话简要分析。"
        )
        prompts.append(prompt)

    # 组合成并行 Prompt
    parallel_prompt = prompts[0]
    for p in prompts[1:]:
        parallel_prompt = parallel_prompt | p

    # 提出问题
    question = "我们公司计划开发一款AI驱动的个人健康助手App"

    results = await parallel_prompt.acall(query=question, is_stream=False)

    print(f"问题: {question}\n")
    print("多角度分析结果:")
    print("-" * 40)
    for (role, _), result in zip(perspectives, results):
        print(f"\n【{role}】")
        print(result)
    print()


# ============================================================
# 示例 4: 投票机制
# ============================================================
async def example_4_voting():
    """
    使用多个模型投票得出最终答案
    """
    print("=" * 60)
    print("示例 4: 投票机制")
    print("=" * 60)

    from alphora.agent import BaseAgent
    from alphora.models import OpenAILike
    from collections import Counter

    llm = OpenAILike(
        api_key=os.environ["LLM_API_KEY"],
        base_url=os.environ["LLM_BASE_URL"],
        model_name="qwen-plus"
    )

    agent = BaseAgent(llm=llm)

    # 创建5个投票者
    prompts = []
    for i in range(5):
        prompt = agent.create_prompt(
            system_prompt=f"""你是评委{i+1}。对于给定的陈述，判断其是"正确"还是"错误"。
只输出一个词：正确 或 错误"""
        )
        prompts.append(prompt)

    # 组合成并行 Prompt
    parallel_prompt = prompts[0]
    for p in prompts[1:]:
        parallel_prompt = parallel_prompt | p

    # 测试陈述
    statement = "地球是太阳系中最大的行星"

    results = await parallel_prompt.acall(query=statement, is_stream=False)

    print(f"陈述: {statement}\n")
    print("投票结果:")
    for i, result in enumerate(results):
        print(f"  评委{i+1}: {result.strip()}")

    # 统计投票
    votes = [r.strip() for r in results]
    vote_count = Counter(votes)

    print(f"\n投票统计: {dict(vote_count)}")
    final_answer = vote_count.most_common(1)[0][0]
    print(f"最终判定: {final_answer}")
    print()


# ============================================================
# 示例 5: 带占位符的并行 Prompt
# ============================================================
async def example_5_with_placeholders():
    """
    并行 Prompt 中使用占位符
    """
    print("=" * 60)
    print("示例 5: 带占位符的并行 Prompt")
    print("=" * 60)

    from alphora.agent import BaseAgent
    from alphora.models import OpenAILike

    llm = OpenAILike(
        api_key=os.environ["LLM_API_KEY"],
        base_url=os.environ["LLM_BASE_URL"],
        model_name="qwen-plus"
    )

    agent = BaseAgent(llm=llm)

    # 创建带占位符的 Prompt
    prompt1 = agent.create_prompt(
        prompt="将以下{{lang}}翻译成中文：{{query}}"
    )

    prompt2 = agent.create_prompt(
        prompt="用{{style}}风格改写以下文本：{{query}}"
    )

    # 分别设置占位符
    prompt1.update_placeholder(lang="英文")
    prompt2.update_placeholder(style="幽默")

    # 组合
    parallel_prompt = prompt1 | prompt2

    text = "Hello, how are you today?"
    results = await parallel_prompt.acall(query=text, is_stream=False)

    print(f"原文: {text}\n")
    print(f"翻译结果: {results[0]}")
    print(f"改写结果: {results[1]}")
    print()


# ============================================================
# 示例 6: 直接使用 ParallelPrompt 类
# ============================================================
async def example_6_direct_parallel_prompt():
    """
    直接使用 ParallelPrompt 类创建并行执行
    """
    print("=" * 60)
    print("示例 6: 直接使用 ParallelPrompt 类")
    print("=" * 60)

    from alphora.agent import BaseAgent
    from alphora.models import OpenAILike
    from alphora.prompter.parallel import ParallelPrompt

    llm = OpenAILike(
        api_key=os.environ["LLM_API_KEY"],
        base_url=os.environ["LLM_BASE_URL"],
        model_name="qwen-plus"
    )

    agent = BaseAgent(llm=llm)

    # 创建 Prompt 列表
    prompt_list = [
        agent.create_prompt(system_prompt="你是数学老师，简单解释数学概念。"),
        agent.create_prompt(system_prompt="你是物理老师，简单解释物理概念。"),
        agent.create_prompt(system_prompt="你是化学老师，简单解释化学概念。"),
    ]

    # 直接用列表创建 ParallelPrompt
    parallel_prompt = ParallelPrompt(prompt_list)

    question = "什么是能量？"
    results = await parallel_prompt.acall(query=question, is_stream=False)

    print(f"问题: {question}\n")
    teachers = ["数学老师", "物理老师", "化学老师"]
    for teacher, result in zip(teachers, results):
        print(f"【{teacher}】")
        print(f"{result}\n")


# ============================================================
# 示例 7: 同步并行调用
# ============================================================
def example_7_sync_parallel():
    """
    同步方式的并行调用
    """
    print("=" * 60)
    print("示例 7: 同步并行调用")
    print("=" * 60)

    from alphora.agent import BaseAgent
    from alphora.models import OpenAILike

    llm = OpenAILike(
        api_key=os.environ["LLM_API_KEY"],
        base_url=os.environ["LLM_BASE_URL"],
        model_name="qwen-plus"
    )

    agent = BaseAgent(llm=llm)

    # 创建并行 Prompt
    prompt1 = agent.create_prompt(system_prompt="你是助手A，简短回答。")
    prompt2 = agent.create_prompt(system_prompt="你是助手B，简短回答。")

    parallel_prompt = prompt1 | prompt2

    # 同步调用
    results = parallel_prompt.call(query="你好", is_stream=False)

    print("同步并行调用结果:")
    print(f"  助手A: {results[0]}")
    print(f"  助手B: {results[1]}")
    print()


# ============================================================
# 主函数
# ============================================================
def main():
    """运行所有示例"""
    print("\n" + "=" * 60)
    print("Alphora 并行提示词示例")
    print("=" * 60 + "\n")

    # 示例 1: 使用 | 操作符
    asyncio.run(example_1_parallel_operator())

    # 示例 2: 串行 vs 并行对比
    asyncio.run(example_2_serial_vs_parallel())

    # 示例 3: 多角度分析
    asyncio.run(example_3_multi_perspective())

    # 示例 4: 投票机制
    asyncio.run(example_4_voting())

    # 示例 5: 带占位符的并行
    asyncio.run(example_5_with_placeholders())

    # 示例 6: 直接使用 ParallelPrompt
    asyncio.run(example_6_direct_parallel_prompt())

    # 示例 7: 同步并行调用
    example_7_sync_parallel()

    print("\n" + "=" * 60)
    print("所有示例执行完成!")
    print("=" * 60)


if __name__ == "__main__":
    main()