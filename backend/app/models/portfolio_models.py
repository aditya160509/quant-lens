"""
Portfolio System v2 - Pydantic Models
All data contracts for 29-feature institutional-grade portfolio system
"""
from pydantic import BaseModel, Field
from typing import List, Dict, Optional, Any, Literal
from datetime import datetime
from enum import Enum


# =============================================================================
# ENUMS
# =============================================================================

class Severity(str, Enum):
    CRITICAL = "CRITICAL"
    HIGH = "HIGH"
    MEDIUM = "MEDIUM"
    LOW = "LOW"

class GuardrailStatus(str, Enum):
    GREEN = "GREEN"
    YELLOW = "YELLOW"
    ORANGE = "ORANGE"
    RED = "RED"

class RegimeType(str, Enum):
    BULL = "Bull"
    BEAR = "Bear"
    HIGH_VOL = "HighVol"
    CRISIS = "Crisis"
    RECOVERY = "Recovery"

class OrderType(str, Enum):
    MARKET = "MARKET"
    LIMIT = "LIMIT"
    STOP = "STOP"
    TWAP = "TWAP"
    VWAP = "VWAP"


# =============================================================================
# QUALITY & PROVENANCE (Audit Layer)
# =============================================================================

class Quality(BaseModel):
    """Data quality indicators for audit."""
    staleness_sec: int = Field(0, description="Seconds since last update")
    missing_pct: float = Field(0.0, description="Percentage of missing data")
    confidence: float = Field(1.0, ge=0, le=1, description="Confidence score")
    warnings: List[str] = Field(default_factory=list)

class Provenance(BaseModel):
    """Data provenance for audit trail."""
    retrieved_at: str = Field(default_factory=lambda: datetime.utcnow().isoformat())
    source: str = Field("", description="Data source identifier")
    transforms: List[str] = Field(default_factory=list)


# =============================================================================
# CORE POSITION & PORTFOLIO
# =============================================================================

class Position(BaseModel):
    """Single portfolio position with full metrics."""
    ticker: str
    name: str = ""
    shares: float
    price: float = Field(..., description="Last price")
    market_value: float = Field(..., description="Market value")
    weight: float = Field(..., ge=0, le=1, description="Portfolio weight")
    cost_basis: float = 0.0
    pnl: float = 0.0
    pnl_pct: float = 0.0
    sector: str = "Unknown"
    region: str = "US"
    beta: float = 1.0
    exit_days: float = Field(1.0, description="Days to exit position")
    risk_contribution: float = Field(0.0, description="% of portfolio risk")
    
class PortfolioSnapshot(BaseModel):
    """Complete portfolio state at a point in time."""
    id: str = ""
    as_of: str = Field(..., description="ISO timestamp")
    hash: str = Field("", description="SHA-256 for integrity")
    nav: float = Field(..., description="Net asset value")
    cash: float = Field(0, description="Cash balance")
    positions: List[Position] = Field(default_factory=list)
    sector_weights: Dict[str, float] = Field(default_factory=dict)
    factor_exposures: Dict[str, float] = Field(default_factory=dict)
    quality: Quality = Field(default_factory=Quality)
    provenance: Provenance = Field(default_factory=Provenance)


# =============================================================================
# RISK METRICS
# =============================================================================

class RiskMetrics(BaseModel):
    """Portfolio risk metrics with full breakdown."""
    as_of: str
    vol_ann: float = Field(..., description="Annualized volatility")
    var_95: float = Field(..., description="95% VaR (negative)")
    cvar_95: float = Field(..., description="95% CVaR (Expected Shortfall)")
    max_dd: float = Field(..., description="Maximum drawdown")
    current_dd: float = Field(0, description="Current drawdown")
    beta: float = Field(1.0, description="Beta to benchmark")
    sharpe: float = Field(0, description="Sharpe ratio")
    sortino: float = Field(0, description="Sortino ratio")
    treynor: float = Field(0, description="Treynor ratio")
    information_ratio: float = Field(0, description="Information ratio")
    tracking_error: float = Field(0, description="Tracking error")
    risk_contributions: Dict[str, float] = Field(default_factory=dict)
    factor_risks: Dict[str, float] = Field(default_factory=dict)
    quality: Quality = Field(default_factory=Quality)


