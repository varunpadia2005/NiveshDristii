"""Market literals validation — ensure core/ and engine/ contain no market-specific code."""

from __future__ import annotations
from pathlib import Path
from typing import List, Optional
import re


# Patterns that indicate market-specific code in core/engine
# These should only match in EXECUTABLE code, not in comments/docstrings
FORBIDDEN_PATTERNS = [
    # India-specific (exact matches only in code context)
    r"\.NS\b",
    r"\.BO\b",
    r"\^NSEI\b",
    r"\^NSEBANK\b",
    r"\^INDIAVIX\b",
    r"\bSTT\b",
    r"\bSEBI\b",
    r"Nifty\s+\d+",
    r"Muhurat\b",
    # r"T\+1\b",  # Settlement notation - allowed in docs/specs
    r"\bASM\b",
    r"\bGSM\b",
    r"F&O\b",
    r"\bFNO\b",
    r"\bMWPL\b",
    r"DP\s+charge\b",
    # India-specific terms that should not appear in core/engine
    r"₹",
    r"Kolkata",
    r"\bIST\b",
    r"\bNSE\b",
    r"\bNIFTY\b",
    r"\bNifty\b",
    # US-specific (exact matches only in code context)
    r"\.NYSE\b",
    r"\.NASDAQ\b",
    r"\^GSPC\b",
    r"\^DJI\b",
    r"\^IXIC\b",
    r"\^VIX\b",
]


# File extensions to scan
SCAN_EXTS = {".py", ".yaml", ".yml", ".json", ".txt", ".md"}

# Directories to scan (relative to root)
SCAN_DIRS = [
    "src/niveshdristi/core",
    "src/niveshdristi/engine",
]


def scan_market_literals(root: Path = Path("."), scan_dirs: Optional[List[str]] = None) -> List[dict]:
    """
    Scan core/ and engine/ for market-specific literals.

    Args:
        root: Root directory to scan from
        scan_dirs: Optional list of directories to scan (relative to root).
                   If None, uses default SCAN_DIRS.

    Returns:
        List of issues, each with file, line, pattern, and context.
    """
    issues = []
    patterns = [re.compile(p, re.IGNORECASE) for p in FORBIDDEN_PATTERNS]
    scan_dirs = scan_dirs or SCAN_DIRS

    for scan_dir in scan_dirs:
        dir_path = root / scan_dir
        if not dir_path.exists():
            continue

        for file_path in dir_path.rglob("*"):
            if file_path.suffix not in SCAN_EXTS:
                continue
            if file_path.name.startswith("."):
                continue

            try:
                content = file_path.read_text(encoding="utf-8", errors="ignore")
                lines = content.splitlines()
                for line_num, line in enumerate(lines, 1):
                    # Skip comment lines
                    stripped = line.strip()
                    if stripped.startswith("#"):
                        continue
                    # Check for inline comments - split on # and only check code part
                    code_part = line.split("#")[0] if "#" in line else line
                    if not code_part.strip():
                        continue

                    # Check FORBIDDEN_PATTERNS in actual code (including string literals)
                    for pattern in [re.compile(p, re.IGNORECASE) for p in FORBIDDEN_PATTERNS]:
                        if pattern.search(code_part):
                            issues.append({
                                "file": str(file_path.relative_to(root)),
                                "line": line_num,
                                "pattern": pattern.pattern,
                                "context": line.strip()[:120],
                            })
            except Exception:
                pass

    return issues


def main() -> int:
    """CLI entry point for validation."""
    issues = scan_market_literals()
    if issues:
        print(f"❌ Found {len(issues)} market-specific literals in core/engine:")
        for issue in issues:
            print(f"  {issue['file']}:{issue['line']} - matched '{issue['pattern']}'")
            print(f"    {issue['context']}")
        return 1
    else:
        print("✅ No market-specific literals found in core/ and engine/")
        return 0


if __name__ == "__main__":
    exit(main())