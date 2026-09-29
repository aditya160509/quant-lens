"""Complete HTTP surface for the Studio V2 backend."""

from __future__ import annotations

import io
import asyncio
import json
import zipfile
import uuid
from functools import wraps
import logging
import multiprocessing
from dataclasses import asdict, is_dataclass
from typing import Annotated, Any, Literal

import numpy as np
import pandas as pd
from fastapi import (
    APIRouter,
    Body,
    Depends,
    File,
    Form,
    HTTPException,
    Query,
    UploadFile,
    WebSocket,
    WebSocketDisconnect,
)
from fastapi.responses import JSONResponse, StreamingResponse

from ..auth.dependencies import CurrentUser, get_current_user

from .algorithm_lab.collaboration import CollaboratorSession
from .algorithm_lab.compute_budget import ComputeBudget
from .algorithm_lab.exporter import StandaloneExporter
from .algorithm_lab.kernel import KernelGateway
from .algorithm_lab.linter import LookaheadBiasLinter
from .algorithm_lab.portfolio_composer import PortfolioComposer
from .algorithm_lab.repository import StrategyRepository
from .algorithm_lab.snippets import SnippetRepository
from .algorithm_lab.templates import TemplateRepository
from .backtest.attribution import AttributionEngine
from .backtest.engine import EventDrivenEngine, SimulationConfig
from .backtest.lineage import ModelLineage, SearchQuery
from .backtest.portfolio_engine import PortfolioBacktestEngine
from .backtest.repository import BacktestResultRepository
from .backtest.scenarios import ScenarioReplay
from .backtest.slippage_audit import SlippageAuditor
from .data_studio.event_calendar import EventCalendar
from .data_studio.multi_asset import MultiAssetCatalog
from .data_studio.synthetic_flagging import SyntheticRangeDetector
from .factors.governance import FactorGovernance
from .portfolio_risk.alert_feed import AlertFeed
from .portfolio_risk.concentration import ConcentrationEngine
from .portfolio_risk.limits import RiskLimitService
from .portfolio_risk.var_engine import VaREngine
from .robustness.jobs import DurableRobustnessJobService
from .services.journal_service import JournalService
from .shared.data_loader import get_data_access_metrics
from .shared.data_manifest import manifest_snapshot
from .shared.health import StudioHealthService
from .shared.observability import METRICS, current_request_id
from .shared.persistence import SQLiteStore, default_database_path
from .contracts import (
    AdversarialRequest,
    AdversarialResponse,
    AlgorithmLabResponse,
    AlertAckRequest,
    AttributionResponse,
    AuditTrailRequest,
    BacktestCompareRequest,
    BacktestExportRequest,
    BacktestRunRequest,
    CompositionCreateRequest,
    CompositionExecuteRequest,
    BacktestResponse,
    DataStudioResponse,
    CustomUploadMetadataRequest,
    CustomUploadResponse,
    DataUniverseBuildRequest,
    DatasetManifestResponse,
    ErrorResponse,
    ExecuteCodeRequest,
    PaperTradeRequest,
    PushToBacktestRequest,
    FactorEvaluateRequest,
    FactorICDiagnosticsRequest,
    FactorLibraryCreateRequest,
    FactorLibraryUpdateRequest,
    FactorResponse,
    FuturesUniverseRequest,
    MultiAssetUniverseResponse,
    MissingDataHeatmapResponse,
    ManifestRefreshRequest,
    ManifestRefreshResponse,
    GovernanceTransitionRequest,
    InviteRequest,
    JournalEntryRequest,
    JournalEntryResponse,
    JournalPatchRequest,
    OptimizerCrossValidationRequest,
    OptimizerCrossValidationResponse,
    OptimizerCPCVRequest,
    OptimizerCPCVResponse,
    OptimizerEnsembleRequest,
    OptimizerEnsembleResponse,
    OptimizerSearchRequest,
    OptimizerResponse,
    OptimizerStudyResponse,
    OptimizerStudySummaryResponse,
    OptimizerTrialResponse,
    OptimizerWalkForwardRequest,
    OptimizerWalkForwardResponse,
    OperationResponse,
    PortfolioRunRequest,
    PortfolioRunResponse,
    PortfolioRiskResponse,
    RiskLimitRequest,
    RobustnessCoreRequest,
    RobustnessCoreResponse,
    RobustnessExtendedRequest,
    RobustnessExtendedResponse,
    RobustnessJobCreateRequest,
    RobustnessJobResultResponse,
    RobustnessJobStatusResponse,
    CompositeRobustnessResponse,
    RobustnessResponse,
    SnippetCreateRequest,
    SnippetPatchRequest,
    StudioLivenessResponse,
    StudioOperationalMetricsResponse,
    StudioReadinessResponse,
    TemplateForkRequest,
)

logger = logging.getLogger(__name__)


def _jsonable(value: Any) -> Any:
    if is_dataclass(value):
        return _jsonable(asdict(value))
    if isinstance(value, pd.DataFrame):
        clean = value.replace([np.inf, -np.inf], np.nan)
        return [{str(key): _jsonable(item) for key, item in row.items()} for row in clean.to_dict(orient="records")]
    if isinstance(value, pd.Series):
        return {str(key): _jsonable(item) for key, item in value.replace([np.inf, -np.inf], np.nan).items()}
    if isinstance(value, dict):
        return {str(key): _jsonable(item) for key, item in value.items()}
    if isinstance(value, (list, tuple, set, np.ndarray)):
        return [_jsonable(item) for item in list(value)]
    if isinstance(value, np.generic):
        value = value.item()
    if isinstance(value, float) and not np.isfinite(value):
        return None
    if isinstance(value, (pd.Timestamp, np.datetime64)):
        return pd.Timestamp(value).isoformat()
    return value


def _body(value: Any) -> dict[str, Any]:
    return value.model_dump(exclude_none=True, exclude_unset=True) if hasattr(value, "model_dump") else dict(value)


_RESPONSE_MODELS: dict[tuple[str, str], Any] = {
    ("POST", "/api/v2/backtest/portfolio-run"): PortfolioRunResponse,
    ("GET", "/api/v2/backtest/attribution/{run_id}"): AttributionResponse,
    ("POST", "/api/v2/robustness/run-core-tests"): RobustnessCoreResponse,
    ("POST", "/api/v2/robustness/run-extended"): RobustnessExtendedResponse,
    ("GET", "/api/v2/robustness/composite-score"): CompositeRobustnessResponse,
    ("POST", "/api/v2/robustness/jobs"): RobustnessJobStatusResponse,
    ("GET", "/api/v2/robustness/jobs/{job_id}"): RobustnessJobStatusResponse,
    ("POST", "/api/v2/robustness/jobs/{job_id}/cancel"): RobustnessJobStatusResponse,
    ("GET", "/api/v2/robustness/jobs/{job_id}/result"): RobustnessJobResultResponse,
    ("POST", "/api/v2/robustness/adversarial"): AdversarialResponse,
    ("POST", "/api/v2/optimizer/ensemble"): OptimizerEnsembleResponse,
    ("POST", "/api/v2/optimizer/cross-validate"): OptimizerCrossValidationResponse,
    ("POST", "/api/v2/optimizer/cpcv"): OptimizerCPCVResponse,
    ("POST", "/api/v2/optimizer/walk-forward"): OptimizerWalkForwardResponse,
    ("GET", "/api/v2/optimizer/studies/{study_id}"): OptimizerStudyResponse,
    ("POST", "/api/v2/data-studio/universes/futures"): MultiAssetUniverseResponse,
    ("GET", "/api/v2/data-studio/universes/crypto"): MultiAssetUniverseResponse,
    ("GET", "/api/v2/data-studio/universes/fx"): MultiAssetUniverseResponse,
    ("GET", "/api/v2/data-studio/explorer/heatmap"): MissingDataHeatmapResponse,
    ("POST", "/api/v2/data-studio/upload"): CustomUploadResponse,
    ("POST", "/api/v2/data-studio/manifests/refresh"): ManifestRefreshResponse,
    ("GET", "/api/v2/journal"): list[JournalEntryResponse],
    ("POST", "/api/v2/journal"): JournalEntryResponse,
    ("PUT", "/api/v2/journal/{entry_id}"): JournalEntryResponse,
    ("GET", "/api/v2/health/live"): StudioLivenessResponse,
    ("GET", "/api/v2/health/ready"): StudioReadinessResponse,
    ("GET", "/api/v2/health/metrics"): StudioOperationalMetricsResponse,
}

