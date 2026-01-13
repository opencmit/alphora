/**
 * graph.js - 图形拓扑视图
 */

const GraphView = {
    nodeWidth: 180,
    nodeHeight: 70,
    padding: 60,
    
    /**
     * 渲染图形视图
     */
    render() {
        // 节流：100ms内不重复渲染
        const now = Date.now();
        if (now - State.lastGraphRender < 100) return;
        State.lastGraphRender = now;
        
        const svg = document.getElementById('graphSvg');
        const nodesG = document.getElementById('graphNodes');
        const edgesG = document.getElementById('graphEdges');
        
        if (!svg || !nodesG || !edgesG) return;
        
        const nodes = State.graphData.nodes || [];
        const edges = State.graphData.edges || [];
        
        if (nodes.length === 0) {
            nodesG.innerHTML = '';
            edgesG.innerHTML = '';
            return;
        }
        
        const width = svg.clientWidth || 800;
        const height = svg.clientHeight || 600;
        
        // 计算节点位置
        const positions = this.calculateLayout(nodes, edges, width, height);
        
        // 渲染边
        edgesG.innerHTML = this.renderEdges(edges, positions);
        
        // 渲染节点
        nodesG.innerHTML = this.renderNodes(positions);
    },
    
    /**
     * 计算层级布局
     */
    calculateLayout(nodes, edges, width, height) {
        const levels = {};
        const processed = new Set();
        
        // 找出派生关系中的子节点
        const childIds = new Set(edges.filter(e => e.type === 'derive').map(e => e.target));
        
        // 根节点：没有被派生的节点
        let roots = nodes.filter(n => !childIds.has(n.id));
        if (roots.length === 0 && nodes.length > 0) {
            roots = [nodes[0]];
        }
        
        // BFS分配层级
        const assignLevel = (node, level) => {
            if (processed.has(node.id)) return;
            processed.add(node.id);
            
            if (!levels[level]) levels[level] = [];
            levels[level].push(node);
            
            // 找到该节点的子节点
            edges.filter(e => e.source === node.id && e.type === 'derive')
                .forEach(e => {
                    const child = nodes.find(n => n.id === e.target);
                    if (child) assignLevel(child, level + 1);
                });
        };
        
        roots.forEach(r => assignLevel(r, 0));
        
        // 处理未分配的节点
        nodes.filter(n => !processed.has(n.id))
            .forEach(n => assignLevel(n, Object.keys(levels).length));
        
        // 计算位置
        const positions = {};
        const levelCount = Object.keys(levels).length;
        
        Object.entries(levels).forEach(([level, nodesInLevel]) => {
            const l = parseInt(level);
            const y = this.padding + (height - 2 * this.padding) / Math.max(levelCount, 1) * l + this.nodeHeight / 2;
            
            nodesInLevel.forEach((node, i) => {
                const x = this.padding + (width - 2 * this.padding) / (nodesInLevel.length + 1) * (i + 1);
                positions[node.id] = { x, y, node };
            });
        });
        
        return positions;
    },
    
    /**
     * 渲染边
     */
    renderEdges(edges, positions) {
        return edges.map(edge => {
            const from = positions[edge.source];
            const to = positions[edge.target];
            if (!from || !to) return '';
            
            const startY = from.y + this.nodeHeight / 2;
            const endY = to.y - this.nodeHeight / 2;
            const midY = (startY + endY) / 2;
            
            const edgeClass = edge.type === 'derive' ? 'edge-line derive' : 
                              edge.type === 'call' ? 'edge-line call' : 'edge-line';
            const marker = edge.type === 'derive' ? 'url(#arrowhead-derive)' : 'url(#arrowhead)';
            
            return `<path class="${edgeClass}" 
                d="M ${from.x} ${startY} C ${from.x} ${midY}, ${to.x} ${midY}, ${to.x} ${endY}" 
                marker-end="${marker}"/>`;
        }).join('');
    },
    
    /**
     * 渲染节点
     */
    renderNodes(positions) {
        return Object.values(positions).map((pos, idx) => {
            const { x, y, node } = pos;
            const color = AGENT_COLORS[idx % AGENT_COLORS.length];
            const data = node.data || {};
            const isSelected = State.selectedAgent === node.id;
            
            return `
                <g class="node-group" 
                   transform="translate(${x - this.nodeWidth/2}, ${y - this.nodeHeight/2})" 
                   onclick="Handlers.selectAgent('${node.id}')">
                    <rect class="node-box ${isSelected ? 'selected' : ''}" 
                          width="${this.nodeWidth}" height="${this.nodeHeight}" 
                          style="${isSelected ? 'stroke:' + color + ';' : ''}"/>
                    <rect class="node-header" x="0" y="0" width="${this.nodeWidth}" height="24" rx="8" 
                          style="clip-path: inset(0 0 4px 0 round 8px 8px 0 0); fill: ${color}20;"/>
                    <text class="node-title" x="12" y="17" style="fill:${color}">${node.label || 'Agent'}</text>
                    <text class="node-sub" x="12" y="40">${node.id.slice(0, 12)}...</text>
                    <text class="node-stat" x="12" y="58">
                        <tspan font-weight="600">${data.llm_call_count || 0}</tspan> calls
                        <tspan dx="8">${Utils.formatNumber(data.total_tokens || 0)} toks</tspan>
                    </text>
                </g>
            `;
        }).join('');
    }
};
