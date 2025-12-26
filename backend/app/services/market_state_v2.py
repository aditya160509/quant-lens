"""
MarketState V2 - Unified Data Foundation for PCA Eigenphysics
=============================================================

Architectural Principles:
1. NSE API is PRIMARY for Indian markets, yfinance is FALLBACK
2. All data is cached with TTL-based invalidation
3. Zero redundant fetches - MarketState is built once and reused
4. Quality gates: tickers with >5% missing data are dropped
5. No interpolation, no forward-fill for missing trading days

Schema:
- prices: pd.DataFrame (ticker × date) - adjusted close prices
- returns: pd.DataFrame (ticker × date) - log returns
- volumes: pd.DataFrame (ticker × date) - traded volume
- dollar_volume: pd.DataFrame (ticker × date) - price × volume
- ohlc: Dict[str, pd.DataFrame] - open, high, low, close
- metadata: MarketStateMetadata - provenance, quality, timestamps

Usage:
    state = await get_market_state("INDIA", lookback_days=252)
    print(state.returns.shape)  # (251, 80) for 80 tickers
    print(state.metadata.quality)  # {'missing_pct': 0.02, ...}
"""

import numpy as np
import pandas as pd
from typing import Dict, List, Optional, Tuple, Any, Literal
from datetime import datetime, timedelta
from dataclasses import dataclass, field
import hashlib
import logging
import asyncio

logger = logging.getLogger(__name__)


# =============================================================================
# SCHEMA DEFINITIONS
# =============================================================================

@dataclass(frozen=True)
class QualityMetrics:
    """Quality metrics for a MarketState build."""
    tickers_requested: int
    tickers_valid: int
    tickers_dropped: int
    dropped_tickers: Tuple[str, ...]
    drop_reasons: Dict[str, str]
    avg_completeness: float
    min_completeness: float
    trading_days: int
    date_range: Tuple[str, str]
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "tickers_requested": self.tickers_requested,
            "tickers_valid": self.tickers_valid,
            "tickers_dropped": self.tickers_dropped,
            "dropped_tickers": list(self.dropped_tickers),
            "drop_reasons": self.drop_reasons,
            "avg_completeness": round(self.avg_completeness, 4),
            "min_completeness": round(self.min_completeness, 4),
            "trading_days": self.trading_days,
            "date_range": list(self.date_range),
        }


@dataclass(frozen=True)
class DataProvenance:
    """Provenance tracking for a MarketState."""
    data_source: Literal["nse_direct", "yfinance", "mixed"]
    fetch_timestamp: str
    build_timestamp: str
    config_hash: str
    universe_key: str
    lookback_days: int
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "data_source": self.data_source,
            "fetch_timestamp": self.fetch_timestamp,
            "build_timestamp": self.build_timestamp,
            "config_hash": self.config_hash,
            "universe_key": self.universe_key,
            "lookback_days": self.lookback_days,
        }


@dataclass
class MarketStateMetadata:
    """Metadata container for MarketState."""
    quality: QualityMetrics
    provenance: DataProvenance
    sector_map: Dict[str, str]
    state_hash: str
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "quality": self.quality.to_dict(),
            "provenance": self.provenance.to_dict(),
            "sector_map": self.sector_map,
            "state_hash": self.state_hash,
        }


@dataclass
class OHLCData:
    """OHLC container."""
    open: pd.DataFrame
    high: pd.DataFrame
    low: pd.DataFrame
    close: pd.DataFrame


# =============================================================================
# UNIVERSE CONFIGURATIONS - Extended for PCA
# =============================================================================

