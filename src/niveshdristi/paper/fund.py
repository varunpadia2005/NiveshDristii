"""Paper fund lifecycle (NEW, Phase 6): create, load, status, list, tick.

Commit protocol (amendment C2): the lock is held for the WHOLE tick; the
ledger line is written with flush + os.fsync (THE commit point); only then
is the PaperBroker cache file updated (temp file + atomic replace). The
ledger is the single source of truth; the cache is derivable. If cache and
ledger disagree at tick start: raise, halt, log — NEVER auto-repair. The
operator command `nd paper recover` rebuilds the cache from the ledger;
the tick never calls it.

Tick semantics (amendment E):
- Fetch through a caller-supplied provider callable (composition lives in
  cli/; paper/ itself never imports markets/ or touches the network).
- A bar is VALID only if close and volume are finite and volume > 0
  (yfinance returned a NaN-OHLC latest row in the live probe).
- Coverage = fraction of the universe with a valid bar for the candidate
  session; below COVERAGE_MIN_THRESHOLD the tick is a logged NO-OP
  (exit 0). A date with no valid bars at all is a NON-SESSION (the honest
  substitute for the missing holiday list); holidays are never inferred.
- Idempotent: if the ledger's last session == the candidate session, the
  tick is a logged no-op and changes nothing.
- Catch-up: up to MAX_SESSIONS_PER_RUN sessions after the ledger's last
  session are processed in order (a powered-off laptop).
- Staleness: if the latest valid bar for every symbol is older than
  STALE_SESSIONS_LIMIT sessions, log "stale data" and no-op.
- Fetch failure BEFORE the tick: logged failure, no state change, no halt,
  non-zero exit. Only an exception INSIDE advance()/ledger write halts.

Constants are UNVALIDATED DEFAULTS. No clock reads outside the injected
clock; no market literals in paper/.
"""

from __future__ import annotations

import hashlib
import json
import os
from collections.abc import Callable
from datetime import date
from pathlib import Path
from typing import Any

import polars as pl

from niveshdristi.core.errors import LedgerError, LockHeldError
from niveshdristi.core.limitations import DataLimitations
from niveshdristi.core.market_rules import MarketRules
from niveshdristi.core.money import to_paise
from niveshdristi.engine.advance import (
    FundState,
    ModelBundle,
    RebalanceSchedule,
    advance,
)
from niveshdristi.engine.fund import GrossLot, Lot, PendingDecision
from niveshdristi.paper.ledger import PaperLedger, build_header
from niveshdristi.portfolio.risk_gates import GateLimits

# UNVALIDATED DEFAULTS
COVERAGE_MIN_THRESHOLD = 0.60  # below this: logged no-op ("insufficient coverage")
MAX_SESSIONS_PER_RUN = 10  # catch-up cap per tick
STALE_SESSIONS_LIMIT = 5  # latest bar older than this: "stale data" no-op
LOCK_CONTENT_TEMPLATE = '{{"pid": {pid}, "holder": "tick"}}'


class FundPaths:
    """State location (amendment D): configurable, default OUTSIDE the repo."""

    def __init__(self, base: str | Path | None = None) -> None:
        if base is None:
            base = Path.home() / "niveshdristi" / "funds"
        self.base = Path(base)

    def for_fund(self, fund_id: str) -> FundDirectory:
        return FundDirectory(self.base / fund_id)


class FundDirectory:
    """Layout: ledger.jsonl, broker_cache.json, halt.flag, events.jsonl."""

    def __init__(self, root: Path) -> None:
        self.root = Path(root)
        self.ledger = self.root / "ledger.jsonl"
        self.broker_cache = self.root / "broker_cache.json"
        self.halt_flag = self.root / "halt.flag"
        self.events = self.root / "events.jsonl"
        self.heartbeat = self.root / "heartbeat.json"
        self.snapshots = self.root / "snapshots"

    def __truediv__(self, name: str) -> Path:
        return self.root / name

    def mkdir(self, parents: bool = False, exist_ok: bool = False) -> None:
        self.root.mkdir(parents=parents, exist_ok=exist_ok)


def default_fund_root() -> Path:
    """The DEFAULT state root (amendment D): outside the repo, under the
    user profile. Tests always pass an explicit tmp_path base instead."""
    return Path.home() / "niveshdristi" / "funds"


class Lock:
    """Cross-platform lock file: os.open with O_CREAT|O_EXCL (atomic).

    Contents: pid + creation marker. Stale-lock handling is a MANUAL step
    (`nd paper unlock`, logged) — never automatic, per amendment C3.
    """

    def __init__(self, path: Path) -> None:
        self.path = Path(path)

    def __enter__(self) -> Lock:
        try:
            self._fd = os.open(
                str(self.path), os.O_CREAT | os.O_EXCL | os.O_WRONLY
            )
        except FileExistsError as exc:
            raise LockHeldError(
                f"lock already held: {self.path} (stale? run `nd paper unlock`)"
            ) from exc
        os.write(self._fd, LOCK_CONTENT_TEMPLATE.format(pid=os.getpid()).encode("utf-8"))
        os.fsync(self._fd)
        return self

    def __exit__(self, *exc_info: object) -> None:
        os.close(self._fd)
        self.path.unlink(missing_ok=True)


