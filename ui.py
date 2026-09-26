"""Open the paper bot in a browser.

    python ui.py

Then open http://127.0.0.1:8765
The page is the React app in web/. The wallet trades forward when a new candle closes.
"""

from __future__ import annotations

import json
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import unquote

from live import step
from session import load_config

ROOT = Path(__file__).resolve().parent
DIST = ROOT / "web" / "dist"
LEGACY = ROOT / "ui" / "index.html"
HOST = "127.0.0.1"
PORT = 8765

MIME = {
    ".html": "text/html; charset=utf-8",
    ".js": "text/javascript; charset=utf-8",
    ".css": "text/css; charset=utf-8",
    ".svg": "image/svg+xml",
    ".json": "application/json; charset=utf-8",
    ".png": "image/png",
    ".ico": "image/x-icon",
    ".woff": "font/woff",
    ".woff2": "font/woff2",
    ".map": "application/json",
}


def main() -> None:
    server = ThreadingHTTPServer((HOST, PORT), Handler)
    if (DIST / "index.html").is_file():
        print(f"Paper bot UI: http://{HOST}:{PORT}")
    else:
        print("React build not found. From the web folder run: npm install && npm run build")
        print(f"Serving the previous page at http://{HOST}:{PORT}")
    print("Leave this window open. Nothing is sent to an exchange.")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nStopped.")


class Handler(BaseHTTPRequestHandler):
    def do_OPTIONS(self) -> None:
        self.send_response(204)
        self._cors()
        self.end_headers()

    def do_GET(self) -> None:
        path = unquote(self.path.split("?", 1)[0])
        if path == "/api/run":
            self._run({})
            return
        if self._static(path):
            return
        self._send(404, "text/plain; charset=utf-8", b"Not found")

    def do_POST(self) -> None:
        if self.path.split("?", 1)[0] != "/api/run":
            self._send(404, "text/plain; charset=utf-8", b"Not found")
            return
        length = int(self.headers.get("Content-Length", "0"))
        if length > 20_000:
            self._json(413, {"error": "Request is too large."})
            return
        raw = self.rfile.read(length) if length else b"{}"
        try:
            form = json.loads(raw.decode("utf-8"))
        except json.JSONDecodeError:
            self._json(400, {"error": "The form was not valid JSON."})
            return
        if not isinstance(form, dict):
            self._json(400, {"error": "The form must be an object."})
            return
        self._run(form)

    def _static(self, path: str) -> bool:
        index = DIST / "index.html"
        if index.is_file():
            target = _dist_file(path)
            if target is None and "." not in Path(path).name:
                target = index
            if target is not None and target.is_file():
                cache = "public, max-age=31536000, immutable" if path.startswith("/assets/") else "no-cache"
                mime = MIME.get(target.suffix.lower(), "application/octet-stream")
                self._send(200, mime, target.read_bytes(), cache)
                return True
            return False
        if path == "/" and LEGACY.is_file():
            self._send(200, "text/html; charset=utf-8", LEGACY.read_bytes())
            return True
        return False

    def _run(self, form: dict) -> None:
        try:
            payload = step(load_config(ROOT / "config.json"), form)
        except ValueError as exc:
            self._json(400, {"error": str(exc)})
            return
        except Exception as exc:
            self._json(500, {"error": str(exc)})
            return
        self._json(200, payload)

    def _json(self, status: int, payload: dict) -> None:
        body = json.dumps(payload).encode("utf-8")
        self._send(status, "application/json; charset=utf-8", body)

    def _send(self, status: int, content_type: str, body: bytes, cache: str = "no-cache") -> None:
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", cache)
        self._cors()
        self.end_headers()
        self.wfile.write(body)

    def _cors(self) -> None:
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")

    def log_message(self, fmt: str, *args) -> None:
        if self.path.split("?", 1)[0].startswith("/api"):
            print(f"{self.address_string()} {fmt % args}")


def _dist_file(path: str) -> Path | None:
    relative = path.lstrip("/")
    if not relative:
        return DIST / "index.html"
    if "\\" in relative or relative.startswith("/") or ".." in Path(relative).parts:
        return None
    root = DIST.resolve()
    candidate = (DIST / relative).resolve()
    if candidate != root and root not in candidate.parents:
        return None
    if candidate.is_file():
        return candidate
    return None


if __name__ == "__main__":
    main()
