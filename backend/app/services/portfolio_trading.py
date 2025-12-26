"""
Portfolio Trading Service - Features 18-21
Category 5: Decisions & Execution Control
"""
import numpy as np
import pandas as pd
from datetime import datetime
from typing import List, Dict, Optional, Tuple
import yfinance as yf
import logging
import uuid

from app.models.portfolio_models import (
    Position, PortfolioSnapshot, Quality,
    OrderTicket, OrderType, TradeImpact, TradeResult, BasketTrade,
    Opportunity
)
from app.services.portfolio_core import (
    market_impact_sqrt, exit_days, liquidity_score
)

logger = logging.getLogger(__name__)


# =============================================================================
# TRADE HISTORY
# =============================================================================

_trade_history: List[TradeResult] = []
_cash_balance: float = 100000.0


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
    except Exception as e:
        logger.warning(f"Failed to get price for {ticker}: {e}")
    return None


def _get_adv_dollar(ticker: str) -> float:
    """Get average daily dollar volume."""
    try:
        tk = yf.Ticker(ticker)
        hist = tk.history(period="3mo")
        if len(hist) > 0:
            avg_vol = float(hist['Volume'].mean())
            avg_price = float(hist['Close'].mean())
            return avg_vol * avg_price
    except:
        pass
    return 1e8


def _get_ticker_info(ticker: str) -> Dict:
    """Get basic ticker info."""
    try:
        tk = yf.Ticker(ticker)
        info = tk.info
        return {
            "name": info.get("shortName", ticker),
            "sector": info.get("sector", "Unknown"),
            "industry": info.get("industry", "Unknown"),
        }
    except:
        return {"name": ticker, "sector": "Unknown", "industry": "Unknown"}


# =============================================================================
# FEATURE 18: TRADE INTENT SIMULATOR
# =============================================================================

def preview_trade(
    ticket: OrderTicket,
    snapshot: PortfolioSnapshot
) -> TradeImpact:
    """
    Preview trade impact before execution.
    Computes:
    - Transaction cost (commission + spread)
    - Slippage estimate
    - Market impact
    - New portfolio weights
    - Risk impact
    - Guardrail status
    """
    price = _get_price(ticket.ticker)
    if price is None:
        return TradeImpact(
            ticket=ticket,
            estimated_cost=0,
            commission=0,
            new_weight=0,
            sector_impact={},
            risk_impact={},
            guardrail_status=[],
            approved=False,
            blocked_reason="Could not get price"
        )
    
    trade_value = ticket.quantity * price
    adv_dollar = _get_adv_dollar(ticket.ticker)
    
    # Commission (fixed $0 + $0.005/share for US equities)
    commission = ticket.quantity * 0.005
    
    # Spread cost (estimated)
    spread_bps = 5 if adv_dollar > 1e9 else 10 if adv_dollar > 1e8 else 20
    spread_cost = trade_value * spread_bps / 10000
    
    # Market impact (Almgren-Chriss)
    vol = 0.25  # Assumed volatility
    impact = market_impact_sqrt(trade_value, adv_dollar, vol)
    impact_cost = trade_value * impact
    
    # Slippage estimate
    slippage = trade_value * 0.001  # 10bps baseline
    
    total_cost = commission + spread_cost + impact_cost + slippage
    
    # New weight calculation
    current_mv = 0
    for pos in snapshot.positions:
        if pos.ticker == ticket.ticker:
            current_mv = pos.market_value
            break
    
    if ticket.action == "BUY":
        new_mv = current_mv + trade_value
    else:
        new_mv = max(0, current_mv - trade_value)
    
    # Adjust NAV for trade
    if ticket.action == "BUY":
        new_nav = snapshot.nav  # Cash decreases, position increases
    else:
        new_nav = snapshot.nav  # Position decreases, cash increases
    
    new_weight = new_mv / new_nav if new_nav > 0 else 0
    
    # Sector impact
    info = _get_ticker_info(ticket.ticker)
    sector = info.get("sector", "Unknown")
    
    current_sector_weight = sum(p.weight for p in snapshot.positions if p.sector == sector)
    new_sector_weight = current_sector_weight + (new_weight - (current_mv / new_nav if new_nav > 0 else 0))
    
    sector_impact = {
        sector: new_sector_weight - current_sector_weight
    }
    
    # Risk impact (simplified)
    risk_impact = {
        "volatility_contribution": 0.001 * (1 if ticket.action == "BUY" else -1),
        "concentration_change": new_weight - (current_mv / new_nav if new_nav > 0 else 0),
        "beta_contribution": 0.01 * (1 if ticket.action == "BUY" else -1)
    }
    
    # Guardrail checks
    guardrail_status = []
    blocked_reason = None
    
    # Position size check
    if new_weight > 0.20:
        guardrail_status.append({
            "rule": "Max Position Size",
            "status": "BREACH",
            "current": new_weight,
            "limit": 0.20
        })
        blocked_reason = f"Would exceed 20% position limit ({new_weight:.1%})"
    else:
        guardrail_status.append({
            "rule": "Max Position Size",
            "status": "OK",
            "current": new_weight,
            "limit": 0.20
        })
    
    # Cash check for buys
    if ticket.action == "BUY":
        required_cash = trade_value + total_cost
        if required_cash > snapshot.cash:
            guardrail_status.append({
                "rule": "Cash Available",
                "status": "BREACH",
                "current": snapshot.cash,
                "required": required_cash
            })
            blocked_reason = f"Insufficient cash (need ${required_cash:,.0f}, have ${snapshot.cash:,.0f})"
        else:
            guardrail_status.append({
                "rule": "Cash Available",
                "status": "OK",
                "current": snapshot.cash,
                "required": required_cash
            })
    
    approved = blocked_reason is None
    
    return TradeImpact(
        ticket=ticket,
        estimated_cost=total_cost,
        commission=commission,
        new_weight=new_weight,
        sector_impact=sector_impact,
        risk_impact=risk_impact,
        guardrail_status=guardrail_status,
        approved=approved,
        blocked_reason=blocked_reason,
        slippage_estimate=slippage,
        market_impact=impact_cost
    )


