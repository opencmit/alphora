# Alphora Agent

**智能体核心框架组件**

Agent 是 Alphora 框架中的智能体核心组件，提供可组合、可派生的智能体架构。它支持多种智能体模式（如 ReAct）、流式输出、调试追踪，并能与 Memory、Prompter 等组件无缝集成，构建复杂的多智能体系统。

## 特性

-  **派生机制** - 支持从父智能体派生子智能体，共享配置与记忆
-  **ReAct 模式** - 内置推理-行动循环，自动处理工具调用
-  **流式输出** - 完整的异步流式响应支持，兼容 OpenAI SSE
-  **工具集成** - 与 ToolRegistry 深度集成，支持 Function Calling
-  **调试追踪** - 内置 Debugger 支持，可视化智能体执行流程
-  **组合能力** - 支持智能体链式组合与并行执行
-  **状态共享** - 通过 MemoryManager 实现跨智能体状态共享
- ️ **配置继承** - 配置字典自动传递给派生智能体

## 安装

```bash
pip install alphora
```

## 快速开始

```python
from alphora.agent import BaseAgent, ReActAgent
from alphora.models import OpenAILike

# 创建基础智能体
llm = OpenAILike(model_name="gpt-4")
agent = BaseAgent(llm=llm, verbose=True)

# 创建提示词并调用
prompt = agent.create_prompt(
    system_prompt="你是一个有帮助的助手",
    user_prompt="{{query}}"
)
response = await prompt.acall(query="你好！")
```

## 目录

