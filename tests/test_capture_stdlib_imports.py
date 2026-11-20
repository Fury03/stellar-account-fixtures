#!/usr/bin/env python3
"""tools/capture.py may import only the standard library and this repository's own modules.

ROADMAP.md D-02 and CONTRIBUTING.md make the tooling standard-library only. A third-party
import would pass on any machine that happens to have the package installed and fail
only for a consumer on a clean interpreter, so this reads the source with `ast` and never
imports or runs it.
"""

from __future__ import annotations

import ast
import sys
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
CAPTURE = REPO_ROOT / "tools" / "capture.py"

# Modules that live in this repository and that capture.py is allowed to import.
LOCAL_MODULES = frozenset(
    {path.stem for path in REPO_ROOT.glob("*.py")}
    | {path.stem for path in (REPO_ROOT / "tools").glob("*.py")}
)


def top_level_imports(source: str) -> set[str]:
    """Top-level names of every absolute import in `source`, at any depth."""
    names: set[str] = set()
    for node in ast.walk(ast.parse(source)):
        if isinstance(node, ast.Import):
            names.update(alias.name.split(".")[0] for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.level == 0 and node.module:
            names.add(node.module.split(".")[0])
    return names


def non_stdlib(source: str) -> list[str]:
    allowed = sys.stdlib_module_names | LOCAL_MODULES
    return sorted(name for name in top_level_imports(source) if name not in allowed)


class CaptureImportsStdlibOnly(unittest.TestCase):
    def test_capture_imports_nothing_outside_the_standard_library(self) -> None:
        offenders = non_stdlib(CAPTURE.read_text(encoding="utf-8"))
        self.assertEqual(
            offenders,
            [],
            f"tools/capture.py imports non-standard modules {offenders}; "
            "the corpus tooling is standard library only (ROADMAP.md D-02)",
        )

    def test_capture_still_imports_the_local_validator(self) -> None:
        self.assertIn("validate", top_level_imports(CAPTURE.read_text(encoding="utf-8")))

    def test_an_external_import_is_reported(self) -> None:
        self.assertEqual(non_stdlib("import requests\nimport json\n"), ["requests"])

    def test_an_external_from_import_is_reported(self) -> None:
        self.assertEqual(non_stdlib("from toml import loads\n"), ["toml"])

    def test_a_nested_external_import_is_reported(self) -> None:
        source = "def f():\n    import yaml.constructor\n"
        self.assertEqual(non_stdlib(source), ["yaml"])

    def test_standard_library_and_local_imports_pass(self) -> None:
        source = "import urllib.request\nfrom pathlib import Path\nfrom validate import shapes_of\n"
        self.assertEqual(non_stdlib(source), [])


if __name__ == "__main__":
    unittest.main()