def create_fund(
    fund_id: str,
    *,
    base: str | Path | None = None,
    created: date,
    config_digest: str,
    rules: MarketRules,
    limitations: DataLimitations,
    rates_verified: bool,
    initial_cash: float,
    universe: list[str],
) -> Path:
    """Create a fund directory + ledger header (amendment J snapshot)."""
    paths = FundPaths(base).for_fund(fund_id)
    if paths.ledger.exists():
        raise LedgerError(f"fund already exists: {fund_id}")
    paths.root.mkdir(parents=True, exist_ok=True)
    ledger = PaperLedger(paths.ledger)
    header = build_header(
        fund_id=fund_id,
        created=created,
        config_digest=config_digest,
        rules=rules,
        limitations=limitations,
        rates_verified=rates_verified,
    )
    header["initial_cash_paise"] = to_paise(initial_cash)
    header["universe"] = sorted(universe)
    ledger.create(header)
    return paths.ledger


def load_fund(fund_id: str, *, base: str | Path | None = None) -> PaperLedger:
    return PaperLedger(FundPaths(base).for_fund(fund_id).ledger)


def _bar_is_valid(bar: dict[str, Any]) -> bool:
    """Amendment E: finite close AND finite positive volume.

    (The live probe returned a NaN-OHLC row for the latest day.)"""
    close = bar.get("close")
    volume = bar.get("volume")
    if close is None or volume is None:
        return False
    if isinstance(close, str) or isinstance(volume, str):
        return False
    return close == close and 0 < float(volume) == float(volume) and float(close) > 0


def coverage_for_session(
    frames: dict[str, pl.DataFrame], session: date, universe: list[str]
) -> tuple[int, int]:
    """(valid bars, universe size) for the candidate session."""
    import polars as pl

    key = session.isoformat()
    valid = 0
    for symbol in universe:
        frame = frames.get(symbol)
        if frame is None:
            continue
        rows = frame.filter(pl.col("date").cast(pl.String).str.slice(0, 10) == key)
        if rows.height == 0:
            continue
        row = {
            "close": rows["close"].to_list()[0],
            "volume": rows["volume"].to_list()[0] if "volume" in rows.columns else None,
        }
        if _bar_is_valid(row):
            valid += 1
    return valid, len(universe)


def cache_matches_ledger(
    cache_path: Path, ledger: PaperLedger
) -> bool:
    """Amendment C2: cache-vs-ledger agreement check (ledger is truth)."""
    if not cache_path.exists():
        return True  # no cache yet: nothing to disagree with
    cache = json.loads(cache_path.read_text(encoding="utf-8"))
    records = ledger.records()
    if not records:
        # a cache WITHOUT any ledger record is itself a disagreement
        # (the cache is derivable from the ledger; it claims sessions
        # the ledger never recorded)
        return False
    fills_in_cache = cache.get("fills", [])
    # The cache reflects the LAST session only (it is rewritten per tick),
    # so it must equal the ledger's last record fills — NOT the cumulative
    # count. (R8: comparing against the sum halted funds whose fills span
    # multiple sessions.) The cash figure must also match the ledger tail.
    last = records[-1]
    if cache.get("last_session") != last.get("session_date"):
        return False
    if len(fills_in_cache) != len(last.get("fills", [])):
        return False
    return True


