"""P19-LOOK S1: guard rules for the ONE authorized CSS module.

style.py must stay a static-constant CSS injector: no interpolation, no
<script>, no external URLs, no data in markup. Every rule here is a
negative test — it FAILS if a violation is introduced. RED was shown
per rule via mutations in the P19-LOOK report.
"""

from __future__ import annotations

import ast
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
STYLE = REPO / "src" / "niveshdristi" / "ui" / "style.py"


def _source() -> str:
    assert STYLE.exists(), "ui/style.py must exist"
    return STYLE.read_text(encoding="utf-8")


class TestStyleModuleGuard:
    def test_css_is_static_literal(self):
        """The CSS must be a plain string constant (no f-string, no
        .format(), no % interpolation, no + concatenation inside it)."""
        tree = ast.parse(_source())
        for node in ast.walk(tree):
            if isinstance(node, ast.JoinedStr):  # f-string
                raise TypeError(
                    f"style.py must not contain f-strings: line {node.lineno}")
            if isinstance(node, ast.BinOp) and isinstance(node.op, ast.Mod):
                raise TypeError(
                    "style.py must not use % interpolation: line "
                    f"{node.lineno}")
        text = _source()
        assert ".format(" not in text, "style.py must not use .format()"
        assert 'f"' not in text, "no f-string prefixes"
        assert "f'" not in text, "no f-string prefixes"

    def test_no_script_no_external_urls(self):
        text = _source()
        assert "<script" not in text.lower(), "no <script> allowed"
        assert "http://" not in text, "no external URLs"
        assert "https://" not in text, "no external URLs"
        assert "@import" not in text, "no CSS @import allowed"

    def test_inject_uses_st_html_only(self):
        text = _source()
        assert "st.html(" in text, "injection must use st.html"
        assert "unsafe_allow_html" not in text, (
            "st.html only — never unsafe_allow_html"
        )
        assert "st.markdown" not in text

    def test_non_interpolation_of_data(self):
        """No calls that could carry data into the markup: the module may
        only call st.html with the constant."""
        tree = ast.parse(_source())
        calls = [n for n in ast.walk(tree) if isinstance(n, ast.Call)]
        st_calls = [c for c in calls
                    if isinstance(c.func, ast.Attribute)
                    and c.func.attr == "html"]
        assert st_calls, "non-vacuity: st.html must be called once"
        for c in st_calls:
            assert len(c.args) == 1, "st.html takes exactly the constant"
            arg = c.args[0]
            assert isinstance(arg, ast.Name), (
                "st.html must receive the static constant Name, never an "
                "expression"
            )
