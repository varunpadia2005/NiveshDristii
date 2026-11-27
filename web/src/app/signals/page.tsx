"use client";

// P20-WEB S3f: Signals board (lean, conviction, data_status).
import { useEffect, useState } from "react";
import { getOverview } from "@/lib/api";
import { useFundCtx } from "@/app/providers";
import { Shell } from "@/components/shell";
import { ApiErrorBanner } from "@/app/providers";

function SignalsInner() {
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
      <h1 className="text-xl font-semibold mb-1">Signals</h1>
      <p className="text-xs mb-4" style={{ color: "var(--text-muted)" }}>
        leans and uncalibrated convictions over stored instruments; stub
        models are labelled stub
      </p>
      {err && <div className="nd-badge-neg">{err}</div>}
      {!ov ? (
        <div className="nd-card p-6 animate-pulse text-sm">Loading…</div>
      ) : (
        <div className="nd-card p-4 text-sm">
          {Object.keys(ov.decisions).length === 0
            && ov.positions_view.length === 0
            ? "no signals recorded yet"
            : ov.positions_view.map((p) => (
              <div key={p.symbol} className="border-b py-2 last:border-0"
                style={{ borderColor: "var(--border-card)" }}>
                {p.symbol} — see Stock Detail for per-model leans and
                evidence
              </div>
            ))}
          <div className="text-xs mt-2" style={{ color: "var(--text-muted)" }}>
            stub_models_used is part of the fund&apos;s limitation codes —
            never presented as live output
          </div>
        </div>
      )}
    </Shell>
  );
}

export default function SignalsPage() {
  return <SignalsInner />;
}
