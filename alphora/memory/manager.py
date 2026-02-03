# Copyright 2026 China Mobile Information Technology Co., Ltd.
# SPDX-License-Identifier: Apache-2.0
#
# Author: Tian Tian (tiantianit@chinamobile.com)

"""
记忆管理器

统一的对话历史管理入口，提供简洁、开发者友好的API。

核心特性:
- 标准 OpenAI 消息格式
- 完整工具调用链路支持（带验证）
- 多会话管理
- 历史压缩与清理
- 撤销/重做支持
- 多种存储后端

增强特性 (v2):
- 处理器机制 (processor): 构建历史时临时处理消息
- 标记系统 (pin/tag): 标记重要消息，压缩时保留
- apply/remove: 永久修改存储数据
- inject: 注入上下文消息
- 内置处理器: 常用操作开箱即用
"""

from typing import (
    Any, Dict, List, Optional, Union, Literal,
    Callable, Tuple, Set, overload
)
from pathlib import Path
import time
import json
import logging
import copy

from alphora.memory.message import Message, MessageRole, ToolCall
from alphora.memory.history_payload import (
    HistoryPayload,
    ToolChainValidator,
    ToolChainError,
    is_valid_history_payload
)
from alphora.memory.processors import (
    Processor,
    ProcessorContext,
    chain,
    keep_last,
    keep_roles,
    exclude_roles,
    keep_pinned,
    keep_tagged,
    keep_important_and_last,
)

logger = logging.getLogger(__name__)


# 位置常量
class Position:
    """注入位置常量"""
    START = "start"
    END = "end"
    BEFORE_LAST_USER = "before_last_user"
    AFTER_LAST_USER = "after_last_user"


# 目标类型（用于 pin/tag/remove 等方法）
Target = Union[str, Callable[[Message], bool], List[str]]


