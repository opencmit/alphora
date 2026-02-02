"""
消息处理器模块

提供可复用的消息处理器，用于在构建历史时对消息进行过滤、变换等操作。

处理器类型:
    Processor = Callable[[List[Message]], List[Message]]

使用示例:
    from alphora.memory.processors import keep_last, truncate_content, chain

    # 单个处理器
    history = memory.build_history(processor=keep_last(20))

    # 组合多个处理器
    history = memory.build_history(
        processor=chain(
            exclude_roles("system"),
            keep_pinned(),
            keep_last(20),
            truncate_content(2000)
        )
    )

    # 自定义处理器
    history = memory.build_history(
        processor=lambda msgs: [m for m in msgs if len(m.content or "") < 5000]
    )
"""

from typing import (
    Any, Callable, Dict, List, Optional, 
    Set, Tuple, Union, TYPE_CHECKING
)
from dataclasses import dataclass
import json

if TYPE_CHECKING:
    from alphora.memory.message import Message

# 处理器类型定义
Processor = Callable[[List["Message"]], List["Message"]]


# =============================================================================
# 处理器上下文（可选，用于需要额外信息的处理器）
# =============================================================================

@dataclass
class ProcessorContext:
    """
    处理器上下文

    包含处理器可能需要的额外信息。
    """
    session_id: str = "default"
    system_prompt: Optional[str] = None
    user_query: Optional[str] = None
    extra: Dict[str, Any] = None

    def __post_init__(self):
        if self.extra is None:
            self.extra = {}


# =============================================================================
# 工具函数
# =============================================================================

def chain(*processors: Processor) -> Processor:
    """
    组合多个处理器，依次执行

    Args:
        *processors: 要组合的处理器

    Returns:
        组合后的处理器

    Example:
        combined = chain(
            exclude_roles("system"),
            keep_last(20),
            truncate_content(2000)
        )
        result = combined(messages)
    """
    def combined(messages: List["Message"]) -> List["Message"]:
        result = messages
        for proc in processors:
            result = proc(result)
        return result
    return combined


def identity() -> Processor:
    """
    恒等处理器，不做任何处理

    Returns:
        原样返回消息的处理器
    """
    return lambda msgs: msgs


# =============================================================================
# 过滤类处理器
# =============================================================================

def keep_last(n: int) -> Processor:
    """
    保留最后 N 条消息

    Args:
        n: 保留的消息数量

    Returns:
        处理器函数

    Example:
        processor = keep_last(20)
        result = processor(messages)  # 最后 20 条
    """
    def processor(messages: List["Message"]) -> List["Message"]:
        if n <= 0:
            return []
        return messages[-n:] if len(messages) > n else messages
    return processor


def keep_first(n: int) -> Processor:
    """
    保留前 N 条消息

    Args:
        n: 保留的消息数量

    Returns:
        处理器函数
    """
    def processor(messages: List["Message"]) -> List["Message"]:
        if n <= 0:
            return []
        return messages[:n]
    return processor


def keep_rounds(n: int) -> Processor:
    """
    保留最后 N 轮对话

    一轮 = user 消息 + 后续的 assistant/tool 消息

    Args:
        n: 保留的轮数

    Returns:
        处理器函数

    Example:
        processor = keep_rounds(5)
        result = processor(messages)  # 最后 5 轮对话
    """
    def processor(messages: List["Message"]) -> List["Message"]:
        if not messages or n <= 0:
            return []

        # 从后往前扫描，计算轮数
        rounds = 0
        cut_index = 0

        for i in range(len(messages) - 1, -1, -1):
            if messages[i].role == "user":
                rounds += 1
                if rounds > n:
                    cut_index = i + 1
                    break

        return messages[cut_index:]
    return processor


def keep_roles(*roles: str) -> Processor:
    """
    只保留指定角色的消息

    Args:
        *roles: 要保留的角色 ("user", "assistant", "tool", "system")

    Returns:
        处理器函数

    Example:
        processor = keep_roles("user", "assistant")
        result = processor(messages)  # 只有 user 和 assistant
    """
    role_set = set(roles)

    def processor(messages: List["Message"]) -> List["Message"]:
        return [m for m in messages if m.role in role_set]
    return processor


