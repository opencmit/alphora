from alphora.prompter.base import BasePrompt
from alphora.models.llms.openai_like import OpenAILike
import asyncio
import time

from alphora.prompter.postprocess.replace import ReplacePP

llm_api_key: str = 'sk-68ac5f5ccf3540ba834deeeaecb48987'
llm_base_url: str = "https://dashscope.aliyuncs.com/compatible-mode/v1"
llm_model_name: str = "qwen-plus"

llm1 = OpenAILike(api_key=llm_api_key, base_url=llm_base_url, model_name='qwen-plus')
llm2 = OpenAILike(api_key=llm_api_key, base_url=llm_base_url, model_name='deepseek-v3')

llm = llm1 + llm2

bp1 = BasePrompt(verbose=True)
bp2 = BasePrompt(verbose=True)

bp1.add_llm(model=llm)
bp2.add_llm(model=llm)

bp1.load_from_string(prompt='用中文介绍你自己并翻译英文:{{query}}')
bp2.load_from_string(prompt='用中文介绍你自己并翻译日文:{{query}}')

# rpp = ReplacePP(replace_map={' ': '※'})

bp = bp1 | bp2

bpac = bp.acall(
    query='AlphaData 2.0 产品全面更新，由 AlphaData 1.0 版本的单体架构升级至了微服务架构，实现流量统一管控、核心业务解耦、弹性扩展、多版本并行发布，同时极大提升了系统稳定性、可维护性和可扩展性。',
    # postprocessor=rpp,
    is_stream=True,
    force_json=True,
    return_generator=False)

# for i in bpac:
#     print(i)

x = asyncio.run(bpac)
