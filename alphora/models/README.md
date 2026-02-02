# Alphora Models

**大语言模型统一接口组件**

Models 是 Alphora 框架的模型抽象层，提供统一的 LLM 调用接口。它兼容 OpenAI API 规范，支持多模态输入、流式输出、负载均衡、工具调用等特性，并集成调试追踪能力。

## 特性

- 🔌 **OpenAI 兼容** - 完全兼容 OpenAI Chat Completion API
- 🖼 **多模态支持** - 统一的图片、音频、视频消息处理
- 📡 **双模式输出** - 支持流式和非流式响应
- ⚖️ **负载均衡** - 内置轮询/随机策略的多后端负载均衡
- 🛠 **工具调用** - 完整的 Function Calling 支持
- 🔍 **调试追踪** - 请求/响应/Token 统计自动追踪
- 🧩 **可扩展** - 易于扩展支持新的模型提供商
- 📊 **Embedding** - 统一的文本向量化接口

## 安装

```bash
pip install alphora
```

## 快速开始

```python
from alphora.models import OpenAILike, Qwen

# 创建模型实例
llm = OpenAILike(
    model_name="gpt-4",
    api_key="your-api-key",
    base_url="https://api.openai.com/v1"
)

# 简单调用
response = await llm.ainvoke("你好！")
print(response)

# 流式调用
generator = await llm.astream("写一首诗")
async for chunk in generator:
    print(chunk.content, end="")
```

## 目录

