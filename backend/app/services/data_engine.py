
import polars as pl
import pandas as pd
import numpy as np
import os
import json
import logging
import threading
from pathlib import Path
from typing import List, Dict, Optional, Union, Tuple
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)

class DataEngine:
    """
    God-Mode Data Engine
    Vectorized, Parallel, and Parquet-Native.
    
    The central intelligence for all high-performance computations.
    """
    
    def __init__(self, parquet_path: str = None):
        base_dir = Path(__file__).parent.parent.parent
        if parquet_path is None:
            self.parquet_path = str(base_dir / "data" / "market_universe.parquet")
        else:
            self.parquet_path = parquet_path
            
        self.data_dir = base_dir / "data"
        self.universes_path = Path(__file__).parent.parent / "data" / "universes.json"
        self._df: Optional[pl.DataFrame] = None
        self._factors_cache: Dict[str, pl.DataFrame] = {}
        self._universes: Dict[str, List[str]] = {}
        self._lock = threading.Lock()
        
    def _load_if_needed(self):
        """Lazy load the main price parquet file."""
        if self._df is None:
            with self._lock:
                if self._df is not None: return
                if not os.path.exists(self.parquet_path):
                    logger.error(f"Parquet file not found at {self.parquet_path}")
                    self._df = pl.DataFrame(schema={"Date": pl.Date, "Ticker": pl.Utf8, "Close": pl.Float64})
                    return
                logger.info(f"Loading market universe from {self.parquet_path}")
                self._df = pl.read_parquet(self.parquet_path)
                if self._df["Date"].dtype != pl.Date:
                    self._df = self._df.with_columns(pl.col("Date").cast(pl.Date))
                
                # Cache unique tickers for faster normalization
                self._parquet_tickers = set(self._df["Ticker"].unique().to_list())
            
            # Load universes (moved outside the main price data lock for clarity, but still lazy)
            if self.universes_path.exists():
                with open(self.universes_path, 'r') as f:
                    self._universes = json.load(f)

    def get_factors(self, set_id: str = "ff5_daily") -> pl.DataFrame:
        """Load factor data (FF5, Momentum, etc.) from Parquet."""
        cache_key = set_id
        if cache_key in self._factors_cache:
            return self._factors_cache[cache_key]

        path = self.data_dir / "factors_us" / f"{set_id}.parquet"
        if not path.exists():
            path = self.data_dir / "factors_india" / f"{set_id}.parquet"
            
        if not path.exists():
            logger.error(f"Factor file {set_id}.parquet not found")
            return pl.DataFrame()

        df = pl.read_parquet(path)
        # Standardize date column
        date_col = next((c for c in df.columns if 'date' in c.lower()), None)
        if date_col:
            df = df.rename({date_col: "Date"})
            try:
                # Handle YYYYMMDD or other formats
                df = df.with_columns(pl.col("Date").cast(pl.Utf8).str.to_date("%Y%m%d"))
            except:
                pass
        
        with self._lock:
            self._factors_cache[cache_key] = df
        return df

    def get_macro_dataset(self, name: str) -> pl.DataFrame:
        """Load a macro dataset (e.g., 'yield_curve', 'inflation') from Parquet."""
        path = self.data_dir / f"{name}.parquet"
        if not path.exists():
            path = self.data_dir / "macro" / f"{name}.parquet"
        
        if not path.exists():
            logger.error(f"Macro dataset '{name}.parquet' not found at {path}")
            return pl.DataFrame()
        return pl.read_parquet(path)

    def get_tickers_for_universe(self, universe_name: str) -> List[str]:
        """Get ticker list for a specific universe (e.g., 'nifty50', 'sp500')."""
        self._load_if_needed()
        return self._universes.get(universe_name.lower(), [])

    def get_price_matrix(self, 
                        tickers: Optional[List[str]] = None, 
                        universe: Optional[str] = None,
                        lookback_days: int = 252,
                        column: str = "Close") -> pd.DataFrame:
        """
        Matrix-form data (Date x Ticker) for specific tickers or universe.
        Extremely fast using Polars pivot.
        """
        self._load_if_needed()
        
        # Determine tickers
        if universe:
            source_tickers = self.get_tickers_for_universe(universe)
        elif tickers:
            source_tickers = tickers
        else:
            source_tickers = list(self._parquet_tickers)

        # Normalize tickers to match parquet format (e.g. .NS -> _NS, -USD -> _USD)
        target_tickers = []
        reverse_map = {}
        
        for t in source_tickers:
            if t in self._parquet_tickers:
                target_tickers.append(t)
                reverse_map[t] = t
            else:
                # Try translations
                alt = t.replace(".", "_").replace("-", "_").replace("^", "_IDX_")
                if alt in self._parquet_tickers:
                    target_tickers.append(alt)
                    reverse_map[alt] = t
                else:
                    # Keep original if no match found, just in case
                    target_tickers.append(t)
                    reverse_map[t] = t

        # Filter and pivot
        # FIX: Anchoring to the max date in the dataset instead of current wall-clock time
        data_max_date = self._df["Date"].max()
        start_date = data_max_date - timedelta(days=lookback_days + 30)
        
        subset = self._df.filter(
            (pl.col("Ticker").is_in(target_tickers)) & 
            (pl.col("Date") >= start_date)
        )
        
        if subset.is_empty():
            return pd.DataFrame()
            
        # Handle duplicates if any (e.g. backfill errors)
        subset = subset.group_by(["Date", "Ticker"]).last()
        
        # Pivot into Matrix
        matrix_pl = subset.pivot(
            values=column,
            index="Date",
            columns="Ticker"
        ).sort("Date")
        
        # Convert to Pandas and map columns back to original names if possible
        df_pd = matrix_pl.to_pandas().set_index("Date")
        df_pd.columns = [reverse_map.get(c, c) for c in df_pd.columns]
        return df_pd

    def get_returns_matrix(self, 
                          tickers: Optional[List[str]] = None, 
                          universe: Optional[str] = None,
                          lookback_days: int = 252,
                          method: str = "log") -> pd.DataFrame:
        """
        Matrix-form Returns (Date x Ticker).
        """
        prices = self.get_price_matrix(tickers, universe, lookback_days + 1)
        if prices.empty:
            return pd.DataFrame()
            
        if method == "log":
            return np.log(prices / prices.shift(1)).dropna()
        else:
            return prices.pct_change().dropna()

    def get_latest_indicators(self, tickers: Optional[List[str]] = None) -> pl.DataFrame:
        """
        GOD-MODE: Compute core technical indicators for every stock in the universe.
        Uses Polars vectorized expressions for lightspeed scanning.
        """
        self._load_if_needed()
        
        # Determine slice date (look back 300 days max for performance)
        slice_date = datetime.now().date() - timedelta(days=300)
        
        df = self._df.filter(pl.col("Date") >= slice_date)
        
        if tickers:
            normalized_tickers = []
            for t in tickers:
                if t in self._parquet_tickers:
                    normalized_tickers.append(t)
                else:
                    alt = t.replace(".", "_").replace("-", "_").replace("^", "_IDX_")
                    if alt in self._parquet_tickers:
                        normalized_tickers.append(alt)
                    else:
                        normalized_tickers.append(t)
            df = df.filter(pl.col("Ticker").is_in(normalized_tickers))
            
        # Group by Ticker and calculate
        # Only compute on sorted subset
        scan_results = df.sort("Date").group_by("Ticker").agg([
            pl.col("Close").last().alias("Price"),
            ((pl.col("Close").last() / pl.col("Close").shift(1).last()) - 1).alias("Change_1D"),
            ((pl.col("Close").last() / pl.col("Close").shift(5).last()) - 1).alias("Change_5D"),
            ((pl.col("Close").last() / pl.col("Close").shift(20).last()) - 1).alias("Change_20D"),
            pl.col("Volume").tail(20).mean().alias("Avg_Volume_20D"),
            (pl.col("Close") * pl.col("Volume")).tail(20).mean().alias("Avg_Dollar_Volume_20D"),
            # MA Distances
            (pl.col("Close").last() / pl.col("Close").tail(20).mean() - 1).alias("Dist_MA20"),
            (pl.col("Close").last() / pl.col("Close").tail(50).mean() - 1).alias("Dist_MA50"),
            (pl.col("Close").last() / pl.col("Close").tail(200).mean() - 1).alias("Dist_MA200"),
            # Volatility
            (pl.col("Close").pct_change().tail(20).std() * np.sqrt(252)).alias("Vol_20D")
        ])
        
        return scan_results

    def get_full_ohlcv(self, ticker: str, lookback_days: int = 252) -> pd.DataFrame:
        """Standard OHLCV for a single ticker with translation support."""
        self._load_if_needed()
        
        # Translate ticker to match parquet format
        target_ticker = ticker
        if ticker not in self._parquet_tickers:
            alt = ticker.replace(".", "_").replace("-", "_").replace("^", "_IDX_")
            if alt in self._parquet_tickers:
                target_ticker = alt
        
        data_max_date = self._df["Date"].max()
        start_date = data_max_date - timedelta(days=lookback_days)
        
        return self._df.filter(
            (pl.col("Ticker") == target_ticker) & 
            (pl.col("Date") >= start_date)
        ).sort("Date").to_pandas().set_index("Date")

# Global singleton
engine = DataEngine()
