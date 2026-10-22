# NiveshDristi (निवेश दृष्टि)

**Investment Vision** — AI-driven research assistant for Indian equities.

## Overview

NiveshDristi collects market data and company filings, turns them into structured evidence (trend, momentum, valuation, risk, market regime, model probabilities), tests ideas with honest backtests, and explains results in plain language.

**Five Principles:**
1. Honesty over hype
2. No look-ahead, ever
3. Everything explainable
4. Engine computes, LLM narrates
5. Every feature testable

## Quick Start

### Prerequisites
- Python 3.11+
- Docker & Docker Compose (for local stack)
- OpenRouter API key (for AI analyst)

### Local Development

```bash
# 1. Clone and enter
cd NiveshDristii

# 2. Configure environment
cp .env.example .env
# Edit .env and add your OPENROUTER_API_KEY

# 3. Start stack (PostgreSQL + FastAPI + Streamlit)
docker-compose up --build

# 4. Open UI
# Streamlit: http://localhost:8501
# FastAPI docs: http://localhost:8000/docs
```

### Manual Python Setup (without Docker)

```bash
python -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"

# Start PostgreSQL separately, then:
uvicorn niveshdristi.api.main:app --reload  # Terminal 1
streamlit run src/niveshdristi/app/main.py   # Terminal 2
```

## Architecture

```
Raw Sources (yfinance .NS)
    │
    ▼
Data Layer: download, cache (Parquet+PG), validate, adjust
    │
    ▼
Analysis Layer: indicators (Polars), signals, fundamentals, regimes
    │
    ▼
Decision Layer: backtest (1-day delay, Indian costs), portfolio, ML
    │
    ▼
Explanation Layer: grounded AI (OpenRouter + Jinja2 fallback), validator
    │
    ▼
Interface: Streamlit (light/dark) + FastAPI
```

## Key Features

| Layer | Implementation |
|-------|----------------|
| **Data** | yfinance → Parquet + PG cache, abstract `DataProvider` for Kite/Upstox/NSE |
| **Indicators** | 8 indicators as Polars expressions (vectorized, no loops) |
| **Signals** | 4-group engine (-1 to +1), composite with plain-English reasons |
| **Fundamentals** | yfinance `.info` weekly PG cache, config-driven guardrails |
| **Regimes** | RRG sector rotation + Bull/Choppy/Bear market states |
| **Backtest** | Event-driven, 1-day delay, full Indian cost model, walk-forward |
| **ML** | Feature registry, purged CV, LightGBM + Optuna, SHAP, calibration |
| **GenAI** | OpenRouter (any model) + Jinja2 deterministic fallback |
| **Validator** | Number extraction → bundle verification → retry → fallback |
| **UI** | Streamlit, light theme default, dark toggle, 8 pages |

## Configuration

All parameters in `config.yaml`:
- Data sources, cache, universe, validation thresholds
- Indicator periods, signal weights, normalization
- Fundamental guardrails, regime parameters
- Backtest costs, portfolio constraints
- Model hyperparameters, GenAI settings
- App theme, pages

## Deployment

### Render (Backend) + Streamlit Cloud (Frontend)

1. Push to GitHub
2. **Render**: New Web Service → Docker → Set `OPENROUTER_API_KEY`, `DATABASE_URL` (Neon/Supabase)
3. **Streamlit Cloud**: Connect repo → Set `API_BASE=https://your-render-app.onrender.com`

## Project Structure

```
niveshdristi/
├── config.yaml              # All parameters
├── docker-compose.yml       # Local stack
├── Dockerfile
├── pyproject.toml
├── src/niveshdristi/
│   ├── config.py            # Pydantic Settings
│   ├── data/                # Providers, cache, adjust, validate, loader
│   ├── indicators/          # Polars expressions
│   ├── signals/             # Engine, conviction
│   ├── fundamentals/        # Loader, guardrails
│   ├── regime/              # RRG, market state
│   ├── backtest/            # Engine, walk-forward
│   ├── genai/               # OpenRouter, analyst, validator, templates
│   ├── api/                 # FastAPI endpoints
│   └── app/                 # Streamlit UI
├── tests/
├── cache/                   # Parquet (gitignored)
├── migrations/              # Alembic
└── prompts/                 # Versioned prompts
```

## Disclaimer

**NiveshDristi is an educational research tool, not investment advice.**
It does not recommend buying or selling any security. No SEBI registration.
All signals are computational outputs — verify independently before acting.