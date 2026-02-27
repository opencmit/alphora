<h1 align="center">
<img src="asset/image/logo.png" width="70" style="vertical-align:middle; margin-right:8px;">
<span style="font-size:46px; vertical-align:middle;">Alphora</span>
</h1>

<p align="center">
  <img src="https://img.shields.io/badge/Python-3.9+-blue.svg" alt="Python">
  <img src="https://img.shields.io/badge/License-Apache%202.0-green.svg" alt="License">
  <img src="https://img.shields.io/badge/PRs-welcome-brightgreen.svg" alt="PRs Welcome">
</p>

<p align="center">
<strong>构建可组合 AI Agent 的生产级框架</strong>
</p>

<p align="center">
轻松构建强大、模块化且易于维护的 AI Agent 应用。
</p>

<p align="center">
<a href="docs/ARCHITECTURE.md">文档</a> •
<a href="#快速上手">快速上手</a> •
<a href="#示例">示例</a> •
<a href="README.md">English</a>
</p>

---

## 什么是 Alphora?

Alphora 是一个用于构建生产级 AI Agent 的全栈框架。它提供了你所需要的一切核心能力——Agent 编排、工具执行、记忆管理、安全代码沙箱、Skills 生态、流式输出以及部署——所有功能都采用异步优先、兼容 OpenAI 的设计。

```python
from alphora.agent import ReActAgent
from alphora.models import OpenAILike
from alphora.tools import tool

@tool
def get_weather(city: str) -> str:
    """获取指定城市的当前天气。"""
    return f"{city} 的天气：22°C, 晴"

agent = ReActAgent(
    llm=OpenAILike(model_name="gpt-4"),
    tools=[get_weather],
    system_prompt="你是一个得力的助手。",
)

result = await agent.run("北京的天气怎么样？")
```

## 安装

```bash
pip install alphora
```

---

## 核心特性

### Agent 系统

* **ReAct 循环** — 内置推理-动作循环，具备自动工具编排、重试逻辑和迭代控制。
* **Agent 派生** — 子 Agent 继承父级的 LLM、记忆和配置。构建可共享上下文的层级结构。
* **流式优先** — 原生异步流式传输，采用 OpenAI SSE 格式。支持多种内容类型：`char`、`think`、`result`、`sql`、`chart`。
* **调试追踪** — 内置可视化调试器，用于追踪 Agent 执行流、LLM 调用和工具调用。

### 模型层

* **OpenAI 兼容** — 兼容任何 OpenAI 标准的 API：GPT, Claude, Qwen, DeepSeek 以及本地模型。
* **多模态支持** — 统一的 `Message` 类，支持文本、图像、音频和视频输入。
* **负载均衡** — 内置多个 LLM 后端之间的轮询/随机负载均衡。
* **思考模式** — 支持推理模型（如 Qwen3 等），具有独立的思考流和内容流。
* **嵌入 (Embedding) API** — 统一的文本嵌入接口，支持批量处理。

### 工具系统

* **零配置工具** — `@tool` 装饰器根据类型提示（Type Hints）和文档字符串自动生成 OpenAI 函数调用 Schema。
* **类型安全** — 对所有工具参数进行 Pydantic V2 校验。自动向 LLM 返回错误反馈。
* **原生异步** — 异步工具原生运行；同步工具自动在线程池中执行。
* **并行执行** — 并发执行多个工具调用以提升性能。
* **实例方法** — 支持将类方法注册为工具，并可访问 `self` 上下文（如数据库连接、用户状态等）。

### 提示词引擎

* **Jinja2 模板** — 动态提示词，支持变量插值、条件判断、循环和引用。
* **长文本续写** — 自动检测截断并继续生成，突破 Token 限制。
* **并行提示词** — 使用 `ParallelPrompt` 并发执行多个提示词任务。
* **后处理器** — 通过可插拔的处理器流水线转换流式输出。
* **模板文件** — 从外部文件加载提示词，便于组织和管理。

