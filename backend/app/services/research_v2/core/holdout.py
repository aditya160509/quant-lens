"""Protected out-of-sample windows.

Reserving a window locks the most recent N months of a (signal, universe,
dependent variable) study away from every Research V2 feature. Only the
placebo suite can evaluate it, and each evaluation is recorded so a later
viewer knows whether the holdout is still pristine.
"""

from __future__ import annotations

import fcntl
import json
import os
from datetime import datetime, timezone
from typing import Any

import pandas as pd

from .data_loader import BACKEND_DATA

STORE = BACKEND_DATA / "research_v2" / "protected_windows.json"


def study_key(config: dict[str, Any], universe: Any) -> str:
    label = ",".join(universe) if isinstance(universe, (list, tuple)) else str(universe or "us_equities")
    return f"{config['signal']}|{label.lower()}|{config['dependent_variable']}|h{config['holding_months']}"


def _read() -> dict[str, Any]:
    if not STORE.exists():
        return {}
    with STORE.open() as fh:
        fcntl.flock(fh, fcntl.LOCK_SH)
        try:
            return json.load(fh)
        finally:
            fcntl.flock(fh, fcntl.LOCK_UN)


def _write(data: dict[str, Any]) -> None:
    STORE.parent.mkdir(parents=True, exist_ok=True)
    tmp = STORE.with_suffix(".tmp")
    with tmp.open("w") as fh:
        fcntl.flock(fh, fcntl.LOCK_EX)
        json.dump(data, fh, indent=2, default=str)
        fh.flush()
        os.fsync(fh.fileno())
        fcntl.flock(fh, fcntl.LOCK_UN)
    tmp.replace(STORE)


def all_windows() -> dict[str, Any]:
    return _read()


def get_window(key: str) -> dict[str, Any] | None:
    return _read().get(key)


def reserve_window(key: str, start: pd.Timestamp, months: int) -> dict[str, Any]:
    data = _read()
    if key in data:
        return data[key]
    data[key] = {"start": pd.Timestamp(start).strftime("%Y-%m-%d"), "months": int(months), "reserved_at": datetime.now(timezone.utc).isoformat(), "evaluations": []}
    _write(data)
    return data[key]


def record_evaluation(key: str) -> dict[str, Any]:
    data = _read()
    if key not in data:
        raise KeyError(key)
    data[key]["evaluations"].append(datetime.now(timezone.utc).isoformat())
    _write(data)
    return data[key]


def release_window(key: str) -> bool:
    data = _read()
    if key not in data:
        return False
    del data[key]
    _write(data)
    return True


# ---------------------------------------------------------------------------
# Locked (pre-registered) specifications. A column is "confirmatory" only if
# its exact specification was locked before it was estimated.

LOCKS = BACKEND_DATA / "research_v2" / "locked_specs.json"


def spec_hash(spec: dict[str, Any]) -> str:
    import hashlib

    keys = ["dependent_variable", "signal", "controls", "estimator", "se", "fixed_effects", "weighting", "start", "end", "holding_months", "universe"]
    canonical = json.dumps({k: str(spec.get(k, "")) for k in keys}, sort_keys=True)
    return hashlib.sha256(canonical.encode()).hexdigest()[:16]


def _read_locks() -> dict[str, Any]:
    if not LOCKS.exists():
        return {}
    with LOCKS.open() as fh:
        return json.load(fh)


def lock_specification(spec: dict[str, Any], note: str = "") -> dict[str, Any]:
    locks = _read_locks()
    key = spec_hash(spec)
    if key not in locks:
        locks[key] = {"spec": spec, "note": note, "locked_at": datetime.now(timezone.utc).isoformat()}
        LOCKS.parent.mkdir(parents=True, exist_ok=True)
        tmp = LOCKS.with_suffix(".tmp")
        tmp.write_text(json.dumps(locks, indent=2, default=str))
        tmp.replace(LOCKS)
    return {"hash": key, **locks[key]}


def all_locks() -> dict[str, Any]:
    return _read_locks()


def locked(spec: dict[str, Any]) -> dict[str, Any] | None:
    return _read_locks().get(spec_hash(spec))
