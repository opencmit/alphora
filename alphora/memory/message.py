"""
消息模型

定义标准 OpenAI 消息格式，支持:
- user: 用户消息
- assistant: 助手消息 (可包含 tool_calls)
- tool: 工具执行结果
- system: 系统消息

扩展功能:
- 不可变更新方法 (with_content, with_metadata)
- 标记系统 (pin, tag)
"""

from typing import Any, Dict, List, Optional, Union
from dataclasses import dataclass, field, replace
from enum import Enum
import time
import uuid
import json
import copy


class MessageRole(str, Enum):
    """消息角色枚举"""
    SYSTEM = "system"
    USER = "user"
    ASSISTANT = "assistant"
    TOOL = "tool"


@dataclass
class ToolCall:
    """
    工具调用结构

    对应 OpenAI 的 tool_calls 中的单个调用
    """
    id: str
    type: str = "function"
    function: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "type": self.type,
            "function": self.function
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "ToolCall":
        return cls(
            id=data.get("id", ""),
            type=data.get("type", "function"),
            function=data.get("function", {})
        )

    @classmethod
    def create(
            cls,
            name: str,
            arguments: Union[str, Dict],
            call_id: Optional[str] = None
    ) -> "ToolCall":
        """
        便捷创建工具调用

        Args:
            name: 函数名称
            arguments: 参数 (str 或 dict，dict会自动转为JSON字符串)
            call_id: 调用ID (不传则自动生成)
        """
        if isinstance(arguments, dict):
            arguments = json.dumps(arguments, ensure_ascii=False)

        return cls(
            id=call_id or f"call_{uuid.uuid4().hex[:12]}",
            type="function",
            function={"name": name, "arguments": arguments}
        )


