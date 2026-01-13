/**
 * app.js - 应用入口
 */

const App = {
    /**
     * 初始化应用
     */
    init() {
        this.bindEvents();
        WS.connect();
        
        // 窗口resize时重新渲染图形
        window.addEventListener('resize', Utils.debounce(() => {
            if (State.currentView === 'graph') {
                GraphView.render();
            }
        }, 150));
    },
    
    /**
     * 绑定DOM事件
     */
    bindEvents() {
        // 视图切换Tab
        document.querySelectorAll('.graph-tab').forEach(tab => {
            tab.onclick = () => Handlers.switchView(tab.dataset.view);
        });
        
        // 过滤器按钮
        document.querySelectorAll('.filter-btn').forEach(btn => {
            btn.onclick = () => Handlers.switchFilter(btn.dataset.filter);
        });
    }
};

// 页面加载完成后初始化
document.addEventListener('DOMContentLoaded', () => App.init());
