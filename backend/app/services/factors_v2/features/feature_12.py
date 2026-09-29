"""Feature 12: Factor DNA Attribution."""

from typing import Any, Dict, Tuple

import numpy as np
import pandas as pd
from sklearn.tree import DecisionTreeClassifier

from app.services.factors_v2.core.analytics import factor_returns, response, run_feature_module
from app.services.factors_v2.core.performance import elastic_net_coordinate_descent, runtime_meta

_DNA_CLASSIFIER = None
_DNA_CLASSIFIER_AUDIT = None
_CLASS_LABELS = ["Risk Factor", "Behavioral Factor", "Structural Factor", "Data-Mining Artifact"]


def run(payload: Dict[str, Any]) -> Dict[str, Any]:
    f5 = run_feature_module(5, payload)
    f6 = run_feature_module(6, payload)
    f8 = run_feature_module(8, payload)
    f4 = run_feature_module(4, payload)
    ic = (f5.get("tables", {}).get("ic_by_horizon") or [{}])[0].get("mean_ic") or 0
    icir = (f5.get("tables", {}).get("ic_by_horizon") or [{}])[0].get("icir") or 0
    half = (f5.get("summary_cards") or [{}, {}])[1].get("value") or 252
    crowd = (f6.get("summary_cards") or [{}])[0].get("value") or 50
    corr_rows = f8.get("charts", {}).get("correlation_heatmap", [])
    nearest = max([abs(r.get("value") or 0) for r in corr_rows if r.get("row") != r.get("column")] or [0])
    purity = _purity_score(payload)
    anatomy = _return_anatomy(payload)
    sector_dna = _sector_dna_snapshot(payload)
    regime_dna = _regime_dna_bar(f4)
    correlation_dna = _latest_correlation_dna(payload)
    dna = [
        {"axis": "IC", "score": min(100, max(0, 50 + ic * 1000))},
        {"axis": "ICIR", "score": min(100, max(0, 50 + icir * 20))},
        {"axis": "Half-Life", "score": max(0, 100 - half / 5)},
        {"axis": "Uncrowded", "score": 100 - crowd},
        {"axis": "Sector Breadth", "score": _sector_breadth(f6)},
        {"axis": "Regime Robustness", "score": max(0, min(100, 100 - nearest * 50))},
        {"axis": "Uniqueness", "score": 100 * (1 - nearest)},
        {"axis": "Purity", "score": purity["score"]},
    ]
    avg = sum(d["score"] for d in dna) / len(dna)
    classifier, classifier_audit = _cart_classifier(dna)
    return response(
        "feature_12",
        "ok",
        summary_cards=[{"label": "DNA Composite", "value": avg}, {"label": "Primary Classification", "value": max(classifier, key=classifier.get)}],
        charts={"dna_radar": dna, "classifier_probability": [{"class": k, "probability": v} for k, v in classifier.items()], "sector_dna": sector_dna, "regime_dna": regime_dna, "correlation_dna": correlation_dna},
        tables={"dna_vector": dna, "return_anatomy": anatomy, "purity_regression": [purity], "classifier_training_audit": classifier_audit, "sector_dna_snapshot": sector_dna, "regime_dna": regime_dna, "correlation_dna_latest": correlation_dna},
        alerts=[{"level": "medium", "message": "DNA score is weak"}] if avg < 40 else [],
        meta={**runtime_meta("feature_12", payload, ["CART classifier trained on deterministic 100+ sample academic archetype library"]), "classifier": "CART decision tree max_depth=4 trained on seeded academic factor archetypes", "features": [d["axis"] for d in dna], "removed_io": ["sector DNA animation requires historical sector composition snapshots", "rolling correlation DNA grid replaced by latest factor-correlation bar"], "audit_closures": ["static sector DNA snapshot", "regime DNA bar from F04", "latest correlation DNA bar"]},
    )


def _purity_score(payload):
    rets = factor_returns(payload).dropna().tail(int(payload.get("window_days", 1260)))
    factor = payload.get("factor", "value_pb")
    col_map = {"value_pb": "HML", "momentum_12_1": "Mom", "quality_roe": "RMW", "low_vol": "BAB", "size": "SMB"}
    y_col = col_map.get(factor, "HML")
    if y_col not in rets or len(rets) < 80:
        return {"alpha": None, "r_squared": None, "score": 50}
    x_cols = [c for c in ["Mkt-RF", "SMB", "HML", "RMW", "CMA"] if c in rets.columns and c != y_col]
    df = rets[[y_col] + x_cols].dropna()
    if len(df) < 80 or not x_cols:
        return {"alpha": None, "r_squared": None, "score": 50}
    X = np.column_stack([np.ones(len(df)), df[x_cols].values])
    y = df[y_col].values
    y_mean = float(np.nanmean(y))
    y_std = float(np.nanstd(y) or 1.0)
    X_scale = X[:, 1:]
    mu = X_scale.mean(axis=0)
    sigma = X_scale.std(axis=0)
    sigma[sigma == 0] = 1.0
    X_std = (X_scale - mu) / sigma
    y_std_vec = (y - y_mean) / y_std
    beta = elastic_net_coordinate_descent(X_std.astype(float), y_std_vec.astype(float), alpha=0.002, l1_ratio=0.15, max_iter=160)
    yhat = y_mean + y_std * (X_std @ beta)
    r2 = 1 - np.sum((y - yhat) ** 2) / max(np.sum((y - y.mean()) ** 2), 1e-12)
    alpha = float((y - yhat).mean() * 252)
    score = max(0, min(100, abs(alpha) * 1000 + (1 - r2) * 60))
    return {"alpha": float(alpha), "r_squared": float(r2), "score": float(score), "regularization": "elastic_net_coordinate_descent"}


