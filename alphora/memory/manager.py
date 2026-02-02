"""
记忆管理器

统一的对话历史管理入口，提供简洁、开发者友好的API

特性:
- 标准 OpenAI 消息格式
- 完整工具调用链路支持（带验证）
- 多会话管理
- 历史压缩与清理
- 撤销/重做支持
- 多种存储后端
"""

from typing import Any, Dict, List, Optional, Union, Literal, Callable, Tuple, Set
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

logger = logging.getLogger(__name__)


class MemoryManager:
    """
    记忆管理器

    管理对话历史，支持多会话、工具调用、历史压缩等功能。

    - 需要开发者手动调用 add_* 方法
    - 使用 build_history() 获取 HistoryPayload，传入 BasePrompt
    - 工具调用链会自动验证完整性

    基本用法:
    ```python
    # 创建管理器
    memory = MemoryManager()

    # 手动添加对话
    memory.add_user("你好")
    memory.add_assistant("你好！有什么可以帮你的？")

    # 获取历史用于 LLM 调用
    history = memory.build_history(max_rounds=5)

    # 传入 BasePrompt
    response = await prompt.acall(query="新问题", history=history)

    # 手动保存响应
    memory.add_user("新问题")
    memory.add_assistant(response)
    ```

    工具调用 (手动管理):
    ```python
    # 1. 用户输入
    memory.add_user("北京天气怎么样？")

    # 2. 调用 LLM
    history = memory.build_history()
    response = await prompt.acall(query=None, history=history, tools=tools)

    # 3. 智能记录 assistant
    memory.add_assistant(response)

    # 4. 如果有工具调用，执行并记录
    if getattr(response, 'has_tool_calls', False):
        results = await executor.execute(response)
        memory.add_tool_result(results)  # 一行搞定！

        # 5. 继续对话获取最终回复
        history = memory.build_history()
        final_response = await prompt.acall(query=None, history=history)
        memory.add_assistant(final_response)
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

    # ==================== 添加消息 API ====================

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
            memory.add_assistant(response)  # 自动判断类型

            # 方式 2: 普通文本回复
            memory.add_assistant("你好！有什么可以帮你的？")

            # 方式 3: 显式工具调用
            memory.add_assistant(tool_calls=[
                {"id": "call_1", "type": "function", "function": {"name": "search", "arguments": '{"q": "天气"}'}}
            ])
        """
        actual_content = content
        actual_tool_calls = tool_calls

        # 智能识别 ToolCall 对象 (继承自 list，有 tool_calls 属性)
        # 检查方式: 是 list 且有 content 属性 (ToolCall 的特征)
        if isinstance(content, list) and hasattr(content, 'content'):
            tc_obj = content
            if len(tc_obj) > 0:
                # 有工具调用
                actual_tool_calls = list(tc_obj)  # ToolCall 本身就是列表
                actual_content = tc_obj.content
            else:
                # 没有工具调用，使用 content 属性
                actual_content = tc_obj.content or str(tc_obj) if tc_obj.content else None
                actual_tool_calls = None
        elif content is not None and not isinstance(content, str):
            # 其他非字符串类型 (如 PrompterOutput)，转为字符串
            actual_content = str(content)

        msg = Message.assistant(actual_content, actual_tool_calls, **metadata)
        return self._add_message(msg, session_id)

    def add_tool_result(
            self,
            result: Optional[Union["ToolExecutionResult", List["ToolExecutionResult"], Any]] = None,
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

            # 方式 2: 传入单个结果
            result = await executor.execute_single(tool_call)
            memory.add_tool_result(result)

            # 方式 3: 传统方式
            memory.add_tool_result(
                tool_call_id="call_123",
                name="get_weather",
                content={"city": "北京", "weather": "晴"}
            )
        """
        # 方式 1: 传入 ToolExecutionResult 列表
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
        # 验证 tool_call_id 是否存在
        if not self._validate_tool_call_id(session_id, tool_call_id):
            logger.warning(
                f"tool_call_id '{tool_call_id}' not found in session '{session_id}'. "
                "This may cause tool chain validation to fail."
            )

        # 自动序列化非字符串内容
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

        Example:
            memory.add_system("你是一个友好的助手。")
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

        Example:
            # 从 LLM 响应直接添加
            memory.add_message(response.choices[0].message.model_dump())
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

    # ==================== 获取消息 API ====================

    def get_messages(
            self,
            session_id: str = DEFAULT_SESSION,
            limit: Optional[int] = None,
            offset: int = 0,
            role: Optional[str] = None
    ) -> List[Message]:
        """
        获取消息列表

        Args:
            session_id: 会话ID
            limit: 返回数量限制
            offset: 偏移量 (从末尾算起)
            role: 筛选角色 (user/assistant/tool/system)

        Returns:
            Message 列表

        Example:
            # 获取所有消息
            messages = memory.get_messages()

            # 获取最后5条
            messages = memory.get_messages(limit=5)

            # 只获取用户消息
            messages = memory.get_messages(role="user")
        """
        messages = self._cache.get(session_id, [])

        # 角色过滤
        if role:
            messages = [m for m in messages if m.role == role]

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

    # ==================== 构建历史 API ====================

    def build_history(
            self,
            session_id: str = DEFAULT_SESSION,
            max_rounds: Optional[int] = None,
            max_messages: Optional[int] = None,
            include_system: bool = False,
            validate_tool_chain: bool = True,
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

        Returns:
            HistoryPayload 对象

        Raises:
            ToolChainError: 如果工具调用链不完整

        Example:
            # 获取最近 5 轮对话
            history = memory.build_history(max_rounds=5)

            # 传入 BasePrompt
            response = await prompt.acall(query="你好", history=history)
        """
        messages = self._cache.get(session_id, [])

        # 过滤 system 消息 (如果不需要)
        if not include_system:
            messages = [m for m in messages if m.role != "system"]

        # 按轮数限制
        if max_rounds:
            messages = self._limit_by_rounds(messages, max_rounds)

        # 按消息数限制
        if max_messages and len(messages) > max_messages:
            messages = messages[-max_messages:]

        # 转换为 OpenAI 格式
        openai_messages = [m.to_openai_format() for m in messages]

        # 计算轮数
        round_count = sum(1 for m in messages if m.role == "user")

        # 创建 HistoryPayload (内部会验证工具链)
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
    ) -> HistoryPayload:
        """
        构建历史记录载荷 (不验证工具链)

        警告: 仅在你确定工具链是不完整的情况下使用（例如工具调用进行中）

        Args:
            session_id: 会话ID
            max_rounds: 最大对话轮数
            max_messages: 最大消息数
            include_system: 是否包含历史中的 system 消息

        Returns:
            HistoryPayload 对象 (tool_chain_valid 可能为 False)
        """
        return self.build_history(
            session_id=session_id,
            max_rounds=max_rounds,
            max_messages=max_messages,
            include_system=include_system,
            validate_tool_chain=False
        )

    def check_tool_chain(
            self,
            session_id: str = DEFAULT_SESSION
    ) -> Tuple[bool, Optional[str], List[Dict]]:
        """
        检查工具调用链完整性

        Returns:
            (is_valid, error_message, incomplete_calls)
            - is_valid: 是否完整
            - error_message: 错误信息 (如果有)
            - incomplete_calls: 未完成的工具调用列表

        Example:
            is_valid, error, incomplete = memory.check_tool_chain()
            if not is_valid:
                print(f"工具链不完整: {error}")
                for tc in incomplete:
                    print(f"  缺少结果: {tc['function']['name']}")
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
        获取所有待处理的工具调用（有 tool_call 但没有对应 tool 结果）

        Returns:
            待处理的 tool_call 列表

        Example:
            pending = memory.get_pending_tool_calls()
            for tc in pending:
                result = await execute_tool(tc)
                memory.add_tool_result(tc["id"], tc["function"]["name"], result)
        """
        messages = [m.to_openai_format() for m in self._cache.get(session_id, [])]
        return ToolChainValidator.find_incomplete_tool_calls(messages)

    # ==================== 兼容方法 (保留但标记为废弃) ====================

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

        推荐使用 build_history() 代替，然后传入 BasePrompt。

        此方法保留是为了向后兼容。
        """
        import warnings
        warnings.warn(
            "build_messages() is deprecated. Use build_history() instead.",
            DeprecationWarning,
            stacklevel=2
        )

        result = []

        # 1. 添加 system_prompt
        if system_prompt:
            if isinstance(system_prompt, str):
                result.append({"role": "system", "content": system_prompt})
            else:
                for sp in system_prompt:
                    result.append({"role": "system", "content": sp})

        # 2. 获取历史消息
        history = self._get_history_for_build(
            session_id=session_id,
            max_rounds=max_rounds,
            max_messages=max_messages,
            include_system=include_system,
        )

        result.extend(history)

        # 3. 添加当前 user_query
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

        # 过滤 system 消息 (如果不需要)
        if not include_system:
            messages = [m for m in messages if m.role != "system"]

        # 按轮数限制
        if max_rounds:
            messages = self._limit_by_rounds(messages, max_rounds)

        # 按消息数限制
        if max_messages and len(messages) > max_messages:
            messages = messages[-max_messages:]

        return [m.to_openai_format() for m in messages]

    def _limit_by_rounds(self, messages: List[Message], max_rounds: int) -> List[Message]:
        """
        按对话轮数限制消息

        一轮 = user + assistant (+ 可能的 tool_calls + tool)
        从后往前数 max_rounds 轮
        """
        if not messages:
            return []

        # 从后往前扫描，计算轮数
        rounds = 0
        cut_index = 0

        i = len(messages) - 1
        while i >= 0:
            msg = messages[i]

            # user 消息标志一轮的开始
            if msg.role == "user":
                rounds += 1
                if rounds > max_rounds:
                    cut_index = i + 1
                    break

            i -= 1

        return messages[cut_index:]

    # ==================== 删除/清理 API ====================

    def delete_message(
            self,
            message_id: str,
            session_id: str = DEFAULT_SESSION
    ) -> bool:
        """
        删除指定消息

        Args:
            message_id: 消息ID
            session_id: 会话ID

        Returns:
            是否删除成功
        """
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
        """
        删除最后 N 条消息

        Args:
            count: 删除数量
            session_id: 会话ID

        Returns:
            实际删除的数量
        """
        if session_id not in self._cache:
            return 0

        self._save_undo_state(session_id)

        original_len = len(self._cache[session_id])
        self._cache[session_id] = self._cache[session_id][:-count] if count < original_len else []

        deleted = original_len - len(self._cache[session_id])
        if deleted > 0:
            self._save_session(session_id)
        return deleted

    def delete_last_round(self, session_id: str = DEFAULT_SESSION) -> int:
        """
        删除最后一轮对话

        一轮 = 最后一个 user 消息及其后的所有消息

        Returns:
            删除的消息数量

        Example:
            # 如果历史是: [user, assistant, user, assistant(tool_calls), tool, assistant]
            # 调用后变为: [user, assistant]
        """
        messages = self._cache.get(session_id, [])
        if not messages:
            return 0

        self._save_undo_state(session_id)

        # 从后往前找最后一个 user 消息
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

        Returns:
            删除的消息数量

        Example:
            # 如果历史是: [user, assistant(tool_calls), tool, tool, assistant]
            # 调用后变为: [user]
        """
        messages = self._cache.get(session_id, [])
        if not messages:
            return 0

        self._save_undo_state(session_id)

        # 从后往前找 assistant 带 tool_calls 的消息
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
        """
        清空指定会话

        Args:
            session_id: 会话ID

        Returns:
            清空的消息数量
        """
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
            summarizer: Optional[Callable[[List[Message]], str]] = None
    ) -> int:
        """
        压缩历史记录

        Args:
            session_id: 会话ID
            keep_last: 保留最后 N 条消息
            keep_rounds: 保留最后 N 轮对话
            summarizer: 自定义摘要函数 (接收 Message 列表，返回摘要字符串)

        Returns:
            压缩掉的消息数量
        """
        messages = self._cache.get(session_id, [])
        if not messages:
            return 0

        self._save_undo_state(session_id)

        original_len = len(messages)

        if keep_rounds:
            messages = self._limit_by_rounds(messages, keep_rounds)
        elif keep_last:
            messages = messages[-keep_last:] if keep_last < len(messages) else messages

        # 如果提供了 summarizer，将被删除的消息生成摘要
        if summarizer and len(messages) < original_len:
            removed = self._cache[session_id][:-len(messages)] if messages else self._cache[session_id]
            summary = summarizer(removed)
            # 将摘要作为 system 消息添加到开头
            summary_msg = Message.system(f"[历史摘要] {summary}")
            messages = [summary_msg] + messages

        self._cache[session_id] = messages
        self._save_session(session_id)

        return original_len - len(messages)

    # ==================== 撤销/重做 API ====================

    def undo(self, session_id: str = DEFAULT_SESSION) -> bool:
        """
        撤销上一次操作

        Returns:
            是否撤销成功
        """
        if not self._enable_undo:
            return False

        if not self._undo_stacks.get(session_id):
            return False

        # 保存当前状态到重做栈
        current = [copy.deepcopy(m) for m in self._cache.get(session_id, [])]
        self._redo_stacks.setdefault(session_id, []).append(current)

        # 恢复上一个状态
        self._cache[session_id] = self._undo_stacks[session_id].pop()
        self._save_session(session_id)

        return True

    def redo(self, session_id: str = DEFAULT_SESSION) -> bool:
        """
        重做上一次撤销的操作

        Returns:
            是否重做成功
        """
        if not self._enable_undo:
            return False

        if not self._redo_stacks.get(session_id):
            return False

        # 保存当前状态到撤销栈
        current = [copy.deepcopy(m) for m in self._cache.get(session_id, [])]
        self._undo_stacks.setdefault(session_id, []).append(current)

        # 恢复重做状态
        self._cache[session_id] = self._redo_stacks[session_id].pop()
        self._save_session(session_id)

        return True

    def can_undo(self, session_id: str = DEFAULT_SESSION) -> bool:
        """是否可以撤销"""
        return bool(self._undo_stacks.get(session_id))

    def can_redo(self, session_id: str = DEFAULT_SESSION) -> bool:
        """是否可以重做"""
        return bool(self._redo_stacks.get(session_id))

    # ==================== 会话管理 API ====================

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

        # 检查工具链完整性
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

        # 清理撤销栈
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
            raise ValueError(f"Session '{to_session}' already exists. Use overwrite=True to replace.")

        # 深拷贝消息
        self._cache[to_session] = [copy.deepcopy(m) for m in self._cache[from_session]]
        self._save_session(to_session)

        return True

    # ==================== 持久化 API ====================

    def save(self):
        """手动保存到存储"""
        for session_id in self._cache:
            self._save_session(session_id)
        self._storage.save()

    def reload(self):
        """从存储重新加载"""
        self._cache.clear()
        self._load_from_storage()

    def __len__(self) -> int:
        """返回总消息数"""
        return sum(len(msgs) for msgs in self._cache.values())

    def __contains__(self, session_id: str) -> bool:
        """检查会话是否存在"""
        return self.has_session(session_id)

    def __repr__(self) -> str:
        return f"MemoryManager(sessions={len(self._cache)}, messages={len(self)}, storage={self._storage_type})"

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
            tool_status = "✓" if stats.get('tool_chain_valid', True) else f"✗ ({stats.get('pending_tool_calls', 0)} pending)"
            lines.append(
                f"  [{session_id}]: {stats['total_messages']} messages, "
                f"{stats['rounds']} rounds, tools: {tool_status}"
            )

        lines.append("=" * 50)
        return "\n".join(lines)