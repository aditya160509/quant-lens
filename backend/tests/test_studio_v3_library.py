"""Studio Library: versioned items, cost compare, universes, benchmarks, regimes, crises, safe metrics, profiles (Y-1, 5-8, 10, 12, 16, 18, 35, 36)."""

import pytest
from fastapi.testclient import TestClient

from app.services.studio_v3.core import data, library
from tests.test_studio_v3_backtest import SETTINGS, SMA, studio  # noqa: F401  (fixture)

L = "/api/studio-v3/library"


@pytest.fixture
def lib(studio, tmp_path, monkeypatch) -> TestClient:  # noqa: F811
    monkeypatch.setattr(library, "LIB_PATH", tmp_path / "library.json")
    monkeypatch.setattr(library.backtest, "_universe", lambda s: ["AAA", "BBB", "CCC", "DEAD"])
    return studio


def test_cost_presets_seeded_versioned_archived(lib):  # Y-8
    items = {i["name"]: i for i in lib.get(L, params={"type": "cost_preset"}).json()["items"]}
    assert {"US retail", "IBKR fixed", "IBKR tiered", "Zero commission + spread", "Custom"} <= set(items)
    fixed = items["IBKR fixed"]
    assert fixed["body"]["commission_share"] == 0.005 and fixed["body"]["commission_min"] == 1.0 and fixed["body"]["effective_from"]
    v2 = lib.post(f"{L}/{fixed['id']}/versions", json={"body": {**fixed["body"], "commission_share": 0.004}}).json()
    assert v2["version"] == 2 and lib.get(f"{L}/{fixed['id']}", params={"version": 1}).json()["body"]["commission_share"] == 0.005
    assert lib.post(f"{L}/{fixed['id']}/versions", json={"body": v2["body"]}).json()["version"] == 2  # unchanged: no copy
    assert lib.delete(f"{L}/{fixed['id']}").json()["archived"] is True
    assert fixed["id"] not in [i["id"] for i in lib.get(L).json()["items"]]
    assert lib.post(f"{L}/{fixed['id']}/versions", json={"body": {"commission_bps": -1}}).status_code == 422
    assert lib.get(f"{L}/nope").status_code == 404


def test_cost_compare(lib):  # Y-10
    r = lib.post(f"{L}/cost-compare", json={"payload": {"spec": SMA, **SETTINGS}, "a": {"item_id": "cost-us-retail"}, "b": {"item_id": "cost-ibkr-fixed"}})
    assert r.status_code == 200, r.text
    out = r.json()
    assert out["a"]["profile"] == "US retail" and out["b"]["profile"] == "IBKR fixed"
    assert out["delta"]["total_return"] == pytest.approx(out["b"]["total_return"] - out["a"]["total_return"])
    assert lib.post(f"{L}/cost-compare", json={"payload": {"spec": SMA, **SETTINGS}, "a": {"item_id": "x"}, "b": {"item_id": "cost-us-retail"}}).status_code == 404


def test_universes_static_top_screen_point_in_time(lib):  # Y-5/6/7
    static = lib.post(L, json={"type": "universe", "name": "Mine", "body": {"kind": "static", "symbols": ["aaa", "BBB", "ZZZZ"]}}).json()
    p = lib.post(f"{L}/universe/preview", json={"item_id": static["id"]}).json()
    assert p["members"] == ["AAA", "BBB"] and p["point_in_time"] is False  # unknown symbol never crashes
    top = {"kind": "top_dollar_volume", "n": 2, "lookback": 20, "symbols": ["AAA", "BBB", "CCC", "DEAD"], "rebalance": "M"}
    p = lib.post(f"{L}/universe/preview", json={"body": top}).json()
    assert p["count"][-1]["count"] == 2 and 0 <= p["turnover"] <= 1 and p["coverage"] > 0 and "over-represented" in p["note"]
    screen = {"kind": "screen", "rule": "close > sma(close, 50)", "symbols": ["AAA", "BBB", "CCC", "DEAD"]}
    body = library.UniverseBody(**screen)
    m = library.membership(body)[2]
    assert not m[:50].any()  # nothing before the first rebalance with a full window
    # no look-ahead: membership on bar t+1 is fixed by data up to the rebalance bar, so a change after it cannot alter earlier rows
    full = data.panel(list(screen["symbols"]))
    cut = 300
    m2 = library.membership(body, end=str(full.dates[cut].date()))[2]
    assert (m2[: cut - 25] == m[: cut - 25]).all()
    assert lib.post(f"{L}/universe/preview", json={"body": {**screen, "rule": "close > delay(close, -1)"}}).status_code == 422
    v2 = lib.post(f"{L}/{static['id']}/versions", json={"body": {"kind": "static", "symbols": ["AAA"]}}).json()
    assert v2["version"] == 2 and lib.get(f"{L}/{static['id']}", params={"version": 1}).json()["body"]["symbols"] == ["AAA", "BBB", "ZZZZ"]