# =============================================================================
# FEATURE 1: PORTFOLIO BRAIN
# =============================================================================

class RiskItem(BaseModel):
    """Single risk item with impact analysis."""
    id: str
    name: str
    description: str
    impact: float = Field(..., description="Potential loss in $")
    probability: float = Field(..., ge=0, le=1)
    score: float = Field(..., description="Impact * probability")
    positions_affected: List[str] = Field(default_factory=list)
    time_horizon: str = ""
    mitigation_options: List[str] = Field(default_factory=list)

class StabilizerAction(BaseModel):
    """Risk-reducing action recommendation."""
    id: str
    action: str
    risk_reduction: float = Field(..., description="Expected risk reduction %")
    cost: float = Field(0, description="Transaction cost")
    efficiency: float = Field(..., description="Risk reduction / cost")
    confidence: float = Field(1.0, ge=0, le=1)
    blocked_by: Optional[str] = None
    
class BrainRecommendation(BaseModel):
    """Action recommendation with full context."""
    priority: int
    severity: Severity
    title: str
    current_state: str
    recommended_action: str
    expected_outcome: str
    confidence: float
    blockers: List[str] = Field(default_factory=list)

class PortfolioBrainOutput(BaseModel):
    """Complete Portfolio Brain output."""
    as_of: str
    executive_summary: str
    top_risks: List[RiskItem]
    stabilizers: List[StabilizerAction]
    recommendations: List[BrainRecommendation]
    change_vs_prior: Dict[str, Any] = Field(default_factory=dict)


# =============================================================================
# FEATURE 2: HEALTH METER
# =============================================================================

class HealthComponent(BaseModel):
    """Single health component with scoring."""
    name: str
    score: float = Field(..., ge=0, le=100)
    weight: float = Field(..., ge=0, le=1)
    penalty: float = Field(0, description="Penalty applied")
    current: float
    target: float
    status: str  # OK, CAUTION, BREACH

class HealthMeter(BaseModel):
    """Real-time health meter output."""
    score: float = Field(..., ge=0, le=100)
    smoothed_score: float = Field(..., ge=0, le=100)
    label: str  # EXCELLENT, GOOD, CAUTION, AT_RISK, CRITICAL
    components: List[HealthComponent]
    trend: str  # IMPROVING, STABLE, DETERIORATING
    breach_probability_30d: float = Field(0, ge=0, le=1)
    history: List[Dict[str, Any]] = Field(default_factory=list)


# =============================================================================
# FEATURE 3: STATES & SNAPSHOTS
# =============================================================================

class StateDelta(BaseModel):
    """Difference between two portfolio states."""
    from_id: str
    to_id: str
    from_date: str
    to_date: str
    nav_change: float
    nav_change_pct: float
    positions_added: List[str]
    positions_removed: List[str]
    positions_modified: List[Dict[str, Any]]
    metric_changes: Dict[str, Dict[str, float]]  # {metric: {old, new, delta}}
    magnitude: str  # TRIVIAL, MINOR, MODERATE, MAJOR, CRITICAL

class RevertSimulation(BaseModel):
    """Simulation of state revert impact."""
    target_snapshot_id: str
    trades_required: List[Dict[str, Any]]
    transaction_cost: float
    slippage_estimate: float
    post_revert_risk: Dict[str, float]
    guardrail_violations: List[str]
    feasibility: str  # HIGH, MODERATE, LOW
    

# =============================================================================
# FEATURE 4: FINGERPRINT
# =============================================================================

