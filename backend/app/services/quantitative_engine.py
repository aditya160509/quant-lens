"""
Quantitative Engine - Institutional-Grade Mathematical Finance
===============================================================

4 Core Modules:
1. SDE Path Laboratory - Heston, GBM, Jump-Diffusion
2. State-Space Tracking - Kalman Filter, Dynamic Beta
3. Arbitrage Matrix - Johansen Cointegration, VECM, Half-Life
4. Spectral Physics - Continuous Wavelet Transform, Lyapunov Exponents

All math is real. No placeholders.
"""

import numpy as np
import pandas as pd
from scipy import signal, stats, optimize
from scipy.stats import rankdata
from scipy.integrate import odeint
from scipy.linalg import sqrtm
from typing import Dict, List, Any, Optional, Tuple, Union
from functools import lru_cache
from cachetools import TTLCache
import time
import logging

logger = logging.getLogger(__name__)

# Global cache for heavy quant calcs (1 hour TTL)
QUANT_CACHE = TTLCache(maxsize=128, ttl=3600)

# Constants
TRADING_DAYS = 252
EPSILON = 1e-10


# =============================================================================
# MODULE 1: SDE PATH LABORATORY
# =============================================================================

class SDEPathEngine:
    """
    Stochastic Differential Equation Path Simulator
    Implements: GBM, Heston (Stochastic Vol), Merton Jump-Diffusion
    """
    
    def __init__(self):
        self.rng = np.random.default_rng(42)
    
    def gbm_paths(
        self,
        S0: float,
        mu: float,
        sigma: float,
        T: int = 252,
        n_paths: int = 1000,
        dt: float = 1/252
    ) -> Dict[str, Any]:
        """
        Geometric Brownian Motion paths.
        dS = mu*S*dt + sigma*S*dW
        
        Returns paths and statistics.
        """
        n_steps = int(T / dt)
        
        # Generate Wiener increments
        dW = self.rng.normal(0, np.sqrt(dt), (n_paths, n_steps))
        
        # Initialize paths
        S = np.zeros((n_paths, n_steps + 1))
        S[:, 0] = S0
        
        # Euler-Maruyama discretization
        for t in range(n_steps):
            S[:, t + 1] = S[:, t] * np.exp((mu - 0.5 * sigma**2) * dt + sigma * dW[:, t])
        
        # Compute statistics
        percentiles = [5, 25, 50, 75, 95]
        cones = {f"p{p}": np.percentile(S, p, axis=0).tolist() for p in percentiles}
        
        terminal = S[:, -1]
        
        return {
            "paths_sample": S[:min(100, n_paths), :].tolist(),  # Cap for payload
            "time_axis": list(range(n_steps + 1)),
            "cones": cones,
            "terminal_stats": {
                "mean": float(np.mean(terminal)),
                "std": float(np.std(terminal)),
                "skewness": float(stats.skew(terminal)),
                "kurtosis": float(stats.kurtosis(terminal)),
                "min": float(np.min(terminal)),
                "max": float(np.max(terminal)),
            },
            "model": "GBM",
            "params": {"mu": mu, "sigma": sigma, "T": T, "n_paths": n_paths}
        }
    
    def heston_paths(
        self,
        S0: float,
        V0: float,
        mu: float,
        kappa: float,
        theta: float,
        xi: float,
        rho: float,
        T: int = 252,
        n_paths: int = 1000,
        dt: float = 1/252
    ) -> Dict[str, Any]:
        """
        Heston Stochastic Volatility Model.
        dS = mu*S*dt + sqrt(V)*S*dW1
        dV = kappa*(theta - V)*dt + xi*sqrt(V)*dW2
        corr(dW1, dW2) = rho
        
        Parameters:
        - kappa: Mean reversion speed of variance
        - theta: Long-term variance
        - xi: Vol of vol
        - rho: Correlation between price and vol shocks
        """
        n_steps = int(T / dt)
        
        # Generate correlated Wiener increments
        dW1 = self.rng.normal(0, np.sqrt(dt), (n_paths, n_steps))
        dZ = self.rng.normal(0, np.sqrt(dt), (n_paths, n_steps))
        dW2 = rho * dW1 + np.sqrt(1 - rho**2) * dZ
        
        # Initialize
        S = np.zeros((n_paths, n_steps + 1))
        V = np.zeros((n_paths, n_steps + 1))
        S[:, 0] = S0
        V[:, 0] = V0
        
        # Euler-Maruyama with variance floor
        for t in range(n_steps):
            V_pos = np.maximum(V[:, t], EPSILON)
            sqrt_V = np.sqrt(V_pos)
            
            S[:, t + 1] = S[:, t] * np.exp((mu - 0.5 * V_pos) * dt + sqrt_V * dW1[:, t])
            V[:, t + 1] = V[:, t] + kappa * (theta - V_pos) * dt + xi * sqrt_V * dW2[:, t]
            V[:, t + 1] = np.maximum(V[:, t + 1], EPSILON)  # Reflection at 0
        
        # Compute cones
        percentiles = [5, 25, 50, 75, 95]
        cones = {f"p{p}": np.percentile(S, p, axis=0).tolist() for p in percentiles}
        vol_cones = {f"vol_p{p}": (np.sqrt(np.percentile(V, p, axis=0)) * np.sqrt(252)).tolist() for p in percentiles}
        
        terminal = S[:, -1]
        
        return {
            "paths_sample": S[:min(50, n_paths), :].tolist(),
            "vol_paths_sample": np.sqrt(V[:min(20, n_paths), :] * 252).tolist(),
            "time_axis": list(range(n_steps + 1)),
            "cones": cones,
            "vol_cones": vol_cones,
            "terminal_stats": {
                "mean": float(np.mean(terminal)),
                "std": float(np.std(terminal)),
                "skewness": float(stats.skew(terminal)),
                "kurtosis": float(stats.kurtosis(terminal)),
                "var_95": float(np.percentile(terminal, 5)),
                "cvar_95": float(np.mean(terminal[terminal <= np.percentile(terminal, 5)])),
            },
            "model": "Heston",
            "params": {
                "mu": mu, "kappa": kappa, "theta": theta,
                "xi": xi, "rho": rho, "V0": V0
            },
            "feller_condition": bool(2 * kappa * theta > xi**2),
            "likelihood_of_ruin": {
                "ruin_prob_10pct": float(np.mean(terminal < S0 * 0.9) * 100),
                "ruin_prob_25pct": float(np.mean(terminal < S0 * 0.75) * 100),
                "ruin_prob_50pct": float(np.mean(terminal < S0 * 0.5) * 100),
                "heatmap_data": [{"price": float(p), "prob": float(np.mean(terminal < p) * 100)} for p in np.linspace(S0*0.5, S0*1.5, 20)]
            }
        }
    
    def jump_diffusion_paths(
        self,
        S0: float,
        mu: float,
        sigma: float,
        lam: float,
        jump_mean: float,
        jump_std: float,
        T: int = 252,
        n_paths: int = 1000,
        dt: float = 1/252
    ) -> Dict[str, Any]:
        """
        Merton Jump-Diffusion Model.
        dS/S = (mu - lambda*k)*dt + sigma*dW + J*dN
        
        Parameters:
        - lam: Jump intensity (expected jumps per year)
        - jump_mean: Mean of log-jump size
        - jump_std: Std of log-jump size
        """
        n_steps = int(T / dt)
        k = np.exp(jump_mean + 0.5 * jump_std**2) - 1  # Compensator
        
        # Wiener increments
        dW = self.rng.normal(0, np.sqrt(dt), (n_paths, n_steps))
        
        # Poisson jumps
        N = self.rng.poisson(lam * dt, (n_paths, n_steps))
        J = np.zeros((n_paths, n_steps))
        for i in range(n_paths):
            for t in range(n_steps):
                if N[i, t] > 0:
                    J[i, t] = np.sum(self.rng.normal(jump_mean, jump_std, N[i, t]))
        
        # Initialize
        S = np.zeros((n_paths, n_steps + 1))
        S[:, 0] = S0
        
        # Path evolution
        for t in range(n_steps):
            S[:, t + 1] = S[:, t] * np.exp(
                (mu - lam * k - 0.5 * sigma**2) * dt + 
                sigma * dW[:, t] + 
                J[:, t]
            )
        
        # Statistics
        percentiles = [5, 25, 50, 75, 95]
        cones = {f"p{p}": np.percentile(S, p, axis=0).tolist() for p in percentiles}
        
        terminal = S[:, -1]
        jump_counts = np.sum(N, axis=1)
        
        return {
            "paths_sample": S[:min(50, n_paths), :].tolist(),
            "time_axis": list(range(n_steps + 1)),
            "cones": cones,
            "terminal_stats": {
                "mean": float(np.mean(terminal)),
                "std": float(np.std(terminal)),
                "skewness": float(stats.skew(terminal)),
                "kurtosis": float(stats.kurtosis(terminal)),
            },
            "jump_stats": {
                "avg_jumps_per_path": float(np.mean(jump_counts)),
                "max_jumps": int(np.max(jump_counts)),
                "paths_with_jumps_pct": float(np.mean(jump_counts > 0) * 100),
            },
            "model": "Merton Jump-Diffusion",
            "params": {
                "mu": mu, "sigma": sigma, "lambda": lam,
                "jump_mean": jump_mean, "jump_std": jump_std
            }
        }
    
    def probability_of_touch(
        self,
        S0: float,
        target: float,
        stop: float,
        mu: float,
        sigma: float,
        T: int = 21,
        n_paths: int = 10000
    ) -> Dict[str, Any]:
        """
        Calculate probability of hitting target or stop before expiry.
        Uses Monte Carlo simulation.
        """
        dt = 1/252
        n_steps = T
        
        dW = self.rng.normal(0, np.sqrt(dt), (n_paths, n_steps))
        
        S = np.zeros((n_paths, n_steps + 1))
        S[:, 0] = S0
        
        for t in range(n_steps):
            S[:, t + 1] = S[:, t] * np.exp((mu - 0.5 * sigma**2) * dt + sigma * dW[:, t])
        
        # Check touches
        hit_target = np.any(S >= target, axis=1) if target > S0 else np.any(S <= target, axis=1)
        hit_stop = np.any(S <= stop, axis=1) if stop < S0 else np.any(S >= stop, axis=1)
        
        first_target = np.full(n_paths, np.inf)
        first_stop = np.full(n_paths, np.inf)
        
        for i in range(n_paths):
            target_hits = np.where((S[i] >= target) if target > S0 else (S[i] <= target))[0]
            stop_hits = np.where((S[i] <= stop) if stop < S0 else (S[i] >= stop))[0]
            if len(target_hits) > 0:
                first_target[i] = target_hits[0]
            if len(stop_hits) > 0:
                first_stop[i] = stop_hits[0]
        
        target_first = first_target < first_stop
        stop_first = first_stop < first_target
        
        return {
            "prob_target": float(np.mean(hit_target) * 100),
            "prob_stop": float(np.mean(hit_stop) * 100),
            "prob_neither": float(np.mean(~hit_target & ~hit_stop) * 100),
            "prob_target_first": float(np.mean(target_first) * 100),
            "prob_stop_first": float(np.mean(stop_first) * 100),
            "expected_days_to_target": float(np.mean(first_target[first_target < np.inf])) if np.any(first_target < np.inf) else None,
            "expected_days_to_stop": float(np.mean(first_stop[first_stop < np.inf])) if np.any(first_stop < np.inf) else None,
            "inputs": {
                "S0": S0, "target": target, "stop": stop,
                "T_days": T, "mu": mu, "sigma": sigma
            }
        }


