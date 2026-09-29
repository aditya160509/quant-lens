"""Feature 06: Specification Builder and Publication Output."""

from __future__ import annotations

import base64
import json
from io import BytesIO
from typing import Any

import numpy as np
import pandas as pd

from .estimators import fama_macbeth, panel_regression
from .holdout import locked, spec_hash
from .panel import build_panel
from .stats import auto_nw_lag

ESTIMATORS = {"fama_macbeth", "panel_ols"}
DEFAULT_LABELS = {
    "momentum": "Momentum (12-1)", "reversal": "Reversal (1m)", "low_vol": "Low volatility", "yang_zhang_vol": "Low Yang-Zhang vol",
    "garman_klass_vol": "Low Garman-Klass vol", "beta": "Beta", "ivol": "Idiosyncratic vol", "size": "Size (log ME)",
    "value": "Value (log B/M)", "quality": "Quality (ROE)", "profitability": "Gross profitability", "investment": "Low investment",
    "leverage": "Leverage", "asset_growth": "Asset growth",
}
SE_TYPES = {"nw_auto", "nw_3", "nw_6", "nw_12", "clustered_time", "clustered_asset", "clustered_both", "driscoll_kraay", "robust", "unadjusted"}


def default_columns(signal: str, alt_signal: str) -> list[dict[str, Any]]:
    base = {"dependent_variable": "forward_return", "signal": signal, "weighting": "equal"}
    return [
        {**base, "label": "(1)", "controls": "none", "estimator": "fama_macbeth", "se": "nw_auto", "fixed_effects": "none"},
        {**base, "label": "(2)", "controls": "size", "estimator": "fama_macbeth", "se": "nw_auto", "fixed_effects": "none"},
        {**base, "label": "(3)", "controls": "size,value", "estimator": "fama_macbeth", "se": "nw_auto", "fixed_effects": "none"},
        {**base, "label": "(4)", "controls": "full", "estimator": "fama_macbeth", "se": "nw_auto", "fixed_effects": "none"},
        {**base, "label": "(5)", "controls": "full", "estimator": "panel_ols", "se": "clustered_both", "fixed_effects": "time"},
        {**base, "label": "(6)", "controls": "full", "estimator": "panel_ols", "se": "clustered_both", "fixed_effects": "asset"},
        {**base, "label": "(7)", "controls": "full", "estimator": "panel_ols", "se": "clustered_both", "fixed_effects": "two_way"},
        {**base, "label": "(8)", "signal": alt_signal, "controls": "full", "estimator": "fama_macbeth", "se": "nw_auto", "fixed_effects": "none"},
    ]


def parse_columns(payload: dict[str, Any]) -> list[dict[str, Any]]:
    raw = payload.get("table_columns")
    if isinstance(raw, str) and raw.strip():
        raw = json.loads(raw)
    if raw:
        cols = [dict(c) for c in raw]
    else:
        n = int(payload.get("number_of_columns") or 4)
        cols = default_columns(str(payload.get("signal") or "momentum"), str(payload.get("alternative_signal") or "low_vol"))[: max(2, min(8, n))]
    if not 2 <= len(cols) <= 8:
        raise ValueError("A publication table needs between 2 and 8 columns.")
    for i, c in enumerate(cols, start=1):
        c.setdefault("label", f"({i})")
        c.setdefault("estimator", "fama_macbeth")
        c.setdefault("se", "nw_auto")
        c.setdefault("fixed_effects", "none")
        c.setdefault("controls", "none")
        c.setdefault("weighting", "equal")
        c.setdefault("dependent_variable", "forward_return")
        c.setdefault("signal", payload.get("signal") or "momentum")
        c.setdefault("universe", payload.get("universe") or "us_equities")
        if c["estimator"] not in ESTIMATORS:
            raise ValueError(f"Column {c['label']}: estimator must be one of {sorted(ESTIMATORS)}")
        if c["se"] not in SE_TYPES:
            raise ValueError(f"Column {c['label']}: se must be one of {sorted(SE_TYPES)}")
        if c["estimator"] == "fama_macbeth" and c["fixed_effects"] != "none":
            raise ValueError(f"Column {c['label']}: fixed effects need the panel_ols estimator (Fama-MacBeth already removes time effects).")
    return cols


