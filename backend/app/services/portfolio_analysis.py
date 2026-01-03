"""
Portfolio Analysis Service - Features 41, 42, 43
Holdings Overlap, Dividend Tracker, Tax Lot Optimizer
"""
import numpy as np
import pandas as pd
from typing import List, Dict, Optional, Any
import yfinance as yf
import logging
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)


# =============================================================================
# FEATURE 41: HOLDINGS OVERLAP
# =============================================================================

def compute_holdings_overlap(
    portfolios: List[Dict],
    etf_holdings: Optional[Dict[str, List[Dict]]] = None
) -> Dict[str, Any]:
    """
    Detect exposure redundancy across portfolios and ETFs.
    
    Args:
        portfolios: List of portfolio dicts with:
            - name: Portfolio name
            - holdings: List of {ticker, weight} dicts
        etf_holdings: Optional dict of ETF ticker -> list of {ticker, weight}
    
    Returns:
        Dict with overlap_matrix, overlapping_holdings, redundancy_score
    """
    try:
        # Combine all entities (portfolios + ETFs)
        entities = {}
        
        for port in portfolios:
            name = port.get("name", f"Portfolio_{len(entities)}")
            holdings = {h.get("ticker"): h.get("weight", 0) for h in port.get("holdings", [])}
            entities[name] = holdings
        
        if etf_holdings:
            for etf, holdings in etf_holdings.items():
                entities[etf] = {h.get("ticker"): h.get("weight", 0) for h in holdings}
        
        entity_names = list(entities.keys())
        n_entities = len(entity_names)
        
        # Compute pairwise overlap matrix
        overlap_matrix = {}
        for i, name1 in enumerate(entity_names):
            overlap_matrix[name1] = {}
            for j, name2 in enumerate(entity_names):
                if i == j:
                    overlap_matrix[name1][name2] = 100.0
                else:
                    # Overlap = sum of min weights for shared holdings
                    holdings1 = entities[name1]
                    holdings2 = entities[name2]
                    shared = set(holdings1.keys()) & set(holdings2.keys())
                    
                    overlap = sum(min(holdings1.get(t, 0), holdings2.get(t, 0)) for t in shared)
                    overlap_pct = overlap * 100
                    overlap_matrix[name1][name2] = float(overlap_pct)
        
        # Identify all overlapping holdings
        all_holdings = {}
        for name, holdings in entities.items():
            for ticker, weight in holdings.items():
                if ticker not in all_holdings:
                    all_holdings[ticker] = {}
                all_holdings[ticker][name] = weight
        
        # Filter to holdings in multiple entities
        overlapping_holdings = []
        for ticker, presence in all_holdings.items():
            if len(presence) > 1:
                total_exposure = sum(presence.values())
                overlapping_holdings.append({
                    "ticker": ticker,
                    "presence": presence,
                    "count": len(presence),
                    "total_exposure": float(total_exposure)
                })
        
        # Sort by total exposure
        overlapping_holdings.sort(key=lambda x: x["total_exposure"], reverse=True)
        
        # Effective concentration (what you really own)
        effective_holdings = {}
        for ticker, presence in all_holdings.items():
            effective_holdings[ticker] = float(sum(presence.values()) / n_entities)
        
        # Sort by effective weight
        top_effective = sorted(effective_holdings.items(), key=lambda x: x[1], reverse=True)[:20]
        
        # Mega-cap exposure warning
        mega_caps = ["AAPL", "MSFT", "GOOGL", "AMZN", "NVDA", "META", "TSLA"]
        mega_cap_exposure = sum(effective_holdings.get(t, 0) for t in mega_caps)
        
        # Redundancy score (0-100)
        total_overlap = 0
        for name1 in entity_names:
            for name2 in entity_names:
                if name1 != name2:
                    total_overlap += overlap_matrix[name1][name2]
        
        avg_overlap = total_overlap / (n_entities * (n_entities - 1)) if n_entities > 1 else 0
        redundancy_score = min(100, avg_overlap)
        
        # Diversification illusion
        unique_holdings = len(all_holdings)
        
        return {
            "overlap_matrix": overlap_matrix,
            "overlapping_holdings": overlapping_holdings[:30],  # Top 30
            "effective_concentration": dict(top_effective),
            "metrics": {
                "redundancy_score": float(redundancy_score),
                "unique_holdings": unique_holdings,
                "mega_cap_exposure": float(mega_cap_exposure),
                "avg_pairwise_overlap": float(avg_overlap)
            },
            "diversification_warning": {
                "illusory": redundancy_score > 30,
                "message": f"Effective exposure is {unique_holdings} securities, but {redundancy_score:.0f}% overlap exists"
            }
        }
        
    except Exception as e:
        logger.error(f"Holdings overlap error: {e}")
        return {"error": str(e)}