# =============================================================================
# MODULE 1.5: RISK COPULAS & TAIL DEPENDENCE
# =============================================================================

class StressTestCopula:
    """
    Implements Section 1.6 of quant.md
    Correlation and Tail Dependency using Gaussian/t-Copulas
    """
    def run_bivariate_stress(self, returns_a: np.ndarray, returns_b: np.ndarray) -> Dict[str, Any]:
        from scipy.stats import norm, t
        
        # 1. Transform to uniform marginals (Probability Integral Transform)
        u = rankdata(returns_a) / (len(returns_a) + 1)
        v = rankdata(returns_b) / (len(returns_b) + 1)
        
        # 2. Estimate Copula Correlation
        corr = np.corrcoef(norm.ppf(u), norm.ppf(v))[0, 1]
        
        # 3. Lower/Upper Tail Dependence (Empirical)
        n = len(u)
        q = 0.05
        lower_tail = np.sum((u <= q) & (v <= q)) / (n * q)
        upper_tail = np.sum((u >= 1-q) & (v >= 1-q)) / (n * q)
        
        return {
            "copula_correlation": float(corr),
            "lower_tail_dependence": float(lower_tail),
            "upper_tail_dependence": float(upper_tail),
            "stress_scenario": "Contagion" if lower_tail > 1.5 * corr else "Normal",
            "diversification_health": float(1 - lower_tail),
            "tail_risk_score": float(lower_tail * 100)
        }


