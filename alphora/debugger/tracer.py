"""
Alphora Debugger - Enhanced Tracer

改进功能：
1. 会话(Session)管理 - 区分每次对话
2. 完整的流式输出追踪 - 记录每个chunk和最终输出
3. Prompter追踪 - 记录每个Prompter的完整输入输出
4. 调用链追踪 - 支持嵌套的Agent调用
5. 性能分析 - Token统计、响应时间分析

用法：
    agent = BaseAgent(llm=llm, debugger=True)
    # 访问 http://localhost:9527/
"""

import os
import time
import threading
import json
import copy
from uuid import uuid4
from enum import Enum
from typing import Dict, List, Any, Optional, Union
from dataclasses import dataclass, field, asdict
from contextlib import contextmanager
import traceback


class EventType(str, Enum):
    """事件类型枚举"""
    # Session 生命周期
    SESSION_START = "session_start"
    SESSION_END = "session_end"

    # Agent 生命周期
    AGENT_CREATED = "agent_created"
    AGENT_DERIVED = "agent_derived"
    AGENT_DESTROYED = "agent_destroyed"

    # LLM 调用
    LLM_CALL_START = "llm_call_start"
    LLM_CALL_END = "llm_call_end"
    LLM_CALL_ERROR = "llm_call_error"

    # 流式输出
    LLM_STREAM_START = "llm_stream_start"
    LLM_STREAM_CHUNK = "llm_stream_chunk"
    LLM_STREAM_END = "llm_stream_end"

    # Prompt 相关
    PROMPT_CREATED = "prompt_created"
    PROMPT_RENDER = "prompt_render"
    PROMPT_CALL_START = "prompt_call_start"
    PROMPT_CALL_END = "prompt_call_end"

    # 记忆操作
    MEMORY_ADD = "memory_add"
    MEMORY_RETRIEVE = "memory_retrieve"
    MEMORY_SEARCH = "memory_search"
    MEMORY_CLEAR = "memory_clear"

    # 工具调用
    TOOL_CALL_START = "tool_call_start"
    TOOL_CALL_END = "tool_call_end"
    TOOL_CALL_ERROR = "tool_call_error"

    # 后处理
    POSTPROCESS_START = "postprocess_start"
    POSTPROCESS_END = "postprocess_end"

    # 自定义
    CUSTOM = "custom"
    ERROR = "error"


@dataclass
class DebugEvent:
    """调试事件"""
    event_id: str
    event_type: EventType
    timestamp: float
    agent_id: Optional[str] = None
    session_id: Optional[str] = None  # 会话ID
    trace_id: Optional[str] = None  # 调用链ID
    parent_event_id: Optional[str] = None  # 父事件ID
    data: Dict[str, Any] = field(default_factory=dict)
    duration_ms: Optional[float] = None
    seq: int = 0  # 序列号

    def to_dict(self) -> dict:
        return {
            "event_id": self.event_id,
            "event_type": self.event_type.value if isinstance(self.event_type, EventType) else self.event_type,
            "timestamp": self.timestamp,
            "agent_id": self.agent_id,
            "session_id": self.session_id,
            "trace_id": self.trace_id,
            "parent_event_id": self.parent_event_id,
            "data": self.data,
            "duration_ms": self.duration_ms,
            "seq": self.seq
        }


@dataclass
class SessionInfo:
    """会话信息"""
    session_id: str
    start_time: float
    end_time: Optional[float] = None
    root_agent_id: Optional[str] = None
    query: str = ""  # 用户原始查询
    status: str = "running"  # running, completed, error
    event_count: int = 0
    llm_call_count: int = 0
    total_tokens: int = 0
    total_duration_ms: float = 0
    error: Optional[str] = None
    agents: List[str] = field(default_factory=list)  # 参与的agent_ids

    def to_dict(self) -> dict:
        return {
            "session_id": self.session_id,
            "start_time": self.start_time,
            "end_time": self.end_time,
            "root_agent_id": self.root_agent_id,
            "query": self.query[:200] if self.query else "",
            "status": self.status,
            "event_count": self.event_count,
            "llm_call_count": self.llm_call_count,
            "total_tokens": self.total_tokens,
            "total_duration_ms": self.total_duration_ms,
            "error": self.error,
            "agents": self.agents
        }


@dataclass
class AgentInfo:
    """Agent信息"""
    agent_id: str
    agent_type: str
    created_at: float
    session_id: Optional[str] = None
    parent_id: Optional[str] = None
    config: Dict[str, Any] = field(default_factory=dict)
    llm_info: Dict[str, Any] = field(default_factory=dict)
    children_ids: List[str] = field(default_factory=list)
    prompt_ids: List[str] = field(default_factory=list)  # 关联的prompts
    status: str = "active"  # active, idle, destroyed
    llm_call_count: int = 0
    total_tokens: int = 0

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class PromptInfo:
    """Prompt信息"""
    prompt_id: str
    agent_id: str
    created_at: float
    session_id: Optional[str] = None
    system_prompt: Optional[str] = None
    template: Optional[str] = None
    placeholders: List[str] = field(default_factory=list)
    rendered_prompt: Optional[str] = None
    enable_memory: bool = False
    memory_id: Optional[str] = None
    call_count: int = 0

    def to_dict(self) -> dict:
        # 安全转换为字符串，避免Template对象等非字符串类型
        def safe_str(val):
            if val is None:
                return None
            if isinstance(val, str):
                return val
            return str(val)

        def safe_preview(val, max_len=200):
            s = safe_str(val)
            if s and len(s) > max_len:
                return s[:max_len] + "..."
            return s

        return {
            "prompt_id": self.prompt_id,
            "agent_id": self.agent_id,
            "session_id": self.session_id,
            "created_at": self.created_at,
            "system_prompt_preview": safe_preview(self.system_prompt),
            "template_preview": safe_preview(self.template),
            "placeholders": self.placeholders,
            "rendered_preview": safe_preview(self.rendered_prompt),
            "enable_memory": self.enable_memory,
            "memory_id": self.memory_id,
            "call_count": self.call_count
        }


