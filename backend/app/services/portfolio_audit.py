"""
Portfolio Audit Service - Features 25-29
Category 7-8: Behavioral & Audit/Learning
"""
import numpy as np
import pandas as pd
from datetime import datetime, timedelta
from typing import List, Dict, Optional, Tuple
import hashlib
import json
import logging

from app.models.portfolio_models import (
    Position, Quality, Provenance,
    CounterfactualScenario, ContributionPeriod, ReturnPath,
    AuditEntry, PostTradeCheck
)

logger = logging.getLogger(__name__)


# =============================================================================
# AUDIT LOG STORAGE
# =============================================================================

_audit_log: List[AuditEntry] = []
_contribution_history: List[ContributionPeriod] = []


# =============================================================================
# FEATURE 25: COUNTERFACTUAL PORTFOLIO GENERATOR
# =============================================================================

def generate_counterfactual(
    positions: List[Position],
    scenario_type: str = "held_longer",
    lookback_days: int = 90
) -> CounterfactualScenario:
    """
    Generate counterfactual "what if" scenarios.
    
    scenario_type: "held_longer", "sold_earlier", "never_bought", "doubled_down"
    """
    actual_pnl = sum(p.pnl for p in positions)
    actual_return = actual_pnl / max(1, sum(p.cost_basis for p in positions))
    
    # Generate alternative scenario
    if scenario_type == "held_longer":
        # Assume continued trend
        avg_daily_ret = actual_return / lookback_days if lookback_days > 0 else 0
        hypothetical_days = lookback_days + 30
        hypothetical_return = avg_daily_ret * hypothetical_days * 1.1  # Slight improvement
        description = "If positions were held 30 days longer"
        
    elif scenario_type == "sold_earlier":
        # Assume sold at peak (20% better)
        hypothetical_return = actual_return * 1.2 if actual_return > 0 else actual_return * 0.5
        description = "If sold at recent peak"
        
    elif scenario_type == "never_bought":
        # Cash alternative (risk-free rate)
        hypothetical_return = 0.05 * lookback_days / 365
        description = "If kept as cash (5% annual rate)"
        
    elif scenario_type == "doubled_down":
        # 2x leverage on winners, 0.5x on losers
        winner_pnl = sum(p.pnl for p in positions if p.pnl > 0) * 2
        loser_pnl = sum(p.pnl for p in positions if p.pnl < 0) * 0.5
        hypothetical_pnl = winner_pnl + loser_pnl
        total_cost = sum(p.cost_basis for p in positions)
        hypothetical_return = hypothetical_pnl / max(1, total_cost)
        description = "If doubled down on winners, halved losers"
    else:
        hypothetical_return = actual_return
        description = "No change"
    
    # Position-level counterfactuals
    position_deltas = []
    for pos in positions:
        multiplier = 1.1 if scenario_type == "held_longer" else 1.2 if scenario_type == "sold_earlier" else 0 if scenario_type == "never_bought" else 1.5 if pos.pnl > 0 else 0.5
        hypothetical_pos_pnl = pos.pnl * multiplier if scenario_type != "never_bought" else 0
        position_deltas.append({
            "ticker": pos.ticker,
            "actual_pnl": pos.pnl,
            "hypothetical_pnl": hypothetical_pos_pnl,
            "delta": hypothetical_pos_pnl - pos.pnl
        })
    
    hypothetical_pnl_total = sum(p["hypothetical_pnl"] for p in position_deltas)
    
    return CounterfactualScenario(
        scenario_type=scenario_type,
        description=description,
        actual_return=actual_return,
        hypothetical_return=hypothetical_return,
        return_delta=hypothetical_return - actual_return,
        actual_pnl=actual_pnl,
        hypothetical_pnl=hypothetical_pnl_total,
        position_deltas=position_deltas,
        confidence=0.6,
        assumptions=[
            "Past trends continue",
            "No transaction costs",
            "Perfect execution"
        ]
    )


