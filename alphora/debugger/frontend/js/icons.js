/**
 * icons.js - SVG图标定义
 */

const Icons = {
    agent: '<svg class="icon-svg"><use href="#icon-cpu"/></svg>',
    chat: '<svg class="icon-svg"><use href="#icon-message"/></svg>',
    search: '<svg class="icon-svg"><use href="#icon-search"/></svg>',
    code: '<svg class="icon-svg"><use href="#icon-code"/></svg>',
    tool: '<svg class="icon-svg"><use href="#icon-tool"/></svg>',
    database: '<svg class="icon-svg"><use href="#icon-database"/></svg>',
    play: '<svg class="icon-svg"><use href="#icon-play"/></svg>',
    check: '<svg class="icon-svg"><use href="#icon-check"/></svg>',
    alert: '<svg class="icon-svg"><use href="#icon-alert"/></svg>',
    clock: '<svg class="icon-svg"><use href="#icon-clock"/></svg>',
    
    /**
     * 根据Agent类型获取对应图标
     */
    getAgentIcon(agentType) {
        if (!agentType) return this.agent;
        const lower = agentType.toLowerCase();
        if (lower.includes('chat')) return this.chat;
        if (lower.includes('search')) return this.search;
        if (lower.includes('code')) return this.code;
        if (lower.includes('tool')) return this.tool;
        if (lower.includes('rag') || lower.includes('memory')) return this.database;
        return this.agent;
    }
};
