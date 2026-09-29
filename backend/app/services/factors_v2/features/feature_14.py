"""Feature 14: Allocator Transparency Report Generator."""

import base64
import json
from concurrent.futures import ThreadPoolExecutor, as_completed
from io import BytesIO
from typing import Any, Dict

from app.services.factors_v2.core.analytics import html_report, response, run_feature_module
from app.services.factors_v2.core.performance import compute_mode, runtime_meta, stable_cache_key
from reportlab.lib import colors
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.platypus import Image, Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

_SECTION_FRAGMENT_CACHE: dict[str, Dict[str, Any]] = {}

DDQ_MAPPING = {
    "Current Factor Exposures": "ILPA DDQ 2.0: Investment strategy, portfolio exposures, and risk-factor disclosure",
    "Factor Attribution": "AIMA DDQ: Performance attribution and source-of-return decomposition",
    "Crowding Disclosure": "ILPA DDQ 2.0: Risk management, concentration, liquidity, and crowding controls",
    "Backtest and Drawdown": "AIMA DDQ: Track record, drawdown, and backtest methodology disclosure",
    "Capacity Map": "ILPA DDQ 2.0: Capacity, liquidity, and scalability of strategy",
    "Stress Test Results": "AIMA DDQ: Scenario analysis, stress testing, and downside-risk controls",
    "Signal Health": "ILPA DDQ 2.0: Ongoing monitoring, model governance, and signal decay surveillance",
    "Manager Commentary": "Manager-provided supplemental narrative",
    "Fund-Specific Disclosures": "Fund-specific legal and operational disclosures",
}


def run(payload: Dict[str, Any]) -> Dict[str, Any]:
    mode = compute_mode(payload)
    sections = []
    upstream = {}
    include_sections = set(payload.get("include_sections") or ["Current Factor Exposures", "Factor Attribution", "Crowding Disclosure", "Backtest and Drawdown", "Capacity Map", "Stress Test Results", "Signal Health"])
    custom_narrative = payload.get("custom_narrative", "")
    disclosures = payload.get("fund_disclosures", "")
    feature_map = [
        (2, "Current Factor Exposures"),
        (3, "Factor Attribution"),
        (6, "Crowding Disclosure"),
        (7, "Backtest and Drawdown"),
        (9, "Capacity Map"),
        (11, "Stress Test Results"),
        (13, "Signal Health"),
    ]
    selected = [(num, title) for num, title in feature_map if title in include_sections]
    section_by_title = {}
    # Default to sequential collection. Several upstream features use Numba
    # parallel kernels; running them from multiple Python threads can terminate
    # the process under Numba's workqueue backend. Parallel collection remains
    # an explicit Research/ops toggle after the runtime is configured for TBB.
    parallel_requested = bool(payload.get("parallel_report_sections", False))
    max_workers = min(len(selected), 7) if parallel_requested else 1
    if max_workers > 1:
        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            futures = {executor.submit(run_feature_module, num, payload): (num, title) for num, title in selected}
            iterator = ((futures[future], future) for future in as_completed(futures))
            for (num, title), future in iterator:
                try:
                    out = future.result()
                    upstream[f"feature_{num:02d}"] = out.get("status")
                    summary = "; ".join(f"{c.get('label')}: {c.get('value')}" for c in out.get("summary_cards", [])[:3])
                    section_key = stable_cache_key("feature_14", {"title": title, "summary": summary, "status": out.get("status")}, "section_fragment")
                    section_by_title[title] = _SECTION_FRAGMENT_CACHE.setdefault(section_key, {"title": title, "summary": summary, "status": out.get("status")})
                except Exception as exc:
                    upstream[f"feature_{num:02d}"] = f"error: {exc}"
                    section_by_title[title] = {"title": title, "summary": "Section unavailable from upstream compute.", "status": "error"}
    else:
        for num, title in selected:
            try:
                out = run_feature_module(num, payload)
                upstream[f"feature_{num:02d}"] = out.get("status")
                summary = "; ".join(f"{c.get('label')}: {c.get('value')}" for c in out.get("summary_cards", [])[:3])
                section_key = stable_cache_key("feature_14", {"title": title, "summary": summary, "status": out.get("status")}, "section_fragment")
                section_by_title[title] = _SECTION_FRAGMENT_CACHE.setdefault(section_key, {"title": title, "summary": summary, "status": out.get("status")})
            except Exception as exc:
                upstream[f"feature_{num:02d}"] = f"error: {exc}"
                section_by_title[title] = {"title": title, "summary": "Section unavailable from upstream compute.", "status": "error"}
    sections.extend([section_by_title[title] for _, title in selected if title in section_by_title])
    if custom_narrative:
        sections.insert(0, {"title": "Manager Commentary", "summary": custom_narrative, "status": "manual"})
    if disclosures:
        sections.insert(0, {"title": "Fund-Specific Disclosures", "summary": disclosures, "status": "manual"})
    sections = _order_sections(sections, payload.get("section_order"))
    max_pages = int(payload.get("max_pdf_pages", 20))
    estimated_pages = max(2, len(sections) + 1)
    pdf_deferred = estimated_pages > max_pages and mode != "research"
    html = html_report(sections)
    audit = {
        "report_version": payload.get("report_version", "v1.0"),
        "generated_at": __import__("datetime").datetime.utcnow().isoformat() + "Z",
        "data_through": payload.get("data_through", "latest local close"),
        "history_note": _history_note(payload),
        "parameters": payload,
        "upstream_status": upstream,
        "manual_overrides": {"custom_narrative": bool(custom_narrative), "fund_disclosures": bool(disclosures), "section_order": bool(payload.get("section_order"))},
    }
    pdf_bytes = b"" if pdf_deferred else _render_pdf(sections, payload, audit)
    pdf_b64 = base64.b64encode(pdf_bytes).decode("ascii")
    return response(
        "feature_14",
        "ok",
        summary_cards=[{"label": "Report Sections", "value": len(sections)}, {"label": "PDF Export", "value": "async_required" if pdf_deferred else "ready"}, {"label": "PDF Size", "value": len(pdf_bytes), "unit": "bytes"}],
        charts={},
        tables={
            "sections": sections,
            "aima_ddq_cross_reference": [{"section": s["title"], "ddq_mapping": DDQ_MAPPING.get(s["title"], "Supplemental factor analytics disclosure")} for s in sections],
            "customization_controls": [
                {"control": "include_sections", "active": bool(payload.get("include_sections"))},
                {"control": "section_order", "active": bool(payload.get("section_order"))},
                {"control": "custom_narrative", "active": bool(custom_narrative)},
                {"control": "fund_disclosures", "active": bool(disclosures)},
                {"control": "report_version", "value": audit["report_version"]},
            ],
        },
        alerts=[{"level": "medium", "message": "PDF page estimate exceeds realtime cap; run in Research Mode/async", "estimated_pages": estimated_pages, "max_pages": max_pages}] if pdf_deferred else [],
        meta={
            **runtime_meta("feature_14", payload, ["PDF rendering capped at 20 pages by default; longer reports require Research Mode/async"]),
            "html": html,
            "audit_trail": audit,
            "pdf_export": "async_required" if pdf_deferred else "reportlab_pdf_base64",
            "pdf_base64": pdf_b64,
            "pdf_page_cap": max_pages,
            "estimated_pages": estimated_pages,
            "async_cache_key": stable_cache_key("feature_14", payload, "long_pdf") if pdf_deferred else None,
            "performance": {
                "section_parallelism": max_workers,
                "parallelism_policy": "sequential by default because upstream Numba parallel kernels are not thread-safe under workqueue; set parallel_report_sections only when runtime threading layer is configured safely",
                "template_fragment_cache_entries": len(_SECTION_FRAGMENT_CACHE),
                "pdf_streaming": "BytesIO ReportLab stream",
                "chart_rendering": "upstream JSON fragments reused; chart image rasterization remains frontend/export worker concern",
                "logo_embedding": "enabled when payload.logo_path points to a local image",
            },
        },
    )


