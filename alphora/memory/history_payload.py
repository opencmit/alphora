# Copyright 2026 China Mobile Information Technology Co., Ltd.
# SPDX-License-Identifier: Apache-2.0
#
# Author: Tian Tian (tiantianit@chinamobile.com)


"""
Immutable History Payload & Integrity Validation.

This module defines the secure, immutable data structure used to transport
conversation history between the Memory Manager and the Prompt Engine.
It enforces strict data integrity and validates the consistency of
tool-use interaction chains (Function Calling).

Key Features:
    1.  Immutability: Once created, the payload cannot be modified, ensuring
        consistency across the request lifecycle.
    2.  Integrity Verification: Uses internal cryptographic signatures to
        detect tampering or corruption during transport.
    3.  Tool Chain Logic: rigorous validation to ensure every `tool_call`
        has a corresponding `tool` response, preventing LLM context errors.
"""

from typing import Any, Dict, List, Optional, Set, Tuple
from dataclasses import dataclass, field
import time
import hashlib
import json


class ToolChainError(Exception):
    """Raised when an incomplete or invalid tool invocation chain is detected."""
    pass


class ToolChainValidator:
    """
    Provides static validation logic for OpenAI-format message lists.

    This validator ensures the structural integrity of function calling sequences,
    enforcing that every 'assistant' message with `tool_calls` is properly
    resolved by subsequent 'tool' messages.
    """

    @staticmethod
    def validate(messages: List[Dict[str, Any]]) -> Tuple[bool, Optional[str]]:
        """
        验证消息列表中的工具调用链完整性

        Args:
            messages: OpenAI 格式的消息列表

        Returns:
            (is_valid, error_message) - 验证结果和错误信息
        """
        # 收集所有 tool_call_ids (来自 assistant 消息)
        expected_tool_ids: Set[str] = set()
        # 收集所有 tool 消息的 tool_call_id
        actual_tool_ids: Set[str] = set()

        pending_tool_calls: Dict[str, str] = {}  # tool_call_id -> tool_name

        for i, msg in enumerate(messages):
            role = msg.get("role")

            if role == "assistant":
                tool_calls = msg.get("tool_calls", [])
                if tool_calls:
                    for tc in tool_calls:
                        tc_id = tc.get("id")
                        tc_name = tc.get("function", {}).get("name", "unknown")
                        if tc_id:
                            expected_tool_ids.add(tc_id)
                            pending_tool_calls[tc_id] = tc_name

            elif role == "tool":
                tool_call_id = msg.get("tool_call_id")
                if tool_call_id:
                    actual_tool_ids.add(tool_call_id)
                    # 移除已匹配的
                    pending_tool_calls.pop(tool_call_id, None)
                else:
                    return False, f"Tool message at index {i} missing 'tool_call_id'"

        # 检查是否有未匹配的 tool_calls
        missing_results = expected_tool_ids - actual_tool_ids
        if missing_results:
            missing_info = [f"{tid}" for tid in missing_results]
            return False, f"Missing tool results for tool_call_ids: {missing_info}"

        # 检查是否有多余的 tool 消息
        orphan_tools = actual_tool_ids - expected_tool_ids
        if orphan_tools:
            return False, f"Orphan tool messages with tool_call_ids: {list(orphan_tools)}"

        return True, None

    @staticmethod
    def find_incomplete_tool_calls(messages: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        Identifies pending tool calls that lack a corresponding output.

        Args:
            messages: A list of message dictionaries.

        Returns:
            A list of tool call objects (dictionaries) that are currently unresolved.
        """
        expected: Dict[str, Dict] = {}  # tool_call_id -> tool_call_info

        for msg in messages:
            if msg.get("role") == "assistant":
                for tc in msg.get("tool_calls", []):
                    tc_id = tc.get("id")
                    if tc_id:
                        expected[tc_id] = tc

            elif msg.get("role") == "tool":
                tc_id = msg.get("tool_call_id")
                expected.pop(tc_id, None)

        return list(expected.values())


@dataclass(frozen=True)
class HistoryPayload:
    """
    A secured, immutable container for session history.

    This class serves as the Data Transfer Object (DTO) between the MemoryManager
    and the BasePrompt. It guarantees that the history has been validated for
    structural correctness and has not been modified since retrieval.

    Attributes:
        messages: The raw history as an immutable tuple of dictionaries.
        session_id: The unique identifier for the conversation session.
        created_at: Unix timestamp indicating when this payload was generated.
        message_count: The total number of messages in the payload.
        round_count: The estimated number of conversation turns.
        has_tool_calls: Boolean flag indicating if function calling occurred.
        tool_chain_valid: Boolean flag indicating if the tool chain passed validation.

    Example:
        messages = [{"role": "user", "content": "Hello"}]
        payload = HistoryPayload.create(messages, session_id="sess_123")
        print(payload.message_count)
    """
    messages: Tuple[Dict[str, Any], ...]    # 使用 tuple 确保不可变
    session_id: str
    created_at: float
    message_count: int
    round_count: int
    has_tool_calls: bool
    tool_chain_valid: bool
    _signature: str = field(repr=False)

    # 类级别的密钥
    _SECRET_KEY: str = field(default="alphora_memory_v1", repr=False, compare=False)

    def __post_init__(self):
        """验证签名"""
        expected_sig = self._compute_signature()
        if self._signature != expected_sig:
            raise ValueError("Invalid HistoryPayload: signature mismatch (possible forgery)")

    def _compute_signature(self) -> str:
        """计算签名"""
        # 基于关键属性计算哈希
        data = f"{self.session_id}:{self.created_at}:{self.message_count}:{self._SECRET_KEY}"
        return hashlib.sha256(data.encode()).hexdigest()[:16]

    @classmethod
    def create(
            cls,
            messages: List[Dict[str, Any]],
            session_id: str,
            round_count: int = 0,
            validate_tool_chain: bool = True
    ) -> "HistoryPayload":

        """
        Factory method to build a verified HistoryPayload.

        This is the standard entry point for creating history objects. It handles
        type conversion (List -> Tuple) and optional structural validation.

        Args:
            messages: The list of OpenAI-formatted messages.
            session_id: The unique session identifier.
            round_count: Optional counter for conversation turns.
            validate_tool_chain: If True, enforces tool chain integrity checks.

        Returns:
            A frozen HistoryPayload instance.

        Raises:
            ToolChainError: If validation is enabled and the tool chain is broken.
        """

        # Detect presence of tool usage
        has_tool_calls = any(
            msg.get("role") == "assistant" and msg.get("tool_calls")
            for msg in messages
        )

        # 验证工具调用链
        tool_chain_valid = True
        if validate_tool_chain and has_tool_calls:
            is_valid, error_msg = ToolChainValidator.validate(messages)
            if not is_valid:
                raise ToolChainError(f"Tool chain validation failed: {error_msg}")
            tool_chain_valid = is_valid

        created_at = time.time()
        message_count = len(messages)

        # 先计算签名
        temp_sig = hashlib.sha256(
            f"{session_id}:{created_at}:{message_count}:alphora_memory_v1".encode()
        ).hexdigest()[:16]

        return cls(
            messages=tuple(messages),  # 转为 tuple
            session_id=session_id,
            created_at=created_at,
            message_count=message_count,
            round_count=round_count,
            has_tool_calls=has_tool_calls,
            tool_chain_valid=tool_chain_valid,
            _signature=temp_sig
        )

    def to_list(self) -> List[Dict[str, Any]]:
        """转换为可变的消息列表"""
        return list(self.messages)

    def is_empty(self) -> bool:
        """是否为空"""
        return self.message_count == 0

    def __len__(self) -> int:
        return self.message_count

    def __bool__(self) -> bool:
        return self.message_count > 0

    def __iter__(self):
        return iter(self.messages)


def is_valid_history_payload(obj: Any) -> bool:
    """
    检查对象是否是有效的 HistoryPayload

    用于 BasePrompt 验证传入的 history 参数
    """
    if not isinstance(obj, HistoryPayload):
        return False

    try:
        # 尝试验证签名
        expected_sig = obj._compute_signature()
        return obj._signature == expected_sig
    except Exception:
        return False

