"""
Alphora Server Component - 服务器和API示例

本文件演示如何将Agent发布为API服务：
1. publish_agent_api 基础
2. 路由配置
3. 流式响应API
4. 认证和安全
5. 请求/响应格式
6. 中间件
7. 错误处理
8. 部署配置
9. 多Agent服务
10. 监控和日志

Server组件让你能够快速将Agent部署为生产级API服务
"""

import os
import asyncio
from typing import Optional, Dict, Any, List
from datetime import datetime

# 模拟导入（实际使用时需要安装相应依赖）
# from alphora.server import publish_agent_api, APIConfig, AuthConfig
# from alphora.agent import BaseAgent


# ============================================================
# 示例 1: publish_agent_api 基础
# ============================================================
def example_1_basic_api():
    """
    使用 publish_agent_api 快速发布Agent为API

    最简单的方式将Agent变成HTTP API服务
    """
    print("=" * 60)
    print("示例 1: publish_agent_api 基础")
    print("=" * 60)

    print("""
    from alphora.agent import BaseAgent
    from alphora.server import publish_agent_api
    
    # 创建Agent
    agent = BaseAgent(
        llm_api_key=os.getenv("LLM_API_KEY"),
        llm_base_url=os.getenv("LLM_BASE_URL"),
        default_llm=os.getenv("DEFAULT_LLM")
    )
    
    # 一行代码发布为API
    publish_agent_api(
        agent=agent,
        host="0.0.0.0",
        port=8000
    )
    
    # API现在运行在 http://localhost:8000
    """)

    print("\n默认提供的端点:")
    print("  POST /chat          - 单轮对话")
    print("  POST /chat/stream   - 流式对话")
    print("  GET  /health        - 健康检查")
    print("  GET  /info          - Agent信息")

    print("\n请求示例 (curl):")
    print("""
    curl -X POST http://localhost:8000/chat \\
      -H "Content-Type: application/json" \\
      -d '{"message": "你好，请介绍一下自己"}'
    """)


# ============================================================
# 示例 2: 自定义路由配置
# ============================================================
def example_2_custom_routes():
    """
    自定义API路由和端点
    """
    print("\n" + "=" * 60)
    print("示例 2: 自定义路由配置")
    print("=" * 60)

    print("""
    from alphora.server import publish_agent_api, APIConfig
    
    # API配置
    config = APIConfig(
        # 基础路由
        base_path="/api/v1",
        
        # 自定义端点
        endpoints={
            "chat": "/conversation",           # 改名为 /api/v1/conversation
            "stream": "/conversation/stream",  # 改名为 /api/v1/conversation/stream
            "health": "/status",               # 改名为 /api/v1/status
        },
        
        # 启用的功能
        enable_docs=True,          # 启用 Swagger 文档
        enable_cors=True,          # 启用 CORS
        enable_metrics=True,       # 启用 Prometheus 指标
        
        # 文档配置
        title="My AI Assistant API",
        description="基于Alphora构建的AI助手API",
        version="1.0.0"
    )
    
    publish_agent_api(agent=agent, config=config)
    """)

    print("\n自定义端点后的路由:")
    print("  POST /api/v1/conversation          - 对话")
    print("  POST /api/v1/conversation/stream   - 流式对话")
    print("  GET  /api/v1/status               - 健康检查")
    print("  GET  /api/v1/docs                 - Swagger文档")
    print("  GET  /api/v1/metrics              - Prometheus指标")


