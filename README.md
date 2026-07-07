<p align="center">
  <img src="asset/image/wutong-data-color.svg" height="60" alt="梧桐数据">
  <span style="display:inline-block; width:1px; height:48px; background:#999; margin:0 24px; vertical-align:middle;"></span>
  <img src="asset/image/jiutian-intelligent-color.svg" height="60" alt="九天智能">
</p>

<p align="center">
  <img src="https://img.shields.io/badge/version-1.2.3-blue.svg" alt="Version">
  <img src="https://img.shields.io/badge/Python-3.11+-blue.svg" alt="Python">
  <img src="https://img.shields.io/badge/License-Apache%202.0-green.svg" alt="License">
  <img src="https://img.shields.io/badge/PRs-welcome-brightgreen.svg" alt="PRs Welcome">
</p>

<p align="center">
  <strong>A Production-Ready Framework for Building Composable AI Agents</strong><br>
  Build powerful, modular, and maintainable AI agent applications with ease.
</p>

<p align="center">
  <a href="docs/ARCHITECTURE.md">Docs</a> &nbsp;·&nbsp;
  <a href="#quick-start">Quick Start</a> &nbsp;·&nbsp;
  <a href="#examples">Examples</a> &nbsp;·&nbsp;
  <a href="README.cn.md">中文</a>
</p>

---

## What is Alphora?

Alphora is a full-stack framework for building production AI agents. It provides everything you need — agent orchestration, tool execution, memory management, secure code sandbox, skills ecosystem, streaming, and deployment — all with an async-first, OpenAI-compatible design.

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

## Installation

```bash
pip install alphora
```

---

## Features

