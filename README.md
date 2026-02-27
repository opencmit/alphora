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
  <strong>A Production-Ready Framework for Building Composable AI Agents</strong>
</p>

<p align="center">
  Build powerful, modular, and maintainable AI agent applications with ease.
</p>

<p align="center">
  <a href="docs/ARCHITECTURE.md">Docs</a> •
  <a href="#quick-start">Quick Start</a> •
  <a href="#examples">Examples</a> •
  <a href="README.cn.md">中文</a>
</p>

---

## What is Alphora?

Alphora is a full-stack framework for building production AI agents. It provides everything you need — agent orchestration, tool execution, memory management, secure code sandbox, skills ecosystem, streaming, and deployment — all with an async-first, OpenAI-compatible design.

```python
from alphora.agent import ReActAgent
from alphora.models import OpenAILike
from alphora.tools import tool

@tool
def get_weather(city: str) -> str:
    """Get current weather for a city."""
    return f"Weather in {city}: 22°C, Sunny"

agent = ReActAgent(
    llm=OpenAILike(model_name="gpt-4"),
    tools=[get_weather],
    system_prompt="You are a helpful assistant.",
)

result = await agent.run("What's the weather in BeiJing?")
```

## Installation

```bash
pip install alphora
```

---

## Features

### Agent System

- **ReAct Loop** — Built-in reasoning-action loop with automatic tool orchestration, retry logic, and iteration control.
- **Agent Derivation** — Child agents inherit LLM, memory, and config from parents. Build hierarchies that share context.
- **Streaming First** — Native async streaming with OpenAI SSE format. Multiple content types: `char`, `think`, `result`, `sql`, `chart`.
- **Debug Tracing** — Built-in visual debugger for agent execution flow, LLM calls, and tool invocations.

### Model Layer

- **OpenAI Compatible** — Works with any OpenAI-compatible API: GPT, Claude, Qwen, DeepSeek, local models.
- **Multimodal Support** — Unified `Message` class for text, images, audio, and video inputs.
- **Load Balancing** — Built-in round-robin/random load balancing across multiple LLM backends.
- **Thinking Mode** — Support for reasoning models (Qwen3, etc.) with separate thinking/content streams.
- **Embedding API** — Unified text embedding interface with batch processing.

### Tool System

- **Zero-Config Tools** — `@tool` decorator auto-generates OpenAI function calling schema from type hints and docstrings.
- **Type Safety** — Pydantic V2 validation for all tool parameters. Automatic error feedback to LLM.
- **Async Native** — Async tools run natively; sync tools auto-execute in thread pool.
- **Parallel Execution** — Execute multiple tool calls concurrently for better performance.
- **Instance Methods** — Register class methods as tools with access to `self` context (DB connections, user state, etc.).

### Prompt Engine

- **Jinja2 Templates** — Dynamic prompts with variable interpolation, conditionals, loops, and includes.
- **Long Text Continuation** — Auto-detect truncation and continue generation to bypass token limits.
- **Parallel Prompts** — Execute multiple prompts concurrently with `ParallelPrompt`.
- **Post-Processors** — Transform streaming output with pluggable processor pipeline.
- **Template Files** — Load prompts from external files for better organization.

### Memory & Storage

- **Session Memory** — Multi-session conversation management with full OpenAI message format support.
- **Tool Call Tracking** — Complete function calling chain management with validation.
- **Pin/Tag System** — Protect important messages from being trimmed or modified.
- **Undo/Redo** — Rollback conversation operations when needed.
- **Multiple Backends** — In-memory, JSON file, SQLite storage options.
- **TTL Support** — Automatic session cleanup with time-to-live.

### Skills ([agentskills.io](https://agentskills.io) compatible)

- **Progressive Disclosure** — 3-phase loading (metadata → instructions → resources) to optimize token budget.
- **Ecosystem Ready** — Use community skills published for Anthropic / OpenAI / Copilot style workflows.
- **Safe Resource Access** — Path traversal detection and file-size limits by default.
- **SkillAgent** — Works out-of-the-box with `SkillAgent` or can be plugged into `ReActAgent`.

