"""
PCA God Mode Omega - Complete Feature Implementation
====================================================

Elite institutional-grade Principal Component Analysis system for:
- Portfolio structure discovery
- Risk decomposition  
- Factor intelligence
- Regime shift detection
- Systemic shock simulation

This module implements the full God Mode specification with 6 tabs:
1. Structure Overview
2. Factors & Meaning
3. Factor Behavior & Stability
4. Structure Map & Redundancy
5. Systemic Risk & Shocks
6. Governance & Export
"""

import numpy as np
import pandas as pd
from typing import Dict, List, Optional, Tuple, Any, Literal
from dataclasses import dataclass, field, asdict
from datetime import datetime, timedelta
from enum import Enum
import hashlib
import logging
import json
from functools import lru_cache
from scipy import stats
from scipy.sparse.csgraph import connected_components
from scipy.sparse import csr_matrix

from app.services.robust_data_fetcher import get_batch_data, get_price_data
from app.services import universe
from app.services.data_engine import engine
import threading
from datetime import datetime as dt

logger = logging.getLogger(__name__)

# Module-level cache for returns data to speed up repeated requests
_returns_cache: Dict[str, Tuple[pd.DataFrame, dt]] = {}
_returns_cache_lock = threading.Lock()
_RETURNS_CACHE_TTL = 300  # 5 minutes


# =============================================================================
# UNIVERSE DEFINITIONS
# =============================================================================

class UniverseRegion(str, Enum):
    """Supported market regions"""
    INDIA = "india"
    US = "us"
    EUROPE = "europe"
    JAPAN = "japan"
    GLOBAL = "global"
    CUSTOM = "custom"


# Global Sector Registry for Granular Classification
SECTOR_REGISTRY = {
    # India - Financials
    "HDFCBANK.NS": "Banking", "ICICIBANK.NS": "Banking", "SBIN.NS": "Banking", "KOTAKBANK.NS": "Banking", "AXISBANK.NS": "Banking",
    "BAJFINANCE.NS": "NBFC", "BAJAJFINSV.NS": "NBFC", "CHOLAFIN.NS": "NBFC", "SHRIRAMFIN.NS": "NBFC",
    "HDFCLIFE.NS": "Insurance", "SBILIFE.NS": "Insurance", "ICICIPRULI.NS": "Insurance",
    # India - IT
    "TCS.NS": "IT Services", "INFY.NS": "IT Services", "HCLTECH.NS": "IT Services", "WIPRO.NS": "IT Services", "TECHM.NS": "IT Services",
    "LTIM.NS": "IT Services", "LTTS.NS": "IT Services",
    # India - Energy & Oil
    "RELIANCE.NS": "Energy", "ONGC.NS": "Oil & Gas", "BPCL.NS": "Oil & Gas", "IOC.NS": "Oil & Gas", "GAIL.NS": "Oil & Gas",
    "NTPC.NS": "Power", "POWERGRID.NS": "Power", "ADANIGREEN.NS": "Renewables", "ADANIPOWER.NS": "Power", "TATAPOWER.NS": "Power",
    # India - Consumer
    "HINDUNILVR.NS": "FMCG", "ITC.NS": "FMCG", "NESTLEIND.NS": "FMCG", "BRITANNIA.NS": "FMCG", "TATACONSUM.NS": "FMCG",
    "TITAN.NS": "Retail", "ASIANPAINT.NS": "Paints", "PIDILITIND.NS": "Chemicals",
    # India - Auto
    "MARUTI.NS": "Auto", "TATAMOTORS.NS": "Auto", "M&M.NS": "Auto", "BAJAJ-AUTO.NS": "Auto", "EICHERMOT.NS": "Auto", "HEROMOTOCO.NS": "Auto",
    # India - Pharma
    "SUNPHARMA.NS": "Pharma", "DRREDDY.NS": "Pharma", "CIPLA.NS": "Pharma", "DIVISLAB.NS": "Pharma", "APOLLOHOSP.NS": "Healthcare",
    # US - Technology
    "AAPL": "Technology", "MSFT": "Technology", "GOOGL": "Internet", "META": "Internet", "NVDA": "Semiconductors", "AMD": "Semiconductors", "AVGO": "Semiconductors",
    # US - Financials
    "JPM": "Banking", "BAC": "Banking", "GS": "Banking", "MS": "Banking", "V": "Payments", "MA": "Payments",
}

# Predefined universes by region
UNIVERSE_PRESETS = {
    "INDIA_NIFTY50": {
        "name": "NIFTY 50",
        "region": UniverseRegion.INDIA,
        "tickers": [
            "RELIANCE.NS", "TCS.NS", "HDFCBANK.NS", "INFY.NS", "ICICIBANK.NS",
            "HINDUNILVR.NS", "ITC.NS", "SBIN.NS", "BHARTIARTL.NS", "KOTAKBANK.NS",
            "LT.NS", "AXISBANK.NS", "ASIANPAINT.NS", "MARUTI.NS", "BAJFINANCE.NS",
            "HCLTECH.NS", "SUNPHARMA.NS", "TITAN.NS", "ULTRACEMCO.NS", "WIPRO.NS",
            "NESTLEIND.NS", "TATAMOTORS.NS", "POWERGRID.NS", "NTPC.NS", "BAJAJFINSV.NS",
            "ONGC.NS", "M&M.NS", "JSWSTEEL.NS", "TATASTEEL.NS", "COALINDIA.NS",
            "HINDALCO.NS", "GRASIM.NS", "TECHM.NS", "DRREDDY.NS", "INDUSINDBK.NS",
            "CIPLA.NS", "HDFCLIFE.NS", "BPCL.NS", "SBILIFE.NS", "DIVISLAB.NS",
            "APOLLOHOSP.NS", "BRITANNIA.NS", "TATACONSUM.NS", "EICHERMOT.NS",
            "HEROMOTOCO.NS", "UPL.NS", "ADANIPORTS.NS", "BAJAJ-AUTO.NS"
        ],
        "sector_map": {
            "IT": ["TCS.NS", "INFY.NS", "HCLTECH.NS", "WIPRO.NS", "TECHM.NS"],
            "Financials": ["HDFCBANK.NS", "ICICIBANK.NS", "SBIN.NS", "KOTAKBANK.NS", "AXISBANK.NS", "BAJFINANCE.NS", "BAJAJFINSV.NS", "HDFCLIFE.NS", "SBILIFE.NS", "INDUSINDBK.NS"],
            "Energy": ["RELIANCE.NS", "ONGC.NS", "BPCL.NS", "NTPC.NS", "POWERGRID.NS", "COALINDIA.NS"],
            "Consumer": ["HINDUNILVR.NS", "ITC.NS", "NESTLEIND.NS", "BRITANNIA.NS", "TATACONSUM.NS", "TITAN.NS", "ASIANPAINT.NS"],
            "Auto": ["MARUTI.NS", "TATAMOTORS.NS", "M&M.NS", "BAJAJ-AUTO.NS", "EICHERMOT.NS", "HEROMOTOCO.NS"],
            "Pharma": ["SUNPHARMA.NS", "DRREDDY.NS", "CIPLA.NS", "DIVISLAB.NS", "APOLLOHOSP.NS"],
            "Metals": ["TATASTEEL.NS", "JSWSTEEL.NS", "HINDALCO.NS"],
            "Infra": ["LT.NS", "ULTRACEMCO.NS", "GRASIM.NS", "ADANIPORTS.NS", "BHARTIARTL.NS"],
            "Other": ["UPL.NS"]
        }
    },
    "US_SP500_TOP50": {
        "name": "S&P 500 Top 50",
        "region": UniverseRegion.US,
        "tickers": [
            "AAPL", "MSFT", "GOOGL", "AMZN", "NVDA", "META", "TSLA", "BRK-B",
            "UNH", "XOM", "JNJ", "JPM", "V", "PG", "MA", "HD", "CVX", "MRK",
            "ABBV", "LLY", "PEP", "KO", "COST", "AVGO", "MCD", "WMT", "CSCO",
            "CRM", "TMO", "ACN", "ABT", "DHR", "VZ", "CMCSA", "NKE", "INTC",
            "TXN", "AMD", "ADBE", "PM", "NEE", "QCOM", "UPS", "HON", "LOW",
            "BA", "CAT", "GE", "IBM", "DIS"
        ],
        "sector_map": {
            "Technology": ["AAPL", "MSFT", "GOOGL", "NVDA", "META", "AVGO", "CSCO", "CRM", "INTC", "TXN", "AMD", "ADBE", "QCOM", "IBM", "ACN"],
            "Consumer Discretionary": ["AMZN", "TSLA", "HD", "MCD", "NKE", "LOW", "DIS"],
            "Financials": ["BRK-B", "JPM", "V", "MA"],
            "Healthcare": ["UNH", "JNJ", "MRK", "ABBV", "LLY", "TMO", "ABT", "DHR"],
            "Consumer Staples": ["PG", "PEP", "KO", "COST", "WMT", "PM"],
            "Energy": ["XOM", "CVX"],
            "Industrials": ["UPS", "HON", "BA", "CAT", "GE"],
            "Communication": ["VZ", "CMCSA"],
            "Utilities": ["NEE"]
        }
    },
    "GLOBAL_MACRO": {
        "name": "Global Macro",
        "region": UniverseRegion.GLOBAL,
        "tickers": [
            "SPY", "QQQ", "IWM", "EFA", "EEM", "VGK", "EWJ", "INDA",
            "TLT", "IEF", "HYG", "LQD", "GLD", "SLV", "USO", "UNG",
            "DBA", "VNQ", "FXE", "FXY", "FXB", "UUP"
        ],
        "sector_map": {
            "US Equity": ["SPY", "QQQ", "IWM"],
            "Intl Equity": ["EFA", "EEM", "VGK", "EWJ", "INDA"],
            "Fixed Income": ["TLT", "IEF", "HYG", "LQD"],
            "Commodities": ["GLD", "SLV", "USO", "UNG", "DBA"],
            "Real Estate": ["VNQ"],
            "FX": ["FXE", "FXY", "FXB", "UUP"]
        }
    }
}


