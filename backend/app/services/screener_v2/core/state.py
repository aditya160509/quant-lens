"""Atomic screen membership/rank snapshots shared by alerts and exports."""
import json
import sqlite3
from contextlib import contextmanager

from .data_loader import BACKEND_DATA

STATE_PATH = BACKEND_DATA / 'screener_v2' / 'screens.sqlite3'


def compare_and_store(screen_id: str, rows: list[dict], as_of_date: str, rank_shift: int = 10) -> list[dict]:
    if not screen_id.strip() or len(screen_id) > 120 or rank_shift < 1:
        raise ValueError('screen_id must contain 1-120 characters')
    current = {r['ticker']: {'rank': i + 1, 'score': r.get('core_quant_score')} for i, r in enumerate(rows)}
    STATE_PATH.parent.mkdir(parents=True, exist_ok=True)
    with _connection() as conn:
        conn.execute('CREATE TABLE IF NOT EXISTS snapshots (screen_id TEXT PRIMARY KEY, as_of_date TEXT, members TEXT NOT NULL)')
        conn.execute('CREATE TABLE IF NOT EXISTS events (screen_id TEXT, as_of_date TEXT, event TEXT NOT NULL)')
        conn.execute('BEGIN IMMEDIATE')
        previous = conn.execute('SELECT as_of_date, members FROM snapshots WHERE screen_id=?', (screen_id,)).fetchone()
        if previous and as_of_date < previous[0]:
            raise ValueError('Cannot overwrite screen state with an earlier as_of_date')
        if previous and as_of_date == previous[0]:
            if json.loads(previous[1]) != current:
                raise ValueError('Screen definition changed for an existing date; use a new screen_id')
            return [json.loads(r[0]) for r in conn.execute('SELECT event FROM events WHERE screen_id=? AND as_of_date=?', (screen_id, as_of_date))]
        old = json.loads(previous[1]) if previous else None
        changes = []
        # The first observation establishes a baseline, not fabricated entries.
        if old is not None:
            for ticker in sorted(current.keys() | old.keys()):
                event = 'entered' if ticker not in old else 'exited' if ticker not in current else 'rank_shift'
                delta = old[ticker]['rank'] - current[ticker]['rank'] if ticker in old and ticker in current else None
                if event == 'rank_shift' and abs(delta) < rank_shift:
                    continue
                changes.append({'ticker': ticker, 'event': event, 'date': as_of_date, 'rank_change': delta,
                                'prior_rank': old.get(ticker, {}).get('rank'), 'rank': current.get(ticker, {}).get('rank')})
        conn.execute('INSERT OR REPLACE INTO snapshots VALUES (?, ?, ?)', (screen_id, as_of_date, json.dumps(current, allow_nan=False)))
        conn.executemany('INSERT INTO events VALUES (?, ?, ?)', [(screen_id, as_of_date, json.dumps(row)) for row in changes])
        return changes


@contextmanager
def _connection():
    STATE_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(STATE_PATH, timeout=30)
    conn.execute('CREATE TABLE IF NOT EXISTS definitions (screen_id TEXT PRIMARY KEY, name TEXT NOT NULL, feature_id TEXT NOT NULL, payload TEXT NOT NULL)')
    conn.execute('CREATE TABLE IF NOT EXISTS universes (universe_id TEXT PRIMARY KEY, name TEXT NOT NULL, symbols TEXT NOT NULL)')
    conn.execute('CREATE TABLE IF NOT EXISTS runs (run_id INTEGER PRIMARY KEY, screen_id TEXT NOT NULL, as_of_date TEXT NOT NULL, result TEXT NOT NULL)')
    conn.execute('CREATE TABLE IF NOT EXISTS channels (screen_id TEXT NOT NULL, url TEXT NOT NULL, digest INTEGER NOT NULL, PRIMARY KEY (screen_id, url))')
    conn.execute('CREATE TABLE IF NOT EXISTS deliveries (screen_id TEXT NOT NULL, date TEXT NOT NULL, ticker TEXT NOT NULL, type TEXT NOT NULL, metric TEXT NOT NULL, ok INTEGER NOT NULL, error TEXT)')
    try:
        with conn:
            yield conn
    finally:
        conn.close()


def save_screen(screen_id: str, name: str, feature_id: str, payload: dict) -> dict:
    if not screen_id.strip() or len(screen_id) > 120 or not name.strip():
        raise ValueError('Screen id and name must be nonempty; id has a 120-character limit')
    encoded = json.dumps(payload, allow_nan=False, sort_keys=True)
    with _connection() as conn:
        old = conn.execute('SELECT feature_id, payload FROM definitions WHERE screen_id=?', (screen_id,)).fetchone()
        if old and old != (feature_id, encoded):
            raise ValueError('Saved screen definitions are immutable; use a new screen_id for changed filters')
        conn.execute('INSERT OR REPLACE INTO definitions VALUES (?, ?, ?, ?)', (screen_id, name.strip(), feature_id, encoded))
    return {'screen_id': screen_id, 'name': name.strip(), 'feature_id': feature_id, 'payload': payload}