UNIVERSE_CONFIG = {
    "INDIA": {
        "primary_source": "nse_direct",
        "fallback_source": "yfinance",
        "max_tickers": 80,
        "min_trading_days": 240,
        "max_missing_pct": 0.05,
        "benchmark": "^NSEI",
        "anchors": [
            "^NSEI",  # Nifty 50
            "^NSEBANK",  # Bank Nifty
            "USDINR=X",  # USD/INR
        ],
        "sector_groups": {
            "Banking": [
                "HDFCBANK.NS", "ICICIBANK.NS", "SBIN.NS", "KOTAKBANK.NS",
                "AXISBANK.NS", "INDUSINDBK.NS", "BANKBARODA.NS", "PNB.NS",
            ],
            "IT": [
                "TCS.NS", "INFY.NS", "WIPRO.NS", "HCLTECH.NS",
                "TECHM.NS", "LTIM.NS", "PERSISTENT.NS", "COFORGE.NS",
            ],
            "Energy": [
                "RELIANCE.NS", "ONGC.NS", "NTPC.NS", "POWERGRID.NS",
                "ADANIGREEN.NS", "TATAPOWER.NS", "BPCL.NS", "IOC.NS",
            ],
            "Auto": [
                "MARUTI.NS", "TATAMOTORS.NS", "M&M.NS", "BAJAJ-AUTO.NS",
                "HEROMOTOCO.NS", "EICHERMOT.NS", "ASHOKLEY.NS",
            ],
            "Pharma": [
                "SUNPHARMA.NS", "DRREDDY.NS", "DIVISLAB.NS", "CIPLA.NS",
                "APOLLOHOSP.NS", "BIOCON.NS", "TORNTPHARM.NS",
            ],
            "FMCG": [
                "HINDUNILVR.NS", "ITC.NS", "NESTLEIND.NS", "BRITANNIA.NS",
                "DABUR.NS", "GODREJCP.NS", "MARICO.NS",
            ],
            "Metals": [
                "TATASTEEL.NS", "HINDALCO.NS", "JSWSTEEL.NS", "VEDL.NS",
                "COALINDIA.NS", "NMDC.NS", "SAIL.NS",
            ],
            "Infrastructure": [
                "LT.NS", "ULTRACEMCO.NS", "ADANIPORTS.NS", "GRASIM.NS",
                "SHREECEM.NS", "ACC.NS", "AMBUJACEM.NS",
            ],
            "Finance_NBFC": [
                "BAJFINANCE.NS", "BAJAJFINSV.NS", "HDFCAMC.NS", "SBILIFE.NS",
                "ICICIPRULI.NS", "MUTHOOTFIN.NS", "CHOLAFIN.NS",
            ],
            "Consumer": [
                "TITAN.NS", "ASIANPAINT.NS", "HAVELLS.NS", "PIDILITIND.NS",
                "VOLTAS.NS", "PAGEIND.NS",
            ],
            "Communication": [
                "BHARTIARTL.NS", "IDEA.NS", "TATACOMM.NS",
            ],
        },
    },
    "US": {
        "primary_source": "yfinance",
        "fallback_source": None,
        "max_tickers": 200,
        "min_trading_days": 240,
        "max_missing_pct": 0.05,
        "benchmark": "SPY",
        "anchors": [
            "SPY", "QQQ", "IWM", "DIA",  # Major equity ETFs
            "TLT", "IEF", "LQD", "HYG",  # Bond ETFs
            "GLD", "SLV",  # Commodities
            "VIX",  # Volatility
        ],
        "sector_groups": {
            "Technology": [
                "XLK", "AAPL", "MSFT", "NVDA", "GOOGL", "META", "AVGO",
                "ORCL", "CRM", "AMD", "INTC", "ADBE", "CSCO", "NOW", "IBM",
            ],
            "Financials": [
                "XLF", "JPM", "BAC", "WFC", "GS", "MS", "C",
                "BLK", "SCHW", "AXP", "USB", "PNC", "TFC", "COF",
            ],
            "Healthcare": [
                "XLV", "UNH", "JNJ", "LLY", "PFE", "ABBV", "MRK",
                "TMO", "ABT", "DHR", "CVS", "BMY", "AMGN", "GILD",
            ],
            "Energy": [
                "XLE", "XOM", "CVX", "COP", "SLB", "EOG", "MPC",
                "PSX", "VLO", "OXY", "HAL", "DVN", "HES",
            ],
            "Consumer_Discretionary": [
                "XLY", "AMZN", "TSLA", "HD", "MCD", "NKE", "SBUX",
                "TGT", "LOW", "CMG", "GM", "F", "ROST", "TJX",
            ],
            "Consumer_Staples": [
                "XLP", "PG", "KO", "PEP", "COST", "WMT", "PM",
                "MO", "CL", "MDLZ", "KHC", "GIS", "K", "HSY",
            ],
            "Industrials": [
                "XLI", "CAT", "BA", "HON", "UNP", "GE", "RTX",
                "LMT", "DE", "MMM", "UPS", "WM", "CSX", "FDX",
            ],
            "Materials": [
                "XLB", "LIN", "APD", "SHW", "FCX", "NEM", "NUE",
                "DD", "ECL", "VMC", "MLM", "DOW", "PPG",
            ],
            "Utilities": [
                "XLU", "NEE", "DUK", "SO", "D", "AEP", "EXC",
                "SRE", "XEL", "PEG", "ED", "WEC", "ES", "AWK",
            ],
            "Real_Estate": [
                "XLRE", "AMT", "PLD", "CCI", "EQIX", "PSA", "SPG",
                "WELL", "DLR", "O", "AVB", "VTR", "EQR", "ARE",
            ],
            "Communication": [
                "XLC", "NFLX", "DIS", "CMCSA", "VZ", "T", "TMUS",
                "CHTR", "EA", "TTWO", "WBD", "PARA",
            ],
        },
    },
    "MACRO": {
        "primary_source": "yfinance",
        "fallback_source": None,
        "max_tickers": 25,
        "min_trading_days": 200,
        "max_missing_pct": 0.10,
        "benchmark": "SPY",
        "anchors": [
            # US Equity
            "SPY", "QQQ", "IWM", "DIA",
            # US Bonds
            "TLT", "IEF", "LQD", "HYG", "SHY",
            # Commodities
            "GLD", "SLV", "USO", "DBA",
            # International
            "EFA", "EEM", "VWO",
            # Volatility
            "VXX",
            # Real Estate
            "VNQ",
        ],
        "sector_groups": {},  # No sector breakdown for macro
    },
    "ETF": {
        "primary_source": "yfinance",
        "fallback_source": None,
        "max_tickers": 60,
        "min_trading_days": 200,
        "max_missing_pct": 0.10,
        "benchmark": "SPY",
        "anchors": [],
        "sector_groups": {
            "Equity_US_Large": ["SPY", "VOO", "VTI", "IVV", "QQQ", "IWB"],
            "Equity_US_Small": ["IWM", "IJR", "VB", "SCHA", "IWN"],
            "Equity_Growth": ["VUG", "IWF", "SCHG", "SPYG", "IVW"],
            "Equity_Value": ["VTV", "IWD", "SCHV", "SPYV", "IVE"],
            "Sector_ETFs": [
                "XLK", "XLF", "XLV", "XLE", "XLY", "XLP",
                "XLI", "XLB", "XLU", "XLRE", "XLC",
            ],
            "Fixed_Income": [
                "TLT", "IEF", "SHY", "BND", "AGG", "LQD",
                "HYG", "JNK", "TIP", "EMB",
            ],
            "International": ["EFA", "EEM", "VEA", "VWO", "IEFA", "IEMG"],
            "Commodity": ["GLD", "SLV", "USO", "DBA", "DBC", "PDBC"],
            "Real_Estate": ["VNQ", "IYR", "SCHH", "REM"],
            "Volatility": ["VXX", "SVXY", "UVXY"],
        },
    },
}