### 记忆与存储

* **会话记忆** — 多会话管理，完整支持 OpenAI 消息格式。
* **工具调用追踪** — 完整的函数调用链管理及校验。
* **置顶/标签系统** — 保护重要消息不被裁剪或修改。
* **撤销/重做** — 在需要时回滚对话操作。
* **多种后端** — 提供内存、JSON 文件、SQLite 存储选项。
* **TTL 支持** — 自动清理过期会话，支持生存时间设置。

### Skills（兼容 [agentskills.io](https://agentskills.io)）

* **渐进式加载** — 三阶段加载（元数据 → 指令 → 资源），优化 Token 预算。
* **生态兼容** — 使用为 Anthropic / OpenAI / Copilot 工作流发布的社区 Skills。
* **安全资源访问** — 内置路径遍历检测和文件大小限制。
* **SkillAgent** — 与 `SkillAgent` 开箱即用，也可插入 `ReActAgent`。

### 沙箱

* **安全执行** — 在隔离环境中运行 Agent 生成的代码，支持资源限制和安全策略。
* **本地 / Docker 后端** — 本地快速运行用于开发，容器隔离用于生产。
* **远程 Docker (TCP)** — 通过 `docker_host="tcp://..."` 连接远程 Docker daemon。自动镜像校验、本地 Skills 同步、容器内文件操作。
* **Agent 友好路径** — `uploads/` 和 `outputs/` 作为工作目录子目录（对齐 OpenAI Code Interpreter 规范），Agent 使用相对路径即可。
* **文件与包管理** — 完整文件操作（读写/列表/复制/移动/删除）和沙箱内 pip 包管理。

### Hooks（扩展与治理）

* **统一事件** — 一套 Hook 系统覆盖工具、记忆、提示词/LLM、沙箱和 Agent 全生命周期。
* **稳定默认** — 默认 fail-open（Hook 失败不会阻断主流程）。
* **运维控制** — 执行顺序、超时、错误策略（fail-open / fail-close）和基础指标/审计模式。

### 部署

* **单行 API** — 使用 `publish_agent_api()` 将任何 Agent 发布为兼容 OpenAI 的 REST API。
* **FastAPI 集成** — 基于 FastAPI 构建，自动生成 OpenAPI 文档。
* **SSE 流式传输** — 使用服务器发送事件（SSE）实现实时流式响应。
* **会话管理** — 内置会话处理，支持可配置的 TTL。

---

## 快速上手

### 1. ReAct Agent + 工具

```python
from alphora.agent import ReActAgent
from alphora.models import OpenAILike
from alphora.tools import tool

@tool
def get_weather(city: str, unit: str = "celsius") -> str:
    """获取指定城市的当前天气。"""
    return f"{city} 的天气：22°{unit[0].upper()}, 晴"

@tool
async def search_docs(query: str, limit: int = 5) -> list:
    """搜索内部文档。"""
    return [{"title": "结果 1", "score": 0.95}]

agent = ReActAgent(
    llm=OpenAILike(model_name="gpt-4"),
    tools=[get_weather, search_docs],
    system_prompt="你是一个得力的助手。",
    max_iterations=10,
)

result = await agent.run("东京的天气怎么样？")
```

### 2. 沙箱（安全代码执行）

```python
from alphora.sandbox import Sandbox

async with Sandbox(
    runtime="docker",
    workspace_root="/data/workspace",
    image="alphora-sandbox:latest",
) as sandbox:
    result = await sandbox.execute_code("print(6 * 7)")
    print(result.stdout)  # 42

    await sandbox.write_file("outputs/result.txt", "done")
    files = await sandbox.list_files()
```

远程 Docker：

