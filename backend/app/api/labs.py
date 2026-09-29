from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import List, Optional, Dict, Any, Union
from app.services import labs
from app.services.regimes_intelligence import sanitize_dict
from datetime import datetime

router = APIRouter()

# --- Request Models ---
class FactorsRequest(BaseModel):
    ticker: str
    window_years: int = 3
    model: str = "ff3"

class VolatilityRequest(BaseModel):
    ticker: str
    window_years: int = 1

class RegimeRequest(BaseModel):
    ticker: str
    window_years: int = 3

class PCARequest(BaseModel):
    tickers: Optional[List[str]] = None

# --- Endpoints ---

@router.post("/factors")
def get_factors(req: FactorsRequest):
    res = labs.run_factor_regression(req.ticker, req.window_years, req.model)
    if "error" in res:
        raise HTTPException(status_code=400, detail=res["error"])
    return res

@router.post("/volatility")
def get_volatility(req: VolatilityRequest):
    res = labs.run_volatility_analysis(req.ticker, req.window_years)
    if "error" in res:
        raise HTTPException(status_code=400, detail=res["error"])
    return res


@router.post("/volatility/intelligence")
def get_volatility_intelligence(req: VolatilityRequest):
    """
    Main Volatility Command Center Controller.
    Returns all 13 institutional volatility features.
    """
    from app.services.volatility_intelligence import run_volatility_intelligence
    result = run_volatility_intelligence(req.ticker, req.window_years)
    return sanitize_dict(result)


# =============================================================================
# VOLATILITY INTELLIGENCE - Individual Feature Endpoints
# =============================================================================

class VolFeatureRequest(BaseModel):
    ticker: str
    window_years: int = 2

@router.post("/volatility/dna")
def get_vol_dna(req: VolFeatureRequest):
    from app.services.volatility_intelligence import compute_vol_dna
    return compute_vol_dna(req.ticker, req.window_years)

@router.post("/volatility/surface")
def get_vol_surface(req: VolFeatureRequest):
    from app.services.volatility_intelligence import compute_vol_surface
    return compute_vol_surface(req.ticker, req.window_years)

@router.post("/volatility/edge")
def get_vol_edge(req: VolFeatureRequest):
    from app.services.volatility_intelligence import compute_vol_edge
    return compute_vol_edge(req.ticker, req.window_years)

@router.post("/volatility/traps")
def get_vol_traps(req: VolFeatureRequest):
    from app.services.volatility_intelligence import compute_vol_traps
    return compute_vol_traps(req.ticker, req.window_years)

@router.post("/volatility/skew")
def get_vol_skew(req: VolFeatureRequest):
    from app.services.volatility_intelligence import compute_vol_skew
    return compute_vol_skew(req.ticker, req.window_years)

@router.post("/volatility/dispersion")
def get_vol_dispersion(req: VolFeatureRequest):
    from app.services.volatility_intelligence import compute_vol_dispersion
    return compute_vol_dispersion(window_years=req.window_years)

@router.post("/volatility/clusters")
def get_vol_clusters(req: VolFeatureRequest):
    from app.services.volatility_intelligence import compute_vol_clusters
    return compute_vol_clusters(req.ticker, req.window_years)

@router.post("/regimes")
def get_regimes(req: RegimeRequest):
    res = labs.run_regime_detection(req.ticker, req.window_years)
    if "error" in res:
        raise HTTPException(status_code=400, detail=res["error"])
    return res

@router.post("/pca/run")
def run_pca_engine(req: Dict[str, Any]):
    """
    God-Mode PCA Engine entry point.
    Maps frontend keys to backend universe keys.
    """
    from app.services.pca_god_mode import PCAGodModeEngine, PCAConfig
    
    universe_key = req.get("universeKey", "US")
    # Map frontend to backend
    mapping = {
        "US": "us_equities",
        "INDIA": "india_nse",
        "MACRO": "GLOBAL_MACRO",
        "ETF": "etfs"
    }
    backend_key = mapping.get(universe_key, universe_key)
    
    config = PCAConfig(
        universe_key=backend_key,
        lookback_days=req.get("lookbackDays", 252),
        rolling_enabled=req.get("rollingEnabled", False)
    )
    
    engine = PCAGodModeEngine(config)
    success = engine.compute()
    
    if not success:
        return {"error": "PCA computation failed. Check logs."}
        
    # Construct complete result set
    # (Simplified for now, can be expanded to match full God Mode spec)
    structure = engine.get_structure_metrics()
    factors = engine.get_factor_meanings()
    
    return {
        "pca_state": {
            "N": len(engine._tickers),
            "T": len(engine._returns),
            "window_days": config.lookback_days,
            "explained_variance": structure.explained_variance,
            "cumulative_variance": structure.cumulative_variance,
        },
        "features": {
            "collapse_gauge": {"values": {
                "collapse_score": structure.fragility_score,
                "pc1_share": structure.pc1_variance_share / 100,
                "state": structure.classification.split()[0].lower()
            }}
        },
        "governor_score": {
            "score": structure.fragility_score,
            "state": structure.classification,
            "color": "#ef4444" if structure.fragility_score > 60 else "#22c55e"
        }
    }

