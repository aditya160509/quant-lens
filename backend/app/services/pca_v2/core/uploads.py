"""Validated PCA CSV uploads; clients use opaque ids, never server paths."""
from pathlib import Path
from io import BytesIO
import uuid
import numpy as np
import pandas as pd
from .data_loader import BACKEND_DATA, normalize_symbol

UPLOAD_DIR = BACKEND_DATA / "pca_v2" / "uploads"
REQUIRED = {"returns": {"date", "ticker", "return"}, "weights": {"ticker", "weight"}, "groups": {"ticker", "group"}}


def validate_frame(frame, kind):
    if kind not in REQUIRED:
        raise ValueError("Upload kind must be returns, weights or groups")
    frame = frame.copy()
    frame.columns = [str(c).strip().lower() for c in frame.columns]
    missing = REQUIRED[kind] - set(frame.columns)
    if missing or frame.empty:
        raise ValueError(f"Missing columns {sorted(missing)} or empty upload")
    frame["ticker"] = frame["ticker"].map(normalize_symbol)
    if frame["ticker"].eq("").any():
        raise ValueError("Empty ticker")
    if kind == "returns":
        frame["date"] = pd.to_datetime(frame["date"], errors="raise")
        if frame.duplicated(["date", "ticker"]).any():
            raise ValueError("Duplicate ticker/date rows")
    elif frame["ticker"].duplicated().any():
        raise ValueError("Duplicate ticker rows")
    numeric = "return" if kind == "returns" else "weight" if kind == "weights" else None
    if numeric:
        frame[numeric] = pd.to_numeric(frame[numeric], errors="raise")
        if not np.isfinite(frame[numeric]).all():
            raise ValueError("Values must be finite")
    elif frame["group"].isna().any():
        raise ValueError("Groups must be nonempty")
    return frame


def save_upload(raw, kind):
    frame = validate_frame(pd.read_csv(BytesIO(raw)), kind)
    UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
    upload_id = f"{kind}_{uuid.uuid4().hex}.csv"
    frame.to_csv(UPLOAD_DIR / upload_id, index=False)
    return {"upload_id": upload_id, "kind": kind, "rows": len(frame), "columns": list(frame.columns)}


def read_upload(upload_id, kind):
    if not isinstance(upload_id, str) or Path(upload_id).name != upload_id or not upload_id.startswith(kind + "_") or not upload_id.endswith(".csv"):
        raise ValueError("Invalid upload id")
    path = (UPLOAD_DIR / upload_id).resolve()
    if path.parent != UPLOAD_DIR.resolve() or not path.is_file():
        raise ValueError("Unknown upload id")
    return validate_frame(pd.read_csv(path), kind)


def resolve_payload(payload):
    payload = dict(payload)
    for kind in ("weights", "groups"):
        upload_id = payload.get(kind + "_upload_id")
        if upload_id:
            frame = read_upload(upload_id, kind)
            value = "weight" if kind == "weights" else "group"
            payload[kind] = dict(zip(frame.ticker, frame[value]))
    return payload
