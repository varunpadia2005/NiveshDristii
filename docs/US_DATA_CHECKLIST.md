# US-Market Data Checklist (Phase 14-B, 2026-11-21)

Every external input needed to make `US_NYSE` usable, derived from the
code (file:line cited). **No rates, fees, tax percentages, holiday
dates, benchmark values or FX numbers appear in this document** — each
item carries a `SOURCE REQUIRED: <kind of source>` slot for you to
fill with a primary/official source. Owner of every item: you (the
data must come from outside this repo); I implement and test once a
source is supplied.

## Milestone order (dependencies)

1. **Costs + tax** → unblocks `to_rules(US_NYSE_PROFILE)` with non-zero
   rates (today it requires `costs_not_modeled=True` and yields zeros).
2. **Holiday calendar** → unblocks a non-derived US session calendar
   (today: `derived_calendar` limitation, sessions = data dates).
3. **Benchmark** → unblocks TRI-style return comparisons.
4. **FX rate (INR/USD)** → unblocks multi-market NAV composition.
5. **Data provider** → unblocks `data fetch/refresh` for US tickers.
6. **Stub-model data** → independent of 1–5; unblocks the four stub
   models one at a time.

Items 1–4 must ALL land before "US usable" (each is required by the
profile composition); item 5 replaces the typed shell; item 6 is
independent of the others.

---

## 1. US cost fields (12 null fields)

**Destination**: `src/niveshdristi/markets/in_us/costs.yaml` (fields
verbatim at lines 6-17 today, all `null` with `# UNVERIFIED` markers).

**Field names** (exact): `brokerage_per_order`, `brokerage_pct`,
`stt_delivery_buy_pct` (US analogue), `stt_delivery_sell_pct` (US
analogue), `stt_intraday_sell_pct` (US analogue), `exchange_charges_pct`,
`sebi_fees_pct` (regulator fee slot), `stamp_duty_buy_pct`,
`dp_charge_per_scrip`, `gst_pct`, `transaction_levy`,
`slippage_base_bps`.

**Validation the values must pass** (cited):
- `load_costs` strict loader (`markets/in_nse/loaders.py`, used by
  `test_us_profile.py::test_magnitude_checks_still_apply_to_non_null`)
  — rejects `ConfigurationError("fails sanity")` for absurd non-null
  values (e.g. 500% STT).
- `YFinanceClient`-free: these are consumed by `to_rules(profile)` →
  `MarketRules.rates`.

**Behavior before**: `us_market_rules` raises `CostsNotModeledError`
unless `costs_not_modeled=True`; rates are all 0.0 and the
`costs_not_modeled` limitation code + "COSTS NOT MODELED" banner are
attached (`markets/in_us/profile.py:41-44`).
**Behavior after**: `rates_verified` can become True, the banner and
limitation code drop, and US backtest/paper runs carry real cost
deductions.
**Acceptance test to add later**: US profile composes non-zero rates
and no longer carries `costs_not_modeled` (mirror of
`test_backtest_costs_flag.py` IN/US asymmetry test).

**SOURCE REQUIRED: primary/official US fee schedule** (exchange fee
schedule, regulator fee table, or the broker's published commission
schedule) — per field, with a retrieval date.

**Unblocks "US usable"?**: NO — only in combination with items 2, 3, 5
below (the profile composition needs all of them to drop the
limitation set).

## 2. US tax fields (6 null fields)

**Destination**: `src/niveshdristi/markets/in_us/tax.yaml` (fields at
lines 4-9, all `null`).

**Field names** (exact): `enabled`, `short_term_threshold_days`,
`short_term_rate`, `long_term_rate`, `long_term_exemption`,
`loss_setoff_years`.

**Validation**: same strict loader sanity checks as item 1.

**Behavior before**: `tax_model = None` in the profile (P9-S2);
`tax_enabled` runs produce zero accrual.
**Behavior after**: US tax accrual computes through the existing tax
seam.
**Acceptance test to add later**: US tax accrual test mirroring the
IN_NSE tax tests.

