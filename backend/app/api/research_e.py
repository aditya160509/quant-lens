"""
Research E Router
FastAPI endpoints for Cluster E research modules.
"""

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field
from typing import List, Dict, Any, Optional
from datetime import datetime, timedelta
import pandas as pd
import numpy as np
import yfinance as yf
import logging

from app.services.cluster_e_service import (
    zscore_single, percentile_rank_single, daily_return, realized_vol_scalar,
    rolling_mean, rolling_std, sharpe_ratio, correlation_matrix,
    sma, ema, rsi, macd, detect_golden_cross, detect_death_cross,
    detect_rsi_oversold, detect_rsi_overbought, detect_volume_spike, detect_breakout,
    stress_from_zscore, risk_label, candle_sentiment, sentiment_label,
    REPLAY_PRESETS, get_replay_dates
)
from app.services.fundamentals_service import get_fundamentals, get_fundamentals_compact
from app.services.research_cache import research_cache
from app.services.universe import get_universe_list

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api", tags=["Research E"])


# ===== Request/Response Models =====

class NarrativeRequest(BaseModel):
    as_of: Optional[str] = None
    market_proxy: str = "SPY"
    region: str = "US"
    lookback_days: int = 60
    include: Dict[str, bool] = Field(default_factory=lambda: {
        "breadth": True, "vol": True, "factors": True, "macro": True, "sentiment": True
    })


class RiskScoreRequest(BaseModel):
    as_of: Optional[str] = None
    lookback_days: int = 252
    components: List[str] = Field(default_factory=lambda: ["vix", "realized_vol", "breadth"])
    region: str = "US"
    weights: Dict[str, float] = Field(default_factory=lambda: {
        "vix": 0.25, "realized_vol": 0.25, "breadth": 0.25
    })


class ReplayRequest(BaseModel):
    mode: str = "preset"  # "preset" or "custom"
    preset: Optional[str] = "covid"
    start: Optional[str] = None
    end: Optional[str] = None
    assets: List[str] = Field(default_factory=lambda: ["SPY"])
    include: List[str] = Field(default_factory=lambda: ["risk_score", "sentiment"])


class ScanRequest(BaseModel):
    pattern: str = "golden_cross"
    tickers: List[str] = Field(default_factory=lambda: ["ALL"])
    params: Dict[str, Any] = Field(default_factory=lambda: {
        "lookback_days": 365, "window_fast": 50, "window_slow": 200
    })
    limit: int = 200


class SharpeRadarRequest(BaseModel):
    tickers: List[str] = Field(default_factory=lambda: ["SPY", "QQQ"])
    horizons: List[int] = Field(default_factory=lambda: [21, 63, 126, 252])
    lookback_days: int = 756


class SpiderRequest(BaseModel):
    ref: str = "SPY"
    tickers: List[str] = Field(default_factory=lambda: ["SPY", "QQQ", "GLD"])
    window: int = 60
    lookback_days: int = 252


# ===== Helper Functions =====

def _fetch_prices(ticker: str, days: int) -> pd.DataFrame:
    """Fetch historical prices from yfinance."""
    end = datetime.now()
    start = end - timedelta(days=days + 10)
    
    try:
        df = yf.download(ticker, start=start, end=end, progress=False)
        if df.empty:
            return pd.DataFrame()
        df = df.tail(days)
        return df
    except Exception as e:
        logger.error(f"Error fetching {ticker}: {e}")
        return pd.DataFrame()


def _compute_breadth(tickers: List[str], days: int = 1) -> float:
    """Compute market breadth as % of tickers with positive returns."""
    up_count = 0
    total = 0
    
    for ticker in tickers[:100]:  # Limit for performance
        try:
            df = _fetch_prices(ticker, 10)
            if len(df) >= 2:
                ret = (df['Close'].iloc[-1] / df['Close'].iloc[-1-days] - 1)
                if hasattr(ret, 'iloc'):
                    ret = ret.iloc[0]
                if ret > 0:
                    up_count += 1
                total += 1
        except:
            pass
    
    return up_count / max(total, 1)


# ===== E1: Narrative Analytics =====

