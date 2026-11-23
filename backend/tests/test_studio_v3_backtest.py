"""Studio v3 phase 1: compile, backtest payload, ledger, strategies and the agent API. Acceptance ids from docs/studio/plan/PAGES.md."""

import itertools
import json
import time

import numpy as np
import pandas as pd
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.api import studio_v3 as api
from app.services.shared import metrics as M
from app.services.studio.jobs import JobStore
from app.services.studio_v3.core import backtest, data, engine, formula, pyrunner, store
from app.services.studio_v3.core import compile as C
from app.services.studio_v3.core.spec import Costs, Settings, Strategy

SMA = {"name": "SMA cross", "entry_long": "crosses_above(sma(close, fast), sma(close, slow))", "exit_long": "crosses_below(sma(close, fast), sma(close, slow))",
       "params": {"fast": {"value": 10}, "slow": {"value": 30}}}
SYMBOLS = ("AAA", "BBB", "CCC", "DEAD", "SPY")


def fixture_panel(T=800):
    rng = np.random.default_rng(11)
    dates = pd.bdate_range("2015-01-01", periods=T)
    c = 100 * np.exp(np.cumsum(rng.normal(0.0004, 0.015, (T, 5)) + 0.004 * np.sin(np.arange(T) / 25)[:, None], axis=0))
    o = np.vstack([c[:1], c[:-1]]) * (1 + rng.normal(0, 0.004, (T, 5)))
    h, lo = np.maximum(o, c) * 1.01, np.minimum(o, c) * 0.99
    v = np.full((T, 5), 1e6)
    c[400:, 3] = np.nan  # DEAD stops trading
    for a in (o, h, lo, v):
        a[np.isnan(c)] = np.nan
    return data.Panel(dates, SYMBOLS, o, h, lo, c, v)


@pytest.fixture
def studio(tmp_path, monkeypatch):
    full = fixture_panel()

    def panel(symbols, start=None, end=None):
        cols = [i for i, s in enumerate(full.symbols) if s in {x.upper() for x in symbols}]
        rows = (full.dates >= pd.Timestamp(start or "1900")) & (full.dates <= pd.Timestamp(end or "2100"))
        return data.Panel(full.dates[rows], tuple(full.symbols[i] for i in cols), *(getattr(full, f)[rows][:, cols] for f in data.FIELDS))

    monkeypatch.setattr(data, "panel", panel)
    monkeypatch.setattr(data, "data_version", lambda: "fixture")
    monkeypatch.setattr(store, "DB_PATH", tmp_path / "studio.sqlite")
    monkeypatch.setattr(api, "RESULTS_DIR", tmp_path / "results")
    monkeypatch.setattr(api, "JOBS", JobStore(path=tmp_path / "jobs.json"))
    app = FastAPI()
    app.include_router(api.router, prefix="/api")
    return TestClient(app)


SETTINGS = {"symbols": ["AAA", "BBB", "CCC", "DEAD"], "benchmark": "SPY"}


def run_job(client, payload, headers=None):
    job = client.post("/api/studio-v3/feature/st01/jobs", json={"payload": payload}, headers=headers or {}).json()
    for _ in range(400):
        out = client.get(f"/api/studio-v3/jobs/{job['job_id']}").json()
        if out["status"] in {"completed", "failed", "cancelled"}:
            return out
        time.sleep(0.02)
    raise AssertionError("job did not finish")


def test_hero_numbers_equal_metrics_py(studio):  # K-1
    spec, settings = Strategy(**SMA), Settings(**SETTINGS)
    out = backtest.run_backtest(spec, settings)
    prep = backtest.prepare(settings)
    r = backtest.simulate(spec, prep, settings)
    want = M.return_metrics(r.equity, prep.panel.dates)
    for k in ("sharpe", "cagr", "max_drawdown", "total_return", "sortino"):
        assert out["meta"]["metrics"][k] == pytest.approx(want[k], abs=1e-9)
    cards = {c["label"]: c["value"] for c in out["summary_cards"]}
    assert cards["Sharpe"] == pytest.approx(want["sharpe"], abs=1e-9) and cards["Trades"] == len(r.trades)
    assert out["meta"]["total_return"] == pytest.approx(r.equity[-1] / settings.capital - 1, abs=1e-9)


def test_payload_carries_lean_stats(studio):  # K-15, K-16, K-19, K-20, K-21
    out = backtest.run_backtest(Strategy(**SMA), Settings(**SETTINGS))
    m, meta = out["meta"]["metrics"], out["meta"]
    for k in ("psr", "var_99", "cvar_99", "var_95_normal", "fees_total", "volume_traded", "jensen_alpha", "treynor", "beta", "tracking_error"):
        assert k in m
    assert set(meta["trade_split"]) == {"all", "long", "short"} and meta["trade_split"]["all"]["count"] == meta["trade_split"]["long"]["count"] + meta["trade_split"]["short"]["count"]
    assert len(meta["distribution"]["best"]) == 10 and {"return_36m", "sharpe_36m", "beta_6m"} <= set(out["charts"]["rolling"][-1])


def test_same_run_twice_has_the_same_hash(studio):  # K-2
    a, b = (backtest.run_backtest(Strategy(**SMA), Settings(**SETTINGS)) for _ in range(2))
    assert a["meta"]["result_hash"] == b["meta"]["result_hash"] and a["tables"]["trades"] == b["tables"]["trades"]


def test_zero_costs_show_costs_off(studio):  # K-4
    off = backtest.run_backtest(Strategy(**SMA), Settings(**SETTINGS, costs=Costs(commission_bps=0, slippage_bps=0)))
    on = backtest.run_backtest(Strategy(**SMA), Settings(**SETTINGS))
    assert off["meta"]["costs_off"] is True and on["meta"]["costs_off"] is False
    assert any(x["detail"] == "Costs off" for x in off["tables"]["limits"])


def test_start_dates_match_separate_runs(studio):  # K-5
    spec, settings = Strategy(**SMA), Settings(**SETTINGS)
    prep = backtest.prepare(settings)
    sig = C.signals(spec, prep.sig_bars, prep.panel.dates)
    rows = backtest.start_dates(spec, prep, settings, sig, [0, 100, 250])
    for row, lo in zip(rows, [0, 100, 250], strict=True):
        p = prep.panel.window(lo, len(prep.panel.dates))
        r = engine.run(p.bars(), np.where(np.isfinite(p.close), sig.entries[lo:], 0), sig.exits[lo:], backtest.engine_params(spec, settings))
        assert row["start"] == str(p.dates[0].date())
        assert row["total_return"] == pytest.approx(r.equity[-1] / settings.capital - 1, abs=1e-12)
        assert row["cagr"] == pytest.approx((r.equity[-1] / settings.capital) ** (252 / len(r.equity)) - 1, abs=1e-12)


def test_survivorship_delta_and_delisting_rule(studio):  # K-6
    out = backtest.run_backtest(Strategy(**SMA), Settings(**SETTINGS, holdout=0))
    s = out["meta"]["survivorship"]
    assert s["delisted"] == 1 and s["with_delisted"] != s["survivors_only"]
    curve = out["charts"]["equity_curve"]
    assert any(abs(r["strategy"] - r["survivors_only"]) > 1e-6 for r in curve)
    assert any("settle at the last close" in x["detail"] for x in out["tables"]["limits"])
    haircut = backtest.run_backtest(Strategy(**SMA), Settings(**SETTINGS, holdout=0, delist_haircut=0.5))
    assert any("less 50%" in x["detail"] for x in haircut["tables"]["limits"])


def test_zero_entry_run_is_refused_with_a_reason(studio):  # K-7
    never = {**SMA, "entry_long": "close < 0"}
    r = studio.post("/api/studio-v3/backtest", json={"payload": {"spec": never, **SETTINGS}})
    assert r.status_code == 422 and r.json()["detail"]["refused"] and r.json()["detail"]["reason"].startswith("0 entries") and len(r.json()["detail"]["causes"]) == 3
    job = run_job(studio, {"spec": never, **SETTINGS})
    assert job["status"] == "failed" and job["error"].startswith("0 entries") and "result" not in job


def test_few_trades_are_marked(studio):
    out = backtest.run_backtest(Strategy(**SMA), Settings(symbols=["AAA"], benchmark="SPY"))
    assert out["meta"]["few_trades"] is True and 0 < out["meta"]["metrics"]["trades"] < 30


def test_holdout_dates_are_in_no_series(studio):  # K-10
    out = backtest.run_backtest(Strategy(**SMA), Settings(**SETTINGS))
    out.pop("_trial")
    boundary = out["meta"]["holdout_from"]
    assert boundary == str(fixture_panel().dates[640].date())
    series = {"charts": out["charts"], "tables": {k: v for k, v in out["tables"].items() if k != "limits"}, "period": out["meta"]["period"]}
    dates = [v for v in _walk(series) if isinstance(v, str) and len(v) == 10 and v[4] == "-" and v[7] == "-"]
    assert len(dates) > 500 and max(dates) < boundary


def _walk(v):
    if isinstance(v, dict):
        for x in v.values():
            yield from _walk(x)
    elif isinstance(v, list):
        for x in v:
            yield from _walk(x)
    else:
        yield v


def test_lookahead_is_refused_with_line_and_token(studio):  # B-2
    for text, token in (("close[+1] > close", "close[+1]"), ("delay(close, -1) > close", "delay(close, -1)"), ("center(close, 5) > 0", "center(close, 5)")):
        out = studio.post("/api/studio-v3/compile", json={"spec": {**SMA, "exit_long": text}}).json()
        f = next(x for x in out["findings"] if x["severity"] == "error")
        assert not out["ok"] and f["lookahead"] and f["line"] == 2 and f["role"] == "exit_long" and f["token"] == token
    with pytest.raises(backtest.Refusal, match="does not compile"):
        backtest.run_backtest(Strategy(**{**SMA, "entry_long": "close[1] > close"}), Settings(**SETTINGS))


