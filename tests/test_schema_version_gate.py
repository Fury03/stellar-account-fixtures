#!/usr/bin/env python3
"""schema_version is the integer 1, never a string, float, bool or other integer."""

from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))

import validate  # noqa: E402

ALPHABET = "ABCDEFGHIJKLMNOPQRSTUVWXYZ234567"
WHERE = "fixtures/plain"


def account_id() -> str:
    body = bytes([48]) + bytes(range(32))
    raw = body + validate.crc16_xmodm(body).to_bytes(2, "little")
    bits = int.from_bytes(raw, "big")
    return "".join(ALPHABET[(bits >> (5 * (55 - index))) & 0x1F] for index in range(56))


ACCOUNT = account_id()
SIDECAR = f"""# Test sidecar.
schema_version = {{version}}
id = "plain"
kind = "captured"
scenario = "a plain account used to test the schema version gate"
account_id = "{ACCOUNT}"
network = "public"
source_url = "https://horizon.stellar.org/accounts/{ACCOUNT}"
captured_at = "2026-11-02T00:00:00Z"
ledger = 1
horizon_version = "30.0.0"
sha256 = "{"0" * 64}"
shape = ["no_data"]
"""


class SchemaVersionGate(unittest.TestCase):
    def setUp(self) -> None:
        stage = tempfile.TemporaryDirectory(prefix="schema-version-gate-test-")
        self.addCleanup(stage.cleanup)
        self.root = Path(stage.name)
        self.path = self.root / "fixture.toml"

    def load(self, declared: str) -> tuple[validate.Corpus, dict | None]:
        self.path.write_text(SIDECAR.format(version=declared), encoding="utf-8")
        corpus = validate.Corpus(self.root)
        data = validate.load_manifest(corpus, self.path, WHERE)
        return corpus, data

    def test_integer_one_passes_cleanly(self) -> None:
        corpus, data = self.load(str(validate.SCHEMA_VERSION))
        self.assertEqual(corpus.problems, [])
        self.assertIsNotNone(data)
        assert data is not None
        self.assertEqual(data["schema_version"], 1)
        self.assertIs(type(data["schema_version"]), int)

    def test_string_one_is_rejected_with_the_exact_message(self) -> None:
        corpus, _ = self.load('"1"')
        self.assertEqual(corpus.problems, [f"{WHERE}: schema_version '1' must be an integer"])

    def test_float_one_is_rejected_with_the_exact_message(self) -> None:
        corpus, _ = self.load("1.0")
        self.assertEqual(corpus.problems, [f"{WHERE}: schema_version 1.0 must be an integer"])

    def test_boolean_true_is_rejected_with_the_exact_message(self) -> None:
        corpus, _ = self.load("true")
        self.assertEqual(corpus.problems, [f"{WHERE}: schema_version True must be an integer"])

    def test_boolean_false_is_rejected_with_the_exact_message(self) -> None:
        corpus, _ = self.load("false")
        self.assertEqual(corpus.problems, [f"{WHERE}: schema_version False must be an integer"])

    def test_unsupported_integer_is_rejected_with_the_exact_message(self) -> None:
        corpus, _ = self.load("2")
        self.assertEqual(
            corpus.problems,
            [f"{WHERE}: schema_version 2, this tool reads {validate.SCHEMA_VERSION}"],
        )

    def test_negative_integer_is_rejected_with_the_exact_message(self) -> None:
        corpus, _ = self.load("-1")
        self.assertEqual(
            corpus.problems,
            [f"{WHERE}: schema_version -1, this tool reads {validate.SCHEMA_VERSION}"],
        )

    def test_one_without_type_drift_compares_equal_to_one_point_zero(self) -> None:
        self.assertEqual(1, 1.0)
        self.assertIsInstance(True, int)
        corpus, _ = self.load("1")
        self.assertEqual(corpus.problems, [])


if __name__ == "__main__":
    unittest.main()
