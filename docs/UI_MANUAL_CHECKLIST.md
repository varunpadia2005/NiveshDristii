# UI Manual Checklist (NEW, P8-S3) — run LOCALLY ONLY, after approval

Launch (never committed to any scheduler; manual):
```
"D:\venvs\niveshdristi\Scripts\streamlit" run src\niveshdristi\ui\app.py --server.address 127.0.0.1
```
`.streamlit/config.toml` already binds 127.0.0.1 with usage stats OFF.

- [ ] Light AND dark theme: every panel readable (no white-on-white)
- [ ] No color-only meaning: HALTED/FAILED/UNVERIFIED always carry text labels
- [ ] Mobile width (~375 px): columns stack, tables scroll, no clipping
- [ ] Keyboard: tab order logical; all controls are native Streamlit widgets
- [ ] Banner strip present on every page (DataLimitations, RATES UNVERIFIED,
      disclaimer) and never dismissible
- [ ] Footer as-of equals the ledger's last session (change the ledger, the
      as-of follows; it never matches the wall clock when data is older)
- [ ] "unavailable: no verified data source" panels for the 5 unbuilt pages
- [ ] Paper Fund: decisions sidecar shows verified payload; tamper a sidecar
      file -> page shows UNVERIFIED; delete decisions/ -> "decisions not
      recorded"
- [ ] Write actions invisible by default; with the flag on, halt requires
      the confirm checkbox; resume (CLI) still requires --note
- [ ] No currency symbols anywhere (ISO code from the profile only)
- [ ] Server binds 127.0.0.1 only; no external exposure; browser.gatherUsageStats=false
