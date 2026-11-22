"use client";

// P20-WEB S3e: Orders — Fills/Pending tabs, symbol/side filters.
import { useEffect, useState } from "react";
import { getOrders, fmtMoney, OrdersView } from "@/lib/api";
import { useFundCtx } from "@/app/providers";
import { Shell } from "@/components/shell";

function displayName(symbol: string) {
  const m = symbol.match(/^SYN0*(\d+)$/);
  return m ? `Synthetic Co ${m[1]} (demo)` : symbol;
}

function OrdersInner() {
  const { fund } = useFundCtx();
  const [o, setO] = useState<OrdersView | null>(null);
  const [err, setErr] = useState<string | null>(null);
  const [tab, setTab] = useState("Fills");
  const [sym, setSym] = useState("(all)");
  const [side, setSide] = useState("(all)");
  useEffect(() => {
    if (!fund) return;
    getOrders(fund).then(setO).catch((e) => setErr(`${e.error} — ${e.hint}`));
  }, [fund]);
  const fills = (o?.fills ?? []).filter(
    (f) => (sym === "(all)" || f.symbol === sym)
      && (side === "(all)" || f.side.toUpperCase() === side.toUpperCase()));
  const weights = o?.pending_gated?.weights ?? {};
  return (
    <Shell>
      <h1 className="text-xl font-semibold mb-1">Orders / Activity</h1>
      <p className="text-xs mb-4" style={{ color: "var(--text-muted)" }}>
        fills and pending gated orders from the ledger and broker cache —
        nothing estimated
      </p>
      {err && <div className="nd-badge-neg">{err}</div>}
      {!o ? (
        <div className="nd-card p-6 animate-pulse text-sm">Loading…</div>
      ) : (
        <>
          <div className="flex gap-2 mb-4">
            {["Fills", "Pending"].map((t) => (
              <button key={t} onClick={() => setTab(t)}
                className="rounded-full px-4 py-1 text-sm"
                style={{
                  border: tab === t ? "1px solid var(--accent)"
                    : "1px solid var(--border-card)",
                  color: tab === t ? "var(--accent)"
                    : "var(--text-secondary)",
                }}>{t}</button>
            ))}
          </div>
          {tab === "Fills" ? (
            <>
              <div className="flex gap-2 mb-3 flex-wrap">
                <select aria-label="filter symbol" value={sym}
                  onChange={(e) => setSym(e.target.value)}
                  className="rounded-lg px-2 py-1 text-sm"
                  style={{ background: "var(--bg-card)",
                           color: "var(--text-primary)",
                           border: "1px solid var(--border-card)" }}>
                  {["(all)",
                    ...new Set((o?.fills ?? []).map((f) => f.symbol))]
                    .map((s) => <option key={s}>{s}</option>)}
                </select>
                <select aria-label="filter side" value={side}
                  onChange={(e) => setSide(e.target.value)}
                  className="rounded-lg px-2 py-1 text-sm"
                  style={{ background: "var(--bg-card)",
                           color: "var(--text-primary)",
                           border: "1px solid var(--border-card)" }}>
                  {["(all)", "BUY", "SELL"].map((s) =>
                    <option key={s}>{s}</option>)}
                </select>
                <span className="text-xs self-center"
                  style={{ color: "var(--text-muted)" }}>
                  {fills.length} of {o?.fills.length ?? 0} fill(s)
                </span>
              </div>
              {fills.length === 0 ? (
                <div className="nd-card p-4 text-sm">
                  no fills match this filter — Next: clear the filters or run
                  <code> nd paper tick</code>
                </div>
              ) : (
                <div className="nd-card overflow-x-auto">
                  <table className="w-full text-sm">
                    <thead>
                      <tr style={{ color: "var(--text-muted)" }}>
                        {["Name", "Ticker", "Side", "Qty", "Price",
                          "Costs", "Session"].map((c) => (
                          <th key={c} className="text-left px-3 py-2">
                            {c}</th>
                        ))}
                      </tr>
                    </thead>
                    <tbody>
                      {fills.map((f, i) => (
                        <tr key={i} className="border-t"
                          style={{ borderColor: "var(--border-card)" }}>
                          <td className="px-3 py-2">
                            {displayName(f.symbol)} *</td>
                          <td className="px-3 py-2">{f.symbol}</td>
                          <td className="px-3 py-2">
                            <span className={f.side === "buy"
                              ? "nd-badge-pos" : "nd-badge-neg"}>
                              {f.side.toUpperCase()}</span></td>
                          <td className="px-3 py-2">
                            {(f.quantity ?? 0).toLocaleString()}</td>
                          <td className="px-3 py-2">
                            {fmtMoney(f.price)}</td>
                          <td className="px-3 py-2">
                            {f.fees !== null || f.slippage !== null
                              ? `fees ${fmtMoney(f.fees)}, slippage ${fmtMoney(f.slippage)}`
                              : "costs not modeled"}</td>
                          <td className="px-3 py-2">{f.session_date}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              )}
              <div className="text-xs mt-2"
                style={{ color: "var(--text-muted)" }}>
                * synthetic demo data
              </div>
            </>
          ) : (
            <div className="nd-card p-4 text-sm">
              {Object.keys(weights).length === 0
                ? "no pending gated orders"
                : Object.entries(weights).map(([s, w]) => (
                  <div key={s}>
                    {displayName(s)} ({s}) — target weight {w.toFixed(2)} —
                    pending gate review
                  </div>
                ))}
              {(o?.pending_gated?.log ?? []).map((g, i) => (
                <div key={i} className="text-xs mt-1"
                  style={{ color: "var(--text-muted)" }}>
                  gate {String(g.gate)}: {String(g.outcome)} (
                  {String(g.reason)})
                </div>
              ))}
            </div>
          )}
        </>
      )}
    </Shell>
  );
}

export default function OrdersPage() {
  return <OrdersInner />;
}
