# ChangeLog

## [1.2.9] - 2026-04-23
### Fixed
- 新增公开 processor ensure_tool_call_integrity，修复了Agent中可能出现的找不到父 assistant 的孤儿 tool 情况；(alphora/memory/processor.py)

### Update
- 新增 Hook - MessageInspector 的对话导出功能


## [1.3.0] - 2026-05-31
### Update
- 重写 OpenAILike 类，优化了可拓展性和鲁棒性
- 新增DeepSeek-V4适配
- 新增Qwen适配


## [1.3.1] - 2026-04-28
### Fixed
- **修复并发请求下的串沙箱 / 串状态严重 bug**：`quick_api.publish_agent_api`
  之前用 `copy.copy(agent)` + 手工 rebind 三个字段做"每请求一份新 agent"，
  但浅拷贝并未隔离 `self.config` 这个可变 dict。当不同 `session_id` 的请求
  在短时间内并发到达时（典型场景：复杂任务沙箱长存活），后到达请求的
  `update_config("sandbox", ...)` 会覆盖单例共享 dict，导致先到的请求在
  派生子智能体中通过 `get_config("sandbox")` 拿到别人的沙箱，进而出现
  "agent A 在 agent B 的沙箱里执行操作"的串号。
  （影响范围：所有使用 `publish_agent_api` 并通过 `update_config` 写入
  请求级状态的服务，例如 svc-alphadata 的 hyper / hyper_v2 / swarm 模式）

### Update
- **`BaseAgent` 引入请求作用域机制**：`config / memory / callback / stream / llm`
  五个属性现在通过 `RequestScoped` 描述符 + `contextvars.ContextVar`
  在每个请求 asyncio Task 中自动隔离。`asyncio.create_task` 的
  `copy_context()` 语义保证写入只对本任务可见，对其它并发任务和单例本身
  完全透明。
- 新增 `alphora.agent._request_scope` 模块（`RequestScoped`、
  `enter_request_scope`、`current_overrides`），框架内部使用。
- `quick_api.api_endpoints` 不再调用 `copy.copy(agent)`，改为复用单例
  agent + 在 `_guarded_run` 内 `enter_request_scope()`，更轻量也更正确。
- 新增 `MemoryManager`的 clone 方法

### Compatibility
- 应用层（`BaseAgent` 子类）**无需任何改动**：`self.update_config(...)` /
  `self.memory = ...` / `self.derive(SubAgent)` 等用法语义保持完全一致。
- 唯一可观察的内部变化：`agent.__dict__` 里这五个属性的存储键由
  `'config'` / `'memory'` / ... 改名为 `'_singleton_config'` /
  `'_singleton_memory'` / ...。如果有第三方代码绕过公共 API 直接读
  `agent.__dict__["config"]`，需要改为 `agent.config`。

## [1.3.2] - 2026-04-24
### Update
- 新增异常循环流输出检测，检测到循环异常可触发 stop 并流式输出异常消息；
- 新增流式SSE输出中携带meta元数据，与content, content_type同级；
- 新增 astream_status, astream_tool 等功能；
- 优化工具调用参数流式后处理器（ToolCallArgStreamPP）：保持向后兼容的同时，新增多个args解析能力；
- 将文件服务设置为了全部隐藏文件、路径均对外不可见；
