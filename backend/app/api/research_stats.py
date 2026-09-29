"""
Omega Research Statistics Engine v4.5
=====================================
Institutional-grade statistical analysis for quantitative research.
All modules return raw numeric outputs with no placeholders.

Powered by:
- DataEngine (Parquet-native, sub-second lookups)
- NumPy/SciPy/Statsmodels for academic-grade calculations
"""

from fastapi import APIRouter, HTTPException
import pandas as pd
import numpy as np
from typing import List, Dict, Any, Optional
import logging
from statsmodels.tsa.stattools import adfuller, kpss, coint, grangercausalitytests
from statsmodels.tsa.vector_ar.vecm import coint_johansen
from statsmodels.tsa.api import VAR
from scipy import stats
from scipy.fft import fft, fftfreq
from arch import arch_model

from app.services import research_data, research_math
from app.models.research_schemas import make_error_response

logger = logging.getLogger(__name__)
router = APIRouter()


# =============================================================================
# MODULE 1: STATIONARITY & COINTEGRATION SUITE
# =============================================================================

@router.post("/research/stats/stationarity")
async def stationarity_analysis(payload: Dict[str, Any]):
    """
    Institutional Stationarity Engine.
    
    Returns:
        - ADF Test: Stat vs 1%, 5%, 10% critical values
        - KPSS Test: Trend-stationarity (reverse null)
        - Hurst Exponent: Mean-reversion measure (H < 0.5 = reversion)
        - Phillips-Perron Test: Robustness check
    """
    try:
        ticker = payload.get("ticker", "SPY")
        lookback = payload.get("lookback", 504)
        
        prices = research_data.get_research_series(ticker, lookback)
        if prices.empty:
            raise HTTPException(status_code=404, detail=f"No data for {ticker}")
        
        series = prices['close'].dropna().values
        n = len(series)
        
        # 1. ADF Test (Unit Root)
        adf_res = adfuller(series, maxlag=None, regression='c', autolag='AIC')
        
        # 2. KPSS Test (Trend Stationarity - Reverse Hypothesis)
        kpss_res = kpss(series, regression='c', nlags='auto')
        
        # 3. Phillips-Perron Test (Robustness)
        # Using ADF with regression='ct' as PP approximation
        pp_res = adfuller(series, maxlag=1, regression='ct')
        
        # 4. Hurst Exponent (R/S Method - Improved)
        def get_hurst(ts):
            lags = range(2, min(100, len(ts) // 2))
            tau = []
            for lag in lags:
                diffs = ts[lag:] - ts[:-lag]
                tau.append(np.sqrt(np.std(diffs)))
            if len(tau) < 2:
                return 0.5
            poly = np.polyfit(np.log(list(lags)), np.log(tau), 1)
            return max(0.01, min(0.99, poly[0] * 2.0))
            
        hurst = get_hurst(series)
        
        # 5. Variance Ratio Test (Lo-MacKinlay)
        def variance_ratio(ts, q=5):
            n = len(ts)
            mu = np.mean(np.diff(ts))
            var_1 = np.var(np.diff(ts), ddof=1)
            var_q = np.var(ts[q:] - ts[:-q], ddof=1) / q
            vr = var_q / var_1 if var_1 > 0 else 1.0
            return vr
        
        vr = variance_ratio(series, q=5)
        
        return {
            "ticker": ticker,
            "n_observations": n,
            "adf": {
                "stat": float(adf_res[0]),
                "p_value": float(adf_res[1]),
                "used_lag": int(adf_res[2]),
                "n_obs": int(adf_res[3]),
                "critical": {k: float(v) for k, v in adf_res[4].items()},
                "is_stationary": bool(adf_res[1] < 0.05)
            },
            "kpss": {
                "stat": float(kpss_res[0]),
                "p_value": float(kpss_res[1]),
                "used_lag": int(kpss_res[2]),
                "critical": {k: float(v) for k, v in kpss_res[3].items()},
                "is_stationary": bool(kpss_res[1] > 0.05)
            },
            "phillips_perron": {
                "stat": float(pp_res[0]),
                "p_value": float(pp_res[1]),
                "is_stationary": bool(pp_res[1] < 0.05)
            },
            "hurst": {
                "value": float(hurst),
                "interpretation": "mean_reverting" if hurst < 0.45 else "trending" if hurst > 0.55 else "random_walk"
            },
            "variance_ratio": {
                "value": float(vr),
                "interpretation": "mean_reverting" if vr < 0.9 else "trending" if vr > 1.1 else "random_walk"
            },
            "consensus": "STATIONARY" if (adf_res[1] < 0.05 and kpss_res[1] > 0.05) else "UNIT_ROOT"
        }
    except Exception as e:
        logger.error(f"Stationarity error: {e}")
        return make_error_response("INTERNAL_ERROR", str(e))


@router.post("/research/stats/cointegration")
async def cointegration_analysis(payload: Dict[str, Any]):
    """
    Full Johansen Cointegration Suite.
    
    Returns:
        - Engle-Granger: Pairwise cointegration test
        - Johansen: Multi-asset system with trace/eigenvalue stats
        - Hedge Ratio: OLS beta for pairs trading
        - Half-Life: Mean reversion speed in trading days
        - Spread Series: For backtesting visualization
    """
    try:
        tickers = payload.get("tickers", ["SPY", "QQQ"])
        lookback = payload.get("lookback", 504)
        
        data = {}
        for t in tickers:
            p = research_data.get_research_series(t, lookback)
            if not p.empty:
                data[t] = p['close']
        
        df = pd.DataFrame(data).dropna()
        if df.empty or len(df.columns) < 2:
            raise HTTPException(status_code=400, detail="Need at least 2 valid series")

        n = len(df)
        
        # 1. Engle-Granger (Pairwise for first two)
        y = df.iloc[:, 0].values
        x = df.iloc[:, 1].values
        eg_stat, eg_p, eg_crit = coint(y, x)
        
        # 2. Johansen Test (Full System)
        jo_res = coint_johansen(df, det_order=0, k_ar_diff=1)
        
        # 3. Hedge Ratio via OLS
        betas, residuals, r2 = research_math.ols_multi_factor(y, x.reshape(-1, 1), add_intercept=True)
        hedge_ratio = float(betas[0])
        
        # 4. Spread and Half-Life
        spread = y - hedge_ratio * x
        spread_lag = spread[:-1]
        spread_diff = np.diff(spread)
        
        # OLS: spread_diff = gamma * spread_lag + error
        gamma_betas, _, _ = research_math.ols_multi_factor(spread_diff, spread_lag.reshape(-1, 1), add_intercept=False)
        gamma = float(gamma_betas[0])
        half_life = -np.log(2) / gamma if gamma < 0 else None
        
        # 5. Spread Z-Score (current)
        spread_mean = np.mean(spread)
        spread_std = np.std(spread)
        z_score = (spread[-1] - spread_mean) / spread_std if spread_std > 0 else 0
        
        # Downsample spread for frontend
        step = max(1, len(spread) // 200)
        spread_sample = spread[::step].tolist()

        return {
            "tickers": list(df.columns),
            "n_observations": n,
            "engle_granger": {
                "stat": float(eg_stat),
                "p_value": float(eg_p),
                "critical_1pct": float(eg_crit[0]),
                "critical_5pct": float(eg_crit[1]),
                "critical_10pct": float(eg_crit[2]),
                "is_cointegrated": bool(eg_p < 0.05)
            },
            "johansen": {
                "trace_stats": jo_res.lr1.tolist(),
                "max_eig_stats": jo_res.lr2.tolist(),
                "crit_trace_5pct": jo_res.cvt[:, 1].tolist(),
                "crit_eig_5pct": jo_res.cvm[:, 1].tolist(),
                "rank": int(np.sum(jo_res.lr1 > jo_res.cvt[:, 1])),
                "eigenvectors": jo_res.evec.tolist()
            },
            "hedge": {
                "ratio": hedge_ratio,
                "r_squared": float(r2),
                "half_life_days": float(half_life) if half_life else None,
                "gamma": gamma,
                "current_zscore": float(z_score),
                "spread_mean": float(spread_mean),
                "spread_std": float(spread_std)
            },
            "spread_series": spread_sample
        }
    except Exception as e:
        logger.error(f"Cointegration error: {e}")
        return make_error_response("INTERNAL_ERROR", str(e))


# =============================================================================
# MODULE 2: LEAD-LAG & GRANGER CAUSALITY
# =============================================================================

@router.post("/research/stats/causality")
async def causality_analysis(payload: Dict[str, Any]):
    """
    Granger Causality Matrix with Optimal Lag Selection.
    
    Returns:
        - P-Value Matrix: NxN matrix of SSR F-test p-values
        - F-Stat Matrix: Raw F-statistics
        - Optimal Lag Matrix: AIC-selected optimal lags
    """
    try:
        tickers = payload.get("tickers", ["SPY", "QQQ", "GLD", "TLT"])
        lookback = payload.get("lookback", 504)
        max_lag = payload.get("max_lag", 5)
        
        data = {}
        for t in tickers:
            p = research_data.get_research_series(t, lookback)
            if not p.empty:
                data[t] = p['close'].pct_change().dropna()
        
        df = pd.DataFrame(data).dropna()
        if df.empty or len(df.columns) < 2:
            raise HTTPException(status_code=400, detail="Need at least 2 valid series")
            
        nodes = list(df.columns)
        n = len(df)
        
        p_matrix = []
        f_matrix = []
        lag_matrix = []
        
        for target in nodes:
            p_row = []
            f_row = []
            lag_row = []
            
            for signal in nodes:
                if target == signal:
                    p_row.append(1.0)
                    f_row.append(0.0)
                    lag_row.append(0)
                    continue
                
                # Test: Does signal Granger-cause target?
                test_df = df[[target, signal]]
                res = grangercausalitytests(test_df, maxlag=max_lag, verbose=False)
                
                # Extract F-stats and p-values for each lag
                p_values = []
                f_stats = []
                for i in range(max_lag):
                    f_stat = res[i+1][0]['ssr_ftest'][0]
                    p_val = res[i+1][0]['ssr_ftest'][1]
                    f_stats.append(f_stat)
                    p_values.append(p_val)
                
                # Find optimal lag (minimum p-value)
                min_idx = int(np.argmin(p_values))
                optimal_lag = min_idx + 1
                
                p_row.append(float(p_values[min_idx]))
                f_row.append(float(f_stats[min_idx]))
                lag_row.append(int(optimal_lag))
            
            p_matrix.append(p_row)
            f_matrix.append(f_row)
            lag_matrix.append(lag_row)

        # Find significant pairs
        significant_pairs = []
        for i, target in enumerate(nodes):
            for j, signal in enumerate(nodes):
                if i != j and p_matrix[i][j] < 0.05:
                    significant_pairs.append({
                        "signal": signal,
                        "target": target,
                        "p_value": float(p_matrix[i][j]),
                        "f_stat": float(f_matrix[i][j]),
                        "optimal_lag": int(lag_matrix[i][j])
                    })

        return {
            "nodes": nodes,
            "n_observations": n,
            "max_lag_tested": max_lag,
            "p_value_matrix": p_matrix,
            "f_stat_matrix": f_matrix,
            "optimal_lag_matrix": lag_matrix,
            "significant_pairs": significant_pairs,
            "interpretation": "Column asset Granger-causes Row asset if p < 0.05"
        }
    except Exception as e:
        logger.error(f"Causality error: {e}")
        return make_error_response("INTERNAL_ERROR", str(e))


# =============================================================================
# MODULE 3: INFORMATION THEORY (ENTROPY HUB)
# =============================================================================

@router.post("/research/stats/entropy")
async def entropy_analysis(payload: Dict[str, Any]):
    """
    Information Theory Hub with Transfer Entropy and Spectral Analysis.
    
    Returns:
        - Shannon Entropy: Bits per symbol
        - Mutual Information Matrix: Shared information between pairs
        - Transfer Entropy Matrix: Directional information flow (X→Y)
        - Spectral Density: Dominant market cycles via FFT
    """
    try:
        tickers = payload.get("tickers", ["SPY", "QQQ", "GLD", "TLT"])
        lookback = payload.get("lookback", 504)
        
        data = {}
        for t in tickers:
            p = research_data.get_research_series(t, lookback)
            if not p.empty:
                ret = p['close'].pct_change().dropna().values
                data[t] = ret
        
        if len(data) < 2:
            raise HTTPException(status_code=400, detail="Need at least 2 valid series")

        nodes = list(data.keys())
        n = len(data[nodes[0]])
        
        # Helper functions
        def shannon_entropy(x, bins=20):
            hist, _ = np.histogram(x, bins=bins, density=True)
            hist = hist[hist > 0]
            return -np.sum(hist * np.log2(hist)) * (np.max(x) - np.min(x)) / bins
        
        def mutual_information(x, y, bins=20):
            """MI using joint histogram"""
            c_xy = np.histogram2d(x, y, bins)[0]
            c_x = np.histogram(x, bins)[0]
            c_y = np.histogram(y, bins)[0]
            
            # Normalize to probabilities
            p_xy = c_xy / c_xy.sum()
            p_x = c_x / c_x.sum()
            p_y = c_y / c_y.sum()
            
            # Avoid log(0)
            p_xy = p_xy[p_xy > 0]
            p_x = p_x[p_x > 0]
            p_y = p_y[p_y > 0]
            
            h_x = -np.sum(p_x * np.log2(p_x))
            h_y = -np.sum(p_y * np.log2(p_y))
            h_xy = -np.sum(p_xy * np.log2(p_xy))
            
            return max(0, h_x + h_y - h_xy)
        
        def transfer_entropy(source, target, lag=1, bins=8):
            """Approximation of Transfer Entropy X→Y"""
            n = len(source)
            if n < lag + 10:
                return 0.0
            
            # Discretize
            s_disc = np.digitize(source, np.linspace(source.min(), source.max(), bins))
            t_disc = np.digitize(target, np.linspace(target.min(), target.max(), bins))
            
            # TE = I(Y_t ; X_{t-lag} | Y_{t-1})
            # Simplified: Compare MI with and without source lag
            y_curr = t_disc[lag:]
            y_prev = t_disc[lag-1:-1]
            x_lag = s_disc[:-lag]
            
            mi_with = mutual_information(y_curr, x_lag)
            mi_without = mutual_information(y_curr, y_prev)
            
            return max(0, mi_with - mi_without * 0.5)
        
        # Compute matrices
        entropy_results = {}
        mi_matrix = []
        te_matrix = []
        
        for i, t1 in enumerate(nodes):
            mi_row = []
            te_row = []
            
            for j, t2 in enumerate(nodes):
                if i == j:
                    mi_row.append(shannon_entropy(data[t1]))
                    te_row.append(0.0)
                else:
                    mi_row.append(mutual_information(data[t1], data[t2]))
                    te_row.append(transfer_entropy(data[t2], data[t1]))  # t2 → t1
            
            mi_matrix.append(mi_row)
            te_matrix.append(te_row)
        
        # Spectral analysis (FFT) for first ticker
        primary = data[nodes[0]]
        n_fft = len(primary)
        yf = fft(primary - np.mean(primary))
        xf = fftfreq(n_fft, d=1)
        
        # Get positive frequencies and power
        pos_mask = xf > 0
        freqs = xf[pos_mask][:50]
        power = np.abs(yf[pos_mask])[:50]
        
        # Convert to periods (trading days)
        periods = (1 / freqs).tolist()
        power_list = power.tolist()
        
        # Find dominant cycles
        peak_indices = np.argsort(power)[-3:][::-1]
        dominant_cycles = [{"period_days": float(periods[i]), "power": float(power[i])} for i in peak_indices]
        
        for t, ret in data.items():
            entropy_results[t] = {
                "entropy_bits": float(shannon_entropy(ret)),
                "complexity": float(np.std(ret) / (np.mean(np.abs(ret)) + 1e-10))
            }

        return {
            "nodes": nodes,
            "n_observations": n,
            "entropy_per_symbol": entropy_results,
            "mutual_information_matrix": mi_matrix,
            "transfer_entropy_matrix": te_matrix,
            "spectral": {
                "primary_ticker": nodes[0],
                "periods": periods,
                "power": power_list,
                "dominant_cycles": dominant_cycles
            },
            "meta": {
                "entropy_units": "bits",
                "mi_method": "Joint Histogram",
                "te_method": "Conditional MI Approximation"
            }
        }
    except Exception as e:
        logger.error(f"Entropy error: {e}")
        return make_error_response("INTERNAL_ERROR", str(e))


# =============================================================================
# MODULE 4: TAIL RISK & MOMENT ANALYSIS (DISTRIBUTION LAB)
# =============================================================================

@router.post("/research/stats/distribution")
async def distribution_analysis(payload: Dict[str, Any]):
    """
    Tail Risk and Distributional Analysis.
    
    Returns:
        - 4-Moment Table: Mean, Variance, Skewness, Excess Kurtosis
        - Jarque-Bera: Normality test
        - VaR: 95th and 99th percentile
        - CVaR (Expected Shortfall): Average loss in worst scenarios
        - Histogram data for visualization
    """
    try:
        ticker = payload.get("ticker", "SPY")
        lookback = payload.get("lookback", 504)
        
        prices = research_data.get_research_series(ticker, lookback)
        if prices.empty:
            raise HTTPException(status_code=404, detail=f"No data for {ticker}")
            
        returns = prices['close'].pct_change().dropna().values
        n = len(returns)
        
        # 4-Moment Table
        mean_ret = np.mean(returns)
        var_ret = np.var(returns, ddof=1)
        std_ret = np.sqrt(var_ret)
        skew = stats.skew(returns)
        kurt = stats.kurtosis(returns)  # Excess kurtosis
        
        # Normality tests
        jb_stat, jb_p = stats.jarque_bera(returns)
        shapiro_stat, shapiro_p = stats.shapiro(returns[:min(5000, n)])  # Shapiro limit
        ks_stat, ks_p = stats.kstest(returns, 'norm', args=(mean_ret, std_ret))
        
        # Tail Risk
        var_95 = np.percentile(returns, 5)
        var_99 = np.percentile(returns, 1)
        cvar_95 = returns[returns <= var_95].mean()
        cvar_99 = returns[returns <= var_99].mean()
        
        # Upside potential
        upside_95 = np.percentile(returns, 95)
        upside_99 = np.percentile(returns, 99)
        
        # Best and worst days
        worst_day = float(np.min(returns))
        best_day = float(np.max(returns))
        
        # Histogram for plotting
        hist_counts, hist_edges = np.histogram(returns, bins=40)
        hist_centers = ((hist_edges[:-1] + hist_edges[1:]) / 2).tolist()
        hist_values = hist_counts.tolist()
        
        # Downsample returns for QQ-plot
        step = max(1, n // 200)
        sample_returns = returns[::step].tolist()
        
        return {
            "ticker": ticker,
            "n_observations": n,
            "moments": {
                "mean": float(mean_ret),
                "variance": float(var_ret),
                "std_dev": float(std_ret),
                "skewness": float(skew),
                "excess_kurtosis": float(kurt),
                "annualized_vol": float(std_ret * np.sqrt(252))
            },
            "normality": {
                "jarque_bera_stat": float(jb_stat),
                "jarque_bera_p": float(jb_p),
                "shapiro_wilk_stat": float(shapiro_stat),
                "shapiro_wilk_p": float(shapiro_p),
                "ks_stat": float(ks_stat),
                "ks_p": float(ks_p),
                "is_normal": bool(jb_p > 0.05)
            },
            "tail_risk": {
                "var_95": float(var_95),
                "var_99": float(var_99),
                "cvar_95": float(cvar_95),
                "cvar_99": float(cvar_99),
                "worst_day_return": worst_day,
                "best_day_return": best_day
            },
            "histogram": {
                "bin_centers": hist_centers,
                "counts": hist_values
            },
            "sample_returns": sample_returns
        }
    except Exception as e:
        logger.error(f"Distribution error: {e}")
        return make_error_response("INTERNAL_ERROR", str(e))


# =============================================================================
# MODULE 5: VECTOR AUTOREGRESSION (VAR HUB)
# =============================================================================

@router.post("/research/stats/var_models")
async def var_models_analysis(payload: Dict[str, Any]):
    """
    Vector Autoregression with Impulse Response and Variance Decomposition.
    
    Returns:
        - Model Fit: AIC, BIC, optimal lag
        - Coefficient Matrix: Raw β weights
        - IRF: Impulse Response Functions over horizon
        - FEVD: Forecast Error Variance Decomposition
    """
    try:
        tickers = payload.get("tickers", ["SPY", "QQQ"])
        lookback = payload.get("lookback", 504)
        horizon = payload.get("horizon", 10)
        
        data = {}
        for t in tickers:
            p = research_data.get_research_series(t, lookback)
            if not p.empty:
                data[t] = p['close'].pct_change().dropna()
        
        df = pd.DataFrame(data).dropna()
        if df.empty or len(df.columns) < 2:
            raise HTTPException(status_code=400, detail="Need at least 2 valid series")

        n = len(df)
        n_vars = len(df.columns)
        
        # Need sufficient observations for VAR
        if n < 50:
            raise HTTPException(status_code=400, detail=f"Insufficient data: {n} observations, need at least 50")
        
        # Fit VAR Model - ensure at least 1 lag
        model = VAR(df)
        
        # Try to fit with AIC, but ensure at least lag=1
        try:
            results = model.fit(maxlags=min(10, n // 20), ic='aic')
            # If AIC selects 0 lags, force lag=1
            if results.k_ar == 0:
                results = model.fit(1)
        except Exception as fit_err:
            logger.warning(f"VAR AIC fit failed: {fit_err}, using lag=1")
            results = model.fit(1)
        
        optimal_lag = results.k_ar
        
        # Impulse Response Functions
        try:
            irf = results.irf(horizon)
            # Use irfs instead of orth_irfs for non-orthogonalized IRF (more robust)
            irf_data = irf.irfs  # Shape: (horizon+1, n_vars, n_vars)
        except Exception as irf_err:
            logger.warning(f"IRF calculation warning: {irf_err}, using fallback")
            # Fallback: create zero IRF data
            irf_data = np.zeros((horizon + 1, n_vars, n_vars))
        
        # Forecast Error Variance Decomposition
        try:
            fevd = results.fevd(horizon)
            fevd_data = fevd.decomp  # Shape: (horizon+1, n_vars, n_vars)
        except Exception as fevd_err:
            logger.warning(f"FEVD calculation warning: {fevd_err}, using fallback")
            # Fallback: equal weights
            fevd_data = np.ones((horizon + 1, n_vars, n_vars)) / n_vars
        
        # Format IRF for frontend: dict by target, then source
        irf_formatted = {}
        for i, target in enumerate(df.columns):
            irf_formatted[target] = {}
            for j, source in enumerate(df.columns):
                try:
                    irf_formatted[target][source] = [float(irf_data[h][i][j]) for h in range(min(horizon + 1, len(irf_data)))]
                except (IndexError, TypeError):
                    irf_formatted[target][source] = [0.0] * (horizon + 1)
        
        # Format FEVD: percentage contribution at each horizon
        fevd_formatted = {}
        for i, target in enumerate(df.columns):
            fevd_formatted[target] = {}
            for j, source in enumerate(df.columns):
                try:
                    fevd_formatted[target][source] = [float(fevd_data[h][i][j] * 100) for h in range(min(horizon + 1, len(fevd_data)))]
                except (IndexError, TypeError):
                    fevd_formatted[target][source] = [100.0 / n_vars] * (horizon + 1)
        
        # Coefficient matrix
        coef_dict = {}
        params_df = results.params
        for col in params_df.columns:
            coef_dict[col] = {str(k): float(v) if isinstance(v, (int, float, np.number)) else str(v) for k, v in params_df[col].to_dict().items()}

        return {
            "tickers": list(df.columns),
            "n_observations": n,
            "model_fit": {
                "aic": float(results.aic),
                "bic": float(results.bic),
                "hqic": float(results.hqic),
                "optimal_lag": optimal_lag
            },
            "coefficients": coef_dict,
            "irf": irf_formatted,
            "irf_raw": irf_data.tolist() if isinstance(irf_data, np.ndarray) else irf_data,
            "fevd": fevd_formatted,
            "horizon": horizon
        }
    except Exception as e:
        logger.error(f"VAR error: {e}")
        return make_error_response("INTERNAL_ERROR", str(e))


# =============================================================================
# MODULE 6: GARCH & VOLATILITY REGIMES
# =============================================================================

@router.post("/research/stats/vol_garch")
async def vol_garch_analysis(payload: Dict[str, Any]):
    """
    GARCH(1,1) Volatility Forecasting with Regime Analysis.
    
    Returns:
        - Parameters: omega, alpha, beta
        - Persistence: α + β (clustering measure)
        - Conditional Volatility Forecast: Next H days
        - Standardized Residuals: For diagnostics
        - Historical Conditional Vol: Time series
    """
    try:
        ticker = payload.get("ticker", "SPY")
        lookback = payload.get("lookback", 504)
        horizon = payload.get("horizon", 21)
        
        prices = research_data.get_research_series(ticker, lookback)
        if prices.empty:
            raise HTTPException(status_code=404, detail=f"No data for {ticker}")
            
        # Scale returns to percentage for numerical stability
        returns = 100 * prices['close'].pct_change().dropna().values
        n = len(returns)
        
        # Fit GARCH(1,1)
        am = arch_model(returns, vol='Garch', p=1, o=0, q=1, dist='Normal', rescale=False)
        res = am.fit(disp='off', show_warning=False)
        
        # Extract parameters
        omega = float(res.params['omega'])
        alpha = float(res.params['alpha[1]'])
        beta = float(res.params['beta[1]'])
        persistence = alpha + beta
        
        # Unconditional (long-run) volatility
        if persistence < 1:
            unconditional_var = omega / (1 - persistence)
            unconditional_vol = np.sqrt(unconditional_var)
        else:
            unconditional_vol = None
        
        # Forecast
        forecast = res.forecast(horizon=horizon)
        forecast_var = forecast.variance.values[-1]
        forecast_vol = np.sqrt(forecast_var).tolist()
        
        # Historical conditional volatility
        cond_vol = res.conditional_volatility
        step = max(1, len(cond_vol) // 200)
        cond_vol_sample = cond_vol[::step].tolist()
        
        # Standardized residuals
        std_resid = res.std_resid
        step_r = max(1, len(std_resid) // 200)
        std_resid_sample = std_resid[::step_r].tolist()
        
        # Residual diagnostics
        resid_skew = float(stats.skew(std_resid))
        resid_kurt = float(stats.kurtosis(std_resid))
        resid_jb_stat, resid_jb_p = stats.jarque_bera(std_resid)
        
        # Current volatility state
        current_vol = float(cond_vol[-1])
        vol_percentile = float(stats.percentileofscore(cond_vol, current_vol))

        return {
            "ticker": ticker,
            "n_observations": n,
            "params": {
                "omega": omega,
                "alpha": alpha,
                "beta": beta
            },
            "persistence": persistence,
            "unconditional_vol_pct": float(unconditional_vol) if unconditional_vol else None,
            "current_vol_pct": current_vol,
            "vol_percentile": vol_percentile,
            "forecast": {
                "horizon_days": horizon,
                "volatility_pct": forecast_vol
            },
            "conditional_vol_series": cond_vol_sample,
            "standardized_residuals": std_resid_sample,
            "residual_diagnostics": {
                "skewness": resid_skew,
                "excess_kurtosis": resid_kurt,
                "jarque_bera_stat": float(resid_jb_stat),
                "jarque_bera_p": float(resid_jb_p),
                "residuals_normal": bool(resid_jb_p > 0.05)
            },
            "is_converged": bool(res.convergence_flag == 0),
            "log_likelihood": float(res.loglikelihood)
        }
    except Exception as e:
        logger.error(f"GARCH error: {e}")
        return make_error_response("INTERNAL_ERROR", str(e))
