"""
JsonKeyExtractorPP 使用示例

功能特性：
1. 从流式 JSON 输出中提取指定 key 的值
2. 支持嵌套路径: "data.product.desc"
3. 支持数组索引: "items[0].name"
4. 支持多 key 提取: ["title", "content"]
"""

import asyncio
from alphora.agent.base_agent import BaseAgent
from alphora.models.llms import OpenAILike
from alphora.postprocess import JsonKeyExtractorPP


class DemoAgent(BaseAgent):
    """演示用智能体"""

    async def demo_single_key(self, text: str):
        """
        示例1: 单个 key 提取

        LLM 输出: {"analysis": "这是分析结果", "score": 8}
        提取后:   这是分析结果
        """
        prompt = (
            "请分析以下文本，以 JSON 格式输出，包含 analysis 和 score 两个字段。\n"
            "文本: {{ text }}\n"
            "直接返回 JSON，不要 markdown 格式。"
        )

        # 只提取 analysis 字段
        pp = JsonKeyExtractorPP(target_key="analysis")

        prompter = self.create_prompt(prompt=prompt)
        prompter.update_placeholder(text=text)

        return await prompter.acall(query=None, is_stream=True, postprocessor=pp)

    async def demo_nested_key(self, text: str):
        """
        示例2: 嵌套 key 提取

        LLM 输出: {"code": 200, "data": {"result": {"content": "核心内容"}}}
        提取后:   核心内容
        """
        prompt = (
            "请分析文本，以嵌套 JSON 格式输出。\n"
            "格式: {\"code\": 200, \"data\": {\"result\": {\"content\": \"你的分析\"}}}\n"
            "文本: {{ text }}\n"
            "直接返回 JSON。"
        )

        # 提取嵌套路径
        pp = JsonKeyExtractorPP(target_key="data.result.content")

        prompter = self.create_prompt(prompt=prompt)
        prompter.update_placeholder(text=text)

        return await prompter.acall(query=None, is_stream=True, postprocessor=pp)

    async def demo_array_index(self, text: str):
        """
        示例3: 数组索引提取

        LLM 输出: {"items": [{"name": "第一项"}, {"name": "第二项"}]}
        提取后:   第一项
        """
        prompt = (
            "请从文本中提取关键词，以 JSON 格式输出。\n"
            "格式: {\"items\": [{\"name\": \"关键词1\"}, {\"name\": \"关键词2\"}]}\n"
            "文本: {{ text }}\n"
            "直接返回 JSON。"
        )

        # 提取数组第一个元素的 name
        pp = JsonKeyExtractorPP(target_key="items[0].name")

        prompter = self.create_prompt(prompt=prompt)
        prompter.update_placeholder(text=text)

        return await prompter.acall(query=None, is_stream=True, postprocessor=pp)

    async def demo_multi_keys(self, text: str):
        """
        示例4: 多 key 提取

        LLM 输出: {"title": "标题", "summary": "摘要内容", "score": 9}
        提取后:   标题
                  ---
                  摘要内容
        """
        prompt = (
            "请分析文本，输出 JSON 格式，包含 title、summary、score 三个字段。\n"
            "文本: {{ text }}\n"
            "直接返回 JSON。"
        )

        # 提取多个 key，用分隔符连接
        pp = JsonKeyExtractorPP(
            target_keys=["title", "summary"],
            separator="\n---\n"
        )

        prompter = self.create_prompt(prompt=prompt)
        prompter.update_placeholder(text=text)

        return await prompter.acall(query=None, is_stream=True, postprocessor=pp)

    async def demo_output_mode_both(self, text: str):
        """
        示例5: output_mode="both" 模式

        - 流式输出: 目标值（用户实时看到提取的内容）
        - 响应返回: 原始 JSON（程序拿到完整 JSON 做后续处理）

        适用场景：前端展示提取内容，后端保存原始 JSON
        """
        prompt = (
            "请分析文本，输出 JSON 格式，包含 content 和 metadata 字段。\n"
            "文本: {{ text }}\n"
            "直接返回 JSON。"
        )

        pp = JsonKeyExtractorPP(
            target_key="content",
            output_mode="both"  # 流式输出目标值，响应返回原始 JSON
        )

        prompter = self.create_prompt(prompt=prompt)
        prompter.update_placeholder(text=text)

        return await prompter.acall(query=None, is_stream=True, postprocessor=pp)


async def main():
    # 配置 LLM（请替换为你的配置）
    llm = OpenAILike(
        api_key="sk-68ac5f5ccf3540ba834deeeaecb48987",
        base_url="https://dashscope.aliyuncs.com/compatible-mode/v1",
        model_name="qwen-plus"
    )

    agent = DemoAgent(llm=llm)
    test_text = "这家餐厅的牛排非常好吃，环境优雅，但上菜有点慢。"

    print("=" * 60)
    print("示例1: 单个 key 提取")
    print("=" * 60)
    result = await agent.demo_single_key(test_text)
    print(f"\n返回结果: {result}\n")

    print("=" * 60)
    print("示例2: 嵌套 key 提取 (data.result.content)")
    print("=" * 60)
    result = await agent.demo_nested_key(test_text)
    print(f"\n返回结果: {result}\n")

    print("=" * 60)
    print("示例3: 数组索引提取 (items[0].name)")
    print("=" * 60)
    result = await agent.demo_array_index(test_text)
    print(f"\n返回结果: {result}\n")

    print("=" * 60)
    print("示例4: 多 key 提取 ([title, summary])")
    print("=" * 60)
    result = await agent.demo_multi_keys(test_text)
    print(f"\n返回结果: {result}\n")

    print("=" * 60)
    print("示例5: output_mode='both'")
    print("=" * 60)
    result = await agent.demo_output_mode_both(test_text)
    print(f"\n返回结果 (原始JSON): {result}\n")


if __name__ == "__main__":
    asyncio.run(main())