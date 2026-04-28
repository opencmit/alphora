import logging
import datetime
from typing import Type, Dict, Any, Optional
import asyncio
from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import StreamingResponse

from alphora.agent.base_agent import BaseAgent
from alphora.agent._request_scope import enter_request_scope
from alphora.server.openai_request_body import OpenAIRequest
from alphora.server.stream_responser import DataStreamer
from alphora.agent.stream import Stream
from alphora.memory import MemoryManager

from .memory_pool import MemoryPool
from .config import APIPublisherConfig

logger = logging.getLogger(__name__)


def create_api_router(
        agent: BaseAgent,
        method_name: str,
        memory_pool: MemoryPool,
        config: APIPublisherConfig
) -> APIRouter:
    """
    创建API路由
    :param agent: Agent类
    :param method_name: 要暴露的方法名
    :param memory_pool: 记忆池实例
    :param config: 配置
    :return: FastAPI路由实例
    """
    router = APIRouter()

    # 构建完整API路径
    full_api_path = f"{config.path}/chat/completions"
    if config.path.endswith("/"):
        full_api_path = f"{config.path[:-1]}/chat/completions"

    @router.post(full_api_path, response_description="OpenAI兼容格式的响应")
    async def agent_api_endpoint(body_data: OpenAIRequest,
                                 raw_request: Request):
        """复用单例 agent，每个请求在自己的 asyncio Task 上下文里
        激活独立的请求作用域（contextvars），从而把 ``config / memory /
        callback / stream / llm`` 等写入隔离到本次请求。"""
        try:
            body_data.set_headers(dict(raw_request.headers))

            # 确定记忆类
            memory_cls = MemoryManager

            if hasattr(agent, 'default_memory_cls') and issubclass(agent.default_memory_cls, MemoryManager):
                memory_cls = agent.default_memory_cls

            # 获取/创建会话记忆
            session_id, session_memory = memory_pool.get_or_create(
                session_id=body_data.session_id,
                memory_cls=memory_cls
            )

            logger.debug(
                f"处理请求 - session_id: {session_id}，在 {agent.__class__.__name__} 单例上激活请求作用域"
            )

            new_callback = DataStreamer(timeout=1800)

            async def _guarded_run(_agent, _method_name, _body, _cb, _session_memory):
                # 注意：必须在新建的 Task 上下文里激活作用域，
                # 这样后续对 _agent 这五个属性的写入只影响本任务，不会污染单例或其它并发请求。
                try:
                    enter_request_scope()
                    # 给单例 agent 在本次请求里覆盖请求级属性。
                    # config 必须显式克隆一份新字典，否则当任务结束、覆盖随 ContextVar 释放后，
                    # 它们仍是同一个 dict 引用，在并发下会和后续请求相互写脏。
                    _agent.config = dict(_agent.config or {})
                    _agent.memory = _session_memory
                    _agent.callback = _cb
                    _agent.stream = Stream(callback=_cb)

                    method = getattr(_agent, _method_name)
                    await method(_body)
                except Exception as exc:
                    logger.error(f"Agent 执行异常: {exc}", exc_info=exc)
                    if not _cb._closed:
                        await _cb.send_data(content_type="error", content=str(exc))
                finally:
                    if not _cb._closed:
                        await _cb.stop()

            asyncio.create_task(
                _guarded_run(agent, method_name, body_data, new_callback, session_memory)
            )

            # 返回响应（流式/非流式）
            if body_data.stream:
                return new_callback.start_streaming_openai()
            else:
                return await new_callback.start_non_streaming_openai()

        except Exception as e:
            session_id = body_data.session_id or "unknown"
            logger.error(f"处理请求异常 (session_id: {session_id})", exc_info=e)
            raise HTTPException(
                status_code=500,
                detail={
                    "error": str(e),
                    "session_id": session_id,
                    "timestamp": datetime.datetime.now().isoformat(),
                    "agent_instance": "请求作用域激活失败"
                }
            )

    return router