class ScreenerRequest(BaseModel):
    universe: str = "us"

@router.post("/factors/screener")
def get_factor_screener(req: ScreenerRequest):
    res = labs.get_factor_screen(req.universe)
    # res is a list, so no "error" key check unless it returns dict on error
    return res

# --- NEW: Full Screener Endpoint ---
from fastapi import Query
from app.services import screener

@router.get("/screener")
def get_screener(
    sector: Optional[str] = Query(None, description="Filter by sector"),
    industry: Optional[str] = Query(None, description="Filter by industry"),
    liquidity: Optional[str] = Query(None, description="HIGH, MEDIUM, LOW, ILLIQUID"),
    vol_bucket: Optional[str] = Query(None, description="LOW, MEDIUM, HIGH"),
    marketcap_min: Optional[float] = Query(None, description="Min market cap"),
    marketcap_max: Optional[float] = Query(None, description="Max market cap"),
    sort_by: str = Query("change_pct", description="Sort field"),
    sort_dir: str = Query("desc", description="asc or desc"),
    limit: int = Query(50, ge=1, le=200, description="Results per page"),
    offset: int = Query(0, ge=0, description="Pagination offset")
):
    """
    Full-featured screener with filtering, sorting, and pagination.
    """
    return screener.get_screener_data(
        sector=sector,
        industry=industry,
        liquidity=liquidity,
        vol_bucket=vol_bucket,
        marketcap_min=marketcap_min,
        marketcap_max=marketcap_max,
        sort_by=sort_by,
        sort_dir=sort_dir,
        limit=limit,
        offset=offset
    )


# =============================================================================
# FACTORS INTELLIGENCE SYSTEM - 11 Features
# =============================================================================

class FactorsIntelligenceRequest(BaseModel):
    ticker: str
    factor_set_id: str = "ff5_mom"
    window_years: int = 3
    universe_tickers: Optional[List[str]] = None
    z_score: float = 2.0
    outlier_handling: bool = True


@router.get("/factors/universe")
def get_factors_universe():
    """
    Returns available factor sets, universes, and configuration.
    Frontend uses this to populate dropdowns.
    """
    from app.services.factors_intelligence import get_factors_universe
    return get_factors_universe()


@router.post("/factors/intelligence/run")
def run_factors_intelligence(req: FactorsIntelligenceRequest):
    """
    Main factors intelligence endpoint.
    Returns all 11 factor features in a single payload.
    """
    from app.services.factors_intelligence import run_factors_analysis
    res = run_factors_analysis(
        ticker=req.ticker,
        factor_set_id=req.factor_set_id,
        window_years=req.window_years,
        universe_tickers=req.universe_tickers,
        z_score=req.z_score,
        outlier_handling=req.outlier_handling
    )
    return res


# Individual factor feature endpoints
class FactorFeatureRequest(BaseModel):
    ticker: str
    factor_set_id: str = "ff5_mom"
    window_years: int = 3
    z_score: float = 2.0
    outlier_handling: bool = True


@router.post("/factors/multi_model")
def get_factor_multi_model(req: FactorFeatureRequest):
    """Feature 1: Multi-Model Factor Engine"""
    from app.services.factors_intelligence import compute_multi_model_engine
    return compute_multi_model_engine(req.ticker, req.window_years, req.factor_set_id, req.z_score, req.outlier_handling)


@router.post("/factors/rolling_exposures")
def get_factor_rolling_exposures(req: FactorFeatureRequest):
    """Feature 2: Rolling Factor Exposures Timeline"""
    from app.services.factors_intelligence import compute_rolling_exposures
    return compute_rolling_exposures(req.ticker, req.window_years, req.factor_set_id, z_score=req.z_score, outlier_handling=req.outlier_handling)


