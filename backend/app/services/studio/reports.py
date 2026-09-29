"""Artifact-referenced output recipes and deterministic standalone reports."""

from __future__ import annotations

import csv
import hashlib
import html
import io
import json
import os
import uuid
from typing import Any, Optional

from app.studio_v2.shared.persistence import SQLiteStore
from app.services.studio.quotas import get_quota


RECIPES = "studio_output_recipes"
NOTES = "studio_research_notes"

REPORT_CONTRACT_VERSION = "1.1"
REPORT_ENGINE_VERSION = "studio-reports/1.1"

#: Central formula registry: resolved metric path -> human-readable formula.
#: Every formula is descriptive documentation of the canonical calculator that
#: produced the value; the registry never recomputes metrics.
FORMULAS: dict[str, str] = {
    "portfolio.metrics.sharpe": "mean(excess_returns) / std(excess_returns) * sqrt(periods_per_year)",
    "portfolio.metrics.expected_return": "sum(weights * expected_returns), annualized by periods_per_year",
    "portfolio.metrics.volatility": "sqrt(weights^T @ covariance @ weights) * sqrt(periods_per_year)",
    "portfolio.metrics.max_drawdown": "min(equity / running_peak - 1) over the net equity curve",
    "portfolio.metrics.turnover": "sum(|weight_new - weight_current|) / 2 against current weights",
    "portfolio.metrics.concentration_hhi": "sum(weights^2) across portfolio assets",
    "portfolio.metrics.tracking_error": "std(active_returns) * sqrt(periods_per_year) versus benchmark weights",
    "portfolio.metrics.estimated_cost_fraction": "turnover * cost_bps / 10000",
    "portfolio.warnings": "assumption and data-quality notes recorded with the artifact, not computed",
    "summary.avgOosSharpe": "mean(fold out-of-sample Sharpe) across walk-forward folds",
    "summary.consistency": "100 * profitable out-of-sample folds / total folds",
    "verdict.status": "deterministic threshold rules over average OOS Sharpe and fold consistency, not statistical confidence",
    "summary.mean_slippage_bps": "mean signed (fill_price / expected_price - 1) * 10000 over classified fills",
    "summary.fill_count": "count of fill events joined to intended orders in the causal ledger",
    "summary.alert_count": "count of alert events recorded for the paper deployment",
}

#: Per-template required-field policy: metric paths each template recommends.
#: Missing paths are reported as warnings in render/exports, never inferred.
TEMPLATE_REQUIRED_PATHS: dict[str, list[str]] = {
    "strategy_review": ["portfolio.metrics.sharpe", "portfolio.metrics.max_drawdown"],
    "validation": ["summary.avgOosSharpe", "verdict.status"],
    "portfolio_review": ["portfolio.metrics.sharpe", "portfolio.metrics.volatility"],
    "paper_reconciliation": ["summary.mean_slippage_bps", "summary.fill_count"],
    "custom": [],
}

