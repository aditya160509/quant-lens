"""Dated stock re-selection, next-close execution and drift-based trading costs."""

from __future__ import annotations
import numpy as np
import pandas as pd
from scipy.optimize import brentq
from .data_loader import load_market_universe, request_scope
from .panel import characteristic_panel, usd_prices


def execute_targets(close, targets, cost_bps=0, borrow_bps=0):
    """Signals at t execute at t+1 close; positions earn returns from t+2."""
    returns = close.pct_change(fill_method=None)
    held = pd.Series(0.0, index=close.columns)
    gross_held = held.copy()
    nav_gross = nav_net = 1.0
    gross, net, trades = [], [], []
    pending = None
    for date in close.index:
        marks = returns.loc[date]
        active = held.ne(0)
        gross_active = gross_held.ne(0)
        if marks[active].isna().any():
            raise ValueError(
                f"Missing held return at {date.date()}: {list(held[active & marks.isna()].index)}"
            )
        earned = float((held[active] * marks[active]).sum())
        if marks[gross_active].isna().any():
            raise ValueError(f"Missing gross-book held return at {date.date()}")
        gross_earned = float((gross_held[gross_active] * marks[gross_active]).sum())
        if gross_earned <= -1:
            raise ValueError("Gross portfolio insolvency")
        gross_drift = gross_held.copy()
        gross_drift[gross_active] *= (1 + marks[gross_active]) / (1 + gross_earned)
        borrow = float(-held.clip(upper=0).sum() * borrow_bps / 10000 / 252)
        if earned - borrow <= -1:
            raise ValueError("Portfolio insolvency")
        drift = held.copy()
        drift[active] *= (1 + marks[active]) / (1 + earned - borrow)
        nav_gross *= 1 + gross_earned
        nav_net *= 1 + earned - borrow
        fee = 0.0
        if pending is not None:
            desired = pending.reindex(close.columns, fill_value=0.0)
            changing = desired.ne(0) | drift.ne(0)
            if close.loc[date, changing].isna().any():
                raise ValueError(f"Missing execution quote at {date.date()}")
            rate = cost_bps / 10000
            q = brentq(lambda q: q + rate * (q * desired - drift).abs().sum() - 1, 0, 1)
            turnover = float((q * desired - drift).abs().sum())
            fee = 1 - q
            nav_net *= q
            held = desired
            gross_held = desired.copy()
            trades.append(
                {"execution_date": date, "turnover": turnover, "cost_fraction": fee}
            )
        else:
            held = drift
            gross_held = gross_drift
        gross.append(gross_earned)
        net.append((1 + earned - borrow) * (1 - fee) - 1)
        pending = targets.get(date)
    return {
        "gross": pd.Series(gross, index=close.index),
        "net": pd.Series(net, index=close.index),
        "trades": trades,
    }


