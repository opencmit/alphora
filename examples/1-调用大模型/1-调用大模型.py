from alphora.models.llms.openai_like import OpenAILike


llm_api_key: str = 'sk-68ac5f5ccf3540ba834deeeaecb48987'
llm_base_url: str = "https://dashscope.aliyuncs.com/compatible-mode/v1"
# llm_model_name: str = "deepseek-v3"
# llm_model_name: str = "Moonshot-Kimi-K2-Instruct"
llm_model_name: str = "qwen-plus"


llm = OpenAILike(api_key=llm_api_key, base_url=llm_base_url, model_name=llm_model_name)

# llm.invoke(message='111')
print(llm.invoke(message='介绍自己用10个字'))
