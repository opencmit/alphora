"""
后处理功能示例

这个示例展示了如何使用各种后处理器以及它们的组合来处理智能体的输出。

主要功能：
1. 基本后处理器使用（JsonKeyExtractorPP, FilterPP, ReplacePP）
2. 后处理器的组合（使用 | 操作符）
3. 同步和异步处理示例
"""

import asyncio
from alphora.agent.base import BaseAgent
from alphora.models.llms import OpenAILike
from alphora.postprocess import JsonKeyExtractorPP, FilterPP, ReplacePP
from alphora.memory import BaseMemory


class ProductInfoAgent(BaseAgent):
    """产品信息智能体，返回产品的JSON格式信息"""

    async def product_info(self, product_name):
        """获取产品信息"""
        prompt = "请提供关于{{ product_name }}的详细信息，包括：名称、价格、分类和描述。"
        prompt += "请以JSON格式返回，包含name、price、category和description字段。"

        json_pp = JsonKeyExtractorPP(target_key="description")
        replace_pp = ReplacePP(replace_map={"苹果": "华为"})

        complex_pp = replace_pp >> json_pp
        
        prompter = self.create_prompt(prompt=prompt)
        prompter.update_placeholder(product_name=product_name)
        resp = await prompter.acall(is_stream=True, force_json=True, postprocessor=complex_pp)
        print('完整输出：', resp)
        return resp


async def main():
    print("===== 后处理功能示例 =====\n")

    llm_api_key: str = 'sk-68ac5f5ccf3540ba834deeeaecb48987'  # 替换为您的API密钥
    llm_base_url: str = "https://dashscope.aliyuncs.com/compatible-mode/v1"
    llm_model_name: str = "qwen-plus"
    
    # 创建模型实例
    llm = OpenAILike(
        api_key=llm_api_key,
        base_url=llm_base_url,
        model_name=llm_model_name
    )
    
    # 1. JSON键提取示例
    print("1. JSON键提取示例")
    print("=" * 40)
    
    product_agent = ProductInfoAgent(llm=llm)

    # 获取产品信息
    response = await product_agent.product_info("苹果手机")
    pass


if __name__ == "__main__":
    asyncio.run(main())