@dataclass
class LLMCallInfo:
    """LLM调用详细信息"""
    call_id: str
    agent_id: str
    prompt_id: Optional[str] = None
    session_id: Optional[str] = None
    trace_id: Optional[str] = None
    model_name: str = ""
    start_time: float = 0.0
    end_time: Optional[float] = None

    # 请求信息
    request_messages: List[Dict] = field(default_factory=list)
    request_params: Dict[str, Any] = field(default_factory=dict)
    system_prompt: Optional[str] = None

    # 响应信息
    response_text: str = ""
    reasoning_text: str = ""
    finish_reason: Optional[str] = None

    # Token统计
    prompt_tokens: int = 0
    completion_tokens: int = 0
    total_tokens: int = 0

    # 流式输出
    is_streaming: bool = False
    stream_chunks: List[Dict] = field(default_factory=list)
    chunk_count: int = 0
    first_token_time: Optional[float] = None
    stream_content_by_type: Dict[str, str] = field(default_factory=dict)  # 按类型聚合的内容

    # 错误信息
    error: Optional[str] = None
    error_traceback: Optional[str] = None

    @property
    def duration_ms(self) -> float:
        if self.end_time:
            return (self.end_time - self.start_time) * 1000
        return 0

    @property
    def time_to_first_token_ms(self) -> Optional[float]:
        if self.first_token_time and self.start_time:
            return (self.first_token_time - self.start_time) * 1000
        return None

    @property
    def tokens_per_second(self) -> float:
        if self.duration_ms > 0 and self.completion_tokens > 0:
            return self.completion_tokens / (self.duration_ms / 1000)
        return 0

    def to_dict(self) -> dict:
        d = asdict(self)
        d['duration_ms'] = self.duration_ms
        d['time_to_first_token_ms'] = self.time_to_first_token_ms
        d['tokens_per_second'] = round(self.tokens_per_second, 2)
        return d

    def to_summary(self) -> dict:
        """返回摘要信息（用于列表展示）"""
        return {
            "call_id": self.call_id,
            "agent_id": self.agent_id,
            "prompt_id": self.prompt_id,
            "session_id": self.session_id,
            "model_name": self.model_name,
            "is_streaming": self.is_streaming,
            "duration_ms": self.duration_ms,
            "total_tokens": self.total_tokens,
            "prompt_tokens": self.prompt_tokens,
            "completion_tokens": self.completion_tokens,
            "tokens_per_second": round(self.tokens_per_second, 2),
            "time_to_first_token_ms": self.time_to_first_token_ms,
            "input_preview": self._get_input_preview(),
            "output_preview": self._get_output_preview(),
            "has_error": self.error is not None,
            "finish_reason": self.finish_reason,
            "chunk_count": self.chunk_count,
            "start_time": self.start_time
        }

    def _get_input_preview(self) -> str:
        if self.request_messages:
            last_msg = self.request_messages[-1]
            content = last_msg.get('content', '')
            # 安全转换为字符串
            if not isinstance(content, str):
                content = str(content) if content else ''
            if len(content) > 100:
                return content[:100] + "..."
            return content
        return ""

    def _get_output_preview(self) -> str:
        text = self.response_text
        # 安全转换为字符串
        if not isinstance(text, str):
            text = str(text) if text else ''
        if len(text) > 100:
            return text[:100] + "..."
        return text


@dataclass
class TraceContext:
    """调用链上下文"""
    trace_id: str
    session_id: Optional[str] = None
    start_time: float = 0.0
    agent_id: str = ""
    events: List[str] = field(default_factory=list)
    llm_calls: List[str] = field(default_factory=list)
    tool_calls: List[str] = field(default_factory=list)
    total_tokens: int = 0
    total_duration_ms: float = 0
    status: str = "running"

    def to_dict(self) -> dict:
        return asdict(self)


