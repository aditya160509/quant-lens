"""
Portfolio Regimes Service - Features 11-12
Category 3: Regimes & Scenarios
"""
import numpy as np
import pandas as pd
from datetime import datetime
from typing import List, Dict, Optional, Tuple
import yfinance as yf
import logging

from app.models.portfolio_models import (
    Position, RegimeType, Quality,
    RegimeState, RegimeConditionalStats, RegimeOutput,
    ShockImpact, ShockPropagationResult
)
from app.services.portfolio_core import (
    log_returns, realized_volatility, z_score, 
    ledoit_wolf_shrinkage, sample_correlation
)

logger = logging.getLogger(__name__)


# =============================================================================
# REGIME CLASSIFICATION
# =============================================================================

def _get_market_data(period: str = "2y") -> pd.DataFrame:
    """Get market data for regime classification."""
    try:
        spy = yf.Ticker("SPY")
        vix = yf.Ticker("^VIX")
        
        spy_hist = spy.history(period=period)
        vix_hist = vix.history(period=period)
        
        data = pd.DataFrame({
            "spy_close": spy_hist['Close'],
            "spy_volume": spy_hist['Volume'],
            "vix": vix_hist['Close']
        }).dropna()
        
        if len(data) > 20:
            data['spy_returns'] = log_returns(data['spy_close'])
            data['spy_vol_20d'] = data['spy_returns'].rolling(20).std() * np.sqrt(252)
            data['spy_momentum'] = data['spy_close'].pct_change(20)
            data['volume_ratio'] = data['spy_volume'] / data['spy_volume'].rolling(50).mean()
        
        return data
    except Exception as e:
        logger.warning(f"Failed to get market data: {e}")
        return pd.DataFrame()


def compute_regime_features() -> Dict[str, float]:
    """Compute z-score normalized regime features."""
    data = _get_market_data()
    
    if len(data) < 50:
        return {
            "volatility_z": 0,
            "momentum_z": 0,
            "vix_z": 0,
            "volume_z": 0
        }
    
    # Latest values
    latest = data.iloc[-1]
    
    # Z-scores
    vol_z = z_score(data['spy_vol_20d'].dropna())
    mom_z = z_score(data['spy_momentum'].dropna())
    vix_z = z_score(data['vix'].dropna())
    vol_ratio_z = z_score(data['volume_ratio'].dropna())
    
    return {
        "volatility_z": vol_z,
        "momentum_z": mom_z,
        "vix_z": vix_z,
        "volume_z": vol_ratio_z
    }


def classify_regime() -> Tuple[RegimeType, float]:
    """
    Classify current market regime using z-score features.
    Returns: (regime, confidence)
    """
    features = compute_regime_features()
    
    vol_z = features.get("volatility_z", 0)
    mom_z = features.get("momentum_z", 0)
    vix_z = features.get("vix_z", 0)
    
    # Classification logic
    if vix_z > 2 or vol_z > 2:
        regime = RegimeType.CRISIS
        confidence = min(1, abs(vix_z) / 3)
    elif vix_z > 1 or vol_z > 1:
        regime = RegimeType.HIGH_VOL
        confidence = min(1, (abs(vix_z) + abs(vol_z)) / 4)
    elif mom_z < -1.5:
        regime = RegimeType.BEAR
        confidence = min(1, abs(mom_z) / 3)
    elif mom_z > 0.5 and vol_z < 0.5:
        regime = RegimeType.BULL
        confidence = min(1, (mom_z + 1) / 3)
    else:
        # Check for recovery (following crisis/bear)
        regime = RegimeType.RECOVERY if mom_z > 0 else RegimeType.BULL
        confidence = 0.5
    
    return regime, confidence


def estimate_transition_matrix() -> np.ndarray:
    """
    Estimate regime transition probability matrix.
    Simplified version using historical patterns.
    """
    # Stylized transition matrix (would be estimated from data in production)
    # Rows: from regime, Cols: to regime
    # Order: Bull, Bear, HighVol, Crisis, Recovery
    matrix = np.array([
        [0.85, 0.05, 0.05, 0.02, 0.03],  # From Bull
        [0.05, 0.75, 0.10, 0.05, 0.05],  # From Bear
        [0.15, 0.10, 0.60, 0.10, 0.05],  # From HighVol
        [0.05, 0.10, 0.20, 0.50, 0.15],  # From Crisis
        [0.30, 0.05, 0.10, 0.05, 0.50],  # From Recovery
    ])
    return matrix


def compute_regime_persistence() -> Dict:
    """Compute regime persistence metrics."""
    regime, conf = classify_regime()
    matrix = estimate_transition_matrix()
    
    regime_idx = ["Bull", "Bear", "HighVol", "Crisis", "Recovery"].index(regime.value)
    
    # Expected duration = 1 / (1 - p_stay)
    p_stay = matrix[regime_idx, regime_idx]
    expected_duration = 1 / (1 - p_stay) if p_stay < 1 else float('inf')
    
    return {
        "current_regime": regime.value,
        "persistence_probability": p_stay,
        "expected_duration_days": expected_duration * 21,  # Convert to trading days
        "confidence": conf
    }


