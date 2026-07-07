<p align="center">
  <img src="asset/image/wutong-data-color.svg" height="60" alt="梧桐数据">
  <img src="asset/image/divider-vertical.png" height="48" alt="">
  <img src="asset/image/jiutian-intelligent-color.svg" height="60" alt="九天智能">
</p>

<p align="center">
  <img src="https://img.shields.io/badge/version-1.3.4-blue.svg" alt="Version">
  <img src="https://img.shields.io/badge/Python-3.11+-blue.svg" alt="Python">
  <img src="https://img.shields.io/badge/License-Apache%202.0-green.svg" alt="License">
  <img src="https://img.shields.io/badge/PRs-welcome-brightgreen.svg" alt="PRs Welcome">
</p>

<p align="center">
  <strong>构建可组合 AI Agent 的生产级框架</strong><br>
  轻松构建强大、模块化且易于维护的 AI Agent 应用。
</p>

<p align="center">
  <a href="docs/ARCHITECTURE.md">文档</a> &nbsp;·&nbsp;
  <a href="#快速上手">快速上手</a> &nbsp;·&nbsp;
  <a href="#示例">示例</a> &nbsp;·&nbsp;
  <a href="README.md">English</a>
</p>

---

## 什么是 Alphora?

Alphora 是一个用于构建生产级 AI Agent 的全栈框架。它提供了你所需要的一切核心能力——Agent 编排、工具执行、记忆管理、安全代码沙箱、Skills 生态、流式输出以及部署——所有功能都采用异步优先、兼容 OpenAI 的设计。

```python
from alphora.agent import SkillAgent
from alphora.models import OpenAILike
from alphora.sandbox import Sandbox

agent = SkillAgent(
    llm=OpenAILike(model_name="gpt-4"),
    skill_paths=["./skills"],
    sandbox=Sandbox(runtime="docker"),
    system_prompt="You are a data analyst. Explore data before coding.",
)

result = await agent.run("Analyze sales.xlsx and find the top-performing regions.")
```

## 安装

```bash
pip install alphora

# 可选扩展
pip install "alphora[mcp]"   # MCP 工具接入
pip install "alphora[cli]"   # 终端 rich 分屏渲染
```

生产环境并发 API 建议使用 **alphora >= 1.3.3**（修复请求级 config / 沙箱隔离问题）。

---

## 特性

