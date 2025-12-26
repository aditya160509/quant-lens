"""
Portfolio Hedging Service - Features 22-24
Category 6: Defense & Hedging
"""
import numpy as np
import pandas as pd
from datetime import datetime, timedelta
from typing import List, Dict, Optional
import yfinance as yf
import logging

from app.models.portfolio_models import (
    Position, Quality,
    HedgeInstrument, HedgeRecommendation, HedgeResponse,
    HedgeClock, HedgeLeg, HedgePnL
)
from app.services.portfolio_core import realized_volatility

logger = logging.getLogger(__name__)


# =============================================================================
# HEDGE INSTRUMENTS DATABASE
# =============================================================================

_hedge_instruments = {
    "SH": {"name": "ProShares Short S&P500", "type": "inverse_etf", "beta": -1.0, "expense": 0.0089},
    "SDS": {"name": "ProShares UltraShort S&P500", "type": "inverse_etf", "beta": -2.0, "expense": 0.0089},
    "SPXS": {"name": "Direxion Daily S&P500 Bear 3X", "type": "inverse_etf", "beta": -3.0, "expense": 0.0095},
    "SQQQ": {"name": "ProShares UltraPro Short QQQ", "type": "inverse_etf", "beta": -3.0, "expense": 0.0095},
    "VXX": {"name": "iPath VIX Short-Term", "type": "volatility", "beta": 0.4, "expense": 0.0089},
    "UVXY": {"name": "ProShares Ultra VIX", "type": "volatility", "beta": 1.5, "expense": 0.0095},
    "GLD": {"name": "SPDR Gold Shares", "type": "commodity", "beta": -0.1, "expense": 0.0040},
    "TLT": {"name": "iShares 20+ Year Treasury", "type": "bond", "beta": -0.3, "expense": 0.0015},
}

# Active hedges
_active_hedges: List[HedgeLeg] = []


# =============================================================================
# HELPER FUNCTIONS
# =============================================================================

def _get_price(ticker: str) -> Optional[float]:
    """Get current price for ticker."""
    try:
        tk = yf.Ticker(ticker)
        hist = tk.history(period="5d")
        if len(hist) > 0:
            return float(hist['Close'].iloc[-1])
    except:
        pass
    return None


def _compute_hedge_effectiveness(portfolio_beta: float, hedge_beta: float, hedge_weight: float) -> float:
    """
    Compute how effective a hedge would be.
    Effectiveness = 1 - abs(port_beta + hedge_beta * hedge_weight)
    """
    net_beta = portfolio_beta + hedge_beta * hedge_weight
    return 1 - abs(net_beta)


# =============================================================================
# FEATURE 22: HEDGE RESPONSE VIEW
# =============================================================================