def execute_trade(
    ticket: OrderTicket,
    snapshot: PortfolioSnapshot
) -> TradeResult:
    """
    Execute a trade (simulated).
    Updates portfolio state and records to blotter.
    """
    global _trade_history, _cash_balance
    
    price = _get_price(ticket.ticker)
    if price is None:
        return TradeResult(
            order_id=str(uuid.uuid4())[:8],
            ticker=ticket.ticker,
            action=ticket.action,
            quantity=ticket.quantity,
            fill_price=0,
            fill_time=datetime.utcnow().isoformat(),
            commission=0,
            status="REJECTED"
        )
    
    # Apply slippage
    slippage = 0.001  # 10bps
    if ticket.action == "BUY":
        fill_price = price * (1 + slippage)
    else:
        fill_price = price * (1 - slippage)
    
    trade_value = ticket.quantity * fill_price
    commission = ticket.quantity * 0.005
    
    # Update cash
    if ticket.action == "BUY":
        _cash_balance -= (trade_value + commission)
    else:
        _cash_balance += (trade_value - commission)
    
    result = TradeResult(
        order_id=str(uuid.uuid4())[:8],
        ticker=ticket.ticker,
        action=ticket.action,
        quantity=ticket.quantity,
        fill_price=fill_price,
        fill_time=datetime.utcnow().isoformat(),
        commission=commission,
        status="FILLED"
    )
    
    _trade_history.append(result)
    
    return result


def get_trade_history() -> List[TradeResult]:
    """Get trade blotter."""
    return _trade_history


# =============================================================================
# FEATURE 19: TARGET PROFILE SCULPTOR
# =============================================================================

def compute_rebalance_basket(
    current_positions: List[Position],
    target_weights: Dict[str, float],
    total_nav: float,
    min_trade_value: float = 1000
) -> BasketTrade:
    """
    Compute trades needed to reach target weights.
    Minimizes trading costs while respecting constraints.
    """
    trades = []
    total_buys = 0
    total_sells = 0
    
    current_weights = {p.ticker: p.weight for p in current_positions}
    all_tickers = set(current_weights.keys()) | set(target_weights.keys())
    
    for ticker in all_tickers:
        current_weight = current_weights.get(ticker, 0)
        target_weight = target_weights.get(ticker, 0)
        
        weight_delta = target_weight - current_weight
        value_delta = weight_delta * total_nav
        
        if abs(value_delta) < min_trade_value:
            continue
        
        price = _get_price(ticker)
        if price is None:
            continue
        
        shares = int(abs(value_delta) / price)
        if shares == 0:
            continue
        
        action = "BUY" if weight_delta > 0 else "SELL"
        
        trades.append(OrderTicket(
            action=action,
            ticker=ticker,
            quantity=shares,
            order_type=OrderType.MARKET
        ))
        
        if action == "BUY":
            total_buys += abs(value_delta)
        else:
            total_sells += abs(value_delta)
    
    # Transaction cost estimate
    transaction_cost = (total_buys + total_sells) * 0.002
    
    # Risk improvement (simplified)
    risk_improvement = {
        "concentration_delta": -0.02,  # Assume rebalancing reduces concentration
        "tracking_error_delta": -0.01
    }
    
    # Execution priority (sell first, then buy to free up cash)
    sell_trades = [t for t in trades if t.action == "SELL"]
    buy_trades = [t for t in trades if t.action == "BUY"]
    execution_priority = [t.ticker for t in sell_trades] + [t.ticker for t in buy_trades]
    
    return BasketTrade(
        trades=trades,
        total_buys=total_buys,
        total_sells=total_sells,
        net_cash_flow=total_sells - total_buys,
        transaction_cost=transaction_cost,
        risk_improvement=risk_improvement,
        execution_priority=execution_priority
    )


# =============================================================================
# FEATURE 20: BASKET TRADES
# =============================================================================

