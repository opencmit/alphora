"""
Alphora Debugger - Server

功能：
1. 实时事件推送（WebSocket）
2. 调用链可视化
3. LLM调用详情面板
4. Token统计面板
5. 时间线视图
"""

import asyncio
import threading
import time
from typing import Optional

HAS_FASTAPI = False

try:
    from fastapi import FastAPI, WebSocket, WebSocketDisconnect, Query, HTTPException
    from fastapi.responses import HTMLResponse, JSONResponse
    from fastapi.middleware.cors import CORSMiddleware
    import uvicorn
    HAS_FASTAPI = True
except ImportError:
    pass

import logging
logger = logging.getLogger(__name__)

_server_thread: Optional[threading.Thread] = None


def start_server_background(port: int = 9527):
    """在后台启动服务器"""
    global _server_thread

    if not HAS_FASTAPI:
        raise ImportError("需要安装: pip install fastapi uvicorn")

    if _server_thread and _server_thread.is_alive():
        return

    def run():
        from .tracer import tracer
        from .frontend import get_html

        app = FastAPI(title="Alphora Debugger", version="2.1")
        app.add_middleware(
            CORSMiddleware,
            allow_origins=["*"],
            allow_methods=["*"],
            allow_headers=["*"]
        )

        # ==================== API 端点 ====================

        @app.get("/", response_class=HTMLResponse)
        async def dashboard():
            return get_html()

        @app.get("/api/status")
        async def get_status():
            return {"enabled": tracer.enabled, "stats": tracer.get_stats()}

        @app.post("/api/clear")
        async def api_clear():
            tracer.clear()
            return {"success": True}

        @app.get("/api/events")
        async def get_events(
                event_type: Optional[str] = None,
                agent_id: Optional[str] = None,
                trace_id: Optional[str] = None,
                since_seq: int = 0,
                limit: int = Query(100, ge=1, le=1000)
        ):
            return tracer.get_events(
                event_type=event_type,
                agent_id=agent_id,
                trace_id=trace_id,
                since_seq=since_seq,
                limit=limit
            )

        @app.get("/api/agents")
        async def get_agents():
            return tracer.get_agents()

        @app.get("/api/agents/{agent_id}")
        async def get_agent(agent_id: str):
            agent = tracer.get_agent(agent_id)
            if not agent:
                raise HTTPException(status_code=404, detail="Agent not found")
            return agent

        @app.get("/api/llm-calls")
        async def get_llm_calls(
                agent_id: Optional[str] = None,
                trace_id: Optional[str] = None,
                limit: int = Query(100, ge=1, le=1000)
        ):
            return tracer.get_llm_calls(
                agent_id=agent_id,
                trace_id=trace_id,
                limit=limit
            )

        @app.get("/api/llm-calls/{call_id}")
        async def get_llm_call(call_id: str):
            call = tracer.get_llm_call(call_id)
            if not call:
                raise HTTPException(status_code=404, detail="LLM call not found")
            return call

        @app.get("/api/traces")
        async def get_traces(limit: int = Query(50, ge=1, le=200)):
            return tracer.get_traces(limit=limit)

        @app.get("/api/traces/{trace_id}")
        async def get_trace(trace_id: str):
            trace = tracer.get_trace(trace_id)
            if not trace:
                raise HTTPException(status_code=404, detail="Trace not found")
            return trace

        @app.get("/api/graph")
        async def get_graph():
            return tracer.get_call_graph()

        @app.get("/api/stats")
        async def get_stats():
            return tracer.get_stats()

        @app.get("/api/timeline")
        async def get_timeline(
                agent_id: Optional[str] = None,
                trace_id: Optional[str] = None,
                limit: int = Query(200, ge=1, le=1000)
        ):
            return tracer.get_timeline(
                agent_id=agent_id,
                trace_id=trace_id,
                limit=limit
            )

        # ==================== WebSocket ====================

        @app.websocket("/ws")
        async def websocket_endpoint(ws: WebSocket):
            await ws.accept()

            # 发送初始数据 - 修复：添加llm_calls
            await ws.send_json({
                "type": "init",
                "stats": tracer.get_stats(),
                "agents": tracer.get_agents(),
                "events": tracer.get_events(limit=500),
                "llm_calls": tracer.get_llm_calls(limit=100),  # 新增
                "graph": tracer.get_call_graph()
            })

            last_seq = tracer.event_seq

            try:
                while True:
                    await asyncio.sleep(0.2)
                    current_seq = tracer.event_seq

                    if current_seq > last_seq:
                        events = tracer.get_events(since_seq=last_seq, limit=100)
                        if events:
                            # 修复：添加llm_calls
                            await ws.send_json({
                                "type": "update",
                                "events": events,
                                "stats": tracer.get_stats(),
                                "agents": tracer.get_agents(),
                                "llm_calls": tracer.get_llm_calls(limit=100),  # 新增
                                "graph": tracer.get_call_graph()
                            })
                        last_seq = current_seq

                    try:
                        data = await asyncio.wait_for(ws.receive_json(), timeout=0.05)
                        if data.get("type") == "ping":
                            await ws.send_json({"type": "pong"})
                        elif data.get("type") == "get_llm_call":
                            call = tracer.get_llm_call(data.get("call_id", ""))
                            await ws.send_json({"type": "llm_call_detail", "data": call})
                        elif data.get("type") == "get_trace":
                            trace = tracer.get_trace(data.get("trace_id", ""))
                            await ws.send_json({"type": "trace_detail", "data": trace})
                    except asyncio.TimeoutError:
                        pass
            except WebSocketDisconnect:
                pass
            except Exception as e:
                logger.error(f"WebSocket error: {e}")

        # ==================== 启动 ====================

        config = uvicorn.Config(app, host="0.0.0.0", port=port, log_level="warning")
        server = uvicorn.Server(config)

        logger.info(f"[Debugger] 🔍 调试面板: http://localhost:{port}/")
        print(f"[Debugger] 🔍 调试面板: http://localhost:{port}/")

        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        loop.run_until_complete(server.serve())

    # daemon=False 保持程序运行
    _server_thread = threading.Thread(target=run, daemon=False, name="DebugServer")
    _server_thread.start()
    time.sleep(0.5)