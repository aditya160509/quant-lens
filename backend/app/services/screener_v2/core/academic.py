"""Screener V2 academic computations."""
from __future__ import annotations

from typing import Any

import numpy as np
import pandas as pd

from .common import clean_json, number_like, records
from .data_loader import fundamental_history
from .stats import _pick, rank_pct
from .validation import point_in_time_scorer, score_backtest


def greenblatt_roic(panel: pd.DataFrame, symbols: list[str]) -> pd.Series:
    by_ticker = panel.set_index("ticker")
    def column(name):
        return pd.to_numeric(by_ticker.get(name, pd.Series(np.nan, index=by_ticker.index)), errors="coerce")
    capital = column("current_assets") - column("current_liabilities") - column("cash") + column("net_ppe")
    return (column("ebit") / capital.where(capital > 0)).reindex(symbols)


ACADEMIC_STRATEGIES = ["magic_formula", "acquirers_multiple", "value_composite", "novy_marx_gpa", "momentum_jt", "low_vol", "sloan_accruals", "graham_net_net", "high_dividend_low_payout", "interest_coverage_distress", "piotroski_f_score", "altman_z_score", "altman_z_double_prime"]


def academic_strategy_scores(panel: pd.DataFrame) -> pd.DataFrame:
    if panel.ticker.duplicated().any():
        raise ValueError("Academic strategies require one row per ticker")
    out = panel[["ticker", "sector", "industry"]].copy()
    def field(name):
        return pd.to_numeric(panel.get(name, pd.Series(np.nan, index=panel.index)), errors="coerce")
    symbols = panel.ticker.tolist()
    out["greenblatt_roic"] = greenblatt_roic(panel, symbols).to_numpy()
    out["magic_formula"] = (rank_pct(field("earnings_yield")) + rank_pct(out.greenblatt_roic)) / 2
    out["acquirers_multiple"] = rank_pct(field("ev_ebit"), higher_better=False)
    # Explicit five-ratio composite; do not call it O'Shaughnessy's VC2.
    out["value_composite"] = sum(rank_pct(field(name), higher_better=False) for name in ["trailing_pe", "pb_ratio", "ps_ratio", "p_cf", "ev_ebitda"]) / 5
    out["novy_marx_gpa"] = rank_pct(field("gpa"))
    out["momentum_jt"] = rank_pct(field("momentum_jt"))
    out["low_vol"] = rank_pct(field("realized_vol_252d"), higher_better=False)
    out["sloan_accruals"] = rank_pct(field("accruals_assets"), higher_better=False)
    ncav = field("current_assets") - field("total_liabilities")
    market_cap = field("market_cap_statement_currency")
    out["graham_net_net"] = ((2 / 3) * ncav > market_cap).astype(float).where(ncav.notna() & market_cap.notna()) * 100
    out["high_dividend_low_payout"] = (rank_pct(field("dividend_yield")) + rank_pct(field("payout_ratio"), higher_better=False)) / 2
    out["interest_coverage_distress"] = rank_pct(field("interest_coverage"), higher_better=False)
    criteria = piotroski_criteria_spec(panel, symbols)
    out = out.merge(criteria, on="ticker", how="left", validate="one_to_one")
    out["piotroski_f_score"] = out.piotroski_f_score_spec
    out["altman_z_score"] = altman_z_score(panel).to_numpy()
    out["altman_z_double_prime"] = altman_z_double_prime(panel).to_numpy()
    out["altman_status"] = pd.cut(out.altman_z_score, [-np.inf, 1.81, 2.99, np.inf], labels=["Distress", "Grey", "Safe"], right=False).astype(object)
    out["altman_piotroski_overlay"] = out.piotroski_f_score * 10 + rank_pct(out.altman_z_score) * .1
    scores = out[[name for name in ACADEMIC_STRATEGIES if name in out]].copy()
    for name in ["piotroski_f_score", "altman_z_score", "altman_z_double_prime"]:
        scores[name] = rank_pct(scores[name])
    out["best_strategy_score"] = scores.max(axis=1)
    out["best_strategy"] = scores.idxmax(axis=1).where(scores.notna().any(axis=1))
    return out.sort_values("best_strategy_score", ascending=False).reset_index(drop=True)