class PortfolioFingerprint(BaseModel):
    """Style fingerprint vector with drift analysis."""
    as_of: str
    factor_exposures: Dict[str, float]  # market, size, value, momentum, quality
    sector_weights: Dict[str, float]
    region_weights: Dict[str, float]
    volatility_posture: float
    liquidity_posture: float
    drift_from_baseline: float
    drift_components: Dict[str, float]  # which dimensions contributed to drift
    style_consistency_score: float


# =============================================================================
# FEATURES 5-10: RISK WIRING
# =============================================================================

class CentralityMetrics(BaseModel):
    """Network centrality for cross-impact."""
    ticker: str
    degree: float
    eigenvector: float
    betweenness: float
    pagerank: float
    systemic_score: float

class Cluster(BaseModel):
    """Correlation cluster."""
    id: int
    assets: List[str]
    total_weight: float
    internal_correlation: float
    external_correlation: float
    fragility_score: float

class CrossImpactOutput(BaseModel):
    """Cross-impact matrix analysis output."""
    correlation_matrix: List[List[float]]
    tickers: List[str]
    centrality: List[CentralityMetrics]
    clusters: List[Cluster]
    top_connectors: List[str]
    correlation_stability: Dict[str, float]

class LiquidityPosition(BaseModel):
    """Liquidity analysis per position."""
    ticker: str
    market_value: float
    adv: float
    exit_days_normal: float
    exit_days_stress: float
    spread_cost: float
    total_haircut: float
    liquidity_score: float
    status: str  # LIQUID, MODERATE, ILLIQUID, VERY_ILLIQUID

class LiquidityMap(BaseModel):
    """Portfolio liquidity analysis."""
    positions: List[LiquidityPosition]
    portfolio_score: float
    portfolio_percentile: float
    bottlenecks: List[str]
    exit_distribution: Dict[str, float]  # {bucket: pct}
    stress_test: Dict[str, Any]

class ConcentrationMetrics(BaseModel):
    """Crowding and concentration analysis."""
    hhi: float
    effective_n: float
    entropy: float
    diversification_ratio: float
    correlation_adjusted_hhi: float
    top_5_concentration: float
    sector_concentration: Dict[str, float]
    factor_concentration: Dict[str, float]
    crowding_alerts: List[str]

class DrawdownAttribution(BaseModel):
    """Drawdown attribution analysis."""
    period_start: str
    period_end: str
    total_drawdown: float
    position_contributions: Dict[str, float]
    sector_contributions: Dict[str, float]
    factor_contributions: Dict[str, float]
    top_loss_drivers: List[Dict[str, Any]]
    sensitivity_matrix: Dict[str, Dict[str, float]]

class Guardrail(BaseModel):
    """Single guardrail definition and status."""
    id: str
    name: str
    type: str  # position, sector, factor, risk, leverage, liquidity
    limit: float
    current: float
    utilization: float
    status: GuardrailStatus
    buffer: float
    days_to_breach: Optional[float] = None
    breach_probability: float = 0.0

class GuardrailsOutput(BaseModel):
    """Full guardrails status."""
    guardrails: List[Guardrail]
    system_stress_score: float
    breaches: List[str]
    near_breaches: List[str]
    blocked_actions: List[Dict[str, Any]]

class Alert(BaseModel):
    """Portfolio alert."""
    id: str
    severity: Severity
    category: str
    message: str
    evidence: List[str]
    timestamp: str
    status: str  # NEW, ACKNOWLEDGED, IN_PROGRESS, RESOLVED
    related_alerts: List[str] = Field(default_factory=list)
    
class AlertsOutput(BaseModel):
    """Alerts system output."""
    active_alerts: List[Alert]
    alert_count_by_severity: Dict[str, int]
    false_positive_rate: float
    escalation_required: List[str]


# =============================================================================
# FEATURES 11-12: REGIMES & SCENARIOS
# =============================================================================

class RegimeState(BaseModel):
    """Current regime classification."""
    current_regime: RegimeType
    confidence: float
    days_in_regime: int
    persistence_score: float
    transition_probabilities: Dict[str, float]
    drivers: Dict[str, float]  # which indicators drove classification

