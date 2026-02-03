<h1 align="center">
  <img src="asset/image/logo.png" width="40" style="vertical-align:middle">
  Alphora
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
  <a href="https://docs.alphora.dev">Docs</a> •
  <a href="#quick-start">Quick Start</a> •
  <a href="#examples">Examples</a> •
  <a href="https://github.com/alphora/alphora/discussions">Community</a>
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

###  Sandbox

- **Secure Execution** — Run agent-generated code in isolated environments.
- **File Isolation** — Sandboxed file system for safe file operations.
- **Resource Tracking** — Monitor and limit compute resources.

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
from alphora.server import publish_agent_api, APIPublisherConfig

config = APIPublisherConfig(
    path="/chat",
    api_title="My Agent API",
    memory_ttl=3600
)

app = publish_agent_api(agent=agent, method="run", config=config)

# Run: uvicorn main:app --port 8000
```

```bash
curl -X POST http://localhost:8000/chat/v1/chat/completions \
  -H "Content-Type: application/json" \
  -d '{"messages": [{"role": "user", "content": "Hello!"}], "stream": true}'
```

---

## Examples

| Example | Description |
|---------|-------------|
| [ChatExcel](./examples/chat-excel) | Data analysis agent with sandbox code execution |
| [RAG Agent](./examples/rag-agent) | Retrieval-augmented generation with vector search |
| [Multi-Agent](./examples/multi-agent) | Hierarchical agents with tool-as-agent pattern |
| [Streaming Chat](./examples/streaming-chat) | Real-time chat with thinking mode |

---

## Architecture

For detailed system design, component relationships, and implementation patterns, see the [Architecture Guide](./docs/ARCHITECTURE.md).

### Component Overview

| Component | Purpose |
|-----------|---------|
| [Agent](./docs/agent_readme.md) | Core agent lifecycle, derivation, ReAct loop |
| [Prompter](./docs/prompter_readme.md) | Jinja2 templates, LLM invocation, streaming |
| [Models](./docs/model_readme.md) | LLM interface, multimodal, load balancing |
| [Tools](./docs/tool_readme.md) | @tool decorator, registry, parallel execution |
| [Memory](./docs/memory_readme.md) | Session management, history, pin/tag system |
| [Storage](./docs/storage_readme.md) | Persistent backends (memory, JSON, SQLite) |
| [Sandbox](./docs/sandbox_readme.md) | Secure code execution environment |
| [Server](./docs/server_readme.md) | API publishing, SSE streaming |
| [Postprocess](./docs/postprocess_readme.md) | Stream transformation pipeline |

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

---

## Documentation

| Resource | Description |
|----------|-------------|
| [Getting Started](https://docs.alphora.dev/getting-started) | Installation and first agent |
| [Core Concepts](https://docs.alphora.dev/concepts) | Agents, prompts, tools, memory |
| [Architecture](./docs/ARCHITECTURE.md) | System design and patterns |
| [API Reference](https://docs.alphora.dev/api) | Complete API documentation |
| [Cookbook](https://docs.alphora.dev/cookbook) | Recipes and best practices |

---

## Contributing

We welcome contributions! See [CONTRIBUTING.md](./CONTRIBUTING.md) for guidelines.

```bash
git clone https://github.com/alphora/alphora.git
cd alphora && pip install -e ".[dev]"
pytest tests/
```

## Community

-  [GitHub Discussions](https://github.com/alphora/alphora/discussions) — Questions and ideas
-  [GitHub Issues](https://github.com/alphora/alphora/issues) — Bug reports and features
-  [Documentation](https://docs.alphora.dev) — Guides and reference

## License

CLA 