# ============================================================
# 示例 3: 流式响应API
# ============================================================
def example_3_streaming_api():
    """
    流式响应的API实现
    """
    print("\n" + "=" * 60)
    print("示例 3: 流式响应API")
    print("=" * 60)

    print("""
    # 服务端配置
    config = APIConfig(
        stream_format="sse",      # Server-Sent Events 格式
        # 或 stream_format="ndjson"  # Newline Delimited JSON
        stream_timeout=60,        # 流式超时时间（秒）
        chunk_size=100,           # 每块大小
    )
    
    publish_agent_api(agent=agent, config=config)
    """)

    print("\n流式请求示例:")
    print("""
    curl -X POST http://localhost:8000/chat/stream \\
      -H "Content-Type: application/json" \\
      -H "Accept: text/event-stream" \\
      -d '{"message": "写一篇关于AI的文章"}'
    """)

    print("\nSSE响应格式:")
    print("""
    data: {"type": "start", "id": "msg_001"}
    
    data: {"type": "content", "text": "人工"}
    
    data: {"type": "content", "text": "智能"}
    
    data: {"type": "content", "text": "是"}
    
    ...
    
    data: {"type": "end", "usage": {"tokens": 150}}
    """)

    print("\nPython客户端示例:")
    print("""
    import httpx
    
    async def stream_chat(message: str):
        async with httpx.AsyncClient() as client:
            async with client.stream(
                "POST",
                "http://localhost:8000/chat/stream",
                json={"message": message}
            ) as response:
                async for line in response.aiter_lines():
                    if line.startswith("data: "):
                        data = json.loads(line[6:])
                        if data["type"] == "content":
                            print(data["text"], end="", flush=True)
    
    asyncio.run(stream_chat("你好"))
    """)


# ============================================================
# 示例 4: 认证和安全
# ============================================================
def example_4_authentication():
    """
    API认证和安全配置
    """
    print("\n" + "=" * 60)
    print("示例 4: 认证和安全")
    print("=" * 60)

    print("""
    from alphora.server import publish_agent_api, APIConfig, AuthConfig
    
    # 认证配置
    auth_config = AuthConfig(
        # API Key 认证
        api_key_enabled=True,
        api_keys=["sk-key1", "sk-key2"],  # 有效的API密钥
        api_key_header="X-API-Key",        # 密钥头名称
        
        # JWT 认证
        jwt_enabled=False,
        jwt_secret="your-secret-key",
        jwt_algorithm="HS256",
        
        # 速率限制
        rate_limit_enabled=True,
        rate_limit_requests=100,   # 每个时间窗口最大请求数
        rate_limit_window=60,      # 时间窗口（秒）
        
        # IP 白名单
        ip_whitelist=["127.0.0.1", "10.0.0.0/8"],
        
        # HTTPS
        ssl_enabled=True,
        ssl_cert_path="/path/to/cert.pem",
        ssl_key_path="/path/to/key.pem"
    )
    
    config = APIConfig(auth=auth_config)
    publish_agent_api(agent=agent, config=config)
    """)

    print("\n带认证的请求:")
    print("""
    curl -X POST http://localhost:8000/chat \\
      -H "Content-Type: application/json" \\
      -H "X-API-Key: sk-key1" \\
      -d '{"message": "你好"}'
    """)

    print("\n认证失败响应:")
    print("""
    {
        "error": "unauthorized",
        "message": "Invalid or missing API key",
        "status_code": 401
    }
    """)

    print("\n速率限制响应:")
    print("""
    {
        "error": "rate_limit_exceeded",
        "message": "Too many requests. Please retry after 60 seconds.",
        "retry_after": 60,
        "status_code": 429
    }
    """)