def test_no_operator_reads_a_later_bar():
    """Repaint check: every operator's value at bar t is unchanged when later bars are altered."""
    p = fixture_panel(300)
    bars = {f: getattr(p, f)[:, :3] for f in data.FIELDS}
    changed = {k: v.copy() for k, v in bars.items()}
    for v in changed.values():
        v[200:] *= 1.7
    for name, (_, args, _, example) in formula.OPERATORS.items():
        a, b = formula.evaluate(example, bars, p.dates), formula.evaluate(example, changed, p.dates)
        np.testing.assert_array_equal(a[:200], b[:200], err_msg=name)


def test_weekly_rule_uses_the_last_closed_week():  # B-3
    dates = pd.bdate_range("2024-01-01", periods=15)  # Mon 1 Jan .. Fri 19 Jan
    close = np.arange(1.0, 16.0)[:, None]
    bars = {f: close for f in data.FIELDS}
    out = formula.evaluate("weekly(close)", bars, dates)[:, 0]
    hand = [np.nan] * 5 + [5.0] * 5 + [10.0] * 5  # first week has no closed week; then the prior Friday's close
    np.testing.assert_array_equal(out, hand)
    assert dates[7].day_name() == "Wednesday" and out[7] == 5.0


def test_compile_under_100_ms_for_a_20_row_strategy(studio):  # B-4
    rows = " & ".join(f"(sma(close, {5 + i}) > sma(close, {40 + i}))" for i in range(20))
    out = studio.post("/api/studio-v3/compile", json={"spec": {**SMA, "entry_long": rows}}).json()
    assert out["ok"] and out["ms"] < 100


def test_what_it_does_paragraph(studio):  # B-9
    assert C.describe(Strategy(**SMA, exits={"stop": 0.08})) == (
        "Buy when crosses_above(sma(close, fast), sma(close, slow)).\n"
        "Exit: Sell when crosses_below(sma(close, fast), sma(close, slow)); stop 8%.\n"
        "Size: an equal share of equity per trade, at most 10 positions.")


def test_ledger_counts_raw_and_effective_trials(studio):  # B-7
    sid = studio.post("/api/studio-v3/strategies", json={"spec": SMA}).json()["id"]
    for i in range(10):  # ten neighbouring sweep cells
        r = studio.post("/api/studio-v3/backtest", json={"payload": {"spec": {**SMA, "params": {"fast": {"value": 10}, "slow": {"value": 30 + i}}}, "strategy_id": sid, **SETTINGS}})
        assert r.status_code == 200
    again = studio.post("/api/studio-v3/backtest", json={"payload": {"spec": SMA, "strategy_id": sid, **SETTINGS}}).json()  # an exact repeat is not a new trial
    led = studio.get(f"/api/studio-v3/strategies/{sid}/ledger").json()
    assert led["raw"] == 10 and led["effective"] < 4 and again["ledger"]["raw"] == 10
    assert led["by_actor"] == {"agents": 10}
    assert store.effective_trials([np.random.default_rng(i).normal(size=60) for i in range(10)]) > 6  # unrelated tries count nearly in full


def test_duplicate_starts_at_version_1_with_an_empty_ledger(studio):  # H-3
    sid = studio.post("/api/studio-v3/strategies", json={"spec": SMA}).json()["id"]
    studio.put(f"/api/studio-v3/strategies/{sid}", json={"spec": {**SMA, "exits": {"stop": 0.1}}})
    studio.post("/api/studio-v3/backtest", json={"payload": {"strategy_id": sid, **SETTINGS}})
    copy = studio.post(f"/api/studio-v3/strategies/{sid}/duplicate").json()
    assert studio.get(f"/api/studio-v3/strategies/{sid}").json()["latest"] == 2
    assert copy["version"] == 1 and copy["latest"] == 1 and copy["spec"]["exits"]["stop"] == 0.1 and copy["name"] == "SMA cross copy"
    assert studio.get(f"/api/studio-v3/strategies/{copy['id']}/ledger").json()["raw"] == 0
    assert studio.get(f"/api/studio-v3/strategies/{sid}/ledger").json()["raw"] == 1


def test_versions_are_immutable_and_drafts_survive(studio):  # B-6 (server side)
    sid = studio.post("/api/studio-v3/strategies", json={"spec": SMA}).json()["id"]
    studio.put(f"/api/studio-v3/strategies/{sid}/draft", json={"spec": {**SMA, "exit_long": "close < sma(close, 5"}})
    got = studio.get(f"/api/studio-v3/strategies/{sid}").json()
    assert got["draft"]["exit_long"] == "close < sma(close, 5" and got["has_draft"]
    v2 = studio.put(f"/api/studio-v3/strategies/{sid}", json={"spec": {**SMA, "name": "SMA cross 2", "exits": {"trail": 0.05}}}).json()
    assert v2["latest"] == 2 and v2["draft"] is None and v2["name"] == "SMA cross 2"
    assert studio.put(f"/api/studio-v3/strategies/{sid}", json={"spec": v2["spec"]}).json()["latest"] == 2  # unchanged: no new version
    assert studio.get(f"/api/studio-v3/strategies/{sid}?version=1").json()["spec"]["exits"]["trail"] == 0
    assert studio.get("/api/studio-v3/strategies/nope").status_code == 404


def test_import_recompiles_and_shows_findings_before_saving(studio):  # H-4
    bad = studio.post("/api/studio-v3/strategies/import?save=true", json={"spec": {**SMA, "entry_long": "sma(close) > 1"}}).json()
    assert not bad["compile"]["ok"] and bad["saved"] is None and "sma takes 2 arguments" in bad["compile"]["findings"][0]["message"]
    preview = studio.post("/api/studio-v3/strategies/import", json={"spec": SMA}).json()
    assert preview["compile"]["ok"] and preview["saved"] is None and studio.get("/api/studio-v3/strategies").json()["strategies"] == []
    saved = studio.post("/api/studio-v3/strategies/import?save=true", json={"spec": SMA}).json()["saved"]
    assert saved["version"] == 1
    assert studio.post("/api/studio-v3/strategies/import", json={"spec": {"nonsense": 1}}).status_code == 422


def test_ui_job_and_agent_api_give_the_same_hash(studio):  # X-3
    sid = studio.post("/api/studio-v3/strategies", json={"spec": SMA}).json()["id"]
    job = run_job(studio, {"strategy_id": sid, **SETTINGS})
    assert job["status"] == "completed", job
    rest = studio.post("/api/studio-v3/backtest", json={"payload": {"strategy_id": sid, **SETTINGS}}, headers={"X-Studio-Actor": "agent:test"}).json()
    rpc = studio.post("/api/studio-v3/mcp", json={"jsonrpc": "2.0", "id": 1, "method": "tools/call", "params": {"name": "backtest", "arguments": {"payload": {"strategy_id": sid, **SETTINGS}}}}).json()
    mcp = rpc["result"]["structuredContent"]
    meta = job["result"]["meta"]
    assert meta["result_hash"] == rest["result_hash"] == mcp["result_hash"] and meta["run_hash"] == rest["run_hash"]
    assert rest["verdict"] == "not validated" and rest["limits"] and rest["ledger"]["raw"] == 1 and rest["spec"]["entry_long"] == SMA["entry_long"]
    assert "_trial" not in job["result"] and meta["ledger"]["raw"] == 1 and meta["strategy"] == {"id": sid, "version": 1, "name": "SMA cross", "hypothesis": "", "regime_claim": "", "notes": ""}
    log = studio.get(f"/api/studio-v3/actor-log?strategy_id={sid}").json()["log"]
    assert {x["actor"] for x in log} == {"human", "agent:test", "agent:mcp"} and all(x["action"] in {"create", "st01"} for x in log)
    home = studio.get("/api/studio-v3/home").json()
    assert home["strategies"][0]["last_run"]["headline"] == meta["headline"] and home["strategies"][0]["trials"]["raw"] == 1 and len(home["strategies"][0]["last_run"]["spark"]) > 10


def test_mcp_lists_tools_and_never_ranks_by_return(studio):
    tools = studio.post("/api/studio-v3/mcp", json={"jsonrpc": "2.0", "id": 1, "method": "tools/list"}).json()["result"]["tools"]
    assert {t["name"] for t in tools} >= {"compile", "backtest", "get_ledger", "get_data_audit"}
    bad = studio.post("/api/studio-v3/mcp", json={"jsonrpc": "2.0", "id": 2, "method": "tools/call", "params": {"name": "compile", "arguments": {"spec": {**SMA, "entry_long": "close[+1] > 1"}}}}).json()
    assert bad["result"]["structuredContent"]["ok"] is False
    refused = studio.post("/api/studio-v3/mcp", json={"jsonrpc": "2.0", "id": 3, "method": "tools/call", "params": {"name": "backtest", "arguments": {"payload": {"spec": {**SMA, "entry_long": "close < 0"}, **SETTINGS}}}}).json()
    assert refused["result"]["isError"] and refused["result"]["structuredContent"]["refused"]


def test_bars_endpoint_serves_the_same_closes_as_the_backtest(studio):  # C-2
    got = studio.get("/api/studio-v3/bars?symbols=AAA,DEAD&from=2015-06-01&to=2015-12-31").json()
    p = data.panel(["AAA"], "2015-06-01", "2015-12-31")
    assert [b["close"] for b in got["bars"]["AAA"]] == p.close[:, 0].tolist() and got["bars"]["AAA"][0]["time"] == str(p.dates[0].date())
    weekly = studio.get("/api/studio-v3/bars?symbols=AAA&tf=1w&from=2015-06-01&to=2015-06-30").json()["bars"]["AAA"]
    week = pd.Series(data.panel(["AAA"], "2015-06-01", "2015-06-30").close[:, 0], index=data.panel(["AAA"], "2015-06-01", "2015-06-30").dates).resample("W-FRI").last()
    assert [b["close"] for b in weekly] == week.tolist()
    assert studio.get("/api/studio-v3/bars?symbols=AAA&tf=5m").status_code == 422


