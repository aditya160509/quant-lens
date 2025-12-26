"""
Portfolio God Mode - Data Contracts
Pydantic models for all Portfolio God Mode endpoints
"""
from pydantic import BaseModel, Field
from typing import List, Dict, Optional, Any, Literal
from datetime import datetime


# =============================================================================
# CORE DATA MODELS
# =============================================================================

class TimeSeriesPoint(BaseModel):
    """Single point in a time series."""
    t: str = Field(..., description="Date in YYYY-MM-DD format")
    v: float = Field(..., description="Value")


class Quality(BaseModel):
    """Data quality indicators for audit."""
    stalenessSec: int = Field(0, description="Seconds since last update")
    missingPct: float = Field(0.0, description="Percentage of missing data points")
    revisionFlag: bool = Field(False, description="True if data was revised")
    warnings: List[str] = Field(default_factory=list)


class Provenance(BaseModel):
    """Data provenance for audit trail."""
    retrievedAt: str = Field(..., description="ISO timestamp of retrieval")
    sourceUrl: str = Field("", description="Source URL or identifier")
    transform: List[str] = Field(default_factory=list, description="Transforms applied")


class TimeSeries(BaseModel):
    """Full time series with metadata and quality."""
    id: str
    name: str
    freq: Literal["D", "W", "M", "Q", "A"] = "D"
    unit: str = ""
    points: List[TimeSeriesPoint]
    meta: Dict[str, str] = Field(default_factory=dict)
    quality: Quality = Field(default_factory=Quality)
    provenance: Provenance = Field(default_factory=lambda: Provenance(retrievedAt=datetime.utcnow().isoformat()))


# =============================================================================
# PORTFOLIO MODELS
# =============================================================================

class Position(BaseModel):
    """Single portfolio position with full attributes."""
    ticker: str
    name: str
    qty: float
    px: float = Field(..., description="Last price")
    mv: float = Field(..., description="Market value")
    weight: float = Field(..., description="Portfolio weight 0-1")
    sector: str = Field("Unknown", description="GICS sector")
    region: str = Field("US", description="Region code")
    beta: float = Field(1.0, description="Beta to benchmark")
    pnl: float = Field(0.0, description="Unrealized P&L")


class Benchmark(BaseModel):
    """Benchmark definition."""
    id: str
    name: str


class PortfolioSnapshot(BaseModel):
    """Complete portfolio state at a point in time."""
    asOf: str = Field(..., description="Date in YYYY-MM-DD format")
    baseCcy: str = "USD"
    nav: float = Field(..., description="Net asset value")
    cash: float = Field(..., description="Cash balance")
    positions: List[Position]
    benchmarks: List[Benchmark] = Field(default_factory=list)
    quality: Quality = Field(default_factory=Quality)
    provenance: Provenance = Field(default_factory=lambda: Provenance(retrievedAt=datetime.utcnow().isoformat()))


# =============================================================================
# RISK MODELS
# =============================================================================

class RiskMetrics(BaseModel):
    """Portfolio risk metrics with audit."""
    asOf: str
    volAnn: float = Field(..., description="Annualized volatility")
    var95: float = Field(..., description="95% VaR (negative)")
    cvar95: float = Field(..., description="95% CVaR (negative)")
    maxDd: float = Field(..., description="Max drawdown (negative)")
    beta: float = Field(..., description="Portfolio beta")
    corrAvg: float = Field(..., description="Average pairwise correlation")
    liqScore: int = Field(..., description="Liquidity score 0-100")
    quality: Quality = Field(default_factory=Quality)
    explain: List[str] = Field(default_factory=list, description="Risk explanations")


# =============================================================================
# DRIVERS AND EXPLANATION MODELS
# =============================================================================

class Driver(BaseModel):
    """Single driver/contributor to a metric."""
    name: str
    direction: Literal["Up", "Down", "Flat"] = "Flat"
    magnitude: float = 0.0
    contribution: float = 0.0
    confidence: float = 1.0
    explain: str = ""
    evidence: List[str] = Field(default_factory=list)


class DriversTable(BaseModel):
    """Table of drivers/contributors."""
    rows: List[Driver]


class ExplainPacket(BaseModel):
    """Explanation packet for audit and transparency."""
    summary: str = ""
    assumptions: List[str] = Field(default_factory=list)
    inputsUsed: List[str] = Field(default_factory=list)
    limitations: List[str] = Field(default_factory=list)


# =============================================================================
# ALERTS
# =============================================================================

class Alert(BaseModel):
    """Portfolio alert."""
    id: str
    severity: Literal["Low", "Med", "High"]
    message: str
    evidence: List[str] = Field(default_factory=list)
    timestamp: str = Field(default_factory=lambda: datetime.utcnow().isoformat())


