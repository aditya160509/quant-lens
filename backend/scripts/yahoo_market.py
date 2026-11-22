"""Yahoo daily market store: every ticker Yahoo lists, full history, split by asset class and country.

    python scripts/yahoo_market.py discover [--regions us,in] [--assets equity,etf,crypto,fx,future,index]
    python scripts/yahoo_market.py download [--assets ...] [--batch 100] [--limit N]
    python scripts/yahoo_market.py build
    python scripts/yahoo_market.py update            # daily: last 10 days for every ticker, merged in

Writes only under backend/data/market/ (the old market_universe.parquet is read, never changed):
    tickers.parquet                              one row per ticker: ticker, yahoo, name, asset, country, exchange, currency, source
    _staging/<asset>/<country>/<batch>.parquet   raw downloads, one file per batch (resume skips tickers already staged)
    asset=<asset>/country=<country>/data.parquet the store: date, ticker, OHLC, adj_close, volume, dividends, splits; float32, zstd, sorted

Rate limits: Yahoo publishes none. yf.download does not raise on HTTP 429; it records the error and returns empty columns.
So each batch is checked against yfinance's error list: a rate-limit hit waits (30 s, 2 min, 10 min, 30 min), halves the
batch and retries; a clean batch slowly grows it back. Delisted tickers ("no timezone", "no data") are marked and skipped.
"""

from __future__ import annotations

import argparse
import os
import re
import time
from pathlib import Path

import polars as pl
import yfinance as yf
import yfinance.shared as yfs

ROOT = Path(__file__).resolve().parents[1]
OLD = ROOT / "data" / "market_universe.parquet"
OUT = Path(
    os.environ.get("MARKET_DIR", ROOT / "data" / "market")
)  # MARKET_DIR: a scratch store for tests
TICKERS = OUT / "tickers.parquet"
STAGE = OUT / "_staging"
DEAD = OUT / "_staging" / "_no_data.txt"

# Exchange suffixes in the old file's names (SUZLON_NS -> SUZLON.NS) and Yahoo's suffix -> country.
SUFFIX_COUNTRY = {
    "NS": "in",
    "BO": "in",
    "KS": "kr",
    "KQ": "kr",
    "AX": "au",
    "SR": "sa",
    "TW": "tw",
    "TWO": "tw",
    "TA": "il",
    "JK": "id",
    "T": "jp",
    "HK": "hk",
    "DE": "de",
    "F": "de",
    "TO": "ca",
    "V": "ca",
    "BK": "th",
    "SI": "sg",
    "L": "gb",
    "ST": "se",
    "SA": "br",
    "NZ": "nz",
    "PA": "fr",
    "KL": "my",
    "HE": "fi",
    "MI": "it",
    "SS": "cn",
    "SZ": "cn",
    "MX": "mx",
    "SW": "ch",
    "JO": "za",
    "MC": "es",
    "AS": "nl",
    "BR": "be",
    "CO": "dk",
    "OL": "no",
    "VI": "at",
    "LS": "pt",
    "AT": "gr",
    "IS": "tr",
    "WA": "pl",
    "PR": "cz",
    "BD": "hu",
    "IR": "ie",
}
FX = [
    "USD",
    "EUR",
    "JPY",
    "GBP",
    "CHF",
    "CAD",
    "AUD",
    "NZD",
    "CNY",
    "HKD",
    "SGD",
    "SEK",
    "NOK",
    "DKK",
    "INR",
    "KRW",
    "TWD",
    "BRL",
    "MXN",
    "ZAR",
    "TRY",
    "RUB",
    "PLN",
    "HUF",
    "CZK",
    "ILS",
    "THB",
    "IDR",
    "MYR",
    "PHP",
    "SAR",
    "AED",
    "CLP",
    "COP",
    "PEN",
    "ARS",
    "EGP",
    "VND",
    "PKR",
    "KWD",
    "QAR",
    "NGN",
]
FUTURES = [
    "ES",
    "NQ",
    "YM",
    "RTY",
    "ZB",
    "ZN",
    "ZF",
    "ZT",
    "CL",
    "BZ",
    "NG",
    "RB",
    "HO",
    "GC",
    "SI",
    "HG",
    "PL",
    "PA",
    "ZC",
    "ZW",
    "ZS",
    "ZM",
    "ZL",
    "ZO",
    "KE",
    "CC",
    "KC",
    "SB",
    "CT",
    "OJ",
    "LBS",
    "LE",
    "HE",
    "GF",
    "DX",
    "6E",
    "6J",
    "6B",
    "6A",
    "6C",
    "6S",
    "6N",
    "6M",
    "BTC",
    "ETH",
    "MES",
    "MNQ",
    "MYM",
    "M2K",
    "MGC",
    "SIL",
    "VX",
]
INDICES = [
    "^GSPC",
    "^DJI",
    "^IXIC",
    "^NDX",
    "^RUT",
    "^NYA",
    "^XAX",
    "^VIX",
    "^MID",
    "^SP600",
    "^TNX",
    "^IRX",
    "^FVX",
    "^TYX",
    "^FTSE",
    "^GDAXI",
    "^FCHI",
    "^STOXX50E",
    "^N100",
    "^BFX",
    "^AEX",
    "^IBEX",
    "^SSMI",
    "^N225",
    "^HSI",
    "^000001.SS",
    "^399001.SZ",
    "^STI",
    "^AXJO",
    "^AORD",
    "^BSESN",
    "^NSEI",
    "^JKSE",
    "^KLSE",
    "^NZ50",
    "^KS11",
    "^TWII",
    "^GSPTSE",
    "^BVSP",
    "^MXX",
    "^IPSA",
    "^MERV",
    "^TA125.TA",
    "^JN0U.JO",
    "^CASE30",
    "^XDB",
    "^XDE",
    "^XDN",
    "^XDA",
    "^BKX",
    "^SOX",
    "^HSCE",
    "^SET.BK",
    "^PSI20",
    "^OMXC25",
    "^OMXS30",
    "^OMXH25",
    "^OSEAX",
    "^WIG20",
    "^BUX",
    "^ATX",
    "^SPGSCI",
    "^GVZ",
    "^OVX",
    "^VVIX",
    "^MOVE",
]
WAITS = (30, 120, 600, 1800)
COLS = {
    "Open": "open",
    "High": "high",
    "Low": "low",
    "Close": "close",
    "Adj Close": "adj_close",
    "Volume": "volume",
    "Dividends": "dividends",
    "Stock Splits": "splits",
}