@router.post("/factors/contribution")
def get_factor_contribution(req: FactorFeatureRequest):
    """Feature 3: Factor Contribution to Returns"""
    from app.services.factors_intelligence import compute_factor_contribution
    return compute_factor_contribution(req.ticker, req.window_years, req.factor_set_id, z_score=req.z_score, outlier_handling=req.outlier_handling)


@router.post("/factors/vol_impact")
def get_factor_vol_impact(req: FactorFeatureRequest):
    """Feature 4: Factor Volatility Impact Map"""
    from app.services.factors_intelligence import compute_vol_impact_map
    return compute_vol_impact_map(req.ticker, req.window_years, req.factor_set_id)


@router.post("/factors/regime_sensitivity")
def get_factor_regime_sensitivity(req: FactorFeatureRequest):
    """Feature 6: Regime-Linked Factor Sensitivity"""
    from app.services.factors_intelligence import compute_regime_sensitivity
    return compute_regime_sensitivity(req.ticker, req.window_years, req.factor_set_id)


@router.post("/factors/microstructure")
def get_factor_microstructure(req: FactorFeatureRequest):
    """Feature 9: Factor Microstructure Decomposition"""
    from app.services.factors_intelligence import compute_microstructure
    return compute_microstructure(req.ticker, req.window_years, req.factor_set_id)


@router.post("/factors/projection")
def get_factor_projection(req: FactorFeatureRequest):
    """Feature 10: Forward Factor Sensitivity Projection"""
    from app.services.factors_intelligence import compute_forward_projection
    return compute_forward_projection(req.ticker, req.window_years, req.factor_set_id)


@router.post("/factors/shock_replay")
def get_factor_shock_replay(req: FactorFeatureRequest):
    """Feature 11: Factor Shock Replay Simulator"""
    from app.services.factors_intelligence import compute_shock_replay
    return compute_shock_replay(req.ticker, req.window_years, req.factor_set_id)


@router.post("/factors/network")
def get_factor_network(factor_set_id: str = "ff5_mom"):
    """Feature 7: Cross-Asset Factor Network Graph"""
    from app.services.factors_intelligence import compute_factor_network
    return compute_factor_network(factor_set_id)


class ClusteringRequest(BaseModel):
    tickers: List[str]
    factor_set_id: str = "ff5_mom"
    k: int = 5
    window_years: int = 2


@router.post("/factors/clustering")
def get_factor_clustering(req: ClusteringRequest):
    """Feature 8: Multi-Ticker Factor Clustering"""
    from app.services.factors_intelligence import compute_factor_clustering
    return compute_factor_clustering(req.tickers, req.factor_set_id, req.k, req.window_years)


class CrowdingRequest(BaseModel):
    tickers: List[str]
    factor_set_id: str = "ff5_mom"
    window_years: int = 2


@router.post("/factors/crowding")
def get_factor_crowding(req: CrowdingRequest):
    """Feature 5: Factor Crowding Risk Indicator"""
    from app.services.factors_intelligence import compute_crowding_risk
    return compute_crowding_risk(req.tickers, req.factor_set_id, req.window_years)


class FactorBacktestRequest(BaseModel):
    universe: str = "us_sp500"
    factor: str = "momentum"
    window_years: int = 5
    rebalance_freq: str = "M"
    z_score: float = 2.0
    outlier_handling: bool = True


@router.post("/factors/backtest")
def get_factor_backtest(req: FactorBacktestRequest):
    """Tab 2: Quintile Backtest Engine"""
    from app.services.factors_intelligence import compute_quintile_backtest
    from app.services.regimes_intelligence import sanitize_dict
    res = compute_quintile_backtest(req.universe, req.factor, req.window_years, req.rebalance_freq, req.z_score, req.outlier_handling)
    return sanitize_dict(res)


class FactorSetRequest(BaseModel):
    factor_set_id: str = "ff5_mom"


@router.post("/factors/rotation")
def get_factor_rotation(req: FactorSetRequest):
    """Tab 4: Style Rotation Map"""
    from app.services.factors_intelligence import compute_factor_rotation
    from app.services.regimes_intelligence import sanitize_dict
    res = compute_factor_rotation(req.factor_set_id)
    return sanitize_dict(res)


