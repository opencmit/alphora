<p align="center">
  <img src="asset/image/new_logo.png" width="360" alt="Alphora">
</p>

<p align="center">
  <img src="https://img.shields.io/badge/version-1.2.3-blue.svg" alt="Version">
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
    system_prompt="你是一位数据分析专家，先探查数据再编码。",
)

result = await agent.run("分析 sales.xlsx，找出表现最好的区域。")
```

<p align="center">
  <em>完整演示 — 从上传数据到产出洞察的完整数据分析流程：</em>
</p>

<p align="center">
  <a href="https://github.com/user-attachments/assets/YOUR_VIDEO_ID_HERE">
    <img src="https://github.com/user-attachments/assets/YOUR_THUMBNAIL_ID_HERE" width="600" alt="Alphora 演示：数据分析 Agent">
  </a>
</p>

<!-- 上传视频后，将上方链接替换为实际的 GitHub 视频/缩略图 URL -->

## 安装

```bash
pip install alphora
```

---

## 为什么选择 Alphora？

与主流 Agent 框架的快速对比：

| 能力 | Alphora | LangChain / LangGraph | Agno | CrewAI |
|:-----|:--------|:----------------------|:-----|:-------|
| **Agent 编排** | ✅ ReAct、Plan-Execute、层级派生 | ✅ 图编排 StateGraph，最灵活 | ✅ 团队模式，5 级抽象 | ✅ 角色分工 |
| **工具系统** | ✅ `@tool`，自动 Schema，并行执行 | ✅ `@tool` + 700+ 集成 | ✅ `@tool` + Toolkit | ✅ `@tool` + 委派 |
| **记忆管理** | ✅ 处理器管道、置顶/标签、撤销/重做 | ✅ 多种 Memory 类，Redis/Postgres | ✅ 自动会话 + 统一数据库 | ⚠️ 基础短期/长期记忆 |
| **代码沙箱** | ✅ 内置 Local / Docker / 远程 Docker | ⚠️ 需第三方（E2B 等） | ❌ 无内置 | ❌ 无内置 |
| **类型化流式输出** | ✅ SSE 含 `think`、`result`、`sql`、`chart` | ⚠️ SSE（纯文本） | ⚠️ SSE（纯文本） | ⚠️ SSE（纯文本） |
| **Hooks 与可观测性** | ✅ 跨全组件统一 Hook 系统 | ⚠️ Callbacks + LangSmith (SaaS) | ⚠️ AgentOS 基础指标 | ❌ 有限 |
| **提示词引擎** | ✅ Jinja2、ParallelPrompt、自动续写 | ✅ 自有模板 + RunnableParallel | ⚠️ 字符串 / Jinja2 | ⚠️ 字符串模板 |
| **一键部署** | ✅ `publish_agent_api()`，兼容 OpenAI | ✅ LangServe / LangGraph Platform | ✅ 内置 FastAPI 路由 | ✅ 内置 serve |
| **Skills 生态** | ✅ [agentskills.io](https://agentskills.io)，三阶段加载 | ⚠️ Hub（社区 chains） | ❌ 无内置 | ❌ 无内置 |
| **LLM 负载均衡** | ✅ 内置轮询 / 随机 | ⚠️ 通过 LangSmith 路由 | ❌ 无内置 | ❌ 无内置 |
| **多模型支持** | ✅ 任意 OpenAI 兼容 API | ✅ 700+ 模型集成 | ✅ 多提供商，~3μs 初始化 | ✅ 多提供商 |

**一句话总结：** Alphora 提供自包含的生产就绪技术栈，在**内置沙箱**、**全链路 Hooks**、**类型化流式输出**方面尤为突出，无需依赖外部 SaaS 或大量插件。

---

## 核心特性

- **ReAct 与 Plan-Execute** — 内置推理-行动循环，支持自动工具编排、重试逻辑和迭代控制。先规划，再执行。
- **Agent 派生** — 子 Agent 通过 `derive()` 继承父级的 LLM、记忆和配置，高效构建共享上下文的层级结构。
- **零配置工具** — `@tool` 装饰器根据类型提示和文档字符串自动生成 OpenAI 函数调用 Schema。支持 Pydantic V2 校验、并行执行、实例方法绑定。
- **智能记忆** — 多会话隔离，可组合的处理器管道（`keep_last`、`token_budget`、`summarize` 等），置顶/标签系统，撤销/重做。
- **代码沙箱** — 在 Local / Docker / 远程 Docker 环境中运行 Agent 生成的代码，支持文件隔离、包管理和安全策略。
- **Skills 生态** — 兼容 [agentskills.io](https://agentskills.io)，三阶段渐进加载（元数据 → 指令 → 资源）优化 Token 用量。
- **类型化流式输出** — 原生异步 SSE，带内容类型标注（`char`、`think`、`result`、`sql`、`chart`），前端可按类型差异化渲染。
- **提示词引擎** — Jinja2 模板、`ParallelPrompt` 并发执行、自动长文本续写突破 Token 限制。
- **统一 Hooks** — 一套事件系统覆盖工具、记忆、LLM、沙箱和 Agent 全生命周期。默认 fail-open，支持优先级、超时和错误策略。
- **多模型支持** — 兼容任意 OpenAI 标准 API（GPT、Claude、Qwen、DeepSeek、本地模型）。支持多模态输入（文本、图像、音频、视频）。
- **LLM 负载均衡** — 通过 `llm1 + llm2` 组合多个后端，自动轮询/随机负载均衡与故障转移。
- **思考模式** — 原生支持推理模型，独立的思考流与内容流。
- **一键部署** — `publish_agent_api(agent)` 将任意 Agent 发布为兼容 OpenAI 的 REST API，内置会话管理和 SSE 流式传输。
- **调试追踪** — 内置可视化调试器，追踪 Agent 执行流、LLM 调用和工具调用。

---

## 快速上手

### 1. Agent + 工具

```python
from alphora.agent import ReActAgent
from alphora.models import OpenAILike
from alphora.tools import tool

