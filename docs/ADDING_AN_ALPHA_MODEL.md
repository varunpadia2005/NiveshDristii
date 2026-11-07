# Adding an Alpha Model (NEW, P10-S5)

Worked examples: `alpha/quant/momentum.py` (live), `alpha/quant/
quality_value.py` (stub).

## Contract

```python
class MyModel:
    @property
    def model_id(self) -> str: ...

    def predict(self, ctx: AsOfContext, inputs: ModelInputs) -> list[Signal]:
        # ctx.as_of is the HARD ceiling: reading data past it is a
        # look-ahead bug that tests CANNOT catch inside the model
        # (see the M17 residual-risk note in docs/PROGRESS.md).
        ...

    def registry_entry(self) -> ModelRegistryEntry:
        # data_status: "live" | "stub" | "evidence_only" - HONESTLY
        ...
```

## Rules

1. Signal carries conviction in [-1, +1], a thesis, and evidence — the
   numbers cited in the thesis MUST be in evidence.
2. Currency: `currency=currency_for_market(ctx.market_id)` — never a
   literal.
3. Thresholds are named UNVALIDATED DEFAULT constants with comments.
4. data_status "stub" models are labelled "Stub: not computed" everywhere
   and contribute `stub_models_used` to the limitations.
5. The UI shows the model's lean as icon + word with a "Why?" expander;
   no buy/sell/hold vocabulary (the advice-verb test greps outputs).
6. Register in the live bundle(s) the CLI/services compose
   (services/signals_view.py `_live_bundle`) and add unit tests with
   fixture data + a documented `signal_horizon`.