# =============================================================================
# DATA CLASSES
# =============================================================================

@dataclass
class UniverseQuality:
    """Universe data quality assessment"""
    coverage_pct: float
    median_history_days: int
    data_completeness_pct: float
    quality_badge: Literal["LOW", "MEDIUM", "HIGH"]
    dropped_assets: List[str]
    warnings: List[str]


@dataclass
class PCAConfig:
    """Configuration for PCA analysis"""
    universe_key: str
    custom_tickers: Optional[List[str]] = None
    lookback_days: int = 252
    min_history_days: int = 100  # Lowered for better international market support
    max_missing_pct: float = 0.10  # Increased tolerance for international stocks
    return_type: Literal["simple", "log"] = "log"
    normalization: Literal["none", "zscore", "minmax"] = "zscore"
    matrix_type: Literal["correlation", "covariance"] = "correlation"
    winsorize_pct: float = 0.01
    rolling_enabled: bool = False  # Disabled by default for faster initial load
    rolling_window: int = 126  # Reduced from 252 for faster rolling computation
    rolling_step: int = 42  # Increased step for faster rolling computation
    

@dataclass
class StructureMetrics:
    """Tab 1: Structure Overview metrics"""
    pc1_variance_share: float
    top3_pcs_variance: float
    top5_pcs_variance: float
    enb: float  # Effective Number of Bets
    concentration_index: float
    fragility_score: float
    noise_floor: float
    optimal_pc_count: int
    classification: str
    explained_variance: List[float]
    cumulative_variance: List[float]
    enb_curve: List[float]
    warnings: List[str]


@dataclass
class FactorMeaning:
    """Tab 2: Factor meaning for a single PC"""
    pc_index: int
    dominant_sector: str
    sector_share: float
    sign_consistency: float
    purity_score: float
    label: Literal["PURE", "MIXED", "NOISE"]
    interpretation: str
    top_loaders: List[Dict[str, Any]]


@dataclass  
class StabilityMetrics:
    """Tab 3: Stability metrics for a single PC"""
    pc_index: int
    loading_stability: float
    variance_stability: float
    return_consistency: float
    trust_score: float
    classification: Literal["HIGH", "MEDIUM", "LOW"]
    mean_return: float
    volatility: float
    sharpe: float
    max_drawdown: float
    market_correlation: float


@dataclass
class DiversifierScore:
    """Tab 4: Diversification score for an asset"""
    ticker: str
    sector: str
    explained_pct: float
    residual_pct: float
    tail_risk: float
    diversifier_score: float
    classification: Literal["STRONG", "MODERATE", "CORE"]


@dataclass
class StructuralBreak:
    """Tab 5: Detected structural break"""
    date: str
    break_type: str
    impact_score: float
    pc1_delta: float
    enb_delta: float
    regime_label: str


# =============================================================================
# PCA GOD MODE ENGINE
# =============================================================================

