"""Stock universe definitions and trading calendar."""
from datetime import date, timedelta
from typing import List, Dict
import pandas as pd


# Nifty 50 (as of 2024)
NIFTY50 = [
    "RELIANCE", "TCS", "HDFCBANK", "ICICIBANK", "INFY",
    "HINDUNILVR", "ITC", "SBIN", "BHARTIARTL", "KOTAKBANK",
    "LT", "BAJFINANCE", "ASIANPAINT", "MARUTI", "SUNPHARMA",
    "TITAN", "ULTRACEMCO", "NESTLEIND", "POWERGRID", "NTPC",
    "ONGC", "COALINDIA", "BAJAJFINSV", "ADANIENT", "ADANIPORTS",
    "JSWSTEEL", "TATASTEEL", "HINDALCO", "INDUSINDBK", "AXISBANK",
    "WIPRO", "TECHM", "HCLTECH", "DRREDDY", "CIPLA",
    "APOLLOHOSP", "DIVISLAB", "BPCL", "IOC", "GRASIM",
    "SBILIFE", "HDFCLIFE", "BRITANNIA", "TATACONSUM", "EICHERMOT",
    "HEROMOTOCO", "BAJAJ-AUTO", "M&M", "TATAMOTORS", "MARUTI"
]


# Sector mapping (simplified)
SECTOR_MAP = {
    "RELIANCE": "Energy", "TCS": "IT", "HDFCBANK": "Banking",
    "ICICIBANK": "Banking", "INFY": "IT", "HINDUNILVR": "FMCG",
    "ITC": "FMCG", "SBIN": "Banking", "BHARTIARTL": "Telecom",
    "KOTAKBANK": "Banking", "LT": "Infrastructure", "BAJFINANCE": "NBFC",
    "ASIANPAINT": "Consumer", "MARUTI": "Auto", "SUNPHARMA": "Pharma",
    "TITAN": "Consumer", "ULTRACEMCO": "Cement", "NESTLEIND": "FMCG",
    "POWERGRID": "Power", "NTPC": "Power",
}


def get_universe(name: str) -> List[str]:
    """Get tickers for a named universe."""
    universes = {
        "nifty50": NIFTY50,
        "default": NIFTY50[:10],  # Smaller default for quick testing
    }
    return universes.get(name, NIFTY50[:10])


def get_sector(ticker: str) -> str:
    return SECTOR_MAP.get(ticker, "Unknown")


# --- Trading Calendar ---

# NSE Holidays 2024 (major ones)
NSE_HOLIDAYS_2024 = [
    date(2024, 1, 26),   # Republic Day
    date(2024, 3, 8),    # Holi
    date(2024, 3, 29),   # Good Friday
    date(2024, 4, 11),   # Eid-ul-Fitr
    date(2024, 4, 17),   # Ram Navami
    date(2024, 5, 1),    # Maharashtra Day
    date(2024, 6, 17),   # Bakri Eid
    date(2024, 7, 17),   # Muharram
    date(2024, 8, 15),   # Independence Day
    date(2024, 10, 2),   # Gandhi Jayanti
    date(2024, 11, 1),   # Diwali
    date(2024, 11, 15),  # Guru Nanak Jayanti
    date(2024, 12, 25),  # Christmas
]


def is_trading_day(d: date) -> bool:
    """Check if date is a trading day (weekday + not holiday)."""
    if d.weekday() >= 5:  # Sat=5, Sun=6
        return False
    if d in NSE_HOLIDAYS_2024:
        return False
    return True


def previous_trading_day(d: date) -> date:
    """Get previous trading day."""
    d = d - timedelta(days=1)
    while not is_trading_day(d):
        d = d - timedelta(days=1)
    return d


def next_trading_day(d: date) -> date:
    """Get next trading day."""
    d = d + timedelta(days=1)
    while not is_trading_day(d):
        d = d + timedelta(days=1)
    return d