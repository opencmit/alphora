"""
Alphora Memory Component - 对话历史管理组件

核心特性:
- 标准 OpenAI 消息格式 (user/assistant/tool/system)
- 完整的工具调用链路支持
- 灵活的历史构建与压缩
- 多种存储后端 (内存/JSON/SQLite)
- 撤销/重做支持
- 多会话管理

v2 新增特性:
- 处理器机制 (processor): 构建历史时临时处理消息
- 标记系统 (pin/tag): 标记重要消息，压缩时保留
- apply/remove: 永久修改存储数据
- inject: 注入上下文消息
- 内置处理器: 常用操作开箱即用

================================================================================
快速开始
================================================================================

```python
from alphora.memory import MemoryManager

# 创建管理器 (内存存储)
memory = MemoryManager()

# 或使用持久化存储
memory = MemoryManager(storage_path="./chat.db", storage_type="sqlite")
```

================================================================================
基本对话
================================================================================

```python
# 添加消息
memory.add_user("你好")
memory.add_assistant("你好！有什么可以帮你的？")

# 获取历史
history = memory.build_history(max_rounds=5)

# 传入 LLM
response = await prompt.acall(query="今天天气怎么样？", history=history)
```

================================================================================
v2 新增：处理器机制
================================================================================

```python
# 方式 1：自定义处理器 (lambda)
history = memory.build_history(
    processor=lambda msgs: msgs[-20:]  # 只保留最后 20 条
)

# 方式 2：使用内置处理器
from alphora.memory.processors import keep_last, exclude_roles, chain

history = memory.build_history(
    processor=chain(
        exclude_roles("tool", "system"),  # 排除工具和系统消息
        keep_last(20)                      # 保留最后 20 条
    )
)

# 方式 3：便捷参数
history = memory.build_history(
    exclude_roles=["tool"],
    keep_pinned=True,
    max_messages=30
)
```

================================================================================
v2 新增：标记系统
================================================================================

```python
# 固定重要消息（压缩时保留）
memory.pin(lambda m: "重要" in (m.content or ""))
memory.pin("msg_id_xxx")  # 按 ID

# 添加标签
memory.tag("user_pref", lambda m: "喜欢" in (m.content or ""))

# 构建时保留标记的消息
history = memory.build_history(
    keep_pinned=True,
    keep_tagged=["user_pref"],
    max_messages=20
)
```

================================================================================
v2 新增：永久修改
================================================================================

```python
# 截断超长消息
memory.apply(
    fn=lambda m: m.with_content(m.content[:1000]),
    predicate=lambda m: len(m.content or "") > 1000
)

# 删除满足条件的消息
memory.remove(lambda m: m.role == "tool" and "error" in (m.content or ""))

# 注入上下文（如 RAG 结果）
memory.inject(
    Message.system(f"参考资料:\\n{rag_context}"),
    position="before_last_user"
)
```

================================================================================
工具调用
================================================================================

```python
response = await prompt.acall(
    tools=registry.get_openai_tools_schema(),
    history=memory.build_history()
)

memory.add_assistant(response)  # 智能识别工具调用

if response.tool_calls:
    results = await executor.execute(response)
    memory.add_tool_result(results)
```

================================================================================
历史管理
================================================================================

```python
# 删除最后一轮对话
memory.delete_last_round()

# 压缩历史（保留重要消息）
memory.compress(keep_last=20, keep_pinned=True)

# 撤销/重做
memory.undo()
memory.redo()

# 清空会话
memory.clear()
```

================================================================================
多会话支持
================================================================================

```python
# 使用不同的 session_id 管理多个对话
memory.add_user("你好", session_id="user_001")
memory.add_user("Hello", session_id="user_002")

# 获取指定会话的历史
history = memory.build_history(session_id="user_001")

# 列出所有会话
sessions = memory.list_sessions()

# 删除会话
memory.delete_session("user_001")
```
"""

from alphora.memory.manager import MemoryManager, Position
from alphora.memory.message import Message, MessageRole, ToolCall
from alphora.memory.history_payload import (
    HistoryPayload,
    ToolChainValidator,
    ToolChainError,
    is_valid_history_payload
)

# 导出处理器（可选导入）
from alphora.memory import processors

__all__ = [
    # 核心类
    "MemoryManager",
    "Message",
    "MessageRole",
    "ToolCall",

    # 历史载荷
    "HistoryPayload",
    "ToolChainValidator",
    "ToolChainError",
    "is_valid_history_payload",

    # 位置常量
    "Position",

    # 处理器模块
    "processors",
]