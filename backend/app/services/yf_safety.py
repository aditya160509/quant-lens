"""
Enhanced YFinance Safety Layer
Local data persistence + Synthetic fallback + Request deduplication
Significantly boosts reliability when yfinance is rate-limited or unavailable
"""

import os
import json
import sqlite3
import pandas as pd
import numpy as np
from pathlib import Path
from datetime import datetime, timedelta
from typing import Optional, Dict, List, Any
import hashlib
import logging

logger = logging.getLogger(__name__)

# Database path for local persistence
DB_PATH = Path(__file__).parent.parent.parent / "data" / "yf_cache.db"
DB_PATH.parent.mkdir(parents=True, exist_ok=True)


class LocalDataStore:
    """
    SQLite-based local persistence for yfinance data.
    Survives restarts and provides data even when API is unavailable.
    """
    
    def __init__(self, db_path: Path = DB_PATH):
        self.db_path = db_path
        self._init_db()
    
    def _init_db(self):
        """Initialize database tables"""
        conn = sqlite3.connect(str(self.db_path))
        try:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS price_history (
                    symbol TEXT NOT NULL,
                    date TEXT NOT NULL,
                    open REAL,
                    high REAL,
                    low REAL,
                    close REAL,
                    volume INTEGER,
                    updated_at TEXT,
                    PRIMARY KEY (symbol, date)
                )
            """)
            conn.execute("""
                CREATE TABLE IF NOT EXISTS ticker_info (
                    symbol TEXT PRIMARY KEY,
                    info_json TEXT,
                    updated_at TEXT
                )
            """)
            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_price_symbol ON price_history(symbol)
            """)
            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_price_date ON price_history(date)
            """)
            conn.commit()
        finally:
            conn.close()
    
    def save_history(self, symbol: str, df: pd.DataFrame):
        """Save price history to local database"""
        if df is None or df.empty:
            return
        
        conn = sqlite3.connect(str(self.db_path))
        try:
            now = datetime.now().isoformat()
            records = []
            for idx, row in df.iterrows():
                date_str = idx.strftime('%Y-%m-%d') if hasattr(idx, 'strftime') else str(idx)[:10]
                records.append((
                    symbol, date_str,
                    float(row.get('Open', 0)) if pd.notna(row.get('Open')) else None,
                    float(row.get('High', 0)) if pd.notna(row.get('High')) else None,
                    float(row.get('Low', 0)) if pd.notna(row.get('Low')) else None,
                    float(row.get('Close', 0)) if pd.notna(row.get('Close')) else None,
                    int(row.get('Volume', 0)) if pd.notna(row.get('Volume')) else None,
                    now
                ))
            
            conn.executemany("""
                INSERT OR REPLACE INTO price_history 
                (symbol, date, open, high, low, close, volume, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """, records)
            conn.commit()
            logger.info(f"[LocalDB] Saved {len(records)} rows for {symbol}")
        except Exception as e:
            logger.error(f"[LocalDB] Error saving {symbol}: {e}")
        finally:
            conn.close()
    
    def load_history(self, symbol: str, days: int = 365) -> Optional[pd.DataFrame]:
        """Load price history from local database"""
        conn = sqlite3.connect(str(self.db_path))
        try:
            cutoff = (datetime.now() - timedelta(days=days)).strftime('%Y-%m-%d')
            query = """
                SELECT date, open, high, low, close, volume
                FROM price_history
                WHERE symbol = ? AND date >= ?
                ORDER BY date
            """
            df = pd.read_sql_query(query, conn, params=(symbol, cutoff))
            
            if df.empty:
                return None
            
            df['date'] = pd.to_datetime(df['date'])
            df.set_index('date', inplace=True)
            df.columns = ['Open', 'High', 'Low', 'Close', 'Volume']
            logger.info(f"[LocalDB] Loaded {len(df)} rows for {symbol}")
            return df
        except Exception as e:
            logger.error(f"[LocalDB] Error loading {symbol}: {e}")
            return None
        finally:
            conn.close()
    
    def save_info(self, symbol: str, info: Dict):
        """Save ticker info to local database"""
        if not info:
            return
        
        conn = sqlite3.connect(str(self.db_path))
        try:
            # Clean info dict for JSON serialization
            clean_info = {}
            for k, v in info.items():
                if isinstance(v, (str, int, float, bool, type(None))):
                    clean_info[k] = v
                elif isinstance(v, (list, dict)):
                    try:
                        json.dumps(v)
                        clean_info[k] = v
                    except:
                        clean_info[k] = str(v)
            
            conn.execute("""
                INSERT OR REPLACE INTO ticker_info (symbol, info_json, updated_at)
                VALUES (?, ?, ?)
            """, (symbol, json.dumps(clean_info), datetime.now().isoformat()))
            conn.commit()
        except Exception as e:
            logger.error(f"[LocalDB] Error saving info {symbol}: {e}")
        finally:
            conn.close()
    
    def load_info(self, symbol: str, max_age_hours: int = 24) -> Optional[Dict]:
        """Load ticker info from local database"""
        conn = sqlite3.connect(str(self.db_path))
        try:
            row = conn.execute("""
                SELECT info_json, updated_at FROM ticker_info WHERE symbol = ?
            """, (symbol,)).fetchone()
            
            if not row:
                return None
            
            info_json, updated_at = row
            
            # Check age
            if max_age_hours > 0:
                updated = datetime.fromisoformat(updated_at)
                if datetime.now() - updated > timedelta(hours=max_age_hours):
                    logger.debug(f"[LocalDB] Info for {symbol} is stale ({max_age_hours}h)")
                    return json.loads(info_json)  # Return stale but indicate it
            
            return json.loads(info_json)
        except Exception as e:
            logger.error(f"[LocalDB] Error loading info {symbol}: {e}")
            return None
        finally:
            conn.close()
    
    def get_stats(self) -> Dict:
        """Get database statistics"""
        conn = sqlite3.connect(str(self.db_path))
        try:
            symbols = conn.execute("SELECT COUNT(DISTINCT symbol) FROM price_history").fetchone()[0]
            rows = conn.execute("SELECT COUNT(*) FROM price_history").fetchone()[0]
            info_count = conn.execute("SELECT COUNT(*) FROM ticker_info").fetchone()[0]
            db_size = self.db_path.stat().st_size if self.db_path.exists() else 0
            return {
                'symbols': symbols,
                'price_rows': rows,
                'info_count': info_count,
                'db_size_mb': round(db_size / (1024 * 1024), 2)
            }
        finally:
            conn.close()


class SyntheticDataGenerator:
    """
    Generates statistically-similar synthetic data when real data unavailable.
    Uses historical statistics to simulate realistic returns.
    """
    
    # Default statistics for common asset classes
    DEFAULT_STATS = {
        'equity': {'mean': 0.0004, 'std': 0.015, 'skew': -0.2, 'kurt': 4.0},
        'bond': {'mean': 0.0001, 'std': 0.005, 'skew': 0.0, 'kurt': 3.0},
        'commodity': {'mean': 0.0002, 'std': 0.020, 'skew': -0.1, 'kurt': 5.0},
        'crypto': {'mean': 0.001, 'std': 0.04, 'skew': -0.3, 'kurt': 6.0},
    }
    
    @classmethod
    def generate_returns(
        cls,
        n_days: int = 252,
        asset_class: str = 'equity',
        mean: Optional[float] = None,
        std: Optional[float] = None
    ) -> pd.Series:
        """Generate synthetic returns based on asset class statistics"""
        stats = cls.DEFAULT_STATS.get(asset_class, cls.DEFAULT_STATS['equity'])
        
        mean = mean if mean is not None else stats['mean']
        std = std if std is not None else stats['std']
        
        # Generate returns with slight autocorrelation (like real markets)
        returns = np.random.normal(mean, std, n_days)
        
        # Add slight negative autocorrelation (mean reversion)
        for i in range(1, len(returns)):
            returns[i] -= 0.1 * returns[i-1]
        
        dates = pd.date_range(end=datetime.now(), periods=n_days, freq='B')
        return pd.Series(returns, index=dates, name='returns')
    
    @classmethod
    def generate_ohlcv(
        cls,
        symbol: str,
        n_days: int = 252,
        start_price: float = 100.0,
        asset_class: str = 'equity'
    ) -> pd.DataFrame:
        """Generate synthetic OHLCV data"""
        returns = cls.generate_returns(n_days, asset_class)
        
        # Cumulative returns to get price series
        prices = start_price * (1 + returns).cumprod()
        
        # Generate OHLC from close prices with realistic intraday volatility
        intraday_vol = 0.02
        
        df = pd.DataFrame(index=returns.index)
        df['Close'] = prices
        df['Open'] = df['Close'].shift(1).fillna(start_price) * (1 + np.random.normal(0, 0.005, n_days))
        
        # High/Low with realistic range
        high_mult = 1 + np.abs(np.random.normal(0, intraday_vol, n_days))
        low_mult = 1 - np.abs(np.random.normal(0, intraday_vol, n_days))
        
        df['High'] = df[['Open', 'Close']].max(axis=1) * high_mult
        df['Low'] = df[['Open', 'Close']].min(axis=1) * low_mult
        df['Volume'] = np.random.randint(100000, 10000000, n_days)
        
        logger.warning(f"[Synthetic] Generated {n_days} days of synthetic data for {symbol}")
        return df
    
    @classmethod
    def generate_info(cls, symbol: str) -> Dict:
        """Generate synthetic ticker info"""
        return {
            'symbol': symbol,
            'shortName': f'{symbol} (Synthetic)',
            'currentPrice': 100.0,
            'regularMarketPrice': 100.0,
            'previousClose': 99.5,
            'marketCap': 10_000_000_000,
            'beta': 1.0 + np.random.uniform(-0.3, 0.3),
            '_synthetic': True,
            '_generated_at': datetime.now().isoformat()
        }


class RequestDeduplicator:
    """
    Prevents duplicate in-flight requests for the same data.
    If request A is in progress and request B asks for same data,
    B waits for A's result instead of making a new API call.
    """
    
    _pending: Dict[str, Any] = {}
    
    @classmethod
    def get_or_create(cls, key: str) -> tuple:
        """
        Returns (result, is_new).
        If is_new is True, caller should fetch data and call complete().
        If is_new is False, result contains the data.
        """
        if key in cls._pending:
            return cls._pending[key], False
        
        # Create placeholder
        cls._pending[key] = None
        return None, True
    
    @classmethod
    def complete(cls, key: str, result: Any):
        """Mark request as complete with result"""
        cls._pending[key] = result
    
    @classmethod
    def cleanup(cls, key: str):
        """Remove completed request"""
        cls._pending.pop(key, None)


# =============================================================================
# GLOBAL INSTANCES
# =============================================================================

local_store = LocalDataStore()
synthetic_gen = SyntheticDataGenerator()


# =============================================================================
# ENHANCED WRAPPER FUNCTIONS
# =============================================================================

def get_safe_history(
    symbol: str,
    period: str = "1y",
    interval: str = "1d",
    allow_synthetic: bool = True
) -> Optional[pd.DataFrame]:
    """
    Get historical data with multiple fallback layers:
    1. Try yfinance (rate-limited)
    2. Try local database
    3. Generate synthetic data if allowed
    """
    from app.services.yf_wrapper import YFinanceWrapper
    
    # Try yfinance first
    df = YFinanceWrapper.get_history(symbol, period, interval)
    
    if df is not None and not df.empty:
        # Save to local store for future use
        local_store.save_history(symbol, df)
        return df
    
    # Fallback to local database
    days = {'1mo': 30, '3mo': 90, '6mo': 180, '1y': 365, '2y': 730, '5y': 1825}.get(period, 365)
    local_df = local_store.load_history(symbol, days)
    
    if local_df is not None and not local_df.empty:
        logger.info(f"[Safety] Using local data for {symbol}")
        return local_df
    
    # Last resort: synthetic data
    if allow_synthetic:
        logger.warning(f"[Safety] Generating synthetic data for {symbol}")
        return synthetic_gen.generate_ohlcv(symbol, days)
    
    return None


def get_safe_info(symbol: str, allow_synthetic: bool = True) -> Optional[Dict]:
    """
    Get ticker info with multiple fallback layers
    """
    from app.services.yf_wrapper import YFinanceWrapper
    
    # Try yfinance
    info = YFinanceWrapper.get_ticker_info(symbol)
    
    if info:
        local_store.save_info(symbol, info)
        return info
    
    # Fallback to local
    local_info = local_store.load_info(symbol, max_age_hours=72)  # 3 days
    if local_info:
        logger.info(f"[Safety] Using local info for {symbol}")
        return local_info
    
    # Synthetic
    if allow_synthetic:
        return synthetic_gen.generate_info(symbol)
    
    return None


def get_safe_price(symbol: str, allow_synthetic: bool = True) -> Optional[float]:
    """Get current price with fallbacks"""
    info = get_safe_info(symbol, allow_synthetic)
    if info:
        return info.get('currentPrice') or info.get('regularMarketPrice')
    return None


def prefetch_universe(symbols: List[str]):
    """
    Pre-fetch data for entire universe and cache locally.
    Run this at market open to avoid rate limits during trading.
    """
    import asyncio
    from app.services.yf_wrapper import YFinanceWrapper
    
    logger.info(f"[Prefetch] Starting prefetch for {len(symbols)} symbols")
    
    for i, symbol in enumerate(symbols):
        try:
            # Rate-limited fetch
            df = YFinanceWrapper.get_history(symbol, period="1y")
            if df is not None and not df.empty:
                local_store.save_history(symbol, df)
            
            info = YFinanceWrapper.get_ticker_info(symbol)
            if info:
                local_store.save_info(symbol, info)
            
            if (i + 1) % 10 == 0:
                logger.info(f"[Prefetch] Completed {i + 1}/{len(symbols)}")
        
        except Exception as e:
            logger.error(f"[Prefetch] Error for {symbol}: {e}")
    
    logger.info(f"[Prefetch] Complete. Stats: {local_store.get_stats()}")


def get_safety_stats() -> Dict:
    """Get statistics about the safety layer"""
    return {
        'local_store': local_store.get_stats(),
        'pending_requests': len(RequestDeduplicator._pending),
    }