def exclude_roles(*roles: str) -> Processor:
    """
    排除指定角色的消息

    Args:
        *roles: 要排除的角色

    Returns:
        处理器函数

    Example:
        processor = exclude_roles("tool", "system")
        result = processor(messages)
    """
    role_set = set(roles)

    def processor(messages: List["Message"]) -> List["Message"]:
        return [m for m in messages if m.role not in role_set]
    return processor


def keep_pinned() -> Processor:
    """
    只保留被固定(pinned)的消息

    Returns:
        处理器函数

    Example:
        processor = keep_pinned()
        result = processor(messages)  # 只有 pinned 的消息
    """
    def processor(messages: List["Message"]) -> List["Message"]:
        return [m for m in messages if m.is_pinned]
    return processor


def keep_tagged(*tags: str, match_any: bool = True) -> Processor:
    """
    保留带有指定标签的消息

    Args:
        *tags: 要匹配的标签
        match_any: True=匹配任一标签, False=匹配所有标签

    Returns:
        处理器函数

    Example:
        processor = keep_tagged("important", "user_pref")
        result = processor(messages)
    """
    tag_set = set(tags)

    def processor(messages: List["Message"]) -> List["Message"]:
        result = []
        for m in messages:
            msg_tags = set(m.tags)
            if match_any:
                if msg_tags & tag_set:  # 交集非空
                    result.append(m)
            else:
                if tag_set <= msg_tags:  # tags 是子集
                    result.append(m)
        return result
    return processor


def exclude_tagged(*tags: str, match_any: bool = True) -> Processor:
    """
    排除带有指定标签的消息

    Args:
        *tags: 要排除的标签
        match_any: True=匹配任一标签即排除, False=匹配所有标签才排除

    Returns:
        处理器函数
    """
    tag_set = set(tags)

    def processor(messages: List["Message"]) -> List["Message"]:
        result = []
        for m in messages:
            msg_tags = set(m.tags)
            if match_any:
                if not (msg_tags & tag_set):  # 交集为空，保留
                    result.append(m)
            else:
                if not (tag_set <= msg_tags):  # tags 不是子集，保留
                    result.append(m)
        return result
    return processor


def filter_by(predicate: Callable[["Message"], bool]) -> Processor:
    """
    通用过滤器

    Args:
        predicate: 过滤函数，返回 True 保留，False 排除

    Returns:
        处理器函数

    Example:
        processor = filter_by(lambda m: len(m.content or "") < 5000)
        result = processor(messages)
    """
    def processor(messages: List["Message"]) -> List["Message"]:
        return [m for m in messages if predicate(m)]
    return processor


def exclude_by(predicate: Callable[["Message"], bool]) -> Processor:
    """
    通用排除器

    Args:
        predicate: 过滤函数，返回 True 排除，False 保留

    Returns:
        处理器函数
    """
    def processor(messages: List["Message"]) -> List["Message"]:
        return [m for m in messages if not predicate(m)]
    return processor


# =============================================================================
# 组合过滤器（保留重要消息 + 最后 N 条）
# =============================================================================

def keep_important_and_last(
    n: int,
    include_pinned: bool = True,
    include_tags: Optional[List[str]] = None
) -> Processor:
    """
    保留重要消息 + 最后 N 条

    这是一个常用的组合过滤器，确保重要消息不被丢弃。

    Args:
        n: 保留最后 N 条
        include_pinned: 是否保留固定的消息
        include_tags: 保留带有这些标签的消息

    Returns:
        处理器函数

    Example:
        processor = keep_important_and_last(20, include_tags=["user_pref"])
        result = processor(messages)
    """
    include_tags = include_tags or []
    tag_set = set(include_tags)

    def processor(messages: List["Message"]) -> List["Message"]:
        if not messages:
            return []

        # 找出重要消息（保持原始顺序）
        important_indices: Set[int] = set()
        for i, m in enumerate(messages):
            if include_pinned and m.is_pinned:
                important_indices.add(i)
            if tag_set and (set(m.tags) & tag_set):
                important_indices.add(i)

        # 最后 N 条的索引
        last_n_start = max(0, len(messages) - n)
        last_n_indices = set(range(last_n_start, len(messages)))

        # 合并索引并排序
        keep_indices = sorted(important_indices | last_n_indices)

        return [messages[i] for i in keep_indices]
    return processor


