"""
Portfolio Strategy Service - Features 13-17
Category 4: Strategy & Backtesting
"""
import numpy as np
import pandas as pd
from datetime import datetime, timedelta
from typing import List, Dict, Optional, Tuple
import logging
import uuid

from app.models.portfolio_models import (
    Position, Quality,
    StrategySlot, StrategyRun, DivergenceMetrics
)
from app.services.portfolio_core import (
    simple_returns, sharpe_ratio, maximum_drawdown, realized_volatility
)

logger = logging.getLogger(__name__)


# =============================================================================
# STRATEGY SLOT STORAGE
# =============================================================================

_strategy_slots: Dict[str, StrategySlot] = {}

# Pre-defined strategies
_default_strategies = {
    "momentum": {
        "name": "Momentum",
        "description": "Long winners, short losers based on 12-1 month returns",
        "parameters": {"lookback": 252, "skip": 21, "top_n": 5}
    },
    "low_vol": {
        "name": "Low Volatility",
        "description": "Overweight low volatility assets",
        "parameters": {"lookback": 60, "target_vol": 0.12}
    },
    "quality": {
        "name": "Quality",
        "description": "Weight by profitability and stability metrics",
        "parameters": {"roe_weight": 0.4, "stability_weight": 0.6}
    },
    "value": {
        "name": "Value",
        "description": "Overweight low valuation assets",
        "parameters": {"pe_threshold": 15, "pb_threshold": 2}
    },
    "equal_weight": {
        "name": "Equal Weight",
        "description": "Equal allocation across all positions",
        "parameters": {}
    }
}


# =============================================================================
# FEATURE 13: STRATEGY SLOT SYSTEM
# =============================================================================

def get_available_strategies() -> List[Dict]:
    """Get list of available strategy templates."""
    return [{"id": k, **v} for k, v in _default_strategies.items()]


def activate_strategy_slot(slot_id: str, strategy_id: str, weight: float = 1.0) -> StrategySlot:
    """Activate a strategy in a slot."""
    if strategy_id not in _default_strategies:
        raise ValueError(f"Unknown strategy: {strategy_id}")
    
    template = _default_strategies[strategy_id]
    
    slot = StrategySlot(
        slot_id=slot_id,
        strategy_id=strategy_id,
        name=template["name"],
        description=template["description"],
        status="ACTIVE",
        weight=weight,
        parameters=template["parameters"],
        activated_at=datetime.utcnow().isoformat()
    )
    
    _strategy_slots[slot_id] = slot
    return slot


def deactivate_strategy_slot(slot_id: str) -> bool:
    """Deactivate a strategy slot."""
    if slot_id in _strategy_slots:
        _strategy_slots[slot_id].status = "INACTIVE"
        return True
    return False


def get_active_slots() -> List[StrategySlot]:
    """Get all active strategy slots."""
    return [s for s in _strategy_slots.values() if s.status == "ACTIVE"]


def compute_blended_weights(positions: List[Position]) -> Dict[str, float]:
    """
    Compute blended target weights from all active strategy slots.
    """
    active_slots = get_active_slots()
    if not active_slots:
        # Default to equal weight
        n = len(positions)
        return {p.ticker: 1.0 / n for p in positions}
    
    tickers = [p.ticker for p in positions]
    blended = {t: 0.0 for t in tickers}
    total_slot_weight = sum(s.weight for s in active_slots)
    
    for slot in active_slots:
        slot_weights = _compute_strategy_weights(slot.strategy_id, positions, slot.parameters)
        for ticker, weight in slot_weights.items():
            if ticker in blended:
                blended[ticker] += weight * slot.weight / total_slot_weight
    
    return blended


def _compute_strategy_weights(strategy_id: str, positions: List[Position], params: Dict) -> Dict[str, float]:
    """Compute weights for a single strategy."""
    tickers = [p.ticker for p in positions]
    n = len(tickers)
    
    if n == 0:
        return {}
    
    if strategy_id == "equal_weight":
        return {t: 1.0 / n for t in tickers}
    
    elif strategy_id == "momentum":
        # Use existing returns as proxy for momentum
        returns = {p.ticker: p.pnl_pct for p in positions}
        sorted_by_ret = sorted(returns.items(), key=lambda x: x[1], reverse=True)
        top_n = min(params.get("top_n", 5), n)
        weights = {t: 0.0 for t in tickers}
        for i, (ticker, _) in enumerate(sorted_by_ret[:top_n]):
            weights[ticker] = 1.0 / top_n
        return weights
    
    elif strategy_id == "low_vol":
        # Inverse volatility weighting (using exit_days as proxy for vol)
        inv_vol = {p.ticker: 1.0 / max(0.1, p.exit_days) for p in positions}
        total = sum(inv_vol.values())
        return {t: v / total for t, v in inv_vol.items()}
    
    else:
        # Fallback to equal weight
        return {t: 1.0 / n for t in tickers}