- **ReAct & Plan-Execute** — Built-in reasoning-action loops with automatic tool orchestration, retry logic, and iteration control. Plan first, then execute.
- **Agent Derivation** — Child agents inherit LLM, memory, and config from parents via `derive()`. Build hierarchies that share context efficiently.
- **Zero-Config Tools** — `@tool` decorator auto-generates OpenAI function calling schema from type hints and docstrings. Pydantic V2 validation, parallel execution, instance method support.
- **Smart Memory** — Multi-session isolation with composable processor pipeline (`keep_last`, `token_budget`, `summarize`, etc.), pin/tag system, and undo/redo.
- **Code Sandbox** — Run agent-generated code in Local / Docker / Remote Docker environments with file isolation, package management, and security policies.
- **Skills Ecosystem** — [agentskills.io](https://agentskills.io) compatible. 3-phase progressive loading (metadata → instructions → resources) to optimize token budget.
- **Typed Streaming** — Native async SSE with content types (`char`, `think`, `result`, `sql`, `chart`) so frontends can render each type differently.
- **Prompt Engine** — Jinja2 templates, `ParallelPrompt` for concurrent execution, and auto long-text continuation to bypass token limits.
- **Unified Hooks** — One event system across tools, memory, LLM, sandbox, and agent lifecycle. Fail-open by default, with priority, timeout, and error policy controls.
- **Multi-Model Support** — Works with any OpenAI-compatible API (GPT, Claude, Qwen, DeepSeek, local models). Multimodal input (text, image, audio, video).
- **LLM Load Balancing** — Combine multiple backends with `llm1 + llm2` for automatic round-robin / random load balancing and failover.
- **Thinking Mode** — First-class support for reasoning models with separate thinking / content streams.
- **One-Line Deploy** — `publish_agent_api(agent)` serves any agent as an OpenAI-compatible REST API with built-in session management and SSE streaming.
- **Debug Tracing** — Built-in visual debugger for agent execution flow, LLM calls, and tool invocations.

---

## Quick Start

### 1. Agent with Tools

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

### 2. Code Sandbox

Run agent-generated code in an isolated Docker container. The image is built automatically on first use. See the [Sandbox docs](docs/components/cn/sandbox_readme.md) for Docker build, remote Docker, and TLS configuration.

```python
from alphora.sandbox import Sandbox

async with Sandbox(runtime="docker", workspace_root="/data/workspace") as sandbox:
    result = await sandbox.execute_code("print(6 * 7)")
    print(result.stdout)  # 42

    await sandbox.write_file("outputs/result.txt", "done")
    files = await sandbox.list_files()
```

### 3. Deploy as API

Publish any agent as an OpenAI-compatible REST API in one line:

```python
from alphora.server.quick_api import publish_agent_api

app = publish_agent_api(agent)
# uvicorn main:app --port 8000
```

```bash
curl -X POST http://localhost:8000/chat/completions \
  -H "Content-Type: application/json" \
  -d '{"messages": [{"role": "user", "content": "Hello!"}], "stream": true}'
```

---

## Examples

| Example | Description |
|---------|-------------|
| [ChatExcel](./examples/chat_excel) | Data analysis agent with skill-driven workflow and sandbox code execution |
| [Deep Research](./examples/deep_research) | Multi-step research agent with web search and report generation |


---

## Configuration

```bash
export LLM_API_KEY="your-api-key"
export LLM_BASE_URL="https://api.openai.com/v1"
export DEFAULT_LLM="gpt-4"

# Optional
export EMBEDDING_API_KEY="your-key"
export EMBEDDING_BASE_URL="https://api.openai.com/v1"
```

---

## Documentation

For detailed system design, component relationships, and implementation patterns, see the [Architecture Guide](./docs/ARCHITECTURE.md).

### Component Overview

| Component                                                | Description |
|----------------------------------------------------------|-------------|
| [Agent](docs/components/cn/agent_readme.md)              | Core agent lifecycle, derivation, ReAct loop |
| [Prompter](docs/components/cn/prompter_readme.md)        | Jinja2 templates, LLM invocation, streaming |
| [Models](docs/components/cn/model_readme.md)             | LLM interface, multimodal, load balancing |
| [Tools](docs/components/cn/tool_readme.md)               | tool decorator, registry, parallel execution |
| [Memory](docs/components/cn/memory_readme.md)            | Session management, history, pin/tag system |
| [Storage](docs/components/cn/storage_readme.md)          | Persistent backends (memory, JSON, SQLite) |
| [Sandbox](docs/components/cn/sandbox_readme.md)          | Secure code execution, local/Docker/remote |
| [Skills](docs/components/cn/skill_readme.md)             | agentskills.io compatible, SkillAgent integration |
| [Hooks](docs/components/cn/hooks_readme.md)              | Extension & governance via unified hook events |
| [Server](docs/components/cn/server_readme.md)            | API publishing, SSE streaming |
| [Postprocess](docs/components/cn/postprocess_readme.md)  | Stream transformation pipeline |

---

## Contributors

Crafted by the AlphaData Team. 

<table><tr><td align="center" width="170px"><a href="https://github.com/tian-cmcc"><img src="https://avatars.githubusercontent.com/tian-cmcc" width="80px;" style="border-radius: 50%;" alt="Tian Tian"/><br /><b>Tian Tian</b></a><br /><sub>Project Lead & Core Dev</sub><br /><a href="mailto:tiantianit@chinamobile.com" title="Email Tian Tian">📧</a></td><td align="center" width="170px"><a href="https://github.com/yilingliang"><img src="https://avatars.githubusercontent.com/yilingliang" width="80px;" style="border-radius: 50%;" alt="Yuhang Liang"/><br /><b>Yuhang Liang</b></a><br /><sub>Developer</sub><br /><a href="mailto:liangyuhang@chinamobile.com" title="Email Yuhang Liang">📧</a></td><td align="center" width="170px"><a href="https://github.com/jianhuishi"><img src="https://avatars.githubusercontent.com/jianhuishi" width="80px;" style="border-radius: 50%;" alt="Jianhui Shi"/><br /><b>Jianhui Shi</b></a><br /><sub>Developer</sub><br /><a href="mailto:shijianhui@chinamobile.com" title="Email Jianhui Shi">📧</a></td><td align="center" width="170px"><a href="https://github.com/liuyingdi2025"><img src="https://avatars.githubusercontent.com/liuyingdi2025" width="80px;" style="border-radius: 50%;" alt="Yingdi Liu"/><br /><b>Yingdi Liu</b></a><br /><sub>Developer</sub><br /><a href="mailto:liuyingdi@chinamobile.com" title="Email Yingdi Liu">📧</a></td><td align="center" width="170px"><a href="https://github.com/Cjdddd"><img src="https://avatars.githubusercontent.com/Cjdddd" width="80px;" style="border-radius: 50%;" alt="Cjdddd"/><br /><b>Cjdddd</b></a><br /><sub>Developer</sub><br /><a href="mailto:cuijindong@chinamobile.com" title="Email Cjdddd">📧</a></td><td align="center" width="170px"><a href="https://github.com/wwy99"><img src="https://avatars.githubusercontent.com/wwy99" width="80px;" style="border-radius: 50%;" alt="Weiyu Wang"/><br /><b>Weiyu Wang</b></a><br /><sub>Developer</sub><br /><a href="mailto:wangweiyu@chinamobile.com" title="Email Weiyu Wang">📧</a></td><td align="center" width="170px"></td><td align="center" width="170px"></td></tr></table>

## License

This project is licensed under the **Apache License 2.0**.  
See [LICENSE](./LICENSE) for details.

Contributions require acceptance of the [Contributor License Agreement (CLA)](CLA.md).