def test_manifest_lists_the_backtest_feature(studio):
    m = studio.get("/api/studio-v3/features").json()
    assert m["features"][0]["id"] == "st01" and {i["key"] for i in m["features"][0]["inputs"]} >= {"strategy_id", "symbols", "fill", "commission_bps", "capital", "benchmark"}
    assert json.dumps(m)


def test_every_template_compiles_and_trades_only_on_past_bars(studio):
    got = studio.get("/api/studio-v3/templates").json()["templates"]
    assert len(got) == 20 and len({t["name"] for t in got}) == 20
    p = fixture_panel(400)
    bars = {f: getattr(p, f)[:, :3] for f in data.FIELDS}
    for t in got:
        spec = Strategy(**t["spec"])
        assert C.compile_spec(spec)["ok"], t["name"]
        assert t["rule"] and t["description"]
        C.signals(spec, bars, p.dates)


def test_trade_monte_carlo_keeps_the_trades():
    from app.services.studio_v3.core import paths
    pnl = np.array([100.0, -50, 30, -20, 80, -10, 40, -60, 20, 10, -30, 50])
    mc = paths.trade_monte_carlo(pnl, 1000.0, n=200)
    assert mc["fan"][-1]["p5"] == pytest.approx(1000 + pnl.sum()) and mc["fan"][-1]["p95"] == pytest.approx(1000 + pnl.sum())  # every reshuffle ends at the same equity
    assert mc["streak_actual"] == 1 and sum(r["share"] for r in mc["streaks"]) == pytest.approx(1)
    assert [r["probability"] for r in mc["ruin"]] == sorted((r["probability"] for r in mc["ruin"]), reverse=True)


@pytest.mark.parametrize(("text", "fields", "exits", "unmatched"), [
    ("buy when the 50 day sma crosses above the 200 day sma; sell when rsi(2) above 70; stop 8%",
     {"entry_long": "crosses_above(sma(close, 50), sma(close, 200))", "exit_long": "(rsi(close, 2) > 70)"}, {"stop": 0.08}, []),
    ("buy a new 52 week high when the weekly trend is up, trailing stop of 10%, purple elephants",
     {"entry_long": "(close >= highest(high, 252)) & (weekly(close) > weekly(sma(close, 30)))"}, {"trail": 0.1}, ["purple", "elephants"]),
])
def test_plain_english_rules(text, fields, exits, unmatched):
    from app.services.studio_v3.core import compile as C
    from app.services.studio_v3.core import plain
    from app.services.studio_v3.core.spec import Strategy
    out = plain.to_spec(text)
    assert (out["fields"], out["exits"], out["unmatched"]) == (fields, exits, unmatched)
    assert C.compile_spec(Strategy(**out["fields"], exits=out["exits"]))["ok"]
    with pytest.raises(ValueError):
        plain.to_spec("make me rich")


def test_repaint_check_passes_a_causal_rule():
    from app.services.studio_v3.core import backtest as B
    from app.services.studio_v3.core.spec import Strategy
    out = B.preview(Strategy(entry_long="crosses_above(sma(close, 10), sma(close, 30))", exit_long="close < sma(close, 30)"), "SPY")
    assert out["repaint"]["cuts"] >= 40 and out["repaint"]["changed"] == 0


def test_agent_validate_and_holdout_budget(studio):  # V-5 through MCP
    sid = studio.post("/api/studio-v3/strategies", json={"spec": SMA}).json()["id"]

    def call(name, **payload):
        return studio.post("/api/studio-v3/mcp", json={"jsonrpc": "2.0", "id": 1, "method": "tools/call", "params": {"name": name, "arguments": {"payload": {"strategy_id": sid, **SETTINGS, **payload}}}}).json()["result"]

    v = call("validate", show_holdout=True)
    assert not v["isError"] and v["structuredContent"]["grade"]["grade"] in "ABCDF"
    assert studio.get(f"/api/studio-v3/strategies/{sid}/holdout").json()["looks"] == []  # show_holdout is ignored for agents on validate
    for left in (2, 1, 0):
        assert call("open_holdout")["structuredContent"]["looks_left_for_agents"] == left
    refused = call("open_holdout")
    assert refused["isError"] and "budget" in refused["structuredContent"]["reason"]


def test_market_rule_blocks_entries_and_closes_everything_when_off():
    import pandas as pd

    from app.services.studio_v3.core import compile as C
    from app.services.studio_v3.core.spec import Strategy

    n, k = 60, 2
    c = np.ones((n, k)) * 100
    mkt = np.r_[np.full(30, 200.0), np.full(30, 100.0)]  # market falls at bar 30
    bars = {"open": c, "high": c, "low": c, "close": c, "volume": c, "market": np.repeat(mkt[:, None], k, axis=1)}
    s = Strategy(entry_long="close > 0", market_filter="market > 150")
    sig = C.signals(s, bars, pd.bdate_range("2020-01-01", periods=n))
    assert (sig.entries[:30] == 1).all() and (sig.entries[30:] == 0).all() and (sig.exits[30:] & 1).all()


def test_rule_check_passes_on_target_and_fails_on_daily_loss():
    import pandas as pd

    from app.services.studio_v3.core import paths

    dates = pd.bdate_range("2020-01-01", periods=60)
    up = 100 * 1.01 ** np.arange(60)  # +1% a day: hits +10% on day 10
    r = paths.rule_check(up, dates, target=0.10, daily_loss=0.05, max_dd=0.10, min_days=5, every=30)
    assert r["pass"] == r["starts"] and r["rows"][0]["days"] == 10
    crash = up.copy()
    crash[3:] *= 0.9  # one -10% day
    assert paths.rule_check(crash, dates, 0.10, 0.05, 0.10, 5, every=60)["fail_daily_loss"] == 1


def test_build_preview_returns_runner_output_and_runtime_problem(studio):
    url = "/api/studio-v3/preview"
    code = """class Strategy:
    warmup = 2
    def on_bar(self, ctx):
        if ctx.bar == 2:
            ctx.log("ready")
            ctx.plot("close", ctx.close[-1])
        ctx.buy()
"""
    result = studio.post(url, json={"spec": {"code": code}, "symbol": "SPY"}).json()
    assert result["logs"] == [{"date": "2015-01-05", "symbol": "SPY", "line": 5, "text": "ready", "level": "info"}]
    assert result["plots"]["close"] == [{
        "date": "2015-01-05", "symbol": "SPY", "value": fixture_panel().close[2, -1],
    }]

    error = studio.post(url, json={"spec": {"code": code.replace("ctx.close[-1]", "ctx.close[1]")}}).json()
    assert error["status"] == "error"
    assert error["problem"]["line"] == 6
    assert error["problem"]["exception_type"] == "IndexError"


def test_python_preview_fills_match_formula_trades(studio):
    url = "/api/studio-v3/preview"
    base = {"sizing": {"mode": "shares", "value": 5}}
    formula_spec = base | SMA
    expected = studio.post(url, json={"spec": formula_spec}).json()
    code = C.pycode.from_formulas(Strategy(**formula_spec)) + '''
    def on_fill(self, ctx, fill):
        ctx.log((fill.symbol, fill.side, fill.quantity, fill.price, fill.date, fill.fee))
'''
    actual = studio.post(url, json={"spec": formula_spec | {"code": code}}).json()
    assert actual["trades"]
    assert len(actual["trades"]) == len(expected["trades"])
    for got, want in zip(actual["trades"], expected["trades"], strict=True):
        assert {k: got[k] for k in ("entry_date", "exit_date", "side")} == {k: want[k] for k in ("entry_date", "exit_date", "side")}
        assert [got[k] for k in ("entry", "exit", "shares", "pnl")] == pytest.approx([want[k] for k in ("entry", "exit", "shares", "pnl")])
    assert all(row["symbol"] == "SPY" and "'SPY'" in row["text"] for row in actual["logs"])
    assert actual["logs"]


def test_full_backtest_runs_python_without_formula_rules(studio):
    spec = Strategy(code="""class Strategy:
    def on_bar(self, ctx):
        if ctx.bar == 1:
            ctx.buy()

    def on_fill(self, ctx, fill):
        ctx.log(fill.side)
        if fill.side == "buy":
            ctx.sell()
""")
    result = backtest.run_backtest(spec, Settings(symbols=["SPY"], benchmark=""))
    assert result["meta"]["entry_signals"] == 1
    assert result["meta"]["logs"][0]["text"] == "buy"
    assert result["meta"]["logs"][1]["text"] == "sell"
    assert len(result["tables"]["trades"]) == 1
    assert result["tables"]["trades"][0]["entry_date"] == "2015-01-05"
    assert result["tables"]["trades"][0]["exit_date"] == "2015-01-06"


def test_monthly_rule_uses_last_closed_calendar_month():
    dates = pd.DatetimeIndex(["2024-01-30", "2024-01-31", "2024-02-01", "2024-02-29", "2024-03-01"])
    close = np.array([[10, 20], [11, np.nan], [12, 22], [13, 23], [14, 24]], dtype=float)
    bars = {field: close for field in data.FIELDS}
    values = formula.evaluate("monthly(close)", bars, dates)
    np.testing.assert_array_equal(values, [[np.nan, np.nan], [np.nan, np.nan], [11, 20], [11, 20], [13, 23]])
    for cutoff in range(1, len(dates)):
        prefix = {field: series[:cutoff] for field, series in bars.items()}
        np.testing.assert_array_equal(formula.evaluate("monthly(close)", prefix, dates[:cutoff]), values[:cutoff])


