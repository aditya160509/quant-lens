"""Built-in historical crisis windows and replay persistence."""

from __future__ import annotations

import uuid
from dataclasses import asdict, dataclass
from typing import Any, Optional


from ..algorithm_lab.repository import StrategyRepository
from ..shared.persistence import SQLiteStore
from .engine import EventDrivenEngine, SimulationConfig
from .metrics import PerformanceMetrics


@dataclass(frozen=True)
class Scenario:
    id: str
    name: str
    description: str
    start_date: str
    end_date: str
    events: list[str]


SCENARIOS = (
    Scenario("gfc_2008", "2008 Global Financial Crisis", "Lehman failure, TARP, and the March market bottom.", "2008-09-01", "2009-03-31", ["Lehman bankruptcy", "TARP signed", "S&P market bottom"]),
    Scenario("covid_2020", "March 2020 COVID Crash", "Pandemic declaration, circuit breakers, and emergency monetary policy.", "2020-02-15", "2020-04-30", ["Pandemic declaration", "Circuit breakers", "Federal Reserve emergency actions"]),
    Scenario("rate_hike_2022", "2022 Rate-Hike Drawdown", "Inflation shock, policy tightening, and US-dollar strength.", "2022-01-01", "2022-10-31", ["First rate hike", "Inflation peak", "US-dollar strength"]),
    Scenario("china_deval_2015", "2015 China Devaluation", "Renminbi devaluation and global growth scare.", "2015-08-01", "2016-02-29", ["PBOC devaluation", "Commodity drawdown", "China growth scare"]),
    Scenario("dotcom_2000", "Dot-Com Drawdown", "Technology unwind, 9/11, and accounting scandals.", "2000-03-01", "2002-10-31", ["Nasdaq peak", "9/11", "Accounting scandals"]),
)


class ScenarioReplay:
    def __init__(
        self,
        store: Optional[SQLiteStore] = None,
        strategies: Optional[StrategyRepository] = None,
    ) -> None:
        self.store = store or SQLiteStore()
        self.strategies = strategies or StrategyRepository(self.store)

    def list_scenarios(self) -> list[dict[str, Any]]:
        return [asdict(item) for item in SCENARIOS]

    def replay(
        self,
        strategy_id: str,
        scenario_id: str,
        config: Optional[dict[str, Any]] = None,
    ) -> dict[str, Any]:
        scenario = next((item for item in SCENARIOS if item.id == scenario_id), None)
        if scenario is None:
            raise KeyError(f"scenario '{scenario_id}' not found")
        strategy = self.strategies.get(strategy_id)
        request = dict(config or {})
        request.update(
            {
                "strategy_source": strategy["file_path"],
                "date_start": scenario.start_date,
                "date_end": scenario.end_date,
            }
        )
        result = EventDrivenEngine().run(SimulationConfig(**request))
        if result.daily_returns.empty:
            raise ValueError(result.warnings[0] if result.warnings else "scenario replay returned no observations")
        metrics = PerformanceMetrics().compute_all(result.daily_returns).to_dict()
        nav = result.daily_nav
        peak = nav.cummax()
        drawdown = nav / peak - 1.0
        trough = drawdown.idxmin()
        prior_peak = peak.loc[:trough].iloc[-1]
        recovery = nav.loc[trough:]
        recovered = recovery.loc[recovery >= prior_peak]
        recovery_days = int((recovered.index[0] - trough).days) if not recovered.empty else None
        run_id = f"run_scenario_{uuid.uuid4().hex[:12]}"
        payload = {
            "run_id": run_id,
            "scenario_id": scenario_id,
            "strategy_id": strategy_id,
            "equity_curve": result.daily_nav.to_dict(),
            "max_drawdown_pct": float(drawdown.min() * 100.0),
            "recovery_days": recovery_days,
            "metrics": metrics,
            "warnings": result.warnings,
        }
        return self.store.put("scenario_results", run_id, payload, create_only=True)

    def get_result(self, run_id: str) -> dict[str, Any]:
        return self.store.get("scenario_results", run_id)
