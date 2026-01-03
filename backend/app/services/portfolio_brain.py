"""
Portfolio Brain Service - Features 1-4
Category 1: Executive Control & Intelligence

Now uses robust_data_fetcher for multi-source data with caching and rate limiting.
"""
import hashlib
import json
import numpy as np
import pandas as pd
from datetime import datetime, timedelta
from typing import List, Dict, Optional, Tuple, Any
import logging
import uuid

# Use robust data fetcher instead of yfinance directly
from app.services.robust_data_fetcher import (
    get_price_data as rdf_get_price,
    get_current_price as rdf_current_price,
    Ticker as RDFTicker
)

from app.models.portfolio_models import (
    Position, PortfolioSnapshot, RiskMetrics, Quality, Provenance,
    RiskItem, StabilizerAction, BrainRecommendation, PortfolioBrainOutput,
    HealthComponent, HealthMeter, StateDelta, RevertSimulation,
    PortfolioFingerprint, Severity
)
from app.services.portfolio_core import (
    log_returns, simple_returns, realized_volatility, ewma_volatility,
    ledoit_wolf_shrinkage, value_at_risk, conditional_var, maximum_drawdown,
    current_drawdown, sharpe_ratio, sortino_ratio, risk_contribution,
    percentage_risk_contribution, herfindahl_hirschman_index, effective_n,
    entropy, exit_days, liquidity_score, portfolio_volatility
)

logger = logging.getLogger(__name__)


# =============================================================================
# STATE STORAGE - Synced with Legacy Portfolio Service
# =============================================================================

def _get_synced_state() -> Dict[str, Any]:
    """
    Get portfolio state synced from legacy portfolio.py service.
    This ensures V2 features have access to real positions.
    """
    try:
        from app.services.portfolio import _portfolio_state as legacy_state
        
        # Transform legacy format to V2 format
        holdings = {}
        for ticker, data in legacy_state.get("holdings", {}).items():
            holdings[ticker] = {
                "shares": data.get("quantity", 0),
                "cost_basis": data.get("avg_cost", 0) * data.get("quantity", 0),
                "entry_date": datetime.utcnow().isoformat()
            }
        
        return {
            "holdings": holdings,
            "cash": legacy_state.get("cash", 100000.0),
            "nav_history": [],
            "snapshots": _snapshot_storage,
            "health_history": _health_history_storage,
        }
    except Exception as e:
        logger.warning(f"Could not sync with legacy state: {e}")
        return {
            "holdings": {},
            "cash": 100000.0,
            "nav_history": [],
            "snapshots": [],
            "health_history": [],
        }

# Separate storage for snapshots and health history (persists across calls)
_snapshot_storage: List[Dict] = []
_health_history_storage: List[Dict] = []

_factor_baseline = {
    "market": 1.0,
    "size": 0.0,
    "value": 0.0,
    "momentum": 0.0,
    "quality": 0.0
}


# =============================================================================
# HELPER FUNCTIONS - Using robust_data_fetcher
# =============================================================================

def _get_price(ticker: str) -> Optional[float]:
    """Get current price for ticker using robust data fetcher."""
    try:
        price = rdf_current_price(ticker)
        if price is not None:
            return float(price)
        # Fallback to getting last close
        df = rdf_get_price(ticker, period="5d")
        if df is not None and not df.empty and 'Close' in df.columns:
            return float(df['Close'].iloc[-1])
    except Exception as e:
        logger.warning(f"Failed to get price for {ticker}: {e}")
    return None


def _get_returns(ticker: str, period: str = "1y") -> pd.Series:
    """Get return series for ticker using robust data fetcher."""
    try:
        df = rdf_get_price(ticker, period=period)
        if df is not None and not df.empty and 'Close' in df.columns and len(df) > 10:
            return log_returns(df['Close'])
    except Exception as e:
        logger.warning(f"Failed to get returns for {ticker}: {e}")
    return pd.Series([])


