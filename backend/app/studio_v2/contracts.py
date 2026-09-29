"""Validated request contracts for Studio V2 extension endpoints."""

from __future__ import annotations

import math
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


class StudioRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")


class PortfolioStrategyRequest(StudioRequest):
    strategy_id: str | None = None
    name: str | None = None
    strategy_source: Any = None
    universe_id: Any = None
    date_start: Any = None
    date_end: Any = None
    parameters: dict[str, Any] = Field(default_factory=dict)


class PortfolioRunRequest(StudioRequest):
    composition_id: str | None = None
    strategies: list[PortfolioStrategyRequest] = Field(default_factory=list, max_length=10)
    strategy_configs: list[PortfolioStrategyRequest] | dict[str, dict[str, Any]] = Field(default_factory=list)
    shared_config: dict[str, Any] = Field(default_factory=dict)
    weight_scheme: Literal["equal", "equal_weight", "risk_parity", "custom"] = "equal_weight"
    weights: list[float] = Field(default_factory=list, max_length=10)
    initial_cash: float = Field(1_000_000.0, gt=0)
    redundancy_threshold: float = Field(0.7, ge=0, le=1)

    @model_validator(mode="after")
    def require_input(self) -> "PortfolioRunRequest":
        if not self.composition_id and not self.strategies and not self.strategy_configs:
            raise ValueError("composition_id, strategies, or strategy_configs is required")
        return self


class RobustnessCoreRequest(StudioRequest):
    test: Literal["parameter", "timing", "universe", "cost", "capacity", "noise", "data_source"] | None = None
    returns: list[float] | None = None
    prices: Any = None
    strategy_source: Any = None
    strategy_parameters: dict[str, Any] = Field(default_factory=dict)
    sources: dict[str, Any] | None = None
    noise_std: float = Field(0.001, ge=0, le=0.05)
    n_simulations: int = Field(200, ge=10, le=500)
    seed: int = 42
    tolerance_bps: float = Field(10, ge=0)
    parameter_grid: dict[str, list[Any]] | None = None
    parameter_ranges: dict[str, Any] | None = None
    observations: list[dict[str, Any]] | None = None
    backtest_config: dict[str, Any] | None = None
    trade_log: list[dict[str, Any]] | None = None
    tickers: list[str] = Field(default_factory=list, max_length=500)
    drop_pct: float = Field(0.10, gt=0, lt=1)
    noise_bps: float = Field(10.0, ge=0, le=500)
    shift_magnitudes: list[int] = Field(default_factory=list, max_length=20)
    strategy_id: str | None = None


class RobustnessExtendedRequest(StudioRequest):
    test: Literal["parameter", "timing", "noise", "universe", "cost", "capacity", "boundary", "regime"]
    returns: list[float] = Field(default_factory=list, max_length=100_000)
    returns_by_ticker: dict[str, list[float]] = Field(default_factory=dict)
    vix: list[float] = Field(default_factory=list, max_length=100_000)
    trade_log: list[dict[str, Any]] = Field(default_factory=list, max_length=100_000)
    cost_sharpes: list[dict[str, float]] = Field(default_factory=list, max_length=1_000)
    parameter_grid: dict[str, list[float]] = Field(default_factory=dict)
    observations: list[dict[str, Any]] = Field(default_factory=list, max_length=10_000)
    realistic_band: tuple[float, float] = (5.0, 15.0)
    adv_data: dict[str, float] = Field(default_factory=dict)
    vol_data: dict[str, float] = Field(default_factory=dict)
    lambda_by_bucket: dict[str, float] = Field(default_factory=lambda: {"small": 1.2e-4})
    oos_sharpes: list[float] = Field(default_factory=list, max_length=1_000)
    n_simulations: int = Field(200, ge=10, le=500)
    noise_bps: float = Field(10.0, ge=0, le=500)
    drop_pct: float = Field(0.10, gt=0, lt=1)
    seed: int = 42

    @model_validator(mode="after")
    def validate_ranges(self) -> "RobustnessExtendedRequest":
        if self.realistic_band[1] <= self.realistic_band[0]:
            raise ValueError("realistic_band upper bound must exceed lower bound")
        lengths = {len(values) for values in self.returns_by_ticker.values()}
        if len(lengths) > 1:
            raise ValueError("returns_by_ticker arrays must have equal lengths")
        return self


