/**
 * stats.js - 顶部统计面板
 */

const StatsPanel = {
    /**
     * 更新统计数据显示
     */
    update(stats) {
        const els = {
            'statAgents': stats.active_agents || Object.keys(State.agents).length || 0,
            'statCalls': stats.total_llm_calls || 0,
            'statTokens': Utils.formatNumber(stats.total_tokens || 0),
            'statTPS': (stats.avg_tokens_per_second || 0).toFixed(1),
            'statErrors': stats.errors || 0,
            'eventCount': stats.total_events || State.events.length || 0
        };
        
        for (const [id, value] of Object.entries(els)) {
            const el = document.getElementById(id);
            if (el) el.textContent = value;
        }
    }
};