def _return_anatomy(payload):
    rets = factor_returns(payload).dropna().tail(int(payload.get("window_days", 1260)))
    if rets.empty:
        return []
    cols = [c for c in ["HML", "Mom", "RMW", "BAB", "SMB", "Mkt-RF"] if c in rets.columns]
    if not cols:
        return []
    y = rets[cols[0]].dropna()
    parts = {
        "valuation_reversion": abs(float(rets.get("HML", y).corr(y))) if "HML" in rets else 0,
        "characteristic_momentum": abs(float(rets.get("Mom", y).corr(y))) if "Mom" in rets else 0,
        "quality_profitability": abs(float(rets.get("RMW", y).corr(y))) if "RMW" in rets else 0,
        "low_beta_structure": abs(float(rets.get("BAB", y).corr(y))) if "BAB" in rets else 0,
    }
    total = sum(v for v in parts.values() if np.isfinite(v)) or 1
    return [{"component": k, "share": v / total} for k, v in parts.items()]


def _sector_breadth(f6):
    rows = f6.get("tables", {}).get("crowding_metrics", [])
    hhi = next((r.get("raw") for r in rows if r.get("metric") == "concentration_hhi"), None)
    return max(0, min(100, 100 - float(hhi or 0.1) * 500))


def _sector_dna_snapshot(payload):
    from app.services.factors_v2.core.analytics import characteristic_panel
    chars = characteristic_panel(payload)
    factor = payload.get("factor", "value_pb")
    if chars.empty or factor not in chars or "sector" not in chars:
        return []
    q = chars[factor].rank(pct=True)
    rows = []
    for side, mask in [("long", q >= 0.8), ("short", q <= 0.2)]:
        book = chars.loc[mask].copy()
        if book.empty:
            continue
        weights = book["market_cap"].fillna(1).clip(lower=1)
        sector_weights = weights.groupby(book["sector"].astype(str)).sum()
        sector_weights = sector_weights / max(float(sector_weights.sum()), 1e-12)
        rows.extend({"sector": sector, "side": side, "weight": float(weight)} for sector, weight in sector_weights.items())
    return sorted(rows, key=lambda row: (row["sector"], row["side"]))


def _regime_dna_bar(f4):
    rows = f4.get("tables", {}).get("conditional_returns", [])
    out = []
    for row in rows:
        out.append({"regime": row.get("regime"), "factor": row.get("factor"), "avg_daily_return": row.get("avg_daily_return"), "sample": row.get("sample")})
    return out


def _latest_correlation_dna(payload):
    rets = factor_returns(payload).dropna().tail(int(payload.get("window_days", 1260)))
    if rets.empty:
        return []
    factor = payload.get("factor", "value_pb")
    col_map = {"value_pb": "HML", "momentum_12_1": "Mom", "quality_roe": "RMW", "low_vol": "BAB", "size": "SMB"}
    target = col_map.get(factor, factor)
    if target not in rets.columns:
        target = rets.columns[0]
    corr = rets.corr()[target].drop(labels=[target], errors="ignore").dropna().sort_values(key=lambda s: s.abs(), ascending=False)
    return [{"factor": idx, "correlation_to_primary": float(value), "primary_factor": target} for idx, value in corr.items()]


def _cart_classifier(dna):
    clf, audit = _get_classifier()
    x = np.array([[d["score"] for d in dna]], dtype=float)
    probs = clf.predict_proba(x)[0]
    out = {label: 0.0 for label in _CLASS_LABELS}
    for cls, prob in zip(clf.classes_, probs):
        out[_CLASS_LABELS[int(cls)]] = float(prob)
    return out, audit


