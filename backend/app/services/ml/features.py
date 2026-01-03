"""
Labs → ML → Features
====================
Feature Engineering & Validation Engine

Responsibilities:
- Feature engineering (lags, rolling stats, interactions)
- Normalization logic
- Leakage detection
- Feature stability tracking
"""

import pandas as pd
import numpy as np
from scipy import stats
from typing import Dict, List, Any, Optional, Tuple, Literal
from datetime import datetime
import logging
import warnings

logger = logging.getLogger(__name__)

# =============================================================================
# NORMALIZATION METHODS
# =============================================================================

class Normalizer:
    """Feature normalization methods"""
    
    @staticmethod
    def zscore(series: pd.Series, window: int = None) -> pd.Series:
        """Z-score normalization: (x - mean) / std"""
        if window:
            mean = series.rolling(window).mean()
            std = series.rolling(window).std()
        else:
            mean = series.mean()
            std = series.std()
        
        if isinstance(std, pd.Series):
            std = std.replace(0, np.nan)
        elif std == 0:
            return pd.Series(0, index=series.index)
        
        return (series - mean) / std
    
    @staticmethod
    def minmax(series: pd.Series, window: int = None) -> pd.Series:
        """Min-max normalization: (x - min) / (max - min)"""
        if window:
            min_val = series.rolling(window).min()
            max_val = series.rolling(window).max()
        else:
            min_val = series.min()
            max_val = series.max()
        
        range_val = max_val - min_val
        if isinstance(range_val, pd.Series):
            range_val = range_val.replace(0, np.nan)
        elif range_val == 0:
            return pd.Series(0.5, index=series.index)
        
        return (series - min_val) / range_val
    
    @staticmethod
    def rank(series: pd.Series, window: int = None) -> pd.Series:
        """Rank-based normalization (percentile rank)"""
        if window:
            return series.rolling(window).apply(
                lambda x: stats.percentileofscore(x, x.iloc[-1]) / 100,
                raw=False
            )
        else:
            return series.rank(pct=True)
    
    @staticmethod
    def robust_zscore(series: pd.Series, window: int = None) -> pd.Series:
        """Robust z-score using median and MAD"""
        if window:
            median = series.rolling(window).median()
            mad = series.rolling(window).apply(
                lambda x: np.median(np.abs(x - np.median(x))),
                raw=True
            )
        else:
            median = series.median()
            mad = np.median(np.abs(series - median))
        
        if isinstance(mad, pd.Series):
            mad = mad.replace(0, np.nan)
        elif mad == 0:
            return pd.Series(0, index=series.index)
        
        return (series - median) / (1.4826 * mad)
    
    @staticmethod
    def log_transform(series: pd.Series) -> pd.Series:
        """Log transformation for skewed data"""
        # Handle negative values by shifting
        min_val = series.min()
        if min_val <= 0:
            shifted = series - min_val + 1
        else:
            shifted = series
        
        return np.log(shifted)


# =============================================================================
# FEATURE ENGINEERING
# =============================================================================