@router.post("/factors/regimes")
def get_factor_regimes(req: FactorSetRequest):
    """Tab 5: Macro x Factor Regimes"""
    from app.services.factors_intelligence import compute_factor_regimes
    from app.services.regimes_intelligence import sanitize_dict
    res = compute_factor_regimes(req.factor_set_id)
    return sanitize_dict(res)


class FactorOptimizerRequest(BaseModel):
    factor_set_id: str = "ff5_mom"
    target_vol: float = 0.15
    z_score: float = 2.0
    outlier_handling: bool = True


@router.post("/factors/optimizer")
def get_factor_optimizer(req: FactorOptimizerRequest):
    """Tab 3: Factor Mixer Optimizer"""
    from app.services.factors_intelligence import compute_factor_optimizer
    from app.services.regimes_intelligence import sanitize_dict
    res = compute_factor_optimizer(req.factor_set_id, req.target_vol, req.z_score, req.outlier_handling)
    return sanitize_dict(res)



# =============================================================================
# REGIMES CROWN ENGINE - 7 Market Structural Stability Primitives
# =============================================================================

class RegimesCrownRequest(BaseModel):
    benchmark: str = "SPY"
    nodes: Optional[List[str]] = None
    window_years: int = 2
    force_refresh: bool = False


@router.get("/regimes/universe")
def get_regimes_universe():
    """Returns available configuration for the regimes engine."""
    from app.services.regimes_intelligence import get_regimes_universe
    return get_regimes_universe()


@router.post("/regimes/run")
def run_regimes_engine(req: RegimesCrownRequest):
    """
    Main Regimes Crown Engine endpoint.
    Returns all 7 crown primitives in a single payload.
    """
    import time
    from app.services.regimes_intelligence import run_regimes_engine
    
    start = time.time()
    result = run_regimes_engine(
        benchmark=req.benchmark,
        nodes=req.nodes,
        window_years=req.window_years,
        force_refresh=req.force_refresh
    )
    
    # Add compute time
    if 'provenance' in result:
        result['provenance']['computeTimeMs'] = int((time.time() - start) * 1000)
    
    return result


class RegimesTabRequest(BaseModel):
    benchmark: str = "SPY"
    nodes: Optional[List[str]] = None
    window_years: int = 2


@router.post("/regimes/integrity")
def get_regimes_integrity(req: RegimesTabRequest):
    """Tab 1: Structural Integrity Index"""
    from app.services.regimes_intelligence import (
        get_aligned_universe, compute_state_vector, compute_integrity
    )
    bars, evidence, quality = get_aligned_universe(
        req.benchmark, req.nodes or ['TLT', 'LQD', 'UUP'], req.window_years
    )
    if not bars:
        raise HTTPException(status_code=400, detail="Failed to fetch data")
    state = compute_state_vector(bars, req.benchmark, req.nodes or ['TLT', 'LQD', 'UUP'])
    result = compute_integrity(state)
    result['quality'] = quality
    result['evidence'] = evidence
    return sanitize_dict(result)


@router.post("/regimes/mass_flow")
def get_regimes_mass_flow(req: RegimesTabRequest):
    """Tab 2: Probability Mass Flow Engine"""
    from app.services.regimes_intelligence import (
        get_aligned_universe, compute_state_vector, compute_mass_flow
    )
    bars, evidence, quality = get_aligned_universe(
        req.benchmark, req.nodes or ['TLT', 'LQD', 'UUP'], req.window_years
    )
    if not bars:
        raise HTTPException(status_code=400, detail="Failed to fetch data")
    state = compute_state_vector(bars, req.benchmark, req.nodes or ['TLT', 'LQD', 'UUP'])
    result = compute_mass_flow(state)
    result['quality'] = quality
    result['evidence'] = evidence
    return sanitize_dict(result)


@router.post("/regimes/reflex_denial")
def get_regimes_reflex_denial(req: RegimesTabRequest):
    """Tab 3: Reflexive Pressure & Denial Index"""
    from app.services.regimes_intelligence import (
        get_aligned_universe, compute_state_vector, compute_mass_flow, compute_reflex_denial
    )
    bars, evidence, quality = get_aligned_universe(
        req.benchmark, req.nodes or ['TLT', 'LQD', 'UUP'], req.window_years
    )
    if not bars:
        raise HTTPException(status_code=400, detail="Failed to fetch data")
    state = compute_state_vector(bars, req.benchmark, req.nodes or ['TLT', 'LQD', 'UUP'])
    mass_flow = compute_mass_flow(state)
    result = compute_reflex_denial(state, mass_flow)
    result['quality'] = quality
    result['evidence'] = evidence
    return sanitize_dict(result)


