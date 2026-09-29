"""
Research Math Service
Mathematical functions for research computations.
"""

import pandas as pd
import numpy as np
from typing import Tuple, Literal, Callable, Optional, Any
import logging

logger = logging.getLogger(__name__)

# Small epsilon to avoid division by zero
EPSILON = 1e-8


def returns_from_close(
    close: pd.Series,
    returns_type: Literal["log", "simple"] = "log"
) -> pd.Series:
    """
    Compute returns from close prices.
    
    Args:
        close: Series of close prices
        returns_type: "log" for ln(p_t/p_{t-1}), "simple" for (p_t - p_{t-1})/p_{t-1}
        
    Returns:
        Series of returns (first value will be NaN)
    """
    if close.empty:
        return pd.Series(dtype=float)
    
    if returns_type == "log":
        # Log returns: ln(p_t / p_{t-1})
        returns = np.log(close / close.shift(1))
    else:
        # Simple returns: (p_t - p_{t-1}) / p_{t-1}
        returns = close.pct_change()
    
    return returns


def winsorize(series: pd.Series, p: float = 0.01) -> pd.Series:
    """
    Winsorize a series to reduce outlier impact.
    
    Args:
        series: Input series
        p: Percentile to clip at (e.g., 0.01 clips at 1st and 99th percentiles)
        
    Returns:
        Winsorized series
    """
    if series.empty:
        return series
    
    lower = series.quantile(p)
    upper = series.quantile(1 - p)
    
    return series.clip(lower=lower, upper=upper)


def standardize(series: pd.Series) -> pd.Series:
    """
    Standardize a series to z-scores.
    
    Args:
        series: Input series
        
    Returns:
        Standardized series: z = (x - mean) / std
    """
    if series.empty:
        return series
    
    mean = series.mean()
    std = series.std()
    
    # Use epsilon floor to avoid division by zero
    std = max(std, EPSILON)
    
    return (series - mean) / std


def standardize_cross_sectional(df: pd.DataFrame) -> pd.DataFrame:
    """
    Standardize each column cross-sectionally (across rows at each point).
    
    Args:
        df: DataFrame with multiple columns
        
    Returns:
        DataFrame with each column standardized
    """
    result = pd.DataFrame(index=df.index)
    
    for col in df.columns:
        result[col] = standardize(df[col])
    
    return result


def ols_single_factor(
    y: np.ndarray,
    x: np.ndarray
) -> Tuple[float, float, float]:
    """
    Fast single-factor OLS regression.
    
    beta = cov(x, y) / var(x)
    alpha = mean(y) - beta * mean(x)
    r2 = 1 - SSE/SST
    
    Args:
        y: Dependent variable (returns)
        x: Independent variable (factor)
        
    Returns:
        Tuple of (beta, alpha, r2)
    """
    # Remove NaN values and cast to float to avoid ufunc 'isnan' error on object arrays
    y = np.asanyarray(y).astype(float)
    x = np.asanyarray(x).astype(float)
    
    mask = ~(np.isnan(y) | np.isnan(x))
    y_clean = y[mask]
    x_clean = x[mask]
    
    if len(y_clean) < 2:
        return np.nan, np.nan, np.nan
    
    # Compute statistics
    mean_y = np.mean(y_clean)
    mean_x = np.mean(x_clean)
    
    # Covariance and variance
    cov_xy = np.mean((x_clean - mean_x) * (y_clean - mean_y))
    var_x = np.var(x_clean, ddof=0)
    
    if var_x < EPSILON:
        return np.nan, np.nan, np.nan
    
    # Beta and alpha
    beta = cov_xy / var_x
    alpha = mean_y - beta * mean_x
    
    # R-squared
    y_pred = alpha + beta * x_clean
    ss_res = np.sum((y_clean - y_pred) ** 2)
    ss_tot = np.sum((y_clean - mean_y) ** 2)
    
    if ss_tot < EPSILON:
        r2 = 0.0
    else:
        r2 = 1.0 - (ss_res / ss_tot)
        r2 = max(0.0, min(1.0, r2))  # Clamp to [0, 1]
    
    return float(beta), float(alpha), float(r2)