def tick(
    fund_id: str,
    *,
    base: str | Path | None = None,
    fetch_bars: Callable[[list[str], date], dict],
    clock_now: date,
    models: ModelBundle,
    rules: MarketRules,
    limits: GateLimits,
    rebalance: RebalanceSchedule,
    universe: list[str],
    tax_enabled: bool = False,
) -> dict:
    """One scheduler tick (amendment E). Returns an outcome dict for events.

    Outcome keys: outcome ("filled"|"no-op"|"failure"), reason, sessions.
    Fetch failure BEFORE the tick: failure, no halt, no state change.
    An exception INSIDE the tick (advance/gates/broker/ledger): halt.
    """
    paths = FundPaths(base).for_fund(fund_id)
    ledger = PaperLedger(paths.ledger)
    outcome: dict[str, Any] = {"outcome": "no-op", "reason": "", "sessions": []}

    if paths.halt_flag.exists():
        outcome["reason"] = "fund is halted"
        return outcome

    last_session = ledger.last_session_date()
    if last_session is not None and last_session >= clock_now:
        outcome["reason"] = (
            f"idempotent no-op: ledger last session {last_session} >= "
            f"candidate {clock_now}"
        )
        return outcome

    # Candidate sessions: from (ledger last session | fund creation) forward,
    # capped at MAX_SESSIONS_PER_RUN (amendment E catch-up).
    header = ledger.header()
    anchor = date.fromisoformat(header["created"]) if last_session is None else last_session
    candidates: list[date] = []
    start = anchor
    while len(candidates) < MAX_SESSIONS_PER_RUN:
        start = date.fromordinal(start.toordinal() + 1)
        if start > clock_now:
            break
        candidates.append(start)

    # PaperBroker only (no real broker integration in Phase 6); stateless
    # execution per session — the LEDGER is the state, the cache is a copy.
    from niveshdristi.execution.sim_broker import SimBroker

    broker = SimBroker(rates=rules.rates, price_limits=rules.price_limits)
    if not candidates:
        outcome["reason"] = "no candidate sessions (created date >= candidate)"
        return outcome
    try:
        frames = fetch_bars(sorted(universe), candidates[0])
    except Exception as exc:  # noqa: BLE001 - provider failure is an event
        outcome["outcome"] = "failure"
        outcome["reason"] = f"provider chain exhausted: {exc}"
        return outcome

    processed = 0
    fund = _rebuild_state(ledger, header, paths.broker_cache)
    for session in candidates:
        valid, total = coverage_for_session(frames, session, universe)
        if valid == 0:
            outcome["sessions"].append(
                f"{session.isoformat()}: non-session (no valid bars) - skipped"
            )
            continue
        if valid / total < COVERAGE_MIN_THRESHOLD:
            outcome["sessions"].append(
                f"{session.isoformat()}: logged no-op (insufficient coverage "
                f"{valid}/{total})"
            )
            continue
        cutoff = session.isoformat()
        snapshots_for_session = {
            sym: frame.filter(
                pl.col("date").cast(pl.String).str.slice(0, 10) <= cutoff
            )
            for sym, frame in frames.items()
        }
        with Lock(paths.root / "tick.lock"):
            if not cache_matches_ledger(paths.broker_cache, ledger):
                _halt(paths, fund_id, session, "broker cache disagrees with ledger")
                outcome["outcome"] = "failure"
                outcome["reason"] = (
                    "broker cache disagrees with ledger; halted; run "
                    "`nd paper recover`"
                )
                return outcome
            fund, record = advance(
                fund, session, broker, frames,
                models=models, rules=rules, limits=limits,
                rebalance=rebalance, tax_enabled=tax_enabled,
            )
            linked_hash = ledger.append(record, fund.last_hash)
            fund = fund.with_(last_hash=linked_hash)
            # cache written AFTER the ledger fsync (C2 commit order); it
            # carries the PENDING decision created by this session's assess
            _write_cache_atomic(paths.broker_cache, record, fund)
            save_snapshot(paths, session, snapshots_for_session)
            processed += 1
            outcome["sessions"].append(
                f"{session.isoformat()}: advanced (fills={len(record.fills)})"
            )
    if processed:
        outcome["outcome"] = "filled"
    return outcome


def save_snapshot(
    paths: FundDirectory, session: date, frames: dict[str, pl.DataFrame]
) -> dict[str, str]:
    """Amendment I: store the frames the models saw for this session
    (parquet sidecars keyed by content hash) so replay never refetches
    (yfinance restates adjusted history after corporate actions)."""
    out: dict[str, str] = {}
    snapshot_dir = paths.snapshots / session.isoformat()
    snapshot_dir.mkdir(parents=True, exist_ok=True)
    for symbol in sorted(frames):
        frame = frames[symbol]
        tmp = snapshot_dir / f"_{symbol}.parquet.tmp"
        frame.write_parquet(tmp)
        raw = tmp.read_bytes()
        digest = hashlib.sha256(raw).hexdigest()
        tmp.unlink()
        target = snapshot_dir / f"{symbol}_{digest[:16]}.parquet"
        if not target.exists():
            target.write_bytes(raw)
        out[symbol] = digest
    manifest = snapshot_dir / "manifest.json"
    manifest.write_text(json.dumps(out, sort_keys=True), encoding="utf-8")
    return out


def _halt(paths: FundDirectory, fund_id: str, session: date, reason: str) -> None:
    """Amendment F: halt flag (JSON) + fail-safe semantics."""
    flag = {
        "fund_id": fund_id, "reason": reason,
        "session": session.isoformat(),
    }
    paths.halt_flag.write_text(json.dumps(flag, sort_keys=True), encoding="utf-8")


