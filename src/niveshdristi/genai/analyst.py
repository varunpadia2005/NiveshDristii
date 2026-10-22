"""Grounded AI Analyst: builds facts bundle, calls LLM, validates output."""
import json
import re
from typing import Optional
from niveshdristi.config import CFG
from niveshdristi.data.contracts import FactsBundle, AnalystNote
from niveshdristi.genai.client import OpenRouterClient, render_template


client = OpenRouterClient()

SYSTEM_PROMPT = """You are a research analyst for Indian equities.
Write a structured note using ONLY the provided facts.
Rules:
- NEVER invent numbers not in the facts bundle
- NEVER use buy/sell/hold/recommend language
- ALWAYS include uncertainty and risks
- Output valid JSON with keys: summary, bull_case, bear_case, risks, would_change_view"""

USER_PROMPT_TEMPLATE = """Ticker: {ticker}
Date: {date}

TECHNICAL SIGNALS:
Composite: {signal.composite:.3f}
Components: {signal.components}
Reasons: {signal.reasons}

FUNDAMENTALS:
P/E: {fundamentals.pe_ratio}
P/B: {fundamentals.pb_ratio}
ROE: {fundamentals.roe}
Debt/Equity: {fundamentals.debt_to_equity}
Profit Margin: {fundamentals.profit_margin}
Revenue Growth: {fundamentals.revenue_growth}
Sector: {fundamentals.sector}

GUARDRAILS:
Flags: {guardrails.flags}
Max Score Cap: {guardrails.max_score_cap}

REGIME:
Market State: {regime.market_state}
VIX: {regime.vix_level:.1f}
Sector Quadrants: {regime.sector_quadrants}

MODEL:
P(Up): {model.prob_up:.3f}
P(Down): {model.prob_down:.3f}
Top SHAP: {model.shap_values}

PRICE RANGE:
{price_range}

OUTPUT JSON ONLY."""


def _build_template_context(bundle: FactsBundle) -> dict:
    """Build context for template fallback."""
    signal = bundle.signal
    return {
        "ticker": bundle.ticker,
        "signal": signal,
        "fundamentals": bundle.fundamentals,
        "guardrails": bundle.guardrails,
        "regime": bundle.regime,
        "model": bundle.model or {"prob_up": 0.5, "prob_down": 0.5, "shap_values": {}},
        "price_range": bundle.price_range,
        "bull_case": [
            f"Technical composite positive ({signal.composite:.2f})" if signal.composite > 0 else "Technical setup neutral",
            f"Market regime supportive ({bundle.regime.market_state})" if bundle.regime.market_state == "bull" else "Regime not unfavorable",
        ],
        "bear_case": [
            f"Technical composite negative ({signal.composite:.2f})" if signal.composite < 0 else "Technical setup neutral",
            f"VIX elevated at {bundle.regime.vix_level:.1f}" if bundle.regime.vix_level > 20 else "VIX moderate",
        ],
        "risks": [
            "Key levels based on historical volatility, not predictions",
            "Fundamentals may be stale (quarterly reporting lag)",
            "Model probabilities uncalibrated on recent regime",
            "Past performance does not guarantee future results",
        ],
        "would_change_view": [
            "Break above/below key technical levels with volume",
            "Earnings surprise vs consensus estimates",
            "Regime shift confirmed by HMM state transition",
            "Significant change in fundamental guardrails",
        ],
    }


def _parse_template_output(text: str) -> AnalystNote:
    """Parse template output into AnalystNote structure."""
    sections = {"summary": "", "bull_case": [], "bear_case": [], "risks": [], "would_change_view": []}
    current = None
    for line in text.split("\n"):
        line = line.strip()
        if line.startswith("Summary:"):
            current = "summary"
            sections[current] = line.replace("Summary:", "").strip()
        elif line.startswith("Bull Case:"):
            current = "bull_case"
        elif line.startswith("Bear Case:"):
            current = "bear_case"
        elif line.startswith("Risks:"):
            current = "risks"
        elif line.startswith("Would Change View:"):
            current = "would_change_view"
        elif line.startswith("- ") and current and current != "summary":
            sections[current].append(line[2:])
    return AnalystNote(**sections)


async def generate_analyst_note(bundle: FactsBundle) -> AnalystNote:
    """Generate analyst note via LLM or deterministic template fallback."""
    # Try LLM first
    if CFG.genai.provider == "openrouter" and client.api_key:
        try:
            # Create model object for template (handle None or dict)
            model_obj = bundle.model
            if model_obj is None:
                from types import SimpleNamespace
                model_obj = SimpleNamespace(prob_up=0.5, prob_down=0.5, shap_values={})
            elif isinstance(model_obj, dict):
                from types import SimpleNamespace
                model_obj = SimpleNamespace(**model_obj)
            
            prompt = USER_PROMPT_TEMPLATE.format(
                ticker=bundle.ticker,
                date=bundle.date.isoformat(),
                signal=bundle.signal,
                fundamentals=bundle.fundamentals,
                guardrails=bundle.guardrails,
                regime=bundle.regime,
                model=model_obj,
                price_range=bundle.price_range,
            )
            response = await client.chat(
                [{"role": "system", "content": SYSTEM_PROMPT},
                 {"role": "user", "content": prompt}],
                temperature=CFG.genai.temperature,
                response_format={"type": "json_object"}
            )
            data = json.loads(response)
            return AnalystNote(**data)
        except Exception as e:
            print(f"LLM generation failed, using template: {e}")

    # Deterministic template fallback
    context = _build_template_context(bundle)
    rendered = render_template(CFG.genai.fallback_template, **context)
    return _parse_template_output(rendered)