def list_screens() -> list[dict]:
    with _connection() as conn:
        return [{'screen_id': r[0], 'name': r[1], 'feature_id': r[2], 'payload': json.loads(r[3])}
                for r in conn.execute('SELECT screen_id, name, feature_id, payload FROM definitions ORDER BY screen_id')]


def get_screen(screen_id: str) -> dict:
    with _connection() as conn:
        row = conn.execute('SELECT name, feature_id, payload FROM definitions WHERE screen_id=?', (screen_id,)).fetchone()
    if not row:
        raise KeyError(f'Unknown saved screen: {screen_id}')
    return {'screen_id': screen_id, 'name': row[0], 'feature_id': row[1], 'payload': json.loads(row[2])}


def save_universe(universe_id: str, name: str, symbols: list[str]) -> dict:
    if not universe_id.strip() or len(universe_id) > 120 or not name.strip() or not symbols:
        raise ValueError('Universe requires an id, name and at least one ticker')
    encoded = json.dumps(symbols, allow_nan=False)
    with _connection() as conn:
        old = conn.execute('SELECT symbols FROM universes WHERE universe_id=?', (universe_id,)).fetchone()
        if old and old[0] != encoded:
            raise ValueError('Saved universes are immutable; use a new id for changed membership')
        conn.execute('INSERT OR REPLACE INTO universes VALUES (?, ?, ?)', (universe_id, name.strip(), encoded))
    return {'universe_id': universe_id, 'name': name.strip(), 'symbols': symbols, 'count': len(symbols)}


def list_universes() -> list[dict]:
    with _connection() as conn:
        return [{'universe_id': r[0], 'name': r[1], 'symbols': json.loads(r[2]), 'count': len(json.loads(r[2]))}
                for r in conn.execute('SELECT universe_id, name, symbols FROM universes ORDER BY universe_id')]


def delete_universe(universe_id: str) -> None:
    with _connection() as conn:
        conn.execute('DELETE FROM universes WHERE universe_id=?', (universe_id,))


def get_universe(universe_id: str) -> list[str]:
    with _connection() as conn:
        row = conn.execute('SELECT symbols FROM universes WHERE universe_id=?', (universe_id,)).fetchone()
    if not row:
        raise KeyError(f'Unknown saved universe: {universe_id}')
    return json.loads(row[0])


def save_run(screen_id: str, as_of_date: str, result: dict) -> None:
    with _connection() as conn:
        conn.execute('INSERT INTO runs (screen_id, as_of_date, result) VALUES (?, ?, ?)',
                     (screen_id, as_of_date, json.dumps(result, allow_nan=False)))


def run_history(screen_id: str, limit: int = 20) -> list[dict]:
    if not 1 <= limit <= 100:
        raise ValueError('History limit must be between 1 and 100')
    with _connection() as conn:
        return [{'run_id': r[0], 'as_of_date': r[1], 'result': json.loads(r[2])}
                for r in conn.execute('SELECT run_id, as_of_date, result FROM runs WHERE screen_id=? ORDER BY run_id DESC LIMIT ?', (screen_id, limit))]


def store_alerts(screen_id: str, date: str, alerts: list[dict]) -> None:
    with _connection() as conn:
        conn.execute('CREATE TABLE IF NOT EXISTS alert_history (screen_id TEXT, date TEXT, ticker TEXT, type TEXT, metric TEXT, payload TEXT, PRIMARY KEY (screen_id, date, ticker, type, metric))')
        conn.executemany('INSERT OR IGNORE INTO alert_history VALUES (?, ?, ?, ?, ?, ?)',
                         [(screen_id, date, row['ticker'], row['type'], str(row.get('metric', '')), json.dumps(row, allow_nan=False)) for row in alerts])


def alert_history(screen_id: str, delivered_only: bool = False) -> list[dict]:
    with _connection() as conn:
        conn.execute('CREATE TABLE IF NOT EXISTS alert_history (screen_id TEXT, date TEXT, ticker TEXT, type TEXT, metric TEXT, payload TEXT, PRIMARY KEY (screen_id, date, ticker, type, metric))')
        sent = ' AND EXISTS (SELECT 1 FROM deliveries d WHERE d.screen_id=a.screen_id AND d.date=a.date AND d.ticker=a.ticker AND d.type=a.type AND d.metric=a.metric AND d.ok=1)' if delivered_only else ''
        return [{'date': row[0], **json.loads(row[1])} for row in conn.execute(f'SELECT date, payload FROM alert_history a WHERE screen_id=?{sent} ORDER BY date', (screen_id,))]


