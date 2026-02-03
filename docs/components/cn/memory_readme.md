# Alphora Memory

**智能体对话历史管理组件**

Memory 是一个为 LLM 智能体设计的对话历史管理组件，提供灵活的消息存储、处理和构建能力。它完全兼容 OpenAI Chat Completion API 格式，支持复杂的工具调用链路，并提供丰富的上下文操作接口。

## 特性

-  **标准消息格式** - 完全兼容 OpenAI API (user/assistant/tool/system)
-  **工具调用支持** - 完整的 Function Calling 链路管理与验证
-  **处理器机制** - 灵活的消息过滤、变换、组合
-  **标记系统** - Pin/Tag 机制保护重要信息
-  **多存储后端** - 内存、JSON、SQLite
- ️ **撤销/重做** - 操作可回滚
-  **多会话管理** - 独立管理多个对话

## 安装

```bash
pip install alphora
```

## 快速开始

```python
from alphora.memory import MemoryManager

# 创建管理器
memory = MemoryManager()

# 添加对话
memory.add_user("你好")
memory.add_assistant("你好！有什么可以帮你的？")

# 获取历史用于 LLM 调用
history = memory.build_history()
```

## 目录

- [基础用法](#基础用法)
- [处理器机制](#处理器机制)
- [标记系统](#标记系统)
- [上下文操作](#上下文操作)
- [工具调用](#工具调用)
- [历史管理](#历史管理)
- [多会话管理](#多会话管理)
- [存储配置](#存储配置)
- [API 参考](#api-参考)

---

## 基础用法

### 添加消息

```python
from alphora.memory import MemoryManager, Message

memory = MemoryManager()

# 添加用户消息
memory.add_user("帮我查一下北京的天气")

# 添加助手回复
memory.add_assistant("北京今天晴，气温 25°C")

# 添加系统消息
memory.add_system("你是一个天气助手")

# 添加原始消息
memory.add_message({"role": "user", "content": "谢谢"})
```

### 构建历史

```python
# 获取 HistoryPayload（推荐，用于传入 Prompt）
history = memory.build_history()

# 限制轮数
history = memory.build_history(max_rounds=5)

# 限制消息数
history = memory.build_history(max_messages=20)

# 传入 LLM
response = await prompt.acall(history=history)
```

### 获取消息

```python
# 获取所有消息
messages = memory.get_messages()

# 获取最后 5 条
messages = memory.get_messages(limit=5)

# 按角色过滤
messages = memory.get_messages(role="user")

# 自定义过滤
messages = memory.get_messages(filter=lambda m: len(m.content or "") > 100)

# 获取最后一条消息
last_msg = memory.get_last_message()
```

---

## 处理器机制

处理器允许你在构建历史时对消息进行临时处理，**不会修改原始数据**。

### 自定义处理器

```python
# 使用 lambda
history = memory.build_history(
    processor=lambda msgs: msgs[-20:]  # 保留最后 20 条
)

# 使用函数
def my_processor(messages):
    return [m for m in messages if m.role != "tool"][-10:]

history = memory.build_history(processor=my_processor)
```

### 内置处理器

```python
from alphora.memory.processors import (
    keep_last,
    keep_rounds,
    keep_roles,
    exclude_roles,
    keep_pinned,
    keep_tagged,
    truncate_content,
    remove_tool_details,
    token_budget,
    chain,
)

# 保留最后 N 条
history = memory.build_history(processor=keep_last(20))

# 保留最后 N 轮对话
history = memory.build_history(processor=keep_rounds(5))

# 只保留指定角色
history = memory.build_history(processor=keep_roles("user", "assistant"))

# 排除指定角色
history = memory.build_history(processor=exclude_roles("tool", "system"))

# 截断过长内容
history = memory.build_history(processor=truncate_content(max_length=2000))

# 移除工具调用细节
history = memory.build_history(processor=remove_tool_details())
```

### 组合处理器

```python
from alphora.memory.processors import chain, exclude_roles, keep_last, truncate_content

# 依次执行多个处理器
history = memory.build_history(
    processor=chain(
        exclude_roles("system"),
        keep_last(20),
        truncate_content(2000)
    )
)

# 或传入列表
history = memory.build_history(
    processor=[exclude_roles("system"), keep_last(20)]
)
```

### 便捷参数

```python
# exclude_roles 参数
history = memory.build_history(exclude_roles=["tool", "system"])

# 保留标记的消息
history = memory.build_history(
    keep_pinned=True,
    keep_tagged=["important"],
    max_messages=20
)
```

### Token 预算控制

```python
import tiktoken
from alphora.memory.processors import token_budget

enc = tiktoken.encoding_for_model("gpt-4")

history = memory.build_history(
    processor=token_budget(
        max_tokens=8000,
        tokenizer=lambda s: len(enc.encode(s)),
        reserve_for_response=1000
    )
)
```

---

## 标记系统

标记系统允许你标记重要消息，在压缩或过滤时保留它们。

### Pin（固定）

```python
# 按条件固定
memory.pin(lambda m: "重要" in (m.content or ""))

# 按消息 ID 固定
memory.pin("msg_id_xxx")

# 批量固定
memory.pin(["msg_id_1", "msg_id_2"])

# 取消固定
memory.unpin("msg_id_xxx")

# 获取固定的消息
pinned = memory.get_pinned()
```

### Tag（标签）

```python
# 添加标签
memory.tag("user_preference", lambda m: "喜欢" in (m.content or ""))
memory.tag("important", "msg_id_xxx")

# 移除标签
memory.untag("user_preference", "msg_id_xxx")

# 获取带标签的消息
tagged = memory.get_tagged("important")
```

### 在构建时使用

```python
# 保留固定的消息 + 最后 20 条
history = memory.build_history(
    keep_pinned=True,
    max_messages=20
)

# 保留带标签的消息
history = memory.build_history(
    keep_tagged=["important", "user_preference"],
    max_messages=20
)

# 使用处理器
from alphora.memory.processors import keep_important_and_last

history = memory.build_history(
    processor=keep_important_and_last(
        n=20,
        include_pinned=True,
        include_tags=["important"]
    )
)
```

---

## 上下文操作

### apply - 变换消息

对满足条件的消息应用变换，**永久修改存储数据**。

```python
# 截断超长消息
memory.apply(
    fn=lambda m: m.with_content(m.content[:1000] + "..."),
    predicate=lambda m: len(m.content or "") > 1000
)

# 添加元数据
memory.apply(
    fn=lambda m: m.with_metadata(processed=True),
    predicate=lambda m: m.role == "assistant"
)

# 所有消息
memory.apply(fn=lambda m: m.with_tags("archived"))
```

### remove - 删除消息

删除满足条件的消息，**永久修改存储数据**。

```python
# 删除工具消息
memory.remove(lambda m: m.role == "tool")

# 删除包含错误的消息
memory.remove(lambda m: "error" in (m.content or "").lower())

# 删除空消息
memory.remove(lambda m: not m.content)
```

### inject - 注入消息

在指定位置注入消息，常用于 RAG 场景。

```python
from alphora.memory import Message, Position

# 注入到最后一个 user 消息之前（RAG 推荐位置）
memory.inject(
    Message.system(f"参考资料:\n{retrieved_docs}"),
    position=Position.BEFORE_LAST_USER
)

# 注入到开头
memory.inject(
    Message.system("对话背景信息..."),
    position=Position.START
)

# 注入到末尾
memory.inject(
    Message.system("补充说明..."),
    position=Position.END
)

# 注入到指定索引
memory.inject(Message.user("插入的消息"), position=5)

# 批量注入
memory.inject([msg1, msg2, msg3], position=Position.START)
```

### Message 不可变更新

Message 提供不可变更新方法，返回新实例而不修改原对象：

```python
msg = Message.user("原始内容")

# 更新内容
new_msg = msg.with_content("新内容")

# 更新元数据
new_msg = msg.with_metadata(source="rag", score=0.95)

# 添加标签
new_msg = msg.with_tags("important", "reviewed")

# 固定
new_msg = msg.pinned()
```

---

## 工具调用

Memory 完整支持 OpenAI Function Calling 格式，并提供工具链验证。

### 基础流程

```python
# 1. 用户输入
memory.add_user("北京天气怎么样？")

# 2. 调用 LLM
history = memory.build_history()
response = await prompt.acall(history=history, tools=tools)

# 3. 添加助手响应（智能识别工具调用）
memory.add_assistant(response)

# 4. 执行工具并记录结果
if response.tool_calls:
    results = await executor.execute(response)
    memory.add_tool_result(results)

# 5. 继续对话
history = memory.build_history()
final_response = await prompt.acall(history=history)
memory.add_assistant(final_response)
```

### 工具结果添加方式

```python
# 方式 1：直接传入执行结果（推荐）
results = await executor.execute(response.tool_calls)
memory.add_tool_result(results)

# 方式 2：传入单个结果
memory.add_tool_result(result)

# 方式 3：手动指定参数
memory.add_tool_result(
    tool_call_id="call_abc123",
    name="get_weather",
    content={"city": "北京", "weather": "晴", "temp": 25}
)
```

### 工具链验证

```python
# 检查工具链完整性
is_valid, error_msg, incomplete = memory.check_tool_chain()

if not is_valid:
    print(f"工具链不完整: {error_msg}")
    for tc in incomplete:
        print(f"  缺少结果: {tc['function']['name']}")

# 获取待处理的工具调用
pending = memory.get_pending_tool_calls()

# 构建历史时跳过验证（工具调用进行中）
history = memory.build_history_unsafe()
```

### 工具调用精简

长 Agent 循环后，工具调用细节可能占用大量上下文：

```python
from alphora.memory.processors import remove_tool_details, summarize_tool_calls

# 完全移除工具调用细节
history = memory.build_history(processor=remove_tool_details())

# 折叠为摘要
history = memory.build_history(processor=summarize_tool_calls())

# 自定义摘要格式
history = memory.build_history(
    processor=summarize_tool_calls(
        format_fn=lambda calls: f"[执行了 {len(calls)} 个工具]"
    )
)
```

---

## 历史管理

### 删除操作

```python
# 删除最后 N 条
memory.delete_last(count=3)

# 删除最后一轮对话（最后一个 user 及其后的所有消息）
memory.delete_last_round()

# 删除最后一轮工具调用（assistant+tool_calls → tools → assistant）
memory.delete_last_tool_round()

# 删除指定消息
memory.delete_message("msg_id_xxx")

# 清空会话
memory.clear()
```

### 压缩

```python
# 保留最后 N 条
memory.compress(keep_last=20)

# 保留最后 N 轮
memory.compress(keep_rounds=5)

# 保留重要消息
memory.compress(
    keep_last=20,
    keep_pinned=True,
    keep_tagged=["important"]
)

# 带摘要的压缩
def summarize(messages):
    contents = [m.content for m in messages if m.content]
    return f"之前讨论了: {', '.join(contents[:3])}..."

memory.compress(keep_last=10, summarizer=summarize)
```

### 撤销/重做

```python
# 撤销上一次操作
memory.undo()

# 重做
memory.redo()

# 检查是否可撤销/重做
if memory.can_undo():
    memory.undo()
```

---

## 多会话管理

```python
# 不同会话使用不同的 session_id
memory.add_user("你好", session_id="user_001")
memory.add_user("Hello", session_id="user_002")

# 获取指定会话历史
history = memory.build_history(session_id="user_001")

# 列出所有会话
sessions = memory.list_sessions()

# 检查会话是否存在
if memory.has_session("user_001"):
    ...

# 获取会话统计
stats = memory.get_session_stats("user_001")
print(stats)
# {
#     "session_id": "user_001",
#     "total_messages": 42,
#     "rounds": 15,
#     "role_counts": {"user": 15, "assistant": 20, "tool": 7},
#     "tool_chain_valid": True,
#     "pinned_count": 3,
#     ...
# }

# 复制会话
memory.copy_session("user_001", "user_001_backup")

# 删除会话
memory.delete_session("user_001")
```

---

## 存储配置

```python
# 内存存储（默认，进程结束后丢失）
memory = MemoryManager()

# JSON 文件存储
memory = MemoryManager(
    storage_type="json",
    storage_path="./chat_history.json"
)

# SQLite 存储
memory = MemoryManager(
    storage_type="sqlite",
    storage_path="./chat.db"
)

# 配置选项
memory = MemoryManager(
    storage_type="sqlite",
    storage_path="./chat.db",
    auto_save=True,           # 自动保存
    max_messages=1000,        # 超出自动压缩
    enable_undo=True,         # 启用撤销
    undo_limit=50             # 撤销历史限制
)

# 手动保存/重载
memory.save()
memory.reload()
```

---

## API 参考

### MemoryManager

#### 添加消息
| 方法 | 说明 |
|------|------|
| `add_user(content, session_id, **metadata)` | 添加用户消息 |
| `add_assistant(content, tool_calls, session_id, **metadata)` | 添加助手消息 |
| `add_tool_result(result, tool_call_id, name, content, session_id)` | 添加工具结果 |
| `add_system(content, session_id, **metadata)` | 添加系统消息 |
| `add_message(message, session_id)` | 添加原始消息 |
| `add_messages(messages, session_id)` | 批量添加消息 |

#### 获取消息
| 方法 | 说明 |
|------|------|
| `get_messages(session_id, limit, offset, role, filter)` | 获取消息列表 |
| `get_last_message(session_id, role)` | 获取最后一条消息 |
| `get_message_by_id(message_id, session_id)` | 按 ID 获取消息 |
| `get_pinned(session_id)` | 获取固定的消息 |
| `get_tagged(tag, session_id)` | 获取带标签的消息 |

#### 构建历史
| 方法 | 说明 |
|------|------|
| `build_history(session_id, max_rounds, max_messages, processor, ...)` | 构建历史载荷 |
| `build_history_unsafe(...)` | 构建历史（跳过工具链验证） |

#### 上下文操作
| 方法 | 说明 |
|------|------|
| `apply(fn, predicate, session_id)` | 变换消息（永久） |
| `remove(predicate, session_id)` | 删除消息（永久） |
| `inject(message, position, session_id)` | 注入消息 |

#### 标记系统
| 方法 | 说明 |
|------|------|
| `pin(target, session_id)` | 固定消息 |
| `unpin(target, session_id)` | 取消固定 |
| `tag(tag_name, target, session_id)` | 添加标签 |
| `untag(tag_name, target, session_id)` | 移除标签 |

#### 历史管理
| 方法 | 说明 |
|------|------|
| `delete_message(message_id, session_id)` | 删除指定消息 |
| `delete_last(count, session_id)` | 删除最后 N 条 |
| `delete_last_round(session_id)` | 删除最后一轮对话 |
| `delete_last_tool_round(session_id)` | 删除最后一轮工具调用 |
| `clear(session_id)` | 清空会话 |
| `compress(session_id, keep_last, keep_rounds, keep_pinned, ...)` | 压缩历史 |

#### 撤销/重做
| 方法 | 说明 |
|------|------|
| `undo(session_id)` | 撤销 |
| `redo(session_id)` | 重做 |
| `can_undo(session_id)` | 是否可撤销 |
| `can_redo(session_id)` | 是否可重做 |

#### 会话管理
| 方法 | 说明 |
|------|------|
| `list_sessions()` | 列出所有会话 |
| `has_session(session_id)` | 检查会话是否存在 |
| `get_session_stats(session_id)` | 获取会话统计 |
| `delete_session(session_id)` | 删除会话 |
| `copy_session(from_session, to_session, overwrite)` | 复制会话 |

#### 工具链
| 方法 | 说明 |
|------|------|
| `check_tool_chain(session_id)` | 检查工具链完整性 |
| `get_pending_tool_calls(session_id)` | 获取待处理的工具调用 |

### 内置处理器

```python
from alphora.memory.processors import (
    # 过滤
    keep_last,              # keep_last(n)
    keep_first,             # keep_first(n)
    keep_rounds,            # keep_rounds(n)
    keep_roles,             # keep_roles("user", "assistant")
    exclude_roles,          # exclude_roles("tool", "system")
    keep_pinned,            # keep_pinned()
    keep_tagged,            # keep_tagged("tag1", "tag2")
    exclude_tagged,         # exclude_tagged("tag")
    filter_by,              # filter_by(predicate)
    exclude_by,             # exclude_by(predicate)
    keep_important_and_last,  # keep_important_and_last(n, include_pinned, include_tags)
    
    # 变换
    truncate_content,       # truncate_content(max_length, suffix)
    map_content,            # map_content(fn)
    map_messages,           # map_messages(fn)
    
    # 工具调用
    summarize_tool_calls,   # summarize_tool_calls(format_fn)
    remove_tool_details,    # remove_tool_details()
    keep_final_tool_result, # keep_final_tool_result()
    
    # Token 控制
    token_budget,           # token_budget(max_tokens, tokenizer, reserve)
    
    # 组合
    chain,                  # chain(proc1, proc2, ...)
    identity,               # identity()
)
```