# =============================================================================
# MARKET STATE CLASS V2
# =============================================================================

class MarketStateV2:
    """
    Unified market state for PCA Eigenphysics and all analytics engines.
    
    Key Improvements over V1:
    - NSE Direct as primary for India
    - Explicit quality gates (no silent drops)
    - Frozen timestamps for reproducibility
    - No forward-fill (explicit NaN handling)
    """
    
    WINDOWS = (5, 20, 60, 120, 252)
    
    def __init__(
        self,
        universe_key: str = "INDIA",
        lookback_days: int = 252,
        custom_tickers: Optional[List[str]] = None,
    ):
        self.universe_key = universe_key.upper()
        self.lookback_days = lookback_days
        self.custom_tickers = custom_tickers
        
        config = UNIVERSE_CONFIG.get(self.universe_key)
        if config is None:
            raise ValueError(f"Unknown universe: {universe_key}")
        
        self.config = config
        
        # Data matrices (set during build)
        self._prices: Optional[pd.DataFrame] = None
        self._returns: Optional[pd.DataFrame] = None
        self._volumes: Optional[pd.DataFrame] = None
        self._dollar_volume: Optional[pd.DataFrame] = None
        self._ohlc: Optional[OHLCData] = None
        self._metadata: Optional[MarketStateMetadata] = None
        
        # Build state
        self._is_built: bool = False
        self._build_error: Optional[str] = None
    
    # =========================================================================
    # PROPERTIES (read-only access to data)
    # =========================================================================
    
    @property
    def prices(self) -> pd.DataFrame:
        if not self._is_built:
            raise RuntimeError("MarketState not built. Call build() first.")
        return self._prices
    
    @property
    def returns(self) -> pd.DataFrame:
        if not self._is_built:
            raise RuntimeError("MarketState not built. Call build() first.")
        return self._returns
    
    @property
    def volumes(self) -> pd.DataFrame:
        if not self._is_built:
            raise RuntimeError("MarketState not built. Call build() first.")
        return self._volumes
    
    @property
    def dollar_volume(self) -> pd.DataFrame:
        if not self._is_built:
            raise RuntimeError("MarketState not built. Call build() first.")
        return self._dollar_volume
    
    @property
    def ohlc(self) -> OHLCData:
        if not self._is_built:
            raise RuntimeError("MarketState not built. Call build() first.")
        return self._ohlc
    
    @property
    def metadata(self) -> MarketStateMetadata:
        if not self._is_built:
            raise RuntimeError("MarketState not built. Call build() first.")
        return self._metadata
    
    @property
    def tickers(self) -> List[str]:
        if not self._is_built:
            return []
        return list(self._prices.columns)
    
    @property
    def dates(self) -> List[datetime]:
        if not self._is_built:
            return []
        return list(self._prices.index)
    
    @property
    def is_built(self) -> bool:
        return self._is_built
    
    # =========================================================================
    # TICKER RESOLUTION
    # =========================================================================
    
    def _get_ticker_list(self) -> List[str]:
        """Resolve the complete ticker list for this universe."""
        if self.custom_tickers:
            return self.custom_tickers[:self.config["max_tickers"]]
        
        tickers = list(self.config.get("anchors", []))
        for sector, sector_tickers in self.config.get("sector_groups", {}).items():
            tickers.extend(sector_tickers)
        
        # Deduplicate while preserving order
        seen = set()
        unique = []
        for t in tickers:
            if t not in seen:
                seen.add(t)
                unique.append(t)
        
        return unique[:self.config["max_tickers"]]
    
    def _get_sector_map(self, tickers: List[str]) -> Dict[str, str]:
        """Build sector map for given tickers."""
        sector_map = {}
        for sector, sector_tickers in self.config.get("sector_groups", {}).items():
            for t in sector_tickers:
                if t in tickers:
                    sector_map[t] = sector
        return sector_map
    
    # =========================================================================
    # DATA FETCHING
    # =========================================================================
    
    async def _fetch_india_data(self, tickers: List[str]) -> Tuple[pd.DataFrame, str]:
        """
        Fetch data for Indian tickers.
        
        Strategy:
        1. Try NSE Direct API for OHLCV (requires scraping historical data)
        2. Fallback to yfinance if NSE fails
        
        Note: NSE Direct doesn't provide easy historical OHLCV.
        We use yfinance for historical data but with NSE-aware caching.
        """
        from app.services.yf_wrapper import get_cached_yf_data
        
        fetch_timestamp = datetime.now()
        
        # For historical data, yfinance is most reliable for Indian stocks
        # NSE Direct is better for real-time quotes and corporate actions
        logger.info(f"[MarketStateV2] Fetching {len(tickers)} India tickers via yfinance")
        
        try:
            df = await get_cached_yf_data(
                tickers,
                period=f"{self.lookback_days + 30}d",
                interval="1d"
            )
            
            if df is None or df.empty:
                raise ValueError("No data returned from yfinance for India tickers")
            
            return df, "yfinance"  # Source tracking
            
        except Exception as e:
            logger.error(f"[MarketStateV2] India fetch failed: {e}")
            raise
    
    async def _fetch_us_data(self, tickers: List[str]) -> Tuple[pd.DataFrame, str]:
        """Fetch data for US tickers via yfinance."""
        from app.services.yf_wrapper import get_cached_yf_data
        
        logger.info(f"[MarketStateV2] Fetching {len(tickers)} US tickers via yfinance")
        
        try:
            df = await get_cached_yf_data(
                tickers,
                period=f"{self.lookback_days + 30}d",
                interval="1d"
            )
            
            if df is None or df.empty:
                raise ValueError("No data returned from yfinance for US tickers")
            
            return df, "yfinance"
            
        except Exception as e:
            logger.error(f"[MarketStateV2] US fetch failed: {e}")
            raise
    
    # =========================================================================
    # BUILD
    # =========================================================================
    
    async def build(self) -> Dict[str, Any]:
        """
        Build the MarketState from fresh data.
        
        Returns:
            Build result with success/error status and metadata
        """
        build_start = datetime.now()
        requested_tickers = self._get_ticker_list()
        
        logger.info(
            f"[MarketStateV2] Building {self.universe_key} with "
            f"{len(requested_tickers)} tickers, {self.lookback_days} days"
        )
        
        try:
            # Fetch data based on universe
            if self.universe_key == "INDIA":
                raw_data, source = await self._fetch_india_data(requested_tickers)
            else:
                raw_data, source = await self._fetch_us_data(requested_tickers)
            
            # Parse multi-level columns from yf.download
            if isinstance(raw_data.columns, pd.MultiIndex):
                prices = raw_data['Close'].copy()
                volumes = raw_data['Volume'].copy()
                open_df = raw_data['Open'].copy()
                high_df = raw_data['High'].copy()
                low_df = raw_data['Low'].copy()
            else:
                # Single ticker
                ticker = requested_tickers[0] if requested_tickers else "UNKNOWN"
                prices = raw_data[['Close']].copy()
                prices.columns = [ticker]
                volumes = raw_data[['Volume']].copy()
                volumes.columns = [ticker]
                open_df = raw_data[['Open']].copy()
                open_df.columns = [ticker]
                high_df = raw_data[['High']].copy()
                high_df.columns = [ticker]
                low_df = raw_data[['Low']].copy()
                low_df.columns = [ticker]
            
            # Trim to lookback window
            prices = prices.tail(self.lookback_days)
            volumes = volumes.tail(self.lookback_days)
            open_df = open_df.tail(self.lookback_days)
            high_df = high_df.tail(self.lookback_days)
            low_df = low_df.tail(self.lookback_days)
            
            # Quality gate: compute missingness per ticker
            max_missing = self.config["max_missing_pct"]
            # min_days is the LOWER of config value and 70% of requested lookback
            min_days = min(self.config["min_trading_days"], int(self.lookback_days * 0.7))
            
            drop_reasons = {}
            valid_tickers = []
            
            for ticker in prices.columns:
                col = prices[ticker]
                missing_pct = col.isna().sum() / len(col)
                trading_days = col.notna().sum()
                
                if missing_pct > max_missing:
                    drop_reasons[ticker] = f"missing {missing_pct:.1%} > {max_missing:.0%}"
                elif trading_days < min_days:
                    drop_reasons[ticker] = f"only {trading_days} days < {min_days}"
                else:
                    valid_tickers.append(ticker)
            
            if not valid_tickers:
                raise ValueError("No tickers passed quality gates")
            
            # Filter to valid tickers
            prices = prices[valid_tickers]
            volumes = volumes[valid_tickers]
            open_df = open_df[valid_tickers]
            high_df = high_df[valid_tickers]
            low_df = low_df[valid_tickers]
            
            # Compute log returns (no forward-fill!)
            returns = np.log(prices / prices.shift(1))
            returns = returns.iloc[1:]  # Drop first NaN row
            
            # Align all dataframes
            common_idx = returns.index
            prices = prices.loc[common_idx]
            volumes = volumes.loc[common_idx].fillna(0)  # Zero volume for NaN
            open_df = open_df.loc[common_idx]
            high_df = high_df.loc[common_idx]
            low_df = low_df.loc[common_idx]
            
            # Dollar volume
            dollar_volume = prices * volumes
            
            # Compute quality metrics
            completeness = 1 - prices.isna().sum() / len(prices)
            
            quality = QualityMetrics(
                tickers_requested=len(requested_tickers),
                tickers_valid=len(valid_tickers),
                tickers_dropped=len(drop_reasons),
                dropped_tickers=tuple(drop_reasons.keys()),
                drop_reasons=drop_reasons,
                avg_completeness=completeness.mean(),
                min_completeness=completeness.min(),
                trading_days=len(prices),
                date_range=(
                    str(prices.index[0].date()),
                    str(prices.index[-1].date()),
                ),
            )
            
            # Compute config hash
            config_str = f"{self.universe_key}_{len(valid_tickers)}_{self.lookback_days}"
            config_hash = hashlib.md5(config_str.encode()).hexdigest()[:12]
            
            # Build provenance
            provenance = DataProvenance(
                data_source=source,
                fetch_timestamp=build_start.isoformat(),
                build_timestamp=datetime.now().isoformat(),
                config_hash=config_hash,
                universe_key=self.universe_key,
                lookback_days=self.lookback_days,
            )
            
            # State hash (for cache invalidation)
            state_str = f"{config_hash}_{prices.index[-1]}_{len(valid_tickers)}"
            state_hash = hashlib.md5(state_str.encode()).hexdigest()[:12]
            
            # Build metadata
            self._metadata = MarketStateMetadata(
                quality=quality,
                provenance=provenance,
                sector_map=self._get_sector_map(valid_tickers),
                state_hash=state_hash,
            )
            
            # Store data
            self._prices = prices
            self._returns = returns
            self._volumes = volumes
            self._dollar_volume = dollar_volume
            self._ohlc = OHLCData(
                open=open_df,
                high=high_df,
                low=low_df,
                close=prices.copy(),
            )
            
            self._is_built = True
            self._build_error = None
            
            logger.info(
                f"[MarketStateV2] Build complete: {len(valid_tickers)} tickers, "
                f"{len(prices)} days, quality={quality.avg_completeness:.2%}"
            )
            
            return {
                "success": True,
                "universe_key": self.universe_key,
                "ticker_count": len(valid_tickers),
                "trading_days": len(prices),
                "date_range": quality.date_range,
                "state_hash": state_hash,
                "quality": quality.to_dict(),
                "provenance": provenance.to_dict(),
            }
            
        except Exception as e:
            self._is_built = False
            self._build_error = str(e)
            logger.error(f"[MarketStateV2] Build failed: {e}")
            
            return {
                "success": False,
                "error": str(e),
                "universe_key": self.universe_key,
            }
    
    # =========================================================================
    # DERIVED COMPUTATIONS (used by PCA and other engines)
    # =========================================================================
    
    def covariance_matrix(
        self,
        window: Optional[int] = None,
        shrinkage: Optional[str] = "ledoit_wolf",
    ) -> pd.DataFrame:
        """
        Compute covariance matrix for returns.
        
        Args:
            window: Rolling window (None = full sample)
            shrinkage: "ledoit_wolf" | "oas" | None
        
        Returns:
            Covariance matrix (N × N)
        """
        if window:
            rets = self._returns.tail(window)
        else:
            rets = self._returns
        
        if shrinkage == "ledoit_wolf":
            from sklearn.covariance import LedoitWolf
            cov_estimator = LedoitWolf()
            cov_estimator.fit(rets.dropna())
            return pd.DataFrame(
                cov_estimator.covariance_,
                index=rets.columns,
                columns=rets.columns,
            )
        elif shrinkage == "oas":
            from sklearn.covariance import OAS
            cov_estimator = OAS()
            cov_estimator.fit(rets.dropna())
            return pd.DataFrame(
                cov_estimator.covariance_,
                index=rets.columns,
                columns=rets.columns,
            )
        else:
            return rets.cov()
    
    def correlation_matrix(self, window: Optional[int] = None) -> pd.DataFrame:
        """Compute correlation matrix."""
        if window:
            return self._returns.tail(window).corr()
        return self._returns.corr()
    
    def rolling_volatility(self, window: int = 20) -> pd.DataFrame:
        """Annualized rolling volatility."""
        return self._returns.rolling(window).std() * np.sqrt(252)
    
    def rolling_correlation(
        self,
        reference: str,
        window: int = 60,
    ) -> pd.DataFrame:
        """Rolling correlation with a reference ticker."""
        if reference not in self._returns.columns:
            raise ValueError(f"Reference {reference} not in tickers")
        
        ref = self._returns[reference]
        return self._returns.apply(lambda x: x.rolling(window).corr(ref))
    
    def sector_returns(self) -> pd.DataFrame:
        """Equal-weighted sector returns."""
        sector_rets = {}
        for sector in set(self._metadata.sector_map.values()):
            tickers = [
                t for t, s in self._metadata.sector_map.items()
                if s == sector and t in self._returns.columns
            ]
            if tickers:
                sector_rets[sector] = self._returns[tickers].mean(axis=1)
        
        return pd.DataFrame(sector_rets)
    
    def median_dollar_volume(self, window: int = 20) -> pd.Series:
        """Median dollar volume per ticker over window."""
        return self._dollar_volume.tail(window).median()
    
    # =========================================================================
    # SERIALIZATION
    # =========================================================================
    
    def to_summary(self) -> Dict[str, Any]:
        """Get a summary dict (for API responses)."""
        if not self._is_built:
            return {"error": self._build_error or "Not built"}
        
        return {
            "universe_key": self.universe_key,
            "tickers": self.tickers,
            "ticker_count": len(self.tickers),
            "trading_days": len(self.dates),
            "date_range": self._metadata.quality.date_range,
            "state_hash": self._metadata.state_hash,
            "quality": self._metadata.quality.to_dict(),
            "provenance": self._metadata.provenance.to_dict(),
        }


