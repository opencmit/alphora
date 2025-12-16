import asyncio
import json
from datetime import datetime
from fastapi.responses import StreamingResponse


class DataStreamer:
    def __init__(self, timeout: int = 300):
        self.timeout = timeout
        self.data_queue = asyncio.Queue()
        self._closed = False

    async def send_data(self, content_type: str, content: str = None):
        """由智能体调用：向流中发送数据"""
        if self._closed:
            return

        await self.data_queue.put({
            "type": content_type,
            "content": content,
            "timestamp": datetime.utcnow().isoformat()
        })

    async def send_stop(self):
        """发送结束信号"""
        await self.send_data("stop")

    def _generate_sse_chunk(self, data: dict) -> str:
        """将数据包装为 SSE 格式"""
        if data["type"] == "stop":
            return "data: [DONE]\n\n"
        try:
            json_str = json.dumps(data, ensure_ascii=False)
        except Exception:
            json_str = json.dumps({"error": "serialize failed"}, ensure_ascii=False)
        return f"data: {json_str}\n\n"

    async def data_generator(self):
        """异步生成器：供 StreamingResponse 使用"""
        end_time = asyncio.get_event_loop().time() + self.timeout
        try:
            while True:
                # 计算剩余超时时间
                remaining = end_time - asyncio.get_event_loop().time()
                if remaining <= 0:
                    yield self._generate_sse_chunk({"type": "error", "content": "timeout"})
                    break

                try:
                    # 带超时等待数据
                    data = await asyncio.wait_for(self.data_queue.get(), timeout=remaining)
                except asyncio.TimeoutError:
                    yield self._generate_sse_chunk({"type": "error", "content": "timeout"})
                    break

                yield self._generate_sse_chunk(data)

                if data["type"] == "stop":
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

