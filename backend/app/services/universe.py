"""
Universe Service
Provides symbol validation and group classification for all modules.
"""

import json
import os
from typing import Dict, List, Set, Tuple, Optional
from pathlib import Path
import logging

logger = logging.getLogger(__name__)

# ===== Load Universe =====
_UNIVERSE_PATH = Path(__file__).parent.parent / "data" / "universes.json"

def _load_universe() -> Dict[str, List[str]]:
    """Load universe from JSON file."""
    try:
        with open(_UNIVERSE_PATH, 'r') as f:
            return json.load(f)
    except Exception as e:
        logger.error(f"Failed to load universe: {e}")
        return {}

UNIVERSE = _load_universe()

# ===== Build Lookup Structures =====
ALLOWED_SYMBOLS: Set[str] = set()
GROUP_MAP: Dict[str, str] = {}  # symbol -> group

for group, symbols in UNIVERSE.items():
    for symbol in symbols:
        ALLOWED_SYMBOLS.add(symbol)
        GROUP_MAP[symbol] = group

# ===== Group Sets =====
SECURITY_GROUPS = {"india_nse", "india_bse", "us_equities"}
MARKET_GROUPS = {"indices", "etfs"}
MARKET_OPTIONAL_GROUPS = {"fx", "crypto"}
ALL_GROUPS = set(UNIVERSE.keys())

# ===== Asset Type Classification =====
# Maps groups to asset types for screener feature gating
ASSET_TYPE_MAP = {
    "india_nse": "EQUITY",
    "india_bse": "EQUITY",
    "us_equities": "EQUITY",
    "etfs": "ETF",
    "indices": "INDEX",
    "crypto": "CRYPTO",
    "fx": "FX",
}

def get_asset_type(symbol: str) -> str:
    """Get asset type for a symbol (EQUITY, CRYPTO, FX, INDEX, ETF)."""
    group = GROUP_MAP.get(symbol)
    if group:
        return ASSET_TYPE_MAP.get(group, "EQUITY")
    # Fallback detection by pattern
    if symbol.startswith("^"):
        return "INDEX"
    if symbol.endswith("-USD"):
        return "CRYPTO"
    if symbol.endswith("=X"):
        return "FX"
    if symbol.endswith(".NS") or symbol.endswith(".BO"):
        return "EQUITY"
    return "EQUITY"

def get_available_asset_types() -> List[str]:
    """Get list of available asset types in the universe."""
    return list(set(ASSET_TYPE_MAP.values()))

def get_symbols_by_asset_type(asset_type: str) -> List[str]:
    """Get all symbols matching an asset type (EQUITY, CRYPTO, FX, INDEX, ETF)."""
    asset_type = asset_type.upper()
    result = []
    for group, atype in ASSET_TYPE_MAP.items():
        if atype == asset_type:
            result.extend(UNIVERSE.get(group, []))
    return result

SECURITY_SET: Set[str] = set()
MARKET_SET: Set[str] = set()
MARKET_OPTIONAL_SET: Set[str] = set()

for group in SECURITY_GROUPS:
    SECURITY_SET.update(UNIVERSE.get(group, []))

for group in MARKET_GROUPS:
    MARKET_SET.update(UNIVERSE.get(group, []))

for group in MARKET_OPTIONAL_GROUPS:
    MARKET_OPTIONAL_SET.update(UNIVERSE.get(group, []))

# ===== Limits =====
LIMITS = {
    "intraday_max": 10,
    "correlation_max": 50,
    "pca_max": 40,
    "beta_max": 100,
    "batch_max": 200,
    "min_history_days": 365,
}

# ===== Validation Functions =====

def get_group(symbol: str) -> Optional[str]:
    """Get the group for a symbol."""
    return GROUP_MAP.get(symbol)


def is_valid_symbol(symbol: str) -> bool:
    """Check if symbol is in the allowed universe."""
    return symbol in ALLOWED_SYMBOLS


def is_security_allowed(symbol: str) -> bool:
    """Check if symbol is allowed for Security pages (equities only)."""
    return symbol in SECURITY_SET


def is_market_allowed(symbol: str, allow_fx_crypto: bool = False) -> bool:
    """Check if symbol is allowed for Markets page."""
    if symbol in MARKET_SET:
        return True
    if allow_fx_crypto and symbol in MARKET_OPTIONAL_SET:
        return True
    return False


