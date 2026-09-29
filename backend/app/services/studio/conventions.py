"""Centralized Studio financial conventions.

Single source of truth for annualization, return conventions, trading calendar,
timezone, and benchmark defaults referenced by metrics and router validation.
"""

from __future__ import annotations

from datetime import timezone

# Annualization
PERIODS_PER_YEAR: int = 252
TRADING_DAYS_PER_YEAR: int = 252

# Risk
ANNUAL_RISK_FREE_RATE: float = 0.0

# Time and data
STUDIO_TIMEZONE = timezone.utc
STUDIO_TIMEZONE_NAME: str = "UTC"
SUPPORTED_CURRENCIES: tuple[str, ...] = ("USD",)
DEFAULT_CURRENCY: str = "USD"
DEFAULT_BENCHMARK: str = "SPY"
TRADING_CALENDAR: str = "XNYS"

# Numerical thresholds
MIN_EQUITY_OBSERVATIONS: int = 2
MIN_RETURNS_FOR_MONTE_CARLO: int = 20
MIN_RETURNS_FOR_WALK_FORWARD: int = 100

# Execution limits
MAX_SLIPPAGE_BPS: float = 50.0
MAX_COMMISSION_PCT: float = 1.0
MAX_SIMULATIONS: int = 10000
MAX_WALK_FORWARD_FOLDS: int = 20
MAX_RETURN_OBSERVATIONS: int = 100000
MAX_LOOKBACK_YEARS: int = 30

# Execution limits are owned by execution.py; conventions only document them here.