# =============================================================================
# MODULE 1.2: MARKOV REGIME MODELS
# =============================================================================

class MarkovRegimeModel:
    """
    Implements Section 1.2 / 2.8 of quant.md
    Hidden Markov Model for Regime Detection (Bull/Bear/Sideways)
    """
    def detect_regimes(self, returns: np.ndarray, n_states: int = 3) -> Dict[str, Any]:
        from statsmodels.tsa.regime_switching.markov_regression import MarkovRegression
        
        try:
            # Fit Markov Switching Model
            model = MarkovRegression(returns, k_regimes=n_states, trend='c', switching_variance=True)
            res = model.fit()
            
            # Identify current state (highest probability)
            probs_data = np.asarray(res.smoothed_marginal_probabilities)
            last_probs = probs_data[-1]
            current_state = int(np.argmax(last_probs))
            
            # Transition Matrix
            if hasattr(res, 'regime_transition'):
                p_matrix = np.asarray(res.regime_transition)
                if p_matrix.ndim == 3: p_matrix = p_matrix[:, :, -1]
            elif hasattr(res, 'regime_transition_matrix'):
                p_matrix = np.asarray(res.regime_transition_matrix)
                if p_matrix.ndim == 3: p_matrix = p_matrix[:, :, -1]
            else:
                p_matrix = np.eye(n_states)
            
            # Label states by their mean returns
            means = []
            for i in range(n_states):
                # Try common param naming patterns
                p_keys = [f'const[{i}]', f'p[regime={i}].const', f'const.regime.{i}']
                val = 0.0
                for k in p_keys:
                    if k in res.params:
                        val = res.params[k]
                        break
                means.append(val)
            state_labels = []
            for m in means:
                if m > 0.0005: state_labels.append("Bullish")
                elif m < -0.0005: state_labels.append("Bearish")
                else: state_labels.append("Sideways")
            
            return {
                "current_regime": state_labels[current_state],
                "regime_probabilities": last_probs.tolist(),
                "transition_matrix": p_matrix.tolist(),
                "state_definitions": state_labels,
                "regime_stability": float(p_matrix[current_state, current_state]),
                "expected_duration": float(1.0 / (1.0 - p_matrix[current_state, current_state] + EPSILON))
            }
        except Exception as e:
            logger.error(f"Markov detect failed: {e}")
            return {
                "current_regime": "Unknown",
                "regime_probabilities": [1.0, 0.0, 0.0],
                "transition_matrix": np.eye(n_states).tolist(),
                "state_definitions": ["Unknown"] * n_states,
                "regime_stability": 1.0,
                "expected_duration": 0.0
            }


# =============================================================================
# MODULE 2: STATE-SPACE TRACKING (KALMAN FILTER)
# =============================================================================

