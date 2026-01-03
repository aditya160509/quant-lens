"""
QUANT360 Screener API
=====================

Professional-grade multi-asset screener with unified evaluation engine.
"""

from fastapi import APIRouter, Query, Body, HTTPException
from typing import Optional, List, Dict, Any
from pydantic import BaseModel
import logging
import json
from datetime import datetime

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/screener", tags=["QUANT360 Screener"])


# =============================================================================
# PYDANTIC MODELS FOR API
# =============================================================================

class ConditionModel(BaseModel):
    field: str
    operator: str
    value: Any
    condition_type: str = "indicator"
    missing_policy: str = "exclude"
    weight: float = 1.0
    source_tab: Optional[str] = None
    label: Optional[str] = None


class ScreenerStateModel(BaseModel):
    universe: str = "INDIA"
    time_window: str = "60D"
    lookback_days: int = 60
    active_tab: str = "tradeable"
    conditions: List[ConditionModel] = []
    formula_mode: bool = False
    filter_formula: Optional[str] = None
    rank_formula: Optional[str] = None
    sort_by: str = "score"
    sort_desc: bool = True
    max_results: int = 100


class SavedScanModel(BaseModel):
    name: str
    description: Optional[str] = ""
    tags: List[str] = []
    state: ScreenerStateModel


# In-memory storage for saved scans (would be DB in production)
_saved_scans: Dict[str, Dict] = {}


# =============================================================================
# UNIVERSE ENDPOINTS
# =============================================================================

@router.get("/universes")
async def get_available_universes():
    """
    Get available universes for the screener dropdown.
    Returns asset types with their symbol counts.
    """
    from app.services.universe import (
        UNIVERSE, get_available_asset_types, get_symbols_by_asset_type, stats
    )
    
    universe_stats = stats()
    
    universes = []
    for asset_type in ["EQUITY", "CRYPTO", "FX", "INDEX", "ETF"]:
        symbols = get_symbols_by_asset_type(asset_type)
        if symbols:
            universes.append({
                "id": asset_type.lower(),
                "label": {
                    "EQUITY": "Equities (India + US)",
                    "CRYPTO": "Crypto",
                    "FX": "Forex (FX)",
                    "INDEX": "Global Indices",
                    "ETF": "ETFs",
                }.get(asset_type, asset_type),
                "asset_type": asset_type,
                "count": len(symbols),
                "features": {
                    "fundamentals": asset_type == "EQUITY",
                    "technicals": True,
                    "volume": asset_type not in ["FX"],
                    "tradeable": asset_type not in ["INDEX"],
                }
            })
    
    return {
        "universes": universes,
        "total_symbols": universe_stats["total_symbols"],
        "groups": universe_stats["groups"],
    }


# =============================================================================
# EVALUATION ENDPOINT (Task 2.2)
# =============================================================================

@router.post("/evaluate")
async def evaluate_screener(state: ScreenerStateModel):
    """
    Main evaluation endpoint.
    Takes ScreenerState and returns matching symbols.
    All asset types flow through this single pipeline.
    """
    from app.services.screener_state import ScreenerState, Condition
    from app.services.screener_evaluator import get_evaluator
    
    # Convert Pydantic model to internal state
    internal_state = ScreenerState(
        universe=state.universe,
        time_window=state.time_window,
        lookback_days=state.lookback_days,
        active_tab=state.active_tab,
        conditions=[
            Condition(
                field=c.field,
                operator=c.operator,
                value=c.value,
                condition_type=c.condition_type,
                missing_policy=c.missing_policy,
                weight=c.weight,
                source_tab=c.source_tab,
                label=c.label,
            ) for c in state.conditions
        ],
        formula_mode=state.formula_mode,
        filter_formula=state.filter_formula,
        rank_formula=state.rank_formula,
        sort_by=state.sort_by,
        sort_desc=state.sort_desc,
        max_results=state.max_results,
    )
    
    # Parse formula if in formula mode
    if state.formula_mode and state.filter_formula:
        from app.services.screener_evaluator import get_formula_parser
        parser = get_formula_parser()
        formula_conditions = parser.parse(state.filter_formula)
        internal_state.conditions.extend(formula_conditions)
    
    evaluator = get_evaluator()
    result = await evaluator.evaluate(internal_state)
    
    return result.to_dict()