def test_build_condition_explains_when_a_rule_fired(studio):
    endpoint = "/api/studio-v3/build/condition"
    request = {"symbol": "SPY", "spec": {"params": {"limit": {"value": 0}}}}
    false = studio.post(endpoint, json=request | {"expression": "close < limit"}).json()
    assert false["observations"] > 0 and false["constant"] is False
    assert false["true_rate"] == 0 and false["fired_dates"] == [] and false["last_true_date"] is None

    true = studio.post(endpoint, json=request | {"expression": "close > limit"}).json()
    assert true["true_count"] == true["observations"] and true["constant"] is True
    assert true["true_rate"] == 1 and true["last_true_date"] == true["fired_dates"][-1]

    mixed = studio.post(endpoint, json=request | {"expression": "close > open"}).json()
    assert 0 < mixed["true_rate"] < 1 and mixed["constant"] is None
    assert mixed["true_count"] == len(mixed["fired_dates"])

    error = studio.post(endpoint, json=request | {"expression": "future(close)"})
    assert error.status_code == 422 and "Look-ahead" in error.json()["detail"]["message"]


def test_compile_counts_rules_and_independent_tunable_parameters(studio):
    spec = {
        "entry_long": "(close > sma(close, period)) & ((volume > 0) | (open < close))",
        "exit_long": "close < sma(close, period)",
        "market_filter": "market > floor",
        "score": "roc(close, period)",
        "params": {
            "period": {"value": 10, "min": 5, "max": 20, "step": 1},
            "floor": {"value": 100},
            "unused": {"value": 1, "min": 0, "max": 2},
        },
    }
    result = studio.post("/api/studio-v3/compile", json={"spec": spec}).json()
    assert result["ok"]
    assert result["complexity"] == {"parameter_count": 3, "formula_rule_count": 5, "degrees_of_freedom": 1}


@pytest.mark.parametrize(("blocks", "params", "expected"), [
    (200, 8, {}),
    (201, 9, {"blocks": "warning", "params": "warning"}),
    (1000, 8, {"blocks": "warning"}),
    (1001, 8, {"blocks": "error"}),
])
def test_build_compile_checks_strategy_limits(studio, blocks, params, expected):
    spec = {
        "entry_long": "close > 0",
        "exit_long": "close < 0",
        "blocks": [{}] * blocks,
        "params": {f"p{i}": {"value": 1, "min": 0, "max": 2} for i in range(params)},
    }
    result = studio.post("/api/studio-v3/compile", json={"spec": spec}).json()
    limits = {item["token"]: item["severity"] for item in result["findings"] if item["token"] in {"blocks", "params"}}
    assert limits == expected
    assert result["ok"] is ("error" not in expected.values())


def test_formula_condition_kinds_are_causal():
    dates = pd.DatetimeIndex(["2024-01-30", "2024-01-31", "2024-02-01", "2024-02-02", "2024-02-05"])
    close = np.array([[10, 20], [11, 21], [12, 22], [11, 20], [10, 19]], dtype=float)
    bars = {field: close for field in data.FIELDS}
    expected = {
        "for_bars(close > 10, 2)": [False, False, True, True, False],
        "rising(close, 2)": [False, False, True, False, False],
        "falling(close, 2)": [False, False, False, False, True],
        "month_start()": [True, False, True, False, False],
        "week_start()": [True, False, False, False, True],
        "zscore(close) < 0": [True, True, True, True, True],
    }
    for expression, result in expected.items():
        np.testing.assert_array_equal(formula.evaluate(expression, bars, dates)[:, 0], result)
        prefix = {field: series[:-1] for field, series in bars.items()}
        np.testing.assert_array_equal(formula.evaluate(expression, prefix, dates[:-1])[:, 0], result[:-1])


def test_build_check_reports_python_problems_with_editor_locations(studio):
    code = """import os
class Strategy:
    def on_bar(self, ctx):
        unused = 2
        print(missing, math.sqrt(4))
        print(ctx.close[+1])
"""
    response = studio.post("/api/studio-v3/build/check", json={"code": code})
    assert response.status_code == 200
    problems = response.json()["problems"]
    assert [(item["line"], item["code"]) for item in problems] == [
        (1, "studio-check"), (4, "F841"), (5, "print-in-loop"), (5, "F821"),
        (6, "print-in-loop"), (6, "look-ahead"),
    ]
    assert problems[1]["severity"] == "warning"
    assert problems[3]["file"] == "main.py" and problems[3]["column"] == 15


def test_build_completion_and_signature_use_portfolio_and_local_members(studio):
    code = """class Strategy:
    def on_data(self, ctx):
        self.counter = 1

    def threshold(self, level=5):
        return self.counter > level
"""
    base = "/api/studio-v3/build"
    result = studio.post(f"{base}/complete", json={"scope": "ctx", "code": code, "prefix": "market"}).json()
    assert {item["name"] for item in result} == {"market", "market_order"}
    signature = studio.post(f"{base}/signature", json={"scope": "ctx", "code": code, "name": "market_order"}).json()
    assert signature["signature"] == "market_order(symbol, quantity)"
    local = studio.post(f"{base}/complete", json={"scope": "self", "code": code}).json()
    members = {item["name"]: item["signature"] for item in local}
    assert {"counter": None, "on_data": "on_data(ctx)", "threshold": "threshold(level=5)"}.items() <= members.items()
    assert {"sma", "ema", "rsi", "atr", "std", "roc", "highest", "lowest"} <= set(members)
    holding = studio.post(f"{base}/complete", json={"scope": "position", "prefix": "quant"}).json()
    assert holding[0]["name"] == "quantity"


def test_build_definition_returns_local_python_declarations(studio):
    code = """def helper(value):
    return value + 1

class Strategy:
    def on_bar(self, ctx):
        self.counter = helper(ctx.bar)
"""
    endpoint = "/api/studio-v3/build/definition"
    result = studio.post(endpoint, json={"code": code, "line": 6, "column": 25})
    assert result.status_code == 200
    assert result.json() == [{"file": "main.py", "name": "helper", "line": 1, "column": 5}]
    assert studio.post(endpoint, json={"code": code, "line": 20, "column": 1}).json() == []


def test_build_completion_suggests_formula_inputs_and_snippets(studio):
    endpoint = "/api/studio-v3/build/complete"
    result = studio.post(endpoint, json={"scope": "formula", "prefix": "sma"}).json()
    assert result[0]["insert_text"] == "sma(${1:x}, ${2:n})"
    assert result[0]["signature"] == "sma(x, n)"
    for scope, extra, prefix, expected in [
        ("history_field", {}, "cl", "close"),
        ("param", {"params": ["fast", "slow"]}, "fa", "fast"),
        ("symbol", {"symbols": ["SPY", "QQQ"]}, "SP", "SPY"),
    ]:
        choices = studio.post(endpoint, json={"scope": scope, "prefix": prefix, **extra}).json()
        assert [item["name"] for item in choices] == [expected]


def test_python_preview_returns_chart_markers_and_structured_tables(studio):
    code = """class Strategy:
    def on_bar(self, ctx):
        if ctx.bar == 1:
            ctx.plot("price", ctx.close[-1], chart="main", color="#ff9900", width=2)
            ctx.hline(70, color="red")
            ctx.fill("price", "price")
            ctx.bgcolor("#00ff0022")
            ctx.mark(ctx.symbol, "review")
            ctx.table("signals", {"count": 2, "confirmed": True})
"""
    result = studio.post("/api/studio-v3/preview", json={"symbol": "SPY", "spec": {"code": code}}).json()
    assert result["status"] == "ok"
    assert result["plot_charts"] == {"price": "main"}
    assert result["draw"] == {
        "styles": {"price": {"color": "#ff9900", "width": 2, "style": "line"}},
        "hlines": [{"value": 70.0, "chart": "own", "color": "red", "name": ""}],
        "fills": [{"a": "price", "b": "price", "color": None}],
        "bg": [{"date": "2015-01-02", "color": "#00ff0022"}],
    }
    assert result["marks"] == [{"date": "2015-01-02", "symbol": "SPY", "label": "review"}]
    assert result["tables"]["signals"] == [
        {"date": "2015-01-02", "symbol": "SPY", "cells": {"count": 2, "confirmed": True}},
    ]


def test_project_files_keep_immutable_versions_and_reject_stale_changes(studio):
    strategy = studio.post("/api/studio-v3/strategies", json={"spec": {"name": "Project", "code": "class Strategy: pass\n"}}).json()
    url = f"/api/studio-v3/strategies/{strategy['id']}/files"
    assert studio.get(url).json() == {"version": 1, "files": {"main.py": "class Strategy: pass\n"}}

    def change(operation, name, base_version, **extra):
        return studio.patch(url, json={"operation": operation, "name": name, "base_version": base_version, **extra})

    assert change("create", "../bad.py", 1).status_code == 422
    assert change("create", "helpers.py", 1, source="value = 1\n").json()["version"] == 2
    assert change("save", "helpers.py", 1, source="value = 2\n").status_code == 409
    assert change("rename", "helpers.py", 2, new_name="signals.py").json()["version"] == 3
    assert change("save", "signals.py", 3, source="value = 2\n").json()["version"] == 4
    assert change("delete", "main.py", 4).status_code == 422
    assert change("delete", "signals.py", 4).json()["version"] == 5
    old = studio.get(url, params={"version": 4, "base_version": 3}).json()
    assert old["files"]["signals.py"] == "value = 2\n"
    assert "-value = 1\n+value = 2" in old["diffs"]["signals.py"]
    assert studio.get(url).json()["files"] == {"main.py": "class Strategy: pass\n"}


