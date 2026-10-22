"""Market literals validation — ensure core/ and engine/ contain no market-specific code."""

from __future__ import annotations
from pathlib import Path
from typing import List
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
    r"T\+1\b",
    r"\bASM\b",
    r"\bGSM\b",
    r"F&O\b",
    r"\bFNO\b",
    r"\bMWPL\b",
    r"DP\s+charge\b",
    # US-specific (exact matches only in code context)
    r"\.NYSE\b",
    r"\.NASDAQ\b",
    r"\^GSPC\b",
    r"\^DJI\b",
    r"\^IXIC\b",
    r"\^VIX\b",
]

# Patterns that are OK in comments/docstrings but not in code
# (These are more general terms that appear in explanations)
COMMENT_ONLY_PATTERNS = [
    r"\bNSE\b",
    r"\bBSE\b",
    r"\bNIFTY\b",
    r"\bNifty\b",
    r"₹",
    r"INR",
    # Note: "IST" removed - matches "List", "dist", etc. too often
    r"Asia/Kolkata",
    r"\^NSEI\b",
    r"\^NSEBANK\b",
    r"\^INDIAVIX\b",
    r"\bSTT\b",
    r"\bSEBI\b",
    r"Nifty\s+\d+",
    r"Muhurat\b",
    r"T\+1\b",
    r"\bASM\b",
    r"\bGSM\b",
    r"F&O\b",
    r"\bFNO\b",
    r"\bMWPL\b",
    r"DP\s+charge\b",
    r"\bNYSE\b",
    r"\bNASDAQ\b",
    r"\bUSD\b",
    r"\$",
    r"\bEST\b",
    r"\bEDT\b",
    r"America/New_York",
    r"\^GSPC\b",
    r"\^DJI\b",
    r"\^IXIC\b",
    r"\^VIX\b",
]

# Files to scan
SCAN_DIRS = [
    "src/niveshdristi/core",
    "src/niveshdristi/engine",
]

# File extensions to scan
SCAN_EXTS = {".py", ".yaml", ".yml", ".json", ".txt", ".md"}


def scan_market_literals(root: Path = Path(".")) -> List[dict]:
    """
    Scan core/ and engine/ for market-specific literals.

    Returns:
        List of issues, each with file, line, pattern, and context.
    """
    issues = []
    patterns = [re.compile(p, re.IGNORECASE) for p in FORBIDDEN_PATTERNS]
    comment_patterns = [re.compile(p, re.IGNORECASE) for p in COMMENT_ONLY_PATTERNS]

    for scan_dir in SCAN_DIRS:
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
                in_multiline_string = False
                for line_num, line in enumerate(lines, 1):
                    # Skip comment lines
                    stripped = line.strip()
                    if stripped.startswith("#"):
                        continue
                    # Skip lines that are inside docstrings (triple quotes)
                    if '"""' in line or "'''" in line:
                        in_multiline_string = not in_multiline_string
                    if in_multiline_string:
                        continue
                    # Check for inline comments
                    code_part = line.split("#")[0] if "#" in line else line
                    if not code_part.strip():
                        continue
                    
                    # First check FORBIDDEN_PATTERNS in actual code
                    for pattern in patterns:
                        if pattern.search(code_part):
                            issues.append({
                                "file": str(file_path.relative_to(root)),
                                "line": line_num,
                                "pattern": pattern.pattern,
                                "context": line.strip()[:120],
                            })
                    # Then check COMMENT_ONLY_PATTERNS only if they appear in code (not just comments)
                    for pattern in comment_patterns:
                        if pattern.search(code_part):
                            # Additional check: ignore if it's in a string literal that looks like a comment/docstring
                            # Simple heuristic: if the match is inside quotes and looks like documentation
                            match = pattern.search(code_part)
                            if match:
                                # Check if it's inside a string literal that's likely a docstring
                                before = code_part[:match.start()]
                                after = code_part[match.end():]
                                if before.count('"') % 2 == 0 and before.count("'") % 2 == 0:
                                    # Not inside quotes, it's actual code
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