def _get_volume(ticker: str) -> float:
    """Get average daily volume using robust data fetcher."""
    try:
        df = rdf_get_price(ticker, period="3mo")
        if df is not None and not df.empty and 'Volume' in df.columns:
            return float(df['Volume'].mean())
    except Exception:
        pass
    return 1e6  # Default fallback


def _compute_sha256(data: Dict) -> str:
    """Compute deterministic SHA-256 hash."""
    json_str = json.dumps(data, sort_keys=True, default=str)
    return hashlib.sha256(json_str.encode()).hexdigest()[:16]


# =============================================================================
# PORTFOLIO STATE MANAGEMENT
# =============================================================================

def get_portfolio_state() -> Dict[str, Any]:
    """Get current portfolio state (synced from legacy service)."""
    return _get_synced_state()


def update_portfolio_holdings(ticker: str, shares: float, cost_basis: float):
    """Update or add a holding in legacy service."""
    try:
        from app.services.portfolio import _portfolio_state as legacy_state
        legacy_state["holdings"][ticker] = {
            "quantity": shares,
            "avg_cost": cost_basis / shares if shares > 0 else 0
        }
    except Exception as e:
        logger.error(f"Failed to update holdings: {e}")


def remove_holding(ticker: str):
    """Remove a holding from legacy service."""
    try:
        from app.services.portfolio import _portfolio_state as legacy_state
        if ticker in legacy_state["holdings"]:
            del legacy_state["holdings"][ticker]
    except Exception as e:
        logger.error(f"Failed to remove holding: {e}")


def update_cash(amount: float):
    """Update cash balance in legacy service."""
    try:
        from app.services.portfolio import _portfolio_state as legacy_state
        legacy_state["cash"] = amount
    except Exception as e:
        logger.error(f"Failed to update cash: {e}")


# =============================================================================
# FEATURE 1: PORTFOLIO BRAIN
# =============================================================================

def compute_portfolio_brain(snapshot: PortfolioSnapshot, risk_metrics: RiskMetrics) -> PortfolioBrainOutput:
    """
    Central intelligence: aggregate signals, rank risks, recommend actions.
    """
    as_of = datetime.utcnow().isoformat()
    
    # 1. Identify top risks
    top_risks = _identify_risks(snapshot, risk_metrics)
    
    # 2. Identify stabilizers
    stabilizers = _identify_stabilizers(snapshot, risk_metrics)
    
    # 3. Generate recommendations
    recommendations = _generate_recommendations(top_risks, stabilizers, risk_metrics)
    
    # 4. Executive summary
    summary = _generate_executive_summary(snapshot, risk_metrics, top_risks)
    
    return PortfolioBrainOutput(
        as_of=as_of,
        executive_summary=summary,
        top_risks=top_risks,
        stabilizers=stabilizers,
        recommendations=recommendations,
        change_vs_prior={}
    )


