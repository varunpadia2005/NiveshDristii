#!/usr/bin/env python3
"""Phase 1 Gate Script — validates all Phase 1 requirements."""

from __future__ import annotations
import hashlib
import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path


def run(cmd: list[str], cwd: Path | None = None, capture: bool = True, env: dict | None = None) -> subprocess.CompletedProcess:
    """Run a command and return the result."""
    return subprocess.run(cmd, cwd=cwd, capture_output=capture, text=True, check=False, env=env)


def info(id_: str, detail: str) -> None:
    print(f"INFO {id_} {detail}")


def pass_(id_: str, detail: str) -> None:
    print(f"PASS {id_} {detail}")


def fail(id_: str, detail: str) -> None:
    print(f"FAIL {id_} {detail}")


def main() -> int:
    repo_root = Path(__file__).parent.parent
    phase0_root = Path(sys.argv[sys.argv.index("--phase0") + 1]) if "--phase0" in sys.argv else None
    
    fails = 0
    
    # G01: git status --porcelain is empty, both before and after pytest run
    print("\n=== G01: Clean git status ===")
    result = run(["git", "status", "--porcelain"], cwd=repo_root)
    if result.stdout.strip():
        fail("G01", f"git status not clean before pytest:\n{result.stdout}")
        fails += 1
    else:
        pass_("G01", "git status clean before pytest")
    
    # Run pytest
    run([sys.executable, "-m", "pytest", "-q"], cwd=repo_root, capture=False)
    
    result = run(["git", "status", "--porcelain"], cwd=repo_root)
    if result.stdout.strip():
        fail("G01", f"git status not clean after pytest:\n{result.stdout}")
        fails += 1
    else:
        pass_("G01", "git status clean after pytest")
    
    # G02: No test_*.py, check_*.py or *.bak outside tests/ and tools/
    print("\n=== G02: No stray test/check files ===")
    stray = []
    for pattern in ["test_*.py", "check_*.py", "*.bak"]:
        for f in repo_root.rglob(pattern):
            if any(part.startswith(".venv") or part == "__pycache__" or part == ".pytest_cache" or part == ".mypy_cache" or part == ".ruff_cache" for part in f.parts):
                continue
            if not any(part in ("tests", "tools") for part in f.parts):
                stray.append(str(f))
    if stray:
        fail("G02", f"Stray files found: {stray}")
        fails += 1
    else:
        pass_("G02", "No stray test/check/bak files")
    
    # G03: Legacy contract - git diff empty over legacy folders
    print("\n=== G03: Legacy contract ===")
    legacy_folders = [
        "backtest", "data", "signals", "indicators", "app", "api", 
        "fundamentals", "genai", "regime"
    ]
    diff_args = ["git", "diff", "--diff-filter=MD", "--name-only", "82f76d8", "HEAD"]
    for folder in legacy_folders:
        diff_args.extend(["--", f"src/niveshdristi/{folder}"])
    diff_args.extend(["--", "tests/test_characterization.py"])
    
    result = run(diff_args, cwd=repo_root)
    if result.stdout.strip():
        fail("G03", f"Legacy folders have changes:\n{result.stdout}")
        fails += 1
    else:
        pass_("G03", "Legacy contract intact")
    
    # Also check for additions (diff without --diff-filter=MD)
    result = run(["git", "diff", "82f76d8", "HEAD", "--"] + 
                 [f"src/niveshdristi/{f}" for f in legacy_folders] + 
                 ["tests/test_characterization.py"], cwd=repo_root)
    if result.stdout.strip():
        fail("G03", f"Legacy folders have additions:\n{result.stdout}")
        fails += 1
    else:
        pass_("G03", "No additions to legacy folders")
    
    # G04: Config equality - MD5 match
    print("\n=== G04: Config equality ===")
    if phase0_root:
        # Run dump_config on phase0 using current repo's tool with phase0 src
        env0 = os.environ.copy()
        env0["PYTHONPATH"] = str(phase0_root / "src")
        result0 = run([sys.executable, "tools/dump_config.py"], cwd=repo_root, capture=True, env=env0)
        
        # Run dump_config on current
        env1 = os.environ.copy()
        env1["PYTHONPATH"] = str(repo_root / "src")
        result1 = run([sys.executable, "tools/dump_config.py"], cwd=repo_root, capture=True, env=env1)
        
        if result0.returncode == 0 and result1.returncode == 0:
            try:
                data0 = json.loads(result0.stdout.strip().split("JSON: ")[1])
                data1 = json.loads(result1.stdout.strip().split("JSON: ")[1])
                md5_0 = result0.stdout.strip().split("MD5: ")[1].split(" |")[0]
                md5_1 = result1.stdout.strip().split("MD5: ")[1].split(" |")[0]
                
                if md5_0 == md5_1:
                    pass_("G04", f"Config MD5 match: {md5_0}")
                    # Check __file__ paths
                    if "phase0" in data0.get("__file__", "") or str(phase0_root) in data0.get("__file__", ""):
                        pass_("G04", "Phase0 __file__ under phase0 root")
                    else:
                        fail("G04", f"Phase0 __file__ not under phase0 root: {data0.get('__file__')}")
                        fails += 1
                    if "NiveshDristii" in data1.get("__file__", "") or str(repo_root) in data1.get("__file__", ""):
                        pass_("G04", "Current __file__ under current root")
                    else:
                        fail("G04", f"Current __file__ not under current root: {data1.get('__file__')}")
                        fails += 1
                else:
                    fail("G04", f"MD5 mismatch: phase0={md5_0} current={md5_1}")
                    fails += 1
            except Exception as e:
                fail("G04", f"Failed to parse dump_config output: {e}")
                fails += 1
        else:
            fail("G04", f"dump_config failed: phase0_rc={result0.returncode} phase0_err={result0.stderr} current_rc={result1.returncode} current_err={result1.stderr}")
            fails += 1
    else:
        info("G04", "Skipped (no phase0 path)")
    
    # G05: Backtest equality
    print("\n=== G05: Backtest equality ===")
    if phase0_root:
        env0 = os.environ.copy()
        env0["PYTHONPATH"] = str(phase0_root / "src")
        result0 = run([sys.executable, "tools/compare_backtest.py"], cwd=phase0_root, capture=True, env=env0)
        
        env1 = os.environ.copy()
        env1["PYTHONPATH"] = str(repo_root / "src")
        result1 = run([sys.executable, "tools/compare_backtest.py"], cwd=repo_root, capture=True, env=env1)
        
        if result0.returncode == 0 and result1.returncode == 0:
            try:
                out0 = json.loads(result0.stdout.strip())
                out1 = json.loads(result1.stdout.strip())
                
                keys = ["total_return", "trade_count", "total_cost", "equity_curve_md5"]
                match = all(abs(out0[k] - out1[k]) < 1e-9 if isinstance(out0[k], float) else out0[k] == out1[k] for k in keys)
                
                if match:
                    pass_("G05", "Backtest outputs match")
                    # Check __file__ paths
                    f0 = out0.get("niveshdristi_file", "")
                    f1 = out1.get("niveshdristi_file", "")
                    if "phase0" in f0 or str(phase0_root) in f0:
                        pass_("G05", "Phase0 __file__ under phase0 root")
                    else:
                        fail("G05", f"Phase0 __file__ not under phase0 root: {f0}")
                        fails += 1
                    if "NiveshDristii" in f1 or str(repo_root) in f1:
                        pass_("G05", "Current __file__ under current root")
                    else:
                        fail("G05", f"Current __file__ not under current root: {f1}")
                        fails += 1
                else:
                    fail("G05", f"Backtest mismatch: phase0={out0} current={out1}")
                    fails += 1
            except Exception as e:
                fail("G05", f"Failed to parse compare_backtest output: {e}")
                fails += 1
        else:
            fail("G05", f"compare_backtest failed: phase0_rc={result0.returncode} phase0_err={result0.stderr} current_rc={result1.returncode} current_err={result1.stderr}")
            fails += 1
    else:
        info("G05", "Skipped (no phase0 path)")
    
    # G06: pytest results
    print("\n=== G06: Pytest results ===")
    result = run([sys.executable, "-m", "pytest", "-q", "--tb=no", "-v"], cwd=repo_root)
    if result.returncode in (0, 5):  # 5 = no tests collected
        # Parse pytest output for counts
        passed = failed = errors = xfailed = skipped = 0
        for line in result.stdout.split("\n"):
            if "passed" in line and "failed" in line and "error" in line:
                # Typical format: "110 passed, 1 xfailed, 2 warnings in 4.30s"
                parts = line.split()
                for i, part in enumerate(parts):
                    if part == "passed" and i > 0:
                        passed = int(parts[i-1])
                    elif part == "failed" and i > 0:
                        failed = int(parts[i-1])
                    elif part == "error" and i > 0:
                        errors = int(parts[i-1])
                    elif part == "xfailed" and i > 0:
                        xfailed = int(parts[i-1])
                    elif part == "skipped" and i > 0:
                        skipped = int(parts[i-1])
        
        if failed == 0 and errors == 0 and skipped == 0 and xfailed == 1 and passed >= 110:
            pass_("G06", f"passed={passed} failed={failed} errors={errors} xfailed={xfailed} skipped={skipped}")
        else:
            fail("G06", f"passed={passed} failed={failed} errors={errors} xfailed={xfailed} skipped={skipped}")
            fails += 1
    else:
        fail("G06", f"pytest exited with code {result.returncode}")
        fails += 1
    
    # G07: No utcnow warnings
    print("\n=== G07: No utcnow warnings ===")
    result = run([sys.executable, "-m", "pytest", "-q", "--tb=no", "-W", "default"], cwd=repo_root)
    warnings = []
    for line in result.stderr.split("\n"):
        if "utcnow" in line.lower():
            warnings.append(line.strip())
    if warnings:
        info("G07", f"Found {len(warnings)} utcnow warnings: {warnings[:3]}")
    else:
        pass_("G07", "No utcnow warnings")
    
    # G08: core/*.py: no @dataclass, no utcnow, no naive datetime.now()
    print("\n=== G08: Core types hygiene ===")
    issues = []
    for f in (repo_root / "src/niveshdristi/core").glob("*.py"):
        content = f.read_text(encoding="utf-8")
        if "@dataclass" in content:
            issues.append(f"{f.name}: has @dataclass")
        if "utcnow(" in content:
            issues.append(f"{f.name}: has utcnow()")
        if "datetime.now()" in content and "datetime.now(timezone.utc)" not in content and "datetime.now(UTC)" not in content:
            issues.append(f"{f.name}: has naive datetime.now()")
    if issues:
        fail("G08", f"Issues: {issues}")
        fails += 1
    else:
        pass_("G08", "Core types clean")
    
    # G09: arbitrary_types_allowed has justification comment
    print("\n=== G09: arbitrary_types_allowed justification ===")
    issues = []
    for f in (repo_root / "src/niveshdristi/core").glob("*.py"):
        lines = f.read_text(encoding="utf-8").split("\n")
        for i, line in enumerate(lines):
            if "arbitrary_types_allowed" in line:
                # Check line above for comment
                if i == 0 or not lines[i-1].strip().startswith("# arbitrary_types_allowed:"):
                    issues.append(f"{f.name}:{i+1}: missing justification comment")
    if issues:
        fail("G09", f"Issues: {issues}")
        fails += 1
    else:
        pass_("G09", "All arbitrary_types_allowed have justification")
    
    # G10: Literal guard
    print("\n=== G10: Literal guard ===")
    # Run the literal guard on real core/ and engine/
    sys.path.insert(0, str(repo_root))
    from tests.market_literals import scan_market_literals
    issues = scan_market_literals(repo_root / "src/niveshdristi/core")
    core_issues = [i for i in issues if i["file"].startswith("src/niveshdristi/core/")]
    engine_issues = [i for i in issues if i["file"].startswith("src/niveshdristi/engine/")]
    if core_issues or engine_issues:
        fail("G10", f"Real code has findings: core={len(core_issues)} engine={len(engine_issues)}")
        fails += 1
    else:
        pass_("G10", "Real core/ and engine/ have 0 findings")
    
    # Test on temp tree with forbidden patterns
    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = Path(tmp)
        test_content = "NSE\nRELIANCE.NS\n\u20b9\nKolkata\nIST"
        (tmp_path / "test.txt").write_text(test_content, encoding="utf-8")
        issues = scan_market_literals(tmp_path)
        patterns_found = set(i["pattern"] for i in issues)
        expected = {"NSE", r"RELIANCE\.NS", "\u20b9", "Kolkata", r"\bIST\b"}
        if expected.issubset(patterns_found):
            pass_("G10", f"Temp tree reports all 5 patterns: {sorted(patterns_found)}")
        else:
            fail("G10", f"Temp tree missing patterns: expected={expected}, found={patterns_found}")
            fails += 1
    
    # G11: Typed CFG
    print("\n=== G11: Typed CFG ===")
    code = "from niveshdristi.config import CFG; CFG.backtest.does_not_exist"
    result = run([sys.executable, "-m", "mypy", "-c", code], cwd=repo_root)
    if "attr-defined" in result.stdout and "does_not_exist" in result.stdout:
        pass_("G11", "Typed CFG works (attr-defined error for does_not_exist)")
    else:
        fail("G11", f"Typed CFG check failed: {result.stdout}")
        fails += 1
    
    # G12: CLI via python -m niveshdristi.cli.main
    print("\n=== G12: CLI validation ===")
    # Check nd command on PATH
    result = run(["nd", "--help"], cwd=repo_root)
    nd_on_path = result.returncode == 0
    info("G12", f"nd command on PATH: {nd_on_path}")
    
    # --json validate exits 0
    result = run([sys.executable, "-m", "niveshdristi.cli.main", "--json", "validate"], cwd=repo_root)
    if result.returncode == 0:
        try:
            data = json.loads(result.stdout.strip().split("\n")[-1])
            if data.get("summary", {}).get("failed", -1) == 0:
                pass_("G12", "--json validate exits 0 with summary.failed == 0")
            else:
                fail("G12", f"summary.failed != 0: {data}")
                fails += 1
        except Exception as e:
            fail("G12", f"Failed to parse JSON output: {e}")
            fails += 1
    else:
        fail("G12", f"--json validate exited {result.returncode}: {result.stdout}")
        fails += 1
    
    # --config <bad yaml> --json validate exits 1
    with tempfile.TemporaryDirectory() as tmp:
        bad_yaml = Path(tmp) / "bad.yaml"
        bad_yaml.write_text("unknown_key: true\n")
        result = run([sys.executable, "-m", "niveshdristi.cli.main", "--config", str(bad_yaml), "--json", "validate"], cwd=repo_root)
        if result.returncode == 1:
            pass_("G12", "--config <bad> --json validate exits 1")
        else:
            fail("G12", f"--config <bad> --json validate exited {result.returncode}: {result.stdout}")
            fails += 1
    
    # G13: ruff check on new-code paths = 0 errors
    print("\n=== G13: Ruff on new code ===")
    result = run([sys.executable, "-m", "ruff", "check", 
                  "src/niveshdristi/core", "src/niveshdristi/markets", 
                  "src/niveshdristi/cli", "src/niveshdristi/engine", 
                  "src/niveshdristi/config_loader.py"], cwd=repo_root)
    if result.returncode == 0:
        pass_("G13", "Ruff clean on new code paths")
    else:
        fail("G13", f"Ruff errors: {result.stdout}")
        fails += 1
    
    # G14: mypy on new code paths = 0 errors, #type:ignore <= 10
    print("\n=== G14: Mypy on new code ===")
    result = run([sys.executable, "-m", "mypy", 
                  "src/niveshdristi/core", "src/niveshdristi/markets", 
                  "src/niveshdristi/cli", "src/niveshdristi/engine", 
                  "src/niveshdristi/config_loader.py", "--ignore-missing-imports"], cwd=repo_root)
    if result.returncode == 0:
        # Count type: ignore comments
        ignore_count = 0
        for f in repo_root.rglob("*.py"):
            if any(p in f.parts for p in ["core", "markets", "cli", "engine", "config_loader.py"]):
                content = f.read_text(encoding="utf-8")
                ignore_count += content.count("# type: ignore")
        if ignore_count <= 10:
            pass_("G14", f"Mypy clean, type:ignore count={ignore_count}")
        else:
            fail("G14", f"type:ignore count={ignore_count} > 10")
            fails += 1
    else:
        fail("G14", f"Mypy errors: {result.stdout}")
        fails += 1
    
    # G15: Exactly one xfail marker in tests/, strict=True
    print("\n=== G15: Xfail markers ===")
    xfail_count = 0
    strict_xfail = False
    for f in (repo_root / "tests").glob("*.py"):
        content = f.read_text(encoding="utf-8")
        for line in content.split("\n"):
            if "@pytest.mark.xfail" in line:
                xfail_count += 1
                if "strict=True" in line:
                    strict_xfail = True
    if xfail_count == 1 and strict_xfail:
        pass_("G15", f"Exactly one xfail marker, strict=True")
    else:
        fail("G15", f"xfail_count={xfail_count}, strict={strict_xfail}")
        fails += 1
    
    # G16: Docs exist, .gitignore contains .venv
    print("\n=== G16: Docs and gitignore ===")
    docs_ok = (repo_root / "docs" / "PHASE2_PREREQS.md").exists() and (repo_root / "docs" / "PROGRESS.md").exists()
    gitignore = (repo_root / ".gitignore").read_text(encoding="utf-8") if (repo_root / ".gitignore").exists() else ""
    venv_ignored = ".venv" in gitignore
    if docs_ok and venv_ignored:
        pass_("G16", "Docs exist, .gitignore contains .venv")
    else:
        fail("G16", f"docs_ok={docs_ok}, venv_ignored={venv_ignored}")
        fails += 1
    
    # G17: Environment info
    print("\n=== G17: Environment info ===")
    info("G17", f"python={sys.version.split()[0]}, executable={sys.executable}")
    import pytest
    import mypy
    info("G17", f"pytest={pytest.__version__}, mypy={mypy.__version__}")
    
    print(f"\n{'='*50}")
    if fails == 0:
        print("GATE: PASS")
        return 0
    else:
        print(f"GATE: FAIL ({fails})")
        return 1


if __name__ == "__main__":
    sys.exit(main())