def piotroski_criteria_spec(panel: pd.DataFrame, symbols: list[str]) -> pd.DataFrame:
    """Original nine signals; unavailable inputs are unknown, never failed signals."""
    rows = []
    for symbol in symbols:
        hist = fundamental_history(symbol)
        if "periodType" in hist:
            hist = hist[hist.periodType.eq("annual")]
        hist = hist.sort_values("reportDate").drop_duplicates("reportDate", keep="last") if not hist.empty else hist
        def values(fields, hist=hist):
            return pd.to_numeric(_pick(hist, fields), errors="coerce")
        assets = values(["Total Assets"])
        beginning = assets.shift(1).where(assets.shift(1) > 0)
        average = (assets + assets.shift(1)) / 2
        average = average.where(average > 0)
        roa = values(["Net Income"]) / beginning
        cfo = values(["Operating Cash Flow"]) / beginning
        # Current portion is required separately; total debt is not a substitute.
        leverage = (values(["Long Term Debt"]) + values(["Current Portion Of Long Term Debt"])) / average
        liquidity = values(["Current Assets"]) / values(["Current Liabilities"]).where(values(["Current Liabilities"]) > 0)
        margin = values(["Gross Profit"]) / values(["Total Revenue"]).where(values(["Total Revenue"]) > 0)
        turnover = values(["Total Revenue"]) / average
        issuance = values(["Issuance Of Capital Stock"])
        def last(series, offset=1):
            return number_like(series.iloc[-offset]) if len(series) >= offset else None
        def signal(function, *args):
            return float(function(*args)) if all(value is not None for value in args) else None
        r, old_r, c, lev, old_lev, liq, old_liq, mar, old_mar, turn, old_turn = [last(x, i) for x, i in [(roa, 1), (roa, 2), (cfo, 1), (leverage, 1), (leverage, 2), (liquidity, 1), (liquidity, 2), (margin, 1), (margin, 2), (turnover, 1), (turnover, 2)]]
        tests = {
            "f1_positive_roa": signal(lambda x: x > 0, r),
            "f2_positive_cfo_assets": signal(lambda x: x > 0, c),
            "f3_roa_improving": signal(lambda x, y: x > y, r, old_r),
            "f4_cfo_exceeds_roa": signal(lambda x, y: x > y, c, r),
            "f5_leverage_declining": signal(lambda x, y: x < y, lev, old_lev),
            "f6_liquidity_improving": signal(lambda x, y: x > y, liq, old_liq),
            "f7_no_equity_issuance": signal(lambda x: x == 0, last(issuance)),
            "f8_margin_improving": signal(lambda x, y: x > y, mar, old_mar),
            "f9_turnover_improving": signal(lambda x, y: x > y, turn, old_turn),
        }
        gaps = pd.to_datetime(hist.reportDate).diff().dt.days.tail(2) if not hist.empty else pd.Series(dtype=float)
        if len(gaps) < 2 or not gaps.between(320, 410).all():
            for key in ("f3_roa_improving", "f5_leverage_declining", "f9_turnover_improving"):
                tests[key] = None
        complete = all(value is not None for value in tests.values())
        rows.append({"ticker": symbol, **tests, "piotroski_f_score_spec": sum(tests.values()) if complete else None,
                     "piotroski_passed": sum(value for value in tests.values() if value is not None) if any(value is not None for value in tests.values()) else None,
                     "piotroski_available_criteria": sum(value is not None for value in tests.values()),
                     "piotroski_missing_criteria": [key for key, value in tests.items() if value is None]})
    return pd.DataFrame(rows)


def altman_z_score(panel: pd.DataFrame) -> pd.Series:
    components = pd.concat(
        [pd.to_numeric(panel.get(field), errors="coerce") for field in ["working_capital_assets", "retained_earnings_assets", "ebit_assets", "market_value_liabilities", "sales_assets"]],
        axis=1,
    )
    components.columns = ["wc", "re", "ebit", "mv", "sales"]
    score = 1.2 * components["wc"] + 1.4 * components["re"] + 3.3 * components["ebit"] + 0.6 * components["mv"] + components["sales"]
    return score.where(components.notna().all(axis=1))