- [基础用法](#基础用法)
- [派生机制](#派生机制)
- [ReAct 智能体](#react-智能体)
- [流式输出](#流式输出)
- [配置管理](#配置管理)
- [调试追踪](#调试追踪)
- [第三方 API 调用](#第三方-api-调用)
- [API 参考](#api-参考)

---

## 基础用法

### 创建智能体

```python
from alphora.agent import BaseAgent
from alphora.models import OpenAILike
from alphora.memory import MemoryManager

# 基础创建
agent = BaseAgent(llm=OpenAILike())

# 带完整配置
agent = BaseAgent(
    llm=OpenAILike(model_name="gpt-4"),
    memory=MemoryManager(),
    verbose=True,
    agent_id="my_agent",
    config={"max_retries": 3}
)
```

### 创建提示词

```python
# 简单模式
prompt = agent.create_prompt(
    user_prompt="请回答：{{query}}"
)
response = await prompt.acall(query="什么是人工智能？")

# 带系统提示
prompt = agent.create_prompt(
    system_prompt="你是一个{{role}}专家",
    user_prompt="{{query}}"
)
prompt.update_placeholder(role="Python")
response = await prompt.acall(query="如何使用列表推导式？")

# 从模板文件加载
prompt = agent.create_prompt(
    template_path="prompts/qa_template.txt",
    content_type="char"
)
```

### 流式调用

```python
# 异步流式（推荐）
response = await prompt.acall(
    query="写一首诗",
    is_stream=True
)

# 带回调的流式
from alphora.server.stream_responser import DataStreamer

agent = BaseAgent(
    llm=llm,
    callback=DataStreamer(websocket)  # 自动推送到客户端
)
```

---

## 派生机制

派生机制允许从父智能体创建子智能体，共享 LLM、Memory、Config 等资源。

### 从类派生

```python
from alphora.agent import BaseAgent

class AnalysisAgent(BaseAgent):
    agent_type = "AnalysisAgent"
    
    def __init__(self, domain: str = "general", **kwargs):
        super().__init__(**kwargs)
        self.domain = domain

# 主智能体派生子智能体
main_agent = BaseAgent(llm=llm, config={"debug": True})
analysis_agent = main_agent.derive(AnalysisAgent)

# 子智能体自动继承：
# - llm
# - memory
# - config
# - callback
# - verbose
```

### 从实例派生

```python
# 预配置的实例
file_agent = FileViewerAgent(base_dir="/data/files")

# 派生时保留实例特有属性
file_agent = main_agent.derive(file_agent)
# file_agent.base_dir 仍然是 "/data/files"
# 但 llm, memory, config 已从 main_agent 继承
```

### 派生链

```python
# 多层派生
root_agent = BaseAgent(llm=llm, config={"project": "demo"})
task_agent = root_agent.derive(TaskAgent)
sub_task_agent = task_agent.derive(SubTaskAgent)

# 所有智能体共享同一个 memory 实例
root_agent.memory.add_user("你好")
# task_agent 和 sub_task_agent 都能看到这条消息
```

---

## ReAct 智能体

ReAct (Reasoning + Acting) 智能体自动处理工具调用循环。

### 基础使用

```python
from alphora.agent import ReActAgent
from alphora.tools.decorators import tool

# 定义工具
@tool
def get_weather(city: str) -> str:
    """获取城市天气"""
    return f"{city}今天晴，25°C"

@tool  
def search(query: str) -> str:
    """搜索信息"""
    return f"关于{query}的搜索结果..."

# 创建 ReAct 智能体
agent = ReActAgent(
    llm=OpenAILike(model_name="gpt-4"),
    tools=[get_weather, search],
    system_prompt="你是一个智能助手，可以查询天气和搜索信息",
    max_iterations=10
)

# 执行
response = await agent.run("北京今天天气怎么样？")
```

### 自定义系统提示

```python
agent = ReActAgent(
    llm=llm,
    tools=[get_weather, search, calculate],
    system_prompt="""你是一个数据分析助手。
    
    工作流程：
    1. 理解用户需求
    2. 选择合适的工具
    3. 分析结果
    4. 给出结论
    
    请始终解释你的推理过程。"""
)
```

---

## 流式输出

### Stream 类

```python
from alphora.agent.stream import Stream

stream = Stream(callback=data_streamer)

# 发送流式消息
await stream.astream_message(
    content="这是一段文字",
    content_type="char",
    interval=0.05  # 模拟打字效果
)

# 终止流
await stream.astop(stop_reason="complete")
```

### 流式生成器处理

```python
from alphora.models.llms.stream_helper import BaseGenerator, GeneratorOutput

# 将生成器转为响应
generator = await llm.aget_streaming_response(message="你好")
response = await stream.astream_to_response(
    generator,
    post_processors=[my_processor]  # 可选的后处理器
)
```

### 内容类型

| content_type | 说明 |
|--------------|------|
| `char` | 普通文本字符 |
| `think` | 推理/思考内容 |
| `result` | 最终结果 |
| `sql` | SQL 查询 |
| `chart` | 图表数据 |
| `[STREAM_IGNORE]` | 不发送到流，但计入响应 |
| `[RESPONSE_IGNORE]` | 发送到流，但不计入响应 |
| `[BOTH_IGNORE]` | 既不发送也不计入 |

---

## 配置管理

### 更新配置

```python
agent = BaseAgent(llm=llm)

# 设置配置项
agent.update_config("max_retries", 3)
agent.update_config("timeout", 30)

# 批量设置（通过初始化）
agent = BaseAgent(
    llm=llm,
    config={
        "max_retries": 3,
        "timeout": 30,
        "debug": True
    }
)
```

### 获取配置

```python
# 获取配置值
retries = agent.get_config("max_retries")

# 配置不存在时会提供建议
try:
    agent.get_config("max_retry")  # 拼写错误
except KeyError as e:
    print(e)  # "Config 'max_retry' not found. Did you mean 'max_retries'?"
```

### 配置继承

```python
parent = BaseAgent(llm=llm, config={"project": "demo", "version": "1.0"})
child = parent.derive(ChildAgent)

# 子智能体自动继承配置
print(child.get_config("project"))  # "demo"

# 子智能体可以覆盖
child.update_config("version", "2.0")
```

---

## 调试追踪

### 启用调试器

```python
agent = BaseAgent(
    llm=llm,
    debugger=True,
    debugger_port=9527
)

# 访问 http://localhost:9527 查看调试界面
```

### 追踪内容

- 智能体创建与派生关系
- Prompt 创建与渲染
- LLM 调用（请求/响应/Token 统计）
- 工具执行
- 流式输出

---

## 第三方 API 调用

`afetch_stream` 方法支持调用第三方流式 API 并透传输出。

### 标准 OpenAI 格式

```python
# 自动解析 OpenAI SSE 格式
response = await agent.afetch_stream(
    url="https://api.example.com/v1/chat/completions",
    payload={
        "model": "gpt-4",
        "messages": [{"role": "user", "content": "你好"}],
        "stream": True
    },
    content_type="char"
)
```

### 自定义解析器

```python
# 自定义解析逻辑
def my_parser(chunk: bytes) -> str:
    data = json.loads(chunk)
    return data.get("text", "")

response = await agent.afetch_stream(
    url="https://custom-api.com/generate",
    payload={"prompt": "你好"},
    parser_func=my_parser,
    headers={"Authorization": "Bearer xxx"}
)
```

---

## API 参考

### BaseAgent

#### 构造参数

| 参数 | 类型 | 默认值 | 说明 |
|------|------|--------|------|
| `llm` | `OpenAILike` | `None` | LLM 实例 |
| `verbose` | `bool` | `False` | 详细日志 |
| `agent_id` | `str` | `uuid` | 智能体 ID |
| `callback` | `DataStreamer` | `None` | 流式回调 |
| `debugger` | `bool` | `False` | 启用调试器 |
| `debugger_port` | `int` | `9527` | 调试器端口 |
| `config` | `Dict` | `{}` | 配置字典 |
| `memory` | `MemoryManager` | `None` | 记忆管理器 |

#### 方法

| 方法 | 说明 |
|------|------|
| `create_prompt(user_prompt, system_prompt, template_path, ...)` | 创建提示词实例 |
| `derive(agent_cls_or_instance, **kwargs)` | 派生子智能体 |
| `update_config(key, value)` | 更新配置项 |
| `get_config(key)` | 获取配置项 |
| `afetch_stream(url, payload, parser_func, ...)` | 调用第三方流式 API |

### ReActAgent

#### 构造参数

| 参数 | 类型 | 默认值 | 说明 |
|------|------|--------|------|
| `llm` | `OpenAILike` | 必填 | LLM 实例 |
| `tools` | `List[Tool\|Callable]` | 必填 | 工具列表 |
| `system_prompt` | `str` | `""` | 系统提示词 |
| `max_iterations` | `int` | `10` | 最大迭代次数 |

#### 方法

| 方法 | 说明 |
|------|------|
| `run(query)` | 执行完整的工具调用循环 |

### Stream

#### 方法

| 方法 | 说明 |
|------|------|
| `astream_message(content, content_type, interval)` | 异步发送流式消息 |
| `stream_message(content, content_type, interval)` | 同步发送流式消息（不推荐） |
| `astop(stop_reason)` | 异步终止流 |
| `stop(stop_reason)` | 同步终止流（不推荐） |
| `astream_to_response(generator, post_processors)` | 将生成器转为响应字符串 |
| `stream_to_response(generator, post_processors)` | 同步版本（不推荐） |