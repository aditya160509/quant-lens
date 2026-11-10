import pytest


@pytest.fixture(autouse=True)
def _no_feature_store(monkeypatch):
    """Synthetic test data must neither read nor reach the real snapshot store; snapshot tests opt in."""
    from app.services.screener_v2.core import snapshots
    monkeypatch.setattr(snapshots, "STORE", None)