#: Minimal authored server-side template layouts. Artifact blocks carry a null
#: reference that the composer fills with a real artifact identity; narrative
#: blocks carry guidance text only and never fabricated metrics.
TEMPLATE_DEFAULTS: dict[str, dict[str, Any]] = {
    "strategy_review": {
        "label": "Strategy review",
        "description": "Headline risk-adjusted result with drawdown and reviewer narrative.",
        "blocks": [
            {"block_id": "strategy_headline", "kind": "artifact", "title": "Headline result",
             "reference": None, "metric_paths": ["portfolio.metrics.sharpe", "portfolio.metrics.max_drawdown"],
             "text": "", "citations": [], "layout": {"w": 12, "h": 4}},
            {"block_id": "strategy_notes", "kind": "narrative", "title": "Reviewer notes",
             "reference": None, "metric_paths": [], "text": "Record the decision and its evidence here.",
             "citations": ["portfolio.metrics.sharpe"], "layout": {"w": 12, "h": 4}},
        ],
    },
    "validation": {
        "label": "Validation",
        "description": "Out-of-sample evidence with the deterministic promotion verdict.",
        "blocks": [
            {"block_id": "validation_evidence", "kind": "artifact", "title": "Out-of-sample evidence",
             "reference": None, "metric_paths": ["summary.avgOosSharpe", "summary.consistency"],
             "text": "", "citations": [], "layout": {"w": 6, "h": 4}},
            {"block_id": "validation_verdict", "kind": "artifact", "title": "Promotion verdict",
             "reference": None, "metric_paths": ["verdict.status"],
             "text": "", "citations": ["verdict.status"], "layout": {"w": 6, "h": 4}},
        ],
    },
    "portfolio_review": {
        "label": "Portfolio review",
        "description": "Allocation summary with risk, cost, and concentration context.",
        "blocks": [
            {"block_id": "allocation_summary", "kind": "artifact", "title": "Allocation summary",
             "reference": None, "metric_paths": ["portfolio.metrics.sharpe", "portfolio.metrics.volatility"],
             "text": "", "citations": [], "layout": {"w": 6, "h": 4}},
            {"block_id": "allocation_costs", "kind": "artifact", "title": "Costs and concentration",
             "reference": None, "metric_paths": ["portfolio.metrics.estimated_cost_fraction", "portfolio.metrics.concentration_hhi"],
             "text": "", "citations": [], "layout": {"w": 6, "h": 4}},
        ],
    },
    "paper_reconciliation": {
        "label": "Paper reconciliation",
        "description": "Fill reconciliation against intended prices with deployment alerts.",
        "blocks": [
            {"block_id": "reconciliation_slippage", "kind": "artifact", "title": "Execution reconciliation",
             "reference": None, "metric_paths": ["summary.mean_slippage_bps", "summary.fill_count"],
             "text": "", "citations": [], "layout": {"w": 6, "h": 4}},
            {"block_id": "reconciliation_alerts", "kind": "artifact", "title": "Alerts",
             "reference": None, "metric_paths": ["summary.alert_count"],
             "text": "", "citations": [], "layout": {"w": 6, "h": 4}},
        ],
    },
}


def template_block_list(template: str) -> list[dict[str, Any]]:
    """Return a deep copy of the authored block list for a template identity."""
    defaults = TEMPLATE_DEFAULTS.get(template)
    if defaults is None:
        raise ReportError("REPORT_TEMPLATE_NOT_FOUND", f"Unknown report template: {template}.", 404)
    return json.loads(json.dumps(defaults["blocks"]))


class ReportError(ValueError):
    def __init__(self, code: str, message: str, status_code: int = 422) -> None:
        super().__init__(message)
        self.code = code
        self.status_code = status_code


