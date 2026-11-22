"use client";

// P20-WEB S3a: Dashboard = Overview. Hero NAV card (Chart.js line),
// change chip (arrow + word), KPI tiles, positions cards, activity,
// needs-attention. Mandatory wording everywhere.

import { useEffect, useState } from "react";
import { Line } from "react-chartjs-2";
import {
  CategoryScale, Chart as ChartJS, Filler, LinearScale, LineElement,
  PointElement, Tooltip,
} from "chart.js";
import { getNav, getOverview, fmtMoney, NavSeries } from "@/lib/api";
import { useFundCtx } from "@/app/providers";
import { Shell } from "@/components/shell";

ChartJS.register(CategoryScale, LinearScale, PointElement, LineElement,
                 Filler, Tooltip);

function BannerStrip({ ov }: {
  ov: NonNullable<Awaited<ReturnType<typeof getOverview>>> }) {
  return (
    <div className="flex flex-col gap-2 mb-4">
      {ov.banner && (
        <div className="nd-badge-caution !block rounded-xl p-3 text-sm">
          {ov.banner}
        </div>
      )}
      {ov.rates_banner && (
        <div className="nd-badge-neg !block rounded-xl p-3 text-sm">
          {ov.rates_banner}
        </div>
      )}
      <div className="rounded-xl p-3 text-sm"
        style={{ background: "var(--pos-bg)",
                 border: "1px solid var(--pos-border)" }}>
        {ov.disclaimer}
      </div>
    </div>
  );
}

