"""
NSE India Stock Market API Integration
Using stock-nse-india package (https://github.com/hi-imcodeman/stock-nse-india)
Features:
- FREE API - No keys needed!
- Rate limiting (3 req/sec default)
- In-memory caching (60s default)
- Fallback mechanisms
- Earnings/Financial data endpoints
- Direct API fallback (no external server needed!)
"""

from fastapi import APIRouter, HTTPException, Query
from typing import Optional, List, Dict, Any
import httpx
import asyncio
from datetime import datetime, timedelta
from functools import lru_cache
import time
import logging
import os

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/nse", tags=["NSE India"])

# Configuration
NSE_API_BASE = os.getenv("NSE_API_BASE", "http://localhost:3001")  # Run: npx stock-nse-india serve --port 3001
USE_DIRECT_API = os.getenv("USE_DIRECT_NSE", "true").lower() == "true"  # Default to direct API (no server needed!)
RATE_LIMIT_CALLS = 3  # Max calls per second
CACHE_TTL_SECONDS = 60  # Cache duration

# Import direct client for fallback/production
try:
    from app.services.nse_direct import nse_direct, NSEDirectClient
    DIRECT_CLIENT_AVAILABLE = True
except ImportError:
    DIRECT_CLIENT_AVAILABLE = False
    logger.warning("[NSE] Direct client not available")


# ===================== RATE LIMITER =====================
class RateLimiter:
    """Token bucket rate limiter"""
    def __init__(self, calls_per_second: int = RATE_LIMIT_CALLS):
        self.calls_per_second = calls_per_second
        self.tokens = calls_per_second
        self.last_update = time.time()
        self._lock = asyncio.Lock()
    
    async def acquire(self):
        async with self._lock:
            now = time.time()
            elapsed = now - self.last_update
            self.tokens = min(self.calls_per_second, self.tokens + elapsed * self.calls_per_second)
            self.last_update = now
            
            if self.tokens < 1:
                wait_time = (1 - self.tokens) / self.calls_per_second
                await asyncio.sleep(wait_time)
                self.tokens = 1
            
            self.tokens -= 1


# ===================== CACHE =====================
class SimpleCache:
    """In-memory cache with TTL"""
    def __init__(self, ttl: int = CACHE_TTL_SECONDS):
        self.ttl = ttl
        self._cache: Dict[str, tuple[Any, float]] = {}
    
    def get(self, key: str) -> Optional[Any]:
        if key in self._cache:
            value, timestamp = self._cache[key]
            if time.time() - timestamp < self.ttl:
                return value
            del self._cache[key]
        return None
    
    def set(self, key: str, value: Any):
        self._cache[key] = (value, time.time())
    
    def clear(self):
        self._cache.clear()


