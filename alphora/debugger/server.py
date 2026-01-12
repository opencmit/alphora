"""
Alphora Debugger

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

        app = FastAPI(title="Alphora Debugger", version="2.0")
        app.add_middleware(
            CORSMiddleware,
            allow_origins=["*"],
            allow_methods=["*"],
            allow_headers=["*"]
        )

        # ==================== API 端点 ====================

        @app.get("/", response_class=HTMLResponse)
        async def dashboard():
            return DASHBOARD_HTML

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

            # 发送初始数据
            await ws.send_json({
                "type": "init",
                "stats": tracer.get_stats(),
                "agents": tracer.get_agents(),
                "events": tracer.get_events(limit=500),
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
                            await ws.send_json({
                                "type": "update",
                                "events": events,
                                "stats": tracer.get_stats(),
                                "agents": tracer.get_agents(),
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

        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        loop.run_until_complete(server.serve())

    _server_thread = threading.Thread(target=run, daemon=False, name="DebugServer")
    _server_thread.start()
    time.sleep(0.5)


# ==================== 前端页面 ====================

DASHBOARD_HTML = '''
<!DOCTYPE html>
<html lang="zh-CN">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Alphora Debugger v2.1</title>
    <style>
        :root {
            /* 专业浅色主题色板 */
            --bg-body: #f1f5f9;       /* 整体背景 */
            --bg-panel: #ffffff;      /* 面板背景 */
            --bg-hover: #f8fafc;      /* 悬停背景 */
            --bg-active: #e2e8f0;     /* 激活状态 */
            
            --border: #e2e8f0;        /* 边框颜色 */
            --border-hover: #cbd5e1;
            
            --text-main: #0f172a;     /* 主要文字 */
            --text-secondary: #64748b;/* 次要文字 */
            --text-muted: #94a3b8;    /* 弱化文字 */
            
            /* 功能色 - 调和过的专业色调 */
            --brand: #2563eb;         /* 品牌蓝 */
            --brand-light: #eff6ff;
            
            --success: #10b981;       /* 成功绿 */
            --success-light: #ecfdf5;
            
            --warning: #f59e0b;       /* 警告黄 */
            --warning-light: #fffbeb;
            
            --danger: #ef4444;        /* 错误红 */
            --danger-light: #fef2f2;
            
            --purple: #8b5cf6;        /* 辅助紫 */
            --purple-light: #f5f3ff;
            
            --cyan: #06b6d4;
            --orange: #f97316;
            
            --shadow-sm: 0 1px 2px 0 rgb(0 0 0 / 0.05);
            --shadow-md: 0 4px 6px -1px rgb(0 0 0 / 0.1), 0 2px 4px -2px rgb(0 0 0 / 0.1);
        }

        * { margin: 0; padding: 0; box-sizing: border-box; }
        
        body { 
            font-family: 'Inter', -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, "Helvetica Neue", Arial, sans-serif;
            background: var(--bg-body); 
            color: var(--text-main); 
            overflow: hidden;
            font-size: 13px;
            line-height: 1.5;
        }

        /* SVG Icons Style */
        .icon-svg {
            width: 14px;
            height: 14px;
            fill: currentColor;
            vertical-align: middle;
        }
        .icon-svg-lg {
            width: 18px;
            height: 18px;
        }
        
        /* Header */
        header {
            display: flex; justify-content: space-between; align-items: center;
            padding: 0 20px; 
            background: var(--bg-panel); 
            border-bottom: 1px solid var(--border);
            position: fixed; top: 0; left: 0; right: 0; z-index: 100; height: 56px;
            box-shadow: var(--shadow-sm);
        }
        
        .logo { display: flex; align-items: center; gap: 12px; }
        .logo-icon { 
            width: 32px; height: 32px; 
            background: var(--brand); 
            color: white;
            border-radius: 8px; display: flex; align-items: center; justify-content: center; 
        }
        .logo h1 { font-size: 16px; font-weight: 700; letter-spacing: -0.5px; color: var(--text-main); }
        .logo-version { 
            font-size: 11px; color: var(--brand); background: var(--brand-light); 
            padding: 2px 6px; border-radius: 4px; font-weight: 600; margin-left: 6px;
        }
        
        .stats-bar { display: flex; gap: 20px; }
        .stat-item { 
            display: flex; align-items: center; gap: 8px;
            font-size: 12px; color: var(--text-secondary); 
            padding: 4px 0;
        }
        .stat-item .value { font-weight: 600; font-family: 'JetBrains Mono', monospace; font-size: 13px; color: var(--text-main); }
        
        .header-right { display: flex; align-items: center; gap: 16px; }
        .status { display: flex; align-items: center; gap: 6px; font-size: 12px; color: var(--text-secondary); font-weight: 500; }
        .status-dot { width: 8px; height: 8px; border-radius: 50%; background: var(--success); box-shadow: 0 0 0 2px var(--success-light); }
        .status-dot.off { background: var(--danger); box-shadow: 0 0 0 2px var(--danger-light); }
        
        .btn { 
            padding: 8px 16px; border-radius: 6px; border: 1px solid var(--border); 
            font-size: 12px; font-weight: 500; cursor: pointer; 
            background: var(--bg-panel); color: var(--text-main);
            transition: all 0.2s;
            display: inline-flex; align-items: center; gap: 6px;
        }
        .btn:hover { background: var(--bg-hover); border-color: var(--border-hover); }
        .btn-danger { color: var(--danger); border-color: var(--danger-light); background: var(--danger-light); }
        .btn-danger:hover { background: var(--danger); color: white; }
        
        /* Main Layout */
        main { margin-top: 56px; height: calc(100vh - 56px); display: flex; }
        
        /* Sidebar */
        .sidebar {
            width: 260px; background: var(--bg-panel); border-right: 1px solid var(--border);
            display: flex; flex-direction: column; flex-shrink: 0;
            z-index: 10;
        }
        .sidebar-section { padding: 16px; border-bottom: 1px solid var(--border); }
        .sidebar-title { 
            font-size: 11px; text-transform: uppercase; color: var(--text-muted); 
            margin-bottom: 12px; font-weight: 700; letter-spacing: 0.5px;
        }
        
        .agent-list { max-height: 240px; overflow-y: auto; }
        .agent-item {
            display: flex; align-items: center; gap: 10px; padding: 10px 12px;
            border-radius: 8px; cursor: pointer; margin-bottom: 4px;
            transition: all 0.15s; border: 1px solid transparent;
        }
        .agent-item:hover { background: var(--bg-hover); border-color: var(--border); }
        .agent-item.selected { background: var(--brand-light); border-color: var(--brand); }
        .agent-icon { 
            width: 32px; height: 32px; border-radius: 6px; 
            display: flex; align-items: center; justify-content: center;
            background: var(--bg-body); color: var(--text-secondary);
        }
        .agent-item.selected .agent-icon { background: white; color: var(--brand); }
        
        .agent-info { flex: 1; min-width: 0; }
        .agent-name { font-size: 13px; font-weight: 600; color: var(--text-main); white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
        .agent-id { font-size: 11px; color: var(--text-secondary); font-family: 'JetBrains Mono', monospace; }
        .agent-badge { 
            font-size: 10px; padding: 2px 6px; border-radius: 10px; font-weight: 600;
            background: var(--success-light); color: var(--success); border: 1px solid rgba(16, 185, 129, 0.1);
        }
        
        .filter-group { display: flex; flex-wrap: wrap; gap: 6px; }
        .filter-btn {
            padding: 5px 10px; border-radius: 6px; font-size: 11px; font-weight: 500;
            background: var(--bg-body); border: 1px solid transparent; color: var(--text-secondary); cursor: pointer;
        }
        .filter-btn:hover { background: var(--bg-active); }
        .filter-btn.active { background: var(--brand); color: white; box-shadow: var(--shadow-sm); }
        
        /* Graph Panel */
        .graph-panel { 
            flex: 1; position: relative; background: var(--bg-body); 
            display: flex; flex-direction: column; overflow: hidden;
        }
        .graph-header {
            display: flex; justify-content: space-between; align-items: center;
            padding: 12px 20px; background: var(--bg-panel); border-bottom: 1px solid var(--border);
        }
        .graph-tabs { display: flex; gap: 4px; background: var(--bg-body); padding: 4px; border-radius: 8px; }
        .graph-tab {
            padding: 6px 16px; border-radius: 6px; font-size: 12px; font-weight: 600;
            background: transparent; border: none; color: var(--text-secondary); cursor: pointer;
        }
        .graph-tab:hover { color: var(--text-main); }
        .graph-tab.active { background: var(--bg-panel); color: var(--brand); box-shadow: var(--shadow-sm); }
        
        .graph-content { flex: 1; overflow: hidden; position: relative; background-image: radial-gradient(#cbd5e1 1px, transparent 1px); background-size: 20px 20px; }
        #graphSvg { width: 100%; height: 100%; }
        
        /* Node Styles */
        .node-group { cursor: pointer; transition: transform 0.2s; }
        .node-group:hover { transform: scale(1.02); }
        .node-box { fill: var(--bg-panel); stroke: var(--border); stroke-width: 1.5; rx: 8; filter: drop-shadow(0 2px 4px rgba(0,0,0,0.05)); }
        .node-box.selected { stroke: var(--brand); stroke-width: 2; filter: drop-shadow(0 0 0 4px var(--brand-light)); }
        .node-header { fill: var(--bg-body); }
        .node-icon-container { fill: var(--text-secondary); }
        .node-title { fill: var(--text-main); font-size: 12px; font-weight: 600; font-family: 'Inter', sans-serif; }
        .node-sub { fill: var(--text-muted); font-size: 10px; font-family: 'JetBrains Mono', monospace; }
        .node-stat { font-size: 10px; fill: var(--text-secondary); font-family: 'Inter', sans-serif; }
        
        .edge-line { stroke: var(--border-hover); stroke-width: 2; fill: none; }
        .edge-line.derive { stroke: var(--orange); stroke-dasharray: 4,4; }
        .edge-line.llm { stroke: var(--success); }
        
        /* Timeline View */
        .timeline-container { 
            flex: 1; overflow-y: auto; padding: 20px;
            display: none; background: var(--bg-body);
        }
        .timeline-container.active { display: block; }
        
        .timeline-item {
            display: flex; gap: 16px; padding: 12px 0;
            border-left: 2px solid var(--border); margin-left: 10px; padding-left: 20px;
            position: relative;
        }
        .timeline-item::before {
            content: ''; position: absolute; left: -6px; top: 16px;
            width: 10px; height: 10px; border-radius: 50%; background: var(--bg-panel);
            border: 2px solid var(--border); box-shadow: 0 0 0 4px var(--bg-body);
        }
        .timeline-item:hover::before { transform: scale(1.2); transition: transform 0.2s; }
        
        .timeline-item.llm_call_start::before { border-color: var(--brand); background: var(--brand); }
        .timeline-item.llm_call_end::before { border-color: var(--success); background: var(--success); }
        .timeline-item.llm_call_error::before { border-color: var(--danger); background: var(--danger); }
        .timeline-item.agent_created::before { border-color: var(--purple); background: var(--bg-panel); }
        .timeline-item.memory_add::before { border-color: var(--warning); background: var(--bg-panel); }
        
        .timeline-time { 
            font-size: 11px; color: var(--text-muted); font-family: 'JetBrains Mono', monospace;
            width: 60px; flex-shrink: 0; padding-top: 2px;
        }
        .timeline-content { 
            flex: 1; background: var(--bg-panel); padding: 12px; 
            border-radius: 8px; border: 1px solid var(--border);
            box-shadow: var(--shadow-sm);
        }
        .timeline-title { 
            font-size: 13px; font-weight: 600; margin-bottom: 6px; 
            display: flex; align-items: center; justify-content: space-between;
        }
        .timeline-detail { font-size: 12px; color: var(--text-secondary); line-height: 1.5; }
        .timeline-tag {
            display: inline-flex; align-items: center; gap: 4px;
            font-size: 10px; padding: 2px 8px; font-weight: 600;
            border-radius: 4px; background: var(--bg-body); color: var(--text-secondary);
        }
        
        /* Right Panel */
        .detail-panel {
            width: 400px; background: var(--bg-panel); border-left: 1px solid var(--border);
            display: flex; flex-direction: column; flex-shrink: 0;
            box-shadow: -4px 0 16px rgba(0,0,0,0.02);
        }
        .detail-header {
            padding: 16px 20px; border-bottom: 1px solid var(--border);
            display: flex; justify-content: space-between; align-items: center;
        }
        .detail-title { font-size: 14px; font-weight: 700; color: var(--text-main); }
        .detail-close { 
            background: none; border: none; color: var(--text-muted); 
            cursor: pointer; padding: 4px; border-radius: 4px;
        }
        .detail-close:hover { background: var(--bg-body); color: var(--text-main); }
        
        .detail-content { flex: 1; overflow-y: auto; padding: 20px; }
        
        .detail-section { margin-bottom: 24px; }
        .detail-section-title {
            font-size: 11px; text-transform: uppercase; color: var(--text-muted);
            margin-bottom: 12px; font-weight: 700; letter-spacing: 0.5px;
            border-left: 3px solid var(--brand); padding-left: 8px;
        }
        
        .detail-grid { display: grid; grid-template-columns: 1fr 1fr; gap: 12px; }
        .detail-item { 
            background: var(--bg-body); border-radius: 8px; padding: 12px; border: 1px solid var(--border);
        }
        .detail-item.full { grid-column: 1 / -1; }
        .detail-label { font-size: 11px; color: var(--text-muted); margin-bottom: 6px; }
        .detail-value { font-size: 13px; font-family: 'JetBrains Mono', monospace; font-weight: 500; color: var(--text-main); word-break: break-all; }
        .detail-value.large { font-size: 18px; font-weight: 600; font-family: 'Inter', sans-serif; }
        
        .code-block {
            background: var(--bg-body); border-radius: 8px; padding: 12px;
            font-family: 'JetBrains Mono', 'Menlo', monospace; font-size: 12px;
            line-height: 1.6; max-height: 300px; overflow-y: auto;
            white-space: pre-wrap; word-break: break-all; color: var(--text-secondary);
            border: 1px solid var(--border);
        }
        .code-block.messages { max-height: 400px; background: white; }
        
        .message-item {
            margin-bottom: 12px; padding: 12px; border-radius: 8px;
            border: 1px solid var(--border); background: var(--bg-body);
        }
        .message-role {
            font-size: 10px; font-weight: 700; margin-bottom: 6px;
            text-transform: uppercase; display: inline-block; padding: 2px 6px; border-radius: 4px;
        }
        .message-role.system { background: var(--purple-light); color: var(--purple); }
        .message-role.user { background: var(--brand-light); color: var(--brand); }
        .message-role.assistant { background: var(--success-light); color: var(--success); }
        .message-content { font-size: 12px; color: var(--text-main); white-space: pre-wrap; line-height: 1.6; }
        
        /* Token Stats */
        .token-bar {
            display: flex; height: 8px; border-radius: 4px; overflow: hidden;
            background: var(--bg-active); margin-top: 8px;
        }
        .token-bar-segment { height: 100%; }
        .token-bar-segment.prompt { background: var(--brand); }
        .token-bar-segment.completion { background: var(--success); }
        
        /* Empty State */
        .empty-state {
            display: flex; flex-direction: column; align-items: center; 
            justify-content: center; height: 100%; color: var(--text-muted); gap: 12px;
        }
        .empty-state-svg { width: 48px; height: 48px; fill: var(--bg-active); }
        
        /* Scrollbar */
        ::-webkit-scrollbar { width: 6px; height: 6px; }
        ::-webkit-scrollbar-track { background: transparent; }
        ::-webkit-scrollbar-thumb { background: #cbd5e1; border-radius: 3px; }
        ::-webkit-scrollbar-thumb:hover { background: #94a3b8; }
        
        /* Animations */
        @keyframes fadeIn { from { opacity: 0; transform: translateY(5px); } to { opacity: 1; transform: translateY(0); } }
        .fade-in { animation: fadeIn 0.2s ease-out; }
    </style>
</head>
<body>
    <svg style="display: none;">
        <symbol id="icon-cpu" viewBox="0 0 24 24"><path d="M4 4h16v16H4z" fill="none" stroke="currentColor" stroke-width="2"/><path d="M9 9h6v6H9z" fill="currentColor" opacity="0.2"/><path d="M9 4v-2m6 2v-2m4 6h2m-2 6h2m-6 4v2m-6-2v2m-4-6h-2m2-6h-2" stroke="currentColor" stroke-width="2"/></symbol>
        <symbol id="icon-message" viewBox="0 0 24 24"><path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z" fill="none" stroke="currentColor" stroke-width="2"/></symbol>
        <symbol id="icon-search" viewBox="0 0 24 24"><circle cx="11" cy="11" r="8" fill="none" stroke="currentColor" stroke-width="2"/><line x1="21" y1="21" x2="16.65" y2="16.65" stroke="currentColor" stroke-width="2"/></symbol>
        <symbol id="icon-code" viewBox="0 0 24 24"><polyline points="16 18 22 12 16 6" fill="none" stroke="currentColor" stroke-width="2"/><polyline points="8 6 2 12 8 18" fill="none" stroke="currentColor" stroke-width="2"/></symbol>
        <symbol id="icon-tool" viewBox="0 0 24 24"><path d="M14.7 6.3a1 1 0 0 0 0 1.4l1.6 1.6a1 1 0 0 0 1.4 0l3.77-3.77a6 6 0 0 1-7.94 7.94l-6.91 6.91a2.12 2.12 0 0 1-3-3l6.91-6.91a6 6 0 0 1 7.94-7.94l-3.76 3.76z" fill="none" stroke="currentColor" stroke-width="2"/></symbol>
        <symbol id="icon-database" viewBox="0 0 24 24"><ellipse cx="12" cy="5" rx="9" ry="3" fill="none" stroke="currentColor" stroke-width="2"/><path d="M21 12c0 1.66-4 3-9 3s-9-1.34-9-3" fill="none" stroke="currentColor" stroke-width="2"/><path d="M3 5v14c0 1.66 4 3 9 3s9-1.34 9-3V5" fill="none" stroke="currentColor" stroke-width="2"/></symbol>
        <symbol id="icon-play" viewBox="0 0 24 24"><polygon points="5 3 19 12 5 21 5 3" fill="currentColor"/></symbol>
        <symbol id="icon-check" viewBox="0 0 24 24"><polyline points="20 6 9 17 4 12" fill="none" stroke="currentColor" stroke-width="2"/></symbol>
        <symbol id="icon-alert" viewBox="0 0 24 24"><circle cx="12" cy="12" r="10" fill="none" stroke="currentColor" stroke-width="2"/><line x1="12" y1="8" x2="12" y2="12" stroke="currentColor" stroke-width="2"/><line x1="12" y1="16" x2="12.01" y2="16" stroke="currentColor" stroke-width="2"/></symbol>
        <symbol id="icon-clock" viewBox="0 0 24 24"><circle cx="12" cy="12" r="10" fill="none" stroke="currentColor" stroke-width="2"/><polyline points="12 6 12 12 16 14" fill="none" stroke="currentColor" stroke-width="2"/></symbol>
    </svg>

    <header>
        <div class="logo">
            <div class="logo-icon"><svg class="icon-svg-lg"><use href="#icon-search"/></svg></div>
            <h1>Alphora Debugger <span class="logo-version">v2.1</span></h1>
        </div>
        <div class="stats-bar">
            <div class="stat-item">
                <span style="color: var(--brand)">Active Agents:</span>
                <span class="value" id="statAgents">0</span>
            </div>
            <div class="stat-item">
                <span style="color: var(--success)">LLM Calls:</span>
                <span class="value" id="statCalls">0</span>
            </div>
            <div class="stat-item">
                <span style="color: var(--warning)">Tokens:</span>
                <span class="value" id="statTokens">0</span>
            </div>
            <div class="stat-item">
                <span style="color: var(--purple)">TPS:</span>
                <span class="value" id="statTPS">0</span>
            </div>
            <div class="stat-item">
                <span style="color: var(--danger)">Errors:</span>
                <span class="value" id="statErrors">0</span>
            </div>
        </div>
        <div class="header-right">
            <div class="status">
                <div class="status-dot" id="statusDot"></div>
                <span id="statusText">Connecting...</span>
            </div>
            <button class="btn btn-danger" onclick="clearData()">
                <svg class="icon-svg"><use href="#icon-alert"/></svg> Clear
            </button>
        </div>
    </header>
    
    <main>
        <div class="sidebar">
            <div class="sidebar-section">
                <div class="sidebar-title">Agents</div>
                <div class="agent-list" id="agentList">
                    </div>
            </div>
            <div class="sidebar-section">
                <div class="sidebar-title">Filters</div>
                <div class="filter-group" id="eventFilters">
                    <button class="filter-btn active" data-filter="all">All</button>
                    <button class="filter-btn" data-filter="llm">LLM</button>
                    <button class="filter-btn" data-filter="agent">Agent</button>
                    <button class="filter-btn" data-filter="memory">Memory</button>
                    <button class="filter-btn" data-filter="tool">Tool</button>
                    <button class="filter-btn" data-filter="error">Error</button>
                </div>
            </div>
            <div class="sidebar-section" style="flex: 1; display: flex; flex-direction: column;">
                <div class="sidebar-title">Recent LLM Activity</div>
                <div class="agent-list" id="llmCallList" style="flex: 1;">
                    </div>
            </div>
        </div>
        
        <div class="graph-panel">
            <div class="graph-header">
                <div class="graph-tabs">
                    <button class="graph-tab active" data-view="graph">Topology</button>
                    <button class="graph-tab" data-view="timeline">Timeline</button>
                </div>
                <div style="font-size: 11px; color: var(--text-secondary); font-family: 'JetBrains Mono';">
                    Total Events: <span id="eventCount" style="color: var(--text-main); font-weight: 600;">0</span>
                </div>
            </div>
            
            <div class="graph-content" id="graphView">
                <svg id="graphSvg">
                    <defs>
                        <marker id="arrowhead" markerWidth="10" markerHeight="7" refX="9" refY="3.5" orient="auto">
                            <polygon points="0 0, 10 3.5, 0 7" fill="#cbd5e1"/>
                        </marker>
                        <marker id="arrowhead-derive" markerWidth="10" markerHeight="7" refX="9" refY="3.5" orient="auto">
                            <polygon points="0 0, 10 3.5, 0 7" fill="#f97316"/>
                        </marker>
                    </defs>
                    <g id="graphEdges"></g>
                    <g id="graphNodes"></g>
                </svg>
            </div>
            
            <div class="timeline-container" id="timelineView">
                </div>
        </div>
        
        <div class="detail-panel" id="detailPanel">
            <div class="detail-header">
                <div class="detail-title" id="detailTitle">Details</div>
                <button class="detail-close" onclick="closeDetail()">×</button>
            </div>
            <div class="detail-content" id="detailContent">
                <div class="empty-state">
                    <svg class="empty-state-svg" viewBox="0 0 24 24"><path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z" fill="none" stroke="currentColor" stroke-width="2"/><polyline points="14 2 14 8 20 8" fill="none" stroke="currentColor" stroke-width="2"/><line x1="16" y1="13" x2="8" y2="13" stroke="currentColor" stroke-width="2"/><line x1="16" y1="17" x2="8" y2="17" stroke="currentColor" stroke-width="2"/><polyline points="10 9 9 9 8 9" fill="none" stroke="currentColor" stroke-width="2"/></svg>
                    <div>Select an event or node</div>
                </div>
            </div>
        </div>
    </main>
    
    <script>
        // ==================== State ====================
        let ws = null;
        let events = [];
        let agents = {};
        let graphData = { nodes: [], edges: [] };
        let selectedAgent = null;
        let currentView = 'graph';
        let currentFilter = 'all';
        
        // Professional Color Palette Mappings
        const agentColors = ['#2563eb', '#10b981', '#f59e0b', '#ef4444', '#8b5cf6', '#06b6d4', '#f97316', '#ec4899'];
        
        // ==================== Icons Helper ====================
        const ICONS = {
            agent: '<svg class="icon-svg"><use href="#icon-cpu"/></svg>',
            chat: '<svg class="icon-svg"><use href="#icon-message"/></svg>',
            search: '<svg class="icon-svg"><use href="#icon-search"/></svg>',
            code: '<svg class="icon-svg"><use href="#icon-code"/></svg>',
            tool: '<svg class="icon-svg"><use href="#icon-tool"/></svg>',
            rag: '<svg class="icon-svg"><use href="#icon-database"/></svg>',
            play: '<svg class="icon-svg"><use href="#icon-play"/></svg>',
            check: '<svg class="icon-svg"><use href="#icon-check"/></svg>',
            alert: '<svg class="icon-svg"><use href="#icon-alert"/></svg>',
            clock: '<svg class="icon-svg"><use href="#icon-clock"/></svg>'
        };

        function getAgentIconHtml(type) {
            if (!type) return ICONS.agent;
            const lower = type.toLowerCase();
            if (lower.includes('trans')) return ICONS.agent;
            if (lower.includes('chat')) return ICONS.chat;
            if (lower.includes('search')) return ICONS.search;
            if (lower.includes('code')) return ICONS.code;
            if (lower.includes('tool')) return ICONS.tool;
            if (lower.includes('rag')) return ICONS.rag;
            return ICONS.agent;
        }

        // ==================== Init ====================
        function init() {
            connectWS();
            setupEventListeners();
            window.addEventListener('resize', () => {
                if (currentView === 'graph') renderGraph();
            });
        }
        
        function setupEventListeners() {
            document.querySelectorAll('.graph-tab').forEach(tab => {
                tab.onclick = () => {
                    document.querySelectorAll('.graph-tab').forEach(t => t.classList.remove('active'));
                    tab.classList.add('active');
                    currentView = tab.dataset.view;
                    
                    document.getElementById('graphView').style.display = currentView === 'graph' ? 'block' : 'none';
                    document.getElementById('timelineView').classList.toggle('active', currentView === 'timeline');
                    
                    if (currentView === 'graph') renderGraph();
                    else renderTimeline();
                };
            });
            
            document.querySelectorAll('.filter-btn').forEach(btn => {
                btn.onclick = () => {
                    document.querySelectorAll('.filter-btn').forEach(b => b.classList.remove('active'));
                    btn.classList.add('active');
                    currentFilter = btn.dataset.filter;
                    renderTimeline();
                };
            });
        }
        
        // ==================== WebSocket ====================
        function connectWS() {
            const proto = location.protocol === 'https:' ? 'wss:' : 'ws:';
            ws = new WebSocket(`${proto}//${location.host}/ws`);
            
            ws.onopen = () => {
                document.getElementById('statusDot').classList.remove('off');
                document.getElementById('statusText').textContent = 'Connected';
            };
            
            ws.onclose = () => {
                document.getElementById('statusDot').classList.add('off');
                document.getElementById('statusText').textContent = 'Disconnected';
                setTimeout(connectWS, 2000);
            };
            
            ws.onmessage = (e) => {
                const msg = JSON.parse(e.data);
                if (msg.type === 'init' || msg.type === 'update') {
                    if (msg.stats) updateStats(msg.stats);
                    if (msg.agents) processAgents(msg.agents);
                    if (msg.events) {
                         if(msg.type === 'init') events = msg.events;
                         else msg.events.forEach(ev => events.push(ev));
                    }
                    if (msg.graph) graphData = msg.graph;
                    renderAll();
                } else if (msg.type === 'llm_call_detail') {
                    showLLMCallDetail(msg.data);
                }
            };
        }
        
        function processAgents(agentList) {
            agentList.forEach(a => agents[a.agent_id] = a);
        }
        
        // ==================== Stats ====================
        function updateStats(s) {
            document.getElementById('statAgents').textContent = s.active_agents || 0;
            document.getElementById('statCalls').textContent = s.total_llm_calls || 0;
            document.getElementById('statTokens').textContent = formatNumber(s.total_tokens || 0);
            document.getElementById('statTPS').textContent = (s.avg_tokens_per_second || 0).toFixed(1);
            document.getElementById('statErrors').textContent = s.errors || 0;
            document.getElementById('eventCount').textContent = s.total_events || 0;
        }
        
        function formatNumber(n) {
            if (n >= 1000000) return (n / 1000000).toFixed(1) + 'M';
            if (n >= 1000) return (n / 1000).toFixed(1) + 'K';
            return n.toString();
        }
        
        // ==================== Render ====================
        function renderAll() {
            renderAgentList();
            renderLLMCallList();
            if (currentView === 'graph') renderGraph();
            else renderTimeline();
        }
        
        function renderAgentList() {
            const container = document.getElementById('agentList');
            const agentList = Object.values(agents);
            
            if (agentList.length === 0) {
                container.innerHTML = '<div class="empty-state" style="height:100px; font-size:12px;">No Active Agents</div>';
                return;
            }
            
            container.innerHTML = agentList.map((agent, idx) => {
                const callCount = events.filter(e => 
                    e.agent_id === agent.agent_id && e.event_type === 'llm_call_end'
                ).length;
                
                return `
                    <div class="agent-item ${selectedAgent === agent.agent_id ? 'selected' : ''}" 
                         onclick="selectAgent('${agent.agent_id}')">
                        <div class="agent-icon">
                            ${getAgentIconHtml(agent.agent_type)}
                        </div>
                        <div class="agent-info">
                            <div class="agent-name">${agent.agent_type}</div>
                            <div class="agent-id">${agent.agent_id.slice(0, 8)}</div>
                        </div>
                        ${callCount > 0 ? `<div class="agent-badge">${callCount}</div>` : ''}
                    </div>
                `;
            }).join('');
        }
        
        function renderLLMCallList() {
            const container = document.getElementById('llmCallList');
            const calls = events
                .filter(e => e.event_type === 'llm_call_end')
                .slice(-10)
                .reverse();
            
            if (calls.length === 0) {
                container.innerHTML = '<div class="empty-state" style="height:100px; font-size:12px;">No Recent Calls</div>';
                return;
            }
            
            container.innerHTML = calls.map(call => {
                const data = call.data || {};
                return `
                    <div class="agent-item" onclick="showLLMCallById('${data.call_id}')">
                        <div class="agent-icon" style="color: var(--success); background: var(--success-light);">
                            ${ICONS.chat}
                        </div>
                        <div class="agent-info">
                            <div class="agent-name">${data.output_preview?.slice(0, 30) || 'LLM Call'}</div>
                            <div class="agent-id">${data.duration_ms?.toFixed(0) || 0}ms | ${data.token_usage?.total_tokens || 0} toks</div>
                        </div>
                    </div>
                `;
            }).join('');
        }
        
        // ==================== Graph ====================
        function renderGraph() {
            const svg = document.getElementById('graphSvg');
            const nodesG = document.getElementById('graphNodes');
            const edgesG = document.getElementById('graphEdges');
            
            nodesG.innerHTML = '';
            edgesG.innerHTML = '';
            
            const nodes = graphData.nodes || [];
            const edges = graphData.edges || [];
            
            if (nodes.length === 0) return;
            
            const width = svg.clientWidth;
            const height = svg.clientHeight;
            const nodeWidth = 180;
            const nodeHeight = 70;
            const padding = 60;
            
            // Simple Level Layout Algorithm
            const levels = {};
            const processed = new Set();
            const childIds = new Set(edges.filter(e => e.type === 'derive').map(e => e.target));
            const roots = nodes.filter(n => !childIds.has(n.id));
            
            function assignLevel(node, level) {
                if (processed.has(node.id)) return;
                processed.add(node.id);
                if (!levels[level]) levels[level] = [];
                levels[level].push(node);
                edges.filter(e => e.source === node.id && e.type === 'derive')
                    .forEach(e => {
                        const child = nodes.find(n => n.id === e.target);
                        if (child) assignLevel(child, level + 1);
                    });
            }
            
            roots.forEach(r => assignLevel(r, 0));
            nodes.filter(n => !processed.has(n.id)).forEach(n => assignLevel(n, 0));
            
            const levelCount = Object.keys(levels).length;
            const positions = {};
            
            Object.entries(levels).forEach(([level, nodesInLevel]) => {
                const l = parseInt(level);
                const y = padding + (height - 2 * padding) / Math.max(levelCount, 1) * l + nodeHeight / 2;
                nodesInLevel.forEach((node, i) => {
                    const x = padding + (width - 2 * padding) / (nodesInLevel.length + 1) * (i + 1);
                    positions[node.id] = { x, y, node };
                });
            });
            
            // Draw Edges
            edges.forEach(edge => {
                const from = positions[edge.source];
                const to = positions[edge.target];
                if (!from || !to) return;
                
                const path = document.createElementNS('http://www.w3.org/2000/svg', 'path');
                const startY = from.y + nodeHeight / 2;
                const endY = to.y - nodeHeight / 2;
                const midY = (startY + endY) / 2;
                
                path.setAttribute('d', `M ${from.x} ${startY} C ${from.x} ${midY}, ${to.x} ${midY}, ${to.x} ${endY}`);
                path.setAttribute('class', `edge-line ${edge.type}`);
                path.setAttribute('marker-end', edge.type === 'derive' ? 'url(#arrowhead-derive)' : 'url(#arrowhead)');
                edgesG.appendChild(path);
            });
            
            // Draw Nodes
            Object.values(positions).forEach((pos, idx) => {
                const { x, y, node } = pos;
                const color = agentColors[idx % agentColors.length];
                const data = node.data || {};
                
                const g = document.createElementNS('http://www.w3.org/2000/svg', 'g');
                g.setAttribute('class', 'node-group');
                g.setAttribute('transform', `translate(${x - nodeWidth/2}, ${y - nodeHeight/2})`);
                
                g.innerHTML = `
                    <rect class="node-box ${selectedAgent === node.id ? 'selected' : ''}" 
                          width="${nodeWidth}" height="${nodeHeight}" 
                          style="${selectedAgent === node.id ? `stroke: ${color};` : ''}"/>
                    <rect class="node-header" x="0" y="0" width="${nodeWidth}" height="24" rx="8" 
                          style="clip-path: inset(0 0 4px 0 round 8px 8px 0 0); fill: ${color}20;"/>
                    
                    <text class="node-title" x="12" y="17" style="fill:${color}">${node.label || 'Agent'}</text>
                    <text class="node-sub" x="12" y="40">${node.id.slice(0, 12)}...</text>
                    <text class="node-stat" x="12" y="58">
                        <tspan font-weight="600">${data.llm_call_count || 0}</tspan> calls · 
                        ${formatNumber(data.total_tokens || 0)} toks
                    </text>
                `;
                
                g.onclick = () => selectAgent(node.id);
                nodesG.appendChild(g);
            });
        }
        
        // ==================== Timeline ====================
        function renderTimeline() {
            const container = document.getElementById('timelineView');
            let filtered = [...events];
            
            if (selectedAgent) filtered = filtered.filter(e => e.agent_id === selectedAgent);
            
            if (currentFilter !== 'all') {
                const filterMap = {
                    'llm': ['llm_call_start', 'llm_call_end', 'llm_call_error'],
                    'agent': ['agent_created', 'agent_derived', 'prompt_created'],
                    'memory': ['memory_add', 'memory_retrieve', 'memory_search', 'memory_clear'],
                    'tool': ['tool_call_start', 'tool_call_end', 'tool_call_error'],
                    'error': ['llm_call_error', 'tool_call_error', 'error']
                };
                const types = filterMap[currentFilter] || [];
                filtered = filtered.filter(e => types.includes(e.event_type));
            }
            
            if (filtered.length === 0) {
                container.innerHTML = '<div class="empty-state"><div>No Events</div></div>';
                return;
            }
            
            container.innerHTML = filtered.slice(-100).map(ev => {
                const info = getEventDisplayInfo(ev);
                const time = new Date(ev.timestamp * 1000).toLocaleTimeString('zh-CN', { hour12: false });
                
                return `
                    <div class="timeline-item ${ev.event_type} fade-in" 
                         onclick="showEventDetail('${ev.event_id}', ${JSON.stringify(ev).replace(/"/g, '&quot;')})">
                        <div class="timeline-time">${time}</div>
                        <div class="timeline-content">
                            <div class="timeline-title">
                                <span class="timeline-tag" style="background: ${info.color}15; color: ${info.color}">
                                    ${info.icon} ${info.type}
                                </span>
                                ${ev.duration_ms ? `<span class="timeline-tag">${ev.duration_ms.toFixed(0)}ms</span>` : ''}
                            </div>
                            <div class="timeline-detail">${info.detail}</div>
                        </div>
                    </div>
                `;
            }).join('');
        }
        
        function getEventDisplayInfo(ev) {
            const d = ev.data || {};
            // Using SVGs from ICONS constant for consistent look
            const typeMap = {
                'agent_created': { icon: ICONS.agent, type: 'Agent Created', color: 'var(--purple)', detail: d.agent_type || '' },
                'agent_derived': { icon: ICONS.agent, type: 'Agent Forked', color: 'var(--orange)', detail: `→ ${d.child_type || ''}` },
                'llm_call_start': { icon: ICONS.play, type: 'LLM Start', color: 'var(--brand)', detail: d.input_preview?.slice(0, 80) || d.model_name || '' },
                'llm_call_end': { icon: ICONS.check, type: 'LLM Complete', color: 'var(--success)', detail: `${d.token_usage?.total_tokens || 0} tokens - ${d.output_preview?.slice(0, 60) || ''}` },
                'llm_call_error': { icon: ICONS.alert, type: 'LLM Error', color: 'var(--danger)', detail: d.error?.slice(0, 60) || '' },
                'prompt_created': { icon: ICONS.code, type: 'Prompt Built', color: 'var(--cyan)', detail: d.system_prompt_preview?.slice(0, 60) || '' },
                'memory_add': { icon: ICONS.rag, type: 'Memory Saved', color: 'var(--warning)', detail: `[${d.role}] ${d.content_preview?.slice(0, 50) || ''}` },
                'memory_retrieve': { icon: ICONS.search, type: 'Retrieval', color: 'var(--warning)', detail: `${d.message_count || 0} messages` },
                'tool_call_start': { icon: ICONS.tool, type: 'Tool Start', color: '#ec4899', detail: d.tool_name || '' },
                'tool_call_end': { icon: ICONS.check, type: 'Tool Done', color: '#ec4899', detail: d.result_preview?.slice(0, 60) || '' },
                'error': { icon: ICONS.alert, type: 'System Error', color: 'var(--danger)', detail: d.error?.slice(0, 60) || '' }
            };
            
            return typeMap[ev.event_type] || { icon: ICONS.agent, type: ev.event_type, color: 'var(--text-secondary)', detail: JSON.stringify(d).slice(0, 50) };
        }
        
        // ==================== Detail Panel ====================
        function selectAgent(agentId) {
            selectedAgent = selectedAgent === agentId ? null : agentId;
            renderAll();
            if (selectedAgent && agents[selectedAgent]) showAgentDetail(agents[selectedAgent]);
            else closeDetail();
        }
        
        function showAgentDetail(agent) {
            document.getElementById('detailTitle').textContent = agent.agent_type;
            const agentEvents = events.filter(e => e.agent_id === agent.agent_id);
            const llmCalls = agentEvents.filter(e => e.event_type === 'llm_call_end');
            const totalTokens = llmCalls.reduce((sum, e) => sum + (e.data?.token_usage?.total_tokens || 0), 0);
            
            document.getElementById('detailContent').innerHTML = `
                <div class="detail-section">
                    <div class="detail-section-title">Overview</div>
                    <div class="detail-grid">
                        <div class="detail-item">
                            <div class="detail-label">Agent ID</div>
                            <div class="detail-value">${agent.agent_id.slice(0, 16)}...</div>
                        </div>
                        <div class="detail-item">
                            <div class="detail-label">Model</div>
                            <div class="detail-value">${agent.llm_info?.model_name || 'N/A'}</div>
                        </div>
                    </div>
                </div>
                
                <div class="detail-section">
                    <div class="detail-section-title">Metrics</div>
                    <div class="detail-grid">
                        <div class="detail-item">
                            <div class="detail-label">LLM Calls</div>
                            <div class="detail-value large" style="color: var(--success)">${llmCalls.length}</div>
                        </div>
                        <div class="detail-item">
                            <div class="detail-label">Total Tokens</div>
                            <div class="detail-value large" style="color: var(--warning)">${formatNumber(totalTokens)}</div>
                        </div>
                    </div>
                </div>
                
                ${agent.llm_info ? `
                <div class="detail-section">
                    <div class="detail-section-title">Configuration</div>
                    <div class="code-block">${JSON.stringify(agent.llm_info, null, 2)}</div>
                </div>
                ` : ''}
            `;
        }
        
        function showLLMCallById(callId) {
            if (ws && ws.readyState === WebSocket.OPEN) {
                ws.send(JSON.stringify({ type: 'get_llm_call', call_id: callId }));
            }
        }
        
        function showLLMCallDetail(call) {
            if (!call) return;
            document.getElementById('detailTitle').textContent = 'LLM Call Details';
            const promptRatio = call.total_tokens > 0 ? (call.prompt_tokens / call.total_tokens * 100) : 0;
            
            document.getElementById('detailContent').innerHTML = `
                <div class="detail-section">
                    <div class="detail-section-title">Performance</div>
                    <div class="detail-grid">
                        <div class="detail-item">
                            <div class="detail-label">Duration</div>
                            <div class="detail-value large" style="color: var(--brand)">${call.duration_ms?.toFixed(0) || 0}ms</div>
                        </div>
                        <div class="detail-item">
                            <div class="detail-label">Speed</div>
                            <div class="detail-value large" style="color: var(--purple)">${call.tokens_per_second?.toFixed(1) || 0} TPS</div>
                        </div>
                    </div>
                </div>
                
                <div class="detail-section">
                    <div class="detail-section-title">Token Usage</div>
                    <div class="detail-grid">
                        <div class="detail-item">
                            <div class="detail-label">Prompt</div>
                            <div class="detail-value" style="color: var(--brand)">${formatNumber(call.prompt_tokens || 0)}</div>
                        </div>
                        <div class="detail-item">
                            <div class="detail-label">Completion</div>
                            <div class="detail-value" style="color: var(--success)">${formatNumber(call.completion_tokens || 0)}</div>
                        </div>
                        <div class="detail-item full">
                            <div class="detail-label">Total: ${formatNumber(call.total_tokens || 0)}</div>
                            <div class="token-bar">
                                <div class="token-bar-segment prompt" style="width: ${promptRatio}%"></div>
                                <div class="token-bar-segment completion" style="width: ${100 - promptRatio}%"></div>
                            </div>
                        </div>
                    </div>
                </div>
                
                ${call.request_messages?.length > 0 ? `
                <div class="detail-section">
                    <div class="detail-section-title">Input Messages (${call.request_messages.length})</div>
                    <div class="code-block messages">
                        ${call.request_messages.map(msg => `
                            <div class="message-item">
                                <div class="message-role ${msg.role}">${msg.role}</div>
                                <div class="message-content">${escapeHtml(msg.content || '')}</div>
                            </div>
                        `).join('')}
                    </div>
                </div>
                ` : ''}
                
                <div class="detail-section">
                    <div class="detail-section-title">Output</div>
                    <div class="code-block" style="background: var(--bg-hover); border-left: 3px solid var(--success);">${escapeHtml(call.response_text || '')}</div>
                </div>
                
                ${call.error ? `
                <div class="detail-section">
                    <div class="detail-section-title" style="color: var(--danger)">Error</div>
                    <div class="code-block" style="color: var(--danger); border-color: var(--danger-light);">${escapeHtml(call.error)}</div>
                </div>
                ` : ''}
            `;
        }
        
        function showEventDetail(eventId, event) {
            document.getElementById('detailTitle').textContent = 'Event Details';
            const info = getEventDisplayInfo(event);
            
            document.getElementById('detailContent').innerHTML = `
                <div class="detail-section">
                    <div class="detail-section-title">Metadata</div>
                    <div class="detail-grid">
                        <div class="detail-item">
                            <div class="detail-label">Type</div>
                            <div class="detail-value" style="display:flex; gap:6px; align-items:center;">
                                <span style="color:${info.color}">${info.icon}</span> 
                                ${event.event_type}
                            </div>
                        </div>
                        <div class="detail-item">
                            <div class="detail-label">Time</div>
                            <div class="detail-value">${new Date(event.timestamp * 1000).toLocaleString()}</div>
                        </div>
                        ${event.duration_ms ? `
                        <div class="detail-item">
                            <div class="detail-label">Latency</div>
                            <div class="detail-value">${event.duration_ms.toFixed(0)}ms</div>
                        </div>
                        ` : ''}
                    </div>
                </div>
                
                <div class="detail-section">
                    <div class="detail-section-title">Payload</div>
                    <div class="code-block">${JSON.stringify(event.data || {}, null, 2)}</div>
                </div>
                
                ${event.event_type === 'llm_call_end' && event.data?.call_id ? `
                <button class="btn" style="width:100%; justify-content:center;" onclick="showLLMCallById('${event.data.call_id}')">
                    View Full Trace
                </button>
                ` : ''}
            `;
        }
        
        function closeDetail() {
            document.getElementById('detailContent').innerHTML = `
                <div class="empty-state">
                    <svg class="empty-state-svg" viewBox="0 0 24 24"><path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z" fill="none" stroke="currentColor" stroke-width="2"/><polyline points="14 2 14 8 20 8" fill="none" stroke="currentColor" stroke-width="2"/><line x1="16" y1="13" x2="8" y2="13" stroke="currentColor" stroke-width="2"/><line x1="16" y1="17" x2="8" y2="17" stroke="currentColor" stroke-width="2"/><polyline points="10 9 9 9 8 9" fill="none" stroke="currentColor" stroke-width="2"/></svg>
                    <div>Select an event or node</div>
                </div>
            `;
            document.getElementById('detailTitle').textContent = 'Details';
        }
        
        function escapeHtml(text) {
            if (!text) return '';
            const div = document.createElement('div');
            div.textContent = text;
            return div.innerHTML;
        }
        
        async function clearData() {
            if (!confirm('Clear all debug data?')) return;
            await fetch('/api/clear', { method: 'POST' });
            events = [];
            agents = {};
            graphData = { nodes: [], edges: [] };
            selectedAgent = null;
            renderAll();
            closeDetail();
        }
        
        init();
    </script>
</body>
</html>
'''