from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import List, Optional, Dict, Any
from app.services import labs
from app.services.regimes_intelligence import sanitize_dict

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
    Aggregate endpoint: Returns all 13 volatility features in one response.
    Used by VolatilityLabPro frontend component.
    """
    from app.services.volatility_intelligence import (
        compute_rv_suite,
        compute_vol_heatmap,
        compute_iv_rv_spread,
        compute_cluster_detector,
        compute_zscore,
        compute_regime_classifier,
        compute_macro_model,
        compute_forecast_cone,
        compute_gravity_well,
        compute_fracture_map,
        compute_energy_reservoir,
        compute_symmetry_break,
        compute_transmission_engine,
        get_cached_prices
    )
    
    ticker = req.ticker
    window_years = req.window_years
    
    # Get price data for date range info
    df = get_cached_prices(ticker, f'{window_years}y')
    data_range = None
    if not df.empty:
        data_range = {
            'start': df.index[0].strftime('%Y-%m-%d'),
            'end': df.index[-1].strftime('%Y-%m-%d'),
            'trading_days': len(df)
        }
    
    # Compute all features (with error handling for each)
    def safe_compute(func, *args, **kwargs):
        try:
            return func(*args, **kwargs)
        except Exception as e:
            return {'error': str(e)}
    
    return {
        'ticker': ticker,
        'window_years': window_years,
        'data_range': data_range,
        'rv_suite': safe_compute(compute_rv_suite, ticker, window_years),
        'heatmap': safe_compute(compute_vol_heatmap, ticker, window_years),
        'iv_rv_spread': safe_compute(compute_iv_rv_spread, ticker, window_years),
        'cluster_detector': safe_compute(compute_cluster_detector, ticker, window_years),
        'zscore': safe_compute(compute_zscore, ticker, window_years),
        'regime': safe_compute(compute_regime_classifier, ticker, window_years),
        'macro_model': safe_compute(compute_macro_model, ticker, window_years),
        'forecast_cone': safe_compute(compute_forecast_cone, ticker),
        'gravity_well': safe_compute(compute_gravity_well, ticker, window_years),
        'fracture_map': safe_compute(compute_fracture_map, ticker, window_years),
        'energy_reservoir': safe_compute(compute_energy_reservoir, ticker, window_years),
        'symmetry_break': safe_compute(compute_symmetry_break, ticker, window_years),
        'transmission': safe_compute(compute_transmission_engine),
    }


# =============================================================================
# VOLATILITY INTELLIGENCE - Individual Feature Endpoints
# =============================================================================

class VolFeatureRequest(BaseModel):
    ticker: str
    window_years: int = 2

@router.post("/volatility/rv_suite")
def get_vol_rv_suite(req: VolFeatureRequest):
    """Feature 1: Realized Volatility Suite"""
    from app.services.volatility_intelligence import compute_rv_suite
    res = compute_rv_suite(req.ticker, req.window_years)
    if "error" in res:
        raise HTTPException(status_code=400, detail=res["error"])
    return res


@router.post("/volatility/heatmap")
def get_vol_heatmap(req: VolFeatureRequest):
    """Feature 2: Volatility Heatmap"""
    from app.services.volatility_intelligence import compute_vol_heatmap
    res = compute_vol_heatmap(req.ticker, req.window_years)
    if "error" in res:
        raise HTTPException(status_code=400, detail=res["error"])
    return res


@router.post("/volatility/iv_rv")
def get_vol_iv_rv(req: VolFeatureRequest):
    """Feature 3: IV-RV Spread"""
    from app.services.volatility_intelligence import compute_iv_rv_spread
    res = compute_iv_rv_spread(req.ticker, req.window_years)
    if "error" in res:
        raise HTTPException(status_code=400, detail=res["error"])
    return res


@router.post("/volatility/cluster")
def get_vol_cluster(req: VolFeatureRequest):
    """Feature 4: Volatility Cluster Detector"""
    from app.services.volatility_intelligence import compute_cluster_detector
    res = compute_cluster_detector(req.ticker, req.window_years)
    if "error" in res:
        raise HTTPException(status_code=400, detail=res["error"])
    return res


@router.post("/volatility/zscore")
def get_vol_zscore(req: VolFeatureRequest):
    """Feature 5: Volatility Z-Score"""
    from app.services.volatility_intelligence import compute_zscore
    res = compute_zscore(req.ticker, req.window_years)
    if "error" in res:
        raise HTTPException(status_code=400, detail=res["error"])
    return res


@router.post("/volatility/regime")
def get_vol_regime(req: VolFeatureRequest):
    """Feature 6: Volatility Regime Classifier"""
    from app.services.volatility_intelligence import compute_regime_classifier
    res = compute_regime_classifier(req.ticker, req.window_years)
    if "error" in res:
        raise HTTPException(status_code=400, detail=res["error"])
    return res


@router.post("/volatility/macro")
def get_vol_macro(req: VolFeatureRequest):
    """Feature 7: Macro-Linked Vol Model"""
    from app.services.volatility_intelligence import compute_macro_model
    res = compute_macro_model(req.ticker, req.window_years)
    if "error" in res:
        raise HTTPException(status_code=400, detail=res["error"])
    return res


class ForecastRequest(BaseModel):
    ticker: str
    horizon: int = 20


@router.post("/volatility/forecast")
def get_vol_forecast(req: ForecastRequest):
    """Feature 8: Volatility Forecast Cone"""
    from app.services.volatility_intelligence import compute_forecast_cone
    res = compute_forecast_cone(req.ticker, req.horizon)
    if "error" in res:
        raise HTTPException(status_code=400, detail=res["error"])
    return res


@router.post("/volatility/gravity")
def get_vol_gravity(req: VolFeatureRequest):
    """Feature 9: Volatility Gravity Well"""
    from app.services.volatility_intelligence import compute_gravity_well
    res = compute_gravity_well(req.ticker, req.window_years)
    if "error" in res:
        raise HTTPException(status_code=400, detail=res["error"])
    return res


@router.post("/volatility/fracture")
def get_vol_fracture(req: VolFeatureRequest):
    """Feature 10: Temporal Volatility Fracture Map"""
    from app.services.volatility_intelligence import compute_fracture_map
    res = compute_fracture_map(req.ticker, req.window_years)
    if "error" in res:
        raise HTTPException(status_code=400, detail=res["error"])
    return res


@router.post("/volatility/reservoir")
def get_vol_reservoir(req: VolFeatureRequest):
    """Feature 11: Volatility Energy Reservoir"""
    from app.services.volatility_intelligence import compute_energy_reservoir
    res = compute_energy_reservoir(req.ticker, req.window_years)
    if "error" in res:
        raise HTTPException(status_code=400, detail=res["error"])
    return res


@router.post("/volatility/symmetry")
def get_vol_symmetry(req: VolFeatureRequest):
    """Feature 12: Volatility Symmetry Break Index"""
    from app.services.volatility_intelligence import compute_symmetry_break
    res = compute_symmetry_break(req.ticker, req.window_years)
    if "error" in res:
        raise HTTPException(status_code=400, detail=res["error"])
    return res


class TransmissionRequest(BaseModel):
    tickers: Optional[List[str]] = None


@router.post("/volatility/transmission")
def get_vol_transmission(req: TransmissionRequest):
    """Feature 13: Volatility Transmission Engine"""
    from app.services.volatility_intelligence import compute_transmission_engine
    res = compute_transmission_engine(req.tickers)
    if "error" in res:
        raise HTTPException(status_code=400, detail=res["error"])
    return res

@router.post("/regimes")
def get_regimes(req: RegimeRequest):
    res = labs.run_regime_detection(req.ticker, req.window_years)
    if "error" in res:
        raise HTTPException(status_code=400, detail=res["error"])
    return res

@router.post("/pca")
def get_pca(req: PCARequest):
    res = labs.run_pca_analysis(req.tickers)
    if "error" in res:
        raise HTTPException(status_code=400, detail=res["error"])
    return res

# Fallback GET for PCA if frontend uses GET
@router.get("/pca")
def get_pca_get():
    res = labs.run_pca_analysis()
    if "error" in res:
        raise HTTPException(status_code=400, detail=res["error"])
    return res

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
        universe_tickers=req.universe_tickers
    )
    return res


# Individual factor feature endpoints
class FactorFeatureRequest(BaseModel):
    ticker: str
    factor_set_id: str = "ff5_mom"
    window_years: int = 3


@router.post("/factors/multi_model")
def get_factor_multi_model(req: FactorFeatureRequest):
    """Feature 1: Multi-Model Factor Engine"""
    from app.services.factors_intelligence import compute_multi_model_engine
    return compute_multi_model_engine(req.ticker, req.window_years, req.factor_set_id)


@router.post("/factors/rolling_exposures")
def get_factor_rolling_exposures(req: FactorFeatureRequest):
    """Feature 2: Rolling Factor Exposures Timeline"""
    from app.services.factors_intelligence import compute_rolling_exposures
    return compute_rolling_exposures(req.ticker, req.window_years, req.factor_set_id)


@router.post("/factors/contribution")
def get_factor_contribution(req: FactorFeatureRequest):
    """Feature 3: Factor Contribution to Returns"""
    from app.services.factors_intelligence import compute_factor_contribution
    return compute_factor_contribution(req.ticker, req.window_years, req.factor_set_id)


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
