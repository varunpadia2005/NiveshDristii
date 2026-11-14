# Adding a Market (NEW, P10-S5)

Phase 9's US_NYSE is the worked example. The engine and core NEVER change;
everything lives in `markets/<id>/`.

## Steps (worked: markets/in_us/)

1. **Profile** — `markets/in_us/profile.py`: a `MarketProfile` (market_id,
   name, timezone, currency, digit_grouping, compact_units, session times,
   settlement, cost/tax models, benchmark, calendar path, shorting flags)
   + `register_market(...)`.
2. **Rates policy** — if no rate is verified, the YAML files carry
   `null` with `# UNVERIFIED: no value entered`, and composition requires
   the explicit `costs_not_modeled=True` flag (typed
   `CostsNotModeledError` otherwise; the result carries the COSTS NOT
   MODELED banner and the limitation code). NEVER invent a number.
3. **Holiday calendar** — an EMPTY yaml + the `derived_calendar`
   limitation until an official list is verified. No invented dates.
4. **Provider shell** — `markets/in_us/providers/<id>_adapter.py`: a
   DataClient shell where EVERY role raises a typed error (no network, no
   suffix logic). Register it in `markets/providers_registry.py` keyed by
   market_id.
5. **Gate** — add the provider file to the G10 adapter allowlist; the
   literal guard treats the profile as a market zone.
6. **Currency** — add the market to `alpha/currency.py`
   MARKET_CURRENCIES (the registry-sync TEST asserts agreement).
7. **Two-market proof** — extend tests/test_two_market.py: the SAME
   run_backtest + one paper tick for the new market on synthetic data.

## Checklist

- [ ] registry.get(market_id) resolves
- [ ] provider shell raises for every role
- [ ] null-rate policy typed error fires without the flag
- [ ] limitation codes ride (costs_not_modeled, derived_calendar, ...)
- [ ] services formatting uses the profile (grouping, compact units)
- [ ] literal guard passes; G10 allowlist updated
