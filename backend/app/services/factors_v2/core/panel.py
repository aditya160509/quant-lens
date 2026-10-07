"""Formation-date characteristics from observed prices and lagged statements."""

from __future__ import annotations
from functools import lru_cache
import numpy as np
import pandas as pd
from .data_loader import (
    load_market_universe,
    load_fundamentals,
    request_payload,
    request_scope,
    parse_symbols,
    source_version,
)

PRICE_FACTORS = {"momentum_12_1", "momentum_6_1", "low_vol"}
FACTORS = [
    "value_pb",
    "value_ep",
    "momentum_12_1",
    "momentum_6_1",
    "quality_roe",
    "profitability",
    "low_vol",
    "size",
    "growth",
    "investment",
]


def select_universe(prices, payload, limit):
    explicit = parse_symbols(payload.get("tickers", payload.get("symbols")))
    if explicit:
        if len(explicit) > limit:
            raise ValueError(
                "Explicit universe exceeds max_tickers; increase the limit"
            )
        return explicit
    # Selection occurs at the formation date, never on today's volume.
    last_date = prices.Date.max()
    last = prices.loc[prices.Date == last_date].copy()
    metadata = payload.get("instrument_metadata", {})
    if not metadata:
        raise ValueError(
            "Supply explicit tickers or instrument_metadata for a USD-liquidity universe; native currency notionals cannot be ranked together"
        )
    marks = last.set_index("Ticker").Close.to_frame().T
    marks.index = pd.DatetimeIndex([last_date])
    dollars = usd_prices(marks, metadata).iloc[0]
    last["notional"] = last.Ticker.map(dollars) * last.Volume
    eligible = last.loc[last.notional.notna() & last.notional.gt(0)]
    if eligible.empty:
        raise ValueError(
            "No USD-liquidity observations with declared currencies and exact-date FX"
        )
    return (
        eligible.sort_values(["notional", "Ticker"], ascending=[False, True])
        .head(limit)
        .Ticker.astype(str)
        .tolist()
    )


def price_sample(max_tickers=240):
    payload = request_payload()
    prices = load_market_universe()
    selected = select_universe(prices, payload, max_tickers)
    return prices.loc[prices.Ticker.isin(selected)].copy()


def _numeric(frame, key):
    return (
        pd.to_numeric(frame[key], errors="coerce")
        if key in frame
        else pd.Series(np.nan, index=frame.index)
    )


