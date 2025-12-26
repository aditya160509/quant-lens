"""
Portfolio v2 API Router
Complete API endpoints for 29-feature institutional portfolio system
"""
from fastapi import APIRouter, HTTPException, Query
from typing import List, Dict, Optional, Any
from datetime import datetime
import logging

from app.models.portfolio_models import (
    PortfolioSnapshot, RiskMetrics, HealthMeter, PortfolioBrainOutput,
    StateDelta, RevertSimulation, PortfolioFingerprint,
    CrossImpactOutput, LiquidityMap, ConcentrationMetrics, DrawdownAttribution,
    GuardrailsOutput, AlertsOutput, Alert,
    RegimeOutput, ShockPropagationResult,
    OrderTicket, TradeImpact, TradeResult, BasketTrade, Opportunity,
    PortfolioResponse, Quality, Provenance
)

logger = logging.getLogger(__name__)
router = APIRouter()


# =============================================================================
# CORE ENDPOINTS
# =============================================================================

@router.get("/portfolio/snapshot", response_model=PortfolioResponse)
async def get_snapshot():
    """
    GET /api/portfolio/snapshot
    Returns complete portfolio state with positions, weights, metrics.
    """
    try:
        from app.services.portfolio_brain import create_snapshot
        snapshot = create_snapshot(trigger="api")
        return PortfolioResponse(data=snapshot.dict())
    except Exception as e:
        logger.error(f"Failed to get snapshot: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/portfolio/risk", response_model=PortfolioResponse)