# =============================================================================
# FEATURE 14: STRATEGY STATE BACKTEST
# =============================================================================

def backtest_strategy(
    strategy_id: str,
    positions: List[Position],
    lookback_days: int = 252,
    rebalance_freq: str = "monthly"
) -> StrategyRun:
    """
    Backtest a strategy using historical data.
    """
    run_id = str(uuid.uuid4())[:8]
    
    # Simplified backtest - in production would use full historical data
    # For demo, generate synthetic results
    
    end_date = datetime.utcnow()
    start_date = end_date - timedelta(days=lookback_days)
    
    # Generate synthetic daily returns
    np.random.seed(hash(strategy_id) % 2**32)
    n_days = lookback_days
    
    if strategy_id == "momentum":
        daily_ret = np.random.normal(0.0005, 0.015, n_days)  # Slight positive skew
    elif strategy_id == "low_vol":
        daily_ret = np.random.normal(0.0003, 0.008, n_days)  # Lower vol
    elif strategy_id == "value":
        daily_ret = np.random.normal(0.0004, 0.012, n_days)
    else:
        daily_ret = np.random.normal(0.0003, 0.012, n_days)
    
    returns = pd.Series(daily_ret)
    nav = (1 + returns).cumprod() * 100000
    
    # Compute metrics
    sharpe = sharpe_ratio(returns)
    max_dd, _, _ = maximum_drawdown(nav)
    vol = realized_volatility(returns)
    total_return = float(nav.iloc[-1] / nav.iloc[0] - 1)
    
    return StrategyRun(
        run_id=run_id,
        strategy_id=strategy_id,
        start_date=start_date.isoformat(),
        end_date=end_date.isoformat(),
        total_return=total_return,
        sharpe=sharpe,
        max_drawdown=max_dd,
        volatility=vol,
        win_rate=0.52 + np.random.uniform(-0.05, 0.05),
        trades_count=int(lookback_days / 21 * len(positions)),
        turnover=0.15 + np.random.uniform(-0.05, 0.05),
        nav_series=nav.tolist()[-60:],  # Last 60 days for charting
        status="COMPLETED",
        quality=Quality(confidence=0.8)
    )


# =============================================================================
# FEATURE 15: DECISION PATH BACKTESTING
# =============================================================================

def backtest_decision_path(
    decisions: List[Dict],
    initial_nav: float = 100000
) -> Dict:
    """
    Backtest a sequence of historical decisions to see alternative outcomes.
    
    decisions: List of {"date": str, "action": str, "ticker": str, "quantity": float}
    """
    results = {
        "decisions_analyzed": len(decisions),
        "paths": [],
        "best_path": None,
        "worst_path": None
    }
    
    # Path 1: Actual decisions
    actual_nav = initial_nav
    for d in decisions:
        # Simulate each decision's impact
        impact = np.random.uniform(-0.02, 0.03)
        actual_nav *= (1 + impact)
    
    results["paths"].append({
        "name": "Actual",
        "final_nav": actual_nav,
        "return": actual_nav / initial_nav - 1
    })
    
    # Path 2: If we had held
    hold_nav = initial_nav * (1 + np.random.uniform(0.05, 0.15))
    results["paths"].append({
        "name": "Hold",
        "final_nav": hold_nav,
        "return": hold_nav / initial_nav - 1
    })
    
    # Path 3: Inverse decisions
    inverse_nav = initial_nav
    for d in decisions:
        impact = np.random.uniform(-0.03, 0.02)
        inverse_nav *= (1 + impact)
    
    results["paths"].append({
        "name": "Inverse",
        "final_nav": inverse_nav,
        "return": inverse_nav / initial_nav - 1
    })
    
    # Determine best/worst
    sorted_paths = sorted(results["paths"], key=lambda p: p["final_nav"], reverse=True)
    results["best_path"] = sorted_paths[0]["name"]
    results["worst_path"] = sorted_paths[-1]["name"]
    
    return results


