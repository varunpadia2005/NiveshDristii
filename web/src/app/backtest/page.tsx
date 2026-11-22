"use client";

// P20-WEB S3f: Backtest Lab — the API serves the PRECOMPUTED run over
// stored snapshots (GET-only); the verdict wording is FIXED.
import { useEffect, useState } from "react";
import { getOverview } from "@/lib/api";
import { useFundCtx } from "@/app/providers";
import { Shell } from "@/components/shell";

function BacktestInner() {
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
      <h1 className="text-xl font-semibold mb-1">Backtest Lab</h1>
      <p className="text-xs mb-4" style={{ color: "var(--text-muted)" }}>
        runs the engine over the fund&apos;s STORED snapshots — no network,
        no refetch. Results are a pipeline demonstration only; not evidence
        of performance.
      </p>
      {err && <div className="nd-badge-neg">{err}</div>}
      <div className="nd-card p-4 text-sm">
        The web UI does not start engine runs. To produce the backtest
        result for this fund, run in a terminal:
        <pre className="mt-2 rounded-lg p-3 text-xs overflow-x-auto"
          style={{ background: "var(--bg-primary)",
                   border: "1px solid var(--border-card)" }}>
          nd backtest run {fund ?? "<fund-id>"}
        </pre>
        then reload this page. The verdict, drag and limitation codes come
        from that recorded run — never presented as performance.
      </div>
      {ov && (
        <div className="nd-card p-4 text-sm mt-3">
          DataLimitations: {ov.limitation_codes.join(", ")}
        </div>
      )}
    </Shell>
  );
}

export default function BacktestPage() {
  return <BacktestInner />;
}
