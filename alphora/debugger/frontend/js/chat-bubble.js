/**
 * chat-bubble.js - 聊天气泡组件
 */

const ChatBubble = {
    /**
     * 角色样式配置
     */
    roleStyles: {
        'system': { 
            bg: 'var(--purple-light)', 
            border: 'var(--purple)', 
            color: 'var(--purple)', 
            label: 'SYSTEM' 
        },
        'user': { 
            bg: 'var(--bg-panel)', 
            border: 'var(--border)', 
            color: 'var(--text-secondary)', 
            label: 'USER' 
        },
        'assistant': { 
            bg: 'var(--brand-light)', 
            border: 'var(--brand)', 
            color: 'var(--brand)', 
            label: 'ASSISTANT' 
        },
        'tool': { 
            bg: 'var(--warning-light)', 
            border: 'var(--warning)', 
            color: 'var(--warning)', 
            label: 'TOOL' 
        }
    },
    
    /**
     * 渲染聊天气泡
     */
    render(role, content) {
        const style = this.roleStyles[role] || this.roleStyles['user'];
        
        return `
            <div class="chat-message ${role}">
                <div class="chat-bubble" style="
                    background: ${style.bg}; 
                    border: 1px solid ${style.border}20; 
                    border-left: 3px solid ${style.border};
                ">
                    <div class="chat-role" style="color: ${style.color};">${style.label}</div>
                    <div class="chat-content">${Utils.escapeHtml(content || '')}</div>
                </div>
            </div>
        `;
    }
};