class RobustnessJobCreateRequest(StudioRequest):
    kind: Literal["core", "extended"]
    payload: RobustnessCoreRequest | RobustnessExtendedRequest
    timeout_seconds: float = Field(60.0, ge=1.0, le=300.0)
    max_output_bytes: int = Field(1_000_000, ge=1_024, le=5_000_000)

    @model_validator(mode="before")
    @classmethod
    def validate_typed_payload(cls, values: Any) -> Any:
        if not isinstance(values, dict):
            return values
        normalized = dict(values)
        kind = normalized.get("kind")
        raw_payload = normalized.get("payload")
        if kind == "core":
            normalized["payload"] = RobustnessCoreRequest.model_validate(raw_payload)
        elif kind == "extended":
            normalized["payload"] = RobustnessExtendedRequest.model_validate(raw_payload)
        return normalized

    @model_validator(mode="after")
    def require_matching_payload(self) -> "RobustnessJobCreateRequest":
        expected = (
            RobustnessCoreRequest if self.kind == "core" else RobustnessExtendedRequest
        )
        if not isinstance(self.payload, expected):
            raise ValueError(f"{self.kind} jobs require a typed {self.kind} payload")
        return self


class AuditTrailRequest(StudioRequest):
    format: Literal["json", "pdf"] = "json"
    run_ids: list[str] = Field(default_factory=list, max_length=100)
    cv_runs: list[dict[str, Any]] = Field(default_factory=list)
    purge: int | None = Field(None, ge=0)
    embargo: int | None = Field(None, ge=0)


class AdversarialRequest(StudioRequest):
    returns: list[float] = Field(min_length=20)
    seed: int = 42
    shock_sigma: float = Field(4, gt=0)
    window: int = Field(63, ge=10)
    max_vol_percentile: float = Field(95, gt=0, le=100)
    max_cost_percentile: float = Field(95, gt=0, le=100)
    min_correlation: float = Field(-0.25, ge=-1, le=1)


class FactorEvaluateRequest(StudioRequest):
    factors: dict[str, Any] | None = None
    weights: dict[str, float] | None = None
    weighting: Literal["equal", "ic", "ic_weighted", "ic_ir", "ic_ir_weighted", "custom"] = "equal"
    normalization: Literal["zscore", "rank"] = "zscore"
    ic_history: dict[str, list[float]] | None = None
    custom_code: str | None = None
    forward_returns: Any = None
    factor_id: str | None = None
    expression: str | None = None
    author: str = "unknown"
    universe_id: Any = None
    start: Any = None
    end: Any = None
    factor_expression: str | None = Field(None, max_length=100_000)
    tickers: list[str] | None = Field(None, max_length=500)
    date_start: Any = None
    date_end: Any = None


class FactorICDiagnosticsRequest(StudioRequest):
    factor_values: list[list[float]] = Field(min_length=3, max_length=100_000)
    forward_returns: list[list[float]] = Field(min_length=3, max_length=100_000)
    cost_bps: float = Field(10.0, ge=0, le=10_000)
    operation: str | None = Field(None, max_length=100)

    @model_validator(mode="after")
    def aligned_observations(self) -> "FactorICDiagnosticsRequest":
        if len(self.factor_values) != len(self.forward_returns):
            raise ValueError("factor_values and forward_returns must have equal lengths")
        score_widths = {len(row) for row in self.factor_values}
        return_widths = {len(row) for row in self.forward_returns}
        if len(score_widths) != 1 or len(return_widths) != 1 or score_widths != return_widths:
            raise ValueError("factor_values and forward_returns must be aligned rectangular matrices")
        if next(iter(score_widths), 0) < 2:
            raise ValueError("IC diagnostics require at least two assets per date")
        return self


class FactorLibraryCreateRequest(StudioRequest):
    name: str = Field(min_length=1, max_length=300)
    expression: str = Field(min_length=1, max_length=100_000)
    metrics: dict[str, float] = Field(default_factory=dict)
    author: str = Field("unknown", min_length=1, max_length=200)


class FactorLibraryUpdateRequest(StudioRequest):
    expression: str = Field(min_length=1, max_length=100_000)
    author: str = Field("unknown", min_length=1, max_length=200)
    notes: str = Field("", max_length=10_000)


class OptimizerEnsembleRequest(StudioRequest):
    trials: list[dict[str, Any]] = Field(min_length=1)
    top_n: int = Field(5, ge=1, le=100)
    weighting: Literal["equal", "objective", "inverse_variance"] = "equal"
    objective: str = "objective"
    return_series: dict[str, list[float]] | None = None
    backtest_config: dict[str, Any] | None = None


