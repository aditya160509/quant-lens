"""
Historical Price Data API
=========================
Endpoints for managing and querying stored price data.
"""

from fastapi import APIRouter, Query, HTTPException
from typing import List, Optional, Dict
import logging

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/prices", tags=["Historical Prices"])


@router.get("/stats")
async def get_storage_stats():
    """
    Get statistics about stored historical price data.
    
    Returns:
        - Number of tickers stored
        - Total storage size
        - Last update times
    """
    try:
        from app.services.historical_price_service import get_storage_stats
        return get_storage_stats()
    except Exception as e:
        logger.error(f"Failed to get storage stats: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")


@router.get("/stored")
async def get_stored_tickers():
    """
    Get list of all tickers with stored historical data.
    """
    try:
        from app.services.historical_price_service import get_stored_tickers
        tickers = get_stored_tickers()
        return {
            "count": len(tickers),
            "tickers": tickers
        }
    except Exception as e:
        logger.error(f"Failed to get stored tickers: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")


@router.get("/coverage")
async def check_coverage(
    tickers: str = Query(..., description="Comma-separated list of tickers")
):
    """
    Check data coverage for specified tickers.
    
    Returns which tickers have stored data and their date ranges.
    """
    try:
        from app.services.historical_price_service import check_data_coverage
        
        ticker_list = [t.strip().upper() for t in tickers.split(",")]
        coverage = check_data_coverage(ticker_list)
        
        has_data = sum(1 for c in coverage.values() if c["has_data"])
        
        return {
            "total_requested": len(ticker_list),
            "has_data": has_data,
            "missing": len(ticker_list) - has_data,
            "coverage": coverage
        }
    except Exception as e:
        logger.error(f"Failed to check coverage: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")


@router.get("/historical/{ticker}")
async def get_historical_prices(
    ticker: str,
    period: str = Query("2y", description="Period: 1mo, 3mo, 6mo, 1y, 2y, 5y, max"),
    format: str = Query("json", description="Response format: json or csv")
):
    """
    Get historical prices for a ticker.
    
    Uses CSV-first approach - loads from stored data when available,
    falls back to yfinance only when necessary.
    """
    try:
        from app.services.historical_price_service import get_historical_prices
        
        df = get_historical_prices(ticker.upper(), period=period)
        
        if df.empty:
            raise HTTPException(status_code=404, detail=f"No data found for {ticker}")
        
        if format == "csv":
            return df.to_csv()
        
        # JSON format
        return {
            "ticker": ticker.upper(),
            "period": period,
            "rows": len(df),
            "start_date": str(df.index.min().date()),
            "end_date": str(df.index.max().date()),
            "data": df.reset_index().to_dict(orient="records")
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get historical prices for {ticker}: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")


@router.get("/returns/{ticker}")
async def get_ticker_returns(
    ticker: str,
    period: str = Query("1y", description="Period for returns calculation")
):
    """
    Get daily returns for a ticker.
    """
    try:
        from app.services.historical_price_service import get_returns
        
        returns = get_returns(ticker.upper(), period=period)
        
        if returns.empty:
            raise HTTPException(status_code=404, detail=f"No data found for {ticker}")
        
        return {
            "ticker": ticker.upper(),
            "period": period,
            "count": len(returns),
            "mean_daily_return": float(returns.mean()),
            "std_daily_return": float(returns.std()),
            "annualized_volatility": float(returns.std() * (252 ** 0.5)),
            "data": returns.to_dict()
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get returns for {ticker}: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")


@router.post("/clear-cache")
async def clear_memory_cache():
    """
    Clear in-memory price cache.
    """
    try:
        from app.services.historical_price_service import clear_cache
        clear_cache()
        return {"status": "success", "message": "In-memory cache cleared"}
    except Exception as e:
        logger.error(f"Failed to clear cache: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")
