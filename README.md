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

Alphora is a full-stack framework for building production AI agents. It provides everything you need: agent orchestration, prompt engineering, tool execution, memory management, streaming, and deployment—all with an async-first, OpenAI-compatible design.

```python
from alphora.agent import ReActAgent
from alphora.models import OpenAILike
from alphora.sandbox import Sandbox
from alphora.tools import tool

@tool
def search_database(query: str) -> str:
    """Search the product database."""
    return f"Found 3 results for: {query}"


sandbox = Sandbox.create_docker()

agent = ReActAgent(
    llm=OpenAILike(model_name="gpt-4"),
    tools=[search_database],
    system_prompt="You are a helpful assistant.",
    sandbox=sandbox
)

response = await agent.run("Find laptops under $1000")
```

## Installation

```bash
pip install alphora
```

---

## Features

Alphora is packed with features for building sophisticated AI agents:

###  Agent System

- **Agent Derivation** — Child agents inherit LLM, memory, and config from parents. Build hierarchies that share context.
- **ReAct Loop** — Built-in reasoning-action loop with automatic tool orchestration, retry logic, and iteration control.
- **Streaming First** — Native async streaming with OpenAI SSE format. Multiple content types: `char`, `think`, `result`, `sql`, `chart`.
- **Debug Tracing** — Built-in visual debugger for agent execution flow, LLM calls, and tool invocations.

###  Model Layer

- **OpenAI Compatible** — Works with any OpenAI-compatible API: GPT, Claude, Qwen, DeepSeek, local models.
- **Multimodal Support** — Unified `Message` class for text, images, audio, and video inputs.
- **Load Balancing** — Built-in round-robin/random load balancing across multiple LLM backends.
- **Thinking Mode** — Support for reasoning models (Qwen3, etc.) with separate thinking/content streams.
- **Embedding API** — Unified text embedding interface with batch processing.

###  Tool System

- **Zero-Config Tools** — `@tool` decorator auto-generates OpenAI function calling schema from type hints and docstrings.
- **Type Safety** — Pydantic V2 validation for all tool parameters. Automatic error feedback to LLM.
- **Async Native** — Async tools run natively; sync tools auto-execute in thread pool.
- **Parallel Execution** — Execute multiple tool calls concurrently for better performance.
- **Instance Methods** — Register class methods as tools with access to `self` context (DB connections, user state, etc.).

###  Prompt Engine

- **Jinja2 Templates** — Dynamic prompts with variable interpolation, conditionals, loops, and includes.
- **Long Text Continuation** — Auto-detect truncation and continue generation to bypass token limits.
- **Parallel Prompts** — Execute multiple prompts concurrently with `ParallelPrompt`.
- **Post-Processors** — Transform streaming output with pluggable processor pipeline.
- **Template Files** — Load prompts from external files for better organization.

###  Memory & Storage

- **Session Memory** — Multi-session conversation management with full OpenAI message format support.
- **Tool Call Tracking** — Complete function calling chain management with validation.
- **Pin/Tag System** — Protect important messages from being trimmed or modified.
- **Undo/Redo** — Rollback conversation operations when needed.
- **Multiple Backends** — In-memory, JSON file, SQLite storage options.
- **TTL Support** — Automatic session cleanup with time-to-live.

### Skills (agentskills.io compatible)

- **Progressive Disclosure** — 3-phase loading (metadata → instructions → resources) to optimize token budget.
- **Ecosystem Ready** — Use community skills published for Anthropic / OpenAI / Copilot style workflows.
- **Safe Resource Access** — Path traversal detection and file-size limits by default.
- **SkillAgent Ready** — Works out-of-the-box with `SkillAgent` or can be plugged into `ReActAgent`.

### Hooks (Extension & Governance)

- **Unified Events** — One hook system across tools, memory, prompter/LLM, sandbox, and agent lifecycle.
- **Stable Defaults** — Fail-open by default (hook failures won’t break the main flow).
- **Operational Controls** — Ordering, timeout, error policy (fail-open / fail-close), and basic metrics/audit patterns.

###  Sandbox

- **Secure Execution** — Run agent-generated code in isolated environments.
- **Local / Docker Backends** — Fast local runs or stronger container isolation in production.
- **File & Workspace Ops** — Read/write/list/copy/move files with optional persistent workspace mounting.
- **Package Management** — Install/uninstall/query pip packages inside the sandbox runtime.
- **Security & Limits** — Resource limits (CPU/mem/disk/time) and configurable security policies.

### Deployment

- **One-Line API** — Publish any agent as OpenAI-compatible REST API with `publish_agent_api()`.
- **FastAPI Integration** — Built on FastAPI with automatic OpenAPI documentation.
- **SSE Streaming** — Server-Sent Events for real-time streaming responses.
- **Session Management** — Built-in session handling with configurable TTL.

---

## Quick Start

### 1. Basic Agent

```python
from alphora.agent import BaseAgent
from alphora.models import OpenAILike

agent = BaseAgent(llm=OpenAILike(model_name="gpt-4"))

prompt = agent.create_prompt(
    system_prompt="You are a helpful assistant.",
    user_prompt="{{query}}"
)

response = await prompt.acall(query="What is Python?")
```

