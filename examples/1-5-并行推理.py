import asyncio
from typing import List
from alphora.agent.base import BaseAgent
from alphora.models.llms import OpenAILike
from alphora.postprocess import JsonKeyExtractorPP, ReplacePP
from alphora.memory import BaseMemory
from alphora.prompter.parallel import ParallelPrompt


class ParallelAgent(BaseAgent):
    """产品信息智能体，返回产品的JSON格式信息"""

    async def translate(self, query: str, target_languages: List[str]):

        prompt = "请将{{query}}翻译为{{target_language}}"

        prompts = [
            self.create_prompt(prompt=prompt, content_type=target_lang).
            update_placeholder(target_language=target_lang)
            for target_lang in target_languages
        ]

        replace_pp = ReplacePP(replace_map={"China": "***"})

        parallel_prompt = ParallelPrompt(prompts=prompts)

        resp = await parallel_prompt.acall(query=query, is_stream=True, postprocessor=replace_pp)

        return resp


async def main():
    print("===== 后处理功能示例 =====\n")

    llm_api_key: str = 'sk-68ac5f5ccf3540ba834deeeaecb48987'
    llm_base_url: str = "https://dashscope.aliyuncs.com/compatible-mode/v1"
    llm_model_name: str = "qwen-plus"
    
    # 创建模型实例
    llm = OpenAILike(
        api_key=llm_api_key,
        base_url=llm_base_url,
        model_name=llm_model_name
    )

    pp_agent = ParallelAgent(llm=llm)

    _ = await pp_agent.translate(query='中国的首都是北京', target_languages=['en', 'ko', 'jp', 'es'])

    pass


if __name__ == "__main__":
    asyncio.run(main())