def _identify_risks(snapshot: PortfolioSnapshot, risk_metrics: RiskMetrics) -> List[RiskItem]:
    """Identify and rank top risks."""
    risks = []
    
    # Risk 1: Concentration risk
    if snapshot.positions:
        weights = np.array([p.weight for p in snapshot.positions])
        hhi = herfindahl_hirschman_index(weights)
        eff_n = effective_n(weights)
        
        if hhi > 0.15:
            risks.append(RiskItem(
                id="risk_concentration",
                name="High Concentration",
                description=f"Portfolio concentrated in {eff_n:.1f} effective positions (HHI: {hhi:.2%})",
                impact=snapshot.nav * 0.1,
                probability=0.3,
                score=0.03,
                positions_affected=[p.ticker for p in snapshot.positions[:3]],
                time_horizon="30d",
                mitigation_options=["Diversify into new positions", "Reduce top holdings"]
            ))
    
    # Risk 2: Volatility risk
    if risk_metrics.vol_ann > 0.25:
        risks.append(RiskItem(
            id="risk_volatility",
            name="High Volatility",
            description=f"Portfolio volatility at {risk_metrics.vol_ann:.1%} annualized",
            impact=snapshot.nav * risk_metrics.var_95,
            probability=0.05,
            score=0.05 * risk_metrics.var_95 * snapshot.nav,
            positions_affected=[],
            time_horizon="1d",
            mitigation_options=["Reduce volatile positions", "Add hedges"]
        ))
    
    # Risk 3: Drawdown risk
    if risk_metrics.current_dd < -0.1:
        risks.append(RiskItem(
            id="risk_drawdown",
            name="Active Drawdown",
            description=f"Currently in {risk_metrics.current_dd:.1%} drawdown",
            impact=snapshot.nav * abs(risk_metrics.current_dd),
            probability=0.7,
            score=0.7 * abs(risk_metrics.current_dd),
            positions_affected=[],
            time_horizon="ongoing",
            mitigation_options=["Reduce exposure", "Wait for recovery"]
        ))
    
    # Risk 4: Liquidity risk
    illiquid = [p for p in snapshot.positions if p.exit_days > 5]
    if illiquid:
        illiquid_value = sum(p.market_value for p in illiquid)
        risks.append(RiskItem(
            id="risk_liquidity",
            name="Illiquid Positions",
            description=f"{len(illiquid)} positions require >5 days to exit (${illiquid_value:,.0f})",
            impact=illiquid_value * 0.05,
            probability=0.2,
            score=0.01 * illiquid_value,
            positions_affected=[p.ticker for p in illiquid],
            time_horizon="5d+",
            mitigation_options=["Reduce illiquid holdings"]
        ))
    
    # Sort by score
    risks.sort(key=lambda r: r.score, reverse=True)
    return risks[:5]


def _identify_stabilizers(snapshot: PortfolioSnapshot, risk_metrics: RiskMetrics) -> List[StabilizerAction]:
    """Identify risk-reducing actions."""
    stabilizers = []
    
    if not snapshot.positions:
        return stabilizers
    
    # Calculate risk contributions
    positions = snapshot.positions
    weights = np.array([p.weight for p in positions])
    
    # Stabilizer 1: Reduce top concentration
    if len(positions) > 0:
        top_pos = max(positions, key=lambda p: p.weight)
        if top_pos.weight > 0.2:
            reduction = min(0.1, top_pos.weight - 0.15)
            stabilizers.append(StabilizerAction(
                id="stb_reduce_top",
                action=f"Reduce {top_pos.ticker} by {reduction:.1%}",
                risk_reduction=reduction * 0.5,
                cost=top_pos.market_value * reduction * 0.002,
                efficiency=0.25,
                confidence=0.85
            ))
    
    # Stabilizer 2: Add cash buffer
    cash_pct = snapshot.cash / snapshot.nav if snapshot.nav > 0 else 0
    if cash_pct < 0.05:
        stabilizers.append(StabilizerAction(
            id="stb_add_cash",
            action="Raise cash buffer to 5%",
            risk_reduction=0.02,
            cost=snapshot.nav * 0.05 * 0.002,
            efficiency=0.1,
            confidence=0.9
        ))
    
    # Stabilizer 3: Hedge with inverse ETF
    if risk_metrics.vol_ann > 0.2:
        stabilizers.append(StabilizerAction(
            id="stb_hedge",
            action="Add 5% hedge position (SH/SQQQ)",
            risk_reduction=0.03,
            cost=snapshot.nav * 0.05 * 0.005,
            efficiency=0.15,
            confidence=0.7
        ))
    
    stabilizers.sort(key=lambda s: s.efficiency, reverse=True)
    return stabilizers[:5]


