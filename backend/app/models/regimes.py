import pandas as pd
import numpy as np
from hmmlearn.hmm import GaussianHMM
import logging

logger = logging.getLogger(__name__)

def detect_regimes(returns: pd.Series, n_states: int = 2) -> dict:
    """
    Fits a Gaussian HMM to detect market regimes.
    
    Args:
        returns (pd.Series): Daily returns.
        n_states (int): Number of regimes (e.g., 2 for Low/High Vol).
        
    Returns:
        dict: States, probabilities, and regime stats.
    """
    try:
        # Prepare data
        X = returns.values.reshape(-1, 1)
        
        # Fit HMM
        # We use a simple Gaussian HMM
        model = GaussianHMM(n_components=n_states, covariance_type="full", n_iter=100, random_state=42)
        model.fit(X)
        
        # Predict states
        hidden_states = model.predict(X)
        
        # Get probabilities
        probs = model.predict_proba(X)
        
        # Analyze regimes to label them (e.g., by volatility)
        regime_stats = {}
        for i in range(n_states):
            mask = (hidden_states == i)
            r = returns[mask]
            regime_stats[i] = {
                "mean": r.mean() * 252,
                "volatility": r.std() * np.sqrt(252),
                "count": int(mask.sum())
            }
            
        # Sort states by volatility to have consistent labeling (0=Low Vol, 1=High Vol)
        sorted_states = sorted(regime_stats.keys(), key=lambda k: regime_stats[k]['volatility'])
        mapping = {old: new for new, old in enumerate(sorted_states)}
        
        # Remap states
        mapped_states = np.array([mapping[s] for s in hidden_states])
        mapped_probs = probs[:, sorted_states] # Reorder columns
        
        return {
            "states": mapped_states.tolist(),
            "probs": mapped_probs.tolist(),
            "regime_stats": {mapping[k]: v for k, v in regime_stats.items()},
            "dates": returns.index.strftime('%Y-%m-%d').tolist()
        }
    except Exception as e:
        logger.error(f"HMM fit failed: {e}")
        return {}