class PCAGodModeEngine:
    """
    Complete PCA God Mode implementation.
    
    Provides institutional-grade PCA analysis with:
    - Multi-region universe support
    - Quality filtering and validation
    - Structure discovery
    - Factor interpretation
    - Stability analysis
    - Diversification scoring
    - Shock simulation
    - Structural break detection
    """
    
    def __init__(self, config: PCAConfig):
        self.config = config
        self._returns: Optional[pd.DataFrame] = None
        self._eigenvalues: Optional[np.ndarray] = None
        self._eigenvectors: Optional[np.ndarray] = None
        self._tickers: List[str] = []
        self._sector_map: Dict[str, str] = {}
        self._quality: Optional[UniverseQuality] = None
        self._computed: bool = False
        self._rolling_states: List[Dict] = []
        
    def _get_universe_tickers(self) -> Tuple[List[str], Dict[str, str]]:
        """Get tickers and sector map from universe config"""
        # Build a sector map for all tickers using our registries
        def build_sector_map(ticker_list):
            sector_map = {}
            for ticker in ticker_list:
                # 1. Check our granular registry first
                if ticker in SECTOR_REGISTRY:
                    sector_map[ticker] = SECTOR_REGISTRY[ticker]
                else:
                    # 2. Check universe groups as fallback
                    group = universe.get_group(ticker)
                    if group:
                        sector_map[ticker] = group.replace('_', ' ').title()
                    else:
                        sector_map[ticker] = "Other"
            return sector_map

        if self.config.custom_tickers:
            return self.config.custom_tickers, build_sector_map(self.config.custom_tickers)
            
        preset = UNIVERSE_PRESETS.get(self.config.universe_key)
        if preset:
            # Prefer registry over fixed preset map if available
            return preset["tickers"], build_sector_map(preset["tickers"])
            
        # Fallback to existing universe module
        group_tickers = universe.get_universe_list(self.config.universe_key.lower())
        if group_tickers:
            return group_tickers, build_sector_map(group_tickers)
            
        # Default to global macro
        return UNIVERSE_PRESETS["GLOBAL_MACRO"]["tickers"], {}
    

    def _fetch_returns(self, tickers: List[str]) -> pd.DataFrame:
        """Fetch returns data with quality filtering using DataEngine"""
        logger.info(f"[PCA GodMode] Fetching {len(tickers)} tickers using DataEngine")
        
        # DataEngine handles caching and high-performance parquet loading
        returns = engine.get_returns_matrix(
            tickers=tickers,
            lookback_days=self.config.lookback_days,
            method=self.config.return_type
        )
        
        if returns.empty:
            logger.warning(f"[PCA GodMode] No returns data available for universe")
            
        return returns
    
    def _filter_and_validate(self, returns: pd.DataFrame) -> Tuple[pd.DataFrame, UniverseQuality]:
        """Apply quality filters and return cleaned data"""
        original_cols = returns.columns.tolist()
        warnings = []
        dropped = []
        
        # 1. Check minimum history (Dynamic based on window length)
        history_per_col = returns.notna().sum()
        # Ensure we don't require more history than the total window size
        # Default to 70% of requested window or min_history_days, whichever is smaller
        n_obs = len(returns)
        min_required = min(self.config.min_history_days, int(n_obs * 0.7))
        valid_history = history_per_col >= min_required
        
        for col in returns.columns:
            if not valid_history[col]:
                dropped.append(col)
        
        returns = returns.loc[:, valid_history]
        
        # 2. Check missing data tolerance
        missing_pct = returns.isna().sum() / len(returns)
        valid_missing = missing_pct <= self.config.max_missing_pct
        
        for col in returns.columns:
            if not valid_missing[col] and col not in dropped:
                dropped.append(col)
                
        returns = returns.loc[:, valid_missing]
        
        # 3. Forward fill small gaps (max 5 days)
        returns = returns.ffill(limit=5)
        
        # 4. Drop any remaining columns with NaN
        returns = returns.dropna(axis=1)
        
        # 5. Winsorization
        if self.config.winsorize_pct > 0:
            lower = returns.quantile(self.config.winsorize_pct)
            upper = returns.quantile(1 - self.config.winsorize_pct)
            returns = returns.clip(lower=lower, upper=upper, axis=1)
        
        # 6. Normalization
        if self.config.normalization == "zscore":
            returns = (returns - returns.mean()) / returns.std()
        elif self.config.normalization == "minmax":
            returns = (returns - returns.min()) / (returns.max() - returns.min())
        
        # Compute quality metrics
        coverage = len(returns.columns) / max(len(original_cols), 1)
        median_history = int(history_per_col[returns.columns].median()) if len(returns.columns) > 0 else 0
        completeness = 1 - (returns.isna().sum().sum() / (returns.shape[0] * returns.shape[1])) if returns.size > 0 else 0
        
        # Quality badge
        if coverage >= 0.8 and median_history >= 252 and completeness >= 0.95:
            badge = "HIGH"
        elif coverage >= 0.6 and median_history >= 126:
            badge = "MEDIUM"
        else:
            badge = "LOW"
            
        # Warnings
        N, T = returns.shape[1], len(returns)
        if T < N:
            warnings.append(f"Observations ({T}) < assets ({N}) — PCA not well-defined")
        elif T < 3 * N:
            warnings.append(f"Insufficient observations: T/N = {T/N:.1f} < 3 — overfitting risk")
        elif T < 5 * N:
            warnings.append(f"Low sample ratio: T/N = {T/N:.1f} — results may be unstable")
            
        quality = UniverseQuality(
            coverage_pct=round(coverage * 100, 1),
            median_history_days=median_history,
            data_completeness_pct=round(completeness * 100, 1),
            quality_badge=badge,
            dropped_assets=dropped,
            warnings=warnings
        )
        
        return returns, quality
    
    def _compute_pca(self, returns: pd.DataFrame) -> Tuple[np.ndarray, np.ndarray]:
        """Compute PCA decomposition"""
        # Build matrix
        if self.config.matrix_type == "correlation":
            matrix = returns.corr().values
        else:
            matrix = returns.cov().values
        
        # Handle NaN/Inf
        matrix = np.nan_to_num(matrix, nan=0.0, posinf=0.0, neginf=0.0)
        
        # Eigendecomposition
        try:
            eigenvalues, eigenvectors = np.linalg.eigh(matrix)
        except np.linalg.LinAlgError:
            # Fallback to SVD
            U, S, Vt = np.linalg.svd(matrix)
            eigenvalues = S
            eigenvectors = U
        
        # Sort descending
        idx = np.argsort(eigenvalues)[::-1]
        eigenvalues = eigenvalues[idx]
        eigenvectors = eigenvectors[:, idx]
        
        # Clip negative eigenvalues
        eigenvalues = np.clip(eigenvalues, 0, None)
        
        return eigenvalues, eigenvectors
    
    def compute(self) -> bool:
        """Run full PCA computation"""
        try:
            # Get universe
            tickers, sector_map = self._get_universe_tickers()
            self._sector_map = sector_map
            
            # Fetch data
            returns = self._fetch_returns(tickers)
            if returns.empty:
                logger.error("[PCA GodMode] No returns data available")
                return False
            
            # Filter and validate
            returns, quality = self._filter_and_validate(returns)
            if returns.empty or returns.shape[1] < 3:
                logger.error(f"[PCA GodMode] Insufficient assets after filtering: {returns.shape[1]}")
                return False
            
            self._returns = returns
            self._quality = quality
            self._tickers = returns.columns.tolist()
            
            # Compute PCA
            eigenvalues, eigenvectors = self._compute_pca(returns)
            self._eigenvalues = eigenvalues
            self._eigenvectors = eigenvectors
            
            # Rolling PCA if enabled
            if self.config.rolling_enabled:
                self._compute_rolling_pca()
            
            self._computed = True
            logger.info(f"[PCA GodMode] Computed successfully: {len(self._tickers)} assets, {len(returns)} observations")
            return True
            
        except Exception as e:
            logger.exception(f"[PCA GodMode] Computation failed: {e}")
            return False
    
    def _compute_rolling_pca(self):
        """
        Compute rolling PCA for stability analysis.
        
        OPTIMIZATION: Uses Rank-1 Incremental Covariance Update
        Instead of recomputing covariance from scratch for each window,
        we update the existing covariance matrix by:
        - Adding the new observation's outer product
        - Subtracting the old observation's outer product
        
        Formula: Σ_new = Σ_old + (1/n) * (x_new @ x_new.T - x_old @ x_old.T)
        
        This reduces complexity from O(T * N^2) to O(N^2) per step.
        """
        if self._returns is None:
            return
            
        window = self.config.rolling_window
        step = self.config.rolling_step
        T = len(self._returns)
        N = len(self._tickers)
        
        states = []
        
        # Get raw returns matrix
        returns_matrix = self._returns.values
        
        # Use optimized incremental update only if step=1 and window large enough
        use_incremental = (step == 1 and window >= 60 and N < 100)
        
        if use_incremental:
            # OPTIMIZATION PATH: Incremental Rank-1 Update
            logger.info(f"[PCA GodMode] Using incremental covariance update (N={N}, window={window})")
            
            # Initialize with first window
            initial_chunk = returns_matrix[:window]
            cov_matrix = np.cov(initial_chunk, rowvar=False)
            
            for end in range(window, T, step):
                # Compute eigendecomposition
                eigenvalues, eigenvectors = self._eigdecomp_safe(cov_matrix)
                
                total_var = eigenvalues.sum()
                explained = eigenvalues / total_var if total_var > 0 else eigenvalues
                
                states.append({
                    "date": str(self._returns.index[end - 1].date()) if hasattr(self._returns.index[end - 1], 'date') else str(self._returns.index[end - 1]),
                    "eigenvalues": eigenvalues.tolist(),
                    "explained_variance": explained.tolist(),
                    "pc1_share": float(explained[0]) if len(explained) > 0 else 0,
                    "eigenvectors": eigenvectors,
                })
                
                # Rank-1 Update: roll the window forward by 1
                if end < T:
                    x_old = returns_matrix[end - window]  # Row leaving window
                    x_new = returns_matrix[end]          # Row entering window
                    
                    # Incremental update (rank-1 modification)
                    # Δ = (1/n) * (x_new @ x_new.T - x_old @ x_old.T)
                    outer_new = np.outer(x_new, x_new)
                    outer_old = np.outer(x_old, x_old)
                    cov_matrix = cov_matrix + (outer_new - outer_old) / window
        else:
            # STANDARD PATH: Recompute each window (for large step sizes)
            for end in range(window, T, step):
                start = end - window
                chunk = self._returns.iloc[start:end]
                
                if len(chunk) < window // 2:
                    continue
                
                eigenvalues, eigenvectors = self._compute_pca(chunk)
                
                total_var = eigenvalues.sum()
                explained = eigenvalues / total_var if total_var > 0 else eigenvalues
                
                states.append({
                    "date": str(self._returns.index[end - 1].date()) if hasattr(self._returns.index[end - 1], 'date') else str(self._returns.index[end - 1]),
                    "eigenvalues": eigenvalues.tolist(),
                    "explained_variance": explained.tolist(),
                    "pc1_share": float(explained[0]) if len(explained) > 0 else 0,
                    "eigenvectors": eigenvectors,
                })
        
        self._rolling_states = states
        logger.info(f"[PCA GodMode] Computed {len(states)} rolling states")
    
    def _eigdecomp_safe(self, matrix: np.ndarray) -> Tuple[np.ndarray, np.ndarray]:
        """Safe eigendecomposition with SVD fallback"""
        # Handle NaN/Inf
        matrix = np.nan_to_num(matrix, nan=0.0, posinf=0.0, neginf=0.0)
        
        try:
            eigenvalues, eigenvectors = np.linalg.eigh(matrix)
        except np.linalg.LinAlgError:
            # Fallback to SVD for numerical stability
            U, S, Vt = np.linalg.svd(matrix)
            eigenvalues = S
            eigenvectors = U
        
        # Sort descending
        idx = np.argsort(eigenvalues)[::-1]
        eigenvalues = eigenvalues[idx]
        eigenvectors = eigenvectors[:, idx]
        
        # Clip negative eigenvalues
        eigenvalues = np.clip(eigenvalues, 0, None)
        
        return eigenvalues, eigenvectors
    
    # =========================================================================
    # TAB 1: STRUCTURE OVERVIEW
    # =========================================================================
    
    def get_structure_metrics(self) -> StructureMetrics:
        """Compute Tab 1 structure metrics"""
        if not self._computed:
            raise ValueError("PCA not computed. Call compute() first.")
        
        eigenvalues = self._eigenvalues
        total_var = eigenvalues.sum()
        
        # Explained variance
        explained = eigenvalues / total_var if total_var > 0 else eigenvalues
        cumulative = np.cumsum(explained)
        
        # Key metrics
        pc1_share = float(explained[0]) if len(explained) > 0 else 0
        top3 = float(cumulative[2]) if len(cumulative) > 2 else float(cumulative[-1])
        top5 = float(cumulative[4]) if len(cumulative) > 4 else float(cumulative[-1])
        
        # ENB (Effective Number of Bets)
        enb = 1.0 / np.sum(explained ** 2) if np.sum(explained ** 2) > 0 else len(explained)
        
        # ENB Curve
        enb_curve = []
        for k in range(1, len(explained) + 1):
            partial_explained = explained[:k]
            # Normalize to k PCs
            partial_explained = partial_explained / partial_explained.sum() if partial_explained.sum() > 0 else partial_explained
            enb_k = 1.0 / np.sum(partial_explained ** 2) if np.sum(partial_explained ** 2) > 0 else k
            enb_curve.append(float(enb_k))
        
        # Concentration Index
        ci = pc1_share
        
        # Noise floor (median of bottom half eigenvalues)
        n_half = len(eigenvalues) // 2
        noise_floor = float(np.median(eigenvalues[n_half:]) / total_var) if total_var > 0 else 0
        
        # Optimal PC count (knee detection)
        # Find where marginal explained variance drops below 1.5x noise floor
        optimal_k = len(explained)
        noise_threshold = noise_floor * 1.5
        for i, ev in enumerate(explained):
            if ev < noise_threshold:
                optimal_k = max(1, i)
                break
        
        # Structural Fragility Score (0-100)
        w1, w2, w3 = 0.5, 0.3, 0.2
        fragility = (
            w1 * max(0, ci - 0.2) * 100 +
            w2 * max(0, 1 - enb / 10) * 100 +
            w3 * noise_floor * 100
        )
        fragility = min(100, max(0, fragility))
        
        # Classification
        if ci > 0.5 and enb < 5:
            classification = "HIGHLY CONCENTRATED SYSTEM"
        elif 0.3 < ci <= 0.5 and 5 <= enb <= 10:
            classification = "MODERATELY DIVERSIFIED"
        elif ci <= 0.3 and enb > 10:
            classification = "FRAGMENTED/NOISY"
        else:
            classification = "MIXED STRUCTURE"
        
        # Warnings
        warnings = list(self._quality.warnings) if self._quality else []
        if fragility > 70:
            warnings.append("Extreme structural fragility — systemic shock risk")
        if noise_floor > 0.05:
            warnings.append("High noise — PC interpretation difficult beyond PC3")
        
        return StructureMetrics(
            pc1_variance_share=round(pc1_share * 100, 1),
            top3_pcs_variance=round(top3 * 100, 1),
            top5_pcs_variance=round(top5 * 100, 1),
            enb=round(enb, 2),
            concentration_index=round(ci, 3),
            fragility_score=round(fragility, 0),
            noise_floor=round(noise_floor * 100, 2),
            optimal_pc_count=optimal_k,
            classification=classification,
            explained_variance=[round(float(e) * 100, 2) for e in explained[:10]],
            cumulative_variance=[round(float(c) * 100, 2) for c in cumulative[:10]],
            enb_curve=[round(e, 2) for e in enb_curve[:10]],
            warnings=warnings
        )
    
    # =========================================================================
    # TAB 2: FACTORS & MEANING
    # =========================================================================
    
    def get_factor_meanings(self, num_pcs: int = 10) -> List[FactorMeaning]:
        """Compute Tab 2 factor meanings"""
        if not self._computed:
            raise ValueError("PCA not computed. Call compute() first.")
        
        results = []
        K = min(num_pcs, len(self._eigenvalues))
        
        for k in range(K):
            loadings = self._eigenvectors[:, k]
            abs_loadings = np.abs(loadings)
            
            # Sector dominance
            sector_totals = {}
            for i, ticker in enumerate(self._tickers):
                sector = self._sector_map.get(ticker, "Other")
                sector_totals[sector] = sector_totals.get(sector, 0) + abs_loadings[i]
            
            total_loading = abs_loadings.sum()
            if total_loading > 0:
                sector_shares = {s: v / total_loading for s, v in sector_totals.items()}
            else:
                sector_shares = {}
            
            dominant_sector = max(sector_shares, key=sector_shares.get) if sector_shares else "Mixed"
            sector_share = sector_shares.get(dominant_sector, 0)
            
            # Sign consistency
            positive_pct = np.sum(loadings > 0.01) / len(loadings)
            negative_pct = np.sum(loadings < -0.01) / len(loadings)
            sign_consistency = max(positive_pct, negative_pct)
            
            # Loading concentration (top 5)
            top5_idx = np.argsort(abs_loadings)[-5:]
            loading_concentration = abs_loadings[top5_idx].sum() / total_loading if total_loading > 0 else 0
            
            # Purity score
            w1, w2, w3 = 0.4, 0.3, 0.3
            purity = w1 * sector_share + w2 * loading_concentration + w3 * sign_consistency
            
            # Classification
            if purity > 0.7:
                label = "PURE"
            elif purity > 0.4:
                label = "MIXED"
            else:
                label = "NOISE"
            
            # Interpretation
            if k == 0 and sign_consistency > 0.85:
                interpretation = "Market Beta Factor"
            elif dominant_sector != "Other" and purity > 0.6:
                interpretation = f"{dominant_sector} Sector Factor"
            elif sign_consistency < 0.55 and purity > 0.6:
                interpretation = "Long-Short Rotation Factor"
            elif label == "NOISE":
                interpretation = "Statistical Artifact"
            else:
                interpretation = "Mixed Multi-Factor"
            
            # Top loaders
            sorted_idx = np.argsort(np.abs(loadings))[::-1][:20]
            top_loaders = [
                {
                    "ticker": self._tickers[i],
                    "loading": round(float(loadings[i]), 4),
                    "abs_loading": round(float(abs_loadings[i]), 4),
                    "sector": self._sector_map.get(self._tickers[i], "Other"),
                    "rank": idx + 1
                }
                for idx, i in enumerate(sorted_idx)
            ]
            
            results.append(FactorMeaning(
                pc_index=k + 1,
                dominant_sector=dominant_sector,
                sector_share=round(sector_share * 100, 1),
                sign_consistency=round(sign_consistency * 100, 1),
                purity_score=round(purity, 2),
                label=label,
                interpretation=interpretation,
                top_loaders=top_loaders
            ))
        
        return results
    
    def get_loadings_table(self, pc_index: int = 1) -> List[Dict]:
        """Get full loadings table for a specific PC"""
        if not self._computed or pc_index < 1 or pc_index > len(self._eigenvalues):
            return []
        
        loadings = self._eigenvectors[:, pc_index - 1]
        abs_loadings = np.abs(loadings)
        total = abs_loadings.sum()
        
        result = []
        sorted_idx = np.argsort(abs_loadings)[::-1]
        
        for rank, i in enumerate(sorted_idx):
            contribution = abs_loadings[i] / total if total > 0 else 0
            result.append({
                "rank": rank + 1,
                "ticker": self._tickers[i],
                "sector": self._sector_map.get(self._tickers[i], "Other"),
                "loading": round(float(loadings[i]), 4),
                "abs_loading": round(float(abs_loadings[i]), 4),
                "contribution_pct": round(contribution * 100, 2),
                "sign": "+" if loadings[i] >= 0 else "-"
            })
        
        return result
    
    # =========================================================================
    # TAB 3: FACTOR BEHAVIOR & STABILITY
    # =========================================================================
    
    def get_factor_returns(self, num_pcs: int = 5) -> Dict[str, Any]:
        """Compute factor returns time series with proper normalization"""
        if not self._computed or self._returns is None:
            return {}
        
        K = min(num_pcs, len(self._eigenvalues))
        loadings = self._eigenvectors[:, :K]
        n_assets = len(self._tickers)
        
        returns_matrix = self._returns.values
        
        # NOTE: If normalization is 'zscore' (the default), returns are already standardized!
        # So we just project them onto eigenvectors, no need to re-standardize.
        # The eigenvectors of a correlation matrix are unit length, so the projection
        # gives us factor "z-scores" which we scale back to interpretable returns.
        
        # Get original returns (un-normalized) for realistic return calculation
        # We'll use these to form 'factor portfolios'
        try:
            raw_returns = self._returns.copy()
            # If they were z-scored, we need to undo it or track the originals.
            # But the safer way is to just compute the factor portfolio weights 
            # from the eigenvectors and apply them to the asset returns.
            
            factor_returns_list = []
            for k in range(K):
                v = loadings[:, k]
                # Normalize weights so sum(|w|) = 1.0 (to represent a $1 position)
                # This makes the factor return comparable to a standard portfolio return.
                denom = np.sum(np.abs(v))
                if denom > 0:
                    weights = v / denom
                else:
                    weights = v
                
                # Calculate portfolio return: R_p = sum(w_i * r_i)
                # We use the returns as they were provided (simple or log)
                f_ret = returns_matrix @ weights
                factor_returns_list.append(f_ret)
            
            factor_returns = np.column_stack(factor_returns_list)
        except Exception as e:
            # Assuming 'logger' is defined elsewhere, e.g., at the module level
            # import logging
            # logger = logging.getLogger(__name__)
            # If not, this line will cause an error. For this change, we assume it exists.
            # If logger is not available, you might replace it with print(f"[PCA GodMode] Error in factor return calc: {e}")
            import logging
            logger = logging.getLogger(__name__)
            logger.error(f"[PCA GodMode] Error in factor return calc: {e}")
            # Fallback to simple projection if something goes wrong
            factor_returns = returns_matrix @ loadings / np.sqrt(n_assets or 1)
        
        # Build time series
        dates = [str(d.date()) if hasattr(d, 'date') else str(d) for d in self._returns.index]
        
        result = {
            "dates": dates,
            "factor_returns": {},
            "cumulative_returns": {},
            "statistics": []
        }
        
        for k in range(K):
            fr = factor_returns[:, k]
            
            # Clamp extreme daily returns (safety valve)
            fr = np.clip(fr, -0.10, 0.10)
            fr = np.nan_to_num(fr, nan=0.0, posinf=0.0, neginf=0.0)
            
            # Cumulative returns
            cum_ret = np.cumprod(1 + fr) - 1
            cum_ret = np.clip(cum_ret, -0.95, 3.0)  # Max -95% to +300%
            
            result["factor_returns"][f"PC{k+1}"] = [round(float(r), 6) for r in fr]
            result["cumulative_returns"][f"PC{k+1}"] = [round(float(c), 4) for c in cum_ret]
            
            # Statistics
            mean_ret = np.mean(fr) * 252
            vol = np.std(fr) * np.sqrt(252)
            
            # Clamp to reasonable annualized values
            mean_ret = np.clip(mean_ret, -2.0, 2.0)  # -200% to +200%
            vol = np.clip(vol, 0.01, 2.0)  # 1% to 200%
            
            sharpe = mean_ret / vol if vol > 0 else 0
            sharpe = np.clip(sharpe, -5, 5)
            
            # Drawdown
            cumulative = np.cumprod(1 + fr)
            cumulative = np.clip(cumulative, 0.01, 100)  # Prevent extreme values
            peak = np.maximum.accumulate(cumulative)
            drawdown = (cumulative - peak) / (peak + 1e-10)
            max_dd = np.min(drawdown)
            max_dd = np.clip(max_dd, -1.0, 0.0)  # Max 100% drawdown
            
            # Market correlation
            market_ret = returns_matrix.mean(axis=1)
            try:
                market_corr = np.corrcoef(fr, market_ret)[0, 1] if len(fr) > 1 else 0
                market_corr = np.clip(market_corr, -1.0, 1.0)
                if np.isnan(market_corr):
                    market_corr = 0.0
            except:
                market_corr = 0.0
            
            # Compute skew and kurtosis with bounds
            try:
                skew_val = float(stats.skew(fr))
                kurt_val = float(stats.kurtosis(fr))
                skew_val = np.clip(skew_val, -10, 10)
                kurt_val = np.clip(kurt_val, -10, 100)
            except:
                skew_val, kurt_val = 0.0, 0.0
            
            result["statistics"].append({
                "pc": k + 1,
                "mean_return": round(float(mean_ret * 100), 2),
                "volatility": round(float(vol * 100), 2),
                "sharpe": round(float(sharpe), 2),
                "max_drawdown": round(float(max_dd * 100), 2),
                "market_correlation": round(float(market_corr), 2),
                "skew": round(skew_val, 2),
                "kurtosis": round(kurt_val, 2)
            })
        
        return result
    
    def get_stability_metrics(self, num_pcs: int = 5) -> List[StabilityMetrics]:
        """Compute factor stability metrics from rolling PCA"""
        if not self._computed:
            return []
        
        if not self._rolling_states:
            factor_data = self.get_factor_returns(num_pcs)
            stats_list = factor_data.get("statistics", [])
            factor_rets = factor_data.get("factor_returns", {})
            
            results = []
            for s in stats_list:
                pc_key = f"PC{s['pc']}"
                rets = factor_rets.get(pc_key, [])
                
                # Estimate stability from return properties
                # Higher variance = lower stability
                vol = s.get("volatility", 20) / 100
                loading_stability = max(0.3, 0.9 - vol)  # Higher vol = less stable
                variance_stability = max(0.3, 0.85 - abs(s.get("skew", 0)) * 0.1)
                
                # Return consistency from rolling vol of returns
                if len(rets) > 63:
                    rets_arr = np.array(rets)
                    rolling_vol = [np.std(rets_arr[max(0,i-21):i+1]) for i in range(21, len(rets_arr))]
                    return_consistency = 1 - (np.std(rolling_vol) / (np.mean(rolling_vol) + 1e-10))
                    return_consistency = max(0.3, min(0.95, return_consistency))
                else:
                    return_consistency = 0.6
                
                # Trust score
                trust = 0.4 * loading_stability + 0.3 * variance_stability + 0.3 * return_consistency
                classification = "HIGH" if trust > 0.7 else "MEDIUM" if trust > 0.4 else "LOW"
                
                results.append(StabilityMetrics(
                    pc_index=s["pc"],
                    loading_stability=round(loading_stability, 2),
                    variance_stability=round(variance_stability, 2),
                    return_consistency=round(return_consistency, 2),
                    trust_score=round(trust, 2),
                    classification=classification,
                    mean_return=s["mean_return"],
                    volatility=s["volatility"],
                    sharpe=s["sharpe"],
                    max_drawdown=s["max_drawdown"],
                    market_correlation=s["market_correlation"]
                ))
            
            return results
        
        # Compute from rolling states
        K = min(num_pcs, len(self._eigenvalues))
        results = []
        
        for k in range(K):
            # Loading stability (cosine similarity across windows)
            loading_sims = []
            for i in range(1, len(self._rolling_states)):
                v1 = self._rolling_states[i-1]["eigenvectors"][:, k]
                v2 = self._rolling_states[i]["eigenvectors"][:, k]
                sim = abs(np.dot(v1, v2) / (np.linalg.norm(v1) * np.linalg.norm(v2) + 1e-10))
                loading_sims.append(sim)
            
            loading_stability = np.mean(loading_sims) if loading_sims else 0.8
            
            # Variance stability
            var_shares = [s["explained_variance"][k] for s in self._rolling_states if k < len(s["explained_variance"])]
            variance_stability = 1 - (np.std(var_shares) / np.mean(var_shares)) if var_shares and np.mean(var_shares) > 0 else 0.5
            variance_stability = max(0, min(1, variance_stability))
            
            # Get factor stats
            factor_data = self.get_factor_returns(num_pcs)
            stats_list = factor_data.get("statistics", [])
            pc_stats = next((s for s in stats_list if s["pc"] == k + 1), {})
            
            # Return consistency from rolling volatility
            factor_data_full = self.get_factor_returns(num_pcs)
            factor_rets = factor_data_full.get("factor_returns", {})
            pc_rets = factor_rets.get(f"PC{k+1}", [])
            if len(pc_rets) > 63:
                rets_arr = np.array(pc_rets)
                rolling_vol = [np.std(rets_arr[max(0,i-21):i+1]) for i in range(21, len(rets_arr))]
                return_consistency = 1 - (np.std(rolling_vol) / (np.mean(rolling_vol) + 1e-10))
                return_consistency = max(0.3, min(0.95, return_consistency))
            else:
                return_consistency = 0.6
            
            # Trust score
            w1, w2, w3 = 0.4, 0.3, 0.3
            trust = w1 * loading_stability + w2 * variance_stability + w3 * return_consistency
            
            if trust > 0.7:
                classification = "HIGH"
            elif trust > 0.4:
                classification = "MEDIUM"
            else:
                classification = "LOW"
            
            results.append(StabilityMetrics(
                pc_index=k + 1,
                loading_stability=round(loading_stability, 2),
                variance_stability=round(variance_stability, 2),
                return_consistency=round(return_consistency, 2),
                trust_score=round(trust, 2),
                classification=classification,
                mean_return=pc_stats.get("mean_return", 0),
                volatility=pc_stats.get("volatility", 0),
                sharpe=pc_stats.get("sharpe", 0),
                max_drawdown=pc_stats.get("max_drawdown", 0),
                market_correlation=pc_stats.get("market_correlation", 0)
            ))
        
        return results
    
    def get_loading_drift_heatmap(self, num_pcs: int = 5) -> Dict[str, Any]:
        """
        Compute loading drift heatmap from rolling PCA.
        Shows how each asset's loading on each PC changes over time.
        """
        if not self._computed or not self._rolling_states:
            return {"error": "Rolling PCA required for drift analysis"}
        
        K = min(num_pcs, len(self._eigenvalues))
        N = len(self._tickers)
        T = len(self._rolling_states)
        
        # Build drift matrix: [time x (assets * PCs)]
        dates = [s["date"] for s in self._rolling_states]
        
        # For each PC, compute loading changes
        drift_data = {}
        for k in range(K):
            pc_key = f"PC{k+1}"
            drift_data[pc_key] = {
                "dates": dates,
                "assets": self._tickers[:20],  # Top 20 assets
                "loadings": []
            }
            
            for state in self._rolling_states:
                if state["eigenvectors"] is not None and k < state["eigenvectors"].shape[1]:
                    loadings = state["eigenvectors"][:20, k].tolist()
                    drift_data[pc_key]["loadings"].append([round(l, 4) for l in loadings])
                else:
                    drift_data[pc_key]["loadings"].append([0] * 20)
        
        # Compute sign flip counts
        sign_flips = {}
        for k in range(K):
            pc_key = f"PC{k+1}"
            flips = []
            for i in range(1, len(self._rolling_states)):
                prev = self._rolling_states[i-1]["eigenvectors"]
                curr = self._rolling_states[i]["eigenvectors"]
                if prev is not None and curr is not None and k < prev.shape[1] and k < curr.shape[1]:
                    flip_count = int(np.sum(np.sign(prev[:, k]) != np.sign(curr[:, k])))
                    flips.append(flip_count)
                else:
                    flips.append(0)
            sign_flips[pc_key] = flips
        
        return {
            "drift_data": drift_data,
            "sign_flips": sign_flips,
            "total_windows": T,
            "tickers": self._tickers[:20]
        }
    
    def get_pc_dominance_history(self) -> Dict[str, Any]:
        """Get PC1 dominance (concentration) over time from rolling PCA."""
        if not self._computed or not self._rolling_states:
            return {"error": "Rolling PCA required"}
        
        dates = []
        pc1_shares = []
        enb_values = []
        
        for state in self._rolling_states:
            dates.append(state["date"])
            pc1_shares.append(round(state["pc1_share"] * 100, 2))
            
            # Compute ENB for this window
            explained = np.array(state["explained_variance"])
            enb = 1.0 / np.sum(explained ** 2) if np.sum(explained ** 2) > 0 else len(explained)
            enb_values.append(round(enb, 2))
        
        return {
            "dates": dates,
            "pc1_share": pc1_shares,
            "enb": enb_values,
            "avg_pc1_share": round(np.mean(pc1_shares), 2) if pc1_shares else 0,
            "avg_enb": round(np.mean(enb_values), 2) if enb_values else 0,
            "max_pc1_share": round(max(pc1_shares), 2) if pc1_shares else 0,
            "min_enb": round(min(enb_values), 2) if enb_values else 0
        }
    
    # =========================================================================
    # TAB 4: STRUCTURE MAP & REDUNDANCY
    # =========================================================================
    
    def get_asset_projections(self) -> List[Dict]:
        """Get PC1 vs PC2 projections for all assets"""
        if not self._computed:
            return []
        
        # Get loadings for first 2 PCs
        pc1 = self._eigenvectors[:, 0] if len(self._eigenvalues) > 0 else np.zeros(len(self._tickers))
        pc2 = self._eigenvectors[:, 1] if len(self._eigenvalues) > 1 else np.zeros(len(self._tickers))
        pc3 = self._eigenvectors[:, 2] if len(self._eigenvalues) > 2 else np.zeros(len(self._tickers))
        
        result = []
        for i, ticker in enumerate(self._tickers):
            result.append({
                "ticker": ticker,
                "sector": self._sector_map.get(ticker, "Other"),
                "pc1": round(float(pc1[i]), 4),
                "pc2": round(float(pc2[i]), 4),
                "pc3": round(float(pc3[i]), 4)
            })
        
        return result
    
    def get_diversifier_scores(self, k_components: int = 5) -> List[DiversifierScore]:
        """Compute diversifier scores for all assets"""
        if not self._computed or self._returns is None:
            return []
        
        K = min(k_components, len(self._eigenvalues))
        loadings = self._eigenvectors[:, :K]
        
        # Reconstruct returns
        returns_std = (self._returns - self._returns.mean()) / (self._returns.std() + 1e-10)
        returns_matrix = returns_std.values
        
        projected = returns_matrix @ loadings
        reconstructed = projected @ loadings.T
        residuals = returns_matrix - reconstructed
        
        # First pass: collect all tail risks for normalization
        tail_risks = []
        for i, ticker in enumerate(self._tickers):
            residual_5th = np.percentile(residuals[:, i], 5)
            residual_95th = np.percentile(residuals[:, i], 95)
            tail_risk = abs(residual_5th) + abs(residual_95th)
            tail_risks.append(tail_risk)
        
        max_tail_risk = max(tail_risks) if tail_risks else 1.0
        
        results = []
        for i, ticker in enumerate(self._tickers):
            actual_var = np.var(returns_matrix[:, i])
            residual_var = np.var(residuals[:, i])
            
            explained_pct = 1 - (residual_var / (actual_var + 1e-10))
            residual_pct = 1 - explained_pct
            
            tail_risk = tail_risks[i]
            
            # Diversifier score: higher residual + higher normalized tail risk = better diversifier
            w1, w2, w3 = 0.5, 0.3, 0.2
            normalized_tail = tail_risk / (max_tail_risk + 1e-10)
            score = w1 * residual_pct + w2 * normalized_tail + w3 * residual_pct
            score = min(100, score * 100)
            
            if score > 70:
                classification = "STRONG"
            elif score > 40:
                classification = "MODERATE"
            else:
                classification = "CORE"
            
            results.append(DiversifierScore(
                ticker=ticker,
                sector=self._sector_map.get(ticker, "Other"),
                explained_pct=round(explained_pct * 100, 1),
                residual_pct=round(residual_pct * 100, 1),
                tail_risk=round(tail_risk, 4),
                diversifier_score=round(score, 0),
                classification=classification
            ))
        
        # Sort by score descending
        results.sort(key=lambda x: x.diversifier_score, reverse=True)
        return results
    
    def get_redundant_pairs(self, threshold: float = 0.85) -> List[Dict]:
        """Find redundant asset pairs based on loading similarity"""
        if not self._computed:
            return []
        
        K = min(4, len(self._eigenvalues))
        loadings = self._eigenvectors[:, :K]
        N = len(self._tickers)
        
        pairs = []
        for i in range(N):
            for j in range(i + 1, N):
                v1, v2 = loadings[i], loadings[j]
                sim = np.dot(v1, v2) / (np.linalg.norm(v1) * np.linalg.norm(v2) + 1e-10)
                
                if abs(sim) >= threshold:
                    sector_i = self._sector_map.get(self._tickers[i], "Other")
                    sector_j = self._sector_map.get(self._tickers[j], "Other")
                    
                    pairs.append({
                        "asset_a": self._tickers[i],
                        "asset_b": self._tickers[j],
                        "similarity": round(float(sim), 3),
                        "sector_match": sector_i == sector_j,
                        "sector_a": sector_i,
                        "sector_b": sector_j,
                        "suggestion": "Consider consolidating" if abs(sim) > 0.9 else "Review overlap"
                    })
        
        pairs.sort(key=lambda x: x["similarity"], reverse=True)
        return pairs[:50]  # Top 50 pairs
    
    # =========================================================================
    # TAB 5: SYSTEMIC RISK & SHOCKS
    # =========================================================================
    
    def simulate_shock(self, shock_config: Dict[int, float]) -> Dict[str, Any]:
        """
        Simulate shock to principal components.
        
        Args:
            shock_config: {pc_index: shock_magnitude} e.g., {1: 2.0, 2: -1.0}
        """
        if not self._computed:
            return {"error": "PCA not computed"}
        
        K = len(self._eigenvalues)
        shock_vector = np.zeros(K)
        
        for pc_idx, magnitude in shock_config.items():
            if 1 <= pc_idx <= K:
                shock_vector[pc_idx - 1] = magnitude
        
        # Compute impacts
        loadings = self._eigenvectors
        impacts = loadings @ shock_vector
        
        # Sort by absolute impact
        sorted_idx = np.argsort(np.abs(impacts))[::-1]
        
        asset_impacts = []
        for rank, i in enumerate(sorted_idx):
            asset_impacts.append({
                "rank": rank + 1,
                "ticker": self._tickers[i],
                "sector": self._sector_map.get(self._tickers[i], "Other"),
                "impact": round(float(impacts[i]), 4),
                "impact_pct": round(float(impacts[i]) * 100, 2)
            })
        
        return {
            "shock_config": shock_config,
            "total_market_impact": round(float(np.mean(impacts)), 4),
            "dispersion": round(float(np.std(impacts)), 4),
            "max_positive": asset_impacts[0] if impacts[sorted_idx[0]] > 0 else None,
            "max_negative": [a for a in asset_impacts if a["impact"] < 0][:1],
            "asset_impacts": asset_impacts[:30],
            "impact_distribution": {
                "positive_count": int(np.sum(impacts > 0.01)),
                "negative_count": int(np.sum(impacts < -0.01)),
                "neutral_count": int(np.sum(np.abs(impacts) <= 0.01))
            }
        }
    
    def detect_structural_breaks(self) -> List[StructuralBreak]:
        """Detect structural breaks from rolling PCA"""
        if not self._rolling_states or len(self._rolling_states) < 2:
            return []
        
        breaks = []
        
        for i in range(1, len(self._rolling_states)):
            prev = self._rolling_states[i - 1]
            curr = self._rolling_states[i]
            
            # PC1 dominance change
            pc1_delta = curr["pc1_share"] - prev["pc1_share"]
            
            # Rank change (simplified)
            rank_change = 0
            for k in range(min(5, len(prev["eigenvalues"]), len(curr["eigenvalues"]))):
                if k < len(prev["eigenvalues"]) and k < len(curr["eigenvalues"]):
                    prev_rank = np.argsort(prev["eigenvalues"])[::-1]
                    curr_rank = np.argsort(curr["eigenvalues"])[::-1]
                    if prev_rank[k] != curr_rank[k]:
                        rank_change += 1
            
            # Loading sign flips
            sign_flips = 0
            if prev["eigenvectors"] is not None and curr["eigenvectors"] is not None:
                for k in range(min(3, prev["eigenvectors"].shape[1], curr["eigenvectors"].shape[1])):
                    v1 = prev["eigenvectors"][:, k]
                    v2 = curr["eigenvectors"][:, k]
                    flips = np.sum(np.sign(v1) != np.sign(v2))
                    sign_flips += flips
            
            # Impact score
            impact = (
                0.4 * abs(pc1_delta) * 10 +
                0.3 * (rank_change / 5) +
                0.3 * (sign_flips / (len(self._tickers) * 3))
            )
            
            # Classify
            if abs(pc1_delta) > 0.1 or impact > 0.7:
                break_type = "PC Dominance Collapse" if pc1_delta < -0.1 else "Regime Shift"
                regime_label = "Crisis" if pc1_delta < -0.1 else "Transition"
                
                breaks.append(StructuralBreak(
                    date=curr["date"],
                    break_type=break_type,
                    impact_score=round(min(1.0, impact), 2),
                    pc1_delta=round(pc1_delta * 100, 2),
                    enb_delta=0,  # Would need ENB history
                    regime_label=regime_label
                ))
        
        return breaks
    
    # =========================================================================
    # TAB 6: GOVERNANCE & EXPORT
    # =========================================================================
    
    def get_governance_metadata(self) -> Dict[str, Any]:
        """Get governance and audit metadata"""
        config_str = json.dumps(asdict(self.config), sort_keys=True, default=str)
        config_hash = hashlib.sha256(config_str.encode()).hexdigest()[:16]
        
        universe_str = ",".join(sorted(self._tickers))
        universe_hash = hashlib.md5(universe_str.encode()).hexdigest()[:16]
        
        return {
            "run_id": f"PCA_{datetime.now().strftime('%Y%m%d_%H%M%S')}_{config_hash[:8]}",
            "execution_timestamp": datetime.now().isoformat(),
            "config_hash": config_hash,
            "universe_hash": universe_hash,
            "config": asdict(self.config),
            "quality": asdict(self._quality) if self._quality else None,
            "data_stats": {
                "n_assets": len(self._tickers),
                "n_observations": len(self._returns) if self._returns is not None else 0,
                "date_range": {
                    "start": str(self._returns.index[0].date()) if self._returns is not None and len(self._returns) > 0 else None,
                    "end": str(self._returns.index[-1].date()) if self._returns is not None and len(self._returns) > 0 else None
                }
            }
        }
    
    def export_data(self, formats: List[str] = ["eigenvalues", "loadings", "factor_returns"]) -> Dict[str, Any]:
        """Export PCA data in various formats"""
        exports = {}
        
        if "eigenvalues" in formats:
            total = self._eigenvalues.sum()
            exports["eigenvalues"] = {
                "values": [round(float(e), 6) for e in self._eigenvalues[:20]],
                "explained_variance": [round(float(e/total)*100, 2) for e in self._eigenvalues[:20]],
                "cumulative_variance": [round(float(sum(self._eigenvalues[:i+1])/total)*100, 2) for i in range(min(20, len(self._eigenvalues)))]
            }
        
        if "loadings" in formats:
            K = min(10, len(self._eigenvalues))
            loadings_dict = {}
            for i, ticker in enumerate(self._tickers):
                loadings_dict[ticker] = {
                    f"PC{k+1}": round(float(self._eigenvectors[i, k]), 4)
                    for k in range(K)
                }
            exports["loadings"] = loadings_dict
        
        if "factor_returns" in formats:
            exports["factor_returns"] = self.get_factor_returns(5)
        
        if "stability" in formats:
            exports["stability"] = [asdict(s) for s in self.get_stability_metrics()]
        
        if "diversifiers" in formats:
            exports["diversifiers"] = [asdict(d) for d in self.get_diversifier_scores()]
        
        return exports


