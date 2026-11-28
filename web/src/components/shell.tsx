"use client";

// P20-WEB S2: app shell — sticky navbar with logo/name, global search,
// tab nav with icons, theme toggle, market chip, status pills, DATA
// LIMITATIONS popover, fund selector, footer disclaimer. Data via the
// GET-only API; honesty wording is never dropped.

import Link from "next/link";
import { usePathname } from "next/navigation";
import { useEffect, useState } from "react";
import {
  Activity, ArrowLeftRight, BarChart3, Globe2, LayoutDashboard,
  ListChecks, Moon, Search, Settings, Sparkles, Sun, Wallet,
} from "lucide-react";
import {
  ApiError, getOverview, searchNames, type FundOverview,
  type NameHit,
} from "@/lib/api";
import { useFundCtx } from "@/app/providers";

const TABS = [
  { href: "/", label: "Dashboard", icon: LayoutDashboard },
  { href: "/watchlist", label: "Explore", icon: Search },
  { href: "/holdings", label: "Holdings", icon: Wallet },
  { href: "/orders", label: "Orders", icon: ArrowLeftRight },
  { href: "/market", label: "Market", icon: Globe2 },
  { href: "/signals", label: "Signals", icon: Sparkles },
  { href: "/backtest", label: "Backtest", icon: BarChart3 },
  { href: "/paper", label: "Paper Fund", icon: ListChecks },
  { href: "/settings", label: "Settings", icon: Settings },
];

function useOverview(fund: string | null) {
  const [ov, setOv] = useState<FundOverview | null>(null);
  const [err, setErr] = useState<ApiError | null>(null);
  useEffect(() => {
    if (!fund) return;
    getOverview(fund).then(setOv).catch((e) => {
      setOv(null);
      setErr(e instanceof ApiError ? e : new ApiError(0, String(e), ""));
    });
  }, [fund]);
  return { ov, err };
}

export function ThemeToggle() {
  const [dark, setDark] = useState(false);
  useEffect(() => {
    setDark(document.documentElement.classList.contains("dark"));
  }, []);
  return (
    <button
      aria-label="toggle theme"
      className="p-2 rounded-full border"
      style={{ borderColor: "var(--border-card)",
               color: "var(--text-secondary)" }}
      onClick={() => {
        const next = !dark;
        document.documentElement.classList.toggle("dark", next);
        localStorage.setItem("nd-theme", next ? "dark" : "light");
        setDark(next);
      }}
    >
      {dark ? <Sun size={16} /> : <Moon size={16} />}
    </button>
  );
}

export function useThemeInit() {
  useEffect(() => {
    const saved = localStorage.getItem("nd-theme");
    if (saved === "dark") document.documentElement.classList.add("dark");
  }, []);
}

export function FundSelector() {
  const { fund, setFund, funds } = useFundCtx();
  return (
    <select aria-label="select fund"
      className="rounded-lg px-2 py-1 text-sm"
      style={{ background: "var(--bg-card)",
               color: "var(--text-primary)",
               border: "1px solid var(--border-card)" }}
      value={fund ?? ""} onChange={(e) => setFund(e.target.value)}>
      {funds.map((f) => <option key={f} value={f}>{f}</option>)}
    </select>
  );
}

