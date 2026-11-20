#!/usr/bin/env python3
"""Boundary test for the account response cap in tools/capture.py.

fetch() reads cap + 1 bytes and refuses when it got more than cap, so a body of exactly
ACCOUNT_CAP bytes is accepted and one byte more is refused. An off-by-one in either the
read size or the comparison would move that threshold without any other test noticing.
The refusal has to happen before capture() creates the fixture directory.
"""

from __future__ import annotations

import http.server
import json
import sys
import tempfile
import threading
import unittest
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path
from unittest import mock

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))
sys.path.insert(0, str(REPO_ROOT / "tools"))

import capture  # noqa: E402

ACCOUNT_ID = "GAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAWHF"


def serve(payload: bytes) -> type[http.server.BaseHTTPRequestHandler]:
    class Handler(http.server.BaseHTTPRequestHandler):
        def do_GET(self) -> None:
            self.send_response(200)
            self.send_header("Content-Length", str(len(payload)))
            self.end_headers()
            self.wfile.write(payload)

        def log_message(self, *args: object) -> None:
            """Silence: the assertion is the output."""

    return Handler


@contextmanager
def loopback(payload: bytes) -> Iterator[str]:
    server = http.server.ThreadingHTTPServer(("127.0.0.1", 0), serve(payload))
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        yield f"http://127.0.0.1:{server.server_address[1]}/"
    finally:
        server.shutdown()
        server.server_close()
        thread.join()


class AccountCapBoundary(unittest.TestCase):
    def test_cap_is_the_documented_size(self) -> None:
        self.assertEqual(capture.ACCOUNT_CAP, 512_000)

    def test_body_of_exactly_the_cap_is_accepted(self) -> None:
        payload = b"x" * capture.ACCOUNT_CAP
        with loopback(payload) as url:
            self.assertEqual(capture.fetch(url, capture.ACCOUNT_CAP), payload)

    def test_body_one_byte_over_the_cap_is_refused(self) -> None:
        payload = b"x" * (capture.ACCOUNT_CAP + 1)
        with loopback(payload) as url, self.assertRaises(capture.Refused) as raised:
            capture.fetch(url, capture.ACCOUNT_CAP)
        self.assertIn(f"exceeds the {capture.ACCOUNT_CAP} byte cap", str(raised.exception))

    def test_oversized_account_leaves_nothing_on_disk(self) -> None:
        root_document = json.dumps(
            {"network_passphrase": capture.PASSPHRASES["public"], "horizon_version": "test"}
        ).encode()
        oversized = b"x" * (capture.ACCOUNT_CAP + 1)
        real_fetch = capture.fetch

        def fake_fetch(url: str, cap: int) -> bytes:
            if url.endswith("/"):
                return root_document
            with loopback(oversized) as local:
                return real_fetch(local, cap)

        with tempfile.TemporaryDirectory() as tmp, mock.patch.object(capture, "fetch", fake_fetch):
            root = Path(tmp)
            with self.assertRaises(capture.Refused) as raised:
                capture.capture("cap-boundary", ACCOUNT_ID, "cap test", "public", root, False)
            self.assertIn("byte cap", str(raised.exception))
            self.assertFalse((root / "fixtures" / "cap-boundary").exists())
            self.assertFalse((root / "fixtures").exists())
            self.assertEqual(list(root.iterdir()), [])


if __name__ == "__main__":
    unittest.main()
