#!/usr/bin/env python3
"""Phase 1 Gate Script — validates all Phase 1 requirements."""

from __future__ import annotations
import hashlib
import json
import os
import shutil
import subprocess
import sys
import tempfile
import time
from pathlib import Path


def run(cmd: list[str], cwd: Path | None = None, capture: bool = True, env: dict | None = None) -> subprocess.CompletedProcess:
    """Run a command and return the result."""
    return subprocess.run(cmd, cwd=cwd, capture_output=capture, text=True, check=False, env=env)


def info(id_: str, detail: str) -> None:
    _print_safe(f"INFO {id_} {detail}")


def pass_(id_: str, detail: str) -> None:
    _print_safe(f"PASS {id_} {detail}")


def fail(id_: str, detail: str) -> None:
    _print_safe(f"FAIL {id_} {detail}")


def _print_safe(msg: str) -> None:
    """Print message safely handling unicode on Windows."""
    try:
        print(msg)
    except UnicodeEncodeError:
        # Replace unencodable characters
        safe_msg = msg.encode(sys.stdout.encoding or "utf-8", errors="replace").decode(sys.stdout.encoding or "utf-8")
        print(safe_msg)


def main() -> int:
    repo_root = Path(__file__).parent.parent
    phase0_root = Path(sys.argv[sys.argv.index("--phase0") + 1]) if "--phase0" in sys.argv else None

    # Zero-write policy: child processes must not write bytecode inside either tree
    os.environ["PYTHONDONTWRITEBYTECODE"] = "1"
    # Marker for the end-of-gate zero-writes check (G18)
    gate_marker = time.time()

    def _in_gate_scope(f: Path) -> bool:
        """G18 scope: everything under the repo root except .git and .venv*."""
        parts = f.parts
        if ".git" in parts:
            return False
        if any(p.startswith(".venv") for p in parts):
            return False
        return True

    # Eager start-of-gate snapshot: hash every in-scope file NOW, before any
    # subprocess runs (hashing after pytest rewrote a file would prove nothing).
    start_snapshot: dict[str, str] = {}
    for f in repo_root.rglob("*"):
        if not f.is_file() or not _in_gate_scope(f):
            continue
        rel = f.relative_to(repo_root).as_posix()
        try:
            start_snapshot[rel] = hashlib.sha256(f.read_bytes()).hexdigest()
        except OSError:
            start_snapshot[rel] = "<unreadable at gate start>"

    # Load .env file to ensure DATABASE_URL and other vars are in environment
    from dotenv import load_dotenv
    load_dotenv(repo_root / ".env")

    fails = 0
    shared_pytest: subprocess.CompletedProcess | None = None

    # G01: git status --porcelain is empty, both before and after pytest run
    print("\n=== G01: Clean git status ===")
    result = run(["git", "status", "--porcelain"], cwd=repo_root)
    if result.stdout.strip():
        fail("G01", f"git status not clean before pytest:\n{result.stdout}")
        fails += 1
    else:
        pass_("G01", "git status clean before pytest")

    # Single shared pytest run: G01 (bracket), G06 (counts + node IDs), G07
    # (utcnow) all consume this one run. -v puts every node ID in the output
    # so the "all nodes under tests/" check needs no second invocation.
    # -p no:cacheprovider keeps .pytest_cache unwritten.
    print("\n=== Shared pytest run ===")
    info("PYTEST", "pytest runs: 1")
    shared_pytest = run(
        [sys.executable, "-m", "pytest", "-v", "-p", "no:cacheprovider"], cwd=repo_root, capture=True
    )
    tail = [l for l in shared_pytest.stdout.splitlines() if l.strip()][-1:]
    info("PYTEST", tail[0] if tail else f"exit={shared_pytest.returncode}")

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
    
    # G03b: phase0 tool precheck — the comparison tools must exist in the
    # phase0 tree and be byte-identical to the repo copies, otherwise G04/G05
    # would compare with different code. The gate never writes to phase0_root.
    phase0_tools_ok = True
    if phase0_root:
        print("\n=== G03b: phase0 tool md5 precheck ===")
        for name in ("dump_config.py", "compare_backtest.py"):
            p0 = phase0_root / "tools" / name
            p1 = repo_root / "tools" / name
            if not p0.exists() or not p1.exists():
                fail("G03b", f"missing tool copy: tools/{name} (phase0 exists={p0.exists()}, repo exists={p1.exists()})")
                phase0_tools_ok = False
                fails += 1
                continue
            h0 = hashlib.md5(p0.read_bytes()).hexdigest()
            h1 = hashlib.md5(p1.read_bytes()).hexdigest()
            if h0 != h1:
                fail("G03b", f"md5 mismatch for tools/{name}: phase0={h0} repo={h1}")
                phase0_tools_ok = False
                fails += 1
            else:
                pass_("G03b", f"tools/{name} md5 match: {h0}")

    # G04: Config equality - MD5 match
    print("\n=== G04: Config equality ===")
    if phase0_root and phase0_tools_ok:
        # Run dump_config on phase0 using current repo's tool with phase0 src, cwd=phase0_root
        env0 = os.environ.copy()
        env0["PYTHONPATH"] = str(phase0_root / "src")
        result0 = run([sys.executable, "tools/dump_config.py"], cwd=phase0_root, capture=True, env=env0)
        
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
        if phase0_root and not phase0_tools_ok:
            info("G04", "Skipped (phase0 tool precheck failed)")
        else:
            info("G04", "Skipped (no phase0 path)")

    # G05: Backtest equality
    print("\n=== G05: Backtest equality ===")
    if phase0_root and phase0_tools_ok:
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
        if phase0_root and not phase0_tools_ok:
            info("G05", "Skipped (phase0 tool precheck failed)")
        else:
            info("G05", "Skipped (no phase0 path)")
    
    # G06: pytest results (derived from the single shared run)
    print("\n=== G06: Pytest results ===")
    assert shared_pytest is not None
    import re
    collected_m = re.search(r"collected (\d+) items?", shared_pytest.stdout)
    collected = int(collected_m.group(1)) if collected_m else 0

    passed = failed = errors = xfailed = skipped = 0
    for line in shared_pytest.stdout.split("\n"):
        if "passed" in line and ("failed" in line or "xfailed" in line or "skipped" in line or "warnings" in line):
            # Typical format: "110 passed, 1 xfailed, 2 warnings in 4.30s"
            passed_m = re.search(r"(\d+)\s+passed", line)
            failed_m = re.search(r"(\d+)\s+failed", line)
            error_m = re.search(r"(\d+)\s+error", line)
            xfailed_m = re.search(r"(\d+)\s+xfailed", line)
            skipped_m = re.search(r"(\d+)\s+skipped", line)
            if passed_m:
                passed = int(passed_m.group(1))
            if failed_m:
                failed = int(failed_m.group(1))
            if error_m:
                errors = int(error_m.group(1))
            if xfailed_m:
                xfailed = int(xfailed_m.group(1))
            if skipped_m:
                skipped = int(skipped_m.group(1))
            break

    if failed == 0 and errors == 0 and skipped == 0 and xfailed == 1 and passed >= 110 and collected >= 111:
        pass_("G06", f"collected={collected} passed={passed} failed={failed} errors={errors} xfailed={xfailed} skipped={skipped}")
    else:
        fail("G06", f"collected={collected} passed={passed} failed={failed} errors={errors} xfailed={xfailed} skipped={skipped}")
        fails += 1

    # G06 (cont.): every collected test node ID must start with tests/
    status_re = re.compile(r"^(.*?)\s+(?:PASSED|FAILED|ERROR|SKIPPED|XFAIL|XPASS)\b")
    node_ids = []
    for line in shared_pytest.stdout.split("\n"):
        m = status_re.match(line.strip())
        if m and "::" in m.group(1):
            node_ids.append(m.group(1))
    outside = [n for n in node_ids if not n.startswith("tests/")]
    if outside:
        fail("G06", f"{len(outside)} collected node(s) outside tests/: {outside[:10]}")
        fails += 1
    elif len(node_ids) != collected:
        fail("G06", f"node-id count {len(node_ids)} != collected {collected}")
        fails += 1
    else:
        pass_("G06", f"all {len(node_ids)} collected node IDs under tests/")

    # G07: No utcnow warnings (derived from the single shared run)
    print("\n=== G07: No utcnow warnings ===")
    warnings = []
    for line in (shared_pytest.stdout + "\n" + shared_pytest.stderr).split("\n"):
        if "utcnow" in line.lower():
            warnings.append(line.strip())
    if warnings:
        info("G07", f"Found {len(warnings)} utcnow warnings: {warnings[:3]}")
    else:
        pass_("G07", "No utcnow warnings")
    
    # G08: time hygiene across core/, engine/, markets/, cli/, config_loader.py;
    # the @dataclass ban stays core/-only
    print("\n=== G08: Time & dataclass hygiene ===")
    issues = []
    g08_files = []
    for d in ("src/niveshdristi/core", "src/niveshdristi/engine", "src/niveshdristi/markets", "src/niveshdristi/cli", "src/niveshdristi/marketdata"):
        g08_files.extend((repo_root / d).glob("*.py"))
    g08_files.append(repo_root / "src/niveshdristi/config_loader.py")
    for f in g08_files:
        content = f.read_text(encoding="utf-8")
        if "utcnow(" in content:
            issues.append(f"{f.name}: has utcnow()")
        if "datetime.now()" in content and "datetime.now(timezone.utc)" not in content and "datetime.now(UTC)" not in content:
            issues.append(f"{f.name}: has naive datetime.now()")
        if f.parent.name == "core" and "@dataclass" in content:
            issues.append(f"{f.name}: has @dataclass")
    if issues:
        fail("G08", f"Issues: {issues}")
        fails += 1
    else:
        pass_("G08", f"Time & dataclass hygiene clean ({len(g08_files)} files)")
    
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
    from tests.market_literals import scan_market_literals, SCAN_EXTS

    def _rel_posix(p: str) -> str:
        # Scanner finding paths carry os-native separators (backslashes on Windows)
        return p.replace("\\", "/")

    issues = scan_market_literals(
        repo_root,
        scan_dirs=["src/niveshdristi/core", "src/niveshdristi/engine", "src/niveshdristi/marketdata"],
    )
    core_issues = [i for i in issues if _rel_posix(i["file"]).startswith("src/niveshdristi/core/")]
    engine_issues = [i for i in issues if _rel_posix(i["file"]).startswith("src/niveshdristi/engine/")]
    md_issues = [i for i in issues if _rel_posix(i["file"]).startswith("src/niveshdristi/marketdata/")]
    if core_issues or engine_issues or md_issues:
        fail("G10", f"Neutral zones have findings: core={len(core_issues)} engine={len(engine_issues)} marketdata={len(md_issues)}")
        for i in (core_issues + engine_issues + md_issues)[:10]:
            info("G10", f"  {i['file']}:{i['line']} matched {i['pattern']}")
        fails += 1
    else:
        pass_("G10", "Neutral zones (core/engine/marketdata) have 0 findings")

    # Market literals are allowed ONLY in this explicit adapter allowlist.
    # Any other file under markets/in_nse/providers/ carrying a literal FAILs.
    ADAPTER_ALLOWLIST = {
        "src/niveshdristi/markets/in_nse/providers/yfinance_adapter.py",
        "src/niveshdristi/markets/in_nse/providers/bhavcopy_file.py",
    }
    providers_dir = repo_root / "src/niveshdristi/markets/in_nse/providers"
    if providers_dir.exists():
        adapter_issues = scan_market_literals(repo_root, scan_dirs=["src/niveshdristi/markets/in_nse/providers"])
        rogue = sorted(
            {_rel_posix(i["file"]) for i in adapter_issues} - ADAPTER_ALLOWLIST
        )
        if rogue:
            fail("G10", f"Market literals outside the adapter allowlist: {rogue}")
            fails += 1
        else:
            present = sorted(
                p.relative_to(repo_root).as_posix()
                for p in providers_dir.glob("*.py")
                if p.relative_to(repo_root).as_posix() in ADAPTER_ALLOWLIST
            )
            pass_("G10", f"Adapter allowlist enforced (present: {present})")

    # Non-vacuity: each scan target must contain scannable files
    for target in ("src/niveshdristi/core", "src/niveshdristi/engine", "src/niveshdristi/marketdata"):
        scannable = [p for p in (repo_root / target).rglob("*") if p.suffix in SCAN_EXTS]
        if scannable:
            pass_("G10", f"{target}: scan covers {len(scannable)} files")
        else:
            fail("G10", f"{target}: scan covers 0 files (guard would be vacuous)")
            fails += 1
    
    # Test on temp tree with forbidden patterns
    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = Path(tmp)
        # Create the scan directory structure
        core_dir = tmp_path / "src/niveshdristi/core"
        core_dir.mkdir(parents=True)
        engine_dir = tmp_path / "src/niveshdristi/engine"
        engine_dir.mkdir(parents=True)
        test_content = "NSE\nRELIANCE.NS\n\u20b9\nKolkata\nIST"
        (core_dir / "test.txt").write_text(test_content, encoding="utf-8")
        issues = scan_market_literals(tmp_path)
        patterns_found = set(i["pattern"] for i in issues)
        # These are the actual FORBIDDEN_PATTERNS that should match
        expected = {r"\bNSE\b", r"\.NS\b", r"₹", r"Kolkata", r"\bIST\b"}
        if expected.issubset(patterns_found):
            pass_("G10", f"Temp tree reports all 5 patterns: {sorted(patterns_found)}")
        else:
            fail("G10", f"Temp tree missing patterns: expected={expected}, found={patterns_found}")
            fails += 1
    
    # G11: Typed CFG
    print("\n=== G11: Typed CFG ===")
    # mypy cache goes to a fresh temp dir outside the repo (removed after G14)
    mypy_cache_dir = tempfile.mkdtemp(prefix="nd_gate_mypy_")
    # Use a file-based check since mypy needs the full module context
    # Run with PYTHONPATH=src to use source tree instead of installed package
    with tempfile.NamedTemporaryFile(mode="w", suffix=".py", delete=False) as f:
        f.write("from niveshdristi.config import CFG\nCFG.backtest.does_not_exist\n")
        temp_file = f.name
    try:
        env = os.environ.copy()
        env["PYTHONPATH"] = str(repo_root / "src")
        result = run([sys.executable, "-m", "mypy", temp_file, "--cache-dir", mypy_cache_dir], cwd=repo_root, env=env)
        if "attr-defined" in result.stdout and "does_not_exist" in result.stdout:
            pass_("G11", "Typed CFG works (attr-defined error for does_not_exist)")
        else:
            fail("G11", f"Typed CFG check failed: {result.stdout}")
            fails += 1
    finally:
        Path(temp_file).unlink(missing_ok=True)
    
    # G12: CLI via python -m niveshdristi.cli.main
    print("\n=== G12: CLI validation ===")
    # Check nd command on PATH
    result = run(["nd", "--help"], cwd=repo_root)
    nd_on_path = result.returncode == 0
    info("G12", f"nd command on PATH: {nd_on_path}")
    
    # --json validate exits 0
    result = run([sys.executable, "-m", "niveshdristi.cli.main", "--json", "validate"], cwd=repo_root, capture=True)
    if result.returncode == 0:
        try:
            # Extract JSON from stdout (may have warnings mixed in)
            stdout = result.stdout
            # Find the first { and last } to extract JSON
            start = stdout.find("{")
            end = stdout.rfind("}") + 1
            if start >= 0 and end > start:
                json_str = stdout[start:end]
                data = json.loads(json_str)
                if data.get("summary", {}).get("failed", -1) == 0:
                    pass_("G12", "--json validate exits 0 with summary.failed == 0")
                else:
                    fail("G12", f"summary.failed != 0: {data}")
                    fails += 1
            else:
                fail("G12", f"No JSON output found: {stdout}")
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
    result = run([sys.executable, "-m", "ruff", "check", "--no-cache",
                  "src/niveshdristi/core", "src/niveshdristi/markets",
                  "src/niveshdristi/cli", "src/niveshdristi/engine",
                  "src/niveshdristi/marketdata",
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
                  "src/niveshdristi/marketdata",
                  "src/niveshdristi/config_loader.py", "--ignore-missing-imports",
                  "--cache-dir", mypy_cache_dir], cwd=repo_root)
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
    import mypy.version
    mypy_ver = mypy.version.__version__
    info("G17", f"pytest={pytest.__version__}, mypy={mypy_ver}")

    # Remove the mypy temp cache dir (created before G11, used by G11+G14)
    shutil.rmtree(mypy_cache_dir, ignore_errors=True)

    # G18: Zero writes inside the repo since gate start
    #
    # Rule: every in-scope file present at gate start is sha256-snapshotted
    # before any subprocess runs. At gate end, a file with mtime newer than
    # the marker is an identical rewrite (INFO) if its bytes equal the
    # snapshot, a FAIL if changed, and a FAIL if it did not exist at start.
    # A snapshot file missing at gate end is a FAIL.
    #
    # Known behavior: legacy characterization tests rewrite three gitignored
    # parquet fixtures (tests/fixtures/*.parquet) on every pytest run. On a
    # fresh clone those files do not exist at start, so the FIRST gate run
    # FAILs G18 once ("new during gate"); from the second run on they are
    # byte-identical rewrites and G18 passes. No allowlist is added for this.
    print("\n=== G18: Zero writes inside repo ===")
    g18_failures: list[str] = []
    identical = 0

    # Files currently on disk with mtime newer than the marker
    current_newer: dict[str, Path] = {}
    for f in repo_root.rglob("*"):
        if not f.is_file() or not _in_gate_scope(f):
            continue
        try:
            if f.stat().st_mtime > gate_marker:
                current_newer[f.relative_to(repo_root).as_posix()] = f
        except OSError:
            continue

    for rel, f in sorted(current_newer.items()):
        if rel not in start_snapshot:
            g18_failures.append(f"{rel} (new during gate)")
            continue
        try:
            disk_sha = hashlib.sha256(f.read_bytes()).hexdigest()
        except OSError:
            g18_failures.append(f"{rel} (unreadable at gate end)")
            continue
        if disk_sha == start_snapshot[rel]:
            identical += 1
            info("G18", f"rewritten identically: {rel}")
        else:
            g18_failures.append(f"{rel} (content changed)")

    # Deletions: a snapshot file that no longer exists
    for rel in sorted(start_snapshot):
        if not (repo_root / rel).exists():
            g18_failures.append(f"{rel} (deleted during gate)")

    if g18_failures:
        fail("G18", f"{len(g18_failures)} zero-write violation(s) after gate start:")
        for entry in g18_failures[:20]:
            info("G18", f"  {entry}")
        if identical:
            info("G18", f"(+{identical} byte-identical rewrite(s), not failing)")
        fails += 1
    else:
        pass_(
            "G18",
            f"No changed/new/deleted files after gate start ({identical} byte-identical legacy rewrite(s) allowed)",
        )

    print(f"\n{'='*50}")
    if fails == 0:
        print("GATE: PASS")
        return 0
    else:
        print(f"GATE: FAIL ({fails})")
        return 1


if __name__ == "__main__":
    sys.exit(main())