def _get_classifier():
    global _DNA_CLASSIFIER, _DNA_CLASSIFIER_AUDIT
    if _DNA_CLASSIFIER is None:
        train_x, train_y = _academic_archetype_library()
        _DNA_CLASSIFIER = DecisionTreeClassifier(max_depth=4, random_state=1729).fit(train_x, train_y)
        _DNA_CLASSIFIER_AUDIT = [
            {"measure": "training_samples", "value": int(len(train_x))},
            {"measure": "base_archetypes", "value": len(_ACADEMIC_ARCHETYPES)},
            {"measure": "augmentation", "value": "4x deterministic jitter replicates at +/-4 DNA points per dimension"},
            {"measure": "max_depth", "value": 4},
            {"measure": "classes", "value": ", ".join(_CLASS_LABELS)},
            {"measure": "calibration", "value": "leaf probability from academic archetype proportions"},
            {"measure": "sources", "value": "Fama-French, Carhart, Frazzini-Pedersen, AQR QMJ/BAB, Sloan, Novy-Marx, Harvey-Liu-Zhu"},
            {"measure": "compile_policy", "value": "module-level cached CART tree; no per-run refit"},
        ]
    return _DNA_CLASSIFIER, _DNA_CLASSIFIER_AUDIT


_ACADEMIC_ARCHETYPES = [
    {"name": "Market_MktRF", "dna": [72, 68, 90, 60, 75, 62, 30, 15], "label": 0},
    {"name": "Size_SMB", "dna": [52, 48, 82, 65, 70, 58, 55, 42], "label": 0},
    {"name": "Value_HML", "dna": [68, 58, 80, 55, 72, 52, 48, 55], "label": 0},
    {"name": "Investment_CMA", "dna": [55, 52, 85, 70, 68, 60, 52, 50], "label": 0},
    {"name": "Profitability_RMW", "dna": [62, 60, 78, 65, 74, 65, 50, 58], "label": 0},
    {"name": "BAB", "dna": [65, 62, 75, 48, 65, 55, 58, 62], "label": 0},
    {"name": "Momentum_UMD", "dna": [78, 72, 28, 38, 58, 42, 52, 68], "label": 1},
    {"name": "STR_ShortTermRev", "dna": [70, 52, 10, 55, 48, 38, 58, 60], "label": 1},
    {"name": "LTR_LongTermRev", "dna": [42, 35, 88, 72, 55, 48, 62, 45], "label": 1},
    {"name": "QMJ", "dna": [70, 68, 65, 45, 70, 62, 48, 65], "label": 1},
    {"name": "GrossProfitability", "dna": [65, 60, 72, 62, 72, 60, 52, 60], "label": 1},
    {"name": "PEAD", "dna": [68, 58, 35, 60, 55, 50, 60, 62], "label": 1},
    {"name": "ValueComposite_VAL", "dna": [64, 58, 78, 52, 80, 55, 45, 55], "label": 1},
    {"name": "LowVol_IVOL", "dna": [58, 55, 70, 42, 65, 58, 55, 55], "label": 2},
    {"name": "LiquidityPremium", "dna": [50, 48, 85, 58, 60, 62, 62, 50], "label": 2},
    {"name": "JanuaryEffect", "dna": [45, 38, 92, 75, 50, 35, 65, 38], "label": 2},
    {"name": "DividendYield", "dna": [48, 45, 82, 68, 65, 65, 55, 42], "label": 2},
    {"name": "Accruals_Sloan", "dna": [55, 50, 75, 72, 62, 60, 60, 52], "label": 2},
    {"name": "ImpliedSkewness", "dna": [48, 42, 65, 65, 52, 48, 68, 48], "label": 2},
    {"name": "Artifact_5varComposite", "dna": [28, 22, 35, 50, 35, 32, 30, 18], "label": 3},
    {"name": "Artifact_DayOfWeek", "dna": [22, 18, 25, 62, 40, 28, 35, 12], "label": 3},
    {"name": "Artifact_RSICrossover", "dna": [32, 25, 20, 55, 38, 25, 42, 15], "label": 3},
    {"name": "Artifact_3varInteraction", "dna": [20, 15, 30, 52, 28, 22, 35, 10], "label": 3},
    {"name": "Artifact_LuckyBacktest", "dna": [38, 28, 42, 45, 32, 28, 28, 12], "label": 3},
]


def _academic_archetype_library() -> Tuple[np.ndarray, np.ndarray]:
    """Academic factor archetype library with deterministic small-jitter augmentation."""
    base_x = np.asarray([row["dna"] for row in _ACADEMIC_ARCHETYPES], dtype=float)
    base_y = np.asarray([row["label"] for row in _ACADEMIC_ARCHETYPES], dtype=int)
    rng = np.random.default_rng(1729)
    x_parts = [base_x]
    y_parts = [base_y]
    for _ in range(4):
        x_parts.append(np.clip(base_x + rng.uniform(-4.0, 4.0, size=base_x.shape), 0, 100))
        y_parts.append(base_y.copy())
    return np.vstack(x_parts), np.concatenate(y_parts)
