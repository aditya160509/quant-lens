from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.api import studio_v3 as api
from app.services.studio_v3.core import store


def test_share_freezes_snapshot_and_revokes(monkeypatch, tmp_path):
    monkeypatch.setattr(store, "DB_PATH", tmp_path / "studio.sqlite")
    app = FastAPI()
    app.include_router(api.router, prefix="/api")
    c = TestClient(app)
    s = store.create(api.Strategy(name="Alpha", code="print(1)"))
    token = c.post("/api/studio-v3/pinned-share", json={"strategy_id": s["id"]}).json()["token"]
    store.save_version(s["id"], api.Strategy(name="Alpha", code="print(2)"))
    snap = c.get(f"/api/studio-v3/pinned-share/{token}").json()
    assert snap["name"] == "Alpha" and snap["version"] == 1 and "print(1)" in "".join(snap["files"].values())
    assert c.post("/api/studio-v3/pinned-share", json={"strategy_id": "nope"}).status_code == 404
    assert c.delete(f"/api/studio-v3/pinned-share/{token}").status_code == 200
    assert c.get(f"/api/studio-v3/pinned-share/{token}").status_code == 404
