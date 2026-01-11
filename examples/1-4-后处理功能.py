"""
后处理功能示例

这个示例展示了如何使用各种后处理器以及它们的组合来处理智能体的输出。

主要功能：
1. 基本后处理器使用（JsonKeyExtractorPP, FilterPP, ReplacePP）
2. 后处理器的组合（使用 | 操作符）
3. 同步和异步处理示例
"""

import asyncio
from alphora.agent.base_agent import BaseAgent
from alphora.models.llms import OpenAILike
from alphora.postprocess import JsonKeyExtractorPP, ReplacePP
from alphora.memory import BaseMemory


class PostProcessAgent(BaseAgent):
    """产品信息智能体，返回产品的JSON格式信息"""

    async def sql_coder(self, query: str, school_name: str):

        prompt = ("请编写用户问题的SQL脚本（表名: sch_info, 列名: school, score, city, prov, is_211, is_985），"
                  "其中如涉及学校名称相关必须预留学校名称为 PLACEHOLDER，问题:{{ query }}，用json写，包含 sql, explain 两个key")

        replace_pp = ReplacePP(replace_map={"PLACEHOLDER": school_name})

        json_pp = JsonKeyExtractorPP(target_key="explain",
                                     stream_only_target=True,
                                     response_only_target=True)

        # 多个后处理可进行级联
        complex_pp = json_pp >> replace_pp

        prompter = self.create_prompt(prompt=prompt)
        resp = await prompter.acall(query=query, is_stream=True, postprocessor=complex_pp)
        return resp


async def main():
    print("===== 后处理功能示例 =====\n")

    llm_api_key: str = "sk-68ac5f5ccf3540ba834deeeaecb48987"
    llm_base_url: str = "https://dashscope.aliyuncs.com/compatible-mode/v1"
    llm_model_name: str = "qwen-plus"
    
    # 创建模型实例
    llm = OpenAILike(
        api_key=llm_api_key,
        base_url=llm_base_url,
        model_name=llm_model_name
    )

    pp_agent = PostProcessAgent(llm=llm)

    _ = await pp_agent.sql_coder(query='查询我学校是不是985', school_name='北京大学')

    pass


if __name__ == "__main__":
    asyncio.run(main())
