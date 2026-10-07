"""Source-backed PDF reporting with explicit section failures and no fragment cache."""

import base64
from datetime import datetime, timezone
from io import BytesIO
from html import escape
import json
import numpy as np
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, Image
from reportlab.graphics.shapes import Drawing, PolyLine, String
from reportlab.lib import colors
from reportlab.pdfgen.canvas import Canvas
from app.services.factors_v2.core.analytics import response
from app.services.factors_v2.core.uploads import resolve_id

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


FEATURES = {
    2: "Current Factor Exposures",
    3: "Factor Attribution",
    6: "Crowding Disclosure",
    7: "Backtest and Drawdown",
    9: "Capacity Map",
    11: "Stress Test Results",
    13: "Signal Health",
}


def _chart(result):
    for key, value in result.get("charts", {}).items():
        candidates = (
            value
            if isinstance(value, list)
            else next((v for v in value.values() if isinstance(v, list)), [])
            if isinstance(value, dict)
            else []
        )
        if len(candidates) < 2 or not isinstance(candidates[0], dict):
            continue
        column = next(
            (
                k
                for k, v in candidates[0].items()
                if isinstance(v, (float, int))
                and k not in {"horizon", "sample", "observations", "rank"}
            ),
            None,
        )
        if column:
            points = [
                (i, float(row[column]))
                for i, row in enumerate(candidates)
                if isinstance(row.get(column), (float, int))
                and np.isfinite(row[column])
            ]
            if len(points) > 1:
                return key, column, points
    return None


class ReportCanvas(Canvas):
    max_pages = 100

    def showPage(self):
        if self._pageNumber > self.max_pages:
            raise ValueError(
                "Rendered PDF exceeds max_pdf_pages; request a larger explicit cap"
            )
        self.setFont("Helvetica", 8)
        self.drawRightString(560, 24, f"Page {self._pageNumber}")
        super().showPage()


def _render_pdf(sections, payload, audit, results):
    buffer = BytesIO()
    style = getSampleStyleSheet()
    story = [
        Paragraph(escape(payload.get("fund_name", "Factors V2 Report")), style["Title"])
    ]
    if payload.get("logo_upload_id"):
        story.append(
            Image(
                str(resolve_id(payload["logo_upload_id"], "png")),
                width=96,
                height=48,
                kind="proportional",
            )
        )
    story.append(Paragraph(escape(audit["generated_at"]), style["Normal"]))
    for section in sections:
        story.extend(
            [
                Spacer(1, 12),
                Paragraph(escape(section["title"]), style["Heading2"]),
                Paragraph(escape(section["summary"]), style["BodyText"]),
            ]
        )
        result = results.get(section["title"])
        chart = _chart(result) if result else None
        if chart:
            key, column, points = chart
            ys = np.array([v for _, v in points])
            span = float(np.ptp(ys)) or 1
            drawing = Drawing(480, 160)
            xy = [
                (
                    10 + i / max(len(points) - 1, 1) * 460,
                    25 + (v - ys.min()) / span * 110,
                )
                for i, (_, v) in enumerate(points)
            ]
            drawing.add(
                PolyLine(xy, strokeColor=colors.HexColor("#2463a5"), strokeWidth=1)
            )
            drawing.add(String(10, 145, f"{key}: {column}", fontSize=9))
            drawing.add(
                String(
                    10,
                    10,
                    f"Observed range {ys.min():.5g} to {ys.max():.5g}; ordered records",
                    fontSize=8,
                )
            )
            story.append(drawing)
        if result:
            cards = result.get("summary_cards", [])
            if cards:
                story.append(
                    Table(
                        [
                            [
                                str(c.get("label", c.get("factor", "metric"))),
                                str(c.get("value", c.get("characteristic_exposure"))),
                            ]
                            for c in cards
                        ],
                        colWidths=[240, 240],
                    )
                )
    for label, key in [("Contact", "contact_info"), ("Disclaimer", "disclaimer")]:
        if payload.get(key):
            story.extend(
                [
                    Spacer(1, 10),
                    Paragraph(label, style["Heading2"]),
                    Paragraph(escape(str(payload[key])), style["BodyText"]),
                ]
            )
    story.extend(
        [
            Spacer(1, 10),
            Paragraph("Audit", style["Heading2"]),
            Paragraph(escape(json.dumps(audit, default=str)), style["BodyText"]),
        ]
    )

    class CappedCanvas(ReportCanvas):
        max_pages = int(payload.get("max_pdf_pages", 20))

    SimpleDocTemplate(buffer, rightMargin=40, leftMargin=40).build(
        story, canvasmaker=CappedCanvas
    )
    return buffer.getvalue()


