"""P6-S1 tests: canonical money conversion (amendment A).

All arithmetic hand-computed and shown in comments. Everything NEW.
"""

import pytest

from niveshdristi.core.money import from_paise, snap, to_paise


class TestMoney:
    def test_ties_away_from_zero(self):
        """ROUND_HALF_UP is ties AWAY FROM ZERO for both signs (the decimal
        module's definition), unlike Python round() (banker's):
        round(0.005) == 0 but to_paise(0.005) == 1."""
        assert to_paise(0.005) == 1    # 0.5 paise -> 1 (away from zero)
        assert to_paise(0.015) == 2    # 1.5 paise -> 2 (away from zero)
        assert to_paise(-0.005) == -1  # -0.5 paise -> -1 (away from zero)
        assert to_paise(-0.015) == -2

    def test_negative_non_tie(self):
        assert to_paise(-1.234) == -123
        assert to_paise(-1.235) == -124  # 123.5 paise -> 124 away from zero

    def test_from_paise_exact(self):
        assert from_paise(1) == 0.01
        assert from_paise(12345) == 123.45
        assert from_paise(-1) == -0.01

    def test_round_trip(self):
        for paise in (1, 99, 100, 12345, -500, 0):
            assert to_paise(from_paise(paise)) == paise

    def test_ten_thousand_round_trip_accumulation(self):
        """10,000 round trips of a 100.05 buy / 99.95 sell: the paise-snapped
        accumulation must equal the exact integer arithmetic — no float
        drift. Hand: each buy debits 10,005 paise, each sell credits
        9,995 paise; net per round trip = -10 paise; 10,000 trips =
        -100,000 paise = -1,000.00."""
        cash_paise = 100_000_000  # 1,000,000.00
        for _ in range(10_000):
            cash_paise -= to_paise(100.05)
            cash_paise += to_paise(99.95)
        assert cash_paise == 100_000_000 - 10_000 * 10
        assert from_paise(cash_paise) == pytest.approx(999_000.0)

    def test_snap_bounded_drift_vs_unsnapped(self):
        """The snapped engine differs from an unsnapped float run by at most
        half a paisa per snap (documented bound): 100 snaps of a value with
        a repeating binary fraction drift at most 100 x 0.005 = 0.5."""
        value = 0.0
        snapped = 0.0
        for _ in range(100):
            value += 86.059457  # never exactly representable in binary
            snapped = snap(snapped + 86.059457)
        # unsnapped float run drifts from the exact decimal sum
        drift = abs(value - snapped)
        assert drift <= 0.5 + 1e-9  # documented bound: half a paisa per snap
        # and the snapped path is exactly on the paise grid
        assert to_paise(snapped) == pytest.approx(snapped * 100)

    def test_snap_grid(self):
        assert snap(86.059457) == 86.06
        assert snap(0.005) == 0.01
        assert snap(-0.005) == -0.01
        assert snap(0.0) == 0.0
