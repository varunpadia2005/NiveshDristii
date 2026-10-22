"""Core data contracts - all modules exchange these typed objects."""
from dataclasses import dataclass
from datetime import date
from typing import Dict, List, Optional
import polars as pl


@dataclass
class ValidationIssue:
    level: str  # ERROR, WARN, INFO
    message: str
    details: dict = None


@dataclass
class ValidationReport:
    ticker: str
    issues: List[ValidationIssue]
    passed: bool


@dataclass
class PriceData:
    ticker: str
    df: pl.DataFrame  # date, open, high, low, close, volume, adj_*, adj_factor, suspicious_move
    metadata: dict
    validation: ValidationReport


@dataclass
class SignalReport:
    ticker: str
    date: date
    trend_score: float
    momentum_score: float
    volatility_score: float
    volume_score: float
    composite: float
    components: Dict[str, float]
    reasons: List[str]


@dataclass
class PriceRange:
    ticker: str
    date: date
    current_price: float
    volatility: float
    ranges: Dict[str, tuple[float, float]]  # e.g., "1d_90": (low, high)
    atr_bands: tuple[float, float]
    sr_levels: List[dict]


@dataclass
class FundamentalData:
    ticker: str
    pe_ratio: Optional[float]
    pb_ratio: Optional[float]
    roe: Optional[float]
    debt_to_equity: Optional[float]
    profit_margin: Optional[float]
    revenue_growth: Optional[float]
    sector: str
    as_of: date


@dataclass
class GuardrailReport:
    flags: List[dict]
    max_score_cap: int  # 100 or lower if guardrails triggered


@dataclass
class RegimeReport:
    market_state: str
    vix_level: float
    sector_quadrants: Dict[str, str]
    state_probs: Dict[str, float] = None


@dataclass
class ModelOutput:
    ticker: str
    date: date
    prob_up: float
    prob_down: float
    prob_flat: float
    shap_values: Dict[str, float]


@dataclass
class BacktestResult:
    equity_curve: pl.DataFrame  # date, equity
    trades: pl.DataFrame
    metrics: dict


@dataclass
class Trade:
    date: date
    ticker: str
    side: str  # "buy" / "sell"
    price: float
    shares: int
    cost: float


@dataclass
class FactsBundle:
    ticker: str
    date: date
    signal: SignalReport
    fundamentals: FundamentalData
    guardrails: GuardrailReport
    regime: RegimeReport
    price_range: PriceRange
    model: Optional[ModelOutput]
    backtest_stats: Optional[dict]


@dataclass
class AnalystNote:
    summary: str
    bull_case: List[str]
    bear_case: List[str]
    risks: List[str]
    would_change_view: List[str]