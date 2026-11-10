import numpy as np
import pandas as pd

from app.services.screener_v2.core.explain import (
    explain_difference,
    near_misses,
    screen_diff,
    why_here,
)

P = pd.DataFrame({"sector": ["T", "T", "T"], "roe": [0.3, 0.1, np.nan], "trailing_pe": [10, 12, 8]}, index=["A", "B", "C"])
F = {"roe_min": 0.2, "pe_max": 15}


def test_explain():
    w = {r["filter"]: r for r in why_here(P, F, "A")}
    assert w["pe_max"]["margin"] == 5 and w["roe_min"]["sector_percentile"] == 100
    nm = {r["symbol"]: r for r in near_misses(P, F)}
    assert abs(nm["B"]["relax_by"] - 0.1) < 1e-9 and nm["C"]["unknown"] and nm["C"]["value"] is None
    assert explain_difference(P, F, "A", "B")[0]["filter"] == "roe_min"
    assert screen_diff(["A", "B"], ["B", "C"]) == {"entered": ["C"], "left": ["A"], "moved": [{"symbol": "B", "from": 1, "to": 0}]}


def test_preview_counts_and_kept_histogram(monkeypatch):
    from app.services.screener_v2.core import explain
    panel = pd.DataFrame({"ticker": list("ABCD"), "sector": ["T"] * 4, "trailing_pe": [5.0, 10.0, 20.0, np.nan], "price_usd": [10.0] * 4})
    monkeypatch.setattr(explain, "_preview_panel", lambda payload: panel)
    out = explain.preview({"pe_max": 12}, ["trailing_pe", "missing"], bins=4)
    assert (out["universe"], out["passed"]) == (4, 2)
    d = out["dist"]["trailing_pe"]
    assert d["known"] == 3 and sum(d["bins"]) == 3 and sum(d["kept"]) == 2 and "missing" not in out["dist"]