@router.post("/regimes/fragility")
def get_regimes_fragility(req: RegimesTabRequest):
    """Tab 4: Liquidity & Leverage Fragility Surface"""
    from app.services.regimes_intelligence import (
        get_aligned_universe, compute_state_vector, compute_fragility
    )
    bars, evidence, quality = get_aligned_universe(
        req.benchmark, req.nodes or ['TLT', 'LQD', 'UUP'], req.window_years
    )
    if not bars:
        raise HTTPException(status_code=400, detail="Failed to fetch data")
    state = compute_state_vector(bars, req.benchmark, req.nodes or ['TLT', 'LQD', 'UUP'])
    result = compute_fragility(state)
    result['quality'] = quality
    result['evidence'] = evidence
    return sanitize_dict(result)


@router.post("/regimes/feedback_loops")
def get_regimes_feedback_loops(req: RegimesTabRequest):
    """Tab 5: Feedback Loop Closure Monitor"""
    from app.services.regimes_intelligence import (
        get_aligned_universe, compute_state_vector, compute_feedback_loops
    )
    bars, evidence, quality = get_aligned_universe(
        req.benchmark, req.nodes or ['TLT', 'LQD', 'UUP'], req.window_years
    )
    if not bars:
        raise HTTPException(status_code=400, detail="Failed to fetch data")
    state = compute_state_vector(bars, req.benchmark, req.nodes or ['TLT', 'LQD', 'UUP'])
    result = compute_feedback_loops(state)
    result['quality'] = quality
    result['evidence'] = evidence
    return sanitize_dict(result)


@router.post("/regimes/nonlinearity")
def get_regimes_nonlinearity(req: RegimesTabRequest):
    """Tab 6: Nonlinearity Proximity & Break Threshold"""
    from app.services.regimes_intelligence import (
        get_aligned_universe, compute_state_vector, compute_nonlinearity
    )
    bars, evidence, quality = get_aligned_universe(
        req.benchmark, req.nodes or ['TLT', 'LQD', 'UUP'], req.window_years
    )
    if not bars:
        raise HTTPException(status_code=400, detail="Failed to fetch data")
    state = compute_state_vector(bars, req.benchmark, req.nodes or ['TLT', 'LQD', 'UUP'])
    result = compute_nonlinearity(state)
    result['quality'] = quality
    result['evidence'] = evidence
    return sanitize_dict(result)


@router.post("/regimes/collapse_state")
def get_regimes_collapse_state(req: RegimesTabRequest):
    """Tab 7: Collapse State Governor"""
    from app.services.regimes_intelligence import run_regimes_engine
    result = run_regimes_engine(
        benchmark=req.benchmark,
        nodes=req.nodes,
        window_years=req.window_years
    )
    if 'error' in result:
        raise HTTPException(status_code=400, detail=result['error'])
    return {
        'asOf': result['asOf'],
        'collapseState': result['outputs']['collapseState'],
        'quality': result['quality'],
        'evidence': result['evidence']
    }

# =============================================================================
# ML LABS - INSTITUTIONAL GOD-MODE (12 Outputs)
# =============================================================================

class MLIntelligenceRequest(BaseModel):
    universe: Union[str, List[str]] = "sp500"
    ticker: Optional[str] = None
    lookback: int = 252
    timeframe: str = "1D"
    shock_pct: float = -0.03

@router.post("/ml/structural")
def get_ml_structural(req: MLIntelligenceRequest):
    """Sub-tab 1: Structural DNA (Eigen-Exposure)"""
    from app.services.institutional_engine import inst_engine
    return inst_engine.compute_structural_dna(req.universe, req.lookback, req.timeframe)

@router.post("/ml/alpha")
def get_ml_alpha(req: MLIntelligenceRequest):
    """Sub-tab 2: Alpha Ribbon (Institutional Momentum)"""
    from app.services.institutional_engine import inst_engine
    return inst_engine.compute_alpha_ribbon(req.universe, req.lookback, req.timeframe)

