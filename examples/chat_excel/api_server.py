import uvicorn
from alphora.server.quick_api import publish_agent_api, APIPublisherConfig
from chatexcel.model_chatexcel import ChatExcel
from alphora.models.llms import OpenAILike

from load_configs import configs

llm = OpenAILike(
    base_url=configs['llm']['base_url'],
    model_name=configs['llm']['model_name'],
    api_key=configs['llm']['api_key'],
    max_tokens=8000
)

# 初始化一个Agent
agent = ChatExcel(llm=llm)

agent.update_config(key='workspace_dir', value=configs['workspace_dir'])

# 3. 配置 API 发布
api_conf = configs['agent_api']

# API发布配置信息
config = APIPublisherConfig(
    path=api_conf['path'],
    memory_ttl=api_conf['memory_ttl'],
    max_memory_items=api_conf['max_memory_items'],
    auto_clean_interval=api_conf['auto_clean_interval'],
    api_title=api_conf['title'],
    api_description=api_conf['description']
)

# 4. 发布 API
app = publish_agent_api(
    agent=agent,
    method="run_logic",
    config=config
)


if __name__ == "__main__":
    server_conf = configs['server']
    uvicorn.run(
        app,
        host=server_conf['host'],
        port=server_conf['port']
    )

