"""
Direct NSE India API Client (No external server needed!)
Makes requests directly to NSE India's official APIs.
Perfect for production deployment - no need for stock-nse-india server.
"""

import httpx
import asyncio
from typing import Optional, Dict, Any, List
from datetime import datetime, timedelta
import time
import logging
from functools import wraps

logger = logging.getLogger(__name__)

# NSE India Official API Endpoints
NSE_BASE_URL = "https://www.nseindia.com"
NSE_API_URL = "https://www.nseindia.com/api"

# Headers to mimic browser (required for NSE)
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Accept": "application/json, text/plain, */*",
    "Accept-Language": "en-US,en;q=0.9",
    "Referer": "https://www.nseindia.com/",
    "Connection": "keep-alive",
}


class RateLimiter:
    """Token bucket rate limiter"""
    def __init__(self, calls_per_second: int = 2):
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


class SimpleCache:
    """In-memory cache with TTL"""
    def __init__(self, ttl: int = 60):
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


class NSEDirectClient:
    """
    Direct client for NSE India's official APIs.
    No external server required - makes requests directly to nseindia.com
    """
    
    def __init__(self):
        self.timeout = 30.0
        self.rate_limiter = RateLimiter(calls_per_second=2)
        self.cache = SimpleCache(ttl=60)
        self._cookies = None
        self._cookie_expiry = 0
    
    async def _get_cookies(self, client: httpx.AsyncClient) -> dict:
        """Get session cookies from NSE (required for API access)"""
        if self._cookies and time.time() < self._cookie_expiry:
            return self._cookies
        
        try:
            # Visit main page to get cookies
            response = await client.get(NSE_BASE_URL, headers=HEADERS)
            self._cookies = dict(response.cookies)
            self._cookie_expiry = time.time() + 300  # 5 min expiry
            logger.info("[NSE Direct] Obtained fresh cookies")
            return self._cookies
        except Exception as e:
            logger.error(f"[NSE Direct] Failed to get cookies: {e}")
            return {}
    
    async def _get(self, endpoint: str, use_cache: bool = True) -> Any:
        """Make GET request to NSE API with rate limiting and caching"""
        cache_key = endpoint
        
        # Check cache
        if use_cache:
            cached = self.cache.get(cache_key)
            if cached is not None:
                logger.debug(f"[NSE Direct] Cache hit: {endpoint}")
                return cached
        
        # Rate limit
        await self.rate_limiter.acquire()
        
        async with httpx.AsyncClient(timeout=self.timeout, follow_redirects=True) as client:
            # Get cookies first
            cookies = await self._get_cookies(client)
            
            try:
                response = await client.get(
                    f"{NSE_API_URL}{endpoint}",
                    headers=HEADERS,
                    cookies=cookies
                )
                response.raise_for_status()
                
                # Handle response encoding
                try:
                    data = response.json()
                except Exception:
                    # Try with explicit encoding
                    text = response.content.decode('utf-8', errors='ignore')
                    import json
                    data = json.loads(text)
                
                # Cache successful response
                if use_cache and data:
                    self.cache.set(cache_key, data)
                
                return data
            except httpx.HTTPStatusError as e:
                logger.error(f"[NSE Direct] HTTP error: {e}")
                return {"error": str(e), "status_code": e.response.status_code}
            except Exception as e:
                logger.error(f"[NSE Direct] Request error: {e}")
                return {"error": str(e)}
    
    # ===================== EQUITY DATA =====================
    
    async def get_equity_details(self, symbol: str) -> dict:
        """Get equity details for a symbol"""
        return await self._get(f"/quote-equity?symbol={symbol.upper()}")
    
    async def get_trade_info(self, symbol: str) -> dict:
        """Get trading statistics for a symbol"""
        return await self._get(f"/quote-equity?symbol={symbol.upper()}&section=trade_info")
    
    async def get_corporate_info(self, symbol: str) -> dict:
        """Get corporate information (earnings, dividends, etc.)"""
        return await self._get(f"/corporates-corporateActions?index=equities&symbol={symbol.upper()}")
    
    async def get_financial_results(self, symbol: str) -> dict:
        """Get financial results"""
        return await self._get(f"/corporates-financial-results-data?index=equities&symbol={symbol.upper()}&period=Quarterly")
    
    async def get_board_meetings(self, symbol: str) -> dict:
        """Get board meeting information"""
        return await self._get(f"/corporates-board-meetings?index=equities&symbol={symbol.upper()}")
    
    async def get_shareholding(self, symbol: str) -> dict:
        """Get shareholding pattern"""
        return await self._get(f"/corporates-shareholdingPatterns?index=equities&symbol={symbol.upper()}")
    
    async def get_announcements(self, symbol: str) -> dict:
        """Get company announcements"""
        return await self._get(f"/corporates-announcements?index=equities&symbol={symbol.upper()}")
    
    # ===================== OPTIONS DATA =====================
    
    async def get_option_chain(self, symbol: str) -> dict:
        """Get options chain for equity"""
        return await self._get(f"/option-chain-equities?symbol={symbol.upper()}")
    
    async def get_index_option_chain(self, index: str = "NIFTY") -> dict:
        """Get options chain for index"""
        return await self._get(f"/option-chain-indices?symbol={index.upper()}")
    
    # ===================== MARKET DATA =====================
    
    async def get_market_status(self) -> dict:
        """Get market status"""
        return await self._get("/marketStatus")
    
    async def get_indices(self) -> dict:
        """Get all indices"""
        return await self._get("/allIndices")
    
    async def get_nifty50(self) -> dict:
        """Get Nifty 50 stocks"""
        return await self._get("/equity-stockIndices?index=NIFTY%2050")
    
    async def get_gainers_losers(self, index: str = "NIFTY 50") -> dict:
        """Get top gainers and losers"""
        return await self._get(f"/live-analysis-variations?index={index.replace(' ', '%20')}")
    
    async def get_most_active(self) -> dict:
        """Get most active stocks"""
        return await self._get("/live-analysis-most-active-securities?index=volume")
    
    # ===================== EARNINGS COMBINED =====================
    
    async def get_earnings(self, symbol: str) -> dict:
        """
        Get comprehensive earnings data for a stock.
        Combines financial results + board meetings + corporate actions.
        """
        try:
            # Fetch all data concurrently
            results = await asyncio.gather(
                self.get_financial_results(symbol),
                self.get_board_meetings(symbol),
                self.get_corporate_info(symbol),
                self.get_shareholding(symbol),
                return_exceptions=True
            )
            
            financial_results, board_meetings, corp_actions, shareholding = results
            
            # Parse financial results
            parsed_financials = []
            if isinstance(financial_results, list):
                for r in financial_results[:8]:
                    parsed_financials.append({
                        'period_end': r.get('toDate'),
                        'income': float(r.get('income', 0) or 0),
                        'profit_before_tax': float(r.get('proLossBefTax', 0) or 0),
                        'profit_after_tax': float(r.get('proLossAftTax', 0) or 0),
                        'eps_diluted': float(r.get('dilEPS', 0) or 0),
                        'audited': r.get('audited') == 'Audited',
                        'consolidated': r.get('consolidated') == 'Consolidated',
                        'broadcast_date': r.get('broadcastDttm')
                    })
            
            # Parse board meetings
            parsed_meetings = []
            if isinstance(board_meetings, list):
                for m in board_meetings:
                    purpose = m.get('purpose', '').lower()
                    parsed_meetings.append({
                        'date': m.get('meetingDate'),
                        'purpose': m.get('purpose'),
                        'is_earnings': 'financial' in purpose or 'result' in purpose
                    })
            
            # Parse dividends from corporate actions
            dividends = []
            if isinstance(corp_actions, list):
                for a in corp_actions:
                    if 'dividend' in a.get('subject', '').lower():
                        dividends.append({
                            'ex_date': a.get('exDate'),
                            'purpose': a.get('subject')
                        })
            
            # Parse shareholding
            latest_holding = None
            if isinstance(shareholding, dict) and shareholding.get('data'):
                data = shareholding['data']
                if data:
                    latest_holding = {
                        'date': data[0].get('date') if data else None,
                        'pattern': data
                    }
            
            return {
                'symbol': symbol.upper(),
                'financial_results': parsed_financials,
                'upcoming_board_meetings': [m for m in parsed_meetings if m.get('is_earnings')],
                'dividends': dividends,
                'latest_shareholding': latest_holding,
                'announcements_count': 0
            }
        except Exception as e:
            logger.error(f"[NSE Direct] Error getting earnings for {symbol}: {e}")
            return {'error': str(e)}


# Singleton instance
nse_direct = NSEDirectClient()


# ===================== CONVENIENCE FUNCTIONS =====================

async def get_nse_earnings(symbol: str) -> dict:
    """Get earnings data for Indian stock"""
    return await nse_direct.get_earnings(symbol)

async def get_nse_equity(symbol: str) -> dict:
    """Get equity details"""
    return await nse_direct.get_equity_details(symbol)

async def get_nse_trade_info(symbol: str) -> dict:
    """Get trade info"""
    return await nse_direct.get_trade_info(symbol)

async def get_nse_options(symbol: str) -> dict:
    """Get options chain"""
    return await nse_direct.get_option_chain(symbol)

async def is_nse_available() -> bool:
    """Check if NSE API is accessible"""
    try:
        status = await nse_direct.get_market_status()
        return status is not None
    except:
        return False
