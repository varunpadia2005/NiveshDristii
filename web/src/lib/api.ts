// P20-WEB S2: typed API client. The API is GET-only, loopback-only
// (src/niveshdristi/webapi). Errors arrive as {error, hint}.

export class ApiError extends Error {
  hint: string;
  status: number;
  error: string;
  constructor(status: number, error: string, hint: string) {
    super(error);
    this.error = error;
    this.hint = hint;
    this.status = status;
  }
}

async function getJson<T>(path: string): Promise<T> {
  const resp = await fetch(`/api/${path}`, { cache: "no-store" });
  const body = await resp.json();
  if (!resp.ok) {
    throw new ApiError(resp.status, body.error ?? "unknown error",
                       body.hint ?? "");
  }
  return body as T;
}

export interface FundOverview {
  fund_id: string;
  as_of: string;
  market_labels: { market_id: string; market_name: string;
                   currency_code: string; timezone: string };
  banner: string | null;
  rates_banner: string | null;
  disclaimer: string;
  records: number;
  cash: number;
  positions: Array<{ instrument: { symbol: string; exchange: string;
                                   market_id: string; currency: string },
                     avg_cost: number }>;
  verify: string;
  halted: boolean;
  halt_reason: string | null;
  limitation_codes: string[];
  kpis: { fund_value: string; net_pnl_session: string;
          gross_pnl_session: string; net_pnl_value: number } | null;
  positions_view: Array<{ symbol: string; quantity: number;
                          avg_cost: number; last_close: number | null;
                          unrealised_pct: number | null }>;
  decisions: Record<string, unknown>;
  change_feed: Array<{ event: string; detail: string }>;
  needs_attention: string[];
  fund_base?: string;
}

export interface NavPoint { session: string; equity: number }
export interface NavSeries { series: NavPoint[] }

export interface WatchRow {
  symbol: string; has_data: boolean;
  last_close: number | null; prev_close: number | null;
  change: number | null; closes: number[];
}
export interface Watchlist { as_of: string | null; rows: WatchRow[] }

export interface HoldingsView {
  as_of: string | null;
  rows: Array<{ symbol: string; quantity: number; avg_cost: number | null;
                last_close: number | null; value: number | null;
                pnl_amount: number | null; pnl_pct: number | null;
                weight_pct: number | null }>;
  total_value: number | null;
}

export interface OrdersView {
  fills: Array<{ symbol: string; side: string; quantity: number | null;
                 price: number | null; session_date: string;
                 fees: number | null; slippage: number | null;
                 commission: number | null }>;
  pending_gated: { log?: Array<Record<string, unknown>>;
                   weights?: Record<string, number> };
}

export interface DeepDive {
  symbol: string;
  banner: string | null; rates_banner: string | null; disclaimer: string;
  candles?: unknown;
  per_model: Array<{ model_id: string; label: string; thesis: string;
                     conviction?: number | null }>;
  zones_evidence_only?: unknown;
  gate_log?: Array<Record<string, unknown>>;
}

export function listFunds(): Promise<{ funds: string[] }> {
  return getJson("funds");
}
export function getOverview(fund: string): Promise<FundOverview> {
  return getJson(`overview?fund=${encodeURIComponent(fund)}`);
}
export function getNav(fund: string): Promise<NavSeries> {
  return getJson(`nav?fund=${encodeURIComponent(fund)}`);
}
export function getWatchlist(fund: string): Promise<Watchlist> {
  return getJson(`watchlist?fund=${encodeURIComponent(fund)}`);
}
export function getHoldings(fund: string): Promise<HoldingsView> {
  return getJson(`holdings?fund=${encodeURIComponent(fund)}`);
}
export function getOrders(fund: string): Promise<OrdersView> {
  return getJson(`orders?fund=${encodeURIComponent(fund)}`);
}
export function getDeepDive(fund: string, symbol: string):
    Promise<DeepDive> {
  return getJson(`deepdive?fund=${encodeURIComponent(fund)}` +
                 `&symbol=${encodeURIComponent(symbol)}`);
}
export function getSettings():
    Promise<{ market_labels: { market_name: string; market_id: string;
                               currency_code: string } }> {
  return getJson("settings");
}
export function fmtMoney(v: number | null | undefined,
                          code = ""): string {
  if (v === null || v === undefined) return "—";
  const s = v.toLocaleString(undefined,
                             { minimumFractionDigits: 2,
                               maximumFractionDigits: 2 });
  return code ? `${s} ${code}` : s;
}
export function fmtPct(v: number | null | undefined): string {
  return v === null || v === undefined ? "—" : `${v >= 0 ? "+" : ""}${v.toFixed(2)}%`;
}