class OptimizerCrossValidationRequest(StudioRequest):
    observations: list[dict[str, Any]] | None = None
    folds: int = Field(5, ge=2, le=20)
    purge: int = Field(5, ge=0)
    embargo: int = Field(5, ge=0)
    bayesian_trials: list[dict[str, Any]] | None = None
    walk_forward_windows: list[dict[str, Any]] | None = None
    top_fraction: float = Field(0.20, gt=0, le=1)
    objective: str = "objective"

    @model_validator(mode="after")
    def require_mode(self) -> "OptimizerCrossValidationRequest":
        overlay = self.bayesian_trials is not None or self.walk_forward_windows is not None
        if overlay and (self.bayesian_trials is None or self.walk_forward_windows is None):
            raise ValueError("both bayesian_trials and walk_forward_windows are required")
        if not overlay and self.observations is None:
            raise ValueError("observations or both preferred-region inputs are required")
        return self


class OptimizerValidationBacktestRequest(StudioRequest):
    universe_id: list[str] = Field(min_length=1, max_length=10)
    date_start: str = Field(min_length=10, max_length=40)
    date_end: str = Field(min_length=10, max_length=40)
    benchmark: str = Field("SPY", min_length=1, max_length=32)
    rebalance_freq: Literal["daily", "weekly", "monthly", "quarterly"] = "daily"
    position_sizing: Literal["equal_weight", "vol_scaled"] = "equal_weight"
    cost_model: Literal["zero", "flat_bps", "almgren_chriss"] = "almgren_chriss"
    cost_bps: float = Field(0.0, ge=0.0, le=1_000.0)
    fixed_cost_bps: float = Field(0.0, ge=0.0, le=1_000.0)
    survivorship_bias: bool = True
    margin_enabled: bool = False
    max_fill_pct: float = Field(0.20, gt=0.0, le=1.0)
    hard_to_borrow_threshold: float = Field(0.05, ge=0.0, le=1.0)
    initial_cash: float = Field(1_000_000.0, gt=0.0, le=1_000_000_000_000.0)
    max_leverage: float = Field(1.0, gt=0.0, le=10.0)
    parameters: dict[str, Any] = Field(default_factory=dict)

    @field_validator("universe_id")
    @classmethod
    def normalize_validation_tickers(cls, values: list[str]) -> list[str]:
        normalized = [str(value).strip().upper() for value in values]
        if any(not value or len(value) > 32 for value in normalized):
            raise ValueError("universe tickers must contain 1-32 characters")
        if len(set(normalized)) != len(normalized):
            raise ValueError("universe tickers must be unique")
        return normalized


class OptimizerValidationParameterRequest(StudioRequest):
    name: str = Field(min_length=1, max_length=100)
    type: Literal["continuous", "discrete", "categorical"] = "continuous"
    current_value: Any = None
    suggested_range: tuple[float, float] | None = None
    values: list[Any] | None = Field(None, min_length=1, max_length=20)
    included: bool = True

    @model_validator(mode="after")
    def validate_parameter_domain(self) -> "OptimizerValidationParameterRequest":
        if self.type == "continuous":
            if self.suggested_range is None and self.current_value is None:
                raise ValueError("continuous parameters require current_value or suggested_range")
            if self.suggested_range is not None:
                low, high = map(float, self.suggested_range)
                if not math.isfinite(low) or not math.isfinite(high) or high <= low:
                    raise ValueError("suggested_range must contain finite increasing bounds")
        elif not self.values:
            raise ValueError(f"{self.type} parameters require non-empty values")
        return self


class _OptimizerTemporalValidationRequest(StudioRequest):
    strategy_id: str | None = Field(None, min_length=1, max_length=200)
    strategy_file: str | None = Field(None, min_length=1, max_length=2_000)
    backtest_config: OptimizerValidationBacktestRequest

    @model_validator(mode="after")
    def require_one_strategy_source(self) -> "_OptimizerTemporalValidationRequest":
        if bool(self.strategy_id) == bool(self.strategy_file):
            raise ValueError("provide exactly one of strategy_id or strategy_file")
        return self


class OptimizerCPCVRequest(_OptimizerTemporalValidationRequest):
    mode: Literal["cpcv"] = "cpcv"
    n_groups: int | None = Field(None, ge=3, le=8)
    n_splits: int | None = Field(None, ge=3, le=8)
    k_test: int = Field(2, ge=1, le=3)
    purge_days: int = Field(21, ge=0, le=63)
    embargo_days: int = Field(10, ge=0, le=63)
    embargo_lengths: list[int] = Field(
        default_factory=lambda: [0, 5, 10, 21], min_length=1, max_length=4
    )
    m_trials: int = Field(1, ge=1, le=2_000)

    @model_validator(mode="after")
    def bound_combinatorial_paths(self) -> "OptimizerCPCVRequest":
        if self.n_groups is not None and self.n_splits is not None and self.n_groups != self.n_splits:
            raise ValueError("n_groups and compatibility n_splits must match when both are supplied")
        groups = self.n_groups or self.n_splits or 6
        if self.k_test >= groups:
            raise ValueError("k_test must be smaller than the number of groups")
        if math.comb(groups, self.k_test) > 28:
            raise ValueError("CPCV is capped at 28 combinatorial paths")
        if len(set(self.embargo_lengths)) != len(self.embargo_lengths):
            raise ValueError("embargo_lengths must be unique")
        if any(value < 0 or value > 63 for value in self.embargo_lengths):
            raise ValueError("embargo lengths must be between 0 and 63 sessions")
        return self