_LIST_RESPONSE_MODELS: dict[str, Any] = {
    "/api/v2/algorithm-lab/templates": list[AlgorithmLabResponse],
    "/api/v2/algorithm-lab/strategies": list[AlgorithmLabResponse],
    "/api/v2/algorithm-lab/session/{session_id}/participants": list[AlgorithmLabResponse],
    "/api/v2/algorithm-lab/snippets": list[AlgorithmLabResponse],
    "/api/v2/backtest/scenarios": list[BacktestResponse],
    "/api/v2/backtest/lineage/search": list[BacktestResponse],
    "/api/v2/factors/library/{id}/versions": list[FactorResponse],
    "/api/v2/factors/library/{id}/changelog": list[FactorResponse],
    "/api/v2/factors/library": list[FactorResponse],
    "/api/v2/optimizer/trials": list[OptimizerTrialResponse],
    "/api/v2/optimizer/studies": list[OptimizerStudySummaryResponse],
    "/api/v2/data-studio/asset-classes": list[DataStudioResponse],
    "/api/v2/data-studio/catalog": list[DataStudioResponse],
    "/api/v2/data-studio/freshness": list[DataStudioResponse],
    "/api/v2/data-studio/explorer/anomalies": list[DataStudioResponse],
    "/api/v2/data-studio/events/{ticker}": list[DataStudioResponse],
    "/api/v2/portfolio-risk/active-strategies": list[PortfolioRiskResponse],
    "/api/v2/portfolio-risk/limits": list[PortfolioRiskResponse],
    "/api/v2/portfolio-risk/alerts": list[PortfolioRiskResponse],
    "/api/v2/journal/tags": list[str],
}


def _response_model_for(method: str, path: str) -> Any:
    explicit = _RESPONSE_MODELS.get((method, path))
    if explicit is not None:
        return explicit
    if method == "GET" and path in _LIST_RESPONSE_MODELS:
        return _LIST_RESPONSE_MODELS[path]
    if path == "/api/v2/data-studio/manifests":
        return DatasetManifestResponse
    if path.startswith("/api/v2/algorithm-lab/"):
        return AlgorithmLabResponse
    if path.startswith("/api/v2/backtest/"):
        return BacktestResponse
    if path.startswith("/api/v2/robustness/"):
        return RobustnessResponse
    if path.startswith("/api/v2/factors/"):
        return FactorResponse
    if path.startswith("/api/v2/optimizer/"):
        return OptimizerResponse
    if path.startswith("/api/v2/data-studio/"):
        return DataStudioResponse
    if path.startswith("/api/v2/portfolio-risk/"):
        return PortfolioRiskResponse
    if path.startswith("/api/v2/journal/"):
        return OperationResponse
    raise KeyError(f"No response model registered for {method} {path}")


def _error_detail(code: str, message: str, details: Any = None) -> dict[str, Any]:
    return {
        "code": code,
        "message": message,
        "details": details,
        "request_id": current_request_id(),
    }


def _guarded(handler: Any) -> Any:
    @wraps(handler)
    async def guarded(*args: Any, **kwargs: Any) -> Any:
        try:
            return await handler(*args, **kwargs)
        except HTTPException:
            raise
        except (FileNotFoundError, KeyError) as exc:
            raise HTTPException(404, detail=_error_detail("not_found", str(exc))) from exc
        except PermissionError as exc:
            raise HTTPException(403, detail=_error_detail("forbidden", str(exc))) from exc
        except ValueError as exc:
            raise HTTPException(422, detail=_error_detail("invalid_request", str(exc))) from exc
        except RuntimeError as exc:
            raise HTTPException(409, detail=_error_detail("conflict", str(exc))) from exc
        except Exception as exc:
            logger.exception("Unhandled Studio V2 API failure in %s", handler.__name__)
            raise HTTPException(
                500,
                detail=_error_detail("internal_error", "The Studio V2 request failed unexpectedly"),
            ) from exc
    return guarded


_ERROR_RESPONSES = {
    400: {"model": ErrorResponse, "description": "Malformed request"},
    403: {"model": ErrorResponse, "description": "Permission denied"},
    404: {"model": ErrorResponse, "description": "Resource not found"},
    409: {"model": ErrorResponse, "description": "Resource state conflict"},
    422: {"model": ErrorResponse, "description": "Request validation failed"},
    500: {"model": ErrorResponse, "description": "Internal Studio V2 error"},
}
_AUTHENTICATED_RESPONSES = {
    **_ERROR_RESPONSES,
    401: {"model": ErrorResponse, "description": "Authentication required"},
}
_UPLOAD_RESPONSES = {
    **_AUTHENTICATED_RESPONSES,
    413: {"model": ErrorResponse, "description": "Upload or storage quota exceeded"},
}