class AlertsResponse(BaseModel):
    """Alerts response."""
    alerts: List[Alert]
    quality: Quality = Field(default_factory=Quality)


# =============================================================================
# STATE MANAGEMENT
# =============================================================================

class PortfolioState(BaseModel):
    """Saved portfolio state."""
    stateId: str
    name: str
    createdAt: str
    notes: str = ""
    overrides: Dict[str, Any] = Field(default_factory=dict)


class SaveStateRequest(BaseModel):
    """Request to save portfolio state."""
    stateId: Optional[str] = None
    name: str
    notes: str = ""
    overrides: Dict[str, Any] = Field(default_factory=dict)


class SaveStateResponse(BaseModel):
    """Response after saving state."""
    ok: bool
    stateId: str


class StateListResponse(BaseModel):
    """List of saved states."""
    states: List[PortfolioState]


# =============================================================================
# TIMESERIES RESPONSE
# =============================================================================

class TimeseriesResponse(BaseModel):
    """Response for timeseries endpoint."""
    nav: TimeSeries
    bench: List[TimeSeries] = Field(default_factory=list)
    factors: List[TimeSeries] = Field(default_factory=list)
    quality: Quality = Field(default_factory=Quality)


# =============================================================================
# BACKTEST
# =============================================================================

class BacktestRequest(BaseModel):
    """Backtest run request."""
    stateId: str = ""
    window: Literal["1Y", "3Y", "5Y", "MAX"] = "1Y"
    rebalance: Literal["M", "Q"] = "Q"
    costBps: float = 0.0
    slippageBps: float = 0.0


class BacktestResponse(BaseModel):
    """Backtest run response."""
    runId: str
    nav: TimeSeries
    risk: RiskMetrics
    drivers: DriversTable
    explain: ExplainPacket
    quality: Quality = Field(default_factory=Quality)


# =============================================================================
# SCENARIO
# =============================================================================

class ScenarioRequest(BaseModel):
    """Scenario run request."""
    scenarioIds: List[str]
    stackMode: Literal["add", "max", "custom"] = "add"
    horizon: Literal["1W", "1M", "3M"] = "1M"


class ScenarioImpact(BaseModel):
    """Scenario impact summary."""
    navPct: float = Field(..., description="NAV impact percentage")
    ddPct: float = Field(..., description="Drawdown impact percentage")


class ScenarioResponse(BaseModel):
    """Scenario run response."""
    impact: ScenarioImpact
    byPosition: DriversTable
    hedgeSuggestions: DriversTable
    explain: ExplainPacket
    quality: Quality = Field(default_factory=Quality)


# =============================================================================
# HEDGE
# =============================================================================

class HedgeApplyRequest(BaseModel):
    """Hedge apply request."""
    scenarioRunId: str = ""
    hedgeId: str
    budgetPct: float = 0.01


class Trade(BaseModel):
    """Single trade in a basket."""
    ticker: str
    qty: int
    side: Literal["BUY", "SELL"]


class SanityCheck(BaseModel):
    """Sanity check after trade."""
    drivers: DriversTable
    warnings: List[str] = Field(default_factory=list)
    guardrailViolations: List[str] = Field(default_factory=list)


class HedgeApplyResponse(BaseModel):
    """Hedge apply response."""
    tradeBasket: List[Trade]
    post: PortfolioSnapshot
    sanity: SanityCheck


# =============================================================================
# TRADE BASKET
# =============================================================================

class Allocation(BaseModel):
    """Target allocation."""
    ticker: str
    weight: float


class TradeBasketRequest(BaseModel):
    """Trade basket request."""
    allocations: List[Allocation]
    cashGuard: float = 0.02


class TradeBasketResponse(BaseModel):
    """Trade basket response."""
    tradeBasket: List[Trade]
    post: PortfolioSnapshot
    sanity: SanityCheck


# =============================================================================
# EXPORT
# =============================================================================

class ExportRequest(BaseModel):
    """Export request."""
    type: Literal["png", "csv", "json"]
    moduleId: str
    payload: Dict[str, Any] = Field(default_factory=dict)


class ExportResponse(BaseModel):
    """Export response."""
    ok: bool
    url: str = ""
    data: Optional[Any] = None


# =============================================================================
# HEALTH METER
# =============================================================================

class HealthMeterResponse(BaseModel):
    """Health meter response for Feature 21."""
    score: int = Field(..., description="Health score 0-100")
    label: Literal["Excellent", "Good", "Fair", "Poor", "Critical"]
    components: Dict[str, float] = Field(default_factory=dict)
    drivers: DriversTable
    quality: Quality = Field(default_factory=Quality)
