"""Build run levels: quick and full runs, progress, cancel, delta against the previous run."""

import time

from tests.test_studio_v3_backtest import SMA, studio  # noqa: F401  (fixture)

API = "/api/studio-v3"


def _wait(client, job_id):
    for _ in range(500):
        out = client.get(f"{API}/build/run/{job_id}").json()
        if out["status"] in {"completed", "failed", "cancelled"}:
            return out
        time.sleep(0.02)
    raise AssertionError("run did not finish")


def test_quick_run_is_not_in_the_ledger_and_reports_delta(studio):  # noqa: F811
    sid = studio.post(f"{API}/strategies", json={"spec": SMA}).json()["id"]
    body = {"level": "quick", "strategy_id": sid, "settings": {"symbols": ["AAA", "BBB"], "holdout": 0}}
    first = studio.post(f"{API}/build/run", json=body).json()
    assert first["level"] == "quick" and first["previous_job_id"] is None and first["budget_seconds"] == 120
    done = _wait(studio, first["job_id"])
    assert done["status"] == "completed" and done["delta"] is None
    assert studio.get(f"{API}/strategies/{sid}/ledger").json()["raw"] == 0
    changed = {**SMA, "entry_long": "crosses_above(sma(close, 5), sma(close, 20))"}
    second = studio.post(f"{API}/build/run", json={**body, "strategy_id": None, "spec": changed}).json()
    again = studio.post(f"{API}/build/run", json=body).json()
    assert again["previous_job_id"] == second["job_id"] or again["previous_job_id"] == first["job_id"]
    out = _wait(studio, again["job_id"])
    assert set(out["delta"]) == {"previous_job_id", "total_return", "sharpe", "trades"}


def test_full_run_needs_a_saved_strategy_and_lands_in_the_ledger(studio):  # noqa: F811
    assert studio.post(f"{API}/build/run", json={"level": "full", "spec": SMA}).status_code == 422
    assert studio.post(f"{API}/build/run", json={"level": "quick"}).status_code == 422
    sid = studio.post(f"{API}/strategies", json={"spec": SMA}).json()["id"]
    job = studio.post(f"{API}/build/run", json={"level": "full", "strategy_id": sid, "settings": {"symbols": ["AAA", "BBB"]}}).json()
    assert _wait(studio, job["job_id"])["status"] == "completed"
    assert studio.get(f"{API}/strategies/{sid}/ledger").json()["raw"] == 1


def test_cancel_stops_a_run_at_the_next_stage(studio):  # noqa: F811
    from app.services.studio_v3.core import backtest
    from app.services.studio_v3.core.spec import Settings, Strategy

    def cancelled(name, percent, partial=None):
        pass

    cancelled.cancelled = lambda: True
    try:
        backtest.run_backtest(Strategy(**SMA), Settings(symbols=["AAA"], benchmark=""), cancelled)
    except backtest.Refusal as exc:
        assert "cancelled" in str(exc)
    else:
        raise AssertionError("a cancelled run must stop")


def test_progress_names_symbols_bars_elapsed_and_budget(studio):  # noqa: F811
    from app.services.studio_v3.core import backtest
    from app.services.studio_v3.core.spec import Settings, Strategy

    seen = []
    backtest.run_backtest(Strategy(**SMA), Settings(symbols=["AAA", "BBB"], benchmark=""), lambda name, percent, partial=None: seen.append((name, partial)))
    assert [n for n, _ in seen][:3] == ["load", "signals", "simulate"]
    last = seen[-1][1]
    assert last["symbols"] == 2 and last["bars"] > 0 and last["elapsed_seconds"] >= 0 and last["budget_seconds"] == 120


_CODE = '''import math


class Strategy:
    def init(self, ctx):
        self.count = 0

    def on_bar(self, ctx):
        self.count += 1
        if ctx.t % 40 == 0:
            ctx.buy()
        elif ctx.t % 40 == 20:
            ctx.sell()
        total = 0.0
        for k in range(200):
            total += math.sqrt(k)
'''


def test_preview_names_the_lines_that_placed_orders(studio):  # noqa: F811
    result = studio.post(f"{API}/preview", json={"symbol": "SPY", "spec": {"code": _CODE}}).json()
    rows = {row["line"]: row for row in result["order_lines"]}
    assert set(rows) == {11, 13} and rows[11]["count"] >= 2 and 1 <= len(rows[11]["dates"]) <= 5 and rows[11]["file"] == "main.py"
    assert "profile" not in result


def test_profiler_reports_slowest_lines_and_functions(studio):  # noqa: F811
    result = studio.post(f"{API}/build/profile", json={"symbol": "SPY", "spec": {"code": _CODE}}).json()
    lines = result["profile"]["lines"]
    assert 1 <= len(lines) <= 10 and lines == sorted(lines, key=lambda r: -r["seconds"])
    assert lines[0]["line"] in {15, 16} and "math.sqrt" in lines[0]["text"] + lines[1]["text"]
    names = {f["name"]: f for f in result["profile"]["functions"]}
    assert names["on_bar"]["calls"] > 100 and names["init"]["calls"] == 1


def test_runtime_error_returns_the_locals_at_the_failing_bar(studio):  # noqa: F811
    code = "class Strategy:\n    def init(self, ctx):\n        self.seen = 0\n\n    def on_bar(self, ctx):\n        self.seen += 1\n        ratio = 1\n        if ctx.t == 30:\n            ratio = 1 / (ctx.t - 30)\n"
    result = studio.post(f"{API}/preview", json={"symbol": "SPY", "spec": {"code": code}}).json()
    at = result["problem"]["locals"]
    assert result["status"] == "error" and result["problem"]["exception_type"] == "ZeroDivisionError"
    assert at["symbol"] == "SPY" and at["bar_index"] == 30 and at["variables"]["ratio"] == 1 and at["state"]["seen"] == 31 and at["date"]
