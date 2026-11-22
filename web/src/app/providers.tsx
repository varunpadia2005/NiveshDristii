"use client";

// Fund-selection context so the Shell and pages share one selection.
import { createContext, useContext, useEffect, useState } from "react";
import { listFunds } from "@/lib/api";

const Ctx = createContext<{ fund: string | null; setFund: (f: string) => void;
                            funds: string[] }>(
  { fund: null, setFund: () => {}, funds: [] });

export function FundProvider({ children }: { children: React.ReactNode }) {
  const [funds, setFunds] = useState<string[]>([]);
  const [fund, setFundState] = useState<string | null>(null);
  useEffect(() => {
    listFunds().then((d) => {
      setFunds(d.funds);
      const saved = localStorage.getItem("nd-fund");
      setFundState(saved && d.funds.includes(saved)
        ? saved : (d.funds[0] ?? null));
    }).catch(() => setFunds([]));
  }, []);
  return (
    <Ctx.Provider value={{
      fund,
      setFund: (f) => {
        localStorage.setItem("nd-fund", f);
        setFundState(f);
      },
      funds,
    }}>
      {children}
    </Ctx.Provider>
  );
}

export function useFundCtx() { return useContext(Ctx); }
