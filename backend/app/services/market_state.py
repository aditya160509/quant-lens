"""
Market Labs - Market State Service
Core data foundation for all 7 engines

Computes and caches:
- Clean OHLCV matrix (ticker × date)
- Returns matrix: r_it = ln(C_it / C_it-1)
- Rolling metrics (5D, 20D, 60D, 120D, 252D)
- Sector mappings
"""

import numpy as np
import pandas as pd
from typing import Dict, List, Optional, Tuple, Any
from datetime import datetime, timedelta
import hashlib
import logging

logger = logging.getLogger(__name__)

# ============================================================================
# UNIVERSE CONFIGURATIONS
# ============================================================================

US_UNIVERSE = {
    "anchors": ["SPY", "QQQ", "IWM", "DIA", "TLT", "IEF", "LQD", "HYG", "GLD", "VIX"],
    "sector_etfs": {
        "Technology": ["XLK", "QQQ", "AAPL", "MSFT", "NVDA", "GOOGL", "META", "AVGO", "ORCL", "CRM"],
        "Financials": ["XLF", "JPM", "BAC", "WFC", "GS", "MS", "C", "BLK", "SCHW", "AXP"],
        "Healthcare": ["XLV", "UNH", "JNJ", "LLY", "PFE", "ABBV", "MRK", "TMO", "ABT", "DHR"],
        "Energy": ["XLE", "XOM", "CVX", "COP", "SLB", "EOG", "MPC", "PSX", "VLO", "OXY"],
        "Consumer Discretionary": ["XLY", "AMZN", "TSLA", "HD", "MCD", "NKE", "SBUX", "TGT", "LOW", "CMG"],
        "Consumer Staples": ["XLP", "PG", "KO", "PEP", "COST", "WMT", "PM", "MO", "CL", "MDLZ"],
        "Industrials": ["XLI", "CAT", "BA", "HON", "UNP", "GE", "RTX", "LMT", "DE", "MMM"],
        "Materials": ["XLB", "LIN", "APD", "SHW", "FCX", "NEM", "NUE", "DD", "ECL", "VMC"],
        "Utilities": ["XLU", "NEE", "DUK", "SO", "D", "AEP", "EXC", "SRE", "XEL", "PEG"],
        "Real Estate": ["XLRE", "AMT", "PLD", "CCI", "EQIX", "PSA", "SPG", "WELL", "DLR", "O"],
        "Communication": ["XLC", "META", "GOOGL", "NFLX", "DIS", "CMCSA", "VZ", "T", "TMUS", "CHTR"],
    },
    "benchmark": "SPY"
}

INDIA_UNIVERSE = {
    "anchors": ["^NSEI", "USDINR=X"],
    "sector_groups": {
        "Banking": ["HDFCBANK.NS", "ICICIBANK.NS", "SBIN.NS", "KOTAKBANK.NS", "AXISBANK.NS", "INDUSINDBK.NS"],
        "IT": ["TCS.NS", "INFY.NS", "WIPRO.NS", "HCLTECH.NS", "TECHM.NS", "LTI.NS"],
        "Energy": ["RELIANCE.NS", "ONGC.NS", "NTPC.NS", "POWERGRID.NS", "ADANIGREEN.NS"],
        "Auto": ["MARUTI.NS", "TATAMOTORS.NS", "M&M.NS", "BAJAJ-AUTO.NS", "HEROMOTOCO.NS"],
        "Pharma": ["SUNPHARMA.NS", "DRREDDY.NS", "DIVISLAB.NS", "CIPLA.NS", "APOLLOHOSP.NS"],
        "FMCG": ["HINDUNILVR.NS", "ITC.NS", "NESTLEIND.NS", "BRITANNIA.NS", "DABUR.NS"],
        "Metals": ["TATASTEEL.NS", "HINDALCO.NS", "JSWSTEEL.NS", "VEDL.NS", "COALINDIA.NS"],
        "Infra": ["LARSEN.NS", "ULTRACEMCO.NS", "ADANIPORTS.NS", "GRASIM.NS", "SHREECEM.NS"],
    },
    "benchmark": "^NSEI"
}


