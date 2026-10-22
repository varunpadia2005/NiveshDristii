# NiveshDristi — Rates & Rules Requiring Verification

**Source:** `docs/CHANGES.md` §7 (India Market Rule Sheet) + `config.yaml`  
**Rule:** Every rate marked `# VERIFY` must be confirmed against current SEBI/NSE circulars and Finance Act before production use.

---

## 1. Trading Session & Settlement

| Item | Current Value | Source to Verify | Status |
|------|---------------|------------------|--------|
| Session hours | 09:15–15:30 IST | NSE circular | 🔴 Unverified |
| Pre-open session | ~09:00–09:15 | NSE circular | 🔴 Unverified |
| Settlement cycle | T+1 | SEBI circular | 🔴 Unverified |
| Muhurat trading | Special Diwali session | NSE calendar | 🔴 Unverified |
| Saturday special sessions | Occasional | NSE circular | 🔴 Unverified |

---

## 2. Shorting Rules (Cash Segment)

| Item | Current Value | Source to Verify | Status |
|------|---------------|------------------|--------|
| Intraday shorting | Allowed | SEBI/Exchange rules | 🔴 Unverified |
| Delivery shorting | **Not allowed** for retail | SEBI rules | 🔴 Unverified |
| F&O shorting | Via derivatives only | SEBI rules | 🔴 Unverified |
| SLB (Securities Lending) | Institutional only | SEBI SLB framework | 🔴 Unverified |

---

## 3. Price Bands / Circuit Limits

| Item | Current Value | Source to Verify | Status |
|------|---------------|------------------|--------|
| Circuit filter categories | 2% / 5% / 10% / 20% | NSE circular (varies by stock) | 🔴 Unverified |
| F&O stocks dynamic bands | Exchange-determined | NSE circular | 🔴 Unverified |
| Index circuit limits | 10% / 15% / 20% (Nifty) | SEBI/NSE | 🔴 Unverified |
| Pre-open price band | Based on previous close | NSE rules | 🔴 Unverified |

---

## 4. Transaction Costs (from `config.yaml` — MUST MOVE to `markets/in_nse/costs.yaml`)

| Cost Component | Current Value | Unit | Source to Verify | Status |
|----------------|---------------|------|------------------|--------|
| Brokerage (flat per order) | 20.0 | ₹ | Broker schedule / SEBI max | 🔴 Unverified |
| STT (delivery sell) | 0.1 | % | Finance Act / SEBI | 🔴 Unverified |
| STT (intraday sell) | 0.025 | % | Finance Act / SEBI | 🔴 Unverified |
| Exchange transaction charges | 0.00345 | % | NSE / BSE circular | 🔴 Unverified |
| SEBI turnover fee | 0.0001 | % | SEBI circular | 🔴 Unverified |
| Stamp duty (buy side) | 0.015 | % | Indian Stamp Act / State rules | 🔴 Unverified |
| GST (on brokerage + charges) | 18.0 | % | GST Council | 🔴 Unverified |
| DP charge (per scrip on sell) | *Missing* | ₹ | Depository (CDSL/NSDL) | 🔴 Unverified |
| Slippage model | 5.0 | bps | Internal assumption | 🔴 Unverified |

> **Note:** All above must move to `markets/in_nse/costs.yaml` with `# VERIFY` comments per spec.

---

## 5. Capital Gains Tax (from `config.yaml` — MUST MOVE to `markets/in_nse/tax.yaml`)

| Item | Current Value | Source to Verify | Status |
|------|---------------|------------------|--------|
| STCG rate (listed equity, <12 months) | 20% (post Budget 2024) | Finance Act 2024 | 🔴 Unverified |
| LTCG rate (listed equity, ≥12 months) | 12.5% (post Budget 2024) | Finance Act 2024 | 🔴 Unverified |
| LTCG annual exemption | ₹1.25 lakh (post Budget 2024) | Finance Act 2024 | 🔴 Unverified |
| Holding period threshold | 12 months | Income Tax Act | 🔴 Unverified |
| Loss set-off rules | STCL vs STCG/LTCG; LTCL vs LTCG only | Income Tax Act | 🔴 Unverified |
| Indexation benefit | Removed for equity (Budget 2024) | Finance Act 2024 | 🔴 Unverified |