def ols_multi_factor(
    y: np.ndarray,
    X: np.ndarray,
    ridge: float = 1e-6,
    add_intercept: bool = True,
    robust: bool = False
) -> Tuple[np.ndarray, Any, float]:
    """
    Multi-factor OLS regression with ridge regularization and optional HAC (Newey-West) errors.
    
    Args:
        y: Dependent variable (T,)
        X: Independent variables (T, K)
        ridge: Ridge regularization parameter
        add_intercept: Whether to add intercept column
        robust: Whether to use Newey-West robust standard errors
        
    Returns:
        Tuple of (betas, stats_dict, r2)
        - betas: array of coefficients
        - stats_dict: dictionary containing se, tstats, pvalues
        - r2: R-squared
    """
    # Remove NaN rows and cast to float to avoid ufunc 'isnan' error on object arrays
    y = np.asanyarray(y).astype(float)
    X = np.asanyarray(X).astype(float)
    
    mask = ~np.isnan(y)
    for k in range(X.shape[1]):
        mask = mask & ~np.isnan(X[:, k])
    
    y_clean = y[mask]
    X_clean = X[mask]
    
    if len(y_clean) < X.shape[1] + (3 if robust else 2):
        n_cols = X.shape[1] + (1 if add_intercept else 0)
        return np.full(n_cols, np.nan), {}, np.nan
    
    # Add intercept column
    if add_intercept:
        intercept = np.ones((X_clean.shape[0], 1))
        X_clean = np.hstack([intercept, X_clean])
    
    # CASE 1: Robust / Statistics focused (uses statsmodels)
    if robust:
        try:
            import statsmodels.api as sm
            model = sm.OLS(y_clean, X_clean)
            # Newey-West with automatic lag selection
            results = model.fit(cov_type='HAC', cov_kwds={'maxlags': int(4 * (len(y_clean)/100)**(2/9))})
            
            stats_dict = {
                "se": results.bse,
                "t_stats": results.tvalues,
                "p_values": results.pvalues,
                "residual_std": np.std(results.resid, ddof=len(results.params))
            }
            return results.params, stats_dict, float(results.rsquared)
        except Exception as e:
            logger.debug(f"Robust OLS failed, falling back to standard: {e}")
            # fall through to normal OLS
            
    # CASE 2: High-performance / Ridge focused (uses numpy)
    # AUDIT FIX: Use lstsq instead of solve for numerical stability
    # lstsq handles singular/near-singular matrices gracefully (common during regime shifts)
    XtX = X_clean.T @ X_clean
    XtX += ridge * np.eye(XtX.shape[0])
    Xty = X_clean.T @ y_clean
    
    try:
        # Use lstsq instead of solve for better numerical stability
        # lstsq finds minimum norm solution even for rank-deficient matrices
        betas, residuals, rank, singular_values = np.linalg.lstsq(XtX, Xty, rcond=None)
        
        # Check for rank deficiency and log warning
        if rank < XtX.shape[0]:
            logger.warning(f"Rank deficient matrix detected (rank={rank}/{XtX.shape[0]}). Results may be unstable.")
        
        y_pred = X_clean @ betas
        residuals = y_clean - y_pred
        ss_res = np.sum(residuals ** 2)
        ss_tot = np.sum((y_clean - np.mean(y_clean)) ** 2)
        r2 = 1.0 - (ss_res / (ss_tot + EPSILON))
        
        # Simple standard errors (non-robust)
        n, k = X_clean.shape
        sigma_sq = ss_res / max(1, n - k)  # Prevent division by zero
        try:
            # Use pinv (pseudo-inverse) for stability instead of inv
            var_beta = sigma_sq * np.linalg.pinv(XtX)
            se = np.sqrt(np.maximum(np.diag(var_beta), 0))  # Ensure non-negative
            t_stats = betas / (se + EPSILON)
        except:
            se = np.zeros(k)
            t_stats = np.zeros(k)
            
        stats_dict = {
            "se": se,
            "t_stats": t_stats,
            "residual_std": np.sqrt(max(0, sigma_sq)),
            "matrix_rank": int(rank) if rank else k
        }
        
        return betas, stats_dict, float(max(0, min(1, r2)))
    except Exception as e:
        logger.warning(f"OLS computation failed: {e}")
        n_cols = X.shape[1] + (1 if add_intercept else 0)
        return np.full(n_cols, np.nan), {}, np.nan


