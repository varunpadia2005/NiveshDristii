"""Conviction Score: blends technical, fundamental, regime, and ML signals into 0-100 score."""
from dataclasses import dataclass
from typing import Optional
from niveshdristi.data.contracts import SignalReport, GuardrailReport, RegimeReport, ModelOutput


@dataclass
class ConvictionComponents:
    technical: float      # 0-100 from signal composite
    fundamental: float    # 0-100 from guardrails (capped)
    regime: float         # 0-100 from market/sector regime
    ml: float             # 0-100 from model probability


@dataclass
class ConvictionScore:
    score: int            # 0-100 final
    components: ConvictionComponents
    capped_by_guardrails: bool
    details: dict


def compute_conviction(
    signal: SignalReport,
    guardrails: GuardrailReport,
    regime: RegimeReport,
    model: Optional[ModelOutput] = None,
    weights: dict = None
) -> ConvictionScore:
    """Blend all components into final conviction score."""
    # Default weights (configurable)
    w = weights or {
        "technical": 0.30,
        "fundamental": 0.25,
        "regime": 0.20,
        "ml": 0.25,
    }

    # Technical: map -1..+1 composite to 0..100
    technical = int(50 + 50 * signal.composite)

    # Fundamental: guardrail cap (100, 60, or 30)
    fundamental = guardrails.max_score_cap

    # Regime: bull=80, choppy=50, bear=20
    regime_map = {"bull": 80, "choppy": 50, "bear": 20, "unknown": 50}
    regime_score = regime_map.get(regime.market_state.lower(), 50)

    # ML: model probability of up move
    if model:
        ml_score = int(50 + 100 * (model.prob_up - 0.5) * 2)  # scale prob_up 0..1 to 0..100
    else:
        ml_score = 50  # neutral if no model

    # Weighted blend
    raw_score = (
        w["technical"] * technical +
        w["fundamental"] * fundamental +
        w["regime"] * regime_score +
        w["ml"] * ml_score
    )

    # Apply guardrail cap
    final_score = min(int(round(raw_score)), guardrails.max_score_cap)
    capped = final_score < int(round(raw_score))

    return ConvictionScore(
        score=final_score,
        components=ConvictionComponents(
            technical=technical,
            fundamental=fundamental,
            regime=regime_score,
            ml=ml_score,
        ),
        capped_by_guardrails=capped,
        details={
            "weights": w,
            "raw_score": round(raw_score, 1),
            "guardrail_cap": guardrails.max_score_cap,
        }
    )