@dataclass
class Message:
    """
    标准消息模型

    完全兼容 OpenAI Chat Completion API 的消息格式。

    Attributes:
        role: 消息角色 (system/user/assistant/tool)
        content: 消息内容 (assistant 的 tool_calls 消息中可为 None)
        tool_calls: 工具调用列表 (仅 assistant 消息)
        tool_call_id: 对应的工具调用ID (仅 tool 消息)
        name: 工具名称 (仅 tool 消息)

        # 元数据 (不会发送给LLM)
        id: 消息唯一ID
        timestamp: 创建时间戳
        metadata: 额外元数据 (包含 _pinned, _tags 等内部字段)

    Example:
        msg = Message.user("你好")
        msg = Message.assistant("你好！", tool_calls=[...])
        msg = Message.tool("call_123", "执行结果")
    """
    role: str
    content: Optional[str] = None

    # Tool calling 相关
    tool_calls: Optional[List[ToolCall]] = None
    tool_call_id: Optional[str] = None
    name: Optional[str] = None  # tool 消息的函数名

    # 元数据
    id: str = field(default_factory=lambda: uuid.uuid4().hex[:16])
    timestamp: float = field(default_factory=time.time)
    metadata: Dict[str, Any] = field(default_factory=dict)

    # 内部元数据键名（避免与用户自定义冲突）
    _PINNED_KEY: str = field(default="_pinned", repr=False, compare=False)
    _TAGS_KEY: str = field(default="_tags", repr=False, compare=False)

    def __post_init__(self):
        """验证消息格式"""
        # 规范化 role
        if isinstance(self.role, MessageRole):
            self.role = self.role.value

        # 验证 tool 消息必须有 tool_call_id
        if self.role == "tool" and not self.tool_call_id:
            raise ValueError("Tool message must have 'tool_call_id'")
        
        # 确保 metadata 是可变的（深拷贝）
        if self.metadata is not None:
            self.metadata = dict(self.metadata)

    # ==================== 不可变更新方法 ====================

    def with_content(self, content: str) -> "Message":
        """
        返回内容更新后的新消息（不可变更新）

        Args:
            content: 新的消息内容

        Returns:
            新的 Message 实例

        Example:
            new_msg = msg.with_content(msg.content[:1000])
        """
        return self._copy_with(content=content)

    def with_metadata(self, **kwargs) -> "Message":
        """
        返回元数据更新后的新消息（不可变更新）

        Args:
            **kwargs: 要更新或添加的元数据

        Returns:
            新的 Message 实例

        Example:
            new_msg = msg.with_metadata(processed=True, source="rag")
        """
        new_metadata = {**self.metadata, **kwargs}
        return self._copy_with(metadata=new_metadata)

    def with_tags(self, *tags: str, replace: bool = False) -> "Message":
        """
        返回添加标签后的新消息

        Args:
            *tags: 要添加的标签
            replace: 是否替换现有标签（默认追加）

        Returns:
            新的 Message 实例

        Example:
            new_msg = msg.with_tags("important", "user_preference")
        """
        if replace:
            new_tags = list(tags)
        else:
            existing = self.tags
            new_tags = list(set(existing + list(tags)))
        
        new_metadata = {**self.metadata, self._TAGS_KEY: new_tags}
        return self._copy_with(metadata=new_metadata)

    def without_tags(self, *tags: str) -> "Message":
        """
        返回移除标签后的新消息

        Args:
            *tags: 要移除的标签

        Returns:
            新的 Message 实例
        """
        existing = self.tags
        new_tags = [t for t in existing if t not in tags]
        new_metadata = {**self.metadata, self._TAGS_KEY: new_tags}
        return self._copy_with(metadata=new_metadata)

    def pinned(self) -> "Message":
        """
        返回标记为固定的新消息

        Returns:
            新的 Message 实例
        """
        new_metadata = {**self.metadata, self._PINNED_KEY: True}
        return self._copy_with(metadata=new_metadata)

    def unpinned(self) -> "Message":
        """
        返回取消固定的新消息

        Returns:
            新的 Message 实例
        """
        new_metadata = {**self.metadata, self._PINNED_KEY: False}
        return self._copy_with(metadata=new_metadata)

    def _copy_with(self, **changes) -> "Message":
        """
        内部方法：创建带有指定更改的副本

        Args:
            **changes: 要更改的字段

        Returns:
            新的 Message 实例
        """
        # 深拷贝 tool_calls
        tool_calls_copy = None
        if self.tool_calls:
            tool_calls_copy = [
                ToolCall(id=tc.id, type=tc.type, function=dict(tc.function))
                for tc in self.tool_calls
            ]

        # 构建新实例的参数
        params = {
            "role": self.role,
            "content": self.content,
            "tool_calls": tool_calls_copy,
            "tool_call_id": self.tool_call_id,
            "name": self.name,
            "id": self.id,  # 保持相同 ID
            "timestamp": self.timestamp,
            "metadata": copy.deepcopy(self.metadata),
        }
        params.update(changes)

        return Message(**params)

    # ==================== 标记属性 ====================

    @property
    def is_pinned(self) -> bool:
        """是否被固定"""
        return self.metadata.get(self._PINNED_KEY, False)

    @property
    def tags(self) -> List[str]:
        """获取标签列表"""
        return self.metadata.get(self._TAGS_KEY, [])

    def has_tag(self, tag: str) -> bool:
        """检查是否有指定标签"""
        return tag in self.tags

    # ==================== OpenAI 格式转换 ====================

    def to_openai_format(self) -> Dict[str, Any]:
        """
        转换为 OpenAI API 格式

        只包含发送给 LLM 需要的字段，不包含元数据。
        """
        msg = {"role": self.role}

        # content 处理
        if self.content is not None:
            msg["content"] = self.content
        elif self.role == "assistant" and self.tool_calls:
            # assistant 调用工具时 content 可以为 None
            msg["content"] = None

        # tool_calls (assistant)
        if self.tool_calls:
            msg["tool_calls"] = [tc.to_dict() for tc in self.tool_calls]

        # tool 消息特有字段
        if self.role == "tool":
            msg["tool_call_id"] = self.tool_call_id
            if self.name:
                msg["name"] = self.name

        return msg

    def to_dict(self) -> Dict[str, Any]:
        """
        转换为完整字典 (用于持久化存储)
        """
        data = {
            "role": self.role,
            "content": self.content,
            "id": self.id,
            "timestamp": self.timestamp,
            "metadata": self.metadata,
        }

        if self.tool_calls:
            data["tool_calls"] = [tc.to_dict() for tc in self.tool_calls]

        if self.tool_call_id:
            data["tool_call_id"] = self.tool_call_id

        if self.name:
            data["name"] = self.name

        return data

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "Message":
        """从字典创建 (用于从存储加载)"""
        tool_calls = None
        if "tool_calls" in data and data["tool_calls"]:
            tool_calls = [ToolCall.from_dict(tc) for tc in data["tool_calls"]]

        return cls(
            role=data["role"],
            content=data.get("content"),
            tool_calls=tool_calls,
            tool_call_id=data.get("tool_call_id"),
            name=data.get("name"),
            id=data.get("id", uuid.uuid4().hex[:16]),
            timestamp=data.get("timestamp", time.time()),
            metadata=data.get("metadata", {}),
        )

    @classmethod
    def from_openai_format(cls, data: Dict[str, Any]) -> "Message":
        """
        从 OpenAI API 响应格式创建

        便于直接将 LLM 响应转为 Message
        """
        tool_calls = None
        if "tool_calls" in data and data["tool_calls"]:
            tool_calls = [ToolCall.from_dict(tc) for tc in data["tool_calls"]]

        return cls(
            role=data["role"],
            content=data.get("content"),
            tool_calls=tool_calls,
            tool_call_id=data.get("tool_call_id"),
            name=data.get("name"),
        )

    # ==================== 工厂方法 ====================

    @classmethod
    def user(cls, content: str, **metadata) -> "Message":
        """创建用户消息"""
        return cls(role="user", content=content, metadata=metadata)

    @classmethod
    def assistant(
            cls,
            content: Optional[str] = None,
            tool_calls: Optional[List[Union[ToolCall, Dict]]] = None,
            **metadata
    ) -> "Message":
        """
        创建助手消息

        Args:
            content: 回复内容
            tool_calls: 工具调用列表 (可以是 ToolCall 对象或 dict)
        """
        # 规范化 tool_calls
        if tool_calls:
            normalized = []
            for tc in tool_calls:
                if isinstance(tc, dict):
                    normalized.append(ToolCall.from_dict(tc))
                else:
                    normalized.append(tc)
            tool_calls = normalized

        return cls(
            role="assistant",
            content=content,
            tool_calls=tool_calls,
            metadata=metadata
        )

    @classmethod
    def tool(
            cls,
            tool_call_id: str,
            content: str,
            name: Optional[str] = None,
            **metadata
    ) -> "Message":
        """
        创建工具结果消息

        Args:
            tool_call_id: 对应的工具调用ID
            content: 工具执行结果
            name: 工具名称 (可选)
        """
        return cls(
            role="tool",
            content=content,
            tool_call_id=tool_call_id,
            name=name,
            metadata=metadata
        )

    @classmethod
    def system(cls, content: str, **metadata) -> "Message":
        """创建系统消息"""
        return cls(role="system", content=content, metadata=metadata)

    # ==================== 属性方法 ====================

    @property
    def is_user(self) -> bool:
        return self.role == "user"

    @property
    def is_assistant(self) -> bool:
        return self.role == "assistant"

    @property
    def is_tool(self) -> bool:
        return self.role == "tool"

    @property
    def is_system(self) -> bool:
        return self.role == "system"

    @property
    def has_tool_calls(self) -> bool:
        """是否包含工具调用"""
        return bool(self.tool_calls)

    @property
    def is_tool_call_request(self) -> bool:
        """是否是工具调用请求 (assistant 消息带 tool_calls)"""
        return self.is_assistant and self.has_tool_calls

    def get_tool_call_ids(self) -> List[str]:
        """获取所有工具调用ID"""
        if not self.tool_calls:
            return []
        return [tc.id for tc in self.tool_calls]

    def get_tool_names(self) -> List[str]:
        """获取所有调用的工具名称"""
        if not self.tool_calls:
            return []
        return [tc.function.get("name", "") for tc in self.tool_calls]

    @property
    def display_content(self) -> str:
        """用于显示的内容"""
        if self.content:
            return self.content
        if self.tool_calls:
            names = self.get_tool_names()
            return f"[调用工具: {', '.join(names)}]"
        return ""

    def formatted_timestamp(self, fmt: str = "%Y-%m-%d %H:%M:%S") -> str:
        """格式化时间戳"""
        return time.strftime(fmt, time.localtime(self.timestamp))

    # ==================== 魔术方法 ====================

    def __repr__(self) -> str:
        content_preview = (
            (self.display_content[:30] + "...") 
            if len(self.display_content) > 30 
            else self.display_content
        )
        extras = []
        if self.is_pinned:
            extras.append("pinned")
        if self.tags:
            extras.append(f"tags={self.tags}")
        extra_str = f", {', '.join(extras)}" if extras else ""
        return f"Message(role={self.role}, content={content_preview!r}{extra_str})"

    def __str__(self) -> str:
        prefix = ""
        if self.is_pinned:
            prefix = "📌 "
        return f"{prefix}[{self.role}]: {self.display_content}"