> **Note:** Rates changed in Budget 2024 (July) and may change again. Verify against latest Finance Act.

---

## 6. Fundamental Reporting Timelines (for PIT Lags)

| Item | Current Assumption | SEBI Rule | Status |
|------|-------------------|-----------|--------|
| Quarterly results deadline | 45 days from quarter end | LODR Regulation 33 | 🔴 Unverified |
| Annual (Q4) results deadline | 60 days from year end | LODR Regulation 33 | 🔴 Unverified |
| Shareholding pattern filing | 21 days from quarter end | LODR Regulation 31 | 🔴 Unverified |
| Promoter pledge disclosure | Within 7 days of creation/change | SEBI (SAST) Regulations | 🔴 Unverified |
| Insider trading (PIT) disclosures | Within 2 days | SEBI (PIT) Regulations | 🔴 Unverified |
| Bulk/block deal reporting | Same day (post-market) | NSE/BSE circular | 🔴 Unverified |

---

## 7. NSE Holidays & Calendar

| Item | Current State | Source | Status |
|------|---------------|--------|--------|
| 2024 holidays | Hard-coded 13 dates in `data/universe.py` | NSE circular | 🔴 Unverified |
| 2025+ holidays | **Missing** | NSE annual circular | 🔴 Unverified |
| Muhurat trading date | Not handled | NSE Diwali circular | 🔴 Unverified |
| Trading calendar library | Custom `is_trading_day()` | `nsepython` / `jugaad-data` / official | 🔴 Unverified |

---

## 8. Sector Taxonomy & Indices

| Item | Current State | Source | Status |
|------|---------------|--------|--------|
| NSE sector indices (8) | Hard-coded in `regime/rrg.py` | NSE Indices website | 🔴 Unverified |
| Sector ETF tickers (yfinance) | May not all exist | yfinance / NSE | 🔴 Unverified |
| GICS mapping | Not implemented | MSCI / NSE | 🔴 Unverified |

---

## 9. Market Data Sources (Terms of Use)

| Source | Data | Terms Checked? | Status |
|--------|------|----------------|--------|
| yfinance (`.NS`, `.BO`, `^NSEI`, `^INDIAVIX`) | Prices, fundamentals, indices | ❌ No | 🔴 Unverified |
| `jugaad-data` / `nsepython` | NSE bhavcopy (EOD + delivery qty) | ❌ No | 🔴 Unverified |
| niftyindices.com | Official index history + TRI | ❌ No | 🔴 Unverified |
| NSE/BSE corporate filings | Shareholding, pledges, insider trades | ❌ No | 🔴 Unverified |
| FII/DII daily flows | NSDL/CDSL / NSE reports | ❌ No | 🔴 Unverified |
| RBI / FRED / World Bank | Macro (repo, CPI, INR, crude, G-sec) | ❌ No | 🔴 Unverified |

> **Rule:** Avoid scraping sites whose terms forbid it. Prefer exchange disclosures and licensed APIs.

---

## 10. Lot Sizes & F&O (Out of Scope for v1)

| Item | Note |
|------|------|
| F&O lot sizes | Revised periodically by NSE; later module |
| Margin requirements | SPAN + exposure; later module |
| Expiry calendar | Monthly/weekly; later module |

---

## Verification Process

1. **Before each phase** that uses a rate, check this list
2. **Mark verified** with date and source (circular number, Act section, URL)
3. **Update `config.yaml` / `markets/in_nse/*.yaml`** with verified values
4. **Add `# VERIFIED: <date> <source>`** comment next to the rate
5. **Move verified rates** from `config.yaml` to `markets/in_nse/` YAML files per spec

---

## Quick Reference: Current `config.yaml` Costs (to migrate)

```yaml
backtest:
  costs:
    brokerage_per_order: 20.0           # VERIFY
    stt_delivery_sell_pct: 0.1          # VERIFY
    stt_intraday_sell_pct: 0.025        # VERIFY
    exchange_charges_pct: 0.00345       # VERIFY
    sebi_fees_pct: 0.0001               # VERIFY
    stamp_duty_buy_pct: 0.015           # VERIFY
    gst_pct: 18.0                       # VERIFY
    slippage_bps: 5.0                   # VERIFY (assumption)
```

---

*Last updated: 2026-10-22 — All items unverified*