### 2. Tools with @tool Decorator

```python
from alphora.tools import tool, ToolRegistry, ToolExecutor

@tool
def get_weather(city: str, unit: str = "celsius") -> str:
    """Get current weather for a city."""
    return f"Weather in {city}: 22°{unit[0].upper()}, Sunny"

@tool
async def search_docs(query: str, limit: int = 5) -> list:
    """Search internal documents."""
    return [{"title": "Result 1", "score": 0.95}]

registry = ToolRegistry()
registry.register(get_weather)
registry.register(search_docs)

# Get OpenAI-compatible schema
tools_schema = registry.get_openai_tools_schema()
```

### 3. ReAct Agent (Auto Tool Loop)

```python
from alphora.agent import ReActAgent

agent = ReActAgent(
    llm=llm,
    tools=[get_weather, search_docs],
    system_prompt="You are a helpful assistant.",
    max_iterations=10
)

# Agent automatically handles tool calling loop
result = await agent.run("What's the weather in Tokyo?")
```

### 4. Agent Derivation (Shared Context)

```python
from alphora.agent import BaseAgent
from alphora.memory import MemoryManager

# Parent with shared resources
parent = BaseAgent(
    llm=llm,
    memory=MemoryManager(),
    config={"project": "demo"}
)

# Children inherit llm, memory, config
researcher = parent.derive(ResearchAgent)
analyst = parent.derive(AnalysisAgent)

# All agents share the same memory
parent.memory.add_user(session_id="s1", content="Hello")
# researcher and analyst can see this message
```

### 5. Multimodal Messages

```python
from alphora.models.message import Message

# Create multimodal message
msg = Message()
msg.add_text("What's in this image?")
msg.add_image(base64_data, format="png")

response = await llm.ainvoke(msg)
```

### 6. Load Balancing

```python
# Primary LLM
llm1 = OpenAILike(model_name="gpt-4", api_key="key1", base_url="https://api1.com/v1")

# Backup LLM
llm2 = OpenAILike(model_name="gpt-4", api_key="key2", base_url="https://api2.com/v1")

# Combine with automatic load balancing
llm = llm1 + llm2

response = await llm.ainvoke("Hello")  # Auto round-robin
```

### 7. Memory Management

```python
from alphora.memory import MemoryManager

memory = MemoryManager()

# Add conversation
memory.add_user(session_id="user_123", content="Hello")
memory.add_assistant(session_id="user_123", content="Hi there!")

# Add tool results
memory.add_tool_result(session_id="user_123", result=tool_output)

# Build history for LLM
history = memory.build_history(session_id="user_123")
```

### 8. Deploy as API

```python
from alphora.server.quick_api import publish_agent_api, APIPublisherConfig

config = APIPublisherConfig(
    path="/alphadata",
    api_title="My Agent API",
    memory_ttl=3600
)

app = publish_agent_api(agent=agent, method="run", config=config)

# Run: uvicorn main:app --port 8000
```

```bash
curl -X POST http://localhost:8000/alphadata/chat/completions \
  -H "Content-Type: application/json" \
  -d '{"messages": [{"role": "user", "content": "Hello!"}], "stream": true}'
```

### 9. Skills (Community & Standard)

```python
from alphora.agent import SkillAgent
from alphora.models import OpenAILike

# Bundled community skills live under ./alphora_community/skills
agent = SkillAgent(
    llm=OpenAILike(model_name="gpt-4"),
    skill_paths=["./alphora_community/skills"],
    system_prompt="You are a helpful assistant."
)

result = await agent.run("Help me do a deep research on a topic.")
```

### 10. Hooks (Observability / Policy)

```python
from alphora.tools import ToolRegistry, ToolExecutor

def log_after(ctx):
    # ctx.data may include tool_name, tool_args, elapsed_ms, etc.
    print("after tool:", ctx.data.get("tool_name"))

registry = ToolRegistry()
executor = ToolExecutor(registry, after_execute=log_after)
```

---

## Examples

| Example                                     | Description |
|---------------------------------------------|-------------|
| [ChatExcel](./examples/chatexcel)           | Data analysis agent with sandbox code execution |
| [RAG Agent](./examples/rag-agent)           | Retrieval-augmented generation with vector search |
| [Multi-Agent](./examples/multi-agent)       | Hierarchical agents with tool-as-agent pattern |
| [Streaming Chat](./examples/streaming-chat) | Real-time chat with thinking mode |

### Community Skills

This repo ships with a small set of community skills under `alphora_community/skills`, for example:

- `deep-research`: deep research workflow (search, dedupe, evidence aggregation, report output)
- `data-quality-audit`: CSV profiling, schema checks, anomaly detection, and Markdown report generation

---

## Configuration

```bash
# Environment variables
export LLM_API_KEY="your-api-key"
export LLM_BASE_URL="https://api.openai.com/v1"
export DEFAULT_LLM="gpt-4"

# Optional: Embedding
export EMBEDDING_API_KEY="your-key"
export EMBEDDING_BASE_URL="https://api.openai.com/v1"
```