def characteristic_panel(payload=None):
    payload = {**request_payload(), **(payload or {})}
    with request_scope(payload):
        prices = price_sample(int(payload.get("max_tickers", 240)))
        fund = load_fundamentals()
        if "ticker" in fund:
            fund = fund.loc[fund.ticker.isin(prices.Ticker.unique())].copy()
    if prices.empty:
        raise ValueError("No observed prices at the requested formation date")
    asof = pd.Timestamp(payload.get("as_of_date", prices.Date.max()))
    prices = prices.loc[prices.Date <= asof]
    # One observed formation calendar; stale quotes are not today's quotes.
    date = prices.Date.max()
    rows = prices.loc[prices.Date == date, ["Ticker", "Date", "Close", "Volume"]].copy()
    if prices.duplicated(["Ticker", "Date"]).any():
        raise ValueError("Duplicate ticker/date price observations")
    close = prices.set_index(["Date", "Ticker"]).Close.unstack().sort_index()
    volume = prices.set_index(["Date", "Ticker"]).Volume.unstack().reindex_like(close)
    scoring_close = (
        usd_prices(close, payload["instrument_metadata"])
        if payload.get("instrument_metadata")
        else close
    )
    ret = scoring_close.pct_change(fill_method=None)
    # Skip latest month by dividing the actual two endpoint marks.
    for period, key in [(252, "momentum_12_1"), (126, "momentum_6_1")]:
        score = scoring_close.shift(21) / scoring_close.shift(period) - 1
        rows[key] = rows.Ticker.map(score.iloc[-1])
    vol = ret.rolling(252, min_periods=63).std().iloc[-1] * np.sqrt(252)
    rows["low_vol"] = -rows.Ticker.map(vol)
    rows["realized_vol"] = rows.Ticker.map(vol)
    rows["adv_native"] = rows.Ticker.map(
        (close * volume).rolling(63, min_periods=30).mean().iloc[-1]
    )
    if {"ticker", "reportDate"}.issubset(fund):
        fund.reportDate = pd.to_datetime(fund.reportDate, errors="coerce")
        eligible = fund.loc[fund.reportDate + pd.Timedelta(days=90) <= asof].copy()
        # Vendor ratios and marketCap are snapshot fields, never historical statements.
        eligible = eligible.drop(
            columns=[
                c
                for c in [
                    "marketCap",
                    "priceToBook",
                    "trailingPE",
                    "returnOnEquity",
                    "grossMargins",
                ]
                if c in eligible
            ]
        )
        annual = (
            eligible.loc[eligible.periodType.eq("12M")]
            if "periodType" in eligible
            else eligible
        )
        annual = annual.sort_values(["ticker", "reportDate"]).drop_duplicates(
            ["ticker", "reportDate"]
        )
        for col, target in [
            ("Total Revenue", "growth"),
            ("Total Assets", "investment"),
        ]:
            annual[target] = (
                annual.groupby("ticker")[col].pct_change(fill_method=None)
                if col in annual
                else np.nan
            )
        annual["investment"] = -annual["investment"]
        last = annual.drop_duplicates("ticker", keep="last").rename(
            columns={"ticker": "Ticker", "reportDate": "statement_date"}
        )
        rows = rows.merge(last, on="Ticker", how="left", suffixes=("", "_statement"))
    for col in ["sector", "industry", "statement_date"]:
        if col not in rows:
            rows[col] = None
    equity = _numeric(rows, "Common Stock Equity").combine_first(
        _numeric(rows, "Stockholders Equity")
    )
    shares = _numeric(rows, "Ordinary Shares Number").where(lambda s: s > 0)
    rows["quality_roe"] = _numeric(rows, "Net Income") / equity.where(equity > 0)
    rows["profitability"] = _numeric(rows, "Gross Profit") / _numeric(
        rows, "Total Revenue"
    ).where(lambda s: s > 0)
    metadata = payload.get("instrument_metadata", {})
    compatible = rows.Ticker.map(
        lambda t: (
            bool(metadata.get(t, {}).get("quote_currency"))
            and metadata.get(t, {}).get("quote_currency")
            == metadata.get(t, {}).get("financial_currency")
            and metadata.get(t, {}).get("quoted_units_per_ordinary_share", 0) > 0
        )
    )
    units = rows.Ticker.map(
        lambda t: metadata.get(t, {}).get("quoted_units_per_ordinary_share", np.nan)
    )
    statement_market_value = (rows.Close * units * shares).where(compatible)
    rows["value_pb"] = equity / statement_market_value.where(statement_market_value > 0)
    rows["value_ep"] = _numeric(rows, "Net Income") / statement_market_value.where(
        statement_market_value > 0
    )
    # Global size and ADV comparisons require observed USD marks, never mixed quote units.
    usd = usd_prices(close, metadata)
    rows["market_cap"] = rows.Ticker.map(usd.iloc[-1]) * units * shares
    rows["adv"] = rows.Ticker.map(
        (usd * volume).rolling(63, min_periods=30).mean().iloc[-1]
    )
    rows["size"] = -np.log(rows.market_cap.where(rows.market_cap > 0))
    for factor in FACTORS:
        if factor not in rows:
            rows[factor] = np.nan
        v = pd.to_numeric(rows[factor], errors="coerce").replace(
            [np.inf, -np.inf], np.nan
        )
        rows[factor] = v
        std = v.std()
        rows[factor + "_z"] = (v - v.mean()) / std if std > 0 else np.nan
    if payload.get("selected_sector"):
        rows = rows.loc[rows.sector == payload["selected_sector"]]
    rows.attrs.update(
        as_of_date=str(asof.date()),
        universe_method="explicit_or_formation_date_native_notional",
        fundamental_lag_days=90,
    )
    return rows