# ===================== NSE CLIENT =====================
class NSEClient:
    """Client for NSE India stock data with rate limiting and caching"""
    
    def __init__(self, base_url: str = NSE_API_BASE):
        self.base_url = base_url
        self.timeout = 30.0
        self.rate_limiter = RateLimiter()
        self.cache = SimpleCache()
        self._is_healthy = None
        self._last_health_check = 0
    
    async def _get(self, endpoint: str, params: dict = None, use_cache: bool = True) -> Any:
        """Make GET request with rate limiting and caching"""
        cache_key = f"{endpoint}:{str(params)}"
        
        # Check cache first
        if use_cache:
            cached = self.cache.get(cache_key)
            if cached is not None:
                logger.debug(f"[NSE] Cache hit: {endpoint}")
                return cached
        
        # Rate limit
        await self.rate_limiter.acquire()
        
        # Make request
        async with httpx.AsyncClient(timeout=self.timeout) as client:
            try:
                response = await client.get(
                    f"{self.base_url}{endpoint}",
                    params=params
                )
                response.raise_for_status()
                data = response.json()
                
                # Cache successful responses
                if use_cache and data:
                    self.cache.set(cache_key, data)
                
                return data
            except httpx.ConnectError:
                # Fallback to direct NSE API if available
                if DIRECT_CLIENT_AVAILABLE and USE_DIRECT_API:
                    logger.info(f"[NSE] Falling back to direct API for {endpoint}")
                    return await self._fallback_direct(endpoint, params)
                raise HTTPException(
                    status_code=503, 
                    detail="NSE API unavailable. Set USE_DIRECT_NSE=true to use direct API."
                )
            except httpx.HTTPError as e:
                raise HTTPException(status_code=500, detail=f"NSE API error: {str(e)}")
    
    async def _fallback_direct(self, endpoint: str, params: dict = None) -> Any:
        """Fallback to direct NSE India API"""
        if not DIRECT_CLIENT_AVAILABLE:
            raise HTTPException(status_code=503, detail="Direct NSE client not available")
        
        # Map endpoints to direct client methods
        if "/api/equity/" in endpoint:
            symbol = endpoint.split("/api/equity/")[-1].split("/")[0]
            if "/historical" in endpoint:
                return await nse_direct.get_equity_details(symbol)
            elif "/trade-info" in endpoint:
                return await nse_direct.get_trade_info(symbol)
            elif "/corporate" in endpoint:
                return await nse_direct.get_corporate_info(symbol)
            elif "/options" in endpoint:
                return await nse_direct.get_option_chain(symbol)
            else:
                return await nse_direct.get_equity_details(symbol)
        elif "/api/marketStatus" in endpoint:
            return await nse_direct.get_market_status()
        elif "/api/indices" in endpoint:
            return await nse_direct.get_indices()
        
        elif "/api/stocks" in endpoint:
            # Return NIFTY_50_STOCKS as fallback
            return NIFTY_50_STOCKS
            
        raise HTTPException(status_code=404, detail=f"No direct API mapping for {endpoint}")
    
    async def is_healthy(self) -> bool:
        """Check if NSE API server is running (cached for 30s)"""
        if time.time() - self._last_health_check < 30:
            return self._is_healthy if self._is_healthy is not None else False
        
        try:
            async with httpx.AsyncClient(timeout=5.0) as client:
                response = await client.get(f"{self.base_url}/")
                self._is_healthy = response.status_code == 200
        except:
            self._is_healthy = False
        
        self._last_health_check = time.time()
        return self._is_healthy
    
    # ===================== CORE METHODS =====================
    
    async def get_all_symbols(self) -> List[str]:
        """Get all NSE stock symbols"""
        return await self._get("/api/stocks")
    
    async def get_equity_details(self, symbol: str) -> dict:
        """Get equity details for a symbol"""
        return await self._get(f"/api/equity/{symbol}")
    
    async def get_equity_historical(self, symbol: str, start: str, end: str) -> dict:
        """Get historical data for equity"""
        return await self._get(f"/api/equity/{symbol}/historical", {
            "start": start,
            "end": end
        })
    
    async def get_equity_intraday(self, symbol: str) -> dict:
        """Get intraday data for equity"""
        return await self._get(f"/api/equity/{symbol}/intraday")
    
    async def get_options_chain(self, symbol: str) -> dict:
        """Get options chain for equity"""
        return await self._get(f"/api/equity/{symbol}/options")
    
    async def get_corporate_info(self, symbol: str) -> dict:
        """Get corporate information (includes earnings data!)"""
        return await self._get(f"/api/equity/{symbol}/corporate")
    
    async def get_trade_info(self, symbol: str) -> dict:
        """Get trading statistics"""
        return await self._get(f"/api/equity/{symbol}/trade-info")
    
    async def get_indices(self) -> dict:
        """Get all market indices"""
        return await self._get("/api/indices")
    
    async def get_index_historical(self, index: str, start: str, end: str) -> dict:
        """Get historical data for index"""
        return await self._get(f"/api/index/{index}/historical", {
            "start": start,
            "end": end
        })
    
    async def get_nifty_50(self) -> dict:
        """Get Nifty 50 index data"""
        return await self._get("/api/index/NIFTY%2050")
    
    async def get_gainers_losers(self, index: str = "NIFTY 50") -> dict:
        """Get top gainers and losers"""
        return await self._get(f"/api/gainers-losers/{index}")
    
    async def get_most_active(self) -> dict:
        """Get most actively traded stocks"""
        return await self._get("/api/most-active")
    
    # ===================== EARNINGS METHODS =====================
    
    async def get_financial_results(self, symbol: str) -> dict:
        """Get quarterly financial results (earnings)"""
        corp = await self.get_corporate_info(symbol)
        return corp.get('financial_results', {})
    
    async def get_board_meetings(self, symbol: str) -> dict:
        """Get upcoming board meetings (earnings announcements)"""
        corp = await self.get_corporate_info(symbol)
        return corp.get('borad_meeting', {})  # Note: NSE typo is intentional
    
    async def get_announcements(self, symbol: str) -> dict:
        """Get corporate announcements"""
        corp = await self.get_corporate_info(symbol)
        return corp.get('latest_announcements', {})
    
    async def get_dividends(self, symbol: str) -> dict:
        """Get dividend history (from corporate actions)"""
        corp = await self.get_corporate_info(symbol)
        actions = corp.get('corporate_actions', {}).get('data', [])
        return [a for a in actions if 'Dividend' in a.get('purpose', '')]
    
    async def get_shareholding(self, symbol: str) -> dict:
        """Get shareholding pattern"""
        corp = await self.get_corporate_info(symbol)
        return corp.get('shareholdings_patterns', {})