# =============================================================================
# 变换类处理器
# =============================================================================

def truncate_content(max_length: int, suffix: str = "...[truncated]") -> Processor:
    """
    截断过长的消息内容

    Args:
        max_length: 最大长度
        suffix: 截断后添加的后缀

    Returns:
        处理器函数

    Example:
        processor = truncate_content(2000)
        result = processor(messages)
    """
    def processor(messages: List["Message"]) -> List["Message"]:
        result = []
        for m in messages:
            content = m.content or ""
            if len(content) > max_length:
                truncated = content[:max_length - len(suffix)] + suffix
                result.append(m.with_content(truncated))
            else:
                result.append(m)
        return result
    return processor


def map_content(fn: Callable[[str], str]) -> Processor:
    """
    对每条消息的内容应用函数

    Args:
        fn: 内容变换函数

    Returns:
        处理器函数

    Example:
        processor = map_content(lambda c: c.lower())
        result = processor(messages)
    """
    def processor(messages: List["Message"]) -> List["Message"]:
        result = []
        for m in messages:
            if m.content:
                result.append(m.with_content(fn(m.content)))
            else:
                result.append(m)
        return result
    return processor


def map_messages(fn: Callable[["Message"], "Message"]) -> Processor:
    """
    对每条消息应用函数

    Args:
        fn: 消息变换函数

    Returns:
        处理器函数

    Example:
        processor = map_messages(lambda m: m.with_metadata(processed=True))
        result = processor(messages)
    """
    def processor(messages: List["Message"]) -> List["Message"]:
        return [fn(m) for m in messages]
    return processor


# =============================================================================
# 工具调用相关处理器
# =============================================================================

def summarize_tool_calls(
    format_fn: Optional[Callable[[List[Dict]], str]] = None
) -> Processor:
    """
    将工具调用序列折叠为摘要

    将 assistant(tool_calls) + tool + tool + ... 序列折叠为一条摘要消息。

    Args:
        format_fn: 自定义格式化函数，接收工具调用列表，返回摘要字符串

    Returns:
        处理器函数

    Example:
        processor = summarize_tool_calls()
        result = processor(messages)
        # [user, assistant(tool_calls), tool, tool, assistant]
        # -> [user, assistant("[Used tools: search, calculator]"), assistant]
    """
    def default_format(tool_calls: List[Dict]) -> str:
        names = [tc.get("name", "unknown") for tc in tool_calls]
        return f"[Used tools: {', '.join(names)}]"

    formatter = format_fn or default_format

    def processor(messages: List["Message"]) -> List["Message"]:
        result = []
        i = 0
        while i < len(messages):
            m = messages[i]
            
            # 检测 assistant 带 tool_calls
            if m.is_assistant and m.has_tool_calls:
                # 收集这一轮的工具调用信息
                tool_info = []
                for tc in m.tool_calls:
                    tool_info.append({
                        "id": tc.id,
                        "name": tc.function.get("name", "unknown"),
                        "arguments": tc.function.get("arguments", "")
                    })
                
                # 跳过后续的 tool 消息
                j = i + 1
                while j < len(messages) and messages[j].role == "tool":
                    j += 1
                
                # 创建摘要消息
                summary = formatter(tool_info)
                summary_msg = m.with_content(summary)
                # 移除 tool_calls，因为已经摘要了
                summary_msg = Message(
                    role="assistant",
                    content=summary,
                    id=m.id,
                    timestamp=m.timestamp,
                    metadata=m.metadata
                )
                result.append(summary_msg)
                
                i = j  # 跳到 tool 消息之后
            else:
                result.append(m)
                i += 1
        
        return result
    return processor


def remove_tool_details() -> Processor:
    """
    移除工具调用的详细信息，只保留结果摘要

    比 summarize_tool_calls 更激进，完全移除 tool 消息。

    Returns:
        处理器函数
    """
    def processor(messages: List["Message"]) -> List["Message"]:
        result = []
        for m in messages:
            # 跳过 tool 消息
            if m.role == "tool":
                continue
            
            # assistant 带 tool_calls 的，替换为摘要
            if m.is_assistant and m.has_tool_calls:
                names = m.get_tool_names()
                summary = f"[Called: {', '.join(names)}]"
                from alphora.memory.message import Message
                result.append(Message(
                    role="assistant",
                    content=summary,
                    id=m.id,
                    timestamp=m.timestamp,
                    metadata=m.metadata
                ))
            else:
                result.append(m)
        
        return result
    return processor


