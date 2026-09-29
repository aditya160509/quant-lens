"""Isolated kernel execution worker used by cancellable compute jobs."""

from __future__ import annotations

import pickle
import traceback
from multiprocessing.connection import Connection
from typing import Any

import numpy as np
import pandas as pd


def _picklable(value: Any) -> bool:
    try:
        pickle.dumps(value, protocol=pickle.HIGHEST_PROTOCOL)
        return True
    except Exception:
        return False


def execute_in_worker(connection: Connection, code: str, namespace: dict[str, Any]) -> None:
    try:
        globals_namespace = {"pd": pd, "np": np, "__builtins__": __builtins__, **namespace}
        local_namespace: dict[str, Any] = {}
        exec(compile(code, "<studio-kernel>", "exec"), globals_namespace, local_namespace)
        changes = {
            key: value for key, value in local_namespace.items()
            if not key.startswith("_") and _picklable(value)
        }
        omitted = [key for key, value in local_namespace.items() if not key.startswith("_") and not _picklable(value)]
        connection.send({"status": "ok", "changes": changes, "omitted": omitted})
    except BaseException as exc:
        connection.send({"status": "error", "error": str(exc), "traceback": traceback.format_exc(limit=8)})
    finally:
        connection.close()