def test_benchmark_blend_refuses_unknown(lib):  # Y-12
    r = lib.post(f"{L}/benchmark/series", json={"weights": {"AAA": 0.6, "BBB": 0.4}}).json()
    assert r["series"][0]["value"] == pytest.approx(100) and r["weights"]["AAA"] == pytest.approx(0.6)
    assert lib.post(f"{L}/benchmark/series", json={"weights": {"NOPE": 1}}).status_code == 422
    assert lib.post(f"{L}/benchmark/series", json={"weights": {"AAA": -1}}).status_code == 422


def test_regime_and_crisis_windows(lib):  # Y-16
    r = lib.post(f"{L}/regime/evaluate", json={"body": {"benchmark": "SPY", "rule": "close > sma(close, 100)"}}).json()
    assert r["spans"] and 0 < r["share_on"] < 1 and sum(s["bars"] for s in r["spans"]) == len(data.panel(["SPY"]).dates)
    ok = lib.post(L, json={"type": "crisis", "name": "Taper", "body": {"start": "2018-02-01", "end": "2018-02-08"}})
    assert ok.status_code == 200
    bad = lib.post(L, json={"type": "crisis", "name": "Dot-com", "body": {"start": "2000-03-24", "end": "2002-10-09"}})
    assert bad.status_code == 422 and "2015" in bad.text and "DECISIONS" in bad.text


def test_custom_metric_whitelist(lib):  # Y-1
    m = lib.post(L, json={"type": "metric", "name": "CAGR per ulcer", "body": {"formula": "cagr / ulcer"}}).json()
    assert lib.post(f"{L}/metric/evaluate", json={"item_id": m["id"], "metrics": {"cagr": 0.2, "ulcer": 0.05}}).json()["value"] == pytest.approx(4.0)
    assert lib.post(f"{L}/metric/evaluate", json={"formula": "cagr / ulcer", "metrics": {"cagr": 0.2}}).json()["value"] is None
    assert lib.post(f"{L}/metric/evaluate", json={"formula": "sharpe > 1 and trades > 5", "metrics": {}}).status_code == 422
    for bad in ("__import__('os').system('x')", "cagr.__class__", "open('f')", "[1][0]", "sharpe if (lambda: 1)() else 0", "cagr ** 9"):
        assert lib.post(L, json={"type": "metric", "name": "x", "body": {"formula": bad}}).status_code == 422, bad
    run = lib.post(f"{L}/metric/evaluate", json={"formula": "trades", "payload": {"spec": SMA, **SETTINGS}})
    assert run.status_code == 200 and run.json()["value"] > 0


def test_profile_export_import_and_catalog(lib, monkeypatch):  # Y-35, Y-18, Y-36
    prof = lib.post(L, json={"type": "profile", "name": "Strict", "body": {"validation": {"min_trades": 50}, "report_order": ["returns", "risk"], "sizing": {"mode": "pct_equity", "value": 0.1}}}).json()
    doc = lib.get(f"{L}/{prof['id']}/export").json()
    back = lib.post(f"{L}/profile/import", json=doc).json()
    assert back["id"] != prof["id"] and back["body"] == prof["body"] and back["name"] == "Strict"
    assert lib.post(f"{L}/profile/import", json={"kind": "other"}).status_code == 422
    monkeypatch.setattr(library, "_per_symbol", lambda v: [{"symbol": s, "first": "2015-01-02", "last": "2020-01-01", "bars": 5, "gaps": 0} for s in ("AAA", "AAB", "BBB")])
    page = lib.get(f"{L}/data/catalog", params={"q": "aa", "limit": 1}).json()
    assert page["total"] == 2 and len(page["rows"]) == 1 and page["rows"][0]["symbol"] == "AAA"
    assert lib.get(f"{L}/data/catalog", params={"limit": 0}).status_code == 422
