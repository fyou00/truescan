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
from .enhance import enhancePage
from .pdf import PAGE_MODES, PAGE_SIZES, exportPdf, renderPageMode
from .perspective import correctPerspective


WEB_ROOT = Path(__file__).resolve().parents[1] / "web"
MAX_PNG_BYTES = 128 * 1024 * 1024
MAX_PIXELS = 64_000_000
MAX_DOCUMENT_BYTES = 256 * 1024 * 1024
MAX_DOCUMENT_PIXELS = 128_000_000
MAX_DOCUMENT_PAGES = 100


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


def readDocumentPages(stream, remaining):
    """Yield enhanced PNG frames in request order without buffering the whole batch."""
    page_count = total_pixels = 0
    if not remaining:
        raise RequestError(400, "Tambahkan minimal satu halaman.")
    while remaining:
        if page_count >= MAX_DOCUMENT_PAGES:
            raise RequestError(413, "Jumlah halaman melebihi batas satu dokumen.")
        if remaining < 4:
            raise RequestError(400, "Ukuran halaman tidak lengkap.")
        prefix = stream.read(4)
        size = int.from_bytes(prefix, "big")
        remaining -= 4
        if len(prefix) != 4 or not 0 < size <= remaining:
            raise RequestError(400, "Ukuran halaman tidak valid.")
        if size > MAX_PNG_BYTES:
            raise RequestError(413, "Berkas foto terlalu besar.")
        data = stream.read(size)
        if len(data) != size:
            raise RequestError(400, "Data halaman tidak lengkap.")
        image = readPage(data)
        height, width = image.shape[:2]
        total_pixels += height * width
        if total_pixels > MAX_DOCUMENT_PIXELS:
            raise RequestError(413, "Resolusi total halaman terlalu besar.")
        page_count += 1
        remaining -= size
        yield enhancePage(image)


def previewPage(image, mode):
    pixels = renderPageMode(enhancePage(image), mode)
    height, width = pixels.shape[:2]
    if max(width, height) <= 480:
        return pixels
    scale = 480 / max(width, height)
    size = (max(1, round(width * scale)), max(1, round(height * scale)))
    interpolation = cv2.INTER_NEAREST if mode == "black-and-white" else cv2.INTER_AREA
    return cv2.resize(pixels, size, interpolation=interpolation)


def _content_type(headers):
    if hasattr(headers, "get_content_type"):
        return headers.get_content_type()
    return headers.get("Content-Type", "").split(";", 1)[0].strip().lower()


def _json_reply(status, value):
    return status, "application/json; charset=utf-8", json.dumps(value).encode()


def handleApiPost(path, headers, body_stream):
    """Handle TrueScan API POST requests and return (status, media_type, body)."""
    if path not in ("/api/corners", "/api/warp", "/api/preview", "/api/pdf"):
        return _json_reply(404, {"error": "Alamat tidak ditemukan."})
    try:
        length = headers.get("Content-Length", "")
        if not length.isascii() or not length.isdigit() or len(length) > 12:
            raise RequestError(400, "Ukuran data gambar tidak valid.")
        length = int(length)
        if path in ("/api/pdf", "/api/preview"):
            mode = headers.get("X-Document-Mode")
            if mode not in PAGE_MODES:
                raise RequestError(400, "Mode warna dokumen tidak valid.")
        content_type = _content_type(headers)
        if path == "/api/pdf":
            if content_type != "application/octet-stream":
                raise RequestError(415, "Kirim urutan halaman dalam format biner.")
            if length > MAX_DOCUMENT_BYTES:
                raise RequestError(413, "Berkas dokumen terlalu besar.")
            page_size = headers.get("X-Document-Page-Size", "original")
            if page_size not in PAGE_SIZES:
                raise RequestError(400, "Ukuran halaman PDF tidak valid.")
            pdf = exportPdf(readDocumentPages(body_stream, length), mode, page_size=page_size)
            return 200, "application/pdf", pdf
        if content_type != "image/png":
            raise RequestError(415, "Kirim foto dalam format PNG.")
        if length > MAX_PNG_BYTES:
            raise RequestError(413, "Berkas foto terlalu besar.")
        image = readPage(body_stream.read(length))
        if path == "/api/corners":
            points = detectCorners(image)
            return _json_reply(200, {"corners": None if points is None else points.tolist()})
        if path == "/api/preview":
            page = previewPage(image, mode)
        else:
            page = warpPage(image, headers.get("X-Document-Corners"))
        success, encoded = cv2.imencode(".png", page)
        if not success:
            raise RequestError(500, "Gagal membuat gambar halaman.")
        return 200, "image/png", encoded.tobytes()
    except RequestError as error:
        return _json_reply(error.status, {"error": str(error)})
    except cv2.error:
        return _json_reply(400, {"error": "Gambar gagal diproses."})


class ScannerHandler(BaseHTTPRequestHandler):
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
        status, media_type, data = handleApiPost(self.path, self.headers, self.rfile)
        self._reply(status, media_type, data)


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
