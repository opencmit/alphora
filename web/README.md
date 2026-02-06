# AgentChat Frontend

智能体框架自带对话前端。零依赖启动，支持流式渲染、多 content_type 差异化展示、可视化样式配置。

## 启动

```bash
python frontend/serve.py
python frontend/serve.py --api http://localhost:8000/v1/chat/completions
python frontend/serve.py --port 3000 --no-browser
```

## 功能

- **流式 SSE 渲染** — 兼容 OpenAI chat.completion.chunk 格式
- **多 content_type** — text / code / bash / json / html / image / table / thinking / tool_call 等
- **终端面板** — bash / stdout / stderr 自动路由到右侧深色终端面板
- **文件上传** — 点击、拖拽、粘贴上传，支持图片 base64 编码发送
- **渲染器配置面板** — 预设样式一键切换 + 原子样式点选组合 + 自定义 CSS 覆盖 + 实时预览


## 自定义渲染器

### 方式一：编辑 renderer_config.js

```javascript
const RENDERER_CONFIG = {
  my_type: {
    label: "分析结果",
    component: "markdown",    // text | markdown | code | terminal | json | html | image | table
    layout: "inline",         // inline | panel
    icon: "📊",
    preset: "淡蓝信息",       // 一键应用预设
    atoms: ["text-sm", "font-sans", "color-accent", "bg-blue-50", "border-l-blue", "p-4", "rounded-md"],
    style: {},                // 自定义 CSS 覆盖
  },
};
```

### 方式二：界面内配置

点击顶栏齿轮图标 → 左侧选择 content_type → 右侧操作：
1. 选择预设样式卡片一键应用
2. 点选原子样式 chip 自由组合
3. 填写 CSS 覆盖值精细调整
4. 底部实时预览效果

### 后端集成

```python
streamer = DataStreamer(model_name="my-agent")
await streamer.send_data("text", "分析结论如下...")
await streamer.send_data("bash", "pip install pandas")
await streamer.send_data("stdout", "Successfully installed")
await streamer.send_data("code", "print('hello')")
await streamer.stop()
```

嵌入到已有 FastAPI 项目:

```python
from fastapi.staticfiles import StaticFiles
app.mount("/chat", StaticFiles(directory="frontend", html=True), name="chat")
```
