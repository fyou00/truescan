import http.client
import json
import threading
import unittest
from http.server import ThreadingHTTPServer
from unittest.mock import patch

import cv2
import numpy as np
import pypdfium2 as pdfium

from api.index import handler as vercel_handler
from truescan.enhance import enhancePage
from truescan.pdf import renderPageMode
from truescan.server import ScannerHandler


def encode_page(image):
    success, encoded = cv2.imencode(".png", image)
    assert success
    return encoded.tobytes()


class ScannerServerTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.server = ThreadingHTTPServer(("127.0.0.1", 0), ScannerHandler)
        cls.thread = threading.Thread(target=cls.server.serve_forever, daemon=True)
        cls.thread.start()

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown()
        cls.thread.join()
        cls.server.server_close()

    def request(self, method, path, body=None, headers=None):
        connection = http.client.HTTPConnection(*self.server.server_address, timeout=5)
        try:
            connection.request(method, path, body, headers or {})
            response = connection.getresponse()
            if path == "/api/pdf" and response.status == 200:
                self.assertEqual(response.getheader("Content-Disposition"),
                                 'attachment; filename="scan.pdf"')
            return response.status, response.headers.get_content_type(), response.read()
        finally:
            connection.close()

    def post(self, path, data, **headers):
        return self.request("POST", path, data, {"Content-Type": "image/png", **headers})

    def test_detect_corners_in_source_coordinates(self):
        page = np.zeros((200, 300, 3), np.uint8)
        cv2.rectangle(page, (45, 20), (255, 180), (230, 230, 230), -1)
        status, _, body = self.post("/api/corners", encode_page(page))
        self.assertEqual(status, 200)
        np.testing.assert_allclose(json.loads(body)["corners"],
                                   [[45, 20], [255, 20], [255, 180], [45, 180]], atol=3)

    def test_missing_outline_then_manual_warp(self):
        source = np.full((80, 140, 3), 225, np.uint8)
        source[15:20, 20:25] = [20, 30, 90]
        png = encode_page(source)
        status, _, body = self.post("/api/corners", png)
        self.assertEqual((status, json.loads(body)), (200, {"corners": None}))
        corners = [[10, 10], [129, 10], [129, 69], [10, 69]]
        status, media_type, body = self.post("/api/warp", png, **{
            "X-Document-Corners": json.dumps(corners),
        })
        self.assertEqual((status, media_type), (200, "image/png"))
        result = cv2.imdecode(np.frombuffer(body, np.uint8), cv2.IMREAD_COLOR)
        np.testing.assert_array_equal(result, source[10:70, 10:130])

    def test_invalid_requests(self):
        png = encode_page(np.zeros((20, 20), np.uint8))
        cases = [
            ("/api/corners", b"invalid", {}, 400),
            ("/api/corners", png, {"Content-Type": "image/jpeg"}, 415),
            ("/api/warp", png, {}, 400),
            ("/api/warp", png, {"X-Document-Corners": "{invalid"}, 400),
            ("/api/warp", png, {"X-Document-Corners": "[[0,0],[0,0],[0,0],[0,0]]"}, 400),
            ("/api/corners", png, {"Origin": "https://example.org"}, 403),
            ("/api/corners", png, {"Host": "example.org"}, 403),
        ]
        for path, data, extra, expected in cases:
            with self.subTest(path=path, headers=extra):
                status, media_type, body = self.post(path, data, **extra)
                self.assertEqual((status, media_type), (expected, "application/json"))
                self.assertIn("error", json.loads(body))

    def test_download_matches_mode_previews_in_request_order(self):
        horizontal = np.full((100, 150, 3), (235, 210, 195), np.uint8)
        horizontal[15:20, 10:80] = (20, 45, 110)
        vertical = np.full((150, 100, 3), (210, 235, 245), np.uint8)
        vertical[35:110, 20:25] = (80, 35, 10)
        pages = [vertical, horizontal]
        encoded = [encode_page(page) for page in pages]
        body = b"".join(len(page).to_bytes(4, "big") + page for page in encoded)
        for mode in ("color", "grayscale", "black-and-white"):
            with self.subTest(mode=mode):
                headers = {"X-Document-Mode": mode}
                status, media_type, pdf = self.post("/api/pdf", body, **headers,
                                                    **{"Content-Type": "application/octet-stream"})
                self.assertEqual((status, media_type), (200, "application/pdf"))
                with pdfium.PdfDocument(pdf) as document:
                    self.assertEqual(len(document), 2)
                    for index, (page, png) in enumerate(zip(pages, encoded)):
                        status, media_type, data = self.post("/api/preview", png, **headers)
                        self.assertEqual((status, media_type), (200, "image/png"))
                        preview = cv2.imdecode(np.frombuffer(data, np.uint8), cv2.IMREAD_UNCHANGED)
                        expected = renderPageMode(enhancePage(page), mode)
                        np.testing.assert_array_equal(preview, expected)
                        expected_bgr = cv2.imdecode(np.frombuffer(data, np.uint8), cv2.IMREAD_COLOR)
                        pdf_page = document[index]
                        bitmap = pdf_page.render(scale=300 / 72)
                        try:
                            np.testing.assert_array_equal(bitmap.to_numpy()[:, :, :3], expected_bgr)
                        finally:
                            bitmap.close()
                            pdf_page.close()

    def test_large_binary_preview_remains_binary(self):
        photo = np.full((320, 960), 225, np.uint8)
        photo[20:25, 20:800] = 20
        status, _, data = self.post("/api/preview", encode_page(photo),
                                    **{"X-Document-Mode": "black-and-white"})
        self.assertEqual(status, 200)
        result = cv2.imdecode(np.frombuffer(data, np.uint8), cv2.IMREAD_UNCHANGED)
        self.assertEqual(result.shape, (160, 480))
        np.testing.assert_array_equal(np.unique(result), [0, 255])

    def test_select_a4_for_pdf_download(self):
        png = encode_page(np.full((160, 80), 220, np.uint8))
        frame = len(png).to_bytes(4, "big") + png
        headers = {"Content-Type": "application/octet-stream", "X-Document-Mode": "color",
                   "X-Document-Page-Size": "a4"}
        status, media_type, data = self.post("/api/pdf", frame, **headers)
        self.assertEqual((status, media_type), (200, "application/pdf"))
        with pdfium.PdfDocument(data) as document:
            np.testing.assert_allclose(document[0].get_size(), np.array([210, 297]) * 72 / 25.4,
                                       atol=0.01)
        headers["X-Document-Page-Size"] = "letter"
        status, media_type, data = self.post("/api/pdf", frame, **headers)
        self.assertEqual((status, media_type), (400, "application/json"))
        self.assertIn("error", json.loads(data))

    def test_invalid_pdf_batch(self):
        png = encode_page(np.zeros((20, 20), np.uint8))
        frame = len(png).to_bytes(4, "big") + png
        headers = {"Content-Type": "application/octet-stream", "X-Document-Mode": "color"}
        for body in (b"", frame + b"x", frame[:-1], b"\x00" * 4):
            status, media_type, data = self.post("/api/pdf", body, **headers)
            self.assertEqual((status, media_type), (400, "application/json"))
            self.assertIn("error", json.loads(data))
        for setting, limit in (("MAX_DOCUMENT_BYTES", len(frame)), ("MAX_DOCUMENT_PIXELS", 400),
                               ("MAX_DOCUMENT_PAGES", 1)):
            with self.subTest(setting=setting), patch("truescan.server." + setting, limit):
                status, _, _ = self.post("/api/pdf", frame * 2, **headers)
                self.assertEqual(status, 413)
        for path in ("/api/preview", "/api/pdf"):
            status, _, _ = self.post(path, png, **{"X-Document-Mode": "sepia"})
            self.assertEqual(status, 400)

    def test_serve_workspace_assets_only(self):
        status, media_type, body = self.request("GET", "/")
        self.assertEqual((status, media_type), (200, "text/html"))
        self.assertIn(b"TrueScan", body)
        status, _, _ = self.request("GET", "/%2e%2e/README.md")
        self.assertEqual(status, 404)


class VercelHandlerTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.server = ThreadingHTTPServer(("127.0.0.1", 0), vercel_handler)
        cls.thread = threading.Thread(target=cls.server.serve_forever, daemon=True)
        cls.thread.start()

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown()
        cls.thread.join()
        cls.server.server_close()

    def request(self, method, path, body=None, headers=None):
        connection = http.client.HTTPConnection(*self.server.server_address, timeout=5)
        try:
            connection.request(method, path, body, headers or {})
            response = connection.getresponse()
            return (
                response.status,
                response.headers.get_content_type(),
                response.headers,
                response.read(),
            )
        finally:
            connection.close()

    def test_health_and_unknown_get_routes(self):
        for path in ("/api/health", "/api/index?endpoint=health"):
            with self.subTest(path=path):
                status, media_type, _, body = self.request("GET", path)
                self.assertEqual((status, media_type, json.loads(body)),
                                 (200, "application/json", {"status": "ok"}))
        status, media_type, _, body = self.request("GET", "/api/index?endpoint=unknown")
        self.assertEqual((status, media_type), (404, "application/json"))
        self.assertIn("error", json.loads(body))

    def test_corners_warp_preview_and_pdf_routes(self):
        page = np.zeros((200, 300, 3), np.uint8)
        cv2.rectangle(page, (45, 20), (255, 180), (230, 230, 230), -1)
        png = encode_page(page)

        for path in ("/api/index?endpoint=corners", "/api/corners"):
            with self.subTest(path=path):
                status, media_type, _, body = self.request(
                    "POST", path, png, {"Content-Type": "image/png"},
                )
                self.assertEqual((status, media_type), (200, "application/json"))
                np.testing.assert_allclose(json.loads(body)["corners"],
                                           [[45, 20], [255, 20], [255, 180], [45, 180]], atol=3)

        corners = [[45, 20], [255, 20], [255, 180], [45, 180]]
        status, media_type, _, body = self.request(
            "POST",
            "/api/index?endpoint=warp",
            png,
            {"Content-Type": "image/png", "X-Document-Corners": json.dumps(corners)},
        )
        self.assertEqual((status, media_type), (200, "image/png"))
        warped = cv2.imdecode(np.frombuffer(body, np.uint8), cv2.IMREAD_COLOR)
        self.assertEqual(warped.shape[:2], (161, 211))

        status, media_type, _, body = self.request(
            "POST",
            "/api/index?endpoint=preview",
            encode_page(warped),
            {"Content-Type": "image/png", "X-Document-Mode": "grayscale"},
        )
        self.assertEqual((status, media_type), (200, "image/png"))
        preview = cv2.imdecode(np.frombuffer(body, np.uint8), cv2.IMREAD_UNCHANGED)
        self.assertEqual(preview.ndim, 2)

        frame = len(png).to_bytes(4, "big") + png
        status, media_type, resp_headers, pdf = self.request(
            "POST",
            "/api/index?endpoint=pdf",
            frame,
            {
                "Content-Type": "application/octet-stream",
                "X-Document-Mode": "color",
                "X-Document-Page-Size": "a4",
            },
        )
        self.assertEqual((status, media_type), (200, "application/pdf"))
        self.assertEqual(resp_headers.get("Content-Disposition"),
                         'attachment; filename="scan.pdf"')
        with pdfium.PdfDocument(pdf) as document:
            self.assertEqual(len(document), 1)
            np.testing.assert_allclose(document[0].get_size(),
                                       np.array([297, 210]) * 72 / 25.4, atol=0.01)

    def test_same_origin_check(self):
        png = encode_page(np.zeros((20, 20), np.uint8))
        status, media_type, _, _ = self.request(
            "POST",
            "/api/index?endpoint=corners",
            png,
            {
                "Content-Type": "image/png",
                "Origin": "https://truescan-demo.vercel.app",
                "X-Forwarded-Host": "truescan-demo.vercel.app",
            },
        )
        self.assertEqual((status, media_type), (200, "application/json"))

        status, media_type, _, body = self.request(
            "POST",
            "/api/index?endpoint=corners",
            png,
            {
                "Content-Type": "image/png",
                "Origin": "https://evil.example",
                "X-Forwarded-Host": "truescan-demo.vercel.app",
            },
        )
        self.assertEqual((status, media_type), (403, "application/json"))
        self.assertIn("error", json.loads(body))
