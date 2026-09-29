"""
Quantitative Lab API - REST Endpoints for the Quantitative Engine
=================================================================

Provides endpoints for:
1. SDE Path Laboratory - Heston, GBM, Jump-Diffusion simulations
2. State-Space Tracking - Kalman Filter, Dynamic Beta
3. Arbitrage Matrix - Cointegration, VECM, Half-Life
4. Spectral Physics - CWT, Lyapunov, Bifurcation
"""

from fastapi import APIRouter, HTTPException, Query, Body
from typing import Dict, Any, List, Optional
import logging

router = APIRouter()
logger = logging.getLogger(__name__)

# Lazy load engine to avoid circular imports
_engine = None

def get_engine():
    global _engine
    if _engine is None:
        from app.services.quantitative_engine import quant_engine
        _engine = quant_engine
    return _engine


# =============================================================================
# MODULE 1: SDE PATH LABORATORY
# =============================================================================

@router.post("/quantitative/sde/paths")
async def sde_path_simulation(
    ticker: str = Body(..., description="Ticker symbol"),
    model: str = Body("heston", description="Model: gbm, heston, jump"),
    horizon: int = Body(63, ge=5, le=504, description="Simulation horizon in trading days"),
    n_paths: int = Body(1000, ge=100, le=10000, description="Number of Monte Carlo paths"),
    lookback: int = Body(252, ge=60, le=1260, description="Historical lookback for parameter estimation")
) -> Dict[str, Any]:
    """
    Run SDE path simulation (GBM, Heston, or Jump-Diffusion).
    Returns path cloud, cones of uncertainty, and terminal distribution stats.
    """
    try:
        engine = get_engine()
        result = engine.run_sde_analysis(
            ticker=ticker,
            model=model,
            horizon=horizon,
            n_paths=n_paths,
            lookback=lookback
        )
        return {"status": "success", "data": result, "ticker": ticker, "model": model}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"SDE simulation failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/quantitative/sde/touch-probability")
async def touch_probability(
    ticker: str = Body(...),
    target: float = Body(..., description="Target price to touch"),
    stop: float = Body(..., description="Stop price to touch"),
    horizon: int = Body(21, ge=1, le=252, description="Time horizon in trading days"),
    n_paths: int = Body(10000, ge=1000, le=50000),
    lookback: int = Body(252, ge=60, le=504)
) -> Dict[str, Any]:
    """
    Calculate probability of hitting target or stop before expiry.
    """
    try:
        engine = get_engine()
        prices = engine.get_price_data(ticker, lookback)
        
        import numpy as np
        returns = np.diff(np.log(prices))
        mu = np.mean(returns) * 252
        sigma = np.std(returns) * np.sqrt(252)
        S0 = prices[-1]
        
        result = engine.sde.probability_of_touch(
            S0=S0, target=target, stop=stop,
            mu=mu, sigma=sigma, T=horizon, n_paths=n_paths
        )
        return {"status": "success", "data": result, "ticker": ticker}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Touch probability calculation failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# =============================================================================
# MODULE 2: STATE-SPACE TRACKING (KALMAN FILTER)
# =============================================================================

@router.post("/quantitative/kalman/filter")
async def kalman_filter_analysis(
    ticker: str = Body(...),
    benchmark: str = Body("SPY", description="Benchmark for dynamic beta"),
    Q: float = Body(0.01, ge=0.0001, le=1.0, description="Process noise"),
    R: float = Body(1.0, ge=0.1, le=10.0, description="Measurement noise"),
    lookback: int = Body(252, ge=60, le=504)
) -> Dict[str, Any]:
    """
    Run Kalman filter for price denoising, phase portrait, and dynamic beta.
    """
    try:
        engine = get_engine()
        result = engine.run_kalman_analysis(
            ticker=ticker,
            benchmark=benchmark,
            Q=Q,
            R=R,
            lookback=lookback
        )
        return {"status": "success", "data": result}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Kalman filter failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/quantitative/kalman/denoise-only")
async def kalman_denoise_only(
    ticker: str = Body(...),
    Q: float = Body(0.01, ge=0.0001, le=1.0),
    R: float = Body(1.0, ge=0.1, le=10.0),
    lookback: int = Body(252, ge=60, le=504)
) -> Dict[str, Any]:
    """
    Quick Kalman denoise endpoint - just filtered prices.
    """
    try:
        engine = get_engine()
        prices = engine.get_price_data(ticker, lookback)
        result = engine.kalman.kalman_denoise(prices, Q=Q, R=R)
        return {"status": "success", "data": result, "ticker": ticker}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Kalman denoise failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/quantitative/kalman/dynamic-beta")