@router.post("/research/e/narrative")
async def compute_narrative(request: NarrativeRequest):
    """
    E1: Generate structured market narrative from computed metrics.
    """
    cache_key = {"endpoint": "narrative", **request.dict()}
    cached, hit = research_cache.get_compute(cache_key)
    if hit:
        return cached
    
    try:
        proxy = request.market_proxy
        df = _fetch_prices(proxy, request.lookback_days + 30)
        
        if df.empty:
            raise HTTPException(status_code=404, detail=f"No data for {proxy}")
        
        # Compute metrics
        close = df['Close']
        if hasattr(close, 'iloc'):
            close = close.squeeze()
        
        returns = daily_return(close)
        
        ret_1d = float((close.iloc[-1] / close.iloc[-2] - 1)) if len(close) >= 2 else 0
        ret_5d = float((close.iloc[-1] / close.iloc[-6] - 1)) if len(close) >= 6 else 0
        ret_21d = float((close.iloc[-1] / close.iloc[-22] - 1)) if len(close) >= 22 else 0
        
        rv_21d = realized_vol_scalar(returns.tail(21))
        
        # Breadth - Region-aware universal breadth
        region = request.region.upper()
        if region in ["IN", "INDIA"]:
            universe = get_universe_list("india_nse") + get_universe_list("india_bse")
        else:
            universe = get_universe_list("us_equities")
            
        breadth_1d = _compute_breadth(universe, 1)
        
        # Build narrative sections
        sections = []
        
        # Market tone section
        if ret_1d < -0.01:
            tone = "Risk-off day with broad selling pressure."
        elif ret_1d > 0.01:
            tone = "Risk-on day with broad buying interest."
        else:
            tone = "Neutral market tone with mixed signals."
        
        if ret_5d < -0.03:
            tone += " Weekly trend is bearish."
        elif ret_5d > 0.03:
            tone += " Weekly trend is bullish."
        
        sections.append({
            "key": "market",
            "title": "Market Tone",
            "text": tone
        })
        
        # Volatility section
        if request.include.get("vol", True):
            if rv_21d > 0.25:
                vol_text = f"Elevated volatility regime at {rv_21d*100:.1f}% annualized. Risk management essential."
            elif rv_21d < 0.12:
                vol_text = f"Low volatility environment at {rv_21d*100:.1f}% annualized. Complacency risk."
            else:
                vol_text = f"Normal volatility at {rv_21d*100:.1f}% annualized."
            
            sections.append({
                "key": "vol",
                "title": "Volatility",
                "text": vol_text
            })
        
        # Risk notes
        risk_notes = []
        if ret_21d < -0.10:
            risk_notes.append("Monthly drawdown exceeds 10%.")
        if rv_21d > 0.30:
            risk_notes.append("Volatility spike indicates stress.")
        
        sections.append({
            "key": "risk",
            "title": "Risk Notes",
            "text": " ".join(risk_notes) if risk_notes else "No elevated risk signals."
        })
        
        # Determine overall risk level
        if rv_21d > 0.30 or ret_21d < -0.15:
            risk_level = "stressed"
        elif rv_21d > 0.20 or ret_21d < -0.08:
            risk_level = "cautious"
        elif rv_21d < 0.12 and ret_21d > 0:
            risk_level = "calm"
        else:
            risk_level = "neutral"
        
        result = {
            "as_of": datetime.now().strftime("%Y-%m-%d"),
            "market_proxy": proxy,
            "inputs": {
                "ret_1d": round(ret_1d, 4),
                "ret_5d": round(ret_5d, 4),
                "ret_21d": round(ret_21d, 4),
                "rv_21d": round(rv_21d, 4),
                "breadth_1d": round(breadth_1d, 2)
            },
            "sections": sections,
            "signals": {
                "risk_level": risk_level
            },
            "meta": {
                "source": ["yfinance"],
                "cache_ttl_sec": 300
            }
        }
        
        research_cache.set_compute(cache_key, result)
        return result
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Narrative error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ===== E2: Risk Thermometer =====

