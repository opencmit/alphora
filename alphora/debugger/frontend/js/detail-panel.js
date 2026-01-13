/**
 * detail-panel.js - 右侧详情面板
 */

const DetailPanel = {
    /**
     * 显示Agent详情
     */
    showAgent(agent) {
        document.getElementById('detailTitle').textContent = agent.agent_type || 'Agent';
        
        const agentEvents = State.events.filter(e => e.agent_id === agent.agent_id);
        const agentLLMCalls = agentEvents.filter(e => e.event_type === 'llm_call_end');
        const totalTokens = agent.total_tokens || agentLLMCalls.reduce((sum, e) => 
            sum + (e.data?.token_usage?.total_tokens || 0), 0);
        
        document.getElementById('detailContent').innerHTML = `
            <div class="detail-section">
                <div class="detail-section-title">Overview</div>
                <div class="detail-grid">
                    <div class="detail-item">
                        <div class="detail-label">Agent Type</div>
                        <div class="detail-value">${agent.agent_type || 'Unknown'}</div>
                    </div>
                    <div class="detail-item">
                        <div class="detail-label">Status</div>
                        <div class="detail-value" style="color: var(--success)">${agent.status || 'active'}</div>
                    </div>
                    <div class="detail-item full">
                        <div class="detail-label">Agent ID</div>
                        <div class="detail-value">${agent.agent_id}</div>
                    </div>
                    <div class="detail-item">
                        <div class="detail-label">Model</div>
                        <div class="detail-value">${agent.llm_info?.model_name || 'N/A'}</div>
                    </div>
                    <div class="detail-item">
                        <div class="detail-label">Has Memory</div>
                        <div class="detail-value">${agent.has_memory ? 'Yes' : 'No'}</div>
                    </div>
                </div>
            </div>
            
            <div class="detail-section">
                <div class="detail-section-title">Metrics</div>
                <div class="detail-grid">
                    <div class="detail-item">
                        <div class="detail-label">LLM Calls</div>
                        <div class="detail-value large" style="color: var(--success)">${agent.llm_call_count || agentLLMCalls.length}</div>
                    </div>
                    <div class="detail-item">
                        <div class="detail-label">Total Tokens</div>
                        <div class="detail-value large" style="color: var(--warning)">${Utils.formatNumber(totalTokens)}</div>
                    </div>
                </div>
            </div>
            
            ${this.renderChildAgents(agent)}
            ${this.renderLLMConfig(agent)}
        `;
    },
    
    /**
     * 渲染子Agent列表
     */
    renderChildAgents(agent) {
        if (!agent.children_ids || agent.children_ids.length === 0) return '';
        
        return `
            <div class="detail-section">
                <div class="detail-section-title">Child Agents (${agent.children_ids.length})</div>
                <div class="detail-grid">
                    ${agent.children_ids.map(cid => {
                        const child = State.agents[cid];
                        return `
                            <div class="detail-item" style="cursor:pointer" onclick="Handlers.selectAgent('${cid}')">
                                <div class="detail-label">${child?.agent_type || 'Agent'}</div>
                                <div class="detail-value">${cid.slice(0, 8)}...</div>
                            </div>
                        `;
                    }).join('')}
                </div>
            </div>
        `;
    },
    
    /**
     * 渲染LLM配置
     */
    renderLLMConfig(agent) {
        if (!agent.llm_info) return '';
        
        return `
            <div class="detail-section">
                <div class="detail-section-title">LLM Configuration</div>
                <div class="code-block">${JSON.stringify(agent.llm_info, null, 2)}</div>
            </div>
        `;
    },
    
    /**
     * 显示LLM调用详情
     */
    showLLMCall(call) {
        if (!call) return;
        
        State._currentLLMCall = call;
        State.currentDetailTab = 'overview';
        
        document.getElementById('detailTitle').textContent = 'LLM Call Details';
        document.getElementById('detailContent').innerHTML = `
            <div class="detail-tabs">
                <div class="detail-tab active" data-tab="overview" onclick="DetailPanel.switchTab('overview')">Overview</div>
                <div class="detail-tab" data-tab="messages" onclick="DetailPanel.switchTab('messages')">Messages</div>
                <div class="detail-tab" data-tab="response" onclick="DetailPanel.switchTab('response')">Response</div>
                <div class="detail-tab" data-tab="stream" onclick="DetailPanel.switchTab('stream')">Stream</div>
            </div>
            <div id="detailTabContent">
                ${this.renderOverviewTab(call)}
            </div>
        `;
    },
    
    /**
     * 切换Tab
     */
    switchTab(tabName) {
        State.currentDetailTab = tabName;
        
        // 更新Tab按钮状态
        document.querySelectorAll('.detail-tab').forEach(tab => {
            tab.classList.toggle('active', tab.dataset.tab === tabName);
        });
        
        const call = State._currentLLMCall;
        if (!call) return;
        
        const container = document.getElementById('detailTabContent');
        if (!container) return;
        
        switch(tabName) {
            case 'overview':
                container.innerHTML = this.renderOverviewTab(call);
                break;
            case 'messages':
                container.innerHTML = this.renderMessagesTab(call);
                break;
            case 'response':
                container.innerHTML = this.renderResponseTab(call);
                break;
            case 'stream':
                container.innerHTML = this.renderStreamTab(call);
                break;
        }
    },
    
    /**
     * 计算LLM调用的性能指标
     */
    calculateMetrics(call) {
        let ttft = 0;
        if (call.first_token_time && call.start_time) {
            ttft = (call.first_token_time - call.start_time) * 1000;
        }
        
        let duration = 0;
        if (call.end_time && call.start_time) {
            duration = (call.end_time - call.start_time) * 1000;
        }
        
        const tps = call.completion_tokens && duration > 0 
            ? (call.completion_tokens / (duration / 1000)).toFixed(1) 
            : '0';
        
        const promptRatio = call.total_tokens > 0 
            ? (call.prompt_tokens / call.total_tokens * 100) 
            : 50;
        
        return { ttft, duration, tps, promptRatio };
    },
    
    /**
     * 渲染Overview Tab
     */
    renderOverviewTab(call) {
        const { ttft, duration, tps, promptRatio } = this.calculateMetrics(call);
        
        return `
            <div class="detail-section">
                <div class="detail-section-title">Performance</div>
                <div class="detail-grid">
                    <div class="detail-item">
                        <div class="detail-label">Duration</div>
                        <div class="detail-value large" style="color: var(--brand)">${Utils.formatDuration(duration)}</div>
                    </div>
                    <div class="detail-item">
                        <div class="detail-label">Time to First Token</div>
                        <div class="detail-value large" style="color: var(--purple)">${Utils.formatDuration(ttft)}</div>
                    </div>
                    <div class="detail-item">
                        <div class="detail-label">Speed</div>
                        <div class="detail-value large" style="color: var(--success)">${tps} TPS</div>
                    </div>
                    <div class="detail-item">
                        <div class="detail-label">Chunks</div>
                        <div class="detail-value large">${call.chunk_count || 0}</div>
                    </div>
                </div>
            </div>
            
            <div class="detail-section">
                <div class="detail-section-title">Model Info</div>
                <div class="detail-grid">
                    <div class="detail-item full">
                        <div class="detail-label">Model</div>
                        <div class="detail-value">${call.model_name || 'Unknown'}</div>
                    </div>
                    <div class="detail-item">
                        <div class="detail-label">Streaming</div>
                        <div class="detail-value">${call.is_streaming ? 'Yes' : 'No'}</div>
                    </div>
                    <div class="detail-item">
                        <div class="detail-label">Finish Reason</div>
                        <div class="detail-value">${call.finish_reason || 'N/A'}</div>
                    </div>
                </div>
            </div>
            
            <div class="detail-section">
                <div class="detail-section-title">Token Usage</div>
                <div class="detail-grid">
                    <div class="detail-item">
                        <div class="detail-label">Prompt Tokens</div>
                        <div class="detail-value" style="color: var(--brand)">${Utils.formatNumber(call.prompt_tokens || 0)}</div>
                    </div>
                    <div class="detail-item">
                        <div class="detail-label">Completion Tokens</div>
                        <div class="detail-value" style="color: var(--success)">${Utils.formatNumber(call.completion_tokens || 0)}</div>
                    </div>
                    <div class="detail-item full">
                        <div class="detail-label">Total: ${Utils.formatNumber(call.total_tokens || 0)}</div>
                        <div class="token-bar">
                            <div class="token-bar-segment prompt" style="width: ${promptRatio}%"></div>
                            <div class="token-bar-segment completion" style="width: ${100 - promptRatio}%"></div>
                        </div>
                    </div>
                </div>
            </div>
            
            ${call.error ? `
            <div class="detail-section">
                <div class="detail-section-title" style="color: var(--danger)">Error</div>
                <div class="code-block" style="color: var(--danger); border-left: 3px solid var(--danger);">${Utils.escapeHtml(call.error)}</div>
            </div>
            ` : ''}
        `;
    },
    
    /**
     * 渲染Messages Tab
     */
    renderMessagesTab(call) {
        const messages = call.request_messages || [];
        
        if (messages.length === 0) {
            return '<div class="empty-state" style="height:200px"><div>No messages</div></div>';
        }
        
        return `
            <div class="detail-section">
                <div class="detail-section-title">Input Messages (${messages.length})</div>
                <div class="chat-container">
                    ${messages.map(msg => ChatBubble.render(msg.role, msg.content)).join('')}
                </div>
            </div>
        `;
    },
    
    /**
     * 渲染Response Tab
     */
    renderResponseTab(call) {
        const response = call.response_text || '';
        const reasoning = call.reasoning_text || '';
        
        return `
            ${reasoning ? `
            <div class="detail-section">
                <div class="detail-section-title">Reasoning</div>
                <div class="code-block reasoning-block">${Utils.escapeHtml(reasoning)}</div>
            </div>
            ` : ''}
            
            <div class="detail-section">
                <div class="detail-section-title">Response</div>
                <div class="chat-container">
                    ${ChatBubble.render('assistant', response)}
                </div>
            </div>
        `;
    },
    
    /**
     * 渲染Stream Tab
     */
    renderStreamTab(call) {
        const chunks = call.stream_chunks || [];
        
        if (chunks.length === 0) {
            return '<div class="empty-state" style="height:200px"><div>No stream data</div></div>';
        }
        
        const startTime = call.start_time || 0;
        
        return `
            <div class="detail-section">
                <div class="detail-section-title">Stream Chunks (${chunks.length})</div>
                <div class="stream-timeline">
                    ${chunks.map((chunk, idx) => {
                        const relativeTime = chunk.timestamp 
                            ? ((chunk.timestamp - startTime) * 1000).toFixed(0) 
                            : 0;
                        return `
                            <div class="stream-chunk ${idx % 2 === 0 ? 'even' : ''}">
                                <div class="chunk-index">#${chunk.index || idx + 1}</div>
                                <div class="chunk-time">+${relativeTime}ms</div>
                                <div class="chunk-content">${Utils.escapeHtml(chunk.content || '')}</div>
                            </div>
                        `;
                    }).join('')}
                </div>
            </div>
            
            ${call.stream_content_by_type ? `
            <div class="detail-section">
                <div class="detail-section-title">Content by Type</div>
                <div class="code-block">${JSON.stringify(call.stream_content_by_type, null, 2)}</div>
            </div>
            ` : ''}
        `;
    },
    
    /**
     * 显示事件详情
     */
    showEvent(eventId, event) {
        document.getElementById('detailTitle').textContent = 'Event Details';
        const info = TimelineView.getEventDisplayInfo(event);
        
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
                        <div class="detail-value">${Utils.formatDateTime(event.timestamp)}</div>
                    </div>
                    ${event.duration_ms ? `
                    <div class="detail-item">
                        <div class="detail-label">Duration</div>
                        <div class="detail-value">${Utils.formatDuration(event.duration_ms)}</div>
                    </div>
                    ` : ''}
                    <div class="detail-item">
                        <div class="detail-label">Sequence</div>
                        <div class="detail-value">#${event.seq || 0}</div>
                    </div>
                    ${event.agent_id ? `
                    <div class="detail-item full">
                        <div class="detail-label">Agent ID</div>
                        <div class="detail-value">${event.agent_id}</div>
                    </div>
                    ` : ''}
                </div>
            </div>
            
            <div class="detail-section">
                <div class="detail-section-title">Event Data</div>
                <div class="code-block">${JSON.stringify(event.data || {}, null, 2)}</div>
            </div>
            
            ${event.event_type === 'llm_call_end' && event.data?.call_id ? `
            <button class="btn btn-full" onclick="Handlers.selectLLMCall('${event.data.call_id}')">
                ${Icons.search} View Full LLM Call Details
            </button>
            ` : ''}
        `;
    },
    
    /**
     * 关闭详情面板（显示空状态）
     */
    close() {
        State._currentLLMCall = null;
        
        document.getElementById('detailTitle').textContent = 'Details';
        document.getElementById('detailContent').innerHTML = `
            <div class="empty-state">
                <svg class="empty-state-svg" viewBox="0 0 24 24">
                    <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z" fill="none" stroke="currentColor" stroke-width="2"/>
                    <polyline points="14 2 14 8 20 8" fill="none" stroke="currentColor" stroke-width="2"/>
                    <line x1="16" y1="13" x2="8" y2="13" stroke="currentColor" stroke-width="2"/>
                    <line x1="16" y1="17" x2="8" y2="17" stroke="currentColor" stroke-width="2"/>
                </svg>
                <div>Select an event or node</div>
            </div>
        `;
    }
};