class OptimizerWalkForwardRequest(_OptimizerTemporalValidationRequest):
    mode: Literal["walk_forward", "walk-forward"] = "walk_forward"
    parameters: list[OptimizerValidationParameterRequest] = Field(
        min_length=1, max_length=5
    )
    is_months: int = Field(12, ge=3, le=24)
    oos_months: int = Field(3, ge=1, le=6)
    window_mode: Literal["rolling", "anchored"] = "rolling"
    objective: Literal["sharpe", "sortino", "calmar"] = "sharpe"
    trials_per_window: int | None = Field(None, ge=1, le=6)
    trial_budget: int | None = Field(None, ge=1, le=2_000)
    max_windows: int = Field(8, ge=2, le=8)
    seed: int = 42

    @model_validator(mode="after")
    def validate_parameter_names(self) -> "OptimizerWalkForwardRequest":
        enabled = [parameter.name for parameter in self.parameters if parameter.included]
        if not enabled:
            raise ValueError("at least one optimizer parameter must be enabled")
        if len(set(enabled)) != len(enabled):
            raise ValueError("optimizer parameter names must be unique")
        return self


class FuturesUniverseRequest(StudioRequest):
    contracts: list[dict[str, Any]] | None = None
    roll_method: Literal["active_front_month", "ratio_adjusted", "constant_maturity"] = "active_front_month"
    target_days: int = Field(30, ge=1, le=365)


class DataUniverseBuildRequest(StudioRequest):
    """Bounded point-in-time universe request used by Data Studio."""

    filters: list[dict[str, Any]] = Field(default_factory=list, max_length=25)
    tickers: list[str] = Field(default_factory=list, max_length=500)
    as_of: str | None = None
    start: str | None = None
    end: str | None = None
    logic: Literal["AND", "OR"] = "AND"
    asset_class: str = Field("equity", min_length=1, max_length=50)
    operation: Literal["universe"] | None = None


class CustomUploadMetadataRequest(StudioRequest):
    """Validated form metadata for an authenticated custom dataset upload."""

    source_name: str = Field(min_length=1, max_length=100)
    date_column: str = Field(min_length=1, max_length=128)
    symbol_column: str = Field(min_length=1, max_length=128)


class ManifestRefreshRequest(StudioRequest):
    """Explicit bounded set of known manifest datasets to regenerate."""

    dataset_ids: list[str] = Field(min_length=1, max_length=32)

    @field_validator("dataset_ids")
    @classmethod
    def validate_dataset_ids(cls, values: list[str]) -> list[str]:
        normalized = [str(value).strip() for value in values]
        if any(not value or len(value) > 100 for value in normalized):
            raise ValueError("dataset ids must contain 1-100 characters")
        if len(set(normalized)) != len(normalized):
            raise ValueError("dataset ids must be unique")
        return normalized


class JournalEntryRequest(StudioRequest):
    title: str = Field(min_length=1, max_length=300)
    content: str = Field(default="", max_length=200_000)
    tags: list[str] = Field(default_factory=list, max_length=100)
    linked_run_ids: list[str] = Field(default_factory=list, max_length=500)
    metadata: dict[str, Any] = Field(default_factory=dict)


class JournalPatchRequest(StudioRequest):
    expected_version: int = Field(ge=1)
    title: str | None = Field(None, min_length=1, max_length=300)
    content: str | None = Field(None, max_length=200_000)
    tags: list[str] | None = Field(None, max_length=100)
    linked_run_ids: list[str] | None = Field(None, max_length=500)
    metadata: dict[str, Any] | None = None


class AlertAckRequest(StudioRequest):
    actor: str = Field(min_length=1, max_length=200)


class ExecuteCodeRequest(StudioRequest):
    session_id: str = Field("default", min_length=1, max_length=200)
    cell_id: str = Field("cell", min_length=1, max_length=200)
    code: str = Field(min_length=1, max_length=1_000_000)