class RegimeConditionalStats(BaseModel):
    """Performance stats by regime."""
    regime: RegimeType
    days: int
    return_ann: float
    volatility: float
    sharpe: float
    max_dd: float
    win_rate: float

class RegimeOutput(BaseModel):
    """Weather station output."""
    current: RegimeState
    history: List[Dict[str, Any]]
    stats_by_regime: List[RegimeConditionalStats]
    transition_matrix: List[List[float]]
    what_works: Dict[str, Dict[str, str]]  # {strategy: {regime: performance}}

class ShockImpact(BaseModel):
    """Impact of shock on single position."""
    ticker: str
    direct_impact: float
    first_order: float
    second_order: float
    total_impact: float
    pct_of_loss: float
    confidence: float

class ShockPropagationResult(BaseModel):
    """Shock simulation result."""
    shock_config: Dict[str, float]
    total_loss: float
    total_loss_pct: float
    position_impacts: List[ShockImpact]
    nav_path: List[Dict[str, float]]  # by propagation order
    confidence_decay: List[float]
    liquidity_haircut: float


# =============================================================================
# FEATURES 13-17: STRATEGY & BACKTESTING
# =============================================================================

class StrategyDefinition(BaseModel):
    """Strategy slot definition."""
    id: str
    name: str
    description: str
    allowed_instruments: List[str]
    sector_limits: Dict[str, float]
    factor_targets: Dict[str, float]
    risk_budget: float
    guardrails: List[str]
    active: bool = True

class BacktestResult(BaseModel):
    """Strategy backtest output."""
    strategy_id: str
    start_date: str
    end_date: str
    nav_series: List[Dict[str, float]]
    total_return: float
    cagr: float
    volatility: float
    sharpe: float
    max_drawdown: float
    calmar: float
    win_rate: float
    regime_performance: Dict[str, Dict[str, float]]
    guardrail_breaches: int
    robustness_score: float

class DecisionPathResult(BaseModel):
    """Decision path backtest output."""
    actual_nav: float
    alternate_navs: Dict[str, float]  # by shift
    regret_total: float
    opportunity_costs: List[Dict[str, Any]]
    timing_sensitivity: Dict[str, float]
    robustness_score: float

class DivergenceReport(BaseModel):
    """Strategy vs reality divergence."""
    strategy_id: str
    drift_score: float
    exposure_mismatches: Dict[str, Dict[str, float]]  # {exposure: {strategy, actual, delta}}
    violations: List[str]
    days_since_alignment: int
    adherence_score: float


# =============================================================================
# FEATURES 18-21: TRADING & EXECUTION
# =============================================================================

class OrderTicket(BaseModel):
    """Trade order ticket."""
    action: Literal["BUY", "SELL"]
    ticker: str
    quantity: float
    order_type: OrderType = OrderType.MARKET
    limit_price: Optional[float] = None
    time_in_force: str = "DAY"

class TradeImpact(BaseModel):
    """Pre-trade impact analysis."""
    ticket: OrderTicket
    estimated_cost: float
    commission: float
    new_weight: float
    sector_impact: Dict[str, float]
    risk_impact: Dict[str, float]
    guardrail_status: List[Dict[str, Any]]
    approved: bool
    blocked_reason: Optional[str] = None
    slippage_estimate: float = 0.0
    market_impact: float = 0.0

class TradeResult(BaseModel):
    """Executed trade result."""
    order_id: str
    ticker: str
    action: str
    quantity: float
    fill_price: float
    fill_time: str
    commission: float
    status: str  # FILLED, PARTIAL, CANCELLED, REJECTED

class BasketTrade(BaseModel):
    """Basket trade for rebalancing."""
    trades: List[OrderTicket]
    total_buys: float
    total_sells: float
    net_cash_flow: float
    transaction_cost: float
    risk_improvement: Dict[str, float]
    execution_priority: List[str]

