"use client";

// P20-WEB S3c: Stock detail route — name + tags, price chart with range
// pills, per-model signal cards with conviction bars, position info,
// orders for the symbol. Honest labels only.

import { useParams } from "next/navigation";
import { useEffect, useMemo, useState } from "react";
import { Line } from "react-chartjs-2";
import {
  CategoryScale, Chart as ChartJS, LinearScale, LineElement, PointElement,
  Tooltip,
} from "chart.js";
import { getDeepDive, getOverview, DeepDive, FundOverview } from "@/lib/api";
import { useFundCtx } from "@/app/providers";
import { Shell } from "@/components/shell";
import { ApiErrorBanner } from "@/app/providers";

ChartJS.register(CategoryScale, LinearScale, PointElement, LineElement,
                 Tooltip);

function displayName(symbol: string, realName?: string | null) {
  const m = symbol.match(/^SYN0*(\d+)$/);
  if (m) return `Synthetic Co ${m[1]} (demo)`;
  return realName || symbol;
}

export default function StockPage() {
  const params = useParams<{ symbol: string }>();
  const symbol = decodeURIComponent(String(params.symbol));
  const { fund } = useFundCtx();
  const [dd, setDd] = useState<DeepDive | null>(null);
  const [ov, setOv] = useState<FundOverview | null>(null);
  const [err, setErr] = useState<string | null>(null);
  const [range, setRange] = useState("All");
  useEffect(() => {
    if (!fund || !symbol) return;
    getDeepDive(fund, symbol).then(setDd).catch(
      (e) => setErr(`${e.error} — ${e.hint}`));
    getOverview(fund).then(setOv).catch(() => setOv(null));
  }, [fund, symbol]);

  const candles = useMemo(() => {
    // deep_dive returns candles as a polars frame; the API serialises it
    // via default=str, so the web side renders only what arrived as a
    // table-shaped payload. If unavailable, show the honest empty state.
    const c = dd?.candles as { columns?: string[]; rows?: unknown[][] } |
      string | undefined;
    if (c && typeof c === "object" && Array.isArray((c as { rows?: unknown[] }).rows)) {
      return (c as { rows: unknown[][] }).rows;
    }
    return null;
  }, [dd]);

  return (
    <Shell>
      <ApiErrorBanner />
      <h1 className="text-xl font-semibold mb-1">
        Stock detail: {displayName(symbol)}
      </h1>
      <p className="text-xs mb-2" style={{ color: "var(--text-muted)" }}>
        ticker: {symbol}
      </p>
      {/^SYN\d+$/.test(symbol) && (
        <span className="nd-badge-caution">synthetic demo data</span>
      )}
      {err && <div className="nd-badge-neg">{err}</div>}
      {!dd && !err ? (
        <div className="nd-card p-6 animate-pulse text-sm">Loading…</div>
      ) : (
        dd && (
          <>
            <div className="nd-card p-4 mt-3">
              <div className="flex gap-2 items-center mb-2">
                {["All", "Last 10", "Last 30"].map((r) => (
                  <button key={r} onClick={() => setRange(r)}
                    className="rounded-full px-3 py-1 text-sm"
                    style={{
                      border: range === r ? "1px solid var(--accent)"
                        : "1px solid var(--border-card)",
                      color: range === r ? "var(--accent)"
                        : "var(--text-secondary)",
                    }}>{r}</button>
                ))}
              </div>
              {candles ? (
                <StockChart candles={candles} range={range} />
              ) : (
                <div className="text-sm" style={{ color: "var(--text-muted)" }}>
                  no stored price data for this symbol in this fund
                </div>
              )}
            </div>

            <div className="nd-card p-4 mt-4 text-sm">
              {ov?.positions.some(
                (p) => p.instrument.symbol === symbol)
                ? <span className="nd-badge-pos">held in this fund</span>
                : <span style={{ color: "var(--text-muted)" }}>
                    not held in this fund
                  </span>}
            </div>

            <h2 className="text-lg font-semibold mt-6 mb-2">
              Per-model signals
            </h2>
            <div className="grid gap-3 md:grid-cols-2">
              {(dd.per_model ?? []).map((m) => (
                <div key={m.model_id} className="nd-card p-4">
                  <div className="font-medium">{m.model_id}</div>
                  <div className="text-xs" style={{
                    color: "var(--text-muted)" }}>{m.label}</div>
                  {m.conviction !== null && m.conviction !== undefined && (
                    <div className="mt-2">
                      <div className="h-2 rounded-full overflow-hidden"
                        style={{ background: "var(--border-card)" }}>
                        <div className="h-full"
                          style={{
                            width: `${Math.min(100,
                              Math.abs(m.conviction) * 100)}%`,
                            background: "var(--accent)",
                          }} />
                      </div>
                      <div className="text-xs mt-1">
                        conviction (uncalibrated): {m.conviction >= 0 ? "+" : ""}
                        {Number(m.conviction).toFixed(2)}
                      </div>
                    </div>
                  )}
                  <details className="text-xs mt-2">
                    <summary className="cursor-pointer">Why?</summary>
                    <span>{m.thesis}</span>
                  </details>
                </div>
              ))}
            </div>

            <div className="text-xs mt-4"
              style={{ color: "var(--text-muted)" }}>
              {dd.banner} {dd.disclaimer}
            </div>
          </>
        )
      )}
    </Shell>
  );
}

function StockChart({ candles, range }: {
  candles: unknown[][]; range: string }) {
  const pts = range === "Last 10" ? candles.slice(-10)
    : range === "Last 30" ? candles.slice(-30) : candles;
  const dates = pts.map((r) => String(r[0]));
  const closes = pts.map((r) => Number(r[1]));
  return (
    <Line
      data={{
        labels: dates,
        datasets: [{ data: closes, borderColor: "#0e9488", pointRadius: 0 }],
      }}
      options={{
        responsive: true,
        plugins: { legend: { display: false } },
        scales: { x: { ticks: { maxTicksLimit: 8 } } },
      }}
      height={220}
    />
  );
}
