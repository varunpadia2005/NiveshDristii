# Definition-of-done status (NEW, P10-S7)

Against docs/CHANGES.md section 12 ("Definition of done (v1, India)"):

| # | Item | Status | Proof / blocker |
|---|---|---|---|
| 1 | `nd backtest` offline from cache, net-of-cost vs Nifty TRI + gate verdict | **PARTIAL** | `nd backtest run` (P10-S3) runs offline over stored snapshots with the gate verdict; **BLOCKED: no Nifty TRI source exists** (docs/VERIFY.md §13) — benchmark comparison is unavailable by design. tests/test_cli.py::TestBacktestRunP10 |
| 2 | `nd paper create/tick/status/halt/resume` idempotent, ledger verifies | **DONE-TESTED** | test_tick_idempotent_noop_byte_for_byte; TestPaperLedger (verify/tamper); test_paper_cli.py |
| 3 | Every legacy analytic an AlphaModel; ≥5 new, 3 India-specific | **DONE-TESTED** | alpha/quant/* registry tests (test_alpha.py); 3 India-specific: ta_ensemble, regime, sector_rotation (stubs honestly labelled) |
| 4 | LLM narrator grounded, schema-valid; lying-LLM rejected | **DONE-TESTED** | tests/test_llm.py (validate_output rejection tests), test_llm_safety.py (24-payload injection set) — narrator personas themselves are DEFERRED (P7 scope excluded by binding R2) |
| 5 | Streamlit six pages, as-of stamps + disclaimers | **DONE-TESTED** | tests/test_ui.py (all pages render banners + data-derived as-of); manual checklist docs/UI_MANUAL_CHECKLIST.md |
| 6 | US profile smoke test, zero core/engine edits | **DONE-TESTED** | tests/test_two_market.py (core/engine diff vs 6948457 asserted EMPTY inside the test; costs_not_modeled now first-class per D4) |
| 7 | CI green, no network calls in tests | **PARTIAL** | .github/workflows/ci.yml written (docs/CI.md) — NOT RUN (needs your 3 action SHAs, then push); offline-ness proven structurally (shell providers, FakeLLM, G18) |

Plain statement: items 1 and 7 are partial for the same two reasons the
whole project carries — no verified TRI source, and CI not yet pushed.
Everything else is done and tested.
