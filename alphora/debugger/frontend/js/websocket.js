/**
 * websocket.js - WebSocket通信管理
 */

const WS = {
    /**
     * 建立WebSocket连接
     */
    connect() {
        const proto = location.protocol === 'https:' ? 'wss:' : 'ws:';
        State.ws = new WebSocket(`${proto}//${location.host}/ws`);
        
        State.ws.onopen = () => this.onOpen();
        State.ws.onclose = () => this.onClose();
        State.ws.onmessage = (e) => this.onMessage(e);
        State.ws.onerror = (e) => this.onError(e);
    },
    
    /**
     * 连接成功
     */
    onOpen() {
        State.connected = true;
        document.getElementById('statusDot').classList.remove('off');
        document.getElementById('statusText').textContent = 'Connected';
    },
    
    /**
     * 连接断开
     */
    onClose() {
        State.connected = false;
        document.getElementById('statusDot').classList.add('off');
        document.getElementById('statusText').textContent = 'Disconnected';
        // 2秒后重连
        setTimeout(() => this.connect(), 2000);
    },
    
    /**
     * 收到消息
     */
    onMessage(e) {
        const msg = JSON.parse(e.data);
        
        switch (msg.type) {
            case 'init':
                this.handleInit(msg);
                break;
            case 'update':
                this.handleUpdate(msg);
                break;
            case 'llm_call_detail':
                DetailPanel.showLLMCall(msg.data);
                break;
        }
    },
    
    /**
     * 连接错误
     */
    onError(e) {
        console.error('WebSocket error:', e);
    },
    
    /**
     * 处理初始化数据
     */
    handleInit(msg) {
        if (msg.stats) StatsPanel.update(msg.stats);
        if (msg.agents) {
            msg.agents.forEach(a => State.agents[a.agent_id] = a);
        }
        if (msg.events) State.events = msg.events;
        if (msg.llm_calls) State.llmCalls = msg.llm_calls;
        if (msg.graph) State.graphData = msg.graph;
        
        this.renderAll();
    },
    
    /**
     * 处理增量更新数据
     */
    handleUpdate(msg) {
        if (msg.stats) StatsPanel.update(msg.stats);
        if (msg.agents) {
            msg.agents.forEach(a => State.agents[a.agent_id] = a);
        }
        if (msg.events) {
            msg.events.forEach(ev => State.events.push(ev));
        }
        if (msg.llm_calls) State.llmCalls = msg.llm_calls;
        if (msg.graph) State.graphData = msg.graph;
        
        this.renderAll();
    },
    
    /**
     * 渲染所有UI组件
     */
    renderAll() {
        Sidebar.renderAgentList();
        Sidebar.renderLLMCallList();
        
        if (State.currentView === 'graph') {
            GraphView.render();
        } else {
            TimelineView.render();
        }
    },
    
    /**
     * 发送消息
     */
    send(data) {
        if (State.ws && State.ws.readyState === WebSocket.OPEN) {
            State.ws.send(JSON.stringify(data));
        }
    },
    
    /**
     * 请求LLM调用详情
     */
    requestLLMCallDetail(callId) {
        this.send({ type: 'get_llm_call', call_id: callId });
    }
};