```python
async with Sandbox(
    runtime="docker",
    docker_host="tcp://your-server:2375",
    workspace_root="/data/sandboxes",
    skill_host_path="./local-skills",
    image="alphora-sandbox:latest",
) as sandbox:
    result = await sandbox.execute_code("print('Hello from remote!')")
```

### 3. Skills（社区与标准）

```python
from alphora.agent import SkillAgent
from alphora.models import OpenAILike

agent = SkillAgent(
    llm=OpenAILike(model_name="gpt-4"),
    skill_paths=["./alphora_community/skills"],
    system_prompt="你是一个得力的助手。",
)

result = await agent.run("帮我做一个关于 AI Agent 的深度调研。")
```

### 4. 记忆管理

```python
from alphora.memory import MemoryManager

memory = MemoryManager()

memory.add_user(session_id="user_123", content="你好")
memory.add_assistant(session_id="user_123", content="你好！")

history = memory.build_history(session_id="user_123")
```

### 5. 负载均衡

```python
llm1 = OpenAILike(model_name="gpt-4", api_key="key1", base_url="https://api1.com/v1")
llm2 = OpenAILike(model_name="gpt-4", api_key="key2", base_url="https://api2.com/v1")

llm = llm1 + llm2  # 自动轮询负载均衡

response = await llm.ainvoke("你好")
```

### 6. 部署为 API

```python
from alphora.server.quick_api import publish_agent_api, APIPublisherConfig

config = APIPublisherConfig(
    path="/alphadata",
    api_title="我的 Agent API",
    memory_ttl=3600,
)

app = publish_agent_api(agent=agent, method="run", config=config)

# 运行: uvicorn main:app --port 8000
```

```bash
curl -X POST http://localhost:8000/alphadata/chat/completions \
  -H "Content-Type: application/json" \
  -d '{"messages": [{"role": "user", "content": "你好！"}], "stream": true}'
```

---

## 示例

| 示例 | 描述 |
|------|------|
| [ChatExcel](./examples/chatexcel)           | 具备沙箱代码执行能力的数据分析 Agent |
| [RAG Agent](./examples/rag-agent)           | 结合向量搜索的检索增强生成 Agent |
| [多 Agent](./examples/multi-agent)          | 采用 Agent-as-tool 模式的分层 Agent |
| [流式对话](./examples/streaming-chat)       | 具备思考模式的实时对话 |


---

## 配置

```bash
export LLM_API_KEY="your-api-key"
export LLM_BASE_URL="https://api.openai.com/v1"
export DEFAULT_LLM="gpt-4"

# 可选：Embedding
export EMBEDDING_API_KEY="your-key"
export EMBEDDING_BASE_URL="https://api.openai.com/v1"
```

```python
from alphora.models import OpenAILike

llm = OpenAILike(
    model_name="gpt-4",
    api_key="sk-xxx",
    base_url="https://api.openai.com/v1",
    temperature=0.7,
    max_tokens=4096,
    is_multimodal=True,
)
```

---

## 文档

关于系统设计、组件关系和实现模式的详细信息，请参阅 [架构指南](./docs/ARCHITECTURE.md)。

### 组件概览

| 组件 | 描述 |
|------|------|
| [Agent](docs/components/cn/agent_readme.md)              | 核心 Agent 生命周期、派生、ReAct 循环 |
| [Prompter](docs/components/cn/prompter_readme.md)        | Jinja2 模板、LLM 调用、流式传输 |
| [Models](docs/components/cn/model_readme.md)             | LLM 接口、多模态、负载均衡 |
| [Tools](docs/components/cn/tool_readme.md)               | tool 装饰器、注册表、并行执行 |
| [Memory](docs/components/cn/memory_readme.md)            | 会话管理、历史记录、置顶/标签系统 |
| [Storage](docs/components/cn/storage_readme.md)          | 持久化后端 (内存, JSON, SQLite) |
| [Sandbox](docs/components/cn/sandbox_readme.md)          | 安全代码执行、本地/Docker/远程 |
| [Skills](docs/components/cn/skill_readme.md)             | agentskills.io 兼容、SkillAgent 集成 |
| [Hooks](docs/components/cn/hooks_readme.md)              | 通过统一 Hook 事件进行扩展与治理 |
| [Server](docs/components/cn/server_readme.md)            | API 发布、SSE 流式传输 |
| [Postprocess](docs/components/cn/postprocess_readme.md)  | 流式转换流水线 |