def fit_column(col: dict[str, Any], payload: dict[str, Any], cache: dict[str, Any]) -> dict[str, Any]:
    key = json.dumps({k: col.get(k) for k in ["dependent_variable", "signal", "controls", "weighting", "universe"]}, sort_keys=True)
    if key not in cache:
        cache[key] = build_panel({**payload, **{k: col[k] for k in ["dependent_variable", "signal", "controls", "weighting", "universe"]}})
    panel = cache[key]
    if col.get("start") or col.get("end"):
        lo = pd.Timestamp(col.get("start") or panel.dates.min())
        hi = pd.Timestamp(col.get("end") or panel.dates.max())
        panel = panel.subset_dates((panel.dates >= lo) & (panel.dates <= hi))
    controls = list(panel.controls)
    out: dict[str, Any] = {"label": col["label"], "spec_hash": spec_hash({**col, "holding_months": panel.holding_months})}
    if col["estimator"] == "fama_macbeth":
        lag = None if col["se"] == "nw_auto" else int(col["se"].split("_")[1]) if col["se"].startswith("nw_") else None
        weights = panel.weights if col["weighting"] != "equal" else None
        fm, slopes = fama_macbeth(panel, controls, lag) if weights is None else _weighted_fm(panel, controls, lag, weights)
        coefs = {r["term"]: {"coef": r["lambda"], "se": r["nw_se"], "t": r["t_stat"], "p": r["p_value"]} for r in fm.to_dict("records")}
        out.update({"coefficients": coefs, "r2": float(slopes["r2"].mean()) if len(slopes) else np.nan, "adj_r2": np.nan, "within_r2": np.nan, "observations": int(slopes["n_assets"].sum()) if len(slopes) else 0, "months": int(len(slopes)), "se_label": f"Newey-West ({int(fm['nw_lag'].iloc[0]) if len(fm) else '-'} lags)"})
    else:
        cov = "driscoll_kraay" if col["se"] in {"nw_auto", "driscoll_kraay"} or col["se"].startswith("nw_") else col["se"]
        res = panel_regression(panel, controls, col["fixed_effects"], cov, weighted=col["weighting"] == "value")
        if not res.get("available"):
            raise ValueError(f"Column {col['label']}: {res.get('reason')}")
        coefs = {r["term"]: {"coef": r["coefficient"], "se": r["se"], "t": r["t_stat"], "p": r["p_value"]} for r in res["table"].to_dict("records")}
        out.update({"coefficients": coefs, "r2": res["rsquared"], "within_r2": res["within_r2"] if res["asset_fe"] or res["time_fe"] else np.nan, "observations": res["nobs"], "months": res["periods"], "se_label": cov.replace("_", " ")})
    main_signal = str(payload.get("signal") or "momentum")
    if col["signal"] != main_signal and "signal" in out["coefficients"]:
        out["coefficients"][col["signal"]] = out["coefficients"].pop("signal")  # alternative signal gets its own row
    out["period"] = f"{panel.dates.min():%Y-%m} to {panel.dates.max():%Y-%m}"
    lock = locked({**col, "holding_months": panel.holding_months})
    out["tag"] = "confirmatory" if lock else "exploratory"
    out["locked_at"] = lock["locked_at"] if lock else None
    out["spec"] = col
    return out


