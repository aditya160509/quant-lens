"""Historical factor weighting and next-close long-short portfolios."""
from __future__ import annotations
import numpy as np
import pandas as pd
from sklearn.covariance import LedoitWolf
from .common import build_provenance, response, summary, matrix_records
from .data_loader import universe_label
from .panel import load_context, make_feature_panel, numeric_xy
from .performance import fast_spearman_ic
from .portfolio import execute_portfolio


def daily_ic_table(features, targets, dates):
    """Per-date cross-sectional Spearman IC of every feature column against the target (NaN below 4 pairs)."""
    x = features.to_numpy(float)
    y = targets.reindex(features.index).to_numpy(float)
    codes, days = pd.factorize(pd.Series(np.asarray(dates)), sort=True)
    order = np.argsort(codes, kind="stable")
    edges = np.flatnonzero(np.diff(codes[order])) + 1
    rows = []
    for day, idx in zip(days, np.split(order, edges)):
        if len(idx) < 4:
            continue
        rows.append([fast_spearman_ic(x[idx, j], y[idx]) for j in range(x.shape[1])])
        rows[-1] = dict(zip(features.columns, rows[-1]), date=day)
    return pd.DataFrame(rows).set_index("date") if rows else pd.DataFrame(columns=features.columns)


def training_transform(train, future, method):
    """Fit sequential residualization coefficients only on the training window."""
    tr, te = train.copy(), future.copy()
    if method == "none":
        return tr, te
    if method != "gram_schmidt":
        raise ValueError("Supported orthogonalization: none or gram_schmidt")
    columns = list(tr.columns)
    for i, col in enumerate(columns):
        if not i:
            continue
        previous = columns[:i]
        coefficient = np.linalg.lstsq(tr[previous].to_numpy(), tr[col].to_numpy(), rcond=None)[0]
        tr[col] -= tr[previous].to_numpy() @ coefficient
        te[col] -= te[previous].to_numpy() @ coefficient
    return tr, te


