"""P16-A-5 (15-V F2): a cwd without config.yaml must give the typed
JSON error and exit 1, never a FileNotFoundError traceback."""

from __future__ import annotations

import json


class TestMissingConfigTypedError:
    """P16-A-5 (15-V F2): running the CLI from a cwd without config.yaml
    must produce the project's typed JSON error and exit 1 — never a raw
    FileNotFoundError traceback (config.py:144, import-time)."""

    def test_empty_cwd_typed_error(self, tmp_path):
        import subprocess
        import sys

        r = subprocess.run(
            [sys.executable, "-m", "niveshdristi", "--json", "version"],
            capture_output=True, text=True, cwd=str(tmp_path), timeout=120,
        )
        assert r.returncode == 1, (
            f"expected exit 1; stdout={r.stdout!r} stderr={r.stderr[-400:]!r}"
        )
        assert "Traceback" not in r.stderr, (
            f"raw traceback leaked: {r.stderr[-400:]!r}"
        )
        d = json.loads(r.stdout)
        assert d["status"] == "error"
        assert "config.yaml" in d["error"]
        assert "project root" in d["error"], (
            f"error must name the remedy; got {d['error']!r}"
        )
        assert "--config" in d["error"], (
            f"error must name --config/-c; got {d['error']!r}"
        )

    def test_explicit_missing_config_typed_error(self, tmp_path):
        import subprocess
        import sys

        r = subprocess.run(
            [sys.executable, "-m", "niveshdristi", "--json",
             "--config", str(tmp_path / "nope.yaml"), "version"],
            capture_output=True, text=True, cwd=str(tmp_path), timeout=120,
        )
        assert r.returncode == 1
        assert "Traceback" not in r.stderr
        d = json.loads(r.stdout)
        assert d["status"] == "error"
        assert "nope.yaml" in d["error"]

    def test_project_root_still_works(self):
        import subprocess
        import sys
        from pathlib import Path

        r = subprocess.run(
            [sys.executable, "-m", "niveshdristi", "--json", "version"],
            capture_output=True, text=True,
            cwd=str(Path(__file__).resolve().parent.parent), timeout=120,
        )
        assert r.returncode == 0, r.stderr[-400:]
        d = json.loads(r.stdout)
        assert d.get("version"), "the version command must answer with JSON"