def _weighted_fm(panel: Any, controls: list[str], lag: int | None, weights: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    from .estimators import fm_slopes
    from .stats import mean_test

    regs = {"signal": panel.signal, **{c: panel.controls[c] for c in controls}}
    slopes = fm_slopes(panel.dependent, regs, weights=weights)
    use = int(lag) if lag is not None else max(auto_nw_lag(len(slopes)), panel.holding_months)
    rows = []
    for term in [c for c in slopes.columns if c not in {"r2", "n_assets"}]:
        t = mean_test(slopes[term], use)
        rows.append({"term": term, "lambda": t["mean"], "nw_se": t["se"], "t_stat": t["t"], "p_value": t["p"], "nw_lag": use})
    return pd.DataFrame(rows), slopes


def star_rule(payload: dict[str, Any]) -> list[tuple[float, str]]:
    mode = str(payload.get("significance_stars") or "standard").lower()
    if mode == "five_one":
        return [(0.01, "***"), (0.05, "**")]
    if mode == "custom":
        cuts = sorted(float(x) for x in str(payload.get("custom_star_thresholds") or "0.01,0.05,0.10").split(","))
        return [(c, "*" * (len(cuts) - i)) for i, c in enumerate(cuts)]
    return [(0.01, "***"), (0.05, "**"), (0.10, "*")]


def _stars(p: float, rule: list[tuple[float, str]]) -> str:
    if not np.isfinite(p):
        return ""
    for cut, mark in rule:
        if p < cut:
            return mark
    return ""


def assemble_table(fits: list[dict[str, Any]], labels: dict[str, str], rule: list[tuple[float, str]], stats_rows: list[str]) -> tuple[list[dict[str, Any]], list[str]]:
    terms: list[str] = []
    for f in fits:
        for t in f["coefficients"]:
            if t not in terms and t not in {"const", "intercept"}:
                terms.append(t)
    terms = sorted(terms, key=lambda t: (t != "signal", terms.index(t)))
    cols = [f["label"] for f in fits]
    rows = []
    for term in terms:
        coef_row = {"row": labels.get(term, term), "kind": "coefficient"}
        se_row = {"row": "", "kind": "se"}
        for f in fits:
            c = f["coefficients"].get(term)
            coef_row[f["label"]] = f"{c['coef']:.3f}{_stars(c['p'], rule)}" if c and np.isfinite(c["coef"]) else ""
            se_row[f["label"]] = f"({c['se']:.3f})" if c and np.isfinite(c["se"]) else ""
        rows += [coef_row, se_row]
    stat_defs = {
        "r2": ("R²", lambda f: f"{f['r2']:.3f}" if np.isfinite(f.get("r2", np.nan)) else ""),
        "within_r2": ("Within R²", lambda f: f"{f['within_r2']:.3f}" if np.isfinite(f.get("within_r2", np.nan)) else ""),
        "observations": ("Observations", lambda f: f"{f['observations']:,}"),
        "months": ("Months", lambda f: str(f["months"])),
        "period": ("Sample", lambda f: f["period"]),
        "fixed_effects": ("Fixed effects", lambda f: f["spec"]["fixed_effects"].replace("_", "-")),
        "estimator": ("Estimator", lambda f: "FM" if f["spec"]["estimator"] == "fama_macbeth" else "Panel OLS"),
        "se": ("Std. errors", lambda f: f["se_label"]),
        "tag": ("Tag", lambda f: f["tag"]),
    }
    for key in stats_rows:
        if key in stat_defs:
            name, fn = stat_defs[key]
            rows.append({"row": name, "kind": "stat", **{f["label"]: fn(f) for f in fits}})
    return rows, cols


def latex(rows: list[dict[str, Any]], cols: list[str], title: str, notes: str, rule: list[tuple[float, str]], fits: list[dict[str, Any]]) -> str:
    def esc(s: str) -> str:
        return str(s).replace("&", "\\&").replace("%", "\\%").replace("_", "\\_").replace("²", "$^2$")

    tags = " & ".join(["", *[("\\textit{C}" if f["tag"] == "confirmatory" else "\\textit{E}") for f in fits]]) + " \\\\"
    lines = [
        "\\begin{table}[htbp]\\centering",
        "\\begin{threeparttable}",
        f"\\caption{{{esc(title)}}}",
        f"\\begin{{tabular}}{{l{'c' * len(cols)}}}",
        "\\toprule",
        " & ".join(["", *cols]) + " \\\\",
        tags,
        "\\midrule",
    ]
    stat_started = False
    for r in rows:
        if r["kind"] == "stat" and not stat_started:
            lines.append("\\midrule")
            stat_started = True
        lines.append(" & ".join([esc(r["row"]), *[esc(r.get(c, "")) for c in cols]]) + " \\\\")
    star_note = ", ".join(f"{mark} p < {cut:g}" for cut, mark in rule)
    lines += [
        "\\bottomrule",
        "\\end{tabular}",
        "\\begin{tablenotes}\\footnotesize",
        f"\\item {esc(notes)} Standard errors in parentheses. {esc(star_note)}. C = confirmatory (pre-registered) column, E = exploratory.",
        "\\end{tablenotes}",
        "\\end{threeparttable}",
        "\\end{table}",
    ]
    return "\n".join(lines)


def pdf(rows: list[dict[str, Any]], cols: list[str], title: str, notes: str) -> dict[str, Any]:
    from reportlab.lib import colors
    from reportlab.lib.pagesizes import letter
    from reportlab.lib.styles import getSampleStyleSheet
    from reportlab.lib.units import inch
    from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

    buffer = BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=letter, leftMargin=inch, rightMargin=inch, topMargin=inch, bottomMargin=inch)  # 6.5in text width
    styles = getSampleStyleSheet()
    data = [["", *cols], *[[r["row"], *[r.get(c, "") for c in cols]] for r in rows]]
    col_w = [1.6 * inch] + [(6.5 - 1.6) * inch / len(cols)] * len(cols)
    table = Table(data, colWidths=col_w, repeatRows=1)
    first_stat = next((i + 1 for i, r in enumerate(rows) if r["kind"] == "stat"), len(rows) + 1)
    table.setStyle(TableStyle([
        ("FONTNAME", (0, 0), (-1, -1), "Times-Roman"), ("FONTSIZE", (0, 0), (-1, -1), 8.5),
        ("ALIGN", (1, 0), (-1, -1), "CENTER"),
        ("LINEABOVE", (0, 0), (-1, 0), 1, colors.black), ("LINEBELOW", (0, 0), (-1, 0), 0.5, colors.black),
        ("LINEABOVE", (0, first_stat), (-1, first_stat), 0.5, colors.black), ("LINEBELOW", (0, -1), (-1, -1), 1, colors.black),
        ("TOPPADDING", (0, 0), (-1, -1), 1.5), ("BOTTOMPADDING", (0, 0), (-1, -1), 1.5),
    ]))
    doc.build([Paragraph(title, styles["Heading3"]), Spacer(1, 6), table, Spacer(1, 6), Paragraph(notes, styles["BodyText"])])
    raw = buffer.getvalue()
    return {"filename": "research_v2_table.pdf", "mime_type": "application/pdf", "bytes": len(raw), "base64": base64.b64encode(raw).decode("ascii")}


