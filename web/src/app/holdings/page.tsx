"use client";

// P20-WEB S3d: Holdings — table with weight bars, colored P&L with
// arrows, totals. Ledger-derived numbers only.
import { useEffect, useState } from "react";
import { getHoldings, fmtMoney, HoldingsView } from "@/lib/api";
import { useFundCtx } from "@/app/providers";
import { Shell } from "@/components/shell";
import { ApiErrorBanner } from "@/app/providers";

function displayName(symbol: string) {
  const m = symbol.match(/^SYN0*(\d+)$/);
  return m ? `Synthetic Co ${m[1]} (demo)` : symbol;
}

function HoldingsInner() {
  const { fund } = useFundCtx();
  const [h, setH] = useState<HoldingsView | null>(null);
  const [err, setErr] = useState<string | null>(null);
  useEffect(() => {
    if (!fund) return;
    getHoldings(fund).then(setH).catch(
      (e) => setErr(`${e.error} — ${e.hint}`));
  }, [fund]);
  return (
    <Shell>
      <ApiErrorBanner />
      <h1 className="text-xl font-semibold mb-1">Holdings</h1>
      <p className="text-xs mb-4" style={{ color: "var(--text-muted)" }}>
        every number from the ledger and stored snapshots — no estimates
      </p>
      {err && <div className="nd-badge-neg">{err}</div>}
      {!h ? (
        <div className="nd-card p-6 animate-pulse text-sm">Loading…</div>
      ) : h.rows.length === 0 ? (
        <div className="nd-card p-4 text-sm">no holdings recorded</div>
      ) : (
        <>
          <div className="nd-card overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr style={{ color: "var(--text-muted)" }}>
                  {["Name", "Ticker", "Qty", "Avg cost", "Last price",
                    "Value", "Unrealised P&L", "Weight"].map((c) => (
                    <th key={c} className="text-left px-3 py-2">{c}</th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {h.rows.map((r) => (
                  <tr key={r.symbol} className="border-t"
                    style={{ borderColor: "var(--border-card)" }}>
                    <td className="px-3 py-2">{displayName(r.symbol)} *</td>
                    <td className="px-3 py-2">{r.symbol}</td>
                    <td className="px-3 py-2">
                      {r.quantity.toLocaleString()}</td>
                    <td className="px-3 py-2">
                      {r.avg_cost ? fmtMoney(r.avg_cost) : "—"}</td>
                    <td className="px-3 py-2">{fmtMoney(r.last_close)}</td>
                    <td className="px-3 py-2">{fmtMoney(r.value)}</td>
                    <td className="px-3 py-2">
                      {r.pnl_amount === null
                        ? "n/a (no avg cost recorded)"
                        : <span className={r.pnl_amount >= 0
                          ? "nd-badge-pos" : "nd-badge-neg"}>
                          {r.pnl_amount >= 0 ? "▲ up" : "▼ down"}{" "}
                          {fmtMoney(r.pnl_amount)} ({fmtPct(r.pnl_pct)})
                        </span>}
                    </td>
                    <td className="px-3 py-2">
                      <div className="w-24 h-2 rounded-full inline-block align-middle"
                        style={{ background: "var(--border-card)" }}>
                        <div className="h-full rounded-full"
                          style={{ width: `${r.weight_pct ?? 0}%`,
                                   background: "var(--accent)" }} />
                      </div>{" "}
                      {(r.weight_pct ?? 0).toFixed(1)}%
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          <div className="text-xs mt-2"
            style={{ color: "var(--text-muted)" }}>
            * synthetic demo data · Total value: {fmtMoney(h.total_value)} ·
            as-of: {h.as_of}
          </div>
        </>
      )}
    </Shell>
  );
}

function fmtPct(v: number | null | undefined) {
  return v === null || v === undefined ? "—" : `${v >= 0 ? "+" : ""}${v.toFixed(2)}%`;
}

export default function HoldingsPage() {
  return <HoldingsInner />;
}