def set_channels(screen_id: str, urls: list[str], digest: bool) -> None:
    get_screen(screen_id)
    with _connection() as conn:
        conn.execute('DELETE FROM channels WHERE screen_id=?', (screen_id,))
        conn.executemany('INSERT INTO channels VALUES (?, ?, ?)', [(screen_id, url.strip(), int(digest)) for url in urls if url.strip()])


def channels(screen_id: str) -> list[dict]:
    with _connection() as conn:
        return [{'url': r[0], 'digest': bool(r[1])} for r in conn.execute('SELECT url, digest FROM channels WHERE screen_id=?', (screen_id,))]


def record_deliveries(screen_id: str, date: str, alerts: list[dict], ok: bool, error: str | None = None) -> None:
    with _connection() as conn:
        conn.executemany('INSERT INTO deliveries VALUES (?, ?, ?, ?, ?, ?, ?)', [(screen_id, date, a['ticker'], a['type'], str(a.get('metric', '')), int(ok), error) for a in alerts])


def screen_events(screen_id: str, limit: int = 500) -> list[dict]:
    with _connection() as conn:
        return [json.loads(r[0]) for r in conn.execute('SELECT event FROM events WHERE screen_id=? ORDER BY as_of_date DESC, rowid DESC LIMIT ?', (screen_id, limit))]


def _schedule_schema(conn):
    conn.execute('CREATE TABLE IF NOT EXISTS schedules (screen_id TEXT PRIMARY KEY, interval_seconds INTEGER NOT NULL, next_due REAL NOT NULL, enabled INTEGER NOT NULL, last_job_id TEXT, error TEXT)')


def set_schedule(screen_id: str, interval_seconds: int, enabled: bool = True, now=None):
    import time
    get_screen(screen_id)
    if not 60 <= interval_seconds <= 604800:
        raise ValueError('Schedule interval must be 60-604800 seconds')
    now = time.time() if now is None else float(now)
    with _connection() as conn:
        _schedule_schema(conn)
        conn.execute('INSERT OR REPLACE INTO schedules VALUES (?, ?, ?, ?, NULL, NULL)',
                     (screen_id, interval_seconds, now + interval_seconds, int(enabled)))
    return {'screen_id': screen_id, 'interval_seconds': interval_seconds, 'next_due': now + interval_seconds, 'enabled': enabled}


def list_schedules():
    with _connection() as conn:
        _schedule_schema(conn)
        columns = ['screen_id', 'interval_seconds', 'next_due', 'enabled', 'last_job_id', 'error']
        return [dict(zip(columns, row)) for row in conn.execute('SELECT * FROM schedules ORDER BY screen_id')]


def claim_due_schedules(now=None):
    import time
    now = time.time() if now is None else float(now)
    with _connection() as conn:
        _schedule_schema(conn)
        conn.execute('BEGIN IMMEDIATE')
        rows = list(conn.execute('SELECT screen_id, interval_seconds, next_due FROM schedules WHERE enabled=1 AND next_due<=?', (now,)))
        for screen_id, interval, due in rows:
            conn.execute('UPDATE schedules SET next_due=? WHERE screen_id=?', (now + interval, screen_id))
        return [{'screen_id': row[0], 'due': row[2]} for row in rows]


def schedule_result(screen_id, job_id=None, error=None):
    with _connection() as conn:
        _schedule_schema(conn)
        conn.execute('UPDATE schedules SET last_job_id=?, error=? WHERE screen_id=?', (job_id, error, screen_id))


def _metric_schema(conn):
    conn.execute('CREATE TABLE IF NOT EXISTS metrics (name TEXT PRIMARY KEY, expression TEXT NOT NULL, show INTEGER NOT NULL)')


def save_metric(name: str, expression: str, show: bool = False) -> dict:
    with _connection() as conn:
        _metric_schema(conn)
        conn.execute('INSERT OR REPLACE INTO metrics VALUES (?, ?, ?)', (name, expression, int(show)))
    return {'name': name, 'expression': expression, 'show': show}


def list_metrics() -> list[dict]:
    with _connection() as conn:
        _metric_schema(conn)
        return [{'name': r[0], 'expression': r[1], 'show': bool(r[2])} for r in conn.execute('SELECT name, expression, show FROM metrics ORDER BY name')]


def delete_metric(name: str) -> None:
    with _connection() as conn:
        _metric_schema(conn)
        conn.execute('DELETE FROM metrics WHERE name=?', (name,))
