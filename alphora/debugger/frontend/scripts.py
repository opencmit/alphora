"""
Alphora Debugger - JavaScript逻辑
修复：添加llmCalls独立数据源
"""

SCRIPTS = '''
// ==================== State ====================
let ws = null;
let events = [];
let agents = {};
let llmCalls = [];  // 新增：独立的LLM调用数组
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
            if (msg.llm_calls) llmCalls = msg.llm_calls;  // 新增：接收llm_calls
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
    
    // 使用独立的llmCalls数组，如果为空则从events提取
    let calls = llmCalls.length > 0 ? llmCalls.slice(-10).reverse() : 
        events.filter(e => e.event_type === 'llm_call_end').slice(-10).reverse();
    
    if (calls.length === 0) {
        container.innerHTML = '<div class="empty-state" style="height:100px; font-size:12px;">No Recent Calls</div>';
        return;
    }
    
    container.innerHTML = calls.map(call => {
        // 兼容两种数据格式：llmCalls数组 或 events中的llm_call_end
        const isFromLLMCalls = call.call_id !== undefined;
        const callId = isFromLLMCalls ? call.call_id : call.data?.call_id;
        const outputPreview = isFromLLMCalls ? call.output_preview : call.data?.output_preview;
        const durationMs = isFromLLMCalls ? call.duration_ms : call.data?.duration_ms;
        const totalTokens = isFromLLMCalls ? call.total_tokens : (call.data?.token_usage?.total_tokens || 0);
        
        return `
            <div class="agent-item" onclick="showLLMCallById('${callId}')">
                <div class="agent-icon" style="color: var(--success); background: var(--success-light);">
                    ${ICONS.chat}
                </div>
                <div class="agent-info">
                    <div class="agent-name">${(outputPreview || 'LLM Call').slice(0, 30)}</div>
                    <div class="agent-id">${(durationMs || 0).toFixed ? durationMs.toFixed(0) : durationMs}ms | ${totalTokens} toks</div>
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
    const typeMap = {
        'agent_created': { icon: ICONS.agent, type: 'Agent Created', color: 'var(--purple)', detail: d.agent_type || '' },
        'agent_derived': { icon: ICONS.agent, type: 'Agent Forked', color: 'var(--orange)', detail: `→ ${d.child_type || ''}` },
        'llm_call_start': { icon: ICONS.play, type: 'LLM Start', color: 'var(--brand)', detail: d.input_preview?.slice(0, 80) || d.model_name || '' },
        'llm_call_end': { icon: ICONS.check, type: 'LLM Complete', color: 'var(--success)', detail: `${d.token_usage?.total_tokens || d.total_tokens || 0} tokens - ${(d.output_preview || '').slice(0, 60)}` },
        'llm_call_error': { icon: ICONS.alert, type: 'LLM Error', color: 'var(--danger)', detail: (d.error || '').slice(0, 60) },
        'prompt_created': { icon: ICONS.code, type: 'Prompt Built', color: 'var(--cyan)', detail: (d.system_prompt_preview || '').slice(0, 60) },
        'memory_add': { icon: ICONS.rag, type: 'Memory Saved', color: 'var(--warning)', detail: `[${d.role || ''}] ${(d.content_preview || '').slice(0, 50)}` },
        'memory_retrieve': { icon: ICONS.search, type: 'Retrieval', color: 'var(--warning)', detail: `${d.message_count || 0} messages` },
        'tool_call_start': { icon: ICONS.tool, type: 'Tool Start', color: '#ec4899', detail: d.tool_name || '' },
        'tool_call_end': { icon: ICONS.check, type: 'Tool Done', color: '#ec4899', detail: (d.result_preview || '').slice(0, 60) },
        'error': { icon: ICONS.alert, type: 'System Error', color: 'var(--danger)', detail: (d.error || '').slice(0, 60) }
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
    const agentLLMCalls = agentEvents.filter(e => e.event_type === 'llm_call_end');
    const totalTokens = agentLLMCalls.reduce((sum, e) => sum + (e.data?.token_usage?.total_tokens || 0), 0);
    
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
                    <div class="detail-value large" style="color: var(--success)">${agentLLMCalls.length}</div>
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
            <div class="code-block messages">${call.request_messages.map(msg => `<div class="message-item"><div class="message-role ${msg.role}">${msg.role}</div><div class="message-content">${escapeHtml(msg.content || '')}</div></div>`).join('')}</div>
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
    llmCalls = [];
    graphData = { nodes: [], edges: [] };
    selectedAgent = null;
    renderAll();
    closeDetail();
}

init();
'''