### Sandbox

- **Secure Execution** — Run agent-generated code in isolated environments with resource limits and security policies.
- **Local / Docker Backends** — Fast local runs for development, stronger container isolation for production.
- **Remote Docker (TCP)** — Connect to remote Docker daemons via `docker_host="tcp://..."`. Auto image validation, local skills sync, and container-API file operations.
- **Agent-Friendly Paths** — `uploads/` and `outputs/` live inside the workspace (aligned with OpenAI Code Interpreter conventions). Agents use simple relative paths.
- **File & Package Management** — Full file operations (read/write/list/copy/move/delete) and pip package management inside the sandbox.

### Hooks (Extension & Governance)

- **Unified Events** — One hook system across tools, memory, prompter/LLM, sandbox, and agent lifecycle.
- **Stable Defaults** — Fail-open by default (hook failures won't break the main flow).
- **Operational Controls** — Ordering, timeout, error policy (fail-open / fail-close), and basic metrics/audit patterns.

### Deployment

- **One-Line API** — Publish any agent as OpenAI-compatible REST API with `publish_agent_api()`.
- **FastAPI Integration** — Built on FastAPI with automatic OpenAPI documentation.
- **SSE Streaming** — Server-Sent Events for real-time streaming responses.
- **Session Management** — Built-in session handling with configurable TTL.

---

## Quick Start

### 1. ReAct Agent with Tools

```python
from alphora.agent import ReActAgent
from alphora.models import OpenAILike
from alphora.tools import tool

@tool
def get_weather(city: str, unit: str = "celsius") -> str:
    """Get current weather for a city."""
    return f"Weather in {city}: 22°{unit[0].upper()}, Sunny"

@tool
async def search_docs(query: str, limit: int = 5) -> list:
    """Search internal documents."""
    return [{"title": "Result 1", "score": 0.95}]

agent = ReActAgent(
    llm=OpenAILike(model_name="gpt-4"),
    tools=[get_weather, search_docs],
    system_prompt="You are a helpful assistant.",
    max_iterations=10,
)

result = await agent.run("What's the weather in Tokyo?")
```

### 2. Sandbox (Secure Code Execution)

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

Remote Docker:

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

### 3. Skills (Community & Standard)

```python
from alphora.agent import SkillAgent
from alphora.models import OpenAILike

agent = SkillAgent(
    llm=OpenAILike(model_name="gpt-4"),
    skill_paths=["./alphora_community/skills"],
    system_prompt="You are a helpful assistant.",
)

result = await agent.run("Help me do a deep research on AI agents.")
```

### 4. Memory Management

```python
from alphora.memory import MemoryManager

memory = MemoryManager()

memory.add_user(session_id="user_123", content="Hello")
memory.add_assistant(session_id="user_123", content="Hi there!")

history = memory.build_history(session_id="user_123")
```

### 5. Load Balancing

```python
llm1 = OpenAILike(model_name="gpt-4", api_key="key1", base_url="https://api1.com/v1")
llm2 = OpenAILike(model_name="gpt-4", api_key="key2", base_url="https://api2.com/v1")

llm = llm1 + llm2  # Automatic round-robin load balancing

response = await llm.ainvoke("Hello")
```

### 6. Deploy as API

```python
from alphora.server.quick_api import publish_agent_api, APIPublisherConfig

config = APIPublisherConfig(
    path="/alphadata",
    api_title="My Agent API",
    memory_ttl=3600,
)

app = publish_agent_api(agent=agent, method="run", config=config)

# Run: uvicorn main:app --port 8000
```

```bash
curl -X POST http://localhost:8000/alphadata/chat/completions \
  -H "Content-Type: application/json" \
  -d '{"messages": [{"role": "user", "content": "Hello!"}], "stream": true}'
```

---

## Examples

| Example                                     | Description |
|---------------------------------------------|-------------|
| [ChatExcel](./examples/chatexcel)           | Data analysis agent with sandbox code execution |
| [RAG Agent](./examples/rag-agent)           | Retrieval-augmented generation with vector search |
| [Multi-Agent](./examples/multi-agent)       | Hierarchical agents with tool-as-agent pattern |
| [Streaming Chat](./examples/streaming-chat) | Real-time chat with thinking mode |


---

## Configuration

```bash
export LLM_API_KEY="your-api-key"
export LLM_BASE_URL="https://api.openai.com/v1"
export DEFAULT_LLM="gpt-4"

# Optional: Embedding
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

<table><tr><td align="center" width="170px"><a href="https://github.com/tian-cmcc"><img src="https://avatars.githubusercontent.com/tian-cmcc" width="80px;" style="border-radius: 50%;" alt="Tian Tian"/><br /><b>Tian Tian</b></a><br /><sub>Project Lead & Core Dev</sub><br /><a href="mailto:tiantianit@chinamobile.com" title="Email Tian Tian">📧</a></td><td align="center" width="170px"><a href="https://github.com/yilingliang"><img src="https://avatars.githubusercontent.com/yilingliang" width="80px;" style="border-radius: 50%;" alt="Yuhang Liang"/><br /><b>Yuhang Liang</b></a><br /><sub>Developer</sub><br /><a href="mailto:liangyuhang@chinamobile.com" title="Email Yuhang Liang">📧</a></td><td align="center" width="170px"><a href="https://github.com/jianhuishi"><img src="https://avatars.githubusercontent.com/jianhuishi" width="80px;" style="border-radius: 50%;" alt="Jianhui Shi"/><br /><b>Jianhui Shi</b></a><br /><sub>Developer</sub><br /><a href="mailto:shijianhui@chinamobile.com" title="Email Jianhui Shi">📧</a></td><td align="center" width="170px"><a href="https://github.com/liuyingdi2025"><img src="https://avatars.githubusercontent.com/liuyingdi2025" width="80px;" style="border-radius: 50%;" alt="Yingdi Liu"/><br /><b>Yingdi Liu</b></a><br /><sub>Developer</sub><br /><a href="mailto:liuyingdi@chinamobile.com" title="Email Yingdi Liu">📧</a></td><td align="center" width="170px"><a href="https://github.com/hqy479"><img src="https://avatars.githubusercontent.com/hqy479" width="80px;" style="border-radius: 50%;" alt="Qiuyang He"/><br /><b>Qiuyang He</b></a><br /><sub>Developer</sub><br />-</td></tr><tr><td align="center" width="170px"><a href="https://github.com/ljx139"><img src="https://avatars.githubusercontent.com/ljx139" width="80px;" style="border-radius: 50%;" alt="LiuJX"/><br /><b>LiuJX</b></a><br /><sub>Developer</sub><br />-</td><td align="center" width="170px"><a href="https://github.com/Cjdddd"><img src="https://avatars.githubusercontent.com/Cjdddd" width="80px;" style="border-radius: 50%;" alt="Cjdddd"/><br /><b>Cjdddd</b></a><br /><sub>Developer</sub><br /><a href="mailto:cuijindong@chinamobile.com" title="Email Cjdddd">📧</a></td><td align="center" width="170px"><a href="https://github.com/wwy99"><img src="https://avatars.githubusercontent.com/wwy99" width="80px;" style="border-radius: 50%;" alt="Weiyu Wang"/><br /><b>Weiyu Wang</b></a><br /><sub>Developer</sub><br /><a href="mailto:wangweiyu@chinamobile.com" title="Email Weiyu Wang">📧</a></td><td align="center" width="170px"></td><td align="center" width="170px"></td></tr></table>

## License

This project is licensed under the **Apache License 2.0**.  
See [LICENSE](./LICENSE) for details.

Contributions require acceptance of the [Contributor License Agreement (CLA)](CLA.md).