def run(payload):
    from app.services.factors_v2.registry import run_feature
    from app.services.factors_v2.features.inputs import inputs

    selected = payload.get("include_sections") or list(FEATURES.values())
    unknown = set(selected) - set(FEATURES.values())
    if unknown:
        raise ValueError("Unknown report sections: " + ", ".join(sorted(unknown)))
    results = {}
    sections = []
    for num, title in FEATURES.items():
        if title not in selected:
            continue
        fid = str(num).zfill(2)
        allowed = {i["key"] for i in inputs(fid)}
        params = {k: v for k, v in payload.items() if k in allowed}
        params.update(payload.get("feature_payloads", {}).get(fid, {}))
        try:
            result = run_feature(fid, params)
            results[title] = result
            summary = (
                "; ".join(
                    str(c.get("label", c.get("factor", "Metric")))
                    + ": "
                    + str(c.get("value", c.get("characteristic_exposure")))
                    for c in result.get("summary_cards", [])
                )
                or "See observed tables and estimator limitations in the source artifact."
            )
            sections.append(
                {"title": title, "status": result["status"], "summary": summary}
            )
        except (ValueError, TypeError, KeyError, np.linalg.LinAlgError) as exc:
            sections.append({"title": title, "status": "error", "summary": str(exc)})
    for title, key in [
        ("Manager Commentary", "custom_narrative"),
        ("Fund-Specific Disclosures", "fund_disclosures"),
    ]:
        if payload.get(key):
            sections.append(
                {"title": title, "status": "manual", "summary": str(payload[key])}
            )
    order = {s: i for i, s in enumerate(payload.get("section_order", []))}
    sections.sort(key=lambda s: order.get(s["title"], 1000))
    audit = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "as_of_date": payload.get("as_of_date"),
        "parameters": payload,
        "upstream_status": {s["title"]: s["status"] for s in sections},
        "source_versions": next(iter(results.values()), {})
        .get("meta", {})
        .get("source_versions", []),
    }
    status = (
        "partial"
        if any(s["status"] not in {"ok", "manual"} for s in sections)
        else "ok"
    )
    pdf = _render_pdf(sections, payload, audit, results)
    html = (
        "<!doctype html><html><body>"
        + "".join(
            "<h2>" + escape(s["title"]) + "</h2><p>" + escape(s["summary"]) + "</p>"
            for s in sections
        )
        + "</body></html>"
    )
    return response(
        "feature_14",
        status,
        summary_cards=[
            {"label": "Report Sections", "value": len(sections)},
            {"label": "PDF Size", "value": len(pdf)},
        ],
        tables={
            "sections": sections,
            "aima_ddq_cross_reference": [
                {
                    "section": s["title"],
                    "ddq_mapping": DDQ_MAPPING.get(s["title"], "Manager narrative"),
                }
                for s in sections
            ],
        },
        meta={
            "pdf_base64": base64.b64encode(pdf).decode(),
            "html": html,
            "audit_trail": audit,
            "chart_rendering": "Vector plots of actual upstream ordered numeric records; no demo series",
            "missing_output_reasons": {
                "individual_section_exports": "Only full PDF and JSON section export are offered"
            },
        },
    )


from .inputs import inputs as _inputs, outputs as _outputs

INPUTS = _inputs("14")
OUTPUTS = _outputs("14")
