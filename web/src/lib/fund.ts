"use client";

// Selected fund, persisted in localStorage; shared by every page.
import { useEffect, useState } from "react";
import { listFunds } from "@/lib/api";

export function useFund(): string | null {
  const [fund, setFund] = useState<string | null>(null);
  useEffect(() => {
    const saved = localStorage.getItem("nd-fund");
    if (saved) { setFund(saved); return; }
    listFunds().then((d) => {
      if (d.funds.length) {
        localStorage.setItem("nd-fund", d.funds[0]);
        setFund(d.funds[0]);
      }
    }).catch(() => setFund(null));
  }, []);
  return fund;
}

export function setFund(f: string) {
  localStorage.setItem("nd-fund", f);
  window.dispatchEvent(new Event("nd-fund-changed"));
}

export function useFundList(): string[] {
  const [funds, setFunds] = useState<string[]>([]);
  useEffect(() => {
    listFunds().then((d) => setFunds(d.funds)).catch(() => setFunds([]));
  }, []);
  return funds;
}

export function useFundChanged(fund: string | null, cb: () => void) {
  useEffect(() => {
    const h = () => cb();
    window.addEventListener("nd-fund-changed", h);
    return () => window.removeEventListener("nd-fund-changed", h);
  }, [fund, cb]);
}
