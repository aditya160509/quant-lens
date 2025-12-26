"""
Market Labs API Router
7-Engine Market Structure Analysis Platform

Endpoints:
- POST /build-state - Build/cache MarketState
- GET /engine/{engine_id} - Get engine-specific data
- GET /drilldown/{ticker} - Ticker detail modal data
"""

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel
from typing import Optional, List, Dict, Any
import numpy as np
import pandas as pd
from datetime import datetime
import logging

from app.services.market_state import get_or_build_market_state, MarketState

logger = logging.getLogger(__name__)
router = APIRouter()


# ============================================================================
# REQUEST/RESPONSE MODELS
# ============================================================================

class BuildStateRequest(BaseModel):
    universe: str = "US"  # US or INDIA
    force_rebuild: bool = False


class EngineRequest(BaseModel):
    universe: str = "US"
    window: int = 60
    date: Optional[str] = None  # YYYY-MM-DD, defaults to latest


# ============================================================================
# HELPER FUNCTIONS
# ============================================================================

def df_to_records(df: pd.DataFrame, round_decimals: int = 4) -> List[Dict]:
    """Convert DataFrame to list of records for JSON."""
    if df is None or df.empty:
        return []
    df = df.round(round_decimals)
    df.index = df.index.astype(str)
    return df.reset_index().to_dict('records')


def series_to_records(s: pd.Series, name: str = "value", round_decimals: int = 4) -> List[Dict]:
    """Convert Series to list of records for JSON."""
    if s is None or s.empty:
        return []
    s = s.round(round_decimals)
    df = pd.DataFrame({name: s})
    df.index = df.index.astype(str)
    return df.reset_index().to_dict('records')


def percentile_rank(value: float, series: pd.Series) -> float:
    """Compute percentile rank of value in series."""
    if series.empty or pd.isna(value):
        return 50.0
    return (series < value).sum() / len(series) * 100


# ============================================================================
# BUILD STATE ENDPOINT
# ============================================================================

