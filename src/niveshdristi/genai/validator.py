"""Validator: extracts numbers from AI output, verifies against facts bundle."""
import re
from typing import Tuple, List
from niveshdristi.data.contracts import AnalystNote, FactsBundle


def validate_note(note: AnalystNote, bundle: FactsBundle) -> Tuple[bool, List[str]]:
    """Extract all numbers from note, check each exists in facts bundle."""
    full_text = " ".join([
        note.summary,
        " ".join(note.bull_case),
        " ".join(note.bear_case),
        " ".join(note.risks),
        " ".join(note.would_change_view)
    ])

    # Extract numbers (integers and decimals)
    number_strings = re.findall(r'\b\d+\.?\d*\b', full_text)
    numbers = [float(n) for n in number_strings]

    # Build allowed numbers from bundle (with rounding tolerance)
    allowed = set()

    def add_allowed(val, precisions=(1, 2, 3)):
        if val is None:
            return
        try:
            for p in precisions:
                allowed.add(round(float(val), p))
        except (ValueError, TypeError):
            pass

    # Signal composite
    add_allowed(bundle.signal.composite)

    # Regime VIX
    add_allowed(bundle.regime.vix_level)

    # Model probabilities
    if bundle.model:
        add_allowed(bundle.model.prob_up)
        add_allowed(bundle.model.prob_down)

    # Fundamentals
    f = bundle.fundamentals
    add_allowed(f.pe_ratio)
    add_allowed(f.pb_ratio)
    add_allowed(f.roe * 100 if f.roe else None)  # Convert to percentage
    add_allowed(f.debt_to_equity)
    add_allowed(f.profit_margin * 100 if f.profit_margin else None)
    add_allowed(f.revenue_growth * 100 if f.revenue_growth else None)

    # Check each number
    errors = []
    tolerance = 0.015  # 1.5% absolute tolerance for rounding
    for num in numbers:
        if not any(abs(num - a) < tolerance for a in allowed):
            errors.append(f"Unverified number: {num}")

    return len(errors) == 0, errors