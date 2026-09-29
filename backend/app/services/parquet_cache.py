import pandas as pd
import polars as pl
import os
import logging
from pathlib import Path
from datetime import datetime, timedelta
import threading
from typing import Optional

logger = logging.getLogger(__name__)

class ParquetCache:
    """
    High-performance Parquet-based persistent cache.
    Ensures all backend data inputs/outputs adhere to the Parquet standard.
    """
    
    def __init__(self, cache_dir: str = None):
        if cache_dir is None:
            self.cache_dir = Path(__file__).parent.parent.parent / "data" / "parquet_cache"
        else:
            self.cache_dir = Path(cache_dir)
            
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        self._lock = threading.Lock()
        
    def _get_path(self, key: str) -> Path:
        # Sanitize key for filesystem
        safe_key = "".join([c if c.isalnum() else "_" for c in key])
        return self.cache_dir / f"{safe_key}.parquet"
        
    def set(self, key: str, df: pd.DataFrame):
        """Save a pandas DataFrame to Parquet."""
        if df is None or df.empty:
            return
            
        path = self._get_path(key)
        try:
            with self._lock:
                # Convert index to column if it's named or a DatetimeIndex
                temp_df = df.copy()
                if temp_df.index.name is None:
                    temp_df.index.name = "index"
                
                # Polars is faster for writing parquets
                pl_df = pl.from_pandas(temp_df.reset_index())
                pl_df.write_parquet(path)
                logger.debug(f"[ParquetCache] Saved {key} to {path}")
        except Exception as e:
            logger.error(f"[ParquetCache] Failed to save {key}: {e}")
            
    def get(self, key: str, max_age_hours: int = 24) -> Optional[pd.DataFrame]:
        """Load a DataFrame from Parquet if not expired."""
        path = self._get_path(key)
        
        if not path.exists():
            return None
            
        try:
            # Check age
            mtime = datetime.fromtimestamp(path.stat().st_mtime)
            if datetime.now() - mtime > timedelta(hours=max_age_hours):
                logger.debug(f"[ParquetCache] {key} expired ({mtime})")
                return None
                
            with self._lock:
                # Read with Polars for speed
                pl_df = pl.read_parquet(path)
                df = pl_df.to_pandas()
                
                # Restore index
                if "Date" in df.columns:
                    df["Date"] = pd.to_datetime(df["Date"])
                    df.set_index("Date", inplace=True)
                elif "index" in df.columns:
                    df.set_index("index", inplace=True)
                    
                return df
        except Exception as e:
            logger.error(f"[ParquetCache] Failed to load {key}: {e}")
            return None

    def clear(self):
        """Clear all parquet files in cache."""
        with self._lock:
            for f in self.cache_dir.glob("*.parquet"):
                try:
                    f.unlink()
                except Exception:
                    pass

# Singleton instance
pq_cache = ParquetCache()