def generate_all_counterfactuals(positions: List[Position]) -> List[CounterfactualScenario]:
    """Generate all standard counterfactual scenarios."""
    scenarios = ["held_longer", "sold_earlier", "never_bought", "doubled_down"]
    return [generate_counterfactual(positions, s) for s in scenarios]


# =============================================================================
# FEATURE 26: ROLLING CONTRIBUTION REPLAY
# =============================================================================

def compute_contribution_replay(
    positions: List[Position],
    lookback_periods: int = 12  # Monthly periods
) -> List[ContributionPeriod]:
    """
    Compute rolling contribution of each position to portfolio returns.
    """
    global _contribution_history
    
    periods = []
    end_date = datetime.utcnow()
    
    for i in range(lookback_periods):
        period_end = end_date - timedelta(days=30 * i)
        period_start = period_end - timedelta(days=30)
        
        # Generate synthetic contribution data (would use actual returns in production)
        np.random.seed(i)
        
        contributions = {}
        total_contrib = 0
        
        for pos in positions:
            # Random contribution proportional to weight
            base_contrib = pos.weight * np.random.uniform(-0.03, 0.05)
            contributions[pos.ticker] = base_contrib
            total_contrib += base_contrib
        
        # Top/bottom contributors
        sorted_contribs = sorted(contributions.items(), key=lambda x: x[1])
        
        periods.append(ContributionPeriod(
            period_start=period_start.strftime("%Y-%m-%d"),
            period_end=period_end.strftime("%Y-%m-%d"),
            total_return=total_contrib,
            contributions=contributions,
            top_contributors=[t for t, _ in sorted_contribs[-3:]],
            bottom_contributors=[t for t, _ in sorted_contribs[:3]],
            attribution_quality=0.85
        ))
    
    _contribution_history = periods
    return periods


def get_contribution_summary(positions: List[Position]) -> Dict:
    """Get contribution summary across all periods."""
    periods = compute_contribution_replay(positions)
    
    # Aggregate contributions
    ticker_totals = {}
    for period in periods:
        for ticker, contrib in period.contributions.items():
            ticker_totals[ticker] = ticker_totals.get(ticker, 0) + contrib
    
    sorted_totals = sorted(ticker_totals.items(), key=lambda x: x[1], reverse=True)
    
    return {
        "periods_analyzed": len(periods),
        "cumulative_return": sum(p.total_return for p in periods),
        "best_contributors": sorted_totals[:5],
        "worst_contributors": sorted_totals[-5:],
        "consistency_score": 1 - np.std([p.total_return for p in periods]) / max(0.01, np.mean([abs(p.total_return) for p in periods]))
    }


# =============================================================================
# FEATURE 27: RETURN PATH ANALYSIS
# =============================================================================

def analyze_return_path(
    positions: List[Position],
    lookback_days: int = 252
) -> ReturnPath:
    """
    Decompose cumulative returns by source: skill, luck, risk, cost.
    """
    # Generate synthetic return decomposition
    np.random.seed(42)
    
    total_return = sum(p.pnl_pct * p.weight for p in positions)
    
    # Decomposition (simplified model)
    market_return = 0.10  # Assume 10% market return
    
    # Skill = alpha (excess return after accounting for beta)
    avg_beta = np.mean([p.beta for p in positions])
    expected_return = avg_beta * market_return
    alpha = total_return - expected_return
    
    # Luck component (residual volatility)
    luck = np.random.uniform(-0.02, 0.02)
    
    # Risk premium captured
    risk_premium = avg_beta * 0.05  # 5% equity risk premium
    
    # Costs
    costs = sum(p.market_value for p in positions) * 0.002 / max(1, sum(p.cost_basis for p in positions))
    
    # Adjustments
    skill = alpha - luck
    
    # Daily path (synthetic)
    dates = pd.date_range(end=datetime.utcnow(), periods=lookback_days, freq='D')
    cumulative_returns = np.cumsum(np.random.normal(total_return / lookback_days, 0.01, lookback_days))
    
    daily_path = [
        {"date": d.strftime("%Y-%m-%d"), "cumulative_return": float(r)}
        for d, r in zip(dates, cumulative_returns)
    ]
    
    return ReturnPath(
        period_start=(datetime.utcnow() - timedelta(days=lookback_days)).strftime("%Y-%m-%d"),
        period_end=datetime.utcnow().strftime("%Y-%m-%d"),
        total_return=total_return,
        skill_component=skill,
        luck_component=luck,
        risk_component=risk_premium,
        cost_component=-costs,
        market_component=expected_return,
        daily_path=daily_path,
        confidence_intervals={
            "skill_95": [skill - 0.05, skill + 0.05],
            "luck_95": [luck - 0.03, luck + 0.03]
        }
    )