class PushToBacktestRequest(StudioRequest):
    strategy_source: str = Field(min_length=1, max_length=1_000_000)
    name: str = Field("Studio strategy", min_length=1, max_length=300)
    target: Literal["backtest"] = "backtest"
    default_config: dict[str, Any] = Field(default_factory=dict)


class PaperTradeRequest(StudioRequest):
    strategy_name: str = Field(min_length=3, max_length=40, pattern=r"^[A-Za-z0-9][A-Za-z0-9_-]+$")
    strategy_id: str | None = None
    universe: list[str] = Field(default_factory=list, max_length=100)
    burn_in_days: int = Field(20, ge=2, le=252)


class BacktestExportRequest(StudioRequest):
    format: Literal["json", "csv", "pdf"] = "json"
    sections: list[Literal["metrics", "equity", "drawdown", "trades", "positions", "config", "lineage", "tax"]] = Field(
        default_factory=lambda: ["metrics", "equity", "trades"], max_length=8
    )


class TemplateForkRequest(StudioRequest):
    session_name: str | None = Field(None, max_length=300)
    name: str | None = Field(None, max_length=300)


class CompositionCreateRequest(StudioRequest):
    strategy_ids: list[str] = Field(min_length=2, max_length=10)
    weights: Literal["equal", "equal_weight", "risk_parity", "custom"] = "equal_weight"
    portfolio_name: str = Field("Untitled Portfolio", min_length=1, max_length=300)
    custom_allocator: str | None = Field(None, max_length=100_000)
    custom_weights: dict[str, float] | None = None


class CompositionExecuteRequest(StudioRequest):
    market_data: Any
    config: dict[str, dict[str, Any]] = Field(default_factory=dict)


class InviteRequest(StudioRequest):
    user_id: str = Field(min_length=1, max_length=200)
    role: Literal["read", "edit"] = "read"
    name: str | None = Field(None, max_length=200)
    expires_minutes: int = Field(60, ge=1, le=1_440)


class SnippetCreateRequest(StudioRequest):
    name: str = Field(min_length=1, max_length=300)
    code: str = Field(min_length=1, max_length=1_000_000)
    language: str = Field("python", min_length=1, max_length=50)
    tags: list[str] = Field(default_factory=list, max_length=100)


class SnippetPatchRequest(StudioRequest):
    name: str | None = Field(None, min_length=1, max_length=300)
    code: str | None = Field(None, min_length=1, max_length=1_000_000)
    language: str | None = Field(None, min_length=1, max_length=50)
    tags: list[str] | None = Field(None, max_length=100)


class BacktestRunRequest(StudioRequest):
    strategy_source: Any = None
    universe_id: Any = None
    date_start: Any = None
    date_end: Any = None
    benchmark: str = "SPY"
    rebalance_freq: str = "daily"
    position_sizing: Any = "equal_weight"
    cost_model: str = "almgren_chriss"
    cost_bps: float = Field(0, ge=0)
    survivorship_bias: bool = True
    margin_enabled: bool = False
    max_fill_pct: float = Field(0.20, gt=0, le=1)
    hard_to_borrow_threshold: float = Field(0.05, ge=0, le=1)
    initial_cash: float = Field(1_000_000, gt=0)
    max_leverage: float = Field(1, gt=0)
    fixed_cost_bps: float = Field(0, ge=0)
    parameters: dict[str, Any] = Field(default_factory=dict)
    corporate_actions: Any = None
    tax_config: Any = None
    date_range_override: Any = None
    attribution_inputs: dict[str, Any] | None = None
    monte_carlo_paths: int = Field(200, ge=0, le=1_000)
    monte_carlo_seed: int = 42


class ScenarioReplayRequest(StudioRequest):
    parameters: dict[str, Any] = Field(default_factory=dict)


class BacktestCompareRequest(StudioRequest):
    run_ids: list[str] = Field(min_length=2, max_length=100)


class GovernanceTransitionRequest(StudioRequest):
    actor: str = Field("unknown", min_length=1, max_length=200)
    reason: str = Field("", max_length=10_000)


class SearchParameterRequest(StudioRequest):
    name: str = Field(min_length=1, max_length=200)
    type: Literal["continuous", "discrete", "categorical"] = "continuous"
    current_value: Any = None
    suggested_range: tuple[float, float] | None = None
    values: list[Any] | None = None
    included: bool = True