def validate_symbols(
    tickers: List[str],
    mode: str = "any",
    allow_fx_crypto: bool = False
) -> Tuple[List[str], List[str]]:
    """
    Validate a list of symbols against the universe.
    
    Args:
        tickers: List of ticker symbols
        mode: "security" | "market" | "any"
        allow_fx_crypto: Whether to allow FX/Crypto in market mode
        
    Returns:
        Tuple of (valid_tickers, invalid_tickers)
    """
    valid = []
    invalid = []
    
    for ticker in tickers:
        ticker = ticker.strip().upper() if ticker else ""
        
        if not ticker:
            continue
            
        if ticker not in ALLOWED_SYMBOLS:
            invalid.append(ticker)
            continue
        
        # Mode-specific validation
        if mode == "security":
            if is_security_allowed(ticker):
                valid.append(ticker)
            else:
                invalid.append(ticker)
        elif mode == "market":
            if is_market_allowed(ticker, allow_fx_crypto):
                valid.append(ticker)
            else:
                invalid.append(ticker)
        else:  # mode == "any"
            valid.append(ticker)
    
    return valid, invalid


def check_limits(
    tickers: List[str],
    interval: str = "1d",
    module: str = "default"
) -> Tuple[bool, Optional[str]]:
    """
    Check if request exceeds limits.
    
    Returns:
        Tuple of (is_ok, error_message)
    """
    count = len(tickers)
    
    # Batch limit
    if count > LIMITS["batch_max"]:
        return False, f"Too many symbols: {count} exceeds maximum of {LIMITS['batch_max']}"
    
    # Intraday limit
    if interval in ["1m", "5m", "15m", "1h"]:
        if count > LIMITS["intraday_max"]:
            return False, f"Too many symbols for intraday: {count} exceeds maximum of {LIMITS['intraday_max']}"
    
    # Module-specific limits
    if module == "correlation" and count > LIMITS["correlation_max"]:
        return False, f"Too many symbols for correlation: {count} exceeds maximum of {LIMITS['correlation_max']}"
    
    if module == "pca" and count > LIMITS["pca_max"]:
        return False, f"Too many symbols for PCA: {count} exceeds maximum of {LIMITS['pca_max']}"
    
    if module == "beta" and count > LIMITS["beta_max"]:
        return False, f"Too many symbols for rolling beta: {count} exceeds maximum of {LIMITS['beta_max']}"
    
    return True, None


def get_universe_list(group: Optional[str] = None) -> List[str]:
    """
    Get list of symbols from universe.
    
    Args:
        group: Optional group name to filter by
        
    Returns:
        List of symbol strings
    """
    if group:
        return UNIVERSE.get(group, [])
    return list(ALLOWED_SYMBOLS)


def get_security_universe() -> List[str]:
    """Get all security symbols (equities only)."""
    return list(SECURITY_SET)


def get_market_universe(include_fx_crypto: bool = False) -> List[str]:
    """Get all market symbols (indices + ETFs, optionally FX/Crypto)."""
    result = list(MARKET_SET)
    if include_fx_crypto:
        result.extend(MARKET_OPTIONAL_SET)
    return result


# ===== Symbol Normalization =====

def normalize_symbol(symbol: str) -> str:
    """
    Normalize a symbol to canonical form.
    
    - Uppercase
    - Trim whitespace
    - Handle BRK.B -> BRK-B for US equities
    """
    if not symbol:
        return ""
    
    symbol = symbol.strip().upper()
    
    # Don't modify Indian symbols or special symbols
    if symbol.endswith(".NS") or symbol.endswith(".BO"):
        return symbol
    if symbol.startswith("^"):
        return symbol
    if symbol.endswith("=X") or "-USD" in symbol:
        return symbol
    
    # For US equities, normalize class shares (BRK.B -> BRK-B)
    if "." in symbol and not symbol.endswith(".NS") and not symbol.endswith(".BO"):
        # Check if it's a class share pattern
        parts = symbol.split(".")
        if len(parts) == 2 and len(parts[1]) == 1:
            normalized = f"{parts[0]}-{parts[1]}"
            if normalized in ALLOWED_SYMBOLS:
                return normalized
    
    return symbol


