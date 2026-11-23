"""Build workspace: version labels and lock, branch merge, local history, snippets, share links, editing lease, find and replace, zip projects."""

import io
import zipfile

from app.services.studio_v3.core import workspace
from tests.test_studio_v3_backtest import studio  # noqa: F401  (fixture)

API = "/api/studio-v3"


def _make(studio, code="a = 1\nb = 2\n", **extra):  # noqa: F811
    return studio.post(f"{API}/strategies", json={"spec": {"name": "W", "code": code, **extra}}).json()["id"]


def test_labels_and_lock_stop_saving_over_the_live_version(studio):  # noqa: F811
    sid = _make(studio)
    studio.put(f"{API}/strategies/{sid}", json={"spec": {"name": "W", "code": "a = 2\n"}})
    studio.put(f"{API}/strategies/{sid}/versions/2/label", json={"name": "validated", "tags": ["live", "live", "q4"]})
    assert studio.put(f"{API}/strategies/{sid}/lock", json={"version": 2}).json() == {"locked_version": 2}
    rows = studio.get(f"{API}/strategies/{sid}/timeline").json()
    assert [(r["version"], r["name"], r["tags"], r["locked"]) for r in rows] == [(1, "", [], False), (2, "validated", ["live", "q4"], True)]
    assert studio.put(f"{API}/strategies/{sid}", json={"spec": {"name": "W", "code": "a = 3\n"}}).status_code == 423
    assert studio.put(f"{API}/strategies/{sid}", json={"spec": {"name": "W", "code": "a = 2\n"}}).status_code == 200  # unchanged is not a write
    studio.put(f"{API}/strategies/{sid}/lock", json={"version": None})
    assert studio.put(f"{API}/strategies/{sid}", json={"spec": {"name": "W", "code": "a = 3\n"}}).json()["version"] == 3


def test_branch_compare_and_three_way_merge(studio):  # noqa: F811
    sid = _make(studio, "a = 1\nb = 2\n", files={"helpers.py": "x = 1\n"})
    branch = studio.post(f"{API}/strategies/{sid}/versions/1/branch").json()["id"]
    studio.put(f"{API}/strategies/{branch}", json={"spec": {"name": "W", "code": "a = 1\nb = 2\n", "files": {"helpers.py": "x = 9\n"}}})
    diff = studio.get(f"{API}/strategies/{sid}/compare/{branch}").json()["diffs"]
    assert list(diff) == ["helpers.py"] and "+x = 9" in diff["helpers.py"]
    studio.put(f"{API}/strategies/{sid}", json={"spec": {"name": "W", "code": "a = 5\nb = 2\n", "files": {"helpers.py": "x = 1\n"}}})
    merged = studio.post(f"{API}/strategies/{sid}/merge", json={"source": branch}).json()
    assert merged["version"] == 3
    files = studio.get(f"{API}/strategies/{sid}/files").json()["files"]
    assert files == {"main.py": "a = 5\nb = 2\n", "helpers.py": "x = 9\n"}
    other = studio.post(f"{API}/strategies/{sid}/versions/1/branch").json()["id"]
    studio.put(f"{API}/strategies/{other}", json={"spec": {"name": "W", "code": "a = 7\nb = 2\n", "files": {"helpers.py": "x = 9\n"}}})
    clash = studio.post(f"{API}/strategies/{sid}/merge", json={"source": other})
    assert clash.status_code == 409 and clash.json()["detail"]["conflicts"] == ["main.py"]
    assert studio.post(f"{API}/strategies/{sid}/merge", json={"source": other, "resolution": "theirs"}).status_code == 200
    assert studio.post(f"{API}/strategies/{other}/merge", json={"source": sid}).status_code == 422  # not a branch of it