def test_project_preview_runs_saved_helper_modules_and_locates_errors(studio):
    code = """from signals import calculate

class Strategy:
    def on_bar(self, ctx):
        if ctx.bar == 1:
            ctx.plot("signal", calculate(ctx))
"""
    request = {"symbol": "SPY", "spec": {
        "code": code,
        "files": {
            "signals.py": "from inputs import threshold\ndef calculate(ctx):\n    return ctx.value('close') > threshold\n",
            "inputs.py": "threshold = 0\n",
        },
    }}
    endpoint = "/api/studio-v3/preview"
    result = studio.post(endpoint, json=request).json()
    assert result["status"] == "ok"
    assert result["plots"]["signal"][0]["value"] == 1
    request["spec"]["files"]["signals.py"] = "def calculate(ctx):\n    return 1 / 0\n"
    error = studio.post(endpoint, json=request).json()
    assert error["problem"]["file"] == "signals.py" and error["problem"]["line"] == 2
    assert [frame["file"] for frame in error["problem"]["traceback"]] == ["main.py", "signals.py"]
    request["spec"]["files"]["signals.py"] = "import os\n"
    checked = studio.post("/api/studio-v3/compile", json={"spec": request["spec"]}).json()
    assert not checked["ok"]
    assert checked["findings"][0]["file"] == "signals.py"


def test_build_definition_follows_only_project_imports(studio):
    endpoint = "/api/studio-v3/build/definition"
    request = {
        "code": "from helper import signal\nresult = signal()", "line": 2, "column": 11,
        "files": {"helper.py": "def signal():\n    return 1\n"},
    }
    assert studio.post(endpoint, json=request).json() == [
        {"file": "helper.py", "name": "signal", "line": 1, "column": 5},
    ]
    invalid = studio.post(endpoint, json=request | {"files": {"../outside.py": "x = 1"}})
    assert invalid.status_code == 422


def test_build_references_and_rename_preview_cover_project_files(studio):
    root = "/api/studio-v3/build"
    request = {
        "code": "from helper import signal\nresult = signal()\n", "line": 2, "column": 11,
        "files": {"helper.py": "def signal():\n    return 1\n"},
    }
    references = studio.post(f"{root}/references", json=request).json()
    assert {(item["file"], item["line"]) for item in references} == {
        ("main.py", 1), ("main.py", 2), ("helper.py", 1),
    }
    renamed = studio.post(f"{root}/rename", json=request | {"new_name": "forecast"}).json()
    assert renamed == {
        "main.py": "from helper import forecast\nresult = forecast()\n",
        "helper.py": "def forecast():\n    return 1\n",
    }
    assert studio.post(f"{root}/rename", json=request | {"new_name": "for"}).status_code == 422


def test_build_outline_lists_nested_methods_and_indicators(studio):
    code = """def helper():
    pass

class Strategy:
    def on_bar(self, ctx):
        if ctx.bar > 2:
            self.fast = ctx.value("sma(close, 3)")
        price = ctx.close[-1]
"""
    endpoint = "/api/studio-v3/build/outline"
    helper, strategy = studio.post(endpoint, json={"code": code}).json()
    assert (helper["name"], helper["kind"], helper["line"]) == ("helper", "function", 1)
    assert (strategy["name"], strategy["kind"], strategy["line"]) == ("Strategy", "class", 4)
    method, = strategy["children"]
    indicator, = method["children"]
    assert method["kind"] == "method" and method["name"] == "on_bar"
    assert (indicator["name"], indicator["kind"], indicator["line"]) == ("self.fast", "indicator", 7)
    assert studio.post(endpoint, json={"code": "class"}).json() == []


def test_build_check_lints_project_helper_and_unreachable_orders(studio):
    code = """from config import threshold

def handle(ctx):
    if False:
        ctx.buy()
    if threshold > 0:
        return
        ctx.liquidate()
    ctx.sell()
"""
    response = studio.post("/api/studio-v3/build/check", json={
        "file": "helper.py", "code": code, "files": {"config.py": "threshold = 3"},
    })
    assert response.status_code == 200
    assert [(p["file"], p["line"], p["code"]) for p in response.json()["problems"]] == [
        ("helper.py", 5, "unreachable-order"), ("helper.py", 8, "unreachable-order"),
    ]


def test_build_debug_steps_between_observed_bars_and_reports_orders_and_fills(studio):
    code = """class Strategy:
    def init(self, ctx):
        self.counter = 0

    def on_bar(self, ctx):
        self.counter += 1
        if self.counter == 2:
            ctx.buy()
"""
    path = "/api/studio-v3/build/debug"
    payload = {"symbol": "SPY", "date": "2015-01-02", "spec": {"code": code}}
    first = studio.post(path, json=payload)
    assert first.status_code == 200
    snapshot = first.json()
    assert snapshot["state"] == {"counter": 2}
    assert snapshot["fills"] == []
    assert snapshot["orders"][0]["quantity_or_direction"] == 1
    assert snapshot["next_date"] == "2015-01-05"
    second = studio.post(path, json=payload | {"step": 1}).json()
    assert second["date"] == snapshot["next_date"]
    assert second["state"] == {"counter": 3}
    assert second["previous_date"] == snapshot["date"]
    assert second["fills"][0]["symbol"] == "SPY"
    assert second["fills"][0]["side"] == "buy"
    assert second["context"]["quantity"] == second["fills"][0]["quantity"]
    assert studio.post(path, json=payload).json() == snapshot


def test_build_debug_jumps_to_the_next_order_or_fill(studio):
    source = """class Strategy:
    def on_bar(self, ctx):
        if ctx.bar == 3:
            ctx.buy()
"""
    path = "/api/studio-v3/build/debug"
    payload = {"symbol": "SPY", "date": "2015-01-01", "spec": {"code": source}}
    order = studio.post(path, json=payload | {"event": "order"}).json()
    assert order["bar_index"] == 3 and order["orders"][0]["symbol"] == "SPY"
    assert order["fills"] == []
    fill = studio.post(path, json=payload | {"event": "fill"}).json()
    assert fill["bar_index"] == 4 and fill["fills"][0]["side"] == "buy"
    assert fill["previous_date"] == order["date"]
    assert studio.post(path, json=payload | {"date": fill["date"], "event": "fill"}).status_code == 422
    assert studio.post(path, json=payload | {"event": "order", "step": 1}).status_code == 422


def test_build_debug_finds_a_conditional_breakpoint_in_a_helper(studio):
    source = """from helper import check

class Strategy:
    def on_bar(self, ctx):
        check(ctx)
"""
    path = "/api/studio-v3/build/debug"
    body = {
        "symbol": "SPY", "date": "2015-01-01",
        "spec": {"code": source, "files": {"helper.py": "def check(ctx):\n    local_value = ctx.bar * 2\n    return local_value\n"}},
        "breakpoint": {"file": "helper.py", "line": 3, "condition": "ctx.symbol == 'SPY' and ctx.date >= '2015-01-05'"},
    }
    result = studio.post(path, json=body)
    assert result.status_code == 200
    result = result.json()
    assert result["date"] == "2015-01-05"
    assert result["breakpoint"]["file"] == "helper.py" and result["breakpoint"]["line"] == 3
    assert result["breakpoint"]["hit_count"] == 1
    assert result["breakpoint"]["locals"]["local_value"] == 4
    invalid = {"file": "helper.py", "line": 3, "condition": "ctx.buy()"}
    assert studio.post(path, json=body | {"breakpoint": invalid}).status_code == 422


def test_build_debug_breakpoint_stops_on_the_nth_hit_and_after_its_trigger(studio):
    code = "class Strategy:\n    def on_bar(self, ctx):\n        a = ctx.t\n        b = a + 1\n        c = b + 1\n"
    body = {"symbol": "SPY", "date": "2015-01-01", "spec": {"code": code}, "breakpoint": {"file": "main.py", "line": 4}}
    path = "/api/studio-v3/build/debug"
    first = studio.post(path, json=body).json()["breakpoint"]
    third = studio.post(path, json=body | {"breakpoint": {"file": "main.py", "line": 4, "hit": 3}}).json()["breakpoint"]
    assert third["hit_count"] == 3 and third["locals"]["a"] > first["locals"]["a"]
    after = {"file": "main.py", "line": 4, "trigger": {"file": "main.py", "line": 5}}  # line 5 only runs after line 4 on the same bar
    assert studio.post(path, json=body | {"breakpoint": after}).json()["breakpoint"]["hit_count"] == 1
    assert studio.post(path, json=body | {"breakpoint": {**after, "trigger": {"file": "main.py", "line": 99}}}).status_code == 422


def test_build_debug_data_breakpoint_stops_where_a_value_changes(studio):
    code = "class Strategy:\n    def __init__(self):\n        self.n = 0\n    def on_bar(self, ctx):\n        if ctx.t % 10 == 0:\n            self.n += 1\n        x = 1\n"
    body = {"symbol": "SPY", "date": "2015-01-01", "spec": {"code": code}, "breakpoint": {"file": "main.py", "line": 6, "watch": "self.n"}}
    hit = studio.post("/api/studio-v3/build/debug", json=body).json()["breakpoint"]
    assert hit["line"] == 7 and hit["watch"]["after"] == hit["watch"]["before"] + 1
    assert studio.post("/api/studio-v3/build/debug", json=body | {"breakpoint": {"file": "main.py", "line": 6, "watch": "1bad"}}).status_code == 422


