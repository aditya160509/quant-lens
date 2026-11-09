"""Alert and change delivery through Apprise: email, push and webhook from one URL each."""
from __future__ import annotations

import logging

from .state import channels, get_screen, record_deliveries

logger = logging.getLogger(__name__)


def message(name: str, as_of: str, changes: list[dict], alerts: list[dict]) -> str:
    lines = [f"{name}, as of {as_of}"]
    for kind in ("entered", "exited", "rank_shift"):
        rows = [c for c in changes if c.get("event") == kind]
        if rows:
            lines.append(f"{kind.replace('_', ' ').capitalize()} ({len(rows)}): " + ", ".join(f"{c['ticker']} {c['rank_change']:+d}" if kind == "rank_shift" else c["ticker"] for c in rows))
    for kind in sorted({a["type"] for a in alerts}):
        rows = [a for a in alerts if a["type"] == kind]
        lines.append(f"{kind.replace('_', ' ').capitalize()} ({len(rows)}): " + ", ".join(str(a["ticker"]) for a in rows))
    return "\n".join(lines) if len(lines) > 1 else lines[0] + "\nNothing changed."


def deliver(screen_id: str, result: dict) -> None:
    """Send a finished run's changes and alerts to the screen's channels; failures are recorded, never raised."""
    configured = channels(screen_id)
    if not configured:
        return
    import apprise
    charts = result.get("charts", {})
    changes = charts.get("run_changes") or charts.get("change_report") or result.get("tables", {}).get("screen_entry_exit_log") or []
    alerts = charts.get("alert_feed") or []
    as_of = str(result.get("meta", {}).get("as_of_date") or "latest")
    name = get_screen(screen_id)["name"]
    for channel in configured:
        if not (changes or alerts or channel["digest"]):
            continue
        sender = apprise.Apprise()
        sender.add(channel["url"])
        try:
            ok = bool(sender.notify(title=name, body=message(name, as_of, changes, alerts)))
            error = None if ok else "Apprise could not deliver"
        except Exception as exc:
            logger.exception("Delivery failed for %s", screen_id)
            ok, error = False, f"{type(exc).__name__}: {exc}"
        record_deliveries(screen_id, as_of, alerts, ok, error)
