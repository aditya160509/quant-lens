"""Content-addressed, size-capped observed implied-volatility uploads."""

from __future__ import annotations
from functools import lru_cache
from io import BytesIO
import hashlib
import re
import pandas as pd
from . import data_loader

MAX_BYTES = 2 * 1024 * 1024
REQUIRED = {"date", "asset", "implied_vol", "maturity_days", "source"}


def upload_directory():
    return data_loader.BACKEND_DATA / "volatility_v2/uploads"


def save_upload(raw, kind):
    if kind != "implied_volatility":
        raise ValueError("Supported upload kind: implied_volatility")
    if not raw or len(raw) > MAX_BYTES:
        raise ValueError("Uploads must contain at most 2 MB of CSV data")
    try:
        frame = pd.read_csv(BytesIO(raw))
    except (pd.errors.ParserError, UnicodeDecodeError, pd.errors.EmptyDataError) as exc:
        raise ValueError("Invalid UTF-8 CSV") from exc
    if set(frame.columns) != REQUIRED or frame.empty:
        raise ValueError(
            "CSV requires exactly date, asset, implied_vol, maturity_days, source columns"
        )
    frame["date"] = pd.to_datetime(frame.date, errors="raise")
    if (
        frame.date.isna().any()
        or (frame.date != frame.date.dt.normalize()).any()
        or frame.date.dt.tz is not None
    ):
        raise ValueError("IV dates must be timezone-naive daily observation dates")
    frame["implied_vol"] = pd.to_numeric(frame.implied_vol, errors="raise")
    frame["maturity_days"] = pd.to_numeric(frame.maturity_days, errors="raise")
    if not frame.implied_vol.between(0.00001, 10).all():
        raise ValueError(
            "implied_vol must be a positive annualized decimal, not percent points"
        )
    if not frame.maturity_days.isin([30, 90, 180]).all():
        raise ValueError("maturity_days must be 30, 90, or 180")
    if (
        frame.asset.isna().any()
        or frame.source.isna().any()
        or frame.source.astype(str).str.strip().eq("").any()
    ):
        raise ValueError("Every IV row requires an observed asset and source")
    frame["asset"] = [data_loader.resolve_symbols([asset])[0] for asset in frame.asset]
    if frame.duplicated(["date", "asset", "maturity_days"]).any():
        raise ValueError("Duplicate IV date/asset/maturity observations")
    frame = frame.sort_values(["asset", "maturity_days", "date"])
    encoded = frame.to_csv(index=False, date_format="%Y-%m-%d").encode()
    identifier = hashlib.sha256(encoded).hexdigest()
    directory = upload_directory()
    directory.mkdir(parents=True, exist_ok=True)
    path = directory / f"{identifier}.csv"
    if not path.exists():
        temporary = path.with_suffix(".tmp")
        temporary.write_bytes(encoded)
        temporary.replace(path)
    return {
        "status": "ok",
        "upload_id": identifier,
        "kind": kind,
        "rows": len(frame),
        "assets": sorted(frame.asset.unique().tolist()),
        "units": "annualized decimal implied volatility",
        "maturities": sorted(frame.maturity_days.unique().tolist()),
    }


def upload_path(identifier):
    if not isinstance(identifier, str) or not re.fullmatch("[0-9a-f]{64}", identifier):
        raise ValueError("Invalid upload identifier")
    path = upload_directory() / f"{identifier}.csv"
    if not path.is_file():
        raise ValueError("Unknown implied-volatility upload")
    return path


@lru_cache(maxsize=4)
def _read(version):
    return pd.read_csv(version[0], parse_dates=["date"])


def load_implied_volatility(identifier, asset):
    frame = _read(data_loader.file_version(upload_path(identifier))).copy()
    frame = frame.loc[frame.asset.eq(asset)]
    if frame.empty:
        raise ValueError(f"IV upload has no observations for {asset}")
    end = data_loader.cutoff()
    if end is not None:
        frame = frame.loc[frame.date <= end]
    return frame