class OptimizerSearchRequest(StudioRequest):
    strategy_file: Any = None
    backtest_config: dict[str, Any] = Field(default_factory=dict)
    parameters: list[SearchParameterRequest] = Field(min_length=1, max_length=100)
    trial_budget: int = Field(50, ge=1, le=2_000)
    objective: str = Field("sharpe", min_length=1, max_length=200)
    capacity_data: Any = None
    session_id: str = Field("default", min_length=1, max_length=200)
    n_jobs: int = Field(1, ge=1, le=32)
    objectives: dict[str, Literal["min", "max", "minimize", "maximize"]] | None = Field(
        None, min_length=1, max_length=8
    )


class RiskLimitRequest(StudioRequest):
    id: str | None = None
    metric: str = Field(min_length=1, max_length=200)
    operator: Literal["max", "min"] = "max"
    threshold: float
    severity: Literal["info", "warning", "critical"] = "warning"
    enabled: bool = True


class StudioResponse(BaseModel):
    model_config = ConfigDict(extra="allow")


class PortfolioRunResponse(StudioResponse):
    run_id: str
    composition_id: str | None = None
    combined: dict[str, Any]
    per_strategy: list[dict[str, Any]]
    correlation_matrix: Any
    redundancy_flags: list[dict[str, Any]]


class AttributionResponse(StudioResponse):
    benchmark_name: str | None = None
    total_allocation_effect: float | None = None
    total_selection_effect: float | None = None
    total_interaction_effect: float | None = None
    sectors: list[dict[str, Any]] = Field(default_factory=list)
    factors: list[dict[str, Any]] = Field(default_factory=list)


class RobustnessCoreResponse(StudioResponse):
    data_source: dict[str, Any] | None = None
    parameter_interaction: dict[str, Any] | None = None
    timing: dict[str, Any] | None = None


class CompositeRobustnessResponse(BaseModel):
    score: float
    component_scores: dict[str, float]
    verdict: str
    diagnoses: dict[str, str]
    complete: bool
    missing_components: list[str]


class RobustnessExtendedResponse(BaseModel):
    run_id: str
    composite: CompositeRobustnessResponse
    noise: dict[str, Any] | None = None
    parameter: dict[str, Any] | None = None
    timing: dict[str, Any] | None = None
    universe: dict[str, Any] | None = None
    cost: dict[str, Any] | None = None
    capacity: dict[str, Any] | None = None
    boundary: dict[str, Any] | None = None
    regime: dict[str, Any] | None = None


class RobustnessJobTransitionResponse(BaseModel):
    status: Literal["queued", "running", "completed", "failed", "cancelled"]
    at: str


class RobustnessJobFailureResponse(BaseModel):
    code: str
    message: str


class RobustnessJobStatusResponse(BaseModel):
    job_id: str
    kind: Literal["core", "extended"]
    status: Literal["queued", "running", "completed", "failed", "cancelled"]
    phase: Literal["queued", "running", "completed", "failed", "cancelled"]
    progress: float = Field(ge=0.0, le=1.0)
    timeout_seconds: float = Field(gt=0.0, le=300.0)
    max_output_bytes: int = Field(ge=256, le=5_000_000)
    created_at: str
    updated_at: str
    started_at: str | None = None
    completed_at: str | None = None
    failure: RobustnessJobFailureResponse | None = None
    result_available: bool
    transitions: list[RobustnessJobTransitionResponse]


class RobustnessJobResultResponse(BaseModel):
    job: RobustnessJobStatusResponse
    result: dict[str, Any]


class AdversarialResponse(StudioResponse):
    run_id: str
    method: str
    baseline: dict[str, Any]
    adversarial: dict[str, Any]
    degradation_percentage: float
    recovery_days: int | None = None
    survival_verdict: Literal["survives", "fails"]
    constraints: dict[str, Any]


class OptimizerEnsembleResponse(StudioResponse):
    members: list[dict[str, Any]]
    ensemble_returns: Any
    ensemble_metrics: dict[str, Any]
    distribution: dict[str, Any]
    mode: str


class OptimizerCrossValidationResponse(StudioResponse):
    verdict: str | None = None
    overlap_percentage: float | None = None
    overlay: list[dict[str, Any]] | None = None
    folds: list[dict[str, Any]] | None = None
    mean_score: float | None = None


class OptimizerCPCVPathResponse(BaseModel):
    path: int = Field(ge=0)
    test_groups: list[int]
    test_start: str
    test_end: str
    observations: int = Field(ge=2)
    train_observations: int = Field(ge=0)
    sharpe: float
    total_return: float
    positive: bool


class OptimizerCPCVSharpeResponse(BaseModel):
    mean: float | None = None
    median: float | None = None
    p5: float | None = None
    p95: float | None = None


