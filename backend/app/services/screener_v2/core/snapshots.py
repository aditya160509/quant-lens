"""Dated raw-feature snapshots (plan D03, D04, §4.3).

Ticker-local technical and fundamental features are stored once per date in Parquet;
percentiles, scores and ranks are computed per request over the chosen universe and never
stored. A name missing from a date's snapshot takes the bounded fallback: the existing
feature code runs for the missing names only, and the result is labelled as computed.
"""
from __future__ import annotations

import fcntl
import hashlib
import json
import os
import re
from pathlib import Path

import pandas as pd
import polars as pl
import pyarrow as pa
import pyarrow.compute as pc
import pyarrow.parquet as pq

from . import data_loader
from .data_loader import AS_OF, normalize_symbol
from .performance import _market_rows, _path_version

# D08: every date re-seeds EMA and Wilder smoothing at the start of its own N-session window,
# so outputs equal the per-date computation. Continuous-history state would need a new version.
ALGORITHM_VERSION = "bounded-window-v1"
STORE: Path | None = data_loader.BACKEND_DATA / "screener_v2" / "features"  # None: compute every time
TECHNICAL_PERIOD_KEYS = ("rsi_period", "stochastic_period", "stochastic_d_period", "adx_period", "atr_period", "bollinger_period",
                         "bollinger_std_multiple", "macd_fast_period", "macd_slow_period", "macd_signal_period", "cross_lookback_days")


def store_key(kind: str, lookback: int | None = None, periods: dict | None = None) -> str:
    """Everything a stored raw value depends on: sources, algorithm, calendar, instruments, window settings."""
    from .currency import CONFIG
    config = CONFIG.get()
    sources = [data_loader.MARKET_UNIVERSE, data_loader.MASTER_FUNDAMENTALS, data_loader.FX_DAILY, data_loader.FF5_DAILY,
               data_loader.MOM_DAILY, data_loader.MASTER_FUNDAMENTALS.parent / "company_names.parquet"]
    spec = {
        "algorithm": ALGORITHM_VERSION, "kind": kind,
        "sources": {str(path): _path_version(path) for path in sources},
        "calendar_ticker": config.get("calendar_ticker"), "explicit_calendar": config.get("explicit_calendar"),
        "instruments": config.get("instruments"), "lookback": lookback,
        "periods": {key: (periods or {}).get(key) for key in TECHNICAL_PERIOD_KEYS} if kind == "technical" else None,
    }
    return hashlib.sha256(json.dumps(spec, sort_keys=True, default=str).encode()).hexdigest()[:24]


def _date_tag(*parts) -> str:
    text = "__".join("none" if part is None or (not isinstance(part, str) and pd.isna(part)) else str(pd.Timestamp(part).date()) for part in parts)
    return re.sub(r"[^0-9a-z_-]", "", text)


def _path(key: str, tag: str) -> Path:
    return STORE / key / f"{tag}.parquet"


PACK_NAME = "_pack.arrow"
PACK_STALE = 50  # rebuild the pack once this many date files are newer than it
_IPC = pa.ipc.IpcWriteOptions(compression="lz4")
_packs: dict[str, tuple[int, dict[str, tuple[int, pd.DataFrame]]]] = {}


def _frames(entries: dict[str, tuple[int, bytes]]) -> dict[str, tuple[int, pd.DataFrame]]:
    """Decode every packed date and convert to pandas once per schema; per-date conversion was most of the read cost."""
    groups: dict[pa.Schema, list[tuple[str, pa.Table]]] = {}
    for tag, (_, data) in entries.items():
        table = pa.ipc.open_file(pa.py_buffer(data)).read_all()
        groups.setdefault(table.schema, []).append((tag, table))
    out: dict[str, tuple[int, pd.DataFrame]] = {}
    for items in groups.values():
        whole = pa.concat_tables([t for _, t in items]).to_pandas()
        start = 0
        for tag, table in items:
            out[tag] = (entries[tag][0], whole.iloc[start:start + table.num_rows].reset_index(drop=True))
            start += table.num_rows
    return out