def test_build_debug_can_stop_on_an_equity_loss(studio):
    url = "/api/studio-v3/build/debug"
    request = {
        "symbol": "SPY", "date": "2015-01-01", "event": "equity", "loss_fraction": 0.01,
        "spec": {"code": "class Strategy:\n    def on_bar(self, ctx):\n        if ctx.bar == 0:\n            ctx.buy()\n"},
    }
    result = studio.post(url, json=request)
    assert result.status_code == 200
    found = result.json()
    assert found["bar_index"] > 0 and found["equity_change"] <= -0.01
    previous = studio.post(url, json={**request, "event": None, "loss_fraction": None, "date": found["previous_date"]}).json()
    assert found["equity_change"] == pytest.approx(found["context"]["total_value"] / previous["context"]["total_value"] - 1)
    assert studio.post(url, json={**request, "loss_fraction": None}).status_code == 422


def test_quantconnect_import_endpoint_returns_code_and_leftovers(studio):  # B-163
    source = """from AlgorithmImports import *


class A(QCAlgorithm):
    def Initialize(self):
        self.AddEquity("SPY", Resolution.Daily)
        self.SetWarmUp(10)

    def OnData(self, data):
        if not self.Portfolio.Invested:
            self.SetHoldings("SPY", 1.0)

    def OnEndOfAlgorithm(self):
        self.Debug("done")
"""
    r = studio.post("/api/studio-v3/build/import-quantconnect", json={"source": source})
    assert r.status_code == 200
    body = r.json()
    assert body["ok"] is True and body["symbols"] == ["SPY"] and body["warmup"] == 10
    assert "class Strategy:" in body["code"] and body["problems"] == []
    assert any("OnEndOfAlgorithm" in row["source"] for row in body["unconverted"])
    assert any("import" in row["source"] for row in body["unconverted"])


def test_build_checks_reports_warmup_data_and_survivorship(studio):  # B-119
    spec = {"symbols": ["AAA", "BBB", "DEAD"], "benchmark": "SPY", "start": "2015-06-01", "end": "2017-06-01"}
    body = {"spec": {"name": "Checks", "entry_long": "crosses_above(sma(close, 50), sma(close, 200))"},
            "settings": spec}
    r = studio.post("/api/studio-v3/build/checks", json=body)
    assert r.status_code == 200
    out = r.json()
    assert out["warmup_bars"] == 201  # 200 bars of the slow average, plus the cross
    assert out["period"][0] == "2015-06-01"
    assert out["universe"]["delisted"] == 1 and "DEAD" in out["universe"]["delisted_names"]
    assert out["survivorship"]["status"] == "ok"
    assert out["data_used"][0]["fields"] == ["close"]
    assert out["data_used"][0]["windows"] == [50, 200]


def test_opposite_signal_and_end_of_week_exits():  # B-120
    p = fixture_panel(120)
    bars = p.bars()
    spec = Strategy(entry_long="close > sma(close, 5)", entry_short="close < sma(close, 5)",
                    exits={"opposite_signal": True})
    sig = C.signals(spec, bars, p.dates)
    assert (sig.exits[sig.entries[:, 0] == -1, 0] & 1 == 1).all()
    assert (sig.exits[sig.entries[:, 0] == 1, 0] & 2 == 2).all()
    weekly = Strategy(entry_long="close > sma(close, 5)", exits={"end_of_week": True})
    weekly_sig = C.signals(weekly, bars, p.dates)
    periods = p.dates.to_period("W-FRI")
    last = np.ones(len(periods), dtype=bool)
    last[:-1] = periods[:-1] != periods[1:]
    assert (weekly_sig.exits[last, 0] == 3).all()
    assert (weekly_sig.exits[~last, 0] == 0).all()


def test_risk_drawdown_flattens_everything_and_stops(studio):
    spec = Strategy(entry_long="close > 0", risk={"max_drawdown": 0.02})
    settings = Settings(**SETTINGS)
    prep = backtest.prepare(settings)
    sig = C.signals(spec, prep.sig_bars, prep.panel.dates)
    bars = prep.panel.bars()
    entries = np.where(np.isfinite(prep.panel.close), sig.entries, 0).astype(np.int8)
    params = backtest.engine_params(spec, settings)
    vector = engine.run(bars, entries, sig.exits, params)
    event = engine.run(bars, entries, sig.exits, params, engine="event")
    assert vector.risk_events and vector.risk_events[0]["kind"] == "drawdown"
    assert vector.risk_events[0]["value"] <= -0.02 and vector.risk_events[0]["limit"] == 0.02
    assert event.risk_events[0]["bar"] == vector.risk_events[0]["bar"]
    assert np.array_equal(vector.equity, event.equity) and np.array_equal(vector.trades, event.trades, equal_nan=True)
    bar = vector.risk_events[0]["bar"]
    assert np.allclose(vector.equity[bar + 1:], vector.equity[bar + 1])
    assert all(x[engine.T_ENTRY_BAR] <= bar for x in vector.trades)
    assert engine.REASONS[int(vector.trades[-1][engine.T_REASON])] in {"risk stop", "open at end"}
    out = backtest.run_backtest(spec, settings)
    assert out["meta"]["risk_events"][0]["kind"] == "drawdown" and out["meta"]["risk_events"][0]["date"]
    assert "Risk:" in out["meta"]["description"]


def test_position_and_gross_caps_hold_at_entry():
    close = np.full((3, 4), 100.0)
    bars = {k: close for k in ("open", "high", "low", "close")} | {"volume": np.full((3, 4), 1e9)}
    entries = np.zeros((3, 4), dtype=np.int8)
    entries[0] = 1
    exits = np.zeros((3, 4), dtype=np.int8)
    per_name = engine.run(bars, entries, exits, engine.Params(commission_bps=0, slippage_bps=0, max_position=0.1))
    free = engine.run(bars, entries, exits, engine.Params(commission_bps=0, slippage_bps=0))
    assert len(per_name.trades) == 4
    assert np.allclose(per_name.trades[:, engine.T_SHARES] * per_name.trades[:, engine.T_ENTRY_PX], 10_000)
    assert np.allclose(free.trades[:, engine.T_SHARES] * free.trades[:, engine.T_ENTRY_PX], 25_000)
    gross = engine.run(bars, entries, exits, engine.Params(commission_bps=0, slippage_bps=0, max_gross=0.25))
    event = engine.run(bars, entries, exits, engine.Params(commission_bps=0, slippage_bps=0, max_gross=0.25), engine="event")
    assert np.allclose(gross.gross_exposure[1:], 0.25) and np.allclose(event.gross_exposure[1:], 0.25)
    assert np.array_equal(gross.trades, event.trades, equal_nan=True) and gross.unfilled == event.unfilled == 3


def test_daily_loss_stop_halts_both_engines_on_the_same_bar():
    close = np.array([[100.0], [100.0], [96.0], [92.0], [90.0]])
    bars = {k: close for k in ("open", "high", "low", "close")} | {"volume": np.ones_like(close)}
    entries = np.zeros((5, 1), dtype=np.int8)
    entries[0, 0] = 1
    exits = np.zeros((5, 1), dtype=np.int8)
    params = engine.Params(commission_bps=0, slippage_bps=0, max_daily_loss=0.03)
    vector = engine.run(bars, entries, exits, params)
    event = engine.run(bars, entries, exits, params, engine="event")
    assert vector.risk_events == [{"bar": 2, "kind": "daily_loss", "value": pytest.approx(-0.04), "limit": 0.03}]
    assert event.risk_events[0]["bar"] == 2 and event.risk_events[0]["kind"] == "daily_loss"
    assert np.array_equal(vector.equity, event.equity) and np.array_equal(vector.trades, event.trades, equal_nan=True)
    assert np.allclose(vector.equity[3:], 92_000)


def test_python_engine_settings_from_code_beat_the_card(studio):
    from app.services.studio_v3.core import pycode

    code = """class Strategy:
    fill = "same_close"
    commission_bps = 0
    slippage_bps = 0
    max_positions = 1

    def on_data(self, ctx):
        for symbol in ctx.symbols:
            if ctx.pos(symbol).quantity == 0:
                ctx.set_holdings(symbol, 0.5)
"""
    assert pycode.engine_overrides(code) == {"fill": "same_close", "commission_bps": 0, "slippage_bps": 0, "max_positions": 1}
    assert pycode.engine_overrides('class Strategy:\n    fill = "soon"\n    max_positions = -1\n') == {}
    spec = Strategy(code=code)
    out = backtest.run_backtest(spec, Settings(**SETTINGS))
    assert out["meta"]["settings_overrides"] == {"fill": "same_close", "commission_bps": 0, "slippage_bps": 0, "max_positions": 1}
    assert out["meta"]["costs_off"] is True and out["meta"]["fill_model"] == "same_close"
    assert max(row["positions"] for row in out["charts"]["exposure"]) <= 1
    trades = out["tables"]["trades"]
    assert trades and all(t["signal_date"] == t["entry_date"] for t in trades)
    preview = studio.post("/api/studio-v3/preview", json={"spec": spec.model_dump(), "symbol": "AAA"}).json()
    assert preview["settings_overrides"]["fill"] == "same_close"
    assert all(t["signal_date"] == t["entry_date"] for t in preview["trades"])


def test_profit_target_ladder_takes_two_rungs_then_the_rest():
    close = np.array([[100.0], [100.0], [115.0], [125.0], [140.0]])
    bars = {k: close for k in ("open", "high", "low", "close")} | {"volume": np.ones_like(close)}
    entries = np.zeros((5, 1), dtype=np.int8)
    entries[0, 0] = 1
    exits = np.zeros((5, 1), dtype=np.int8)
    params = engine.Params(commission_bps=0, slippage_bps=0, scale_at=0.1, scale_frac=0.3, scale_at2=0.2, scale_frac2=0.5, target=0.3)
    rows = {}
    for name in ("vector", "event"):
        result = engine.run(bars, entries, exits, params, engine=name)
        rows[name] = [(engine.REASONS[int(x[engine.T_REASON])], round(x[engine.T_SHARES], 1), int(x[engine.T_EXIT_BAR])) for x in result.trades]
    assert rows["vector"] == [("scale out", 300.0, 2), ("scale out", 350.0, 3), ("target", 350.0, 4)]
    assert rows["event"] == rows["vector"]
    spec = Strategy(entry_long="close > 0", exits={"scale_at": 0.1, "scale_frac": 0.3, "scale_at2": 0.2, "scale_frac2": 0.5})
    assert "then 50% at 20%" in C.describe(spec)


