"""Observed concentration, factor persistence and price-change liquidity diagnostics."""

import numpy as np
from app.services.factors_v2.core.analytics import (
    characteristic_panel,
    backtest_series,
    response,
)
from app.services.factors_v2.core.panel import price_sample


def run(payload):
    chars = characteristic_panel(payload)
    factor = payload.get("factor", "momentum_12_1")
    v = chars.set_index("Ticker")[factor].dropna()
    rank = v.rank(method="first", pct=True)
    top = rank[rank >= 0.8].index
    hhi = 1 / len(top) if len(top) else None
    sector_hhi = None
    if len(top):
        sectors = chars.set_index("Ticker").sector.reindex(top)
        if sectors.notna().all():
            sector_hhi = float((sectors.value_counts(normalize=True) ** 2).sum())
    r = backtest_series(payload)["gross"]
    ac = r.rolling(63).corr(r.shift(1))
    vol = r.rolling(63).std()
    percentile = (
        vol.expanding(min_periods=63)
        .apply(lambda x: float((x < x.iloc[-1]).mean() * 100))
        .dropna()
    )
    prices = price_sample(int(payload.get("max_tickers", 240)))
    close = prices.set_index(["Date", "Ticker"]).Close.unstack().sort_index()
    rows = []
    for symbol in top:
        if symbol not in close:
            continue
        delta = close[symbol].diff()
        cov = delta.rolling(63).cov(delta.shift(1))
        last = cov.iloc[-1]
        rows.append(
            {
                "ticker": symbol,
                "roll_implied_spread_quote_units": 2 * np.sqrt(-last)
                if last < 0
                else None,
                "status": "estimated"
                if last < 0
                else "undefined_nonnegative_or_missing_covariance",
            }
        )
    return response(
        "feature_06",
        summary_cards=[
            {"label": "Equal-weight stock HHI", "value": hhi},
            {
                "label": "Observed volatility percentile",
                "value": float(percentile.iloc[-1]) if len(percentile) else None,
            },
        ],
        charts={
            "crowding_timeseries": [
                {"date": d, "value": v} for d, v in percentile.tail(260).items()
            ]
        },
        tables={
            "crowding_metrics": [
                {"metric": "stock_hhi", "raw": hhi},
                {"metric": "sector_hhi", "raw": sector_hhi},
                {
                    "metric": "factor_return_autocorrelation",
                    "raw": float(ac.dropna().iloc[-1]) if len(ac.dropna()) else None,
                },
            ],
            "bid_ask_detail": rows,
        },
        meta={
            "factor": factor,
            "method": "Equal-weight top-book concentration, published factor-return persistence and Roll price-change estimator",
            "crowding_series_basis": "Observed factor volatility percentile, not an institutional-positioning composite",
            "missing_output_reasons": {
                "composite_crowding": "No empirically calibrated mapping from the observed metrics to institutional positioning",
                "crash_probability": "No matched historical composite-score/crash calibration",
                "short_interest": "No observed short-interest feed",
            },
        },
    )


from .inputs import inputs as _inputs, outputs as _outputs

INPUTS = _inputs("06")
OUTPUTS = _outputs("06")
