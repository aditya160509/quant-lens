"""
Research Schemas
Pydantic models for request/response validation in research endpoints.
"""

from pydantic import BaseModel, Field, validator
from typing import List, Dict, Optional, Literal, Any
from enum import Enum


# ===== Error Response =====

class ErrorDetail(BaseModel):
    """Structured error detail."""
    code: str = Field(..., description="Error code like INVALID_INPUT, NOT_FOUND")
    message: str = Field(..., description="Human-readable error message")
    details: Dict[str, Any] = Field(default_factory=dict, description="Additional error details")


class ErrorResponse(BaseModel):
    """Standard error response wrapper."""
    error: ErrorDetail


# ===== Cache Metadata =====

class CacheMeta(BaseModel):
    """Cache metadata included in every response."""
    cache_hit: bool = Field(..., description="Whether result was served from cache")
    computed_at: str = Field(..., description="ISO timestamp of computation")


# ===== Common Enums =====

class ReturnsType(str, Enum):
    LOG = "log"
    SIMPLE = "simple"


class AlignmentMode(str, Enum):
    INTERSECTION = "intersection"
    UNION = "union"


class CorrelationMethod(str, Enum):
    PEARSON = "pearson"
    SPEARMAN = "spearman"


class RegimeModelType(str, Enum):
    ZSCORE = "zscore"
    KMEANS = "kmeans"
    HMM = "hmm"
    RULE_BASED = "rule_based"


class ShockMode(str, Enum):
    SIGMA = "sigma"
    RAW = "raw"


# ===== D1: Rolling Beta =====

class RegressionConfig(BaseModel):
    """Configuration for regression computation."""
    mode: Literal["single_factor", "multi_factor"] = "single_factor"
    winsor_p: float = Field(default=0.01, ge=0, le=0.1)


class RollingBetaRequest(BaseModel):
    """Request for rolling beta computation."""
    tickers: List[str] = Field(..., min_length=1, description="List of ticker symbols")
    factors: List[str] = Field(default=["MKT"], description="List of factor names")
    windows: List[int] = Field(default=[20, 60, 120], description="Window sizes in days")
    lookback: int = Field(default=365, ge=30, le=2000, description="Lookback period in days")
    returns_type: ReturnsType = Field(default=ReturnsType.LOG)
    regression: RegressionConfig = Field(default_factory=RegressionConfig)
    include_series: bool = Field(default=False, description="Include time series in response")
    
    @validator('windows')
    def validate_windows(cls, v):
        if any(w < 10 for w in v):
            raise ValueError("Window size must be at least 10")
        return sorted(set(v))
    
    @validator('tickers')
    def validate_tickers(cls, v):
        return [t.upper().strip() for t in v if t.strip()]


class BetaQuality(BaseModel):
    """Quality metrics for a beta estimate."""
    r2: Optional[float] = None
    n: Optional[int] = None


class RollingBetaResponse(BaseModel):
    """Response for rolling beta computation."""
    meta: Dict[str, Any]
    matrix: Dict[str, Dict[str, Dict[str, Optional[float]]]]  # ticker -> factor -> window -> beta
    quality: Dict[str, Dict[str, Dict[str, BetaQuality]]]  # ticker -> factor -> window -> quality
    series: Optional[Dict[str, Dict[str, Dict[str, List[Dict[str, Any]]]]]] = None


class RollingBetaDetailRequest(BaseModel):
    """Request for single ticker/factor beta detail."""
    ticker: str
    factor: str
    window: int = Field(default=60, ge=10)
    lookback: int = Field(default=756, ge=30, le=2000)


# ===== D2: Macro Shock =====

class MacroModelConfig(BaseModel):
    """Configuration for macro shock model."""
    type: Literal["multivariate_ols"] = "multivariate_ols"
    winsor_p: float = Field(default=0.01, ge=0, le=0.1)
    ridge: float = Field(default=1e-6, ge=0)


class MacroShockRequest(BaseModel):
    """Request for macro shock propagation analysis."""
    tickers: List[str] = Field(..., min_length=1)
    drivers: List[str] = Field(..., min_length=1, description="Macro driver names")
    lookback: int = Field(default=756, ge=60, le=3000)
    returns_type: ReturnsType = Field(default=ReturnsType.LOG)
    shock_mode: ShockMode = Field(default=ShockMode.SIGMA)
    shocks: Dict[str, float] = Field(..., description="Driver name to shock magnitude")
    model: MacroModelConfig = Field(default_factory=MacroModelConfig)
    
    @validator('tickers')
    def validate_tickers(cls, v):
        return [t.upper().strip() for t in v if t.strip()]


class ImpactDetail(BaseModel):
    """Impact details for a single ticker."""
    total: float
    components: Dict[str, float]
    fit: Dict[str, Any]


