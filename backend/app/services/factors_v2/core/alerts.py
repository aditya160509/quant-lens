"""Idempotent in-app alert events and dated recovery state; no delivery claim."""

import hashlib
import json
import sqlite3
from . import data_loader


def record(payload, rows, active):
    configuration = {
        k: v
        for k, v in payload.items()
        if k not in {"as_of_date", "end_date", "start_date", "compute_mode"}
    }
    monitor = hashlib.sha256(
        json.dumps(configuration, sort_keys=True).encode()
    ).hexdigest()
    date = payload["as_of_date"]
    folder = data_loader.BACKEND_DATA / "factors_v2"
    folder.mkdir(parents=True, exist_ok=True)
    current = {a["factor"] for a in active}
    events = []
    with sqlite3.connect(folder / "alerts.sqlite3", timeout=30) as db:
        db.execute(
            "CREATE TABLE IF NOT EXISTS states (monitor TEXT, factor TEXT, date TEXT, active INTEGER, PRIMARY KEY(monitor,factor))"
        )
        db.execute(
            "CREATE TABLE IF NOT EXISTS events (id TEXT PRIMARY KEY, monitor TEXT, factor TEXT, date TEXT, state TEXT)"
        )
        db.execute("BEGIN IMMEDIATE")
        for row in rows:
            factor = row["factor"]
            previous = db.execute(
                "SELECT date, active FROM states WHERE monitor=? AND factor=?",
                (monitor, factor),
            ).fetchone()
            # Insufficient observations are unknown, not a recovery signal.
            if row.get("ic_z_score") is None:
                continue
            if previous and previous[0] >= date:
                continue
            enabled = factor in current
            state = (
                "triggered"
                if enabled and (not previous or not previous[1])
                else "recovered"
                if not enabled and previous and previous[1]
                else None
            )
            if state:
                event_id = hashlib.sha256(
                    f"{monitor}:{factor}:{date}:{state}".encode()
                ).hexdigest()
                db.execute(
                    "INSERT OR IGNORE INTO events VALUES (?,?,?,?,?)",
                    (event_id, monitor, factor, date, state),
                )
            db.execute(
                "INSERT OR REPLACE INTO states VALUES (?,?,?,?)",
                (monitor, factor, date, int(enabled)),
            )
        for event in db.execute(
            "SELECT id,factor,date,state FROM events WHERE monitor=? ORDER BY date DESC LIMIT 100",
            (monitor,),
        ):
            events.append(dict(zip(["event_id", "factor", "date", "state"], event)))
    return events
