"""Validated opaque holdings and logo uploads; no browser-supplied file paths."""

from io import BytesIO
import re
import uuid
import pandas as pd
from PIL import Image
from .data_loader import BACKEND_DATA, parse_symbols

UPLOADS = BACKEND_DATA / "factors_v2/uploads"


def save_upload(raw, kind):
    UPLOADS.mkdir(parents=True, exist_ok=True)
    identifier = uuid.uuid4().hex
    if kind == "holdings":
        frame = pd.read_csv(BytesIO(raw))
        if set(frame) != {"ticker", "weight"} or frame.empty or len(frame) > 5000:
            raise ValueError("Holdings CSV requires only ticker,weight and 1-5000 rows")
        frame.ticker = frame.ticker.astype(str).str.upper().str.strip()
        if frame.ticker.duplicated().any():
            raise ValueError("Duplicate ticker holdings")
        parse_symbols(frame.ticker.tolist())
        frame.weight = pd.to_numeric(frame.weight, errors="raise")
        import numpy as np

        if not np.isfinite(frame.weight).all() or frame.weight.abs().sum() == 0:
            raise ValueError("Holdings weights must be finite and nonzero")
        frame.to_csv(UPLOADS / f"{identifier}.csv", index=False)
    elif kind == "logo":
        image = Image.open(BytesIO(raw))
        if image.width > 4096 or image.height > 4096:
            raise ValueError("Logo dimensions exceed 4096 pixels")
        image.load()
        image.convert("RGBA").save(UPLOADS / f"{identifier}.png")
    else:
        raise ValueError("Supported upload kinds: holdings, logo")
    return {"upload_id": identifier, "kind": kind}


def resolve_id(identifier, suffix):
    if not re.fullmatch("[a-f0-9]{32}", str(identifier)):
        raise ValueError("Invalid upload id")
    path = UPLOADS / f"{identifier}.{suffix}"
    if not path.is_file():
        raise ValueError("Unknown upload id")
    return path


def resolve_payload(payload):
    out = dict(payload)
    if out.get("holdings_upload_id"):
        out["holdings"] = pd.read_csv(
            resolve_id(out["holdings_upload_id"], "csv")
        ).to_dict("records")
    if out.get("logo_upload_id"):
        resolve_id(out["logo_upload_id"], "png")
    return out
