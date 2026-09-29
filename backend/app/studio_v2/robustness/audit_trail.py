"""Tamper-evident look-ahead audit bundles."""

from __future__ import annotations

import hashlib
import hmac
import json
import os
import io
from typing import Any

from ..shared.persistence import SQLiteStore, utc_now


class AuditTrail:
    def __init__(self, store: SQLiteStore | None = None) -> None:
        self.store = store or SQLiteStore()
        self.key = os.environ.get("STUDIO_V2_AUDIT_KEY", "local-development-key").encode()

    def create(self, strategy_id: str, source: str, findings: list[dict], metadata: dict | None = None) -> dict:
        previous = self.store.list("audit_trail", limit=1)
        context = dict(metadata or {})
        record = {
            "strategy_id": strategy_id,
            "created_at": utc_now(),
            "source_sha256": hashlib.sha256(source.encode()).hexdigest(),
            "findings": findings,
            "sections": {
                "linter_section": {
                    "finding_count": len(findings),
                    "passed": not any(str(row.get("severity", "")).lower() in {"error", "critical"} for row in findings),
                    "findings": findings,
                },
                "engine_section": {
                    "run_ids": context.get("run_ids", []),
                    "fill_timing": context.get("fill_timing", []),
                    "next_open_enforced": context.get("next_open_enforced"),
                },
                "cv_section": {
                    "runs": context.get("cv_runs", []),
                    "purge": context.get("purge"),
                    "embargo": context.get("embargo"),
                },
            },
            "metadata": context,
            "previous_hash": previous[0].get("record_hash") if previous else None,
        }
        canonical = json.dumps(record, sort_keys=True, separators=(",", ":"), default=str).encode()
        record["record_hash"] = hashlib.sha256(canonical).hexdigest()
        record["signature"] = hmac.new(self.key, canonical, hashlib.sha256).hexdigest()
        return self.store.put("audit_trail", record["record_hash"], record, create_only=True)

    @staticmethod
    def render_pdf(record: dict[str, Any]) -> bytes:
        try:
            from reportlab.lib.pagesizes import letter
            from reportlab.pdfgen import canvas
        except ImportError:
            lines = [
                "Studio V2 Look-Ahead Audit",
                f"Strategy: {record.get('strategy_id')}",
                f"Created: {record.get('created_at')}",
                f"Source SHA-256: {record.get('source_sha256')}",
                *json.dumps(record.get("sections", {}), sort_keys=True, default=str, indent=2).splitlines(),
            ]
            escaped = [
                str(line)[:110].replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)")
                for line in lines[:60]
            ]
            stream = "BT /F1 8 Tf 42 750 Td 10 TL " + " ".join(
                f"({line}) Tj T*" for line in escaped
            ) + " ET"
            objects = [
                b"<< /Type /Catalog /Pages 2 0 R >>",
                b"<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
                b"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] /Resources << /Font << /F1 5 0 R >> >> /Contents 4 0 R >>",
                f"<< /Length {len(stream.encode())} >>\nstream\n{stream}\nendstream".encode(),
                b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>",
            ]
            payload = bytearray(b"%PDF-1.4\n")
            offsets = [0]
            for index, obj in enumerate(objects, 1):
                offsets.append(len(payload))
                payload.extend(f"{index} 0 obj\n".encode() + obj + b"\nendobj\n")
            xref = len(payload)
            payload.extend(f"xref\n0 {len(objects) + 1}\n0000000000 65535 f \n".encode())
            for offset in offsets[1:]:
                payload.extend(f"{offset:010d} 00000 n \n".encode())
            payload.extend(
                f"trailer << /Size {len(objects) + 1} /Root 1 0 R >>\nstartxref\n{xref}\n%%EOF".encode()
            )
            return bytes(payload)
        buffer = io.BytesIO()
        document = canvas.Canvas(buffer, pagesize=letter)
        width, height = letter
        y = height - 48
        document.setFont("Helvetica-Bold", 15)
        document.drawString(48, y, "Studio V2 Look-Ahead Audit")
        y -= 24
        document.setFont("Helvetica", 9)
        for label, value in (
            ("Strategy", record.get("strategy_id")),
            ("Created", record.get("created_at")),
            ("Source SHA-256", record.get("source_sha256")),
            ("Record hash", record.get("record_hash")),
        ):
            document.drawString(48, y, f"{label}: {value}")
            y -= 14
        for section_name, section in record.get("sections", {}).items():
            y -= 10
            if y < 90:
                document.showPage(); y = height - 48
            document.setFont("Helvetica-Bold", 11)
            document.drawString(48, y, section_name.replace("_", " ").title())
            y -= 16
            document.setFont("Helvetica", 8)
            for line in json.dumps(section, sort_keys=True, default=str, indent=2).splitlines():
                if y < 48:
                    document.showPage(); y = height - 48; document.setFont("Helvetica", 8)
                document.drawString(56, y, line[:110])
                y -= 10
        document.save()
        return buffer.getvalue()

    def verify(self, record: dict) -> bool:
        unsigned = {
            key: value for key, value in record.items()
            if key not in {"id", "updated_at", "_revision", "record_hash", "signature"}
        }
        canonical = json.dumps(unsigned, sort_keys=True, separators=(",", ":"), default=str).encode()
        return hmac.compare_digest(record["signature"], hmac.new(self.key, canonical, hashlib.sha256).hexdigest())