def _generate_recommendations(risks: List[RiskItem], stabilizers: List[StabilizerAction], 
                             risk_metrics: RiskMetrics) -> List[BrainRecommendation]:
    """Generate actionable recommendations."""
    recommendations = []
    priority = 1
    
    for risk in risks[:2]:
        if risk.mitigation_options:
            recommendations.append(BrainRecommendation(
                priority=priority,
                severity=Severity.HIGH if risk.score > 0.05 else Severity.MEDIUM,
                title=f"Address {risk.name}",
                current_state=risk.description,
                recommended_action=risk.mitigation_options[0],
                expected_outcome=f"Reduce potential loss by ${risk.impact * 0.3:,.0f}",
                confidence=0.7,
                blockers=[]
            ))
            priority += 1
    
    for stb in stabilizers[:2]:
        if stb.blocked_by is None:
            recommendations.append(BrainRecommendation(
                priority=priority,
                severity=Severity.MEDIUM,
                title=stb.action,
                current_state="Portfolio stress elevated",
                recommended_action=stb.action,
                expected_outcome=f"Reduce risk by {stb.risk_reduction:.1%}",
                confidence=stb.confidence,
                blockers=[]
            ))
            priority += 1
    
    return recommendations


def _generate_executive_summary(snapshot: PortfolioSnapshot, risk_metrics: RiskMetrics,
                                risks: List[RiskItem]) -> str:
    """Generate executive summary narrative."""
    nav_str = f"${snapshot.nav:,.0f}"
    vol_str = f"{risk_metrics.vol_ann:.1%}"
    sharpe_str = f"{risk_metrics.sharpe:.2f}"
    
    risk_level = "Low" if len(risks) == 0 else "Moderate" if len(risks) < 3 else "Elevated"
    
    summary = f"""Portfolio NAV: {nav_str} | Volatility: {vol_str} | Sharpe: {sharpe_str}

Risk Level: {risk_level}
Number of positions: {len(snapshot.positions)}
Cash: ${snapshot.cash:,.0f} ({snapshot.cash/snapshot.nav*100:.1f}%)

"""
    if risks:
        summary += f"Top concern: {risks[0].name} - {risks[0].description}"
    else:
        summary += "No immediate concerns identified."
    
    return summary


# =============================================================================
# FEATURE 2: HEALTH METER
# =============================================================================

