"""Universe catalogue and filters over every market in the master parquet.

Everything is a lazy polars scan that returns one small row per ticker (last
close, mean dollar volume, first date); nothing loads daily prices into pandas,
so the same code scales to a much larger production file. Results are cached
per source file and modification time.
"""

from __future__ import annotations

from functools import lru_cache
from typing import Any

import pandas as pd

from .core import data_loader as dl

# Exchange suffix (after normalisation "XYZ.L" -> "XYZ_L") -> (country, region).
SUFFIX_MARKETS = {
    "L": ("UK", "Europe"), "DE": ("Germany", "Europe"), "F": ("Germany", "Europe"), "PA": ("France", "Europe"), "MI": ("Italy", "Europe"), "AS": ("Netherlands", "Europe"),
    "MC": ("Spain", "Europe"), "SW": ("Switzerland", "Europe"), "ST": ("Sweden", "Europe"), "OL": ("Norway", "Europe"), "CO": ("Denmark", "Europe"), "HE": ("Finland", "Europe"),
    "BR": ("Belgium", "Europe"), "LS": ("Portugal", "Europe"), "VI": ("Austria", "Europe"), "IR": ("Ireland", "Europe"), "WA": ("Poland", "Europe"), "AT": ("Greece", "Europe"), "IS": ("Turkey", "Europe"),
    "T": ("Japan", "Asia-Pacific"), "HK": ("Hong Kong", "Asia-Pacific"), "SS": ("China", "Asia-Pacific"), "SZ": ("China", "Asia-Pacific"), "TW": ("Taiwan", "Asia-Pacific"), "TWO": ("Taiwan", "Asia-Pacific"),
    "KS": ("South Korea", "Asia-Pacific"), "KQ": ("South Korea", "Asia-Pacific"), "SI": ("Singapore", "Asia-Pacific"), "AX": ("Australia", "Asia-Pacific"), "NZ": ("New Zealand", "Asia-Pacific"),
    "NS": ("India", "Asia-Pacific"), "BO": ("India", "Asia-Pacific"), "JK": ("Indonesia", "Asia-Pacific"), "BK": ("Thailand", "Asia-Pacific"), "KL": ("Malaysia", "Asia-Pacific"), "VN": ("Vietnam", "Asia-Pacific"),
    "TO": ("Canada", "North America"), "V": ("Canada", "North America"), "CN": ("Canada", "North America"), "MX": ("Mexico", "Latin America"), "SA": ("Brazil", "Latin America"), "SN": ("Chile", "Latin America"), "BA": ("Argentina", "Latin America"),
    "SR": ("Saudi Arabia", "Middle East & Africa"), "TA": ("Israel", "Middle East & Africa"), "JO": ("South Africa", "Middle East & Africa"), "QA": ("Qatar", "Middle East & Africa"), "CA": ("Egypt", "Middle East & Africa"),
}
CRYPTO_QUOTES = {"USD", "USDT", "EUR", "GBP", "BTC", "ETH", "USDC", "JPY"}
ASSET_TYPES = ["equity", "etf", "crypto", "fx", "index", "future"]


def classify(ticker: str, has_sector: bool) -> tuple[str, str, str]:
    """(country, region, asset_type) from the ticker string and sector coverage."""

    t = str(ticker)
    last = t.rsplit("_", 1)[-1] if "_" in t else ""
    if t.startswith("^"):
        return "Global", "Global", "index"
    if t.endswith("=X") or t.endswith("_X"):
        return "Global", "Global", "fx"
    if t.endswith("=F") or t.endswith("_F"):
        return "Global", "Global", "future"
    if last in CRYPTO_QUOTES and "_" in t:
        return "Global", "Global", "crypto"
    if last in SUFFIX_MARKETS:
        country, region = SUFFIX_MARKETS[last]
        return country, region, "equity"
    return "US", "North America", "equity" if has_sector else "etf"


@lru_cache(maxsize=4)
def _stats(source: str, mtime: float, recent_days: int = 63) -> pd.DataFrame:
    """Per normalised ticker: last_close, adv (mean dollar volume over the last ``recent_days`` rows), first_date, last_date, n."""

    import polars as pl

    lf = pl.scan_parquet(source).select(["Ticker", "Date", "Close", "Volume"]).drop_nulls(["Ticker", "Date", "Close"])
    agg = (
        lf.sort(["Ticker", "Date"]).group_by("Ticker").agg(
            pl.col("Close").last().alias("last_close"),
            (pl.col("Close") * pl.col("Volume").fill_null(0)).tail(recent_days).mean().alias("adv"),
            pl.col("Date").first().alias("first_date"),
            pl.col("Date").last().alias("last_date"),
            pl.len().alias("n"),
        ).collect().to_pandas()
    )
    agg["ticker"] = agg["Ticker"].map(dl.normalize_symbol)
    agg = agg[agg["ticker"] != ""].drop(columns="Ticker")
    return agg.groupby("ticker").agg(last_close=("last_close", "last"), adv=("adv", "max"), first_date=("first_date", "min"), last_date=("last_date", "max"), n=("n", "sum"))