**SOURCE REQUIRED: official US tax rules** (IRS publication or the
broker's tax-handling schedule) — per field, with a retrieval date.

**Unblocks "US usable"?**: NO — combination only (see item 1).

## 3. US holiday calendar (empty)

**Destination**: `src/niveshdristi/markets/in_us/holidays_us.yaml`
(today: a comment only — "EMPTY BY DESIGN"; no `years_covered` key,
no `holidays` list).

**Schema** (mirror of `holidays_in.yaml`): `years_covered: [YYYY, …]`
plus a `holidays:` list of `"YYYY-MM-DD"  # Name` entries.

**Validation** (cited): the xfail test
`tests/test_market_profile.py:164-180` pattern — current year in
`years_covered` + at least one `current_year-` holiday entry — applies
to the US file the same way once populated (a US analogue of that test
is the acceptance test to add later).

**Behavior before**: US sessions are data-derived
(`derived_calendar` limitation; empty `holidays_us.yaml`).
**Behavior after**: US holidays become real non-sessions.

**SOURCE REQUIRED: official NYSE holiday calendar** (the exchange's
published holiday page or circular), per year, with a retrieval date.

**Unblocks "US usable"?**: NO — combination only.

## 4. US benchmark

**Destination**: `markets/in_us/profile.py:114`
(`benchmark_symbol=""`, `benchmark_is_total_return=False`).

**What is needed**: a benchmark symbol + whether it is total-return
(the `benchmark_not_tri` limitation exists for IN_NSE's
non-TR benchmark; VERIFY.md §13 records "Nifty TRI benchmark:
UNAVAILABLE — no source" for India).

**Validation** (cited): `benchmark_symbol` flows into
`markets/registry.py` profile composition; the empty-string value is
asserted by `test_us_profile.py::test_registered_second_market`.

**Behavior before**: US benchmark comparisons refuse (no benchmark).
**Behavior after**: US return comparisons compute against the
benchmark.

**SOURCE REQUIRED: official index provider page** for the chosen US
benchmark (e.g. a total-return index series), with a retrieval date.

**Unblocks "US usable"?**: NO — combination only.

## 5. INR/USD FX rate

**Destination**: `markets/fx.py` — an `FxRate` requires (fx.py:25-32):
`base_currency` (3 chars), `quote_currency` (3 chars), `rate` (> 0),
`source` (non-empty), `as_of` (date); `base != quote` enforced by the
model validator; `FxConverter.convert` REFUSES with
`FxRateUnavailable` when no rate exists for the pair/date — never
defaults to 1.0 (fx.py:66-79).

**Validation** (cited): the pydantic model constraints above;
`tests/test_fx.py::test_refusal_without_rate_is_typed` and
`test_distinct_currencies` pin the refusal semantics.

**Behavior before**: multi-market NAV is groundwork only
(`FxRateUnavailable` on any cross-currency conversion).
**Behavior after**: multi-market NAV composes conversions for
sourced pairs/dates.

**SOURCE REQUIRED: a published FX rate series with a retrieval date**
(e.g. a central bank reference rate) — per pair/date.

**Unblocks "US usable"?**: NO — combination only (needed only for
INR-denominated reporting of US positions).

## 6. US data provider

**Destination**: `markets/in_us/providers/us_adapter.py` — every role
raises a typed `DataError` today (prices :31, fundamentals :37,
corporate_actions :43, index_constituents :46, flows :49, filings :51).

**What is needed**: a real `DataClient` implementation for US_NYSE
(the shell's `fetcher` constructor parameter is the designed injection
point, us_adapter.py:24).

**Validation** (cited): the DataClient protocol
(`marketdata/client.py:47-80`); the shell tests
(`test_providers_p9.py::test_us_shell_every_role_raises`,
`test_shell_does_no_network`).

**Behavior before**: every US data role raises typed `DataError`
(no network, no suffix logic).
**Behavior after**: US data flows through the same protocol.

**SOURCE REQUIRED: a US market data feed** you are licensed to use —
per role.

**Unblocks "US usable"?**: NO — combination only (and the largest
effort item).

## 7. Stub-model traceability table

| Model | file:line of stub marker | Missing data | required_data | Source kind | Where it plugs in |
|---|---|---|---|---|---|
| earnings_drift | alpha/quant/earnings_drift.py:96 | `announced_at`-dated fundamentals + prices | fundamentals, prices | announcement-dated earnings source | `inputs.fundamentals` (ModelInputs), earnings_drift.py:39-40 |
| fundamental_guardrails | alpha/quant/fundamental_guardrails.py:131 | PIT fundamentals (announcement-dated records; legacy `FundamentalData` fields at :38) | fundamentals | PIT fundamentals source | `inputs.fundamentals` — fundamental_guardrails.py:39-40, `_fund_from_pit` :64 |
| sector_rotation | alpha/quant/sector_rotation.py:130 | verified sector-index + benchmark series | prices (sector_index/benchmark roles) | sector index data | inputs.prices via the sector_index/benchmark roles |
| quality_value | alpha/quant/quality_value.py:82 | PIT fundamentals (ROCE/earnings-yield fields) | fundamentals | PIT fundamentals source | `inputs.fundamentals` — quality_value.py:39+ |

Each becomes live by replacing its `data_status="stub"` with
`"live"` ONLY after the named source exists and is wired — the
predict() implementations already consume `ModelInputs` and are
exercised by tests today.

## 8. Order-of-operations summary

"US usable" = items 1 + 2 + 3 + 5 all supplied and composed, plus
item 6 for live US data; item 4 (benchmark) and item 7 (stub models)
are valuable but not part of the minimal "US usable" bar. Every item
lands as: you supply the source → I wire it into the destination file
with its validation → acceptance test → CI green.