@router.post("/ml/regime")
def get_ml_regime(req: MLIntelligenceRequest):
    """Sub-tab 3: Regime & Entropy (Market Fragility)"""
    from app.services.institutional_engine import inst_engine
    return inst_engine.compute_regime_entropy(req.universe, req.timeframe)

@router.post("/ml/stress")
def get_ml_stress(req: MLIntelligenceRequest):
    """Sub-tab 4: Stress-Contagion Matrix"""
    from app.services.institutional_engine import inst_engine
    return inst_engine.compute_stress_contagion(req.shock_pct, req.universe, req.timeframe)

@router.post("/ml/peak")
def get_ml_peak(req: MLIntelligenceRequest):
    """Sub-tab 5: Peak ML (Alpha Oracle & Lead-Lag)"""
    from app.services.institutional_engine import inst_engine
    return inst_engine.compute_peak_ml(req.universe, req.timeframe)

@router.get("/ml/macro")
def get_ml_macro():
    """Global Macro Pulse Markers"""
    from app.services.institutional_engine import inst_engine
    return inst_engine.get_macro_pulse()

# --- ML V2 INTELLIGENCE (Merged) ---
def resolve_ticker(universe: str, ticker: Optional[str] = None) -> str:
    """Helper to pick a lead ticker from a universe if none provided."""
    if ticker:
        return ticker
    
    # Mapping universes to benchmarks
    benchmarks = {
        "india_nse": "RELIANCE.NS",
        "us_equities": "AAPL",
        "sp500": "SPY",
        "etfs": "SPY",
        "indices": "^NSEI"
    }
    return benchmarks.get(universe.lower(), "AAPL")

@router.post("/ml/v2/regime")
def get_ml2_regime(req: MLIntelligenceRequest):
    from ..services.ml.v2 import QuantumRegimeDetector
    from ..services.ml.v2.data_loader import MLDataLoader
    ticker = resolve_ticker(req.universe, req.ticker)
    data = MLDataLoader.get_ticker_full_state(ticker)
    if "error" in data: raise HTTPException(status_code=404, detail=data["error"])
    detector = QuantumRegimeDetector()
    return detector.detect_regime(data["closes"], data["volumes"])

@router.post("/ml/v2/anomalies")
def get_ml2_anomalies(req: MLIntelligenceRequest):
    from ..services.ml.v2 import AnomalyGravityDetector
    from ..services.ml.v2.data_loader import MLDataLoader
    ticker = resolve_ticker(req.universe, req.ticker)
    data = MLDataLoader.get_ticker_full_state(ticker)
    if "error" in data: raise HTTPException(status_code=404, detail=data["error"])
    detector = AnomalyGravityDetector()
    return detector.detect_anomalies(data["price_df"])

@router.post("/ml/v2/montecarlo")
def get_ml2_montecarlo(req: MLIntelligenceRequest):
    from ..services.ml.v2 import MonteCarloSimulator
    from ..services.ml.v2.data_loader import MLDataLoader
    ticker = resolve_ticker(req.universe, req.ticker)
    data = MLDataLoader.get_ticker_full_state(ticker)
    if "error" in data: raise HTTPException(status_code=404, detail=data["error"])
    simulator = MonteCarloSimulator(n_simulations=10000)
    return simulator.simulate_paths(data["returns"], current_price=float(data["closes"][-1]))

@router.post("/ml/v2/liquidity")
def get_ml2_liquidity(req: MLIntelligenceRequest):
    from ..services.ml.v2 import LiquidityCanyonAnalyzer
    from ..services.ml.v2.data_loader import MLDataLoader
    ticker = resolve_ticker(req.universe, req.ticker)
    data = MLDataLoader.get_ticker_full_state(ticker)
    if "error" in data: raise HTTPException(status_code=404, detail=data["error"])
    chart_data = data["price_df"].reset_index().to_dict('records')
    analyzer = LiquidityCanyonAnalyzer()
    return analyzer.analyze_volume_profile(chart_data)

