"""Date-group CPCV with event-overlap purging and assembled test paths."""
from __future__ import annotations
from itertools import combinations
import math
import numpy as np
import pandas as pd
from scipy import stats
from .performance import fast_spearman_ic, sharpe, equity_from_returns


def purged_complement(dates, test_dates, horizon, embargo):
    unique = pd.DatetimeIndex(pd.to_datetime(dates).unique()).sort_values()
    positions = unique.get_indexer(pd.to_datetime(dates))
    test_positions = unique.get_indexer(pd.to_datetime(test_dates))
    mask = np.ones(len(unique), dtype=bool)
    for position in test_positions:
        mask[max(0, position - horizon):min(len(unique), position + horizon + embargo + 1)] = False
    return np.flatnonzero(mask[positions])


def path_returns(panel, predictions, horizon):
    data = panel[["date", "ticker", "target_return"]].copy()
    data["prediction"] = predictions
    data = data.dropna()
    # Non-overlapping horizon portfolios: weights fixed until horizon exit.
    rows = []
    for i, (date, group) in enumerate(data.groupby("date", sort=True)):
        if i % horizon:
            continue
        returns = np.expm1(group.target_return.to_numpy())
        weights = np.sign(group.prediction.to_numpy()) / len(group)
        rows.append({"date": str(pd.Timestamp(date).date()), "return": float(weights @ returns)})
    return rows


def run_cpcv_engine(payload=None):
    from .panel import load_context, make_feature_panel, numeric_xy
    from .estimators import _fit_base_model
    from .common import response, summary
    request = payload or {}
    ctx = load_context(request)
    horizon = int(request.get("prediction_horizon", 5))
    embargo = int(request.get("embargo_period", 5))
    groups_count = int(request.get("cpcv_n_groups", 6))
    test_count = int(request.get("cpcv_k_test_groups", 2))
    if not 4 <= groups_count <= 8 or not 1 <= test_count < groups_count or horizon < 1 or embargo < 0:
        raise ValueError("Invalid CPCV grouping, horizon or embargo")
    if request.get("label_type", "regression_return") != "regression_return":
        raise ValueError("CPCV currently supports regression_return labels; classification labels are unavailable")
    panel, target = make_feature_panel(ctx, horizon)
    X, target = numeric_xy(panel, target)
    dates = pd.DatetimeIndex(pd.to_datetime(panel.date).unique()).sort_values()
    if len(dates) < groups_count * (horizon + embargo + 10):
        raise ValueError("Insufficient distinct dates for requested purged CPCV")
    date_groups = np.array_split(dates.to_numpy(), groups_count)
    combinations_list = list(combinations(range(groups_count), test_count))
    paths_count = math.comb(groups_count - 1, test_count - 1)
    paths = np.full((paths_count, len(panel)), np.nan)
    group_occurrence = np.zeros(groups_count, dtype=int)
    split_rows = []
    model_name = request.get("model_type", "ridge")
    for number, combo in enumerate(combinations_list):
        held_dates = np.concatenate([date_groups[g] for g in combo])
        test = np.flatnonzero(pd.to_datetime(panel.date).isin(held_dates).to_numpy())
        train = purged_complement(panel.date, held_dates, horizon, embargo)
        if len(train) < 30:
            raise ValueError("CPCV split has insufficient purged training observations")
        model = _fit_base_model(model_name, 7)
        model.fit(X.iloc[train], target.iloc[train])
        prediction = model.predict(X.iloc[test])
        naive_train = np.flatnonzero(~pd.to_datetime(panel.date).isin(held_dates).to_numpy())
        naive_model = _fit_base_model(model_name, 7).fit(X.iloc[naive_train], target.iloc[naive_train])
        naive_prediction = naive_model.predict(X.iloc[test])
        oos_returns = path_returns(panel.iloc[test], prediction, horizon)
        naive_returns = path_returns(panel.iloc[test], naive_prediction, horizon)
        split_rows.append({"split": number + 1, "test_groups": list(combo),
            "training_observations": len(train), "test_observations": len(test),
            "purged_observations": len(naive_train) - len(train), "embargo_sessions": embargo,
            "test_start": str(pd.Timestamp(held_dates.min()).date()),
            "test_end": str(pd.Timestamp(held_dates.max()).date()),
            "purged_sharpe": sharpe([row["return"] for row in oos_returns], ctx.annualization / horizon),
            "naive_sharpe": sharpe([row["return"] for row in naive_returns], ctx.annualization / horizon),
            "ic": fast_spearman_ic(np.asarray(prediction), target.iloc[test].to_numpy())})
        predicted = pd.Series(prediction, index=test)
        for group in combo:
            group_rows = np.flatnonzero(pd.to_datetime(panel.date).isin(date_groups[group]).to_numpy())
            paths[group_occurrence[group], group_rows] = predicted.loc[group_rows]
            group_occurrence[group] += 1
    if not np.isfinite(paths).all():
        raise RuntimeError("Incomplete CPCV path assembly")
    metrics, curves = [], []
    for path_id, predictions in enumerate(paths, 1):
        returns = path_returns(panel, predictions, horizon)
        values = [row["return"] for row in returns]
        metrics.append({"path": path_id, "sharpe": sharpe(values, ctx.annualization / horizon),
                        "observations": len(values)})
        equity = equity_from_returns(values)
        curves.extend({"path": path_id, "date": row["date"], "equity": float(value)}
                      for row, value in zip(returns, equity))
    sharpes = [row["sharpe"] for row in metrics]
    histogram = [{"sharpe": value} for value in sharpes]
    comparison = [{"method": method, "sharpe": float(np.mean([row[key] for row in split_rows]))}
                  for method, key in [("naive_kfold", "naive_sharpe"), ("purged_kfold", "purged_sharpe")]]
    return response("01", [summary("CPCV Mean Sharpe", float(np.mean(sharpes))), summary("Paths", paths_count)],
        charts={"cpcv_sharpe_distribution": histogram, "purged_vs_naive_cv_comparison": comparison,
                "backtest_paths_chart": curves},
        tables={"per_fold_performance": split_rows, "cpcv_path_metrics": metrics},
        meta={"validation": "date_groups_event_overlap_purge_and_embargo", "paths": paths_count,
              "split_count": len(combinations_list), "performance": "nonoverlapping_horizon_portfolios_gross_of_costs",
              "pbo": "Not produced: requires multiple strategy configurations and CSCV, not fraction below a path median",
              "dsr": "Not produced: independent trial Sharpe variance and higher moments are not supplied",
              "sector_basis": "time_invariant_current_snapshot"})