def compute_hedge_response(
    positions: List[Position],
    target_protection: float = 0.10,  # 10% downside protection
    max_cost: float = 0.02  # 2% of NAV max cost
) -> HedgeResponse:
    """
    Analyze portfolio and recommend hedge positions.
    """
    total_mv = sum(p.market_value for p in positions)
    
    # Compute portfolio beta (simplified)
    portfolio_beta = np.mean([p.beta for p in positions]) if positions else 1.0
    
    # Analyze available hedge instruments
    instruments = []
    for ticker, info in _hedge_instruments.items():
        price = _get_price(ticker)
        if price is None:
            continue
        
        # Calculate required size for target protection
        required_weight = target_protection / abs(info["beta"]) if info["beta"] != 0 else 0
        required_value = required_weight * total_mv
        required_shares = int(required_value / price)
        
        # Cost estimate (expense ratio annualized + spread)
        annual_cost = required_value * (info["expense"] + 0.002)  # 20bps spread
        
        # Effectiveness
        effectiveness = _compute_hedge_effectiveness(portfolio_beta, info["beta"], required_weight)
        
        instruments.append(HedgeInstrument(
            ticker=ticker,
            name=info["name"],
            type=info["type"],
            beta=info["beta"],
            correlation_to_portfolio=-0.7 if info["beta"] < 0 else 0.2,
            current_price=price,
            implied_vol=0.25,  # Placeholder
            cost_to_hedge=annual_cost,
            effectiveness=effectiveness
        ))
    
    # Sort by effectiveness
    instruments.sort(key=lambda x: x.effectiveness, reverse=True)
    
    # Generate recommendations
    recommendations = []
    
    # Recommendation 1: Best single hedge
    if instruments:
        best = instruments[0]
        recommendations.append(HedgeRecommendation(
            strategy="Single Instrument",
            instruments=[best.ticker],
            weights={best.ticker: target_protection / abs(best.beta)},
            expected_protection=target_protection,
            estimated_cost=best.cost_to_hedge,
            confidence=0.8
        ))
    
    # Recommendation 2: Diversified hedge (inverse ETF + volatility)
    inverse_etf = next((i for i in instruments if i.type == "inverse_etf"), None)
    vol_etf = next((i for i in instruments if i.type == "volatility"), None)
    
    if inverse_etf and vol_etf:
        recommendations.append(HedgeRecommendation(
            strategy="Diversified",
            instruments=[inverse_etf.ticker, vol_etf.ticker],
            weights={inverse_etf.ticker: 0.7, vol_etf.ticker: 0.3},
            expected_protection=target_protection * 1.1,
            estimated_cost=inverse_etf.cost_to_hedge * 0.7 + vol_etf.cost_to_hedge * 0.3,
            confidence=0.75
        ))
    
    # Recommendation 3: Safe haven (bonds + gold)
    bond = next((i for i in instruments if i.type == "bond"), None)
    gold = next((i for i in instruments if i.type == "commodity"), None)
    
    if bond and gold:
        recommendations.append(HedgeRecommendation(
            strategy="Safe Haven",
            instruments=[bond.ticker, gold.ticker],
            weights={bond.ticker: 0.6, gold.ticker: 0.4},
            expected_protection=target_protection * 0.6,
            estimated_cost=bond.cost_to_hedge * 0.6 + gold.cost_to_hedge * 0.4,
            confidence=0.85
        ))
    
    return HedgeResponse(
        portfolio_beta=portfolio_beta,
        current_hedge_ratio=sum(h.weight for h in _active_hedges),
        target_protection=target_protection,
        available_instruments=instruments,
        recommendations=recommendations,
        active_hedges=_active_hedges
    )


# =============================================================================
# FEATURE 23: HEDGE REBALANCING CLOCK
# =============================================================================

