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
