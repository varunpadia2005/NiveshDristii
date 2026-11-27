"use client";

// Fund-selection context + API reachability state (P20-WEB S2; hardened
// in WEB-FIX-1: a failed funds fetch surfaces an error banner with a
// Retry button instead of a permanent spinner).

import { createContext, useContext, useEffect, useState } from "react";
import { listFunds } from "@/lib/api";

const Ctx = createContext<{ fund: string | null;
                            setFund: (f: string) => void;
                            funds: string[]; apiError: string | null;
                            retry: () => void }>(
  { fund: null, setFund: () => {}, funds: [], apiError: null,
    retry: () => {} });

export function FundProvider({ children }: { children: React.ReactNode }) {
  const [funds, setFunds] = useState<string[]>([]);
  const [fund, setFundState] = useState<string | null>(null);
  const [apiError, setApiError] = useState<string | null>(null);
  const [reloadTick, setReloadTick] = useState(0);
  useEffect(() => {
    let attempt = 0;
    let timer: ReturnType<typeof setTimeout> | undefined;
    const load = () => {
      attempt += 1;
      listFunds().then((d) => {
        setFunds(d.funds);
        setApiError(null);
        const saved = localStorage.getItem("nd-fund");
        setFundState(saved && d.funds.includes(saved)
          ? saved : (d.funds[0] ?? null));
      }).catch((e: unknown) => {
        // the loopback API may still be starting up; retry, then surface
        // the error state - a failed request must NEVER leave a
        // permanent spinner (WEB-FIX-1).
        if (attempt < 3) {
          timer = setTimeout(load, 2500);
        } else {
          setFunds([]);
          const msg = e instanceof Error ? e.message : String(e);
          setApiError(
            "API not reachable (" + msg + "). Start it with: "
            + "python -m niveshdristi.webapi --fund-base <dir> --port 8000");
        }
      });
    };
    load();
    return () => { if (timer) clearTimeout(timer); };
  }, [reloadTick]);
  return (
    <Ctx.Provider value={{
      fund,
      setFund: (f) => {
        localStorage.setItem("nd-fund", f);
        setFundState(f);
      },
      funds,
      apiError,
      retry: () => {
        setApiError(null);
        setReloadTick((t) => t + 1);
      },
    }}>
      {children}
    </Ctx.Provider>
  );
}

export function useFundCtx() { return useContext(Ctx); }

export function ApiErrorBanner() {
  const { apiError, retry } = useFundCtx();
  if (!apiError) return null;
  return (
    <div className="rounded-xl p-3 mb-3 text-sm"
      style={{ background: "var(--neg-bg)", color: "var(--neg)",
               border:
                 "1px solid color-mix(in srgb, var(--neg) 30%, transparent)" }}>
      {apiError}
      <button onClick={retry}
        className="ml-3 rounded-lg px-3 py-1 text-sm"
        style={{ border: "1px solid var(--border-card)",
                 color: "var(--text-primary)" }}>
        Retry
      </button>
    </div>
  );
}