def compute_health_meter(snapshot: PortfolioSnapshot, risk_metrics: RiskMetrics) -> HealthMeter:
    """
    Real-time health meter with weighted survival scoring.
    Health = Σ αⱼ × metricⱼ with non-linear penalties
    """
    components = []
    
    # Component 1: Volatility health (20% weight)
    vol_target = 0.15
    vol_current = risk_metrics.vol_ann
    vol_score = max(0, 100 - (vol_current - vol_target) / vol_target * 50) if vol_current > vol_target else 100
    vol_penalty = np.exp(max(0, vol_current - 0.30) * 10) - 1  # Exponential penalty above 30%
    vol_score = max(0, vol_score - vol_penalty * 20)
    
    components.append(HealthComponent(
        name="Volatility",
        score=vol_score,
        weight=0.20,
        penalty=vol_penalty,
        current=vol_current,
        target=vol_target,
        status="OK" if vol_score > 70 else "CAUTION" if vol_score > 40 else "BREACH"
    ))
    
    # Component 2: Drawdown health (25% weight)
    dd_target = -0.10
    dd_current = risk_metrics.current_dd
    dd_score = max(0, 100 + dd_current / 0.30 * 100) if dd_current < 0 else 100
    dd_penalty = np.exp(max(0, -dd_current - 0.15) * 5) - 1  # Penalty below -15%
    dd_score = max(0, dd_score - dd_penalty * 30)
    
    components.append(HealthComponent(
        name="Drawdown",
        score=dd_score,
        weight=0.25,
        penalty=dd_penalty,
        current=dd_current,
        target=dd_target,
        status="OK" if dd_score > 70 else "CAUTION" if dd_score > 40 else "BREACH"
    ))
    
    # Component 3: Liquidity health (20% weight)
    if snapshot.positions:
        avg_exit = np.mean([p.exit_days for p in snapshot.positions])
        liq_score = max(0, 100 - avg_exit * 10)
    else:
        avg_exit = 0
        liq_score = 100
    
    components.append(HealthComponent(
        name="Liquidity",
        score=liq_score,
        weight=0.20,
        penalty=0,
        current=avg_exit,
        target=2.0,
        status="OK" if liq_score > 70 else "CAUTION" if liq_score > 40 else "BREACH"
    ))
    
    # Component 4: Concentration health (20% weight)
    if snapshot.positions:
        weights = np.array([p.weight for p in snapshot.positions])
        hhi = herfindahl_hirschman_index(weights)
        eff = effective_n(weights)
        conc_score = min(100, eff * 10)
    else:
        hhi = 0
        conc_score = 100
    
    components.append(HealthComponent(
        name="Concentration",
        score=conc_score,
        weight=0.20,
        penalty=0,
        current=hhi,
        target=0.10,
        status="OK" if conc_score > 70 else "CAUTION" if conc_score > 40 else "BREACH"
    ))
    
    # Component 5: Risk-adjusted return (15% weight)
    sharpe = risk_metrics.sharpe
    sharpe_score = min(100, max(0, (sharpe + 0.5) / 2.5 * 100))
    
    components.append(HealthComponent(
        name="Risk-Adjusted Return",
        score=sharpe_score,
        weight=0.15,
        penalty=0,
        current=sharpe,
        target=1.0,
        status="OK" if sharpe_score > 70 else "CAUTION" if sharpe_score > 40 else "BREACH"
    ))
    
    # Compute weighted total
    raw_score = sum(c.score * c.weight for c in components)
    
    # Apply EWMA smoothing if we have history
    smoothed = raw_score
    if _health_history_storage:
        prev = _health_history_storage[-1].get("smoothed", raw_score)
        smoothed = 0.7 * raw_score + 0.3 * prev
    
    # Determine label
    if smoothed >= 85:
        label = "EXCELLENT"
    elif smoothed >= 70:
        label = "GOOD"
    elif smoothed >= 55:
        label = "CAUTION"
    elif smoothed >= 40:
        label = "AT_RISK"
    else:
        label = "CRITICAL"
    
    # Trend
    if len(_health_history_storage) >= 5:
        recent = [h.get("score", 50) for h in _health_history_storage[-5:]]
        slope = (recent[-1] - recent[0]) / 5
        trend = "IMPROVING" if slope > 1 else "DETERIORATING" if slope < -1 else "STABLE"
    else:
        trend = "STABLE"
    
    # Breach probability (simplified)
    breach_prob = max(0, 1 - smoothed / 50) * 0.3
    
    # Store in history
    _health_history_storage.append({
        "timestamp": datetime.utcnow().isoformat(),
        "score": raw_score,
        "smoothed": smoothed
    })
    
    return HealthMeter(
        score=raw_score,
        smoothed_score=smoothed,
        label=label,
        components=components,
        trend=trend,
        breach_probability_30d=breach_prob,
        history=_health_history_storage[-30:]  # Last 30 readings
    )


# =============================================================================
# FEATURE 3: STATES & SNAPSHOTS
# =============================================================================

