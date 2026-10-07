"""Actual holdings exposures with per-stock return regressions."""

import numpy as np
import pandas as pd
from scipy.stats import t
from app.services.factors_v2.core.analytics import (
    characteristic_panel,
    factor_returns,
    ols_beta,
    response,
)
from app.services.factors_v2.core.data_loader import load_market_universe, parse_symbols


def run(payload):
    holdings = payload.get("holdings")
    if not holdings:
        raise ValueError(
            "Supply actual holdings: [{ticker, weight}]; no arbitrary sample portfolio"
        )
    h = pd.DataFrame(holdings).rename(columns={"ticker": "Ticker"})
    if not {"Ticker", "weight"}.issubset(h):
        raise ValueError("Holdings require ticker and weight")
    parse_symbols(h.Ticker.tolist())
    if h.Ticker.duplicated().any():
        raise ValueError("Duplicate holdings")
    h.weight = pd.to_numeric(h.weight, errors="raise")
    if not np.isfinite(h.weight).all() or h.weight.abs().sum() == 0:
        raise ValueError("Holdings weights must be finite and nonzero")
    chars = characteristic_panel(payload)
    if payload.get("sector_neutral"):
        for f in payload.get("factors") or ["momentum_12_1", "low_vol"]:
            chars[f + "_z"] = chars.groupby("sector")[f].transform(
                lambda v: (
                    (v - v.mean()) / v.std()
                    if v.notna().sum() > 1 and v.std() > 0
                    else np.nan
                )
            )
    merged = h.merge(chars, on="Ticker", how="left")
    factors = payload.get("factors") or ["momentum_12_1", "low_vol"]
    characteristic = []
    for f in factors:
        v = merged[f + "_z"]
        missing = merged.loc[v.isna() & merged.weight.ne(0), "Ticker"].tolist()
        exp = None if missing else float((v * merged.weight).sum())
        characteristic.append(
            {"factor": f, "characteristic_exposure": exp, "missing_tickers": missing}
        )
    prices = load_market_universe()
    prices = prices.loc[prices.Ticker.isin(h.Ticker)]
    close = prices.set_index(["Date", "Ticker"]).Close.unstack().sort_index()
    from app.services.factors_v2.core.panel import usd_prices

    close = usd_prices(close, payload.get("instrument_metadata", {}))
    returns = close.pct_change(fill_method=None).tail(
        int(payload.get("estimation_days", 252))
    )
    ff = factor_returns(payload)
    from app.services.factors_v2.core.data_loader import load_factor_returns

    source = load_factor_returns(payload.get("factor_model", "ff5_mom"))
    if "RF" not in source:
        raise ValueError(
            "Stock excess-return regression requires observed risk-free returns"
        )
    returns = returns.sub(source["RF"].reindex(returns.index), axis=0)
    rows = []
    for symbol in h.Ticker:
        y = returns[symbol]
        beta, se, alpha = ols_beta(y, ff)
        sample = pd.concat([y, ff], axis=1).dropna()
        df = len(sample) - len(ff.columns) - 1
        q = t.ppf(0.975, df) if df > 0 else np.nan
        for f, b in beta.items():
            rows.append(
                {
                    "ticker": symbol,
                    "factor": f,
                    "return_exposure": b,
                    "standard_error": se[f],
                    "ci_low_95": b - q * se[f],
                    "ci_high_95": b + q * se[f],
                    "sample_size": len(sample),
                    "alpha": alpha,
                }
            )
    exposures = []
    for f in ff.columns:
        sub = (
            pd.DataFrame([r for r in rows if r["factor"] == f]).set_index("ticker")
            if rows
            else pd.DataFrame()
        )
        value = (
            float(
                sub.return_exposure.reindex(h.Ticker).to_numpy() @ h.weight.to_numpy()
            )
            if len(sub) == len(h)
            else None
        )
        exposures.append({"factor": f, "return_exposure": value})
    active = []
    if payload.get("benchmark_holdings"):
        benchmark = pd.DataFrame(payload["benchmark_holdings"])
        if (
            not {"ticker", "weight"}.issubset(benchmark)
            or benchmark.ticker.duplicated().any()
        ):
            raise ValueError("Benchmark requires unique ticker and weight rows")
        parse_symbols(benchmark.ticker.tolist())
        weights = pd.to_numeric(benchmark.weight, errors="raise")
        if not np.isfinite(weights).all():
            raise ValueError("Benchmark weights must be finite")
        for row in characteristic:
            observed = chars.set_index("Ticker")[row["factor"] + "_z"].reindex(
                benchmark.ticker
            )
            b = (
                float(observed.to_numpy() @ weights.to_numpy())
                if observed.notna().all()
                else None
            )
            active.append(
                {
                    "factor": row["factor"],
                    "benchmark_characteristic_exposure": b,
                    "active_characteristic_exposure": row["characteristic_exposure"] - b
                    if b is not None and row["characteristic_exposure"] is not None
                    else None,
                }
            )
    snapshots = []
    for snapshot in payload.get("rebalancing_history", []):
        dated = characteristic_panel(
            {**payload, "as_of_date": snapshot["date"]}
        ).set_index("Ticker")
        sh = pd.DataFrame(snapshot["holdings"]).set_index("ticker")
        entries = []
        for f in factors:
            v = dated[f + "_z"].reindex(sh.index)
            entries.append(
                {
                    "factor": f,
                    "exposure": None if v.isna().any() else float(v @ sh.weight),
                }
            )
        snapshots.append({"date": snapshot["date"], "exposures": entries})
    return response(
        "feature_02",
        charts={
            "exposure_bar": characteristic,
            "static_exposure_heatmap": merged[
                ["Ticker", "weight"] + [f + "_z" for f in factors]
            ].to_dict("records"),
            "rolling_exposure_snapshots": {"snapshots": snapshots},
        },
        tables={
            "characteristic_exposures": characteristic,
            "return_exposures": rows,
            "portfolio_return_exposures": exposures,
            "active_characteristic_exposures": active,
        },
        meta={
            "holdings_count": len(h),
            "methodologies": [
                "formation_date_characteristics",
                "per_stock_ols_95pct_t_intervals",
            ],
            "return_basis": "USD converted excess quote returns against USD factor premiums; undeclared currencies have no return regression",
            "missing_output_reasons": {
                "divergence": "Characteristic z-scores and return betas have different units; a difference is not a calibrated surprise",
                "active_exposure": "Supply benchmark_holdings for observed characteristic active exposures; benchmark returns are not inferred",
            },
        },
    )


from .inputs import inputs as _inputs, outputs as _outputs

INPUTS = _inputs("02")
OUTPUTS = _outputs("02")