def altman_z_double_prime(panel: pd.DataFrame) -> pd.Series:
    components = pd.concat(
        [pd.to_numeric(panel.get(field), errors="coerce") for field in ["working_capital_assets", "retained_earnings_assets", "ebit_assets", "book_value_liabilities"]],
        axis=1,
    )
    components.columns = ["wc", "re", "ebit", "mv"]
    score = 6.56 * components["wc"] + 3.26 * components["re"] + 6.72 * components["ebit"] + 1.05 * components["mv"]
    return score.where(components.notna().all(axis=1))


def altman_history(symbol: str, quarters: int = 8) -> list[dict[str, Any]]:
    from .data_loader import AS_OF, as_of_context, close_matrix
    from .fundamentals import latest_fundamental_features
    hist = fundamental_history(symbol)
    if hist.empty:
        return []
    if "periodType" in hist:
        hist = hist[hist.periodType.eq("quarterly")]
    prices = close_matrix([symbol], 1)
    cutoff = AS_OF.get() or (prices.index[-1] if not prices.empty else None)
    dates = (pd.to_datetime(hist.reportDate) + pd.Timedelta(days=90)).drop_duplicates().sort_values()
    if cutoff is not None:
        dates = dates[dates <= cutoff]
    rows = []
    for date in dates.tail(quarters):
        with as_of_context(date):
            panel = latest_fundamental_features([symbol], date)
        rows.append({"ticker": symbol, "available_date": date, "altman_z_score": altman_z_score(panel).iloc[0],
                     "altman_z_double_prime": altman_z_double_prime(panel).iloc[0]})
    return records(pd.DataFrame(rows))


def strategy_leaderboard(strategy_df: pd.DataFrame) -> pd.DataFrame:
    numeric_cols = _strategy_score_columns(strategy_df)
    rows = []
    for col in numeric_cols:
        values = pd.to_numeric(strategy_df[col], errors="coerce")
        rows.append(
            {
                "strategy": col,
                "avg_score": float(values.mean()),
                "top_decile_count": int((values >= values.quantile(0.9)).sum()) if values.notna().sum() else 0,
                "coverage": float(values.notna().mean()),
            }
        )
    return pd.DataFrame(rows).sort_values("avg_score", ascending=False)


def _strategy_score_columns(strategy_df: pd.DataFrame) -> list[str]:
    return [name for name in ACADEMIC_STRATEGIES if name in strategy_df]


def _select_strategies_for_backtest(strategy_df: pd.DataFrame, max_strategies: int = 24) -> tuple[list[str], list[str]]:
    eligible = _strategy_score_columns(strategy_df)
    limit = max(1, int(max_strategies or 1))
    selected = eligible[:limit]
    return selected, eligible


def full_strategy_performance_metadata(strategy_df: pd.DataFrame, max_strategies: int = 24) -> dict[str, Any]:
    selected, eligible = _select_strategies_for_backtest(strategy_df, max_strategies)
    return {
        "eligible_strategy_count": len(eligible),
        "evaluated_strategy_count": len(selected),
        "evaluated_strategies": selected,
        "excluded_due_to_limit": eligible[len(selected) :],
        "excluded_helper_patterns": ["f*_criteria", "piotroski_*", "*_proxy", "*_spec", "altman_z_score", "best_strategy_score"],
    }


def full_strategy_performance_table(
    strategy_df: pd.DataFrame,
    lookback_days: int = 756,
    top_n: int = 50,
    max_strategies: int = 24,
    payload: dict | None = None,
    shared_cache=None,
    symbols=None,
) -> list[dict[str, Any]]:
    if strategy_df.empty or "ticker" not in strategy_df:
        return []
    numeric_cols, _eligible = _select_strategies_for_backtest(strategy_df, max_strategies)
    symbols = symbols if symbols is not None else list(strategy_df["ticker"].dropna().astype(str))
    strategy_by_ticker = strategy_df.set_index("ticker", drop=False)
    rows = []
    shared_cache = shared_cache if shared_cache is not None else {}
    for col in numeric_cols:
        scores = pd.to_numeric(strategy_by_ticker[col], errors="coerce").dropna()
        if scores.empty:
            continue
        stats = score_backtest(symbols, scores, lookback_days=int(lookback_days), top_n=int(top_n), score_at=point_in_time_scorer(symbols, payload or {}, "academic", col, shared_cache)).get("stats", {})
        rows.append({"strategy": col, **stats})
    return clean_json(rows)