- **ReAct 与 Plan-Execute** — 内置推理-行动循环，支持自动工具编排、重试逻辑和迭代控制。先规划，再执行。
- **Agent 派生** — 子 Agent 通过 `derive()` 继承父级的 LLM、记忆和配置。网关可按请求派生主控、专家或快速路径 Agent（见[生产参考](#生产参考)）。
- **零配置工具** — `@tool` 装饰器根据类型提示和文档字符串自动生成 OpenAI 函数调用 Schema。支持 Pydantic V2 校验、并行执行、实例方法绑定。
- **智能记忆** — 多会话隔离，可组合的处理器管道（`keep_last`、`token_budget`、`summarize_tool_calls` 等），置顶/标签系统，撤销/重做。
- **代码沙箱** — 在 Local / Docker / 远程 Docker 环境中运行 Agent 生成的代码，支持文件隔离、包管理和安全策略。
- **Skills 生态** — 兼容 [agentskills.io](https://agentskills.io)，三阶段渐进加载（元数据 → 指令 → 资源）优化 Token 用量。
- **类型化流式输出** — 原生异步 SSE，带内容类型标注（`char`、`think`、`result`、`sql`、`chart`）。配合 `ToolCallStreamRenderPP` 将工具调用渲染为前端可解析的 SSE chunk。
- **提示词引擎** — Jinja2 模板、`ParallelPrompt` 并发执行、自动长文本续写突破 Token 限制。
- **统一 Hooks** — 一套事件系统覆盖工具、记忆、LLM、沙箱和 Agent 全生命周期。默认 fail-open，支持优先级、超时和错误策略。
- **多 Agent 协作** — `AgentCollabScope` + `TaggedCallback` 为并行子 Agent 流打标签，支持丰富的前端展示。
- **MCP 集成** — `pip install "alphora[mcp]"` 后通过 `setup_mcp(servers=[...])` 接入 stdio / SSE / HTTP MCP 服务。
- **多模型支持** — 兼容任意 OpenAI 标准 API（GPT、Claude、Qwen、DeepSeek、本地模型）。支持多模态输入（文本、图像、音频、视频）。
- **LLM 负载均衡** — 通过 `llm1 + llm2` 组合多个后端，支持轮询或随机分发。
- **思考模式** — 原生支持推理模型，独立的思考流与内容流。
- **一键部署** — `publish_agent_api(agent, method=...)` 将任意 Agent 发布为兼容 OpenAI 的 REST API，内置会话管理和 SSE 流式传输。
- **Web UI** — 内置 AgentChat 前端，通过 `alphora-web` 启动（默认 `http://localhost:8813`）。
- **调试追踪** — `debugger=True` 启用可视化调试器 `http://localhost:9527`（实验性）；生产环境亦可用 `MessageInspector` 做轻量 HTML trace。

---

## 快速上手

### 1. 带工具的 Agent

```python
from alphora.agent import ReActAgent
from alphora.models import OpenAILike
from alphora.tools import tool

@tool
def get_weather(city: str, unit: str = "celsius") -> str:
    """Get current weather for a city."""
    return f"Weather in {city}: 22°{unit[0].upper()}, Sunny"

agent = ReActAgent(
    llm=OpenAILike(model_name="gpt-4"),
    tools=[get_weather],
    system_prompt="You are a helpful assistant.",
)

result = await agent.run("What's the weather in Tokyo?")
```

### 2. 代码沙箱

在隔离的 Docker 容器中运行 Agent 生成的代码。镜像在首次使用时自动构建。Docker 构建、远程 Docker 和 TLS 配置详见 [沙箱文档](docs/components/cn/sandbox_readme.md)。

```python
from alphora.sandbox import Sandbox

async with Sandbox(runtime="docker", workspace_root="/data/workspace") as sandbox:
    result = await sandbox.execute_code("print(6 * 7)")
    print(result.stdout)  # 42

    await sandbox.write_file("outputs/result.txt", "done")
    files = await sandbox.list_files()
```

### 3. 部署为 API

将任意 Agent 发布为兼容 OpenAI 的 REST API。`method` 为 Agent 上接收 `OpenAIRequest` 的 async 方法名（参见 [examples/api_mock](./examples/api_mock)）：

```python
from alphora.server.quick_api import publish_agent_api, APIPublisherConfig

config = APIPublisherConfig(path="/v1")
app = publish_agent_api(agent, method="start", config=config)
# uvicorn main:app --port 8000
```

```bash
curl -N http://localhost:8000/v1/chat/completions \
  -H "Content-Type: application/json" \
  -d '{"messages":[{"role":"user","content":"Hello!"}],"stream":true,"session_id":"demo-1"}'
```

常见生产路径：默认 `path="/alphadata"` → `/alphadata/chat/completions`；设置 `sandbox_workspace` 可启用内置文件浏览 API。`OpenAIRequest` 通过 `model_extra` 支持扩展字段（如 `mode`），供应用层自定义路由。

### 4. Web UI

启动内置 AgentChat 前端（指向 §3 的后端）：

```bash
alphora-web
# 浏览器打开 http://localhost:8813 — API Path 需与后端一致（如 /alphadata/chat/completions）
```

---

## 示例

| 示例 | 描述 |
|------|------|
| [ChatExcel](./examples/chat_excel) | SkillAgent + Sandbox 数据分析 — 框架能力入门 |
| [Deep Research](./examples/deep_research) | 多步骤深度调研 Agent，含网页搜索和报告生成 |
| [api_mock](./examples/api_mock) | 最小 `publish_agent_api` 联调示例 |

---

## 生产参考

生产应用建议使用**网关 Agent**，负责按请求创建沙箱并通过 `derive()` 派生子 Agent：

```python
from alphora.agent import BaseAgent
from alphora.server.openai_request_body import OpenAIRequest
from alphora.server.quick_api import publish_agent_api, APIPublisherConfig

class AppGateway(BaseAgent):
    async def serve(self, request: OpenAIRequest):
        sandbox = await self.create_sandbox(session_id=request.session_id, runtime="docker")
        self.update_config("sandbox", sandbox)
        orchestrator = self.derive(OrchestratorAgent)
        await orchestrator.run(request=request)
        await sandbox.destroy()

app = publish_agent_api(
    AppGateway(),
    method="serve",
    config=APIPublisherConfig(path="/alphadata/v1/", sandbox_workspace="/data/sandbox"),
)
```

**AlphaData Core** 在此基础上扩展了：

- 主控 + 专家注册表 + `call_specialist` 上下文隔离
- `app.include_router(...)` 挂载 Skills、MCP、文件等业务 REST API
- 扩展 SSE 协议（`task_graph`、`tool_call`、`usage` 等）

---

## 配置

```bash
export LLM_API_KEY="your-api-key"
export LLM_BASE_URL="https://api.openai.com/v1"
export DEFAULT_LLM="gpt-4"

# 可选
export EMBEDDING_API_KEY="your-key"
export EMBEDDING_URL="https://api.openai.com/v1"
export EMBEDDING_MODEL="text-embedding-3-small"
```

框架通过上述环境变量支持快速上手。大型部署可使用 YAML profile 配置（参见 AlphaData Core 的 `configs/README.md`）。

---

## 文档

关于系统设计、组件关系和实现模式的详细信息，请参阅 [架构指南](./docs/ARCHITECTURE.md)。

### 组件概览

| 组件                                                     | 描述 |
|----------------------------------------------------------|------|
| [Agent](docs/components/cn/agent_readme.md)               | 核心 Agent 生命周期、派生、ReAct 循环 |
| [Prompter](docs/components/cn/prompter_readme.md)         | Jinja2 模板、LLM 调用、流式传输 |
| [Models](docs/components/cn/model_readme.md)              | LLM 接口、多模态、负载均衡 |
| [Tools](docs/components/cn/tool_readme.md)                | tool 装饰器、注册表、并行执行 |
| [Memory](docs/components/cn/memory_readme.md)             | 会话管理、历史记录、置顶/标签系统 |
| [Storage](docs/components/cn/storage_readme.md)           | 持久化后端（内存、JSON、SQLite） |
| [Sandbox](docs/components/cn/sandbox_readme.md)           | 安全代码执行、本地/Docker/远程 |
| [Skills](docs/components/cn/skill_readme.md)              | agentskills.io 兼容、SkillAgent 集成 |
| [Hooks](docs/components/cn/hooks_readme.md)               | 通过统一 Hook 事件进行扩展与治理 |
| [Server](docs/components/cn/server_readme.md)             | API 发布、SSE 流式传输 |
| [Postprocess](docs/components/cn/postprocess_readme.md)   | 流式转换流水线 |
| [MCP](docs/components/cn/mcp_readme.md)                   | 通过 `setup_mcp()` 接入 MCP |
| [Web](alphora/web/README.md)                            | AgentChat 前端与 `alphora-web` CLI |

---

## 贡献者

由 AlphaData 团队精心打造。

<table><tr><td align="center" width="170px"><a href="https://github.com/tian-cmcc"><img src="https://github.com/tian-cmcc.png" width="80px;" style="border-radius: 50%;" alt="Tian Tian"/><br /><b>Tian Tian</b></a><br /><sub>项目负责人 & 核心开发</sub><br /><a href="mailto:tiantianit@chinamobile.com" title="Email Tian Tian">📧</a></td><td align="center" width="170px"><a href="https://github.com/yilingliang"><img src="https://github.com/yilingliang.png" width="80px;" style="border-radius: 50%;" alt="Yuhang Liang"/><br /><b>Yuhang Liang</b></a><br /><sub>开发者</sub><br /><a href="mailto:liangyuhang@chinamobile.com" title="Email Yuhang Liang">📧</a></td><td align="center" width="170px"><a href="https://github.com/jianhuishi"><img src="https://github.com/jianhuishi.png" width="80px;" style="border-radius: 50%;" alt="Jianhui Shi"/><br /><b>Jianhui Shi</b></a><br /><sub>开发者</sub><br /><a href="mailto:shijianhui@chinamobile.com" title="Email Jianhui Shi">📧</a></td><td align="center" width="170px"><a href="https://github.com/liuyingdi2025"><img src="https://github.com/liuyingdi2025.png" width="80px;" style="border-radius: 50%;" alt="Yingdi Liu"/><br /><b>Yingdi Liu</b></a><br /><sub>开发者</sub><br /><a href="mailto:liuyingdi@chinamobile.com" title="Email Yingdi Liu">📧</a></td><td align="center" width="170px"><a href="https://github.com/Cjdddd"><img src="https://github.com/Cjdddd.png" width="80px;" style="border-radius: 50%;" alt="Cjdddd"/><br /><b>Cjdddd</b></a><br /><sub>开发者</sub><br /><a href="mailto:cuijindong@chinamobile.com" title="Email Cjdddd">📧</a></td><td align="center" width="170px"><a href="https://github.com/wwy99"><img src="https://github.com/wwy99.png" width="80px;" style="border-radius: 50%;" alt="Weiyu Wang"/><br /><b>Weiyu Wang</b></a><br /><sub>开发者</sub><br /><a href="mailto:wangweiyu@chinamobile.com" title="Email Weiyu Wang">📧</a></td><td align="center" width="170px"></td><td align="center" width="170px"></td></tr></table>

## 开源协议

本项目遵循 **Apache License 2.0** 协议。  
详情请参阅 [LICENSE](./LICENSE)。

贡献代码前需要签署 [贡献者许可协议 (CLA)](CLA.md)。