def test_risk_parity_sizes_by_inverse_volatility(studio):
    spec = Strategy(entry_long="close > sma(close, 20)", exit_long="close < sma(close, 20)", sizing={"mode": "risk_parity"})
    assert C.compile_spec(spec)["ok"]  # weight by risk needs no size value and no rank rule
    settings = Settings(**SETTINGS)
    prep = backtest.prepare(settings)
    sig = C.signals(spec, prep.sig_bars, prep.panel.dates)
    assert sig.size_vol is not None
    bars = prep.panel.bars()
    entries = np.where(np.isfinite(prep.panel.close), sig.entries, 0).astype(np.int8)
    result = engine.run(bars, entries, sig.exits, backtest.engine_params(spec, settings), size_vol=sig.size_vol)
    first = [t for t in result.trades if int(t[engine.T_ENTRY_BAR]) == min(int(x[engine.T_ENTRY_BAR]) for x in result.trades)]
    assert len(first) >= 2
    a, b = first[0], first[1]
    vol = sig.size_vol[int(a[engine.T_SIGNAL_BAR])]
    va, vb = vol[int(a[engine.T_SYM])], vol[int(b[engine.T_SYM])]
    ratio = (a[engine.T_SHARES] * a[engine.T_ENTRY_PX]) / (b[engine.T_SHARES] * b[engine.T_ENTRY_PX])
    assert ratio == pytest.approx(min(vb / va, (vb / va)) if vb / va <= 3 else 1.0, rel=0.05)
    same = engine.run(bars, entries, sig.exits, backtest.engine_params(spec, settings), size_vol=sig.size_vol, engine="event")
    assert np.array_equal(result.trades, same.trades, equal_nan=True)


def test_entry_frequency_gates_entries_to_period_starts(studio):
    spec = Strategy(entry_long="close > 0", frequency="week_start")
    settings = Settings(**SETTINGS)
    prep = backtest.prepare(settings)
    sig = C.signals(spec, prep.sig_bars, prep.panel.dates)
    fired = np.flatnonzero(sig.entries.any(axis=1))
    periods = prep.panel.dates.to_period("W-FRI")
    assert len(fired) > 50 and all(periods[t] != periods[t - 1] for t in fired if t)
    assert "Entries only on the first bar of each week" in C.describe(spec)


def test_restore_branch_and_blame_never_delete_versions(studio):
    base = "/api/studio-v3/strategies"
    sid = studio.post(base, json={"spec": {"name": "V", "code": "a = 1\nb = 2\n"}}).json()["id"]
    studio.put(f"{base}/{sid}", json={"spec": {"name": "V", "code": "a = 1\nb = 3\nc = 4\n"}})
    assert [(r["line"], r["version"]) for r in studio.get(f"{base}/{sid}/blame").json()] == [(1, 1), (2, 2), (3, 2)]
    restored = studio.post(f"{base}/{sid}/versions/1/restore").json()
    assert restored["version"] == 3 and restored["spec"]["code"] == "a = 1\nb = 2\n" and len(restored["versions"]) == 3
    branch = studio.post(f"{base}/{sid}/versions/2/branch").json()
    assert branch["id"] != sid and branch["spec"]["code"] == "a = 1\nb = 3\nc = 4\n" and branch["version"] == 1
    assert studio.post(f"{base}/{sid}/versions/9/restore").status_code == 404


def test_on_data_preview_covers_only_the_window_and_describes_on_data(studio):
    from app.services.studio_v3.core import templates

    spec = next(t["spec"] for t in templates.list_python_templates() if t["name"] == "Python momentum rotation")
    result = studio.post("/api/studio-v3/preview", json={"symbol": "SPY", "spec": spec}).json()
    assert result["status"] == "ok"
    start = result["window"]["start"]
    assert start == result["bars"][0]["date"] and result["window"]["end"] == result["bars"][-1]["date"]
    assert all(t["entry_date"] >= start for t in result["trades"])
    assert result["total_return"] < 5
    checked = studio.post("/api/studio-v3/compile", json={"spec": spec}).json()
    assert "on_data" in checked["description"]
    bad = studio.post("/api/studio-v3/build/debug", json={"spec": spec, "symbol": "SPY", "date": "1990-01-02"})
    assert bad.status_code == 422 and "Valid dates run from" in str(bad.json()) and result["window"]["end"] in str(bad.json())


def test_preview_trades_several_symbols_from_the_universe_attribute(studio):
    code = '''class Strategy:
    universe = ["AAA", "BBB", "CCC"]
    warmup = 5

    def on_data(self, ctx):
        if ctx.bar_index == 5:
            ctx.target_weights({"AAA": 0.3, "BBB": 0.3, "CCC": 0.3})
'''
    result = studio.post("/api/studio-v3/preview", json={"symbol": "SPY", "spec": {"code": code}}).json()
    assert result["status"] == "ok" and result["symbols"] == ["AAA", "BBB", "CCC"]
    assert set(result["bars_by_symbol"]) == {"AAA", "BBB", "CCC"} and result["bars"] == result["bars_by_symbol"]["AAA"]
    spread = code.replace('ctx.target_weights({"AAA": 0.3, "BBB": 0.3, "CCC": 0.3})', "ctx.target_weights({s: 0.4 for s in ctx.symbols})")
    explicit = studio.post("/api/studio-v3/preview", json={"symbol": "SPY", "symbols": ["AAA", "BBB"], "spec": {"code": spread}}).json()
    assert explicit["symbols"] == ["AAA", "BBB"]
    assert {t["symbol"] for t in result["trades"]} <= {"AAA", "BBB", "CCC"}
    stats = {r["symbol"]: r for r in result["symbol_stats"]}  # CH-12: per-symbol rows from the server
    assert sum(r["trades"] for r in stats.values()) == len(result["trades"])
    assert all(abs(r["pnl"] - sum(t["pnl"] for t in result["trades"] if t["symbol"] == s)) < 1e-6 and r["max_dd"] <= 0 for s, r in stats.items())
    bracketed = studio.post("/api/studio-v3/preview", json={"symbol": "SPY", "spec": {"code": code, "exits": {"stop": 0.05, "target": 0.1}}}).json()
    assert all(abs(t["stop"] / t["entry"] - 0.95) < 1e-9 and abs(t["target"] / t["entry"] - 1.1) < 1e-9 for t in bracketed["trades"])  # CH-36: levels drawn on the chart
    assert all(t["stop"] is None and t["target"] is None for t in result["trades"])
    spans = result["regimes"]  # CH-49: back-to-back spans over the window, P&L per regime adds up
    assert spans[0]["from"] == result["window"]["start"] and spans[-1]["to"] == result["window"]["end"] and all(x["to"] < y["from"] for x, y in itertools.pairwise(spans))
    assert abs(sum(r["pnl"] for r in result["regime_pnl"]) - sum(t["pnl"] for t in result["trades"])) < 1e-6


def test_nested_any_all_groups_generate_the_formula_and_trade_like_it(studio):
    tree = {"op": "all", "items": [
        "close > sma(close, 20)",
        {"op": "any", "items": ["rsi(close, 14) < 40", {"rule": "close > delay(close, 5)", "enabled": False}, {"op": "all", "items": ["rsi(close, 14) < 60", "volume > 0"]}]},
    ]}
    grouped = Strategy(**{**SMA, "entry_long": "", "groups": {"entry_long": tree}})
    assert grouped.entry_long == "((close > sma(close, 20)) & ((rsi(close, 14) < 40) | ((rsi(close, 14) < 60) & (volume > 0))))"
    plain = Strategy(**{**SMA, "entry_long": grouped.entry_long})
    prep = backtest.prepare(Settings(**SETTINGS))
    a, b = C.signals(grouped, prep.sig_bars, prep.panel.dates), C.signals(plain, prep.sig_bars, prep.panel.dates)
    assert np.array_equal(a.entries, b.entries) and a.entries.any()
    assert Strategy(**SMA).hash() == Strategy(**{**SMA, "groups": {}}).hash()
    deep = "close > 0"
    for _ in range(11):
        deep = {"op": "any", "items": [deep]}
    for bad in ({"entry_long": deep}, {"entry_long": {"op": "xor", "items": []}}, {"score": "close"}, {"entry_long": {"op": "all", "items": [""]}}):
        with pytest.raises(ValueError):
            Strategy(**{**SMA, "groups": bad})
    assert Strategy(**{**SMA, "groups": {"exit_long": {"op": "all", "items": [{"rule": "close > 0", "enabled": False}]}}}).exit_long == ""


def test_plain_english_maps_ambiguous_words_and_says_so(studio):
    text = "Buy when it is Oversold in an uptrend, sell on a golden cross or overbought, stop 5%, banana"
    out = studio.post("/api/studio-v3/plain-english", json={"text": text}).json()
    assert out["fields"]["entry_long"] == "(rsi(close, 14) < 30) & (close > sma(close, 200))"
    assert out["unmatched"] == ["banana"]
    words = [(a["word"], text[a["start"]:a["end"]], a["formula"]) for a in out["assumptions"]]
    assert words == [("Oversold", "Oversold", "(rsi(close, 14) < 30)"), ("uptrend", "uptrend", "(close > sma(close, 200))"),
                     ("golden cross", "golden cross", "crosses_above(sma(close, 50), sma(close, 200))"), ("overbought", "overbought", "(rsi(close, 14) > 70)")]
    assert all(a["meaning"] for a in out["assumptions"])
    assert "Buy when" in out["restated"] and "stop" in out["restated"].lower()
    for phrase in ("breakout", "pullback", "volume spike", "downtrend", "death cross"):
        got = studio.post("/api/studio-v3/plain-english", json={"text": f"buy on a {phrase}"}).json()
        assert got["assumptions"][0]["word"] == phrase and got["unmatched"] == [] and got["fields"]["entry_long"] == got["assumptions"][0]["formula"]


