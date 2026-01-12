"""
Alphora Debugger - API Routes
FastAPI路由和WebSocket处理
"""

import asyncio
import logging
from typing import Optional

logger = logging.getLogger(__name__)


def create_app(tracer):
    """创建FastAPI应用"""
    from fastapi import FastAPI, WebSocket, WebSocketDisconnect, Query, HTTPException
    from fastapi.responses import HTMLResponse
    from fastapi.middleware.cors import CORSMiddleware
    from .frontend import get_html

    app = FastAPI(title="Alphora Debugger", version="2.2")
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_methods=["*"],
        allow_headers=["*"]
    )

    # ==================== 页面 ====================

    @app.get("/", response_class=HTMLResponse)
    async def dashboard():
        return get_html()

    # ==================== Status API ====================

    @app.get("/api/status")
    async def get_status():
        return {"enabled": tracer.enabled, "stats": tracer.get_stats()}

    @app.post("/api/clear")
    async def api_clear():
        tracer.clear()
        return {"success": True}

    # ==================== Session API ====================

    @app.get("/api/sessions")
    async def get_sessions(
            status: Optional[str] = None,
            limit: int = Query(50, ge=1, le=200)
    ):
        return tracer.get_sessions(limit=limit, status=status)

    @app.get("/api/sessions/{session_id}")
    async def get_session(session_id: str):
        session = tracer.get_session(session_id)
        if not session:
            raise HTTPException(status_code=404, detail="Session not found")
        return session

    # ==================== Events API ====================

    @app.get("/api/events")
    async def get_events(
            event_type: Optional[str] = None,
            agent_id: Optional[str] = None,
            session_id: Optional[str] = None,
            since_seq: int = 0,
            limit: int = Query(100, ge=1, le=1000)
    ):
        return tracer.get_events(
            event_type=event_type,
            agent_id=agent_id,
            session_id=session_id,
            since_seq=since_seq,
            limit=limit
        )

    # ==================== Agent API ====================

    @app.get("/api/agents")
    async def get_agents(session_id: Optional[str] = None):
        return tracer.get_agents(session_id=session_id)

    @app.get("/api/agents/{agent_id}")
    async def get_agent(agent_id: str):
        agent = tracer.get_agent(agent_id)
        if not agent:
            raise HTTPException(status_code=404, detail="Agent not found")
        return agent

    # ==================== Prompt API ====================

    @app.get("/api/prompts")
    async def get_prompts(
            agent_id: Optional[str] = None,
            session_id: Optional[str] = None
    ):
        return tracer.get_prompts(agent_id=agent_id, session_id=session_id)

    @app.get("/api/prompts/{prompt_id}")
    async def get_prompt(prompt_id: str):
        prompt = tracer.get_prompt(prompt_id)
        if not prompt:
            raise HTTPException(status_code=404, detail="Prompt not found")
        return prompt

    # ==================== LLM Calls API ====================

    @app.get("/api/llm-calls")
    async def get_llm_calls(
            agent_id: Optional[str] = None,
            session_id: Optional[str] = None,
            limit: int = Query(100, ge=1, le=1000)
    ):
        return tracer.get_llm_calls(
            agent_id=agent_id,
            session_id=session_id,
            limit=limit
        )

    @app.get("/api/llm-calls/{call_id}")
    async def get_llm_call(call_id: str):
        call = tracer.get_llm_call(call_id)
        if not call:
            raise HTTPException(status_code=404, detail="LLM call not found")
        return call

    # ==================== Graph & Timeline API ====================

    @app.get("/api/graph")
    async def get_graph(session_id: Optional[str] = None):
        return tracer.get_call_graph(session_id=session_id)

    @app.get("/api/stats")
    async def get_stats():
        return tracer.get_stats()

    @app.get("/api/timeline")
    async def get_timeline(
            agent_id: Optional[str] = None,
            session_id: Optional[str] = None,
            limit: int = Query(200, ge=1, le=1000)
    ):
        return tracer.get_timeline(
            agent_id=agent_id,
            session_id=session_id,
            limit=limit
        )

    # ==================== WebSocket ====================

    @app.websocket("/ws")
    async def websocket_endpoint(ws: WebSocket):
        await ws.accept()

        try:
            # 发送初始数据
            await ws.send_json({
                "type": "init",
                "stats": tracer.get_stats(),
                "sessions": tracer.get_sessions(limit=20),
                "agents": tracer.get_agents(),
                "llm_calls": tracer.get_llm_calls(limit=50),
                "events": tracer.get_events(limit=500),
                "graph": tracer.get_call_graph()
            })

            last_seq = tracer.event_seq

            while True:
                await asyncio.sleep(0.2)
                current_seq = tracer.event_seq

                if current_seq > last_seq:
                    events = tracer.get_events(since_seq=last_seq, limit=100)
                    if events:
                        await ws.send_json({
                            "type": "update",
                            "events": events,
                            "stats": tracer.get_stats(),
                            "sessions": tracer.get_sessions(limit=20),
                            "agents": tracer.get_agents(),
                            "llm_calls": tracer.get_llm_calls(limit=50),
                            "graph": tracer.get_call_graph()
                        })
                    last_seq = current_seq

                # 处理客户端消息
                try:
                    data = await asyncio.wait_for(ws.receive_json(), timeout=0.05)
                    await handle_ws_message(ws, data, tracer)
                except asyncio.TimeoutError:
                    pass

        except WebSocketDisconnect:
            pass
        except Exception as e:
            import traceback
            logger.error(f"WebSocket error: {e}")
            logger.error(traceback.format_exc())

    return app


async def handle_ws_message(ws, data: dict, tracer):
    """处理WebSocket消息"""
    msg_type = data.get("type", "")

    if msg_type == "ping":
        await ws.send_json({"type": "pong"})

    elif msg_type == "get_llm_call":
        call = tracer.get_llm_call(data.get("call_id", ""))
        await ws.send_json({"type": "llm_call_detail", "data": call})

    elif msg_type == "get_session":
        session = tracer.get_session(data.get("session_id", ""))
        await ws.send_json({"type": "session_detail", "data": session})

    elif msg_type == "get_agent":
        agent = tracer.get_agent(data.get("agent_id", ""))
        await ws.send_json({"type": "agent_detail", "data": agent})

    elif msg_type == "get_prompt":
        prompt = tracer.get_prompt(data.get("prompt_id", ""))
        await ws.send_json({"type": "prompt_detail", "data": prompt})

    elif msg_type == "filter_session":
        session_id = data.get("session_id")
        await ws.send_json({
            "type": "filtered_data",
            "session_id": session_id,
            "events": tracer.get_events(session_id=session_id, limit=500),
            "agents": tracer.get_agents(session_id=session_id),
            "llm_calls": tracer.get_llm_calls(session_id=session_id, limit=100),
            "graph": tracer.get_call_graph(session_id=session_id)
        })