def run_composite_optimizer(payload=None):
    request = payload or {}
    ctx = load_context(request)
    horizon = int(request.get("prediction_horizon", 5))
    panel, target = make_feature_panel(ctx, horizon, include_unlabelled=True)
    features, target = numeric_xy(panel, target)
    dates = pd.to_datetime(panel.date)
    # Same-date sector centering and normalization cannot depend on future rows.
    sectors = panel.ticker.map(ctx.sectors)
    centered = features - features.groupby([dates, sectors]).transform("median")
    scales = centered.groupby(dates).transform("std").replace(0., np.nan)
    normalized = centered.div(scales)
    unique = pd.DatetimeIndex(dates.unique()).sort_values()
    window = int(request.get("walk_forward_window", 252))
    embargo = int(request.get("embargo_period", 5))
    scheme = request.get("weighting_scheme", "ic_ir")
    construction = request.get("output_signal_construction", "zscore")
    history, weights_rows, score_rows, targets = [], [], [], {}
    for i in range(window + horizon + embargo, len(unique), 21):
        end = i - horizon - embargo
        train_mask = dates.isin(unique[max(0, end-window):end])
        test_mask = dates.isin(unique[i:min(i+21, len(unique))])
        from sklearn.impute import SimpleImputer
        available = normalized.loc[train_mask].columns[normalized.loc[train_mask].notna().any()]
        if not len(available):
            raise ValueError("No observed standardized training factors")
        imputer = SimpleImputer(strategy="median")
        training = pd.DataFrame(imputer.fit_transform(normalized.loc[train_mask,available]),index=normalized.index[train_mask],columns=available)
        upcoming = pd.DataFrame(imputer.transform(normalized.loc[test_mask,available]),index=normalized.index[test_mask],columns=available)
        train, future = training_transform(training, upcoming,
                                            request.get("orthogonalization", "gram_schmidt"))
        ics = daily_ic_table(train, target.loc[train_mask], dates.loc[train_mask])
        if len(ics) < 20:
            raise ValueError("Composite needs at least 20 training dates with four assets")
        means = ics.mean()
        if scheme == "ic":
            raw = means
        elif scheme == "ic_ir":
            raw = means / ics.std(ddof=1).replace(0., np.nan)
        elif scheme == "shrinkage":
            covariance = LedoitWolf().fit(ics.fillna(0.)).covariance_
            raw = pd.Series(np.linalg.pinv(covariance) @ means.to_numpy(), index=means.index)
        else:
            raise ValueError("Supported weighting schemes: ic, ic_ir, shrinkage")
        raw = raw.replace([np.inf, -np.inf], np.nan).fillna(0.)
        if raw.abs().sum() <= 1e-12:
            raise ValueError("No estimable training factor weights")
        weights = raw / raw.abs().sum()
        weights_rows.extend({"date": str(unique[i].date()), "factor": col, "weight": float(weights[col]),
                             "training_mean_ic": float(means[col]), "training_ic_ir": float(means[col]/ics[col].std(ddof=1)) if ics[col].std(ddof=1)>1e-12 else None}
                            for col in weights.index)
        history.append({"date": str(unique[i].date()), "training_start": str(unique[max(0, end-window)].date()),
                        "training_end": str(unique[end-1].date()), "training_dates": len(ics)})
        scores = future @ weights
        for date, group in panel.loc[test_mask].groupby("date"):
            current = scores.loc[group.index]
            if construction == "signed_rank":
                current = current.rank(pct=True) * 2 - 1
            elif construction == "zscore":
                deviation = current.std(ddof=1)
                current = (current-current.mean())/deviation if deviation>1e-12 else current*0
            elif construction != "long_short_decile":
                raise ValueError("Unsupported signal construction")
            n = max(1, len(group)//10)
            book = group.assign(score=current).sort_values("score")
            holdings = {ticker: -.5/n for ticker in book.ticker.iloc[:n]}
            holdings.update({ticker: .5/n for ticker in book.ticker.iloc[-n:]})
            targets[pd.Timestamp(date)] = holdings
            score_rows.extend({"date": str(pd.Timestamp(date).date()), "ticker": ticker, "score": float(value)}
                              for ticker, value in zip(group.ticker, current))
    if not history:
        raise ValueError("Insufficient historical dates for requested composite training window")
    backtest = execute_portfolio(ctx.returns, targets, float(request.get("cost_bps", 5)))
    latest_date = score_rows[-1]["date"]
    latest = [row for row in score_rows if row["date"] == latest_date]
    provenance = build_provenance(ctx.closes, calendar=ctx.calendar, train_window=(history[0]["training_start"], history[-1]["training_end"]),
                                  test_window=(history[0]["date"], latest_date), purge=horizon, embargo=embargo,
                                  universe=universe_label(ctx.payload, ctx.symbols), extra={"refits": len(history), "window": window})
    return response("08", [summary("Training refits", len(history)), summary("Latest signals", len(latest))], provenance=provenance,
        charts={"ic_weighted_composite_weights": [row for row in weights_rows if row["date"]==weights_rows[-1]["date"]],
                "walk_forward_weight_stability": weights_rows, "composite_signal_distribution": latest,
                "long_short_backtest": backtest, "factor_correlation_heatmap": matrix_records(normalized.corr())},
        tables={"factor_weights": weights_rows, "latest_composite_scores": latest, "training_audit": history},
        meta={"weighting_scheme": scheme, "validation": "historical_label_maturity_plus_embargo",
              "sector_basis": "time_invariant_current_snapshot", "imputation":"training_window_median; wholly unobserved factors excluded", "execution": "formation_t_execute_close_t_plus_1",
              "costs": "actual_drifted_weight_turnover", "return_currency": "native_asset_returns; FX and financing excluded",
              "as_of_date": str(ctx.returns.index.max().date())})