# ============================================================================
# MARKET STATE CLASS
# ============================================================================

class MarketState:
    """
    Core data foundation for Market Labs engines.
    Builds and caches all required data matrices.
    """
    
    WINDOWS = [5, 20, 60, 120, 252]
    
    def __init__(self, universe: str = "US", lookback_days: int = 252):
        self.universe = universe.upper()
        self.lookback_days = lookback_days
        self.config = US_UNIVERSE if universe == "US" else INDIA_UNIVERSE
        
        # Data matrices (populated on build)
        self.prices: Optional[pd.DataFrame] = None  # Close prices
        self.returns: Optional[pd.DataFrame] = None  # Log returns
        self.volumes: Optional[pd.DataFrame] = None  # Volumes
        self.dollar_volume: Optional[pd.DataFrame] = None  # Price × Volume
        self.high: Optional[pd.DataFrame] = None
        self.low: Optional[pd.DataFrame] = None
        self.open_prices: Optional[pd.DataFrame] = None
        
        # Metadata
        self.tickers: List[str] = []
        self.sector_map: Dict[str, str] = {}
        self.dates: List[datetime] = []
        self.build_time: Optional[datetime] = None
        self.state_hash: Optional[str] = None
        self.missingness: Dict[str, float] = {}
        
    def get_all_tickers(self) -> List[str]:
        """Get all tickers for the universe."""
        tickers = set(self.config["anchors"])
        
        if self.universe == "US":
            for sector, names in self.config["sector_etfs"].items():
                tickers.update(names)
                for name in names:
                    self.sector_map[name] = sector
        else:
            for sector, names in self.config["sector_groups"].items():
                tickers.update(names)
                for name in names:
                    self.sector_map[name] = sector
                    
        return list(tickers)
    
    async def build(self) -> Dict[str, Any]:
        """
        Build the MarketState from fresh data.
        Returns metadata about the build.
        """
        from app.services.yf_wrapper import get_cached_yf_data
        
        self.tickers = self.get_all_tickers()
        end_date = datetime.now()
        start_date = end_date - timedelta(days=self.lookback_days + 30)  # Buffer
        
        logger.info(f"Building MarketState for {self.universe} with {len(self.tickers)} tickers")
        
        try:
            # Fetch OHLCV data using our rate-limited wrapper
            data = await get_cached_yf_data(
                self.tickers,
                period=f"{self.lookback_days + 30}d",
                interval="1d"
            )
            
            if data is None or data.empty:
                raise ValueError("No data returned from yfinance")
            
            # Handle multi-level columns from yf.download
            if isinstance(data.columns, pd.MultiIndex):
                self.prices = data['Close'].copy()
                self.volumes = data['Volume'].copy()
                self.high = data['High'].copy()
                self.low = data['Low'].copy()
                self.open_prices = data['Open'].copy()
            else:
                # Single ticker case
                self.prices = data[['Close']].copy()
                self.prices.columns = [self.tickers[0]]
                self.volumes = data[['Volume']].copy()
                self.volumes.columns = [self.tickers[0]]
                self.high = data[['High']].copy()
                self.high.columns = [self.tickers[0]]
                self.low = data[['Low']].copy()
                self.low.columns = [self.tickers[0]]
                self.open_prices = data[['Open']].copy()
                self.open_prices.columns = [self.tickers[0]]
            
            # Trim to lookback
            self.prices = self.prices.tail(self.lookback_days)
            self.volumes = self.volumes.tail(self.lookback_days)
            self.high = self.high.tail(self.lookback_days)
            self.low = self.low.tail(self.lookback_days)
            self.open_prices = self.open_prices.tail(self.lookback_days)
            
            # Compute log returns
            self.returns = np.log(self.prices / self.prices.shift(1))
            self.returns = self.returns.iloc[1:]  # Drop first NaN row
            
            # Compute dollar volume
            self.dollar_volume = self.prices * self.volumes
            
            # Update dates
            self.dates = self.prices.index.tolist()
            
            # Compute missingness
            for ticker in self.prices.columns:
                missing_pct = self.prices[ticker].isna().sum() / len(self.prices) * 100
                self.missingness[ticker] = missing_pct
            
            # Remove tickers with > 20% missing
            valid_tickers = [t for t in self.prices.columns if self.missingness.get(t, 0) < 20]
            self.prices = self.prices[valid_tickers]
            self.returns = self.returns[valid_tickers]
            self.volumes = self.volumes[valid_tickers]
            self.dollar_volume = self.dollar_volume[valid_tickers]
            self.high = self.high[valid_tickers]
            self.low = self.low[valid_tickers]
            self.open_prices = self.open_prices[valid_tickers]
            
            # Forward fill remaining NaNs (weekends, holidays)
            self.prices = self.prices.ffill()
            self.returns = self.returns.fillna(0)
            
            self.build_time = datetime.now()
            self.state_hash = self._compute_hash()
            
            return {
                "success": True,
                "universe": self.universe,
                "ticker_count": len(valid_tickers),
                "date_range": [str(self.dates[0]), str(self.dates[-1])],
                "state_hash": self.state_hash,
                "avg_completeness": 100 - np.mean(list(self.missingness.values())),
                "dropped_tickers": [t for t in self.tickers if t not in valid_tickers]
            }
            
        except Exception as e:
            logger.error(f"MarketState build failed: {e}")
            return {
                "success": False,
                "error": str(e),
                "universe": self.universe
            }
    
    def _compute_hash(self) -> str:
        """Compute unique hash for this state."""
        key = f"{self.universe}_{len(self.tickers)}_{self.lookback_days}_{self.build_time}"
        return hashlib.md5(key.encode()).hexdigest()[:12]
    
    # ========================================================================
    # ROLLING COMPUTATIONS
    # ========================================================================
    
    def rolling_volatility(self, window: int = 20) -> pd.DataFrame:
        """Annualized rolling volatility."""
        return self.returns.rolling(window).std() * np.sqrt(252)
    
    def rolling_mean(self, window: int = 20) -> pd.DataFrame:
        """Rolling mean return."""
        return self.returns.rolling(window).mean()
    
    def moving_average(self, window: int = 20) -> pd.DataFrame:
        """Simple moving average of prices."""
        return self.prices.rolling(window).mean()
    
    def rolling_correlation(self, ticker: str, window: int = 60) -> pd.DataFrame:
        """Rolling correlation of all tickers with a reference ticker."""
        if ticker not in self.returns.columns:
            return pd.DataFrame()
        ref = self.returns[ticker]
        return self.returns.apply(lambda x: x.rolling(window).corr(ref))
    
    # ========================================================================
    # BREADTH METRICS
    # ========================================================================
    
    def advance_decline(self) -> pd.DataFrame:
        """Compute daily advance/decline counts."""
        advances = (self.returns > 0).sum(axis=1)
        declines = (self.returns < 0).sum(axis=1)
        unchanged = (self.returns == 0).sum(axis=1)
        
        return pd.DataFrame({
            "advances": advances,
            "declines": declines,
            "unchanged": unchanged,
            "ad_diff": advances - declines,
            "ad_ratio": advances / (declines + 1),
            "ad_cumulative": (advances - declines).cumsum()
        })
    
    def pct_above_ma(self, window: int = 50) -> pd.Series:
        """Percent of stocks above moving average."""
        ma = self.moving_average(window)
        above = (self.prices > ma).sum(axis=1)
        return above / len(self.prices.columns) * 100
    
    def new_highs_lows(self, window: int = 20) -> pd.DataFrame:
        """Count of new highs and lows over rolling window."""
        rolling_high = self.prices.rolling(window).max()
        rolling_low = self.prices.rolling(window).min()
        
        new_highs = (self.prices == rolling_high).sum(axis=1)
        new_lows = (self.prices == rolling_low).sum(axis=1)
        
        return pd.DataFrame({
            "new_highs": new_highs,
            "new_lows": new_lows,
            "nhnl_diff": new_highs - new_lows
        })
    
    def up_down_volume(self) -> pd.DataFrame:
        """Up volume vs down volume."""
        up_mask = self.returns > 0
        down_mask = self.returns < 0
        
        up_vol = (self.dollar_volume * up_mask).sum(axis=1)
        down_vol = (self.dollar_volume * down_mask).sum(axis=1)
        
        return pd.DataFrame({
            "up_volume": up_vol,
            "down_volume": down_vol,
            "volume_diff": up_vol - down_vol,
            "volume_ratio": up_vol / (down_vol + 1)
        })
    
    # ========================================================================
    # DISPERSION & CONCENTRATION
    # ========================================================================
    
    def dispersion(self) -> pd.Series:
        """Cross-sectional return dispersion (std of returns)."""
        return self.returns.std(axis=1)
    
    def median_return(self) -> pd.Series:
        """Median return across all stocks."""
        return self.returns.median(axis=1)
    
    def equal_weight_return(self) -> pd.Series:
        """Equal-weighted portfolio return."""
        return self.returns.mean(axis=1)
    
    def market_cap_return(self, weights: Optional[Dict[str, float]] = None) -> pd.Series:
        """Cap-weighted return (uses equal weights if not provided)."""
        if weights is None:
            return self.equal_weight_return()
        w = pd.Series(weights)
        w = w.reindex(self.returns.columns).fillna(0)
        w = w / w.sum()
        return (self.returns * w).sum(axis=1)
    
    def contribution(self, weights: Optional[Dict[str, float]] = None) -> pd.DataFrame:
        """Per-ticker contribution to portfolio return."""
        if weights is None:
            w = 1 / len(self.returns.columns)
        else:
            w = pd.Series(weights).reindex(self.returns.columns).fillna(0)
            w = w / w.sum()
        return self.returns * w
    
    def herfindahl(self) -> pd.Series:
        """Herfindahl concentration index from contributions."""
        contrib = self.contribution()
        total = contrib.abs().sum(axis=1)
        shares = (contrib.abs().T / (total + 1e-10)).T
        return (shares ** 2).sum(axis=1)
    
    # ========================================================================
    # TAIL RISK
    # ========================================================================
    
    def tail_shares(self, z_threshold: float = 2.0) -> pd.DataFrame:
        """Percent of returns in left/right tails."""
        mu = self.returns.mean(axis=1)
        sigma = self.returns.std(axis=1)
        
        left_threshold = mu - z_threshold * sigma
        right_threshold = mu + z_threshold * sigma
        
        left_tail = (self.returns.T < left_threshold).T.sum(axis=1) / len(self.returns.columns) * 100
        right_tail = (self.returns.T > right_threshold).T.sum(axis=1) / len(self.returns.columns) * 100
        
        return pd.DataFrame({
            "left_tail_pct": left_tail,
            "right_tail_pct": right_tail,
            "tail_skew": right_tail - left_tail
        })
    
    # ========================================================================
    # LIQUIDITY METRICS  
    # ========================================================================
    
    def amihud_illiquidity(self) -> pd.DataFrame:
        """Amihud illiquidity ratio: |return| / dollar_volume."""
        illiq = self.returns.abs() / (self.dollar_volume + 1)
        return illiq
    
    def gap_detection(self, threshold: float = 0.02) -> Dict:
        """Detect opening gaps. Returns dict with gap_size and gap_flag DataFrames."""
        gaps = (self.open_prices - self.prices.shift(1)) / self.prices.shift(1)
        gap_flags = gaps.abs() > threshold
        return {
            "gap_size": gaps,
            "gap_flag": gap_flags
        }
    
    def gap_fill_rates(self, threshold: float = 0.02) -> Dict[str, Any]:
        """
        Compute gap fill rates: Fill1D and Fill5D.
        Fill1D = 1 if price crosses yesterday's close within today
        Fill5D = 1 if any day in [t, t+5] crosses yesterday's close
        """
        prev_close = self.prices.shift(1)
        gaps = (self.open_prices - prev_close) / prev_close
        gap_flags = gaps.abs() > threshold
        
        # Classify gaps: small (<1%), medium (1-3%), large (>3%)
        gap_abs = gaps.abs()
        gap_small = (gap_abs > 0.001) & (gap_abs <= 0.01)
        gap_medium = (gap_abs > 0.01) & (gap_abs <= 0.03)
        gap_large = gap_abs > 0.03
        
        # Fill1D: low or high crosses prev close within the day
        fill_1d = ((self.low <= prev_close) & (self.high >= prev_close)).astype(int)
        
        # Fill5D: any of next 5 days crosses prev close
        fill_5d = pd.DataFrame(0, index=self.prices.index, columns=self.prices.columns)
        for offset in range(1, 6):
            if offset < len(self.prices):
                low_shifted = self.low.shift(-offset)
                high_shifted = self.high.shift(-offset)
                crossed = ((low_shifted <= prev_close) & (high_shifted >= prev_close)).astype(int)
                fill_5d = fill_5d | crossed
        
        # Only count fills where there was a gap
        fill_1d_flagged = fill_1d * gap_flags.astype(int)
        fill_5d_flagged = fill_5d * gap_flags.astype(int)
        
        # Aggregate by bucket
        results = {}
        for bucket_name, bucket_mask in [("small", gap_small), ("medium", gap_medium), ("large", gap_large)]:
            gaps_in_bucket = bucket_mask.sum().sum()
            fills_1d = (fill_1d_flagged * bucket_mask.astype(int)).sum().sum()
            fills_5d = (fill_5d_flagged * bucket_mask.astype(int)).sum().sum()
            
            results[bucket_name] = {
                "gap_count": int(gaps_in_bucket),
                "fill_1d_count": int(fills_1d),
                "fill_5d_count": int(fills_5d),
                "fill_1d_rate": round(fills_1d / max(gaps_in_bucket, 1), 3),
                "fill_5d_rate": round(fills_5d / max(gaps_in_bucket, 1), 3)
            }
        
        # Overall
        total_gaps = gap_flags.sum().sum()
        total_fill_1d = fill_1d_flagged.sum().sum()
        total_fill_5d = fill_5d_flagged.sum().sum()
        results["overall"] = {
            "gap_count": int(total_gaps),
            "fill_1d_rate": round(total_fill_1d / max(total_gaps, 1), 3),
            "fill_5d_rate": round(total_fill_5d / max(total_gaps, 1), 3)
        }
        
        return results
    
    def illiquidity_surface(self) -> List[Dict]:
        """Sector × Liquidity bucket surface heatmap data."""
        illiq = self.amihud_illiquidity()
        
        # Get dollar volume quintiles
        latest_dv = self.dollar_volume.iloc[-20:].mean()
        dv_bins = pd.qcut(latest_dv, 5, labels=["Q1 (Low)", "Q2", "Q3", "Q4", "Q5 (High)"], duplicates='drop')
        
        surface = []
        for sector in set(self.sector_map.values()):
            sector_tickers = [t for t, s in self.sector_map.items() if s == sector and t in illiq.columns]
            if not sector_tickers:
                continue
                
            for bucket in dv_bins.unique():
                bucket_tickers = [t for t in sector_tickers if t in dv_bins.index and dv_bins[t] == bucket]
                if bucket_tickers:
                    median_illiq = illiq[bucket_tickers].iloc[-1].median()
                    surface.append({
                        "sector": sector,
                        "liquidity_bucket": str(bucket),
                        "median_illiq": float(median_illiq) if not pd.isna(median_illiq) else 0
                    })
        
        return surface
    
    def cluster_stability(self, window_short: int = 20, window_long: int = 60) -> Dict[str, Any]:
        """
        Compute cluster stability / churn using hierarchical clustering.
        Compares cluster labels at short vs long window.
        Churn = fraction of tickers that change cluster.
        """
        from scipy.cluster.hierarchy import linkage, fcluster
        from scipy.spatial.distance import squareform
        
        # Get sector returns for clustering (more stable than individual tickers)
        sector_rets = self.sector_returns()
        if sector_rets.empty:
            return {"churn": 0.0, "clusters": []}
        
        # Compute correlation-based distance for both windows
        corr_short = sector_rets.tail(window_short).corr().fillna(0)
        corr_long = sector_rets.tail(window_long).corr().fillna(0)
        
        # Convert to distance matrix (1 - corr)
        dist_short = 1 - corr_short.clip(-1, 1)
        dist_long = 1 - corr_long.clip(-1, 1)
        
        # Ensure symmetric and positive
        np.fill_diagonal(dist_short.values, 0)
        np.fill_diagonal(dist_long.values, 0)
        
        try:
            # Hierarchical clustering
            linkage_short = linkage(squareform(dist_short, checks=False), method='ward')
            linkage_long = linkage(squareform(dist_long, checks=False), method='ward')
            
            # Cut at threshold to get clusters
            clusters_short = fcluster(linkage_short, t=1.0, criterion='distance')
            clusters_long = fcluster(linkage_long, t=1.0, criterion='distance')
            
            # Compute churn (fraction that changed cluster)
            churn = (clusters_short != clusters_long).sum() / len(clusters_short)
            
            # Build cluster info
            cluster_info = []
            for i, sector in enumerate(sector_rets.columns):
                cluster_info.append({
                    "sector": sector,
                    "cluster_short": int(clusters_short[i]),
                    "cluster_long": int(clusters_long[i]),
                    "changed": bool(clusters_short[i] != clusters_long[i])
                })
            
            return {
                "churn": round(float(churn), 3),
                "clusters": cluster_info,
                "window_short": window_short,
                "window_long": window_long
            }
            
        except Exception as e:
            logger.warning(f"Cluster stability error: {e}")
            return {"churn": 0.0, "clusters": [], "error": str(e)}
    
    def vol_compression_break(self, window: int = 20, compression_pct: float = 20, break_pct: float = 60) -> List[Dict]:
        """
        Detect vol compression → break patterns.
        A simpler, more robust approach: find tickers where recent vol jumped significantly.
        """
        vol = self.rolling_volatility(window)
        
        events = []
        
        for ticker in vol.columns[:50]:  # Limit for performance
            ticker_vol = vol[ticker].dropna()
            if len(ticker_vol) < 60:
                continue
            
            # Get recent vol stats
            recent_vol = float(ticker_vol.iloc[-1])
            avg_vol = float(ticker_vol.tail(60).mean())
            min_vol_60d = float(ticker_vol.tail(60).min())
            max_vol_60d = float(ticker_vol.tail(60).max())
            
            # Check if there was a significant compression-to-break pattern recently
            # Look for minimum vol point and measure break from there
            vol_60d = ticker_vol.tail(60)
            min_idx = vol_60d.idxmin()
            min_pos = vol_60d.index.get_loc(min_idx)
            
            # Only count if min was not in the last 3 days and current is elevated
            if min_pos < len(vol_60d) - 5:
                vol_at_min = float(vol_60d.iloc[min_pos])
                days_since_min = len(vol_60d) - 1 - min_pos
                
                # Calculate expansion ratio
                if vol_at_min > 0.001:  # Avoid division by zero
                    expansion_ratio = recent_vol / vol_at_min
                    
                    # If vol expanded by >50%, record it
                    if expansion_ratio > 1.5:
                        events.append({
                            "ticker": ticker,
                            "compression_date": str(min_idx.date()) if hasattr(min_idx, 'date') else str(min_idx)[:10],
                            "break_date": str(ticker_vol.index[-1].date()) if hasattr(ticker_vol.index[-1], 'date') else str(ticker_vol.index[-1])[:10],
                            "before_vol": round(vol_at_min, 4),
                            "after_vol": round(recent_vol, 4),
                            "expansion_ratio": round(expansion_ratio, 2),
                            "days_compressed": int(days_since_min),
                            "sector": self.sector_map.get(ticker, "Unknown")
                        })
        
        # Sort by expansion ratio descending and return top 20
        return sorted(events, key=lambda x: x.get("expansion_ratio", 0), reverse=True)[:20]
    
    def lead_lag(self, anchors: List[str] = None, max_lag: int = 5) -> List[Dict]:
        """
        Compute lead-lag relationships between anchors and sectors.
        LagCorr(k) = corr(r_anchor[t-k], r_sector[t])
        """
        sector_rets = self.sector_returns()
        
        if anchors is None:
            anchors = self.config.get("anchors", [])[:5]
        
        results = []
        
        for anchor in anchors:
            if anchor not in self.returns.columns:
                continue
                
            anchor_ret = self.returns[anchor]
            
            for sector in sector_rets.columns:
                sector_ret = sector_rets[sector]
                
                # Compute correlation at different lags
                lag_corrs = {}
                for k in range(-max_lag, max_lag + 1):
                    if k < 0:
                        # Anchor leads sector
                        corr = anchor_ret.shift(-k).corr(sector_ret)
                    elif k > 0:
                        # Sector leads anchor
                        corr = anchor_ret.corr(sector_ret.shift(k))
                    else:
                        corr = anchor_ret.corr(sector_ret)
                    
                    lag_corrs[k] = float(corr) if not pd.isna(corr) else 0
                
                # Find optimal lag
                best_lag = max(lag_corrs, key=lambda k: abs(lag_corrs[k]))
                best_corr = lag_corrs[best_lag]
                
                results.append({
                    "anchor": anchor,
                    "sector": sector,
                    "best_lag": best_lag,
                    "lag_corr": round(best_corr, 3),
                    "direction": "anchor_leads" if best_lag < 0 else ("sector_leads" if best_lag > 0 else "synchronous"),
                    "all_lags": lag_corrs
                })
        
        return sorted(results, key=lambda x: abs(x["lag_corr"]), reverse=True)
    
    def regime_drift(self, window: int = 30) -> Dict[str, Any]:
        """
        Compute regime drift - how fingerprint components are trending.
        Tracks 30-day trend in each component percentile.
        """
        # Compute component series
        ad = self.advance_decline()
        dispersion = self.dispersion()
        herfindahl = self.herfindahl()
        illiq = self.amihud_illiquidity().median(axis=1)
        tails = self.tail_shares()
        
        # Build fingerprint percentiles over time
        components = {
            "breadth": ad["ad_diff"],
            "dispersion": dispersion,
            "concentration": herfindahl,
            "liquidity_stress": illiq,
            "left_tail": tails["left_tail_pct"],
            "right_tail": tails["right_tail_pct"]
        }
        
        drift = {}
        for name, series in components.items():
            if len(series) < window * 2:
                drift[name] = 0
                continue
            
            # Compute percentile for recent vs prior window
            recent = series.iloc[-window:]
            prior = series.iloc[-window*2:-window]
            
            recent_pct = recent.mean()
            prior_pct = prior.mean()
            
            # Normalize to percentile change
            overall_std = series.std()
            if overall_std > 0:
                drift[name] = round(float((recent_pct - prior_pct) / overall_std * 10), 1)
            else:
                drift[name] = 0
        
        # Compute overall regime direction
        pos_drift = sum(1 for v in drift.values() if v > 0.5)
        neg_drift = sum(1 for v in drift.values() if v < -0.5)
        
        if pos_drift > neg_drift + 1:
            regime_direction = "deteriorating"
        elif neg_drift > pos_drift + 1:
            regime_direction = "improving"
        else:
            regime_direction = "stable"
        
        return {
            "drift": drift,
            "regime_direction": regime_direction,
            "window": window
        }

    
    # ========================================================================
    # FLOW METRICS
    # ========================================================================
    
    def close_location_value(self) -> pd.DataFrame:
        """CLV = ((C-L) - (H-C)) / (H-L). Ranges -1 to +1."""
        range_hl = self.high - self.low
        clv = ((self.prices - self.low) - (self.high - self.prices)) / (range_hl + 1e-10)
        return clv.clip(-1, 1)
    
    def flow_proxy(self) -> pd.DataFrame:
        """Flow = CLV × Volume."""
        clv = self.close_location_value()
        return clv * self.volumes
    
    # ========================================================================
    # CORRELATION METRICS
    # ========================================================================
    
    def correlation_matrix(self, window: int = 60) -> pd.DataFrame:
        """Full correlation matrix using rolling window."""
        return self.returns.tail(window).corr()
    
    def average_correlation(self, window: int = 60) -> float:
        """Average pairwise correlation."""
        corr = self.correlation_matrix(window)
        # Get upper triangle (excluding diagonal)
        mask = np.triu(np.ones_like(corr, dtype=bool), k=1)
        return corr.where(mask).stack().mean()
    
    def correlation_dispersion(self, window: int = 60) -> float:
        """Std of pairwise correlations."""
        corr = self.correlation_matrix(window)
        mask = np.triu(np.ones_like(corr, dtype=bool), k=1)
        return corr.where(mask).stack().std()
    
    # ========================================================================
    # BENCHMARK METRICS
    # ========================================================================
    
    def get_benchmark_returns(self) -> pd.Series:
        """Get benchmark return series."""
        benchmark = self.config["benchmark"]
        if benchmark in self.returns.columns:
            return self.returns[benchmark]
        # Try to find it with suffix
        for col in self.returns.columns:
            if benchmark in col:
                return self.returns[col]
        return self.equal_weight_return()
    
    def beta_to_benchmark(self, window: int = 60) -> pd.Series:
        """Rolling beta of each ticker to benchmark."""
        bench = self.get_benchmark_returns()
        bench_var = bench.rolling(window).var()
        
        betas = {}
        for ticker in self.returns.columns:
            cov = self.returns[ticker].rolling(window).cov(bench)
            betas[ticker] = (cov / (bench_var + 1e-10)).iloc[-1]
        
        return pd.Series(betas)
    
    # ========================================================================
    # SECTOR AGGREGATIONS
    # ========================================================================
    
    def sector_returns(self) -> pd.DataFrame:
        """Returns aggregated by sector."""
        sector_rets = {}
        for sector in set(self.sector_map.values()):
            tickers = [t for t, s in self.sector_map.items() if s == sector and t in self.returns.columns]
            if tickers:
                sector_rets[sector] = self.returns[tickers].mean(axis=1)
        return pd.DataFrame(sector_rets)
    
    def sector_breadth(self) -> pd.DataFrame:
        """Breadth (% positive) by sector."""
        sector_breadth = {}
        for sector in set(self.sector_map.values()):
            tickers = [t for t, s in self.sector_map.items() if s == sector and t in self.returns.columns]
            if tickers:
                sector_breadth[sector] = (self.returns[tickers] > 0).sum(axis=1) / len(tickers) * 100
        return pd.DataFrame(sector_breadth)


# ============================================================================
# GLOBAL STATE CACHE
# ============================================================================

_market_state_cache: Dict[str, MarketState] = {}

async def get_or_build_market_state(universe: str = "US", force_rebuild: bool = False) -> MarketState:
    """Get cached MarketState or build new one."""
    global _market_state_cache
    
    cache_key = f"{universe.upper()}"
    
    if not force_rebuild and cache_key in _market_state_cache:
        state = _market_state_cache[cache_key]
        # Check if stale (> 24 hours)
        if state.build_time and (datetime.now() - state.build_time).seconds < 86400:
            return state
    
    # Build new state
    state = MarketState(universe=universe)
    result = await state.build()
    
    if result.get("success"):
        _market_state_cache[cache_key] = state
        
    return state