def run_specification(payload: dict[str, Any]) -> dict[str, Any]:
    cols = parse_columns(payload)
    auto = str(payload.get("auto_populate") or "manual").lower()
    curve_note = ""
    if auto == "spec_curve":
        cols, curve_note = _columns_from_curve(payload, cols)
    cache: dict[str, Any] = {}
    fits = [fit_column(c, payload, cache) for c in cols]
    labels = payload.get("variable_labels") or {}
    if isinstance(labels, str) and labels.strip():
        labels = json.loads(labels)
    labels = {**DEFAULT_LABELS, "signal": DEFAULT_LABELS.get(str(payload.get("signal") or "momentum"), "Signal"), **labels}
    rule = star_rule(payload)
    stats_rows = payload.get("statistics_rows") or ["r2", "within_r2", "observations", "months", "fixed_effects", "estimator", "se", "tag"]
    if isinstance(stats_rows, str):
        stats_rows = [s.strip() for s in stats_rows.split(",")]
    title = str(payload.get("table_title") or "Cross-sectional return predictability")
    notes = str(payload.get("table_notes") or "The dependent variable is the forward return over the holding period. Fama-MacBeth columns report time-series averages of monthly cross-sectional slopes; panel columns report pooled OLS with the listed fixed effects.")
    rows, labels_cols = assemble_table(fits, labels, rule, stats_rows)
    latex_code = latex(rows, labels_cols, title, notes, rule, fits)
    pdf_file = pdf(rows, labels_cols, title, notes)
    forest = [{"column": f["label"], "coefficient": f["coefficients"]["signal"]["coef"], "lower_95": f["coefficients"]["signal"]["coef"] - 1.96 * f["coefficients"]["signal"]["se"], "upper_95": f["coefficients"]["signal"]["coef"] + 1.96 * f["coefficients"]["signal"]["se"], "tag": f["tag"]} for f in fits if "signal" in f["coefficients"]]
    csv_rows = [{"column": f["label"], "term": t, **v, "tag": f["tag"]} for f in fits for t, v in f["coefficients"].items()]
    tags = [{"column": f["label"], "tag": f["tag"], "spec_hash": f["spec_hash"], "locked_at": f["locked_at"]} for f in fits]
    tables = {
        "publication_table": rows,
        "column_specifications": [{"label": f["label"], **{k: v for k, v in f["spec"].items() if k != "label"}, "period": f["period"]} for f in fits],
        "confirmatory_exploratory_tags": tags,
        "latex_export": [{"table": "main_table", "latex": latex_code}],
        "csv_export": [{"name": "coefficients", "csv": pd.DataFrame(csv_rows).to_csv(index=False)}],
        "pdf_export": [{k: v for k, v in pdf_file.items() if k != "base64"}],
    }
    charts = {"coefficient_forest_plot": forest}
    summary = [
        {"label": "Columns", "value": len(fits)},
        {"label": "Confirmatory", "value": sum(f["tag"] == "confirmatory" for f in fits)},
        {"label": "Signal t (col 1)", "value": fits[0]["coefficients"].get("signal", {}).get("t")},
    ]
    return {"summary": summary, "charts": charts, "tables": tables, "meta": {"table_title": title, "pdf_base64": pdf_file["base64"], "auto_populate_note": curve_note, "research_caveats": sorted({c for p in cache.values() for c in p.caveats})}}