# =============================================================================
# FEATURE 42: DIVIDEND TRACKER
# =============================================================================

def compute_dividends(
    positions: List[Dict],
    reinvest: bool = False,
    growth_rate: float = 0.03,
    horizon_years: int = 5
) -> Dict[str, Any]:
    """
    Income analysis for dividend-focused portfolios.
    
    Args:
        positions: List of position dicts with:
            - ticker: Stock symbol
            - shares: Number of shares
            - cost_basis: Original purchase price per share
        reinvest: Auto-reinvest dividends
        growth_rate: Expected dividend growth rate
        horizon_years: Forecast horizon
    
    Returns:
        Dict with income_metrics, forecast, calendar, cut_risk
    """
    try:
        holdings_data = []
        annual_income = 0
        total_value = 0
        total_cost = 0
        
        for position in positions:
            ticker = position.get("ticker")
            shares = position.get("shares", 0)
            cost_basis = position.get("cost_basis", 0)
            
            try:
                stock = yf.Ticker(ticker)
                info = stock.info
                
                # Current price
                current_price = info.get("currentPrice") or info.get("regularMarketPrice") or 0
                
                # Dividend info
                dividend_rate = info.get("dividendRate", 0) or 0  # Annual dividend per share
                dividend_yield = info.get("dividendYield", 0) or 0
                ex_dividend_date = info.get("exDividendDate")
                payout_ratio = info.get("payoutRatio", 0) or 0
                
                # Dividend history
                dividends = stock.dividends
                if len(dividends) > 0:
                    recent_dividends = dividends.tail(12)
                    dividend_trend = "stable"
                    if len(recent_dividends) > 1:
                        first = recent_dividends.iloc[0]
                        last = recent_dividends.iloc[-1]
                        if last > first * 1.05:
                            dividend_trend = "growing"
                        elif last < first * 0.95:
                            dividend_trend = "declining"
                else:
                    dividend_trend = "unknown"
                
                # Position value
                position_value = shares * current_price
                position_cost = shares * cost_basis
                position_income = shares * dividend_rate
                
                # Cut risk scoring
                cut_risk = "low"
                if payout_ratio > 0.8:
                    cut_risk = "high"
                elif payout_ratio > 0.6:
                    cut_risk = "medium"
                elif dividend_trend == "declining":
                    cut_risk = "medium"
                
                holdings_data.append({
                    "ticker": ticker,
                    "shares": shares,
                    "current_price": float(current_price),
                    "dividend_rate": float(dividend_rate),
                    "dividend_yield": float(dividend_yield),
                    "annual_income": float(position_income),
                    "payout_ratio": float(payout_ratio),
                    "dividend_trend": dividend_trend,
                    "cut_risk": cut_risk,
                    "ex_dividend_date": str(ex_dividend_date) if ex_dividend_date else None
                })
                
                annual_income += position_income
                total_value += position_value
                total_cost += position_cost
                
            except Exception as e:
                logger.warning(f"Error fetching dividend data for {ticker}: {e}")
                holdings_data.append({
                    "ticker": ticker,
                    "shares": shares,
                    "error": str(e)
                })
        
        # Current yield metrics
        current_yield = annual_income / total_value if total_value > 0 else 0
        yield_on_cost = annual_income / total_cost if total_cost > 0 else 0
        monthly_income = annual_income / 12
        
        # Income forecast
        forecast = []
        cumulative_income = 0
        current_income = annual_income
        
        for year in range(1, horizon_years + 1):
            if reinvest:
                # Compound with reinvested dividends
                current_income *= (1 + growth_rate)
                cumulative_income += current_income
            else:
                current_income *= (1 + growth_rate)
                cumulative_income += current_income
            
            forecast.append({
                "year": year,
                "annual_income": float(current_income),
                "cumulative_income": float(cumulative_income)
            })
        
        # Monthly calendar (simplified)
        calendar = []
        for month in range(1, 13):
            month_income = annual_income / 12  # Simplified even distribution
            calendar.append({
                "month": month,
                "expected_income": float(month_income)
            })
        
        # Income at risk
        high_risk_holdings = [h for h in holdings_data if h.get("cut_risk") == "high"]
        income_at_risk = sum(h.get("annual_income", 0) for h in high_risk_holdings)
        income_at_risk_pct = income_at_risk / annual_income * 100 if annual_income > 0 else 0
        
        # Sustainability score (0-100)
        avg_payout = np.mean([h.get("payout_ratio", 0.5) for h in holdings_data if "payout_ratio" in h])
        sustainability_score = max(0, min(100, 100 - avg_payout * 100))
        
        return {
            "income_metrics": {
                "annual_income": float(annual_income),
                "monthly_income": float(monthly_income),
                "current_yield": float(current_yield),
                "yield_on_cost": float(yield_on_cost),
                "total_value": float(total_value),
                "total_cost": float(total_cost)
            },
            "forecast": forecast,
            "calendar": calendar,
            "holdings": holdings_data,
            "income_at_risk": {
                "amount": float(income_at_risk),
                "percentage": float(income_at_risk_pct),
                "high_risk_count": len(high_risk_holdings)
            },
            "sustainability_score": float(sustainability_score),
            "reinvest_mode": reinvest,
            "growth_rate": growth_rate
        }
        
    except Exception as e:
        logger.error(f"Dividend tracker error: {e}")
        return {"error": str(e)}