# =============================================================================
# FEATURE 28: AUDIT & HISTORY CONSOLE
# =============================================================================

def log_audit_entry(
    action: str,
    entity_type: str,
    entity_id: str,
    changes: Dict,
    user: str = "system"
) -> AuditEntry:
    """Log an audit entry."""
    global _audit_log
    
    # Compute hash of changes
    change_hash = hashlib.sha256(json.dumps(changes, sort_keys=True, default=str).encode()).hexdigest()[:16]
    
    entry = AuditEntry(
        timestamp=datetime.utcnow().isoformat(),
        action=action,
        entity_type=entity_type,
        entity_id=entity_id,
        changes=changes,
        change_hash=change_hash,
        user=user,
        session_id=f"session_{datetime.utcnow().strftime('%Y%m%d')}",
        ip_address="127.0.0.1"
    )
    
    _audit_log.append(entry)
    
    # Keep only last 1000 entries
    if len(_audit_log) > 1000:
        _audit_log = _audit_log[-1000:]
    
    return entry


def get_audit_log(
    entity_type: Optional[str] = None,
    entity_id: Optional[str] = None,
    limit: int = 100
) -> List[AuditEntry]:
    """Get audit log with optional filters."""
    filtered = _audit_log
    
    if entity_type:
        filtered = [e for e in filtered if e.entity_type == entity_type]
    if entity_id:
        filtered = [e for e in filtered if e.entity_id == entity_id]
    
    return filtered[-limit:]


def get_audit_summary() -> Dict:
    """Get summary of audit activity."""
    if not _audit_log:
        return {"total_entries": 0, "by_action": {}, "by_entity": {}}
    
    by_action = {}
    by_entity = {}
    
    for entry in _audit_log:
        by_action[entry.action] = by_action.get(entry.action, 0) + 1
        by_entity[entry.entity_type] = by_entity.get(entry.entity_type, 0) + 1
    
    return {
        "total_entries": len(_audit_log),
        "by_action": by_action,
        "by_entity": by_entity,
        "first_entry": _audit_log[0].timestamp if _audit_log else None,
        "last_entry": _audit_log[-1].timestamp if _audit_log else None
    }


def export_audit_log(format: str = "json") -> str:
    """Export audit log."""
    if format == "json":
        return json.dumps([e.dict() for e in _audit_log], default=str, indent=2)
    else:
        # CSV format
        lines = ["timestamp,action,entity_type,entity_id,change_hash,user"]
        for e in _audit_log:
            lines.append(f"{e.timestamp},{e.action},{e.entity_type},{e.entity_id},{e.change_hash},{e.user}")
        return "\n".join(lines)


# =============================================================================
# FEATURE 29: POST-TRADE SANITY CHECK
# =============================================================================