async def dynamic_beta_analysis(
    ticker: str = Body(...),
    benchmark: str = Body("SPY"),
    Q: float = Body(0.001, ge=0.00001, le=0.1),
    R: float = Body(0.1, ge=0.01, le=1.0),
    lookback: int = Body(504, ge=120, le=1260)
) -> Dict[str, Any]:
    """
    Time-varying beta estimation using Kalman filter.
    """
    try:
        engine = get_engine()
        import numpy as np
        
        asset_prices = engine.get_price_data(ticker, lookback)
        bench_prices = engine.get_price_data(benchmark, lookback)
        
        min_len = min(len(asset_prices), len(bench_prices))
        asset_returns = np.diff(np.log(asset_prices[-min_len:]))
        market_returns = np.diff(np.log(bench_prices[-min_len:]))
        
        result = engine.kalman.dynamic_beta(asset_returns, market_returns, Q=Q, R=R)
        result["ticker"] = ticker
        result["benchmark"] = benchmark
        
        return {"status": "success", "data": result}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Dynamic beta failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# =============================================================================
# MODULE 3: ARBITRAGE MATRIX (COINTEGRATION)
# =============================================================================

@router.post("/quantitative/cointegration/analyze")
async def cointegration_analysis(
    ticker_a: str = Body(..., description="First ticker"),
    ticker_b: str = Body(..., description="Second ticker"),
    lookback: int = Body(504, ge=120, le=1260, description="Lookback period")
) -> Dict[str, Any]:
    """
    Full cointegration analysis: Engle-Granger, Johansen, VECM, Half-Life.
    """
    try:
        engine = get_engine()
        result = engine.run_cointegration_analysis(
            ticker_a=ticker_a,
            ticker_b=ticker_b,
            lookback=lookback
        )
        return {"status": "success", "data": result}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Cointegration analysis failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/quantitative/cointegration/spread")
async def compute_spread(
    ticker_a: str = Body(...),
    ticker_b: str = Body(...),
    lookback: int = Body(252, ge=60, le=504)
) -> Dict[str, Any]:
    """
    Quick spread calculation with z-score and hedge ratio.
    """
    try:
        engine = get_engine()
        import numpy as np
        
        prices_a = engine.get_price_data(ticker_a, lookback)
        prices_b = engine.get_price_data(ticker_b, lookback)
        
        min_len = min(len(prices_a), len(prices_b))
        prices_a = prices_a[-min_len:]
        prices_b = prices_b[-min_len:]
        
        result = engine.arbitrage.engle_granger(prices_a, prices_b)
        
        return {
            "status": "success",
            "data": {
                "spread": result["spread"],
                "zscore": result["spread_zscore"],
                "hedge_ratio": result["hedge_ratio_beta"],
                "cointegrated": result["cointegrated"],
                "adf_stat": result["adf_stat"],
                "p_value": result["p_value"],
                "signal": result["current_signal"],
                "ticker_a": ticker_a,
                "ticker_b": ticker_b
            }
        }
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Spread computation failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/quantitative/cointegration/half-life")
async def half_life_calculation(
    ticker_a: str = Body(...),
    ticker_b: str = Body(...),
    lookback: int = Body(252, ge=60, le=504)
) -> Dict[str, Any]:
    """
    Calculate mean-reversion half-life for a spread.
    """
    try:
        engine = get_engine()
        import numpy as np
        
        prices_a = engine.get_price_data(ticker_a, lookback)
        prices_b = engine.get_price_data(ticker_b, lookback)
        
        min_len = min(len(prices_a), len(prices_b))
        prices_a = prices_a[-min_len:]
        prices_b = prices_b[-min_len:]
        
        eg = engine.arbitrage.engle_granger(prices_a, prices_b)
        spread = np.array(eg["spread"])
        
        result = engine.arbitrage.half_life(spread)
        result["cointegrated"] = eg["cointegrated"]
        result["ticker_a"] = ticker_a
        result["ticker_b"] = ticker_b
        
        return {"status": "success", "data": result}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Half-life calculation failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/quantitative/cointegration/optimal-bounds")
