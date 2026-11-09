# SPDX-License-Identifier: MIT
"""Packaging fixtures must work in a Unicode directory on Western consoles."""
import json
import os
from pathlib import Path
import subprocess
import sys


def test_import_fixture_paths_do_not_depend_on_console_encoding(tmp_path):
    destination = tmp_path / "\u4e2d\u6587 fixtures"
    script = Path(__file__).resolve().parents[1] / "experiments/import_fixtures.py"
    env = dict(os.environ, PYTHONIOENCODING="cp1252", PYTHONUTF8="0")
    result = subprocess.run([sys.executable, "-S", str(script), str(destination)],
                            capture_output=True, env=env, timeout=15)
    assert result.returncode == 0, result.stderr.decode("utf-8", "replace")
    assert json.loads(result.stdout.decode("ascii"))["fixtures"] == str(destination.resolve())
    cases = json.loads((destination / "cases.json").read_text(encoding="utf-8"))
    assert len(cases) == 9 and all(Path(file).is_file() for case in cases for file in case["files"])
