"""
Alphora Debugger - CSS样式
"""

STYLES = '''
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
.node-group { cursor: pointer; }
.node-group:hover .node-box { stroke: var(--brand); stroke-width: 2; }
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
.code-block.messages { 
    max-height: none; 
    background: transparent; 
    padding: 0; 
    border: none;
    font-family: inherit;
    display: flex;
    flex-direction: column;
    gap: 8px;
}

.message-item {
    padding: 8px 10px; border-radius: 6px;
    border: 1px solid var(--border); background: var(--bg-body);
}
.message-role {
    font-size: 10px; font-weight: 700; margin-bottom: 4px;
    text-transform: uppercase; display: inline-block; padding: 2px 6px; border-radius: 4px;
}
.message-role.system { background: var(--purple-light); color: var(--purple); }
.message-role.user { background: var(--brand-light); color: var(--brand); }
.message-role.assistant { background: var(--success-light); color: var(--success); }
.message-content { font-size: 12px; color: var(--text-main); white-space: pre-wrap; word-break: break-word; line-height: 1.6; }

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
'''