class DebugTracer:
    """
    调试追踪器（增强版）

    新增功能：
    - 会话(Session)管理，区分每次对话
    - 完整的流式输出追踪
    - Prompter追踪
    - 改进的统计和分析
    """

    _instance = None
    _lock = threading.Lock()

    def __new__(cls):
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
                    cls._instance._initialized = False
        return cls._instance

    def __init__(self):
        if self._initialized:
            return
        self._initialized = True

        self._enabled = False
        self._server_started = False
        self._server_port = 9527

        # 数据存储
        self._events: List[DebugEvent] = []
        self._sessions: Dict[str, SessionInfo] = {}
        self._agents: Dict[str, AgentInfo] = {}
        self._prompts: Dict[str, PromptInfo] = {}
        self._llm_calls: Dict[str, LLMCallInfo] = {}
        self._traces: Dict[str, TraceContext] = {}
        self._active_streams: Dict[str, Dict] = {}

        # 统计
        self._stats = {
            'total_events': 0,
            'total_sessions': 0,
            'active_sessions': 0,
            'total_llm_calls': 0,
            'total_tokens': 0,
            'prompt_tokens': 0,
            'completion_tokens': 0,
            'total_duration_ms': 0.0,
            'errors': 0,
            'active_streams': 0,
            'avg_tokens_per_second': 0.0,
            'avg_time_to_first_token_ms': 0.0
        }

        self._max_events = 10000
        self._max_stream_chunks = 200
        self._data_lock = threading.RLock()
        self._event_seq = 0

        # 当前上下文（线程本地）
        self._local = threading.local()

    # ==================== 控制方法 ====================

    def enable(self, start_server: bool = True, port: int = 9527):
        """启用调试"""
        if self._enabled and self._server_started:
            return

        self._enabled = True
        self._server_port = port

        if start_server and not self._server_started:
            self._start_server(port)

    def disable(self):
        """禁用调试"""
        self._enabled = False

    @property
    def enabled(self) -> bool:
        return self._enabled

    @property
    def server_url(self) -> str:
        return f"http://localhost:{self._server_port}/"

    @property
    def event_seq(self) -> int:
        return self._event_seq

    def _start_server(self, port: int):
        """启动调试服务器"""
        try:
            from .server import start_server_background
            start_server_background(port)
            self._server_started = True
        except ImportError:
            import logging
            logging.warning("[Debugger] 需要安装: pip install fastapi uvicorn")
        except Exception as e:
            import logging
            logging.warning(f"[Debugger] 启动失败: {e}")

    def clear(self):
        """清空数据"""
        with self._data_lock:
            self._events.clear()
            self._sessions.clear()
            self._agents.clear()
            self._prompts.clear()
            self._llm_calls.clear()
            self._traces.clear()
            self._active_streams.clear()
            self._stats = {
                'total_events': 0,
                'total_sessions': 0,
                'active_sessions': 0,
                'total_llm_calls': 0,
                'total_tokens': 0,
                'prompt_tokens': 0,
                'completion_tokens': 0,
                'total_duration_ms': 0.0,
                'errors': 0,
                'active_streams': 0,
                'avg_tokens_per_second': 0.0,
                'avg_time_to_first_token_ms': 0.0
            }
            self._event_seq = 0

    # ==================== 内部方法 ====================

    def _add_event(self, event: DebugEvent) -> str:
        """添加事件"""
        if not self._enabled:
            return event.event_id

        with self._data_lock:
            self._event_seq += 1
            event.seq = self._event_seq
            self._events.append(event)
            self._stats['total_events'] += 1

            # 更新session事件计数
            if event.session_id and event.session_id in self._sessions:
                self._sessions[event.session_id].event_count += 1

            # 关联到trace
            if event.trace_id and event.trace_id in self._traces:
                self._traces[event.trace_id].events.append(event.event_id)

            # 限制事件数量
            if len(self._events) > self._max_events:
                self._events = self._events[-self._max_events:]

        return event.event_id

    def _truncate_content(self, content: Any, max_length: int = 2000) -> str:
        """截断内容"""
        if content is None:
            return ""
        s = str(content)
        if len(s) > max_length:
            return s[:max_length] + f"... [truncated, total {len(s)} chars]"
        return s

    def _safe_serialize(self, obj: Any, max_depth: int = 3) -> Any:
        """安全序列化对象"""
        if max_depth <= 0:
            return str(obj)[:100]

        if obj is None or isinstance(obj, (bool, int, float, str)):
            return obj

        if isinstance(obj, dict):
            return {k: self._safe_serialize(v, max_depth - 1) for k, v in list(obj.items())[:50]}

        if isinstance(obj, (list, tuple)):
            return [self._safe_serialize(v, max_depth - 1) for v in list(obj)[:50]]

        return str(obj)[:500]

    # ==================== Session管理 ====================

    def start_session(self, query: str = "", root_agent_id: Optional[str] = None) -> str:
        """
        开始一个新会话

        每次用户发起对话时调用
        """
        session_id = str(uuid4())

        if not self._enabled:
            return session_id

        with self._data_lock:
            self._sessions[session_id] = SessionInfo(
                session_id=session_id,
                start_time=time.time(),
                root_agent_id=root_agent_id,
                query=query
            )
            self._stats['total_sessions'] += 1
            self._stats['active_sessions'] += 1

        # 设置当前session
        self._local.current_session_id = session_id

        self._add_event(DebugEvent(
            event_id=str(uuid4()),
            event_type=EventType.SESSION_START,
            timestamp=time.time(),
            session_id=session_id,
            agent_id=root_agent_id,
            data={
                'query_preview': query[:200] if query else "",
                'root_agent_id': root_agent_id
            }
        ))

        return session_id

    def end_session(self, session_id: Optional[str] = None, error: Optional[str] = None):
        """结束会话"""
        if not self._enabled:
            return

        session_id = session_id or self.get_current_session_id()
        if not session_id or session_id not in self._sessions:
            return

        with self._data_lock:
            session = self._sessions[session_id]
            session.end_time = time.time()
            session.status = "error" if error else "completed"
            session.error = error
            session.total_duration_ms = (session.end_time - session.start_time) * 1000
            self._stats['active_sessions'] = max(0, self._stats['active_sessions'] - 1)

        self._add_event(DebugEvent(
            event_id=str(uuid4()),
            event_type=EventType.SESSION_END,
            timestamp=time.time(),
            session_id=session_id,
            data={
                'status': session.status,
                'duration_ms': session.total_duration_ms,
                'llm_call_count': session.llm_call_count,
                'total_tokens': session.total_tokens,
                'error': error
            }
        ))

    def get_current_session_id(self) -> Optional[str]:
        """获取当前session_id"""
        return getattr(self._local, 'current_session_id', None)

    def set_current_session_id(self, session_id: str):
        """设置当前session_id"""
        self._local.current_session_id = session_id

    # ==================== Trace上下文管理 ====================

    @contextmanager
    def trace(self, agent_id: str, name: str = ""):
        """创建调用链上下文"""
        trace_id = str(uuid4())
        session_id = self.get_current_session_id()

        if self._enabled:
            with self._data_lock:
                self._traces[trace_id] = TraceContext(
                    trace_id=trace_id,
                    session_id=session_id,
                    start_time=time.time(),
                    agent_id=agent_id
                )

        old_trace = getattr(self._local, 'current_trace_id', None)
        self._local.current_trace_id = trace_id

        try:
            yield trace_id
        finally:
            self._local.current_trace_id = old_trace

            if self._enabled and trace_id in self._traces:
                with self._data_lock:
                    trace = self._traces[trace_id]
                    trace.status = "completed"
                    trace.total_duration_ms = (time.time() - trace.start_time) * 1000

    def get_current_trace_id(self) -> Optional[str]:
        """获取当前trace_id"""
        return getattr(self._local, 'current_trace_id', None)

    # ==================== Agent追踪 ====================

    def track_agent_created(self, agent, parent_id: Optional[str] = None):
        """追踪Agent创建"""
        if not self._enabled:
            return

        agent_id = getattr(agent, 'agent_id', str(uuid4()))
        agent_type = agent.__class__.__name__
        session_id = self.get_current_session_id()

        llm_info = {}
        llm = getattr(agent, 'llm', None)
        if llm:
            llm_info = {
                'model_name': getattr(llm, 'model_name', 'unknown'),
                'base_url': getattr(llm, 'base_url', ''),
                'temperature': getattr(llm, 'temperature', None),
                'max_tokens': getattr(llm, 'max_tokens', None),
                'is_multimodal': getattr(llm, 'is_multimodal', False)
            }

        info = AgentInfo(
            agent_id=agent_id,
            agent_type=agent_type,
            created_at=time.time(),
            session_id=session_id,
            parent_id=parent_id,
            config=dict(getattr(agent, 'config', {})),
            llm_info=llm_info
        )

        with self._data_lock:
            self._agents[agent_id] = info
            if parent_id and parent_id in self._agents:
                self._agents[parent_id].children_ids.append(agent_id)

            # 更新session的agents列表
            if session_id and session_id in self._sessions:
                if agent_id not in self._sessions[session_id].agents:
                    self._sessions[session_id].agents.append(agent_id)

        self._add_event(DebugEvent(
            event_id=str(uuid4()),
            event_type=EventType.AGENT_CREATED,
            timestamp=time.time(),
            agent_id=agent_id,
            session_id=session_id,
            trace_id=self.get_current_trace_id(),
            data={
                'agent_type': agent_type,
                'parent_id': parent_id,
                'llm_info': llm_info,
                'has_memory': hasattr(agent, 'memory') and agent.memory is not None,
                'has_callback': hasattr(agent, 'callback') and agent.callback is not None
            }
        ))

    def track_agent_derived(self, parent_agent, child_agent):
        """追踪Agent派生"""
        if not self._enabled:
            return

        parent_id = getattr(parent_agent, 'agent_id', 'unknown')
        child_id = getattr(child_agent, 'agent_id', '')
        child_type = child_agent.__class__.__name__
        session_id = self.get_current_session_id()

        # 更新子agent的parent_id和父agent的children_ids
        with self._data_lock:
            if child_id in self._agents:
                self._agents[child_id].parent_id = parent_id
            if parent_id in self._agents:
                if child_id not in self._agents[parent_id].children_ids:
                    self._agents[parent_id].children_ids.append(child_id)

        self._add_event(DebugEvent(
            event_id=str(uuid4()),
            event_type=EventType.AGENT_DERIVED,
            timestamp=time.time(),
            agent_id=parent_id,
            session_id=session_id,
            trace_id=self.get_current_trace_id(),
            data={
                'child_id': child_id,
                'child_type': child_type
            }
        ))

    # ==================== Prompt追踪 ====================

    def track_prompt_created(
            self,
            agent_id: str,
            prompt_id: str,
            system_prompt: Optional[str] = None,
            prompt: Optional[str] = None,
            placeholders: Optional[List[str]] = None,
            enable_memory: bool = False,
            memory_id: Optional[str] = None,
            template_path: Optional[str] = None
    ):
        """追踪Prompt创建"""
        if not self._enabled:
            return

        session_id = self.get_current_session_id()

        # 安全转换为字符串，处理Template对象等非字符串类型
        def safe_str(val):
            if val is None:
                return None
            if isinstance(val, str):
                return val
            return str(val)

        info = PromptInfo(
            prompt_id=prompt_id,
            agent_id=agent_id,
            session_id=session_id,
            created_at=time.time(),
            system_prompt=safe_str(system_prompt),
            template=safe_str(prompt),
            placeholders=placeholders or [],
            enable_memory=enable_memory,
            memory_id=memory_id
        )

        with self._data_lock:
            self._prompts[prompt_id] = info
            if agent_id in self._agents:
                self._agents[agent_id].prompt_ids.append(prompt_id)

        self._add_event(DebugEvent(
            event_id=str(uuid4()),
            event_type=EventType.PROMPT_CREATED,
            timestamp=time.time(),
            agent_id=agent_id,
            session_id=session_id,
            trace_id=self.get_current_trace_id(),
            data={
                'prompt_id': prompt_id,
                'system_prompt_preview': self._truncate_content(system_prompt, 300),
                'template_preview': self._truncate_content(prompt, 300),
                'placeholders': placeholders or [],
                'enable_memory': enable_memory,
                'memory_id': memory_id,
                'template_path': template_path
            }
        ))

    def track_prompt_render(
            self,
            agent_id: str,
            prompt_id: str,
            rendered_prompt: str,
            placeholders: Dict[str, Any] = None
    ):
        """追踪Prompt渲染"""
        if not self._enabled:
            return

        session_id = self.get_current_session_id()

        # 更新prompt信息
        with self._data_lock:
            if prompt_id in self._prompts:
                self._prompts[prompt_id].rendered_prompt = rendered_prompt

        self._add_event(DebugEvent(
            event_id=str(uuid4()),
            event_type=EventType.PROMPT_RENDER,
            timestamp=time.time(),
            agent_id=agent_id,
            session_id=session_id,
            trace_id=self.get_current_trace_id(),
            data={
                'prompt_id': prompt_id,
                'rendered_preview': self._truncate_content(rendered_prompt, 500),
                'placeholder_count': len(placeholders) if placeholders else 0,
                'placeholder_keys': list(placeholders.keys()) if placeholders else [],
                'placeholder_values': {k: self._truncate_content(v, 100) for k, v in (placeholders or {}).items()}
            }
        ))

    def track_prompt_call_start(
            self,
            agent_id: str,
            prompt_id: str,
            query: str,
            is_stream: bool = False
    ) -> str:
        """追踪Prompt调用开始"""
        call_id = str(uuid4())

        if not self._enabled:
            return call_id

        session_id = self.get_current_session_id()

        with self._data_lock:
            if prompt_id in self._prompts:
                self._prompts[prompt_id].call_count += 1

        self._add_event(DebugEvent(
            event_id=str(uuid4()),
            event_type=EventType.PROMPT_CALL_START,
            timestamp=time.time(),
            agent_id=agent_id,
            session_id=session_id,
            trace_id=self.get_current_trace_id(),
            data={
                'call_id': call_id,
                'prompt_id': prompt_id,
                'query_preview': self._truncate_content(query, 300),
                'is_stream': is_stream
            }
        ))

        return call_id

    def track_prompt_call_end(
            self,
            call_id: str,
            agent_id: str,
            prompt_id: str,
            output: str,
            duration_ms: float = 0
    ):
        """追踪Prompt调用结束"""
        if not self._enabled:
            return

        session_id = self.get_current_session_id()

        self._add_event(DebugEvent(
            event_id=str(uuid4()),
            event_type=EventType.PROMPT_CALL_END,
            timestamp=time.time(),
            agent_id=agent_id,
            session_id=session_id,
            trace_id=self.get_current_trace_id(),
            duration_ms=duration_ms,
            data={
                'call_id': call_id,
                'prompt_id': prompt_id,
                'output_preview': self._truncate_content(output, 500),
                'output_length': len(output),
                'duration_ms': duration_ms
            }
        ))

    # ==================== LLM调用追踪 ====================

    def track_llm_start(
            self,
            agent_id: str,
            model_name: str,
            messages: Optional[List[Dict]] = None,
            input_text: str = "",
            is_streaming: bool = False,
            request_params: Optional[Dict] = None,
            system_prompt: Optional[str] = None,
            prompt_id: Optional[str] = None
    ) -> str:
        """追踪LLM调用开始"""
        call_id = str(uuid4())

        if not self._enabled:
            return call_id

        session_id = self.get_current_session_id()
        trace_id = self.get_current_trace_id()

        # 深拷贝messages
        messages_copy = []
        if messages:
            for msg in messages:
                msg_copy = {
                    'role': msg.get('role', ''),
                    'content': self._truncate_content(msg.get('content', ''), 5000)
                }
                messages_copy.append(msg_copy)

        with self._data_lock:
            self._llm_calls[call_id] = LLMCallInfo(
                call_id=call_id,
                agent_id=agent_id,
                prompt_id=prompt_id,
                session_id=session_id,
                trace_id=trace_id,
                model_name=model_name,
                start_time=time.time(),
                request_messages=messages_copy,
                request_params=request_params or {},
                system_prompt=self._truncate_content(system_prompt, 2000),
                is_streaming=is_streaming
            )
            self._stats['total_llm_calls'] += 1

            # 更新session统计
            if session_id and session_id in self._sessions:
                self._sessions[session_id].llm_call_count += 1

            # 更新agent统计
            if agent_id in self._agents:
                self._agents[agent_id].llm_call_count += 1

            if trace_id and trace_id in self._traces:
                self._traces[trace_id].llm_calls.append(call_id)

        # 计算输入预览
        if input_text:
            preview = self._truncate_content(input_text, 500)
        elif messages_copy:
            last_msg = messages_copy[-1] if messages_copy else {}
            preview = self._truncate_content(last_msg.get('content', ''), 500)
        else:
            preview = ""

        self._add_event(DebugEvent(
            event_id=str(uuid4()),
            event_type=EventType.LLM_CALL_START,
            timestamp=time.time(),
            agent_id=agent_id,
            session_id=session_id,
            trace_id=trace_id,
            data={
                'call_id': call_id,
                'prompt_id': prompt_id,
                'model_name': model_name,
                'is_streaming': is_streaming,
                'input_preview': preview,
                'message_count': len(messages_copy),
                'has_system_prompt': bool(system_prompt),
                'request_params': request_params or {}
            }
        ))

        return call_id

    def track_llm_stream_chunk(
            self,
            call_id: str,
            content: str = "",
            content_type: str = "char",
            is_reasoning: bool = False
    ):
        """追踪流式输出块"""
        if not self._enabled or call_id not in self._llm_calls:
            return

        with self._data_lock:
            call = self._llm_calls[call_id]

            # 记录首Token时间
            if call.chunk_count == 0:
                call.first_token_time = time.time()

            call.chunk_count += 1

            # 累积内容
            if is_reasoning or content_type == 'think':
                call.reasoning_text += content
            else:
                call.response_text += content
                # 按类型聚合内容
                if content_type not in call.stream_content_by_type:
                    call.stream_content_by_type[content_type] = ""
                call.stream_content_by_type[content_type] += content

            # 保存chunk（限制数量）
            if len(call.stream_chunks) < self._max_stream_chunks:
                call.stream_chunks.append({
                    'index': call.chunk_count,
                    'content': content,
                    'content_type': content_type,
                    'is_reasoning': is_reasoning,
                    'timestamp': time.time()
                })

    def track_llm_end(
            self,
            call_id: str,
            output_text: str = "",
            reasoning_text: str = "",
            finish_reason: str = "stop",
            token_usage: Optional[Dict[str, int]] = None
    ):
        """追踪LLM调用结束"""
        if not self._enabled or call_id not in self._llm_calls:
            return

        with self._data_lock:
            call = self._llm_calls[call_id]
            call.end_time = time.time()

            # 如果不是流式，直接设置输出
            if not call.is_streaming:
                call.response_text = output_text[:10000]
                call.reasoning_text = reasoning_text[:5000]

            call.finish_reason = finish_reason

            # Token统计
            if token_usage:
                call.prompt_tokens = token_usage.get('prompt_tokens', 0)
                call.completion_tokens = token_usage.get('completion_tokens', 0)
                call.total_tokens = token_usage.get('total_tokens',
                                                    call.prompt_tokens + call.completion_tokens)

                self._stats['total_tokens'] += call.total_tokens
                self._stats['prompt_tokens'] += call.prompt_tokens
                self._stats['completion_tokens'] += call.completion_tokens

                # 更新session统计
                if call.session_id and call.session_id in self._sessions:
                    self._sessions[call.session_id].total_tokens += call.total_tokens

                # 更新agent统计
                if call.agent_id in self._agents:
                    self._agents[call.agent_id].total_tokens += call.total_tokens

            self._stats['total_duration_ms'] += call.duration_ms

            # 更新平均值
            completed_calls = [c for c in self._llm_calls.values() if c.end_time]
            if completed_calls:
                tps_values = [c.tokens_per_second for c in completed_calls if c.tokens_per_second > 0]
                if tps_values:
                    self._stats['avg_tokens_per_second'] = sum(tps_values) / len(tps_values)

                ttft_values = [c.time_to_first_token_ms for c in completed_calls if c.time_to_first_token_ms]
                if ttft_values:
                    self._stats['avg_time_to_first_token_ms'] = sum(ttft_values) / len(ttft_values)

            # 更新trace
            if call.trace_id and call.trace_id in self._traces:
                self._traces[call.trace_id].total_tokens += call.total_tokens

            agent_id = call.agent_id
            session_id = call.session_id
            duration = call.duration_ms

        self._add_event(DebugEvent(
            event_id=str(uuid4()),
            event_type=EventType.LLM_CALL_END,
            timestamp=time.time(),
            agent_id=agent_id,
            session_id=session_id,
            trace_id=call.trace_id,
            duration_ms=duration,
            data={
                'call_id': call_id,
                'duration_ms': duration,
                'finish_reason': finish_reason,
                'token_usage': token_usage,
                'output_preview': self._truncate_content(output_text or call.response_text, 500),
                'has_reasoning': bool(reasoning_text or call.reasoning_text),
                'chunk_count': call.chunk_count if call.is_streaming else 0,
                'time_to_first_token_ms': call.time_to_first_token_ms,
                'tokens_per_second': round(call.tokens_per_second, 2),
                'content_types': list(call.stream_content_by_type.keys()) if call.is_streaming else []
            }
        ))

    def track_llm_error(self, call_id: str, error: str, traceback_str: str = ""):
        """追踪LLM调用错误"""
        if not self._enabled:
            return

        agent_id = 'unknown'
        session_id = None
        trace_id = None

        with self._data_lock:
            if call_id in self._llm_calls:
                call = self._llm_calls[call_id]
                call.error = error
                call.error_traceback = traceback_str
                call.end_time = time.time()
                agent_id = call.agent_id
                session_id = call.session_id
                trace_id = call.trace_id
            self._stats['errors'] += 1

        self._add_event(DebugEvent(
            event_id=str(uuid4()),
            event_type=EventType.LLM_CALL_ERROR,
            timestamp=time.time(),
            agent_id=agent_id,
            session_id=session_id,
            trace_id=trace_id,
            data={
                'call_id': call_id,
                'error': error[:1000],
                'traceback': traceback_str[:2000] if traceback_str else None
            }
        ))

    # ==================== Memory追踪 ====================

    def track_memory_add(
            self,
            memory_id: str,
            role: str,
            content: str,
            agent_id: Optional[str] = None
    ):
        """追踪记忆添加"""
        if not self._enabled:
            return

        session_id = self.get_current_session_id()

        self._add_event(DebugEvent(
            event_id=str(uuid4()),
            event_type=EventType.MEMORY_ADD,
            timestamp=time.time(),
            agent_id=agent_id,
            session_id=session_id,
            trace_id=self.get_current_trace_id(),
            data={
                'memory_id': memory_id,
                'role': role,
                'content_preview': self._truncate_content(content, 300),
                'content_length': len(content)
            }
        ))

    def track_memory_retrieve(
            self,
            memory_id: str,
            rounds: int,
            message_count: int,
            agent_id: Optional[str] = None
    ):
        """追踪记忆检索"""
        if not self._enabled:
            return

        session_id = self.get_current_session_id()

        self._add_event(DebugEvent(
            event_id=str(uuid4()),
            event_type=EventType.MEMORY_RETRIEVE,
            timestamp=time.time(),
            agent_id=agent_id,
            session_id=session_id,
            trace_id=self.get_current_trace_id(),
            data={
                'memory_id': memory_id,
                'rounds': rounds,
                'message_count': message_count
            }
        ))

    def track_memory_search(
            self,
            memory_id: str,
            query: str,
            result_count: int,
            agent_id: Optional[str] = None
    ):
        """追踪记忆搜索"""
        if not self._enabled:
            return

        session_id = self.get_current_session_id()

        self._add_event(DebugEvent(
            event_id=str(uuid4()),
            event_type=EventType.MEMORY_SEARCH,
            timestamp=time.time(),
            agent_id=agent_id,
            session_id=session_id,
            trace_id=self.get_current_trace_id(),
            data={
                'memory_id': memory_id,
                'query_preview': self._truncate_content(query, 200),
                'result_count': result_count
            }
        ))

    def track_memory_clear(self, memory_id: str, agent_id: Optional[str] = None):
        """追踪记忆清空"""
        if not self._enabled:
            return

        session_id = self.get_current_session_id()

        self._add_event(DebugEvent(
            event_id=str(uuid4()),
            event_type=EventType.MEMORY_CLEAR,
            timestamp=time.time(),
            agent_id=agent_id,
            session_id=session_id,
            trace_id=self.get_current_trace_id(),
            data={'memory_id': memory_id}
        ))

    # ==================== Tool追踪 ====================

    def track_tool_start(
            self,
            tool_name: str,
            args: Dict,
            agent_id: Optional[str] = None
    ) -> str:
        """追踪工具调用开始"""
        call_id = str(uuid4())

        if not self._enabled:
            return call_id

        session_id = self.get_current_session_id()

        self._add_event(DebugEvent(
            event_id=call_id,
            event_type=EventType.TOOL_CALL_START,
            timestamp=time.time(),
            agent_id=agent_id,
            session_id=session_id,
            trace_id=self.get_current_trace_id(),
            data={
                'tool_name': tool_name,
                'args': self._safe_serialize(args)
            }
        ))

        return call_id

    def track_tool_end(
            self,
            call_id: str,
            tool_name: str,
            result: Any = None,
            duration_ms: float = 0,
            agent_id: Optional[str] = None
    ):
        """追踪工具调用结束"""
        if not self._enabled:
            return

        session_id = self.get_current_session_id()

        self._add_event(DebugEvent(
            event_id=str(uuid4()),
            event_type=EventType.TOOL_CALL_END,
            timestamp=time.time(),
            agent_id=agent_id,
            session_id=session_id,
            trace_id=self.get_current_trace_id(),
            duration_ms=duration_ms,
            data={
                'call_id': call_id,
                'tool_name': tool_name,
                'result_preview': self._truncate_content(str(result), 500),
                'duration_ms': duration_ms
            }
        ))

    def track_tool_error(
            self,
            call_id: str,
            tool_name: str,
            error: str,
            agent_id: Optional[str] = None
    ):
        """追踪工具调用错误"""
        if not self._enabled:
            return

        session_id = self.get_current_session_id()

        self._add_event(DebugEvent(
            event_id=str(uuid4()),
            event_type=EventType.TOOL_CALL_ERROR,
            timestamp=time.time(),
            agent_id=agent_id,
            session_id=session_id,
            trace_id=self.get_current_trace_id(),
            data={
                'call_id': call_id,
                'tool_name': tool_name,
                'error': error[:1000]
            }
        ))

    # ==================== 自定义追踪 ====================

    def track_custom(
            self,
            name: str,
            data: Dict = None,
            agent_id: Optional[str] = None
    ):
        """追踪自定义事件"""
        if not self._enabled:
            return

        session_id = self.get_current_session_id()

        self._add_event(DebugEvent(
            event_id=str(uuid4()),
            event_type=EventType.CUSTOM,
            timestamp=time.time(),
            agent_id=agent_id,
            session_id=session_id,
            trace_id=self.get_current_trace_id(),
            data={'name': name, **(data or {})}
        ))

    def track_error(
            self,
            error: str,
            traceback_str: str = "",
            agent_id: Optional[str] = None
    ):
        """追踪错误"""
        if not self._enabled:
            return

        session_id = self.get_current_session_id()

        with self._data_lock:
            self._stats['errors'] += 1

        self._add_event(DebugEvent(
            event_id=str(uuid4()),
            event_type=EventType.ERROR,
            timestamp=time.time(),
            agent_id=agent_id,
            session_id=session_id,
            trace_id=self.get_current_trace_id(),
            data={
                'error': error[:1000],
                'traceback': traceback_str[:2000] if traceback_str else None
            }
        ))

    # ==================== 查询方法 ====================

    def get_sessions(self, limit: int = 50, status: Optional[str] = None) -> List[Dict]:
        """获取会话列表"""
        with self._data_lock:
            sessions = list(self._sessions.values())

            if status:
                sessions = [s for s in sessions if s.status == status]

            sessions.sort(key=lambda x: x.start_time, reverse=True)
            return [s.to_dict() for s in sessions[:limit]]

    def get_session(self, session_id: str) -> Optional[Dict]:
        """获取指定会话详情"""
        with self._data_lock:
            if session_id not in self._sessions:
                return None

            session = self._sessions[session_id]
            result = session.to_dict()

            # 附加详细信息
            result['events'] = [
                e.to_dict() for e in self._events
                if e.session_id == session_id
            ]
            result['llm_calls'] = [
                self._llm_calls[cid].to_summary()
                for cid in self._llm_calls
                if self._llm_calls[cid].session_id == session_id
            ]
            result['agents_detail'] = [
                self._agents[aid].to_dict()
                for aid in session.agents
                if aid in self._agents
            ]

            return result

    def get_events(
            self,
            event_type: Optional[str] = None,
            agent_id: Optional[str] = None,
            session_id: Optional[str] = None,
            trace_id: Optional[str] = None,
            since_seq: int = 0,
            limit: int = 100
    ) -> List[Dict]:
        """获取事件列表"""
        with self._data_lock:
            events = [e for e in self._events if e.seq > since_seq]

            if event_type:
                events = [e for e in events if e.event_type.value == event_type]
            if agent_id:
                events = [e for e in events if e.agent_id == agent_id]
            if session_id:
                events = [e for e in events if e.session_id == session_id]
            if trace_id:
                events = [e for e in events if e.trace_id == trace_id]

            return [e.to_dict() for e in events[-limit:]]

    def get_agents(self, session_id: Optional[str] = None) -> List[Dict]:
        """获取所有Agent"""
        with self._data_lock:
            agents = list(self._agents.values())

            if session_id:
                agents = [a for a in agents if a.session_id == session_id]

            return [a.to_dict() for a in agents]

    def get_agent(self, agent_id: str) -> Optional[Dict]:
        """获取指定Agent"""
        with self._data_lock:
            if agent_id not in self._agents:
                return None

            agent = self._agents[agent_id]
            result = agent.to_dict()

            # 附加prompts信息
            result['prompts'] = [
                self._prompts[pid].to_dict()
                for pid in agent.prompt_ids
                if pid in self._prompts
            ]

            # 附加LLM调用
            result['llm_calls'] = [
                self._llm_calls[cid].to_summary()
                for cid in self._llm_calls
                if self._llm_calls[cid].agent_id == agent_id
            ]

            return result

    def get_prompts(self, agent_id: Optional[str] = None, session_id: Optional[str] = None) -> List[Dict]:
        """获取Prompt列表"""
        with self._data_lock:
            prompts = list(self._prompts.values())

            if agent_id:
                prompts = [p for p in prompts if p.agent_id == agent_id]
            if session_id:
                prompts = [p for p in prompts if p.session_id == session_id]

            return [p.to_dict() for p in prompts]

    def get_prompt(self, prompt_id: str) -> Optional[Dict]:
        """获取指定Prompt"""
        def safe_str(val):
            if val is None:
                return None
            if isinstance(val, str):
                return val
            return str(val)

        with self._data_lock:
            if prompt_id not in self._prompts:
                return None

            prompt = self._prompts[prompt_id]
            result = prompt.to_dict()

            # 完整内容 - 安全转换为字符串
            result['system_prompt_full'] = safe_str(prompt.system_prompt)
            result['template_full'] = safe_str(prompt.template)
            result['rendered_full'] = safe_str(prompt.rendered_prompt)

            return result

    def get_llm_calls(
            self,
            agent_id: Optional[str] = None,
            session_id: Optional[str] = None,
            trace_id: Optional[str] = None,
            limit: int = 100
    ) -> List[Dict]:
        """获取LLM调用列表"""
        with self._data_lock:
            calls = list(self._llm_calls.values())

            if agent_id:
                calls = [c for c in calls if c.agent_id == agent_id]
            if session_id:
                calls = [c for c in calls if c.session_id == session_id]
            if trace_id:
                calls = [c for c in calls if c.trace_id == trace_id]

            calls.sort(key=lambda x: x.start_time, reverse=True)
            return [c.to_summary() for c in calls[:limit]]

    def get_llm_call(self, call_id: str) -> Optional[Dict]:
        """获取指定LLM调用详情"""
        with self._data_lock:
            return self._llm_calls[call_id].to_dict() if call_id in self._llm_calls else None

    def get_traces(self, session_id: Optional[str] = None, limit: int = 50) -> List[Dict]:
        """获取调用链列表"""
        with self._data_lock:
            traces = list(self._traces.values())

            if session_id:
                traces = [t for t in traces if t.session_id == session_id]

            traces.sort(key=lambda x: x.start_time, reverse=True)
            return [t.to_dict() for t in traces[:limit]]

    def get_trace(self, trace_id: str) -> Optional[Dict]:
        """获取指定调用链"""
        with self._data_lock:
            if trace_id not in self._traces:
                return None

            trace = self._traces[trace_id]
            result = trace.to_dict()

            result['events_detail'] = [
                e.to_dict() for e in self._events
                if e.trace_id == trace_id
            ]
            result['llm_calls_detail'] = [
                self._llm_calls[cid].to_dict()
                for cid in trace.llm_calls
                if cid in self._llm_calls
            ]

            return result

    def get_call_graph(self, session_id: Optional[str] = None) -> Dict:
        """获取调用图数据"""
        with self._data_lock:
            nodes = []
            edges = []

            agents = list(self._agents.values())
            if session_id:
                agents = [a for a in agents if a.session_id == session_id]

            for agent in agents:
                llm_calls = [c for c in self._llm_calls.values() if c.agent_id == agent.agent_id]

                nodes.append({
                    'id': agent.agent_id,
                    'type': 'agent',
                    'label': agent.agent_type,
                    'data': {
                        'agent_type': agent.agent_type,
                        'status': agent.status,
                        'llm_model': agent.llm_info.get('model_name', ''),
                        'llm_call_count': len(llm_calls),
                        'total_tokens': sum(c.total_tokens for c in llm_calls),
                        'prompt_count': len(agent.prompt_ids),
                        'created_at': agent.created_at
                    }
                })

                if agent.parent_id:
                    edges.append({
                        'source': agent.parent_id,
                        'target': agent.agent_id,
                        'type': 'derive'
                    })

            return {'nodes': nodes, 'edges': edges}

    def get_stats(self) -> Dict:
        """获取统计信息"""
        with self._data_lock:
            stats = {**self._stats}
            stats['active_agents'] = len([a for a in self._agents.values() if a.status == 'active'])
            stats['total_agents'] = len(self._agents)
            stats['total_prompts'] = len(self._prompts)
            stats['event_seq'] = self._event_seq
            stats['active_traces'] = len([t for t in self._traces.values() if t.status == 'running'])
            return stats

    def get_timeline(
            self,
            agent_id: Optional[str] = None,
            session_id: Optional[str] = None,
            trace_id: Optional[str] = None,
            limit: int = 200
    ) -> List[Dict]:
        """获取时间线数据"""
        with self._data_lock:
            events = list(self._events)

            if agent_id:
                events = [e for e in events if e.agent_id == agent_id]
            if session_id:
                events = [e for e in events if e.session_id == session_id]
            if trace_id:
                events = [e for e in events if e.trace_id == trace_id]

            events.sort(key=lambda x: x.timestamp)

            timeline = []
            for e in events[-limit:]:
                item = {
                    'timestamp': e.timestamp,
                    'event_type': e.event_type.value if isinstance(e.event_type, EventType) else e.event_type,
                    'agent_id': e.agent_id,
                    'session_id': e.session_id,
                    'duration_ms': e.duration_ms,
                    'data': e.data,
                    'seq': e.seq
                }
                timeline.append(item)

            return timeline


# 全局实例
tracer = DebugTracer()