class KalmanStateTracker:
    """
    Kalman Filter for Price Denoising and Dynamic Beta Estimation.
    
    State-space model:
    x_t = F * x_{t-1} + w_t
    y_t = h(x_t) + v_t
    
    Using Unscented Kalman Filter (UKF) to handle non-linear volatility and curvature 
    as specified in Quantitavetab.md.
    """
    
    def run_ukf_denoise(self, prices: np.ndarray, Q: float = 0.01, R: float = 1.0) -> Dict[str, Any]:
        """
        Unscented Kalman Filter upgrade.
        Captures 'curvature' of trends better than linear KF.
        """
        from filterpy.kalman import UnscentedKalmanFilter as UKF
        from filterpy.kalman import MerweScaledSigmaPoints
        
        def fx(x, dt):
            # State transition: [pos, vel, acc]
            F = np.array([[1, dt, 0.5*dt**2],
                         [0, 1, dt],
                         [0, 0, 1]])
            return F @ x
            
        def hx(x):
            # Measurement: just position
            return np.array([x[0]])
            
        points = MerweScaledSigmaPoints(n=3, alpha=0.1, beta=2., kappa=0)
        ukf = UKF(dim_x=3, dim_z=1, dt=1.0, hx=hx, fx=fx, points=points)
        ukf.x = np.array([prices[0], 0, 0])
        ukf.P *= 0.1
        ukf.R *= R
        ukf.Q *= Q
        
        n = len(prices)
        uxs = np.zeros((n, 3))
        for i in range(n):
            ukf.predict()
            ukf.update(prices[i])
            uxs[i] = ukf.x
            
        # Newtonian Force Vectors (F = m*a)
        forces = uxs[:, 2] # Acceleration is proportional to Force in this model
        
        return {
            "filtered_price": uxs[:, 0].tolist(),
            "velocity": uxs[:, 1].tolist(),
            "acceleration": uxs[:, 2].tolist(),
            "force_vectors": (forces / (np.max(np.abs(forces)) + EPSILON)).tolist(),
            "snr_db": float(10 * np.log10(np.var(uxs[:, 0]) / (np.var(prices - uxs[:, 0]) + EPSILON)))
        }

    def kalman_denoise(
        self,
        prices: np.ndarray,
        Q: float = 0.01,
        R: float = 1.0
    ) -> Dict[str, Any]:
        """
        1D Kalman filter for price denoising.
        Models price as random walk with trend.
        
        State: [level, velocity]
        """
        n = len(prices)
        
        # State transition matrix
        F = np.array([[1, 1], [0, 1]])
        
        # Observation matrix
        H = np.array([[1, 0]])
        
        # Process noise covariance
        Q_mat = Q * np.eye(2)
        
        # Measurement noise variance
        R_mat = np.array([[R]])
        
        # Initialize
        x = np.array([[prices[0]], [0]])  # [level, velocity]
        P = np.eye(2)
        
        # Storage
        filtered_states = np.zeros((n, 2))
        predicted_states = np.zeros((n, 2))
        innovations = np.zeros(n)
        innovation_var = np.zeros(n)
        
        for t in range(n):
            # Predict
            x_pred = F @ x
            P_pred = F @ P @ F.T + Q_mat
            
            predicted_states[t] = x_pred.flatten()
            
            # Update
            y = prices[t]
            y_pred = (H @ x_pred)[0, 0]
            innovation = y - y_pred
            S = (H @ P_pred @ H.T + R_mat)[0, 0]
            
            K = P_pred @ H.T / S
            
            x = x_pred + K * innovation
            P = (np.eye(2) - K @ H) @ P_pred
            
            filtered_states[t] = x.flatten()
            innovations[t] = innovation
            innovation_var[t] = S
        
        # Compute signal-to-noise metrics
        signal_power = np.var(filtered_states[:, 0])
        noise_power = np.var(prices - filtered_states[:, 0])
        snr_db = 10 * np.log10(signal_power / (noise_power + EPSILON))
        
        return {
            "filtered_price": filtered_states[:, 0].tolist(),
            "velocity": filtered_states[:, 1].tolist(),
            "innovations": innovations.tolist(),
            "innovation_std": np.sqrt(innovation_var).tolist(),
            "original_price": prices.tolist(),
            "snr_db": float(snr_db),
            "signal_std": float(np.std(filtered_states[:, 0])),
            "noise_std": float(np.std(prices - filtered_states[:, 0])),
            "params": {"Q": Q, "R": R}
        }
    
    def dynamic_beta(
        self,
        asset_returns: np.ndarray,
        market_returns: np.ndarray,
        Q: float = 0.001,
        R: float = 0.1
    ) -> Dict[str, Any]:
        """
        Time-varying beta estimation using Kalman filter.
        
        Model: r_asset_t = alpha_t + beta_t * r_market_t + epsilon_t
        State: [alpha_t, beta_t]
        """
        n = len(asset_returns)
        
        # State transition (random walk for parameters)
        F = np.eye(2)
        
        # Process noise
        Q_mat = Q * np.eye(2)
        
        # Measurement noise
        R_mat = np.array([[R]])
        
        # Initialize with OLS estimate
        X = np.column_stack([np.ones(n), market_returns])
        try:
            ols_params = np.linalg.lstsq(X, asset_returns, rcond=None)[0]
            x = ols_params.reshape(-1, 1)
        except:
            x = np.array([[0], [1]])
        
        P = np.eye(2) * 0.1
        
        # Storage
        alphas = np.zeros(n)
        betas = np.zeros(n)
        residuals = np.zeros(n)
        beta_std = np.zeros(n)
        
        for t in range(n):
            # Observation matrix depends on market return
            H = np.array([[1, market_returns[t]]])
            
            # Predict
            x_pred = F @ x
            P_pred = F @ P @ F.T + Q_mat
            
            # Update
            y = asset_returns[t]
            y_pred = (H @ x_pred)[0, 0]
            innovation = y - y_pred
            S = (H @ P_pred @ H.T + R_mat)[0, 0]
            
            K = P_pred @ H.T / S
            
            x = x_pred + K * innovation
            P = (np.eye(2) - K @ H) @ P_pred
            
            alphas[t] = x[0, 0]
            betas[t] = x[1, 0]
            residuals[t] = innovation
            beta_std[t] = np.sqrt(P[1, 1])
        
        # Regime detection based on beta stability
        beta_changes = np.abs(np.diff(betas))
        regime_threshold = np.percentile(beta_changes, 90)
        regime_breaks = np.where(beta_changes > regime_threshold)[0]
        
        return {
            "alphas": alphas.tolist(),
            "betas": betas.tolist(),
            "beta_upper": (betas + 2 * beta_std).tolist(),
            "beta_lower": (betas - 2 * beta_std).tolist(),
            "residuals": residuals.tolist(),
            "regime_breaks": regime_breaks.tolist(),
            "current_beta": float(betas[-1]),
            "current_alpha_ann": float(alphas[-1] * 252),
            "beta_stability": float(1 - np.std(betas[-20:]) / (np.std(betas) + EPSILON)),
            "avg_beta": float(np.mean(betas)),
            "max_beta": float(np.max(betas)),
            "min_beta": float(np.min(betas)),
            "params": {"Q": Q, "R": R}
        }
    
    def phase_portrait(
        self,
        prices: np.ndarray,
        window: int = 5
    ) -> Dict[str, Any]:
        """
        Construct phase portrait: Price vs. Price Velocity.
        Used to visualize attractor dynamics.
        """
        # Velocity = smoothed returns
        returns = np.diff(np.log(prices))
        velocity = np.convolve(returns, np.ones(window)/window, mode='valid')
        
        # Align lengths
        n = len(velocity)
        price_aligned = prices[window:][:n]
        
        # Acceleration = change in velocity
        acceleration = np.diff(velocity)
        
        # Orbit expansion/contraction
        radii = np.sqrt(price_aligned**2 + velocity**2)
        radii_change = np.diff(radii)
        expanding = np.mean(radii_change[-10:]) > 0
        
        # Lyapunov-like stability (local divergence rate)
        local_divergence = np.mean(np.abs(radii_change[-20:])) / (np.mean(radii[-20:]) + EPSILON)
        
        return {
            "price": price_aligned.tolist(),
            "velocity": velocity.tolist(),
            "acceleration": acceleration.tolist(),
            "orbit_expanding": bool(expanding),
            "stability_metric": float(1 - min(local_divergence * 100, 1)),
            "current_phase": {
                "price": float(price_aligned[-1]),
                "velocity": float(velocity[-1]),
                "state": "bullish" if velocity[-1] > 0 else "bearish"
            },
            "orbit_stats": {
                "avg_radius": float(np.mean(radii)),
                "radius_volatility": float(np.std(radii)),
            }
        }


# =============================================================================
# MODULE 3: ARBITRAGE MATRIX (COINTEGRATION)
# =============================================================================

