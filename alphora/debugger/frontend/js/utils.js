/**
 * utils.js - 工具函数
 */

const Utils = {
    /**
     * 格式化数字（K/M后缀）
     */
    formatNumber(n) {
        if (n >= 1000000) return (n / 1000000).toFixed(1) + 'M';
        if (n >= 1000) return (n / 1000).toFixed(1) + 'K';
        return n.toString();
    },
    
    /**
     * 格式化时长
     */
    formatDuration(ms) {
        if (ms === null || ms === undefined) return '--';
        if (ms < 1000) return ms.toFixed(0) + 'ms';
        return (ms / 1000).toFixed(2) + 's';
    },
    
    /**
     * 格式化时间戳为时间字符串
     */
    formatTime(timestamp) {
        return new Date(timestamp * 1000).toLocaleTimeString('zh-CN', { hour12: false });
    },
    
    /**
     * 格式化时间戳为完整日期时间
     */
    formatDateTime(timestamp) {
        return new Date(timestamp * 1000).toLocaleString();
    },
    
    /**
     * HTML转义
     */
    escapeHtml(text) {
        if (!text) return '';
        const div = document.createElement('div');
        div.textContent = text;
        return div.innerHTML;
    },
    
    /**
     * 截断字符串
     */
    truncate(str, maxLen = 50) {
        if (!str) return '';
        return str.length > maxLen ? str.slice(0, maxLen) + '...' : str;
    },
    
    /**
     * 防抖函数
     */
    debounce(fn, delay) {
        let timer = null;
        return function(...args) {
            clearTimeout(timer);
            timer = setTimeout(() => fn.apply(this, args), delay);
        };
    },
    
    /**
     * 节流函数
     */
    throttle(fn, limit) {
        let inThrottle;
        return function(...args) {
            if (!inThrottle) {
                fn.apply(this, args);
                inThrottle = true;
                setTimeout(() => inThrottle = false, limit);
            }
        };
    }
};