# =============================================================================
# INDICATOR REGISTRY (Task 5.1)
# =============================================================================

@router.get("/indicators")
async def get_indicators(
    category: Optional[str] = Query(None, description="Filter by category"),
    asset_type: str = Query("EQUITY", description="Asset type for filtering")
):
    """
    Get available indicators from the registry.
    Used to populate indicator dropdowns.
    """
    from app.services.screener_evaluator import INDICATOR_REGISTRY, get_available_indicators
    
    indicators = get_available_indicators(asset_type)
    
    result = []
    for ind in indicators:
        if category and ind.category.lower() != category.lower():
            continue
        result.append({
            "id": ind.id,
            "name": ind.name,
            "category": ind.category,
            "parameters": ind.parameters,
            "output_fields": ind.output_fields,
            "requires_volume": ind.requires_volume,
        })
    
    # Group by category
    categories = {}
    for ind in result:
        cat = ind["category"]
        if cat not in categories:
            categories[cat] = []
        categories[cat].append(ind)
    
    return {
        "indicators": result,
        "by_category": categories,
        "total": len(result)
    }


# =============================================================================
# FORMULA PARSER (Task 7.1)
# =============================================================================

@router.post("/formula/validate")
async def validate_formula(formula: str = Body(..., embed=True)):
    """
    Validate a formula without running it.
    Returns parsed conditions or error message.
    """
    from app.services.screener_evaluator import get_formula_parser
    
    parser = get_formula_parser()
    is_valid, error = parser.validate(formula)
    
    if is_valid:
        conditions = parser.parse(formula)
        return {
            "valid": True,
            "conditions": [
                {"field": c.field, "operator": c.operator, "value": c.value, "label": c.label}
                for c in conditions
            ],
            "condition_count": len(conditions)
        }
    else:
        return {
            "valid": False,
            "error": error
        }


# =============================================================================
# SAVED SCANS (Tasks 8.1, 8.2)
# =============================================================================

@router.post("/scans")
async def save_scan(scan: SavedScanModel):
    """
    Save a complete screening configuration.
    """
    import uuid
    
    scan_id = str(uuid.uuid4())[:8]
    
    _saved_scans[scan_id] = {
        "id": scan_id,
        "name": scan.name,
        "description": scan.description,
        "tags": scan.tags,
        "state": scan.state.dict(),
        "created_at": datetime.utcnow().isoformat(),
        "last_run": None,
        "run_count": 0
    }
    
    return {"id": scan_id, "message": f"Scan '{scan.name}' saved successfully"}


@router.get("/scans")
async def list_scans():
    """
    List all saved scans.
    """
    scans = list(_saved_scans.values())
    return {
        "scans": scans,
        "total": len(scans)
    }


@router.get("/scans/{scan_id}")
async def get_scan(scan_id: str):
    """
    Get a specific saved scan by ID.
    """
    if scan_id not in _saved_scans:
        raise HTTPException(status_code=404, detail="Scan not found")
    
    return _saved_scans[scan_id]


@router.delete("/scans/{scan_id}")
async def delete_scan(scan_id: str):
    """
    Delete a saved scan.
    """
    if scan_id not in _saved_scans:
        raise HTTPException(status_code=404, detail="Scan not found")
    
    del _saved_scans[scan_id]
    return {"message": "Scan deleted successfully"}