# ============================================================
# 示例 5: 请求/响应格式
# ============================================================
def example_5_request_response():
    """
    API的请求和响应格式详解
    """
    print("\n" + "=" * 60)
    print("示例 5: 请求/响应格式")
    print("=" * 60)

    print("\n=== 对话请求 ===")
    print("""
    POST /chat
    
    请求体:
    {
        "message": "你好，请帮我写一段Python代码",
        "session_id": "sess_001",           // 可选，会话ID
        "context": {                        // 可选，上下文
            "user_name": "张三",
            "preferences": {"language": "zh-CN"}
        },
        "options": {                        // 可选，生成选项
            "temperature": 0.7,
            "max_tokens": 1000,
            "stream": false
        }
    }
    
    响应体:
    {
        "id": "msg_abc123",
        "message": "好的，这是一段Python代码...",
        "session_id": "sess_001",
        "created_at": "2024-01-15T10:30:00Z",
        "usage": {
            "prompt_tokens": 50,
            "completion_tokens": 200,
            "total_tokens": 250
        },
        "model": "gpt-4",
        "finish_reason": "stop"
    }
    """)

    print("\n=== 多轮对话 ===")
    print("""
    POST /chat
    
    请求体:
    {
        "messages": [
            {"role": "user", "content": "你好"},
            {"role": "assistant", "content": "你好！有什么可以帮你的？"},
            {"role": "user", "content": "帮我写代码"}
        ],
        "session_id": "sess_001"
    }
    """)

    print("\n=== 带工具调用 ===")
    print("""
    POST /chat
    
    请求体:
    {
        "message": "北京今天天气怎么样？",
        "tools": ["weather", "search"],   // 启用的工具
        "tool_choice": "auto"             // auto, required, none
    }
    
    响应体（包含工具调用）:
    {
        "id": "msg_abc123",
        "message": "北京今天晴，气温15°C...",
        "tool_calls": [
            {
                "tool": "weather",
                "arguments": {"city": "北京"},
                "result": {"temp": 15, "condition": "晴"}
            }
        ]
    }
    """)


# ============================================================
# 示例 6: 中间件
# ============================================================
def example_6_middleware():
    """
    自定义中间件
    """
    print("\n" + "=" * 60)
    print("示例 6: 中间件")
    print("=" * 60)

    print("""
    from alphora.server import publish_agent_api, Middleware
    
    # 日志中间件
    class LoggingMiddleware(Middleware):
        async def process(self, request, call_next):
            start_time = time.time()
            
            # 记录请求
            print(f"[{datetime.now()}] {request.method} {request.url}")
            
            # 调用下一个处理器
            response = await call_next(request)
            
            # 记录响应
            duration = time.time() - start_time
            print(f"  -> {response.status_code} ({duration:.2f}s)")
            
            return response
    
    # 请求验证中间件
    class ValidationMiddleware(Middleware):
        async def process(self, request, call_next):
            # 验证请求体
            body = await request.json()
            if "message" not in body and "messages" not in body:
                return JSONResponse(
                    {"error": "message is required"},
                    status_code=400
                )
            
            return await call_next(request)
    
    # 响应转换中间件
    class ResponseTransformMiddleware(Middleware):
        async def process(self, request, call_next):
            response = await call_next(request)
            
            # 添加自定义头
            response.headers["X-Request-ID"] = str(uuid.uuid4())
            response.headers["X-Processing-Time"] = str(time.time())
            
            return response
    
    # 应用中间件
    config = APIConfig(
        middlewares=[
            LoggingMiddleware(),
            ValidationMiddleware(),
            ResponseTransformMiddleware()
        ]
    )
    
    publish_agent_api(agent=agent, config=config)
    """)


# ============================================================
# 示例 7: 错误处理
# ============================================================
def example_7_error_handling():
    """
    API错误处理
    """
    print("\n" + "=" * 60)
    print("示例 7: 错误处理")
    print("=" * 60)

    print("""
    from alphora.server import publish_agent_api, APIConfig, ErrorHandler
    
    # 自定义错误处理器
    class CustomErrorHandler(ErrorHandler):
        def handle_validation_error(self, error):
            return {
                "error": "validation_error",
                "message": str(error),
                "status_code": 400
            }
        
        def handle_auth_error(self, error):
            return {
                "error": "authentication_failed",
                "message": "Please provide valid credentials",
                "status_code": 401
            }
        
        def handle_rate_limit_error(self, error):
            return {
                "error": "rate_limit_exceeded",
                "message": "Too many requests",
                "retry_after": error.retry_after,
                "status_code": 429
            }
        
        def handle_llm_error(self, error):
            return {
                "error": "llm_error",
                "message": "AI service temporarily unavailable",
                "status_code": 503
            }
        
        def handle_internal_error(self, error):
            # 记录错误日志
            logging.error(f"Internal error: {error}")
            
            return {
                "error": "internal_error",
                "message": "An unexpected error occurred",
                "status_code": 500
            }
    
    config = APIConfig(error_handler=CustomErrorHandler())
    publish_agent_api(agent=agent, config=config)
    """)

    print("\n标准错误响应格式:")
    print("""
    {
        "error": "error_type",
        "message": "Human readable error message",
        "details": {...},           // 可选，详细信息
        "request_id": "req_xxx",    // 请求ID
        "timestamp": "2024-01-15T10:30:00Z",
        "status_code": 400
    }
    """)


