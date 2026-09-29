from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import List, Optional, Dict, Any
from app.services import watchlists, options, alerts, workspaces, gamification, labs
import numpy as np

router = APIRouter()

# --- Watchlists ---
class WatchlistCreate(BaseModel):
    name: str
    tickers: List[str]

@router.get("/watchlists")
def get_watchlists():
    return watchlists.get_watchlists()

@router.post("/watchlists")
def create_watchlist(wl: WatchlistCreate):
    return watchlists.create_watchlist(wl.name, wl.tickers)

@router.delete("/watchlists/{wl_id}")
def delete_watchlist(wl_id: str):
    return watchlists.delete_watchlist(wl_id)

# --- Options ---
@router.get("/options/{ticker}")
def get_options(ticker: str):
    return options.get_option_chain(ticker)

# --- Alerts ---
class AlertCreate(BaseModel):
    ticker: str
    condition: str
    threshold: float

@router.get("/alerts")
def get_alerts():
    return alerts.get_alerts()

@router.post("/alerts")
def create_alert(alert: AlertCreate):
    return alerts.create_alert(alert.ticker, alert.condition, alert.threshold)

# --- Workspaces ---
class WorkspaceCreate(BaseModel):
    name: str
    config: Dict[str, Any]

@router.get("/workspaces")
def get_workspaces():
    return workspaces.get_workspaces()

@router.post("/workspaces")
def save_workspace(ws: WorkspaceCreate):
    return workspaces.save_workspace(ws.name, ws.config)

# --- Gamification ---
@router.get("/game/status")
def get_game_status():
    return gamification.get_status()

@router.post("/game/event")
def record_game_event(event: Dict[str, Any]):
    return gamification.record_event(event.get("type"), event.get("data"))

# --- Factor Screener ---
@router.get("/factors/screener")
def get_factor_screen(universe: str = "us"):
    return labs.get_factor_screen(universe)

# --- Intraday ---
from app.data_loader import get_price_history

@router.get("/security/{ticker}/intraday")
def get_intraday(ticker: str, interval: str = "5m"):
    # Limit to 1-2 days for intraday
    import datetime
    end = datetime.datetime.now()
    start = end - datetime.timedelta(days=2) # Get last 2 days to be safe
    
    try:
        df = get_price_history(ticker, start=start, end=end, interval=interval)
        if df.empty:
            return {"error": "No data"}
            
        # Format for chart
        # Reset index to get Date as column
        df = df.reset_index()
        
        # Replace NaNs with None for valid JSON
        df = df.replace({np.nan: None})
        
        return {
            "ticker": ticker,
            "interval": interval,
            "dates": df.iloc[:, 0].dt.strftime('%Y-%m-%d %H:%M:%S').tolist(), # First col is Date/Datetime
            "open": df['Open'].values.tolist(),
            "high": df['High'].values.tolist(),
            "low": df['Low'].values.tolist(),
            "close": df['Close'].values.tolist(),
            "volume": df['Volume'].values.tolist()
        }
    except Exception as e:
        return {"error": str(e)}

# --- Macro Impact (module retired) ---
@router.get("/macro/impact")
def get_macro_impact(ticker: str):
    return {
        "ticker": ticker,
        "status": "unavailable",
        "message": "Macro impact module was removed from this build."
    }
