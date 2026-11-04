# UI React Track (NEW, P8-S10, docs only — nothing built)

A future Next.js/FastAPI client would sit ON TOP OF the same services/
composition layer. Nothing in this document is implemented.

## Read-only endpoint list (derived from services/, deferred ones struck)

- GET /api/fund/{id}            → services.read_fund        (banners, verify, positions)
- GET /api/fund/{id}/overview   → services.fund_overview    (KPIs, feed, needs-attention)
- GET /api/fund/{id}/signals    → services.signals_view     (board rows)
- GET /api/fund/{id}/deepdive   → services.deep_dive        (candles, panes, zones)
- GET /api/fund/{id}/records    → services.records_page     (paginated)
- GET /api/fund/{id}/events     → services.events_panel
- GET /api/settings             → services.settings_view    (key presence only)
- ~~POST /explain~~             → deferred: LLM text is UNTRUSTED display-only and
  Phase 7 keeps LlmView out of every automated path; a POST endpoint would
  need the same validators + budget + redaction over HTTP first.
- ~~POST /halt, /resume~~       → deferred: write actions stay CLI/UI-flag-gated;
  the React client is read-only by design (no auth on localhost).
- ~~POST /backtest~~            → deferred: the engine backtest is display-only and
  should not be triggerable remotely before budgets/timeouts are designed.
- ~~WS /live prices~~           → deferred: no verified live data source exists.

## Security requirements
- Loopback binding only (127.0.0.1); no auth BECAUSE local-only; CORS
  closed (no cross-origin callers); no write endpoints; XSRF irrelevant
  without cookies but keep the XSRF middleware on; every response carries
  the DataLimitations + RATES UNVERIFIED banners and the data as-of date.

## Licence checks before adopting any template or chart library
- React/Next.js: MIT (verify at adoption time).
- Charting (recharts/visx/lightweight-charts): recharts MIT; TradingView
  lightweight-charts is Apache-2.0 — CHECK attribution/redistribution terms
  in the LICENSE before bundling.
- Any template ("dashboard kit"): verify its licence permits the derived
  private use and does not require attribution in the UI.

## New-tooling impact
- Node LTS + package.json + lockfile at the repo root (or ui-react/);
  NO pyproject change; the Python services layer is untouched; CI would
  need a Node job (out of scope until adopted).

## Recommendation
Build it only AFTER Phase 10 hardening, and only if the Streamlit client's
ergonomics prove limiting: the services layer already contains every
capability the React client would read; the port is a rendering change,
not a logic change.
