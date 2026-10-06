"""Secure CSV uploads for ML V2 (returns, predictions, trial matrix, feature panel).

Posture: CSV text only, parsed by pandas (no pickle, eval or Excel), size/row/column caps, column-name
whitelist, formula-injection rejection, point-in-time checks. Parsed frames live in process memory under a
random uuid with a TTL and a per-process cap; no user-supplied path is ever written.
"""
from __future__ import annotations

import io
import re
import threading
import time
import uuid
from dataclasses import dataclass, field
from typing import Any

import numpy as np
import pandas as pd

MAX_BYTES = 10 * 1024 * 1024
MAX_ROWS = 250_000
MAX_COLUMNS = 200
TTL_SECONDS = 24 * 3600
MAX_STORED = 64
KINDS = ("returns", "predictions", "trial_matrix", "feature_panel")

COLUMN_RE = re.compile(r"^[a-z][a-z0-9_]{0,63}$")
TICKER_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._^=-]{0,19}$")
FORMULA_LEAD = ("=", "+", "-", "@")
ANOMALY_MOVE = 0.40


class UploadError(ValueError):
    """Validation failure; `status` is the HTTP status the API should return."""

    def __init__(self, message: str, status: int = 422):
        super().__init__(message)
        self.status = status


@dataclass
class StoredUpload:
    upload_id: str
    kind: str
    frame: pd.DataFrame
    summary: dict[str, Any]
    expires: float = field(default_factory=lambda: time.time() + TTL_SECONDS)


_STORE: dict[str, StoredUpload] = {}
_LOCK = threading.Lock()


def _evict(now: float) -> None:
    for key in [k for k, v in _STORE.items() if v.expires <= now]:
        del _STORE[key]


def put_upload(kind: str, frame: pd.DataFrame, summary: dict[str, Any]) -> StoredUpload:
    now = time.time()
    with _LOCK:
        _evict(now)
        if len(_STORE) >= MAX_STORED:
            raise UploadError("Upload store is full; try again later", 429)
        item = StoredUpload(uuid.uuid4().hex, kind, frame, summary)
        _STORE[item.upload_id] = item
    return item


def get_upload(upload_id: str, kinds: tuple[str, ...] | None = None) -> StoredUpload:
    if not isinstance(upload_id, str) or not re.fullmatch(r"[0-9a-f]{32}", upload_id):
        raise ValueError("upload_id is malformed")
    with _LOCK:
        _evict(time.time())
        item = _STORE.get(upload_id)
    if item is None:
        raise ValueError("Unknown or expired upload_id (uploads live 24 hours)")
    if kinds and item.kind not in kinds:
        raise ValueError(f"upload_id is a {item.kind} upload; expected one of {list(kinds)}")
    return item


def _clean_columns(columns: list[str]) -> list[str]:
    out = []
    for raw in columns:
        name = re.sub(r"\s+", "_", str(raw).strip().lower())
        if not COLUMN_RE.fullmatch(name):
            raise UploadError(f"Column name {str(raw)[:40]!r} is not allowed; use letters, digits and underscores, starting with a letter")
        out.append(name)
    if len(set(out)) != len(out):
        raise UploadError("Duplicate column names after normalisation")
    return out


def _reject_formulas(frame: pd.DataFrame) -> None:
    for column in frame.columns:
        text = frame[column].dropna().astype(str).str.strip()
        lead = text[text.str.startswith(FORMULA_LEAD)]
        if lead.empty:
            continue
        numeric = pd.to_numeric(lead, errors="coerce").notna()
        bad = lead[~numeric]
        if len(bad):
            raise UploadError(f"Formula-like cell rejected in column {column!r} (text starting with = + - or @): {bad.iloc[0][:30]!r}")


