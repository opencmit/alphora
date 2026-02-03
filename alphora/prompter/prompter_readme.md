# Alphora Prompter

**智能体提示词编排引擎**

Prompter 是 Alphora 框架的核心提示词编排组件，提供基于 Jinja2 的动态模板渲染、LLM 生命周期管理、流式输出处理等能力。它支持工具调用、长文本续写、并行执行等高级特性，是构建复杂 LLM 应用的基础设施。

## 特性

- 🎯 **Jinja2 模板** - 强大的动态模板渲染，支持变量插值和逻辑控制
- 📝 **双模式调用** - 完整支持同步 `call` 和异步 `acall` 调用模式
- 🔄 **流式输出** - 原生支持 Token 级流式响应和回调处理
- 🛠 **工具调用** - 无缝集成 Function Calling，支持流式工具调用
- 📚 **历史集成** - 与 MemoryManager 深度集成，规范化消息序列
- ✨ **长文本续写** - 自动检测截断并续写，突破 Token 限制
- ⚡ **并行执行** - 支持多提示词并行调用，提升吞吐量
- 🔧 **后处理器** - 灵活的流式输出后处理管道

## 安装

```bash
pip install alphora
```

## 快速开始

```python
from alphora.prompter import BasePrompt
from alphora.models import OpenAILike

# 创建提示词
prompt = BasePrompt(
    system_prompt="你是一个Python专家",
    user_prompt="请解释：{{query}}"
)

# 绑定 LLM
prompt.add_llm(OpenAILike(model_name="gpt-4"))

# 调用
response = await prompt.acall(query="什么是装饰器？", is_stream=True)
```

## 目录

