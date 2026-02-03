# Alphora Server

**快速 API 发布组件**

Server 是 Alphora 框架的 API 发布模块，提供一键将 Agent 发布为 OpenAI 兼容 API 的能力。它支持流式/非流式响应、会话记忆管理、自动过期清理等特性，让你只需几行代码就能将智能体应用对外提供服务。

## 特性

-  **一键发布** - 一行代码将 Agent 发布为 RESTful API
-  **OpenAI 兼容** - 完全兼容 OpenAI chat/completions 接口格式
-  **流式响应** - 支持 SSE 流式输出，实时返回生成内容
-  **会话管理** - 内置会话记忆池，支持多轮对话
-  **自动清理** - TTL 过期 + LRU 容量控制，自动清理过期会话
-  **实例隔离** - 每个请求创建独立 Agent 实例，避免状态污染

## 安装

```bash
pip install alphora
pip install fastapi uvicorn  # 依赖
```

## 快速开始

```python
import uvicorn
from alphora.server.quick_api import publish_agent_api, APIPublisherConfig
from alphora.agent import BaseAgent
from alphora.models.llms import OpenAILike

# 1. 创建 LLM
llm = OpenAILike(
    base_url="https://api.openai.com/v1",
    model_name="gpt-4",
    api_key="your-api-key"
)

# 2. 创建 Agent
agent = MyAgent(llm=llm)

# 3. 发布 API
app = publish_agent_api(
    agent=agent,
    method="run",  # Agent 的异步方法名
)

# 4. 启动服务
if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)
```

启动后访问：`POST http://localhost:8000/alphadata/chat/completions`

## 目录

