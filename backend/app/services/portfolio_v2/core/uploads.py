"""Content-addressed, validated CSV datasets in a module-owned sandbox."""

import hashlib
import io
import json
import re
import os
import tempfile
import numpy as np
import pandas as pd
from .data_loader import BACKEND_DATA

ROOT = BACKEND_DATA / "portfolio_v2/uploads"
MAX_BYTES = 2 * 1024 * 1024
KINDS = {
    "strategy_returns",
    "factor_returns",
    "signal_scores",
    "strategy_trades",
    "peer_portfolios",
}


def upload_path(identifier):
    if not re.fullmatch(r"[a-f0-9]{64}", identifier or ""):
        raise ValueError("Invalid upload identifier")
    path = ROOT / f"{identifier}.json"
    if path.is_symlink() or path.resolve().parent != ROOT.resolve():
        raise ValueError("Upload escapes sandbox")
    if not path.exists():
        raise KeyError("Unknown upload")
    return path


def validate_records(records, kind):
    frame = pd.DataFrame(records)
    if frame.empty:
        raise ValueError("Empty upload")
    if kind == "peer_portfolios":
        if not {"peer", "ticker", "weight"} <= set(frame):
            raise ValueError("Peer CSV requires peer,ticker,weight")
        if frame.duplicated(["peer", "ticker"]).any():
            raise ValueError("Duplicate peer/ticker")
        frame.weight = pd.to_numeric(frame.weight, errors="raise")
        if not np.isfinite(frame.weight).all() or (frame.weight < 0).any():
            raise ValueError("Peer weights must be finite and long-only")
        out = {name: dict(zip(g.ticker, g.weight)) for name, g in frame.groupby("peer")}
        if any(not np.isclose(sum(w.values()), 1) for w in out.values()):
            raise ValueError("Each peer book must sum to one")
        return out
    if "date" not in frame:
        raise ValueError("CSV requires a date column")
    frame.date = pd.to_datetime(frame.date, errors="raise")
    if kind == "strategy_trades":
        if not {"asset", "strategy", "trade_weight"} <= set(frame):
            raise ValueError("Strategy trades require date,asset,strategy,trade_weight")
        if (
            frame.duplicated(["date", "asset", "strategy"]).any()
            or frame.date.isna().any()
        ):
            raise ValueError("Duplicate or missing strategy trade identifiers")
        frame.trade_weight = pd.to_numeric(frame.trade_weight, errors="raise")
        if not np.isfinite(frame.trade_weight).all():
            raise ValueError("Strategy trades must be finite")
        frame.date = frame.date.dt.strftime("%Y-%m-%d")
        return frame.sort_values("date").to_dict("records")

    if frame.date.isna().any() or frame.date.duplicated().any():
        raise ValueError("Duplicate or missing dates")
    if frame.date.dt.tz is not None:
        raise ValueError("Date must not contain timezone")
    if len(frame.columns) < 2:
        raise ValueError("CSV requires at least one observed series")
    values = frame.drop(columns="date").apply(pd.to_numeric, errors="raise")
    if not np.isfinite(values).all().all():
        raise ValueError("Observed series must be finite")
    if kind in {"strategy_returns", "factor_returns"} and (values <= -1).any().any():
        raise ValueError("Returns must be decimal simple returns above -1")
    frame[values.columns] = values
    frame = frame.sort_values("date")
    frame.date = frame.date.dt.strftime("%Y-%m-%d")
    return frame.to_dict("records")


def save_upload(raw, kind):
    if kind not in KINDS:
        raise ValueError("Unsupported upload kind")
    if len(raw) > MAX_BYTES:
        raise ValueError("Upload exceeds 2 MB")
    frame = pd.read_csv(io.BytesIO(raw))
    value = validate_records(frame.to_dict("records"), kind)
    identifier = hashlib.sha256(kind.encode() + b"\0" + raw).hexdigest()
    ROOT.mkdir(parents=True, exist_ok=True)
    path = ROOT / f"{identifier}.json"
    if path.is_symlink():
        raise ValueError("Unsafe upload destination")
    descriptor, temporary = tempfile.mkstemp(prefix="upload-", suffix=".tmp", dir=ROOT)
    try:
        with os.fdopen(descriptor, "w") as stream:
            stream.write(json.dumps({"kind": kind, "value": value}, allow_nan=False))
        os.replace(temporary, path)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)
    return {"upload_id": identifier, "kind": kind, "rows": len(frame)}


def load_upload(identifier):
    data = json.loads(upload_path(identifier).read_text())
    if data["kind"] not in KINDS:
        raise ValueError("Unsupported persisted upload")
    return data["kind"], data["value"]