export function Shell({ children }: { children: React.ReactNode }) {
  useThemeInit();
  const pathname = usePathname();
  const { fund, setFund, funds } = useFundCtx();
  const { ov, err } = useOverview(fund);
  useEffect(() => {
    if (!fund && funds.length) setFund(funds[0]);
  }, [funds, fund, setFund]);
  const [query, setQuery] = useState("");
  const [hits, setHits] = useState<NameHit[] | null>(null);
  useEffect(() => {
    if (!query.trim()) { setHits(null); return; }
    const controller = new AbortController();
    const t = setTimeout(() => {
      searchNames(query.trim(), 20).then((d) => {
        if (!controller.signal.aborted) setHits(d.results);
      }).catch(() => setHits(null));
    }, 200);
    return () => { clearTimeout(t); controller.abort(); };
  }, [query]);

  return (
    <div className="min-h-screen flex flex-col">
      <nav className="sticky top-0 z-20 border-b px-4 py-3"
        style={{ background: "var(--bg-card)",
                 borderColor: "var(--border-card)" }}>
        <div className="max-w-6xl mx-auto flex items-center gap-3 flex-wrap">
          <span className="font-bold text-lg">NiveshDristi</span>
          <span className="nd-badge-caution">educational tool</span>
          <div className="relative ml-auto">
            <Search size={14} className="absolute left-2 top-2 opacity-60" />
            <input aria-label="global search" placeholder="search symbols"
              value={query}
              onChange={(e) => setQuery(e.target.value)}
              className="rounded-lg pl-7 pr-2 py-1.5 text-sm w-44"
              style={{ background: "var(--bg-primary)",
                       color: "var(--text-primary)",
                       border: "1px solid var(--border-card)" }} />
            {query && hits && hits.length > 0 && (
              <div className="absolute mt-1 w-72 rounded-xl border p-2 z-30"
                style={{ background: "var(--bg-card)",
                         borderColor: "var(--border-card)" }}>
                {hits.map((h) => (
                  <Link key={h.ticker}
                    href={`/stock/${encodeURIComponent(h.ticker)}`}
                    className="flex items-center justify-between gap-2 px-2 py-1 text-sm hover:opacity-70">
                    <span>{h.name}</span>
                    <span className="rounded px-1 text-xs font-mono"
                      style={{ background: "var(--bg-primary)",
                               color: "var(--text-secondary)" }}>
                      {h.ticker}
                    </span>
                    {h.exchange && (
                      <span className="text-xs"
                        style={{ color: "var(--text-muted)" }}>
                        {h.exchange}
                      </span>
                    )}
                  </Link>
                ))}
              </div>
            )}
          </div>
          <FundSelector />
          <ThemeToggle />
        </div>
        <div className="max-w-6xl mx-auto flex items-center gap-2 mt-2 flex-wrap text-xs">
          {TABS.map((t) => (
            <Link key={t.href} href={t.href}
              className="flex items-center gap-1 rounded-full px-3 py-1"
              style={{
                color: pathname === t.href
                  ? "var(--accent)" : "var(--text-secondary)",
                border: pathname === t.href
                  ? "1px solid var(--accent)"
                  : "1px solid var(--border-card)",
              }}>
              <t.icon size={13} /> {t.label}
            </Link>
          ))}
        </div>
        {ov && (
          <div className="max-w-6xl mx-auto flex gap-2 mt-2 flex-wrap text-xs">
            <span className="nd-badge-caution">{ov.market_labels.market_name}
              ({ov.market_labels.currency_code})</span>
            <span className={ov.halted ? "nd-badge-neg" : "nd-badge-pos"}>
              {ov.halted ? "HALTED" : "kill-switch: not halted"}
            </span>
            <span className="nd-badge-pos">ledger verify: {ov.verify}</span>
            {(ov.limitation_codes ?? []).length > 0 && (
              <details className="nd-badge-caution">
                <summary className="cursor-pointer">DATA LIMITATIONS</summary>
                <span>{(ov.limitation_codes ?? []).join(", ")}</span>
              </details>
            )}
          </div>
        )}
        {err && <div className="mt-2 nd-badge-neg">{err.error} — {err.hint}</div>}
      </nav>
      <main className="max-w-6xl w-full mx-auto p-4 flex-1">{children}</main>
      <footer className="max-w-6xl mx-auto w-full p-4 text-xs"
        style={{ color: "var(--text-muted)" }}>
        NiveshDristi is an educational research tool. It is NOT investment
        advice. All numbers come from the fund&apos;s own ledger and stored
        snapshots; results are pipeline demonstrations only, not evidence of
        performance.
      </footer>
    </div>
  );
}

export function StatusIcon() {
  return <Activity size={12} />;
}