def ticker_table() -> pd.DataFrame:
    """One row per ticker with country, region, asset_type and the price/liquidity/age statistics."""

    source = dl._market_source()
    stats = _stats(str(source), source.stat().st_mtime if source.exists() else 0.0)
    sectors = dl.static_sectors()
    has_sector = set(sectors.index)
    meta = [classify(t, t in has_sector) for t in stats.index]
    out = stats.copy()
    out["country"], out["region"], out["asset_type"] = zip(*meta) if meta else ([], [], [])
    return out.sort_values("n", ascending=False)


def _id(country: str, asset: str) -> str:
    return f"{country.lower().replace(' ', '_')}.{asset}"


def list_universes() -> list[dict[str, Any]]:
    table = ticker_table()
    rows: list[dict[str, Any]] = [{"id": "us_equities", "label": "US equities", "region": "North America", "asset_type": "equity", "count": int(((table.country == "US") & (table.asset_type == "equity")).sum())}, {"id": "global", "label": "Everything in the file", "region": "Global", "asset_type": "all", "count": int(len(table))}]
    for (region, country, asset), g in table.groupby(["region", "country", "asset_type"]):
        rows.append({"id": _id(country, asset), "label": f"{country} {asset}" if country != "Global" else asset, "region": region, "asset_type": asset, "count": int(len(g))})
    for region, g in table.groupby("region"):
        rows.append({"id": f"region:{region.lower().replace(' ', '_').replace('&', 'and')}", "label": f"All of {region}", "region": region, "asset_type": "all", "count": int(len(g))})
    return rows


def _norm(values: Any) -> set[str]:
    if values is None or values == "":
        return set()
    if isinstance(values, str):
        values = [v for v in values.replace(";", ",").split(",")]
    return {str(v).strip().lower().replace(" ", "_").replace("&", "and") for v in values if str(v).strip()}


CONTROL_KEYS = ("universe_id", "regions", "asset_types", "min_price", "min_dollar_volume", "min_listing_months")


def has_controls(payload: dict[str, Any] | None) -> bool:
    return bool(payload) and any(payload.get(k) not in (None, "", []) for k in CONTROL_KEYS)


def select_symbols(payload: dict[str, Any], default_limit: int = 500, max_symbols: int = 5000, base: list[str] | None = None) -> list[str]:
    """Tickers matching universe_id, regions, asset_types and the price, liquidity and listing-age floors, coverage order, capped."""

    cap = max(1, min(int(payload.get("max_symbols") or payload.get("max_tickers") or default_limit or max_symbols), max_symbols))
    table = ticker_table()
    uid = str(payload.get("universe_id") or "").strip().lower()
    regions, assets = _norm(payload.get("regions")), _norm(payload.get("asset_types"))
    country = region_id = None
    if uid in {"", "global", "all"}:
        pass
    elif uid in {"us_equities", "us"}:
        country, assets = "us", assets or {"equity"}
    elif uid.startswith("region:"):
        region_id = uid.split(":", 1)[1]
    elif "." in uid:
        country, a = uid.split(".", 1)
        assets = assets or {a}
    else:
        raise ValueError(f"Unknown universe_id '{uid}'. See GET /universes.")
    keys = table.index
    mask = pd.Series(True, index=keys)
    if base is not None:
        mask &= keys.isin(base)
    if country:
        mask &= table["country"].str.lower().str.replace(" ", "_") == country
    if region_id:
        mask &= table["region"].str.lower().str.replace(" ", "_").str.replace("&", "and") == region_id
    if regions:
        key = table["region"].str.lower().str.replace(" ", "_").str.replace("&", "and")
        ctry = table["country"].str.lower().str.replace(" ", "_")
        mask &= key.isin(regions) | ctry.isin(regions)
    if assets:
        mask &= table["asset_type"].isin(assets)
    if payload.get("min_price") not in (None, ""):
        mask &= table["last_close"] >= float(payload["min_price"])
    if payload.get("min_dollar_volume") not in (None, ""):
        mask &= table["adv"] >= float(payload["min_dollar_volume"])
    if payload.get("min_listing_months") not in (None, ""):
        age = (table["last_date"].max() - table["first_date"]).dt.days / 30.4
        mask &= age >= float(payload["min_listing_months"])
    out = list(table.index[mask.to_numpy()])
    if not out:
        raise ValueError("No tickers match the universe filters. Loosen universe_id, regions, asset_types or the price, liquidity and listing-age floors.")
    return out[:cap]
