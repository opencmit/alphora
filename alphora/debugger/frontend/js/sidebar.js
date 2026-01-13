/**
 * sidebar.js - 侧边栏渲染（Agent列表、LLM调用列表）
 */

const Sidebar = {
    /**
     * 渲染Agent列表
     */
    renderAgentList() {
        const container = document.getElementById('agentList');
        if (!container) return;
        
        const agentList = Object.values(State.agents);
        
        if (agentList.length === 0) {
            container.innerHTML = '<div class="empty-state" style="height:100px; font-size:12px;">No Active Agents</div>';
            return;
        }
        
        container.innerHTML = agentList.map((agent, idx) => {
            const callCount = agent.llm_call_count || State.events.filter(e => 
                e.agent_id === agent.agent_id && e.event_type === 'llm_call_end'
            ).length;
            
            const isSelected = State.selectedAgent === agent.agent_id;
            
            return `
                <div class="agent-item ${isSelected ? 'selected' : ''}" 
                     onclick="Handlers.selectAgent('${agent.agent_id}')">
                    <div class="agent-icon">
                        ${Icons.getAgentIcon(agent.agent_type)}
                    </div>
                    <div class="agent-info">
                        <div class="agent-name">${agent.agent_type || 'Agent'}</div>
                        <div class="agent-id">${agent.agent_id.slice(0, 8)}</div>
                    </div>
                    ${callCount > 0 ? `<div class="agent-badge">${callCount}</div>` : ''}
                </div>
            `;
        }).join('');
    },
    
    /**
     * 渲染LLM调用列表
     */
    renderLLMCallList() {
        const container = document.getElementById('llmCallList');
        if (!container) return;
        
        // 优先使用llmCalls数组，否则从events中提取
        let calls = State.llmCalls.length > 0 
            ? State.llmCalls.slice(-15).reverse() 
            : State.events.filter(e => e.event_type === 'llm_call_end').slice(-15).reverse();
        
        if (calls.length === 0) {
            container.innerHTML = '<div class="empty-state" style="height:100px; font-size:12px;">No Recent Calls</div>';
            return;
        }
        
        container.innerHTML = calls.map(call => {
            const info = this.extractLLMCallInfo(call);
            const isSelected = State.selectedLLMCall === info.callId;
            
            return `
                <div class="agent-item ${isSelected ? 'selected' : ''}" 
                     onclick="Handlers.selectLLMCall('${info.callId}')">
                    <div class="agent-icon" style="color: var(--success); background: var(--success-light);">
                        ${Icons.chat}
                    </div>
                    <div class="agent-info">
                        <div class="agent-name">${info.displayName}</div>
                        <div class="agent-id">${Utils.formatDuration(info.duration)} | ${info.tokens} toks</div>
                    </div>
                </div>
            `;
        }).join('');
    },
    
    /**
     * 提取LLM调用信息（兼容两种数据格式）
     */
    extractLLMCallInfo(call) {
        const isFromLLMCalls = call.call_id !== undefined;
        
        if (isFromLLMCalls) {
            return {
                callId: call.call_id,
                displayName: call.model_name || (call.response_text || '').slice(0, 30) || 'LLM Call',
                duration: call.end_time && call.start_time 
                    ? (call.end_time - call.start_time) * 1000 
                    : 0,
                tokens: call.total_tokens || 0
            };
        } else {
            return {
                callId: call.data?.call_id,
                displayName: call.data?.model_name || (call.data?.output_preview || '').slice(0, 30) || 'LLM Call',
                duration: call.data?.duration_ms || call.duration_ms || 0,
                tokens: call.data?.token_usage?.total_tokens || 0
            };
        }
    }
};