@router.post("/scans/{scan_id}/run")
async def run_saved_scan(scan_id: str):
    """
    Load and run a saved scan.
    """
    if scan_id not in _saved_scans:
        raise HTTPException(status_code=404, detail="Scan not found")
    
    scan = _saved_scans[scan_id]
    state_data = scan["state"]
    
    # Update metadata
    scan["last_run"] = datetime.utcnow().isoformat()
    scan["run_count"] = scan.get("run_count", 0) + 1
    
    # Run the evaluation
    state = ScreenerStateModel(**state_data)
    return await evaluate_screener(state)


# =============================================================================
# FEATURE AVAILABILITY (Task 12.2)
# =============================================================================

@router.get("/features/{asset_type}")
async def get_feature_availability(asset_type: str):
    """
    Get feature availability for an asset type.
    Used to show/hide UI elements.
    """
    from app.services.screener_state import get_disabled_features
    
    features = get_disabled_features(asset_type.upper())
    
    # Map to tab visibility
    tabs = {
        "tradeable": True,
        "trend": features["technicals"],
        "volatility": features["technicals"],
        "regime": features["technicals"],
        "liquidity": features["volume_indicators"],
        "rotation": features["technicals"],
        "events": features["fundamentals"],
        "stress": features["technicals"],
        "company": features["fundamentals"],
    }
    
    return {
        "asset_type": asset_type.upper(),
        "features": features,
        "tabs": tabs,
        "trading_enabled": features["trading_actions"]
    }



@router.get("/tradeable-universe")
async def get_tradeable_universe(
    universe_key: str = Query("INDIA", description="Universe: INDIA or US"),
    window: int = Query(60, description="Lookback window in days"),
    min_dollar_volume: float = Query(0, description="Minimum dollar volume filter"),
    sector: Optional[str] = Query(None, description="Filter by sector"),
    liquidity_quality: Optional[str] = Query(None, description="Filter: Stable only"),
):
    """
    Tab 1: Tradeable Universe
    
    What can I safely trade without execution traps?
    Returns: Safe trade list, Caution names, Avoid list
    """
    from app.services.screener_quant360 import get_screener_service
    service = get_screener_service()
    return await service.get_tradeable_universe(
        universe_key=universe_key,
        window=window,
        min_dollar_volume=min_dollar_volume,
        sector=sector,
        liquidity_quality=liquidity_quality,
    )


@router.get("/trend-quality")
async def get_trend_quality(
    universe_key: str = Query("INDIA", description="Universe: INDIA or US"),
    window: int = Query(60, description="Lookback window"),
    trend_direction: Optional[str] = Query(None, description="up, down, or any"),
    min_strength: float = Query(0, description="Minimum trend strength"),
):
    """
    Tab 2: Trend Quality Engine
    
    Is this trend real or about to fail?
    Returns: Durable trends, Late stage, Fake trends
    """
    from app.services.screener_quant360 import get_screener_service
    service = get_screener_service()
    return await service.get_trend_quality(
        universe_key=universe_key,
        window=window,
        trend_direction=trend_direction,
        min_strength=min_strength,
    )


@router.get("/volatility")
async def get_volatility_control(
    universe_key: str = Query("INDIA", description="Universe"),
    window: int = Query(60, description="Lookback window"),
    vol_state: Optional[str] = Query(None, description="Filter by vol regime"),
):
    """
    Tab 3: Volatility & Range Control
    
    Is volatility helping or hurting me?
    Returns: Controlled, Expansion plays, Chaos zone
    """
    from app.services.screener_quant360 import get_screener_service
    service = get_screener_service()
    return await service.get_volatility_control(
        universe_key=universe_key,
        window=window,
        vol_state=vol_state,
    )


@router.get("/regime")
async def get_regime_context(
    universe_key: str = Query("INDIA", description="Universe"),
    window: int = Query(60, description="Lookback window"),
):
    """
    Tab 4: Regime & Market Context
    
    Is the environment aligned with this trade?
    Returns: Tailwinds, Neutral, Headwinds
    """
    from app.services.screener_quant360 import get_screener_service
    service = get_screener_service()
    return await service.get_regime_context(
        universe_key=universe_key,
        window=window,
    )


