#!/usr/bin/env python3
"""load_manifest() names the offending line when a sidecar is not valid TOML.

The prefix `sidecar is not valid TOML` is what other tests match, so it stays first and
the position follows it in the same `line N` wording the trailing whitespace check uses.
"""

from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))

import validate  # noqa: E402

PREFIX = "sidecar is not valid TOML: "


def problems_for(text: str) -> list[str]:
    with tempfile.TemporaryDirectory() as tmp:
        path = Path(tmp) / "fixture.toml"
        path.write_bytes(text.encode("utf-8"))
        corpus = validate.Corpus(Path(tmp))
        result = validate.load_manifest(corpus, path, "fixtures/x/fixture.toml")
    assert result is None
    return corpus.problems


class SidecarParseLine(unittest.TestCase):
    def only_problem(self, text: str) -> str:
        problems = problems_for(text)
        self.assertEqual(len(problems), 1, problems)
        self.assertTrue(problems[0].startswith(f"fixtures/x/fixture.toml: {PREFIX}"), problems[0])
        return problems[0].split(PREFIX, 1)[1]

    def test_bare_value_on_line_three(self) -> None:
        detail = self.only_problem('schema_version = 1\nkind = "captured"\nid = plain\n')
        self.assertTrue(detail.startswith("line 3, column 6: "), detail)

    def test_unclosed_quote_on_line_two(self) -> None:
        detail = self.only_problem('schema_version = 1\nscenario = "never closed\n')
        self.assertTrue(detail.startswith("line 2, column "), detail)

    def test_malformed_table_header_on_line_four(self) -> None:
        detail = self.only_problem("# comment\na = 1\nb = 2\n[table\nc = 3\n")
        self.assertTrue(detail.startswith("line 4, column "), detail)

    def test_duplicate_key_on_line_two(self) -> None:
        detail = self.only_problem("a = 1\na = 2\n")
        self.assertTrue(detail.startswith("line 2, column "), detail)
        self.assertIn("Cannot overwrite a value", detail)

    def test_unterminated_array_reports_the_last_line(self) -> None:
        detail = self.only_problem("a = 1\nshape = [\n")
        self.assertTrue(detail.startswith("line 2 (end of document): "), detail)

    def test_the_reported_line_is_not_repeated_in_the_message(self) -> None:
        detail = self.only_problem("id = plain\n")
        self.assertNotIn("(at line", detail)
        self.assertEqual(detail.count("line 1"), 1)


if __name__ == "__main__":
    unittest.main()
