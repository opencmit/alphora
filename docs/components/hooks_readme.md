# Alphora Hooks

**Unified extension and governance component**

Hooks provide a unified extension mechanism in Alphora. They enable logging, auditing,
metrics, guardrails, and other cross-cutting concerns without modifying core logic.
Developers can attach plain functions as hooks, while the framework manages ordering,
timeouts, and error policies.

## Features

-  **Easy onboarding** - functions as hooks, no inheritance required
-  **Unified governance** - priority, timeout, error policy, metrics
-  **Extensible** - consistent event system, plugin support
-  **Stable by default** - fail-open behavior

## Installation

```bash
pip install alphora
```

## Quick Start

### Component-level hooks (recommended)

```python
from alphora.tools import ToolExecutor, ToolRegistry

def log_after(ctx):
    print("after tool:", ctx.data.get("tool_name"))

registry = ToolRegistry()
executor = ToolExecutor(
    registry,
    after_execute=log_after,
)
```

### Event-based hooks (advanced)

```python
from alphora.hooks import HookManager, HookEvent

def log_after(ctx):
    print("after tool:", ctx.data.get("tool_name"))

manager = HookManager()
manager.register(HookEvent.TOOLS_AFTER_EXECUTE, log_after)
```

## Contents

- [Event List](#event-list)
- [Hook Context](#hook-context)
- [Production Features](#production-features)
- [Built-in Hooks](#built-in-hooks)
- [Plugins](#plugins)

## Event List

### Tools
- `tools.before_execute`
- `tools.after_execute`
- `tools.on_error`
- `tools.before_register`
- `tools.after_register`

### Memory
- `memory.before_add`
- `memory.after_add`
- `memory.before_build_history`
- `memory.after_build_history`

### Prompter / LLM
- `prompter.before_build_messages`
- `prompter.after_build_messages`
- `llm.before_call`
- `llm.after_call`
- `llm.on_stream_chunk`

### Sandbox
- `sandbox.before_start`
- `sandbox.after_start`
- `sandbox.before_stop`
- `sandbox.after_stop`
- `sandbox.before_execute`
- `sandbox.after_execute`
- `sandbox.before_write_file`
- `sandbox.after_write_file`

### Agent
- `agent.before_run`
- `agent.after_run`
- `agent.before_iteration`
- `agent.after_iteration`

## Hook Context

Hooks receive a single argument `ctx`:

```python
ctx.event       # event name
ctx.component   # component name
ctx.data        # key context fields
ctx.timestamp   # UTC time
ctx.trace_id    # optional trace id
```

You can read or update `ctx.data` to override parameters
or return results.

## Production Features

HookManager supports:
- priority
- timeouts
- error policy (fail_open / fail_close)
- event-level override
- stats

Example:

```python
from alphora.hooks import HookManager, HookErrorPolicy, HookEvent

manager = HookManager(
    default_timeout=1.0,
    default_error_policy=HookErrorPolicy.FAIL_OPEN,
)
manager.set_event_policy(HookEvent.TOOLS_ON_ERROR, HookErrorPolicy.FAIL_CLOSE)
```

## Built-in Hooks

Located in `alphora/hooks/builtins`:

- `log_event` / `log_tool_execution`
- `MetricsStore` / `make_event_counter`
- `jsonl_audit_writer`

## Plugins

```python
from alphora.hooks import HookPlugin, load_plugins

plugin = HookPlugin(
    name="my_plugin",
    handlers=[my_hook_func],
)

load_plugins(manager, [plugin])
```