@lru_cache(maxsize=2)
def _fx(version):
    from .data_loader import BACKEND_DATA

    path = BACKEND_DATA / "canonical/fx_daily.parquet"
    if not path.exists():
        return pd.DataFrame()
    frame = pd.read_parquet(path)
    return frame


def usd_prices(close, metadata):
    out = pd.DataFrame(np.nan, index=close.index, columns=close.columns)
    frame = _fx(source_version())
    for symbol in close:
        currency = metadata.get(symbol, {}).get("quote_currency")
        minor = {"GBp": ("GBP", 0.01), "ZAc": ("ZAR", 0.01)}
        currency, unit = minor.get(currency, (currency, 1.0))
        if currency == "USD":
            out[symbol] = close[symbol] * unit
        elif currency and not frame.empty:
            # Canonical schema is Date/Ticker/Close, checked in the data audit.
            dc = "date" if "date" in frame else "Date"
            pc = "pair" if "pair" in frame else "Ticker"
            vc = "close" if "close" in frame else "Close"
            for pair, inverse in [(currency + "USD", False), ("USD" + currency, True)]:
                marks = frame.loc[
                    frame[pc]
                    .astype(str)
                    .str.replace("/", "", regex=False)
                    .str.replace("=X", "", regex=False)
                    .eq(pair)
                ]
                if not marks.empty:
                    rates = pd.Series(
                        marks[vc].to_numpy(), index=pd.to_datetime(marks[dc])
                    ).sort_index()
                    if rates.index.duplicated().any():
                        raise ValueError("Duplicate FX marks")
                    rates = rates.reindex(close.index).where(lambda x: x > 0)
                    out[symbol] = (
                        close[symbol] * unit * (1 / rates if inverse else rates)
                    )
                    break
    return out


def historical_snapshots(payload, step=21):
    with request_scope(payload):
        all_prices = load_market_universe()
    dates = pd.DatetimeIndex(sorted(all_prices.Date.unique()))
    dates = dates[-int(payload.get("window_days", payload.get("lookback_days", 756))) :]
    if payload.get("start_date"):
        dates = dates[dates >= pd.Timestamp(payload["start_date"])]
    for date in dates[::step]:
        yield date, characteristic_panel({**payload, "as_of_date": str(date.date())})


def cross_sectional_ic(payload, horizon=21, step=21):
    with request_scope(payload):
        prices = load_market_universe()
    explicit = parse_symbols(payload.get("tickers"))
    if explicit:
        prices = prices.loc[prices.Ticker.isin(explicit)]
    close = prices.set_index(["Date", "Ticker"]).Close.unstack().sort_index()
    if payload.get("instrument_metadata"):
        close = usd_prices(close, payload["instrument_metadata"])
    forward = close.shift(-(horizon + 1)) / close.shift(-1) - 1
    factor = payload.get("factor", "momentum_12_1")
    rows = []
    for date, chars in historical_snapshots(payload, step):
        if date not in forward.index:
            continue
        a = (
            chars.set_index("Ticker")[factor]
            .rename("score")
            .to_frame()
            .join(forward.loc[date].rename("return"))
            .dropna()
        )
        if len(a) >= 5 and a.score.std() > 0 and a["return"].std() > 0:
            mature = close.index.get_loc(date) + horizon + 1
            if mature < len(close):
                rows.append(
                    {
                        "date": close.index[mature],
                        "formation_date": date,
                        "ic": a.score.corr(a["return"], method="spearman"),
                        "stocks": len(a),
                    }
                )
    return pd.DataFrame(rows)