def to_yahoo(ticker: str) -> str:
    """Old store name -> Yahoo symbol: _IDX_X -> ^X, BTC_USD -> BTC-USD, INVE_B_ST -> INVE-B.ST."""
    if ticker.startswith("_IDX_"):
        return "^" + ticker[5:]
    if re.search(r"[\^=]", ticker):
        return ticker
    head, sep, suf = ticker.rpartition("_")
    if sep and suf == "USD":
        return f"{head.replace('_', '-')}-USD"
    if sep and suf in SUFFIX_COUNTRY:
        return f"{head.replace('_', '-')}.{suf}"
    return ticker.replace("_", "-")


def to_ticker(yahoo: str) -> str:
    """Yahoo symbol -> store name, the old file's convention (dots and dashes become underscores; ^ and = kept)."""
    return yahoo if re.search(r"[\^=]", yahoo) else re.sub(r"[.\-]", "_", yahoo)


def classify(yahoo: str) -> tuple[str, str]:
    if yahoo.startswith("^"):
        return "index", "xx"
    if yahoo.endswith("=X"):
        return "fx", "xx"
    if yahoo.endswith("=F"):
        return "future", "xx"
    if re.search(r"-(USD|EUR|BTC|USDT)$", yahoo):
        return "crypto", "xx"
    suf = yahoo.rpartition(".")[2] if "." in yahoo else ""
    return "equity", SUFFIX_COUNTRY.get(suf, "us")


def _screen_all(query, label: str) -> list[dict]:
    """Page a screener query (250 a page; Yahoo serves at most 10,000 rows per query)."""
    rows, off = [], 0
    while True:
        try:
            r = (
                yf.screen(query, size=250, offset=off)
                if not isinstance(query, str)
                else yf.screen(query, count=250, offset=off)
            )
        except Exception as e:  # noqa: BLE001 - a failed page ends this query, the rest of discovery continues
            print(f"  {label}: stopped at {off} ({str(e)[:80]})")
            break
        quotes = r.get("quotes", [])
        new = [q for q in quotes if q.get("symbol") not in {x["symbol"] for x in rows}]
        rows += new
        off += 250
        if not new or off >= min(r.get("total", 0), 10_000):
            break
        time.sleep(0.3)
    return rows