class Opportunity(BaseModel):
    """Alpha opportunity from radar."""
    ticker: str
    sector: str
    fit_score: float
    alpha_estimate: float
    volatility: float
    correlation_to_portfolio: float
    max_weight: float
    risk_impact: Dict[str, float]
    drift_warning: Optional[str] = None
    confidence: float


# =============================================================================
# FEATURES 22-24: HEDGING
# =============================================================================

class HedgeInstrument(BaseModel):
    """Hedge instrument details."""
    ticker: str
    name: str = ""
    type: str  # inverse_etf, volatility, commodity, bond
    beta: float = -1.0
    correlation_to_portfolio: float = -0.5
    current_price: float = 0.0
    implied_vol: float = 0.25
    cost_to_hedge: float = 0.0
    effectiveness: float = 0.5

class HedgeBasket(BaseModel):
    """Hedge basket composition."""
    instruments: List[HedgeInstrument]
    total_coverage: float
    total_cost: float
    cost_benefit_ratio: float
    scenario_responses: Dict[str, float]

class HedgeDecay(BaseModel):
    """Hedge rebalancing clock output."""
    current_coverage: float
    target_coverage: float
    coverage_decay_rate: float
    days_to_threshold: float
    urgency_score: float
    missed_protection_cost: float
    rebalance_recommended: bool

class HedgePnLAttribution(BaseModel):
    """Hedge P&L attribution."""
    period_start: str
    period_end: str
    core_pnl: float
    hedge_pnl: float
    net_pnl: float
    cost_of_insurance: float
    stress_effectiveness: float
    net_benefit_score: float


# =============================================================================
# FEATURES 25-29: BEHAVIORAL & AUDIT
# =============================================================================

class CounterfactualResult(BaseModel):
    """Counterfactual portfolio comparison."""
    real_nav: float
    shadow_nav: float
    regret: float
    opportunity_cost: float
    bias_classification: str  # EXECUTION_LAG, FEAR, GREED, DISCIPLINE
    delay_impact: float

class ContributionTimeline(BaseModel):
    """Rolling contribution replay."""
    period: str
    ticker: str
    contribution: float
    cumulative: float
    rank: int

class ReturnPathMetrics(BaseModel):
    """Return path analysis."""
    drawdown_depths: List[float]
    recovery_times: List[int]
    ulcer_index: float
    pain_index: float
    path_smoothness: float
    fragility_score: float

class DisciplineScore(BaseModel):
    """Audit and discipline scoring."""
    overall_score: float
    consistency_score: float
    rule_adherence: float
    timing_discipline: float
    size_discipline: float
    violations: List[Dict[str, Any]]
    improvement_areas: List[str]

class SanityCheckResult(BaseModel):
    """Post-trade sanity check."""
    trade_id: str
    delta_exposure: Dict[str, float]
    guardrail_compliance: bool
    risk_change_explanation: str
    confirmed: bool
    audit_record: str


# =============================================================================
# ADDITIONAL MODELS FOR SERVICES
# =============================================================================

# Strategy Service Models
class StrategySlot(BaseModel):
    """Active strategy slot."""
    slot_id: str
    strategy_id: str
    name: str
    description: str = ""
    status: str = "ACTIVE"  # ACTIVE, INACTIVE, PAUSED
    weight: float = 1.0
    parameters: Dict[str, Any] = Field(default_factory=dict)
    activated_at: str = ""

class StrategyRun(BaseModel):
    """Strategy backtest run result."""
    run_id: str
    strategy_id: str
    start_date: str
    end_date: str
    total_return: float
    sharpe: float
    max_drawdown: float
    volatility: float
    win_rate: float = 0.5
    trades_count: int = 0
    turnover: float = 0.0
    nav_series: List[float] = Field(default_factory=list)
    status: str = "COMPLETED"
    quality: Quality = Field(default_factory=Quality)

class DivergenceMetrics(BaseModel):
    """Strategy vs portfolio divergence."""
    weight_divergence: float
    return_divergence: float
    tracking_error: float
    drift_by_position: List[Dict[str, Any]] = Field(default_factory=list)
    rebalance_urgency: str = "LOW"  # LOW, MEDIUM, HIGH
    last_rebalance: Optional[str] = None
    days_since_rebalance: int = 0

