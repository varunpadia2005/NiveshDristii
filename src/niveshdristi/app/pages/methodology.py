"""Methodology page: Interactive documentation with Groww-inspired design."""
import streamlit as st
from niveshdristi.app.components import (
    page_header, render_disclaimer, tag, empty_state
)


def render(api_get):
    
    page_header("Methodology", "How NiveshDristi works - transparent, explainable, and honest", "📚")
    
    # Table of contents
    st.markdown("### Table of Contents")
    toc_items = [
        ("1. Data Layer", "data-layer", "📥"),
        ("2. Technical Indicators", "indicators", "📊"),
        ("3. Signal Engine", "signals", "🎯"),
        ("4. Fundamentals & Guardrails", "fundamentals", "📋"),
        ("5. Market Regimes", "regimes", "🌍"),
        ("6. Backtesting", "backtest", "🧪"),
        ("7. Machine Learning", "ml", "🤖"),
        ("8. GenAI Layer", "genai", "🧠"),
        ("9. Principles & Safeguards", "principles", "🛡️"),
    ]
    
    cols = st.columns(3)
    for i, (title, anchor, icon) in enumerate(toc_items):
        with cols[i % 3]:
            if st.button(f"{icon} {title}", key=f"toc_{anchor}", use_container_width=True):
                st.session_state.methodology_section = anchor
                st.rerun()
    
    # Current section
    section = st.session_state.get("methodology_section", "data-layer")
    
    st.markdown("---")
    
    # Section content
    sections = {
        "data-layer": {
            "title": "1. Data Layer",
            "icon": "📥",
            "content": """
            ### Data Sources
            - **Primary**: Yahoo Finance (`yfinance`) with `.NS` suffix for NSE stocks
            - **Abstract Interface**: `DataProvider` protocol allows swapping to NSE API, Kite, Upstox, AngelOne
            - **Fundamentals**: yfinance `.info` + financial statements (P/E, ROE, D/E, Sector, Margins, Growth)
            
            ### Caching Strategy
            - **Local**: Parquet files (one per ticker) - fast, columnar, portable
            - **Shared**: PostgreSQL with asyncpg - for production deployments
            - **TTL**: 1 day for prices, 7 days for fundamentals
            
            ### Price Adjustment
            - Split & dividend adjusted close via `adj_close` from yfinance
            - Adjusted OHLCV columns (`adj_open`, `adj_high`, `adj_low`, `adj_close`)
            - Suspicious move detection (>40% single day) flagged for review
            
            ### Validation
            - **ERROR**: Duplicate dates, High < Low, zero/negative prices
            - **WARN**: Missing trading days (>5%), volume spikes, large gaps
            - **INFO**: Short history, stale data
            - Bad data quarantined, not silently dropped
            
            ### Time Handling
            - All dates = trading days in IST
            - Market closes 3:30 PM IST
            - Signals computed at close → trades at next open (1-day delay)
            """
        },
        "indicators": {
            "title": "2. Technical Indicators",
            "icon": "📊",
            "content": """
            ### Implemented as Polars Expressions (Vectorized)
            All indicators are pure Polars expressions - no Python loops, fully vectorized.
            
            | Indicator | Parameters | Output | Purpose |
            |-----------|------------|--------|---------|
            | SMA | 20, 50, 200 | Trend | Moving average levels |
            | EMA | 20, 50, 200 | Trend | Exponential moving averages |
            | RSI | 14 | Momentum | Overbought/oversold (0-100) |
            | MACD | 12, 26, 9 | Momentum | Trend changes, signal line |
            | Bollinger Bands | 20, 2σ | Volatility | Price stretch, squeeze |
            | ATR | 14 | Volatility | Position sizing, stops |
            | ADX | 14 | Trend Strength | Trend vs range (25+ = trend) |
            | OBV | - | Volume | Volume confirmation |
            
            ### Computation
            - Single pass with `df.with_columns()` for all indicators
            - BB %B calculated after bands for stretch score
            - Volume ratio = Volume / 20-day average volume
            """
        },
        "signals": {
            "title": "3. Signal Engine",
            "icon": "🎯",
            "content": """
            ### Four-Group Scoring (-1 to +1)
            Each indicator normalized to [-1, 1] then grouped:
            
            | Group | Weight | Indicators | Style |
            |-------|--------|------------|-------|
            | Trend | 0.35 | EMA positions, ADX | Momentum-following |
            | Momentum | 0.30 | RSI, MACD histogram | Momentum-following |
            | Volatility Stretch | 0.15 | BB %B | Contrarian |
            | Volume | 0.20 | OBV trend, Volume ratio | Confirming |
            
            ### Composite Score
            `composite = Σ(weight_i × score_i)` → range [-1, +1]
            
            ### Plain-English Reasons
            Each signal includes human-readable reasons:
            - "Price above 200-day EMA"
            - "RSI overbought (>70)"
            - "MACD histogram positive"
            - "Near upper Bollinger Band"
            - "Above-average volume"
            
            ### Normalization Methods
            Configurable: `sigmoid`, `rank`, `zscore`, `minmax`
            """
        },
        "fundamentals": {
            "title": "4. Fundamentals & Guardrails",
            "icon": "📋",
            "content": """
            ### Metrics (from yfinance .info)
            - P/E, P/B, ROE, Debt/Equity, Profit Margin, Revenue Growth, Sector
            
            ### Sector-Relative Scoring (Future)
            - Percentile ranks within sector
            - Financial sector special handling (skip D/E, use CAR, NPA)
            
            ### Guardrails (Config-driven)
            Configurable rules in `config.yaml`:
            ```yaml
            guardrails:
              - metric: "debt_to_equity"
                operator: ">"
                threshold: 2.0
                severity: "warn"
                message: "High leverage"
                applies_to: "non_financial"
            ```
            
            ### Guardrail Actions
            - **info**: Flag only, no score impact
            - **warn**: Cap conviction score at 60
            - **error**: Cap conviction score at 30
            
            ### Missing Data
            - Recorded as `unavailable` with reason (not zero)
            - Prevents silent distortion of scores
            """
        },
        "regimes": {
            "title": "5. Market Regimes",
            "icon": "🌍",
            "content": """
            ### Relative Rotation Graph (RRG)
            - Sector ETFs vs Nifty 50 benchmark
            - **RS-Ratio**: Relative strength vs benchmark (100 = neutral)
            - **RS-Momentum**: Rate of change of RS-Ratio (100 = neutral)
            - Four quadrants: **Leading** → **Weakening** → **Lagging** → **Improving** → repeat
            
            ### Market Regime (HMM)
            - Hidden Markov Model on: Nifty returns, realized volatility, India VIX
            - States: **Bull** (calm uptrend), **Choppy** (sideways), **Bear** (stress)
            - Walk-forward training with purging/embargo
            - State ordering by volatility (post-hoc)
            
            ### Usage
            - Regime as feature for ML models
            - Position sizing filter (reduce size in Bear)
            - Conviction score component
            """
        },
        "backtest": {
            "title": "6. Honest Backtesting",
            "icon": "🧪",
            "content": """
            ### Core Principles
            - **1-day delay**: Signal@close → Trade@next_open (mandatory)
            - **Full Indian cost model**: Brokerage, STT, Exchange, SEBI, Stamp, GST, Slippage
            - **Position sizing**: Volatility targeting, ATR stops, Kelly fraction
            
            ### Cost Model (configurable)
            | Cost | Rate |
            |------|------|
            | Brokerage | ₹20/order |
            | STT (delivery sell) | 0.1% |
            | STT (intraday sell) | 0.025% |
            | Exchange charges | 0.00345% |
            | SEBI fees | 0.0001% |
            | Stamp duty (buy) | 0.015% |
            | GST | 18% on brokerage+charges |
            | Slippage | 5 bps |
            
            ### Validation Defenses
            - **Walk-forward**: Expanding window train → rolling test
            - **Monte Carlo**: Reshuffle trade sequence
            - **Bootstrap CI**: 1000+ resamples for Sharpe
            - **Shift test**: +1 day delay (leak collapses, edge fades)
            - **Holdout**: Recent period untouched until final
            - **Golden tests**: Fixed strategy + data = fixed equity curve
            
            ### Metrics
            CAGR, Volatility, Sharpe, Sortino, Max DD, Calmar, Profit Factor, Turnover
            """
        },
        "ml": {
            "title": "7. Machine Learning",
            "icon": "🤖",
            "content": """
            ### Prediction Targets
            - **Classification**: Will stock hit profit target before stop-loss within N days?
            - **Ranking**: Which stocks will outperform peers? (more robust)
            
            ### Features
            - Multi-period returns (1, 5, 10, 20, 60d)
            - Volatility (realized, EWMA)
            - Indicator states (RSI, MACD, BB%, etc.)
            - Volume ratios, OBV trends
            - Relative strength vs sector & index
            - Macro (VIX, USDINR, Crude, Rates)
            - Regime probabilities
            - **Cross-sectional ranking per date** (removes market-level shifts)
            - **Fundamentals excluded** until point-in-time store exists
            
            ### Labels: Triple Barrier
            - Profit target: +k × ATR
            - Stop loss: -k × ATR
            - Time limit: N days
            - Label: which barrier hit first
            
            ### Purged Cross-Validation
            - Expanding window with purging (remove overlapping labels)
            - Embargo period after test window
            - Sample weighting for overlapping labels
            
            ### Models
            - Baselines: Always-long, Random, Logistic Regression
            - **LightGBM** (primary): Fast, handles noise, SHAP explainability
            - LSTM/Transformer (optional): Sequence models, must beat LightGBM on holdout
            - Ensembles: Out-of-fold blending
            
            ### Calibration & Explainability
            - Isotonic/Platt calibration → Brier score, calibration curves
            - SHAP values for feature attribution
            - Meta-labeling: second model on rule-based signals
            - Conformal prediction for price ranges
            
            ### Evaluation
            - IC (rank correlation), IC IR
            - Decile spread (top 10% - bottom 10%) after costs
            - Turnover, capacity analysis
            - Deflated Sharpe (adjusts for multiple trials)
            - Population Stability Index (drift monitoring)
            
            ### Model Lifecycle
            - Train expanding window → validate recent → champion/challenger
            - Monitor PSI, live accuracy, paper-trading ledger
            - Retrain monthly/quarterly, promote only with pre-defined margin
            """
        },
        "genai": {
            "title": "8. GenAI Layer",
            "icon": "🧠",
            "content": """
            ### Grounded AI Analyst
            - **Facts Bundle**: Signals, fundamentals, guardrails, regime, model prob, price ranges, backtest stats
            - **Strict Prompt**: Only use provided numbers, no buy/sell language, include uncertainty
            - **Structured Output**: JSON with summary, bull_case, bear_case, risks, would_change_view
            
            ### Validator
            - Extract all numbers from AI output
            - Check each exists in facts bundle (±0.01 tolerance, % vs decimal)
            - On mismatch: retry once with errors listed
            - On second failure: fallback to deterministic template
            
            ### RAG for Documents
            - Sources: Annual reports, concall transcripts, investor presentations
            - Chunking: 500 tokens, 100 overlap
            - Embeddings: sentence-transformers (finance-tuned if available)
            - Vector store: FAISS/ChromaDB
            - Prompt injection defense: ignore instructions in retrieved docs
            - Output: Answer + citations (doc, page, chunk)
            
            ### Natural Language Screener
            - LLM translates NL → structured filter object (validated)
            - Code validates: allowed fields, operators, types
            - Shows parsed filter to user before execution
            - Model never writes executed code
            
            ### LLM Provider: OpenRouter
            - Single key → DeepSeek, Claude, Nemotron, Gemini, etc.
            - **Jinja2 deterministic fallback** (offline, free, guaranteed JSON)
            
            ### Evaluation
            - Versioned prompts in `prompts/`
            - Fixed eval set: retrieval hit rate, citation accuracy, unsupported-number rate, answer quality
            - Regression gate: metrics must not worsen
            """
        },
        "principles": {
            "title": "9. Principles & Safeguards",
            "icon": "🛡️",
            "content": """
            ### Five Core Principles
            1. **Honesty over hype** - Results with costs, uncertainty, limits
            2. **No look-ahead, ever** - Only info available on that day
            3. **Everything explainable** - Every score traceable to source numbers
            4. **Engine computes, LLM narrates** - Numbers from testable code, AI only writes words
            5. **Every feature testable** - If not testable, not finished
            
            ### What NiveshDristi is NOT
            - Not a trading bot
            - Does not promise returns
            - Does not tell anyone to buy/sell
            - Not SEBI-registered (educational research tool)
            
            ### Data Contracts
            Typed dataclasses for all module interfaces:
            - `SignalReport`, `PriceRange`, `FundamentalData`
            - `GuardrailReport`, `RegimeReport`, `ModelOutput`
            - `FactsBundle`, `AnalystNote`, `BacktestResult`
            
            ### Configuration
            All thresholds, weights, costs in `config.yaml` (not code)
            - Change behavior without editing logic
            - Versioned with code
            
            ### Testing
            - Unit tests for pure functions
            - Property tests (invariants: RSI ∈ [0,100], sizes ≤ caps)
            - Leakage tests (features@t on truncated data = full@t)
            - Golden tests (fixed strategy + data = fixed equity curve)
            - Integration tests (CLI runs for multiple tickers)
            - CI/CD: lint, type-check, test on every push
            
            ### Extension Patterns
            - **Registries**: Indicators, strategies, models register by name
            - **Base classes**: Strategies, models implement standard interface
            - **Guardrails as data**: Add rules in config, not code
            - **Feature registry**: Declare name, group, inputs, publication lag
            
            ### Changelog & Versioning
            - Cache version, feature version, model version, prompt version
            - Bump on logic changes so stale caches never mix
            - Keep old models loadable (store feature list + settings)
            """
        },
    }
    
    sec = sections.get(section, sections["data-layer"])
    
    st.markdown(f"""
    <div style="margin-bottom: 24px;">
        <h1 style="margin: 0; font-size: 28px; font-weight: 700; display: flex; align-items: center; gap: 12px;">
            {sec['icon']} {sec['title']}
        </h1>
    </div>
    """, unsafe_allow_html=True)
    
    st.markdown(sec['content'])


def render(api_get):
    # theme_toggle() is called in main.py
    render_disclaimer()