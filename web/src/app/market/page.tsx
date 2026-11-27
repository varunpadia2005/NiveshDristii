"use client";

// P20-WEB S3f: Market Overview — honest unavailable panels.
import { useEffect, useState } from "react";
import { getOverview } from "@/lib/api";
import { useFundCtx } from "@/app/providers";
import { Shell } from "@/components/shell";
import { ApiErrorBanner } from "@/app/providers";

const PANELS = ["benchmark index", "bank index", "volatility index",
                "sector heatmap", "institutional flows",
                "regime state (needs aux frames not in snapshots)"];

function MarketInner() {
  const { fund } = useFundCtx();
  const [ov, setOv] = useState<Awaited<ReturnType<typeof getOverview>> | null>(
    null);
  const [err, setErr] = useState<string | null>(null);
  useEffect(() => {
    if (!fund) return;
    getOverview(fund).then(setOv).catch(
      (e) => setErr(`${e.error} — ${e.hint}`));
  }, [fund]);
  return (
    <Shell>
      <ApiErrorBanner />
      <h1 className="text-xl font-semibold mb-1">Market Overview</h1>
      {err && <div className="nd-badge-neg">{err}</div>}
      {!ov ? (
        <div className="nd-card p-6 animate-pulse text-sm">Loading…</div>
      ) : (
        <>
          {ov.banner && <div className="nd-badge-caution !block rounded-xl p-3 mb-3 text-sm">{ov.banner}</div>}
          <div className="nd-card p-4 text-sm mb-4">
            Last data session: {ov.as_of}
          </div>
          {PANELS.map((p) => (
            <div key={p} className="nd-card p-3 text-sm mb-2">
              {p} — unavailable: no verified data source
            </div>
          ))}
          <div className="text-xs mt-2" style={{ color: "var(--text-muted)" }}>
            as-of: {ov.as_of} · {ov.market_labels.market_name}
          </div>
        </>
      )}
    </Shell>
  );
}

export default function MarketPage() {
  return <MarketInner />;
}
