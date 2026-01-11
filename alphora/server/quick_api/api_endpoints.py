import logging
import datetime
from typing import Type, Dict, Any, Optional
import asyncio
from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import StreamingResponse

from copy import copy

from alphora.agent.base_agent import BaseAgent
from alphora.server.openai_request_body import OpenAIRequest
from alphora.server.stream_responser import DataStreamer
from alphora.agent.stream import Stream
from alphora.memory.base import BaseMemory
from alphora.memory.memories.short_term_memory import ShortTermMemory

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
        """每次请求创建全新Agent实例 + 关联会话记忆"""
        try:
            body_data.set_headers(dict(raw_request.headers))

            # 确定记忆类
            memory_cls = ShortTermMemory

            if hasattr(agent, 'default_memory_cls') and issubclass(agent.default_memory_cls, BaseMemory):
                memory_cls = agent.default_memory_cls

            # 获取/创建会话记忆
            session_id, session_memory = memory_pool.get_or_create(
                session_id=body_data.session_id,
                memory_cls=memory_cls
            )

            logger.debug(f"处理请求 - session_id: {session_id}，准备创建全新 {agent.__class__.__name__} 实例")

            # 创建全新Agent实例
            new_agent = copy(agent)

            # 配置Agent实例
            new_agent.memory = session_memory

            new_callback = DataStreamer(timeout=300)
            new_agent.callback = new_callback
            new_agent.stream = Stream(callback=new_callback)

            # 执行Agent方法
            agent_method = getattr(new_agent, method_name)
            _ = asyncio.create_task(agent_method(body_data))

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
                    "agent_instance": "全新实例创建失败"
                }
            )

    return router

