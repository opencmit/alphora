/**
 * state.js - 全局状态管理
 */

const State = {
    // WebSocket连接
    ws: null,
    connected: false,
    
    // 数据
    events: [],
    agents: {},
    llmCalls: [],
    graphData: { nodes: [], edges: [] },
    
    // UI状态
    selectedAgent: null,
    selectedLLMCall: null,
    currentView: 'graph',       // 'graph' | 'timeline'
    currentFilter: 'all',       // 'all' | 'llm' | 'agent' | 'memory' | 'tool' | 'error'
    currentDetailTab: 'overview',
    
    // 性能优化
    lastGraphRender: 0,
    
    // 临时数据
    _currentLLMCall: null
};

// Agent颜色配置
const AGENT_COLORS = [
    '#2563eb', '#10b981', '#f59e0b', '#ef4444', 
    '#8b5cf6', '#06b6d4', '#f97316', '#ec4899'
];
