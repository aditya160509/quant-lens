"""
Macro Lab - Data Contracts
Shared types for DataAdapter, Provenance, and Quality
"""

from pydantic import BaseModel
from typing import List, Dict, Optional, Any
from datetime import datetime
from enum import Enum


class RegimeLabel(str, Enum):
    RISK_ON = "risk_on"
    RISK_OFF = "risk_off"
    INFLATION_UP = "inflation_up"
    INFLATION_DOWN = "inflation_down"
    GROWTH_UP = "growth_up"
    GROWTH_DOWN = "growth_down"
    LIQUIDITY_UP = "liquidity_up"
    LIQUIDITY_DOWN = "liquidity_down"


class Provenance(BaseModel):
    source_name: str
    source_url: str
    retrieved_at: datetime
    fields_covered: List[str]
    license_note: Optional[str] = None


class Quality(BaseModel):
    missing_pct: float
    staleness_sec: int
    revision_flag: bool = False
    warnings: List[str] = []


class SeriesMeta(BaseModel):
    timezone: str = "UTC"
    units: str
    frequency: str  # "1m", "5m", "1d", "1w", "1mo"
    revision_policy: str = "none"


class TimeSeriesPoint(BaseModel):
    t: int  # Unix timestamp
    fields: Dict[str, float]


class DataAdapterResponse(BaseModel):
    """Standard response contract for all macro data"""
    series: List[TimeSeriesPoint]
    meta: SeriesMeta
    provenance: List[Provenance]
    quality: Quality


# =============================================================================
# Model Output Contracts
# =============================================================================

class Driver(BaseModel):
    name: str
    contribution: float  # -100 to 100
    direction: str  # "up", "down", "neutral"
    confidence: float  # 0-1


class Explanation(BaseModel):
    summary: str
    drivers: List[Driver]
    evidence_refs: List[str] = []


class ModelOutput(BaseModel):
    """Standard response for POST /api/macro/model/run"""
    outputs: Dict[str, Any]
    explanations: List[Explanation]
    evidence: List[Dict[str, Any]]
    provenance: List[Provenance]
    quality: Quality


# =============================================================================
# Regime Contract
# =============================================================================

class RegimeOutput(BaseModel):
    label: RegimeLabel
    transition_probability: float
    stability_score: float  # 0-100
    top_drivers: List[Driver]
    pca_factors: Dict[str, float]  # factor_name -> current value


# =============================================================================
# Module-Specific Contracts
# =============================================================================

class ShockNetworkNode(BaseModel):
    id: str
    name: str
    layer: str  # Macro, Rates, FX, Credit, Equities, Commodities
    impact_now: float
    peak_impact: float
    vulnerability: float


class ShockNetworkEdge(BaseModel):
    source: str
    target: str
    strength: float
    delay_bars: int
    confidence: float
    direction: str  # "lead", "lag", "concurrent"


class ShockNetworkOutput(BaseModel):
    nodes: List[ShockNetworkNode]
    edges: List[ShockNetworkEdge]
    propagation_paths: List[Dict[str, Any]]
    vulnerability_ranking: List[Dict[str, Any]]


class EarthquakeOutput(BaseModel):
    composite_score: float  # 0-100
    state_label: str  # Calm, Tension, Warning, Active
    rates_stress: float
    fx_stress: float
    credit_stress: float
    liquidity_stress: float
    acceleration: float
    analogs: List[Dict[str, Any]]


class CBIntentOutput(BaseModel):
    bank: str
    intent_score: float  # -100 (dove) to 100 (hawk)
    confidence_score: float  # 0-100
    uncertainty_score: float
    key_sentences: List[str]
    topic_weights: Dict[str, float]
    pivot_detected: bool


class ProbMatrixCell(BaseModel):
    growth_state: str
    inflation_state: str
    probability: float
    confidence: float
    top_drivers: List[Driver]


class ProbMatrixOutput(BaseModel):
    cells: List[ProbMatrixCell]
    regime_conditional: bool
    calibration_score: float


class AlignmentOutput(BaseModel):
    alignment_score: float  # 0-100
    alignment_label: str  # aligned, mixed, conflicting
    pillars: Dict[str, float]  # inflation, growth, credit, liquidity, policy
    out_of_sync: List[str]
    transition_warning: float


class HeatmapCountry(BaseModel):
    country_code: str
    country_name: str
    health_score: float
    fragility_score: float
    drivers: List[Driver]
    momentum: float  # deterioration speed


class HeatmapOutput(BaseModel):
    countries: List[HeatmapCountry]
    overlays_available: List[str]


class MacroEvent(BaseModel):
    id: str
    timestamp: int
    region: str
    event_type: str
    title: str
    importance_score: float
    surprise_magnitude: Optional[float] = None
    market_reaction: Optional[float] = None


class EventsTimelineOutput(BaseModel):
    upcoming: List[MacroEvent]
    past: List[MacroEvent]
    stress_cluster_alert: bool


class LiquidityOutput(BaseModel):
    liquidity_index: float
    phase_label: str  # expansion, contraction, inflection
    cb_contributions: Dict[str, float]  # fed, ecb, boj, rbi
    turning_point_prob: float
    asset_lag_map: Dict[str, int]


class CommodityTile(BaseModel):
    symbol: str
    name: str
    group: str  # energy, industrial_metals, precious, agri
    price_trend: str
    regime_tag: str
    macro_signal: str
    curve_shape: Optional[str] = None


class CommoditiesOutput(BaseModel):
    tiles: List[CommodityTile]
    inflation_signal: float
    growth_demand: float
    supply_shock_flags: List[str]


class YieldCurvePoint(BaseModel):
    country: str
    tenor: str
    yield_value: float


class YieldCurveOutput(BaseModel):
    curves: Dict[str, List[YieldCurvePoint]]
    regime_labels: Dict[str, str]  # country -> regime
    inversion_scores: Dict[str, float]
    recession_probs: Dict[str, float]
    sync_index: float


# =============================================================================
# API Response Models (for macro.py endpoints)
# =============================================================================

class MacroSeriesResponse(BaseModel):
    """Response for series data endpoints"""
    series: List[TimeSeriesPoint]
    meta: Optional[SeriesMeta] = None
    provenance: Optional[List[Provenance]] = None
    quality: Optional[Quality] = None


class MacroRegime(BaseModel):
    """Current regime information"""
    label: str
    probability: float
    drivers: List[Dict[str, Any]] = []


class MacroModelResponse(BaseModel):
    """Standard response for POST /api/macro/model/run"""
    outputs: Dict[str, Any]
    explanation: Optional[Dict[str, Any]] = None
    drivers: List[Dict[str, Any]] = []
    summary: Optional[str] = None
    evidence: List[Dict[str, Any]] = []
    provenance: List[Dict[str, Any]] = []
    quality: Dict[str, Any] = {}
