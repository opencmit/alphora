"""
快速API部署示例

这个示例展示了如何使用快速API模块将智能体部署为符合OpenAI API规范的FastAPI服务。

主要功能：
1. 创建符合API部署要求的智能体
2. 配置API发布参数
3. 运行FastAPI服务
4. 支持流式和非流式响应
5. 会话记忆管理
"""

import asyncio
from alphora.agent.base import BaseAgent
from alphora.models.llms import OpenAILike
from alphora.server.quick_api import publish_agent_api, APIPublisherConfig
from alphora.server.openai_request_body import OpenAIRequest


class APIDeploymentAgent(BaseAgent):
    """可部署为API服务的智能体"""

    async def chat(self, request: OpenAIRequest):
        """处理聊天请求的核心方法
        
        Args:
            request: OpenAI规范的请求体对象
            
        Returns:
            智能体的回复内容
        """
        # 构建历史对话
        history = self.memory.build_history(
            memory_id=request.session_id or "default", 
            max_round=5
        )
        
        # 提取当前用户查询
        current_query = request.messages[-1].content if request.messages else ""
        
        # 创建包含历史对话的提示词
        prompt = self.create_prompt(
            prompt="你是一个友好的智能助手，请根据历史对话和当前问题用中文回答。\n\n" +
                   "历史对话：\n{{history}}\n\n" +
                   "当前问题：{{query}}"
        )
        
        # 更新提示词占位符
        prompt.update_placeholder(history=history, query=current_query)
        
        # 调用LLM获取回复
        response = await prompt.acall(
            is_stream=request.stream, 
            stream_handler=self.stream.callback.stream_write_openai
        )
        
        # 保存对话到记忆中
        self.memory.add_memory(
            memory_id=request.session_id or "default",
            role="用户", 
            content=current_query
        )
        self.memory.add_memory(
            memory_id=request.session_id or "default",
            role="助手", 
            content=response
        )
        
        return response


async def main():
    """
    主函数，演示API部署流程
    """
    print("===== 快速API部署示例 =====")
    
    # 配置LLM（使用阿里云通义千问作为示例）
    llm_api_key: str = 'sk-68ac5f5ccf3540ba834deeeaecb48987'  # 替换为您的API密钥
    llm_base_url: str = "https://dashscope.aliyuncs.com/compatible-mode/v1"
    llm_model_name: str = "qwen-plus"
    
    # 初始化LLM模型
    llm = OpenAILike(
        api_key=llm_api_key,
        base_url=llm_base_url,
        model_name=llm_model_name
    )
    
    # 初始化智能体
    agent = APIDeploymentAgent(llm=llm)
    
    # 配置API发布参数
    api_config = APIPublisherConfig(
        api_title="智能助手API",
        api_description="这是一个基于Alphora框架开发的智能助手API服务",
        path="/api/v1",  # API基础路径
        memory_ttl=3600,  # 记忆过期时间（秒）
        max_memory_items=100,  # 最大记忆项数量
        auto_clean_interval=600  # 自动清理间隔（秒）
    )
    
    print("\n1. 智能体和API配置信息")
    print("=" * 50)
    print(f"智能体类名: {agent.__class__.__name__}")
    print(f"暴露方法: chat")
    print(f"LLM模型: {llm_model_name}")
    print(f"API基础路径: {api_config.path}")
    print(f"完整接口路径: {api_config.path}/chat/completions")
    print(f"记忆TTL: {api_config.memory_ttl}秒")
    print(f"最大会话数: {api_config.max_memory_items}")
    
    # 创建FastAPI应用
    print("\n2. 创建FastAPI应用")
    print("=" * 50)
    app = publish_agent_api(
        agent=agent,
        method="chat",
        config=api_config
    )
    
    print("✅ FastAPI应用创建成功")
    
    # 这里可以运行FastAPI服务，但在示例中我们只展示创建过程
    print("\n3. API服务启动说明")
    print("=" * 50)
    print("要启动API服务，请在命令行中运行:")
    print("uvicorn 1-6-快速API部署示例:app --host 0.0.0.0 --port 8000")
    print("\n服务启动后，可以通过以下方式访问:")
    print("- API文档: http://localhost:8000/docs")
    print("- API端点: http://localhost:8000/api/v1/chat/completions")
    
    # API使用示例
    print("\n4. API使用示例")
    print("=" * 50)
    print("使用curl测试API:")
    print("\n非流式请求:")
    print('curl -X POST http://localhost:8000/api/v1/chat/completions \\')
    print('     -H "Content-Type: application/json" \\')
    print('     -d "{\"session_id\": \"user_001\",')
    print('         \"messages\": [')
    print('             {')
    print('                 \"role\": \"user\",')
    print('                 \"content\": \"什么是人工智能？\"')
    print('             }')
    print('         ],')
    print('         \"stream\": false')
    print('     }"')
    
    print("\n流式请求:")
    print('curl -X POST http://localhost:8000/api/v1/chat/completions \\')
    print('     -H "Content-Type: application/json" \\')
    print('     -d "{\"session_id\": \"user_001\",')
    print('         \"messages\": [')
    print('             {')
    print('                 \"role\": \"user\",')
    print('                 \"content\": \"请解释机器学习的基本概念\"')
    print('             }')
    print('         ],')
    print('         \"stream\": true')
    print('     }"')
    
    print("\n===== API部署示例完成 =====")


if __name__ == "__main__":
    # 运行异步主函数
    asyncio.run(main())