class ArbitrageMatrix:
    """
    Cointegration and Mean-Reversion Analysis.
    Implements: Engle-Granger, Johansen, VECM, Half-Life.
    """
    
    def engle_granger(
        self,
        series_a: np.ndarray,
        series_b: np.ndarray,
        alpha: float = 0.05
    ) -> Dict[str, Any]:
        """
        Engle-Granger 2-step cointegration test.
        
        Step 1: OLS regression y = alpha + beta * x + epsilon
        Step 2: ADF test on residuals
        """
        from statsmodels.tsa.stattools import adfuller
        
        # Step 1: Cointegrating regression
        X = np.column_stack([np.ones(len(series_b)), series_b])
        params = np.linalg.lstsq(X, series_a, rcond=None)[0]
        alpha_coef, beta = params[0], params[1]
        
        # Spread (residuals)
        spread = series_a - alpha_coef - beta * series_b
        
        # Step 2: ADF test on spread
        adf_result = adfuller(spread, maxlag=int(np.sqrt(len(spread))))
        adf_stat, p_value = adf_result[0], adf_result[1]
        critical_values = adf_result[4]
        
        # Cointegration conclusion
        is_cointegrated = p_value < alpha
        
        # Z-score of current spread
        z_score = (spread[-1] - np.mean(spread)) / (np.std(spread) + EPSILON)
        
        return {
            "cointegrated": bool(is_cointegrated),
            "adf_stat": float(adf_stat),
            "p_value": float(p_value),
            "critical_values": {k: float(v) for k, v in critical_values.items()},
            "hedge_ratio_beta": float(beta),
            "intercept": float(alpha_coef),
            "spread": spread.tolist(),
            "spread_zscore": float(z_score),
            "spread_mean": float(np.mean(spread)),
            "spread_std": float(np.std(spread)),
            "current_signal": "LONG" if z_score < -2 else ("SHORT" if z_score > 2 else "NEUTRAL")
        }
    
    def johansen_test(
        self,
        data: np.ndarray,
        k_ar_diff: int = 1
    ) -> Dict[str, Any]:
        """
        Johansen cointegration test.
        Tests for cointegration rank in a multivariate system.
        """
        from statsmodels.tsa.vector_ar.vecm import coint_johansen
        
        try:
            result = coint_johansen(data, det_order=0, k_ar_diff=k_ar_diff)
            
            n_vars = data.shape[1]
            trace_stats = result.lr1.tolist()
            trace_crit = result.cvt.tolist()
            eigen_stats = result.lr2.tolist()
            eigen_crit = result.cvm.tolist()
            
            # Determine cointegration rank
            rank = 0
            for i in range(n_vars):
                if trace_stats[i] > trace_crit[i][1]:  # 5% critical value
                    rank += 1
                else:
                    break
            
            # Cointegrating vectors
            coint_vectors = result.evec[:, :max(1, rank)].tolist()
            
            return {
                "rank": rank,
                "trace_stats": trace_stats,
                "trace_critical_5pct": [cv[1] for cv in trace_crit],
                "trace_critical_1pct": [cv[2] for cv in trace_crit],
                "eigenvalue_stats": eigen_stats,
                "cointegrating_vectors": coint_vectors,
                "n_variables": n_vars,
                "conclusion": f"Found {rank} cointegrating relationship(s)" if rank > 0 else "No cointegration found"
            }
        except Exception as e:
            logger.error(f"Johansen test failed: {e}")
            return {"error": str(e), "rank": 0}
    
    def half_life(
        self,
        spread: np.ndarray
    ) -> Dict[str, Any]:
        """
        Estimate half-life of mean reversion using OU process.
        
        dS = theta * (mu - S) * dt + sigma * dW
        Half-life = ln(2) / theta
        """
        # Lag-1 regression: spread_t = a + b * spread_{t-1} + epsilon
        y = spread[1:]
        x = spread[:-1]
        
        X = np.column_stack([np.ones(len(x)), x])
        params = np.linalg.lstsq(X, y, rcond=None)[0]
        b = params[1]
        
        # Mean reversion speed
        theta = -np.log(b) * 252  # Annualized
        
        # Half-life in trading days
        if b > 0 and b < 1:
            hl_days = np.log(2) / (-np.log(b))
        else:
            hl_days = np.inf
        
        # Residual analysis
        residuals = y - X @ params
        residual_std = np.std(residuals)
        
        # Long-term mean
        mu = params[0] / (1 - b) if b != 1 else np.mean(spread)
        
        # Current deviation from mean
        current_deviation = (spread[-1] - mu) / (np.std(spread) + EPSILON)
        
        return {
            "half_life_days": float(hl_days) if hl_days != np.inf else None,
            "theta": float(theta),
            "autoregression_coef": float(b),
            "long_term_mean": float(mu),
            "current_deviation_zscore": float(current_deviation),
            "residual_std": float(residual_std),
            "is_mean_reverting": bool(0 < b < 1),
            "expected_reversion_days": float(hl_days * 2) if hl_days != np.inf else None,  # 90% reversion
        }
    
    def vecm_analysis(
        self,
        data: np.ndarray,
        coint_rank: int = 1,
        k_ar_diff: int = 1
    ) -> Dict[str, Any]:
        """
        Vector Error Correction Model analysis.
        Identifies which asset leads/lags in the cointegrating relationship.
        """
        from statsmodels.tsa.vector_ar.vecm import VECM
        
        try:
            model = VECM(data, k_ar_diff=k_ar_diff, coint_rank=coint_rank)
            result = model.fit()
            
            # Alpha (adjustment coefficients) - who adjusts to restore equilibrium
            alphas = result.alpha
            
            # Beta (cointegrating vectors)
            betas = result.beta
            
            # Gamma (short-run dynamics)
            gammas = result.gamma if hasattr(result, 'gamma') else None
            
            # Determine leader/follower
            # Lower alpha magnitude = leader (doesn't adjust)
            # Higher alpha magnitude = follower (adjusts more)
            alpha_mags = np.abs(alphas[:, 0])
            leader_idx = np.argmin(alpha_mags)
            follower_idx = np.argmax(alpha_mags)
            
            return {
                "alpha_adjustments": alphas.tolist(),
                "beta_cointegrating": betas.tolist(),
                "leader_index": int(leader_idx),
                "follower_index": int(follower_idx),
                "leader_adjustment_speed": float(alpha_mags[leader_idx]),
                "follower_adjustment_speed": float(alpha_mags[follower_idx]),
                "equilibrium_restoration_ratio": float(alpha_mags[follower_idx] / (alpha_mags[leader_idx] + EPSILON)),
                "aic": float(result.aic) if hasattr(result, 'aic') else None,
                "bic": float(result.bic) if hasattr(result, 'bic') else None,
            }
        except Exception as e:
            logger.error(f"VECM analysis failed: {e}")
            return {"error": str(e)}
    
    def optimal_bounds(
        self,
        spread: np.ndarray,
        transaction_cost: float = 0.001
    ) -> Dict[str, Any]:
        """
        Calculate optimal entry/exit bounds for spread trading.
        Based on Ornstein-Uhlenbeck optimal stopping.
        """
        mu = np.mean(spread)
        sigma = np.std(spread)
        
        # Half-life
        hl_result = self.half_life(spread)
        theta = hl_result.get("theta", 1)
        
        if theta <= 0:
            theta = 1  # Default if not mean-reverting
        
        # Optimal bounds (simplified Bertram formula)
        # Entry when spread is k standard deviations from mean
        # k depends on transaction costs and mean-reversion speed
        k_entry = 1.5 + 0.5 * np.log(1 + 100 * transaction_cost)
        k_exit = 0.25
        
        entry_long = mu - k_entry * sigma
        entry_short = mu + k_entry * sigma
        exit_level = mu + k_exit * sigma * np.sign(spread[-1] - mu)
        
        return {
            "entry_long_below": float(entry_long),
            "entry_short_above": float(entry_short),
            "exit_level": float(exit_level),
            "spread_mean": float(mu),
            "spread_std": float(sigma),
            "current_spread": float(spread[-1]),
            "current_zscore": float((spread[-1] - mu) / sigma),
            "optimal_k_entry": float(k_entry),
            "transaction_cost": transaction_cost,
            "current_signal": (
                "ENTER_LONG" if spread[-1] < entry_long else
                "ENTER_SHORT" if spread[-1] > entry_short else
                "HOLD/EXIT"
            )
        }