# =============================================================================
# FEATURE 43: TAX LOT OPTIMIZER
# =============================================================================

def optimize_tax_lots(
    tax_lots: List[Dict],
    sell_quantity: float,
    current_price: float,
    short_term_rate: float = 0.35,
    long_term_rate: float = 0.15,
    preference: str = "minimize_tax"
) -> Dict[str, Any]:
    """
    Tax-aware execution assistant for selling positions.
    
    Args:
        tax_lots: List of lot dicts with:
            - purchase_date: Date of purchase (YYYY-MM-DD)
            - quantity: Number of shares
            - cost_basis: Purchase price per share
        sell_quantity: Number of shares to sell
        current_price: Current market price
        short_term_rate: Short-term capital gains tax rate
        long_term_rate: Long-term capital gains tax rate
        preference: 'minimize_tax', 'harvest_losses', 'fifo', 'lifo', 'hifo'
    
    Returns:
        Dict with recommended_lots, tax_impact, comparison
    """
    try:
        today = datetime.now()
        one_year_ago = today - timedelta(days=365)
        
        # Classify lots
        enriched_lots = []
        for i, lot in enumerate(tax_lots):
            purchase_date = datetime.strptime(lot.get("purchase_date", "2020-01-01"), "%Y-%m-%d")
            quantity = lot.get("quantity", 0)
            cost_basis = lot.get("cost_basis", 0)
            
            # Long-term vs short-term
            is_long_term = purchase_date < one_year_ago
            
            # Gain/loss per share
            gain_per_share = current_price - cost_basis
            total_gain = gain_per_share * quantity
            
            # Tax rate
            tax_rate = long_term_rate if is_long_term else short_term_rate
            
            enriched_lots.append({
                "lot_id": i,
                "purchase_date": lot.get("purchase_date"),
                "quantity": quantity,
                "cost_basis": cost_basis,
                "current_price": current_price,
                "gain_per_share": float(gain_per_share),
                "total_gain": float(total_gain),
                "is_long_term": is_long_term,
                "holding_period": "long-term" if is_long_term else "short-term",
                "tax_rate": tax_rate,
                "tax_impact": float(max(0, total_gain) * tax_rate)
            })
        
        # Sort lots based on strategy
        def sort_key(lot):
            if preference == "fifo":
                return datetime.strptime(lot["purchase_date"], "%Y-%m-%d")
            elif preference == "lifo":
                return -datetime.strptime(lot["purchase_date"], "%Y-%m-%d").timestamp()
            elif preference == "hifo":
                return -lot["cost_basis"]  # Highest cost first
            elif preference == "harvest_losses":
                return lot["gain_per_share"]  # Losses first (most negative)
            else:  # minimize_tax
                # Prefer: losses > long-term gains > short-term gains
                if lot["total_gain"] < 0:
                    return (0, lot["total_gain"])  # Losses first
                elif lot["is_long_term"]:
                    return (1, lot["tax_impact"])  # Then long-term (lower tax)
                else:
                    return (2, lot["tax_impact"])  # Then short-term
        
        sorted_lots = sorted(enriched_lots, key=sort_key)
        
        # Select lots to sell
        remaining_quantity = sell_quantity
        selected_lots = []
        total_proceeds = 0
        total_gain = 0
        total_tax = 0
        
        for lot in sorted_lots:
            if remaining_quantity <= 0:
                break
            
            sell_from_lot = min(remaining_quantity, lot["quantity"])
            fraction = sell_from_lot / lot["quantity"]
            
            lot_proceeds = sell_from_lot * current_price
            lot_gain = sell_from_lot * lot["gain_per_share"]
            lot_tax = max(0, lot_gain) * lot["tax_rate"]
            
            selected_lots.append({
                **lot,
                "sell_quantity": sell_from_lot,
                "lot_proceeds": float(lot_proceeds),
                "lot_gain": float(lot_gain),
                "lot_tax": float(lot_tax)
            })
            
            total_proceeds += lot_proceeds
            total_gain += lot_gain
            total_tax += lot_tax
            remaining_quantity -= sell_from_lot
        
        # Compare all strategies
        comparison = {}
        for strategy in ["fifo", "lifo", "hifo", "minimize_tax"]:
            if strategy == preference:
                comparison[strategy] = {
                    "total_gain": float(total_gain),
                    "total_tax": float(total_tax),
                    "after_tax_proceeds": float(total_proceeds - total_tax),
                    "selected": True
                }
            else:
                # Quick calculation for comparison
                temp_lots = sorted(enriched_lots, key=lambda l: sort_key(l) if preference != strategy else sort_key(l))
                temp_remaining = sell_quantity
                temp_gain = 0
                temp_tax = 0
                
                for lot in temp_lots:
                    if temp_remaining <= 0:
                        break
                    sell_qty = min(temp_remaining, lot["quantity"])
                    temp_gain += sell_qty * lot["gain_per_share"]
                    temp_tax += max(0, sell_qty * lot["gain_per_share"]) * lot["tax_rate"]
                    temp_remaining -= sell_qty
                
                comparison[strategy] = {
                    "total_gain": float(temp_gain),
                    "total_tax": float(temp_tax),
                    "after_tax_proceeds": float(sell_quantity * current_price - temp_tax),
                    "selected": False
                }
        
        # Loss harvesting opportunities
        harvestable_losses = []
        for lot in enriched_lots:
            if lot["total_gain"] < 0:
                harvestable_losses.append({
                    "lot_id": lot["lot_id"],
                    "loss_amount": float(abs(lot["total_gain"])),
                    "tax_savings": float(abs(lot["total_gain"]) * lot["tax_rate"]),
                    "holding_period": lot["holding_period"]
                })
        
        # Wash sale warning
        wash_sale_warning = None
        recent_sales = [l for l in selected_lots if l["lot_gain"] < 0]
        if recent_sales:
            wash_sale_warning = {
                "warning": "Wash sale rule applies if you repurchase within 30 days",
                "days_until_clear": 30
            }
        
        return {
            "recommended_lots": selected_lots,
            "tax_impact": {
                "total_proceeds": float(total_proceeds),
                "total_gain": float(total_gain),
                "total_tax": float(total_tax),
                "after_tax_proceeds": float(total_proceeds - total_tax)
            },
            "comparison": comparison,
            "harvestable_losses": harvestable_losses,
            "wash_sale_warning": wash_sale_warning,
            "preference": preference,
            "sell_quantity": sell_quantity,
            "current_price": current_price
        }
        
    except Exception as e:
        logger.error(f"Tax lot optimization error: {e}")
        return {"error": str(e)}