@router.post("/research/e/risk_score")
async def compute_risk_score(request: RiskScoreRequest):
    """
    E2: Compute composite risk score (0-100) with explainable components.
    """
    cache_key = {"endpoint": "risk_score", **request.dict()}
    cached, hit = research_cache.get_compute(cache_key)
    if hit:
        return cached
    
    try:
        # Get market data
        spy = _fetch_prices("SPY", request.lookback_days + 30)
        vix = _fetch_prices("^VIX", request.lookback_days + 30)
        
        if spy.empty:
            raise HTTPException(status_code=404, detail="Could not fetch market data")
        
        components = {}
        weights = request.weights
        
        # VIX component
        if "vix" in request.components and not vix.empty:
            vix_close = vix['Close'].squeeze()
            current_vix = float(vix_close.iloc[-1])
            vix_z = zscore_single(current_vix, vix_close.values)
            vix_stress = stress_from_zscore(vix_z)
            
            components["vix"] = {
                "value": round(current_vix, 2),
                "z": round(vix_z, 2),
                "stress": round(vix_stress, 3),
                "weight": weights.get("vix", 0.25)
            }
        
        # Realized volatility component
        if "realized_vol" in request.components:
            spy_close = spy['Close'].squeeze()
            returns = daily_return(spy_close)
            rv = realized_vol_scalar(returns.tail(21))
            rv_series = returns.rolling(21).std() * np.sqrt(252)
            rv_z = zscore_single(rv, rv_series.dropna().values)
            rv_stress = stress_from_zscore(rv_z)
            
            components["realized_vol"] = {
                "value": round(rv, 4),
                "z": round(rv_z, 2),
                "stress": round(rv_stress, 3),
                "weight": weights.get("realized_vol", 0.25)
            }
        
        # Breadth component
        if "breadth" in request.components:
            region = getattr(request, 'region', 'US').upper()
            if region in ["IN", "INDIA"]:
                universe = get_universe_list("india_nse") + get_universe_list("india_bse")
            else:
                universe = get_universe_list("us_equities")
                
            breadth = _compute_breadth(universe, 1)
            breadth_stress = 1.0 - breadth  # Low breadth = high stress
            
            components["breadth"] = {
                "value": round(breadth, 2),
                "z": 0,
                "stress": round(breadth_stress, 3),
                "weight": weights.get("breadth", 0.25)
            }
        
        # Compute composite score
        total_weight = sum(c["weight"] for c in components.values())
        if total_weight > 0:
            weighted_stress = sum(c["stress"] * c["weight"] for c in components.values())
            score = 100 * weighted_stress / total_weight
        else:
            score = 50
        
        result = {
            "as_of": datetime.now().strftime("%Y-%m-%d"),
            "risk_score": round(score, 1),
            "label": risk_label(score),
            "components": components,
            "meta": {
                "lookback_days": request.lookback_days,
                "cache_ttl_sec": 300
            }
        }
        
        research_cache.set_compute(cache_key, result)
        return result
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Risk score error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ===== E4: Market Replay =====

@router.post("/research/e/replay")
async def compute_replay(request: ReplayRequest):
    """
    E4: Replay historical episodes with synchronized data.
    """
    cache_key = {"endpoint": "replay", **request.dict()}
    cached, hit = research_cache.get_compute(cache_key)
    if hit:
        return cached
    
    try:
        # Determine date range
        if request.mode == "preset" and request.preset:
            dates = get_replay_dates(request.preset)
            if not dates:
                raise HTTPException(status_code=400, detail=f"Unknown preset: {request.preset}")
            start = dates["start"]
            end = dates["end"]
            title = dates.get("title", request.preset)
        else:
            start = request.start
            end = request.end
            title = "Custom Replay"
        
        if not start or not end:
            raise HTTPException(status_code=400, detail="Start and end dates required")
        
        # Fetch data for assets
        timeline = []
        asset_data = {}
        
        for asset in request.assets:
            try:
                df = yf.download(asset, start=start, end=end, progress=False)
                if not df.empty:
                    asset_data[asset] = df
            except:
                pass
        
        if not asset_data:
            raise HTTPException(status_code=404, detail="No data found for assets")
        
        # Build unified timeline
        primary = request.assets[0]
        if primary in asset_data:
            df_main = asset_data[primary]
            
            for idx, row in df_main.iterrows():
                date_str = idx.strftime("%Y-%m-%d")
                point = {
                    "date": date_str,
                    "price": round(float(row['Close'].iloc[0] if hasattr(row['Close'], 'iloc') else row['Close']), 2)
                }
                
                # Add VIX if available
                if "^VIX" in asset_data:
                    vix_df = asset_data["^VIX"]
                    if idx in vix_df.index:
                        vix_val = vix_df.loc[idx, 'Close']
                        if hasattr(vix_val, 'iloc'):
                            vix_val = vix_val.iloc[0]
                        point["vix"] = round(float(vix_val), 2)
                
                timeline.append(point)
        
        result = {
            "start": start,
            "end": end,
            "title": title,
            "preset": request.preset if request.mode == "preset" else None,
            "timeline": timeline,
            "markers": [],
            "meta": {
                "assets": request.assets,
                "cache_ttl_sec": 900
            }
        }
        
        research_cache.set_compute(cache_key, result)
        return result
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Replay error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ===== E5: Pattern Scanner =====

