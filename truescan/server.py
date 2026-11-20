"""Serve the TrueScan workspace and its in-memory OpenCV API on loopback."""

import argparse
import json
import mimetypes
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import unquote

import cv2
import numpy as np

from .corners import detectCorners
from .perspective import correctPerspective


WEB_ROOT = Path(__file__).resolve().parents[1] / "web"
MAX_PNG_BYTES = 128 * 1024 * 1024
MAX_PIXELS = 64_000_000


class RequestError(ValueError):
    def __init__(self, status, message):
        super().__init__(message)
        self.status = status


def readPage(data):
    if len(data) < 33 or not data.startswith(b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR"):
        raise RequestError(400, "Data gambar PNG tidak valid.")
    width = int.from_bytes(data[16:20], "big")
    height = int.from_bytes(data[20:24], "big")
    if width * height > MAX_PIXELS or max(width, height) >= 32767:
        raise RequestError(413, "Resolusi foto terlalu besar.")
    image = cv2.imdecode(np.frombuffer(data, np.uint8), cv2.IMREAD_UNCHANGED)
    if image is None or image.dtype != np.uint8 or min(image.shape[:2]) < 2:
        raise RequestError(400, "Pilih gambar PNG 8-bit dengan ukuran minimal 2 × 2 piksel.")
    return image


def warpPage(image, header):
    try:
        points = np.asarray(json.loads(header or "null"))
        if points.shape != (4, 2) or points.dtype.kind not in "fiu":
            raise ValueError
        if not np.isfinite(points).all():
            raise ValueError
        # A narrow source can still produce a large rectangular destination.
        edges = np.linalg.norm(points.astype(np.float64) - np.roll(points, 1, axis=0), axis=1)
        width = round(float(max(edges[1::2]))) + 1
        height = round(float(max(edges[::2]))) + 1
        if width * height > MAX_PIXELS or max(width, height) >= 32767:
            raise RequestError(413, "Resolusi halaman hasil terlalu besar.")
        return correctPerspective(image, points)
    except RequestError:
        raise
    except (ValueError, TypeError, OverflowError, RecursionError) as error:
        raise RequestError(400, "Periksa urutan dan posisi keempat sudut halaman.") from error


class ScannerHandler(BaseHTTPRequestHandler):
    def _reply(self, status, media_type, data):
        self.send_response(status)
        self.send_header("Content-Type", media_type)
        self.send_header("Content-Length", str(len(data)))
        self.send_header("Cache-Control", "no-store")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.end_headers()
        if self.command != "HEAD":
            self.wfile.write(data)

    def _json(self, status, value):
        self._reply(status, "application/json; charset=utf-8", json.dumps(value).encode())

    def _local_request(self):
        port = self.server.server_port
        suffix = f":{port}"
        hosts = {f"127.0.0.1{suffix}", f"localhost{suffix}"}
        if port == 80:
            hosts.update(["127.0.0.1", "localhost"])
        host = self.headers.get("Host", "").lower()
        origin = self.headers.get("Origin")
        if host not in hosts or (origin is not None and origin != f"http://{host}"):
            self._json(403, {"error": "Buka TrueScan melalui alamat lokalnya."})
            return False
        return True

    def do_GET(self):
        if not self._local_request():
            return
        path = unquote(self.path.partition("?")[0])
        if path == "/":
            path = "/index.html"
        try:
            asset = (WEB_ROOT / path.lstrip("/")).resolve()
            if not asset.is_relative_to(WEB_ROOT) or not asset.is_file():
                raise FileNotFoundError
            data = asset.read_bytes()
        except (OSError, ValueError, RuntimeError):
            self._json(404, {"error": "Berkas tidak ditemukan."})
            return
        self._reply(200, mimetypes.guess_type(asset.name)[0] or "application/octet-stream", data)

    do_HEAD = do_GET

    def do_POST(self):
        if not self._local_request():
            return
        if self.path not in ("/api/corners", "/api/warp"):
            self._json(404, {"error": "Alamat tidak ditemukan."})
            return
        try:
            if self.headers.get_content_type() != "image/png":
                raise RequestError(415, "Kirim foto dalam format PNG.")
            length = self.headers.get("Content-Length", "")
            if not length.isascii() or not length.isdigit() or len(length) > 12:
                raise RequestError(400, "Ukuran data gambar tidak valid.")
            if int(length) > MAX_PNG_BYTES:
                raise RequestError(413, "Berkas foto terlalu besar.")
            image = readPage(self.rfile.read(int(length)))
            if self.path == "/api/corners":
                points = detectCorners(image)
                self._json(200, {"corners": None if points is None else points.tolist()})
            else:
                page = warpPage(image, self.headers.get("X-Document-Corners"))
                success, encoded = cv2.imencode(".png", page)
                if not success:
                    raise RequestError(500, "Gagal menyimpan hasil koreksi.")
                self._reply(200, "image/png", encoded.tobytes())
        except RequestError as error:
            self._json(error.status, {"error": str(error)})
        except cv2.error:
            self._json(400, {"error": "Gambar gagal diproses."})


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--port", type=int, default=8000)
    args = parser.parse_args()
    with ThreadingHTTPServer(("127.0.0.1", args.port), ScannerHandler) as server:
        print(f"TrueScan: http://127.0.0.1:{server.server_port}", flush=True)
        try:
            server.serve_forever()
        except KeyboardInterrupt:
            pass


if __name__ == "__main__":
    main()