async def optimal_trading_bounds(
    ticker_a: str = Body(...),
    ticker_b: str = Body(...),
    transaction_cost: float = Body(0.001, ge=0.0, le=0.01),
    lookback: int = Body(252, ge=60, le=504)
) -> Dict[str, Any]:
    """
    Calculate optimal entry/exit bounds for spread trading.
    """
    try:
        engine = get_engine()
        import numpy as np
        
        prices_a = engine.get_price_data(ticker_a, lookback)
        prices_b = engine.get_price_data(ticker_b, lookback)
        
        min_len = min(len(prices_a), len(prices_b))
        prices_a = prices_a[-min_len:]
        prices_b = prices_b[-min_len:]
        
        eg = engine.arbitrage.engle_granger(prices_a, prices_b)
        spread = np.array(eg["spread"])
        
        result = engine.arbitrage.optimal_bounds(spread, transaction_cost)
        result["hedge_ratio"] = eg["hedge_ratio_beta"]
        result["ticker_a"] = ticker_a
        result["ticker_b"] = ticker_b
        
        return {"status": "success", "data": result}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Optimal bounds calculation failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# =============================================================================
# MODULE 4: SPECTRAL PHYSICS
# =============================================================================

@router.post("/quantitative/spectral/full-analysis")
async def spectral_full_analysis(
    ticker: str = Body(...),
    lookback: int = Body(504, ge=120, le=1260)
) -> Dict[str, Any]:
    """
    Full spectral analysis: CWT Scalogram, Lyapunov, Bifurcation, Entropy.
    """
    try:
        engine = get_engine()
        result = engine.run_spectral_analysis(ticker=ticker, lookback=lookback)
        return {"status": "success", "data": result}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Spectral analysis failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/quantitative/spectral/scalogram")
async def cwt_scalogram(
    ticker: str = Body(...),
    wavelet: str = Body("morl", description="Wavelet: morl, mexh, cgau"),
    scales_max: int = Body(64, ge=16, le=128),
    lookback: int = Body(252, ge=60, le=504)
) -> Dict[str, Any]:
    """
    Continuous Wavelet Transform scalogram for time-frequency analysis.
    """
    try:
        engine = get_engine()
        prices = engine.get_price_data(ticker, lookback)
        result = engine.spectral.cwt_scalogram(prices, wavelet=wavelet, scales_max=scales_max)
        result["ticker"] = ticker
        return {"status": "success", "data": result}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Scalogram failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/quantitative/spectral/chaos")
async def chaos_analysis(
    ticker: str = Body(...),
    lookback: int = Body(504, ge=120, le=1260)
) -> Dict[str, Any]:
    """
    Chaos analysis: Lyapunov exponent and prediction horizon.
    """
    try:
        engine = get_engine()
        prices = engine.get_price_data(ticker, lookback)
        result = engine.spectral.lyapunov_exponent(prices)
        result["ticker"] = ticker
        return {"status": "success", "data": result}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Chaos analysis failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/quantitative/spectral/bifurcation")
async def bifurcation_analysis(
    ticker: str = Body(...),
    window: int = Body(60, ge=20, le=120),
    lookback: int = Body(504, ge=120, le=1260)
) -> Dict[str, Any]:
    """
    Bifurcation distance: Early warning for regime changes.
    """
    try:
        engine = get_engine()
        prices = engine.get_price_data(ticker, lookback)
        result = engine.spectral.bifurcation_distance(prices, window=window)
        result["ticker"] = ticker
        return {"status": "success", "data": result}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Bifurcation analysis failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/quantitative/spectral/entropy")
async def spectral_entropy(
    ticker: str = Body(...),
    lookback: int = Body(252, ge=60, le=504)
) -> Dict[str, Any]:
    """
    Spectral entropy: Measure of signal randomness/complexity.
    """
    try:
        engine = get_engine()
        prices = engine.get_price_data(ticker, lookback)
        result = engine.spectral.spectral_entropy(prices)
        result["ticker"] = ticker
        return {"status": "success", "data": result}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Spectral entropy failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# =============================================================================
# HEALTH CHECK
# =============================================================================

@router.get("/quantitative/health")
async def quantitative_health():
    """Health check for quantitative engine."""
    return {
        "status": "healthy",
        "modules": ["sde", "kalman", "cointegration", "spectral"],
        "engine": "QuantitativeEngine v1.0"
    }
