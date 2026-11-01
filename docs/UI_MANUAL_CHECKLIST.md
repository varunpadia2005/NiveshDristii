# UI Manual Checklist (NEW, P8-S3; D1d demo-fund commands)

## 0. Generate the demo fund (PowerShell, one-time)

```powershell
cd "D:\Nivesh Dristi\NiveshDristii"
& "D:\venvs\niveshdristi\Scripts\python.exe" tools\make_demo_fund.py --base "D:\Nivesh Dristi\demo_funds" --tamper-ledger --tamper-sidecar
```

Writes THREE funds into `D:\Nivesh Dristi\demo_funds` (never the repo,
never the default fund directory):
- `demo_synthetic` — healthy: 130 sessions, fills, verified ledger
- `demo_synthetic_tampered_ledger` — one cash digit flipped
- `demo_synthetic_tampered_sidecar` — one decision sidecar corrupted

## 1. Run the app against the demo base (PowerShell)

```powershell
cd "D:\Nivesh Dristi\NiveshDristii"
$env:NDR_FUND_BASE = "D:\Nivesh Dristi\demo_funds"
$env:NDR_FUND_ID   = "demo_synthetic"
& "D:\venvs\niveshdristi\Scripts\python.exe" -m streamlit run src\niveshdristi\ui\app.py
```

(`.streamlit/config.toml` binds 127.0.0.1, headless, usage stats OFF,
XSRF on, CORS closed. The UI reads the base/id from NDR_FUND_BASE /
NDR_FUND_ID — nothing is hard-coded.) Switch funds by changing
NDR_FUND_ID and rerunning. STOP: press Ctrl+C in the terminal (the
server is foreground) — no scheduler entry, no background process.

## 2. Per-check expectations

- [ ] Banner strip on every page: DATA LIMITATIONS list, RATES UNVERIFIED
      (red), the verbatim disclaimer (info). Not dismissible.
- [ ] Footer: `as-of: 2026-10-30` (the demo's last session — never today's
      date), market labels from the profile (ISO currency code).
- [ ] **demo_synthetic**: verify chip "verified"; positions table with
      SYN090/SYN091; decisions panel shows the sidecar payload (verified).
- [ ] **demo_synthetic_tampered_ledger** (set NDR_FUND_ID accordingly):
      verify chip shows FAILED (loud) naming "line 2: hash mismatch".
- [ ] **demo_synthetic_tampered_sidecar**: decisions panel shows the
      UNVERIFIED warning (content hash mismatch), display only.
- [ ] Overview/Deep-Dive/Signals/Backtest Lab/Settings: "unavailable: no
      verified data source" panels until their phases land (S5-S9 build
      them progressively).
- [ ] Write actions (halt) are INVISIBLE. To exercise: set
      `st.session_state["allow_write_actions"]=True` via a debug runner —
      production UI leaves them off.
- [ ] Narrow window (~400 px): columns stack, tables scroll horizontally.
- [ ] Both themes (Streamlit theme menu): light is the default and every
      text/background pair passes WCAG (see the contrast report in
      tests/test_theme.py output); dark stays readable.
- [ ] No animations, no emoji anywhere. Signals are icon + word, never
      colour alone; the legend (up = green, down = red) is visible.
