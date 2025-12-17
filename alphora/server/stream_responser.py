import asyncio
import json
from datetime import datetime
from fastapi.responses import StreamingResponse
from datetime import datetime, timezone
from pydantic import BaseModel
import queue
from typing import List, Optional, Dict, Any
from fastapi.responses import StreamingResponse
import uuid
import typing
import os
import time
import asyncio


class ChoiceDelta(BaseModel):
    content: Optional[str] = None
    content_type: Optional[str] = 'text'
    function_call: Optional[str] = None
    refusal: Optional[str] = None
    role: Optional[str] = None


class Choice(BaseModel):
    index: int
    delta: ChoiceDelta
    finish_reason: Optional[str] = None


class ChatCompletionChunk(BaseModel):
    id: str
    object: str = "chat.completion.chunk"
    created: str
    model: str
    choices: List[Choice]
    system_fingerprint: Optional[str] = None


class DataStreamer:
    def __init__(self, timeout: int = 300, model_name: str = 'AlphaData'):
        self.timeout = timeout
        self.data_queue = asyncio.Queue()
        self._closed = False
        self.model_name = model_name
        self.completion_id = f'cmpl-{str(uuid.uuid4())}'

    async def send_data(self, content_type: str, content: str = None):
        """由智能体调用：向流中发送数据"""
        if self._closed:
            return

        await self.data_queue.put({
            "type": content_type,
            "content": content
        })

    async def stop(self, stop_reason: str = 'stop'):
        """发送结束信号"""
        await self.send_data(content_type="stop", content=stop_reason)

    def _generate_sse_chunk(self,
                            content: str,
                            content_type: str,
                            finish_reason: Optional[str] = None) -> str:
        """
        生成 SSE 数据块，符合 OpenAI chat.completion.chunk 结构

        :param content: 消息内容
        :param finish_reason: 完成原因，可选
        :return: SSE 格式的字符串
        """
        created_time = datetime.now(timezone.utc).astimezone().isoformat()

        try:
            chunk = ChatCompletionChunk(
                id=self.completion_id,
                created=created_time,
                model=self.model_name,
                choices=[Choice(
                    index=0,
                    delta=ChoiceDelta(content=content,
                                      content_type=content_type),
                    finish_reason=finish_reason
                )]
            )
            return f"data: {chunk.model_dump_json()}\n\n"
        except Exception as e:
            chunk = ChatCompletionChunk(
                id=self.completion_id,
                created=created_time,
                model=self.model_name,
                choices=[Choice(
                    index=0,
                    delta=ChoiceDelta(content=str(e),
                                      content_type='sse error'),
                    finish_reason=finish_reason
                )]
            )
            return f"data: {chunk.model_dump_json()}\n\n"

    async def data_generator(self):
        """异步生成器：供 StreamingResponse 使用"""
        end_time = asyncio.get_event_loop().time() + self.timeout
        try:
            while True:
                # 计算剩余超时时间
                remaining = end_time - asyncio.get_event_loop().time()
                if remaining <= 0:
                    yield self._generate_sse_chunk(content="", content_type='stop', finish_reason='timeout')
                    break

                try:
                    # 带超时等待数据
                    data = await asyncio.wait_for(self.data_queue.get(), timeout=remaining)

                except asyncio.TimeoutError:
                    yield self._generate_sse_chunk(content="", content_type='stop', finish_reason='timeout')
                    break

                yield self._generate_sse_chunk(content=data['content'], content_type=data['type'])

                if data["type"] == "stop":
                    yield self._generate_sse_chunk(content='', content_type='stop', finish_reason=data['content'])
                    break
        finally:
            self._closed = True

            while not self.data_queue.empty():
                try:
                    self.data_queue.get_nowait()
                except asyncio.QueueEmpty:
                    break

    def start_streaming_openai(self) -> StreamingResponse:
        """返回 FastAPI 可用的流式响应"""
        return StreamingResponse(
            content=self.data_generator(),
            media_type="text/event-stream",
            headers={
                "Cache-Control": "no-cache",
                "Connection": "keep-alive",
                "X-Accel-Buffering": "no",  # 禁用 Nginx 缓冲
            }
        )