- [API 发布](#api-发布)
- [配置选项](#配置选项)
- [请求格式](#请求格式)
- [响应格式](#响应格式)
- [会话管理](#会话管理)
- [Agent 方法规范](#agent-方法规范)
- [流式响应](#流式响应)
- [完整示例](#完整示例)
- [API 参考](#api-参考)

---

## API 发布

### publish_agent_api

核心函数，将 Agent 发布为 FastAPI 应用。

```python
from alphora.server.quick_api import publish_agent_api

app = publish_agent_api(
    agent=agent,          # Agent 实例
    method="run",         # 要暴露的异步方法名
    config=config         # 可选配置
)
```

**参数说明**：

| 参数 | 类型 | 说明 |
|------|------|------|
| `agent` | `BaseAgent` | Agent 实例 |
| `method` | `str` | 要暴露的异步方法名 |
| `config` | `APIPublisherConfig` | API 配置（可选） |

**返回值**：FastAPI 应用实例，可直接用 uvicorn 运行。

### 启动服务

```python
import uvicorn

# 方式 1：直接运行
uvicorn.run(app, host="0.0.0.0", port=8000)

# 方式 2：命令行运行
# uvicorn api_server:app --host 0.0.0.0 --port 8000 --reload
```

---

## 配置选项

### APIPublisherConfig

```python
from alphora.server.quick_api import APIPublisherConfig

config = APIPublisherConfig(
    path="/alphadata",           # API 基础路径
    memory_ttl=3600,             # 会话过期时间（秒）
    max_memory_items=1000,       # 最大会话数
    auto_clean_interval=600,     # 自动清理间隔（秒）
    api_title="My Agent API",    # API 文档标题
    api_description="Agent API"  # API 文档描述
)

app = publish_agent_api(agent, "run", config=config)
```

**配置项说明**：

| 配置项 | 类型 | 默认值 | 说明 |
|--------|------|--------|------|
| `path` | `str` | `"/alphadata"` | API 基础路径，完整路径为 `{path}/chat/completions` |
| `memory_ttl` | `int` | `3600` | 会话记忆过期时间（秒） |
| `max_memory_items` | `int` | `1000` | 记忆池最大会话数 |
| `auto_clean_interval` | `int` | `600` | 自动清理间隔（秒） |
| `api_title` | `str` | `"Alphora Agent API Service"` | API 文档标题 |
| `api_description` | `str` | `"Auto-generated API..."` | API 文档描述 |

### 动态标题

支持在标题和描述中使用占位符：

```python
config = APIPublisherConfig(
    api_title="{agent_name} API Service",      # 会替换为 Agent 类名
    api_description="{agent_name}.{method_name} API"  # 会替换为方法名
)
```

---

## 请求格式

### OpenAIRequest

API 接收 OpenAI 兼容格式的请求：

```json
{
    "model": "gpt-4",
    "messages": [
        {"role": "system", "content": "You are a helpful assistant."},
        {"role": "user", "content": "你好"}
    ],
    "stream": true,
    "session_id": "user-session-001",
    "user": "user-123"
}
```

**字段说明**：

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `model` | `str` | 否 | 模型名称（可忽略，由 Agent 决定） |
| `messages` | `List[Message]` | 否 | 消息列表 |
| `stream` | `bool` | 否 | 是否流式响应，默认 `true` |
| `session_id` | `str` | 否 | 会话 ID，用于多轮对话 |
| `user` | `str` | 否 | 用户标识 |

### Message 格式

```python
{
    "role": "user",      # system / user / assistant
    "content": "你好"    # 字符串或复杂对象
}
```

### 使用 curl 调用

```bash
# 流式请求
curl -X POST http://localhost:8000/alphadata/chat/completions \
  -H "Content-Type: application/json" \
  -d '{
    "messages": [{"role": "user", "content": "你好"}],
    "stream": true,
    "session_id": "test-session"
  }'

# 非流式请求
curl -X POST http://localhost:8000/alphadata/chat/completions \
  -H "Content-Type: application/json" \
  -d '{
    "messages": [{"role": "user", "content": "你好"}],
    "stream": false
  }'
```

### 使用 Python 调用

```python
import requests

# 非流式
response = requests.post(
    "http://localhost:8000/alphadata/chat/completions",
    json={
        "messages": [{"role": "user", "content": "你好"}],
        "stream": False,
        "session_id": "my-session"
    }
)
print(response.json())

# 流式
response = requests.post(
    "http://localhost:8000/alphadata/chat/completions",
    json={
        "messages": [{"role": "user", "content": "你好"}],
        "stream": True
    },
    stream=True
)
for line in response.iter_lines():
    if line:
        print(line.decode())
```

### 使用 OpenAI SDK 调用

```python
from openai import OpenAI

client = OpenAI(
    base_url="http://localhost:8000/alphadata",
    api_key="not-needed"  # 如果不需要认证
)

# 流式
stream = client.chat.completions.create(
    model="agent",
    messages=[{"role": "user", "content": "你好"}],
    stream=True,
    extra_body={"session_id": "my-session"}
)

for chunk in stream:
    if chunk.choices[0].delta.content:
        print(chunk.choices[0].delta.content, end="")
```

---

## 响应格式

### 流式响应（SSE）

流式响应使用 Server-Sent Events (SSE) 格式：

```
data: {"id":"cmpl-xxx","object":"chat.completion.chunk","created":1234567890,"model":"AlphaData","choices":[{"index":0,"delta":{"content":"你","content_type":"text"},"finish_reason":null}]}

data: {"id":"cmpl-xxx","object":"chat.completion.chunk","created":1234567890,"model":"AlphaData","choices":[{"index":0,"delta":{"content":"好","content_type":"text"},"finish_reason":null}]}

data: {"id":"cmpl-xxx","object":"chat.completion.chunk","created":1234567890,"model":"AlphaData","choices":[{"index":0,"delta":{"content":"","content_type":"stop"},"finish_reason":"stop"}]}
```

**字段说明**：

| 字段 | 说明 |
|------|------|
| `id` | 响应唯一标识 |
| `object` | 固定为 `chat.completion.chunk` |
| `created` | 创建时间戳 |
| `model` | 模型名称 |
| `choices[0].delta.content` | 内容片段 |
| `choices[0].delta.content_type` | 内容类型 |
| `choices[0].finish_reason` | 结束原因：`stop` / `timeout` |

### 非流式响应

非流式响应返回完整 JSON，内容按类型聚合为 XML 格式：

```json
{
    "id": "cmpl-xxx",
    "object": "chat.completion",
    "created": 1234567890,
    "model": "AlphaData",
    "choices": [{
        "index": 0,
        "delta": {
            "content": "<content type=\"text\">你好！有什么可以帮助你的？</content><content type=\"thinking\">用户在打招呼</content>",
            "content_type": "mixed-xml"
        },
        "finish_reason": "stop"
    }]
}
```

### 内容类型

Agent 可以输出不同类型的内容：

| content_type | 说明 |
|--------------|------|
| `text` | 普通文本 |
| `thinking` | 思考过程 |
| `code` | 代码块 |
| `tool_call` | 工具调用 |
| `stop` | 结束标记 |
| `mixed-xml` | 非流式响应的聚合格式 |

---

## 会话管理

### 会话记忆池

Server 内置会话记忆池，自动管理多轮对话的上下文：

```python
config = APIPublisherConfig(
    memory_ttl=3600,         # 会话 1 小时后过期
    max_memory_items=1000,   # 最多保存 1000 个会话
    auto_clean_interval=600  # 每 10 分钟清理一次
)
```

### 会话 ID

通过 `session_id` 字段实现多轮对话：

```python
# 第一轮对话
requests.post(url, json={
    "messages": [{"role": "user", "content": "我叫张三"}],
    "session_id": "user-001"
})

# 第二轮对话（同一会话）
requests.post(url, json={
    "messages": [{"role": "user", "content": "我叫什么名字？"}],
    "session_id": "user-001"  # 相同的 session_id
})
# Agent 会记住上文，回答"张三"
```

### 清理策略

记忆池采用双重清理策略：

1. **TTL 过期清理**：超过 `memory_ttl` 未访问的会话自动清理
2. **LRU 容量控制**：超过 `max_memory_items` 时，清理最久未访问的会话

### 自定义 Memory 类

Agent 可以指定默认的 Memory 类：

```python
from alphora.agent import BaseAgent
from alphora.memory import MemoryManager

class MyAgent(BaseAgent):
    default_memory_cls = MemoryManager  # 自定义 Memory 类
    
    async def run(self, request: OpenAIRequest):
        # self.memory 会自动使用 default_memory_cls 创建
        pass
```

---

## Agent 方法规范

### 方法签名

暴露的 Agent 方法必须满足以下要求：

```python
from alphora.server.openai_request_body import OpenAIRequest

class MyAgent(BaseAgent):
    async def run(self, request: OpenAIRequest):
        """
        必须是：
        1. async def 定义的异步方法
        2. 只有一个参数
        3. 参数类型注解为 OpenAIRequest
        """
        pass
```

### 使用 OpenAIRequest

```python
async def run(self, request: OpenAIRequest):
    # 获取用户输入
    user_query = request.get_user_query()
    
    # 获取所有消息
    messages = request.messages
    
    # 获取会话 ID
    session_id = request.session_id
    
    # 获取请求头
    auth_header = request.get_header("Authorization")
    all_headers = request.get_header()  # 获取所有头
    
    # 检查是否流式
    is_stream = request.stream
    
    # 获取额外字段（OpenAIRequest 允许额外字段）
    custom_field = getattr(request, 'custom_field', None)
```

### 发送响应

通过 Agent 的 `stream` 对象发送响应：

```python
async def run(self, request: OpenAIRequest):
    user_query = request.get_user_query()
    
    # 发送思考过程
    await self.stream.send("thinking", "正在分析问题...")
    
    # 发送正文
    await self.stream.send("text", "这是回答的内容")
    
    # 发送代码
    await self.stream.send("code", "print('Hello')")
    
    # 结束响应
    await self.stream.stop()
```

---

## 流式响应

### DataStreamer

Server 使用 `DataStreamer` 处理流式响应：

```python
from alphora.server.stream_responser import DataStreamer

streamer = DataStreamer(timeout=300, model_name="MyModel")

# 发送数据
await streamer.send_data(content_type="text", content="Hello")

# 结束流
await streamer.stop(stop_reason="stop")

# 获取流式响应
response = streamer.start_streaming_openai()

# 获取非流式响应
response = await streamer.start_non_streaming_openai()
```

### 超时处理

默认超时 300 秒（5 分钟）。超时后自动返回 `finish_reason: "timeout"`：

```python
streamer = DataStreamer(timeout=60)  # 1 分钟超时
```

---

## 完整示例

### 基础 Agent API

```python
# my_agent.py
from alphora.agent import BaseAgent
from alphora.server.openai_request_body import OpenAIRequest

class MyAgent(BaseAgent):
    async def run(self, request: OpenAIRequest):
        """处理用户请求"""
        user_query = request.get_user_query()
        
        # 记录到会话历史
        self.memory.add_user(user_query)
        
        # 调用 LLM
        result = await self.llm.acall(
            messages=self.memory.build_history()
        )
        
        # 流式输出
        async for chunk in result:
            await self.stream.send("text", chunk.content)
        
        # 记录助手回复
        self.memory.add_assistant(result.response)
        
        # 结束
        await self.stream.stop()
```

```python
# api_server.py
import uvicorn
from alphora.server.quick_api import publish_agent_api, APIPublisherConfig
from alphora.models.llms import OpenAILike
from my_agent import MyAgent

# 初始化
llm = OpenAILike(
    base_url="https://api.openai.com/v1",
    model_name="gpt-4",
    api_key="your-api-key"
)

agent = MyAgent(llm=llm)

# 配置
config = APIPublisherConfig(
    path="/api/v1",
    memory_ttl=7200,        # 2 小时
    max_memory_items=500,
    api_title="My Agent API",
    api_description="智能助手 API 服务"
)

# 发布
app = publish_agent_api(agent=agent, method="run", config=config)

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)
```

### 带工具的 Agent API

```python
from alphora.agent import BaseAgent
from alphora.tools import tool, ToolRegistry, ToolExecutor
from alphora.server.openai_request_body import OpenAIRequest

@tool
def search_web(query: str) -> str:
    """搜索网络"""
    return f"搜索结果: {query}"

class ToolAgent(BaseAgent):
    def __init__(self, llm):
        super().__init__(llm=llm)
        self.registry = ToolRegistry()
        self.registry.register(search_web)
        self.executor = ToolExecutor(self.registry)
    
    async def run(self, request: OpenAIRequest):
        user_query = request.get_user_query()
        self.memory.add_user(user_query)
        
        # 调用 LLM（带工具）
        result = await self.llm.acall(
            messages=self.memory.build_history(),
            tools=self.registry.get_all_tools()
        )
        
        # 处理工具调用
        if result.has_tool_calls:
            await self.stream.send("thinking", "正在调用工具...")
            tool_results = await self.executor.execute(result.tool_calls)
            self.memory.add_assistant(result)
            self.memory.add_tool_result(tool_results)
            
            # 继续对话
            final_result = await self.llm.acall(
                messages=self.memory.build_history()
            )
            async for chunk in final_result:
                await self.stream.send("text", chunk.content)
            self.memory.add_assistant(final_result)
        else:
            async for chunk in result:
                await self.stream.send("text", chunk.content)
            self.memory.add_assistant(result)
        
        await self.stream.stop()
```

### 生产环境配置

```python
import logging
from alphora.server.quick_api import publish_agent_api, APIPublisherConfig

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

config = APIPublisherConfig(
    path="/api/v1",
    memory_ttl=3600,           # 1 小时会话过期
    max_memory_items=10000,    # 支持 1 万并发会话
    auto_clean_interval=300,   # 5 分钟清理一次
    api_title="Production Agent API",
    api_description="生产环境智能助手服务"
)

app = publish_agent_api(agent=agent, method="run", config=config)

# 使用 Gunicorn 部署
# gunicorn api_server:app -w 4 -k uvicorn.workers.UvicornWorker -b 0.0.0.0:8000
```

---

## API 参考

### publish_agent_api

```python
def publish_agent_api(
    agent: BaseAgent,
    method: str,
    config: Optional[APIPublisherConfig] = None
) -> FastAPI
```

| 参数 | 类型 | 说明 |
|------|------|------|
| `agent` | `BaseAgent` | Agent 实例 |
| `method` | `str` | 要暴露的异步方法名 |
| `config` | `APIPublisherConfig` | API 配置 |

### APIPublisherConfig

| 属性 | 类型 | 默认值 | 说明 |
|------|------|--------|------|
| `path` | `str` | `"/alphadata"` | API 基础路径 |
| `memory_ttl` | `int` | `3600` | 会话过期时间（秒） |
| `max_memory_items` | `int` | `1000` | 最大会话数 |
| `auto_clean_interval` | `int` | `600` | 清理间隔（秒） |
| `api_title` | `str` | `"Alphora Agent API Service"` | API 标题 |
| `api_description` | `str` | `"Auto-generated API..."` | API 描述 |

### OpenAIRequest

| 属性/方法 | 类型 | 说明 |
|----------|------|------|
| `model` | `str` | 模型名称 |
| `messages` | `List[Message]` | 消息列表 |
| `stream` | `bool` | 是否流式 |
| `session_id` | `str` | 会话 ID |
| `user` | `str` | 用户标识 |
| `get_user_query()` | `str` | 获取用户输入 |
| `get_header(key)` | `Any` | 获取请求头 |
| `set_headers(headers)` | `None` | 设置请求头 |

### MemoryPool

| 方法 | 说明 |
|------|------|
| `get_or_create(session_id, memory_cls)` | 获取或创建会话记忆 |
| `clean_expired()` | 清理过期会话 |
| `size` | 当前会话数 |

### DataStreamer

| 方法 | 说明 |
|------|------|
| `send_data(content_type, content)` | 发送数据 |
| `stop(stop_reason)` | 结束流 |
| `start_streaming_openai()` | 返回流式响应 |
| `start_non_streaming_openai()` | 返回非流式响应 |

### 异常类

| 异常 | 说明 |
|------|------|
| `AgentValidationError` | Agent 校验失败（类型错误、方法不存在等） |
