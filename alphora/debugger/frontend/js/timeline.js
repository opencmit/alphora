/**
 * timeline.js - 时间线视图
 */

const TimelineView = {
    /**
     * 事件类型配置
     */
    eventTypeConfig: {
        'agent_created': { icon: 'agent', type: 'Agent Created', color: 'var(--purple)' },
        'agent_derived': { icon: 'agent', type: 'Agent Forked', color: 'var(--orange)' },
        'llm_call_start': { icon: 'play', type: 'LLM Start', color: 'var(--brand)' },
        'llm_call_end': { icon: 'check', type: 'LLM Complete', color: 'var(--success)' },
        'llm_call_error': { icon: 'alert', type: 'LLM Error', color: 'var(--danger)' },
        'prompt_created': { icon: 'code', type: 'Prompt Created', color: 'var(--cyan)' },
        'prompt_render': { icon: 'code', type: 'Prompt Rendered', color: 'var(--cyan)' },
        'memory_add': { icon: 'database', type: 'Memory Add', color: 'var(--warning)' },
        'memory_retrieve': { icon: 'search', type: 'Memory Retrieve', color: 'var(--warning)' },
        'tool_call_start': { icon: 'tool', type: 'Tool Start', color: '#ec4899' },
        'tool_call_end': { icon: 'check', type: 'Tool Done', color: '#ec4899' },
        'error': { icon: 'alert', type: 'Error', color: 'var(--danger)' }
    },
    
    /**
     * 过滤器配置
     */
    filterConfig: {
        'llm': ['llm_call_start', 'llm_call_end', 'llm_call_error'],
        'agent': ['agent_created', 'agent_derived', 'prompt_created', 'prompt_render'],
        'memory': ['memory_add', 'memory_retrieve', 'memory_search', 'memory_clear'],
        'tool': ['tool_call_start', 'tool_call_end', 'tool_call_error'],
        'error': ['llm_call_error', 'tool_call_error', 'error']
    },
    
    /**
     * 渲染时间线
     */
    render() {
        const container = document.getElementById('timelineView');
        if (!container) return;
        
        let filtered = this.filterEvents();
        
        if (filtered.length === 0) {
            container.innerHTML = '<div class="empty-state"><div>No Events</div></div>';
            return;
        }
        
        container.innerHTML = filtered.slice(-100).map(ev => this.renderEvent(ev)).join('');
    },
    
    /**
     * 过滤事件
     */
    filterEvents() {
        let filtered = [...State.events];
        
        // 按Agent过滤
        if (State.selectedAgent) {
            filtered = filtered.filter(e => e.agent_id === State.selectedAgent);
        }
        
        // 按类型过滤
        if (State.currentFilter !== 'all') {
            const types = this.filterConfig[State.currentFilter] || [];
            filtered = filtered.filter(e => types.includes(e.event_type));
        }
        
        return filtered;
    },
    
    /**
     * 获取事件显示信息
     */
    getEventDisplayInfo(event) {
        const config = this.eventTypeConfig[event.event_type];
        const d = event.data || {};
        
        if (!config) {
            return {
                icon: Icons.agent,
                type: event.event_type,
                color: 'var(--text-secondary)',
                detail: JSON.stringify(d).slice(0, 50)
            };
        }
        
        let detail = '';
        switch (event.event_type) {
            case 'agent_created':
                detail = d.agent_type || '';
                break;
            case 'agent_derived':
                detail = '-> ' + (d.child_type || '');
                break;
            case 'llm_call_start':
                detail = (d.input_preview || d.model_name || '').slice(0, 80);
                break;
            case 'llm_call_end':
                detail = `${d.token_usage?.total_tokens || d.total_tokens || 0} tokens - ${(d.output_preview || '').slice(0, 60)}`;
                break;
            case 'llm_call_error':
            case 'error':
                detail = (d.error || '').slice(0, 60);
                break;
            case 'prompt_created':
                detail = (d.system_prompt_preview || '').slice(0, 60);
                break;
            case 'prompt_render':
                detail = (d.rendered_preview || '').slice(0, 60);
                break;
            case 'memory_add':
                detail = `[${d.role || ''}] ${(d.content_preview || '').slice(0, 50)}`;
                break;
            case 'memory_retrieve':
                detail = `${d.message_count || 0} messages`;
                break;
            case 'tool_call_start':
                detail = d.tool_name || '';
                break;
            case 'tool_call_end':
                detail = (d.result_preview || '').slice(0, 60);
                break;
            default:
                detail = JSON.stringify(d).slice(0, 50);
        }
        
        return {
            icon: Icons[config.icon] || Icons.agent,
            type: config.type,
            color: config.color,
            detail: detail
        };
    },
    
    /**
     * 渲染单个事件
     */
    renderEvent(event) {
        const info = this.getEventDisplayInfo(event);
        const time = Utils.formatTime(event.timestamp);
        const evJson = JSON.stringify(event).replace(/"/g, '&quot;').replace(/'/g, '&#39;');
        
        return `
            <div class="timeline-item ${event.event_type} fade-in" 
                 onclick="Handlers.showEventDetail('${event.event_id}', ${evJson})">
                <div class="timeline-time">${time}</div>
                <div class="timeline-content">
                    <div class="timeline-title">
                        <span class="timeline-tag" style="background: ${info.color}15; color: ${info.color}">
                            ${info.icon} ${info.type}
                        </span>
                        ${event.duration_ms ? `<span class="timeline-tag">${Utils.formatDuration(event.duration_ms)}</span>` : ''}
                    </div>
                    <div class="timeline-detail">${Utils.escapeHtml(info.detail)}</div>
                </div>
            </div>
        `;
    }
};