function DashboardInner() {
  const { fund } = useFundCtx();
  const [ov, setOv] = useState<Awaited<ReturnType<typeof getOverview>> | null>(
    null);
  const [nav, setNav] = useState<NavSeries | null>(null);
  const [err, setErr] = useState<string | null>(null);
  useEffect(() => {
    if (!fund) return;
    setErr(null);
    getOverview(fund).then(setOv).catch(
      (e) => setErr(`${e.error} — ${e.hint}`));
    getNav(fund).then(setNav).catch(() => setNav(null));
  }, [fund]);

  if (err) return <div className="nd-badge-neg">{err}</div>;
  if (!ov) {
    return (
      <div className="nd-card p-6 animate-pulse text-sm"
        style={{ color: "var(--text-muted)" }}>Loading fund…</div>
    );
  }
  const cur = ov.market_labels.currency_code;
  const kpis = ov.kpis;
  const navPts = nav?.series ?? [];
  const dayChange = navPts.length >= 2
    ? navPts[navPts.length - 1].equity - navPts[navPts.length - 2].equity
    : null;
  const startEquity = navPts.length ? navPts[0].equity : null;
  const lastEquity = navPts.length
    ? navPts[navPts.length - 1].equity : null;
  const totalPct = startEquity && lastEquity
    ? (lastEquity - startEquity) / startEquity * 100 : null;

  return (
    <div>
      <BannerStrip ov={ov} />
      <div className="grid gap-4 md:grid-cols-2">
        <div className="nd-card p-5" data-testid="hero-nav">
          <div className="text-xs" style={{ color: "var(--text-muted)" }}>
            Fund value (last close)
          </div>
          <div className="text-4xl font-bold mt-1"
            style={{ color: "var(--text-primary)" }}>
            {kpis ? kpis.fund_value : "—"}
          </div>
          {dayChange !== null && (
            <div className="mt-2">
              <span className={dayChange >= 0 ? "nd-badge-pos"
                                              : "nd-badge-neg"}>
                {dayChange >= 0 ? "▲" : "▼"} {Math.abs(dayChange).toFixed(2)}{" "}
                {dayChange >= 0 ? "up" : "down"} vs previous close
              </span>
            </div>
          )}
          {totalPct !== null && (
            <div className="text-xs mt-2"
              style={{ color: "var(--text-muted)" }}>
              Total return since start: {totalPct >= 0 ? "▲" : "▼"}{" "}
              {totalPct >= 0 ? "up" : "down"} {totalPct.toFixed(2)}% —
              pipeline demonstration only; not evidence of performance
            </div>
          )}
        </div>
        <div className="nd-card p-5">
          {navPts.length >= 2 ? (
            <Line
              data={{
                labels: navPts.map((p) => p.session),
                datasets: [{
                  data: navPts.map((p) => p.equity),
                  borderColor: "#0e9488",
                  fill: true,
                  backgroundColor: "rgba(14, 148, 136, 0.12)",
                  pointRadius: 0, tension: 0.25,
                }],
              }}
              options={{
                responsive: true,
                plugins: { legend: { display: false } },
                scales: { x: { display: false } },
              }}
              height={200}
            />
          ) : (
            <div className="text-sm" style={{ color: "var(--text-muted)" }}>
              no NAV series yet — run <code>nd paper tick</code>
            </div>
          )}
        </div>
      </div>

      <div className="grid gap-4 md:grid-cols-3 mt-4">
        {[
          ["Last-session net P&L", kpis?.net_pnl_session ?? "—",
           "gross shown separately"],
          ["Last-session gross P&L", kpis?.gross_pnl_session ?? "—",
           "before fees and slippage"],
          ["Cash", fmtMoney(ov.cash, cur),
           `ledger verify: ${ov.verify} · ${ov.records} sessions`],
        ].map(([label, value, caption]) => (
          <div key={label} className="nd-card p-4">
            <div className="text-xs" style={{ color: "var(--text-muted)" }}>
              {label}
            </div>
            <div className="text-xl font-semibold">{value}</div>
            <div className="text-xs" style={{ color: "var(--text-muted)" }}>
              {caption}
            </div>
          </div>
        ))}
      </div>

      <h2 className="text-lg font-semibold mt-6 mb-2">Positions</h2>
      {ov.positions_view.length === 0 ? (
        <div className="nd-card p-4 text-sm">
          no open positions — run <code>nd paper tick</code> or generate a
          demo fund
        </div>
      ) : (
        <div className="grid gap-3 md:grid-cols-2">
          {ov.positions_view.map((p) => (
            <div key={p.symbol} className="nd-card p-4">
              <div className="flex justify-between">
                <span className="font-medium">
                  Synthetic Co {p.symbol.replace(/^SYN0*/, "")} (demo)
                </span>
                <span className="text-xs" style={{
                  color: "var(--text-muted)" }}>{p.symbol}</span>
              </div>
              <div className="nd-badge-caution inline-block mt-1">
                synthetic demo data
              </div>
              <div className="text-sm mt-2">
                {p.quantity.toLocaleString()} @ avg{" "}
                {p.avg_cost ? fmtMoney(p.avg_cost, cur) : "n/a"}
              </div>
            </div>
          ))}
        </div>
      )}

      <h2 className="text-lg font-semibold mt-6 mb-2">
        What changed in the last session
      </h2>
      <div className="nd-card p-4 text-sm">
        {ov.change_feed.length === 0 ? "no events recorded"
          : ov.change_feed.map((e, i) => (
            <div key={i}>{e.event}: {e.detail}</div>
          ))}
      </div>

      <h2 className="text-lg font-semibold mt-6 mb-2">Needs attention</h2>
      <div className="nd-card p-4 text-sm">
        {ov.needs_attention.length === 0 ? "nothing pending"
          : ov.needs_attention.map((n, i) => <div key={i}>• {n}</div>)}
      </div>
      <div className="text-xs mt-2" style={{ color: "var(--text-muted)" }}>
        as-of: {ov.as_of} · {ov.market_labels.market_name} ·{" "}
        {ov.market_labels.currency_code}
      </div>
    </div>
  );
}

export default function DashboardPage() {
  return (
    <Shell>
      <DashboardInner />
    </Shell>
  );
}
