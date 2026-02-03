# Alphora Tools

**AI Agent 工具调用组件**

Tools 是 Alphora 框架的工具调用模块，为 LLM Function Calling 提供完整的工具定义、注册、执行能力。它基于 Pydantic V2 实现类型安全的参数验证，支持同步/异步函数，并与 Prompter、Agent、Memory 等组件深度集成。

## 特性

-  **零配置定义** - 使用 `@tool` 装饰器，自动从函数签名生成 JSON Schema
-  **类型安全** - 基于 Pydantic V2 自动验证参数类型
-  **异步优先** - 原生支持 async/await，同步函数自动线程池执行
-  **并行执行** - 支持多工具并行调用，提升执行效率
- ️ **错误反馈** - 自动捕获异常并格式化为 LLM 可理解的错误信息
-  **深度集成** - 与 Prompter、Agent、Memory 无缝配合

## 安装

```bash
pip install alphora
```

## 快速开始

```python
from alphora.tools import tool, ToolRegistry, ToolExecutor

# 1. 定义工具
@tool
def get_weather(city: str) -> str:
    """获取指定城市的天气"""
    return f"{city}：晴，25°C"

@tool
async def search_web(query: str, limit: int = 5) -> str:
    """搜索网页"""
    return f"搜索 '{query}' 的前 {limit} 条结果..."

# 2. 注册工具
registry = ToolRegistry()
registry.register(get_weather)
registry.register(search_web)

# 3. 获取 Schema 传给 LLM
tools_schema = registry.get_openai_tools_schema()

# 4. 执行工具调用
executor = ToolExecutor(registry)
results = await executor.execute(llm_response.tool_calls)
```

## 目录