@router.post("/research/e/scan")
async def scan_patterns(request: ScanRequest):
    """
    E5: Scan tickers for technical patterns.
    """
    import time
    start_time = time.time()
    
    cache_key = {"endpoint": "scan", **request.dict()}
    cached, hit = research_cache.get_compute(cache_key)
    if hit:
        return cached
    
    try:
        # Get ticker list
        if "ALL" in request.tickers:
            tickers = get_universe_list()[:request.limit * 2]  # Get more for filtering
        else:
            tickers = request.tickers
        
        results = []
        scanned = 0
        params = request.params
        lookback = params.get("lookback_days", 365)
        
        for ticker in tickers:
            if len(results) >= request.limit:
                break
            
            try:
                df = _fetch_prices(ticker, lookback)
                if df.empty or len(df) < 50:
                    continue
                
                scanned += 1
                close = df['Close'].squeeze()
                volume = df['Volume'].squeeze() if 'Volume' in df.columns else None
                
                signal_found = False
                signal_date = None
                metrics = {}
                
                if request.pattern == "golden_cross":
                    fast = params.get("window_fast", 50)
                    slow = params.get("window_slow", 200)
                    signals = detect_golden_cross(close, fast, slow)
                    
                    if signals.iloc[-1]:
                        signal_found = True
                        signal_date = df.index[-1].strftime("%Y-%m-%d")
                        sma_fast = sma(close, fast).iloc[-1]
                        sma_slow = sma(close, slow).iloc[-1]
                        metrics = {"sma_fast": round(float(sma_fast), 2), "sma_slow": round(float(sma_slow), 2)}
                
                elif request.pattern == "death_cross":
                    fast = params.get("window_fast", 50)
                    slow = params.get("window_slow", 200)
                    signals = detect_death_cross(close, fast, slow)
                    
                    if signals.iloc[-1]:
                        signal_found = True
                        signal_date = df.index[-1].strftime("%Y-%m-%d")
                
                elif request.pattern == "rsi_oversold":
                    thresh = params.get("rsi_thresh", 30)
                    signals = detect_rsi_oversold(close, threshold=thresh)
                    
                    if signals.iloc[-1]:
                        signal_found = True
                        signal_date = df.index[-1].strftime("%Y-%m-%d")
                        rsi_val = rsi(close).iloc[-1]
                        metrics = {"rsi": round(float(rsi_val), 2)}
                
                elif request.pattern == "rsi_overbought":
                    thresh = params.get("rsi_thresh", 70)
                    signals = detect_rsi_overbought(close, threshold=thresh)
                    
                    if signals.iloc[-1]:
                        signal_found = True
                        signal_date = df.index[-1].strftime("%Y-%m-%d")
                        rsi_val = rsi(close).iloc[-1]
                        metrics = {"rsi": round(float(rsi_val), 2)}
                
                elif request.pattern == "volume_spike" and volume is not None:
                    thresh = params.get("vol_z", 2.0)
                    signals = detect_volume_spike(volume, threshold=thresh)
                    
                    if signals.iloc[-1]:
                        signal_found = True
                        signal_date = df.index[-1].strftime("%Y-%m-%d")
                
                elif request.pattern == "breakout":
                    window = params.get("breakout_window", 55)
                    high = df['High'].squeeze() if 'High' in df.columns else close
                    signals = detect_breakout(high, close, window)
                    
                    if signals.iloc[-1]:
                        signal_found = True
                        signal_date = df.index[-1].strftime("%Y-%m-%d")
                
                if signal_found:
                    results.append({
                        "ticker": ticker,
                        "signal_date": signal_date,
                        "confidence": 0.6,  # Placeholder
                        "metrics": metrics
                    })
                
            except Exception as e:
                logger.debug(f"Scan error for {ticker}: {e}")
                continue
        
        runtime = int((time.time() - start_time) * 1000)
        
        result = {
            "pattern": request.pattern,
            "as_of": datetime.now().strftime("%Y-%m-%d"),
            "results": results[:request.limit],
            "stats": {
                "scanned": scanned,
                "matched": len(results),
                "runtime_ms": runtime
            },
            "meta": {
                "cache_ttl_sec": 600
            }
        }
        
        research_cache.set_compute(cache_key, result)
        return result
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Scan error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ===== E6: Sharpe Radar =====