def _order_sections(sections, order):
    if not order:
        return sections
    rank = {name: idx for idx, name in enumerate(order)}
    return sorted(sections, key=lambda section: rank.get(section.get("title"), 10_000))


def _history_note(payload):
    years = float(payload.get("history_years", 5))
    if years < 5:
        return f"Available history is {years:g} years; charts and DDQ language should be interpreted with limited-history caution."
    return "History requirement satisfied or using full available local history."


def _render_pdf(sections, payload, audit) -> bytes:
    buffer = BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=letter, rightMargin=40, leftMargin=40, topMargin=40, bottomMargin=40)
    styles = getSampleStyleSheet()
    story = [
        Paragraph(payload.get("fund_name", "Quant360 Factors V2 Allocator Transparency Report"), styles["Title"]),
        Paragraph(f"Generated at {audit['generated_at']}", styles["Normal"]),
        Spacer(1, 16),
    ]
    logo_path = payload.get("logo_path")
    if logo_path:
        try:
            story.insert(0, Image(str(logo_path), width=96, height=48, kind="proportional"))
            story.insert(1, Spacer(1, 10))
        except Exception:
            story.append(Paragraph("Logo path provided but could not be embedded.", styles["Italic"]))
    rows = [["Section", "Status", "Summary"]]
    rows.extend([[s.get("title", ""), s.get("status", ""), s.get("summary", "")[:160]] for s in sections])
    table = Table(rows, colWidths=[170, 70, 280])
    table.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#eef2ff")),
                ("TEXTCOLOR", (0, 0), (-1, 0), colors.HexColor("#111827")),
                ("GRID", (0, 0), (-1, -1), 0.4, colors.HexColor("#d1d5db")),
                ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#f9fafb")]),
            ]
        )
    )
    story.append(table)
    for section in sections:
        story.append(Spacer(1, 14))
        story.append(Paragraph(str(section.get("title", "Section")), styles["Heading2"]))
        story.append(Paragraph(str(section.get("summary", "No summary available.")), styles["BodyText"]))
    contact = payload.get("contact_info")
    disclaimer = payload.get("disclaimer") or payload.get("fund_disclosures")
    if contact:
        story.extend([Spacer(1, 12), Paragraph("Contact", styles["Heading2"]), Paragraph(str(contact), styles["BodyText"])])
    if disclaimer:
        story.extend([Spacer(1, 12), Paragraph("Disclaimer", styles["Heading2"]), Paragraph(str(disclaimer), styles["BodyText"])])
    story.append(Spacer(1, 16))
    story.append(Paragraph("Audit Trail", styles["Heading2"]))
    story.append(Paragraph(json.dumps(audit, sort_keys=True, default=str, indent=2).replace("\n", "<br/>"), styles["Code"]))
    doc.build(story)
    return buffer.getvalue()
