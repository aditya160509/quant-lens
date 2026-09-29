from __future__ import annotations

"""
Composite Robustness Score and PDF Report (F3.9).

Weighted composite: Parameter Stability 30%, Timing 20%,
Cost Break-Even 25%, Capacity 25%. Generates reportlab PDF.
"""

import io
from dataclasses import asdict, dataclass
from typing import Any, Dict

import numpy as np


@dataclass
class CompositeScore:
    score: float
    component_scores: Dict[str, float]
    verdict: str
    diagnoses: Dict[str, str]

    def to_dict(self) -> dict: return asdict(self)


class CompositeRobustnessScorer:
    weights = {"parameter_stability": 0.30, "timing": 0.20, "cost": 0.25, "capacity": 0.25}

    def normalize_test_score(self, raw_value: Any, test_type: str) -> float:
        try: value = float(raw_value)
        except (TypeError, ValueError): return 0.0
        if not np.isfinite(value): return 1.0 if value == float("inf") else 0.0
        kind = str(test_type).lower()
        if kind in {"parameter", "parameter_stability", "timing", "noise", "universe"}: return float(np.clip(value, 0.0, 1.0))
        return float(np.clip(value, 0.0, 1.0))

    def get_verdict(self, composite: float) -> str:
        return "Robust" if composite >= 75 else ("Marginal" if composite >= 50 else "Do not advance")

    def compute_composite_score(self, core_results: Dict[str, Any]) -> CompositeScore:
        values = {}
        for name in self.weights:
            raw = core_results.get(name, 0.0) if isinstance(core_results, dict) else 0.0
            if isinstance(raw, dict): raw = raw.get("score", raw.get("stability_score", raw.get("robustness_score", raw.get("sensitivity_score", raw.get("capacity_ceiling", 0.0)))))
            values[name] = self.normalize_test_score(raw, name)
        score = 100.0 * sum(self.weights[name] * values[name] for name in self.weights)
        diagnoses = {name: self._generate_diagnosis(name, component) for name, component in values.items() if component < 0.60}
        return CompositeScore(score, values, self.get_verdict(score), diagnoses)

    def _generate_diagnosis(self, test_name: str, score: float) -> str:
        if score >= 0.60: return f"{test_name} is within the acceptable robustness range."
        messages = {"parameter_stability": "Performance is hypersensitive to parameter values; broaden the stable region.", "timing": "Performance depends on precise entry timing; test signal timing and execution assumptions.", "cost": "The cost break-even is below the realistic band; reduce turnover or improve the edge.", "capacity": "Capacity is constrained; validate liquidity assumptions and position sizing."}
        return messages.get(test_name, f"{test_name} failed its robustness gate.")


class RobustnessReport:
    def _element(self, text: str, style: str = "BodyText") -> Any:
        try:
            from reportlab.lib.styles import getSampleStyleSheet
            from reportlab.platypus import Paragraph
            return Paragraph(str(text), getSampleStyleSheet()[style])
        except ImportError:
            return str(text)

    def generate_pdf(self, composite: CompositeScore, extended: Any = None, capacity: Any = None, charts: Any = None) -> bytes:
        try:
            from reportlab.lib.pagesizes import letter
            from reportlab.lib.styles import getSampleStyleSheet
            from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table
            buffer = io.BytesIO(); document = SimpleDocTemplate(buffer, pagesize=letter); styles = getSampleStyleSheet(); story = [Paragraph("QUANT360 Robustness Report", styles["Title"]), Spacer(1, 12), Paragraph(f"Composite score: {composite.score:.1f}/100 ({composite.verdict})", styles["Heading2"])]
            story.append(Table([["Test", "Score", "Diagnosis"]] + [[name, f"{score:.3f}", composite.diagnoses.get(name, "Pass")] for name, score in composite.component_scores.items()]))
            if capacity is not None: story.extend([Spacer(1, 12), Paragraph(f"Capacity ceiling: {getattr(capacity, 'capacity_ceiling', capacity)}", styles["BodyText"])])
            document.build(story); return buffer.getvalue()
        except ImportError:
            payload = {"title": "QUANT360 Robustness Report", "composite": composite.to_dict(), "extended": extended, "capacity": capacity}
            return (str(payload)).encode("utf-8")

    def _build_title_page(self, doc: Any, run_info: dict) -> None:
        doc.append(self._element(f"QUANT360 Robustness Report: {run_info.get('run_id', 'unknown')}", "Title"))

    def _build_executive_summary(self, doc: Any, composite: CompositeScore, capacity: Any) -> None:
        doc.append(self._element(f"Composite: {composite.score:.1f}, verdict: {composite.verdict}", "Heading2"))

    def _build_test_page(self, doc: Any, test_name: str, score: float, chart: Any, diagnosis: str) -> None:
        try:
            from reportlab.platypus import Table
            doc.append(Table([["Test", "Score", "Diagnosis"], [test_name, f"{score:.3f}", diagnosis]]))
        except ImportError:
            doc.append({"test": test_name, "score": score, "diagnosis": diagnosis})

    def _build_diagnosis_section(self, doc: Any, diagnoses: dict) -> None:
        for name, diagnosis in diagnoses.items():
            doc.append(self._element(f"{name}: {diagnosis}"))

    def _generate_diagnosis(self, test_name: str, score: float) -> str:
        return CompositeRobustnessScorer()._generate_diagnosis(test_name, score)


def format_performance_metric(value: Any, metric_type: str) -> str:
    try: number = float(value)
    except (TypeError, ValueError): return "nan"
    if not np.isfinite(number): return "∞" if number > 0 else "nan"
    decimals = 2 if str(metric_type).lower() in {"drawdown", "max_drawdown"} else 3
    return f"{number:.{decimals}f}"