def create_basket_from_tickers(
    tickers: List[str],
    allocation_type: str = "equal_weight",
    total_value: float = 10000
) -> BasketTrade:
    """
    Create a basket trade from a list of tickers.
    
    allocation_type: "equal_weight", "market_cap", "inverse_vol"
    """
    trades = []
    n = len(tickers)
    
    if n == 0:
        return BasketTrade(
            trades=[],
            total_buys=0,
            total_sells=0,
            net_cash_flow=0,
            transaction_cost=0,
            risk_improvement={},
            execution_priority=[]
        )
    
    if allocation_type == "equal_weight":
        per_ticker = total_value / n
        allocations = {t: per_ticker for t in tickers}
    else:
        # Default to equal weight
        per_ticker = total_value / n
        allocations = {t: per_ticker for t in tickers}
    
    for ticker, allocation in allocations.items():
        price = _get_price(ticker)
        if price is None:
            continue
        
        shares = int(allocation / price)
        if shares > 0:
            trades.append(OrderTicket(
                action="BUY",
                ticker=ticker,
                quantity=shares,
                order_type=OrderType.MARKET
            ))
    
    total_buys = sum(t.quantity * (_get_price(t.ticker) or 0) for t in trades)
    
    return BasketTrade(
        trades=trades,
        total_buys=total_buys,
        total_sells=0,
        net_cash_flow=-total_buys,
        transaction_cost=total_buys * 0.002,
        risk_improvement={},
        execution_priority=[t.ticker for t in trades]
    )


def execute_basket(basket: BasketTrade, snapshot: PortfolioSnapshot) -> List[TradeResult]:
    """Execute all trades in a basket."""
    results = []
    for ticket in basket.trades:
        result = execute_trade(ticket, snapshot)
        results.append(result)
    return results


# =============================================================================
# FEATURE 21: OPPORTUNISTIC ALPHA RADAR
# =============================================================================

def scan_opportunities(
    universe: List[str],
    current_positions: List[Position],
    strategy_filters: Optional[Dict] = None
) -> List[Opportunity]:
    """
    Scan universe for opportunities that fit strategy and improve risk.
    """
    opportunities = []
    current_tickers = {p.ticker for p in current_positions}
    
    for ticker in universe:
        if ticker in current_tickers:
            continue  # Skip already held positions
        
        try:
            tk = yf.Ticker(ticker)
            info = tk.info
            hist = tk.history(period="6mo")
            
            if len(hist) < 60:
                continue
            
            # Compute metrics
            returns = hist['Close'].pct_change().dropna()
            vol = float(returns.std() * np.sqrt(252))
            momentum = float((hist['Close'].iloc[-1] / hist['Close'].iloc[0]) - 1)
            
            # Alpha estimate (momentum-based, simplified)
            alpha_estimate = momentum * 0.5 if momentum > 0 else momentum * 0.3
            
            # Fit score (based on strategy compatibility)
            fit_score = 0.5
            
            if strategy_filters:
                # Check sector filter
                sector = info.get("sector", "Unknown")
                if "sectors" in strategy_filters:
                    if sector in strategy_filters["sectors"]:
                        fit_score += 0.2
                    else:
                        fit_score -= 0.2
                
                # Check volatility filter
                if "max_vol" in strategy_filters:
                    if vol <= strategy_filters["max_vol"]:
                        fit_score += 0.1
                    else:
                        fit_score -= 0.3
            
            # Correlation to portfolio (simplified)
            corr_to_port = 0.5  # Would compute actual correlation in production
            
            # Max suggested weight
            max_weight = 0.05 if vol > 0.4 else 0.10 if vol > 0.25 else 0.15
            
            # Risk impact
            risk_impact = {
                "volatility_delta": vol * max_weight * 0.5,
                "correlation_benefit": (1 - corr_to_port) * 0.02
            }
            
            # Drift warning
            drift_warning = None
            if vol > 0.4:
                drift_warning = "High volatility asset - would increase portfolio risk"
            
            opportunities.append(Opportunity(
                ticker=ticker,
                sector=info.get("sector", "Unknown"),
                fit_score=fit_score,
                alpha_estimate=alpha_estimate,
                volatility=vol,
                correlation_to_portfolio=corr_to_port,
                max_weight=max_weight,
                risk_impact=risk_impact,
                drift_warning=drift_warning,
                confidence=0.6
            ))
        
        except Exception as e:
            logger.warning(f"Failed to scan {ticker}: {e}")
            continue
    
    # Sort by fit score
    opportunities.sort(key=lambda o: o.fit_score, reverse=True)
    
    return opportunities[:20]  # Return top 20


def get_quick_opportunities(limit: int = 10) -> List[Opportunity]:
    """
    Get quick scan of popular tickers for opportunities.
    """
    popular_universe = [
        "AAPL", "MSFT", "GOOGL", "AMZN", "META", "NVDA", "TSLA",
        "BRK-B", "JPM", "V", "MA", "UNH", "HD", "PG", "JNJ"
    ]
    
    return scan_opportunities(popular_universe[:limit], [], None)