def test_local_history_keeps_seven_days_and_skips_duplicates(studio):  # noqa: F811
    sid = _make(studio)
    spec = {"name": "W", "code": "a = 1\n"}
    assert workspace.snapshot(sid, spec, now=1000.0)
    assert not workspace.snapshot(sid, spec, now=2000.0)  # same files
    assert not workspace.snapshot(sid, {**spec, "code": "a = 2\n"}, now=1010.0)  # under 30 s
    assert workspace.snapshot(sid, {**spec, "code": "a = 2\n"}, now=3000.0)
    assert [r["files"]["main.py"] for r in workspace.history(sid, now=4000.0)] == ["a = 2\n", "a = 1\n"]
    assert workspace.history(sid, now=1000.0 + 8 * 86400) == []
    studio.put(f"{API}/strategies/{sid}/draft", json={"spec": {"name": "W", "code": "a = 9\n"}})
    assert studio.get(f"{API}/strategies/{sid}/history").json()[0]["files"]["main.py"] == "a = 9\n"


def test_snippets_crud_validates_prefix(studio):  # noqa: F811
    made = studio.post(f"{API}/snippets", json={"name": "Entry", "prefix": "entry", "body": "ctx.buy()"}).json()
    assert studio.get(f"{API}/snippets").json() == [made]
    assert studio.put(f"{API}/snippets/{made['id']}", json={"name": "Entry", "prefix": "entry", "body": "ctx.sell()", "tags": ["Exit", "exit ", "risk"]}).json()["tags"] == ["exit", "risk"]
    assert studio.post(f"{API}/snippets", json={"name": "Bad", "prefix": "has space", "body": "x"}).status_code == 422
    assert studio.delete(f"{API}/snippets/{made['id']}").json() == {"deleted": True}
    assert studio.delete(f"{API}/snippets/{made['id']}").status_code == 404


def test_line_comment_threads_and_replies(studio):  # noqa: F811
    sid = _make(studio)
    first = studio.post(f"{API}/strategies/{sid}/comments", json={"file": "main.py", "line": 2, "text": "why 2?"}).json()
    reply = studio.post(f"{API}/strategies/{sid}/comments", json={"line": 9, "text": "tuned", "thread_id": first["thread_id"]}).json()
    assert (reply["file"], reply["line"], reply["thread_id"], reply["version"]) == ("main.py", 2, first["thread_id"], first["version"])
    assert [c["text"] for c in studio.get(f"{API}/strategies/{sid}/comments").json()] == ["why 2?", "tuned"]
    assert studio.post(f"{API}/strategies/{sid}/comments", json={"text": "x", "thread_id": "nope"}).status_code == 404
    bar = studio.post(f"{API}/strategies/{sid}/comments", json={"text": "gap down", "date": "2020-03-16", "symbol": "spy"}).json()
    reply = studio.post(f"{API}/strategies/{sid}/comments", json={"text": "y", "thread_id": bar["thread_id"], "symbol": "QQQ"}).json()
    assert (bar["date"], bar["symbol"], reply["date"], reply["symbol"]) == ("2020-03-16", "SPY", "2020-03-16", "SPY")
    assert studio.put(f"{API}/strategies/{sid}/comments/threads/{bar['thread_id']}/resolved").json() == {"resolved": True}
    assert all(c.get("resolved") for c in studio.get(f"{API}/strategies/{sid}/comments").json() if c["thread_id"] == bar["thread_id"])
    assert studio.delete(f"{API}/strategies/{sid}/comments/{first['id']}").json() == {"deleted": True}
    assert studio.get(f"{API}/strategies/missing/comments").status_code == 404


def test_share_link_is_read_only_and_forks(studio):  # noqa: F811
    sid = _make(studio)
    token = studio.post(f"{API}/strategies/{sid}/share").json()["token"]
    shared = studio.get(f"{API}/share/{token}").json()
    assert shared["read_only"] and shared["files"] == {"main.py": "a = 1\nb = 2\n"}
    assert shared["run"] is None
    pinned = studio.post(f"{API}/strategies/{sid}/share", params={"job_id": "gone"}).json()["token"]
    assert studio.get(f"{API}/share/{pinned}").json()["run"] is None  # a missing run never breaks the link
    fork = studio.post(f"{API}/share/{token}/fork").json()
    assert fork["id"] != sid and fork["spec"]["code"] == "a = 1\nb = 2\n"
    studio.delete(f"{API}/share/{token}")
    assert studio.get(f"{API}/share/{token}").status_code == 404


