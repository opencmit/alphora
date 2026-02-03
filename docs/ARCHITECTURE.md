# Alphora Architecture

This document describes the internal architecture of Alphora, including system design, component relationships, and implementation patterns.

## Table of Contents

- [Design Philosophy](#design-philosophy)
- [System Architecture](#system-architecture)
- [Component Overview](#component-overview)
- [Core Abstractions](#core-abstractions)
- [Data Flow](#data-flow)
- [Multi-Agent Patterns](#multi-agent-patterns)
- [Extension Points](#extension-points)

---

## Design Philosophy

Alphora is built on four core principles:

### Composability

Every component is designed to work independently or together. Agents can derive from other agents, prompts can be nested, and tools can be composed. This enables building complex systems from simple, well-tested pieces.

### Async-Native

Built from the ground up for `async/await` patterns. All I/O operations are non-blocking, enabling high-concurrency agent applications. Synchronous wrappers are provided for convenience but async is the primary interface.

### Protocol-Driven

Follows OpenAI's API specification as the standard protocol. This ensures compatibility with existing tools, easy migration from other frameworks, and straightforward integration with any OpenAI-compatible backend.

### Explicit over Magic

Configuration and behavior are explicit and traceable. No hidden global state or implicit dependencies. You can always understand what an agent will do by reading its configuration.

---

## System Architecture

Alphora adopts a **layered architecture** with clear separation of concerns:

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                              Application Layer                               │
│                                                                             │
│    ┌─────────────┐      ┌─────────────┐      ┌─────────────────────────┐   │
│    │   Server    │      │    Agent    │      │       Your App          │   │
│    │ API Publish │      │  Framework  │      │    Business Logic       │   │
│    └──────┬──────┘      └──────┬──────┘      └───────────┬─────────────┘   │
│           │                    │                         │                  │
├───────────┴────────────────────┴─────────────────────────┴──────────────────┤
│                            Orchestration Layer                               │
│                                                                             │
│    ┌─────────────┐      ┌─────────────┐      ┌─────────────────────────┐   │
│    │  Prompter   │      │   Memory    │      │      Postprocess        │   │
│    │Prompt Engine│      │Session State│      │   Output Transform      │   │
│    └──────┬──────┘      └──────┬──────┘      └───────────┬─────────────┘   │
│           │                    │                         │                  │
├───────────┴────────────────────┴─────────────────────────┴──────────────────┤
│                             Capability Layer                                 │
│                                                                             │
│    ┌─────────────┐      ┌─────────────┐      ┌─────────────────────────┐   │
│    │   Models    │      │    Tools    │      │        Sandbox          │   │
│    │LLM Interface│      │ Tool System │      │    Code Execution       │   │
│    └──────┬──────┘      └──────┬──────┘      └───────────┬─────────────┘   │
│           │                    │                         │                  │
├───────────┴────────────────────┴─────────────────────────┴──────────────────┤
│                           Infrastructure Layer                               │
│                                                                             │
│    ┌─────────────┐      ┌─────────────┐      ┌─────────────────────────┐   │
│    │   Storage   │      │ Serializers │      │       Debugger          │   │
│    │ Persistence │      │ Data Format │      │       Tracing           │   │
│    └─────────────┘      └─────────────┘      └─────────────────────────┘   │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
```

### Layer Responsibilities

| Layer | Components | Responsibility |
|-------|------------|----------------|
| **Application** | Server, Agent, Your App | API endpoints, agent orchestration, business logic |
| **Orchestration** | Prompter, Memory, Postprocess | Prompt management, state tracking, output transformation |
| **Capability** | Models, Tools, Sandbox | LLM communication, tool execution, safe code running |
| **Infrastructure** | Storage, Serializers, Debugger | Data persistence, format conversion, debugging |

---

## Component Overview

| Component | Purpose | Key Classes |
|-----------|---------|-------------|
| **Agent** | Core agent lifecycle and orchestration | `BaseAgent`, `ReActAgent`, `Stream` |
| **Prompter** | Prompt engineering and LLM invocation | `BasePrompt`, `ParallelPrompt` |
| **Models** | Unified LLM/Embedding interface | `OpenAILike`, `Message`, `ToolCall` |
| **Tools** | Tool definition and execution | `@tool`, `ToolRegistry`, `ToolExecutor` |
| **Memory** | Conversation and state management | `MemoryManager`, `HistoryPayload` |
| **Storage** | Persistent data storage | Key-value store interface |
| **Sandbox** | Secure code execution | `Sandbox`, file isolation |
| **Server** | API deployment | `publish_agent_api`, FastAPI integration |
| **Postprocess** | Stream transformation | `BasePostProcessor` |

---

## Core Abstractions

### Agent Derivation Model

Agent derivation enables resource sharing across agent hierarchies. When you derive an agent, the child automatically inherits certain resources from the parent:

```python
parent = BaseAgent(
    llm=llm,
    memory=memory_manager,
    config={"project": "demo", "debug": True},
    callback=stream_handler
)

# Child inherits: llm, memory, config, callback, verbose
child = parent.derive(SpecializedAgent, custom_param="value")
```

**Inheritance behavior:**

| Resource | Behavior | Rationale |
|----------|----------|-----------|
| `llm` | Shared reference | Same model instance for consistency |
| `memory` | Shared reference | Enables cross-agent context sharing |
| `config` | Deep copied | Child can override without affecting parent |
| `callback` | Shared reference | Unified streaming output |
| `verbose` | Copied value | Independent logging control |

This pattern enables:
- **Hierarchical agents**: Controller → specialized workers
- **Shared context**: All agents see the same conversation history
- **Resource efficiency**: Single LLM client shared across agents

### Message Flow Pipeline

```
User Input
    │
    ▼
┌─────────────────────────────────────────────────────────────┐
│  Prompter                                                    │
│  ├─ Template rendering (Jinja2)                             │
│  ├─ History injection                                       │
│  └─ build_messages() → List[Message]                        │
└─────────────────────────────────────────────────────────────┘
    │
    ▼
┌─────────────────────────────────────────────────────────────┐
│  Models                                                      │
│  ├─ LLM API call                                            │
│  ├─ Load balancing (multiple backends)                      │
│  └─ Retry & failover                                        │
└─────────────────────────────────────────────────────────────┘
    │
    ▼
┌─────────────────────────────────────────────────────────────┐
│  Postprocess Pipeline                                        │
│  ├─ Stream transformation                                   │
│  ├─ Content filtering                                       │
│  └─ Format conversion                                       │
└─────────────────────────────────────────────────────────────┘
    │
    ▼
┌─────────────────────────────────────────────────────────────┐
│  Stream Handler                                              │
│  ├─ SSE formatting                                          │
│  └─ Client delivery                                         │
└─────────────────────────────────────────────────────────────┘
    │
    ▼
Client Response
```

### Tool Execution Model

Tools follow a **registry-executor** pattern:

```
┌──────────────────┐     ┌──────────────────┐     ┌──────────────────┐
│   1. Define      │     │   2. Register    │     │   3. Execute     │
│                  │     │                  │     │                  │
│  @tool decorator │────▶│  ToolRegistry    │────▶│  ToolExecutor    │
│  Type hints      │     │  Schema gen      │     │  Function call   │
│  Docstring       │     │                  │     │                  │
└──────────────────┘     └────────┬─────────┘     └──────────────────┘
                                  │
                                  ▼
                         ┌──────────────────┐
                         │  OpenAI Schema   │
                         │  (tools param)   │
                         └──────────────────┘
```

**Schema auto-generation:**

| Source | Maps To |
|--------|---------|
| Function name | `function.name` |
| Docstring | `function.description` |
| Type hints | `function.parameters` |
| Default values | `required` field calculation |

### Memory Architecture

Memory supports multi-session, multi-agent scenarios:

```
┌─────────────────────────────────────────────────────────────┐
│  MemoryManager                                               │
│                                                             │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐         │
│  │ Session A   │  │ Session B   │  │ Session C   │         │
│  │             │  │             │  │             │         │
│  │ user: ...   │  │ user: ...   │  │ user: ...   │         │
│  │ assistant:  │  │ assistant:  │  │ tool_call:  │         │
│  │ tool_call:  │  │ ...         │  │ tool_result │         │
│  └──────┬──────┘  └──────┬──────┘  └──────┬──────┘         │
│         │                │                │                 │
│         └────────────────┼────────────────┘                 │
│                          ▼                                  │
│                    ┌───────────┐                            │
│                    │  Storage  │                            │
│                    │ (optional)│                            │
│                    └───────────┘                            │
└─────────────────────────────────────────────────────────────┘
```

**Features:**

- **Session isolation**: Each session maintains independent conversation history
- **Role normalization**: Automatically normalizes messages to OpenAI format
- **Tool call tracking**: Preserves tool calls and results in conversation flow
- **Cross-agent sharing**: Derived agents share memory for context continuity
- **TTL support**: Automatic cleanup of stale sessions

### Streaming Content Types

The streaming system supports multiple content types for rich output:

| Type | Purpose | Client Behavior |
|------|---------|-----------------|
| `char` | Regular text | Display as-is |
| `think` | Reasoning content | May style differently in UI |
| `result` | Final results | Highlight or format specially |
| `sql` | SQL queries | Syntax highlighting |
| `chart` | Visualization data | Render as chart |
| `[STREAM_IGNORE]` | Internal only | Don't send to client |
| `[RESPONSE_IGNORE]` | Stream only | Don't include in final response |

---

## Data Flow

### Request Lifecycle

```
┌─────────┐     ┌─────────┐     ┌─────────┐     ┌─────────┐
│  User   │────▶│ Server  │────▶│  Agent  │────▶│Prompter │
└─────────┘     └─────────┘     └────┬────┘     └────┬────┘
                                     │               │
                              ┌──────┴──────┐        │
                              ▼             ▼        ▼
                         ┌─────────┐  ┌─────────┐ ┌─────────┐
                         │ Memory  │  │  Tools  │ │ Models  │
                         └────┬────┘  └────┬────┘ └────┬────┘
                              │            │          │
                              ▼            ▼          ▼
                         ┌─────────┐  ┌─────────┐ ┌─────────┐
                         │ Storage │  │ Sandbox │ │ LLM API │
                         └─────────┘  └─────────┘ └────┬────┘
                                                       │
                                                       ▼
                                                ┌─────────────┐
                                                │ Postprocess │
                                                └──────┬──────┘
                                                       │
                                                       ▼
                                                ┌─────────────┐
                                                │   Stream    │
                                                │  Response   │
                                                └─────────────┘
```

### ReAct Loop

The ReAct (Reasoning + Acting) loop is the core execution pattern:

```
                    ┌─────────────────────┐
                    │    User Query       │
                    └──────────┬──────────┘
                               │
                               ▼
              ┌────────────────────────────────┐
              │         ReAct Loop             │
              │                                │
              │  ┌──────────────────────────┐  │
              │  │  1. Build context        │  │
              │  │     (history + tools)    │  │
              │  └────────────┬─────────────┘  │
              │               │                │
              │               ▼                │
              │  ┌──────────────────────────┐  │
              │  │  2. LLM inference        │  │
              │  │     (reasoning)          │  │
              │  └────────────┬─────────────┘  │
              │               │                │
              │               ▼                │
              │  ┌──────────────────────────┐  │
              │  │  3. Check response       │  │
              │  └────────────┬─────────────┘  │
              │               │                │
              │       ┌───────┴───────┐        │
              │       ▼               ▼        │
              │  ┌─────────┐    ┌──────────┐   │
              │  │ Has     │    │   Done   │───┼──▶ Return
              │  │ tools?  │    │          │   │
              │  └────┬────┘    └──────────┘   │
              │       │                        │
              │       ▼                        │
              │  ┌──────────────────────────┐  │
              │  │  4. Execute tools        │  │
              │  │     (acting)             │  │
              │  └────────────┬─────────────┘  │
              │               │                │
              │               ▼                │
              │  ┌──────────────────────────┐  │
              │  │  5. Add to memory        │  │
              │  └────────────┬─────────────┘  │
              │               │                │
              │               └────────────────┼──▶ Loop back to 1
              │                                │
              └────────────────────────────────┘
```

---

## Multi-Agent Patterns

### Pattern 1: Hierarchical Agents

A controller agent orchestrates specialized sub-agents:

```
                    ┌─────────────────────┐
                    │   Controller Agent  │
                    │   (orchestration)   │
                    └──────────┬──────────┘
                               │
              ┌────────────────┼────────────────┐
              │                │                │
              ▼                ▼                ▼
       ┌────────────┐   ┌────────────┐   ┌────────────┐
       │  Research  │   │  Analysis  │   │   Writer   │
       │   Agent    │   │   Agent    │   │   Agent    │
       └─────┬──────┘   └─────┬──────┘   └─────┬──────┘
             │                │                │
             ▼                ▼                ▼
        research()       analyze()         write()
```

```python
controller = BaseAgent(llm=llm, memory=memory)

researcher = controller.derive(ResearchAgent)
analyst = controller.derive(AnalysisAgent)
writer = controller.derive(WritingAgent)

async def process(task):
    research = await researcher.research(task)
    analysis = await analyst.analyze(research)
    return await writer.write(analysis)
```

### Pattern 2: Tool-as-Agent

Wrap agent methods as tools for another agent:

```
                    ┌─────────────────────┐
                    │   ReAct Orchestrator│
                    │                     │
                    │   tools=[          │
                    │     researcher.search,
                    │     analyst.compute │
                    │   ]                 │
                    └──────────┬──────────┘
                               │
                               │ function calling
                               ▼
              ┌────────────────────────────────┐
              │         Tool Registry          │
              │                                │
              │  ┌──────────┐  ┌──────────┐   │
              │  │ search() │  │compute() │   │
              │  └──────────┘  └──────────┘   │
              └────────────────────────────────┘
```

```python
registry = ToolRegistry()
registry.register(researcher.search)
registry.register(analyst.compute)

orchestrator = ReActAgent(
    llm=llm,
    tools=registry.get_tools()
)
```

### Pattern 3: Fan-out / Fan-in Pipeline

Parallel processing with result aggregation:

```
                         ┌─────────────┐
                         │   Document  │
                         └──────┬──────┘
                                │
              ┌─────────────────┼─────────────────┐
              │                 │                 │
              ▼                 ▼                 ▼
       ┌────────────┐   ┌────────────┐   ┌────────────┐
       │ Sentiment  │   │  Keywords  │   │  Summary   │
       │  Prompt    │   │  Prompt    │   │  Prompt    │
       └─────┬──────┘   └─────┬──────┘   └─────┬──────┘
             │                │                │
             └─────────────────┼─────────────────┘
                              │
                              ▼
                       ┌────────────┐
                       │ Synthesis  │
                       │  Prompt    │
                       └─────┬──────┘
                             │
                             ▼
                       ┌────────────┐
                       │   Report   │
                       └────────────┘
```

```python
from alphora.prompter import ParallelPrompt

parallel = ParallelPrompt([
    sentiment_prompt,
    keyword_prompt,
    summary_prompt
])

results = await parallel.acall(text=document)
final = await synthesis_prompt.acall(**results)
```

---

## Extension Points

Alphora is designed for extensibility at every layer:

### Custom Agent

```python
class MyAgent(BaseAgent):
    def __init__(self, custom_param: str, **kwargs):
        super().__init__(**kwargs)
        self.custom_param = custom_param
    
    async def run(self, query: str) -> str:
        # Custom logic
        prompt = self.create_prompt(...)
        return await prompt.acall(query=query)
```

### Custom LLM Provider

```python
class MyLLM(OpenAILike):
    def _get_extra_body(self, enable_thinking=False):
        return {"custom_param": "value"}
    
    def _parse_response(self, response):
        # Custom response parsing
        return super()._parse_response(response)
```

### Custom Tool

```python
from alphora.tools import tool

@tool
def my_tool(param: str, optional: int = 10) -> dict:
    """Tool description for LLM."""
    return {"result": param}

# Or implement the Tool protocol directly
class MyTool:
    name = "my_tool"
    description = "..."
    
    def get_schema(self) -> dict:
        return {...}
    
    async def execute(self, **kwargs) -> Any:
        return ...
```

### Custom Postprocessor

```python
from alphora.postprocess import BasePostProcessor

class MyPostProcessor(BasePostProcessor):
    async def process(self, chunk: str, content_type: str) -> str:
        # Transform the chunk
        return transformed_chunk
```

### Custom Storage Backend

```python
class MyStorage:
    async def get(self, key: str) -> Optional[str]:
        ...
    
    async def set(self, key: str, value: str, ttl: Optional[int] = None):
        ...
    
    async def delete(self, key: str):
        ...
```

---

## Performance Considerations

### Async Everywhere

All I/O operations are async. Use `await` for:
- LLM calls
- Tool execution
- Memory operations
- Storage access

### Connection Pooling

The `OpenAILike` client maintains connection pools. Reuse instances across agents rather than creating new ones.

### Memory Management

- Use session TTL to prevent memory leaks
- Clear completed sessions explicitly when possible
- Consider external storage for long-running applications

### Streaming

Prefer streaming for long responses:
- Reduces time-to-first-token
- Enables real-time UI updates
- Lower memory footprint for large responses