def keep_final_tool_result() -> Processor:
    """
    对于连续的工具调用，只保留最后一个结果

    适用于需要精简但又不想完全丢失工具信息的场景。

    Returns:
        处理器函数
    """
    def processor(messages: List["Message"]) -> List["Message"]:
        result = []
        i = 0
        while i < len(messages):
            m = messages[i]
            
            if m.is_assistant and m.has_tool_calls:
                # 找到这轮工具调用的结束位置
                j = i + 1
                tool_messages = []
                while j < len(messages) and messages[j].role == "tool":
                    tool_messages.append(messages[j])
                    j += 1
                
                # 添加 assistant 消息（保留 tool_calls 信息）
                result.append(m)
                
                # 只添加最后一个 tool 结果
                if tool_messages:
                    result.append(tool_messages[-1])
                
                i = j
            else:
                result.append(m)
                i += 1
        
        return result
    return processor


# =============================================================================
# Token 预算处理器
# =============================================================================

def token_budget(
    max_tokens: int,
    tokenizer: Callable[[str], int],
    reserve_for_response: int = 500,
    priority_fn: Optional[Callable[["Message"], int]] = None
) -> Processor:
    """
    基于 Token 预算过滤消息

    从后往前保留消息，直到达到 token 预算。支持优先级函数。

    Args:
        max_tokens: 最大 token 数
        tokenizer: token 计数函数，接收字符串返回 token 数
        reserve_for_response: 为响应预留的 token 数
        priority_fn: 优先级函数，返回值越大优先级越高（pinned 消息默认最高）

    Returns:
        处理器函数

    Example:
        import tiktoken
        enc = tiktoken.encoding_for_model("gpt-4")
        processor = token_budget(
            max_tokens=8000,
            tokenizer=lambda s: len(enc.encode(s)),
            reserve_for_response=1000
        )
        result = processor(messages)
    """
    budget = max_tokens - reserve_for_response

    def default_priority(m: "Message") -> int:
        if m.is_pinned:
            return 1000
        if m.tags:
            return 100
        return 0

    get_priority = priority_fn or default_priority

    def count_tokens(m: "Message") -> int:
        content = m.content or ""
        if m.tool_calls:
            # 估算 tool_calls 的 token 数
            tc_str = json.dumps([tc.to_dict() for tc in m.tool_calls])
            content += tc_str
        return tokenizer(content)

    def processor(messages: List["Message"]) -> List["Message"]:
        if not messages:
            return []

        # 计算每条消息的 token 数和优先级
        msg_info = [
            (i, m, count_tokens(m), get_priority(m))
            for i, m in enumerate(messages)
        ]

        # 按优先级排序（高优先级先选），同优先级按位置倒序（后面的先选）
        sorted_info = sorted(
            msg_info,
            key=lambda x: (-x[3], -x[0])  # 优先级降序，索引降序
        )

        # 选择消息直到达到预算
        selected_indices: Set[int] = set()
        total_tokens = 0

        for idx, msg, tokens, priority in sorted_info:
            if total_tokens + tokens <= budget:
                selected_indices.add(idx)
                total_tokens += tokens

        # 按原始顺序返回
        return [messages[i] for i in sorted(selected_indices)]
    return processor


# =============================================================================
# 导出
# =============================================================================

__all__ = [
    # 类型
    "Processor",
    "ProcessorContext",
    
    # 工具函数
    "chain",
    "identity",
    
    # 过滤类
    "keep_last",
    "keep_first",
    "keep_rounds",
    "keep_roles",
    "exclude_roles",
    "keep_pinned",
    "keep_tagged",
    "exclude_tagged",
    "filter_by",
    "exclude_by",
    "keep_important_and_last",
    
    # 变换类
    "truncate_content",
    "map_content",
    "map_messages",
    
    # 工具调用相关
    "summarize_tool_calls",
    "remove_tool_details",
    "keep_final_tool_result",
    
    # Token 控制
    "token_budget",
]