def test_second_writer_gets_409_until_it_takes_over(studio):  # noqa: F811
    sid = _make(studio)
    url = f"{API}/strategies/{sid}"
    assert studio.post(f"{url}/lease", json={"session": "tab-a"}).status_code == 200
    blocked = studio.post(f"{url}/lease", json={"session": "tab-b"})
    assert blocked.status_code == 409 and blocked.json()["detail"]["held_by"] == "tab-a"
    body = {"spec": {"name": "W", "code": "a = 4\n"}}
    assert studio.put(url, json=body, headers={"X-Studio-Session": "tab-b"}).status_code == 409
    assert studio.put(url, json=body).status_code == 409
    assert studio.put(url, json=body, headers={"X-Studio-Session": "tab-a"}).status_code == 200
    assert studio.post(f"{url}/lease", json={"session": "tab-b", "take_over": True}).json()["taken_over"]
    assert studio.put(url, json={"spec": {"name": "W", "code": "a = 5\n"}}, headers={"X-Studio-Session": "tab-a"}).status_code == 409
    studio.delete(f"{url}/lease", params={"session": "tab-b"})
    assert studio.put(url, json={"spec": {"name": "W", "code": "a = 5\n"}}).status_code == 200


def test_lease_expires(studio):  # noqa: F811
    sid = _make(studio)
    workspace.acquire_lease(sid, "a", now=100.0)
    workspace.check_writer(sid, "a", now=110.0)
    workspace.check_writer(sid, "b", now=100.0 + workspace.LEASE_SECONDS + 1)  # expired: anyone may write


def test_find_replace_previews_then_saves_one_version(studio):  # noqa: F811
    sid = _make(studio, "fast = 1\nslow = fast + 1\n", files={"helpers.py": "def f(fast):\n    return fast\n"})
    url = f"{API}/strategies/{sid}/find-replace"
    preview = studio.post(url, json={"query": "fast", "whole_word": True}).json()
    assert preview["count"] == 4 and preview["files"] == ["helpers.py", "main.py"] and "version" not in preview
    assert {(m["file"], m["line"], m["column"]) for m in preview["matches"]} >= {("main.py", 2, 8), ("helpers.py", 1, 7)}
    done = studio.post(url, json={"query": "fast", "replacement": "quick", "whole_word": True, "base_version": 1}).json()
    assert done["version"] == 2
    assert studio.get(f"{API}/strategies/{sid}/files").json()["files"]["main.py"] == "quick = 1\nslow = quick + 1\n"
    assert studio.post(url, json={"query": "x", "replacement": "y", "base_version": 1}).status_code == 409
    assert studio.post(url, json={"query": "(", "regex": True}).status_code == 422


def test_zip_round_trip_and_limits(studio):  # noqa: F811
    sid = _make(studio, "a = 1\n", files={"helpers.py": "x = 1\n", "README.md": "notes\n"})
    raw = studio.get(f"{API}/strategies/{sid}/export.zip").content
    assert set(zipfile.ZipFile(io.BytesIO(raw)).namelist()) == {"main.py", "helpers.py", "README.md", "studio.json"}
    made = studio.post(f"{API}/strategies/import-zip", content=raw, params={"name": "Back"}, headers={"Content-Type": "application/zip"}).json()
    assert made["name"] == "Back" and made["spec"]["files"] == {"helpers.py": "x = 1\n", "README.md": "notes\n"}
    bad = io.BytesIO()
    with zipfile.ZipFile(bad, "w") as z:
        z.writestr("sub/main.py", "x = 1\n")
    assert studio.post(f"{API}/strategies/import-zip", content=bad.getvalue()).status_code == 422
    assert studio.post(f"{API}/strategies/import-zip", content=b"nope").status_code == 422


def test_build_prefs_round_trip_and_only_known_names(studio):  # noqa: F811
    assert studio.get(f"{API}/build/prefs/layouts").json() == {"value": None}
    saved = {"active": "debug", "list": [{"id": "u1", "name": "Mine", "layout": {}}]}
    assert studio.put(f"{API}/build/prefs/layouts", json=saved).json()["value"] == saved
    assert studio.get(f"{API}/build/prefs/layouts").json()["value"] == saved
    assert studio.get(f"{API}/build/prefs/anything").status_code == 422