# Hedging Service Models (extended)
class HedgeRecommendation(BaseModel):
    """Hedge recommendation."""
    strategy: str
    instruments: List[str]
    weights: Dict[str, float]
    expected_protection: float
    estimated_cost: float
    confidence: float

class HedgeResponse(BaseModel):
    """Complete hedge response analysis."""
    portfolio_beta: float
    current_hedge_ratio: float
    target_protection: float
    available_instruments: List[Any] = Field(default_factory=list)
    recommendations: List[HedgeRecommendation] = Field(default_factory=list)
    active_hedges: List[Any] = Field(default_factory=list)

class HedgeClock(BaseModel):
    """Hedge rebalancing clock."""
    current_effectiveness: float
    target_effectiveness: float
    decay_rate: float
    days_to_threshold: int
    rebalance_urgency: str  # LOW, MEDIUM, HIGH
    recommended_action: str
    optimal_schedule: List[Dict[str, Any]] = Field(default_factory=list)

class HedgeLeg(BaseModel):
    """Single hedge position."""
    ticker: str
    name: str = ""
    shares: float
    entry_price: float
    current_price: float
    beta: float = -1.0
    weight: float = 0.0
    entry_date: str = ""
    pnl: float = 0.0
    pnl_pct: float = 0.0

class HedgePnL(BaseModel):
    """Hedge P&L analysis."""
    total_hedge_value: float
    total_hedge_pnl: float
    total_hedge_pnl_pct: float
    legs: List[Dict[str, Any]] = Field(default_factory=list)
    cost_of_carry_daily: float = 0.0
    cost_of_carry_mtd: float = 0.0
    effectiveness_vs_loss: float = 0.0
    portfolio_loss_offset: float = 0.0

# Audit Service Models
class CounterfactualScenario(BaseModel):
    """Counterfactual what-if scenario."""
    scenario_type: str
    description: str
    actual_return: float
    hypothetical_return: float
    return_delta: float
    actual_pnl: float
    hypothetical_pnl: float
    position_deltas: List[Dict[str, Any]] = Field(default_factory=list)
    confidence: float = 0.5
    assumptions: List[str] = Field(default_factory=list)

class ContributionPeriod(BaseModel):
    """Rolling contribution period."""
    period_start: str
    period_end: str
    total_return: float
    contributions: Dict[str, float]
    top_contributors: List[str]
    bottom_contributors: List[str]
    attribution_quality: float = 0.8

class ReturnPath(BaseModel):
    """Return path decomposition."""
    period_start: str
    period_end: str
    total_return: float
    skill_component: float
    luck_component: float
    risk_component: float
    cost_component: float
    market_component: float
    daily_path: List[Dict[str, Any]] = Field(default_factory=list)
    confidence_intervals: Dict[str, List[float]] = Field(default_factory=dict)

class AuditEntry(BaseModel):
    """Audit log entry."""
    timestamp: str
    action: str
    entity_type: str
    entity_id: str
    changes: Dict[str, Any]
    change_hash: str
    user: str = "system"
    session_id: str = ""
    ip_address: str = ""

class PostTradeCheck(BaseModel):
    """Post-trade sanity check result."""
    trade_id: str
    timestamp: str
    checks: List[Dict[str, Any]]
    warnings: List[str]
    errors: List[str]
    overall_status: str  # PASSED, PASSED_WITH_WARNINGS, FAILED
    remediation_actions: List[str] = Field(default_factory=list)
    quality: Quality = Field(default_factory=Quality)


# =============================================================================
# API RESPONSE WRAPPERS
# =============================================================================

class PortfolioResponse(BaseModel):
    """Generic portfolio API response."""
    success: bool = True
    data: Any
    quality: Quality = Field(default_factory=Quality)
    provenance: Provenance = Field(default_factory=Provenance)
    error: Optional[str] = None