@router.post("/build-state")
async def build_market_state(request: BuildStateRequest):
    """Build or refresh MarketState for a universe."""
    try:
        state = await get_or_build_market_state(
            universe=request.universe,
            force_rebuild=request.force_rebuild
        )
        
        return {
            "success": state.prices is not None,
            "universe": state.universe,
            "ticker_count": len(state.prices.columns) if state.prices is not None else 0,
            "date_range": [str(state.dates[0]), str(state.dates[-1])] if state.dates else [],
            "state_hash": state.state_hash,
            "build_time": str(state.build_time),
            "sectors": list(set(state.sector_map.values()))
        }
    except Exception as e:
        logger.error(f"Build state error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ============================================================================
# ENGINE 1: MARKET INTERNAL MAP
# ============================================================================

@router.get("/engine/1")
async def engine_market_internals(
    universe: str = Query("US"),
    window: int = Query(20)
):
    """
    Engine 1: Market Internal Map
    Returns breadth, dispersion, concentration, and contribution data.
    """
    try:
        state = await get_or_build_market_state(universe=universe)
        if state.returns is None:
            raise HTTPException(status_code=503, detail="Market state not available")
        
        # Breadth metrics
        ad = state.advance_decline()
        pct_above_20 = state.pct_above_ma(20)
        pct_above_50 = state.pct_above_ma(50)
        pct_above_200 = state.pct_above_ma(200)
        nhnl = state.new_highs_lows(20)
        udv = state.up_down_volume()
        
        # Dispersion & concentration
        dispersion = state.dispersion()
        median_ret = state.median_return()
        ew_ret = state.equal_weight_return()
        herfindahl = state.herfindahl()
        
        # Tail metrics
        tails = state.tail_shares()
        
        # Contribution (latest day)
        contrib = state.contribution()
        latest_contrib = contrib.iloc[-1].sort_values(ascending=False)
        top_contributors = latest_contrib.head(25)
        bottom_contributors = latest_contrib.tail(25)
        
        # Sector breadth
        sector_breadth = state.sector_breadth()
        sector_returns = state.sector_returns()
        
        # Build breadth ribbon data (time series) - align all to common index
        common_idx = ad.index
        breadth_ribbon_data = []
        for i, idx in enumerate(common_idx):
            row = {
                "date": str(idx),
                "ad_cumulative": float(ad["ad_cumulative"].iloc[i]) if not pd.isna(ad["ad_cumulative"].iloc[i]) else 0,
                "pct_above_20": float(pct_above_20.iloc[i]) if i < len(pct_above_20) and not pd.isna(pct_above_20.iloc[i]) else 50,
                "pct_above_50": float(pct_above_50.iloc[i]) if i < len(pct_above_50) and not pd.isna(pct_above_50.iloc[i]) else 50,
                "pct_above_200": float(pct_above_200.iloc[i]) if i < len(pct_above_200) and not pd.isna(pct_above_200.iloc[i]) else 50,
                "nhnl_diff": float(nhnl["nhnl_diff"].iloc[i]) if i < len(nhnl) and not pd.isna(nhnl["nhnl_diff"].iloc[i]) else 0,
                "volume_diff": float(udv["volume_diff"].iloc[i]) if i < len(udv) and not pd.isna(udv["volume_diff"].iloc[i]) else 0,
                "dispersion": float(dispersion.iloc[i]) if i < len(dispersion) and not pd.isna(dispersion.iloc[i]) else 0,
                "median_return": float(median_ret.iloc[i]) if i < len(median_ret) and not pd.isna(median_ret.iloc[i]) else 0,
                "left_tail": float(tails["left_tail_pct"].iloc[i]) if i < len(tails) and not pd.isna(tails["left_tail_pct"].iloc[i]) else 0,
                "right_tail": float(tails["right_tail_pct"].iloc[i]) if i < len(tails) and not pd.isna(tails["right_tail_pct"].iloc[i]) else 0,
                "herfindahl": float(herfindahl.iloc[i]) if i < len(herfindahl) and not pd.isna(herfindahl.iloc[i]) else 0
            }
            breadth_ribbon_data.append(row)

        
        # Get latest values with percentiles
        latest = {
            "ad_diff": int(ad["ad_diff"].iloc[-1]),
            "ad_diff_pctile": percentile_rank(ad["ad_diff"].iloc[-1], ad["ad_diff"]),
            "pct_above_50": round(pct_above_50.iloc[-1], 1),
            "pct_above_50_pctile": percentile_rank(pct_above_50.iloc[-1], pct_above_50),
            "dispersion": round(dispersion.iloc[-1] * 100, 2),
            "dispersion_pctile": percentile_rank(dispersion.iloc[-1], dispersion),
            "herfindahl": round(herfindahl.iloc[-1], 4),
            "herfindahl_pctile": percentile_rank(herfindahl.iloc[-1], herfindahl),
            "date": str(state.dates[-1])
        }
        
        return {
            "engine": 1,
            "name": "Market Internal Map",
            "universe": universe,
            "ticker_count": len(state.prices.columns),
            "latest": latest,
            "breadth_ribbon": breadth_ribbon_data[-60:],
            "contribution_tornado": {
                "top": [{"ticker": t, "contribution": round(v * 100, 4)} 
                       for t, v in top_contributors.items()],
                "bottom": [{"ticker": t, "contribution": round(v * 100, 4)} 
                          for t, v in bottom_contributors.items()]
            },
            "sector_breadth": df_to_records(sector_breadth.tail(60)),
            "sector_returns": df_to_records(sector_returns.tail(60))
        }
        
    except Exception as e:
        logger.error(f"Engine 1 error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ============================================================================
# ENGINE 2: LIQUIDITY & IMPACT SURFACE
# ============================================================================

@router.get("/engine/2")
async def engine_liquidity_impact(
    universe: str = Query("US"),
    window: int = Query(20)
):
    """
    Engine 2: Liquidity & Impact Surface
    Returns illiquidity, gaps, and impact asymmetry data.
    """
    try:
        state = await get_or_build_market_state(universe=universe)
        if state.returns is None or state.returns.empty:
            raise HTTPException(status_code=503, detail="Market state not available")
        
        # Ensure numeric types
        returns = state.returns.apply(pd.to_numeric, errors='coerce').fillna(0)
        
        # Amihud illiquidity - Scaled by 1e9 for readability (Illiq per Billion)
        illiq_raw = state.amihud_illiquidity()
        illiq_raw = illiq_raw.apply(pd.to_numeric, errors='coerce').fillna(0)
        illiq = illiq_raw * 1e9
        median_illiq = illiq.median(axis=1)
        illiq_95 = illiq.quantile(0.95, axis=1)
        illiq_dispersion = illiq.std(axis=1)
        
        # Gap detection  
        gaps = state.gap_detection(threshold=0.02)
        if isinstance(gaps["gap_flag"], pd.DataFrame):
            # Convert boolean to int for sum
            gap_counts = gaps["gap_flag"].astype(int).sum(axis=1)
        else:
            gap_counts = pd.Series([0] * len(median_illiq), index=median_illiq.index)
        
        # Impact asymmetry (illiquidity on up vs down days)
        up_days = returns > 0
        down_days = returns < 0
        illiq_up = (illiq * up_days.astype(int)).sum(axis=1) / (up_days.sum(axis=1) + 1)
        illiq_down = (illiq * down_days.astype(int)).sum(axis=1) / (down_days.sum(axis=1) + 1)
        impact_asymmetry = illiq_down - illiq_up
        
        # Sector illiquidity
        sector_illiq = {}
        for sector in set(state.sector_map.values()):
            tickers = [t for t, s in state.sector_map.items() if s == sector and t in illiq.columns]
            if tickers:
                sector_illiq[sector] = illiq[tickers].median(axis=1).iloc[-1]
        
        # Liquidity regime calendar
        try:
            dates_list = [str(d) for d in median_illiq.index]
            illiq_list = median_illiq.fillna(0).tolist()
            illiq_95_list = illiq_95.fillna(0).tolist()
            disp_list = illiq_dispersion.fillna(0).tolist()
            gap_list = gap_counts.fillna(0).tolist() if len(gap_counts) == len(median_illiq) else [0] * len(median_illiq)
            
            liquidity_calendar = pd.DataFrame({
                "date": dates_list,
                "median_illiq": illiq_list,
                "illiq_95": illiq_95_list,
                "illiq_dispersion": disp_list,
                "gap_count": gap_list
            })
        except Exception as cal_err:
            logger.warning(f"Error building liquidity calendar: {cal_err}")
            liquidity_calendar = pd.DataFrame()
        
        # Latest values
        latest_illiq = median_illiq.iloc[-1]
        latest = {
            "median_illiq": float(latest_illiq) if not pd.isna(latest_illiq) else 0,
            "illiq_pctile": percentile_rank(latest_illiq, median_illiq),
            "impact_asymmetry": float(impact_asymmetry.iloc[-1]) if not pd.isna(impact_asymmetry.iloc[-1]) else 0,
            "date": str(state.dates[-1])
        }
        
        # Illiquidity leaderboard
        latest_illiq_by_ticker = illiq.iloc[-1].sort_values(ascending=False)
        illiq_leaderboard = [
            {
                "ticker": t, 
                "illiq": round(v, 2) if not pd.isna(v) else 0,
                "sector": state.sector_map.get(t, "Unknown")
            }
            for t, v in latest_illiq_by_ticker.head(30).items()
        ]
        
        # Get gap fill rates and illiquidity surface
        gap_fill_rates = state.gap_fill_rates(threshold=0.02)
        illiquidity_surface = state.illiquidity_surface()
        
        return {
            "engine": 2,
            "name": "Liquidity & Impact Surface",
            "universe": universe,
            "ticker_count": len(state.prices.columns),
            "latest": latest,
            "liquidity_calendar": liquidity_calendar.to_dict('records'),
            "impact_asymmetry": series_to_records(impact_asymmetry.tail(60), "asymmetry"),
            "sector_illiquidity": [{"sector": s, "illiq": round(v, 2)} for s, v in sector_illiq.items()],
            "illiq_leaderboard": illiq_leaderboard,
            "gap_fill_rates": gap_fill_rates,
            "illiquidity_surface": illiquidity_surface
        }
        
    except Exception as e:
        logger.error(f"Engine 2 error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ============================================================================
# ENGINE 3: CORRELATION & CROWDING
# ============================================================================

@router.get("/engine/3")
async def engine_correlation_crowding(
    universe: str = Query("US"),
    window: int = Query(60)
):
    """
    Engine 3: Correlation & Crowding Room
    Returns correlation matrix, clustering, and crowding metrics.
    """
    try:
        state = await get_or_build_market_state(universe=universe)
        if state.returns is None:
            raise HTTPException(status_code=503, detail="Market state not available")
        
        # Correlation matrix (sector level for performance)
        sector_returns = state.sector_returns()
        sector_corr = sector_returns.tail(window).corr()
        
        # Average correlation over time
        avg_corr_history = []
        for i in range(window, len(sector_returns)):
            window_data = sector_returns.iloc[i-window:i]
            corr_matrix = window_data.corr()
            mask = np.triu(np.ones_like(corr_matrix, dtype=bool), k=1)
            avg_c = corr_matrix.where(mask).stack().mean()
            avg_corr_history.append({
                "date": str(sector_returns.index[i]),
                "avg_correlation": round(avg_c, 4) if not pd.isna(avg_c) else 0
            })
        
        # Correlation tail (% of pairs > 0.7)
        corr_tail_history = []
        for i in range(window, len(sector_returns)):
            window_data = sector_returns.iloc[i-window:i]
            corr_matrix = window_data.corr()
            mask = np.triu(np.ones_like(corr_matrix, dtype=bool), k=1)
            pairs = corr_matrix.where(mask).stack()
            tail_07 = (pairs > 0.7).sum() / len(pairs) * 100 if len(pairs) > 0 else 0
            tail_085 = (pairs > 0.85).sum() / len(pairs) * 100 if len(pairs) > 0 else 0
            corr_tail_history.append({
                "date": str(sector_returns.index[i]),
                "tail_07": round(tail_07, 2),
                "tail_085": round(tail_085, 2)
            })
        
        # Latest metrics
        latest_avg_corr = state.average_correlation(window)
        latest_corr_disp = state.correlation_dispersion(window)
        
        latest = {
            "avg_correlation": round(latest_avg_corr, 4) if not pd.isna(latest_avg_corr) else 0,
            "corr_dispersion": round(latest_corr_disp, 4) if not pd.isna(latest_corr_disp) else 0,
            "date": str(state.dates[-1])
        }
        
        # Sector correlation matrix for heatmap
        corr_heatmap = []
        for i, row_sector in enumerate(sector_corr.index):
            for j, col_sector in enumerate(sector_corr.columns):
                val = sector_corr.iloc[i, j]
                corr_heatmap.append({
                    "sector1": row_sector,
                    "sector2": col_sector,
                    "correlation": round(val, 3) if not pd.isna(val) else 0
                })
        
        # Cluster stability analysis
        cluster_stability = state.cluster_stability(window_short=20, window_long=window)
        
        return {
            "engine": 3,
            "name": "Correlation & Crowding Room",
            "universe": universe,
            "sector_count": len(sector_corr.columns),
            "latest": latest,
            "correlation_history": avg_corr_history[-60:],
            "correlation_tail_history": corr_tail_history[-60:],
            "sector_correlation_matrix": corr_heatmap,
            "sectors": list(sector_corr.columns),
            "cluster_stability": cluster_stability
        }
        
    except Exception as e:
        logger.error(f"Engine 3 error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ============================================================================
# ENGINE 4: FLOW & DISTRIBUTION FORENSICS
# ============================================================================

@router.get("/engine/4")
async def engine_flow_distribution(
    universe: str = Query("US"),
    window: int = Query(20)
):
    """
    Engine 4: Flow & Distribution Forensics
    Returns CLV, flow divergence, and accumulation/distribution data.
    """
    try:
        state = await get_or_build_market_state(universe=universe)
        if state.returns is None:
            raise HTTPException(status_code=503, detail="Market state not available")
        
        # Close Location Value
        clv = state.close_location_value()
        flow = state.flow_proxy()
        
        # Cumulative flow and price trend
        cumulative_flow = flow.rolling(window).sum()
        price_trend = state.returns.rolling(window).sum()
        
        # Divergence classification (latest)
        latest_flow = cumulative_flow.iloc[-1]
        latest_trend = price_trend.iloc[-1]
        
        # Classify each ticker
        classifications = []
        for ticker in state.returns.columns:
            f = latest_flow.get(ticker, 0)
            t = latest_trend.get(ticker, 0)
            
            if pd.isna(f) or pd.isna(t):
                continue
                
            if t > 0 and f > 0:
                classification = "accumulation"
            elif t > 0 and f < 0:
                classification = "distribution"  # Stealth selling
            elif t < 0 and f > 0:
                classification = "stealth_accumulation"
            else:
                classification = "liquidation"
            
            classifications.append({
                "ticker": ticker,
                "sector": state.sector_map.get(ticker, "Unknown"),
                "price_trend": round(t * 100, 2),
                "flow": round(f / 1e6, 2),  # In millions
                "classification": classification
            })
        
        # Aggregate by classification
        class_counts = {}
        for c in classifications:
            cls = c["classification"]
            class_counts[cls] = class_counts.get(cls, 0) + 1
        
        # Sector phase plane
        sector_returns = state.sector_returns()
        sector_flow = {}
        for sector in set(state.sector_map.values()):
            tickers = [t for t, s in state.sector_map.items() if s == sector and t in flow.columns]
            if tickers:
                sector_flow[sector] = {
                    "price_trend": round(sector_returns[sector].tail(window).sum() * 100, 2) if sector in sector_returns.columns else 0,
                    "flow": round(flow[tickers].sum(axis=1).tail(window).sum() / 1e6, 2)
                }
        
        # Flow time series
        median_clv = clv.median(axis=1)
        median_flow = flow.median(axis=1)
        
        flow_history = pd.DataFrame({
            "date": median_clv.index.astype(str),
            "median_clv": median_clv.values,
            "median_flow": median_flow.values
        })
        
        return {
            "engine": 4,
            "name": "Flow & Distribution Forensics",
            "universe": universe,
            "ticker_count": len(state.prices.columns),
            "classification_counts": class_counts,
            "ticker_classifications": sorted(classifications, key=lambda x: abs(x["price_trend"]), reverse=True)[:50],
            "sector_phase_plane": [{"sector": s, **v} for s, v in sector_flow.items()],
            "flow_history": flow_history.tail(60).to_dict('records'),
            "distribution_leaders": [c for c in classifications if c["classification"] == "distribution"][:20],
            "accumulation_leaders": [c for c in classifications if c["classification"] == "accumulation"][:20]
        }
        
    except Exception as e:
        logger.error(f"Engine 4 error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ============================================================================
# ENGINE 5: VOLATILITY & TAIL RISK
# ============================================================================

@router.get("/engine/5")
async def engine_volatility_tail(
    universe: str = Query("US"),
    window: int = Query(20)
):
    """
    Engine 5: Volatility & Tail Risk Wall
    Returns realized volatility, tail events, and compression patterns.
    """
    try:
        state = await get_or_build_market_state(universe=universe)
        if state.returns is None:
            raise HTTPException(status_code=503, detail="Market state not available")
        
        # Realized volatility at multiple windows
        vol_20 = state.rolling_volatility(20)
        vol_60 = state.rolling_volatility(60)
        vol_120 = state.rolling_volatility(120)
        
        # Median vol across universe
        median_vol_20 = vol_20.median(axis=1)
        median_vol_60 = vol_60.median(axis=1)
        
        # Vol of vol
        vol_of_vol = vol_20.std(axis=1).rolling(20).std()
        
        # Downside semivolatility
        neg_returns = state.returns.clip(upper=0)
        downside_vol = neg_returns.rolling(window).std() * np.sqrt(252)
        downside_share = (downside_vol / (vol_20 + 1e-10)).median(axis=1)
        
        # Tail events (returns < -2 std)
        mu = state.returns.mean(axis=1)
        sigma = state.returns.std(axis=1)
        tail_threshold = mu - 2 * sigma
        
        tail_events = (state.returns.T < tail_threshold).T.sum(axis=1)
        
        # Vol term structure (latest)
        latest_vol_20 = vol_20.iloc[-1]
        latest_vol_60 = vol_60.iloc[-1]
        latest_vol_120 = vol_120.iloc[-1]
        
        term_structure = []
        for ticker in state.returns.columns:
            v20 = latest_vol_20.get(ticker, 0)
            v60 = latest_vol_60.get(ticker, 0)
            v120 = latest_vol_120.get(ticker, 0)
            if pd.isna(v20) or pd.isna(v60) or pd.isna(v120):
                continue
            term_structure.append({
                "ticker": ticker,
                "sector": state.sector_map.get(ticker, "Unknown"),
                "vol_20": round(v20 * 100, 2),
                "vol_60": round(v60 * 100, 2),
                "vol_120": round(v120 * 100, 2),
                "inverted": bool(v20 > v60 > v120)
            })
        
        # Vol history
        vol_history = pd.DataFrame({
            "date": median_vol_20.index.astype(str),
            "median_vol_20": (median_vol_20 * 100).values,
            "median_vol_60": (median_vol_60 * 100).values,
            "vol_of_vol": vol_of_vol.values,
            "downside_share": downside_share.values,
            "tail_events": tail_events.values
        })
        
        # Sector vol
        sector_vol = {}
        for sector in set(state.sector_map.values()):
            tickers = [t for t, s in state.sector_map.items() if s == sector and t in vol_20.columns]
            if tickers:
                sector_vol[sector] = round(vol_20[tickers].iloc[-1].median() * 100, 2)
        
        # Latest values
        latest = {
            "median_vol_20": round(median_vol_20.iloc[-1] * 100, 2) if not pd.isna(median_vol_20.iloc[-1]) else 0,
            "downside_share": round(downside_share.iloc[-1], 2) if not pd.isna(downside_share.iloc[-1]) else 0.5,
            "tail_events": int(tail_events.iloc[-1]) if not pd.isna(tail_events.iloc[-1]) else 0,
            "date": str(state.dates[-1])
        }
        
        # Vol compression break detection
        vol_compression_breaks = state.vol_compression_break(window=window)
        
        return {
            "engine": 5,
            "name": "Volatility & Tail Risk Wall",
            "universe": universe,
            "ticker_count": len(state.prices.columns),
            "latest": latest,
            "vol_history": vol_history.tail(60).to_dict('records'),
            "term_structure": sorted(term_structure, key=lambda x: x["vol_20"], reverse=True)[:50],
            "sector_volatility": [{"sector": s, "vol_20": v} for s, v in sector_vol.items()],
            "vol_expanders": sorted(term_structure, key=lambda x: x["vol_20"], reverse=True)[:25],
            "vol_compression_breaks": vol_compression_breaks
        }
        
    except Exception as e:
        logger.error(f"Engine 5 error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ============================================================================
# ENGINE 6: CROSS-ASSET LINKAGE
# ============================================================================

@router.get("/engine/6")
async def engine_cross_asset_linkage(
    universe: str = Query("US"),
    window: int = Query(60)
):
    """
    Engine 6: Cross-Asset Linkage & Transmission
    Returns anchor correlations, lead-lag, and regime-conditional linkages.
    """
    try:
        state = await get_or_build_market_state(universe=universe)
        if state.returns is None:
            raise HTTPException(status_code=503, detail="Market state not available")
        
        # Get anchor returns
        anchors = state.config["anchors"]
        anchor_returns = state.returns[[a for a in anchors if a in state.returns.columns]]
        sector_returns = state.sector_returns()
        
        # Anchor × Sector correlation matrix
        anchor_sector_corr = []
        for anchor in anchor_returns.columns:
            for sector in sector_returns.columns:
                corr = anchor_returns[anchor].tail(window).corr(sector_returns[sector].tail(window))
                anchor_sector_corr.append({
                    "anchor": anchor,
                    "sector": sector,
                    "correlation": round(corr, 3) if not pd.isna(corr) else 0
                })
        
        # Regime conditional linkage
        benchmark = state.get_benchmark_returns()
        up_days = benchmark > 0
        down_days = benchmark < 0
        
        up_corr = []
        down_corr = []
        for sector in sector_returns.columns:
            sector_ret = sector_returns[sector]
            up_c = benchmark[up_days].corr(sector_ret[up_days])
            down_c = benchmark[down_days].corr(sector_ret[down_days])
            up_corr.append({"sector": sector, "correlation": round(up_c, 3) if not pd.isna(up_c) else 0})
            down_corr.append({"sector": sector, "correlation": round(down_c, 3) if not pd.isna(down_c) else 0})
        
        # Lead-lag analysis (simplified: 1-day lag)
        lead_lag = []
        for anchor in anchor_returns.columns:
            for sector in sector_returns.columns:
                # Lead: anchor t-1 vs sector t
                anchor_lagged = anchor_returns[anchor].shift(1).tail(window)
                sector_curr = sector_returns[sector].tail(window)
                lead_corr = anchor_lagged.corr(sector_curr)
                
                lead_lag.append({
                    "anchor": anchor,
                    "sector": sector,
                    "lag_correlation": round(lead_corr, 3) if not pd.isna(lead_corr) else 0,
                    "lead_days": 1 if lead_corr > 0.3 else 0
                })
        
        # Transmission stability (rolling correlation std)
        stability_history = []
        for i in range(30, len(sector_returns)):
            window_corrs = []
            for sector in sector_returns.columns:
                c = benchmark.iloc[i-30:i].corr(sector_returns[sector].iloc[i-30:i])
                if not pd.isna(c):
                    window_corrs.append(c)
            stability = 1 / (np.std(window_corrs) + 0.01) if window_corrs else 1
            stability_history.append({
                "date": str(sector_returns.index[i]),
                "stability": round(stability, 2)
            })
        
        # Enhanced lead-lag analysis from MarketState
        enhanced_lead_lag = state.lead_lag(anchors=list(anchor_returns.columns), max_lag=5)
        
        return {
            "engine": 6,
            "name": "Cross-Asset Linkage & Transmission",
            "universe": universe,
            "anchor_count": len(anchor_returns.columns),
            "sector_count": len(sector_returns.columns),
            "anchor_sector_matrix": anchor_sector_corr,
            "up_day_linkage": up_corr,
            "down_day_linkage": down_corr,
            "lead_lag_analysis": lead_lag,
            "enhanced_lead_lag": enhanced_lead_lag,
            "stability_history": stability_history[-60:],
            "anchors": list(anchor_returns.columns),
            "sectors": list(sector_returns.columns)
        }
        
    except Exception as e:
        logger.error(f"Engine 6 error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ============================================================================
# ENGINE 7: DAY FINGERPRINT & REGIME ATLAS
# ============================================================================

@router.get("/engine/7")
async def engine_day_fingerprint(
    universe: str = Query("US"),
    top_similar: int = Query(9)
):
    """
    Engine 7: Day Fingerprint & Regime Atlas
    Returns fingerprint vector, similar days, and outcome distributions.
    """
    try:
        state = await get_or_build_market_state(universe=universe)
        if state.returns is None:
            raise HTTPException(status_code=503, detail="Market state not available")
        
        # Compute daily fingerprints
        ad = state.advance_decline()
        pct_above_50 = state.pct_above_ma(50)
        dispersion = state.dispersion()
        herfindahl = state.herfindahl()
        
        illiq = state.amihud_illiquidity()
        median_illiq = illiq.median(axis=1)
        
        sector_returns = state.sector_returns()
        
        # Building fingerprint dataframe
        fingerprints = pd.DataFrame(index=state.returns.index)
        
        # 1. Breadth (AD + pct above)
        fingerprints["breadth"] = (ad["ad_ratio"].rank(pct=True) + pct_above_50.rank(pct=True)) / 2 * 100
        
        # 2. Dispersion
        fingerprints["dispersion"] = dispersion.rank(pct=True) * 100
        
        # 3. Concentration
        fingerprints["concentration"] = herfindahl.rank(pct=True) * 100
        
        # 4. Liquidity stress
        fingerprints["liquidity_stress"] = median_illiq.rank(pct=True) * 100
        
        # 5. Correlation regime
        avg_corr_series = []
        for i in range(60, len(sector_returns)):
            c = sector_returns.iloc[i-60:i].corr()
            mask = np.triu(np.ones_like(c, dtype=bool), k=1)
            avg = c.where(mask).stack().mean()
            avg_corr_series.append(avg if not pd.isna(avg) else 0.5)
        avg_corr = pd.Series([0.5] * 60 + avg_corr_series, index=state.returns.index)
        fingerprints["correlation"] = avg_corr.rank(pct=True) * 100
        
        # 6. Flow divergence (simplified)
        clv = state.close_location_value()
        median_clv = clv.median(axis=1)
        fingerprints["flow"] = median_clv.rank(pct=True) * 100
        
        # 7. Tail clustering
        tails = state.tail_shares()
        fingerprints["tail_risk"] = (tails["left_tail_pct"] + tails["right_tail_pct"]).rank(pct=True) * 100
        
        # 8. Driver concentration (simplified as sector return Herfindahl)
        sector_contrib = sector_returns.abs()
        sector_herfindahl = (sector_contrib.T / sector_contrib.sum(axis=1)).T ** 2
        sector_herfindahl = sector_herfindahl.sum(axis=1)
        fingerprints["driver_concentration"] = sector_herfindahl.rank(pct=True) * 100
        
        fingerprints = fingerprints.dropna()
        
        # Today's fingerprint
        today_fp = fingerprints.iloc[-1]
        
        # Find similar days (Euclidean distance)
        distances = []
        for i in range(len(fingerprints) - 5):  # Exclude last 5 days
            day_fp = fingerprints.iloc[i]
            dist = np.sqrt(((today_fp - day_fp) ** 2).sum())
            distances.append({
                "date": str(fingerprints.index[i]),
                "distance": round(dist, 2),
                "fingerprint": {col: round(day_fp[col], 1) for col in fingerprints.columns}
            })
        
        # Sort by distance
        distances = sorted(distances, key=lambda x: x["distance"])[:top_similar]
        
        # Get forward returns for similar days
        benchmark = state.get_benchmark_returns()
        similar_outcomes = []
        for d in distances:
            date_idx = fingerprints.index.get_loc(pd.Timestamp(d["date"]))
            if date_idx + 5 < len(benchmark):
                d["forward_1d"] = round(benchmark.iloc[date_idx + 1] * 100, 2) if not pd.isna(benchmark.iloc[date_idx + 1]) else 0
                d["forward_3d"] = round(benchmark.iloc[date_idx:date_idx+3].sum() * 100, 2)
                d["forward_5d"] = round(benchmark.iloc[date_idx:date_idx+5].sum() * 100, 2)
                similar_outcomes.append(d)
        
        # Regime drift (30D trend)
        drift = {}
        for col in fingerprints.columns:
            recent = fingerprints[col].tail(30)
            drift[col] = round(recent.iloc[-1] - recent.iloc[0], 1)
        
        # Enhanced regime drift from MarketState
        enhanced_regime_drift = state.regime_drift(window=30)
        
        return {
            "engine": 7,
            "name": "Day Fingerprint & Regime Atlas",
            "universe": universe,
            "today_fingerprint": {col: round(today_fp[col], 1) for col in fingerprints.columns},
            "today_date": str(fingerprints.index[-1]),
            "similar_days": similar_outcomes,
            "regime_drift_30d": drift,
            "enhanced_regime_drift": enhanced_regime_drift,
            "fingerprint_history": fingerprints.tail(30).reset_index().rename(columns={"index": "date"}).to_dict('records'),
            "components": list(fingerprints.columns)
        }
        
    except Exception as e:
        logger.error(f"Engine 7 error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ============================================================================
# DRILLDOWN ENDPOINT
# ============================================================================

@router.get("/drilldown/{ticker}")
async def drilldown_ticker(
    ticker: str,
    universe: str = Query("US")
):
    """
    Get detailed metrics for a single ticker.
    Used for drill-down modals.
    """
    try:
        state = await get_or_build_market_state(universe=universe)
        if state.returns is None:
            raise HTTPException(status_code=503, detail="Market state not available")
        
        if ticker not in state.returns.columns:
            raise HTTPException(status_code=404, detail=f"Ticker {ticker} not found")
        
        # Price history
        prices = state.prices[ticker].tail(60)
        returns = state.returns[ticker].tail(60)
        
        # Metrics
        vol_20 = state.rolling_volatility(20)[ticker].iloc[-1]
        vol_60 = state.rolling_volatility(60)[ticker].iloc[-1]
        
        illiq = state.amihud_illiquidity()[ticker].iloc[-1]
        
        clv = state.close_location_value()[ticker].tail(20)
        
        # Correlation to benchmark
        benchmark = state.get_benchmark_returns()
        corr_to_bench = returns.corr(benchmark.tail(60))
        
        return {
            "ticker": ticker,
            "sector": state.sector_map.get(ticker, "Unknown"),
            "price_history": series_to_records(prices, "price"),
            "return_history": series_to_records(returns * 100, "return"),
            "metrics": {
                "vol_20": round(vol_20 * 100, 2) if not pd.isna(vol_20) else 0,
                "vol_60": round(vol_60 * 100, 2) if not pd.isna(vol_60) else 0,
                "illiquidity": float(illiq) if not pd.isna(illiq) else 0,
                "avg_clv": round(clv.mean(), 3) if not clv.empty else 0,
                "corr_to_benchmark": round(corr_to_bench, 3) if not pd.isna(corr_to_bench) else 0
            }
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Drilldown error: {e}")
        raise HTTPException(status_code=500, detail=str(e))
