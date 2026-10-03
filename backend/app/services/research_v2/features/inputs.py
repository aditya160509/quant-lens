"""Input and output declarations shared by the Research V2 feature files.

Each feature publishes ``INPUTS`` (rendered as the study form) and ``OUTPUTS``
(rendered as result cards) through ``registry.feature_manifest()``. The
frontend builds its form and layout from this manifest, so the contract lives
in one place.
"""

from __future__ import annotations

from typing import Any

from ..core.panel import CONTROL_SETS, DEPENDENT_VARIABLES, SIGNALS, UNIVERSE_FILTERS


def field(key: str, label: str, type_: str, default: Any, group: str, options: list[Any] | None = None, help_: str = "", **extra: Any) -> dict[str, Any]:
    out = {"key": key, "label": label, "type": type_, "default": default, "group": group, "help": help_}
    if options is not None:
        out["options"] = options
    out.update(extra)
    return out


def output(key: str, title: str, source: str, render: str, description: str = "", primary: bool = False) -> dict[str, Any]:
    return {"key": key, "title": title, "source": source, "render": render, "description": description, "primary": primary}


SIGNAL_HELP = "Price signals use prices up to the formation date. Fundamental signals (size, value, quality, profitability, investment, leverage) use point-in-time reports with a 90-day filing lag and exist from 2021 onward."

UNIVERSE = [
    field("universe", "Universe", "ticker_list", "us_equities", "Universe", help_="'us_equities' (default) or a comma-separated ticker list. Unknown tickers are rejected."),
    field("max_symbols", "Universe size", "number", 400, "Universe", min=30, max=2000, help_="Largest-coverage names first."),
    field("universe_filters", "Universe filters", "multiselect", [], "Universe", UNIVERSE_FILTERS, "Size filters use point-in-time market-cap terciles."),
    field("lookback_days", "Lookback (calendar days)", "number", 3650, "Universe", min=730, max=11000, help_="Length of the formation window in calendar days, counted back from the latest data date (1825 = 5 years, 3650 = 10 years). Earlier history, up to twice this length, is loaded only to warm up signals such as 12-month momentum. Local data starts in 2016, so values above about 3650 add nothing."),
]

SIGNAL = [
    field("signal", "Signal", "select", "momentum", "Signal", SIGNALS, SIGNAL_HELP),
    field("signal_csv_path", "Custom signal upload", "file", "", "Signal", help_="CSV or Parquet with date, ticker and signal (or rank) columns. Overrides the signal menu."),
    field("signal_transform", "Signal transform", "select", "raw", "Signal", ["raw", "winsorize", "rank", "zscore", "decile"]),
]

SPEC = [
    field("dependent_variable", "Dependent variable", "select", "forward_return", "Specification", DEPENDENT_VARIABLES, "Measured over the holding period after each formation date."),
    field("forward_months", "Holding period (months)", "select", 1, "Specification", [1, 3, 6, 12]),
    field("rebalancing_frequency", "Rebalancing", "select", "monthly", "Specification", ["monthly", "quarterly", "annual"]),
    field("controls", "Controls", "select", "none", "Specification", list(CONTROL_SETS)),
    field("weighting", "Portfolio weighting", "select", "equal", "Specification", ["equal", "value", "rank"]),
]

BASE = UNIVERSE + SIGNAL + SPEC