def discover(regions: list[str] | None, assets: set[str]) -> None:
    from yfinance import EquityQuery, ETFQuery

    OUT.mkdir(parents=True, exist_ok=True)
    out: dict[str, dict] = {}

    def add(
        yahoo: str,
        source: str,
        name: str = "",
        exchange: str = "",
        currency: str = "",
        asset: str | None = None,
    ) -> None:
        a, c = classify(yahoo)
        out.setdefault(
            yahoo,
            {
                "ticker": to_ticker(yahoo),
                "yahoo": yahoo,
                "name": name,
                "asset": asset or a,
                "country": c,
                "exchange": exchange,
                "currency": currency,
                "source": source,
            },
        )

    if OLD.exists():  # everything we already hold keeps its old name
        for t in (
            pl.scan_parquet(OLD).select("Ticker").unique().collect()["Ticker"].to_list()
        ):
            y = to_yahoo(t)
            add(y, "old")
            out[y]["ticker"] = t
    valid = EquityQuery("eq", ["region", "us"]).valid_values
    for reg in regions or sorted(valid["region"]):
        for exch in sorted(valid["exchange"].get(reg, [])):
            if "equity" in assets:
                for q in _screen_all(
                    EquityQuery(
                        "and",
                        [
                            EquityQuery("eq", ["region", reg]),
                            EquityQuery("eq", ["exchange", exch]),
                        ],
                    ),
                    f"equity {reg}/{exch}",
                ):
                    add(
                        q["symbol"],
                        "screener",
                        q.get("longName") or q.get("shortName", ""),
                        q.get("exchange", ""),
                        q.get("currency", ""),
                        "equity",
                    )
                    out[q["symbol"]]["country"] = reg
            if "etf" in assets:
                for q in _screen_all(
                    ETFQuery(
                        "and",
                        [
                            ETFQuery("eq", ["region", reg]),
                            ETFQuery("eq", ["exchange", exch]),
                        ],
                    ),
                    f"etf {reg}/{exch}",
                ):
                    add(
                        q["symbol"],
                        "screener",
                        q.get("longName") or q.get("shortName", ""),
                        q.get("exchange", ""),
                        q.get("currency", ""),
                        "etf",
                    )
                    out[q["symbol"]]["country"] = reg
        print(f"{reg}: {len(out)} tickers so far")
    if "crypto" in assets:
        for q in _screen_all("all_cryptocurrencies_us", "crypto"):
            add(
                q["symbol"],
                "screener",
                q.get("shortName", ""),
                q.get("exchange", ""),
                q.get("currency", ""),
                "crypto",
            )
    if "fx" in assets:
        for a in FX:
            for b in FX:
                if a != b and (
                    a in ("USD", "EUR", "GBP", "JPY", "CHF")
                    or b in ("USD", "EUR", "GBP", "JPY")
                ):
                    add(f"{a}{b}=X", "built")
    if "future" in assets:
        for f in FUTURES:
            add(f"{f}=F", "built")
    if "index" in assets:
        for i in INDICES:
            add(i, "built")
    df = pl.DataFrame(list(out.values()))
    if (
        TICKERS.exists()
    ):  # keep tickers found earlier (a region run adds to the list, never shrinks it)
        df = pl.concat(
            [pl.read_parquet(TICKERS).filter(~pl.col("yahoo").is_in(df["yahoo"])), df],
            how="diagonal_relaxed",
        )
    df.write_parquet(TICKERS)
    print(df.group_by("asset", "country").len().sort("len", descending=True).head(30))
    print(f"{df.height} tickers -> {TICKERS}")


def _staged() -> set[str]:
    done = set(DEAD.read_text().split()) if DEAD.exists() else set()
    for f in STAGE.rglob("*.parquet"):
        done |= set(
            pl.scan_parquet(f).select("yahoo").unique().collect()["yahoo"].to_list()
        )
    return done


def _fetch(
    batch: list[str], period: str, start: str | None = None
) -> tuple[pl.DataFrame | None, bool, list[str]]:
    """One yf.download call (from `start` when given, else `period`). Returns (rows, rate_limited, tickers with no data)."""
    yfs._ERRORS.clear()
    raw = yf.download(
        batch,
        **({"start": start} if start else {"period": period}),
        interval="1d",
        auto_adjust=False,
        actions=True,
        group_by="ticker",
        threads=True,
        progress=False,
        timeout=30,
    )
    errs = dict(yfs._ERRORS)
    limited = any(
        re.search(r"Too Many Requests|Rate limit|429", str(m), re.IGNORECASE)
        for m in errs.values()
    )
    frames, empty = [], []
    for y in batch:
        try:
            d = (
                raw[y]
                if len(batch) > 1
                else raw.droplevel(0, axis=1)
                if raw.columns.nlevels > 1
                else raw
            )
        except KeyError:
            empty.append(y)
            continue
        d = d.dropna(subset=["Close"]) if "Close" in d else d.iloc[0:0]
        if d.empty:
            empty.append(y)
            continue
        d = d.rename(columns=COLS)
        frames.append(
            pl.from_pandas(d.reset_index())
            .rename({"Date": "date"})
            .with_columns(
                pl.lit(y).alias("yahoo"),
                *[pl.col(c).cast(pl.Float64) for c in COLS.values() if c in d.columns],
            )
        )
    rows = (
        pl.concat(
            [
                f.select(
                    ["date", "yahoo", *[c for c in COLS.values() if c in f.columns]]
                )
                for f in frames
            ],
            how="diagonal_relaxed",
        )
        if frames
        else None
    )
    return rows, limited, [] if limited else empty


