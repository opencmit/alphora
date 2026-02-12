# AgentChat Frontend

Professional AI agent chat interface with multi-content-type rendering, terminal panel, and visual style editor.

## Quick Start

```bash
# Basic (local API)
python serve.py

# With remote API proxy (solves CORS!)
python serve.py --api http://192.168.1.100:8000
# Then set endpoint to: /api/v1/chat/completions
```

Opens `http://localhost:8818` automatically.

## Features

- **SSE Streaming** — OpenAI-compatible, real-time token rendering
- **Multi Content Types** — text, markdown, code, terminal, JSON, HTML, image, table, etc.
- **Terminal Panel** — dark-themed side panel for bash/stdout/stderr
- **File Upload** — drag-drop, paste, or click; images sent as base64
- **Conversation History** — localStorage persistence, create/delete/switch
- **Code Copy** — hover-reveal copy button on all code blocks
- **Renderer Studio** — full visual editor with presets, atoms, live preview
- **Reverse Proxy** — built-in `serve.py` proxy to bypass CORS for remote APIs
- **Keyboard Shortcuts** — ⌘K focus, ⌘N new chat

## Remote API (CORS Fix)

Browser blocks cross-origin requests. Use the built-in proxy:

```bash
python serve.py --api http://YOUR_SERVER:PORT
```

This proxies `/api/*` → your server, same-origin = no CORS issues.
Frontend endpoint: `/api/v1/chat/completions`

## Files

| File | Description |
|------|-------------|
| `index.html` | Single-file SPA (HTML + CSS + JS) |
| `renderer_config.js` | Style atoms, presets, content type config |
| `serve.py` | Dev server with reverse proxy |

## SSE Format

```json
data: {"choices":[{"delta":{"content_type":"text","content":"Hello"}}]}
data: {"choices":[{"delta":{"content_type":"code","content":"print('hi')"}}]}
data: [DONE]
```
