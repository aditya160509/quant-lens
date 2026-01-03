"""
API Call Tracker - Monitors yfinance and external API usage per module/endpoint.
Helps identify which features are causing heavy API load.
"""
import logging
import time
from collections import defaultdict
from datetime import datetime, timedelta
from functools import wraps
from threading import Lock
from typing import Dict, List, Optional

logger = logging.getLogger(__name__)

# Thread-safe tracking storage
_tracker_lock = Lock()
_api_calls: Dict[str, List[dict]] = defaultdict(list)
_yf_calls: Dict[str, int] = defaultdict(int)
_yf_ticker_calls: Dict[str, int] = defaultdict(int)

# Track calls in the last N minutes
TRACKING_WINDOW_MINUTES = 60


def _cleanup_old_calls():
    """Remove calls older than the tracking window."""
    cutoff = datetime.now() - timedelta(minutes=TRACKING_WINDOW_MINUTES)
    with _tracker_lock:
        for module in list(_api_calls.keys()):
            _api_calls[module] = [
                call for call in _api_calls[module]
                if call['timestamp'] > cutoff
            ]
            if not _api_calls[module]:
                del _api_calls[module]


def track_api_call(module: str, endpoint: str, ticker_count: int = 0, source: str = "yfinance"):
    """
    Record an API call for tracking.
    
    Args:
        module: The module/service name (e.g., 'monitor', 'screener', 'portfolio')
        endpoint: The specific endpoint (e.g., '/monitor/leaders', '/screener/scan')
        ticker_count: Number of tickers being fetched
        source: Data source ('yfinance', 'nse_india', 'fred', etc.)
    """
    with _tracker_lock:
        call_record = {
            'timestamp': datetime.now(),
            'endpoint': endpoint,
            'ticker_count': ticker_count,
            'source': source
        }
        _api_calls[module].append(call_record)
        
        if source == 'yfinance':
            _yf_calls[module] += 1


def track_yf_ticker(ticker: str, module: str = "unknown"):
    """Track individual yfinance ticker fetch."""
    with _tracker_lock:
        _yf_ticker_calls[ticker] += 1
        _yf_calls[module] += 1


def get_tracker_stats() -> dict:
    """
    Get current API usage statistics.
    
    Returns comprehensive stats about which modules are making the most calls.
    """
    _cleanup_old_calls()
    
    with _tracker_lock:
        # Calculate per-module stats
        module_stats = {}
        for module, calls in _api_calls.items():
            if calls:
                total_tickers = sum(c.get('ticker_count', 0) for c in calls)
                module_stats[module] = {
                    'call_count': len(calls),
                    'total_tickers_fetched': total_tickers,
                    'yf_calls': _yf_calls.get(module, 0),
                    'endpoints_hit': list(set(c['endpoint'] for c in calls)),
                    'last_call': max(c['timestamp'] for c in calls).isoformat()
                }
        
        # Sort by call count descending
        sorted_modules = sorted(
            module_stats.items(),
            key=lambda x: x[1]['call_count'],
            reverse=True
        )
        
        # Top ticker culprits
        top_tickers = sorted(
            _yf_ticker_calls.items(),
            key=lambda x: x[1],
            reverse=True
        )[:20]
        
        return {
            'tracking_window_minutes': TRACKING_WINDOW_MINUTES,
            'total_calls': sum(len(calls) for calls in _api_calls.values()),
            'total_yf_calls': sum(_yf_calls.values()),
            'modules_ranked': [
                {'module': m, **stats} for m, stats in sorted_modules
            ],
            'top_tickers': [
                {'ticker': t, 'calls': c} for t, c in top_tickers
            ],
            'timestamp': datetime.now().isoformat()
        }


def reset_tracker():
    """Reset all tracking data."""
    with _tracker_lock:
        _api_calls.clear()
        _yf_calls.clear()
        _yf_ticker_calls.clear()
    logger.info("API tracker reset")


def log_heavy_usage_warning():
    """Log a warning if any module is making excessive calls."""
    stats = get_tracker_stats()
    
    for module_data in stats['modules_ranked']:
        if module_data['call_count'] > 50:
            logger.warning(
                f"[API-TRACKER] Heavy usage: {module_data['module']} made "
                f"{module_data['call_count']} calls in last {TRACKING_WINDOW_MINUTES} min"
            )


# Decorator for tracking endpoint calls
def track_endpoint(module: str, endpoint: str, ticker_count_param: str = None):
    """
    Decorator to automatically track API endpoint calls.
    
    Usage:
        @track_endpoint("monitor", "/monitor/leaders", ticker_count_param="k")
        async def get_leaders(k: int = 10):
            ...
    """
    def decorator(func):
        @wraps(func)
        async def async_wrapper(*args, **kwargs):
            ticker_count = kwargs.get(ticker_count_param, 0) if ticker_count_param else 0
            track_api_call(module, endpoint, ticker_count)
            return await func(*args, **kwargs)
        
        @wraps(func)
        def sync_wrapper(*args, **kwargs):
            ticker_count = kwargs.get(ticker_count_param, 0) if ticker_count_param else 0
            track_api_call(module, endpoint, ticker_count)
            return func(*args, **kwargs)
        
        # Return appropriate wrapper based on function type
        import asyncio
        if asyncio.iscoroutinefunction(func):
            return async_wrapper
        return sync_wrapper
    
    return decorator
