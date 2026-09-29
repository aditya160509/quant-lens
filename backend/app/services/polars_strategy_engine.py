import polars as pl
import numpy as np
from typing import List, Dict, Any, Optional
import logging
from datetime import datetime

logger = logging.getLogger(__name__)

class PolarsStrategyEngine:
    """
    ULTRA-HIGH PERFORMANCE STRATEGY ENGINE
    Uses Polars for vectorized operations and Monte Carlo simulations.
    Designed for 10,000+ path iterations in <1s.
    """
    
    @staticmethod
    def run_monte_carlo(returns: pl.Series, n_paths: int = 10000, horizon: int = 252) -> Dict[str, Any]:
        """
        Run vectorized Monte Carlo simulations.
        No loops, pure Polars matrix-style operations.
        """
        start_time = datetime.now()
        
        # Convert to numpy for fast random sampling
        returns_np = returns.to_numpy()
        
        # Sampling indices for all paths at once: (horizon, n_paths)
        indices = np.random.choice(len(returns_np), size=(horizon, n_paths))
        sampled_returns = returns_np[indices]
        
        # Calculate cumulative returns: (horizon, n_paths)
        # 1 + r for each step, then cumprod along axis 0
        path_matrix = np.cumprod(1 + sampled_returns, axis=0) * 100  # Start at 100
        
        # Descriptive stats for the paths (Final values)
        final_values = path_matrix[-1, :]
        
        # Stats
        results = {
            "mean": float(np.mean(final_values)),
            "median": float(np.median(final_values)),
            "std": float(np.std(final_values)),
            "p5": float(np.percentile(final_values, 5)),
            "p95": float(np.percentile(final_values, 95)),
            "paths": [path_matrix[:, i].tolist() for i in range(min(n_paths, 100))], # Sample of paths for UI
            "runtime_ms": (datetime.now() - start_time).microseconds / 1000
        }
        
        return results

    @staticmethod
    def calculate_indicators(df: pl.DataFrame, indicators: List[Dict]) -> pl.DataFrame:
        """
        Calculate technical indicators using Polars expresiones (highly parallel).
        """
        for ind in indicators:
            ind_type = ind.get("type", "").lower()
            params = ind.get("params", {})
            col = ind.get("col", "Close")
            
            if ind_type == "sma":
                p = params.get("period", 20)
                df = df.with_columns([
                    pl.col(col).rolling_mean(window_size=p).alias(f"sma_{p}")
                ])
            elif ind_type == "ema":
                p = params.get("period", 20)
                # Polars doesn't have a direct rolling_ema yet, but we can use ewm_mean
                df = df.with_columns([
                    pl.col(col).ewm_mean(span=p).alias(f"ema_{p}")
                ])
            elif ind_type == "rsi":
                p = params.get("period", 14)
                # RSI implementation in Polars
                diff = pl.col(col).diff()
                gain = pl.when(diff > 0).then(diff).otherwise(0)
                loss = pl.when(diff < 0).then(-diff).otherwise(0)
                avg_gain = gain.rolling_mean(window_size=p)
                avg_loss = loss.rolling_mean(window_size=p)
                rs = avg_gain / avg_loss
                df = df.with_columns([
                    (100 - (100 / (1 + rs))).alias(f"rsi_{p}")
                ])
        
        return df

    @staticmethod
    def backtest_vectorized(df: pl.DataFrame, entry_rules: str, exit_rules: str) -> Dict[str, Any]:
        """
        Institutional-grade vectorized backtest.
        This assumes we can map rules to Polars logical expressions.
        """
        # Note: True event-driven logic still needs loops for state, 
        # but for signal discovery we use vectorization.
        
        # 1. Generate Signals
        # Placeholder: Eval entry_rules against columns
        # In a real system, we'd use a parser to convert "rsi < 30" to pl.col("rsi_14") < 30
        
        # 2. Performance Attribution
        # Calculate log returns
        df = df.with_columns([
            (pl.col("Close").log() - pl.col("Close").shift(1).log()).alias("log_return")
        ])
        
        metrics = {
            "total_return": float(df["log_return"].sum()),
            "volatility": float(df["log_return"].std() * np.sqrt(252)),
            # ... more metrics
        }
        
        return metrics