def split_anomalies(returns: pd.Series, label: str = "") -> list[str]:
    """A5: abs daily move above 40% followed by an opposite-signed move of at least a quarter its size."""
    r = returns.dropna()
    if len(r) < 2:
        return []
    cur, nxt = r.to_numpy()[:-1], r.to_numpy()[1:]
    hit = (np.abs(cur) > ANOMALY_MOVE) & (cur * nxt < 0) & (np.abs(nxt) >= 0.25 * np.abs(cur))
    return [f"Possible split/adjustment error{(' in ' + label) if label else ''} on {r.index[i].date() if hasattr(r.index[i], 'date') else r.index[i]}: "
            f"{cur[i]:+.0%} then {nxt[i]:+.0%}" for i in np.flatnonzero(hit)[:5]]


def parse_csv(raw: bytes, kind: str, today: pd.Timestamp | None = None) -> tuple[pd.DataFrame, dict[str, Any]]:
    if kind not in KINDS:
        raise UploadError(f"kind must be one of {list(KINDS)}")
    if len(raw) > MAX_BYTES:
        raise UploadError("Upload exceeds 10 MB", 413)
    if not raw.strip():
        raise UploadError("Upload is empty")
    if raw[:4] == b"PK\x03\x04" or raw[:2] == b"\x80\x04" or raw[:1] == b"\x80" or b"\x00" in raw[:4096]:
        raise UploadError("Only plain-text CSV is accepted (no Excel, pickle or binary files)")
    try:
        text = raw.decode("utf-8-sig")
    except UnicodeDecodeError as exc:
        raise UploadError("File must be UTF-8 text") from exc
    first = text.split("\n", 1)[0]
    if first.count(",") + 1 > MAX_COLUMNS:
        raise UploadError(f"At most {MAX_COLUMNS} columns are allowed")
    try:
        frame = pd.read_csv(io.StringIO(text), dtype=str, keep_default_na=True, skipinitialspace=True,
                            nrows=MAX_ROWS + 1, engine="c", on_bad_lines="error")
    except (pd.errors.ParserError, pd.errors.EmptyDataError, ValueError) as exc:
        raise UploadError(f"Could not parse CSV: {str(exc)[:160]}") from exc
    if len(frame) > MAX_ROWS:
        raise UploadError(f"At most {MAX_ROWS} rows are allowed")
    if frame.shape[1] > MAX_COLUMNS:
        raise UploadError(f"At most {MAX_COLUMNS} columns are allowed")
    frame.columns = _clean_columns(list(frame.columns))
    _reject_formulas(frame)
    warnings: list[str] = []

    if kind == "returns":
        if "strategy" in frame.columns and "return" not in frame.columns:
            frame = frame.rename(columns={"strategy": "return"})
        expected, numeric, key = ["date", "return"], ["return"], ["date"]
        if list(frame.columns) != expected:
            raise UploadError("returns CSV needs exactly the columns date,return (or date,strategy)")
    elif kind == "predictions":
        allowed = {"date", "ticker", "prediction", "outcome", "outcome_date"}
        if not {"date", "ticker", "prediction"} <= set(frame.columns) or set(frame.columns) - allowed:
            raise UploadError("predictions CSV needs date,ticker,prediction and optionally outcome,outcome_date")
        numeric, key = [c for c in ("prediction", "outcome") if c in frame.columns], ["date", "ticker"]
    elif kind == "trial_matrix":
        rest = [c for c in frame.columns if c != "date"]
        if "date" not in frame.columns or len(rest) < 2 or not all(re.fullmatch(r"trial_\d+", c) for c in rest):
            raise UploadError("trial_matrix CSV needs date plus at least two columns named trial_1..trial_n")
        numeric, key = rest, ["date"]
    else:
        rest = [c for c in frame.columns if c not in {"date", "ticker"}]
        if not {"date", "ticker"} <= set(frame.columns) or not rest:
            raise UploadError("feature_panel CSV needs date,ticker and at least one feature column (optionally outcome)")
        numeric, key = rest, ["date", "ticker"]

    dates = pd.to_datetime(frame["date"], errors="coerce")
    if dates.isna().any():
        raise UploadError(f"{int(dates.isna().sum())} unparseable date value(s); first bad row {int(dates.isna().to_numpy().argmax()) + 2}")
    if dates.dt.tz is not None:
        dates = dates.dt.tz_convert("UTC").dt.tz_localize(None)
    frame["date"] = dates
    limit = (today or pd.Timestamp.today()).normalize() + pd.Timedelta(days=1)
    if dates.max() >= limit:
        raise UploadError(f"Future dates are not allowed (latest {dates.max().date()})")
    if "outcome_date" in frame.columns:
        outcome_date = pd.to_datetime(frame["outcome_date"], errors="coerce")
        if outcome_date.isna().any():
            raise UploadError("outcome_date contains unparseable values")
        if (outcome_date < dates).any():
            raise UploadError("outcome_date earlier than the prediction date (point-in-time violation)")
        frame["outcome_date"] = outcome_date
    if "ticker" in frame.columns:
        tickers = frame["ticker"].astype(str).str.strip().str.upper()
        if frame["ticker"].isna().any() or not tickers.str.fullmatch(TICKER_RE.pattern).all():
            raise UploadError("ticker values must be 1-20 characters of letters, digits and . _ ^ = -")
        frame["ticker"] = tickers
    if frame.duplicated(key).any():
        raise UploadError(f"Duplicate {'+'.join(key)} keys (first duplicate row {int(frame.duplicated(key).to_numpy().argmax()) + 2})")
    if not dates.is_monotonic_increasing:
        raise UploadError("Dates must be in ascending order")

    nan_share: dict[str, float] = {}
    for column in numeric:
        before = frame[column].notna()
        frame[column] = pd.to_numeric(frame[column], errors="coerce")
        coerced = int((before & frame[column].isna()).sum())
        if coerced:
            warnings.append(f"{coerced} non-numeric cell(s) in {column} coerced to missing")
        if np.isinf(frame[column].to_numpy(dtype=float, na_value=np.nan)).any():
            raise UploadError(f"Infinite values in {column}")
        nan_share[column] = float(frame[column].isna().mean())
    if numeric and max(nan_share.values()) > 0.5:
        raise UploadError(f"More than half of column {max(nan_share, key=nan_share.get)!r} is missing")
    for column, share in nan_share.items():
        if share > 0.05:
            warnings.append(f"{column}: {share:.1%} missing")

    if kind == "returns":
        series = frame.set_index("date")["return"]
        if series.abs().median() > 0.2:
            warnings.append("Median absolute return above 20%: are returns in percent rather than fractions?")
        warnings += split_anomalies(series)
    elif kind == "predictions" and "outcome" in frame.columns:
        for ticker, group in frame.groupby("ticker"):
            warnings += split_anomalies(group.set_index("date")["outcome"], str(ticker))
    if kind in {"returns", "trial_matrix"}:
        gaps = dates.diff().dt.days.dropna()
        if len(gaps) and gaps.max() > 7:
            warnings.append(f"Calendar gap of {int(gaps.max())} days; no gap filling is applied")
    if len(frame) < 30:
        warnings.append("Fewer than 30 rows: statistics will be weak")

    summary = {"rows": int(len(frame)), "columns": list(frame.columns), "nan_share": nan_share,
               "date_range": [str(dates.min().date()), str(dates.max().date())], "warnings": warnings}
    return frame.reset_index(drop=True), summary


def store_csv(raw: bytes, kind: str) -> dict[str, Any]:
    frame, summary = parse_csv(raw, kind)
    item = put_upload(kind, frame, summary)
    return {"upload_id": item.upload_id, "kind": kind, "rows": summary["rows"], "columns": summary["columns"],
            "date_range": summary["date_range"], "nan_share": summary["nan_share"], "warnings": summary["warnings"]}