# =============================================================================
# MODULE 4: SPECTRAL PHYSICS
# =============================================================================

class SpectralPhysics:
    """
    Continuous Wavelet Transform and Chaos Analysis.
    Implements: CWT Scalogram, Lyapunov Exponents, Bifurcation Detection.
    """
    
    def cwt_scalogram(
        self,
        prices: np.ndarray,
        wavelet: str = 'morl',
        scales_max: int = 64
    ) -> Dict[str, Any]:
        """
        Continuous Wavelet Transform for time-frequency analysis.
        
        Parameters:
        - wavelet: 'morl' (Morlet), 'mexh' (Mexican Hat), 'cgau' (Complex Gaussian)
        """
        # Compute returns for stationarity
        returns = np.diff(np.log(prices))
        
        # Define scales (frequencies)
        scales = np.arange(2, scales_max)
        
        # CWT
        try:
            import pywt
            coeffs, freqs = pywt.cwt(returns, scales, wavelet)
            power = np.abs(coeffs) ** 2
        except ImportError:
            # Fallback using scipy
            coeffs = np.zeros((len(scales), len(returns)))
            for i, scale in enumerate(scales):
                # Simple Morlet approximation
                wavelet_len = min(len(returns), int(scale * 8))
                t = np.linspace(-4, 4, wavelet_len)
                morlet = np.exp(-t**2/2) * np.cos(5*t)
                coeffs[i] = np.abs(np.convolve(returns, morlet, mode='same'))
            power = coeffs ** 2
            freqs = 1 / scales
        
        # Convert scales to periods (trading days)
        periods = scales
        
        # Global wavelet power spectrum
        global_power = np.mean(power, axis=1)
        
        # Find dominant periods
        peak_indices = signal.find_peaks(global_power, height=np.mean(global_power))[0]
        dominant_periods = periods[peak_indices][:5].tolist() if len(peak_indices) > 0 else []
        
        # Time-averaged power in bands
        short_term = np.mean(power[scales < 10, :])
        medium_term = np.mean(power[(scales >= 10) & (scales < 30), :])
        long_term = np.mean(power[scales >= 30, :])
        
        # Downsample for payload
        step_t = max(1, len(returns) // 200)
        step_s = max(1, len(scales) // 50)

        # Prepare Heatmap for UI (Time vs Frequency vs Intensity)
        heatmap = []
        for i, t_idx in enumerate(range(0, len(returns), step_t)):
            for j, s_idx in enumerate(range(0, len(scales), step_s)):
                heatmap.append({
                    "t": t_idx,
                    "p": float(periods[s_idx]),
                    "v": float(power[s_idx, t_idx])
                })
        
        return {
            "heatmap": heatmap,
            "scalogram": power[::step_s, ::step_t].tolist(),
            "scales": scales[::step_s].tolist(),
            "periods": periods[::step_s].tolist(),
            "time_axis": list(range(0, len(returns), step_t)),
            "global_power": global_power.tolist(),
            "dominant_periods": dominant_periods,
            "power_bands": {
                "short_term": float(short_term),
                "medium_term": float(medium_term),
                "long_term": float(long_term),
            },
            "wavelet": wavelet,
            "interpretation": {
                "trend_strength": "strong" if long_term > medium_term else "weak",
                "swing_activity": "high" if medium_term > short_term * 0.8 else "low",
                "noise_level": "high" if short_term > long_term * 2 else "moderate",
            }
        }
    
    def lyapunov_exponent(
        self,
        prices: np.ndarray,
        embedding_dim: int = 3,
        tau: int = 1,
        divergence_steps: int = 10
    ) -> Dict[str, Any]:
        """
        Estimate largest Lyapunov exponent using Rosenstein algorithm.
        Measures chaos/predictability of the price series.
        
        Lambda > 0: Chaotic (unpredictable)
        Lambda ~ 0: Neutral
        Lambda < 0: Stable (predictable)
        """
        # Use log returns
        series = np.diff(np.log(prices))
        n = len(series)
        
        # Create embedded vectors
        m = embedding_dim
        N_vectors = n - (m - 1) * tau
        if N_vectors < divergence_steps * 2:
            return {"error": "Series too short for embedding"}
        
        X = np.zeros((N_vectors, m))
        for i in range(m):
            X[:, i] = series[i*tau:i*tau + N_vectors]
        
        # Find nearest neighbors (excluding temporal neighbors)
        divergence = np.zeros((N_vectors - divergence_steps, divergence_steps))
        
        for i in range(N_vectors - divergence_steps):
            # Find nearest neighbor (not within 10 steps)
            distances = np.linalg.norm(X - X[i], axis=1)
            distances[max(0, i-10):min(N_vectors, i+10)] = np.inf
            j = np.argmin(distances)
            
            if distances[j] < EPSILON:
                continue
            
            # Track divergence
            for k in range(divergence_steps):
                if i + k < N_vectors and j + k < N_vectors:
                    d_k = np.linalg.norm(X[i + k] - X[j + k])
                    if d_k > EPSILON:
                        divergence[i, k] = np.log(d_k)
        
        # Average divergence
        avg_divergence = np.mean(divergence, axis=0)
        
        # Fit line to get Lyapunov exponent
        valid_mask = ~np.isnan(avg_divergence) & ~np.isinf(avg_divergence)
        if np.sum(valid_mask) < 3:
            return {"error": "Could not compute Lyapunov exponent"}
        
        t = np.arange(divergence_steps)[valid_mask]
        y = avg_divergence[valid_mask]
        slope, intercept = np.polyfit(t, y, 1)
        
        lambda_1 = slope * 252  # Annualize
        
        # Predictability horizon (time until uncertainty doubles)
        if lambda_1 > 0:
            prediction_horizon = np.log(2) / lambda_1 * 252  # In trading days
        else:
            prediction_horizon = np.inf
        
        return {
            "lyapunov_exponent": float(lambda_1),
            "prediction_horizon_days": float(prediction_horizon) if prediction_horizon != np.inf else None,
            "chaos_level": (
                "highly_chaotic" if lambda_1 > 0.5 else
                "chaotic" if lambda_1 > 0.1 else
                "edge_of_chaos" if lambda_1 > 0 else
                "stable"
            ),
            "divergence_curve": avg_divergence.tolist(),
            "embedding_dim": embedding_dim,
            "time_delay": tau,
            "interpretation": (
                "Market is in chaos - predictions unreliable beyond "
                f"{max(1, int(prediction_horizon))} days"
                if lambda_1 > 0 else
                "Market shows stable patterns - predictions may be reliable"
            )
        }
    
    def bifurcation_distance(
        self,
        prices: np.ndarray,
        window: int = 60
    ) -> Dict[str, Any]:
        """
        Measure distance to bifurcation (regime change).
        Uses variance and autocorrelation as early warning signals.
        
        Near bifurcation:
        - Variance increases
        - Autocorrelation increases (critical slowing down)
        """
        returns = np.diff(np.log(prices))
        n = len(returns)
        
        if n < window * 2:
            return {"error": "Series too short"}
        
        # Rolling statistics
        rolling_var = np.zeros(n - window + 1)
        rolling_autocorr = np.zeros(n - window + 1)
        
        for i in range(n - window + 1):
            segment = returns[i:i + window]
            rolling_var[i] = np.var(segment)
            if len(segment) > 1:
                rolling_autocorr[i] = np.corrcoef(segment[:-1], segment[1:])[0, 1]
        
        # Normalize to baseline (first half average)
        baseline_idx = len(rolling_var) // 2
        var_baseline = np.mean(rolling_var[:baseline_idx])
        autocorr_baseline = np.mean(rolling_autocorr[:baseline_idx])
        
        var_ratio = rolling_var / (var_baseline + EPSILON)
        autocorr_change = rolling_autocorr - autocorr_baseline
        
        # Bifurcation score (0-100)
        # High variance + increasing autocorrelation = near bifurcation
        current_var_ratio = var_ratio[-1]
        current_autocorr_change = autocorr_change[-1]
        
        bifurcation_score = min(100, max(0,
            25 * (current_var_ratio - 1) +  # Variance contribution
            50 * max(0, current_autocorr_change) +  # Autocorrelation contribution
            25 * (np.std(var_ratio[-10:]) / (np.std(var_ratio) + EPSILON))  # Recent volatility of variance
        ))
        
        # Trend in warning signals
        var_trend = np.polyfit(np.arange(min(20, len(var_ratio))), var_ratio[-20:], 1)[0]
        autocorr_trend = np.polyfit(np.arange(min(20, len(autocorr_change))), autocorr_change[-20:], 1)[0]
        
        return {
            "bifurcation_score": float(bifurcation_score),
            "variance_ratio": var_ratio.tolist(),
            "autocorrelation_deviation": autocorr_change.tolist(),
            "current_variance_ratio": float(current_var_ratio),
            "current_autocorr_change": float(current_autocorr_change),
            "variance_trend": float(var_trend),
            "autocorr_trend": float(autocorr_trend),
            "warning_level": (
                "CRITICAL" if bifurcation_score > 80 else
                "HIGH" if bifurcation_score > 60 else
                "ELEVATED" if bifurcation_score > 40 else
                "NORMAL"
            ),
            "interpretation": (
                "System approaching critical transition - high probability of regime change"
                if bifurcation_score > 60 else
                "Early warning signals detected - monitor closely"
                if bifurcation_score > 40 else
                "System appears stable"
            )
        }
    
    def spectral_entropy(
        self,
        prices: np.ndarray,
        nperseg: int = 64
    ) -> Dict[str, Any]:
        """
        Compute spectral entropy - measure of signal complexity/randomness.
        
        Low entropy: Regular, periodic patterns
        High entropy: Random, unpredictable
        """
        returns = np.diff(np.log(prices))
        
        # Power spectral density
        freqs, psd = signal.welch(returns, nperseg=min(nperseg, len(returns) // 2))
        
        # Normalize to probability distribution
        psd_norm = psd / (np.sum(psd) + EPSILON)
        
        # Shannon entropy
        entropy = -np.sum(psd_norm * np.log(psd_norm + EPSILON))
        
        # Maximum possible entropy (uniform distribution)
        max_entropy = np.log(len(psd))
        
        # Normalized entropy (0 = periodic, 1 = random)
        normalized_entropy = entropy / max_entropy
        
        # Dominant frequency
        dominant_freq_idx = np.argmax(psd[1:]) + 1  # Exclude DC
        dominant_period = 1 / freqs[dominant_freq_idx] if freqs[dominant_freq_idx] > 0 else np.inf
        
        return {
            "spectral_entropy": float(entropy),
            "normalized_entropy": float(normalized_entropy),
            "frequencies": freqs.tolist(),
            "power_spectrum": psd.tolist(),
            "dominant_period_days": float(dominant_period),
            "randomness_level": (
                "highly_random" if normalized_entropy > 0.9 else
                "random" if normalized_entropy > 0.7 else
                "mixed" if normalized_entropy > 0.5 else
                "structured" if normalized_entropy > 0.3 else
                "highly_structured"
            ),
            "tradability": (
                "LOW - market is too random" if normalized_entropy > 0.85 else
                "MODERATE - some patterns exist" if normalized_entropy > 0.6 else
                "HIGH - clear patterns detected"
            )
        }


# =============================================================================
# MAIN ENGINE
# =============================================================================

class QuantitativeEngine:
    """
    Main interface for all quantitative modules.
    Unified interface for SDE, Kalman, Cointegration, Spectral, Markov, and Copula analysis.
    """
    def __init__(self):
        self.sde = SDEPathEngine()
        self.kalman = KalmanStateTracker()
        self.arbitrage = ArbitrageMatrix()
        self.spectral = SpectralPhysics()
        self.markov = MarkovRegimeModel()
        self.copula = StressTestCopula()
        self._data_engine = None
    
    @property
    def data_engine(self):
        if self._data_engine is None:
            from app.services.data_engine import engine
            self._data_engine = engine
        return self._data_engine

    def get_price_data(self, ticker: str, lookback: int = 504) -> np.ndarray:
        df = self.data_engine.get_full_ohlcv(ticker, lookback)
        if df.empty:
            raise ValueError(f"No price data found for {ticker}")
        return df["Close"].dropna().values

    def run_sde_analysis(self, ticker: str, model: str = 'heston', horizon: int = 63, n_paths: int = 1000, lookback: int = 252) -> Dict[str, Any]:
        key = f"sde_{ticker}_{model}_{horizon}_{n_paths}_{lookback}"
        if key in QUANT_CACHE: return QUANT_CACHE[key]
        
        prices = self.get_price_data(ticker, lookback)
        S0 = float(prices[-1])
        returns = np.diff(np.log(prices))
        mu = float(np.mean(returns) * 252)
        sigma = float(np.std(returns) * np.sqrt(252))
        
        if model == 'gbm':
            res = self.sde.gbm_paths(S0, mu, sigma, T=horizon, n_paths=n_paths)
        elif model == 'heston':
            res = self.sde.heston_paths(S0, sigma**2, mu, kappa=2.0, theta=sigma**2, xi=0.1, rho=-0.7, T=horizon, n_paths=n_paths)
        else: # jump
            res = self.sde.jump_diffusion_paths(S0, mu, sigma, lam=1.0, jump_mean=-0.01, jump_std=0.05, T=horizon, n_paths=n_paths)
            
        res["market_regime"] = self.markov.detect_regimes(returns)
        QUANT_CACHE[key] = res
        return res

    def run_kalman_analysis(self, ticker: str, benchmark: str = 'SPY', Q: float = 0.01, R: float = 1.0, lookback: int = 252) -> Dict[str, Any]:
        key = f"kalman_{ticker}_{benchmark}_{Q}_{R}_{lookback}"
        if key in QUANT_CACHE: return QUANT_CACHE[key]

        prices = self.get_price_data(ticker, lookback)
        # Using UKF (Unscented Kalman Filter) as per Maxed Spec
        denoise = self.kalman.run_ukf_denoise(prices, Q=Q, R=R)
        denoise["original_price"] = prices.tolist()  # Include raw prices for frontend comparison
        phase = self.kalman.phase_portrait(prices)
        
        dynamic_beta = None
        try:
            mkt_prices = self.get_price_data(benchmark, lookback)
            min_l = min(len(prices), len(mkt_prices))
            r_a = np.diff(np.log(prices[-min_l:]))
            r_m = np.diff(np.log(mkt_prices[-min_l:]))
            dynamic_beta = self.kalman.dynamic_beta(r_a, r_m, Q=0.001, R=R/10)
        except Exception:
            dynamic_beta = None
            
        res = {"denoise": denoise, "phase_portrait": phase, "dynamic_beta": dynamic_beta, "ticker": ticker, "benchmark": benchmark}
        QUANT_CACHE[key] = res
        return res

    def run_cointegration_analysis(self, ticker_a: str, ticker_b: str, lookback: int = 504) -> Dict[str, Any]:
        key = f"arb_{ticker_a}_{ticker_b}_{lookback}"
        if key in QUANT_CACHE: return QUANT_CACHE[key]

        pa = self.get_price_data(ticker_a, lookback)
        pb = self.get_price_data(ticker_b, lookback)
        min_l = min(len(pa), len(pb))
        pa, pb = pa[-min_l:], pb[-min_l:]
        
        eg = self.arbitrage.engle_granger(pa, pb)
        spread = np.array(eg['spread'])
        res = {
            "engle_granger": eg,
            "half_life": self.arbitrage.half_life(spread),
            "optimal_bounds": self.arbitrage.optimal_bounds(spread),
            "tail_risk": self.copula.run_bivariate_stress(np.diff(np.log(pa)), np.diff(np.log(pb))),
            "prices_a": pa.tolist(), "prices_b": pb.tolist(), "ticker_a": ticker_a, "ticker_b": ticker_b
        }
        QUANT_CACHE[key] = res
        return res

    def run_spectral_analysis(self, ticker: str, lookback: int = 504) -> Dict[str, Any]:
        key = f"spec_{ticker}_{lookback}"
        if key in QUANT_CACHE: return QUANT_CACHE[key]

        prices = self.get_price_data(ticker, lookback)
        res = {
            "scalogram": self.spectral.cwt_scalogram(prices),
            "lyapunov": self.spectral.lyapunov_exponent(prices),
            "bifurcation": self.spectral.bifurcation_distance(prices),
            "entropy": self.spectral.spectral_entropy(prices),
            "ticker": ticker
        }
        QUANT_CACHE[key] = res
        return res

# Global Singleton
quant_engine = QuantitativeEngine()
