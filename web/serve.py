"""
AgentChat Frontend Server

    python serve.py                          # http://localhost:8818
    python serve.py --port 3000
    python serve.py --api http://localhost:8000/v1/chat/completions

零依赖 (仅 Python 标准库)。如安装了 uvicorn+fastapi 自动启用高性能模式。
"""
import argparse, http.server, os, socketserver, sys, threading, webbrowser
from functools import partial
from pathlib import Path

DIR = Path(__file__).parent.resolve()
PORT = 8818


class Handler(http.server.SimpleHTTPRequestHandler):
    def __init__(self, *a, api_url=None, **kw):
        self.api_url = api_url
        super().__init__(*a, directory=str(DIR), **kw)

    def do_GET(self):
        if self.path in ('/', ''): self.path = '/index.html'
        if self.path == '/index.html' and self.api_url:
            content = (DIR / 'index.html').read_text('utf-8')
            inject = f"<script>document.addEventListener('DOMContentLoaded',()=>{{const e=document.getElementById('cfg-url');if(e)e.value='{self.api_url}';}})</script></head>"
            content = content.replace('</head>', inject)
            enc = content.encode('utf-8')
            self.send_response(200)
            self.send_header('Content-type', 'text/html;charset=utf-8')
            self.send_header('Content-Length', str(len(enc)))
            self.end_headers()
            self.wfile.write(enc)
            return
        return super().do_GET()

    def end_headers(self):
        self.send_header('Access-Control-Allow-Origin', '*')
        self.send_header('Access-Control-Allow-Methods', 'GET,POST,OPTIONS')
        self.send_header('Access-Control-Allow-Headers', '*')
        self.send_header('Cache-Control', 'no-cache')
        super().end_headers()

    def do_OPTIONS(self):
        self.send_response(200)
        self.end_headers()

    def log_message(self, fmt, *a):
        sys.stderr.write(f"  {a[0]}\n")


def main():
    p = argparse.ArgumentParser(description="AgentChat Frontend")
    p.add_argument("--port", "-p", type=int, default=PORT)
    p.add_argument("--api", "-a", type=str, default=None, help="后端 API 地址")
    p.add_argument("--no-browser", action="store_true")
    args = p.parse_args()

    handler = partial(Handler, api_url=args.api)
    with socketserver.TCPServer(("", args.port), handler) as srv:
        srv.allow_reuse_address = True
        url = f"http://localhost:{args.port}"
        print(f"\n  AgentChat → {url}\n")
        if not args.no_browser:
            threading.Timer(0.5, lambda: webbrowser.open(url)).start()
        try:
            srv.serve_forever()
        except KeyboardInterrupt:
            print("\n  Stopped."); srv.shutdown()


if __name__ == "__main__":
    main()