---

## 贡献者

由 AlphaData 团队精心打造。

<table><tr><td align="center" width="170px"><a href="https://github.com/tian-cmcc"><img src="https://avatars.githubusercontent.com/tian-cmcc" width="80px;" style="border-radius: 50%;" alt="Tian Tian"/><br /><b>Tian Tian</b></a><br /><sub>项目负责人 & 核心开发</sub><br /><a href="mailto:tiantianit@chinamobile.com" title="Email Tian Tian">📧</a></td><td align="center" width="170px"><a href="https://github.com/yilingliang"><img src="https://cdn.jsdelivr.net/gh/yilingliang/picbed/mdings/48301768.gif" width="80px;" style="border-radius: 50%;" alt="Yuhang Liang"/><br /><b>Yuhang Liang</b></a><br /><sub>开发者</sub><br /><a href="mailto:liangyuhang@chinamobile.com" title="Email Yuhang Liang">📧</a></td><td align="center" width="170px"><a href="https://github.com/jianhuishi"><img src="https://avatars.githubusercontent.com/jianhuishi" width="80px;" style="border-radius: 50%;" alt="Jianhui Shi"/><br /><b>Jianhui Shi</b></a><br /><sub>开发者</sub><br /><a href="mailto:shijianhui@chinamobile.com" title="Email Jianhui Shi">📧</a></td><td align="center" width="170px"><a href="https://github.com/liuyingdi2025"><img src="https://avatars.githubusercontent.com/liuyingdi2025" width="80px;" style="border-radius: 50%;" alt="Yingdi Liu"/><br /><b>Yingdi Liu</b></a><br /><sub>开发者</sub><br /><a href="mailto:liuyingdi@chinamobile.com" title="Email Yingdi Liu">📧</a></td><td align="center" width="170px"><a href="https://github.com/hqy479"><img src="https://avatars.githubusercontent.com/hqy479" width="80px;" style="border-radius: 50%;" alt="Qiuyang He"/><br /><b>Qiuyang He</b></a><br /><sub>开发者</sub><br />-</td></tr><tr><td align="center" width="170px"><a href="https://github.com/ljx139"><img src="https://avatars.githubusercontent.com/ljx139" width="80px;" style="border-radius: 50%;" alt="LiuJX"/><br /><b>LiuJX</b></a><br /><sub>开发者</sub><br />-</td><td align="center" width="170px"><a href="https://github.com/Cjdddd"><img src="https://avatars.githubusercontent.com/Cjdddd" width="80px;" style="border-radius: 50%;" alt="Cjdddd"/><br /><b>Cjdddd</b></a><br /><sub>开发者</sub><br /><a href="mailto:cuijindong@chinamobile.com" title="Email Cjdddd">📧</a></td><td align="center" width="170px"><a href="https://github.com/wwy99"><img src="https://avatars.githubusercontent.com/wwy99" width="80px;" style="border-radius: 50%;" alt="Weiyu Wang"/><br /><b>Weiyu Wang</b></a><br /><sub>开发者</sub><br /><a href="mailto:wangweiyu@chinamobile.com" title="Email Weiyu Wang">📧</a></td><td align="center" width="170px"></td><td align="center" width="170px"></td></tr></table>

## 开源协议

本项目遵循 **Apache License 2.0** 协议。

详情请参阅 [LICENSE](./LICENSE)。

贡献代码前需要签署 [贡献者许可协议 (CLA)](CLA.md)。
