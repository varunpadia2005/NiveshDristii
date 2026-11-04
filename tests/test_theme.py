"""P8-S4: WCAG contrast over EVERY text/background pair in both themes
(pure Python). Body text >= 4.5; large text and UI borders >= 3.0.
Ratios are computed and REPORTED; a failing token is FIXED, thresholds are
never weakened."""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from niveshdristi.ui.theme import DARK, LIGHT  # noqa: E402


def _channel(c: float) -> float:
    c = c / 255
    return c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4


def _luminance(hex_color: str) -> float:
    h = hex_color.lstrip("#")
    r, g, b = (int(h[i:i + 2], 16) for i in (0, 2, 4))
    return (0.2126 * _channel(r) + 0.7152 * _channel(g)
            + 0.0722 * _channel(b))


def contrast(fg: str, bg: str) -> float:
    l1, l2 = _luminance(fg), _luminance(bg)
    hi, lo = max(l1, l2), min(l1, l2)
    return (hi + 0.05) / (lo + 0.05)


# (text token, background token, threshold, kind)
PAIRS = [
    ("text", "app_background", 4.5, "body"),
    ("text", "card", 4.5, "body"),
    ("muted_text", "card", 4.5, "body"),
    ("muted_text", "app_background", 4.5, "body"),
    ("muted_text", "neutral_bg", 4.5, "body"),
    ("tertiary_text", "app_background", 3.0, "large/tertiary"),
    ("primary", "card", 3.0, "UI element"),
    ("on_primary", "primary", 4.5, "button text"),
    ("positive_text", "positive_bg", 4.5, "body"),
    ("negative_text", "negative_bg", 4.5, "body"),
    ("neutral_text", "neutral_bg", 4.5, "body"),
    ("stub_text", "stub_bg", 4.5, "body"),
    ("caution_text", "caution_bg", 4.5, "banner body"),
    ("border", "card", 3.0, "UI border"),
    ("border", "app_background", 3.0, "UI border"),
]


class TestContrast:
    def test_all_pairs_both_themes(self):
        failures = []
        for name, tokens in (("light", LIGHT), ("dark", DARK)):
            print(f"--- {name} contrast ratios ---")
            for text_key, bg_key, threshold, kind in PAIRS:
                ratio = contrast(tokens[text_key], tokens[bg_key])
                print(f"  {text_key:>14} on {bg_key:<16} {ratio:5.2f}  "
                      f"(need {threshold}, {kind})")
                if ratio < threshold:
                    failures.append((name, text_key, bg_key, round(ratio, 2)))
        assert failures == [], failures