@router.get("/liquidity")
async def get_liquidity_intelligence(
    universe_key: str = Query("INDIA", description="Universe"),
    window: int = Query(60, description="Lookback window"),
    fragility_threshold: Optional[float] = Query(None, description="Fragility filter"),
):
    """
    Tab 5: Liquidity Intelligence
    
    Where will liquidity disappear first?
    Returns: Stable, Deteriorating, Cliff candidates
    """
    from app.services.screener_quant360 import get_screener_service
    service = get_screener_service()
    return await service.get_liquidity_intelligence(
        universe_key=universe_key,
        window=window,
        fragility_threshold=fragility_threshold,
    )


@router.get("/rotation")
async def get_relative_rotation(
    universe_key: str = Query("INDIA", description="Universe"),
    window: int = Query(20, description="RS lookback window"),
):
    """
    Tab 6: Relative Rotation & Leadership
    
    Who is leading, who is being distributed?
    Returns: True leaders, Weak leaders, Distribution
    """
    from app.services.screener_quant360 import get_screener_service
    service = get_screener_service()
    return await service.get_relative_rotation(
        universe_key=universe_key,
        window=window,
    )


@router.get("/events")
async def get_event_risk(
    universe_key: str = Query("INDIA", description="Universe"),
    window: int = Query(60, description="Lookback window"),
):
    """
    Tab 7: Event & Timing Risk
    
    Should I stay away right now?
    Returns: Safe around events, High event risk
    """
    from app.services.screener_quant360 import get_screener_service
    service = get_screener_service()
    return await service.get_event_risk(
        universe_key=universe_key,
        window=window,
    )


@router.get("/stress")
async def get_stress_proximity(
    universe_key: str = Query("INDIA", description="Universe"),
    window: int = Query(60, description="Lookback window"),
    similarity_threshold: float = Query(0.5, description="Crisis similarity threshold"),
):
    """
    Tab 8: Stress & Crisis Proximity
    
    Does this look like past crashes?
    Returns: Normal, Stress-like, Crisis-like
    """
    from app.services.screener_quant360 import get_screener_service
    service = get_screener_service()
    return await service.get_stress_proximity(
        universe_key=universe_key,
        window=window,
        similarity_threshold=similarity_threshold,
    )


@router.get("/summary")
async def get_screener_summary(
    universe_key: str = Query("INDIA", description="Universe"),
):
    """
    Quick summary across all tabs.
    """
    from app.services.screener_quant360 import get_screener_service
    service = get_screener_service()
    
    # Get quick data from tradeable universe
    result = await service.get_tradeable_universe(universe_key=universe_key)
    
    return {
        "universe": universe_key,
        "names_scanned": result["meta"]["names_scanned"],
        "names_passed": result["meta"]["names_passed"],
        "safe_count": result["quick_stats"]["total_safe"],
        "caution_count": result["quick_stats"]["total_caution"],
        "avoid_count": result["quick_stats"]["total_avoid"],
        "median_dollar_volume": result["quick_stats"]["median_dollar_volume"],
        "median_atr_pct": result["quick_stats"]["median_atr_pct"],
    }


# =============================================================================
# COMPANY ANALYSIS ENDPOINTS (SCREENER.IN STYLE)
# =============================================================================

import math

def clean_for_json(obj):
    """Recursively clean data to be JSON serializable (handle NaN, Inf)."""
    if isinstance(obj, dict):
        return {k: clean_for_json(v) for k, v in obj.items()}
    elif isinstance(obj, list):
        return [clean_for_json(v) for v in obj]
    elif isinstance(obj, float):
        if math.isnan(obj) or math.isinf(obj):
            return None
        return obj
    elif hasattr(obj, 'item'):  # numpy types
        val = obj.item()
        if isinstance(val, float) and (math.isnan(val) or math.isinf(val)):
            return None
        return val
    return obj