def create_snapshot(trigger: str = "manual", notes: str = "") -> PortfolioSnapshot:
    """Create a portfolio snapshot for version control."""
    state = _get_synced_state()
    holdings = state["holdings"]
    cash = state["cash"]
    
    positions = []
    nav = cash
    
    for ticker, holding in holdings.items():
        price = _get_price(ticker)
        if price is None:
            continue
        
        shares = holding["shares"]
        market_value = shares * price
        cost_basis = holding.get("cost_basis", price * shares)
        pnl = market_value - cost_basis
        
        # Get additional data
        adv = _get_volume(ticker)
        exit_d = exit_days(market_value, adv * price)
        
        positions.append(Position(
            ticker=ticker,
            name=ticker,
            shares=shares,
            price=price,
            market_value=market_value,
            weight=0,  # Will update after NAV calc
            cost_basis=cost_basis,
            pnl=pnl,
            pnl_pct=pnl / cost_basis if cost_basis > 0 else 0,
            sector="Unknown",
            region="US",
            beta=1.0,
            exit_days=exit_d,
            risk_contribution=0  # Will compute later
        ))
        nav += market_value
    
    # Update weights
    for pos in positions:
        pos.weight = pos.market_value / nav if nav > 0 else 0
    
    # Create snapshot
    snapshot_id = str(uuid.uuid4())[:8]
    snapshot_data = {
        "positions": [p.dict() for p in positions],
        "cash": cash,
        "nav": nav
    }
    
    snapshot = PortfolioSnapshot(
        id=snapshot_id,
        as_of=datetime.utcnow().isoformat(),
        hash=_compute_sha256(snapshot_data),
        nav=nav,
        cash=cash,
        positions=positions,
        sector_weights={},
        factor_exposures=_factor_baseline.copy(),
        quality=Quality(confidence=1.0 if len(positions) > 0 else 0.5),
        provenance=Provenance(
            source="yfinance",
            transforms=[f"trigger: {trigger}", f"notes: {notes}"]
        )
    )
    
    # Store snapshot
    _snapshot_storage.append(snapshot.dict())
    
    return snapshot


def get_snapshots() -> List[Dict]:
    """Get all saved snapshots."""
    return _snapshot_storage


def compute_state_delta(from_id: str, to_id: str) -> StateDelta:
    """Compute difference between two snapshots."""
    snapshots = {s["id"]: s for s in _snapshot_storage}
    
    if from_id not in snapshots or to_id not in snapshots:
        raise ValueError("Snapshot not found")
    
    s1 = snapshots[from_id]
    s2 = snapshots[to_id]
    
    # Position changes
    t1 = {p["ticker"] for p in s1["positions"]}
    t2 = {p["ticker"] for p in s2["positions"]}
    
    added = list(t2 - t1)
    removed = list(t1 - t2)
    
    # Modified positions
    modified = []
    for ticker in t1 & t2:
        p1 = next(p for p in s1["positions"] if p["ticker"] == ticker)
        p2 = next(p for p in s2["positions"] if p["ticker"] == ticker)
        if abs(p1["weight"] - p2["weight"]) > 0.01:
            modified.append({
                "ticker": ticker,
                "weight_old": p1["weight"],
                "weight_new": p2["weight"],
                "delta": p2["weight"] - p1["weight"]
            })
    
    nav_change = s2["nav"] - s1["nav"]
    nav_change_pct = nav_change / s1["nav"] if s1["nav"] > 0 else 0
    
    # Magnitude classification
    if abs(nav_change_pct) < 0.01 and len(added) + len(removed) == 0:
        magnitude = "TRIVIAL"
    elif abs(nav_change_pct) < 0.05 and len(added) + len(removed) < 3:
        magnitude = "MINOR"
    elif abs(nav_change_pct) < 0.15:
        magnitude = "MODERATE"
    elif abs(nav_change_pct) < 0.30:
        magnitude = "MAJOR"
    else:
        magnitude = "CRITICAL"
    
    return StateDelta(
        from_id=from_id,
        to_id=to_id,
        from_date=s1["as_of"],
        to_date=s2["as_of"],
        nav_change=nav_change,
        nav_change_pct=nav_change_pct,
        positions_added=added,
        positions_removed=removed,
        positions_modified=modified,
        metric_changes={
            "nav": {"old": s1["nav"], "new": s2["nav"], "delta": nav_change}
        },
        magnitude=magnitude
    )


