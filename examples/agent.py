# agent.py
import asyncio
from alphora.server.stream_responser import DataStreamer


class AsyncAgent:
    def __init__(self, streamer: DataStreamer):
        self.streamer = streamer

    async def run(self):
        """核心逻辑：完全异步"""
        for i in range(5):
            await asyncio.sleep(0.5)
            await self.streamer.send_data("text", f"Step {i + 1}: processing...")

        # 模拟最终结果
        await self.streamer.send_data("result", "Task completed successfully!")
        await self.streamer.send_stop()


# main.py
from fastapi import FastAPI

app = FastAPI()


@app.get("/stream")
async def stream():
    streamer = DataStreamer(timeout=30)  # 30秒超时
    agent = AsyncAgent(streamer)

    # 启动智能体
    asyncio.create_task(agent.run())

    return streamer.start_streaming_openai()