@router.post("/ml/v2/valuation")
def get_ml2_valuation(req: MLIntelligenceRequest):
    from ..services.ml.v2 import StochasticDCF
    from ..services.ml.v2.data_loader import MLDataLoader
    ticker = resolve_ticker(req.universe, req.ticker)
    data = MLDataLoader.get_ticker_full_state(ticker)
    if "error" in data: raise HTTPException(status_code=404, detail=data["error"])
    f = data["fund"]
    p = data["closes"][-1]
    
    # Normalize keys and extract safe values
    mcap = f.get('marketCap') or f.get('market_cap') or f.get('Market Cap')
    shares = f.get('sharesOutstanding') or f.get('Shares Number') or f.get('shares_outstanding')
    
    # If shares missing, infer from mcap/price
    if not shares and mcap:
        shares = mcap / p
    if not shares:
        shares = 1e7 # Safety fallback
        
    fcf = (f.get('freeCashflow') or f.get('Free Cash Flow') or 
           f.get('operatingCashflow') or f.get('Operating Cash Flow') or 1.0e6)
    
    growth = f.get('earningsGrowth') or f.get('revenue_growth') or f.get('Revenue Growth') or 0.1
    roe = f.get('returnOnEquity') or f.get('Return On Equity') or 0
    cr = f.get('currentRatio') or f.get('Current Ratio') or 1.0
    de = f.get('debtToEquity') or f.get('Debt To Equity') or 0

    dcf_data = {
        'fcf': fcf,
        'shares': shares,
        'price': p,
        'growth_est': growth,
        'wacc_est': 0.09,
        'roe': roe,
        'current_ratio': cr,
        'debt_to_equity': de
    }
    warp = StochasticDCF()
    return warp.calculate_valuation_surface(ticker, dcf_data)

@router.post("/ml/v2/galaxy/universe")
def get_ml2_galaxy_universe(req: MLIntelligenceRequest):
    from ..services.ml.v2 import GalaxyMapper
    from ..services.ml.v2.data_loader import MLDataLoader
    universe_metadata = MLDataLoader.get_universe_state(req.universe)
    if not universe_metadata:
        # Emergency fallback for empty universe state
        ticker = resolve_ticker(req.universe, req.ticker)
        universe_metadata = [MLDataLoader.get_ticker_full_state(ticker or 'AAPL').get('fund', {})]
    
    mapper = GalaxyMapper()
    return mapper.create_universe(universe_metadata)

@router.post("/ml/v2/galaxy/similar")
def get_ml2_galaxy_similar(req: MLIntelligenceRequest):
    from ..services.ml.v2 import GalaxyMapper
    from ..services.ml.v2.data_loader import MLDataLoader
    ticker = resolve_ticker(req.universe, req.ticker)
    universe_metadata = MLDataLoader.get_universe_state(req.universe)
    mapper = GalaxyMapper()
    universe = mapper.create_universe(universe_metadata)
    return mapper.find_similar(universe, ticker, n=5)

# =============================================================================
# MACRO COMMAND CENTER - V2 (Real Data, Parquet-Powered)
# =============================================================================

@router.get("/macro/v2/full")
def get_macro_v2_full():
    """Returns the full macro command center payload (Surveillance, Regimes, Fragility, Credit)."""
    from app.services.macro_intelligence_v2 import get_macro_command_center_full
    return sanitize_dict(get_macro_command_center_full())

@router.get("/macro/v2/surveillance")
def get_macro_v2_surveillance():
    from app.services.macro_intelligence_v2 import compute_macro_surveillance
    return sanitize_dict(compute_macro_surveillance())

@router.get("/macro/v2/regimes")
def get_macro_v2_regimes():
    from app.services.macro_intelligence_v2 import compute_macro_regimes
    return sanitize_dict(compute_macro_regimes())

@router.get("/macro/v2/fragility")
def get_macro_v2_fragility():
    from app.services.macro_intelligence_v2 import compute_macro_fragility
    return sanitize_dict(compute_macro_fragility())

@router.get("/macro/v2/credit")
def get_macro_v2_credit():
    from app.services.macro_intelligence_v2 import compute_macro_credit
    return sanitize_dict(compute_macro_credit())

# =============================================================================
# REGIMES PEAK ENGINE - GOLD MINE (6 Pillars)
# =============================================================================

class RegimePeakRequest(BaseModel):
    mode: str = "US"
    window_years: int = 1

@router.post("/regimes/peak/run")
def run_regimes_peak(req: RegimePeakRequest):
    """
    Gold Mine: Regimes Intelligence Peak Engine.
    Returns all 6 institutional pillars with multi-market support.
    """
    from app.services.regime_peak_engine import RegimePeakEngine
    engine = RegimePeakEngine()
    return engine.run_all_pillars(mode=req.mode, window_years=req.window_years)