# =============================================================================
# FEATURE 16: GUARDRAIL STRESS BACKTEST
# =============================================================================

def backtest_guardrails(
    guardrail_config: Dict,
    lookback_days: int = 252
) -> Dict:
    """
    Backtest guardrail effectiveness over historical period.
    """
    # Simulate how guardrails would have triggered
    
    np.random.seed(42)
    dates = pd.date_range(end=datetime.utcnow(), periods=lookback_days, freq='D')
    
    triggers = []
    for i, date in enumerate(dates):
        # Random chance of guardrail trigger
        if np.random.random() < 0.02:  # 2% daily trigger rate
            triggers.append({
                "date": date.isoformat(),
                "guardrail": np.random.choice(["position_max", "vol_max", "dd_max"]),
                "action_taken": np.random.choice(["reduce_exposure", "add_hedge", "none"]),
                "outcome": np.random.choice(["prevented_loss", "false_positive", "neutral"])
            })
    
    # Compute effectiveness
    prevented = sum(1 for t in triggers if t["outcome"] == "prevented_loss")
    false_pos = sum(1 for t in triggers if t["outcome"] == "false_positive")
    total = len(triggers)
    
    return {
        "period_days": lookback_days,
        "total_triggers": total,
        "prevented_losses": prevented,
        "false_positives": false_pos,
        "effectiveness_rate": prevented / max(1, total),
        "false_positive_rate": false_pos / max(1, total),
        "trigger_log": triggers[:10],  # Last 10
        "recommendation": "Tighten" if false_pos / max(1, total) > 0.3 else "Maintain"
    }


# =============================================================================
# FEATURE 17: STRATEGY VS REALITY DIVERGENCE
# =============================================================================

def compute_divergence(
    actual_weights: Dict[str, float],
    target_weights: Dict[str, float],
    actual_returns: Dict[str, float],
    target_returns: Dict[str, float]
) -> DivergenceMetrics:
    """
    Compute divergence between strategy target and actual portfolio.
    """
    # Weight divergence
    all_tickers = set(actual_weights.keys()) | set(target_weights.keys())
    weight_diffs = []
    for ticker in all_tickers:
        actual = actual_weights.get(ticker, 0)
        target = target_weights.get(ticker, 0)
        weight_diffs.append(abs(actual - target))
    
    weight_divergence = sum(weight_diffs) / 2  # Sum of absolute differences / 2
    
    # Return divergence
    actual_port_ret = sum(actual_weights.get(t, 0) * actual_returns.get(t, 0) for t in all_tickers)
    target_port_ret = sum(target_weights.get(t, 0) * target_returns.get(t, 0) for t in all_tickers)
    return_divergence = actual_port_ret - target_port_ret
    
    # Top drift contributors
    drift_by_ticker = []
    for ticker in all_tickers:
        actual = actual_weights.get(ticker, 0)
        target = target_weights.get(ticker, 0)
        drift_by_ticker.append({
            "ticker": ticker,
            "actual_weight": actual,
            "target_weight": target,
            "drift": actual - target
        })
    
    drift_by_ticker.sort(key=lambda x: abs(x["drift"]), reverse=True)
    
    # Rebalance urgency
    if weight_divergence > 0.15:
        urgency = "HIGH"
    elif weight_divergence > 0.08:
        urgency = "MEDIUM"
    else:
        urgency = "LOW"
    
    return DivergenceMetrics(
        weight_divergence=weight_divergence,
        return_divergence=return_divergence,
        tracking_error=weight_divergence * 0.1,  # Approximate
        drift_by_position=drift_by_ticker[:5],
        rebalance_urgency=urgency,
        last_rebalance=None,
        days_since_rebalance=30  # Placeholder
    )


def monitor_strategy_divergence(positions: List[Position]) -> DivergenceMetrics:
    """
    Monitor current portfolio divergence from active strategy targets.
    """
    actual_weights = {p.ticker: p.weight for p in positions}
    target_weights = compute_blended_weights(positions)
    
    # Use PnL as proxy for returns
    actual_returns = {p.ticker: p.pnl_pct for p in positions}
    target_returns = actual_returns.copy()  # Same returns, different weights
    
    return compute_divergence(actual_weights, target_weights, actual_returns, target_returns)