@tool
def get_weather(city: str, unit: str = "celsius") -> str:
    """获取指定城市的当前天气。"""
    return f"{city} 的天气：22°{unit[0].upper()}, 晴"

agent = ReActAgent(
    llm=OpenAILike(model_name="gpt-4"),
    tools=[get_weather],
    system_prompt="你是一个得力的助手。",
)

result = await agent.run("东京的天气怎么样？")
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

一行代码将任意 Agent 发布为兼容 OpenAI 的 REST API：

```python
from alphora.server.quick_api import publish_agent_api

app = publish_agent_api(agent)
# uvicorn main:app --port 8000
```

```bash
curl -X POST http://localhost:8000/chat/completions \
  -H "Content-Type: application/json" \
  -d '{"messages": [{"role": "user", "content": "你好！"}], "stream": true}'
```

---

## 示例

| 示例 | 描述 |
|------|------|
| [ChatExcel](./examples/chat_excel) | 基于 Skill 驱动工作流的数据分析 Agent，含沙箱代码执行 |
| [Deep Research](./examples/deep_research) | 多步骤深度调研 Agent，含网页搜索和报告生成 |

---

## 配置

```bash
export LLM_API_KEY="your-api-key"
export LLM_BASE_URL="https://api.openai.com/v1"
export DEFAULT_LLM="gpt-4"

# 可选
export EMBEDDING_API_KEY="your-key"
export EMBEDDING_BASE_URL="https://api.openai.com/v1"
```

---

## 文档

关于系统设计、组件关系和实现模式的详细信息，请参阅 [架构指南](./docs/ARCHITECTURE.md)。

### 组件概览