def simulate_revert(target_snapshot_id: str) -> RevertSimulation:
    """Simulate impact of reverting to a previous snapshot."""
    snapshots = {s["id"]: s for s in _snapshot_storage}
    
    if target_snapshot_id not in snapshots:
        raise ValueError("Target snapshot not found")
    
    target = snapshots[target_snapshot_id]
    current = create_snapshot(trigger="revert_simulation")
    
    # Calculate trades needed
    current_holdings = {p.ticker: p.shares for p in current.positions}
    target_holdings = {p["ticker"]: p["shares"] for p in target["positions"]}
    
    trades_required = []
    transaction_cost = 0
    
    all_tickers = set(current_holdings.keys()) | set(target_holdings.keys())
    for ticker in all_tickers:
        current_shares = current_holdings.get(ticker, 0)
        target_shares = target_holdings.get(ticker, 0)
        delta = target_shares - current_shares
        
        if abs(delta) > 0:
            price = _get_price(ticker) or 100
            value = abs(delta * price)
            cost = value * 0.002  # 20bps transaction cost
            
            trades_required.append({
                "ticker": ticker,
                "action": "BUY" if delta > 0 else "SELL",
                "shares": abs(delta),
                "value": value
            })
            transaction_cost += cost
    
    return RevertSimulation(
        target_snapshot_id=target_snapshot_id,
        trades_required=trades_required,
        transaction_cost=transaction_cost,
        slippage_estimate=transaction_cost * 0.5,
        post_revert_risk={},
        guardrail_violations=[],
        feasibility="HIGH" if len(trades_required) < 5 else "MODERATE" if len(trades_required) < 10 else "LOW"
    )


# =============================================================================
# FEATURE 4: PORTFOLIO FINGERPRINT
# =============================================================================

def compute_fingerprint(snapshot: PortfolioSnapshot) -> PortfolioFingerprint:
    """
    Compute style fingerprint as normalized exposure vector.
    Measures drift from baseline using distance metrics.
    """
    # Factor exposures (simplified - would use factor returns in production)
    factor_exposures = {
        "market": 1.0,
        "size": 0.0,
        "value": 0.0,
        "momentum": 0.0,
        "quality": 0.0
    }
    
    # Sector weights
    sector_weights = {}
    for pos in snapshot.positions:
        sector = pos.sector if pos.sector else "Unknown"
        sector_weights[sector] = sector_weights.get(sector, 0) + pos.weight
    
    # Region weights
    region_weights = {}
    for pos in snapshot.positions:
        region = pos.region if pos.region else "US"
        region_weights[region] = region_weights.get(region, 0) + pos.weight
    
    # Volatility posture (0 = defensive, 1 = aggressive)
    if snapshot.positions:
        avg_beta = np.mean([p.beta for p in snapshot.positions])
        vol_posture = min(1, max(0, avg_beta))
    else:
        vol_posture = 0.5
    
    # Liquidity posture (0 = illiquid, 1 = very liquid)
    if snapshot.positions:
        avg_exit = np.mean([p.exit_days for p in snapshot.positions])
        liq_posture = min(1, max(0, 1 - avg_exit / 10))
    else:
        liq_posture = 1.0
    
    # Compute drift from baseline
    current_vector = np.array([
        factor_exposures["market"],
        factor_exposures["size"],
        factor_exposures["value"],
        factor_exposures["momentum"],
        factor_exposures["quality"],
        vol_posture,
        liq_posture
    ])
    
    baseline_vector = np.array([
        _factor_baseline["market"],
        _factor_baseline["size"],
        _factor_baseline["value"],
        _factor_baseline["momentum"],
        _factor_baseline["quality"],
        0.5,  # Neutral vol posture
        0.8   # High liquidity target
    ])
    
    # Euclidean distance
    drift = float(np.linalg.norm(current_vector - baseline_vector))
    
    # Drift components
    drift_components = {
        "market": abs(current_vector[0] - baseline_vector[0]),
        "size": abs(current_vector[1] - baseline_vector[1]),
        "value": abs(current_vector[2] - baseline_vector[2]),
        "momentum": abs(current_vector[3] - baseline_vector[3]),
        "quality": abs(current_vector[4] - baseline_vector[4]),
        "volatility_posture": abs(current_vector[5] - baseline_vector[5]),
        "liquidity_posture": abs(current_vector[6] - baseline_vector[6])
    }
    
    # Style consistency (inverse of drift variance over time)
    consistency = max(0, 1 - drift / 2)
    
    return PortfolioFingerprint(
        as_of=datetime.utcnow().isoformat(),
        factor_exposures=factor_exposures,
        sector_weights=sector_weights,
        region_weights=region_weights,
        volatility_posture=vol_posture,
        liquidity_posture=liq_posture,
        drift_from_baseline=drift,
        drift_components=drift_components,
        style_consistency_score=consistency
    )