class OptimizerCPCVEmbargoResponse(BaseModel):
    embargo_days: int = Field(ge=0, le=63)
    mean_train_observations: float = Field(ge=0.0)
    min_train_observations: int = Field(ge=0)


class OptimizerCPCVResponse(BaseModel):
    mode: Literal["cpcv"]
    method: Literal["fixed_parameter_combinatorial_purged_cv"]
    strategy_id: str | None = None
    strategy_hash: str
    n_groups: int = Field(ge=3, le=8)
    k_test: int = Field(ge=1, le=3)
    n_splits: int = Field(ge=1, le=28)
    source_observations: int = Field(ge=20, le=756)
    paths: list[OptimizerCPCVPathResponse] = Field(min_length=1, max_length=28)
    sharpe: OptimizerCPCVSharpeResponse
    dsr: float | None = None
    pbo: float | None = Field(None, ge=0.0, le=1.0)
    pbo_reason: str
    path_failure_probability: float = Field(ge=0.0, le=1.0)
    embargo_sensitivity: list[OptimizerCPCVEmbargoResponse] = Field(
        min_length=1, max_length=4
    )
    backtests_executed: Literal[1]
    duration_seconds: float = Field(ge=0.0)
    warnings: list[str]


class OptimizerWalkForwardWindowResponse(BaseModel):
    id: str
    window: int = Field(ge=0)
    train_start: str
    train_end: str
    test_start: str
    test_end: str
    train_observations: int = Field(ge=20)
    oos_observations: int = Field(ge=5)
    train_pct: float = Field(gt=0.0, le=100.0)
    test_pct: float = Field(gt=0.0, le=100.0)
    optimal_params: dict[str, Any]
    is_objective: float | None = None
    oos_objective: float | None = None
    is_sharpe: float
    oos_sharpe: float
    ratio: float | None = None


class OptimizerWalkForwardCurvePointResponse(BaseModel):
    date: str
    return_value: float
    equity: float = Field(gt=0.0)


class OptimizerWalkForwardResponse(BaseModel):
    mode: Literal["walk_forward"]
    method: Literal["precomputed_candidate_walk_forward"]
    strategy_id: str | None = None
    strategy_hash: str
    objective: Literal["sharpe", "sortino", "calmar"]
    windows: list[OptimizerWalkForwardWindowResponse] = Field(min_length=2, max_length=8)
    stitched_oos_curve: list[OptimizerWalkForwardCurvePointResponse]
    window_count: int = Field(ge=2, le=8)
    candidate_count: int = Field(ge=1, le=6)
    requested_trial_budget: int = Field(ge=1)
    backtests_executed: int = Field(ge=1, le=6)
    mean_oos_sharpe: float
    pass_rate: float = Field(ge=0.0, le=1.0)
    mean_isoos_ratio: float | None = None
    confidence_interval: tuple[float, float] | None = None
    duration_seconds: float = Field(ge=0.0)
    warnings: list[str]


class OptimizerTrialResponse(BaseModel):
    trial_id: str
    study_id: str
    trial_number: int | None = None
    session_id: str
    strategy_file_hash: str
    parameter_dict: dict[str, Any]
    objective_value: float | None = None
    objective_name: str
    objective_values: dict[str, float | None]
    timestamp: str
    mode: str
    state: str


class OptimizerStudySummaryResponse(BaseModel):
    study_id: str
    session_id: str
    mode: str
    status: Literal["running", "completed", "failed"]
    strategy_file_hash: str
    objective_names: list[str]
    objective_directions: dict[str, str]
    trial_count: int = Field(ge=0)
    started_at: str
    completed_at: str | None = None
    configuration: dict[str, Any]
    error: str | None = None
    created_at: str
    updated_at: str


class OptimizerStudyResponse(OptimizerStudySummaryResponse):
    result: dict[str, Any]


class MultiAssetUniverseResponse(StudioResponse):
    asset_class: str
    instruments: list[str]
    observations: int | None = None


class MissingDataHeatmapResponse(BaseModel):
    tickers: list[str]
    dates: list[str]
    status: list[list[Literal["green", "yellow", "red"]]]
    warning: str | None = None


class JournalEntryResponse(StudioResponse):
    id: str
    version: int = Field(ge=1)
    title: str
    content: str = ""
    tags: list[str] = Field(default_factory=list)


class ErrorDetail(BaseModel):
    code: str
    message: str
    details: Any = None
    request_id: str | None = None


class ErrorResponse(BaseModel):
    detail: ErrorDetail | str | list[dict[str, Any]]


class OperationResponse(StudioResponse):
    status: str | None = None
    id: str | None = None
    deleted: bool | None = None
    job_id: str | None = None
    error: str | None = None
    message: str | None = None


