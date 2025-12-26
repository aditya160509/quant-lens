"""
Research FG Router
API endpoints for Cluster F+G features (FG1-FG9).
"""

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel
from typing import List, Dict, Optional, Any
import logging
from datetime import datetime, timedelta

from app import data_loader, macro_data
from app.services import cluster_fg_service, etf_service
from app.services.options import get_option_chain

logger = logging.getLogger(__name__)

router = APIRouter()

# =============================================================================
# REQUEST MODELS
# =============================================================================

class FlowHeatmapRequest(BaseModel):
    groups: List[str] = ["EQUITIES", "BONDS", "COMMODITIES", "FX", "CRYPTO"]
    tickers_by_group: Dict[str, List[str]] = {
        "EQUITIES": ["SPY", "QQQ", "IWM"],
        "BONDS": ["TLT", "HYG"],
        "COMMODITIES": ["GLD", "USO"],
        "FX": ["UUP"],
        "CRYPTO": ["BTC-USD"]
    }
    lookback_days: int = 60
    volume_window: int = 20
    vol_window: int = 21


class LiquidityRadarRequest(BaseModel):
    tickers: List[str] = ["SPY", "QQQ", "IWM", "HYG", "GLD", "BTC-USD"]
    lookback_days: int = 120
    volume_window: int = 20
    vol_window: int = 21
    corr_window: int = 21


class RecessionProbRequest(BaseModel):
    as_of: Optional[str] = None
    lookback_years: int = 20
    weights: Dict[str, float] = {"yield_curve": 0.4, "credit": 0.2, "macro": 0.25, "equity_vol": 0.15}
    regions: List[str] = ["US"]


class EtfFactorDnaRequest(BaseModel):
    etf: str = "QQQ"
    peer_etfs: List[str] = ["SPY", "VUG", "VTV"]
    factors: List[str] = ["value", "momentum", "quality", "size", "volatility"]
    lookback_days: int = 252


class PortfolioPosition(BaseModel):
    ticker: str
    weight: float


class HedgeSimRequest(BaseModel):
    portfolio: Dict[str, Any]  # {"positions": [{"ticker": "AAPL", "weight": 0.15}, ...]}
    hedges: List[Dict[str, Any]]  # [{"ticker": "GLD", "target_weight": 0.05}, ...]
    benchmark: str = "SPY"
    lookback_days: int = 252
    risk_metrics: List[str] = ["vol", "beta", "var", "cvar", "max_drawdown"]
    scenarios: List[str] = ["rate_hike", "inflation_spike", "equity_crash"]


class HedgeRatioRequest(BaseModel):
    portfolio: Dict[str, Any]  # {"positions": [{"ticker": "AAPL", "weight": 0.15}, ...]}
    hedge_ticker: str = "SPY"
    lookback_days: int = 252
    mode: str = "beta_neutral"  # or "min_var"


# =============================================================================
# HELPER FUNCTIONS
# =============================================================================

def fetch_price_data(tickers: List[str], lookback_days: int) -> Dict[str, Any]:
    """Fetch price data for multiple tickers."""
    end_date = datetime.now()
    start_date = end_date - timedelta(days=lookback_days + 30)  # Extra buffer
    
    result = {}
    for ticker in tickers:
        try:
            df = data_loader.get_price_history(
                [ticker],
                start=start_date.strftime("%Y-%m-%d"),
                end=end_date.strftime("%Y-%m-%d")
            )
            if not df.empty:
                # Handle MultiIndex columns
                if hasattr(df.columns, 'levels'):
                    # MultiIndex - extract Close and Volume
                    if 'Close' in df.columns.get_level_values(0):
                        close = df.xs('Close', axis=1, level=0)
                        volume = df.xs('Volume', axis=1, level=0) if 'Volume' in df.columns.get_level_values(0) else close * 0
                        high = df.xs('High', axis=1, level=0) if 'High' in df.columns.get_level_values(0) else close
                        low = df.xs('Low', axis=1, level=0) if 'Low' in df.columns.get_level_values(0) else close
                        
                        result[ticker] = {
                            "Close": close.iloc[:, 0] if len(close.columns) == 1 else close[ticker],
                            "Volume": volume.iloc[:, 0] if len(volume.columns) == 1 else volume.get(ticker, volume.iloc[:, 0]),
                            "High": high.iloc[:, 0] if len(high.columns) == 1 else high.get(ticker, high.iloc[:, 0]),
                            "Low": low.iloc[:, 0] if len(low.columns) == 1 else low.get(ticker, low.iloc[:, 0])
                        }
                else:
                    result[ticker] = df
        except Exception as e:
            logger.warning(f"Could not fetch data for {ticker}: {e}")
    
    return result