# ============================================================
# 示例 8: 部署配置
# ============================================================
def example_8_deployment():
    """
    生产环境部署配置
    """
    print("\n" + "=" * 60)
    print("示例 8: 部署配置")
    print("=" * 60)

    print("""
    from alphora.server import publish_agent_api, APIConfig, DeployConfig
    
    # 部署配置
    deploy_config = DeployConfig(
        # 服务器配置
        host="0.0.0.0",
        port=8000,
        workers=4,                  # 工作进程数
        
        # 性能配置
        keep_alive=120,            # Keep-Alive 超时
        max_requests=10000,        # 单个worker最大请求数
        max_requests_jitter=1000,  # 请求数抖动
        
        # 超时配置
        timeout_keep_alive=5,
        timeout_notify=30,
        
        # 日志配置
        access_log=True,
        log_level="info",
        log_format="%(asctime)s - %(levelname)s - %(message)s",
        
        # Gunicorn/Uvicorn 特定配置
        worker_class="uvicorn.workers.UvicornWorker",
        
        # 健康检查
        health_check_path="/health",
        health_check_interval=30
    )
    
    publish_agent_api(
        agent=agent,
        config=APIConfig(),
        deploy_config=deploy_config
    )
    """)

    print("\nDocker 部署:")
    print("""
    # Dockerfile
    FROM python:3.10-slim
    
    WORKDIR /app
    
    COPY requirements.txt .
    RUN pip install -r requirements.txt
    
    COPY . .
    
    EXPOSE 8000
    
    CMD ["python", "server.py"]
    """)

    print("\ndocker-compose.yml:")
    print("""
    version: '3.8'
    
    services:
      api:
        build: .
        ports:
          - "8000:8000"
        environment:
          - LLM_API_KEY=${LLM_API_KEY}
          - LLM_BASE_URL=${LLM_BASE_URL}
        volumes:
          - ./data:/app/data
        restart: unless-stopped
        healthcheck:
          test: ["CMD", "curl", "-f", "http://localhost:8000/health"]
          interval: 30s
          timeout: 10s
          retries: 3
    """)


# ============================================================
# 示例 9: 多Agent服务
# ============================================================
def example_9_multi_agent():
    """
    部署多个Agent在同一服务
    """
    print("\n" + "=" * 60)
    print("示例 9: 多Agent服务")
    print("=" * 60)

    print("""
    from alphora.agent import BaseAgent
    from alphora.server import publish_multi_agent_api, APIConfig
    
    # 创建多个Agent
    assistant_agent = BaseAgent(
        system_prompt="你是一个通用助手...",
        ...
    )
    
    coder_agent = BaseAgent(
        system_prompt="你是一个编程专家...",
        ...
    )
    
    writer_agent = BaseAgent(
        system_prompt="你是一个写作助手...",
        ...
    )
    
    # 发布多Agent服务
    publish_multi_agent_api(
        agents={
            "assistant": assistant_agent,
            "coder": coder_agent,
            "writer": writer_agent
        },
        config=APIConfig(
            base_path="/api/v1"
        )
    )
    """)

    print("\n多Agent端点:")
    print("  POST /api/v1/assistant/chat   - 通用助手")
    print("  POST /api/v1/coder/chat       - 编程专家")
    print("  POST /api/v1/writer/chat      - 写作助手")
    print("  GET  /api/v1/agents           - 列出所有Agent")

    print("\n请求示例:")
    print("""
    # 调用编程专家
    curl -X POST http://localhost:8000/api/v1/coder/chat \\
      -H "Content-Type: application/json" \\
      -d '{"message": "帮我写一个快速排序算法"}'
    
    # 调用写作助手
    curl -X POST http://localhost:8000/api/v1/writer/chat \\
      -H "Content-Type: application/json" \\
      -d '{"message": "帮我写一篇产品介绍"}'
    """)


