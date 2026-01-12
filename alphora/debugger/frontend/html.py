"""
Alphora Debugger - HTML模板
"""

from .styles import STYLES
from .scripts import SCRIPTS


def get_html() -> str:
    """生成完整的HTML页面"""
    return f'''<!DOCTYPE html>
<html lang="zh-CN">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Alphora Debugger v2.1</title>
    <style>{STYLES}</style>
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
    
    <script>{SCRIPTS}</script>
</body>
</html>'''