- [基础用法](#基础用法)
- [消息格式](#消息格式)
- [流式输出](#流式输出)
- [工具调用](#工具调用)
- [负载均衡](#负载均衡)
- [模型变体](#模型变体)
- [文本向量化](#文本向量化)
- [调试追踪](#调试追踪)
- [API 参考](#api-参考)

---

## 基础用法

### 创建模型实例

```python
from alphora.models import OpenAILike

# 基础配置
llm = OpenAILike(
    model_name="gpt-4",
    api_key="your-api-key",
    base_url="https://api.openai.com/v1"
)

# 完整配置
llm = OpenAILike(
    model_name="gpt-4",
    api_key="your-api-key",
    base_url="https://api.openai.com/v1",
    temperature=0.7,
    max_tokens=2048,
    top_p=0.9,
    header={"X-Custom-Header": "value"},
    is_multimodal=True
)

# 从环境变量读取
# 设置 LLM_API_KEY, LLM_BASE_URL, DEFAULT_LLM
llm = OpenAILike()
```

### 同步调用

```python
# 简单调用
response = llm.invoke("你好")
print(response)

# 流式调用
generator = llm.stream("写一篇文章")
for chunk in generator:
    print(chunk.content, end="")
```

### 异步调用

```python
# 非流式
response = await llm.ainvoke("你好")

# 流式（推荐）
generator = await llm.astream("写一篇文章")
async for chunk in generator:
    print(chunk.content, end="")
```

### 参数调整

```python
# 运行时调整
llm.set_temperature(0.8)
llm.set_max_tokens(4096)
llm.set_top_p(0.95)
llm.set_model_name("gpt-4-turbo")

# 检查连接
if await llm.aping():
    print("模型连接正常")
```

---

## 消息格式

### Message 类

```python
from alphora.models.message import Message

# 创建文本消息
msg = Message().add_text("这是一段文字")

# 创建多模态消息
msg = Message()
msg.add_text("请描述这张图片")
msg.add_image(base64_data, format="png")

# 链式调用
msg = (Message()
    .add_text("分析以下内容")
    .add_image(image_data)
    .add_audio(audio_data, format="mp3", duration=30.0))
```

### 支持的媒体类型

#### 图片

```python
from alphora.models.message import Image

# 支持格式：png, jpg, jpeg, bmp, dib, icns, jpeg2000, tiff
msg.add_image(
    data="base64编码的图片数据",
    format="png"
)

# 获取 DataURL
image = Image(data=base64_data, format="jpg")
print(image.data_url)  # data:image/jpg;base64,...
```

#### 音频

```python
from alphora.models.message import Audio

# 支持格式：mp3, wav, ogg, flac, aac, m4a
msg.add_audio(
    data="base64编码的音频数据",
    format="mp3",
    duration=60.0  # 秒
)
```

#### 视频

```python
from alphora.models.message import Video

# 支持格式：mp4, webm, mov, avi, mkv, flv
msg.add_video(
    data="base64编码的视频数据",
    format="mp4",
    duration=120.0
)
```

### 消息检查

```python
msg = Message().add_text("你好").add_image(img_data)

# 检查内容类型
msg.has_text()    # True
msg.has_images()  # True
msg.has_audios()  # False
msg.has_videos()  # False

# 转为 OpenAI 格式
openai_msg = msg.to_openai_format(role="user")
# {
#     "role": "user",
#     "content": [
#         {"type": "text", "text": "你好"},
#         {"type": "image_url", "image_url": {"url": "data:image/png;base64,..."}}
#     ]
# }
```

### 使用消息调用

```python
# 创建多模态消息
msg = Message()
msg.add_text("这张图片里有什么？")
msg.add_image(image_base64, format="png")

# 调用（需要多模态模型）
response = await llm.ainvoke(msg)

# 或流式
generator = await llm.astream(msg)
```

---

## 流式输出

### 生成器结构

```python
from alphora.models.llms.stream_helper import GeneratorOutput

generator = await llm.astream("你好")

async for output in generator:
    content = output.content       # 文本内容
    content_type = output.content_type  # 内容类型
    
    if content_type == "think":
        print(f"[思考] {content}")
    else:
        print(content, end="")

# 获取结束原因
print(generator.finish_reason)  # stop, length, tool_calls
```

### 启用思考模式

```python
# 部分模型支持（如 Qwen3）
generator = await llm.aget_streaming_response(
    message="复杂问题",
    enable_thinking=True
)

reasoning = ""
content = ""

async for output in generator:
    if output.content_type == "think":
        reasoning += output.content
    else:
        content += output.content
```

### 自定义内容类型

```python
generator = await llm.aget_streaming_response(
    message="生成SQL查询",
    content_type="sql"  # 标记输出类型
)
```

---

## 工具调用

### 非流式工具调用

```python
from alphora.models.llms.types import ToolCall

# 定义工具
tools = [{
    "type": "function",
    "function": {
        "name": "get_weather",
        "description": "获取天气信息",
        "parameters": {
            "type": "object",
            "properties": {
                "city": {"type": "string", "description": "城市名"}
            },
            "required": ["city"]
        }
    }
}]

# 调用
response = await llm.aget_non_stream_response(
    message="北京天气怎么样？",
    tools=tools
)

# 检查工具调用
if isinstance(response, ToolCall) and response.has_tool_calls:
    for tc in response.tool_calls:
        print(tc["function"]["name"])
        print(tc["function"]["arguments"])
```

### 流式工具调用

```python
generator = await llm.aget_streaming_response(
    message="查询天气",
    tools=tools
)

# 消费流
async for chunk in generator:
    if chunk.content:
        print(chunk.content, end="")

# 流结束后获取工具调用
collected_tools = generator.collected_tool_calls
if collected_tools:
    tool_call = ToolCall(tool_calls=collected_tools)
    tool_call.pretty_print()
```

### ToolCall 对象

```python
from alphora.models.llms.types import ToolCall

# ToolCall 继承自 list，可迭代
for tc in tool_call:
    print(tc)

# 属性和方法
tool_call.has_tool_calls      # 是否有工具调用
tool_call.content             # 文本内容（可能为 None）
tool_call.tool_calls          # 工具调用列表
tool_call.get_tool_names()    # ['get_weather', 'search']
tool_call.get_tool_call_ids() # ['call_abc', 'call_def']

# 格式化输出
tool_call.pretty_print()
# 🔧 工具调用详情 (共 1 个)
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# [1] get_weather
#     ID: call_abc123
#     参数:
#       • city: "北京"

print(tool_call.to_summary())
# 调用 1 个工具: get_weather(city="北京")
```

---

## 负载均衡

### 添加多个后端

```python
from alphora.models import OpenAILike

# 主模型
llm = OpenAILike(
    model_name="gpt-4",
    api_key="key1",
    base_url="https://api1.example.com/v1"
)

# 添加备用模型（使用 + 运算符）
backup = OpenAILike(
    model_name="gpt-4",
    api_key="key2",
    base_url="https://api2.example.com/v1"
)

llm = llm + backup  # 自动负载均衡

# 调用时自动轮询
response = await llm.ainvoke("你好")
```

### 多模态负载均衡

```python
# 标记多模态支持
llm_text = OpenAILike(model_name="gpt-4", is_multimodal=False)
llm_vision = OpenAILike(model_name="gpt-4-vision", is_multimodal=True)

llm = llm_text + llm_vision

# 文本请求 - 两个后端都可用
response = await llm.ainvoke("你好")

# 多模态请求 - 只使用支持的后端
msg = Message().add_text("描述图片").add_image(img_data)
response = await llm.ainvoke(msg)  # 自动路由到 llm_vision
```

### 负载均衡策略

```python
from alphora.models.llms.balancer import _LLMLoadBalancer

# 轮询（默认）
balancer = _LLMLoadBalancer(strategy="round_robin")

# 随机
balancer = _LLMLoadBalancer(strategy="random")
```

---

## 模型变体

### Qwen（通义千问）

```python
from alphora.models import Qwen

# 使用 DashScope API
llm = Qwen(
    model_name="qwen-max",  # qwen-max, qwen-plus, qwen-turbo, qwen3-32b
    api_key="your-dashscope-key",
    temperature=0.7
)

# Qwen3 系列支持思考模式
llm = Qwen(model_name="qwen3-32b")
generator = await llm.astream(
    "复杂推理问题",
    enable_thinking=True
)
```

### DeepSeek

```python
from alphora.models.llms.deepseek import DeepSeek

llm = DeepSeek(
    model_name="deepseek-chat",
    api_key="your-deepseek-key"
)
```

### 自定义模型

```python
from alphora.models.llms.openai_like import OpenAILike

# 任何 OpenAI 兼容的 API
llm = OpenAILike(
    model_name="custom-model",
    api_key="your-key",
    base_url="https://your-api.com/v1"
)

# 继承实现自定义逻辑
class MyModel(OpenAILike):
    def _get_extra_body(self, enable_thinking=False):
        return {"custom_param": "value"}
```

---

## 文本向量化

### 基础使用

```python
from alphora.models.embedder import EmbeddingModel

embedder = EmbeddingModel(
    model="text-embedding-v3",
    api_key="your-key",
    base_url="https://dashscope.aliyuncs.com/compatible-mode/v1"
)

# 单文本
embedding = embedder.get_text_embedding("你好世界")
# [0.123, -0.456, ...]

# 批量（自动分批）
embeddings = embedder.get_text_embeddings(
    ["文本1", "文本2", "文本3"],
    max_batch=10
)
```

### 异步调用

```python
# 单文本
embedding = await embedder.aget_text_embedding("你好")

# 批量
embeddings = await embedder.aget_text_embeddings(["文本1", "文本2"])
```

### 连接检查

```python
# 同步
if embedder.ping():
    print("Embedding 服务正常")

# 异步
if await embedder.aping():
    print("Embedding 服务正常")
```

---

## 调试追踪

### 自动追踪

OpenAILike 会自动追踪以下内容：

- 请求参数（model, temperature, max_tokens）
- 输入消息
- 输出内容
- Token 统计
- 耗时
- 错误信息

### 关联 Agent

```python
# 设置 Agent ID 以关联追踪
llm.agent_id = "my_agent"

# 追踪信息会包含 agent_id
response = await llm.ainvoke("你好")
```

### 查看追踪

```python
from alphora.debugger import tracer

# 启用调试器
tracer.enable(start_server=True, port=9527)

# 访问 http://localhost:9527 查看调试界面
```

---

## API 参考

### OpenAILike

#### 构造参数

| 参数 | 类型 | 默认值 | 说明 |
|------|------|--------|------|
| `model_name` | `str` | 环境变量 | 模型名称 |
| `api_key` | `str` | 环境变量 | API 密钥 |
| `base_url` | `str` | 环境变量 | API 基础 URL |
| `header` | `Mapping` | `None` | 额外请求头 |
| `temperature` | `float` | `0.0` | 采样温度 |
| `max_tokens` | `int` | `1024` | 最大生成 Token |
| `top_p` | `float` | `1.0` | 核采样参数 |
| `is_multimodal` | `bool` | `False` | 是否支持多模态 |

#### 方法

| 方法 | 说明 |
|------|------|
| `invoke(message)` | 同步非流式调用 |
| `ainvoke(message)` | 异步非流式调用 |
| `stream(message, ...)` | 同步流式调用 |
| `astream(message, ...)` | 异步流式调用 |
| `get_non_stream_response(message, tools, ...)` | 底层非流式方法 |
| `aget_non_stream_response(message, tools, ...)` | 底层异步非流式方法 |
| `get_streaming_response(message, ...)` | 底层流式方法 |
| `aget_streaming_response(message, ...)` | 底层异步流式方法 |
| `set_temperature(temp)` | 设置温度 |
| `set_max_tokens(tokens)` | 设置最大 Token |
| `set_top_p(p)` | 设置 top_p |
| `set_model_name(name)` | 设置模型名 |
| `ping()` | 同步连接检查 |
| `aping()` | 异步连接检查 |

### Message

#### 方法

| 方法 | 说明 |
|------|------|
| `add_text(content)` | 添加文本 |
| `add_image(data, format)` | 添加图片 |
| `add_audio(data, format, duration)` | 添加音频 |
| `add_video(data, format, duration)` | 添加视频 |
| `add_function_call(name, parameters)` | 添加函数调用 |
| `add_function_result(name, result, success, error)` | 添加函数结果 |
| `has_text()` | 是否有文本 |
| `has_images()` | 是否有图片 |
| `has_audios()` | 是否有音频 |
| `has_videos()` | 是否有视频 |
| `to_openai_format(role)` | 转为 OpenAI 格式 |

### EmbeddingModel

#### 构造参数

| 参数 | 类型 | 默认值 | 说明 |
|------|------|--------|------|
| `model` | `str` | `'text-embedding-v3'` | 模型名称 |
| `api_key` | `str` | 环境变量 | API 密钥 |
| `base_url` | `str` | DashScope | API 地址 |
| `dimension` | `int` | `None` | 向量维度 |
| `header` | `dict` | `None` | 额外请求头 |

#### 方法

| 方法 | 说明 |
|------|------|
| `get_text_embedding(text)` | 获取单文本向量 |
| `get_text_embeddings(texts, max_batch)` | 批量获取向量 |
| `aget_text_embedding(text)` | 异步获取单文本向量 |
| `aget_text_embeddings(texts, max_batch)` | 异步批量获取向量 |
| `get_embedding_dimension()` | 获取向量维度 |
| `ping()` | 同步连接检查 |
| `aping()` | 异步连接检查 |

### GeneratorOutput

| 属性 | 类型 | 说明 |
|------|------|------|
| `content` | `str` | 文本内容 |
| `content_type` | `str` | 内容类型（char/think/等） |

### ToolCall

| 属性/方法 | 类型 | 说明 |
|-----------|------|------|
| `tool_calls` | `List[Dict]` | 工具调用列表 |
| `content` | `str \| None` | 文本内容 |
| `has_tool_calls` | `bool` | 是否有工具调用 |
| `get_tool_names()` | `List[str]` | 获取工具名称列表 |
| `get_tool_call_ids()` | `List[str]` | 获取调用 ID 列表 |
| `format_details(indent)` | `str` | 格式化详情字符串 |
| `pretty_print(indent)` | `None` | 打印格式化详情 |
| `to_summary()` | `str` | 生成单行摘要 |