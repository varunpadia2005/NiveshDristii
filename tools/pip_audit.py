"""OPT-IN dependency vulnerability scan (NEW, P10-S4 / D6).

Wraps `pip-audit` (a THIRD-PARTY tool installed separately — this project
adds NO dependency). Refuses to run unless --yes-network is passed, because
pip-audit queries PyPI's vulnerability service. Prints the exact command
FIRST, then runs it via stdlib subprocess. NEVER run by tests, the gate,
CI, or an agent session.

Usage (manual):
    python tools/pip_audit.py            # prints the command, refuses
    python tools/pip_audit.py --yes-network
    python tools/pip_audit.py --yes-network --skip-editable
"""

from __future__ import annotations

import argparse
import shutil
import subprocess
import sys

AUDIT_COMMAND = [sys.executable, "-m", "pip_audit"]


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--yes-network", action="store_true",
                        help="REQUIRED: pip-audit queries PyPI's "
                             "vulnerability service")
    parser.add_argument("--skip-editable", action="store_true",
                        help="pass-through: skip the editable local install")
    args = parser.parse_args(argv)

    cmd = list(AUDIT_COMMAND)
    if args.skip_editable:
        cmd.append("--skip-editable")
    print("EXACT COMMAND:", " ".join(cmd))
    print("WARNING: this queries the PyPI vulnerability service (network).")
    if not args.yes_network:
        print("Refusing: pass --yes-network to actually run it.",
              file=sys.stderr)
        return 2
    if shutil.which("pip-audit") is None and _module_missing():
        print("pip-audit is NOT installed. Install it manually first:\n"
              "    pip install pip-audit\n"
              "(the project adds NO dependency for this)",
              file=sys.stderr)
        return 2
    completed = subprocess.run(cmd, check=False)  # noqa: S603 - fixed cmd
    return completed.returncode


def _module_missing() -> bool:
    try:
        import pip_audit  # noqa: F401
    except ImportError:
        return True
    return False


if __name__ == "__main__":
    raise SystemExit(main())