# Initialize client
nse_client = NSEClient()


# ===================== TOP INDIAN STOCKS =====================
NIFTY_50_STOCKS = [
    'RELIANCE', 'TCS', 'HDFCBANK', 'INFY', 'ICICIBANK', 'HINDUNILVR', 
    'ITC', 'SBIN', 'BHARTIARTL', 'KOTAKBANK', 'LT', 'BAJFINANCE',
    'AXISBANK', 'ASIANPAINT', 'MARUTI', 'TITAN', 'SUNPHARMA', 
    'ULTRACEMCO', 'WIPRO', 'NESTLEIND', 'HCLTECH', 'TECHM',
    'ONGC', 'NTPC', 'POWERGRID', 'TATAMOTORS', 'TATASTEEL', 
    'ADANIENT', 'ADANIPORTS', 'COALINDIA', 'JSWSTEEL', 'M&M',
    'BAJAJFINSV', 'HDFCLIFE', 'SBILIFE', 'DIVISLAB', 'DRREDDY',
    'CIPLA', 'APOLLOHOSP', 'EICHERMOT', 'HINDALCO', 'GRASIM',
    'BPCL', 'BRITANNIA', 'INDUSINDBK', 'TATACONSUM', 'HEROMOTOCO'
]


# ===================== API ENDPOINTS =====================

@router.get("/symbols")
async def get_all_symbols():
    """Get all available NSE stock symbols"""
    return await nse_client.get_all_symbols()


@router.get("/equity/{symbol}")
async def get_equity_details(symbol: str):
    """Get detailed information for a stock symbol"""
    return await nse_client.get_equity_details(symbol.upper())


@router.get("/equity/{symbol}/historical")
async def get_historical_data(
    symbol: str,
    start: str = Query(default=None, description="Start date YYYY-MM-DD"),
    end: str = Query(default=None, description="End date YYYY-MM-DD"),
    days: int = Query(default=30, description="Number of days if start/end not provided")
):
    """Get historical OHLC data for a stock"""
    if not start:
        end_date = datetime.now()
        start_date = end_date - timedelta(days=days)
        start = start_date.strftime("%Y-%m-%d")
        end = end_date.strftime("%Y-%m-%d")
    
    return await nse_client.get_equity_historical(symbol.upper(), start, end)