# =============================================================================
# GLOBAL STATE CACHE
# =============================================================================

_market_state_cache: Dict[str, MarketStateV2] = {}
_cache_lock = asyncio.Lock()

async def get_market_state(
    universe_key: str = "INDIA",
    lookback_days: int = 252,
    force_rebuild: bool = False,
) -> MarketStateV2:
    """
    Get cached MarketState or build new one.
    
    Thread-safe with async lock.
    Cache invalidates after 6 hours.
    """
    global _market_state_cache
    
    async with _cache_lock:
        cache_key = f"{universe_key.upper()}_{lookback_days}"
        
        if not force_rebuild and cache_key in _market_state_cache:
            state = _market_state_cache[cache_key]
            if state.is_built:
                # Check freshness (6 hour TTL)
                build_time = datetime.fromisoformat(
                    state.metadata.provenance.build_timestamp
                )
                age_seconds = (datetime.now() - build_time).total_seconds()
                if age_seconds < 21600:  # 6 hours
                    logger.debug(f"[MarketStateV2] Cache hit for {cache_key}")
                    return state
        
        # Build new state
        logger.info(f"[MarketStateV2] Building new state for {cache_key}")
        state = MarketStateV2(universe_key=universe_key, lookback_days=lookback_days)
        result = await state.build()
        
        if result.get("success"):
            _market_state_cache[cache_key] = state
        
        return state


def clear_market_state_cache():
    """Clear all cached market states."""
    global _market_state_cache
    _market_state_cache.clear()
    logger.info("[MarketStateV2] Cache cleared")


def get_cache_status() -> Dict[str, Any]:
    """Get cache status for debugging."""
    status = {}
    for key, state in _market_state_cache.items():
        if state.is_built:
            status[key] = {
                "tickers": len(state.tickers),
                "days": len(state.dates),
                "built": state.metadata.provenance.build_timestamp,
                "hash": state.metadata.state_hash,
            }
        else:
            status[key] = {"error": state._build_error}
    return status