# ============================================================
# 示例 10: 监控和日志
# ============================================================
def example_10_monitoring():
    """
    监控、指标和日志配置
    """
    print("\n" + "=" * 60)
    print("示例 10: 监控和日志")
    print("=" * 60)

    print("""
    from alphora.server import publish_agent_api, APIConfig, MonitorConfig
    
    # 监控配置
    monitor_config = MonitorConfig(
        # Prometheus 指标
        prometheus_enabled=True,
        prometheus_path="/metrics",
        
        # 自定义指标
        custom_metrics={
            "request_count": "counter",      # 请求计数
            "response_time": "histogram",    # 响应时间分布
            "token_usage": "counter",        # Token使用量
            "error_count": "counter",        # 错误计数
        },
        
        # 日志配置
        log_requests=True,           # 记录请求
        log_responses=True,          # 记录响应
        log_errors=True,             # 记录错误
        log_file="/var/log/api.log", # 日志文件
        log_rotation="daily",        # 日志轮转
        log_retention=30,            # 保留天数
        
        # 链路追踪
        tracing_enabled=True,
        tracing_service_name="alphora-api",
        tracing_endpoint="http://jaeger:14268/api/traces"
    )
    
    config = APIConfig(monitor=monitor_config)
    publish_agent_api(agent=agent, config=config)
    """)

    print("\nPrometheus 指标示例:")
    print("""
    # HELP api_requests_total Total API requests
    # TYPE api_requests_total counter
    api_requests_total{endpoint="/chat",method="POST"} 1234
    
    # HELP api_response_time_seconds Response time distribution
    # TYPE api_response_time_seconds histogram
    api_response_time_seconds_bucket{le="0.1"} 100
    api_response_time_seconds_bucket{le="0.5"} 500
    api_response_time_seconds_bucket{le="1.0"} 800
    
    # HELP api_token_usage_total Total tokens used
    # TYPE api_token_usage_total counter
    api_token_usage_total{type="prompt"} 50000
    api_token_usage_total{type="completion"} 100000
    """)

    print("\n日志格式示例:")
    print("""
    2024-01-15 10:30:00 INFO [req_abc123] POST /chat
    2024-01-15 10:30:00 INFO [req_abc123] User: 张三, Session: sess_001
    2024-01-15 10:30:01 INFO [req_abc123] Response: 200 OK (1.23s)
    2024-01-15 10:30:01 INFO [req_abc123] Tokens: prompt=50, completion=200
    """)


# ============================================================
# 主函数
# ============================================================
def main():
    """运行所有示例"""
    print("Alphora Server 服务器和API示例")
    print("=" * 60)

    example_1_basic_api()
    example_2_custom_routes()
    example_3_streaming_api()
    example_4_authentication()
    example_5_request_response()
    example_6_middleware()
    example_7_error_handling()
    example_8_deployment()
    example_9_multi_agent()
    example_10_monitoring()

    print("\n" + "=" * 60)
    print("所有服务器示例完成！")
    print("=" * 60)
    print("\n注意：以上示例代码展示了API的使用方式，")
    print("实际运行需要正确配置环境变量和依赖。")


if __name__ == "__main__":
    main()