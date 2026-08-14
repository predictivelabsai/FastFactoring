"""Single money formatter with an admin-controlled display currency.

Stored demo amounts are UZS-scale and are converted through fixed illustrative
rates for display. Source invoice currencies remain unchanged.
"""

from __future__ import annotations

from time import monotonic

from utils.config import settings

AVAILABLE_CURRENCIES = ("USD", "EUR", "GBP")
SUPPORTED_CURRENCIES = AVAILABLE_CURRENCIES  # compatibility for the existing Admin route
_FX_UZS_PER = {"USD": 12600.0, "EUR": 13700.0, "GBP": 16000.0}
_SYMBOL = {"USD": "$", "EUR": "€", "GBP": "£"}
_currency_cache: tuple[float, str] | None = None


def display_currency(*, refresh: bool = False) -> str:
    """Return the persisted display currency, falling back to configuration."""
    global _currency_cache
    now = monotonic()
    if not refresh and _currency_cache and now - _currency_cache[0] < 5:
        return _currency_cache[1]
    configured = (settings().display_currency or "USD").upper()
    result = configured if configured in AVAILABLE_CURRENCIES else "USD"
    try:
        from db import fetch_one
        row = fetch_one(
            "SELECT value FROM factorio.platform_settings WHERE key='display_currency'"
        )
        candidate = str((row or {}).get("value") or "").upper()
        if candidate in AVAILABLE_CURRENCIES:
            result = candidate
    except Exception:
        pass
    _currency_cache = (now, result)
    return result


def set_display_currency(currency: str) -> str:
    """Persist EUR, GBP, or USD as the application-wide display currency."""
    global _currency_cache
    selected = (currency or "").upper()
    if selected not in AVAILABLE_CURRENCIES:
        raise ValueError("currency must be one of EUR, GBP, USD")
    from db import execute
    execute(
        """INSERT INTO factorio.platform_settings (key, value, updated_at)
           VALUES ('display_currency', %s, now())
           ON CONFLICT (key) DO UPDATE
           SET value=EXCLUDED.value, updated_at=now()""",
        (selected,),
    )
    _currency_cache = (monotonic(), selected)
    return selected


def convert_amount(amount_uzs, currency: str | None = None) -> tuple[float, str]:
    """Convert a stored synthetic amount and return ``(value, currency_code)``."""
    cur = (currency or display_currency()).upper()
    if cur not in AVAILABLE_CURRENCIES:
        cur = display_currency()
    try:
        value = float(amount_uzs or 0) / _FX_UZS_PER[cur]
    except (TypeError, ValueError):
        value = 0.0
    return value, cur


def fmt_money(amount_uzs, currency: str | None = None) -> str:
    """Format a UZS-scale stored amount in the selected display currency."""
    value, cur = convert_amount(amount_uzs, currency)
    return f"{_SYMBOL[cur]}{value:,.0f}"