async def get_risk():
    """
    GET /api/portfolio/risk
    Returns comprehensive risk metrics.
    """
    try:
        from app.services.portfolio_brain import compute_risk_metrics
        metrics = compute_risk_metrics()
        return PortfolioResponse(data=metrics.dict())
    except Exception as e:
        logger.error(f"Failed to get risk metrics: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# =============================================================================
# FEATURE 1: PORTFOLIO BRAIN
# =============================================================================

@router.get("/portfolio/brain", response_model=PortfolioResponse)
async def get_brain():
    """
    GET /api/portfolio/brain
    Returns executive summary, risk ranking, stabilizers, recommendations.
    """
    try:
        from app.services.portfolio_brain import (
            create_snapshot, compute_risk_metrics, compute_portfolio_brain
        )
        snapshot = create_snapshot(trigger="brain")
        risk_metrics = compute_risk_metrics()
        brain = compute_portfolio_brain(snapshot, risk_metrics)
        return PortfolioResponse(data=brain.dict())
    except Exception as e:
        logger.error(f"Failed to get brain: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# =============================================================================
# FEATURE 2: HEALTH METER
# =============================================================================

@router.get("/portfolio/health", response_model=PortfolioResponse)
async def get_health():
    """
    GET /api/portfolio/health
    Returns real-time health meter with components.
    """
    try:
        from app.services.portfolio_brain import (
            create_snapshot, compute_risk_metrics, compute_health_meter
        )
        snapshot = create_snapshot(trigger="health")
        risk_metrics = compute_risk_metrics()
        health = compute_health_meter(snapshot, risk_metrics)
        return PortfolioResponse(data=health.dict())
    except Exception as e:
        logger.error(f"Failed to get health: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# =============================================================================
# FEATURE 3: STATES & SNAPSHOTS
# =============================================================================

@router.get("/portfolio/states", response_model=PortfolioResponse)
async def get_states():
    """
    GET /api/portfolio/states
    Returns list of saved portfolio states.
    """
    try:
        from app.services.portfolio_brain import get_snapshots
        states = get_snapshots()
        return PortfolioResponse(data={"states": states, "count": len(states)})
    except Exception as e:
        logger.error(f"Failed to get states: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/portfolio/states", response_model=PortfolioResponse)
async def create_state(notes: str = ""):
    """
    POST /api/portfolio/states
    Creates a new portfolio snapshot.
    """
    try:
        from app.services.portfolio_brain import create_snapshot
        snapshot = create_snapshot(trigger="manual", notes=notes)
        return PortfolioResponse(data=snapshot.dict())
    except Exception as e:
        logger.error(f"Failed to create state: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/portfolio/states/diff", response_model=PortfolioResponse)
async def get_state_diff(from_id: str, to_id: str):
    """
    GET /api/portfolio/states/diff
    Compares two portfolio states.
    """
    try:
        from app.services.portfolio_brain import compute_state_delta
        delta = compute_state_delta(from_id, to_id)
        return PortfolioResponse(data=delta.dict())
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        logger.error(f"Failed to compute diff: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/portfolio/states/revert-preview", response_model=PortfolioResponse)
async def preview_revert(target_id: str):
    """
    GET /api/portfolio/states/revert-preview
    Simulates impact of reverting to a previous state.
    """
    try:
        from app.services.portfolio_brain import simulate_revert
        simulation = simulate_revert(target_id)
        return PortfolioResponse(data=simulation.dict())
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        logger.error(f"Failed to simulate revert: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# =============================================================================
# FEATURE 4: FINGERPRINT
# =============================================================================

@router.get("/portfolio/fingerprint", response_model=PortfolioResponse)
async def get_fingerprint():
    """
    GET /api/portfolio/fingerprint
    Returns style fingerprint with factor exposures and drift.
    """
    try:
        from app.services.portfolio_brain import create_snapshot, compute_fingerprint
        snapshot = create_snapshot(trigger="fingerprint")
        fingerprint = compute_fingerprint(snapshot)
        return PortfolioResponse(data=fingerprint.dict())
    except Exception as e:
        logger.error(f"Failed to get fingerprint: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# =============================================================================
# FEATURE 5: CROSS-IMPACT MATRIX
# =============================================================================

@router.get("/portfolio/cross-impact", response_model=PortfolioResponse)
async def get_cross_impact():
    """
    GET /api/portfolio/cross-impact
    Returns correlation matrix, network centrality, clusters.
    """
    try:
        from app.services.portfolio_brain import create_snapshot
        from app.services.portfolio_risk import compute_cross_impact
        snapshot = create_snapshot(trigger="cross_impact")
        cross_impact = compute_cross_impact(snapshot.positions)
        return PortfolioResponse(data=cross_impact.dict())
    except Exception as e:
        logger.error(f"Failed to get cross-impact: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# =============================================================================
# FEATURE 6: LIQUIDITY MAP
# =============================================================================

@router.get("/portfolio/liquidity", response_model=PortfolioResponse)
async def get_liquidity(stress: float = 2.0):
    """
    GET /api/portfolio/liquidity
    Returns liquidity analysis with exit times and bottlenecks.
    """
    try:
        from app.services.portfolio_brain import create_snapshot
        from app.services.portfolio_risk import compute_liquidity_map
        snapshot = create_snapshot(trigger="liquidity")
        liquidity = compute_liquidity_map(snapshot.positions, stress)
        return PortfolioResponse(data=liquidity.dict())
    except Exception as e:
        logger.error(f"Failed to get liquidity: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# =============================================================================
# FEATURE 7: CROWDING SCANNER
# =============================================================================

@router.get("/portfolio/concentration", response_model=PortfolioResponse)
async def get_concentration():
    """
    GET /api/portfolio/concentration
    Returns concentration and crowding analysis.
    """
    try:
        from app.services.portfolio_brain import create_snapshot
        from app.services.portfolio_risk import compute_concentration
        snapshot = create_snapshot(trigger="concentration")
        concentration = compute_concentration(snapshot.positions)
        return PortfolioResponse(data=concentration.dict())
    except Exception as e:
        logger.error(f"Failed to get concentration: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# =============================================================================
# FEATURE 8: DRAWDOWN SENSITIVITY
# =============================================================================

@router.get("/portfolio/drawdown-sensitivity", response_model=PortfolioResponse)
async def get_drawdown_sensitivity():
    """
    GET /api/portfolio/drawdown-sensitivity
    Returns drawdown attribution and sensitivity analysis.
    """
    try:
        from app.services.portfolio_brain import create_snapshot
        from app.services.portfolio_risk import compute_drawdown_sensitivity
        snapshot = create_snapshot(trigger="drawdown")
        dd_sensitivity = compute_drawdown_sensitivity(snapshot.positions)
        return PortfolioResponse(data=dd_sensitivity.dict())
    except Exception as e:
        logger.error(f"Failed to get drawdown sensitivity: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# =============================================================================
# FEATURE 9: CAPITAL GUARDRAILS
# =============================================================================

@router.get("/portfolio/guardrails", response_model=PortfolioResponse)
async def get_guardrails():
    """
    GET /api/portfolio/guardrails
    Returns all guardrail statuses with utilization.
    """
    try:
        from app.services.portfolio_brain import create_snapshot, compute_risk_metrics
        from app.services.portfolio_risk import evaluate_guardrails
        snapshot = create_snapshot(trigger="guardrails")
        risk_metrics = compute_risk_metrics()
        guardrails = evaluate_guardrails(snapshot, risk_metrics.dict())
        return PortfolioResponse(data=guardrails.dict())
    except Exception as e:
        logger.error(f"Failed to get guardrails: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# =============================================================================
# FEATURE 10: AUTO-ALERT BRAIN
# =============================================================================

@router.get("/portfolio/alerts", response_model=PortfolioResponse)
async def get_alerts():
    """
    GET /api/portfolio/alerts
    Returns active alerts with severity and evidence.
    """
    try:
        from app.services.portfolio_brain import create_snapshot, compute_risk_metrics
        from app.services.portfolio_risk import evaluate_alerts
        snapshot = create_snapshot(trigger="alerts")
        risk_metrics = compute_risk_metrics()
        alerts = evaluate_alerts(snapshot, risk_metrics.dict())
        return PortfolioResponse(data=alerts.dict())
    except Exception as e:
        logger.error(f"Failed to get alerts: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.put("/portfolio/alerts/{alert_id}/acknowledge")
async def acknowledge_alert(alert_id: str):
    """
    PUT /api/portfolio/alerts/{id}/acknowledge
    Acknowledges an alert.
    """
    try:
        from app.services.portfolio_risk import acknowledge_alert
        acknowledge_alert(alert_id)
        return {"success": True, "message": f"Alert {alert_id} acknowledged"}
    except Exception as e:
        logger.error(f"Failed to acknowledge alert: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.put("/portfolio/alerts/{alert_id}/resolve")
async def resolve_alert(alert_id: str):
    """
    PUT /api/portfolio/alerts/{id}/resolve
    Resolves an alert.
    """
    try:
        from app.services.portfolio_risk import resolve_alert
        resolve_alert(alert_id)
        return {"success": True, "message": f"Alert {alert_id} resolved"}
    except Exception as e:
        logger.error(f"Failed to resolve alert: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# =============================================================================
# FEATURE 11: WEATHER STATION (REGIMES)
# =============================================================================

@router.get("/portfolio/regime", response_model=PortfolioResponse)
async def get_regime():
    """
    GET /api/portfolio/regime
    Returns current regime classification and history.
    """
    try:
        from app.services.portfolio_regimes import compute_weather_station
        regime = compute_weather_station()
        return PortfolioResponse(data=regime.dict())
    except Exception as e:
        logger.error(f"Failed to get regime: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# =============================================================================
# FEATURE 12: SHOCK SIMULATOR
# =============================================================================

@router.post("/portfolio/shock", response_model=PortfolioResponse)
async def run_shock(shocks: Dict[str, float] = None, scenario: str = None):
    """
    POST /api/portfolio/shock
    Runs shock propagation simulation.
    
    Either provide:
    - shocks: Dict of {ticker: shock_magnitude}
    - scenario: Predefined scenario name
    """
    try:
        from app.services.portfolio_brain import create_snapshot
        from app.services.portfolio_regimes import (
            simulate_shock_propagation, run_predefined_scenario
        )
        
        snapshot = create_snapshot(trigger="shock")
        
        if scenario:
            result = run_predefined_scenario(snapshot.positions, scenario)
        elif shocks:
            result = simulate_shock_propagation(snapshot.positions, shocks)
        else:
            # Default: -10% all positions
            default_shocks = {p.ticker: -0.10 for p in snapshot.positions}
            result = simulate_shock_propagation(snapshot.positions, default_shocks)
        
        return PortfolioResponse(data=result.dict())
    except Exception as e:
        logger.error(f"Failed to run shock: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# =============================================================================
# FEATURE 18: TRADE PREVIEW
# =============================================================================

@router.post("/portfolio/trade/preview", response_model=PortfolioResponse)
async def preview_trade(
    action: str,
    ticker: str,
    quantity: float,
    order_type: str = "MARKET"
):
    """
    POST /api/portfolio/trade/preview
    Preview trade impact before execution.
    """
    try:
        from app.services.portfolio_brain import create_snapshot
        from app.services.portfolio_trading import preview_trade
        from app.models.portfolio_models import OrderTicket, OrderType
        
        snapshot = create_snapshot(trigger="trade_preview")
        
        ticket = OrderTicket(
            action=action.upper(),
            ticker=ticker.upper(),
            quantity=quantity,
            order_type=OrderType(order_type)
        )
        
        impact = preview_trade(ticket, snapshot)
        return PortfolioResponse(data=impact.dict())
    except Exception as e:
        logger.error(f"Failed to preview trade: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# =============================================================================
# FEATURE 18-20: TRADE EXECUTION
# =============================================================================

@router.post("/portfolio/trade/execute", response_model=PortfolioResponse)
async def execute_trade(
    action: str,
    ticker: str,
    quantity: float,
    order_type: str = "MARKET"
):
    """
    POST /api/portfolio/trade/execute
    Execute a trade.
    """
    try:
        from app.services.portfolio_brain import (
            create_snapshot, update_portfolio_holdings, remove_holding
        )
        from app.services.portfolio_trading import execute_trade as exec_trade
        from app.models.portfolio_models import OrderTicket, OrderType
        
        snapshot = create_snapshot(trigger="trade_execute")
        
        ticket = OrderTicket(
            action=action.upper(),
            ticker=ticker.upper(),
            quantity=quantity,
            order_type=OrderType(order_type)
        )
        
        result = exec_trade(ticket, snapshot)
        
        # Update portfolio state
        if result.status == "FILLED":
            current_shares = 0
            current_cost = 0
            for pos in snapshot.positions:
                if pos.ticker == ticker.upper():
                    current_shares = pos.shares
                    current_cost = pos.cost_basis
                    break
            
            if action.upper() == "BUY":
                new_shares = current_shares + quantity
                new_cost = current_cost + (result.fill_price * quantity)
                update_portfolio_holdings(ticker.upper(), new_shares, new_cost)
            else:
                new_shares = current_shares - quantity
                if new_shares <= 0:
                    remove_holding(ticker.upper())
                else:
                    remaining_cost = current_cost * (new_shares / current_shares) if current_shares > 0 else 0
                    update_portfolio_holdings(ticker.upper(), new_shares, remaining_cost)
        
        return PortfolioResponse(data=result.dict())
    except Exception as e:
        logger.error(f"Failed to execute trade: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/portfolio/trade/history", response_model=PortfolioResponse)
async def get_trade_history():
    """
    GET /api/portfolio/trade/history
    Returns trade blotter.
    """
    try:
        from app.services.portfolio_trading import get_trade_history
        history = get_trade_history()
        return PortfolioResponse(data={"trades": [t.dict() for t in history]})
    except Exception as e:
        logger.error(f"Failed to get trade history: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/portfolio/trade/basket", response_model=PortfolioResponse)
async def create_basket(
    tickers: List[str],
    allocation: str = "equal_weight",
    total_value: float = 10000
):
    """
    POST /api/portfolio/trade/basket
    Create a basket trade from tickers.
    """
    try:
        from app.services.portfolio_trading import create_basket_from_tickers
        basket = create_basket_from_tickers(tickers, allocation, total_value)
        return PortfolioResponse(data=basket.dict())
    except Exception as e:
        logger.error(f"Failed to create basket: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# =============================================================================
# FEATURE 21: ALPHA RADAR
# =============================================================================

@router.get("/portfolio/opportunities", response_model=PortfolioResponse)
async def get_opportunities(limit: int = 10):
    """
    GET /api/portfolio/opportunities
    Returns ranked opportunities from alpha radar.
    """
    try:
        from app.services.portfolio_trading import get_quick_opportunities
        opportunities = get_quick_opportunities(limit)
        return PortfolioResponse(data={"opportunities": [o.dict() for o in opportunities]})
    except Exception as e:
        logger.error(f"Failed to get opportunities: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# =============================================================================
# HOLDINGS & CASH MANAGEMENT
# =============================================================================

@router.get("/portfolio/holdings", response_model=PortfolioResponse)
async def get_holdings():
    """
    GET /api/portfolio/holdings
    Returns current positions.
    """
    try:
        from app.services.portfolio_brain import create_snapshot
        snapshot = create_snapshot(trigger="holdings")
        return PortfolioResponse(data={
            "positions": [p.dict() for p in snapshot.positions],
            "cash": snapshot.cash,
            "nav": snapshot.nav
        })
    except Exception as e:
        logger.error(f"Failed to get holdings: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/portfolio/holdings/add", response_model=PortfolioResponse)
async def add_holding(ticker: str, shares: float, cost_basis: float = 0):
    """
    POST /api/portfolio/holdings/add
    Add a new holding (for demo/testing).
    """
    try:
        from app.services.portfolio_brain import update_portfolio_holdings, create_snapshot
        import yfinance as yf
        
        # Get current price if cost_basis not provided
        if cost_basis == 0:
            tk = yf.Ticker(ticker.upper())
            hist = tk.history(period="5d")
            if len(hist) > 0:
                cost_basis = float(hist['Close'].iloc[-1]) * shares
        
        update_portfolio_holdings(ticker.upper(), shares, cost_basis)
        snapshot = create_snapshot(trigger="add_holding")
        
        return PortfolioResponse(data={
            "message": f"Added {shares} shares of {ticker}",
            "nav": snapshot.nav
        })
    except Exception as e:
        logger.error(f"Failed to add holding: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/portfolio/cash/set", response_model=PortfolioResponse)
async def set_cash(amount: float):
    """
    POST /api/portfolio/cash/set
    Set cash balance (for demo/testing).
    """
    try:
        from app.services.portfolio_brain import update_cash
        update_cash(amount)
        return PortfolioResponse(data={"cash": amount})
    except Exception as e:
        logger.error(f"Failed to set cash: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# =============================================================================
# SUMMARY ENDPOINT
# =============================================================================

@router.get("/portfolio/summary", response_model=PortfolioResponse)
async def get_summary():
    """
    GET /api/portfolio/summary
    Returns quick summary of portfolio status.
    """
    try:
        from app.services.portfolio_brain import (
            create_snapshot, compute_risk_metrics, compute_health_meter
        )
        from app.services.portfolio_risk import evaluate_guardrails, evaluate_alerts
        from app.services.portfolio_regimes import classify_regime
        
        snapshot = create_snapshot(trigger="summary")
        risk_metrics = compute_risk_metrics()
        health = compute_health_meter(snapshot, risk_metrics)
        guardrails = evaluate_guardrails(snapshot, risk_metrics.dict())
        alerts = evaluate_alerts(snapshot, risk_metrics.dict())
        regime, confidence = classify_regime()
        
        summary = {
            "nav": snapshot.nav,
            "cash": snapshot.cash,
            "positions_count": len(snapshot.positions),
            "health_score": health.score,
            "health_label": health.label,
            "volatility": risk_metrics.vol_ann,
            "sharpe": risk_metrics.sharpe,
            "current_drawdown": risk_metrics.current_dd,
            "guardrail_breaches": len(guardrails.breaches),
            "active_alerts": len(alerts.active_alerts),
            "regime": regime.value,
            "regime_confidence": confidence
        }
        
        return PortfolioResponse(data=summary)
    except Exception as e:
        logger.error(f"Failed to get summary: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# =============================================================================
# FEATURE 13-17: STRATEGY SYSTEM
# =============================================================================

@router.get("/portfolio/strategies", response_model=PortfolioResponse)
async def get_strategies():
    """
    GET /api/portfolio/strategies
    Returns available strategy templates.
    """
    try:
        from app.services.portfolio_strategy import get_available_strategies
        strategies = get_available_strategies()
        return PortfolioResponse(data={"strategies": strategies})
    except Exception as e:
        logger.error(f"Failed to get strategies: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/portfolio/strategies/activate", response_model=PortfolioResponse)
async def activate_strategy(slot_id: str, strategy_id: str, weight: float = 1.0):
    """
    POST /api/portfolio/strategies/activate
    Activate a strategy in a slot.
    """
    try:
        from app.services.portfolio_strategy import activate_strategy_slot
        slot = activate_strategy_slot(slot_id, strategy_id, weight)
        return PortfolioResponse(data=slot.dict())
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Failed to activate strategy: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/portfolio/strategies/active", response_model=PortfolioResponse)
async def get_active_strategies():
    """
    GET /api/portfolio/strategies/active
    Get all active strategy slots.
    """
    try:
        from app.services.portfolio_strategy import get_active_slots
        slots = get_active_slots()
        return PortfolioResponse(data={"slots": [s.dict() for s in slots]})
    except Exception as e:
        logger.error(f"Failed to get active strategies: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/portfolio/strategies/backtest", response_model=PortfolioResponse)
async def backtest_strategy(strategy_id: str, lookback_days: int = 252):
    """
    POST /api/portfolio/strategies/backtest
    Backtest a strategy.
    """
    try:
        from app.services.portfolio_brain import create_snapshot
        from app.services.portfolio_strategy import backtest_strategy
        snapshot = create_snapshot(trigger="backtest")
        result = backtest_strategy(strategy_id, snapshot.positions, lookback_days)
        return PortfolioResponse(data=result.dict())
    except Exception as e:
        logger.error(f"Failed to backtest strategy: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/portfolio/strategies/divergence", response_model=PortfolioResponse)
async def get_strategy_divergence():
    """
    GET /api/portfolio/strategies/divergence
    Get divergence between strategy targets and actual portfolio.
    """
    try:
        from app.services.portfolio_brain import create_snapshot
        from app.services.portfolio_strategy import monitor_strategy_divergence
        snapshot = create_snapshot(trigger="divergence")
        divergence = monitor_strategy_divergence(snapshot.positions)
        return PortfolioResponse(data=divergence.dict())
    except Exception as e:
        logger.error(f"Failed to get divergence: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# =============================================================================
# FEATURE 22-24: HEDGING
# =============================================================================

@router.get("/portfolio/hedge/response", response_model=PortfolioResponse)
async def get_hedge_response(target_protection: float = 0.10, max_cost: float = 0.02):
    """
    GET /api/portfolio/hedge/response
    Get hedge recommendations.
    """
    try:
        from app.services.portfolio_brain import create_snapshot
        from app.services.portfolio_hedging import compute_hedge_response
        snapshot = create_snapshot(trigger="hedge")
        response = compute_hedge_response(snapshot.positions, target_protection, max_cost)
        return PortfolioResponse(data=response.dict())
    except Exception as e:
        logger.error(f"Failed to get hedge response: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/portfolio/hedge/clock", response_model=PortfolioResponse)
async def get_hedge_clock():
    """
    GET /api/portfolio/hedge/clock
    Get hedge rebalancing clock.
    """
    try:
        from app.services.portfolio_brain import create_snapshot
        from app.services.portfolio_hedging import compute_hedge_clock
        snapshot = create_snapshot(trigger="hedge_clock")
        clock = compute_hedge_clock(snapshot.positions)
        return PortfolioResponse(data=clock.dict())
    except Exception as e:
        logger.error(f"Failed to get hedge clock: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/portfolio/hedge/pnl", response_model=PortfolioResponse)
async def get_hedge_pnl():
    """
    GET /api/portfolio/hedge/pnl
    Get hedge P&L.
    """
    try:
        from app.services.portfolio_hedging import compute_hedge_pnl
        pnl = compute_hedge_pnl()
        return PortfolioResponse(data=pnl.dict())
    except Exception as e:
        logger.error(f"Failed to get hedge pnl: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/portfolio/hedge/add", response_model=PortfolioResponse)
async def add_hedge(ticker: str, shares: float, entry_price: float):
    """
    POST /api/portfolio/hedge/add
    Add a hedge position.
    """
    try:
        from app.services.portfolio_hedging import add_hedge
        hedge = add_hedge(ticker.upper(), shares, entry_price)
        return PortfolioResponse(data=hedge.dict())
    except Exception as e:
        logger.error(f"Failed to add hedge: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# =============================================================================
# FEATURE 25-29: AUDIT & BEHAVIORAL
# =============================================================================

@router.get("/portfolio/counterfactual", response_model=PortfolioResponse)
async def get_counterfactual(scenario_type: str = "held_longer"):
    """
    GET /api/portfolio/counterfactual
    Generate counterfactual scenario.
    """
    try:
        from app.services.portfolio_brain import create_snapshot
        from app.services.portfolio_audit import generate_counterfactual
        snapshot = create_snapshot(trigger="counterfactual")
        result = generate_counterfactual(snapshot.positions, scenario_type)
        return PortfolioResponse(data=result.dict())
    except Exception as e:
        logger.error(f"Failed to get counterfactual: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/portfolio/contribution", response_model=PortfolioResponse)
async def get_contribution():
    """
    GET /api/portfolio/contribution
    Get rolling contribution analysis.
    """
    try:
        from app.services.portfolio_brain import create_snapshot
        from app.services.portfolio_audit import get_contribution_summary
        snapshot = create_snapshot(trigger="contribution")
        summary = get_contribution_summary(snapshot.positions)
        return PortfolioResponse(data=summary)
    except Exception as e:
        logger.error(f"Failed to get contribution: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/portfolio/return-path", response_model=PortfolioResponse)
async def get_return_path():
    """
    GET /api/portfolio/return-path
    Get return decomposition (skill, luck, risk).
    """
    try:
        from app.services.portfolio_brain import create_snapshot
        from app.services.portfolio_audit import analyze_return_path
        snapshot = create_snapshot(trigger="return_path")
        path = analyze_return_path(snapshot.positions)
        return PortfolioResponse(data=path.dict())
    except Exception as e:
        logger.error(f"Failed to get return path: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/portfolio/audit", response_model=PortfolioResponse)
async def get_audit_log(entity_type: Optional[str] = None, limit: int = 100):
    """
    GET /api/portfolio/audit
    Get audit log.
    """
    try:
        from app.services.portfolio_audit import get_audit_log, get_audit_summary
        log = get_audit_log(entity_type=entity_type, limit=limit)
        summary = get_audit_summary()
        return PortfolioResponse(data={
            "log": [e.dict() for e in log],
            "summary": summary
        })
    except Exception as e:
        logger.error(f"Failed to get audit log: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/portfolio/post-trade-check", response_model=PortfolioResponse)
async def run_post_trade_check(trade_result: Dict, pre_snapshot: Dict, post_snapshot: Dict):
    """
    POST /api/portfolio/post-trade-check
    Run post-trade sanity check.
    """
    try:
        from app.services.portfolio_audit import run_post_trade_check
        check = run_post_trade_check(trade_result, pre_snapshot, post_snapshot)
        return PortfolioResponse(data=check.dict())
    except Exception as e:
        logger.error(f"Failed to run post-trade check: {e}")
        raise HTTPException(status_code=500, detail=str(e))