class FeatureEngineer:
    """
    Feature Engineering & Validation Engine
    
    - Creates ML-ready features from raw data
    - Applies proper lags to prevent look-ahead bias
    - Normalizes features
    - Validates feature quality
    """
    
    def __init__(self):
        self.feature_registry: Dict[str, Dict] = {}
        self.normalizer = Normalizer()
    
    def apply_lag(
        self,
        df: pd.DataFrame,
        columns: List[str] = None,
        lag_periods: List[int] = [1]
    ) -> pd.DataFrame:
        """
        Apply lag to features to prevent look-ahead bias.
        A lag of 1 means using yesterday's value for today's prediction.
        """
        result = df.copy()
        columns = columns or df.columns.tolist()
        
        for col in columns:
            if col not in df.columns:
                continue
            
            for lag in lag_periods:
                lagged_col = f"{col}_lag{lag}"
                result[lagged_col] = df[col].shift(lag)
        
        return result
    
    def create_rolling_features(
        self,
        df: pd.DataFrame,
        column: str,
        windows: List[int] = [5, 10, 20, 60]
    ) -> pd.DataFrame:
        """Create rolling statistics features"""
        result = df.copy()
        series = df[column]
        
        for window in windows:
            # Rolling mean
            result[f"{column}_ma{window}"] = series.rolling(window).mean()
            
            # Rolling std (volatility)
            result[f"{column}_std{window}"] = series.rolling(window).std()
            
            # Rolling min/max
            result[f"{column}_min{window}"] = series.rolling(window).min()
            result[f"{column}_max{window}"] = series.rolling(window).max()
            
            # Distance from rolling mean
            ma = series.rolling(window).mean()
            result[f"{column}_ma{window}_dist"] = (series - ma) / ma.abs().replace(0, np.nan)
            
            # Rolling skewness
            result[f"{column}_skew{window}"] = series.rolling(window).skew()
            
            # Rolling kurtosis
            result[f"{column}_kurt{window}"] = series.rolling(window).kurt()
        
        return result
    
    def create_momentum_features(
        self,
        df: pd.DataFrame,
        price_col: str = 'Close',
        periods: List[int] = [1, 5, 10, 20, 60]
    ) -> pd.DataFrame:
        """Create momentum/return features"""
        result = df.copy()
        prices = df[price_col]
        
        for period in periods:
            # Simple returns
            result[f"return_{period}d"] = prices.pct_change(period)
            
            # Log returns
            result[f"log_return_{period}d"] = np.log(prices / prices.shift(period))
            
            # Rate of change
            result[f"roc_{period}d"] = (prices - prices.shift(period)) / prices.shift(period)
        
        return result
    
    def create_volatility_features(
        self,
        df: pd.DataFrame,
        return_col: str = None,
        price_col: str = 'Close',
        windows: List[int] = [5, 10, 20, 60]
    ) -> pd.DataFrame:
        """Create volatility features"""
        result = df.copy()
        
        if return_col and return_col in df.columns:
            returns = df[return_col]
        else:
            returns = df[price_col].pct_change()
        
        for window in windows:
            # Realized volatility (annualized)
            result[f"realized_vol_{window}d"] = returns.rolling(window).std() * np.sqrt(252)
            
            # EWMA volatility
            result[f"ewma_vol_{window}d"] = returns.ewm(span=window).std() * np.sqrt(252)
            
            # Volatility of volatility
            rv = returns.rolling(window).std()
            result[f"vol_of_vol_{window}d"] = rv.rolling(window).std()
        
        # Parkinson volatility (if High/Low available)
        if 'High' in df.columns and 'Low' in df.columns:
            hl_ratio = np.log(df['High'] / df['Low'])
            for window in windows:
                result[f"parkinson_vol_{window}d"] = np.sqrt(
                    hl_ratio.pow(2).rolling(window).mean() / (4 * np.log(2))
                ) * np.sqrt(252)
        
        return result
    
    def create_interaction_features(
        self,
        df: pd.DataFrame,
        feature_pairs: List[Tuple[str, str]] = None
    ) -> pd.DataFrame:
        """Create interaction features between pairs of features"""
        result = df.copy()
        
        if feature_pairs is None:
            # Auto-generate some common interactions
            numeric_cols = df.select_dtypes(include=[np.number]).columns.tolist()
            feature_pairs = []
            for i, col1 in enumerate(numeric_cols[:10]):  # Limit to avoid explosion
                for col2 in numeric_cols[i+1:10]:
                    feature_pairs.append((col1, col2))
        
        for col1, col2 in feature_pairs:
            if col1 not in df.columns or col2 not in df.columns:
                continue
            
            # Product interaction
            result[f"{col1}_x_{col2}"] = df[col1] * df[col2]
            
            # Ratio interaction (with safety)
            with warnings.catch_warnings():
                warnings.simplefilter("ignore")
                denom = df[col2].replace(0, np.nan)
                result[f"{col1}_div_{col2}"] = df[col1] / denom
        
        return result
    
    def normalize_features(
        self,
        df: pd.DataFrame,
        method: Literal['zscore', 'minmax', 'rank', 'robust', 'log'] = 'zscore',
        columns: List[str] = None,
        window: int = None
    ) -> pd.DataFrame:
        """Normalize features using specified method"""
        result = df.copy()
        columns = columns or df.select_dtypes(include=[np.number]).columns.tolist()
        
        normalize_fn = {
            'zscore': self.normalizer.zscore,
            'minmax': self.normalizer.minmax,
            'rank': self.normalizer.rank,
            'robust': self.normalizer.robust_zscore,
            'log': self.normalizer.log_transform
        }.get(method, self.normalizer.zscore)
        
        for col in columns:
            if col not in df.columns:
                continue
            
            try:
                if method == 'log':
                    result[col] = normalize_fn(df[col])
                else:
                    result[col] = normalize_fn(df[col], window)
            except Exception as e:
                logger.warning(f"Could not normalize {col}: {e}")
        
        return result
    
    def validate_features(
        self,
        df: pd.DataFrame,
        target: pd.Series = None
    ) -> Dict[str, Any]:
        """
        Validate feature quality and detect issues.
        
        Checks:
        - Constant features (no variance)
        - Highly correlated features (redundancy)
        - Features with excessive missing values
        - Potential look-ahead bias indicators
        - Target leakage
        """
        validation = {
            'total_features': len(df.columns),
            'total_samples': len(df),
            'issues': [],
            'warnings': [],
            'feature_stats': {}
        }
        
        for col in df.columns:
            series = df[col]
            stats_dict = {
                'missing_pct': float(series.isna().mean() * 100),
                'unique_values': int(series.nunique()),
                'dtype': str(series.dtype)
            }
            
            # Check for numeric columns
            if np.issubdtype(series.dtype, np.number):
                stats_dict['mean'] = float(series.mean()) if not series.isna().all() else None
                stats_dict['std'] = float(series.std()) if not series.isna().all() else None
                stats_dict['min'] = float(series.min()) if not series.isna().all() else None
                stats_dict['max'] = float(series.max()) if not series.isna().all() else None
                
                # Check for constant feature
                if series.std() == 0 or series.nunique() == 1:
                    validation['issues'].append({
                        'feature': col,
                        'type': 'constant',
                        'message': f"Feature '{col}' has zero variance"
                    })
                
                # Check for extreme values
                if not series.isna().all():
                    zscore_max = abs((series - series.mean()) / series.std()).max()
                    if zscore_max > 10:
                        validation['warnings'].append({
                            'feature': col,
                            'type': 'outliers',
                            'message': f"Feature '{col}' has extreme outliers (max z-score: {zscore_max:.1f})"
                        })
            
            # Check for excessive missing values
            missing_pct = series.isna().mean() * 100
            if missing_pct > 30:
                validation['warnings'].append({
                    'feature': col,
                    'type': 'missing_data',
                    'message': f"Feature '{col}' has {missing_pct:.1f}% missing values"
                })
            
            validation['feature_stats'][col] = stats_dict
        
        # Check for highly correlated features
        numeric_df = df.select_dtypes(include=[np.number])
        if len(numeric_df.columns) > 1:
            corr_matrix = numeric_df.corr()
            high_corr_pairs = []
            
            for i, col1 in enumerate(corr_matrix.columns):
                for col2 in corr_matrix.columns[i+1:]:
                    corr_val = abs(corr_matrix.loc[col1, col2])
                    if corr_val > 0.95 and not np.isnan(corr_val):
                        high_corr_pairs.append({
                            'feature1': col1,
                            'feature2': col2,
                            'correlation': float(corr_val)
                        })
            
            if high_corr_pairs:
                validation['warnings'].append({
                    'type': 'high_correlation',
                    'message': f"Found {len(high_corr_pairs)} highly correlated feature pairs (r > 0.95)",
                    'pairs': high_corr_pairs[:10]  # Limit to first 10
                })
        
        # Check for target leakage (if target provided)
        if target is not None:
            for col in numeric_df.columns:
                corr_with_target = abs(df[col].corr(target))
                if corr_with_target > 0.95 and not np.isnan(corr_with_target):
                    validation['issues'].append({
                        'feature': col,
                        'type': 'potential_leakage',
                        'message': f"Feature '{col}' has suspiciously high correlation ({corr_with_target:.3f}) with target"
                    })
        
        validation['is_valid'] = len(validation['issues']) == 0
        validation['has_warnings'] = len(validation['warnings']) > 0
        
        return validation
    
    def detect_leakage(
        self,
        feature_df: pd.DataFrame,
        signal_dates: pd.Series,
        feature_creation_dates: Dict[str, pd.Series] = None
    ) -> Dict[str, Any]:
        """
        Detect potential look-ahead bias in features.
        
        Checks if any feature values could have been influenced by
        information available after the signal date.
        """
        leakage_report = {
            'potential_leakage': [],
            'safe_features': [],
            'unknown_features': []
        }
        
        if feature_creation_dates is None:
            # Without explicit dates, we can only do heuristic checks
            for col in feature_df.columns:
                # Check if feature name suggests forward-looking data
                forward_indicators = ['future', 'forward', 'next', 'tomorrow', 'predict']
                if any(ind in col.lower() for ind in forward_indicators):
                    leakage_report['potential_leakage'].append({
                        'feature': col,
                        'reason': 'Name suggests forward-looking data'
                    })
                else:
                    leakage_report['unknown_features'].append(col)
        else:
            for col, creation_dates in feature_creation_dates.items():
                if col not in feature_df.columns:
                    continue
                
                # Check if any feature was created after signal date
                leakage_mask = creation_dates > signal_dates
                if leakage_mask.any():
                    leakage_count = leakage_mask.sum()
                    leakage_report['potential_leakage'].append({
                        'feature': col,
                        'reason': f'{leakage_count} values created after signal date',
                        'leakage_count': int(leakage_count)
                    })
                else:
                    leakage_report['safe_features'].append(col)
        
        return leakage_report
    
    def get_correlation_matrix(
        self,
        df: pd.DataFrame,
        method: Literal['pearson', 'spearman', 'kendall'] = 'pearson'
    ) -> Dict[str, Any]:
        """Get correlation matrix for features"""
        numeric_df = df.select_dtypes(include=[np.number])
        
        corr = numeric_df.corr(method=method)
        
        return {
            'features': list(corr.columns),
            'matrix': corr.values.tolist(),
            'method': method
        }
    
    def get_feature_stability(
        self,
        df: pd.DataFrame,
        windows: List[int] = [20, 60, 120]
    ) -> Dict[str, Any]:
        """Analyze feature stability over time"""
        stability = {}
        
        for col in df.select_dtypes(include=[np.number]).columns:
            series = df[col].dropna()
            if len(series) < max(windows):
                continue
            
            col_stability = {}
            for window in windows:
                rolling_mean = series.rolling(window).mean()
                rolling_std = series.rolling(window).std()
                
                # Coefficient of variation over time
                cv = (rolling_std / rolling_mean.abs().replace(0, np.nan)).dropna()
                
                col_stability[f'cv_mean_{window}d'] = float(cv.mean()) if len(cv) > 0 else None
                col_stability[f'cv_std_{window}d'] = float(cv.std()) if len(cv) > 0 else None
            
            stability[col] = col_stability
        
        return stability
    
    def register_feature(
        self,
        name: str,
        description: str,
        normalization: str = 'zscore',
        lag: int = 1,
        metadata: Dict = None
    ):
        """Register a feature in the registry for versioning"""
        self.feature_registry[name] = {
            'description': description,
            'normalization': normalization,
            'lag': lag,
            'created_at': datetime.now().isoformat(),
            'metadata': metadata or {}
        }
    
    def get_feature_registry(self) -> Dict[str, Dict]:
        """Get all registered features"""
        return self.feature_registry


# =============================================================================
# CONVENIENCE FUNCTIONS
# =============================================================================

def engineer_features(
    df: pd.DataFrame,
    price_col: str = 'Close',
    include_momentum: bool = True,
    include_volatility: bool = True,
    include_rolling: bool = True,
    normalize: bool = True,
    normalization_method: str = 'zscore'
) -> pd.DataFrame:
    """Convenience function for comprehensive feature engineering"""
    engineer = FeatureEngineer()
    result = df.copy()
    
    if include_momentum:
        result = engineer.create_momentum_features(result, price_col)
    
    if include_volatility:
        result = engineer.create_volatility_features(result, price_col=price_col)
    
    if include_rolling and price_col in result.columns:
        result = engineer.create_rolling_features(result, price_col)
    
    if normalize:
        result = engineer.normalize_features(result, method=normalization_method)
    
    return result


def validate_feature_matrix(X: pd.DataFrame, y: pd.Series = None) -> Dict:
    """Convenience function for feature validation"""
    engineer = FeatureEngineer()
    return engineer.validate_features(X, y)
