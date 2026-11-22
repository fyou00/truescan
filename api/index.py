"""Vercel Python Function entrypoint for TrueScan's OpenCV and PDF API."""

from http.server import BaseHTTPRequestHandler
import json
from pathlib import Path
import sys
from urllib.parse import parse_qs, urlsplit

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from truescan.server import handleApiPost


def _resolve_route(path: str) -> str:
    parsed = urlsplit(path)
    endpoint = parse_qs(parsed.query).get("endpoint", [""])[0].strip()
    if endpoint:
        return f"/api/{endpoint.lstrip('/')}"
    return parsed.path


def _is_allowed_origin(headers) -> bool:
    origin = headers.get("Origin")
    if origin is None:
        return True
    hosts = set()
    for name in ("X-Forwarded-Host", "Host"):
        value = headers.get(name)
        if value:
            host = value.split(",", 1)[0].strip().lower()
            if host:
                hosts.add(host)
    parsed = urlsplit(origin.strip())
    return parsed.scheme in ("https", "http") and parsed.netloc.lower() in hosts


class handler(BaseHTTPRequestHandler):
    def _reply(self, status, media_type, data):
        self.send_response(status)
        self.send_header("Content-Type", media_type)
        self.send_header("Content-Length", str(len(data)))
        self.send_header("Cache-Control", "no-store")
        self.send_header("X-Content-Type-Options", "nosniff")
        if media_type == "application/pdf":
            self.send_header("Content-Disposition", 'attachment; filename="scan.pdf"')
        self.end_headers()
        if self.command != "HEAD":
            self.wfile.write(data)

    def _json(self, status, value):
        self._reply(status, "application/json; charset=utf-8", json.dumps(value).encode())

    def do_GET(self):
        if _resolve_route(self.path) == "/api/health":
            self._json(200, {"status": "ok"})
            return
        self._json(404, {"error": "Alamat tidak ditemukan."})

    do_HEAD = do_GET

    def do_POST(self):
        if not _is_allowed_origin(self.headers):
            self._json(403, {"error": "Permintaan lintas asal tidak diizinkan."})
            return
        status, media_type, data = handleApiPost(_resolve_route(self.path), self.headers, self.rfile)
        self._reply(status, media_type, data)