def test_typecheck_reports_type_errors_and_leaves_undefined_names_to_the_linter(studio):
    code = "import numpy as np\nclass Strategy:\n    def on_bar(self, ctx):\n        x: int = 'a'\n        np.foo_bar()\n        print(nope)\n"
    problems = studio.post("/api/studio-v3/build/typecheck", json={"code": code}).json()["problems"]
    assert [(p["line"], p["code"]) for p in problems] == [(4, "ty-invalid-assignment"), (5, "ty-missing-attribute")]


def test_build_debug_step_line_stops_at_the_next_executed_line(studio):
    source = """from helper import check

class Strategy:
    def on_bar(self, ctx):
        check(ctx)
"""
    files = {"helper.py": "def check(ctx):\n    local_value = ctx.bar * 2\n    return local_value\n"}
    path = "/api/studio-v3/build/debug"
    body = {"symbol": "SPY", "date": "2015-01-05", "spec": {"code": source, "files": files},
            "breakpoint": {"file": "helper.py", "line": 2}, "step_line": True}
    result = studio.post(path, json=body)
    assert result.status_code == 200, result.text
    hit = result.json()["breakpoint"]
    assert (hit["file"], hit["line"]) == ("helper.py", 3) and result.json()["date"] == "2015-01-05"
    assert hit["locals"]["local_value"] == 4
    assert studio.post(path, json=body | {"breakpoint": None}).status_code == 422


def test_defensive_symbol_is_held_only_while_the_market_rule_is_false():  # B-122
    import pandas as pd
    import pytest

    from app.services.studio_v3.core import backtest as B
    from app.services.studio_v3.core import compile as C
    from app.services.studio_v3.core.spec import Settings, Strategy

    st = Settings(symbols=["SPY", "TLT"], benchmark="SPY")
    prep = B.prepare(st)
    s = Strategy(entry_long="close > sma(close, 50)", market_filter="market > sma(market, 200)", defensive="TLT")
    on = C.market_on(s, prep.sig_bars, prep.panel.dates)[:, prep.panel.symbols.index("TLT")]
    day = {d: i for i, d in enumerate(prep.panel.dates.strftime("%Y-%m-%d"))}
    held = [t for t in B.trades_table(B.simulate(s, prep, st), prep.panel) if t["symbol"] == "TLT"]
    assert held and all(not on[day[t["signal_date"]]] for t in held)
    with pytest.raises(B.Refusal):
        B.simulate(s.model_copy(update={"defensive": "GLD"}), B.prepare(Settings(symbols=["SPY"], benchmark="SPY")), Settings(symbols=["SPY"], benchmark="SPY"))
    assert pd.Series(on).any() and not pd.Series(on).all()


def test_typing_preview_skips_the_look_ahead_replay(studio):  # B-5
    code = "class Strategy:\n    def on_bar(self, ctx):\n        if ctx.rule('close > sma(close, 50)'):\n            ctx.buy()\n        else:\n            ctx.sell()\n"
    fast = studio.post("/api/studio-v3/preview", json={"spec": {"code": code}, "repaint": False}).json()
    full = studio.post("/api/studio-v3/preview", json={"spec": {"code": code}}).json()
    assert "repaint" not in fast and full["repaint"]["cuts"] > 0 and fast["trades"] == full["trades"]


def test_scale_in_adds_first_entry_size_up_to_max_entries():  # B-124
    import numpy as np

    from app.services.studio_v3.core import backtest as B
    from app.services.studio_v3.core.spec import Settings, Strategy

    st = Settings(symbols=["SPY"], benchmark="")
    prep = B.prepare(st)
    base = Strategy(entry_long="close > sma(close, 100)", exit_long="close < sma(close, 100)", sizing={"mode": "pct_equity", "value": 0.3, "max_positions": 1})
    peak = {k: float(np.max(B.simulate(base.model_copy(update={"scale_in": "rsi(close, 2) < 10", "max_entries": k}), prep, st).gross_exposure)) for k in (1, 2, 3)}
    assert peak[1] < 0.45 < peak[2] < 0.75 < peak[3] < 1.05


def test_python_indicator_class_feeds_strategy_and_chart_with_inputs(studio):
    code = """class Band:
    inputs = {"n": (3, 2, 50, 1)}
    chart = "main"
    plots = {"upper": {"color": "#ff9900"}}
    fills = [("upper", "lower")]
    def update(self, ctx):
        w = ctx.history("close", self.inputs["n"]).to_numpy()
        return {"upper": w.max(), "lower": w.min()}

class Strategy:
    def init(self, ctx):
        self.band = self.use(Band)
    def on_bar(self, ctx):
        ctx.table("seen", {"upper": self.band["upper"], "n": self.band.impl.inputs["n"]})
"""
    result = studio.post("/api/studio-v3/preview", json={"symbol": "SPY", "spec": {"code": code, "params": {"Band_n": {"value": 5}}}}).json()
    assert result["status"] == "ok", (result.get("reason"), result.get("problem"))
    assert result["plot_charts"] == {"Band(5).upper": "main", "Band(5).lower": "main"}
    assert result["draw"]["fills"] == [{"a": "Band(5).upper", "b": "Band(5).lower", "color": None}]
    rows = result["tables"]["seen"]
    plotted = {p["date"]: p["value"] for p in result["plots"]["Band(5).upper"]}
    assert all(r["cells"]["n"] == 5 and plotted[r["date"]] == r["cells"]["upper"] for r in rows)  # chart and strategy read the same numbers


def test_timeframe_returns_only_completed_weeks():
    dates = [str(d.date()) for d in pd.bdate_range("2024-01-01", periods=15)]  # Mon 1 Jan .. Fri 19 Jan: three full weeks
    close = np.arange(1.0, 16.0)
    cols = {f: close.copy() for f in ("open", "high", "low", "close")} | {"volume": np.ones(15)}
    ctx = pyrunner.Ctx(cols, {}, {}, "X", dates)
    ctx._t = 4  # Friday of week one: the week is still forming
    assert len(ctx.timeframe("W")["close"]) == 0
    ctx._t = 7  # Wednesday of week two
    week = ctx.timeframe("W")
    assert week["close"][0] == 5.0 and week["open"][0] == 1.0 and week["volume"][0] == 5.0
    ctx._t = 14
    assert [ctx.timeframe("W")["close"][-i] for i in (1, 0)] == [5.0, 10.0]


def test_waterfall_sums_to_net_pnl_and_costs_split(studio):
    out = backtest.run_backtest(Strategy(**SMA), Settings(**SETTINGS))
    steps = {x["step"]: x["value"] for x in out["tables"]["attribution"]}
    net = sum(t["pnl"] for t in out["tables"]["trades"])
    assert steps["Gross gains"] + steps["Gross losses"] + steps["Commissions and borrow"] + steps["Slippage"] == pytest.approx(net, abs=1e-6)
    assert steps["Net P&L"] == pytest.approx(net, abs=1e-6) and steps["Commissions and borrow"] < 0 and steps["Slippage"] < 0
    free = backtest.run_backtest(Strategy(**SMA), Settings(**SETTINGS, costs=Costs(commission_bps=0, slippage_bps=0, borrow_bps=0)))
    assert {x["step"]: x["value"] for x in free["tables"]["attribution"]}["Slippage"] == 0


def test_side_equity_stats_and_event_study(studio):
    out = backtest.run_backtest(Strategy(**SMA), Settings(**SETTINGS))
    stats = {x["side"]: x for x in out["tables"]["side_stats"]}
    assert stats["all"]["net_pnl"] == pytest.approx(stats["long"]["net_pnl"] + stats["short"]["net_pnl"])
    last = out["charts"]["side_equity"][-1]
    assert last["all"] == pytest.approx(100_000 + stats["all"]["net_pnl"]) and last["long"] == pytest.approx(100_000 + stats["long"]["net_pnl"])
    es = out["charts"]["event_study"]
    assert [x["offset"] for x in es] == list(range(-20, 21)) and es[20]["mean"] == 0 and es[20]["coverage"] == 1 and all(0 <= x["coverage"] <= 1 for x in es)


def test_run_settings_and_benchmark_modes(studio):
    out = backtest.run_backtest(Strategy(**SMA), Settings(**SETTINGS))
    rows = {(x["group"], x["setting"]): x["value"] for x in out["tables"]["run_settings"]}
    assert rows[("Run", "engine_version")] == engine.ENGINE_VERSION and rows[("Run", "data_version")] == "fixture" and rows[("Run", "universe_size")] == 4
    assert rows[("Inputs", "benchmark_mode")] == "ticker" and rows[("Parameters", "fast")] == 10
    for mode, label in (("equal_weight", "Equal weight"), ("cash", "Cash")):
        o = backtest.run_backtest(Strategy(**SMA), Settings(**SETTINGS, benchmark_mode=mode))
        assert o["meta"]["benchmark"] == label and o["charts"]["equity_curve"][0]["benchmark"] == 100_000
        assert o["meta"]["total_return"] == out["meta"]["total_return"]
    assert o["charts"]["equity_curve"][-1]["benchmark"] == 100_000
