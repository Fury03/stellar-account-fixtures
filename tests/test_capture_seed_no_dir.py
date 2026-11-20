#!/usr/bin/env python3
"""A seed-shaped response must be refused before capture() creates any directory.

capture() scans the raw body for a secret-seed pattern and only then calls
directory.mkdir. If the order flipped, a refused capture would leave an empty fixture
directory behind: validate.py would then report missing files instead of the real
cause, and the next attempt would need --update. The sample below is built at run time
from a fixed filler, so nothing in this tree is a key.
"""

from __future__ import annotations

import io
import json
import sys
import tempfile
import unittest
from contextlib import redirect_stderr
from pathlib import Path
from unittest import mock

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))
sys.path.insert(0, str(REPO_ROOT / "tools"))

import capture  # noqa: E402

ACCOUNT_ID = "GAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAWHF"
FIXTURE_ID = "seed-refusal"
# Matches SEED_SHAPE (S followed by 55 base32 characters) and decodes to nothing real.
SEED_LOOKALIKE = "S" + "B" * 55
SEED_MESSAGE = "captured body contains a seed-shaped string; refusing to write it"


class FakeHorizon:
    """Stands in for capture.fetch: a valid root document and a hostile account body."""

    def __init__(self, account_body: bytes) -> None:
        self.account_body = account_body
        self.urls: list[str] = []

    def __call__(self, url: str, cap: int) -> bytes:
        self.urls.append(url)
        if url.endswith("/accounts/" + ACCOUNT_ID):
            return self.account_body
        return json.dumps(
            {"network_passphrase": capture.PASSPHRASES["public"], "horizon_version": "test"}
        ).encode()


def seed_body() -> bytes:
    return json.dumps({"account_id": ACCOUNT_ID, "data": {"note": SEED_LOOKALIKE}}).encode()


class SeedRefusalLeavesNoDirectory(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)

    def run_capture(self, body: bytes) -> FakeHorizon:
        fake = FakeHorizon(body)
        with mock.patch.object(capture, "fetch", fake):
            capture.capture(FIXTURE_ID, ACCOUNT_ID, "seed test", "public", self.root, False)
        return fake

    def test_sample_matches_the_seed_pattern(self) -> None:
        self.assertIsNotNone(capture.SEED_SHAPE.search(seed_body()))

    def test_seed_shaped_body_is_refused(self) -> None:
        with self.assertRaises(capture.Refused) as raised:
            self.run_capture(seed_body())
        self.assertEqual(str(raised.exception), SEED_MESSAGE)

    def test_nothing_is_created_on_disk(self) -> None:
        with self.assertRaises(capture.Refused):
            self.run_capture(seed_body())
        self.assertFalse((self.root / "fixtures" / FIXTURE_ID).exists())
        self.assertFalse((self.root / "fixtures").exists())
        self.assertFalse((self.root / "corpus").exists())
        self.assertEqual(list(self.root.iterdir()), [])

    def test_main_reports_exit_two_with_the_diagnostic(self) -> None:
        stderr = io.StringIO()
        with (
            mock.patch.object(capture, "fetch", FakeHorizon(seed_body())),
            redirect_stderr(stderr),
        ):
            code = capture.main(
                [
                    "--network",
                    "public",
                    "--account",
                    ACCOUNT_ID,
                    "--id",
                    FIXTURE_ID,
                    "--scenario",
                    "seed test",
                    "--root",
                    str(self.root),
                ]
            )
        self.assertEqual(code, 2)
        self.assertEqual(stderr.getvalue().strip(), f"capture refused: {SEED_MESSAGE}")
        self.assertEqual(list(self.root.iterdir()), [])

    def test_a_clean_body_is_not_refused_by_the_seed_check(self) -> None:
        clean = json.dumps({"account_id": ACCOUNT_ID, "last_modified_ledger": 1}).encode()
        self.run_capture(clean)
        self.assertTrue((self.root / "fixtures" / FIXTURE_ID / "account.json").is_file())


if __name__ == "__main__":
    unittest.main()
