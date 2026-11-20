import http.client
import json
import threading
import unittest
from http.server import ThreadingHTTPServer

import cv2
import numpy as np

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

    def test_serve_workspace_assets_only(self):
        status, media_type, body = self.request("GET", "/")
        self.assertEqual((status, media_type), (200, "text/html"))
        self.assertIn(b"TrueScan", body)
        status, _, _ = self.request("GET", "/%2e%2e/README.md")
        self.assertEqual(status, 404)