def _columns_from_curve(payload: dict[str, Any], cols: list[dict[str, Any]]) -> tuple[list[dict[str, Any]], str]:
    """Pick table columns from the Feature 2 specification curve instead of by hand.

    Columns are the curve's 10th, 25th, 50th, 75th and 90th percentile
    specifications among those that change controls (the dimension a
    regression table can express), plus the base.
    """

    from .robustness import robustness_from_panel

    panel = build_panel(payload)
    res = robustness_from_panel(panel, {**payload, "dimensions": "controls,transform,time_window", "permutation_replications": 0})
    curve = res["charts"]["specification_curve"].reset_index(drop=True)
    if curve.empty:
        return cols, "Specification curve was empty; manual columns kept."
    picks = sorted({int(round(q * (len(curve) - 1))) for q in (0.1, 0.25, 0.5, 0.75, 0.9)})
    out = []
    for i, idx in enumerate(picks, start=1):
        row = curve.iloc[idx]
        controls = "none" if row["controls"] == "base" else row["controls"]
        out.append({"label": f"({i})", "signal": payload.get("signal") or "momentum", "controls": controls, "estimator": "fama_macbeth", "se": "nw_auto", "fixed_effects": "none", "weighting": "equal", "dependent_variable": "forward_return", "curve_percentile": round(idx / max(len(curve) - 1, 1), 2)})
    return out, f"Columns chosen at the 10/25/50/75/90th percentiles of a {len(curve)}-specification curve."