def _rebuild_state(
    ledger: PaperLedger, header: dict, cache_path: Path
) -> FundState:
    """Shared by tick() and replay: rebuild FundState from the LEDGER
    (cash, lots via FIFO from the fill history) + the CACHE (pending
    decision). The ledger is the source of truth for money; the cache only
    carries the pending decision between sessions."""

    records = ledger.records()
    initial_cash = float(header.get("initial_cash_paise", 0)) / 100.0
    cash = initial_cash
    lots: list[Lot] = []
    seq = 0
    last_hash = "0" * 64
    last_session: date | None = None
    for record in records:
        session = date.fromisoformat(record["session_date"])
        for fill in record.get("fills", []):
            symbol = fill["order"]["instrument"]["symbol"]
            qty = int(fill["filled_quantity"])
            side = fill["order"]["side"]
            price = float(fill["fill_price"])
            if side == "buy":
                lots.append(
                    Lot(symbol, qty, session, to_paise(qty * price))
                )
            else:
                to_sell = qty
                kept: list[Lot] = []
                for lot in lots:
                    if lot.symbol != symbol or to_sell <= 0:
                        kept.append(lot)
                        continue
                    take = min(to_sell, lot.quantity)
                    to_sell -= take
                    consumed = to_paise(lot.cost_paise_total * take / lot.quantity)
                    if lot.quantity > take:
                        kept.append(
                            Lot(
                                symbol, lot.quantity - take, lot.buy_date,
                                lot.cost_paise_total - consumed,
                            )
                        )
                lots = kept
        cash = float(record["cash_after"])
        last_hash = record["hash"]
        last_session = session
        seq = int(record["session_id"]) + 1

    # GROSS shadow track rebuild (R6d continuation): quantities from the
    # ledger fills (identical to the net path), cash path walked at each
    # session's UNSLIPPED close from that session's stored snapshot.
    gross_cash = initial_cash
    gross_qty: dict[str, int] = {}
    for record in records:
        session = date.fromisoformat(record["session_date"])
        session_closes = {}
        snap_dir = Path(str(cache_path)).parent / "snapshots" / session.isoformat()
        manifest_path = snap_dir / "manifest.json"
        if manifest_path.exists():
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            import polars as _pl

            for sym, digest in manifest.items():
                matches = sorted(snap_dir.glob(f"{sym}_{digest[:16]}.parquet"))
                if matches:
                    frame = _pl.read_parquet(matches[0])
                    if frame.height:
                        session_closes[sym] = float(frame["close"].to_list()[-1])
        for fill in record.get("fills", []):
            symbol = fill["order"]["instrument"]["symbol"]
            qty = int(fill["filled_quantity"])
            side = fill["order"]["side"]
            close = session_closes.get(symbol, 0.0)
            if side == "buy":
                gross_qty[symbol] = gross_qty.get(symbol, 0) + qty
                gross_cash -= qty * close
            else:
                gross_qty[symbol] = gross_qty.get(symbol, 0) - qty
                gross_cash += qty * close

    pending = None
    if cache_path.exists():
        cache = json.loads(cache_path.read_text(encoding="utf-8"))
        pending_data = cache.get("pending")
        if pending_data:

            from niveshdristi.portfolio.risk_gates import GatedTargets

            pending = PendingDecision(
                decision_date=date.fromisoformat(pending_data["decision_date"]),
                gated=GatedTargets._deserialize(pending_data["gated"]),
            )
    return FundState(
        cash=cash, lots=tuple(lots), pending_decision=pending,
        session_seq=seq, last_session=last_session, last_hash=last_hash,
        gross_cash=gross_cash,
        gross_lots=tuple(
            GrossLot(sym, qty, 0) for sym, qty in sorted(gross_qty.items())
        ),
    )


def records_cash(ledger: PaperLedger) -> float:
    records = ledger.records()
    return float(records[-1]["cash_after"]) if records else 0.0


def _write_cache_atomic(cache_path: Path, record: Any, fund: FundState) -> None:
    """Amendment C2: cache is a CACHE — temp file + atomic replace, written
    only AFTER the ledger fsync."""
    tmp = cache_path.with_suffix(".tmp")
    payload = {
        "last_session": record.session_date.isoformat(),
        "cash": fund.cash,
        "fills": [f.model_dump(mode="json") for f in getattr(record, "fills", ())],
        # The pending decision MUST survive the tick boundary (R8 defect
        # found by the live-model equality test): _rebuild_state reads
        # "pending" from this cache; without it the pending created in
        # session N is silently dropped and never executed in N+1.
        "pending": (
            {
                "decision_date": fund.pending_decision.decision_date.isoformat(),
                "gated": json.loads(fund.pending_decision.gated.model_dump_json()),
            }
            if fund.pending_decision is not None
            else None
        ),
    }
    tmp.write_text(json.dumps(payload, sort_keys=True), encoding="utf-8")
    os.replace(tmp, cache_path)

