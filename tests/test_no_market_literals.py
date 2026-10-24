"""
Test market literals scanner.

Protects the rule that core/ and engine/ contain no market-specific literals
(NSE, NIFTY, rupee sign, Kolkata, IST, .NS, .BO as whole words).
Also tests the scanner itself works correctly on known-good and known-bad files.
"""

from pathlib import Path

from tests.market_literals import FORBIDDEN_PATTERNS, SCAN_EXTS, scan_market_literals


def _rel_posix(path_str: str) -> str:
    """Normalize a scanner finding path to forward slashes.

    The scanner emits os-native separators (backslashes on Windows), so a
    finding path must be normalized before comparing it with a forward-slash
    prefix. Uses string replace, not Path.as_posix(), so a Windows-style path
    is normalized identically on every OS.
    """
    return path_str.replace("\\", "/")


class TestScannerSelfTest:
    """Scanner correctly identifies violations in test files."""

    def test_scanner_flags_known_bad(self, tmp_path):
        """Scanner finds NSE, .NS, rupee sign in a test file."""
        # Create test file in temp directory
        bad_file = tmp_path / "bad.py"
        bad_file.write_text("""
# This file has violations
symbol = "RELIANCE.NS"
market = "NSE"
price = "₹100"
city = "Kolkata"
timezone = "IST"
""", encoding="utf-8")
        issues = scan_market_literals(tmp_path, scan_dirs=[tmp_path])
        # Should find at least the patterns we know about
        found_patterns = {issue["pattern"] for issue in issues}
        # Check for some key patterns
        assert any(r"\.NS" in p for p in found_patterns), f"Missing .NS in {found_patterns}"
        assert any("NSE" in p for p in found_patterns), f"Missing NSE in {found_patterns}"
        assert any("Kolkata" in p for p in found_patterns), f"Missing Kolkata in {found_patterns}"
        assert any("₹" in p for p in found_patterns), f"Missing rupee sign in {found_patterns}"

    def test_scanner_ignores_clean_file(self, tmp_path):
        """Clean file with no violations passes."""
        clean_file = tmp_path / "clean.py"
        clean_file.write_text("""
# This file is clean
symbol = "RELIANCE"
market = "EXCHANGE"
price = 100
city = "MUMBAI"
""", encoding="utf-8")
        issues = scan_market_literals(tmp_path, scan_dirs=[tmp_path])
        assert len(issues) == 0, f"Clean file should have no issues, got: {issues}"

    def test_scanner_ignores_comments(self, tmp_path):
        """Comments with forbidden patterns are ignored."""
        commented_file = tmp_path / "commented.py"
        commented_file.write_text("""
# This comment mentions NSE and .NS and ₹
# But it's a comment, so should be ignored
symbol = "RELIANCE"
""", encoding="utf-8")
        issues = scan_market_literals(tmp_path, scan_dirs=[tmp_path])
        # Comments should be ignored
        assert len(issues) == 0, f"Comments should be ignored, got: {issues}"

    def test_scanner_detects_inline_code_not_comment(self, tmp_path):
        """Inline code with violation is detected even with trailing comment."""
        inline_file = tmp_path / "inline.py"
        inline_file.write_text("symbol = 'RELIANCE.NS'  # comment with NSE", encoding="utf-8")
        issues = scan_market_literals(tmp_path, scan_dirs=[tmp_path])
        assert len(issues) > 0, "Should detect violation in code part before comment"
        assert any(r"\.NS" in i["pattern"] for i in issues)


class TestCoreEngineNoLiterals:
    """Core and engine directories contain no market-specific literals."""

    def test_core_no_market_literals(self):
        """src/niveshdristi/core has no forbidden patterns."""
        issues = scan_market_literals(Path("."))
        # Filter to core/ (normalize separators: scanner emits os-native paths)
        core_issues = [
            i for i in issues if _rel_posix(i["file"]).startswith("src/niveshdristi/core/")
        ]
        assert len(core_issues) == 0, (
            f"Found {len(core_issues)} market literals in core/:\n"
            + "\n".join(f"  {i['file']}:{i['line']} - {i['pattern']}" for i in core_issues)
        )

    def test_engine_no_market_literals(self):
        """src/niveshdristi/engine has no forbidden patterns."""
        issues = scan_market_literals(Path("."))
        engine_issues = [
            i for i in issues if _rel_posix(i["file"]).startswith("src/niveshdristi/engine/")
        ]
        assert len(engine_issues) == 0, (
            f"Found {len(engine_issues)} market literals in engine/:\n"
            + "\n".join(f"  {i['file']}:{i['line']} - {i['pattern']}" for i in engine_issues)
        )

    def test_real_tree_scan_is_not_vacuous(self):
        """Non-vacuity: each scan target must contain scannable files.

        If a directory were renamed or emptied, the two tests above would
        pass without checking anything. Fail loudly instead.
        """
        for scan_dir in ("src/niveshdristi/core", "src/niveshdristi/engine"):
            scannable = [p for p in Path(scan_dir).rglob("*") if p.suffix in SCAN_EXTS]
            assert len(scannable) > 0, (
                f"{scan_dir} has no scannable files; the literal guard is vacuous"
            )


class TestFindingPathFilter:
    """The core/engine finding filter must work with Windows-style paths."""

    def test_filter_matches_windows_backslash_paths(self):
        """Regression: scanner findings carry backslash separators on Windows.

        The old forward-slash startswith filter matched nothing there, so the
        real-tree guard passed vacuously on Windows.
        """
        f_core = {
            "file": "src\\niveshdristi\\core\\instrument.py",
            "line": 17, "pattern": r"\bNSE\b", "context": "x",
        }
        f_other = {
            "file": "src\\niveshdristi\\markets\\registry.py",
            "line": 1, "pattern": r"\bNSE\b", "context": "x",
        }
        # Trailing-slash prefix must not match a sibling like corex/
        f_sibling = {
            "file": "src\\niveshdristi\\corex\\other.py",
            "line": 2, "pattern": r"\bNSE\b", "context": "x",
        }
        findings = [f_core, f_other, f_sibling]
        core = [i for i in findings if _rel_posix(i["file"]).startswith("src/niveshdristi/core/")]
        assert [i["line"] for i in core] == [17], core
        engine = [
            i for i in findings if _rel_posix(i["file"]).startswith("src/niveshdristi/engine/")
        ]
        assert engine == [], engine


class TestForbiddenPatternsCoverRequired:
    """FORBIDDEN_PATTERNS covers all required patterns."""

    def test_has_nse_pattern(self):
        """Has NSE pattern."""
        assert any("NSE" in p for p in FORBIDDEN_PATTERNS)

    def test_has_nifty_pattern(self):
        """Has NIFTY pattern."""
        assert any("NIFTY" in p or "Nifty" in p for p in FORBIDDEN_PATTERNS)

    def test_has_rupee_sign(self):
        """Has rupee sign pattern."""
        assert any("₹" in p for p in FORBIDDEN_PATTERNS)

    def test_has_kolkata(self):
        """Has Kolkata pattern."""
        assert any("Kolkata" in p for p in FORBIDDEN_PATTERNS)

    def test_has_ist(self):
        """Has IST pattern."""
        assert any(r"\bIST\b" in p for p in FORBIDDEN_PATTERNS)

    def test_has_ns_suffix(self):
        """Has .NS suffix pattern."""
        assert any(r"\.NS" in p for p in FORBIDDEN_PATTERNS)

    def test_has_bo_suffix(self):
        """Has .BO suffix pattern."""
        assert any(r"\.BO" in p for p in FORBIDDEN_PATTERNS)