def compute_hedge_clock(
    positions: List[Position],
    decay_threshold: float = 0.20  # Rebalance when effectiveness drops 20%
) -> HedgeClock:
    """
    Monitor hedge effectiveness decay and rebalancing needs.
    """
    total_mv = sum(p.market_value for p in positions)
    portfolio_beta = np.mean([p.beta for p in positions]) if positions else 1.0
    
    # Analyze active hedges
    current_effectiveness = 0.0
    target_effectiveness = 0.8
    days_to_decay = 30  # Default
    
    if _active_hedges:
        # Compute current total hedge ratio
        total_hedge_beta = sum(h.beta * h.weight for h in _active_hedges)
        net_beta = portfolio_beta + total_hedge_beta
        current_effectiveness = 1 - abs(net_beta) / abs(portfolio_beta) if portfolio_beta != 0 else 0
        
        # Estimate decay (simplified - inverse ETFs decay due to compounding)
        avg_leverage = np.mean([abs(h.beta) for h in _active_hedges])
        daily_decay = 0.001 * avg_leverage  # Higher leverage = faster decay
        days_to_decay = int((current_effectiveness - (1 - decay_threshold)) / daily_decay) if daily_decay > 0 else 90
    
    # Determine urgency
    if current_effectiveness < 0.5 or days_to_decay < 7:
        urgency = "HIGH"
        action = "REBALANCE_IMMEDIATELY"
    elif current_effectiveness < 0.7 or days_to_decay < 14:
        urgency = "MEDIUM"
        action = "SCHEDULE_REBALANCE"
    else:
        urgency = "LOW"
        action = "MONITOR"
    
    # Optimal rebalance schedule
    schedule = []
    next_date = datetime.utcnow()
    for i in range(3):
        next_date += timedelta(days=max(7, days_to_decay // 3))
        schedule.append({
            "date": next_date.isoformat(),
            "action": "Review and rebalance if needed",
            "priority": "HIGH" if i == 0 else "MEDIUM"
        })
    
    return HedgeClock(
        current_effectiveness=current_effectiveness,
        target_effectiveness=target_effectiveness,
        decay_rate=0.001 * (np.mean([abs(h.beta) for h in _active_hedges]) if _active_hedges else 1),
        days_to_threshold=days_to_decay,
        rebalance_urgency=urgency,
        recommended_action=action,
        optimal_schedule=schedule
    )


def add_hedge(ticker: str, shares: float, entry_price: float) -> HedgeLeg:
    """Add a hedge position."""
    info = _hedge_instruments.get(ticker, {"name": ticker, "beta": -1.0})
    
    hedge = HedgeLeg(
        ticker=ticker,
        name=info.get("name", ticker),
        shares=shares,
        entry_price=entry_price,
        current_price=_get_price(ticker) or entry_price,
        beta=info.get("beta", -1.0),
        weight=0.05,  # Placeholder
        entry_date=datetime.utcnow().isoformat(),
        pnl=0,
        pnl_pct=0
    )
    
    _active_hedges.append(hedge)
    return hedge


def remove_hedge(ticker: str) -> bool:
    """Remove a hedge position."""
    global _active_hedges
    before = len(_active_hedges)
    _active_hedges = [h for h in _active_hedges if h.ticker != ticker]
    return len(_active_hedges) < before


# =============================================================================
# FEATURE 24: HEDGE PNL STREAM
# =============================================================================

def compute_hedge_pnl() -> HedgePnL:
    """
    Compute P&L for all hedge positions.
    """
    total_cost = 0.0
    total_pnl = 0.0
    daily_pnl = []
    
    legs_pnl = []
    
    for hedge in _active_hedges:
        current = _get_price(hedge.ticker) or hedge.current_price
        entry_value = hedge.shares * hedge.entry_price
        current_value = hedge.shares * current
        leg_pnl = current_value - entry_value
        leg_pnl_pct = leg_pnl / entry_value if entry_value > 0 else 0
        
        hedge.current_price = current
        hedge.pnl = leg_pnl
        hedge.pnl_pct = leg_pnl_pct
        
        legs_pnl.append({
            "ticker": hedge.ticker,
            "shares": hedge.shares,
            "entry": hedge.entry_price,
            "current": current,
            "pnl": leg_pnl,
            "pnl_pct": leg_pnl_pct
        })
        
        total_cost += entry_value
        total_pnl += leg_pnl
    
    # Cost of carry (simplified - expense ratios)
    annual_carry = 0
    for hedge in _active_hedges:
        info = _hedge_instruments.get(hedge.ticker, {})
        expense = info.get("expense", 0.01)
        annual_carry += hedge.shares * hedge.current_price * expense
    
    daily_carry = annual_carry / 252
    
    # Effectiveness vs portfolio losses
    effectiveness_ratio = abs(total_pnl / max(1, total_cost * 0.1))  # Normalize
    
    return HedgePnL(
        total_hedge_value=sum(h.shares * h.current_price for h in _active_hedges),
        total_hedge_pnl=total_pnl,
        total_hedge_pnl_pct=total_pnl / max(1, total_cost),
        legs=legs_pnl,
        cost_of_carry_daily=daily_carry,
        cost_of_carry_mtd=daily_carry * 21,
        effectiveness_vs_loss=effectiveness_ratio,
        portfolio_loss_offset=min(1, abs(total_pnl / max(1, total_cost * 0.05)))
    )


def get_hedge_history(days: int = 30) -> List[Dict]:
    """Get historical hedge P&L (simplified - would track actual history)."""
    history = []
    base_pnl = 0
    
    for i in range(days):
        date = datetime.utcnow() - timedelta(days=days - i)
        daily_change = np.random.normal(0, 100)
        base_pnl += daily_change
        history.append({
            "date": date.strftime("%Y-%m-%d"),
            "cumulative_pnl": base_pnl,
            "daily_pnl": daily_change
        })
    
    return history