def download(
    assets: set[str],
    batch: int,
    limit: int | None,
    period: str = "max",
    stage: Path = STAGE,
    since: pl.DataFrame | None = None,
) -> None:
    """Full history for tickers not staged yet; with `since` (yahoo, start), only the days from each ticker's start."""
    t = pl.read_parquet(TICKERS).filter(pl.col("asset").is_in(list(assets)))
    if since is not None:
        # One start per asset/country (the earliest), so a batch is one call, not one call per ticker.
        t = t.join(since, on="yahoo").with_columns(
            pl.col("start").min().over("asset", "country")
        )
    else:
        t = t.with_columns(pl.lit(None, pl.String).alias("start"))
    done = _staged() if since is None else set()
    todo = t.filter(~pl.col("yahoo").is_in(list(done)))
    if limit:
        todo = todo.head(limit)
    print(
        f"{todo.height} to fetch ({t.height - todo.height} already staged), period={period}"
    )
    size, n0, t0 = batch, 0, time.time()
    for (asset, country, start), grp in todo.group_by(
        ["asset", "country", "start"], maintain_order=True
    ):
        syms, i = grp["yahoo"].to_list(), 0
        while i < len(syms):
            chunk = syms[i : i + size]
            for wait in (0, *WAITS):
                if wait:
                    print(
                        f"  rate limited: waiting {wait}s, batch {size} -> {max(10, size // 2)}"
                    )
                    time.sleep(wait)
                    size = max(10, size // 2)
                    chunk = syms[i : i + size]
                rows, limited, empty = _fetch(chunk, period, start)
                if not limited:
                    break
            else:
                raise SystemExit(
                    "Still rate limited after 40 minutes of waiting; rerun later, staged batches are kept."
                )
            if rows is not None:
                d = stage / asset / country
                d.mkdir(parents=True, exist_ok=True)
                rows.write_parquet(
                    d / f"{int(time.time() * 1000)}.parquet", compression="zstd"
                )
            if empty and since is None:
                with DEAD.open("a") as f:
                    f.write("\n".join(empty) + "\n")
            i += len(chunk)
            n0 += len(chunk)
            size = min(batch, size + 10)  # earn the batch size back after clean calls
            rate = n0 / max(1e-9, time.time() - t0)
            print(
                f"  {asset}/{country}: {i}/{len(syms)}  total {n0}/{todo.height}  {rate:.1f} tickers/s  eta {(todo.height - n0) / max(rate, 1e-9) / 60:.0f} min"
            )
            time.sleep(0.5)


def build(stage: Path = STAGE) -> None:
    """Staged batches (and, for tickers Yahoo no longer serves, the old file's rows) -> one sorted float32 file per asset/country."""
    names = pl.read_parquet(TICKERS).select("yahoo", "ticker", "asset", "country")
    f32 = ["open", "high", "low", "close", "adj_close", "dividends", "splits"]
    for d in sorted(
        p for p in stage.glob("*/*") if p.is_dir() and any(p.glob("*.parquet"))
    ):
        asset, country = d.parent.name, d.name
        df = (
            pl.scan_parquet(str(d / "*.parquet"))
            .with_columns(pl.col("date").cast(pl.Date))
            .join(names.lazy().select("yahoo", "ticker"), on="yahoo", how="left")
            .unique(["ticker", "date"], keep="last", maintain_order=True)
            .filter(pl.col("close").is_finite() & (pl.col("close") > 0))
            .with_columns(
                [pl.col(c).cast(pl.Float32) for c in f32]
                + [pl.col("volume").cast(pl.Float64)]
            )
            .select(
                "date",
                "ticker",
                "open",
                "high",
                "low",
                "close",
                "adj_close",
                "volume",
                "dividends",
                "splits",
            )
            .sort("ticker", "date")
            .collect()
        )
        dest = OUT / f"asset={asset}" / f"country={country}" / "data.parquet"
        dest.parent.mkdir(parents=True, exist_ok=True)
        tmp = dest.with_suffix(".tmp")
        df.write_parquet(
            tmp,
            compression="zstd",
            compression_level=6,
            statistics=True,
            row_group_size=250_000,
        )
        tmp.replace(dest)  # atomic swap: a reader never sees half a file
        print(
            f"{asset}/{country}: {df['ticker'].n_unique()} tickers, {df.height} rows, {dest.stat().st_size / 2**20:.1f} MB"
        )
    # Delisted names: Yahoo dropped them, the old file still has their history.
    if OLD.exists() and DEAD.exists():
        dead_old = names.filter(pl.col("yahoo").is_in(DEAD.read_text().split()))
        if dead_old.height:
            old = (
                pl.scan_parquet(OLD)
                .filter(pl.col("Ticker").is_in(dead_old["ticker"].to_list()))
                .select(
                    pl.col("Date").cast(pl.Date).alias("date"),
                    pl.col("Ticker").alias("ticker"),
                    *[
                        pl.col(c.title()).cast(pl.Float32).alias(c)
                        for c in ["open", "high", "low", "close"]
                    ],
                    pl.col("Volume").alias("volume"),
                    pl.col("Close").cast(pl.Float32).alias("adj_close"),
                    pl.lit(0.0, pl.Float32).alias("dividends"),
                    pl.lit(0.0, pl.Float32).alias("splits"),
                )
                .select(
                    "date",
                    "ticker",
                    "open",
                    "high",
                    "low",
                    "close",
                    "adj_close",
                    "volume",
                    "dividends",
                    "splits",
                )
                .sort("ticker", "date")
                .collect()
            )
            dest = OUT / "asset=delisted" / "country=xx" / "data.parquet"
            dest.parent.mkdir(parents=True, exist_ok=True)
            old.write_parquet(dest, compression="zstd", compression_level=6)
            print(
                f"delisted (old rows kept): {old['ticker'].n_unique()} tickers, {old.height} rows"
            )


def update(assets: set[str], batch: int) -> None:
    """Daily: each stored ticker fetches only from its last stored date (minus 5 days, so late corrections land), new tickers
    fetch full history, then rebuild (duplicates keep the newest download)."""
    files = list(OUT.glob("asset=*/country=*/data.parquet"))
    if not files:
        raise SystemExit("No store yet: run download and build first.")
    last = (
        pl.scan_parquet([str(f) for f in files])
        .group_by("ticker")
        .agg(pl.col("date").max())
        .collect()
    )
    since = (
        pl.read_parquet(TICKERS)
        .select("yahoo", "ticker")
        .join(last, on="ticker")
        .select(
            "yahoo",
            (pl.col("date") - pl.duration(days=5))
            .dt.strftime("%Y-%m-%d")
            .alias("start"),
        )
    )
    download(assets, batch, None, since=since)
    download(assets, batch, None)  # tickers discovered since the last run: full history
    build()


def _self_check() -> None:
    assert (
        to_yahoo("SUZLON_NS") == "SUZLON.NS"
        and to_yahoo("INVE_B_ST") == "INVE-B.ST"
        and to_yahoo("CCL_B_TO") == "CCL-B.TO"
    )
    assert (
        to_yahoo("BTC_USD") == "BTC-USD"
        and to_yahoo("_IDX_TWII") == "^TWII"
        and to_yahoo("EURUSD=X") == "EURUSD=X"
        and to_yahoo("BRK_B") == "BRK-B"
    )
    assert to_ticker("SUZLON.NS") == "SUZLON_NS" and to_ticker("^GSPC") == "^GSPC"
    assert (
        classify("RELIANCE.NS") == ("equity", "in")
        and classify("BTC-USD")[0] == "crypto"
        and classify("CL=F")[0] == "future"
    )


if __name__ == "__main__":
    _self_check()
    ap = argparse.ArgumentParser()
    ap.add_argument("cmd", choices=["discover", "download", "build", "update"])
    ap.add_argument("--regions", default="")
    ap.add_argument("--assets", default="equity,etf,crypto,fx,future,index")
    ap.add_argument("--batch", type=int, default=100)
    ap.add_argument("--limit", type=int, default=None)
    a = ap.parse_args()
    assets = set(a.assets.split(","))
    if a.cmd == "discover":
        discover([r for r in a.regions.split(",") if r] or None, assets)
    elif a.cmd == "download":
        download(assets, a.batch, a.limit)
    elif a.cmd == "build":
        build()
    else:
        update(assets, a.batch)