@router.post("/research/e/sharpe_radar")
async def compute_sharpe_radar(request: SharpeRadarRequest):
    """
    E6: Compute rolling Sharpe for multiple assets and horizons.
    """
    cache_key = {"endpoint": "sharpe_radar", **request.dict()}
    cached, hit = research_cache.get_compute(cache_key)
    if hit:
        return cached
    
    try:
        series = []
        
        for ticker in request.tickers:
            df = _fetch_prices(ticker, request.lookback_days + 30)
            if df.empty:
                continue
            
            close = df['Close'].squeeze()
            returns = daily_return(close)
            
            ticker_values = {}
            for horizon in request.horizons:
                if len(returns) >= horizon:
                    sharpe = sharpe_ratio(returns.tail(horizon))
                    ticker_values[str(horizon)] = round(sharpe, 2)
                else:
                    ticker_values[str(horizon)] = None
            
            series.append({
                "ticker": ticker,
                "values": ticker_values
            })
        
        result = {
            "as_of": datetime.now().strftime("%Y-%m-%d"),
            "horizons": request.horizons,
            "series": series,
            "meta": {
                "cache_ttl_sec": 300
            }
        }
        
        research_cache.set_compute(cache_key, result)
        return result
        
    except Exception as e:
        logger.error(f"Sharpe radar error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ===== E7: Fundamentals =====

@router.get("/fundamentals/{ticker}")
async def get_ticker_fundamentals(ticker: str, compact: bool = Query(False)):
    """
    E7: Get corporate fundamentals for a ticker.
    """
    cache_key = {"endpoint": "fundamentals", "ticker": ticker, "compact": compact}
    cached, hit = research_cache.get_compute(cache_key)
    if hit:
        return cached
    
    try:
        if compact:
            result = get_fundamentals_compact(ticker.upper())
        else:
            result = get_fundamentals(ticker.upper())
        
        if "error" in result and result.get("error"):
            raise HTTPException(status_code=404, detail=result["error"])
        
        # Set longer TTL for fundamentals
        research_cache._compute_cache[research_cache._hash_payload(cache_key)] = (
            result, datetime.now()
        )
        
        return result
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Fundamentals error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ===== E9: Sentiment =====

@router.get("/sentiment/market")
async def get_market_sentiment(
    tickers: str = Query("SPY,QQQ,IWM"),
    lookback: int = Query(30)
):
    """
    E9: Get market-wide sentiment from price action.
    """
    cache_key = {"endpoint": "sentiment_market", "tickers": tickers, "lookback": lookback}
    cached, hit = research_cache.get_compute(cache_key)
    if hit:
        return cached
    
    try:
        ticker_list = [t.strip() for t in tickers.split(",")]
        scores = []
        series = []
        
        for ticker in ticker_list:
            df = _fetch_prices(ticker, lookback + 30)
            if df.empty:
                continue
            
            # Compute per-day sentiment
            df = df.tail(lookback)
            vol_series = df['Volume'].squeeze() if 'Volume' in df.columns else pd.Series([1] * len(df))
            vol_mean = vol_series.rolling(20).mean()
            vol_std = vol_series.rolling(20).std().replace(0, 1)
            vol_z = (vol_series - vol_mean) / vol_std
            
            close = df['Close'].squeeze()
            open_p = df['Open'].squeeze()
            high = df['High'].squeeze()
            low = df['Low'].squeeze()
            
            daily_scores = []
            for i in range(1, len(df)):
                score = candle_sentiment(
                    float(open_p.iloc[i]),
                    float(high.iloc[i]),
                    float(low.iloc[i]),
                    float(close.iloc[i]),
                    float(vol_series.iloc[i]),
                    float(close.iloc[i-1]),
                    float(vol_z.iloc[i]) if pd.notna(vol_z.iloc[i]) else 0
                )
                daily_scores.append(score)
            
            if daily_scores:
                avg_score = np.mean(daily_scores)
                scores.append(avg_score)
                series.append({
                    "ticker": ticker,
                    "score": round(avg_score, 3),
                    "label": sentiment_label(avg_score)
                })
        
        market_score = float(np.mean(scores)) if scores else 0
        
        result = {
            "as_of": datetime.now().strftime("%Y-%m-%d"),
            "market_score": round(market_score, 3),
            "label": sentiment_label(market_score),
            "series": series,
            "meta": {
                "lookback": lookback,
                "cache_ttl_sec": 300
            }
        }
        
        research_cache.set_compute(cache_key, result)
        return result
        
    except Exception as e:
        logger.error(f"Market sentiment error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/sentiment/asset")
async def get_asset_sentiment(
    ticker: str = Query(...),
    lookback: int = Query(90)
):
    """
    E9: Get sentiment for a single asset over time.
    """
    cache_key = {"endpoint": "sentiment_asset", "ticker": ticker, "lookback": lookback}
    cached, hit = research_cache.get_compute(cache_key)
    if hit:
        return cached
    
    try:
        df = _fetch_prices(ticker, lookback + 30)
        if df.empty:
            raise HTTPException(status_code=404, detail=f"No data for {ticker}")
        
        df = df.tail(lookback)
        
        vol_series = df['Volume'].squeeze() if 'Volume' in df.columns else pd.Series([1] * len(df))
        vol_mean = vol_series.rolling(20).mean()
        vol_std = vol_series.rolling(20).std().replace(0, 1)
        vol_z = (vol_series - vol_mean) / vol_std
        
        close = df['Close'].squeeze()
        open_p = df['Open'].squeeze()
        high = df['High'].squeeze()
        low = df['Low'].squeeze()
        
        series = []
        for i in range(1, len(df)):
            score = candle_sentiment(
                float(open_p.iloc[i]),
                float(high.iloc[i]),
                float(low.iloc[i]),
                float(close.iloc[i]),
                float(vol_series.iloc[i]),
                float(close.iloc[i-1]),
                float(vol_z.iloc[i]) if pd.notna(vol_z.iloc[i]) else 0
            )
            series.append({
                "date": df.index[i].strftime("%Y-%m-%d"),
                "score": round(score, 3),
                "label": sentiment_label(score)
            })
        
        avg_score = np.mean([s["score"] for s in series]) if series else 0
        
        result = {
            "ticker": ticker.upper(),
            "as_of": datetime.now().strftime("%Y-%m-%d"),
            "current_score": round(series[-1]["score"], 3) if series else 0,
            "current_label": series[-1]["label"] if series else "neutral",
            "avg_score": round(avg_score, 3),
            "series": series,
            "meta": {
                "lookback": lookback,
                "cache_ttl_sec": 600
            }
        }
        
        research_cache.set_compute(cache_key, result)
        return result
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Asset sentiment error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ===== E10: Spider Chart =====

@router.post("/research/e/spider")
async def compute_spider(request: SpiderRequest):
    """
    E10: Compute cross-asset correlations for spider chart.
    """
    cache_key = {"endpoint": "spider", **request.dict()}
    cached, hit = research_cache.get_compute(cache_key)
    if hit:
        return cached
    
    try:
        # Fetch returns for all tickers including reference
        all_tickers = [request.ref] + [t for t in request.tickers if t != request.ref]
        returns_dict = {}
        
        for ticker in all_tickers:
            df = _fetch_prices(ticker, request.lookback_days + 30)
            if df.empty:
                continue
            
            close = df['Close'].squeeze()
            returns = daily_return(close).tail(request.window)
            returns_dict[ticker] = returns
        
        if request.ref not in returns_dict:
            raise HTTPException(status_code=404, detail=f"No data for reference {request.ref}")
        
        ref_returns = returns_dict[request.ref]
        
        # Compute correlations vs reference
        axes = []
        for ticker in request.tickers:
            if ticker == request.ref:
                corr = 1.0
            elif ticker in returns_dict:
                # Align series
                combined = pd.DataFrame({
                    "ref": ref_returns,
                    "other": returns_dict[ticker]
                }).dropna()
                
                if len(combined) >= 10:
                    corr = combined["ref"].corr(combined["other"])
                else:
                    corr = None
            else:
                corr = None
            
            axes.append({
                "ticker": ticker,
                "corr": round(float(corr), 3) if corr is not None else None
            })
        
        result = {
            "ref": request.ref,
            "window": request.window,
            "as_of": datetime.now().strftime("%Y-%m-%d"),
            "axes": axes,
            "meta": {
                "cache_ttl_sec": 300
            }
        }
        
        research_cache.set_compute(cache_key, result)
        return result
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Spider error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ===== E3: Terminal Log (Optional) =====

class TerminalLogRequest(BaseModel):
    command: str
    resolved: Dict[str, Any]
    ok: bool
    ts: str


@router.post("/terminal/log")
async def log_terminal_command(request: TerminalLogRequest):
    """
    E3: Log terminal command history (optional backend).
    """
    logger.info(f"Terminal: {request.command} -> {request.resolved} (ok={request.ok})")
    return {"ok": True}