- [基础用法](#基础用法)
- [模板系统](#模板系统)
- [消息构建](#消息构建)
- [流式输出](#流式输出)
- [工具调用](#工具调用)
- [长文本续写](#长文本续写)
- [并行执行](#并行执行)
- [后处理器](#后处理器)
- [API 参考](#api-参考)

---

## 基础用法

### 创建提示词

```python
from alphora.prompter import BasePrompt

# 方式 1：直接传入字符串
prompt = BasePrompt(
    user_prompt="请回答：{{query}}"
)

# 方式 2：带系统提示
prompt = BasePrompt(
    system_prompt="你是一个{{role}}助手",
    user_prompt="{{query}}"
)

# 方式 3：从文件加载
prompt = BasePrompt(
    template_path="prompts/qa.txt"
)

# 方式 4：多段系统提示
prompt = BasePrompt(
    system_prompt=[
        "你是一个AI助手",
        "请用简洁的语言回答",
        "如果不确定，请说明"
    ],
    user_prompt="{{query}}"
)
```

### 绑定 LLM

```python
from alphora.models import OpenAILike, Qwen

# 绑定 OpenAI 兼容模型
prompt.add_llm(OpenAILike(model_name="gpt-4"))

# 或 Qwen 模型
prompt.add_llm(Qwen(model_name="qwen-max"))

# 链式调用
prompt = BasePrompt(user_prompt="{{query}}").add_llm(llm)
```

### 更新占位符

```python
prompt = BasePrompt(
    system_prompt="你是{{company}}的{{role}}",
    user_prompt="{{context}}\n\n问题：{{query}}"
)

# 更新变量
prompt.update_placeholder(
    company="Anthropic",
    role="AI助手",
    context="以下是背景信息..."
)

# 链式调用
prompt.update_placeholder(company="OpenAI").update_placeholder(role="专家")

# 查看可用占位符
print(prompt.placeholders)  # ['company', 'role', 'context']
```

### 调用方式

```python
# 异步调用（推荐）
response = await prompt.acall(query="你好")

# 同步调用
response = prompt.call(query="你好")

# 流式调用
response = await prompt.acall(query="写一篇文章", is_stream=True)

# 非流式调用
response = await prompt.acall(query="简单问题", is_stream=False)
```

---

## 模板系统

### Jinja2 语法

```python
# 变量插值
prompt = BasePrompt(user_prompt="你好，{{name}}！")

# 条件判断
prompt = BasePrompt(user_prompt="""
{% if detailed %}
请详细解释：{{query}}
{% else %}
简要回答：{{query}}
{% endif %}
""")

# 循环
prompt = BasePrompt(user_prompt="""
请分析以下项目：
{% for item in items %}
- {{item}}
{% endfor %}
""")
```

### 模板文件

```python
# prompts/analysis.txt
"""
你需要分析以下数据：
{{data}}

分析角度：
{% for angle in angles %}
{{loop.index}}. {{angle}}
{% endfor %}

输出格式：{{format}}
"""

prompt = BasePrompt(template_path="prompts/analysis.txt")
prompt.update_placeholder(
    data="销售数据...",
    angles=["趋势", "异常", "预测"],
    format="JSON"
)
```

### 渲染预览

```python
# 查看渲染结果
print(prompt.render())

# 完整预览（包含 system 和 user）
print(prompt)
# [System Prompts]
#  - 你是一个AI助手
# [User Prompt]
# 请回答：{{query}}
```

---

## 消息构建

### build_messages 方法

```python
# 构建标准消息列表
messages = prompt.build_messages(
    query="你好",
    force_json=False,
    runtime_system_prompt=None,
    history=None
)
# [
#     {"role": "system", "content": "你是一个AI助手"},
#     {"role": "user", "content": "你好"}
# ]
```

### 消息顺序

消息按以下顺序组装：

1. **JSON 约束**（如果 `force_json=True`）
2. **预设 System Prompts**
3. **运行时 System Prompts**
4. **历史记录**（来自 HistoryPayload）
5. **User 输入**

### 与 Memory 集成

```python
from alphora.memory import MemoryManager

memory = MemoryManager()
memory.add_user("之前的问题")
memory.add_assistant("之前的回答")

# 构建带历史的消息
history = memory.build_history()
response = await prompt.acall(
    query="继续上面的话题",
    history=history
)
```

### 运行时系统提示

```python
# 动态添加系统指令
response = await prompt.acall(
    query="分析数据",
    runtime_system_prompt="请用表格形式输出"
)

# 多条运行时指令
response = await prompt.acall(
    query="分析数据",
    runtime_system_prompt=[
        "请用表格形式输出",
        "包含数据来源说明"
    ]
)
```

---

## 流式输出

### 基础流式

```python
# 流式调用，自动打印
response = await prompt.acall(
    query="写一首诗",
    is_stream=True
)

# 带回调的流式
prompt = BasePrompt(
    user_prompt="{{query}}",
    callback=data_streamer  # 自动推送到客户端
)
```

### 获取生成器

```python
# 获取原始生成器以自定义处理
generator = await prompt.acall(
    query="写文章",
    is_stream=True,
    return_generator=True
)

# 自定义消费
async for chunk in generator:
    print(chunk.content, end="")
    # chunk.content_type: 'char', 'think', 等
```

### 启用思考链

```python
response = await prompt.acall(
    query="复杂推理问题",
    is_stream=True,
    enable_thinking=True
)

# 访问推理内容
print(response.reasoning)  # 思考过程
print(response)            # 最终回答
```

### 内容类型

```python
response = await prompt.acall(
    query="生成SQL",
    is_stream=True,
    content_type="sql"  # 指定输出类型
)
```

---

## 工具调用

### 基础工具调用

```python
from alphora.tools.decorators import tool

@tool
def get_weather(city: str) -> str:
    """获取天气信息"""
    return f"{city}: 晴, 25°C"

tools_schema = [get_weather.to_openai_schema()]

# 非流式工具调用
response = await prompt.acall(
    query="北京天气如何？",
    tools=tools_schema
)

if response.has_tool_calls:
    print(response.tool_calls)  # 工具调用列表
else:
    print(response.content)     # 文本响应
```

### 流式工具调用

```python
# 流式也支持工具调用
response = await prompt.acall(
    query="查询天气",
    is_stream=True,
    tools=tools_schema
)

# ToolCall 对象
if response.has_tool_calls:
    response.pretty_print()  # 格式化显示
    print(response.to_summary())  # 简短摘要
```

### 完整工具链

```python
from alphora.memory import MemoryManager

memory = MemoryManager()
memory.add_user("北京天气？")

# 第一轮：获取工具调用
history = memory.build_history()
response = await prompt.acall(history=history, tools=tools_schema)

if response.has_tool_calls:
    memory.add_assistant(response)
    
    # 执行工具
    results = await executor.execute(response)
    memory.add_tool_result(results)
    
    # 第二轮：生成最终回答
    history = memory.build_history()
    final = await prompt.acall(history=history)
    memory.add_assistant(final)
```

---

## 长文本续写

当模型输出因 Token 限制被截断时，自动续写生成完整内容。

### 启用长文本模式

```python
response = await prompt.acall(
    query="写一篇10000字的小说",
    is_stream=True,
    long_response=True  # 启用自动续写
)

# 查看续写次数
print(response.continuation_count)  # 续写了几次
```

### 工作原理

1. 检测 `finish_reason == 'length'`（Token 耗尽）
2. 自动构建续写提示，包含：
    - 原始任务描述
    - 已生成内容的尾部（上下文）
    - 续写指令
3. 循环生成直到自然结束或达到最大次数

### 配置参数

```python
from alphora.prompter.long_response import LongResponseGenerator

generator = LongResponseGenerator(
    llm=llm,
    original_message=message,
    content_type="char",
    enable_thinking=False
)

# 内部参数
generator.max_continuations = 100  # 最大续写次数
generator.tail_length = 1500       # 上下文尾部长度
generator.min_chunk_length = 50    # 最小输出长度（防止空循环）
```

---

## 并行执行

### 管道运算符

```python
from alphora.prompter import BasePrompt

prompt1 = BasePrompt(user_prompt="翻译成英文：{{query}}")
prompt2 = BasePrompt(user_prompt="翻译成日文：{{query}}")
prompt3 = BasePrompt(user_prompt="翻译成法文：{{query}}")

# 使用 | 运算符组合
parallel_prompt = prompt1 | prompt2 | prompt3

# 并行执行
results = await parallel_prompt.acall(query="你好世界")
# results = ["Hello World", "こんにちは世界", "Bonjour le monde"]
```

### ParallelPrompt 类

```python
from alphora.prompter.parallel import ParallelPrompt

prompts = [
    BasePrompt(user_prompt="分析情感：{{text}}"),
    BasePrompt(user_prompt="提取关键词：{{text}}"),
    BasePrompt(user_prompt="生成摘要：{{text}}")
]

parallel = ParallelPrompt(prompts)

# 同一输入，多个分析
results = await parallel.acall(text="这是一段需要分析的文本...")
sentiment, keywords, summary = results
```

### 性能优势

- 并行执行多个 LLM 调用
- 减少总等待时间
- 适合多角度分析、批量翻译等场景

---

## 后处理器

### 使用后处理器

```python
from alphora.postprocess.base_pp import BasePostProcessor

# 自定义后处理器
class UpperCaseProcessor(BasePostProcessor):
    def __call__(self, generator):
        async for chunk in generator:
            chunk.content = chunk.content.upper()
            yield chunk

response = await prompt.acall(
    query="你好",
    is_stream=True,
    postprocessor=UpperCaseProcessor()
)
```

### 多个后处理器

```python
response = await prompt.acall(
    query="生成内容",
    is_stream=True,
    postprocessor=[
        FilterProcessor(),
        FormatProcessor(),
        LogProcessor()
    ]
)
```

---

## JSON 输出

### 强制 JSON 格式

```python
response = await prompt.acall(
    query="列出三个水果",
    force_json=True  # 自动添加 JSON 指令并修复输出
)

# 自动使用 json_repair 修复可能的格式问题
data = json.loads(response)
```

---

## API 参考

### BasePrompt

#### 构造参数

| 参数 | 类型 | 默认值 | 说明 |
|------|------|--------|------|
| `user_prompt` | `str` | `None` | User 提示词模板 |
| `template_path` | `str` | `None` | 模板文件路径 |
| `system_prompt` | `str \| List[str]` | `None` | System 提示词 |
| `verbose` | `bool` | `False` | 详细日志 |
| `callback` | `DataStreamer` | `None` | 流式回调 |
| `content_type` | `str` | `'char'` | 默认内容类型 |
| `agent_id` | `str` | `None` | 关联的 Agent ID |

#### 方法

| 方法 | 说明 |
|------|------|
| `add_llm(model)` | 绑定 LLM 实例 |
| `update_placeholder(**kwargs)` | 更新模板变量 |
| `build_messages(query, force_json, runtime_system_prompt, history)` | 构建消息列表 |
| `call(...)` | 同步调用 |
| `acall(...)` | 异步调用 |
| `render()` | 渲染 User 模板 |

#### acall / call 参数

| 参数 | 类型 | 默认值 | 说明 |
|------|------|--------|------|
| `query` | `str` | `None` | 用户输入 |
| `is_stream` | `bool` | `False` | 是否流式 |
| `tools` | `List` | `None` | 工具定义列表 |
| `multimodal_message` | `Message` | `None` | 多模态消息 |
| `return_generator` | `bool` | `False` | 返回原始生成器 |
| `content_type` | `str` | `None` | 覆盖内容类型 |
| `postprocessor` | `BasePostProcessor` | `None` | 后处理器 |
| `enable_thinking` | `bool` | `False` | 启用思考链 |
| `force_json` | `bool` | `False` | 强制 JSON 输出 |
| `long_response` | `bool` | `False` | 启用长文本续写 |
| `runtime_system_prompt` | `str \| List[str]` | `None` | 运行时系统提示 |
| `history` | `HistoryPayload` | `None` | 历史记录载荷 |

### PrompterOutput

继承自 `str`，可直接作为字符串使用，同时提供额外属性：

| 属性 | 类型 | 说明 |
|------|------|------|
| `reasoning` | `str` | 思考链内容（enable_thinking=True 时） |
| `finish_reason` | `str` | 结束原因（stop/length/tool_calls） |
| `continuation_count` | `int` | 续写次数（long_response=True 时） |

### ToolCall

| 属性/方法 | 说明 |
|-----------|------|
| `tool_calls` | 工具调用列表 |
| `content` | 文本内容（可能为 None） |
| `has_tool_calls` | 是否有工具调用 |
| `get_tool_names()` | 获取所有工具名称 |
| `get_tool_call_ids()` | 获取所有调用 ID |
| `pretty_print()` | 格式化打印 |
| `to_summary()` | 生成单行摘要 |

### ParallelPrompt

| 方法 | 说明 |
|------|------|
| `call(*args, **kwargs)` | 同步并行执行 |
| `acall(*args, **kwargs)` | 异步并行执行 |