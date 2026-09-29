
import numpy as np
import pandas as pd
import polars as pl
from datetime import datetime, timedelta
from typing import List, Dict, Any, Optional
from sklearn.decomposition import PCA
from hmmlearn.hmm import GaussianHMM
from scipy.stats import entropy, percentileofscore
import logging
import os

# Internal services
from app.services.data_engine import DataEngine
from app.services.regimes_intelligence import sanitize_dict
from app.services.volatility_intelligence import compute_hurst

logger = logging.getLogger(__name__)

# --- Configuration ---
PEAK_LOOKBACK_DAYS = 500
CALIBRATION_DAYS = 252
HMM_STATES = 4

class RegimePeakEngine:
    def __init__(self):
        self.de = DataEngine()
        
    def _get_universe_returns(self, mode: str, window_years: int = 1) -> pd.DataFrame:
        """Fetch returns matrix for a given market universe."""
        universe_key = "india_nse" if mode == "INDIA" else "us_equities"
        tickers = self.de.get_tickers_for_universe(universe_key)[:60] 
        benchmark = "^NSEI" if mode == "INDIA" else "SPY"
        
        # Ensure benchmark is in the list
        if benchmark not in tickers:
            tickers = [benchmark] + tickers
            
        lookback_days = (window_years * 252) + 60
        return self.de.get_returns_matrix(
            tickers=tickers,
            lookback_days=lookback_days,
            method="simple"
        )

    def compute_integrity_peak(self, mode: str, returns: pd.DataFrame) -> Dict[str, Any]:
        """PCA-based Structural Integrity Analysis."""
        if returns.empty: return {"error": "Insufficient data"}
        
        # 1. Rolling Absorption Ratio (20-day window)
        absorption_history = []
        window_size = 60
        
        # For performance, we compute rolling PCA efficiently or just enough samples
        dates = returns.index[window_size:]
        # Cap at 500 samples for UI performance but ensure we cover the whole window
        max_samples = 500
        step = max(1, len(dates) // max_samples)
        
        for i in range(0, len(dates), step):
            d = dates[i]
            window_ret = returns.loc[:d].tail(window_size)
            if window_ret.shape[1] < 2: continue
            
            pca = PCA(n_components=2)
            pca.fit(window_ret.fillna(0))
            
            exp_var = pca.explained_variance_ratio_
            absorption_history.append({
                "t": d.strftime("%Y-%m-%d"),
                "absorption": float(exp_var[0]),
                "spectralGap": float(exp_var[0] - exp_var[1]),
                "coherence": float(1.0 - (exp_var[1] / exp_var[0]))
            })
            
        # 2. Final PCA for Ticker Table
        final_pca = PCA(n_components=1)
        final_pca.fit(returns.tail(window_size).fillna(0))
        loadings = final_pca.components_[0]
        
        ticker_table = []
        # Final ticker table metrics
        avg_ret = returns.mean(axis=1)
        for i, symbol in enumerate(returns.columns):
            if i >= len(loadings): break
            ticker_table.append({
                "ticker": symbol,
                "eigenWeight": float(loadings[i]),
                "correlation": float(returns[symbol].corr(avg_ret)),
                "coherenceDelta": float(returns[symbol].rolling(20).corr(avg_ret).diff().iloc[-1]) if len(returns) > 21 else 0.0
            })
            
        return {
            "history": absorption_history,
            "alignmentScore": float(absorption_history[-1]["absorption"] * 100 if absorption_history else 50),
            "tickerTable": sorted(ticker_table, key=lambda x: -abs(x["eigenWeight"]))[:50]
        }

    def compute_mass_flow_peak(self, mode: str, returns: pd.DataFrame) -> Dict[str, Any]:
        """HMM Probability Mass Flow."""
        benchmark = "^NSEI" if mode == "INDIA" else "SPY"
        if benchmark not in returns.columns:
            # Fallback to first column if benchmark missing
            benchmark = returns.columns[0]
            
        series = returns[benchmark].fillna(0).values.reshape(-1, 1)
        # Add tiny jitter to prevent singular covariance
        series += np.random.normal(0, 1e-6, series.shape)
        
        # Fit HMM - Reduced iterations for speed
        model = GaussianHMM(n_components=HMM_STATES, covariance_type="full", n_iter=20, tol=1e-2)
        model.fit(series)
        
        # Sort states by mean return (Calm to Crisis)
        order = np.argsort(model.means_.flatten())
        
        posteriors = model.predict_proba(series)
        posteriors = posteriors[:, order]
        
        history = []
        dates = returns.index
        step = max(1, len(dates) // 500)
        for i in range(0, len(dates), step):
            d = dates[i]
            history.append({
                "t": d.strftime("%Y-%m-%d"),
                "probs": posteriors[i].tolist(),
                "entropy": float(-np.sum(posteriors[i] * np.log(posteriors[i] + 1e-10))),
                "massVel": float(0.5 * np.sum(np.abs(posteriors[i] - posteriors[i-1]))) if i > 0 else 0
            })
            
        # Transmat (Transition Matrix)
        transmat = model.transmat_[np.ix_(order, order)]
        
        # Ticker table: Regime Beta
        ticker_table = []
        latest_state = int(np.argmax(posteriors[-1]))
        
        for symbol in returns.columns[:50]:
            # Simple regression for regime beta
            beta = float(returns[symbol].corr(returns[benchmark]))
            ticker_table.append({
                "ticker": symbol,
                "regimeBeta": beta,
                "fidelity": float(abs(beta) * 100),
                "flowIntensity": float(returns[symbol].abs().rolling(20).mean().iloc[-1] * 1000) # Proxy for activity
            })
            
        return {
            "history": history, # Full history for the window
            "transitionMatrix": transmat.tolist(),
            "currentState": latest_state,
            "tickerTable": ticker_table
        }

    def compute_reflexivity_peak(self, mode: str, returns: pd.DataFrame) -> Dict[str, Any]:
        """Reflexivity & Perception Warp."""
        benchmark = "^NSEI" if mode == "INDIA" else "SPY"
        if benchmark not in returns.columns: benchmark = returns.columns[0]
        
        # Synthetic Invariant (Real World Data)
        price = (1 + returns[benchmark]).cumprod()
        rolling_mean = price.rolling(100).mean()
        warp_ratio = (price / rolling_mean - 1) * 100
        
        # Show history for the selected window
        history = []
        b_series = returns[benchmark]
        # Sample for performance if window is large
        dates = returns.index
        step = max(1, len(dates) // 500)
        for i in range(0, len(dates), step):
            d = dates[i]
            history.append({
                "t": d.strftime("%Y-%m-%d"),
                "warp": float(warp_ratio.loc[d]) if not np.isnan(warp_ratio.loc[d]) else 0.0,
                "reflexivity": float(b_series.loc[:d].tail(20).autocorr() * 100) # Real gain
            })
            
        ticker_table = []
        for symbol in returns.columns[:50]:
            s_price = (1 + returns[symbol]).cumprod()
            s_warp = (s_price / s_price.rolling(50).mean() - 1) * 100
            ticker_table.append({
                "ticker": symbol,
                "warpScore": float(s_warp.iloc[-1]) if not np.isnan(s_warp.iloc[-1]) else 0.0,
                "denialHeat": float(returns[symbol].autocorr(lag=1) * 100),
                "squeezePotential": float(percentileofscore(returns[symbol].rolling(20).std(), returns[symbol].iloc[-1]))
            })
            
        return {
            "history": history,
            "masterWarp": float(warp_ratio.iloc[-1]) if not np.isnan(warp_ratio.iloc[-1]) else 0.0,
            "tickerTable": ticker_table
        }

    def compute_fragility_peak(self, mode: str, returns: pd.DataFrame) -> Dict[str, Any]:
        """Mechanical Fragility & Liquidity Air Pockets."""
        if returns.empty: return {"error": "No data"}
        
        vol = returns.iloc[:, 0].rolling(20).std() * np.sqrt(252)
        
        history = []
        dates = returns.index
        step = max(1, len(dates) // 500)
        for i in range(0, len(dates), step):
            d = dates[i]
            history.append({
                "t": d.strftime("%Y-%m-%d"),
                "fragility": float(vol.loc[d] * 100) if not np.isnan(vol.loc[d]) else 0.0,
                "liquidityGap": float(returns.loc[:d].tail(20).std().mean() * 1000)
            })
            
        ticker_table = []
        for symbol in returns.columns[:50]:
            t_vol = returns[symbol].rolling(20).std() * np.sqrt(252)
            ticker_table.append({
                "ticker": symbol,
                "liquidityRisk": float(100 - (returns[symbol].abs() > 0).rolling(20).mean().iloc[-1] * 100),
                "convexityStress": float(t_vol.iloc[-1] / (vol.iloc[-1] + 1e-6)),
                "flashCrashProb": float(max(0, returns[symbol].iloc[-1] / (t_vol.iloc[-1] / np.sqrt(252) + 1e-6) * -1))
            })
            
        return {
            "history": history,
            "fragilityScore": float(vol.iloc[-1] * 100 if not np.isnan(vol.iloc[-1]) else 50),
            "tickerTable": ticker_table
        }

    def compute_nonlinearity_peak(self, mode: str, returns: pd.DataFrame) -> Dict[str, Any]:
        """Chaos & Entropy Engine."""
        if returns.empty: return {"error": "No data"}
        
        benchmark = "^NSEI" if mode == "INDIA" else "SPY"
        if benchmark not in returns.columns: benchmark = returns.columns[0]
        
        b_series = returns[benchmark].dropna()
        
        history = []
        # Calculate rolling entropy and chaos
        window_size = 60
        # Sample for visualization smoothness (max 500 points)
        total_obs = len(b_series)
        dates = b_series.index[window_size:]
        step = max(1, len(dates) // 500)
        
        for i in range(0, len(dates), step):
            d = dates[i]
            sample = b_series.loc[:d].tail(window_size)
            if len(sample) < 20: continue
            
            # 1. Shannon Entropy (quantifies distribution complexity)
            hist, _ = np.histogram(sample, bins=10, density=True)
            ent_val = entropy(hist + 1e-10)
            
            # 2. Chaos (Proxied by Rolling Kurtosis - measures fat-tail "noise")
            chaos_val = float(sample.kurt())
            
            history.append({
                "t": d.strftime("%Y-%m-%d"),
                "entropy": float(ent_val),
                "chaos": float(abs(chaos_val) * 10) # Scaled for visualization normalization
            })
            
        # 3. Bifurcation Distance (Structural Shift Measure)
        # Delta between entropy of short-term (20d) and medium-term (100d) dynamics
        s_tail = b_series.tail(20)
        l_tail = b_series.tail(100)
        
        s_hist, _ = np.histogram(s_tail, bins=10, density=True)
        l_hist, _ = np.histogram(l_tail, bins=10, density=True)
        
        b_dist = abs(entropy(s_hist + 1e-10) - entropy(l_hist + 1e-10)) * 100
        
        ticker_table = []
        for symbol in returns.columns[:50]:
            sym_tail = returns[symbol].tail(100).dropna()
            if sym_tail.empty: continue
            
            hist_t, _ = np.histogram(sym_tail.tail(20), bins=10, density=True)
            ticker_table.append({
                "ticker": symbol,
                "entropyPulse": float(entropy(hist_t + 1e-10)),
                "hurstExponent": float(compute_hurst(sym_tail)),
                "chaosCoefficient": float(sym_tail.tail(20).kurt())
            })
            
        # Numerical cleanup
        for t in ticker_table:
            for k, v in t.items():
                if isinstance(v, float) and (np.isnan(v) or np.isinf(v)):
                    t[k] = 0.0

        return {
            "history": history,
            "bifurcationDistance": float(b_dist) if not np.isnan(b_dist) else 0.0,
            "tickerTable": ticker_table
        }

    def compute_governor_peak(self, mode: str, returns: pd.DataFrame, 
                             integrity: Dict, mass_flow: Dict, reflexivity: Dict,
                             fragility: Dict, nonlinearity: Dict) -> Dict[str, Any]:
        """The Master System Governor synthesis."""
        # Weighted synthesis of all 5 pillars
        try:
            # Helper to safely get score
            def get_score(d, key, default=50):
                val = d.get(key, default)
                return float(val) if not (np.isnan(val) or np.isinf(val)) else default

            # Normalize all pillars to 0-1 (Stability oriented)
            s_integrity = get_score(integrity, "alignmentScore") / 100.0
            
            # Mass Flow Entropy (Max ~1.38 for 4 states)
            mf_history = mass_flow.get("history", [])
            last_entropy = mf_history[-1].get("entropy", 0.7) if mf_history else 0.7
            s_entropy = 1.0 - (min(1.38, last_entropy) / 1.38)
            
            # Reflexivity (Warp > 0 means over-extended/bubbles)
            warp = get_score(reflexivity, "masterWarp", 0)
            s_reflex = max(0, 1.0 - (abs(warp) / 20.0)) # Stability decays as warp exceeds 20%
            
            # Fragility
            s_fragility = 1.0 - (get_score(fragility, "fragilityScore") / 100.0)
            
            # Nonlinearity (Bifurcation Distance)
            b_dist = get_score(nonlinearity, "bifurcationDistance", 10)
            s_nonlin = max(0, 1.0 - (b_dist / 50.0))
            
            # Master Synthesis (0-100)
            # Weights: Integrity (25%), Entropy (20%), Reflexivity (15%), Fragility (20%), Nonlinearity (20%)
            stability_index = (
                s_integrity * 0.25 + 
                s_entropy * 0.20 + 
                s_reflex * 0.15 + 
                s_fragility * 0.20 + 
                s_nonlin * 0.20
            ) * 100
            
            stability_index = float(np.clip(stability_index, 0, 100))
            
            state = "NOMINAL"
            if stability_index < 35: state = "CRITICAL"
            elif stability_index < 60: state = "CAUTION"
            
            # Dynamic Hedges
            hedges = [
                {"asset": "GOLD", "efficiency": int(min(98, 70 + (100-stability_index)*0.3))},
                {"asset": "USDINR" if mode == "INDIA" else "US-10Y", "efficiency": int(min(95, 60 + (100-stability_index)*0.2))},
                {"asset": "VIX" if mode == "US" else "INDIA-VIX", "efficiency": int(min(99, 40 + (100-stability_index)*0.5))}
            ]
            
            # Ticker Table: Stability contribution per ticker
            ticker_table = []
            for symbol in returns.columns[:30]:
                # Contribution = low correlation to general fragility
                sym_cor = returns[symbol].corr(returns.mean(axis=1))
                ticker_table.append({
                    "ticker": symbol, 
                    "signal": "OFF" if stability_index > 50 else "ON", 
                    "severity": "LOW" if stability_index > 70 else "HIGH", 
                    "action": "HOLD" if stability_index > 55 else "TRIM" if stability_index > 40 else "REDUCE"
                })
            
            return {
                "stabilityIndex": float(stability_index),
                "state": state,
                "hedges": hedges,
                "tickerTable": ticker_table
            }
        except Exception as e:
            logger.error(f"Governor compute error: {e}")
            import traceback
            logger.error(traceback.format_exc())
            return {"error": str(e), "stabilityIndex": 50.0, "state": "UNKNOWN"}

    def run_all_pillars(self, mode: str, window_years: int = 1) -> Dict[str, Any]:
        """Orchestrate all 6 pillars with dynamic lookback."""
        logger.info(f"Running Regime Peak Engine for {mode} | Window: {window_years}Y")
        
        # Fetch returns matrix
        returns = self._get_universe_returns(mode, window_years)
        
        if returns.empty:
            return {"error": "No market data found for this universe"}
            
        # Filter returns based on window_years 
        days = window_years * 252
        returns = returns.tail(days)
        
        # Compute in order to allow synthesis
        integrity = self.compute_integrity_peak(mode, returns)
        mass_flow = self.compute_mass_flow_peak(mode, returns)
        reflexivity = self.compute_reflexivity_peak(mode, returns)
        fragility = self.compute_fragility_peak(mode, returns)
        nonlinearity = self.compute_nonlinearity_peak(mode, returns)
        
        # Governor synthesizes the others
        governor = self.compute_governor_peak(mode, returns, integrity, mass_flow, reflexivity, fragility, nonlinearity)
        
        return sanitize_dict({
            "mode": mode,
            "window_years": window_years,
            "asOf": datetime.now().isoformat(),
            "integrity": integrity,
            "massFlow": mass_flow,
            "reflexivity": reflexivity,
            "fragility": fragility,
            "nonlinearity": nonlinearity,
            "governor": governor
        })