- [工具定义](#工具定义)
- [工具注册](#工具注册)
- [工具执行](#工具执行)
- [与 Prompter 集成](#与-prompter-集成)
- [与 Agent 集成](#与-agent-集成)
- [与 Memory 集成](#与-memory-集成)
- [高级用法](#高级用法)
- [错误处理](#错误处理)
- [API 参考](#api-参考)

---

## 工具定义

### 使用 @tool 装饰器

最简单的方式是使用 `@tool` 装饰器，自动从函数签名和文档字符串生成工具定义：

```python
from alphora.tools import tool

# 基础用法：自动提取函数名和 docstring
@tool
def calculate_tax(amount: float, rate: float = 0.1) -> float:
    """
    根据金额和税率计算税费。
    
    Args:
        amount: 金额
        rate: 税率，默认 10%
    
    Returns:
        计算后的税费
    """
    return amount * rate

# 自定义工具名称
@tool(name="weather_query")
def get_weather(city: str) -> str:
    """获取天气信息"""
    return f"{city} 天气晴朗"

# 自定义名称和描述
@tool(name="web_search", description="在互联网上搜索信息")
def search(query: str, max_results: int = 10) -> str:
    """搜索函数"""
    return f"搜索结果: {query}"
```

### 异步工具

异步函数会被自动识别：

```python
@tool
async def fetch_data(url: str) -> str:
    """从 URL 获取数据"""
    async with aiohttp.ClientSession() as session:
        async with session.get(url) as response:
            return await response.text()
```

### 使用 Pydantic Schema

对于复杂的参数验证需求，可以显式定义 Pydantic 模型：

```python
from pydantic import BaseModel, Field

class SearchInput(BaseModel):
    query: str = Field(..., min_length=2, description="搜索关键词")
    category: str = Field("general", pattern="^(news|blog|general)$")
    limit: int = Field(10, ge=1, le=100)

@tool(args_schema=SearchInput)
def advanced_search(query: str, category: str, limit: int) -> str:
    """执行高级搜索"""
    return f"在 {category} 中搜索 '{query}'，返回 {limit} 条结果"
```

### 使用 Tool 类

也可以直接使用 `Tool.from_function()` 创建工具：

```python
from alphora.tools import Tool

def my_function(x: int, y: int) -> int:
    """两数相加"""
    return x + y

# 从函数创建工具
tool = Tool.from_function(
    func=my_function,
    name="add_numbers",
    description="计算两个数的和"
)
```

---

## 工具注册

### ToolRegistry 基础用法

```python
from alphora.tools import ToolRegistry, tool

registry = ToolRegistry()

# 注册工具
@tool
def tool_a(x: int) -> int:
    """工具 A"""
    return x * 2

registry.register(tool_a)

# 注册函数（自动转换为 Tool）
def tool_b(y: str) -> str:
    """工具 B"""
    return y.upper()

registry.register(tool_b)
```

### 获取工具 Schema

```python
# 获取 OpenAI 格式的 tools 列表
tools_schema = registry.get_openai_tools_schema()

# 直接传给 LLM
response = await client.chat.completions.create(
    model="gpt-4",
    messages=messages,
    tools=tools_schema
)
```

### 查询和管理工具

```python
# 获取单个工具
tool = registry.get_tool("tool_a")

# 获取所有工具
all_tools = registry.get_all_tools()

# 清空注册表
registry.clear()
```

### 处理命名冲突

Registry 会在工具重名时抛出异常，避免静默覆盖：

```python
@tool
def process(): pass

registry.register(process)

# 再次注册同名工具会报错
# registry.register(process)  # ToolRegistrationError!

# 解决方法：使用 name_override
registry.register(process, name_override="process_v2")
```

---

## 工具执行

### ToolExecutor 基础用法

```python
from alphora.tools import ToolExecutor

executor = ToolExecutor(registry)

# 执行工具调用（支持并行）
results = await executor.execute(tool_calls)

# 串行执行
results = await executor.execute(tool_calls, parallel=False)

# 执行单个工具
result = await executor.execute_single(single_tool_call)

# 同步执行（非异步环境）
results = executor.execute_sync(tool_calls)
```

### 工具调用格式

ToolExecutor 支持多种输入格式：

```python
# 格式 1：直接传入 LLM 响应的 tool_calls
results = await executor.execute(response.tool_calls)

# 格式 2：字典列表
tool_calls = [
    {
        "id": "call_123",
        "function": {
            "name": "get_weather",
            "arguments": '{"city": "北京"}'
        }
    }
]
results = await executor.execute(tool_calls)

# 格式 3：单个字典
result = await executor.execute_single({
    "id": "call_456",
    "function": {
        "name": "calculate_tax",
        "arguments": '{"amount": 1000}'
    }
})
```

### 执行结果

```python
result = results[0]

# 基本属性
print(result.tool_call_id)  # "call_123"
print(result.tool_name)     # "get_weather"
print(result.content)       # "北京：晴，25°C"
print(result.status)        # "success" 或 "error"
print(result.error_type)    # 仅当 status="error" 时

# 转换为 OpenAI 消息格式
message = result.to_openai_message()
# {"role": "tool", "tool_call_id": "call_123", "name": "get_weather", "content": "..."}

# 转换为 Memory 参数
args = result.to_memory_args()
# {"tool_call_id": "call_123", "name": "get_weather", "content": "..."}
```

---

## 与 Prompter 集成

### 基础集成

Prompter 的 `acall()` / `call()` 方法支持 `tools` 参数：

```python
from alphora.prompter import BasePrompt
from alphora.tools import ToolRegistry, ToolExecutor, tool

# 定义工具
@tool
def get_current_time() -> str:
    """获取当前时间"""
    from datetime import datetime
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")

# 注册
registry = ToolRegistry()
registry.register(get_current_time)

# 创建 Prompter
prompt = BasePrompt(
    system="你是一个助手，可以使用工具回答问题。",
    user="{{ question }}"
)

# 调用时传入工具
result = await prompt.acall(
    question="现在几点了？",
    tools=registry.get_all_tools()  # 或 registry.get_openai_tools_schema()
)

# 检查是否有工具调用
if result.has_tool_calls:
    # 执行工具
    executor = ToolExecutor(registry)
    tool_results = await executor.execute(result.tool_calls)
    
    # 继续对话...
```

### 完整工具调用流程

```python
from alphora.prompter import BasePrompt
from alphora.tools import ToolRegistry, ToolExecutor, tool
from alphora.memory import MemoryManager

# 初始化
registry = ToolRegistry()
executor = ToolExecutor(registry)
memory = MemoryManager()

@tool
def search_product(name: str) -> str:
    """搜索商品"""
    return f"找到商品: {name}，价格 ¥99"

registry.register(search_product)

prompt = BasePrompt(
    system="你是购物助手",
    user="{{ query }}"
)

# 用户输入
query = "帮我找一下 iPhone 15"
memory.add_user(query)

# 第一次调用
result = await prompt.acall(
    query=query,
    history=memory.build_history(),
    tools=registry.get_all_tools()
)

# 记录 assistant 响应
memory.add_assistant(result)

# 如果有工具调用
if result.has_tool_calls:
    # 执行工具
    tool_results = await executor.execute(result.tool_calls)
    
    # 记录工具结果
    memory.add_tool_result(tool_results)
    
    # 继续对话获取最终回复
    final_result = await prompt.acall(
        query=None,
        history=memory.build_history()
    )
    memory.add_assistant(final_result)
    
    print(final_result.response)
```

---

## 与 Agent 集成

### ReActAgent 自动工具调用

ReActAgent 内置了工具调用循环，自动处理工具执行：

```python
from alphora.agent import ReActAgent
from alphora.tools import ToolRegistry, tool

# 定义工具
@tool
def calculator(expression: str) -> str:
    """计算数学表达式"""
    try:
        return str(eval(expression))
    except:
        return "计算错误"

@tool
async def web_search(query: str) -> str:
    """搜索网络"""
    return f"搜索 '{query}' 的结果..."

# 注册
registry = ToolRegistry()
registry.register(calculator)
registry.register(web_search)

# 创建 Agent
agent = ReActAgent(
    system="你是一个智能助手，可以使用工具解决问题。",
    tools=registry.get_all_tools(),
    tool_executor=registry  # 传入 registry，Agent 会自动创建 executor
)

# 运行 - Agent 会自动执行工具调用循环
async for chunk in agent.acall(query="计算 (15 + 27) * 3 等于多少"):
    print(chunk.content, end="")
```

### 自定义工具执行器

```python
from alphora.agent import ReActAgent
from alphora.tools import ToolExecutor

# 自定义执行器
executor = ToolExecutor(registry)

agent = ReActAgent(
    system="你是助手",
    tools=registry.get_all_tools(),
    tool_executor=executor,  # 传入自定义执行器
    max_iterations=5         # 最大工具调用轮数
)
```

---

## 与 Memory 集成

### 手动记录工具调用

```python
from alphora.memory import MemoryManager
from alphora.tools import ToolExecutor

memory = MemoryManager()
executor = ToolExecutor(registry)

# 执行工具
results = await executor.execute(tool_calls)

# 方式 1：使用便捷方法（推荐）
memory.add_tool_result(results)

# 方式 2：逐个添加
for result in results:
    memory.add_tool_result(
        tool_call_id=result.tool_call_id,
        name=result.tool_name,
        content=result.content
    )

# 方式 3：使用 to_memory_args()
for result in results:
    memory.add_tool_result(**result.to_memory_args())
```

### 便捷函数

```python
from alphora.tools import execute_tools, add_tool_results_to_memory

# 执行工具
results = await execute_tools(registry, tool_calls)

# 添加到 Memory
add_tool_results_to_memory(memory, results)
```

---

## 高级用法

### 类实例方法作为工具

适用于需要访问数据库、API 或用户上下文的场景：

```python
class DatabaseService:
    def __init__(self, connection_string: str):
        self.conn = connection_string
    
    def query_user(self, user_id: int) -> str:
        """查询用户信息"""
        return f"User {user_id} from {self.conn}"
    
    async def update_user(self, user_id: int, name: str) -> str:
        """更新用户名"""
        return f"Updated user {user_id} name to {name}"

# 实例化服务
db = DatabaseService("postgres://localhost/mydb")

# 注册实例方法
registry.register(db.query_user, name_override="lookup_user")
registry.register(db.update_user, name_override="modify_user")

# LLM 调用时无需感知 self 参数
```

### 工具组合

```python
# 创建专门的工具集
search_registry = ToolRegistry()
search_registry.register(web_search)
search_registry.register(image_search)

calc_registry = ToolRegistry()
calc_registry.register(calculator)
calc_registry.register(unit_converter)

# 合并使用
all_tools = (
    search_registry.get_all_tools() + 
    calc_registry.get_all_tools()
)

agent = ReActAgent(tools=all_tools, ...)
```

### 动态工具注册

```python
def create_tool_for_api(api_config: dict) -> Tool:
    """根据配置动态创建工具"""
    
    async def api_call(**kwargs) -> str:
        # 调用外部 API
        return await call_api(api_config["url"], kwargs)
    
    return Tool.from_function(
        func=api_call,
        name=api_config["name"],
        description=api_config["description"]
    )

# 从配置文件加载
for config in api_configs:
    tool = create_tool_for_api(config)
    registry.register(tool)
```

---

## 错误处理

### 错误类型

```python
from alphora.tools import (
    ToolError,              # 基础异常
    ToolRegistrationError,  # 注册时错误（如重名）
    ToolValidationError,    # 参数验证失败
    ToolExecutionError,     # 执行时错误
)
```

### 自动错误反馈

ToolExecutor 会自动捕获异常并格式化为 LLM 可理解的错误信息：

```python
# 工具定义
@tool
def divide(a: float, b: float) -> float:
    """除法运算"""
    return a / b

# 当 LLM 传入 b=0 时
result = await executor.execute_single({
    "id": "call_1",
    "function": {
        "name": "divide",
        "arguments": '{"a": 10, "b": 0}'
    }
})

print(result.status)      # "error"
print(result.error_type)  # "ExecutionError"
print(result.content)     # "Error: Execution failed - division by zero"

# 这个错误信息会返回给 LLM，触发其自我修正
```

### 错误类型说明

| 错误类型 | 触发场景 | content 示例 |
|---------|---------|-------------|
| `ToolNotFoundError` | 调用不存在的工具 | "Error: Tool 'xxx' not found in registry." |
| `JSONDecodeError` | 参数 JSON 解析失败 | "Error: Invalid JSON arguments - ..." |
| `ValidationError` | Pydantic 参数验证失败 | "Error: Arguments validation failed - ..." |
| `ExecutionError` | 函数执行时异常 | "Error: Execution failed - ..." |
| `InternalError` | 未预期的内部错误 | "Error: Unexpected internal error - ..." |

### 手动错误处理

```python
try:
    result = tool.run(amount="invalid")  # 应该是 float
except ToolValidationError as e:
    print(f"参数错误: {e}")
except ToolExecutionError as e:
    print(f"执行错误: {e}")
```

---

## API 参考

### Tool

工具包装器类。

#### 类方法

| 方法 | 说明 |
|------|------|
| `from_function(func, name, description, args_schema)` | 从函数创建 Tool 实例 |

#### 实例属性

| 属性 | 类型 | 说明 |
|------|------|------|
| `name` | `str` | 工具名称 |
| `description` | `str` | 工具描述 |
| `func` | `Callable` | 实际执行的函数 |
| `args_schema` | `Type[BaseModel]` | Pydantic 参数模型 |
| `is_async` | `bool` | 是否为异步函数 |
| `openai_schema` | `Dict` | OpenAI 格式的 Schema |

#### 实例方法

| 方法 | 说明 |
|------|------|
| `run(**kwargs)` | 同步执行工具 |
| `arun(**kwargs)` | 异步执行工具 |
| `validate_args(tool_input)` | 验证参数 |

### @tool 装饰器

```python
@tool
def func(): ...

@tool("custom_name")
def func(): ...

@tool(name="name", description="desc", args_schema=MySchema)
def func(): ...
```

| 参数 | 类型 | 说明 |
|------|------|------|
| `name` | `str` | 工具名称（可选） |
| `description` | `str` | 工具描述（可选） |
| `args_schema` | `Type[BaseModel]` | Pydantic 参数模型（可选） |

### ToolRegistry

工具注册中心。

| 方法 | 说明 |
|------|------|
| `register(tool_or_func, name_override)` | 注册工具 |
| `get_tool(name)` | 获取指定工具 |
| `get_all_tools()` | 获取所有工具 |
| `get_openai_tools_schema()` | 获取 OpenAI 格式的 Schema 列表 |
| `clear()` | 清空注册表 |

### ToolExecutor

工具执行器。

| 方法 | 说明 |
|------|------|
| `execute(tool_calls, parallel)` | 异步执行工具调用 |
| `execute_single(tool_call)` | 执行单个工具调用 |
| `execute_sync(tool_calls)` | 同步执行工具调用 |

### ToolExecutionResult

执行结果类。

| 属性 | 类型 | 说明 |
|------|------|------|
| `tool_call_id` | `str` | 调用 ID |
| `tool_name` | `str` | 工具名称 |
| `content` | `str` | 执行结果 |
| `status` | `str` | 状态：`success` / `error` |
| `error_type` | `str` | 错误类型（仅当 error 时） |

| 方法 | 说明 |
|------|------|
| `to_openai_message()` | 转换为 OpenAI 消息格式 |
| `to_memory_args()` | 转换为 Memory 参数格式 |

### 便捷函数

```python
# 执行工具
results = await execute_tools(registry, tool_calls)

# 添加结果到 Memory
add_tool_results_to_memory(memory, results, session_id="default")
```

### 异常类

| 异常 | 说明 |
|------|------|
| `ToolError` | 基础异常 |
| `ToolRegistrationError` | 注册错误（如重名） |
| `ToolValidationError` | 参数验证失败 |
| `ToolExecutionError` | 执行时错误 |