class MemoryManager:
    """
    记忆管理器

    管理对话历史，支持多会话、工具调用、历史压缩等功能。

    基本用法:
    ```python
    # 创建管理器
    memory = MemoryManager()

    # 添加对话
    memory.add_user("你好")
    memory.add_assistant("你好！有什么可以帮你的？")

    # 获取历史
    history = memory.build_history(max_rounds=5)

    # 传入 BasePrompt
    response = await prompt.acall(query="新问题", history=history)
    ```

    增强用法 (v2):
    ```python
    # 使用处理器
    history = memory.build_history(
        processor=lambda msgs: msgs[-20:]  # 自定义处理
    )

    # 使用内置处理器
    from alphora.memory.processors import keep_last, exclude_roles, chain
    history = memory.build_history(
        processor=chain(exclude_roles("tool"), keep_last(20))
    )

    # 使用便捷参数
    history = memory.build_history(
        exclude_roles=["tool"],
        keep_last=20,
        keep_pinned=True
    )

    # 标记重要消息
    memory.pin(lambda m: "重要" in (m.content or ""))
    memory.tag("user_pref", lambda m: "喜欢" in (m.content or ""))

    # 永久修改
    memory.apply(
        fn=lambda m: m.with_content(m.content[:1000]),
        predicate=lambda m: len(m.content or "") > 1000
    )
    ```
    """

    DEFAULT_SESSION = "default"

    def __init__(
            self,
            storage_path: Optional[str] = None,
            storage_type: Literal["memory", "json", "sqlite"] = "memory",
            auto_save: bool = True,
            max_messages: Optional[int] = None,
            enable_undo: bool = True,
            undo_limit: int = 50,
    ):
        """
        Args:
            storage_path: 持久化存储路径 (memory 类型不需要)
            storage_type: 存储类型
                - "memory": 内存存储 (默认，进程结束后丢失)
                - "json": JSON 文件存储
                - "sqlite": SQLite 数据库存储
            auto_save: 是否自动保存 (仅对持久化存储有效)
            max_messages: 每个会话的最大消息数 (超出时自动压缩)
            enable_undo: 是否启用撤销功能
            undo_limit: 撤销历史最大数量
        """
        self._storage_type = storage_type
        self._storage_path = storage_path
        self._auto_save = auto_save
        self._max_messages = max_messages
        self._enable_undo = enable_undo
        self._undo_limit = undo_limit

        # 初始化存储
        self._storage = self._create_storage(storage_type, storage_path)

        # 内存缓存: session_id -> List[Message]
        self._cache: Dict[str, List[Message]] = {}

        # 撤销/重做栈: session_id -> (undo_stack, redo_stack)
        self._undo_stacks: Dict[str, List[List[Message]]] = {}
        self._redo_stacks: Dict[str, List[List[Message]]] = {}

        # 从存储加载
        self._load_from_storage()

    def _create_storage(self, storage_type: str, path: Optional[str]):
        """创建存储后端"""
        if storage_type == "memory":
            from alphora.storage import InMemoryStorage
            return InMemoryStorage()
        elif storage_type == "json":
            from alphora.storage import JSONStorage
            return JSONStorage(path=path)
        elif storage_type == "sqlite":
            from alphora.storage import SQLiteStorage
            return SQLiteStorage(path=path)
        else:
            raise ValueError(f"Unknown storage type: {storage_type}")

    def _get_storage_key(self, session_id: str) -> str:
        """获取存储键名"""
        return f"messages:{session_id}"

    def _load_from_storage(self):
        """从存储加载数据"""
        keys = self._storage.keys("messages:*")
        for key in keys:
            session_id = key.replace("messages:", "")
            data_list = self._storage.lrange(key, 0, -1)
            self._cache[session_id] = [
                Message.from_dict(d) if isinstance(d, dict) else d
                for d in data_list
            ]

    def _save_session(self, session_id: str):
        """保存指定会话到存储"""
        if session_id not in self._cache:
            return

        key = self._get_storage_key(session_id)
        self._storage.delete(key)

        for msg in self._cache[session_id]:
            self._storage.rpush(key, msg.to_dict())

        if self._auto_save:
            self._storage.save()

    def _ensure_session(self, session_id: str):
        """确保会话存在"""
        if session_id not in self._cache:
            self._cache[session_id] = []
        if self._enable_undo:
            if session_id not in self._undo_stacks:
                self._undo_stacks[session_id] = []
            if session_id not in self._redo_stacks:
                self._redo_stacks[session_id] = []

    def _save_undo_state(self, session_id: str):
        """保存撤销状态"""
        if not self._enable_undo:
            return

        self._ensure_session(session_id)

        # 保存当前状态的深拷贝
        current_state = [copy.deepcopy(msg) for msg in self._cache.get(session_id, [])]
        self._undo_stacks[session_id].append(current_state)

        # 限制撤销栈大小
        if len(self._undo_stacks[session_id]) > self._undo_limit:
            self._undo_stacks[session_id] = self._undo_stacks[session_id][-self._undo_limit:]

        # 新操作清空重做栈
        self._redo_stacks[session_id] = []

    def _check_auto_compress(self, session_id: str):
        """检查是否需要自动压缩"""
        if self._max_messages and session_id in self._cache:
            if len(self._cache[session_id]) > self._max_messages:
                self.compress(session_id=session_id, keep_last=self._max_messages)

    def _resolve_target(
            self,
            target: Target,
            session_id: str
    ) -> Callable[[Message], bool]:
        """
        将目标参数转换为谓词函数

        Args:
            target: 目标，可以是:
                - str: 消息 ID
                - List[str]: 消息 ID 列表
                - Callable: 谓词函数
            session_id: 会话 ID

        Returns:
            谓词函数
        """
        if callable(target):
            return target
        elif isinstance(target, str):
            return lambda m: m.id == target
        elif isinstance(target, list):
            target_set = set(target)
            return lambda m: m.id in target_set
        else:
            raise TypeError(f"Invalid target type: {type(target)}")

    # =========================================================================
    # 添加消息 API
    # =========================================================================

    def add_user(
            self,
            content: str,
            session_id: str = DEFAULT_SESSION,
            **metadata
    ) -> Message:
        """
        添加用户消息

        Args:
            content: 用户输入内容
            session_id: 会话ID
            **metadata: 额外元数据

        Returns:
            创建的 Message 对象

        Example:
            memory.add_user("你好，帮我查一下天气")
        """
        msg = Message.user(content, **metadata)
        return self._add_message(msg, session_id)

    def add_assistant(
            self,
            content: Optional[Union[str, Any]] = None,
            tool_calls: Optional[List[Union[Dict, ToolCall]]] = None,
            session_id: str = DEFAULT_SESSION,
            **metadata
    ) -> Message:
        """
        添加助手消息 (智能识别响应类型)

        支持直接传入 LLM 响应对象，自动判断是工具调用还是普通回复。

        Args:
            content: 回复内容，支持以下类型:
                - str: 普通文本回复
                - PrompterOutput: 普通文本回复 (会自动转为 str)
                - ToolCall 对象: 自动提取 tool_calls 和 content
                - None: 仅当有 tool_calls 参数时使用
            tool_calls: 工具调用列表 (可选，如果 content 是 ToolCall 则自动提取)
            session_id: 会话ID
            **metadata: 额外元数据

        Returns:
            创建的 Message 对象

        Example:
            # 方式 1: 直接传入 LLM 响应 (推荐)
            response = await prompt.acall(query="你好", tools=tools)
            memory.add_assistant(response)

            # 方式 2: 普通文本回复
            memory.add_assistant("你好！有什么可以帮你的？")

            # 方式 3: 显式工具调用
            memory.add_assistant(tool_calls=[...])
        """
        actual_content = content
        actual_tool_calls = tool_calls

        # 智能识别 ToolCall 对象
        if isinstance(content, list) and hasattr(content, 'content'):
            tc_obj = content
            if len(tc_obj) > 0:
                actual_tool_calls = list(tc_obj)
                actual_content = tc_obj.content
            else:
                actual_content = tc_obj.content or str(tc_obj) if tc_obj.content else None
                actual_tool_calls = None
        elif content is not None and not isinstance(content, str):
            actual_content = str(content)

        msg = Message.assistant(actual_content, actual_tool_calls, **metadata)
        return self._add_message(msg, session_id)

    def add_tool_result(
            self,
            result: Optional[Union[Any, List[Any]]] = None,
            tool_call_id: Optional[str] = None,
            name: Optional[str] = None,
            content: Optional[Union[str, Dict, Any]] = None,
            session_id: str = DEFAULT_SESSION,
            **metadata
    ) -> Union[Message, List[Message]]:
        """
        添加工具执行结果 (智能识别)

        支持多种调用方式，可直接传入 executor.execute() 的结果。

        Args:
            result: 工具执行结果，支持:
                - ToolExecutionResult: 单个结果
                - List[ToolExecutionResult]: 多个结果 (批量添加)
            tool_call_id: 工具调用ID (传统方式)
            name: 工具名称 (传统方式)
            content: 执行结果内容 (传统方式)
            session_id: 会话ID
            **metadata: 额外元数据

        Returns:
            创建的 Message 对象 (批量时返回列表)

        Example:
            # 方式 1: 直接传入 executor 结果 (推荐)
            results = await executor.execute(response.tool_calls)
            memory.add_tool_result(results)

            # 方式 2: 传统方式
            memory.add_tool_result(
                tool_call_id="call_123",
                name="get_weather",
                content={"city": "北京", "weather": "晴"}
            )
        """
        # 方式 1: 传入列表
        if isinstance(result, list):
            messages = []
            for r in result:
                msg = self._add_single_tool_result(
                    tool_call_id=r.tool_call_id,
                    name=r.tool_name,
                    content=r.content,
                    session_id=session_id,
                    **metadata
                )
                messages.append(msg)
            return messages

        # 方式 2: 传入单个 ToolExecutionResult
        if result is not None and hasattr(result, 'tool_call_id'):
            return self._add_single_tool_result(
                tool_call_id=result.tool_call_id,
                name=result.tool_name,
                content=result.content,
                session_id=session_id,
                **metadata
            )

        # 方式 3: 传统参数方式
        if tool_call_id is not None:
            return self._add_single_tool_result(
                tool_call_id=tool_call_id,
                name=name,
                content=content,
                session_id=session_id,
                **metadata
            )

        raise ValueError(
            "add_tool_result requires either 'result' (ToolExecutionResult) "
            "or 'tool_call_id', 'name', 'content' parameters"
        )

    def _add_single_tool_result(
            self,
            tool_call_id: str,
            name: str,
            content: Union[str, Dict, Any],
            session_id: str = DEFAULT_SESSION,
            **metadata
    ) -> Message:
        """添加单个工具结果 (内部方法)"""
        if not self._validate_tool_call_id(session_id, tool_call_id):
            logger.warning(
                f"tool_call_id '{tool_call_id}' not found in session '{session_id}'. "
                "This may cause tool chain validation to fail."
            )

        if not isinstance(content, str):
            content = json.dumps(content, ensure_ascii=False)

        msg = Message.tool(tool_call_id, content, name, **metadata)
        return self._add_message(msg, session_id)

    def _validate_tool_call_id(self, session_id: str, tool_call_id: str) -> bool:
        """验证 tool_call_id 是否存在于历史中"""
        messages = self._cache.get(session_id, [])
        for msg in messages:
            if msg.has_tool_calls:
                for tc in msg.tool_calls:
                    if tc.id == tool_call_id:
                        return True
        return False

    def add_system(
            self,
            content: str,
            session_id: str = DEFAULT_SESSION,
            **metadata
    ) -> Message:
        """
        添加系统消息

        Args:
            content: 系统指令内容
            session_id: 会话ID
            **metadata: 额外元数据

        Returns:
            创建的 Message 对象
        """
        msg = Message.system(content, **metadata)
        return self._add_message(msg, session_id)

    def add_message(
            self,
            message: Union[Message, Dict],
            session_id: str = DEFAULT_SESSION
    ) -> Message:
        """
        添加原始消息

        支持 Message 对象或 OpenAI 格式的 dict。

        Args:
            message: 消息对象或字典
            session_id: 会话ID

        Returns:
            添加的 Message 对象
        """
        if isinstance(message, dict):
            message = Message.from_openai_format(message)
        return self._add_message(message, session_id)

    def add_messages(
            self,
            messages: List[Union[Message, Dict]],
            session_id: str = DEFAULT_SESSION
    ) -> List[Message]:
        """
        批量添加消息

        Args:
            messages: 消息列表
            session_id: 会话ID

        Returns:
            添加的 Message 对象列表
        """
        result = []
        for msg in messages:
            result.append(self.add_message(msg, session_id))
        return result

    def _add_message(self, message: Message, session_id: str) -> Message:
        """内部添加消息方法"""
        self._ensure_session(session_id)
        self._save_undo_state(session_id)

        self._cache[session_id].append(message)
        self._check_auto_compress(session_id)
        self._save_session(session_id)

        return message

    # =========================================================================
    # 获取消息 API
    # =========================================================================

    def get_messages(
            self,
            session_id: str = DEFAULT_SESSION,
            limit: Optional[int] = None,
            offset: int = 0,
            role: Optional[str] = None,
            filter: Optional[Callable[[Message], bool]] = None
    ) -> List[Message]:
        """
        获取消息列表

        Args:
            session_id: 会话ID
            limit: 返回数量限制
            offset: 偏移量 (从末尾算起)
            role: 筛选角色 (user/assistant/tool/system)
            filter: 自定义过滤函数 (v2 新增)

        Returns:
            Message 列表

        Example:
            # 获取所有消息
            messages = memory.get_messages()

            # 获取最后5条
            messages = memory.get_messages(limit=5)

            # 只获取用户消息
            messages = memory.get_messages(role="user")

            # 获取被固定的消息 (v2)
            messages = memory.get_messages(filter=lambda m: m.is_pinned)
        """
        messages = self._cache.get(session_id, [])

        # 角色过滤
        if role:
            messages = [m for m in messages if m.role == role]

        # 自定义过滤
        if filter:
            messages = [m for m in messages if filter(m)]

        # 偏移和限制
        if offset:
            messages = messages[:-offset] if offset < len(messages) else []

        if limit:
            messages = messages[-limit:]

        return messages

    def get_last_message(
            self,
            session_id: str = DEFAULT_SESSION,
            role: Optional[str] = None
    ) -> Optional[Message]:
        """
        获取最后一条消息

        Args:
            session_id: 会话ID
            role: 筛选角色

        Returns:
            最后一条 Message，不存在返回 None
        """
        messages = self.get_messages(session_id, role=role)
        return messages[-1] if messages else None

    def get_message_by_id(
            self,
            message_id: str,
            session_id: str = DEFAULT_SESSION
    ) -> Optional[Message]:
        """根据消息ID获取消息"""
        for msg in self._cache.get(session_id, []):
            if msg.id == message_id:
                return msg
        return None

    def get_pinned(self, session_id: str = DEFAULT_SESSION) -> List[Message]:
        """
        获取所有被固定的消息

        Args:
            session_id: 会话ID

        Returns:
            被固定的 Message 列表
        """
        return self.get_messages(session_id, filter=lambda m: m.is_pinned)

    def get_tagged(
            self,
            tag: str,
            session_id: str = DEFAULT_SESSION
    ) -> List[Message]:
        """
        获取带有指定标签的消息

        Args:
            tag: 标签名
            session_id: 会话ID

        Returns:
            带有标签的 Message 列表
        """
        return self.get_messages(session_id, filter=lambda m: m.has_tag(tag))

    # =========================================================================
    # 构建历史 API (v2 增强)
    # =========================================================================

    def build_history(
            self,
            session_id: str = DEFAULT_SESSION,
            max_rounds: Optional[int] = None,
            max_messages: Optional[int] = None,
            include_system: bool = False,
            validate_tool_chain: bool = True,
            # v2 新增参数
            processor: Optional[Union[Processor, List[Processor]]] = None,
            exclude_roles: Optional[List[str]] = None,
            keep_pinned: bool = False,
            keep_tagged: Optional[List[str]] = None,
    ) -> HistoryPayload:
        """
        构建历史记录载荷 (用于传入 BasePrompt)

        这是获取历史记录的推荐方式。返回的 HistoryPayload 对象
        包含验证信息，可以安全地传入 BasePrompt.call/acall。

        Args:
            session_id: 会话ID
            max_rounds: 最大对话轮数 (一问一答算一轮)
            max_messages: 最大消息数
            include_system: 是否包含历史中的 system 消息
            validate_tool_chain: 是否验证工具调用链完整性

            # v2 新增参数
            processor: 处理器，可以是:
                - Callable[[List[Message]], List[Message]]: 自定义处理函数
                - List[Processor]: 多个处理器依次执行
            exclude_roles: 排除的角色列表 (便捷参数)
            keep_pinned: 是否保留被固定的消息 (便捷参数)
            keep_tagged: 保留带有这些标签的消息 (便捷参数)

        Returns:
            HistoryPayload 对象

        Raises:
            ToolChainError: 如果工具调用链不完整

        Example:
            # 基础用法
            history = memory.build_history(max_rounds=5)

            # 使用处理器
            history = memory.build_history(
                processor=lambda msgs: msgs[-20:]
            )

            # 使用便捷参数
            history = memory.build_history(
                exclude_roles=["tool"],
                keep_pinned=True,
                max_messages=30
            )

            # 组合使用
            from alphora.memory.processors import chain, truncate_content
            history = memory.build_history(
                exclude_roles=["system"],
                processor=chain(
                    keep_important_and_last(20),
                    truncate_content(2000)
                )
            )
        """
        messages = self._cache.get(session_id, [])

        # 1. 过滤 system 消息 (如果不需要)
        if not include_system:
            messages = [m for m in messages if m.role != "system"]

        # 2. 按轮数限制
        if max_rounds:
            messages = self._limit_by_rounds(messages, max_rounds)

        # 3. 按消息数限制
        if max_messages and len(messages) > max_messages:
            messages = messages[-max_messages:]

        # 4. 处理便捷参数 (转换为处理器链)
        convenience_processors: List[Processor] = []

        if exclude_roles:
            from alphora.memory.processors import exclude_roles as _exclude_roles
            convenience_processors.append(_exclude_roles(*exclude_roles))

        if keep_pinned or keep_tagged:
            from alphora.memory.processors import keep_important_and_last
            # 便捷参数的 keep_pinned/keep_tagged 配合 max_messages 使用
            n = max_messages if max_messages else len(messages)
            convenience_processors.append(
                keep_important_and_last(
                    n=n,
                    include_pinned=keep_pinned,
                    include_tags=keep_tagged
                )
            )

        # 5. 应用便捷参数处理器
        for proc in convenience_processors:
            messages = proc(messages)

        # 6. 应用自定义处理器
        if processor:
            if callable(processor) and not isinstance(processor, list):
                messages = processor(messages)
            elif isinstance(processor, list):
                for proc in processor:
                    messages = proc(messages)

        # 7. 转换为 OpenAI 格式
        openai_messages = [m.to_openai_format() for m in messages]

        # 8. 计算轮数
        round_count = sum(1 for m in messages if m.role == "user")

        # 9. 创建 HistoryPayload
        return HistoryPayload.create(
            messages=openai_messages,
            session_id=session_id,
            round_count=round_count,
            validate_tool_chain=validate_tool_chain
        )

    def build_history_unsafe(
            self,
            session_id: str = DEFAULT_SESSION,
            max_rounds: Optional[int] = None,
            max_messages: Optional[int] = None,
            include_system: bool = False,
            processor: Optional[Union[Processor, List[Processor]]] = None,
    ) -> HistoryPayload:
        """
        构建历史记录载荷 (不验证工具链)

        警告: 仅在你确定工具链是不完整的情况下使用（例如工具调用进行中）

        Args:
            session_id: 会话ID
            max_rounds: 最大对话轮数
            max_messages: 最大消息数
            include_system: 是否包含历史中的 system 消息
            processor: 处理器

        Returns:
            HistoryPayload 对象 (tool_chain_valid 可能为 False)
        """
        return self.build_history(
            session_id=session_id,
            max_rounds=max_rounds,
            max_messages=max_messages,
            include_system=include_system,
            validate_tool_chain=False,
            processor=processor
        )

    def _limit_by_rounds(self, messages: List[Message], max_rounds: int) -> List[Message]:
        """
        按对话轮数限制消息

        一轮 = user + assistant (+ 可能的 tool_calls + tool)
        从后往前数 max_rounds 轮
        """
        if not messages:
            return []

        rounds = 0
        cut_index = 0

        i = len(messages) - 1
        while i >= 0:
            msg = messages[i]
            if msg.role == "user":
                rounds += 1
                if rounds > max_rounds:
                    cut_index = i + 1
                    break
            i -= 1

        return messages[cut_index:]

    # =========================================================================
    # v2 新增：永久修改 API
    # =========================================================================

    def apply(
            self,
            fn: Callable[[Message], Message],
            predicate: Optional[Callable[[Message], bool]] = None,
            session_id: str = DEFAULT_SESSION
    ) -> int:
        """
        对消息应用变换 (永久修改)

        Args:
            fn: 变换函数，接收 Message 返回新的 Message
            predicate: 过滤条件，只对满足条件的消息应用变换
            session_id: 会话ID

        Returns:
            变换的消息数量

        Example:
            # 截断超长消息
            count = memory.apply(
                fn=lambda m: m.with_content(m.content[:1000]),
                predicate=lambda m: len(m.content or "") > 1000
            )

            # 给所有消息添加元数据
            memory.apply(
                fn=lambda m: m.with_metadata(processed=True)
            )
        """
        messages = self._cache.get(session_id, [])
        if not messages:
            return 0

        self._save_undo_state(session_id)

        count = 0
        new_messages = []

        for msg in messages:
            if predicate is None or predicate(msg):
                new_messages.append(fn(msg))
                count += 1
            else:
                new_messages.append(msg)

        self._cache[session_id] = new_messages

        if count > 0:
            self._save_session(session_id)

        return count

    def remove(
            self,
            predicate: Callable[[Message], bool],
            session_id: str = DEFAULT_SESSION
    ) -> int:
        """
        删除满足条件的消息 (永久修改)

        Args:
            predicate: 过滤条件，返回 True 的消息将被删除
            session_id: 会话ID

        Returns:
            删除的消息数量

        Example:
            # 删除所有工具消息
            count = memory.remove(lambda m: m.role == "tool")

            # 删除包含错误的消息
            count = memory.remove(lambda m: "error" in (m.content or "").lower())
        """
        messages = self._cache.get(session_id, [])
        if not messages:
            return 0

        self._save_undo_state(session_id)

        original_len = len(messages)
        self._cache[session_id] = [m for m in messages if not predicate(m)]

        removed = original_len - len(self._cache[session_id])

        if removed > 0:
            self._save_session(session_id)

        return removed

    def inject(
            self,
            message: Union[Message, List[Message]],
            position: Union[str, int] = Position.END,
            session_id: str = DEFAULT_SESSION
    ) -> None:
        """
        在指定位置注入消息 (永久修改)

        Args:
            message: 要注入的消息（单条或列表）
            position: 注入位置:
                - "start": 开头
                - "end": 结尾
                - "before_last_user": 最后一个 user 消息之前
                - "after_last_user": 最后一个 user 消息之后
                - int: 指定索引位置
            session_id: 会话ID

        Example:
            # 注入 RAG 上下文
            memory.inject(
                Message.system(f"参考资料:\\n{docs}"),
                position="before_last_user"
            )

            # 注入到开头
            memory.inject(
                Message.system("对话背景..."),
                position="start"
            )
        """
        self._ensure_session(session_id)
        self._save_undo_state(session_id)

        messages = self._cache[session_id]

        # 标准化为列表
        if isinstance(message, Message):
            to_inject = [message]
        else:
            to_inject = list(message)

        # 计算插入位置
        if position == Position.START:
            insert_index = 0
        elif position == Position.END:
            insert_index = len(messages)
        elif position == Position.BEFORE_LAST_USER:
            # 找最后一个 user 消息
            insert_index = len(messages)
            for i in range(len(messages) - 1, -1, -1):
                if messages[i].role == "user":
                    insert_index = i
                    break
        elif position == Position.AFTER_LAST_USER:
            insert_index = len(messages)
            for i in range(len(messages) - 1, -1, -1):
                if messages[i].role == "user":
                    insert_index = i + 1
                    break
        elif isinstance(position, int):
            insert_index = position
        else:
            raise ValueError(f"Invalid position: {position}")

        # 插入消息
        for i, msg in enumerate(to_inject):
            messages.insert(insert_index + i, msg)

        self._save_session(session_id)

    # =========================================================================
    # v2 新增：标记系统 API
    # =========================================================================

    def pin(
            self,
            target: Target,
            session_id: str = DEFAULT_SESSION
    ) -> int:
        """
        固定消息 (压缩时保留)

        Args:
            target: 目标，可以是:
                - str: 消息 ID
                - List[str]: 消息 ID 列表
                - Callable: 谓词函数
            session_id: 会话ID

        Returns:
            固定的消息数量

        Example:
            # 按 ID 固定
            memory.pin("msg_id_xxx")

            # 按条件固定
            memory.pin(lambda m: "重要" in (m.content or ""))
        """
        predicate = self._resolve_target(target, session_id)
        return self.apply(
            fn=lambda m: m.pinned(),
            predicate=lambda m: predicate(m) and not m.is_pinned,
            session_id=session_id
        )

    def unpin(
            self,
            target: Target,
            session_id: str = DEFAULT_SESSION
    ) -> int:
        """
        取消固定消息

        Args:
            target: 目标
            session_id: 会话ID

        Returns:
            取消固定的消息数量
        """
        predicate = self._resolve_target(target, session_id)
        return self.apply(
            fn=lambda m: m.unpinned(),
            predicate=lambda m: predicate(m) and m.is_pinned,
            session_id=session_id
        )

    def tag(
            self,
            tag_name: str,
            target: Target,
            session_id: str = DEFAULT_SESSION
    ) -> int:
        """
        给消息添加标签

        Args:
            tag_name: 标签名
            target: 目标
            session_id: 会话ID

        Returns:
            添加标签的消息数量

        Example:
            # 给满足条件的消息打标签
            memory.tag("user_pref", lambda m: "喜欢" in (m.content or ""))

            # 给指定 ID 的消息打标签
            memory.tag("important", "msg_id_xxx")
        """
        predicate = self._resolve_target(target, session_id)
        return self.apply(
            fn=lambda m: m.with_tags(tag_name),
            predicate=lambda m: predicate(m) and not m.has_tag(tag_name),
            session_id=session_id
        )

    def untag(
            self,
            tag_name: str,
            target: Target,
            session_id: str = DEFAULT_SESSION
    ) -> int:
        """
        移除消息标签

        Args:
            tag_name: 标签名
            target: 目标
            session_id: 会话ID

        Returns:
            移除标签的消息数量
        """
        predicate = self._resolve_target(target, session_id)
        return self.apply(
            fn=lambda m: m.without_tags(tag_name),
            predicate=lambda m: predicate(m) and m.has_tag(tag_name),
            session_id=session_id
        )

    # =========================================================================
    # 工具链相关 API
    # =========================================================================

    def check_tool_chain(
            self,
            session_id: str = DEFAULT_SESSION
    ) -> Tuple[bool, Optional[str], List[Dict]]:
        """
        检查工具调用链完整性

        Returns:
            (is_valid, error_message, incomplete_calls)
        """
        messages = [m.to_openai_format() for m in self._cache.get(session_id, [])]
        is_valid, error_msg = ToolChainValidator.validate(messages)
        incomplete = ToolChainValidator.find_incomplete_tool_calls(messages)
        return is_valid, error_msg, incomplete

    def get_pending_tool_calls(
            self,
            session_id: str = DEFAULT_SESSION
    ) -> List[Dict[str, Any]]:
        """
        获取所有待处理的工具调用
        """
        messages = [m.to_openai_format() for m in self._cache.get(session_id, [])]
        return ToolChainValidator.find_incomplete_tool_calls(messages)

    # =========================================================================
    # 删除/清理 API
    # =========================================================================

    def delete_message(
            self,
            message_id: str,
            session_id: str = DEFAULT_SESSION
    ) -> bool:
        """删除指定消息"""
        if session_id not in self._cache:
            return False

        self._save_undo_state(session_id)

        original_len = len(self._cache[session_id])
        self._cache[session_id] = [
            m for m in self._cache[session_id] if m.id != message_id
        ]

        if len(self._cache[session_id]) < original_len:
            self._save_session(session_id)
            return True
        return False

    def delete_last(
            self,
            count: int = 1,
            session_id: str = DEFAULT_SESSION
    ) -> int:
        """删除最后 N 条消息"""
        if session_id not in self._cache:
            return 0

        self._save_undo_state(session_id)

        original_len = len(self._cache[session_id])
        self._cache[session_id] = (
            self._cache[session_id][:-count] if count < original_len else []
        )

        deleted = original_len - len(self._cache[session_id])
        if deleted > 0:
            self._save_session(session_id)
        return deleted

    def delete_last_round(self, session_id: str = DEFAULT_SESSION) -> int:
        """
        删除最后一轮对话

        一轮 = 最后一个 user 消息及其后的所有消息
        """
        messages = self._cache.get(session_id, [])
        if not messages:
            return 0

        self._save_undo_state(session_id)

        cut_index = len(messages)
        for i in range(len(messages) - 1, -1, -1):
            if messages[i].role == "user":
                cut_index = i
                break

        deleted = len(messages) - cut_index
        self._cache[session_id] = messages[:cut_index]

        if deleted > 0:
            self._save_session(session_id)
        return deleted

    def delete_last_tool_round(self, session_id: str = DEFAULT_SESSION) -> int:
        """
        删除最后一轮工具调用

        包括: assistant(tool_calls) + 所有 tool 结果 + 最终 assistant 回复
        """
        messages = self._cache.get(session_id, [])
        if not messages:
            return 0

        self._save_undo_state(session_id)

        cut_index = len(messages)
        for i in range(len(messages) - 1, -1, -1):
            if messages[i].is_tool_call_request:
                cut_index = i
                break

        deleted = len(messages) - cut_index
        self._cache[session_id] = messages[:cut_index]

        if deleted > 0:
            self._save_session(session_id)
        return deleted

    def clear(self, session_id: str = DEFAULT_SESSION) -> int:
        """清空指定会话"""
        if session_id not in self._cache:
            return 0

        self._save_undo_state(session_id)

        count = len(self._cache[session_id])
        self._cache[session_id] = []

        if count > 0:
            self._save_session(session_id)
        return count

    def compress(
            self,
            session_id: str = DEFAULT_SESSION,
            keep_last: Optional[int] = None,
            keep_rounds: Optional[int] = None,
            keep_pinned: bool = False,
            keep_tagged: Optional[List[str]] = None,
            summarizer: Optional[Callable[[List[Message]], str]] = None
    ) -> int:
        """
        压缩历史记录

        Args:
            session_id: 会话ID
            keep_last: 保留最后 N 条消息
            keep_rounds: 保留最后 N 轮对话
            keep_pinned: 保留被固定的消息 (v2 新增)
            keep_tagged: 保留带有这些标签的消息 (v2 新增)
            summarizer: 自定义摘要函数

        Returns:
            压缩掉的消息数量
        """
        messages = self._cache.get(session_id, [])
        if not messages:
            return 0

        self._save_undo_state(session_id)

        original_len = len(messages)

        # 使用内部处理器逻辑
        if keep_pinned or keep_tagged:
            n = keep_last if keep_last else (keep_rounds * 3 if keep_rounds else 10)
            processor = keep_important_and_last(
                n=n,
                include_pinned=keep_pinned,
                include_tags=keep_tagged
            )
            messages = processor(messages)
        elif keep_rounds:
            messages = self._limit_by_rounds(messages, keep_rounds)
        elif keep_last:
            messages = messages[-keep_last:] if keep_last < len(messages) else messages

        # 生成摘要
        if summarizer and len(messages) < original_len:
            removed = self._cache[session_id][:-len(messages)] if messages else self._cache[session_id]
            summary = summarizer(removed)
            summary_msg = Message.system(f"[历史摘要] {summary}")
            messages = [summary_msg] + messages

        self._cache[session_id] = messages
        self._save_session(session_id)

        return original_len - len(messages)

    # =========================================================================
    # 撤销/重做 API
    # =========================================================================

    def undo(self, session_id: str = DEFAULT_SESSION) -> bool:
        """撤销上一次操作"""
        if not self._enable_undo:
            return False

        if not self._undo_stacks.get(session_id):
            return False

        current = [copy.deepcopy(m) for m in self._cache.get(session_id, [])]
        self._redo_stacks.setdefault(session_id, []).append(current)

        self._cache[session_id] = self._undo_stacks[session_id].pop()
        self._save_session(session_id)

        return True

    def redo(self, session_id: str = DEFAULT_SESSION) -> bool:
        """重做上一次撤销的操作"""
        if not self._enable_undo:
            return False

        if not self._redo_stacks.get(session_id):
            return False

        current = [copy.deepcopy(m) for m in self._cache.get(session_id, [])]
        self._undo_stacks.setdefault(session_id, []).append(current)

        self._cache[session_id] = self._redo_stacks[session_id].pop()
        self._save_session(session_id)

        return True

    def can_undo(self, session_id: str = DEFAULT_SESSION) -> bool:
        """是否可以撤销"""
        return bool(self._undo_stacks.get(session_id))

    def can_redo(self, session_id: str = DEFAULT_SESSION) -> bool:
        """是否可以重做"""
        return bool(self._redo_stacks.get(session_id))

    # =========================================================================
    # 会话管理 API
    # =========================================================================

    def list_sessions(self) -> List[str]:
        """列出所有会话ID"""
        return list(self._cache.keys())

    def has_session(self, session_id: str) -> bool:
        """检查会话是否存在"""
        return session_id in self._cache and len(self._cache[session_id]) > 0

    def get_session_stats(self, session_id: str = DEFAULT_SESSION) -> Dict[str, Any]:
        """获取会话统计信息"""
        messages = self._cache.get(session_id, [])

        if not messages:
            return {
                "session_id": session_id,
                "exists": False,
                "total_messages": 0,
            }

        role_counts = {}
        for msg in messages:
            role_counts[msg.role] = role_counts.get(msg.role, 0) + 1

        tool_call_count = sum(1 for m in messages if m.has_tool_calls)
        pinned_count = sum(1 for m in messages if m.is_pinned)
        tagged_count = sum(1 for m in messages if m.tags)

        is_valid, _, incomplete = self.check_tool_chain(session_id)

        return {
            "session_id": session_id,
            "exists": True,
            "total_messages": len(messages),
            "role_counts": role_counts,
            "tool_call_count": tool_call_count,
            "tool_chain_valid": is_valid,
            "pending_tool_calls": len(incomplete),
            "rounds": self._count_rounds(messages),
            "pinned_count": pinned_count,
            "tagged_count": tagged_count,
            "first_message_time": messages[0].timestamp if messages else None,
            "last_message_time": messages[-1].timestamp if messages else None,
        }

    def _count_rounds(self, messages: List[Message]) -> int:
        """计算对话轮数"""
        return sum(1 for m in messages if m.role == "user")

    def delete_session(self, session_id: str) -> bool:
        """删除整个会话"""
        if session_id not in self._cache:
            return False

        del self._cache[session_id]
        self._storage.delete(self._get_storage_key(session_id))

        self._undo_stacks.pop(session_id, None)
        self._redo_stacks.pop(session_id, None)

        if self._auto_save:
            self._storage.save()

        return True

    def copy_session(
            self,
            from_session: str,
            to_session: str,
            overwrite: bool = False
    ) -> bool:
        """复制会话"""
        if from_session not in self._cache:
            return False

        if to_session in self._cache and not overwrite:
            raise ValueError(
                f"Session '{to_session}' already exists. Use overwrite=True to replace."
            )

        self._cache[to_session] = [copy.deepcopy(m) for m in self._cache[from_session]]
        self._save_session(to_session)

        return True

    # =========================================================================
    # 持久化 API
    # =========================================================================

    def save(self):
        """手动保存到存储"""
        for session_id in self._cache:
            self._save_session(session_id)
        self._storage.save()

    def reload(self):
        """从存储重新加载"""
        self._cache.clear()
        self._load_from_storage()

    # =========================================================================
    # 兼容方法 (保留但标记为废弃)
    # =========================================================================

    def build_messages(
            self,
            session_id: str = DEFAULT_SESSION,
            system_prompt: Optional[Union[str, List[str]]] = None,
            user_query: Optional[str] = None,
            max_rounds: Optional[int] = None,
            max_messages: Optional[int] = None,
            include_system: bool = True,
    ) -> List[Dict[str, Any]]:
        """
        [已废弃] 构建发送给 LLM 的消息列表

        推荐使用 build_history() 代替。
        """
        import warnings
        warnings.warn(
            "build_messages() is deprecated. Use build_history() instead.",
            DeprecationWarning,
            stacklevel=2
        )

        result = []

        if system_prompt:
            if isinstance(system_prompt, str):
                result.append({"role": "system", "content": system_prompt})
            else:
                for sp in system_prompt:
                    result.append({"role": "system", "content": sp})

        history = self._get_history_for_build(
            session_id=session_id,
            max_rounds=max_rounds,
            max_messages=max_messages,
            include_system=include_system,
        )

        result.extend(history)

        if user_query:
            result.append({"role": "user", "content": user_query})

        return result

    def _get_history_for_build(
            self,
            session_id: str,
            max_rounds: Optional[int] = None,
            max_messages: Optional[int] = None,
            include_system: bool = True,
    ) -> List[Dict[str, Any]]:
        """获取用于构建的历史消息 (内部方法)"""
        messages = self._cache.get(session_id, [])

        if not include_system:
            messages = [m for m in messages if m.role != "system"]

        if max_rounds:
            messages = self._limit_by_rounds(messages, max_rounds)

        if max_messages and len(messages) > max_messages:
            messages = messages[-max_messages:]

        return [m.to_openai_format() for m in messages]

    # =========================================================================
    # 魔术方法
    # =========================================================================

    def __len__(self) -> int:
        """返回总消息数"""
        return sum(len(msgs) for msgs in self._cache.values())

    def __contains__(self, session_id: str) -> bool:
        """检查会话是否存在"""
        return self.has_session(session_id)

    def __repr__(self) -> str:
        return (
            f"MemoryManager(sessions={len(self._cache)}, "
            f"messages={len(self)}, storage={self._storage_type})"
        )

    def __str__(self) -> str:
        lines = [
            "=" * 50,
            "MemoryManager Status",
            "=" * 50,
            f"Storage: {self._storage_type}",
            f"Sessions: {len(self._cache)}",
            f"Total Messages: {len(self)}",
            "-" * 50,
            ]

        for session_id in self._cache:
            stats = self.get_session_stats(session_id)
            tool_status = (
                "✓" if stats.get('tool_chain_valid', True)
                else f"✗ ({stats.get('pending_tool_calls', 0)} pending)"
            )
            pin_info = f", 📌{stats.get('pinned_count', 0)}" if stats.get('pinned_count') else ""
            lines.append(
                f"  [{session_id}]: {stats['total_messages']} msgs, "
                f"{stats['rounds']} rounds, tools: {tool_status}{pin_info}"
            )

        lines.append("=" * 50)
        return "\n".join(lines)