# =============================================================================
# RISK METRICS COMPUTATION
# =============================================================================

def compute_risk_metrics() -> RiskMetrics:
    """Compute comprehensive risk metrics for the portfolio."""
    snapshot = create_snapshot(trigger="risk_computation")
    
    if not snapshot.positions:
        return RiskMetrics(
            as_of=datetime.utcnow().isoformat(),
            vol_ann=0,
            var_95=0,
            cvar_95=0,
            max_dd=0,
            current_dd=0,
            sharpe=0,
            sortino=0,
            quality=Quality(confidence=0.3, warnings=["No positions"])
        )
    
    # Aggregate returns
    all_returns = []
    weights = []
    
    for pos in snapshot.positions:
        ret = _get_returns(pos.ticker)
        if len(ret) > 20:
            all_returns.append(ret)
            weights.append(pos.weight)
    
    if not all_returns:
        return RiskMetrics(
            as_of=datetime.utcnow().isoformat(),
            vol_ann=0.15,
            var_95=0.02,
            cvar_95=0.03,
            max_dd=-0.10,
            current_dd=0,
            sharpe=0.5,
            sortino=0.6,
            quality=Quality(confidence=0.5, warnings=["Limited return data"])
        )
    
    # Align returns and compute portfolio return
    df = pd.concat(all_returns, axis=1).dropna()
    if len(df) < 20:
        return RiskMetrics(
            as_of=datetime.utcnow().isoformat(),
            vol_ann=0.15,
            var_95=0.02,
            cvar_95=0.03,
            max_dd=-0.10,
            current_dd=0,
            sharpe=0.5,
            sortino=0.6,
            quality=Quality(confidence=0.5, warnings=["Insufficient aligned data"])
        )
    
    weights_arr = np.array(weights[:len(df.columns)])
    weights_arr = weights_arr / weights_arr.sum()  # Normalize
    
    port_returns = (df.values @ weights_arr)
    port_returns = pd.Series(port_returns, index=df.index)
    
    # NAV simulation
    nav_series = (1 + port_returns).cumprod() * snapshot.nav
    
    # Compute metrics
    vol = realized_volatility(port_returns)
    var = value_at_risk(port_returns)
    cvar = conditional_var(port_returns)
    max_dd_val, _, _ = maximum_drawdown(nav_series)
    curr_dd = current_drawdown(nav_series)
    sharpe_val = sharpe_ratio(port_returns)
    sortino_val = sortino_ratio(port_returns)
    
    # Risk contributions
    cov, _ = ledoit_wolf_shrinkage(df)
    rc = percentage_risk_contribution(weights_arr, cov.values)
    risk_contributions = {df.columns[i]: float(rc[i]) for i in range(len(rc))}
    
    return RiskMetrics(
        as_of=datetime.utcnow().isoformat(),
        vol_ann=vol,
        var_95=var,
        cvar_95=cvar,
        max_dd=max_dd_val,
        current_dd=curr_dd,
        beta=1.0,
        sharpe=sharpe_val,
        sortino=sortino_val,
        treynor=sharpe_val,
        information_ratio=0,
        tracking_error=0,
        risk_contributions=risk_contributions,
        factor_risks={},
        quality=Quality(confidence=0.9)
    )