# =============================================================================
# FEATURE 11: PORTFOLIO WEATHER STATION
# =============================================================================

def compute_weather_station() -> RegimeOutput:
    """
    Full weather station output with regime classification,
    transition probabilities, and conditioned performance.
    """
    regime, confidence = classify_regime()
    features = compute_regime_features()
    matrix = estimate_transition_matrix()
    persistence = compute_regime_persistence()
    
    # Regime state
    regime_state = RegimeState(
        current_regime=regime,
        confidence=confidence,
        days_in_regime=int(persistence.get("expected_duration_days", 21) * 0.5),  # Estimate
        persistence_score=persistence.get("persistence_probability", 0.5),
        transition_probabilities={
            "Bull": float(matrix[["Bull", "Bear", "HighVol", "Crisis", "Recovery"].index(regime.value), 0]),
            "Bear": float(matrix[["Bull", "Bear", "HighVol", "Crisis", "Recovery"].index(regime.value), 1]),
            "HighVol": float(matrix[["Bull", "Bear", "HighVol", "Crisis", "Recovery"].index(regime.value), 2]),
            "Crisis": float(matrix[["Bull", "Bear", "HighVol", "Crisis", "Recovery"].index(regime.value), 3]),
            "Recovery": float(matrix[["Bull", "Bear", "HighVol", "Crisis", "Recovery"].index(regime.value), 4]),
        },
        drivers=features
    )
    
    # Historical regime stats (stylized)
    stats_by_regime = [
        RegimeConditionalStats(
            regime=RegimeType.BULL,
            days=150,
            return_ann=0.15,
            volatility=0.12,
            sharpe=1.25,
            max_dd=-0.08,
            win_rate=0.58
        ),
        RegimeConditionalStats(
            regime=RegimeType.BEAR,
            days=60,
            return_ann=-0.15,
            volatility=0.25,
            sharpe=-0.60,
            max_dd=-0.25,
            win_rate=0.42
        ),
        RegimeConditionalStats(
            regime=RegimeType.HIGH_VOL,
            days=45,
            return_ann=0.02,
            volatility=0.30,
            sharpe=0.07,
            max_dd=-0.18,
            win_rate=0.48
        ),
        RegimeConditionalStats(
            regime=RegimeType.CRISIS,
            days=20,
            return_ann=-0.40,
            volatility=0.50,
            sharpe=-0.80,
            max_dd=-0.35,
            win_rate=0.35
        ),
        RegimeConditionalStats(
            regime=RegimeType.RECOVERY,
            days=40,
            return_ann=0.25,
            volatility=0.22,
            sharpe=1.14,
            max_dd=-0.10,
            win_rate=0.55
        ),
    ]
    
    # What works by regime
    what_works = {
        "momentum": {
            "Bull": "Strong",
            "Bear": "Weak",
            "HighVol": "Mixed",
            "Crisis": "Very Weak",
            "Recovery": "Strong"
        },
        "value": {
            "Bull": "Moderate",
            "Bear": "Moderate",
            "HighVol": "Weak",
            "Crisis": "Weak",
            "Recovery": "Strong"
        },
        "low_vol": {
            "Bull": "Underperform",
            "Bear": "Outperform",
            "HighVol": "Outperform",
            "Crisis": "Strong Outperform",
            "Recovery": "Underperform"
        }
    }
    
    return RegimeOutput(
        current=regime_state,
        history=[],  # Would be populated from stored history
        stats_by_regime=stats_by_regime,
        transition_matrix=matrix.tolist(),
        what_works=what_works
    )


# =============================================================================
# FEATURE 12: SHOCK PROPAGATION SIMULATOR
# =============================================================================

