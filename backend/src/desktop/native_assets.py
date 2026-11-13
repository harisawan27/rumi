"""Static assets only: this listener has no command or authorization endpoints."""
import mimetypes
import secrets
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import unquote, urlsplit


class AssetServer:
    def __init__(self, root):
        self.root = Path(root).resolve()
        if not (self.root / "desktop-local/index.html").is_file():
            raise FileNotFoundError("Build the frontend before starting Rumi Desktop")
        self.document_path = "/" + secrets.token_urlsafe(32) + "/desktop-local/"
        outer = self

        class Handler(BaseHTTPRequestHandler):
            def log_message(self, *_):
                pass

            def do_GET(self):
                if self.headers.get("Host") != outer.host or self.client_address[0] != "127.0.0.1":
                    self.send_error(403)
                    return
                url = urlsplit(self.path)
                path = unquote(url.path)
                if path == outer.document_path and not url.query:
                    target = outer.root / "desktop-local/index.html"
                elif path.startswith("/_next/static/") and "\\" not in path and ".." not in path:
                    target = (outer.root / path.lstrip("/")).resolve()
                    if not target.is_relative_to(outer.root / "_next/static"):
                        self.send_error(404)
                        return
                else:
                    self.send_error(404)
                    return
                if not target.is_file():
                    self.send_error(404)
                    return
                data = target.read_bytes()
                self.send_response(200)
                self.send_header("Content-Type", mimetypes.guess_type(target)[0] or "application/octet-stream")
                self.send_header("Content-Length", str(len(data)))
                self.send_header("Cache-Control", "no-store")
                self.send_header("X-Content-Type-Options", "nosniff")
                self.send_header("Referrer-Policy", "no-referrer")
                self.send_header("Content-Security-Policy", "default-src 'none'; script-src 'self' 'unsafe-inline' 'unsafe-eval'; style-src 'self' 'unsafe-inline'; font-src 'self'; img-src 'self' data:; connect-src 'none'; frame-src 'none'; frame-ancestors 'none'; object-src 'none'; base-uri 'none'; form-action 'none'")
                self.end_headers()
                self.wfile.write(data)

        self.server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        self.server.daemon_threads = True
        self.host = f"127.0.0.1:{self.server.server_port}"
        self.url = f"http://{self.host}{self.document_path}"
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)

    def start(self):
        self.thread.start()

    def close(self):
        self.server.shutdown()
        self.server.server_close()
        self.thread.join(timeout=5)