class ReportComposer:
    def __init__(self, store: Optional[SQLiteStore] = None, job_store: Any = None) -> None:
        self.store = store or SQLiteStore()
        self.job_store = job_store

    def save_recipe(self, name: str, template: str, blocks: list[dict[str, Any]], recipe_id: Optional[str] = None, views: Optional[list[dict[str, Any]]] = None) -> dict[str, Any]:
        if not name.strip() or not blocks:
            raise ReportError("REPORT_RECIPE_INVALID", "Recipe name and at least one block are required.")
        if template not in {**TEMPLATE_DEFAULTS, "custom": {}}:
            raise ReportError("REPORT_TEMPLATE_NOT_FOUND", f"Unknown report template: {template}.", 404)
        normalized = []
        for index, block in enumerate(blocks):
            kind = block.get("kind")
            if kind not in {"artifact", "narrative", "note"}:
                raise ReportError("REPORT_BLOCK_INVALID", f"Block {index + 1} has an unsupported kind.")
            reference = block.get("reference")
            if kind in {"artifact", "note"} and (not isinstance(reference, dict) or not reference.get("type") or not reference.get("id")):
                raise ReportError("REPORT_REFERENCE_REQUIRED", f"Block {index + 1} requires an artifact reference.")
            if "data" in block or "result" in block:
                raise ReportError("REPORT_EMBEDDED_DATA_FORBIDDEN", "Recipes may reference artifacts but cannot copy result data.")
            normalized.append({
                "block_id": block.get("block_id") or f"block_{index + 1}",
                "kind": kind,
                "title": str(block.get("title") or "").strip(),
                "reference": reference,
                "metric_paths": list(block.get("metric_paths") or []),
                "text": str(block.get("text") or ""),
                "citations": list(block.get("citations") or []),
                "layout": dict(block.get("layout") or {}),
            })
        identifier = recipe_id or f"recipe_{uuid.uuid4().hex[:16]}"
        current = self.store.maybe_get(RECIPES, identifier)
        if current is None and self.store.count(RECIPES) >= get_quota("STUDIO_MAX_REPORT_RECIPES"):
            raise ReportError("REPORT_QUOTA_EXCEEDED", "Saved output recipe quota exceeded.", 429)
        saved_views = self._normalize_views(views) if views is not None else list((current or {}).get("views") or [])
        return self.store.put(RECIPES, identifier, {
            "recipe_id": identifier, "name": name.strip(), "template": template,
            "blocks": normalized, "views": saved_views,
        }, create_only=current is None, expected_version=current.get("_revision") if current else None)

    @staticmethod
    def _normalize_views(views: list[dict[str, Any]]) -> list[dict[str, Any]]:
        normalized = []
        for index, view in enumerate(views):
            if not isinstance(view, dict) or not str(view.get("name") or "").strip():
                raise ReportError("REPORT_VIEW_INVALID", f"Saved view {index + 1} requires a name.")
            layouts = view.get("layouts") or {}
            if not isinstance(layouts, dict) or not layouts:
                raise ReportError("REPORT_VIEW_INVALID", f"Saved view {index + 1} requires at least one block layout.")
            clean_layouts = {}
            for block_id, layout in layouts.items():
                if not isinstance(layout, dict):
                    raise ReportError("REPORT_VIEW_INVALID", f"Saved view {index + 1} has an invalid layout for block {block_id}.")
                clean_layouts[str(block_id)] = {
                    key: layout[key] for key in ("x", "y", "w", "h") if key in layout
                } or {"w": layout.get("w", 12)}
            normalized.append({
                "view_id": view.get("view_id") or f"view_{uuid.uuid4().hex[:8]}",
                "name": str(view["name"]).strip(),
                "layouts": clean_layouts,
            })
            if len(normalized) >= 20:
                break
        return normalized

    def save_view(self, recipe_id: str, name: str, layouts: dict[str, dict[str, Any]], view_id: Optional[str] = None) -> dict[str, Any]:
        recipe = self.get_recipe(recipe_id)
        views = list(recipe.get("views") or [])
        if view_id:
            views = [view for view in views if view.get("view_id") != view_id]
        else:
            view_id = f"view_{uuid.uuid4().hex[:8]}"
        normalized = self._normalize_views([{"view_id": view_id, "name": name, "layouts": layouts}])
        views.extend(normalized)
        return self.store.put(RECIPES, recipe_id, {**recipe, "views": views[:20]}, expected_version=recipe.get("_revision"))

    def get_recipe(self, recipe_id: str) -> dict[str, Any]:
        try:
            return self.store.get(RECIPES, recipe_id)
        except KeyError as exc:
            raise ReportError("REPORT_RECIPE_NOT_FOUND", "Output recipe not found.", 404) from exc

    def list_recipes(self) -> list[dict[str, Any]]:
        return self.store.list(RECIPES, limit=200)

    def save_note(self, title: str, content: str, reference: dict[str, str], note_id: Optional[str] = None) -> dict[str, Any]:
        if not title.strip() or not isinstance(content, str):
            raise ReportError("REPORT_NOTE_INVALID", "Note title and text content are required.")
        self.resolve(reference)
        identifier = note_id or f"note_{uuid.uuid4().hex[:16]}"
        current = self.store.maybe_get(NOTES, identifier)
        if current is None and self.store.count(NOTES) >= get_quota("STUDIO_MAX_RESEARCH_NOTES"):
            raise ReportError("REPORT_QUOTA_EXCEEDED", "Research note quota exceeded.", 429)
        return self.store.put(NOTES, identifier, {
            "note_id": identifier, "title": title.strip(), "content": content, "reference": reference,
        }, create_only=current is None, expected_version=current.get("_revision") if current else None)

    def list_notes(self) -> list[dict[str, Any]]:
        return self.store.list(NOTES, limit=500)

    def resolve(self, reference: dict[str, str]) -> dict[str, Any]:
        kind, identifier = reference.get("type"), reference.get("id")
        namespaces = {
            "portfolio_version": "studio_portfolio_versions",
            "paper_deployment": "studio_paper_deployments",
            "paper_event": "studio_paper_events",
            "research_note": NOTES,
        }
        if kind == "validation_job":
            record = self.job_store.get(identifier) if self.job_store else None
            if record is None:
                raise ReportError("REPORT_ARTIFACT_NOT_FOUND", "Referenced validation job was not found.", 404)
            return record
        namespace = namespaces.get(kind)
        if not namespace:
            raise ReportError("REPORT_REFERENCE_INVALID", f"Unsupported artifact reference type: {kind}.")
        try:
            return self.store.get(namespace, identifier)
        except KeyError as exc:
            raise ReportError("REPORT_ARTIFACT_NOT_FOUND", "Referenced artifact was not found.", 404) from exc

    @staticmethod
    def _path(value: Any, path: str) -> Any:
        current = value
        for part in path.split("."):
            if isinstance(current, dict) and part in current:
                current = current[part]
            else:
                return None
        return current

    @staticmethod
    def _artifact_warnings(block_id: str, artifact: Any) -> list[dict[str, str]]:
        found: list[dict[str, str]] = []
        if isinstance(artifact, dict):
            direct = artifact.get("warnings")
            if isinstance(direct, list):
                found.extend({"block_id": block_id, "warning": str(item)} for item in direct)
            nested = artifact.get("portfolio")
            if isinstance(nested, dict) and isinstance(nested.get("warnings"), list):
                found.extend({"block_id": block_id, "warning": str(item)} for item in nested["warnings"])
        return found

    def render(self, recipe_id: str) -> dict[str, Any]:
        recipe = self.get_recipe(recipe_id)
        rendered = []
        report_warnings: list[dict[str, str]] = []
        requested_paths: list[str] = []
        for block in recipe["blocks"]:
            artifact = self.resolve(block["reference"]) if block.get("reference") else None
            metrics = {path: self._path(artifact, path) for path in block.get("metric_paths", [])}
            for path in block.get("metric_paths", []):
                if path not in requested_paths:
                    requested_paths.append(path)
            formulas = {path: FORMULAS[path] for path in block.get("metric_paths", []) if path in FORMULAS}
            report_warnings.extend(self._artifact_warnings(block["block_id"], artifact))
            rendered.append({**block, "resolved": {
                "reference": block.get("reference"), "metrics": metrics, "formulas": formulas,
                "artifact_hash": hashlib.sha256(json.dumps(artifact, sort_keys=True, separators=(",", ":"), default=str).encode()).hexdigest() if artifact is not None else None,
            }})
        required = list(TEMPLATE_REQUIRED_PATHS.get(recipe.get("template", "custom"), []))
        missing = [path for path in required if path not in requested_paths]
        for path in missing:
            report_warnings.append({
                "block_id": "",
                "warning": f"Template '{recipe.get('template')}' recommends metric path '{path}', which no block requests.",
            })
        body = {
            "recipe_id": recipe_id, "name": recipe["name"], "template": recipe["template"],
            "blocks": rendered, "views": list(recipe.get("views") or []),
            "export_version": REPORT_CONTRACT_VERSION, "engine_version": REPORT_ENGINE_VERSION,
            "formulas": {path: FORMULAS[path] for path in requested_paths if path in FORMULAS},
            "warnings": report_warnings,
            "policy": {"template": recipe.get("template"), "required_paths": required, "missing_required_paths": missing},
        }
        body["report_hash"] = hashlib.sha256(json.dumps(body, sort_keys=True, separators=(",", ":"), default=str).encode()).hexdigest()
        return body

    def export_json(self, recipe_id: str) -> bytes:
        return (json.dumps(self.render(recipe_id), sort_keys=True, indent=2, default=str) + "\n").encode()

    def export_csv(self, recipe_id: str) -> bytes:
        report = self.render(recipe_id)
        output = io.StringIO(); writer = csv.writer(output)
        writer.writerow(["block_id", "title", "reference_type", "reference_id", "metric", "value", "formula", "artifact_hash", "report_hash", "export_version"])
        for block in report["blocks"]:
            ref, resolved = block.get("reference") or {}, block["resolved"]
            metrics = resolved["metrics"] or {"": ""}
            for metric, value in metrics.items():
                writer.writerow([block["block_id"], block["title"], ref.get("type", ""), ref.get("id", ""), metric, json.dumps(value, sort_keys=True, default=str) if isinstance(value, (dict, list)) else value, resolved.get("formulas", {}).get(metric, ""), resolved["artifact_hash"] or "", report["report_hash"], report["export_version"]])
        return output.getvalue().encode()

    def export_arrow(self, recipe_id: str) -> bytes:
        """Minimal Arrow IPC stream export via the existing pyarrow dependency."""
        import pyarrow as pa
        import pyarrow.ipc as ipc

        report = self.render(recipe_id)
        columns: dict[str, list[Any]] = {
            "block_id": [], "title": [], "reference_type": [], "reference_id": [],
            "metric": [], "value_json": [], "formula": [], "artifact_hash": [],
            "report_hash": [], "export_version": [],
        }
        for block in report["blocks"]:
            ref, resolved = block.get("reference") or {}, block["resolved"]
            metrics = resolved["metrics"] or {"": None}
            for metric, value in metrics.items():
                columns["block_id"].append(block["block_id"])
                columns["title"].append(block["title"])
                columns["reference_type"].append(ref.get("type", ""))
                columns["reference_id"].append(ref.get("id", ""))
                columns["metric"].append(metric)
                columns["value_json"].append(json.dumps(value, sort_keys=True, default=str))
                columns["formula"].append(resolved.get("formulas", {}).get(metric, ""))
                columns["artifact_hash"].append(resolved["artifact_hash"] or "")
                columns["report_hash"].append(report["report_hash"])
                columns["export_version"].append(report["export_version"])
        table = pa.table({key: pa.array(values, type=pa.string()) for key, values in columns.items()})
        sink = pa.BufferOutputStream()
        with ipc.new_stream(sink, table.schema) as writer:
            writer.write_table(table)
        return bytes(sink.getvalue().to_pybytes())

    def export_html(self, recipe_id: str) -> bytes:
        report = self.render(recipe_id)
        sections = []
        for block in report["blocks"]:
            metrics = "".join(f"<tr><th scope='row'>{html.escape(path)}</th><td>{html.escape(str(value))}</td><td>{html.escape(block['resolved'].get('formulas', {}).get(path, ''))}</td></tr>" for path, value in block["resolved"]["metrics"].items())
            citations = "".join(f"<li>{html.escape(str(item))}</li>" for item in block.get("citations", []))
            sections.append(f"<section><h2>{html.escape(block['title'] or block['kind'])}</h2><p>{html.escape(block.get('text', ''))}</p><table><thead><tr><th scope='col'>Metric</th><th scope='col'>Value</th><th scope='col'>Formula</th></tr></thead><tbody>{metrics}</tbody></table><ul>{citations}</ul><small>Artifact {html.escape(str(block['resolved']['reference']))} · hash {block['resolved']['artifact_hash'] or 'none'}</small></section>")
        warnings = "".join(f"<li>{html.escape(item['warning'])}</li>" for item in report.get("warnings", []))
        formulas = "".join(f"<tr><th scope='row'>{html.escape(path)}</th><td>{html.escape(formula)}</td></tr>" for path, formula in report.get("formulas", {}).items())
        document = f"<!doctype html><html lang='en'><meta charset='utf-8'><meta name='viewport' content='width=device-width'><title>{html.escape(report['name'])}</title><style>body{{max-width:960px;margin:40px auto;padding:0 24px;font:16px/1.5 system-ui;color:#172033}}section{{border-top:1px solid #ccd2dc;padding:24px 0}}table{{border-collapse:collapse;width:100%}}th,td{{padding:8px;text-align:left;border-bottom:1px solid #e5e7eb}}small{{color:#5b6472}}</style><style media='print'>body{{margin:0;max-width:none}}section{{break-inside:avoid}}.no-print{{display:none}}</style><main><h1>{html.escape(report['name'])}</h1><p class='no-print'>Use the browser Print dialog and Save as PDF for the PDF asset.</p>{''.join(sections)}<section><h2>Warnings</h2><ul>{warnings or '<li>None</li>'}</ul></section><section><h2>Formulas</h2><table><tbody>{formulas or '<tr><td>No registered formulas for the requested paths.</td></tr>'}</tbody></table></section><footer>Report hash {report['report_hash']} · export version {report['export_version']} · engine {report['engine_version']}</footer></main></html>"
        return document.encode()
