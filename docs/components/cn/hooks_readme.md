# Alphora Hooks

**统一扩展与治理组件**

Hooks 是 Alphora 的统一扩展机制，用于在不侵入核心流程的前提下，
提供日志、审计、指标、安全策略、故障注入等能力。它面向开发者保持“函数即 Hook”的简洁体验，
内部统一由 HookManager 管理，保证可治理性与稳定性。

## 特性

-  **极简上手** - 直接传函数，不需要继承
-  **统一治理** - 排序、超时、错误策略、统计
-  **可扩展** - 事件体系统一，插件化能力
-  **稳定默认** - fail-open，Hook 失败不影响主流程

## 安装

```bash
pip install alphora
```

## 快速开始

### 组件级直接传入（推荐）

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

### 使用统一事件（高级）

```python
from alphora.hooks import HookManager, HookEvent

def log_after(ctx):
    print("after tool:", ctx.data.get("tool_name"))

manager = HookManager()
manager.register(HookEvent.TOOLS_AFTER_EXECUTE, log_after)
```

## 目录

- [事件列表（核心）](#事件列表核心)
- [Hook 上下文 (HookContext)](#hook-上下文-hookcontext)
- [工业级能力](#工业级能力)
- [内置 Hooks](#内置-hooks)
- [插件化](#插件化)

## 事件列表（核心）

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

## Hook 上下文 (HookContext)

Hook 的回调默认只接收一个参数 `ctx`，包含：

```python
ctx.event       # 事件名
ctx.component   # 组件名
ctx.data        # 关键上下文字段
ctx.timestamp   # UTC 时间
ctx.trace_id    # 可选追踪ID
```

你可以通过 `ctx.data` 读取或修改上下文字段，
例如修改 `tool_args` 或替换 `history`。

## 工业级能力

HookManager 支持：
- 优先级 (priority)
- 超时 (timeout)
- 错误策略 (fail_open / fail_close)
- 事件级策略覆盖
- 统计指标

示例：

```python
from alphora.hooks import HookManager, HookErrorPolicy, HookEvent

manager = HookManager(
    default_timeout=1.0,
    default_error_policy=HookErrorPolicy.FAIL_OPEN,
)
manager.set_event_policy(HookEvent.TOOLS_ON_ERROR, HookErrorPolicy.FAIL_CLOSE)
```

## 内置 Hooks

位于 `alphora/hooks/builtins`：

- `log_event` / `log_tool_execution`
- `MetricsStore` / `make_event_counter`
- `jsonl_audit_writer`

## 插件化

```python
from alphora.hooks import HookPlugin, load_plugins

plugin = HookPlugin(
    name="my_plugin",
    handlers=[my_hook_func],
)

load_plugins(manager, [plugin])
```
