"use client";

// P20-WEB S3b: Explore / Watchlist — pill filters, card grid with
// honest tags. Open uses the Stock Detail route.
import { useEffect, useMemo, useState } from "react";
import Link from "next/link";
import { getOverview, getWatchlist, fmtMoney, Watchlist } from "@/lib/api";
import { useFundCtx } from "@/app/providers";
import { Shell } from "@/components/shell";

function displayName(symbol: string) {
  const m = symbol.match(/^SYN0*(\d+)$/);
  return m ? `Synthetic Co ${m[1]} (demo)` : symbol;
}
function isSynthetic(symbol: string) { return /^SYN\d+$/.test(symbol); }

function WatchlistInner() {
  const { fund } = useFundCtx();
  const [wl, setWl] = useState<Watchlist | null>(null);
  const [err, setErr] = useState<string | null>(null);
  const [held, setHeld] = useState<Set<string>>(new Set());
  const [query, setQuery] = useState("");
  const [pill, setPill] = useState("All");
  useEffect(() => {
    if (!fund) return;
    getWatchlist(fund).then(setWl).catch(
      (e) => setErr(`${e.error} — ${e.hint}`));
    getOverview(fund).then(
      (o) => setHeld(new Set(o.positions.map(
        (p) => p.instrument.symbol)))).catch(() => setHeld(new Set()));
  }, [fund]);
  const rows = useMemo(() => {
    let rs = wl?.rows ?? [];
    if (query) rs = rs.filter(
      (r) => r.symbol.toUpperCase().includes(query.toUpperCase())
        || displayName(r.symbol).toUpperCase()
          .includes(query.toUpperCase()));
    if (pill === "Held") rs = rs.filter((r) => held.has(r.symbol));
    if (pill === "Gainers") rs = rs.filter((r) => (r.change ?? 0) > 0);
    if (pill === "Losers") rs = rs.filter((r) => (r.change ?? 0) < 0);
    return rs;
  }, [wl, query, pill, held]);

  return (
    <Shell>
      <h1 className="text-xl font-semibold mb-1">Explore / Watchlist</h1>
      <p className="text-xs mb-4" style={{ color: "var(--text-muted)" }}>
        every symbol the fund tracks — last close and change only where the
        fund has stored snapshot data
      </p>
      {err && <div className="nd-badge-neg">{err}</div>}
      {!wl ? (
        <div className="nd-card p-6 animate-pulse text-sm">Loading…</div>
      ) : (
        <>
          <div className="flex gap-2 items-center mb-4 flex-wrap">
            <input aria-label="search watchlist" placeholder="name or ticker"
              value={query} onChange={(e) => setQuery(e.target.value)}
              className="rounded-lg px-3 py-1.5 text-sm"
              style={{ background: "var(--bg-primary)",
                       color: "var(--text-primary)",
                       border: "1px solid var(--border-card)" }} />
            {["All", "Held", "Gainers", "Losers"].map((p) => (
              <button key={p} onClick={() => setPill(p)}
                className="rounded-full px-3 py-1 text-sm"
                style={{
                  border: pill === p ? "1px solid var(--accent)"
                    : "1px solid var(--border-card)",
                  color: pill === p ? "var(--accent)"
                    : "var(--text-secondary)",
                }}>{p}</button>
            ))}
          </div>
          {wl.rows.length === 0 ? (
            <div className="nd-card p-4 text-sm">
              this fund tracks no symbols — Next: generate a demo fund with
              tools/make_demo_fund.py
            </div>
          ) : rows.length === 0 ? (
            <div className="nd-card p-4 text-sm">
              no symbol matches “{query || pill}” — Next: clear the filter
            </div>
          ) : (
            <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-3">
              {rows.map((r) => {
                const dir = r.change === null ? "flat"
                  : r.change > 0 ? "gainers" : "losers";
                return (
                  <div key={r.symbol} className="nd-card p-4">
                    <div className="font-medium">
                      {displayName(r.symbol)}
                    </div>
                    <div className="text-xs mb-2"
                      style={{ color: "var(--text-muted)" }}>
                      {r.symbol}
                    </div>
                    <span className="nd-badge-caution">
                      {isSynthetic(r.symbol) ? "synthetic demo data"
                        : "no verified name source"}
                    </span>
                    <div className="mt-2">
                      <span className="text-lg font-semibold">
                        {r.has_data ? fmtMoney(r.last_close) : "—"}
                      </span>
                      <span className={`ml-2 ${dir === "gainers"
                        ? "nd-badge-pos" : dir === "losers"
                        ? "nd-badge-neg" : "nd-badge-caution"}`}>
                        {r.change === null ? "no change data"
                          : `${r.change >= 0 ? "▲" : "▼"} ${dir}`}
                      </span>
                    </div>
                    {!r.has_data && (
                      <div className="text-xs mt-2"
                        style={{ color: "var(--text-muted)" }}>
                        no stored data for this fund yet
                      </div>
                    )}
                    <Link href={`/stock/${encodeURIComponent(r.symbol)}`}
                      className="inline-block mt-3 text-sm rounded-lg px-3 py-1"
                      style={{ border: "1px solid var(--border-card)",
                               color: "var(--accent)" }}>
                      Open
                    </Link>
                  </div>
                );
              })}
            </div>
          )}
        </>
      )}
    </Shell>
  );
}

export default function WatchlistPage() {
  return <WatchlistInner />;
}