def portfolio_backtest(payload, include_bins=True):
    factor = payload.get("factor", "momentum_12_1")
    factors = payload.get("factors") or [factor]
    with request_scope(payload):
        prices = load_market_universe()
    explicit = payload.get("tickers", payload.get("symbols"))
    if isinstance(explicit, str):
        explicit = explicit.replace(",", " ").split()
    if explicit:
        prices = prices.loc[prices.Ticker.isin(explicit)]
    close = prices.set_index(["Date", "Ticker"]).Close.unstack().sort_index()
    close = usd_prices(close, payload.get("instrument_metadata", {}))
    close = close.tail(int(payload.get("window_days", 756)))
    if payload.get("start_date"):
        close = close.loc[pd.Timestamp(payload["start_date"]) :]
    if close.empty:
        raise ValueError("No prices in backtest period")
    step = int(
        payload.get(
            "rebalance_days",
            {
                "daily": 1,
                "weekly": 5,
                "monthly": 21,
                "quarterly": 63,
                "annual": 252,
            }.get(payload.get("refit_frequency", "monthly"), 21),
        )
    )
    targets = {}
    bucket_targets = {i: {} for i in range(1, 6)}
    decile_targets = {i: {} for i in range(1, 11)}
    for date in close.index[::step]:
        chars = characteristic_panel({**payload, "as_of_date": str(date.date())})
        scores = chars.set_index("Ticker")[[f + "_z" for f in factors]].dropna()
        if not len(scores):
            targets[date] = pd.Series(dtype=float)
            for books in (bucket_targets, decile_targets):
                for book in books.values():
                    book[date] = pd.Series(dtype=float)
            continue
        metadata = payload.get("instrument_metadata", {})
        missing = [
            t for t in scores.index if not metadata.get(t, {}).get("quote_currency")
        ]
        if missing:
            raise ValueError(
                "USD backtest requires instrument_metadata.quote_currency for: "
                + ", ".join(missing)
            )
        weights = payload.get("factor_weights") or {
            f: 1 / len(factors) for f in factors
        }
        score = scores.mul([weights.get(f, 0) for f in factors], axis=1).sum(axis=1)
        rank = score.rank(method="first", pct=True)
        top, bottom = rank[rank >= 0.8].index, rank[rank <= 0.2].index
        target = pd.Series(0.0, index=score.index)
        if len(top):
            target.loc[top] = 1 / len(top)
        if payload.get("long_short", True) and len(bottom):
            target.loc[bottom] = -1 / len(bottom)
        targets[date] = target
        for bins, books in [(5, bucket_targets), (10, decile_targets)]:
            if len(rank) < bins * 2:
                for book in books.values():
                    book[date] = pd.Series(dtype=float)
                continue
            group = np.minimum(np.ceil(rank * bins).astype(int), bins)
            for i in range(1, bins + 1):
                names = group[group == i].index
                books[i][date] = (
                    pd.Series(1 / len(names), index=names)
                    if len(names)
                    else pd.Series(dtype=float)
                )
    used = set().union(*(set(v.index) for v in targets.values())) if targets else set()
    if not used:
        raise ValueError(
            "No eligible formation-date scores; inspect history and statement/currency metadata"
        )
    close = close.loc[:, sorted(used)]
    result = execute_targets(
        close,
        targets,
        float(payload.get("cost_bps", 8)),
        float(payload.get("borrow_bps", 0)),
    )
    result.update(
        factor=factor,
        column="observed_stock_portfolio",
        equity_gross=(1 + result["gross"]).cumprod(),
        equity_net=(1 + result["net"]).cumprod(),
        cost_model={
            "rows": result["trades"],
            "cost_formula": "flat bps times actual drifted traded notional; next-close execution",
            "mean_gross_net_return_difference": float(
                (result["gross"] - result["net"]).mean()
            ),
        },
    )

    if not include_bins:
        return result

    def bins(books, label):
        rows = []
        from .analytics import perf_stats

        for i, book in books.items():
            if not book:
                continue
            r = execute_targets(close, book)["gross"]
            from arch.bootstrap import StationaryBootstrap

            ci = [None, None]
            draws = int(payload.get("bin_bootstrap_samples", 200))
            if len(r) >= 63 and r.ne(0).sum() >= 30:
                boot = StationaryBootstrap(
                    max(2, int(np.sqrt(len(r)))), r.to_numpy(), seed=707 + i
                )
                values = [
                    float(np.prod(1 + sample[0][0]) ** (252 / len(r)) - 1)
                    for sample in boot.bootstrap(draws)
                ]
                ci = np.quantile(values, [0.025, 0.975]).tolist()
            rows.append(
                {
                    label: f"{label[0].upper()}{i}",
                    "annual_return": perf_stats(r).get("annualized_return"),
                    "observations": len(r),
                    "annual_return_low_95": ci[0],
                    "annual_return_high_95": ci[1],
                    "confidence_method": "stationary block bootstrap compounded annual return",
                    "method": "dated_reselection_next_close_observed_returns",
                }
            )
        return rows

    result["quintiles"] = bins(bucket_targets, "quintile")
    result["deciles"] = bins(decile_targets, "decile")
    return result