def compute_portfolio_returns(positions: List[Dict], price_data: Dict, lookback_days: int):
    """Compute weighted portfolio returns."""
    import pandas as pd
    
    returns_list = []
    weights = []
    
    for pos in positions:
        ticker = pos.get("ticker")
        weight = pos.get("weight", 0)
        
        if ticker in price_data:
            df = price_data[ticker]
            close = df["Close"] if isinstance(df, dict) else df.get("Close", df.iloc[:, 0])
            ret = close.pct_change().dropna()
            returns_list.append(ret)
            weights.append(weight)
    
    if not returns_list:
        return pd.Series(dtype=float)
    
    # Align all returns
    all_dates = returns_list[0].index
    for r in returns_list[1:]:
        all_dates = all_dates.intersection(r.index)
    
    portfolio_ret = pd.Series(0.0, index=all_dates)
    total_weight = sum(weights)
    
    for ret, w in zip(returns_list, weights):
        portfolio_ret += (w / total_weight) * ret.loc[all_dates]
    
    return portfolio_ret.tail(lookback_days)


# =============================================================================
# FG1: FLOW HEATMAP
# =============================================================================

@router.post("/research/fg/flow_heatmap")
async def flow_heatmap(request: FlowHeatmapRequest):
    """
    FG1: Cross Asset Flow Heatmap
    Visualize capital flow pressure across asset groups.
    """
    try:
        # Collect all tickers
        all_tickers = []
        for group, tickers in request.tickers_by_group.items():
            all_tickers.extend(tickers)
        all_tickers = list(set(all_tickers))
        
        # Fetch data
        price_data = fetch_price_data(all_tickers, request.lookback_days)
        
        # Compute flow heatmap
        result = cluster_fg_service.compute_flow_heatmap(
            price_data=price_data,
            groups=request.groups,
            tickers_by_group=request.tickers_by_group,
            lookback_days=request.lookback_days,
            volume_window=request.volume_window,
            vol_window=request.vol_window
        )
        
        return result
        
    except Exception as e:
        logger.error(f"Flow heatmap error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# =============================================================================
# FG2: LIQUIDITY RADAR
# =============================================================================

@router.post("/research/fg/liquidity_radar")
async def liquidity_radar(request: LiquidityRadarRequest):
    """
    FG2: Liquidity Stress Radar
    Detect market-wide liquidity stress.
    """
    try:
        # Fetch data for all tickers plus benchmark
        all_tickers = list(set(request.tickers + ["SPY"]))
        price_data = fetch_price_data(all_tickers, request.lookback_days)
        
        result = cluster_fg_service.compute_liquidity_stress(
            price_data=price_data,
            tickers=request.tickers,
            benchmark="SPY",
            lookback_days=request.lookback_days,
            volume_window=request.volume_window,
            vol_window=request.vol_window,
            corr_window=request.corr_window
        )
        
        return result
        
    except Exception as e:
        logger.error(f"Liquidity radar error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# =============================================================================
# FG3: RECESSION PROBABILITY
# =============================================================================

@router.post("/research/fg/recession_prob")
async def recession_prob(request: RecessionProbRequest):
    """
    FG3: Recession Probability Monitor
    Estimate recession probability from macro factors.
    """
    try:
        import pandas as pd
        
        # Fetch macro data
        # Try to get yield curve data
        end_date = datetime.now()
        start_date = end_date - timedelta(days=365 * request.lookback_years)
        
        macro_data_payload = {}
        # 1. Yield Curve (Real 10Y-2Y Spread from FRED)
        try:
            yc_series = macro_data.fetch_series("T10Y2Y", observation_start=start_date.strftime("%Y-%m-%d"))
            if not yc_series.empty:
                macro_data_payload["yield_curve"] = yc_series
            else:
                # Fallback to ^TNX proxy if FRED fails
                tnx_data = data_loader.get_price_history(["^TNX"], start=start_date.strftime("%Y-%m-%d"))
                if not tnx_data.empty:
                    yield_10y = tnx_data.xs('Close', axis=1, level=0).iloc[:, 0] if hasattr(tnx_data.columns, 'levels') else tnx_data["Close"]
                    macro_data_payload["yield_curve"] = yield_10y - 4.5 # Crude fallback
        except Exception as e:
            logger.warning(f"Could not fetch yield data from FRED: {e}")
        
        # 2. Credit Spread (Real BAML HY Spread from FRED)
        try:
            cs_series = macro_data.fetch_series("BAMLH0A0HYM2", observation_start=start_date.strftime("%Y-%m-%d"))
            if not cs_series.empty:
                macro_data_payload["credit_spread"] = cs_series
        except Exception as e:
            logger.warning(f"Could not fetch credit spread from FRED: {e}")
            
        # 3. Equity Volatility (Real VIX from FRED)
        try:
            vix_series = macro_data.fetch_series("VIXCLS", observation_start=start_date.strftime("%Y-%m-%d"))
            if not vix_series.empty:
                macro_data_payload["equity_vol"] = vix_series
        except Exception as e:
            logger.warning(f"Could not fetch VIX from FRED: {e}")
        
        result = cluster_fg_service.compute_recession_prob(
            macro_data=macro_data_payload,
            weights=request.weights,
            lookback_years=request.lookback_years
        )
        
        return result
        
    except Exception as e:
        logger.error(f"Recession prob error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# =============================================================================
# FG4: DRAWDOWN ANATOMY
# =============================================================================

@router.get("/security/{ticker}/drawdown_anatomy")
async def drawdown_anatomy(
    ticker: str,
    lookback_years: int = Query(default=5),
    min_drawdown: float = Query(default=0.1),
    max_events: int = Query(default=10)
):
    """
    FG4: Drawdown Anatomy Panel
    Detailed view of major drawdowns for any ticker.
    """
    try:
        # Fetch price data
        end_date = datetime.now()
        start_date = end_date - timedelta(days=365 * lookback_years)
        
        df = data_loader.get_price_history(
            [ticker],
            start=start_date.strftime("%Y-%m-%d"),
            end=end_date.strftime("%Y-%m-%d")
        )
        
        if df.empty:
            raise HTTPException(status_code=404, detail=f"No data for {ticker}")
        
        # Extract close prices
        if hasattr(df.columns, 'levels'):
            close = df.xs('Close', axis=1, level=0)
            close = close.iloc[:, 0] if len(close.columns) == 1 else close[ticker]
        else:
            close = df["Close"] if "Close" in df.columns else df.iloc[:, 0]
        
        result = cluster_fg_service.compute_drawdown_anatomy(
            close=close,
            lookback_years=lookback_years,
            min_drawdown=min_drawdown,
            max_events=max_events
        )
        
        result["ticker"] = ticker
        
        return result
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Drawdown anatomy error for {ticker}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# =============================================================================
# FG5: ETF LOOK THROUGH
# =============================================================================

@router.get("/etf/{ticker}/lookthrough")
async def etf_lookthrough(
    ticker: str,
    top_n: int = Query(default=10),
    include_factors: bool = Query(default=True)
):
    """
    FG5: ETF Look-Through Exposure
    Transparent breakdown of ETF holdings, sectors, factors.
    """
    try:
        result = etf_service.get_etf_lookthrough(
            ticker=ticker,
            top_n=top_n,
            include_factors=include_factors
        )
        
        return result
        
    except Exception as e:
        logger.error(f"ETF lookthrough error for {ticker}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# =============================================================================
# FG6: VOLATILITY SURFACE
# =============================================================================

@router.get("/options/{ticker}/vol_surface")
async def vol_surface(
    ticker: str,
    as_of: Optional[str] = Query(default=None),
    min_maturity_days: int = Query(default=7),
    max_maturity_days: int = Query(default=365)
):
    """
    FG6: Volatility Surface Viewer
    Implied volatility surface across strikes and maturities.
    """
    try:
        import yfinance as yf
        from datetime import datetime
        
        tk = yf.Ticker(ticker)
        
        # Get spot price
        hist = tk.history(period="1d")
        if hist.empty:
            raise HTTPException(status_code=404, detail=f"No price data for {ticker}")
        spot = float(hist["Close"].iloc[-1])
        
        # Get all expirations
        expirations = tk.options
        if not expirations:
            return {
                "ticker": ticker,
                "as_of": datetime.now().strftime("%Y-%m-%d"),
                "points": [],
                "grid_optional": None,
                "meta": {"source": "yfinance", "cache_ttl_sec": 900}
            }
        
        points = []
        today = datetime.now()
        
        # Process each expiration
        for exp_str in expirations[:8]:  # Limit to first 8 expirations for speed
            try:
                exp_date = datetime.strptime(exp_str, "%Y-%m-%d")
                days_to_exp = (exp_date - today).days
                
                if days_to_exp < min_maturity_days or days_to_exp > max_maturity_days:
                    continue
                
                chain = tk.option_chain(exp_str)
                
                # Process calls
                for _, row in chain.calls.iterrows():
                    iv = row.get("impliedVolatility", 0)
                    if iv and iv > 0 and iv < 5:  # Filter invalid IVs
                        points.append({
                            "strike": float(row["strike"]),
                            "days_to_expiry": days_to_exp,
                            "iv": round(float(iv), 4),
                            "type": "call"
                        })
                
                # Process puts
                for _, row in chain.puts.iterrows():
                    iv = row.get("impliedVolatility", 0)
                    if iv and iv > 0 and iv < 5:
                        points.append({
                            "strike": float(row["strike"]),
                            "days_to_expiry": days_to_exp,
                            "iv": round(float(iv), 4),
                            "type": "put"
                        })
                        
            except Exception as e:
                logger.warning(f"Error processing expiration {exp_str}: {e}")
                continue
        
        # Build optional grid for surface
        grid = None
        if points:
            import numpy as np
            
            strikes = sorted(set(p["strike"] for p in points))
            maturities = sorted(set(p["days_to_expiry"] for p in points))
            
            # Create IV grid
            iv_grid = []
            for mat in maturities:
                row = []
                for strike in strikes:
                    matching = [p["iv"] for p in points if p["strike"] == strike and p["days_to_expiry"] == mat]
                    row.append(round(np.mean(matching), 4) if matching else None)
                iv_grid.append(row)
            
            grid = {
                "strikes": [round(s, 2) for s in strikes],
                "maturities": maturities,
                "iv": iv_grid
            }
        
        return {
            "ticker": ticker,
            "spot": round(spot, 2),
            "as_of": datetime.now().strftime("%Y-%m-%d"),
            "points": points,
            "grid_optional": grid,
            "meta": {"source": "yfinance", "cache_ttl_sec": 900}
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Vol surface error for {ticker}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# =============================================================================
# FG7: ETF FACTOR DNA
# =============================================================================

@router.post("/research/fg/etf_factor_dna")
async def etf_factor_dna(request: EtfFactorDnaRequest):
    """
    FG7: ETF Factor DNA View
    Factor personality of an ETF vs peers.
    """
    try:
        result = etf_service.compute_etf_factor_dna(
            etf=request.etf,
            peer_etfs=request.peer_etfs,
            factors=request.factors
        )
        
        return result
        
    except Exception as e:
        logger.error(f"ETF Factor DNA error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# =============================================================================
# FG8: HEDGE SIMULATOR
# =============================================================================

@router.post("/portfolio/hedge_sim")
async def hedge_sim(request: HedgeSimRequest):
    """
    FG8: Hedge Simulator
    Simulate impact of hedges on portfolio risk.
    """
    try:
        import pandas as pd
        
        positions = request.portfolio.get("positions", [])
        if not positions:
            raise HTTPException(status_code=400, detail="No positions provided")
        
        # Collect all tickers
        portfolio_tickers = [p["ticker"] for p in positions]
        hedge_tickers = [h["ticker"] for h in request.hedges]
        all_tickers = list(set(portfolio_tickers + hedge_tickers + [request.benchmark]))
        
        # Fetch data
        price_data = fetch_price_data(all_tickers, request.lookback_days)
        
        # Compute portfolio returns
        portfolio_returns = compute_portfolio_returns(positions, price_data, request.lookback_days)
        
        if portfolio_returns.empty:
            raise HTTPException(status_code=400, detail="Could not compute portfolio returns")
        
        # Get benchmark returns
        if request.benchmark in price_data:
            bench_df = price_data[request.benchmark]
            bench_close = bench_df["Close"] if isinstance(bench_df, dict) else bench_df.get("Close", bench_df.iloc[:, 0])
            benchmark_returns = bench_close.pct_change().dropna()
        else:
            benchmark_returns = pd.Series(dtype=float)
        
        # Get hedge returns
        hedge_returns = {}
        hedge_weights = {}
        for h in request.hedges:
            ticker = h["ticker"]
            weight = h.get("target_weight", 0.05)
            if ticker in price_data:
                hdf = price_data[ticker]
                hclose = hdf["Close"] if isinstance(hdf, dict) else hdf.get("Close", hdf.iloc[:, 0])
                hedge_returns[ticker] = hclose.pct_change().dropna()
                hedge_weights[ticker] = weight
        
        result = cluster_fg_service.compute_hedge_simulation(
            portfolio_returns=portfolio_returns,
            hedge_returns=hedge_returns,
            hedge_weights=hedge_weights,
            benchmark_returns=benchmark_returns,
            scenarios=request.scenarios
        )
        
        return result
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Hedge sim error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# =============================================================================
# FG9: HEDGE RATIO CALCULATOR
# =============================================================================

@router.post("/portfolio/hedge_ratio")
async def hedge_ratio(request: HedgeRatioRequest):
    """
    FG9: Hedge Ratio Calculator
    Compute optimal hedge size.
    """
    try:
        import pandas as pd
        
        positions = request.portfolio.get("positions", [])
        if not positions:
            raise HTTPException(status_code=400, detail="No positions provided")
        
        # Collect all tickers
        portfolio_tickers = [p["ticker"] for p in positions]
        all_tickers = list(set(portfolio_tickers + [request.hedge_ticker]))
        
        # Fetch data
        price_data = fetch_price_data(all_tickers, request.lookback_days)
        
        # Compute portfolio returns
        portfolio_returns = compute_portfolio_returns(positions, price_data, request.lookback_days)
        
        if portfolio_returns.empty:
            raise HTTPException(status_code=400, detail="Could not compute portfolio returns")
        
        # Get hedge returns
        if request.hedge_ticker in price_data:
            hdf = price_data[request.hedge_ticker]
            hclose = hdf["Close"] if isinstance(hdf, dict) else hdf.get("Close", hdf.iloc[:, 0])
            hedge_returns = hclose.pct_change().dropna()
        else:
            raise HTTPException(status_code=404, detail=f"No data for hedge ticker {request.hedge_ticker}")
        
        result = cluster_fg_service.compute_hedge_ratio(
            portfolio_returns=portfolio_returns,
            hedge_returns=hedge_returns,
            mode=request.mode
        )
        
        result["hedge_ticker"] = request.hedge_ticker
        
        return result
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Hedge ratio error: {e}")
        raise HTTPException(status_code=500, detail=str(e))