```python
# Programmatic configuration
from alphora.models import OpenAILike

llm = OpenAILike(
    model_name="gpt-4",
    api_key="sk-xxx",
    base_url="https://api.openai.com/v1",
    temperature=0.7,
    max_tokens=4096,
    is_multimodal=True  # Enable vision
)
```



## Documentation

For detailed system design, component relationships, and implementation patterns, see the [Architecture Guide](./docs/ARCHITECTURE.md).

### Component Overview

| Component                                    | Description |
|----------------------------------------------|---------|
| [Agent](docs/components/cn/agent_readme.md)             | Core agent lifecycle, derivation, ReAct loop |
| [Prompter](docs/components/cn/prompter_readme.md)       | Jinja2 templates, LLM invocation, streaming |
| [Models](docs/components/cn/model_readme.md)            | LLM interface, multimodal, load balancing |
| [Tools](docs/components/cn/tool_readme.md)              | tool decorator, registry, parallel execution |
| [Memory](docs/components/cn/memory_readme.md)           | Session management, history, pin/tag system |
| [Storage](docs/components/cn/storage_readme.md)         | Persistent backends (memory, JSON, SQLite) |
| [Sandbox](docs/components/cn/sandbox_readme.md)         | Secure code execution environment |
| [Server](docs/components/cn/server_readme.md)           | API publishing, SSE streaming |
| [Postprocess](docs/components/cn/postprocess_readme.md) | Stream transformation pipeline |
| [Skills](docs/components/cn/skill_readme.md)            | agentskills.io compatible skills, SkillAgent integration |
| [Hooks](docs/components/cn/hooks_readme.md)             | Extension & governance via unified hook events |


---
## Contributors

Crafted by the AlphaData Team. 

<table><tr><td align="center" width="170px"><a href="https://github.com/tian-cmcc"><img src="https://avatars.githubusercontent.com/tian-cmcc" width="80px;" style="border-radius: 50%;" alt="Tian Tian"/><br /><b>Tian Tian</b></a><br /><sub>Project Lead & Core Dev</sub><br /><a href="mailto:tiantianit@chinamobile.com" title="Email Tian Tian">📧</a></td><td align="center" width="170px"><a href="https://github.com/yilingliang"><img src="https://avatars.githubusercontent.com/yilingliang" width="80px;" style="border-radius: 50%;" alt="Yuhang Liang"/><br /><b>Yuhang Liang</b></a><br /><sub>Developer</sub><br /><a href="mailto:liangyuhang@chinamobile.com" title="Email Yuhang Liang">📧</a></td><td align="center" width="170px"><a href="https://github.com/jianhuishi"><img src="https://avatars.githubusercontent.com/jianhuishi" width="80px;" style="border-radius: 50%;" alt="Jianhui Shi"/><br /><b>Jianhui Shi</b></a><br /><sub>Developer</sub><br /><a href="mailto:shijianhui@chinamobile.com" title="Email Jianhui Shi">📧</a></td><td align="center" width="170px"><a href="https://github.com/liuyingdi2025"><img src="https://avatars.githubusercontent.com/liuyingdi2025" width="80px;" style="border-radius: 50%;" alt="Yingdi Liu"/><br /><b>Yingdi Liu</b></a><br /><sub>Developer</sub><br /><a href="mailto:liuyingdi@chinamobile.com" title="Email Yingdi Liu">📧</a></td><td align="center" width="170px"><a href="https://github.com/hqy479"><img src="https://avatars.githubusercontent.com/hqy479" width="80px;" style="border-radius: 50%;" alt="Qiuyang He"/><br /><b>Qiuyang He</b></a><br /><sub>Developer</sub><br />-</td></tr><tr><td align="center" width="170px"><a href="https://github.com/ljx139"><img src="https://avatars.githubusercontent.com/ljx139" width="80px;" style="border-radius: 50%;" alt="LiuJX"/><br /><b>LiuJX</b></a><br /><sub>Developer</sub><br />-</td><td align="center" width="170px"><a href="https://github.com/Cjdddd"><img src="https://avatars.githubusercontent.com/Cjdddd" width="80px;" style="border-radius: 50%;" alt="Cjdddd"/><br /><b>Cjdddd</b></a><br /><sub>Developer</sub><br /><a href="mailto:cuijindong@chinamobile.com" title="Email Cjdddd">📧</a></td><td align="center" width="170px"><a href="https://github.com/wwy99"><img src="https://avatars.githubusercontent.com/wwy99" width="80px;" style="border-radius: 50%;" alt="Weiyu Wang"/><br /><b>Weiyu Wang</b></a><br /><sub>Developer</sub><br /><a href="mailto:wangweiyu@chinamobile.com" title="Email Weiyu Wang">📧</a></td><td align="center" width="170px"></td><td align="center" width="170px"></td></tr></table>


## License

This project is licensed under the **Apache License 2.0**.  
See [LICENSE](./LICENSE) for details.

Contributions require acceptance of the [Contributor License Agreement (CLA)](CLA.md).