class AlgorithmLabResponse(OperationResponse):
    session_id: str | None = None
    strategy_id: str | None = None
    composition_id: str | None = None
    name: str | None = None
    source_code: str | None = None
    participants: list[dict[str, Any]] | None = None
    variables: dict[str, Any] | None = None
    result: Any = None


class BacktestResponse(OperationResponse):
    run_id: str | None = None
    result: dict[str, Any] | None = None
    metrics: dict[str, Any] | None = None
    runs: list[dict[str, Any]] | None = None
    metric_comparison: list[dict[str, Any]] | None = None
    best_by_metric: dict[str, str] | None = None
    correlation_matrix: Any = None


class RobustnessResponse(OperationResponse):
    run_id: str | None = None
    method: str | None = None
    baseline: dict[str, Any] | None = None
    adversarial: dict[str, Any] | None = None
    sections: dict[str, Any] | None = None
    survival_verdict: str | None = None


class FactorResponse(OperationResponse):
    factor_id: str | None = None
    version: Any = None
    status: str | None = None
    composite_ic: float | None = None
    ic_ir: float | None = None
    half_life: float | None = None
    optimal_rebalance: Any = None
    diagnostics: dict[str, Any] | None = None


class OptimizerResponse(OperationResponse):
    study_id: str | None = None
    trials: list[dict[str, Any]] | None = None
    best_trial: dict[str, Any] | None = None
    pareto_front: list[dict[str, Any]] | None = None
    hypervolume_progression: list[dict[str, float]] | list[float] | None = None
    verdict: str | None = None


class DataStudioResponse(OperationResponse):
    asset_class: str | None = None
    ticker: str | None = None
    date: str | None = None
    event_type: str | None = None
    instruments: list[str] | None = None
    source: str | None = None
    is_proxy: bool | None = None
    has_synthetic_data: bool | None = None


class CustomUploadResponse(BaseModel):
    success: Literal[True]
    source_name: str
    fields: list[str]
    validation_report: dict[str, Any]
    storage_key: str
    format: Literal["parquet"]
    size_bytes: int = Field(ge=0)
    checksum_sha256: str = Field(min_length=64, max_length=64)
    created_at: str
    expires_at: str
    governance: dict[str, Any]


class ManifestDatasetMetadataResponse(StudioResponse):
    id: str
    path: str
    format: str
    rows: int = Field(ge=0)
    size_bytes: int = Field(ge=0)
    required_columns: list[str]
    sha256: str
    schema_version: int = Field(ge=1)
    schema_fingerprint: str = Field(min_length=64, max_length=64)
    provenance: dict[str, Any]


class ManifestRefreshResponse(BaseModel):
    status: Literal["refreshed"]
    manifest_version: int
    generated_at: str
    refreshed_dataset_ids: list[str]
    refreshed_count: int = Field(ge=1)
    datasets: list[ManifestDatasetMetadataResponse]


class DatasetManifestEntryResponse(StudioResponse):
    id: str
    path: str
    format: str
    compression: str
    rows: int
    size_bytes: int
    date_column: str
    date_min: str
    date_max: str
    required_columns: list[str]
    sha256: str
    role: str
    status: Literal["healthy", "invalid", "missing"]
    errors: list[str]
    checksum_verified: bool = False
    checksum_match: bool | None = None
    schema_version: int = Field(ge=1)
    schema_fingerprint: str = Field(min_length=64, max_length=64)
    schema_verified: bool
    provenance: dict[str, Any]


class DatasetManifestResponse(BaseModel):
    manifest_version: int
    generated_at: str
    manifest_path: str
    deep_validation: bool
    healthy: bool
    datasets: list[DatasetManifestEntryResponse]


class StudioLivenessResponse(BaseModel):
    status: Literal["alive"]
    checked_at: str
    uptime_seconds: float = Field(ge=0.0)


class StudioReadinessResponse(BaseModel):
    status: Literal["ready", "not_ready"]
    checked_at: str
    deep_manifest: bool
    dependencies: dict[str, dict[str, Any]]


class StudioOperationalMetricsResponse(BaseModel):
    requests: dict[str, Any]
    data_access: dict[str, Any]
    jobs: dict[str, Any]


class PortfolioRiskResponse(OperationResponse):
    metric: str | None = None
    threshold: float | None = None
    severity: str | None = None
    acknowledged: bool | None = None
    breaches: list[dict[str, Any]] | None = None
    overlapping_positions: list[dict[str, Any]] | None = None
    portfolio_value: float | None = None
    results: dict[str, Any] | None = None
