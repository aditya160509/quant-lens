"""Observed USD equity liquidity; unavailable spreads and impact calibrations stay absent."""

import math
import numpy as np
import pandas as pd
from .data_loader import ohlcv_for_symbols, load_fundamentals_metadata


def liquidity_table(
    symbols,
    lookback_days=252,
    nav=1000000,
    weights=None,
    adv_window=60,
    participation=0.2,
):
    if nav <= 0 or not 0 < participation <= 1:
        raise ValueError("Positive NAV and valid participation required")
    raw = ohlcv_for_symbols(symbols, lookback_days).copy()
    currencies = load_fundamentals_metadata()
    mapping = (
        dict(zip(currencies.ticker, currencies.currency))
        if "currency" in currencies
        else {}
    )
    weights = (
        pd.Series(1 / len(symbols), index=symbols)
        if weights is None
        else weights.reindex(symbols, fill_value=0)
    )
    rows = []
    for ticker in symbols:
        g = raw.loc[raw.Ticker.eq(ticker)].sort_values("Date")
        currency = mapping.get(ticker)
        if (
            g.empty
            or not g.Asset_Class.eq("equity").all()
            or currency not in {None, "USD"}
            or ("_" in ticker and ticker not in {"BRK_B", "BRK_A"})
        ):
            raise ValueError(
                f"USD share-volume provenance unavailable for {ticker}; no dollar-volume proxy supplied"
            )
        valid = g.loc[
            np.isfinite(g.Volume)
            & g.Volume.gt(0)
            & np.isfinite(g.Open)
            & g.Open.gt(0)
            & g.Close.gt(0)
        ]
        if len(valid) < 20:
            raise ValueError(
                f"At least 20 valid observed share-volume sessions required for {ticker}"
            )
        dv = valid.Close * valid.Volume
        oc = (valid.Close / valid.Open - 1).abs()
        illiq = oc / dv
        time = np.arange(1, len(valid) + 1)
        recency = time / time.sum()
        adv = float(dv.tail(adv_window).mean())
        sigma = float(g.Close.pct_change(fill_method=None).dropna().std(ddof=1))
        position = abs(float(weights[ticker])) * nav
        impact = sigma * math.sqrt(position / adv) if position else 0
        rows.append(
            {
                "ticker": ticker,
                "amihud": float(illiq.mean()),
                "recency_weighted_amihud": float(np.average(illiq, weights=recency)),
                "adv_dollars": adv,
                "daily_return_volatility": sigma,
                "position_dollars": position,
                "days_to_liquidate": position / (participation * adv),
                "days_to_liquidate_15pct_adv": position / (0.15 * adv),
                "days_to_liquidate_20pct_adv": position / (0.2 * adv),
                "square_root_impact_bps": impact * 10000,
                "impact_assumption": "Square-root impact with unit coefficient; observed volatility and ADV, not calibrated order flow",
                "observed_volume_sessions": len(valid),
                "excluded_volume_sessions": len(g) - len(valid),
            }
        )
    return rows


def recency_weighted_amihud(ohlcv):
    values = {}
    for ticker, g in ohlcv.groupby("Ticker"):
        g = g.sort_values("Date")
        x = (
            ((g.Close / g.Open - 1).abs() / (g.Close * g.Volume))
            .replace([np.inf, -np.inf], np.nan)
            .dropna()
        )
        weights = np.arange(1, len(x) + 1)
        values[ticker] = float(np.average(x, weights=weights)) if len(x) else np.nan
    return pd.Series(values)


def liquidity_halflife(series):
    y = np.log(series.replace(0, np.nan).dropna()).tail(60)
    if len(y) < 10:
        return None
    slope = np.polyfit(np.arange(len(y)), y, 1)[0]
    return float(math.log(0.5) / slope) if slope < 0 else None


def regulatory_classification(days_to_liquidate):
    return (
        "highly_liquid"
        if days_to_liquidate <= 3
        else "moderately_liquid"
        if days_to_liquidate <= 7
        else "less_liquid"
        if days_to_liquidate <= 15
        else "illiquid"
    )


def crisis_liquidation_cost(liq_rows, volume_multiplier=0.3):
    if not 0 < volume_multiplier <= 1:
        raise ValueError("Invalid stress volume multiplier")
    return [
        {
            "ticker": r["ticker"],
            "stress_days_to_liquidate": r["days_to_liquidate"] / volume_multiplier,
            "stress_square_root_impact_bps": r["square_root_impact_bps"]
            / math.sqrt(volume_multiplier),
            "volume_multiplier_assumption": volume_multiplier,
            "calibrated_to_crisis": False,
        }
        for r in liq_rows
    ]


def liquidity_frontier(liq_rows):
    return [
        {
            "dtl_cap": cap,
            "eligible_count": sum(r["days_to_liquidate"] <= cap for r in liq_rows),
            "interpretation": "Observed position eligibility, not an optimized expected-return frontier",
        }
        for cap in [1, 3, 5, 10, 20, 40]
    ]


def liquidation_schedule(rows, participation=0.2, urgency="orderly"):
    out = []
    for row in rows:
        position = row["position_dollars"]
        capacity = participation * row["adv_dollars"]
        days = max(1, math.ceil(position / capacity))
        if urgency == "distressed":
            days = max(days, 2)
        if urgency == "crisis":
            days = max(days, 3)
        # Display each executable day; do not silently truncate unresolved balances.
        if days > 10000:
            raise ValueError(
                "Liquidation requires more than 10000 days at declared participation"
            )
        remaining = position
        for day in range(1, days + 1):
            desired = (
                position * 0.5
                if urgency == "distressed" and day == 1
                else position / 3
                if urgency == "crisis" and day <= 3
                else remaining / (days - day + 1)
            )
            # Front-loaded preferences may not leave more than future capacity.
            required_today = max(0.0, remaining - capacity * (days - day))
            traded = min(remaining, capacity, max(desired, required_today))
            remaining -= traded
            out.append(
                {
                    "ticker": row["ticker"],
                    "day": day,
                    "trade_dollars": traded,
                    "remaining_dollars": remaining,
                    "participation": traded / row["adv_dollars"],
                    "requested_urgency": urgency,
                    "urgency_infeasible": urgency == "distressed"
                    and capacity < position * 0.5
                    or urgency == "crisis"
                    and capacity < position / 3,
                }
            )
        if remaining > 1e-6 * max(position, 1):
            raise ValueError("Liquidation schedule leaves unexecuted balance")
    return out