def simulate_shock_propagation(
    positions: List[Position],
    shocks: Dict[str, float],
    max_iterations: int = 5,
    confidence_decay_rate: float = 0.3
) -> ShockPropagationResult:
    """
    Simulate shock propagation through portfolio using correlation structure.
    
    Args:
        positions: List of portfolio positions
        shocks: Dict of {ticker: shock_magnitude} for directly shocked assets
        max_iterations: Max propagation iterations
        confidence_decay_rate: Confidence decay per iteration
    """
    if not positions:
        return ShockPropagationResult(
            shock_config=shocks,
            total_loss=0,
            total_loss_pct=0,
            position_impacts=[],
            nav_path=[],
            confidence_decay=[],
            liquidity_haircut=0
        )
    
    tickers = [p.ticker for p in positions]
    weights = {p.ticker: p.weight for p in positions}
    mvs = {p.ticker: p.market_value for p in positions}
    total_nav = sum(mvs.values())
    
    # Get correlation matrix
    from app.services.portfolio_risk import _get_returns_matrix
    returns_df = _get_returns_matrix(tickers, period="6mo")
    
    if len(returns_df) < 30:
        corr = np.eye(len(tickers))
    else:
        corr = sample_correlation(returns_df).values
    
    ticker_idx = {t: i for i, t in enumerate(tickers)}
    
    # Initialize impacts
    impacts = {t: 0.0 for t in tickers}
    
    # First order: direct shocks
    for ticker, shock in shocks.items():
        if ticker in impacts:
            impacts[ticker] = shock
    
    # Track impacts by order
    nav_path = [{"order": 0, "nav_impact": sum(impacts[t] * mvs.get(t, 0) for t in tickers)}]
    confidence_decay = [1.0]
    
    # Propagation iterations
    for iteration in range(1, max_iterations):
        new_impacts = {t: impacts[t] for t in tickers}
        
        for ticker in tickers:
            if ticker in shocks:
                continue  # Skip directly shocked assets
            
            # Propagate from correlated assets
            propagated = 0.0
            idx = ticker_idx.get(ticker)
            if idx is None:
                continue
            
            for source_ticker, source_impact in impacts.items():
                if source_ticker == ticker or abs(source_impact) < 0.001:
                    continue
                
                source_idx = ticker_idx.get(source_ticker)
                if source_idx is not None and idx < len(corr) and source_idx < len(corr):
                    correlation = corr[idx, source_idx]
                    if abs(correlation) > 0.3:  # Only propagate significant correlations
                        propagated += source_impact * correlation * 0.5  # Damping factor
            
            new_impacts[ticker] = impacts[ticker] + propagated
        
        impacts = new_impacts
        
        # Track progress
        current_conf = (1 - confidence_decay_rate) ** iteration
        confidence_decay.append(current_conf)
        
        nav_impact = sum(impacts[t] * mvs.get(t, 0) for t in tickers)
        nav_path.append({"order": iteration, "nav_impact": nav_impact})
    
    # Build position impacts
    position_impacts = []
    for pos in positions:
        ticker = pos.ticker
        direct = shocks.get(ticker, 0)
        total_impact = impacts.get(ticker, 0)
        second_order = total_impact - direct
        
        position_impacts.append(ShockImpact(
            ticker=ticker,
            direct_impact=direct * pos.market_value,
            first_order=direct * pos.market_value,
            second_order=second_order * pos.market_value,
            total_impact=total_impact * pos.market_value,
            pct_of_loss=abs(total_impact * pos.market_value) / max(1, abs(nav_path[-1]["nav_impact"])) if nav_path else 0,
            confidence=confidence_decay[-1]
        ))
    
    # Sort by impact
    position_impacts.sort(key=lambda x: x.total_impact)
    
    # Liquidity haircut (illiquid positions suffer more in stress)
    liq_haircut = sum(
        0.02 * pos.market_value for pos in positions
        if pos.exit_days > 5
    )
    
    total_loss = abs(nav_path[-1]["nav_impact"]) + liq_haircut if nav_path else 0
    
    return ShockPropagationResult(
        shock_config=shocks,
        total_loss=total_loss,
        total_loss_pct=total_loss / total_nav if total_nav > 0 else 0,
        position_impacts=position_impacts,
        nav_path=nav_path,
        confidence_decay=confidence_decay,
        liquidity_haircut=liq_haircut
    )


def run_predefined_scenario(
    positions: List[Position],
    scenario: str
) -> ShockPropagationResult:
    """
    Run a predefined stress scenario.
    
    Scenarios:
    - "market_crash": -20% broad market
    - "tech_meltdown": -30% tech sector
    - "rate_shock": Interest rate sensitive assets
    - "liquidity_crisis": -10% with 3x liquidity stress
    """
    shocks = {}
    
    if scenario == "market_crash":
        # All positions shocked -20%
        for pos in positions:
            shocks[pos.ticker] = -0.20
    
    elif scenario == "tech_meltdown":
        # Tech positions shocked -30%, others -10%
        tech_keywords = ["AAPL", "MSFT", "GOOGL", "GOOG", "AMZN", "META", "NVDA", "TSLA"]
        for pos in positions:
            if any(kw in pos.ticker for kw in tech_keywords):
                shocks[pos.ticker] = -0.30
            else:
                shocks[pos.ticker] = -0.10
    
    elif scenario == "rate_shock":
        # Financials and rate-sensitive
        for pos in positions:
            if pos.sector in ["Financials", "Real Estate", "Utilities"]:
                shocks[pos.ticker] = -0.15
            else:
                shocks[pos.ticker] = -0.05
    
    elif scenario == "liquidity_crisis":
        # All positions -10%, illiquid positions -20%
        for pos in positions:
            if pos.exit_days > 5:
                shocks[pos.ticker] = -0.20
            else:
                shocks[pos.ticker] = -0.10
    
    else:
        # Default: -15% all
        for pos in positions:
            shocks[pos.ticker] = -0.15
    
    return simulate_shock_propagation(positions, shocks)