def run_post_trade_check(
    trade_result: Dict,
    pre_trade_snapshot: Dict,
    post_trade_snapshot: Dict
) -> PostTradeCheck:
    """
    Run sanity checks after trade execution.
    """
    checks = []
    warnings = []
    errors = []
    
    # Check 1: Fill price vs expected
    expected_price = trade_result.get("expected_price", trade_result.get("fill_price"))
    fill_price = trade_result.get("fill_price", 0)
    slippage = abs(fill_price - expected_price) / expected_price if expected_price > 0 else 0
    
    if slippage > 0.01:
        warnings.append(f"High slippage: {slippage:.2%}")
        checks.append({"name": "Slippage", "status": "WARNING", "value": slippage})
    else:
        checks.append({"name": "Slippage", "status": "OK", "value": slippage})
    
    # Check 2: Position weight after trade
    ticker = trade_result.get("ticker")
    new_weight = 0
    for pos in post_trade_snapshot.get("positions", []):
        if pos.get("ticker") == ticker:
            new_weight = pos.get("weight", 0)
            break
    
    if new_weight > 0.20:
        errors.append(f"Position {ticker} exceeds 20% limit: {new_weight:.1%}")
        checks.append({"name": "Position Limit", "status": "ERROR", "value": new_weight})
    elif new_weight > 0.15:
        warnings.append(f"Position {ticker} approaching limit: {new_weight:.1%}")
        checks.append({"name": "Position Limit", "status": "WARNING", "value": new_weight})
    else:
        checks.append({"name": "Position Limit", "status": "OK", "value": new_weight})
    
    # Check 3: Cash balance
    pre_cash = pre_trade_snapshot.get("cash", 0)
    post_cash = post_trade_snapshot.get("cash", 0)
    cash_change = post_cash - pre_cash
    
    if post_cash < 0:
        errors.append("Negative cash balance after trade")
        checks.append({"name": "Cash Balance", "status": "ERROR", "value": post_cash})
    else:
        checks.append({"name": "Cash Balance", "status": "OK", "value": post_cash})
    
    # Check 4: NAV reconciliation
    pre_nav = pre_trade_snapshot.get("nav", 0)
    post_nav = post_trade_snapshot.get("nav", 0)
    nav_change = post_nav - pre_nav
    expected_nav_change = -cash_change  # Buying reduces cash, increases positions
    
    reconciliation_diff = abs(nav_change - expected_nav_change) if trade_result.get("action") == "BUY" else 0
    if reconciliation_diff > pre_nav * 0.001:  # 0.1% tolerance
        warnings.append(f"NAV reconciliation difference: ${reconciliation_diff:.2f}")
        checks.append({"name": "NAV Reconciliation", "status": "WARNING", "value": reconciliation_diff})
    else:
        checks.append({"name": "NAV Reconciliation", "status": "OK", "value": reconciliation_diff})
    
    # Check 5: Timestamp integrity
    trade_time = trade_result.get("fill_time")
    if trade_time:
        checks.append({"name": "Timestamp", "status": "OK", "value": trade_time})
    else:
        warnings.append("Missing fill timestamp")
        checks.append({"name": "Timestamp", "status": "WARNING", "value": None})
    
    # Overall status
    if errors:
        overall = "FAILED"
    elif warnings:
        overall = "PASSED_WITH_WARNINGS"
    else:
        overall = "PASSED"
    
    # Log to audit
    log_audit_entry(
        action="POST_TRADE_CHECK",
        entity_type="trade",
        entity_id=trade_result.get("order_id", "unknown"),
        changes={
            "status": overall,
            "checks": len(checks),
            "warnings": len(warnings),
            "errors": len(errors)
        }
    )
    
    return PostTradeCheck(
        trade_id=trade_result.get("order_id", "unknown"),
        timestamp=datetime.utcnow().isoformat(),
        checks=checks,
        warnings=warnings,
        errors=errors,
        overall_status=overall,
        remediation_actions=[
            "Review and adjust position" if errors else "No action required"
        ],
        quality=Quality(confidence=0.95 if not errors else 0.7)
    )
