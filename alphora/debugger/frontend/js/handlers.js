/**
 * handlers.js - 全局事件处理
 */

const Handlers = {
    /**
     * 选择Agent
     */
    selectAgent(agentId) {
        State.selectedAgent = State.selectedAgent === agentId ? null : agentId;
        State.selectedLLMCall = null;
        
        // 重新渲染
        Sidebar.renderAgentList();
        Sidebar.renderLLMCallList();
        
        if (State.currentView === 'graph') {
            GraphView.render();
        } else {
            TimelineView.render();
        }
        
        // 显示详情或关闭
        if (State.selectedAgent && State.agents[State.selectedAgent]) {
            DetailPanel.showAgent(State.agents[State.selectedAgent]);
        } else {
            DetailPanel.close();
        }
    },
    
    /**
     * 选择LLM调用
     */
    selectLLMCall(callId) {
        State.selectedLLMCall = callId;
        State.selectedAgent = null;
        
        Sidebar.renderAgentList();
        Sidebar.renderLLMCallList();
        
        // 请求详情
        WS.requestLLMCallDetail(callId);
    },
    
    /**
     * 显示事件详情
     */
    showEventDetail(eventId, event) {
        DetailPanel.showEvent(eventId, event);
    },
    
    /**
     * 切换视图
     */
    switchView(view) {
        State.currentView = view;
        
        // 更新Tab状态
        document.querySelectorAll('.graph-tab').forEach(tab => {
            tab.classList.toggle('active', tab.dataset.view === view);
        });
        
        // 切换显示
        document.getElementById('graphView').style.display = view === 'graph' ? 'block' : 'none';
        document.getElementById('timelineView').classList.toggle('active', view === 'timeline');
        
        // 渲染
        if (view === 'graph') {
            GraphView.render();
        } else {
            TimelineView.render();
        }
    },
    
    /**
     * 切换过滤器
     */
    switchFilter(filter) {
        State.currentFilter = filter;
        
        // 更新按钮状态
        document.querySelectorAll('.filter-btn').forEach(btn => {
            btn.classList.toggle('active', btn.dataset.filter === filter);
        });
        
        // 重新渲染时间线
        TimelineView.render();
    },
    
    /**
     * 关闭详情面板
     */
    closeDetail() {
        State.selectedAgent = null;
        State.selectedLLMCall = null;
        
        Sidebar.renderAgentList();
        Sidebar.renderLLMCallList();
        DetailPanel.close();
    },
    
    /**
     * 清空所有数据
     */
    async clearData() {
        if (!confirm('Clear all debug data?')) return;
        
        await fetch('/api/clear', { method: 'POST' });
        
        State.events = [];
        State.agents = {};
        State.llmCalls = [];
        State.graphData = { nodes: [], edges: [] };
        State.selectedAgent = null;
        State.selectedLLMCall = null;
        
        WS.renderAll();
        DetailPanel.close();
    }
};