def _pack(key: str) -> dict[str, tuple[int, pd.DataFrame]]:
    """Every date file of a key in one memory-mapped Arrow file: tag -> (source mtime_ns, Arrow IPC bytes).

    A backtest reads one small file per date (about 1,200); one mapped file replaces those opens and the
    parquet decodes. Date files stay the source of truth: an entry whose file changed is ignored.
    """
    folder = STORE / key
    pack_path = folder / PACK_NAME
    try:
        mtime = pack_path.stat().st_mtime_ns
    except FileNotFoundError:
        mtime = -1
    cached = _packs.get(key)
    if cached and cached[0] == mtime:
        return cached[1]
    entries: dict[str, tuple[int, bytes]] = {}
    if mtime >= 0:
        table = pa.ipc.open_file(pa.memory_map(str(pack_path))).read_all()
        entries = dict(zip(table["tag"].to_pylist(), zip(table["mtime_ns"].to_pylist(), table["data"].to_pylist())))
    files = {f.stem: f for f in folder.glob("*.parquet")}
    stale = [tag for tag, f in files.items() if tag not in entries or entries[tag][0] != f.stat().st_mtime_ns]
    if len(stale) >= PACK_STALE:
        entries = {tag: entries[tag] for tag in files if tag not in stale}
        for tag in stale:
            sink = pa.BufferOutputStream()
            table = pq.ParquetFile(files[tag]).read()
            with pa.ipc.new_file(sink, table.schema, options=_IPC) as writer:
                writer.write_table(table)
            entries[tag] = (files[tag].stat().st_mtime_ns, sink.getvalue().to_pybytes())
        packed = pa.table({"tag": list(entries), "mtime_ns": pa.array([v[0] for v in entries.values()], pa.int64()),
                           "data": pa.array([v[1] for v in entries.values()], pa.large_binary())})
        temporary = pack_path.with_suffix(f".{os.getpid()}.tmp")
        with pa.OSFile(str(temporary), "wb") as sink, pa.ipc.new_file(sink, packed.schema) as writer:
            writer.write_table(packed)
        os.replace(temporary, pack_path)
        mtime = pack_path.stat().st_mtime_ns
    _packs[key] = (mtime, _frames(entries))
    return _packs[key][1]


def read(key: str, tag: str, tickers: list[str]) -> pd.DataFrame:
    """Rows for these tickers from one date's snapshot; reads nothing else."""
    if STORE is None or not _path(key, tag).exists():
        return pd.DataFrame()
    path = _path(key, tag)
    entry = _pack(key).get(tag)
    if entry and entry[0] == path.stat().st_mtime_ns:
        frame = entry[1]
        return frame[frame["ticker"].isin(tickers).to_numpy()].reset_index(drop=True)
    table = pq.ParquetFile(path).read()  # date files are small; the dataset layer behind filters cost 3x the read
    return table.filter(pc.is_in(table["ticker"], value_set=pa.array(list(tickers), type=table.schema.field("ticker").type))).to_pandas()


def write(key: str, tag: str, rows: pd.DataFrame) -> None:
    """Merge rows into a date's snapshot: temporary file then atomic rename, under a file lock."""
    if STORE is None:
        return
    path = _path(key, tag)
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path.with_suffix(".lock"), "w") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        if path.exists():
            old = pq.read_table(path).to_pandas()
            rows = pd.concat([old[~old.ticker.isin(rows.ticker)], rows], ignore_index=True)
        temporary = path.with_suffix(f".{os.getpid()}.tmp")
        pq.write_table(pa.Table.from_pandas(rows, preserve_index=False), temporary)
        os.replace(temporary, path)


