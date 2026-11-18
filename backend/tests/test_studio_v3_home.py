"""Home: status, attention, duplicate, import preview, search, trash, bulk export (H-2..H-25)."""

import datetime as dt
import io
import json
import time
import zipfile

import pytest

from app.api import studio_v3 as api
from app.services.studio_v3.core import home, store
from app.services.studio_v3.core.spec import Strategy
from tests.test_studio_v3_backtest import studio  # noqa: F401  (fixture)

FRESH = {"tone": "ok", "date": "2000-01-01", "age_days": 0, "label": ""}


@pytest.fixture
def client(studio):  # noqa: F811
    return studio


def _make(name="A", **kw):
    return store.create(Strategy(name=name, entry_long="rsi(close, 14) < 30", **kw))


def test_status_validated_only_for_current_version(client):  # H-7
    s = _make()
    assert store.get(s["id"])["status"] == "Draft"
    store.record_run("j1", s["id"], 1, "st01", "h", "r", {})
    assert store.get(s["id"])["status"] == "Backtested"
    store.record_run("j2", s["id"], 1, "st04", "h", "r", {})
    assert store.get(s["id"])["status"] == "Validated"
    store.save_version(s["id"], Strategy(name="A", entry_long="rsi(close, 14) < 20"))
    c = store.get(s["id"])
    assert c["status"] == "Backtested" and c["validation_expired"]


def test_paper_step_older_than_three_trading_days_needs_attention(client):  # H-2, H-18
    s = _make()
    store.kv_set(f"paper:{s['id']}", [{"version": 1, "from": "2025-01-01", "at": time.time() - 10 * 86400}])
    items = home.attention(store.list_strategies(), {}, FRESH, today=dt.date.today())
    assert [a["kind"] for a in items] == ["paper_stale"] and items[0]["rank"] == home.RANK["paper_stale"]
    store.record_run("j", s["id"], 1, "st05", "h", "r", {"drift": True})
    kinds = [a["kind"] for a in home.attention(store.list_strategies(), {}, FRESH)]
    assert kinds[0] == "drift"  # ranked above everything else


def test_failed_run_and_data_newer_rank_order(client):
    s = _make()
    store.record_run("j", s["id"], 1, "st01", "h", "r", {})
    items = home.attention(store.list_strategies(), {s["id"]: time.time() + 5}, {**FRESH, "date": "2999-01-01"})
    assert [a["kind"] for a in items] == ["data_newer", "failed_run"]


def test_duplicate_is_version_one_with_empty_ledger(client):  # H-3
    s = _make()
    store.record_trial(s["id"], "h1", "human", "backtest", 1.0, __import__("numpy").array([0.01, -0.01, 0.02]))
    store.save_version(s["id"], Strategy(name="A", entry_long="rsi(close, 14) < 20"))
    d = client.post(f"/api/studio-v3/strategies/{s['id']}/duplicate").json()
    assert d["version"] == 1 and d["trials"]["raw"] == 0 and d["id"] != s["id"]


def test_import_previews_findings_without_saving(client):  # H-4
    bad = {"name": "Bad", "entry_long": "nonsense_fn(3) > 1"}
    r = client.post("/api/studio-v3/strategies/import", json={"spec": bad}).json()
    assert r["compile"]["ok"] is False and r["saved"] is None and store.list_strategies() == []
    ok = client.post("/api/studio-v3/strategies/import?save=true", json={"spec": {"name": "Ok", "entry_long": "rsi(close, 14) < 30"}}).json()
    assert ok["saved"]["version"] == 1


def test_search_finds_indicator_text_name_and_tag(client):  # H-8
    a = _make("Mean reversion", hypothesis="oversold bounces")
    _make("Other").update(store.update_meta(_make("Tagged")["id"], tags=["swing"]))
    store.save_version(_make("Plain")["id"], Strategy(name="Plain", entry_long="close > sma(close, 50)"))
    hits = lambda q: sorted(h["name"] for h in client.get("/api/studio-v3/search", params={"q": q}).json()["strategies"])
    assert hits("rsi(") == ["Mean reversion", "Other", "Tagged"]
    assert hits("SWING") == ["Tagged"] and hits("oversold") == ["Mean reversion"] and hits("sma(") == ["Plain"] and hits("") == []
    assert a["id"]


def test_trash_restore_and_hard_delete_need_name(client):  # H-10
    s = _make("Keep me")
    sid = s["id"]
    assert client.post(f"/api/studio-v3/strategies/{sid}/trash", headers={"x-studio-actor": "agent"}).status_code == 403
    assert client.post(f"/api/studio-v3/strategies/{sid}/trash").json()["trashed"]
    assert store.list_strategies() == [] and [t["id"] for t in client.get("/api/studio-v3/trash").json()["strategies"]] == [sid]
    assert client.delete(f"/api/studio-v3/strategies/{sid}?confirm=wrong").status_code == 422
    assert client.delete(f"/api/studio-v3/strategies/{sid}?confirm=Keep me", headers={"x-studio-actor": "agent"}).status_code == 403
    assert client.post(f"/api/studio-v3/strategies/{sid}/trash?restore=true").json()["trashed"] is False
    assert client.delete(f"/api/studio-v3/strategies/{sid}?confirm=Keep me").json() == {"deleted": sid}
    assert client.get(f"/api/studio-v3/strategies/{sid}").status_code == 404


def test_trash_purges_after_thirty_days(client):
    s = _make()
    store.trash(s["id"])
    assert store.list_trash(time.time() + 31 * 86400) == []
    with pytest.raises(KeyError):
        store.get(s["id"])


def test_recent_run_marks_settings_changed(client):  # H-22
    s = _make()
    store.record_run("j", s["id"], 1, "st01", "h", "r", {})
    assert store.recent_runs()[0]["settings_changed"] is False
    store.save_version(s["id"], Strategy(name="A", entry_long="rsi(close, 14) < 20"))
    assert store.recent_runs()[0]["settings_changed"] is True


def test_export_zip_and_rerun_refusals(client):  # H-25
    s = _make()
    z = zipfile.ZipFile(io.BytesIO(client.post("/api/studio-v3/strategies/export", json={"ids": [s["id"]]}).content))
    assert json.loads(z.read(z.namelist()[0]))["spec"]["entry_long"] == "rsi(close, 14) < 30"
    r = client.post("/api/studio-v3/strategies/rerun", json={"ids": ["nope"]}).json()
    assert r["jobs"] == [] and r["refused"][0]["id"] == "nope"


def test_live_block_and_spark(client):  # H-14, H-21
    s = _make()
    store.kv_set(f"paper:{s['id']}", [{"version": 1, "from": "2025-01-01", "at": time.time()}])
    store.record_run("j", s["id"], 1, "st05", "h", "r", {"total_return": 0.02, "paper_day": 0.004})
    store.record_run("k", s["id"], 1, "st01", "h", "r", {"spark": [1.0, 1.1]})
    cards = store.list_strategies()
    blk = home.live_block(cards)
    assert cards[0]["spark"] == [1.0, 1.1] and blk["strategies"][0]["today_pnl"] == 0.004 and blk["heartbeat"]
    assert api.home()["live"]["alerts"] == 0
