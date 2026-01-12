"""
Alphora Debugger

用法:
    agent = BaseAgent(llm=llm, debugger=True)
    # 访问 http://localhost:9527/
"""

from .tracer import (
    tracer,
    DebugTracer,
    EventType,
    DebugEvent,
    SessionInfo,
    AgentInfo,
    PromptInfo,
    LLMCallInfo,
    TraceContext
)

from .server import start_server_background

__all__ = [
    'tracer',
    'DebugTracer',
    'EventType',
    'DebugEvent',
    'SessionInfo',
    'AgentInfo',
    'PromptInfo',
    'LLMCallInfo',
    'TraceContext',
    'start_server_background'
]