# =============================================================================
# CONVENIENCE FUNCTIONS
# =============================================================================

def run_pca_god_mode(
    universe_key: str = "US_SP500_TOP50",
    lookback_days: int = 252,
    rolling_enabled: bool = True,
    custom_tickers: Optional[List[str]] = None
) -> Dict[str, Any]:
    """
    Run full PCA God Mode analysis.
    
    Returns complete analysis results for all 6 tabs.
    """
    config = PCAConfig(
        universe_key=universe_key,
        custom_tickers=custom_tickers,
        lookback_days=lookback_days,
        rolling_enabled=rolling_enabled
    )
    
    engine = PCAGodModeEngine(config)
    
    if not engine.compute():
        return {"error": "PCA computation failed", "details": "Check logs for details"}
    
    return {
        "success": True,
        "metadata": engine.get_governance_metadata(),
        "structure": asdict(engine.get_structure_metrics()),
        "factors": [asdict(f) for f in engine.get_factor_meanings()],
        "stability": [asdict(s) for s in engine.get_stability_metrics()],
        "diversifiers": [asdict(d) for d in engine.get_diversifier_scores()[:20]],
        "redundant_pairs": engine.get_redundant_pairs()[:10],
        "breaks": [asdict(b) for b in engine.detect_structural_breaks()]
    }


def get_available_universes() -> List[Dict]:
    """Get list of available universe presets"""
    result = []
    for key, preset in UNIVERSE_PRESETS.items():
        result.append({
            "key": key,
            "name": preset["name"],
            "region": preset["region"].value,
            "asset_count": len(preset["tickers"]),
            "sectors": list(preset.get("sector_map", {}).keys())
        })
    return result