def map_tradingview_symbol(tv_symbol: str, exchange: str = "") -> Optional[str]:
    """
    Map a TradingView symbol to universe symbol.
    
    Args:
        tv_symbol: Symbol from TradingView (e.g., "TCS", "AAPL")
        exchange: Exchange from TradingView (e.g., "NSE", "NASDAQ")
        
    Returns:
        Universe symbol or None if not found
    """
    if not tv_symbol:
        return None
    
    tv_symbol = tv_symbol.strip().upper()
    exchange = exchange.strip().upper() if exchange else ""
    
    # Direct match first
    if tv_symbol in ALLOWED_SYMBOLS:
        return tv_symbol
    
    # Exchange-based mapping
    if exchange == "NSE":
        candidate = f"{tv_symbol}.NS"
        if candidate in ALLOWED_SYMBOLS:
            return candidate
    
    if exchange == "BSE":
        candidate = f"{tv_symbol}.BO"
        if candidate in ALLOWED_SYMBOLS:
            return candidate
    
    # US exchanges - direct
    if exchange in ["NASDAQ", "NYSE", "AMEX", "ARCA"]:
        if tv_symbol in ALLOWED_SYMBOLS:
            return tv_symbol
        # Try BRK.B -> BRK-B normalization
        normalized = normalize_symbol(tv_symbol)
        if normalized in ALLOWED_SYMBOLS:
            return normalized
    
    # Index mapping
    if exchange in ["INDEX", "CBOE", "SP"]:
        candidate = f"^{tv_symbol}"
        if candidate in ALLOWED_SYMBOLS:
            return candidate
        # Special cases
        index_map = {
            "SPX": "^GSPC",
            "NIFTY": "^NSEI",
            "SENSEX": "^BSESN",
            "VIX": "^VIX",
        }
        if tv_symbol in index_map:
            return index_map[tv_symbol]
    
    # FX mapping
    if exchange in ["FX", "OANDA", "FOREX"]:
        candidate = f"{tv_symbol}=X"
        if candidate in ALLOWED_SYMBOLS:
            return candidate
    
    # Crypto mapping
    if exchange in ["BITSTAMP", "COINBASE", "BINANCE", "CRYPTO"]:
        candidate = f"{tv_symbol}-USD"
        if candidate in ALLOWED_SYMBOLS:
            return candidate
    
    # Fallback attempts
    fallbacks = [
        f"{tv_symbol}.NS",
        f"{tv_symbol}.BO",
        f"^{tv_symbol}",
        f"{tv_symbol}=X",
        f"{tv_symbol}-USD",
        normalize_symbol(tv_symbol),
    ]
    
    for candidate in fallbacks:
        if candidate in ALLOWED_SYMBOLS:
            return candidate
    
    return None


# ===== Info Functions =====

def get_symbol_info(symbol: str) -> Optional[Dict]:
    """
    Get info about a symbol.
    
    Returns:
        Dict with group, display_name, etc. or None if not found
    """
    if symbol not in ALLOWED_SYMBOLS:
        return None
    
    group = GROUP_MAP.get(symbol)
    
    # Determine exchange display
    if symbol.endswith(".NS"):
        exchange = "NSE"
        base = symbol[:-3]
    elif symbol.endswith(".BO"):
        exchange = "BSE"
        base = symbol[:-3]
    elif symbol.startswith("^"):
        exchange = "INDEX"
        base = symbol[1:]
    elif symbol.endswith("=X"):
        exchange = "FX"
        base = symbol[:-2]
    elif "-USD" in symbol:
        exchange = "CRYPTO"
        base = symbol.replace("-USD", "")
    else:
        exchange = "US"
        base = symbol
    
    return {
        "symbol": symbol,
        "base": base,
        "exchange": exchange,
        "group": group,
        "display": f"{base} • {exchange}",
    }


def stats() -> Dict:
    """Get universe statistics."""
    return {
        "total_symbols": len(ALLOWED_SYMBOLS),
        "groups": {group: len(symbols) for group, symbols in UNIVERSE.items()},
        "security_count": len(SECURITY_SET),
        "market_count": len(MARKET_SET),
        "limits": LIMITS,
    }