@router.get("/company")
async def get_company_analysis(
    symbol: str = Query(..., description="Stock symbol (e.g., AAPL, RELIANCE.NS)"),
):
    """
    Company Analysis - screener.in style
    
    Returns comprehensive company data including:
    - Basic info and summary
    - Key financial ratios
    - Financials (income, balance sheet, cash flow)
    - Quarterly results
    - Peer comparison
    - Shareholding pattern
    """
    import yfinance as yf
    import pandas as pd
    
    def normalize_keys(d):
        """Convert pandas index naming to simpler keys"""
        if not isinstance(d, dict):
            return d
        result = {}
        for k, v in d.items():
            # Convert key to lowercase with underscores
            new_key = str(k).replace(' ', '_').lower() if isinstance(k, str) else str(k)
            result[new_key] = clean_for_json(v)
        return result
    
    def get_peers_for_symbol(sym, sector, industry):
        """Get peer tickers based on symbol and sector"""
        is_indian = sym.endswith('.NS') or sym.endswith('.BO')
        
        # Indian sector peers
        indian_peers = {
            "Communication Services": ["BHARTIARTL.NS", "TATACOMM.NS", "IDEA.NS", "HFCL.NS", "STCINDIA.NS"],
            "Technology": ["TCS.NS", "INFY.NS", "WIPRO.NS", "HCLTECH.NS", "TECHM.NS", "LTI.NS"],
            "Financial Services": ["HDFCBANK.NS", "ICICIBANK.NS", "KOTAKBANK.NS", "SBIN.NS", "AXISBANK.NS", "BAJFINANCE.NS"],
            "Consumer Defensive": ["ITC.NS", "HINDUNILVR.NS", "NESTLEIND.NS", "BRITANNIA.NS", "DABUR.NS", "MARICO.NS"],
            "Consumer Cyclical": ["TITAN.NS", "BAJAJFINSV.NS", "MARUTI.NS", "TATAMOTORS.NS", "M&M.NS", "TRENT.NS"],
            "Energy": ["RELIANCE.NS", "ONGC.NS", "BPCL.NS", "IOC.NS", "GAIL.NS", "NTPC.NS"],
            "Basic Materials": ["TATASTEEL.NS", "HINDALCO.NS", "JSWSTEEL.NS", "VEDL.NS", "COALINDIA.NS", "UPL.NS"],
            "Healthcare": ["SUNPHARMA.NS", "DRREDDY.NS", "CIPLA.NS", "DIVISLAB.NS", "APOLLOHOSP.NS", "BIOCON.NS"],
            "Industrials": ["LT.NS", "ADANIENT.NS", "ADANIPORTS.NS", "SIEMENS.NS", "ABB.NS", "HAVELLS.NS"],
            "Utilities": ["POWERGRID.NS", "NTPC.NS", "TATAPOWER.NS", "ADANIGREEN.NS", "NHPC.NS", "TORNTPOWER.NS"],
            "Real Estate": ["DLF.NS", "GODREJPROP.NS", "OBEROIRLTY.NS", "PRESTIGE.NS", "BRIGADE.NS", "SOBHA.NS"],
        }
        
        # US sector peers
        us_peers = {
            "Technology": ["AAPL", "MSFT", "GOOGL", "META", "NVDA", "AMD", "CRM", "ORCL"],
            "Financial Services": ["JPM", "BAC", "GS", "MS", "C", "WFC", "BLK", "SCHW"],
            "Healthcare": ["JNJ", "PFE", "UNH", "MRK", "ABBV", "LLY", "TMO", "ABT"],
            "Consumer Cyclical": ["AMZN", "TSLA", "HD", "NKE", "MCD", "SBUX", "LOW", "TGT"],
            "Consumer Defensive": ["WMT", "PG", "KO", "PEP", "COST", "PM", "MO", "CL"],
            "Energy": ["XOM", "CVX", "COP", "SLB", "EOG", "OXY", "PSX", "VLO"],
            "Communication Services": ["GOOGL", "META", "NFLX", "DIS", "CMCSA", "T", "VZ", "TMUS"],
            "Industrials": ["CAT", "UNP", "GE", "HON", "BA", "RTX", "DE", "LMT"],
            "Basic Materials": ["LIN", "APD", "SHW", "ECL", "DD", "NEM", "FCX", "NUE"],
            "Utilities": ["NEE", "DUK", "SO", "D", "AEP", "EXC", "SRE", "XEL"],
            "Real Estate": ["AMT", "PLD", "CCI", "EQIX", "PSA", "SPG", "O", "WELL"],
        }
        
        peer_map = indian_peers if is_indian else us_peers
        return [p for p in peer_map.get(sector, [])[:6] if p != sym]
    
    try:
        ticker = yf.Ticker(symbol)
        
        # Get basic info
        info = ticker.info or {}
        
        # Get financials with normalized keys
        financials = {}
        try:
            income_stmt = ticker.income_stmt
            balance_sheet = ticker.balance_sheet
            cash_flow = ticker.cashflow
            
            if income_stmt is not None and not income_stmt.empty:
                financials["income"] = {}
                for col in income_stmt.columns[:4]:
                    date_key = str(col.date()) if hasattr(col, 'date') else str(col)
                    data = {}
                    for idx, val in income_stmt[col].items():
                        key = str(idx).replace(' ', '').lower()
                        data[key] = clean_for_json(val)
                    financials["income"][date_key] = data
                    
            if balance_sheet is not None and not balance_sheet.empty:
                financials["balance"] = {}
                for col in balance_sheet.columns[:4]:
                    date_key = str(col.date()) if hasattr(col, 'date') else str(col)
                    data = {}
                    for idx, val in balance_sheet[col].items():
                        key = str(idx).replace(' ', '').lower()
                        data[key] = clean_for_json(val)
                    financials["balance"][date_key] = data
                    
            if cash_flow is not None and not cash_flow.empty:
                financials["cashflow"] = {}
                for col in cash_flow.columns[:4]:
                    date_key = str(col.date()) if hasattr(col, 'date') else str(col)
                    data = {}
                    for idx, val in cash_flow[col].items():
                        key = str(idx).replace(' ', '').lower()
                        data[key] = clean_for_json(val)
                    financials["cashflow"][date_key] = data
                    
        except Exception as e:
            logger.warning(f"Could not fetch financials for {symbol}: {e}")
        
        # Get quarterly financials
        quarterly = {}
        try:
            quarterly_stmt = ticker.quarterly_income_stmt
            if quarterly_stmt is not None and not quarterly_stmt.empty:
                for col in quarterly_stmt.columns[:8]:
                    date_key = str(col.date()) if hasattr(col, 'date') else str(col)
                    data = {}
                    for idx, val in quarterly_stmt[col].items():
                        key = str(idx).replace(' ', '').lower()
                        data[key] = clean_for_json(val)
                    quarterly[date_key] = data
        except Exception as e:
            logger.warning(f"Could not fetch quarterly data for {symbol}: {e}")
        
        # Get holders
        holders = {}
        try:
            inst_holders = ticker.institutional_holders
            mutual_holders = ticker.mutualfund_holders
            major_holders = ticker.major_holders
            
            if inst_holders is not None and not inst_holders.empty:
                # Convert to records and clean column names
                inst_data = inst_holders.to_dict('records')
                holders["institutional"] = [
                    {
                        "holder": r.get("Holder", r.get("holder", "")),
                        "shares": r.get("Shares", r.get("shares", 0)),
                        "value": r.get("Value", r.get("value", 0)),
                        "pctHeld": r.get("% Out", r.get("pctHeld", 0)),
                    }
                    for r in inst_data
                ]
                
            if mutual_holders is not None and not mutual_holders.empty:
                mutual_data = mutual_holders.to_dict('records')
                holders["mutual"] = [
                    {
                        "holder": r.get("Holder", r.get("holder", "")),
                        "shares": r.get("Shares", r.get("shares", 0)),
                        "value": r.get("Value", r.get("value", 0)),
                        "pctHeld": r.get("% Out", r.get("pctHeld", 0)),
                    }
                    for r in mutual_data
                ]
                
            if major_holders is not None and not major_holders.empty:
                holders["major"] = major_holders.to_dict()
                
        except Exception as e:
            logger.warning(f"Could not fetch holders for {symbol}: {e}")
        
        # Get peers
        peers = []
        sector = info.get("sector", "")
        industry = info.get("industry", "")
        
        try:
            peer_tickers = get_peers_for_symbol(symbol, sector, industry)
            for peer_symbol in peer_tickers[:5]:
                try:
                    peer_ticker = yf.Ticker(peer_symbol)
                    peer_info = peer_ticker.fast_info if hasattr(peer_ticker, 'fast_info') else {}
                    peer_full_info = peer_ticker.info or {}
                    
                    peers.append({
                        "symbol": peer_symbol,
                        "name": peer_full_info.get("shortName", peer_symbol),
                        "price": peer_full_info.get("currentPrice") or peer_full_info.get("regularMarketPrice"),
                        "marketCap": peer_full_info.get("marketCap"),
                        "trailingPE": peer_full_info.get("trailingPE"),
                        "priceToBook": peer_full_info.get("priceToBook"),
                        "sector": peer_full_info.get("sector"),
                    })
                except Exception as pe:
                    logger.warning(f"Could not fetch peer {peer_symbol}: {pe}")
                    continue
        except Exception as e:
            logger.warning(f"Could not fetch peers for {symbol}: {e}")
        
        return clean_for_json({
            "symbol": symbol,
            "info": info,
            "quote": {
                "regularMarketPrice": info.get("currentPrice") or info.get("regularMarketPrice"),
                "regularMarketChange": info.get("regularMarketChange"),
                "regularMarketChangePercent": info.get("regularMarketChangePercent"),
            },
            "financials": financials,
            "quarterly": quarterly,
            "holders": holders,
            "peers": peers,
        })
        
    except Exception as e:
        logger.error(f"Error fetching company data for {symbol}: {e}")
        return {"error": str(e), "symbol": symbol}


