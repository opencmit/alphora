"""
调用链追踪模块

支持功能：
1. 统一Trace ID
2. 调用耗时统计
3. 层级追踪
4. 异步上下文传递
5. 日志集成
"""

import asyncio
import functools
import logging
import time
import uuid
from contextvars import ContextVar
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Callable, Dict, List, Optional, TypeVar

logger = logging.getLogger(__name__)

F = TypeVar('F', bound=Callable)

# 上下文变量，用于跨函数传递追踪信息
_current_trace: ContextVar[Optional["TraceContext"]] = ContextVar("current_trace", default=None)
_current_span: ContextVar[Optional["Span"]] = ContextVar("current_span", default=None)


@dataclass
class Span:
    """
    追踪跨度

    表示一次操作的执行记录
    """
    span_id: str
    trace_id: str
    name: str
    parent_id: Optional[str] = None
    start_time: float = field(default_factory=time.time)
    end_time: Optional[float] = None
    status: str = "running"
    tags: Dict[str, Any] = field(default_factory=dict)
    logs: List[Dict[str, Any]] = field(default_factory=list)
    children: List["Span"] = field(default_factory=list)

    @property
    def duration_ms(self) -> Optional[float]:
        """持续时间（毫秒）"""
        if self.end_time is None:
            return None
        return (self.end_time - self.start_time) * 1000

    def finish(self, status: str = "ok"):
        """完成span"""
        self.end_time = time.time()
        self.status = status

    def set_tag(self, key: str, value: Any):
        """设置标签"""
        self.tags[key] = value

    def log(self, message: str, **kwargs):
        """添加日志"""
        self.logs.append({
            "timestamp": time.time(),
            "message": message,
            **kwargs
        })

    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return {
            "span_id": self.span_id,
            "trace_id": self.trace_id,
            "name": self.name,
            "parent_id": self.parent_id,
            "start_time": datetime.fromtimestamp(self.start_time).isoformat(),
            "end_time": datetime.fromtimestamp(self.end_time).isoformat() if self.end_time else None,
            "duration_ms": self.duration_ms,
            "status": self.status,
            "tags": self.tags,
            "logs": self.logs,
            "children": [child.to_dict() for child in self.children]
        }


class TraceContext:
    """
    追踪上下文

    管理一次完整请求的追踪信息
    """

    def __init__(self, trace_id: Optional[str] = None):
        self.trace_id = trace_id or str(uuid.uuid4())[:8]
        self.root_span: Optional[Span] = None
        self._spans: Dict[str, Span] = {}
        self._start_time = time.time()

    def create_span(
            self,
            name: str,
            parent_span: Optional[Span] = None
    ) -> Span:
        """创建新的span"""
        span = Span(
            span_id=str(uuid.uuid4())[:8],
            trace_id=self.trace_id,
            name=name,
            parent_id=parent_span.span_id if parent_span else None
        )

        self._spans[span.span_id] = span

        if self.root_span is None:
            self.root_span = span
        elif parent_span:
            parent_span.children.append(span)

        return span

    @property
    def total_duration_ms(self) -> float:
        """总耗时（毫秒）"""
        return (time.time() - self._start_time) * 1000

    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return {
            "trace_id": self.trace_id,
            "total_duration_ms": self.total_duration_ms,
            "root_span": self.root_span.to_dict() if self.root_span else None
        }

    def print_tree(self, indent: int = 0) -> str:
        """打印追踪树"""
        lines = []

        def _print_span(span: Span, level: int):
            prefix = "  " * level
            duration = f"{span.duration_ms:.2f}ms" if span.duration_ms else "running"
            status_icon = "✓" if span.status == "ok" else "✗" if span.status == "error" else "○"
            lines.append(f"{prefix}{status_icon} {span.name} [{duration}]")

            for tag_key, tag_value in span.tags.items():
                lines.append(f"{prefix}  • {tag_key}: {tag_value}")

            for child in span.children:
                _print_span(child, level + 1)

        lines.append(f"Trace: {self.trace_id} [{self.total_duration_ms:.2f}ms]")
        lines.append("-" * 50)

        if self.root_span:
            _print_span(self.root_span, 0)

        return "\n".join(lines)


