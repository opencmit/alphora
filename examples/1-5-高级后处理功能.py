"""
高级后处理功能示例

这个示例展示了如何使用各种后处理器的高级特性以及它们的复杂组合来处理智能体的输出。

主要功能：
1. 模式匹配后处理器（PatternMatcherPP）的使用
2. 动态内容类型检测（DynamicTypePP）
3. 字符拆分（SplitterPP）和过滤（FilterPP）
4. 内容类型映射（TypeMapperPP）
5. 复杂后处理器链的组合
"""

import asyncio
from alphora.agent.base import BaseAgent
from alphora.models.llms import OpenAILike
from alphora.postprocess import (
    JsonKeyExtractorPP, FilterPP, ReplacePP, PatternMatcherPP, 
    DynamicTypePP, SplitterPP, TypeMapperPP
)


class AdvancedPostProcessAgent(BaseAgent):
    """高级后处理智能体，展示各种后处理器的组合使用"""

    async def pattern_matching_example(self, topic):
        """模式匹配后处理器示例"""
        print("\n1. 模式匹配后处理器示例")
        print("=" * 50)
        
        prompt = f"请介绍一下{topic}的优缺点。\n" \
                "优点请用[优点]开头，[/优点]结尾；\n" \
                "缺点请用[缺点]开头，[/缺点]结尾。"

        # 创建模式匹配后处理器，提取优缺点内容
        pattern_pp = PatternMatcherPP(
            bos="[优点]", 
            eos="[/优点]",
            include_bos=False,
            include_eos=False,
            output_mode="only_matched",
            matched_type="advantage"
        )
        
        prompter = self.create_prompt(prompt=prompt)
        response = await prompter.acall(is_stream=True, postprocessor=pattern_pp)
        
        print(f"{topic}的优点：", response)
        return response

    async def dynamic_type_detection(self, question):
        """动态内容类型检测示例"""
        print("\n2. 动态内容类型检测示例")
        print("=" * 50)
        
        prompt = f"请回答问题：{question}"

        # 创建动态类型检测器，根据标点符号设置内容类型
        dynamic_type_pp = DynamicTypePP(
            char_to_content_type={"?": "question", "!": "exclamation", ".": "statement"},
            default_content_type="other"
        )
        
        prompter = self.create_prompt(prompt=prompt)
        
        # 使用流式处理来展示内容类型变化
        async def stream_handler(chunk, **kwargs):
            print(f"内容: {chunk}, 类型: {kwargs.get('content_type', 'unknown')}")
            return chunk
        
        response = await prompter.acall(
            is_stream=True, 
            postprocessor=dynamic_type_pp,
            stream_handler=stream_handler
        )
        
        print(f"完整回答：", response)
        return response

    async def complex_postprocess_chain(self, product_name):
        """复杂后处理器链示例"""
        print("\n3. 复杂后处理器链示例")
        print("=" * 50)
        
        prompt = f"请提供关于{product_name}的详细信息，包括：名称、价格、分类和描述。\n" \
                "请以JSON格式返回，包含name、price、category和description字段。"

        # 创建后处理器链：
        # 1. 替换产品名称
        # 2. 提取description字段
        # 3. 过滤特殊字符
        # 4. 将内容拆分为单个字符
        postprocess_chain = (
            ReplacePP(replace_map={product_name: "该产品"}) \
            >> JsonKeyExtractorPP(target_key="description") \
            >> FilterPP(filter_chars="!?*") \
            >> SplitterPP()
        )
        
        prompter = self.create_prompt(prompt=prompt)
        
        # 使用流式处理来展示字符级输出
        async def char_stream_handler(chunk, **kwargs):
            print(chunk, end="", flush=True)
            return chunk
        
        print("字符级输出：")
        response = await prompter.acall(
            is_stream=True, 
            force_json=True, 
            postprocessor=postprocess_chain,
            stream_handler=char_stream_handler
        )
        
        print(f"\n完整处理后结果：{response}")
        return response

    async def content_type_mapping(self, text):
        """内容类型映射示例"""
        print("\n4. 内容类型映射示例")
        print("=" * 50)
        
        prompt = f"请分析以下文本的情感：{text}"

        # 先使用动态类型检测，再使用类型映射将结果转换为标准格式
        postprocess_chain = (
            DynamicTypePP(char_to_content_type={"正面": "positive", "负面": "negative"}) \
            >> TypeMapperPP(mapping={"positive": "POSITIVE", "negative": "NEGATIVE"}) \
            >> FilterPP(include_content_types=["POSITIVE", "NEGATIVE"])
        )
        
        prompter = self.create_prompt(prompt=prompt)
        response = await prompter.acall(is_stream=True, postprocessor=postprocess_chain)
        
        print(f"文本情感分析结果：{response}")
        return response


async def main():
    print("===== 高级后处理功能示例 =====")

    # 配置LLM（使用阿里云通义千问作为示例）
    llm_api_key: str = 'sk-68ac5f5ccf3540ba834deeeaecb48987'  # 替换为您的API密钥
    llm_base_url: str = "https://dashscope.aliyuncs.com/compatible-mode/v1"
    llm_model_name: str = "qwen-plus"
    
    # 创建模型实例
    llm = OpenAILike(
        api_key=llm_api_key,
        base_url=llm_base_url,
        model_name=llm_model_name
    )
    
    # 初始化智能体
    agent = AdvancedPostProcessAgent(llm=llm)
    
    # 运行各种后处理示例
    await agent.pattern_matching_example("人工智能")
    await agent.dynamic_type_detection("什么是机器学习？")
    await agent.complex_postprocess_chain("智能手机")
    await agent.content_type_mapping("这部电影非常精彩，演员演技出色，但剧情有点拖沓。")
    
    print("\n===== 所有示例运行完成 =====")


if __name__ == "__main__":
    asyncio.run(main())