class MacroShockResponse(BaseModel):
    """Response for macro shock analysis."""
    meta: Dict[str, Any]
    impacts: Dict[str, ImpactDetail]
    rankings: Dict[str, List[Dict[str, Any]]]


# ===== D3: Style Map =====

class StyleMapRequest(BaseModel):
    """Request for factor style map computation."""
    tickers: List[str] = Field(..., min_length=1)
    lookback: int = Field(default=252, ge=30, le=1000)
    x: str = Field(default="VALUE", description="X-axis factor")
    y: str = Field(default="MOMENTUM", description="Y-axis factor")
    color: str = Field(default="MKT", description="Color encoding factor")
    size: str = Field(default="VOL", description="Size encoding factor")
    standardize: Literal["cross_sectional_z", "raw"] = "cross_sectional_z"
    winsor_p: float = Field(default=0.01, ge=0, le=0.1)
    
    @validator('tickers')
    def validate_tickers(cls, v):
        return [t.upper().strip() for t in v if t.strip()]


class StyleMapPoint(BaseModel):
    """Single point in the style map."""
    ticker: str
    x: Optional[float] = None
    y: Optional[float] = None
    color: Optional[float] = None
    size: Optional[float] = None


class StyleMapResponse(BaseModel):
    """Response for style map computation."""
    meta: Dict[str, Any]
    points: List[StyleMapPoint]


# ===== D4: Regimes =====

class ZscoreThresholds(BaseModel):
    """Thresholds for zscore regime detection."""
    risk_on: float = Field(default=-0.5)
    risk_off: float = Field(default=0.5)


class RegimeModelConfig(BaseModel):
    """Configuration for regime detection model."""
    type: RegimeModelType = RegimeModelType.ZSCORE
    weights: Optional[Dict[str, float]] = None
    smooth_days: int = Field(default=5, ge=1, le=30)
    thresholds: ZscoreThresholds = Field(default_factory=ZscoreThresholds)
    n_clusters: int = Field(default=3, ge=2, le=5)  # For kmeans
    n_states: int = Field(default=3, ge=2, le=5)    # For HMM


class RegimesRequest(BaseModel):
    """Request for regime detection."""
    inputs: List[str] = Field(..., min_length=1, description="Input series names")
    lookback: int = Field(default=1095, ge=90, le=3650)
    model: RegimeModelConfig = Field(default_factory=RegimeModelConfig)


class CurrentRegime(BaseModel):
    """Current regime state."""
    date: str
    regime: str
    score: float
    confidence: float


class RegimesResponse(BaseModel):
    """Response for regime detection."""
    meta: Dict[str, Any]
    current: Optional[CurrentRegime] = None
    timeline: List[Dict[str, Any]]
    contributors: Dict[str, float]


# ===== D5: Correlation =====

class CorrelationMatrixRequest(BaseModel):
    """Request for correlation matrix computation."""
    tickers: List[str] = Field(..., min_length=2)
    windows: List[int] = Field(default=[30, 60, 90])
    returns_type: ReturnsType = Field(default=ReturnsType.LOG)
    method: CorrelationMethod = Field(default=CorrelationMethod.PEARSON)
    lookback: int = Field(default=365, ge=30, le=2000)
    
    @validator('tickers')
    def validate_tickers(cls, v):
        return [t.upper().strip() for t in v if t.strip()]
    
    @validator('windows')
    def validate_windows(cls, v):
        return sorted(set(v))


class CorrelationMatrixResponse(BaseModel):
    """Response for correlation matrix computation."""
    meta: Dict[str, Any]
    tickers: List[str]
    matrices: Dict[str, Dict[str, Dict[str, Optional[float]]]]  # window -> ticker -> ticker -> corr
    delta: Optional[Dict[str, Dict[str, Optional[float]]]] = None  # ticker -> ticker -> delta
    order: List[str]  # Optimal ordering from clustering


class CorrelationPairRequest(BaseModel):
    """Request for pair correlation drilldown."""
    a: str = Field(..., description="First ticker")
    b: str = Field(..., description="Second ticker")
    window: int = Field(default=60, ge=10)
    lookback: int = Field(default=756, ge=30, le=2000)
    
    @validator('a', 'b')
    def validate_ticker(cls, v):
        return v.upper().strip()


class CorrelationPairResponse(BaseModel):
    """Response for pair correlation drilldown."""
    meta: Dict[str, Any]
    series: List[Dict[str, Any]]  # [{date, corr}, ...]


# ===== Utility Functions =====

def make_error_response(code: str, message: str, details: Dict = None) -> dict:
    """Create a standard error response dict."""
    return {
        "error": {
            "code": code,
            "message": message,
            "details": details or {}
        }
    }