@router.get("/chart")
async def get_company_chart(
    symbol: str = Query(..., description="Stock symbol"),
    period: str = Query("1y", description="Chart period: 1mo, 3mo, 6mo, 1y, 2y, 5y, max"),
):
    """
    Get OHLCV chart data for a symbol.
    """
    import yfinance as yf
    
    try:
        ticker = yf.Ticker(symbol)
        
        # Map period to interval
        interval_map = {
            "1mo": "1d",
            "3mo": "1d",
            "6mo": "1d",
            "1y": "1d",
            "2y": "1wk",
            "5y": "1wk",
            "max": "1mo",
        }
        interval = interval_map.get(period, "1d")
        
        hist = ticker.history(period=period, interval=interval)
        
        if hist.empty:
            return {"error": "No data available", "symbol": symbol}
        
        return {
            "symbol": symbol,
            "period": period,
            "dates": hist.index.strftime("%Y-%m-%d").tolist(),
            "open": hist["Open"].tolist(),
            "high": hist["High"].tolist(),
            "low": hist["Low"].tolist(),
            "close": hist["Close"].tolist(),
            "volume": hist["Volume"].tolist(),
        }
        
    except Exception as e:
        logger.error(f"Error fetching chart for {symbol}: {e}")
        return {"error": str(e), "symbol": symbol}