@router.get("/equity/{symbol}/intraday")
async def get_intraday_data(symbol: str):
    """Get intraday trading data for a stock"""
    return await nse_client.get_equity_intraday(symbol.upper())


@router.get("/equity/{symbol}/options")
async def get_options_chain(symbol: str):
    """Get options chain for a stock"""
    return await nse_client.get_options_chain(symbol.upper())


@router.get("/equity/{symbol}/corporate")
async def get_corporate_info(symbol: str):
    """Get corporate information for a stock (includes earnings!)"""
    return await nse_client.get_corporate_info(symbol.upper())


@router.get("/equity/{symbol}/trade-info")
async def get_trade_info(symbol: str):
    """Get trading statistics for a stock"""
    return await nse_client.get_trade_info(symbol.upper())


# ===================== EARNINGS ENDPOINTS =====================

@router.get("/equity/{symbol}/earnings")
async def get_earnings(symbol: str):
    """
    Get earnings data for an Indian stock.
    Returns: financial_results, board_meetings, dividends
    """
    try:
        corp = await nse_client.get_corporate_info(symbol.upper())
        
        # Handle case where corp is a list (direct API returns raw corporate actions)
        if isinstance(corp, list):
            # Parse dividends from corporate actions list
            dividends = []
            for a in corp:
                if isinstance(a, dict) and 'dividend' in a.get('subject', '').lower():
                    dividends.append({
                        'ex_date': a.get('exDate'),
                        'purpose': a.get('subject')
                    })
            return {
                'symbol': symbol.upper(),
                'financial_results': [],  # Need separate API call
                'upcoming_board_meetings': [],
                'dividends': dividends,
                'latest_shareholding': None,
                'announcements_count': len(corp)
            }
        
        # Handle dict format (from stock-nse-india server)
        # Parse financial results into standardized format
        financial_results = []
        for r in corp.get('financial_results', {}).get('data', []):
            financial_results.append({
                'period_end': r.get('to_date'),
                'income': float(r.get('income', 0) or 0) / 100000,  # Convert to Lakhs
                'profit_before_tax': float(r.get('reProLossBefTax', 0) or 0) / 100000,
                'profit_after_tax': float(r.get('proLossAftTax', 0) or 0) / 100000,
                'eps_diluted': float(r.get('reDilEPS', 0) or 0),
                'audited': r.get('audited') == 'Audited',
                'consolidated': r.get('consolidated') == 'Consolidated',
                'broadcast_date': r.get('re_broadcast_timestamp')
            })
        
        # Parse board meetings (upcoming earnings)
        board_meetings = []
        for m in corp.get('borad_meeting', {}).get('data', []):
            if 'financial' in m.get('purpose', '').lower() or 'result' in m.get('purpose', '').lower():
                board_meetings.append({
                    'date': m.get('meetingdate'),
                    'purpose': m.get('purpose'),
                    'is_earnings': True
                })
        
        # Parse dividends
        dividends = []
        for a in corp.get('corporate_actions', {}).get('data', []):
            if 'Dividend' in a.get('purpose', ''):
                dividends.append({
                    'ex_date': a.get('exdate'),
                    'purpose': a.get('purpose')
                })
        
        # Parse shareholding
        shareholding = corp.get('shareholdings_patterns', {}).get('data', {})
        latest_holding = None
        if shareholding and isinstance(shareholding, dict):
            try:
                latest_date = max(shareholding.keys())
                latest_holding = {
                    'date': latest_date,
                    'pattern': shareholding[latest_date]
                }
            except Exception:
                pass
        
        return {
            'symbol': symbol.upper(),
            'financial_results': financial_results,
            'upcoming_board_meetings': board_meetings,
            'dividends': dividends,
            'latest_shareholding': latest_holding,
            'announcements_count': len(corp.get('latest_announcements', {}).get('data', []))
        }
    except Exception as e:
        logger.error(f"Error fetching earnings for {symbol}: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")


