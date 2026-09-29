import pandas as pd
import numpy as np
import logging
from pathlib import Path
from typing import Dict, List, Any, Optional
from ...historical_price_service import get_historical_prices
from ...fundamentals_service import get_fundamentals_compact
import polars as pl

logger = logging.getLogger(__name__)

class MLDataLoader:
    @staticmethod
    def get_ticker_full_state(ticker: str) -> Dict[str, Any]:
        """
        Loads both price history and fundamental context for a ticker.
        Prioritizes master_fundamentals.parquet for institutional fidelity.
        """
        try:
            # 1. Price History
            df = get_historical_prices(ticker)
            if df is None or df.empty:
                return {"error": f"No price data for {ticker}"}

            # 2. Fundamentals - Try Parquet first
            fund = {}
            # Resolving path relative to this file's location (app/services/ml/v2/data_loader.py)
            base_dir = Path(__file__).resolve().parent.parent.parent.parent.parent
            master_path = base_dir / "data" / "fundamentals" / "master_fundamentals.parquet"
            if master_path.exists():
                try:
                    master_df = pl.read_parquet(master_path)
                    target = master_df.filter(pl.col('ticker') == ticker.upper())
                    if not target.is_empty():
                        fund = target.to_dicts()[0]
                        fund['source'] = 'master_parquet'
                except Exception as e:
                    logger.warning(f"Error reading master parquet for {ticker}: {e}")

            # Fallback to yfinance if parquet is missing or empty for this ticker
            if not fund:
                fund = get_fundamentals_compact(ticker)
                fund['source'] = 'yfinance'
            
            # Prepare data dict for models
            return {
                "price_df": df,
                "fund": fund,
                "closes": df['Close'].values,
                "volumes": df['Volume'].values,
                "returns": df['Close'].pct_change().dropna().values
            }
        except Exception as e:
            logger.error(f"Error in MLDataLoader for {ticker}: {e}")
            return {"error": str(e)}

    @staticmethod
    def get_universe_state(universe: Optional[Any] = None) -> List[Dict]:
        """
        Loads metadata for the entire universe (for Galaxy Star Map)
        Uses the master fundamentals parquet for high-speed retrieval.
        """
        try:
            base_dir = Path(__file__).resolve().parent.parent.parent.parent.parent
            path = base_dir / "data" / "fundamentals" / "master_fundamentals.parquet"
            if not path.exists():
                logger.warning(f"master_fundamentals.parquet not found at {path}, returning empty universe")
                return []
                
            # Use Polars for insane speed
            df = pl.read_parquet(path)

            # --- FILTERING ---
            if universe:
                if isinstance(universe, str):
                    # Handle known universes (mocking for now if not in parquet)
                    if universe.lower() == 'sp500':
                        # Example: in a real world we might have a 'is_sp500' column or similar
                        pass 
                elif isinstance(universe, list):
                    tickers = [str(t).upper() for t in universe]
                    df = df.filter(pl.col('ticker').is_in(tickers))
            
            # Limit for galaxy performance if too large
            if len(df) > 1000:
                df = df.head(1000)

            # Select only necessary columns
            cols = {
                'ticker': 'ticker',
                'name': 'name',
                'sector': 'sector',
                'marketCap': 'market_cap',
                'trailingPE': 'pe',
                'priceToBook': 'pb',
                'returnOnEquity': 'roe',
                'grossMargins': 'gross_margin',
                'currentRatio': 'current_ratio',
                'debtToEquity': 'debt_to_equity'
            }
            
            available_cols = [c for c in cols.keys() if c in df.columns]
            df_subset = df.select(available_cols)
            
            rename_map = {k: v for k, v in cols.items() if k in available_cols}
            df_subset = df_subset.rename(rename_map)
            
            return df_subset.to_dicts()
        except Exception as e:
            logger.error(f"Error loading universe state: {e}")
            return []