def last_observation_dates(tickers: list[str]) -> pd.Series:
    """Each ticker's last quote date at the active cutoff; inside a backtest the run's memoized rows are reused."""
    frame = _market_rows(tuple(tickers), AS_OF.get()).select(["Ticker", "Date"]).with_columns(data_loader.NORMALIZED_TICKER)
    if AS_OF.get() is not None:
        frame = frame.filter(pl.col("Date") <= pd.Timestamp(AS_OF.get()))
    last = frame.group_by("Ticker").agg(pl.col("Date").max()).collect()
    return pd.Series(pd.DatetimeIndex(last["Date"].to_list()), index=last["Ticker"].to_list(), dtype="datetime64[us]").reindex(tickers)


def _technical(requested: list[str], lookback: int, payload: dict) -> tuple[pd.DataFrame, pd.Series, list[str]]:
    from .estimators import raw_technical_features
    names = list(dict.fromkeys([*requested, "SPY"]))
    key, tag = store_key("technical", lookback, payload), _date_tag(payload.get("as_of_date"), AS_OF.get())
    # Status (computed, has prices, last quote date) lives apart so absent names cannot turn int columns float.
    status = read(key, f"{tag}_status", names)
    stored = read(key, tag, names)
    known = set(status.ticker) if len(status) else set()
    missing = [name for name in names if name not in known]
    if missing:
        raw = raw_technical_features(missing, lookback, payload)
        fresh = raw[raw.index.isin(missing)] if not raw.empty and "ticker" in raw else pd.DataFrame(columns=["ticker"])
        computed = set(fresh.ticker)
        fresh_status = pd.DataFrame({"ticker": missing, "present": [name in computed for name in missing],
                                     "last_date": last_observation_dates(missing).to_numpy()})
        if len(fresh):
            write(key, tag, fresh)
        write(key, f"{tag}_status", fresh_status)
        stored = pd.concat([stored, fresh], ignore_index=True) if len(stored) else fresh.reset_index(drop=True)
        status = pd.concat([status, fresh_status], ignore_index=True) if len(status) else fresh_status
    present = stored.sort_values("ticker").set_index("ticker", drop=False).rename_axis(None)
    return present, status.set_index("ticker")["last_date"], missing


def _fundamental(symbols: list[str], payload: dict, last_dates: pd.Series) -> tuple[pd.DataFrame, list[str]]:
    from .fundamentals import raw_fundamental_features
    as_of_date = payload.get("as_of_date")
    cutoff = pd.Timestamp(as_of_date) if as_of_date else AS_OF.get()
    if cutoff is None:  # same rule as fundamental_cutoff: the requested names' latest quote
        observed = last_dates.reindex([normalize_symbol(s) for s in symbols]).dropna()
        cutoff = pd.Timestamp(observed.max()) if len(observed) else pd.Timestamp.today().normalize()
    key, tag = store_key("fundamental"), _date_tag(as_of_date, AS_OF.get(), cutoff)
    stored = read(key, tag, symbols)
    known = set(stored.ticker) if len(stored) else set()
    missing = [s for s in symbols if s not in known]
    if missing:
        fresh = raw_fundamental_features(missing, as_of_date, cutoff)
        write(key, tag, fresh)
        stored = pd.concat([stored, fresh], ignore_index=True) if not stored.empty else fresh
    return stored.set_index("ticker", drop=False).reindex(symbols).reset_index(drop=True), missing


def raw_panel_inputs(symbols: list[str], lookback: int, payload: dict):
    """Raw technical rows (requested names plus SPY), raw fundamental rows, latest quote date, and the source label."""
    requested = [normalize_symbol(s) for s in symbols]
    tech, last_dates, tech_missing = _technical(requested, lookback, payload)
    fund, fund_missing = _fundamental(symbols, payload, last_dates)
    observed = last_dates.reindex(list(dict.fromkeys([*requested, "SPY"]))).dropna()
    latest = pd.Timestamp(observed.max()) if len(observed) else None
    computed = len(set(tech_missing) | set(fund_missing))
    source = "snapshot" if not computed else f"computed for {computed} names (snapshot fallback), now stored"
    return tech, fund, latest, source
