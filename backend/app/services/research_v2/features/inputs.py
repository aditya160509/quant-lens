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


# ---------------------------------------------------------------------------
# Input metadata served by GET /features: required, depends_on, conflicts_with,
# unit, level and citation on every input, so the frontend stops hard-coding rules.

QUICK_KEYS = {"universe", "max_symbols", "lookback_days", "signal", "signal_csv_path", "forward_months", "weighting", "identification_design", "treated_unit", "treatment_date", "event_csv_path", "discovery_date", "publication_date", "conditioning_variable", "mode", "sort_portfolios"}
EXPERT_KEYS = {"nw_lag", "se_type", "fixed_effects", "bootstrap_replications", "permutation_replications", "max_specifications", "weighting_philosophy", "kernel", "polynomial_order", "bandwidth", "rd_design", "iv_estimator", "iv_controls", "cluster", "cs_control_group", "matches_per_treated", "anticipation_months", "estimation_window", "contamination_days", "double_sort_type", "rolling_window", "conformal_alpha", "universe_filters", "signal_transform"}
UNIT_BY_KEY = {"lookback_days": "days", "forward_months": "months", "event_window_months": "months", "rolling_window": "months", "pre_period_months": "months", "post_period_months": "months", "anticipation_months": "months", "estimation_window": "days", "contamination_days": "days", "nw_lag": "months", "max_symbols": "tickers", "donor_limit": "tickers", "event_quantile": "percentile", "spread_bps": "bps", "commission_bps": "bps", "embargo_days": "days", "cutoff": "USD bn or rank", "min_price": "USD", "min_dollar_volume": "USD", "min_listing_months": "months", "conformal_alpha": "probability"}
CITATIONS = {
    "nw_lag": "Newey and West (1987)",
    "se_type": "Petersen (2009); Driscoll and Kraay (1998)",
    "sort_portfolios": "Fama and French (1993)",
    "factor_benchmark": "Fama and French (2015); Carhart (1997)",
    "double_sort_type": "Fama and French (1993)",
    "bandwidth": "Calonico, Cattaneo and Titiunik (2014)",
    "kernel": "Calonico, Cattaneo and Titiunik (2014)",
    "cs_control_group": "Callaway and Sant'Anna (2021)",
    "universe_filters": "Hou, Xue and Zhang (2020)",
    "discovery_date": "McLean and Pontiff (2016)",
    "weighting": "Hou, Xue and Zhang (2020)",
    "iv_estimator": "Stock and Yogo (2005)",
    "scm_variant": "Abadie, Diamond and Hainmueller (2010)",
    "conformal_alpha": "Chernozhukov, Wuthrich and Zhu (2021)",
    "permutation_replications": "Harvey, Liu and Zhu (2016)",
    "max_specifications": "Simonsohn, Simmons and Nelson (2020)",
}
# Fields hidden unless the design is selected (feature 07), by group.
F07_GROUP_DESIGNS = {"DiD": ["did", "all"], "Event study": ["event_study", "all"], "Regression discontinuity": ["rdd", "all"], "Instrumental variables": ["iv", "all"]}
F07_UNGROUPED = {"treatment_date": ["did", "event_study", "all"], "treated_unit": ["did", "event_study", "all"], "event_csv_path": ["did", "event_study", "all"], "outcome_variable": ["did", "all"]}
CONFLICTS = {"signal_csv_path": ["signal"], "treated_unit": ["event_csv_path"], "event_csv_path": ["treated_unit"], "donor_list": [], "instrument_csv_path": ["instrument"]}
DEPENDS_OTHER = {
    "instrument_csv_path": {"field": "instrument", "values": ["uploaded"]},
    "donor_list": {"field": "donor_pool", "values": ["user_list"]},
    "custom_split_date": {"field": "dimensions", "values": ["custom_split"]},
    "second_signal": {"field": "double_sort_type", "values": ["independent", "sequential"]},
    "publication_date": {"field": "discovery_date", "values": ["*"]},
}


def annotate(feature_id: str, inputs: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Copy of ``inputs`` with the full metadata contract applied for ``feature_id``."""

    out = []
    for item in inputs:
        key = item["key"]
        meta: dict[str, Any] = {"required": False, "depends_on": None, "conflicts_with": list(CONFLICTS.get(key, [])), "unit": UNIT_BY_KEY.get(key, ""), "level": "quick" if key in QUICK_KEYS else "expert" if key in EXPERT_KEYS else "standard"}
        if key in CITATIONS:
            meta["citation"] = CITATIONS[key]
        if key in DEPENDS_OTHER:
            meta["depends_on"] = DEPENDS_OTHER[key]
        if feature_id == "07":
            designs = F07_UNGROUPED.get(key) or F07_GROUP_DESIGNS.get(item.get("group", ""))
            if designs:
                meta["depends_on"] = {"field": "identification_design", "values": designs}
            if key in {"treated_unit", "treatment_date"}:
                meta.update(required=True, required_unless="event_csv_path")
            if key == "cutoff":
                meta["required"] = True
        if feature_id == "08" and key == "discovery_date":
            meta.update(required=True, level="quick")
        if feature_id == "09" and key in {"treated_unit", "treatment_date"}:
            meta.update(required=True, required_unless="event_csv_path", level="quick")
        if feature_id == "09" and key == "donor_pool":
            meta["level"] = "standard"
        out.append({**item, **{k: v for k, v in meta.items() if k not in item or k in {"required", "depends_on", "conflicts_with", "unit", "level"}}})
    return out