| 组件 | 描述 |
|------|------|
| [Agent](docs/components/cn/agent_readme.md) | 核心 Agent 生命周期、派生、ReAct 循环 |
| [Prompter](docs/components/cn/prompter_readme.md) | Jinja2 模板、LLM 调用、流式传输 |
| [Models](docs/components/cn/model_readme.md) | LLM 接口、多模态、负载均衡 |
| [Tools](docs/components/cn/tool_readme.md) | tool 装饰器、注册表、并行执行 |
| [Memory](docs/components/cn/memory_readme.md) | 会话管理、历史记录、置顶/标签系统 |
| [Storage](docs/components/cn/storage_readme.md) | 持久化后端（内存、JSON、SQLite） |
| [Sandbox](docs/components/cn/sandbox_readme.md) | 安全代码执行、本地/Docker/远程 |
| [Skills](docs/components/cn/skill_readme.md) | agentskills.io 兼容、SkillAgent 集成 |
| [Hooks](docs/components/cn/hooks_readme.md) | 通过统一 Hook 事件进行扩展与治理 |
| [Server](docs/components/cn/server_readme.md) | API 发布、SSE 流式传输 |
| [Postprocess](docs/components/cn/postprocess_readme.md) | 流式转换流水线 |

---

## 贡献者

由 AlphaData 团队精心打造。

<table><tr><td align="center" width="170px"><a href="https://github.com/tian-cmcc"><img src="https://avatars.githubusercontent.com/tian-cmcc" width="80px;" style="border-radius: 50%;" alt="Tian Tian"/><br /><b>Tian Tian</b></a><br /><sub>项目负责人 & 核心开发</sub><br /><a href="mailto:tiantianit@chinamobile.com" title="Email Tian Tian">📧</a></td><td align="center" width="170px"><a href="https://github.com/yilingliang"><img src="https://cdn.jsdelivr.net/gh/yilingliang/picbed/mdings/48301768.gif" width="80px;" style="border-radius: 50%;" alt="Yuhang Liang"/><br /><b>Yuhang Liang</b></a><br /><sub>开发者</sub><br /><a href="mailto:liangyuhang@chinamobile.com" title="Email Yuhang Liang">📧</a></td><td align="center" width="170px"><a href="https://github.com/jianhuishi"><img src="https://avatars.githubusercontent.com/jianhuishi" width="80px;" style="border-radius: 50%;" alt="Jianhui Shi"/><br /><b>Jianhui Shi</b></a><br /><sub>开发者</sub><br /><a href="mailto:shijianhui@chinamobile.com" title="Email Jianhui Shi">📧</a></td><td align="center" width="170px"><a href="https://github.com/liuyingdi2025"><img src="https://avatars.githubusercontent.com/liuyingdi2025" width="80px;" style="border-radius: 50%;" alt="Yingdi Liu"/><br /><b>Yingdi Liu</b></a><br /><sub>开发者</sub><br /><a href="mailto:liuyingdi@chinamobile.com" title="Email Yingdi Liu">📧</a></td><td align="center" width="170px"><a href="https://github.com/hqy479"><img src="https://avatars.githubusercontent.com/hqy479" width="80px;" style="border-radius: 50%;" alt="Qiuyang He"/><br /><b>Qiuyang He</b></a><br /><sub>开发者</sub><br />-</td></tr><tr><td align="center" width="170px"><a href="https://github.com/ljx139"><img src="https://avatars.githubusercontent.com/ljx139" width="80px;" style="border-radius: 50%;" alt="LiuJX"/><br /><b>LiuJX</b></a><br /><sub>开发者</sub><br />-</td><td align="center" width="170px"><a href="https://github.com/Cjdddd"><img src="https://avatars.githubusercontent.com/Cjdddd" width="80px;" style="border-radius: 50%;" alt="Cjdddd"/><br /><b>Cjdddd</b></a><br /><sub>开发者</sub><br /><a href="mailto:cuijindong@chinamobile.com" title="Email Cjdddd">📧</a></td><td align="center" width="170px"><a href="https://github.com/wwy99"><img src="https://avatars.githubusercontent.com/wwy99" width="80px;" style="border-radius: 50%;" alt="Weiyu Wang"/><br /><b>Weiyu Wang</b></a><br /><sub>开发者</sub><br /><a href="mailto:wangweiyu@chinamobile.com" title="Email Weiyu Wang">📧</a></td><td align="center" width="170px"></td><td align="center" width="170px"></td></tr></table>

## 开源协议

本项目遵循 **Apache License 2.0** 协议。

详情请参阅 [LICENSE](./LICENSE)。

贡献代码前需要签署 [贡献者许可协议 (CLA)](CLA.md)。