@router.get("/earnings/upcoming")
async def get_upcoming_earnings(
    limit: int = Query(default=20, description="Number of stocks to check"),
    symbols: str = Query(default=None, description="Comma-separated symbols or empty for Nifty 50")
):
    """
    Get upcoming earnings dates for multiple stocks.
    Checks board meetings for financial results.
    """
    target_symbols = symbols.split(',') if symbols else NIFTY_50_STOCKS[:limit]
    
    results = []
    errors = []
    
    for symbol in target_symbols[:limit]:
        try:
            corp = await nse_client.get_corporate_info(symbol.strip().upper())
            meetings = corp.get('borad_meeting', {}).get('data', [])
            
            for m in meetings:
                purpose = m.get('purpose', '').lower()
                if 'financial' in purpose or 'result' in purpose:
                    meeting_date = m.get('meetingdate')
                    # Parse date and check if upcoming
                    try:
                        date_obj = datetime.strptime(meeting_date, '%d-%b-%Y')
                        if date_obj >= datetime.now():
                            results.append({
                                'symbol': symbol.upper(),
                                'date': meeting_date,
                                'date_iso': date_obj.strftime('%Y-%m-%d'),
                                'purpose': m.get('purpose'),
                                'days_until': (date_obj - datetime.now()).days
                            })
                    except:
                        pass
                    break  # Only get next upcoming meeting
        except Exception as e:
            errors.append({'symbol': symbol, 'error': str(e)})
    
    # Sort by date
    results.sort(key=lambda x: x.get('date_iso', '9999'))
    
    return {
        'upcoming_earnings': results,
        'checked_count': len(target_symbols),
        'errors_count': len(errors)
    }


@router.get("/earnings/history/{symbol}")
async def get_earnings_history(
    symbol: str,
    quarters: int = Query(default=8, description="Number of quarters")
):
    """Get historical earnings data for a stock"""
    try:
        earnings = await get_earnings(symbol)
        return {
            'symbol': symbol.upper(),
            'quarters': earnings['financial_results'][:quarters],
            'dividends': earnings['dividends']
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail="Internal server error")


# ===================== INDEX ENDPOINTS =====================

@router.get("/indices")
async def get_all_indices():
    """Get all market indices"""
    return await nse_client.get_indices()


@router.get("/nifty50")
async def get_nifty_50():
    """Get Nifty 50 index data"""
    return await nse_client.get_nifty_50()


@router.get("/gainers-losers")
async def get_gainers_losers(index: str = Query(default="NIFTY 50")):
    """Get top gainers and losers for an index"""
    return await nse_client.get_gainers_losers(index)


@router.get("/most-active")
async def get_most_active():
    """Get most actively traded stocks"""
    return await nse_client.get_most_active()


# ===================== HEALTH CHECK =====================

@router.get("/health")
async def health_check():
    """Check if NSE API is available (either server or direct)"""
    server_healthy = await nse_client.is_healthy()
    direct_available = DIRECT_CLIENT_AVAILABLE and USE_DIRECT_API
    
    # Consider healthy if either server or direct API is available
    is_healthy = server_healthy or direct_available
    
    return {
        "status": "healthy" if is_healthy else "unhealthy",
        "mode": "direct" if direct_available else "server",
        "nse_server": NSE_API_BASE,
        "direct_api_enabled": USE_DIRECT_API,
        "direct_client_available": DIRECT_CLIENT_AVAILABLE,
        "cache_size": len(nse_client.cache._cache),
        "rate_limit": f"{RATE_LIMIT_CALLS} req/sec",
        "cache_ttl": f"{CACHE_TTL_SECONDS}s",
        "message": None if is_healthy else "Set USE_DIRECT_NSE=true or run 'npx stock-nse-india serve'"
    }


@router.post("/cache/clear")
async def clear_cache():
    """Clear the NSE data cache"""
    nse_client.cache.clear()
    if DIRECT_CLIENT_AVAILABLE:
        nse_direct.cache.clear()
    return {"status": "cache_cleared"}
