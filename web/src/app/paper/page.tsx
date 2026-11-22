"use client";

// P20-WEB S3f: Paper Fund - records/cash/verify/halt state (read-only).
import { useEffect, useState } from "react";
import { getOverview } from "@/lib/api";
import { useFundCtx } from "@/app/providers";
import { Shell } from "@/components/shell";

function PaperInner() {
  const { fund } = useFundCtx();
  const [ov, setOv] = useState<Awaited<ReturnType<typeof getOverview>> | null>(
    null);
  const [err, setErr] = useState<string | null>(null);
  useEffect(() => {
    if (!fund) return;
    getOverview(fund).then(setOv).catch(
      (e) => setErr(`${e.error} - ${e.hint}`));
  }, [fund]);
  return (
    <Shell>
      <h1 className="text-xl font-semibold mb-1">Paper Fund</h1>
      {err && <div className="nd-badge-neg">{err}</div>}
      {!ov ? (
        <div className="nd-card p-6 animate-pulse text-sm">Loading...</div>
      ) : (
        <>
          {ov.banner && (
            <div className="nd-badge-caution !block rounded-xl p-3 mb-3 text-sm">
              {ov.banner}
            </div>
          )}
          {ov.rates_banner && (
            <div className="nd-badge-neg !block rounded-xl p-3 mb-3 text-sm">
              {ov.rates_banner}
            </div>
          )}
          <div className="grid gap-4 md:grid-cols-3">
            <div className="nd-card p-4">
              <div className="text-xs" style={{ color: "var(--text-muted)" }}>
                records
              </div>
              <div className="text-2xl">{ov.records}</div>
            </div>
            <div className="nd-card p-4">
              <div className="text-xs" style={{ color: "var(--text-muted)" }}>
                cash
              </div>
              <div className="text-2xl">{ov.cash}</div>
            </div>
            <div className="nd-card p-4">
              <div className="text-xs" style={{ color: "var(--text-muted)" }}>
                ledger verify
              </div>
              <div className={ov.verify === "verified"
                ? "nd-badge-pos" : "nd-badge-neg"}>
                {ov.verify}
              </div>
            </div>
          </div>
          <div className="nd-card p-4 text-sm mt-4">
            halt/kill-switch state:{" "}
            {ov.halted ? `HALTED - ${ov.halt_reason}` : "not halted"} - write
            actions stay in the CLI
          </div>
          <div className="text-xs mt-2" style={{ color: "var(--text-muted)" }}>
            as-of: {ov.as_of} (from the DATA, never the clock)
          </div>
        </>
      )}
    </Shell>
  );
}

export default function PaperPage() {
  return <PaperInner />;
}
