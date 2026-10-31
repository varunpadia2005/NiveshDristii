"""Custom exceptions for NiveshDristi."""

from __future__ import annotations


class NiveshDristiError(Exception):
    """Base exception for all NiveshDristi errors."""
    pass


class DataError(NiveshDristiError):
    """Errors related to data fetching, validation, or point-in-time violations."""
    pass


class ValidationError(NiveshDristiError):
    """Errors from input validation, schema validation, or grounding validation."""
    pass


class ExecutionError(NiveshDristiError):
    """Errors from order execution, broker communication, or fill processing."""
    pass


class ConfigurationError(NiveshDristiError):
    """Errors from invalid configuration, missing required settings, or schema violations."""
    pass


class RiskGateError(NiveshDristiError):
    """Raised when a risk gate would prevent a required action (not a clamp, a hard stop)."""
    pass


class KillSwitchError(NiveshDristiError):
    """Raised when the kill switch is active and an operation is blocked."""
    pass


class LedgerError(NiveshDristiError):
    """Errors from ledger verification, chain integrity, or replay."""
    pass


class CalendarError(NiveshDristiError):
    """Errors from trading calendar operations (holidays, session times, etc.)."""
    pass


class ProviderError(NiveshDristiError):
    """Errors from data provider failures, rate limits, or unavailable data."""
    pass


class ModelError(NiveshDristiError):
    """Errors from alpha model prediction, registration, or metadata."""
    pass


class LockHeldError(ExecutionError):
    """A concurrent process holds the paper-fund lock (Phase 6)."""
