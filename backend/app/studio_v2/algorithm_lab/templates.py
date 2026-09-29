"""Curated, executable strategy templates and fork orchestration."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Optional

from .kernel import KernelGateway
from .repository import StrategyRepository


@dataclass(frozen=True)
class Template:
    id: str
    name: str
    family: str
    complexity: str
    universe_type: str
    description: str
    source_path: str
    default_config: dict[str, Any]


_INDEX = (
    Template("cross_sectional_momentum", "Cross-Sectional Momentum", "momentum", "intermediate", "equity", "Ranks securities by trailing return and forms a dollar-neutral long-short portfolio.", "cross_sectional_momentum.py", {"lookback": 252, "skip": 21, "top_pct": 0.10, "bottom_pct": 0.10}),
    Template("time_series_momentum", "Time-Series Momentum", "momentum", "beginner", "multi_asset", "Trades each instrument in the direction of its own volatility-scaled trend.", "time_series_momentum.py", {"lookback": 126, "vol_window": 42, "target_vol": 0.12}),
    Template("pairs_mean_reversion", "Pairs Mean Reversion", "mean_reversion", "intermediate", "equity_pair", "Estimates a rolling hedge ratio and trades standardized spread dislocations.", "pairs_mean_reversion.py", {"lookback": 60, "entry_z": 2.0, "exit_z": 0.5}),
    Template("single_name_mean_reversion", "Cross-Sectional Mean Reversion", "mean_reversion", "beginner", "equity", "Trades short-horizon idiosyncratic reversals with daily dollar neutrality.", "single_name_mean_reversion.py", {"lookback": 20, "entry_z": 1.5}),
    Template("statistical_arbitrage", "PCA Statistical Arbitrage", "statistical_arbitrage", "advanced", "equity", "Extracts common components with rolling singular-value decomposition and trades residuals.", "statistical_arbitrage.py", {"lookback": 60, "components": 3, "entry_z": 1.5}),
    Template("volatility_carry", "Volatility Carry", "volatility", "advanced", "multi_asset", "Uses the realized-volatility term structure as a transparent carry proxy.", "volatility_carry.py", {"fast_window": 10, "slow_window": 63, "vol_target": 0.10}),
    Template("factor_tilt", "Composite Factor Tilt", "factor", "intermediate", "equity", "Combines momentum with optional point-in-time fundamentals into a neutral tilt.", "factor_tilt.py", {"momentum_lookback": 126, "top_pct": 0.20}),
)


class TemplateRepository:
    def __init__(
        self,
        kernel: Optional[KernelGateway] = None,
        strategies: Optional[StrategyRepository] = None,
        template_root: Optional[str | Path] = None,
    ) -> None:
        self.kernel = kernel or KernelGateway()
        self.strategies = strategies or StrategyRepository()
        self.template_root = Path(template_root) if template_root else Path(__file__).resolve().parents[1] / "data" / "templates"

    def list_templates(
        self,
        family: Optional[str] = None,
        complexity: Optional[str] = None,
    ) -> list[dict[str, Any]]:
        rows = _INDEX
        if family:
            rows = tuple(item for item in rows if item.family == family)
        if complexity:
            rows = tuple(item for item in rows if item.complexity == complexity)
        return [{key: value for key, value in asdict(item).items() if key != "source_path"} for item in rows]

    def get_template(self, template_id: str) -> dict[str, Any]:
        template = next((item for item in _INDEX if item.id == template_id), None)
        if template is None:
            raise KeyError(f"template '{template_id}' not found")
        source_path = self.template_root / template.source_path
        source_code = source_path.read_text(encoding="utf-8")
        metadata = {key: value for key, value in asdict(template).items() if key not in {"source_path", "default_config"}}
        return {
            **metadata,
            "source_code": source_code,
            "default_config": dict(template.default_config),
            "metadata": metadata,
        }

    def fork_template(
        self,
        template_id: str,
        session_name: Optional[str] = None,
    ) -> dict[str, Any]:
        template = self.get_template(template_id)
        strategy = self.strategies.create(
            session_name or template["name"],
            template["source_code"],
            default_config=template["default_config"],
            metadata={"template_id": template_id, **template["metadata"]},
        )
        session_id = f"sess_{strategy['strategy_id'].removeprefix('strat_')}"
        self.kernel.start_session(
            session_id,
            {
                "strategy_id": strategy["strategy_id"],
                "strategy_config": template["default_config"],
            },
        )
        return {
            "session_id": session_id,
            "strategy_id": strategy["strategy_id"],
            "file_path": strategy["file_path"],
            "source_code": template["source_code"],
            "default_config": template["default_config"],
            "editor_state": {"language": "python", "content": template["source_code"]},
        }
