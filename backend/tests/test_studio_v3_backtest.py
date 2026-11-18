"""Studio v3 phase 1: compile, backtest payload, ledger, strategies and the agent API. Acceptance ids from docs/studio/plan/PAGES.md."""

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
from app.services.studio_v3.core import backtest, data, engine, formula, store
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
    assert "_trial" not in job["result"] and meta["ledger"]["raw"] == 1 and meta["strategy"] == {"id": sid, "version": 1, "name": "SMA cross"}
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
        (1, "studio-check"), (4, "F841"), (5, "F821"), (6, "look-ahead"),
    ]
    assert problems[1]["severity"] == "warning"
    assert problems[2]["file"] == "main.py" and problems[2]["column"] == 15