def rolling_apply(
    df: pd.DataFrame,
    window: int,
    func: Callable,
    min_obs_ratio: float = 0.8,
    **kwargs
) -> pd.DataFrame:
    """
    Apply a function over rolling windows.
    
    Args:
        df: Input DataFrame
        window: Rolling window size
        func: Function to apply (receives DataFrame slice, returns dict)
        min_obs_ratio: Minimum ratio of observations required
        **kwargs: Additional arguments passed to func
        
    Returns:
        DataFrame with results from each window
    """
    min_obs = max(15, int(window * min_obs_ratio))
    results = []
    
    for i in range(window - 1, len(df)):
        window_data = df.iloc[i - window + 1:i + 1]
        
        # Check if enough observations
        valid_rows = window_data.dropna(how='any')
        
        if len(valid_rows) >= min_obs:
            try:
                result = func(window_data, **kwargs)
                result['date'] = df.index[i]
                results.append(result)
            except Exception as e:
                logger.debug(f"Rolling apply error at index {i}: {e}")
        else:
            results.append({'date': df.index[i]})
    
    if not results:
        return pd.DataFrame()
    
    result_df = pd.DataFrame(results)
    result_df = result_df.set_index('date')
    
    return result_df


def correlation_matrix(
    returns_df: pd.DataFrame,
    method: Literal["pearson", "spearman"] = "pearson"
) -> pd.DataFrame:
    """
    Compute correlation matrix for a returns DataFrame.
    
    Args:
        returns_df: DataFrame with ticker columns and date index
        method: Correlation method
        
    Returns:
        Correlation matrix DataFrame
    """
    return returns_df.corr(method=method)


def hierarchical_order(corr_matrix: pd.DataFrame) -> list:
    """
    Compute optimal ordering for correlation matrix using hierarchical clustering.
    
    Args:
        corr_matrix: Correlation matrix
        
    Returns:
        List of column names in optimal order
    """
    from scipy.cluster import hierarchy
    from scipy.spatial.distance import squareform
    
    try:
        # Convert correlation to distance
        dist_matrix = 1 - corr_matrix.abs()
        
        # Ensure symmetric and positive
        dist_matrix = (dist_matrix + dist_matrix.T) / 2
        np.fill_diagonal(dist_matrix.values, 0)
        
        # Condensed distance matrix
        condensed = squareform(dist_matrix.values)
        
        # Hierarchical clustering
        linkage = hierarchy.linkage(condensed, method='average')
        
        # Get optimal ordering
        dendro = hierarchy.dendrogram(linkage, no_plot=True)
        order_indices = dendro['leaves']
        
        return [corr_matrix.columns[i] for i in order_indices]
        
    except Exception as e:
        logger.warning(f"Hierarchical ordering failed: {e}, using original order")
        return list(corr_matrix.columns)


def compute_rolling_correlation(
    series_a: pd.Series,
    series_b: pd.Series,
    window: int
) -> pd.Series:
    """
    Compute rolling correlation between two series.
    
    Args:
        series_a: First series
        series_b: Second series
        window: Rolling window size
        
    Returns:
        Series of rolling correlations
    """
    return series_a.rolling(window=window).corr(series_b)


def downsample_series(series: pd.Series, max_points: int = 300) -> pd.Series:
    """
    Downsample a series to at most max_points using uniform sampling.
    
    Args:
        series: Input series
        max_points: Maximum number of points to keep
        
    Returns:
        Downsampled series
    """
    if len(series) <= max_points:
        return series
    
    # Uniform sampling
    indices = np.linspace(0, len(series) - 1, max_points, dtype=int)
    return series.iloc[indices]