class Router(APIRouter):
    def __init__(self, *, store: SQLiteStore | None = None, **kwargs: Any) -> None:
        super().__init__(tags=["studio-v2"], **kwargs)
        self.analytics_store = store or SQLiteStore()
        self.kernel = KernelGateway()
        self.strategies = StrategyRepository()
        self.templates = TemplateRepository(self.kernel, self.strategies)
        self.composer = PortfolioComposer(strategies=self.strategies)
        self.collaboration = CollaboratorSession()
        self.compute = ComputeBudget()
        from .algorithm_lab.paper_trader import PaperTrader
        self.paper_trader = PaperTrader()
        self.snippets = SnippetRepository()
        self.results = BacktestResultRepository()
        self.portfolio_engine = PortfolioBacktestEngine(
            self.results, composer=self.composer, strategies=self.strategies
        )
        self.lineage = ModelLineage(str(default_database_path().with_name("lineage.json")))
        self.scenarios = ScenarioReplay(strategies=self.strategies)
        self.linter = LookaheadBiasLinter()
        self.governance = FactorGovernance()
        from .factors.library import FactorLibrary
        from .optimizer.verdict import TrialRegistry
        self.factor_library = FactorLibrary(governance=self.governance)
        self.trial_registry = TrialRegistry(self.analytics_store)
        self.robustness_jobs = DurableRobustnessJobService(
            self.analytics_store, finalizer=self._finalize_robustness_job
        )
        self.events = EventCalendar()
        self.journal = JournalService()
        self.limits = RiskLimitService(strategy_provider=self._active_records)
        self.alerts = AlertFeed()
        self.health = StudioHealthService(self.analytics_store.path)
        self._register_routes()

    def _route(self, path: str, method: str, handler: Any) -> None:
        responses = _ERROR_RESPONSES
        if path == "/api/v2/data-studio/manifests/refresh":
            responses = _AUTHENTICATED_RESPONSES
        elif path == "/api/v2/data-studio/upload":
            responses = _UPLOAD_RESPONSES
        elif path == "/api/v2/health/ready":
            responses = {
                **_ERROR_RESPONSES,
                503: {
                    "model": StudioReadinessResponse,
                    "description": "A required Studio V2 dependency is unavailable",
                },
            }
        self.add_api_route(
            path,
            _guarded(handler),
            methods=[method],
            response_model=_response_model_for(method, path),
            responses=responses,
        )

    def _register_routes(self) -> None:
        route_specs = [
            ("POST", "/api/v2/algorithm-lab/execute", self.execute_code),
            ("POST", "/api/v2/algorithm-lab/paper-trade/run", self.run_paper_trade),
            ("POST", "/api/v2/algorithm-lab/push-to-backtest", self.push_to_backtest),
            ("POST", "/api/v2/algorithm-lab/kernel/restore/{run_id}", self.restore_kernel),
            ("GET", "/api/v2/algorithm-lab/variables", self.variables),
            ("GET", "/api/v2/algorithm-lab/lint", self.lint),
            ("GET", "/api/v2/algorithm-lab/templates", self.list_templates),
            ("GET", "/api/v2/algorithm-lab/strategies", self.list_strategies),
            ("GET", "/api/v2/algorithm-lab/templates/{id}", self.get_template),
            ("POST", "/api/v2/algorithm-lab/templates/{id}/fork", self.fork_template),
            ("POST", "/api/v2/algorithm-lab/compose", self.create_composition),
            ("GET", "/api/v2/algorithm-lab/compose/{id}", self.get_composition),
            ("POST", "/api/v2/algorithm-lab/compose/{id}/execute", self.execute_composition),
            ("POST", "/api/v2/algorithm-lab/export/{strategy_id}", self.export_standalone),
            ("POST", "/api/v2/algorithm-lab/session/{session_id}/invite", self.invite),
            ("GET", "/api/v2/algorithm-lab/session/{session_id}/participants", self.participants),
            ("GET", "/api/v2/algorithm-lab/session/{session_id}/compute-status", self.compute_status),
            ("POST", "/api/v2/algorithm-lab/session/{session_id}/kill/{job_id}", self.kill_job),
            ("POST", "/api/v2/algorithm-lab/session/{session_id}/kill-all", self.kill_all),
            ("GET", "/api/v2/algorithm-lab/snippets", self.list_snippets),
            ("POST", "/api/v2/algorithm-lab/snippets", self.create_snippet),
            ("PUT", "/api/v2/algorithm-lab/snippets/{id}", self.update_snippet),
            ("DELETE", "/api/v2/algorithm-lab/snippets/{id}", self.delete_snippet),
            ("POST", "/api/v2/backtest/run", self.run_backtest),
            ("GET", "/api/v2/backtest/result/{run_id}", self.get_backtest_result),
            ("GET", "/api/v2/backtest/metrics/{run_id}", self.get_metrics),
            ("POST", "/api/v2/backtest/export/{run_id}", self.export_backtest),
            ("POST", "/api/v2/backtest/portfolio-run", self.portfolio_run),
            ("GET", "/api/v2/backtest/portfolio-result/{run_id}", self.get_backtest_result),
            ("GET", "/api/v2/backtest/attribution/{run_id}", self.attribution),
            ("GET", "/api/v2/backtest/slippage-audit/{run_id}", self.slippage_audit),
            ("GET", "/api/v2/backtest/tax-report/{run_id}", self.tax_report),
            ("GET", "/api/v2/backtest/scenarios", self.list_scenarios),
            ("POST", "/api/v2/backtest/scenarios/{scenario_id}/replay/{strategy_id}", self.replay_scenario),
            ("GET", "/api/v2/backtest/scenarios/result/{run_id}", self.scenario_result),
            ("POST", "/api/v2/backtest/compare", self.compare),
            ("GET", "/api/v2/backtest/lineage", self.get_lineage),
            ("GET", "/api/v2/backtest/lineage/search", self.search_lineage),
            ("GET", "/api/v2/backtest/lineage/diff/{run_id_a}/{run_id_b}", self.diff_lineage),
            ("POST", "/api/v2/robustness/run-core-tests", self.robustness_core),
            ("POST", "/api/v2/robustness/run-extended", self.robustness_extended),
            ("GET", "/api/v2/robustness/composite-score", self.robustness_composite),
            ("POST", "/api/v2/robustness/jobs", self.create_robustness_job),
            ("GET", "/api/v2/robustness/jobs/{job_id}", self.robustness_job_status),
            ("POST", "/api/v2/robustness/jobs/{job_id}/cancel", self.cancel_robustness_job),
            ("GET", "/api/v2/robustness/jobs/{job_id}/result", self.robustness_job_result),
            ("POST", "/api/v2/robustness/audit-trail/{strategy_id}", self.audit_trail),
            ("POST", "/api/v2/robustness/adversarial", self.adversarial),
            ("GET", "/api/v2/robustness/adversarial/result/{run_id}", self.adversarial_result),
            ("POST", "/api/v2/factors/evaluate", self.factor_evaluate),
            ("GET", "/api/v2/factors/library", self.list_factor_library),
            ("POST", "/api/v2/factors/library", self.create_factor_library),
            ("GET", "/api/v2/factors/library/{id}", self.get_factor_library),
            ("PUT", "/api/v2/factors/library/{id}", self.update_factor_library),
            ("DELETE", "/api/v2/factors/library/{id}", self.delete_factor_library),
            ("GET", "/api/v2/factors/ic-diagnostics", self.ic_diagnostics),
            ("POST", "/api/v2/factors/ic-diagnostics", self.ic_diagnostics_post),
            ("GET", "/api/v2/factors/library/{id}/versions", self.factor_versions),
            ("POST", "/api/v2/factors/library/{id}/approve", self.factor_approve),
            ("POST", "/api/v2/factors/library/{id}/deprecate", self.factor_deprecate),
            ("POST", "/api/v2/factors/library/{id}/restore", self.factor_restore),
            ("GET", "/api/v2/factors/library/{id}/changelog", self.factor_changelog),
            ("POST", "/api/v2/optimizer/bayesian-search", self.optimizer_search),
            ("POST", "/api/v2/optimizer/ensemble", self.optimizer_ensemble),
            ("POST", "/api/v2/optimizer/cross-validate", self.optimizer_cross_validate),
            ("POST", "/api/v2/optimizer/cpcv", self.optimizer_cpcv),
            ("POST", "/api/v2/optimizer/walk-forward", self.optimizer_walk_forward),
            ("GET", "/api/v2/optimizer/verdict", self.optimizer_verdict),
            ("GET", "/api/v2/optimizer/trials", self.optimizer_trials),
            ("GET", "/api/v2/optimizer/studies", self.optimizer_studies),
            ("GET", "/api/v2/optimizer/studies/{study_id}", self.optimizer_study),
            ("GET", "/api/v2/data-studio/asset-classes", self.asset_classes),
            ("GET", "/api/v2/data-studio/catalog", self.data_catalog),
            ("GET", "/api/v2/data-studio/freshness", self.data_freshness),
            ("GET", "/api/v2/data-studio/explorer/series/{ticker}", self.explorer_series),
            ("GET", "/api/v2/data-studio/explorer/anomalies", self.explorer_anomalies),
            ("GET", "/api/v2/data-studio/explorer/heatmap", self.explorer_heatmap),
            ("POST", "/api/v2/data-studio/universe/build", self.build_universe),
            ("POST", "/api/v2/data-studio/upload", self.upload_custom_data),
            ("GET", "/api/v2/data-studio/uploads", self.list_custom_uploads),
            ("DELETE", "/api/v2/data-studio/uploads/{upload_id}", self.delete_custom_upload),
            ("GET", "/api/v2/data-studio/manifests", self.data_manifests),
            ("POST", "/api/v2/data-studio/manifests/refresh", self.refresh_data_manifest),
            ("POST", "/api/v2/data-studio/universes/futures", self.futures_universe),
            ("GET", "/api/v2/data-studio/universes/crypto", self.crypto_universe),
            ("GET", "/api/v2/data-studio/universes/fx", self.fx_universe),
            ("GET", "/api/v2/data-studio/events/{ticker}", self.ticker_events),
            ("GET", "/api/v2/data-studio/synthetic-ranges/{ticker}", self.synthetic_ranges),
            ("GET", "/api/v2/portfolio-risk/active-strategies", self.active_strategies),
            ("GET", "/api/v2/portfolio-risk/var", self.portfolio_var),
            ("GET", "/api/v2/portfolio-risk/correlation", self.portfolio_correlation),
            ("GET", "/api/v2/portfolio-risk/concentration", self.portfolio_concentration),
            ("GET", "/api/v2/portfolio-risk/limits", self.risk_limits),
            ("PUT", "/api/v2/portfolio-risk/limits", self.update_risk_limits),
            ("GET", "/api/v2/portfolio-risk/limits/breaches", self.risk_breaches),
            ("GET", "/api/v2/portfolio-risk/alerts", self.risk_alerts),
            ("POST", "/api/v2/portfolio-risk/alerts/{alert_id}/ack", self.ack_alert),
            ("GET", "/api/v2/journal", self.journal_list),
            ("POST", "/api/v2/journal", self.journal_create),
            ("PUT", "/api/v2/journal/{entry_id}", self.journal_update),
            ("DELETE", "/api/v2/journal/{entry_id}", self.journal_delete),
            ("GET", "/api/v2/journal/tags", self.journal_tags),
            ("GET", "/api/v2/health/live", self.studio_liveness),
            ("GET", "/api/v2/health/ready", self.studio_readiness),
            ("GET", "/api/v2/health/metrics", self.studio_operational_metrics),
        ]
        for method, path, handler in route_specs:
            self._route(path, method, handler)
        self.add_api_websocket_route(
            "/api/v2/algorithm-lab/session/{session_id}/collaborate", self.collaborate
        )

    def _ensure_session(self, session_id: str) -> None:
        self.kernel.start_session(session_id, {})

    async def execute_code(self, payload: ExecuteCodeRequest = Body(...)) -> Any:
        payload = _body(payload)
        session_id = str(payload.get("session_id", "default"))
        cell_id = str(payload.get("cell_id", "cell"))
        code = str(payload.get("code", ""))
        self._ensure_session(session_id)
        job = self.compute.start_job(session_id, type="kernel", cell_id=cell_id)
        if job.status == "queued":
            return _jsonable(job)
        context = multiprocessing.get_context("fork")
        parent, child = context.Pipe(duplex=False)
        from .algorithm_lab.execution_worker import execute_in_worker
        process = context.Process(
            target=execute_in_worker,
            args=(child, code, self.kernel.snapshot_namespace(session_id)),
            daemon=True,
        )
        process.start()
        child.close()
        self.compute.attach_process(job.job_id, process)
        try:
            message = await asyncio.to_thread(parent.recv)
            process.join(timeout=1)
            if message["status"] == "error":
                self.compute.complete_job(session_id, job.job_id, message["error"])
                return {"status": "error", "cell_id": cell_id, "job_id": job.job_id,
                        "error": message["error"], "traceback": message.get("traceback")}
            result = self.kernel.apply_worker_result(
                session_id, cell_id, code, message["changes"], message.get("omitted")
            )
            self.compute.complete_job(session_id, job.job_id)
            return _jsonable({**result, "job_id": job.job_id})
        except (EOFError, BrokenPipeError):
            status = self.compute.get_status(session_id)
            killed = any(row["job_id"] == job.job_id and row["status"] == "killed" for row in status["recent"])
            if not killed:
                self.compute.complete_job(session_id, job.job_id, "worker terminated unexpectedly")
            return {"status": "killed" if killed else "error", "job_id": job.job_id}
        finally:
            parent.close()
            if process.is_alive():
                process.terminate()
                process.join(timeout=1)

    async def variables(self, session_id: str = Query("default")) -> Any:
        self._ensure_session(session_id)
        return _jsonable(self.kernel.serialize_namespace())

    async def push_to_backtest(self, payload: PushToBacktestRequest = Body(...)) -> Any:
        body = _body(payload)
        record = self.strategies.create(
            body.get("name", "Studio strategy"),
            body["strategy_source"],
            default_config=body.get("default_config"),
            metadata={"source": "algorithm_lab", "target": "backtest"},
        )
        return {
            "status": "ready",
            "strategy_id": record["strategy_id"],
            "name": record["name"],
            "backtest_config": {
                **record.get("default_config", {}),
                "strategy_source": record["file_path"],
            },
        }

    async def restore_kernel(self, run_id: str) -> Any:
        if not self.kernel.restore_from_checkpoint(run_id):
            raise HTTPException(404, detail=_error_detail("checkpoint_not_found", f"Checkpoint '{run_id}' was not found or is invalid"))
        return {"status": "restored", "run_id": run_id,
                "session_id": self.kernel.active_session_id,
                "variables": _jsonable(self.kernel.serialize_namespace())}

    async def run_paper_trade(self, payload: PaperTradeRequest = Body(...)) -> Any:
        body = _body(payload)
        route_name = body["strategy_name"]
        strategy_id = body.get("strategy_id")
        candidates = [self.strategies.get(strategy_id)] if strategy_id else self.strategies.list()
        strategy = candidates[0] if strategy_id else next(
            (row for row in candidates if row.get("strategy_id") == route_name or row.get("name") == route_name), None
        )
        if strategy is None:
            raise HTTPException(404, detail=_error_detail(
                "strategy_not_found",
                f"Save or push strategy '{route_name}' before starting its paper route",
            ))
        universe = body.get("universe") or strategy.get("default_config", {}).get("universe_id") or ["SPY"]
        self.paper_trader.register_strategy(
            route_name, strategy["file_path"], universe, body.get("burn_in_days", 20)
        )
        result = self.paper_trader.run_daily_paper_trade(route_name)
        status = self.paper_trader.get_status(route_name)
        return _jsonable({**asdict(result), **asdict(status), "name": route_name})

    async def lint(self, code: str = Query("")) -> Any:
        return _jsonable([finding.to_dict() for finding in self.linter.lint_code(code)])

    async def list_templates(self, family: str | None = None, complexity: str | None = None) -> Any:
        return self.templates.list_templates(family, complexity)

    async def list_strategies(self) -> Any:
        return _jsonable(self.strategies.list())

    async def get_template(self, id: str) -> Any:
        return self.templates.get_template(id)

    async def fork_template(self, id: str, payload: TemplateForkRequest = Body(default=TemplateForkRequest())) -> Any:
        payload = _body(payload)
        return self.templates.fork_template(id, payload.get("session_name"))

    async def create_composition(self, payload: CompositionCreateRequest = Body(...)) -> Any:
        payload = _body(payload)
        return self.composer.create(payload["strategy_ids"], payload.get("weights", "equal_weight"),
                                    payload.get("portfolio_name", "Strategy Portfolio"),
                                    payload.get("custom_allocator"), payload.get("custom_weights"))

    async def get_composition(self, id: str) -> Any:
        return self.composer.get(id)

    async def execute_composition(self, id: str, payload: CompositionExecuteRequest = Body(...)) -> Any:
        payload = _body(payload)
        return _jsonable(self.composer.execute(
            id, payload.get("market_data"), strategy_configs=payload.get("config")
        ))

    async def export_standalone(self, strategy_id: str) -> StreamingResponse:
        strategy = self.strategies.get(strategy_id)
        archive = StandaloneExporter().build_zip(
            strategy["name"], strategy["source_code"], strategy.get("default_config")
        )
        return StreamingResponse(io.BytesIO(archive), media_type="application/zip",
                                 headers={"Content-Disposition": f'attachment; filename="{strategy_id}.zip"'})

    async def invite(self, session_id: str, payload: InviteRequest = Body(...)) -> Any:
        payload = _body(payload)
        return self.collaboration.invite(session_id, payload["user_id"], payload.get("role", "read"),
                                         name=payload.get("name"), expires_minutes=payload.get("expires_minutes", 60))

    async def participants(self, session_id: str) -> Any:
        return self.collaboration.get_participants(session_id)

    async def collaborate(self, websocket: WebSocket, session_id: str) -> None:
        token = websocket.query_params.get("token", "")
        participant = None
        try:
            participant = await self.collaboration.join(session_id, token, websocket)
            while True:
                await self.collaboration.receive(session_id, participant["user_id"], await websocket.receive_json())
        except WebSocketDisconnect:
            pass
        finally:
            if participant:
                await self.collaboration.leave(session_id, participant["user_id"])

    async def compute_status(self, session_id: str) -> Any:
        return self.compute.get_status(session_id)

    async def kill_job(self, session_id: str, job_id: str) -> Any:
        return self.compute.kill_job(session_id, job_id)

    async def kill_all(self, session_id: str) -> Any:
        return self.compute.kill_all(session_id)

    async def list_snippets(self, tag: str | None = None) -> Any:
        return self.snippets.list(tag)

    async def create_snippet(self, payload: SnippetCreateRequest = Body(...)) -> Any:
        payload = _body(payload)
        return self.snippets.create(payload["name"], payload["code"], payload.get("language", "python"), payload.get("tags"))

    async def update_snippet(self, id: str, payload: SnippetPatchRequest = Body(...)) -> Any:
        return self.snippets.update(id, **_body(payload))

    async def delete_snippet(self, id: str) -> Any:
        return self.snippets.delete(id)

    async def run_backtest(self, payload: BacktestRunRequest = Body(...)) -> Any:
        payload = _body(payload)
        attribution_inputs = payload.pop("attribution_inputs", None)
        monte_carlo_paths = payload.pop("monte_carlo_paths", 200)
        monte_carlo_seed = payload.pop("monte_carlo_seed", 42)
        config = SimulationConfig(**payload)
        result = EventDrivenEngine().run(config)
        run_id = self.lineage.record_run(
            str(config.strategy_source or "inline-strategy"),
            config,
            result,
            data_manifest_snapshot=manifest_snapshot(),
        )
        metrics = self.lineage.get_run(run_id).metrics
        stored_result = result.to_dict()
        from .backtest.monte_carlo import bootstrap_paths
        stored_result["monte_carlo"] = bootstrap_paths(
            result.daily_returns, initial_value=config.initial_cash,
            paths=monte_carlo_paths, seed=monte_carlo_seed,
        )
        if attribution_inputs:
            stored_result["attribution_inputs"] = {
                **attribution_inputs,
                "returns": attribution_inputs.get("returns", result.daily_returns),
            }
        self.results.save(run_id, stored_result, metrics)
        return {"run_id": run_id, "result": _jsonable(stored_result), "metrics": _jsonable(metrics)}

    async def get_backtest_result(self, run_id: str) -> Any:
        return _jsonable(self.results.get(run_id))

    async def get_metrics(self, run_id: str) -> Any:
        return _jsonable(self.results.get(run_id).get("metrics", {}))

    async def export_backtest(self, run_id: str,
                              payload: BacktestExportRequest = Body(default=BacktestExportRequest())) -> StreamingResponse:
        body = _body(payload)
        record = _jsonable(self.results.get(run_id))
        result = record.get("result", {})
        section_map = {
            "metrics": record.get("metrics", {}),
            "equity": result.get("equity_curve", result.get("daily_nav", [])),
            "drawdown": result.get("drawdown", result.get("drawdowns", [])),
            "trades": result.get("trade_log", result.get("trades", [])),
            "positions": result.get("positions", []),
            "config": result.get("config", {}),
            "lineage": result.get("lineage", {}),
            "tax": result.get("tax_report", {}),
        }
        selected = {name: section_map[name] for name in body.get("sections", [])}
        export_format = body.get("format", "json")
        if export_format == "json":
            content = json.dumps({"run_id": run_id, "sections": selected}, indent=2).encode("utf-8")
            media_type, suffix = "application/octet-stream", "json"
        elif export_format == "csv":
            buffer = io.BytesIO()
            with zipfile.ZipFile(buffer, "w", compression=zipfile.ZIP_DEFLATED) as archive:
                archive.writestr("manifest.json", json.dumps({"run_id": run_id, "sections": list(selected)}, indent=2))
                for name, value in selected.items():
                    frame = pd.DataFrame(value if isinstance(value, list) else [value])
                    archive.writestr(f"{name}.csv", frame.to_csv(index=False))
            content, media_type, suffix = buffer.getvalue(), "application/zip", "zip"
        else:
            # Reuse the installed PDF renderer while keeping the export bounded
            # to the selected summary fields.
            try:
                from xml.sax.saxutils import escape
                from reportlab.lib.pagesizes import letter
                from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer
                from reportlab.lib.styles import getSampleStyleSheet
                buffer = io.BytesIO(); styles = getSampleStyleSheet(); document = SimpleDocTemplate(buffer, pagesize=letter)
                story = [Paragraph(f"Studio V2 Backtest Export: {run_id}", styles["Title"]), Spacer(1, 12)]
                for name, value in selected.items():
                    story.extend([Paragraph(name.title(), styles["Heading2"]), Paragraph(escape(json.dumps(value, default=str)[:20_000]), styles["BodyText"]), Spacer(1, 8)])
                document.build(story); content = buffer.getvalue()
            except ImportError as exc:
                raise HTTPException(409, detail=_error_detail("pdf_unavailable", "PDF export support is not installed")) from exc
            media_type, suffix = "application/pdf", "pdf"
        return StreamingResponse(io.BytesIO(content), media_type=media_type,
                                 headers={"Content-Disposition": f'attachment; filename="backtest-{run_id}.{suffix}"'})

    async def portfolio_run(self, payload: PortfolioRunRequest = Body(...)) -> Any:
        return _jsonable(self.portfolio_engine.run(_body(payload)))

    async def attribution(self, run_id: str) -> Any:
        record = self.results.get_result(run_id)
        inputs = record.get("attribution_inputs")
        if inputs is None and record.get("sector_rows"):
            inputs = {
                "sector_rows": record["sector_rows"],
                "returns": record.get("daily_returns"),
                "factor_returns": record.get("factor_returns"),
                "benchmark_name": record.get("benchmark_name", "benchmark"),
            }
        if inputs:
            return _jsonable(AttributionEngine().compute(inputs))
        if record.get("attribution"):
            legacy = record["attribution"]
            if "sectors" not in legacy and legacy.get("sector_attribution"):
                legacy = {**legacy, "sectors": legacy["sector_attribution"]}
            return _jsonable(legacy)
        if record.get("return_contributions"):
            contributions = pd.DataFrame(record["return_contributions"])
            return {"strategy_contributions": contributions.sum().to_dict()}
        raise HTTPException(422, "run does not contain sector or factor attribution inputs")

    async def slippage_audit(self, run_id: str) -> Any:
        return _jsonable(SlippageAuditor(self.results).audit(run_id))

    async def tax_report(self, run_id: str) -> Any:
        report = self.results.get_result(run_id).get("tax_report")
        if report is None:
            raise HTTPException(404, "run has no tax report")
        return _jsonable(report)

    async def list_scenarios(self) -> Any:
        return self.scenarios.list_scenarios()

    async def replay_scenario(self, scenario_id: str, strategy_id: str,
                              payload: BacktestRunRequest = Body(default=BacktestRunRequest())) -> Any:
        return _jsonable(self.scenarios.replay(strategy_id, scenario_id, _body(payload)))

    async def scenario_result(self, run_id: str) -> Any:
        return _jsonable(self.scenarios.get_result(run_id))

    async def compare(self, payload: BacktestCompareRequest = Body(...)) -> Any:
        payload = _body(payload)
        run_ids = payload.get("run_ids", [])
        if len(run_ids) < 2:
            raise HTTPException(422, "run_ids must contain at least two runs")
        records = self.results.batch_get(run_ids)
        metrics = pd.DataFrame([{"run_id": run_id, **record.get("metrics", {})} for run_id, record in zip(run_ids, records)])
        series = {}
        for run_id, values in self.results.batch_get_daily_returns(run_ids).items():
            if isinstance(values, dict):
                series[run_id] = pd.Series(values, dtype=float)
            else:
                series[run_id] = pd.Series(values, dtype=float)
        aligned = pd.concat(series, axis=1) if series else pd.DataFrame()
        correlation = aligned.corr(min_periods=2).fillna(0.0) if not aligned.empty else pd.DataFrame()
        return {"runs": _jsonable(records), "metric_comparison": _jsonable(metrics), "best_by_metric": {
            column: metrics.loc[metrics[column].idxmax(), "run_id"] for column in metrics.select_dtypes("number") if metrics[column].notna().any()
        }, "correlation_matrix": _jsonable(correlation)}

    async def get_lineage(self, strategy_file_hash: str = Query(...)) -> Any:
        return _jsonable(self.lineage.get_dag_layout(strategy_file_hash))

    async def search_lineage(self, dsr_min: float | None = None, pbo_max: float | None = None,
                             sharpe_min: float | None = None, tags: str | None = None,
                             limit: int = 100, offset: int = 0) -> Any:
        query = SearchQuery(dsr_min=dsr_min, pbo_max=pbo_max, sharpe_min=sharpe_min,
                            tags=tags.split(",") if tags else None, limit=limit, offset=offset)
        return _jsonable(self.lineage.search_runs(query))

    async def diff_lineage(self, run_id_a: str, run_id_b: str) -> Any:
        return _jsonable(self.lineage.diff_runs(run_id_a, run_id_b))

    async def robustness_core(self, payload: RobustnessCoreRequest = Body(...)) -> Any:
        from .robustness.execution import run_core_diagnostics
        outputs, components = run_core_diagnostics(_body(payload))
        stored = self._store_robustness_result("core", outputs, components)
        return _jsonable({**outputs, "run_id": stored["run_id"], "composite": stored["composite"]})

    def _store_robustness_result(self, test: str, result: Any,
                                 components: dict[str, float]) -> dict[str, Any]:
        from .robustness.scorer import CompositeRobustnessScorer
        prior = self.analytics_store.maybe_get("robustness_state", "latest") or {}
        merged = {**prior.get("components", {}), **components}
        score = CompositeRobustnessScorer().compute_composite_score(merged).to_dict()
        missing = [name for name in CompositeRobustnessScorer.weights if name not in merged]
        run_id = f"robust_{uuid.uuid4().hex[:16]}"
        record = {"run_id": run_id, "test": test, "result": _jsonable(result),
                  "components": merged, "composite": {**score, "complete": not missing,
                                                        "missing_components": missing}}
        self.analytics_store.put("robustness_results", run_id, record, create_only=True)
        self.analytics_store.put("robustness_state", "latest", record)
        return record

    async def robustness_extended(self, payload: RobustnessExtendedRequest = Body(...)) -> Any:
        from .robustness.execution import run_extended_diagnostic
        body = _body(payload)
        result, components = run_extended_diagnostic(body)
        stored = self._store_robustness_result(body["test"], result, components)
        return _jsonable({"run_id": stored["run_id"], **result, "composite": stored["composite"]})

    def _finalize_robustness_job(self, output: dict[str, Any]) -> dict[str, Any]:
        result = dict(output["result"])
        stored = self._store_robustness_result(
            str(output["test"]), result, dict(output.get("components", {}))
        )
        return _jsonable({
            "run_id": stored["run_id"],
            **result,
            "composite": stored["composite"],
        })

    async def create_robustness_job(
        self, payload: RobustnessJobCreateRequest = Body(...)
    ) -> Any:
        body = _body(payload)
        return self.robustness_jobs.submit(
            body["kind"],
            body["payload"],
            timeout_seconds=body.get("timeout_seconds", 60.0),
            max_output_bytes=body.get("max_output_bytes", 1_000_000),
        )

    async def robustness_job_status(self, job_id: str) -> Any:
        return self.robustness_jobs.get_status(job_id)

    async def cancel_robustness_job(self, job_id: str) -> Any:
        return self.robustness_jobs.cancel(job_id)

    async def robustness_job_result(self, job_id: str) -> Any:
        return self.robustness_jobs.get_result(job_id)

    async def robustness_composite(self) -> Any:
        latest = self.analytics_store.maybe_get("robustness_state", "latest")
        if latest is None:
            raise HTTPException(404, detail=_error_detail("robustness_not_found", "Run a robustness diagnostic first"))
        return latest["composite"]

    async def audit_trail(self, strategy_id: str, payload: AuditTrailRequest = Body(default=AuditTrailRequest())) -> Any:
        payload = _body(payload)
        from .robustness.audit_trail import AuditTrail
        strategy = self.strategies.get(strategy_id)
        findings = [finding.to_dict() for finding in self.linter.lint_code(strategy["source_code"])]
        run_ids = payload.get("run_ids", [])
        fill_timing = []
        for run_id in run_ids:
            result = self.results.get_result(run_id)
            for fill in result.get("trade_log", []):
                fill_timing.append({
                    "run_id": run_id,
                    "ticker": fill.get("ticker"),
                    "signal_date": fill.get("signal_date"),
                    "fill_date": fill.get("fill_date"),
                    "next_open": (
                        pd.Timestamp(fill.get("fill_date")) > pd.Timestamp(fill.get("signal_date"))
                        if fill.get("fill_date") and fill.get("signal_date") else None
                    ),
                })
        metadata = {**payload, "fill_timing": fill_timing,
                    "next_open_enforced": all(row["next_open"] for row in fill_timing) if fill_timing else None}
        audit = AuditTrail()
        record = audit.create(strategy_id, strategy["source_code"], findings, metadata)
        if str(payload.get("format", "json")).lower() == "pdf":
            return StreamingResponse(io.BytesIO(audit.render_pdf(record)), media_type="application/pdf",
                                     headers={"Content-Disposition": f'attachment; filename="audit-{strategy_id}.pdf"'})
        return record

    async def adversarial(self, payload: AdversarialRequest = Body(...)) -> Any:
        payload = _body(payload)
        from .robustness.adversarial import AdversarialStressTest
        return _jsonable(AdversarialStressTest().run(payload["returns"], seed=payload.get("seed", 42),
                                                      shock_sigma=payload.get("shock_sigma", 4),
                                                      window=payload.get("window", 63),
                                                      max_vol_percentile=payload.get("max_vol_percentile", 95),
                                                      max_cost_percentile=payload.get("max_cost_percentile", 95),
                                                      min_correlation=payload.get("min_correlation", -0.25)))

    async def adversarial_result(self, run_id: str) -> Any:
        from .robustness.adversarial import AdversarialStressTest
        return AdversarialStressTest().get(run_id)

    async def factor_evaluate(self, payload: FactorEvaluateRequest = Body(...)) -> Any:
        payload = _body(payload)
        if payload.get("factors") is not None:
            from .factors.composite_combiner import CompositeFactorCombiner
            combiner = CompositeFactorCombiner()
            options = {
                "weights": payload.get("weights"),
                "method": payload.get("normalization", "zscore"),
                "weighting": payload.get("weighting", "equal"),
                "ic_history": payload.get("ic_history"),
                "custom_code": payload.get("custom_code"),
            }
            result = (
                combiner.evaluate_composite(payload["factors"], payload["forward_returns"], **options)
                if payload.get("forward_returns") is not None
                else combiner.combine(payload["factors"], **options)
            )
            if payload.get("factor_id") and payload.get("expression"):
                result["version"] = self.governance.create_version(payload["factor_id"], payload["expression"],
                                                                    payload.get("author", "unknown"))
            return _jsonable(result)
        from .factors.evaluator import FactorExpressionEvaluator
        expression = payload.get("factor_expression") or payload.get("expression")
        if not expression:
            raise HTTPException(422, "factor_expression is required")
        return _jsonable(FactorExpressionEvaluator().evaluate(
            expression,
            payload.get("universe_id") or payload.get("tickers"),
            payload.get("start") or payload.get("date_start"),
            payload.get("end") or payload.get("date_end"),
        ))

    async def list_factor_library(self, active_only: bool = True) -> Any:
        factors = self.factor_library.list_factors(active_only=active_only)
        return _jsonable([factor.to_dict() for factor in factors])

    async def create_factor_library(self, payload: FactorLibraryCreateRequest = Body(...)) -> Any:
        body = _body(payload)
        factor_id = self.factor_library.add_factor(
            body["name"], body["expression"], body.get("metrics", {}), body.get("author")
        )
        return _jsonable({**self.factor_library.get_factor_by_id(factor_id).to_dict(),
                          **self.governance.status(factor_id)})

    async def get_factor_library(self, id: str) -> Any:
        return _jsonable({**self.factor_library.get_factor_by_id(id).to_dict(),
                          **self.governance.status(id)})

    async def update_factor_library(self, id: str,
                                    payload: FactorLibraryUpdateRequest = Body(...)) -> Any:
        body = _body(payload)
        record = self.factor_library.update_factor(
            id, body["expression"], body.get("author", "unknown"), body.get("notes", "")
        )
        return _jsonable({**record.to_dict(), **self.governance.status(id)})

    async def delete_factor_library(self, id: str) -> Any:
        return _jsonable(self.factor_library.remove_factor(id).to_dict())

    async def ic_diagnostics(self, factor_values: str | None = None, forward_returns: str | None = None,
                             cost_bps: float = 10.0) -> Any:
        if not factor_values or not forward_returns:
            raise HTTPException(422, "factor_values and forward_returns JSON query parameters are required")
        import json
        from .factors.turnover_estimator import TurnoverDecayEstimator
        return _jsonable(TurnoverDecayEstimator().estimate(json.loads(factor_values), json.loads(forward_returns), cost_bps))

    async def ic_diagnostics_post(self, payload: FactorICDiagnosticsRequest = Body(...)) -> Any:
        from .factors.turnover_estimator import TurnoverDecayEstimator
        body = _body(payload)
        return _jsonable(TurnoverDecayEstimator().estimate(
            body["factor_values"], body["forward_returns"], body.get("cost_bps", 10.0)
        ))

    async def factor_versions(self, id: str) -> Any:
        return self.governance.versions(id)

    async def factor_approve(self, id: str, payload: GovernanceTransitionRequest = Body(...)) -> Any:
        payload = _body(payload)
        return self.governance.approve(id, payload.get("actor", "unknown"), payload.get("reason", ""))

    async def factor_deprecate(self, id: str, payload: GovernanceTransitionRequest = Body(...)) -> Any:
        payload = _body(payload)
        return self.governance.deprecate(id, payload.get("actor", "unknown"), payload.get("reason", ""))

    async def factor_restore(self, id: str, payload: GovernanceTransitionRequest = Body(...)) -> Any:
        body = _body(payload)
        record = self.factor_library.restore_factor(
            id, body.get("actor", "unknown"), body.get("reason", "")
        )
        return _jsonable({**record.to_dict(), **self.governance.status(id)})

    async def factor_changelog(self, id: str) -> Any:
        return self.governance.changelog(id)

    async def optimizer_search(self, payload: OptimizerSearchRequest = Body(...)) -> Any:
        payload = _body(payload)
        from .optimizer.multi_objective import ParetoOptimizer
        from .optimizer.search import BayesianOptimizer, OptimizerConfig
        objectives = payload.pop("objectives", None)
        session_id = str(payload.get("session_id", "default"))
        mode = "pareto" if objectives else "bayesian"
        objective_directions = dict(objectives or {
            str(payload.get("objective", "sharpe")): "maximize"
        })
        parameter_names = [
            str(parameter.get("name"))
            for parameter in payload.get("parameters", [])
            if isinstance(parameter, dict) and parameter.get("name")
        ]
        study = self.trial_registry.start_study(
            session_id=session_id,
            mode=mode,
            strategy_file_hash=self.trial_registry.strategy_hash(
                payload.get("strategy_file"), payload.get("backtest_config")
            ),
            objective_directions=objective_directions,
            configuration={
                "parameters": payload.get("parameters", []),
                "trial_budget": payload.get("trial_budget", 50),
                "objective": payload.get("objective", "sharpe"),
                "objectives": objectives,
                "n_jobs": payload.get("n_jobs", 1),
            },
        )
        study_id = str(study["study_id"])
        try:
            if objectives:
                result = ParetoOptimizer().optimize(payload, objectives)
            else:
                result = BayesianOptimizer().run(OptimizerConfig(**{
                    key: value for key, value in payload.items()
                    if key in OptimizerConfig.__dataclass_fields__
                }))
            output = _jsonable(result)
            output["study_id"] = study_id
            output["session_id"] = session_id
            self.trial_registry.persist_output(
                study_id, output, parameter_names=parameter_names
            )
            return output
        except Exception as exc:
            try:
                self.trial_registry.fail_study(
                    study_id, f"{type(exc).__name__}: {exc}"
                )
            except Exception:
                logger.exception("Failed to persist optimizer study failure %s", study_id)
            raise

    async def optimizer_ensemble(self, payload: OptimizerEnsembleRequest = Body(...)) -> Any:
        payload = _body(payload)
        from .optimizer.ensemble import ParameterEnsemble
        return _jsonable(ParameterEnsemble().build(payload["trials"], payload.get("top_n", 5),
                                                    payload.get("weighting", "equal"),
                                                    payload.get("objective", "objective"),
                                                    payload.get("return_series"),
                                                    payload.get("backtest_config")))

    async def optimizer_cross_validate(self, payload: OptimizerCrossValidationRequest = Body(...)) -> Any:
        payload = _body(payload)
        from .optimizer.cross_validation import OptimizerCrossValidation
        validator = OptimizerCrossValidation()
        if payload.get("bayesian_trials") is not None or payload.get("walk_forward_windows") is not None:
            return _jsonable(validator.compare_regions(
                payload.get("bayesian_trials", []),
                payload.get("walk_forward_windows", []),
                payload.get("top_fraction", 0.20),
                payload.get("objective", "objective"),
            ))
        return _jsonable(validator.run(payload["observations"], folds=payload.get("folds", 5),
                                       purge=payload.get("purge", 5), embargo=payload.get("embargo", 5)))

    async def optimizer_cpcv(self, payload: OptimizerCPCVRequest = Body(...)) -> Any:
        from .optimizer.validation import TemporalValidationService
        return _jsonable(
            TemporalValidationService(self.strategies).run_cpcv(_body(payload))
        )

    async def optimizer_walk_forward(
        self, payload: OptimizerWalkForwardRequest = Body(...)
    ) -> Any:
        from .optimizer.validation import TemporalValidationService
        return _jsonable(
            TemporalValidationService(self.strategies).run_walk_forward(_body(payload))
        )

    async def optimizer_trials(
        self,
        session_id: Annotated[str, Query(min_length=1, max_length=200)] = "default",
        study_id: Annotated[
            str | None, Query(min_length=1, max_length=200)
        ] = None,
        limit: Annotated[int, Query(ge=1, le=1_000)] = 100,
        offset: Annotated[int, Query(ge=0)] = 0,
    ) -> Any:
        return _jsonable([
            trial.to_dict()
            for trial in self.trial_registry.get_session_trials(
                session_id, study_id=study_id, limit=limit, offset=offset
            )
        ])

    async def optimizer_studies(
        self,
        session_id: Annotated[
            str | None, Query(min_length=1, max_length=200)
        ] = None,
        status: Annotated[
            Literal["running", "completed", "failed"] | None, Query()
        ] = None,
        limit: Annotated[int, Query(ge=1, le=1_000)] = 100,
        offset: Annotated[int, Query(ge=0)] = 0,
    ) -> Any:
        return _jsonable(self.trial_registry.list_studies(
            session_id=session_id,
            status=status,
            limit=limit,
            offset=offset,
        ))

    async def optimizer_study(self, study_id: str) -> Any:
        return _jsonable(self.trial_registry.get_study(study_id))

    async def optimizer_verdict(self, dsr: float = Query(...), pbo: float = Query(..., ge=0, le=1),
                                mean_isoos: float = Query(..., ge=0),
                                stability: float = Query(..., ge=0, le=1)) -> Any:
        from .optimizer.verdict import OverfittingVerdict
        return _jsonable(OverfittingVerdict().compute_verdict(dsr, pbo, mean_isoos, stability))

    async def asset_classes(self) -> Any:
        return MultiAssetCatalog().list_asset_classes()

    async def data_catalog(self, source_type: str | None = None, query: str | None = None) -> Any:
        from .data_studio.catalog import DataCatalog
        catalog = DataCatalog()
        entries = catalog.search_catalog(query) if query else catalog.get_catalog(
            {"source_type": source_type} if source_type else None
        )
        return _jsonable([entry.to_dict() for entry in entries])

    async def data_freshness(self) -> Any:
        from .data_studio.catalog import DataFreshnessMonitor
        monitor = DataFreshnessMonitor()
        statuses = monitor.check_all_sources()
        return _jsonable([asdict(status) for status in statuses.values()])

    async def explorer_series(self, ticker: str, start: str | None = None,
                              end: str | None = None, operation: str | None = None,
                              limit: int = Query(200, ge=1, le=500)) -> Any:
        from .data_studio.explorer import DataExplorer
        explorer = DataExplorer()
        full_frame = explorer.get_primary_series(ticker, start, end)
        total_count = len(full_frame)
        frame = full_frame.tail(limit).reset_index(drop=True)
        return {
            "ticker": ticker.upper(),
            "series": _jsonable(frame),
            "count": len(frame),
            "total_count": total_count,
            "limit": limit,
            "truncated": total_count > len(frame),
        }

    async def explorer_anomalies(self, ticker: str = "SPY", start: str | None = None,
                                 end: str | None = None, operation: str | None = None) -> Any:
        from .data_studio.explorer import DataExplorer
        return _jsonable(DataExplorer().get_anomalies(ticker, start, end))

    async def explorer_heatmap(self, tickers: str = "SPY,QQQ,IWM", start: str | None = None,
                               end: str | None = None, operation: str | None = None) -> Any:
        from .data_studio.explorer import MissingDataHeatmap
        symbols = [value.strip().upper() for value in tickers.split(",") if value.strip()][:500]
        if not symbols:
            raise HTTPException(422, "at least one ticker is required")
        return _jsonable(MissingDataHeatmap().get_heatmap_data(symbols, start, end))

    async def build_universe(self, payload: DataUniverseBuildRequest = Body(...)) -> Any:
        from .data_studio.universe import UniverseBuilder
        body = _body(payload)
        filters = list(body.get("filters", []))
        asset_class = body.get("asset_class", "equity")
        if asset_class != "equity":
            filters.insert(0, {"filter_type": "asset_class", "asset_class": asset_class})
        # The UI filter primitive emits field/operator/value. Normalize it to the
        # domain builder's explicit filter cards at the API boundary.
        normalized = []
        for item in filters:
            if "filter_type" in item or "type" in item:
                normalized.append(item)
                continue
            field, value = str(item.get("field", "")).lower(), item.get("value")
            mapping = {
                "market cap": ("market_cap", "min_cap"), "market_cap": ("market_cap", "min_cap"),
                "adv": ("adv", "min_adv"), "price": ("price", "min_price"),
            }
            if field in mapping:
                kind, key = mapping[field]
                normalized.append({"filter_type": kind, key: value})
        builder = UniverseBuilder()
        as_of = body.get("as_of") or body.get("end") or pd.Timestamp.utcnow().date().isoformat()
        if body.get("tickers") and not normalized:
            constituents = [str(value).strip().upper() for value in body["tickers"] if str(value).strip()]
        else:
            constituents = builder.apply_filter_stack(normalized, as_of)["ticker"].tolist()
        universe_id = builder.save_universe_definition("Data Studio universe", normalized)
        return {"universe_id": universe_id, "as_of": as_of, "constituents": constituents,
                "count": len(constituents), "filters": normalized,
                "metadata": {"asset_class": asset_class, "logic": body.get("logic", "AND")}}

    async def upload_custom_data(
        self,
        file: Annotated[
            UploadFile,
            File(description="Bounded CSV, JSON-records, or Parquet dataset"),
        ],
        source_name: Annotated[str, Form(min_length=1, max_length=100)],
        date_column: Annotated[str, Form(min_length=1, max_length=128)],
        symbol_column: Annotated[str, Form(min_length=1, max_length=128)],
        user: Annotated[CurrentUser, Depends(get_current_user)],
        license_status: Annotated[str, Form(min_length=1, max_length=100)] = "user-provided",
        permitted_use_attested: Annotated[bool, Form()] = False,
        retention_days: Annotated[int, Form(ge=1, le=3650)] = 90,
    ) -> Any:
        from .data_studio.catalog import (
            CustomDataUploader,
            UploadQuotaExceededError,
            UploadTooLargeError,
            UploadValidationError,
        )

        metadata = CustomUploadMetadataRequest(
            source_name=source_name,
            date_column=date_column,
            symbol_column=symbol_column,
        )
        if not user.id.strip():
            raise HTTPException(
                401,
                detail=_error_detail(
                    "invalid_identity", "authenticated user id is required"
                ),
            )
        uploader = CustomDataUploader()
        chunks: list[bytes] = []
        total = 0
        try:
            if file.size is not None and file.size > uploader.max_file_bytes:
                raise UploadTooLargeError(
                    f"upload exceeds the {uploader.max_file_bytes:,}-byte file limit"
                )
            while True:
                remaining = uploader.max_file_bytes - total
                chunk = await file.read(min(1024 * 1024, remaining + 1))
                if not chunk:
                    break
                total += len(chunk)
                if total > uploader.max_file_bytes:
                    raise UploadTooLargeError(
                        f"upload exceeds the {uploader.max_file_bytes:,}-byte file limit"
                    )
                chunks.append(chunk)
            result = await asyncio.to_thread(
                uploader.upload,
                b"".join(chunks),
                file.filename or "",
                source_name=metadata.source_name,
                date_column=metadata.date_column,
                symbol_column=metadata.symbol_column,
                owner_id=user.id,
                license_status=license_status,
                permitted_use_attested=permitted_use_attested,
                retention_days=retention_days,
            )
            return _jsonable(asdict(result))
        except UploadTooLargeError as exc:
            raise HTTPException(
                413,
                detail=_error_detail(
                    "upload_too_large",
                    str(exc),
                    {"max_file_bytes": uploader.max_file_bytes},
                ),
            ) from exc
        except UploadQuotaExceededError as exc:
            raise HTTPException(
                413,
                detail=_error_detail(
                    "upload_quota_exceeded",
                    str(exc),
                    {"owner_quota_bytes": uploader.owner_quota_bytes},
                ),
            ) from exc
        except UploadValidationError as exc:
            raise HTTPException(
                422,
                detail=_error_detail("invalid_upload", str(exc)),
            ) from exc
        finally:
            await file.close()

    async def list_custom_uploads(
        self, user: Annotated[CurrentUser, Depends(get_current_user)]
    ) -> Any:
        from .data_studio.catalog import CustomDataUploader

        if not user.id.strip():
            raise HTTPException(401, detail=_error_detail("invalid_identity", "authenticated user id is required"))
        uploads = await asyncio.to_thread(CustomDataUploader().list_uploads, user.id)
        return {"visibility": "private-owner-only", "uploads": uploads, "count": len(uploads)}

    async def delete_custom_upload(
        self,
        upload_id: str,
        user: Annotated[CurrentUser, Depends(get_current_user)],
    ) -> Any:
        from .data_studio.catalog import CustomDataUploader, UploadValidationError

        if not user.id.strip():
            raise HTTPException(401, detail=_error_detail("invalid_identity", "authenticated user id is required"))
        try:
            deleted = await asyncio.to_thread(CustomDataUploader().delete_upload, user.id, upload_id)
        except UploadValidationError as exc:
            raise HTTPException(422, detail=_error_detail("invalid_upload_id", str(exc))) from exc
        if not deleted:
            raise HTTPException(404, detail=_error_detail("upload_not_found", "owner-scoped upload was not found"))
        return {"upload_id": upload_id, "status": "deleted"}

    async def data_manifests(self, deep: bool = Query(False)) -> Any:
        from .shared.data_manifest import validate_manifest
        return validate_manifest(deep=deep)

    async def refresh_data_manifest(
        self,
        payload: ManifestRefreshRequest = Body(...),
        user: CurrentUser = Depends(get_current_user),
    ) -> Any:
        from .shared.data_manifest import refresh_manifest

        if not user.id.strip():
            raise HTTPException(
                401,
                detail=_error_detail(
                    "invalid_identity", "authenticated user id is required"
                ),
            )
        dataset_ids = _body(payload)["dataset_ids"]
        manifest = await asyncio.to_thread(refresh_manifest, dataset_ids)
        selected = set(dataset_ids)
        datasets = [
            entry
            for entry in manifest["datasets"]
            if str(entry.get("id")) in selected
        ]
        return {
            "status": "refreshed",
            "manifest_version": manifest["manifest_version"],
            "generated_at": manifest["generated_at"],
            "refreshed_dataset_ids": dataset_ids,
            "refreshed_count": len(datasets),
            "datasets": datasets,
        }

    async def futures_universe(self, payload: FuturesUniverseRequest = Body(default=FuturesUniverseRequest())) -> Any:
        payload = _body(payload)
        return _jsonable(MultiAssetCatalog().build_futures_universe(
            payload.get("contracts"), payload.get("roll_method", "active_front_month"),
            payload.get("target_days", 30),
        ))

    async def crypto_universe(self, exchange: str | None = None,
                              quote_currency: str | None = None) -> Any:
        return _jsonable(MultiAssetCatalog().build_crypto_universe(exchange, quote_currency))

    async def fx_universe(self, settlement_type: str | None = None) -> Any:
        return _jsonable(MultiAssetCatalog().build_fx_universe(settlement_type))

    async def ticker_events(self, ticker: str, start: str | None = None, end: str | None = None,
                            event_type: str | None = None) -> Any:
        return self.events.get(ticker, start, end, event_type)

    async def synthetic_ranges(self, ticker: str) -> Any:
        return SyntheticRangeDetector().detect(ticker)

    def _active_records(self) -> list[Any]:
        return [record for record in self.lineage.search_runs(SearchQuery(limit=1000))
                if set(record.tags).intersection({"Active", "Deployed"})]

    async def active_strategies(self) -> Any:
        return _jsonable(self._active_records())

    @staticmethod
    def _parse_matrix(value: str | None, name: str) -> Any:
        if value is None:
            raise HTTPException(422, f"{name} JSON query parameter is required")
        import json
        return json.loads(value)

    async def portfolio_var(self, returns: str | None = None, weights: str | None = None,
                            confidence: float = 0.99, horizon_days: int = 1,
                            portfolio_value: float = 1.0) -> Any:
        if returns is None:
            result = VaREngine(self._active_records).compute_from_active_strategies(
                portfolio_value=portfolio_value
            )
            self.alerts.ingest_var(result)
            return _jsonable(result)
        parsed_returns = self._parse_matrix(returns, "returns")
        parsed_weights = self._parse_matrix(weights, "weights") if weights else None
        result = VaREngine().compute(parsed_returns, parsed_weights, confidence, horizon_days, portfolio_value)
        self.alerts.ingest_var(result)
        return _jsonable(result)

    async def portfolio_correlation(self, returns: str | None = None, weights: str | None = None) -> Any:
        result = ConcentrationEngine().compute(self._parse_matrix(returns, "returns"), self._parse_matrix(weights, "weights"))
        return _jsonable(result["correlation"])

    async def portfolio_concentration(self, returns: str | None = None, weights: str | None = None,
                                      positions: str | None = None) -> Any:
        position_maps = self._parse_matrix(positions, "positions") if positions else None
        return _jsonable(ConcentrationEngine().compute(
            self._parse_matrix(returns, "returns"),
            self._parse_matrix(weights, "weights"),
            position_maps,
        ))

    async def risk_limits(self) -> Any:
        return self.limits.list()

    async def update_risk_limits(self, payload: list[RiskLimitRequest] = Body(...)) -> Any:
        return self.limits.replace([_body(item) for item in payload])

    async def risk_breaches(self, metrics: str | None = None) -> Any:
        if metrics is None:
            result = self.limits.get_computed_breaches()
            self.alerts.ingest_breaches("limits", result["breaches"])
            return result
        return self.limits.breaches(self._parse_matrix(metrics, "metrics"))

    async def risk_alerts(self, acknowledged: bool | None = None,
                          severity: str | None = Query(None, pattern="^(info|warning|critical)$"),
                          limit: int = Query(100, ge=1, le=500),
                          offset: int = Query(0, ge=0)) -> Any:
        from .data_studio.catalog import DataFreshnessMonitor
        freshness = DataFreshnessMonitor().check_all_sources()
        self.alerts.ingest_freshness([
            asdict(value) if is_dataclass(value) else dict(value)
            for value in freshness.values()
        ])
        self.alerts.ingest_reconciliation(self._active_records())
        return self.alerts.list(acknowledged, severity, limit, offset)

    async def ack_alert(self, alert_id: str, payload: AlertAckRequest = Body(...)) -> Any:
        return self.alerts.acknowledge(alert_id, _body(payload)["actor"])

    async def journal_list(self, tag: str | None = None, search: str | None = None,
                           date_from: str | None = None, date_to: str | None = None,
                           limit: int = Query(50, ge=1, le=500),
                           offset: int = Query(0, ge=0)) -> Any:
        return self.journal.list(tag, search, date_from, date_to, limit, offset)

    async def journal_create(self, payload: JournalEntryRequest = Body(...)) -> Any:
        return self.journal.create(_body(payload))

    async def journal_update(self, entry_id: str, payload: JournalPatchRequest = Body(...)) -> Any:
        return self.journal.update(entry_id, _body(payload))

    async def journal_delete(self, entry_id: str) -> Any:
        return {"deleted": self.journal.delete(entry_id)}

    async def journal_tags(self) -> Any:
        return self.journal.tags()

    async def studio_liveness(self) -> Any:
        return self.health.liveness()

    async def studio_readiness(self, deep_manifest: bool = Query(False)) -> Any:
        result = await asyncio.to_thread(
            self.health.readiness, deep_manifest=deep_manifest
        )
        return JSONResponse(
            status_code=200 if result["status"] == "ready" else 503,
            content=result,
        )

    async def studio_operational_metrics(self) -> Any:
        jobs = self.analytics_store.list("robustness_jobs", limit=1_000)
        statuses: dict[str, int] = {}
        for job in jobs:
            status = str(job.get("status", "unknown"))
            statuses[status] = statuses.get(status, 0) + 1
        return {
            "requests": METRICS.snapshot(),
            "data_access": get_data_access_metrics(),
            "jobs": {
                "count": len(jobs),
                "active": sum(
                    count
                    for status, count in statuses.items()
                    if status in {"queued", "running"}
                ),
                "statuses": dict(sorted(statuses.items())),
                "max_concurrency": self.robustness_jobs.max_concurrency,
                "max_pending_jobs": self.robustness_jobs.max_pending_jobs,
                "max_timeout_seconds": self.robustness_jobs.max_timeout_seconds,
                "max_output_bytes": self.robustness_jobs.max_output_bytes,
            },
        }


router = Router()
