"""
Alphora Chat Frontend Server

    python serve.py                    # localhost:8813
    python serve.py --port 3000        # custom port
    python serve.py --no-browser       # don't auto open

Backend connection is configured entirely in the frontend UI (API settings).
"""
import argparse, http.server, json, mimetypes, socketserver, sys, threading, webbrowser
from pathlib import Path

DIR = Path(__file__).parent.resolve()
ROOT = DIR.parent
DOCS_DIR = ROOT / 'docs'


def _build_docs_tree(base: Path, rel_prefix: str = ''):
    """Recursively build a tree structure for the docs directory."""
    items = []
    if not base.is_dir():
        return items
    for p in sorted(base.iterdir()):
        if p.name.startswith('.'):
            continue
        rel = f'{rel_prefix}/{p.name}' if rel_prefix else p.name
        if p.is_dir():
            children = _build_docs_tree(p, rel)
            if children:
                items.append({'name': p.name, 'path': rel, 'type': 'dir', 'children': children})
        elif p.suffix.lower() == '.md':
            items.append({'name': p.name, 'path': rel, 'type': 'file'})
    return items


class Handler(http.server.SimpleHTTPRequestHandler):
    def do_GET(self):
        if self.path in ('/', ''):
            self.path = '/index.html'
        if self.path.startswith('/asset/'):
            return self._serve_asset()
        if self.path == '/_api/docs/tree':
            return self._docs_tree()
        if self.path.startswith('/_api/docs/file?path='):
            return self._docs_file()
        return super().do_GET()

    def _serve_asset(self):
        rel = self.path.lstrip('/')
        f = (ROOT / rel).resolve()
        if not f.is_file() or ROOT not in f.parents:
            self.send_error(404)
            return
        ctype, _ = mimetypes.guess_type(str(f))
        data = f.read_bytes()
        self.send_response(200)
        self.send_header('Content-Type', ctype or 'application/octet-stream')
        self.send_header('Content-Length', str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def _docs_tree(self):
        tree = _build_docs_tree(DOCS_DIR)
        data = json.dumps(tree, ensure_ascii=False).encode()
        self.send_response(200)
        self.send_header('Content-Type', 'application/json; charset=utf-8')
        self.send_header('Content-Length', str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def _docs_file(self):
        from urllib.parse import unquote
        qs = self.path.split('?path=', 1)[-1]
        rel = unquote(qs)
        f = (DOCS_DIR / rel).resolve()
        if not f.is_file() or DOCS_DIR not in f.parents:
            self.send_error(404)
            return
        data = f.read_bytes()
        self.send_response(200)
        self.send_header('Content-Type', 'text/plain; charset=utf-8')
        self.send_header('Content-Length', str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def log_message(self, f, *a):
        sys.stderr.write(f"  {a[0]}\n")


def main():
    p = argparse.ArgumentParser(description='Alphora Chat Frontend Server')
    p.add_argument('--port', '-p', type=int, default=8813)
    p.add_argument('--no-browser', action='store_true')
    a = p.parse_args()

    handler = lambda *args, **kw: Handler(*args, directory=str(DIR), **kw)

    with socketserver.TCPServer(('', a.port), handler) as s:
        s.allow_reuse_address = True
        url = f'http://localhost:{a.port}'
        print(f'\n  Alphora Chat → {url}')
        print(f'  Backend: configure in frontend UI (click ··· in top-right)')
        print()
        if not a.no_browser:
            threading.Timer(.5, lambda: webbrowser.open(url)).start()
        try:
            s.serve_forever()
        except KeyboardInterrupt:
            print('\n  Stopped.')
            s.shutdown()


if __name__ == '__main__':
    main()
