"use client";

// P20-WEB S3g: Settings / About — provenance and page guide.
import { useEffect, useState } from "react";
import { getOverview } from "@/lib/api";
import { useFundCtx } from "@/app/providers";
import { Shell } from "@/components/shell";

const GUIDE = [
  ["Overview", "fund value, P&L, NAV line, kill-switch state, banners"],
  ["Explore",
   "every symbol the fund tracks; last close/change where data exists"],
  ["Stock Detail",
   "price chart, per-model signals with data_status, position"],
  ["Holdings", "quantities, avg cost, value, unrealised P&L, weights"],
  ["Orders",
   "fills with costs and pending gated orders; US shows COSTS NOT MODELED"],
  ["Backtest", "recorded engine runs; pipeline demonstration only"],
];

function SettingsInner() {
  const { fund } = useFundCtx();
  const [ov, setOv] = useState<Awaited<ReturnType<typeof getOverview>> | null>(
    null);
  useEffect(() => {
    if (!fund) return;
    getOverview(fund).then(setOv).catch(() => setOv(null));
  }, [fund]);
  return (
    <Shell>
      <h1 className="text-xl font-semibold mb-1">Settings / About</h1>
      {ov?.banner && (
        <div className="nd-badge-caution !block rounded-xl p-3 mb-3 text-sm">
          {ov.banner}
        </div>
      )}
      {ov?.rates_banner && (
        <div className="nd-badge-neg !block rounded-xl p-3 mb-3 text-sm">
          {ov.rates_banner}
        </div>
      )}
      <div className="nd-card p-4 text-sm mt-3">
        <h2 className="font-semibold mb-2">About this data</h2>
        Every number comes from the fund&apos;s own ledger, decision
        sidecars and stored snapshot frames. Nothing is fetched live;
        nothing is estimated. The API is GET-only and loopback-only.
      </div>
      <div className="nd-card p-4 text-sm mt-3">
        <h2 className="font-semibold mb-2">Synthetic demo funds</h2>
        Synthetic tickers display as &quot;Synthetic Co NNN (demo)&quot;
        with a visible synthetic tag — they are not real companies. Real
        company names require a verified ticker-to-name source file.
      </div>
      <div className="nd-card p-4 text-sm mt-3">
        <h2 className="font-semibold mb-2">How to read each page</h2>
        {GUIDE.map(([page, what]) => (
          <div key={page} className="py-1">
            <b>{page}</b> — {what}
          </div>
        ))}
      </div>
    </Shell>
  );
}

export default function SettingsPage() {
  return <SettingsInner />;
}