class Tracer:
    """
    追踪器

    用于创建和管理追踪上下文

    使用方式：
    ```python
    tracer = Tracer()

    @tracer.trace("process_request")
    async def process(data):
        # 子操作会自动关联
        result = await sub_operation(data)
        return result

    # 或者手动使用
    async with tracer.start_trace("my_trace") as trace:
        with tracer.span("step1"):
            await do_step1()
        with tracer.span("step2"):
            await do_step2()

        print(trace.print_tree())
    ```
    """

    def __init__(
            self,
            service_name: str = "alphora",
            on_trace_complete: Optional[Callable[[TraceContext], None]] = None
    ):
        self.service_name = service_name
        self.on_trace_complete = on_trace_complete

    def start_trace(self, name: str = "root", trace_id: Optional[str] = None):
        """启动新的追踪"""
        return _TraceContextManager(self, name, trace_id)

    def span(self, name: str):
        """创建span上下文管理器"""
        return _SpanContextManager(self, name)

    def trace(
            self,
            name: Optional[str] = None,
            tags: Optional[Dict[str, Any]] = None
    ) -> Callable[[F], F]:
        """
        追踪装饰器

        Args:
            name: span名称，默认使用函数名
            tags: 标签
        """
        def decorator(func: F) -> F:
            span_name = name or func.__name__

            @functools.wraps(func)
            async def async_wrapper(*args, **kwargs):
                current_trace = _current_trace.get()
                current_parent = _current_span.get()

                # 如果没有追踪上下文，创建一个新的
                if current_trace is None:
                    async with self.start_trace(span_name) as trace:
                        result = await func(*args, **kwargs)

                        if self.on_trace_complete:
                            self.on_trace_complete(trace)

                        return result

                # 在现有追踪中创建span
                span = current_trace.create_span(span_name, current_parent)

                if tags:
                    for k, v in tags.items():
                        span.set_tag(k, v)

                # 添加函数参数作为标签
                span.set_tag("args_count", len(args))
                span.set_tag("kwargs_keys", list(kwargs.keys()))

                token = _current_span.set(span)
                try:
                    result = await func(*args, **kwargs)
                    span.finish("ok")
                    return result
                except Exception as e:
                    span.finish("error")
                    span.set_tag("error", str(e))
                    span.set_tag("error_type", type(e).__name__)
                    raise
                finally:
                    _current_span.reset(token)

            @functools.wraps(func)
            def sync_wrapper(*args, **kwargs):
                current_trace = _current_trace.get()
                current_parent = _current_span.get()

                if current_trace is None:
                    # 创建简单的追踪
                    trace = TraceContext()
                    span = trace.create_span(span_name)

                    trace_token = _current_trace.set(trace)
                    span_token = _current_span.set(span)

                    try:
                        result = func(*args, **kwargs)
                        span.finish("ok")

                        if self.on_trace_complete:
                            self.on_trace_complete(trace)

                        return result
                    except Exception as e:
                        span.finish("error")
                        span.set_tag("error", str(e))
                        raise
                    finally:
                        _current_span.reset(span_token)
                        _current_trace.reset(trace_token)

                span = current_trace.create_span(span_name, current_parent)

                if tags:
                    for k, v in tags.items():
                        span.set_tag(k, v)

                token = _current_span.set(span)
                try:
                    result = func(*args, **kwargs)
                    span.finish("ok")
                    return result
                except Exception as e:
                    span.finish("error")
                    span.set_tag("error", str(e))
                    raise
                finally:
                    _current_span.reset(token)

            if asyncio.iscoroutinefunction(func):
                return async_wrapper
            return sync_wrapper

        return decorator


class _TraceContextManager:
    """追踪上下文管理器"""

    def __init__(self, tracer: Tracer, name: str, trace_id: Optional[str]):
        self.tracer = tracer
        self.name = name
        self.trace_id = trace_id
        self.trace: Optional[TraceContext] = None
        self._trace_token = None
        self._span_token = None

    async def __aenter__(self) -> TraceContext:
        self.trace = TraceContext(self.trace_id)
        span = self.trace.create_span(self.name)

        self._trace_token = _current_trace.set(self.trace)
        self._span_token = _current_span.set(span)

        return self.trace

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        if self.trace and self.trace.root_span:
            status = "error" if exc_type else "ok"
            self.trace.root_span.finish(status)

            if exc_type:
                self.trace.root_span.set_tag("error", str(exc_val))
                self.trace.root_span.set_tag("error_type", exc_type.__name__)

        if self._span_token:
            _current_span.reset(self._span_token)
        if self._trace_token:
            _current_trace.reset(self._trace_token)

        return False


class _SpanContextManager:
    """Span上下文管理器"""

    def __init__(self, tracer: Tracer, name: str):
        self.tracer = tracer
        self.name = name
        self.span: Optional[Span] = None
        self._token = None

    def __enter__(self) -> Span:
        current_trace = _current_trace.get()
        current_parent = _current_span.get()

        if current_trace is None:
            raise RuntimeError("No active trace context. Use tracer.start_trace() first.")

        self.span = current_trace.create_span(self.name, current_parent)
        self._token = _current_span.set(self.span)

        return self.span

    def __exit__(self, exc_type, exc_val, exc_tb):
        if self.span:
            status = "error" if exc_type else "ok"
            self.span.finish(status)

            if exc_type:
                self.span.set_tag("error", str(exc_val))

        if self._token:
            _current_span.reset(self._token)

        return False

    async def __aenter__(self) -> Span:
        return self.__enter__()

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        return self.__exit__(exc_type, exc_val, exc_tb)


# 全局追踪器
_global_tracer: Optional[Tracer] = None


def get_tracer() -> Tracer:
    """获取全局追踪器"""
    global _global_tracer
    if _global_tracer is None:
        _global_tracer = Tracer()
    return _global_tracer


def set_tracer(tracer: Tracer):
    """设置全局追踪器"""
    global _global_tracer
    _global_tracer = tracer


def get_current_trace() -> Optional[TraceContext]:
    """获取当前追踪上下文"""
    return _current_trace.get()


def get_current_span() -> Optional[Span]:
    """获取当前span"""
    return _current_span.get()


# 便捷装饰器
def trace(name: Optional[str] = None, tags: Optional[Dict[str, Any]] = None):
    """全局追踪装饰器"""
    return get_tracer().trace(name, tags)