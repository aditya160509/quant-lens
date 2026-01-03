"""
Enhanced Alerts Service
Intelligent signal alerts with multiple types, severity levels, and symbol preview

Alert Types:
- earnings_approaching: Earnings within configured days
- vol_expensive: IV percentile above threshold
- momentum_leader: Strong momentum score
- extreme_stretch: Mean reversion opportunity
- dangerous_reversion: High-risk reversion signal
- signal_confluence: Multiple signals agree
"""

import uuid
from datetime import datetime, timedelta
from typing import Optional, List, Dict, Any
import logging

from app.services.portfolio import get_last_price

logger = logging.getLogger(__name__)

# Alert type definitions
ALERT_TYPES = {
    "price": {"name": "Price Alert", "severity": "medium"},
    "earnings_approaching": {"name": "Earnings Approaching", "severity": "high"},
    "vol_expensive": {"name": "Volatility Expensive", "severity": "medium"},
    "vol_cheap": {"name": "Volatility Cheap", "severity": "low"},
    "momentum_leader": {"name": "Momentum Leader", "severity": "medium"},
    "momentum_laggard": {"name": "Momentum Laggard", "severity": "low"},
    "extreme_stretch": {"name": "Extreme Stretch", "severity": "medium"},
    "dangerous_reversion": {"name": "Dangerous Reversion", "severity": "high"},
    "signal_confluence": {"name": "Signal Confluence", "severity": "high"},
}

SEVERITY_PRIORITY = {"high": 3, "medium": 2, "low": 1}

# In-memory store
_alerts: Dict[str, List[dict]] = {"default": []}
_cooldowns: Dict[str, datetime] = {}  # Prevent alert spam


def get_alerts(user_id: str = "default") -> List[dict]:
    """Get all alerts for a user"""
    return _alerts.get(user_id, [])


def create_alert(
    ticker: str,
    condition: str,
    threshold: float,
    user_id: str = "default",
    alert_type: str = "price",
    expiry_hours: Optional[int] = None
) -> dict:
    """
    Create a new alert
    
    Args:
        ticker: Symbol to monitor
        condition: 'above', 'below', or custom for signal alerts
        threshold: Target value
        user_id: User identifier
        alert_type: Type from ALERT_TYPES
        expiry_hours: Optional auto-expire after hours
    """
    if user_id not in _alerts:
        _alerts[user_id] = []
    
    alert_meta = ALERT_TYPES.get(alert_type, ALERT_TYPES["price"])
    
    alert = {
        "id": str(uuid.uuid4()),
        "ticker": ticker.upper(),
        "condition": condition,
        "threshold": float(threshold),
        "alert_type": alert_type,
        "severity": alert_meta["severity"],
        "name": alert_meta["name"],
        "active": True,
        "triggered": False,
        "created_at": datetime.now().isoformat(),
        "expires_at": (datetime.now() + timedelta(hours=expiry_hours)).isoformat() if expiry_hours else None,
        "triggered_at": None,
        "last_price": None
    }
    
    _alerts[user_id].append(alert)
    logger.info(f"Created {alert_type} alert for {ticker}: {condition} {threshold}")
    return alert


def check_alerts(user_id: str = "default") -> List[dict]:
    """Check all alerts and return newly triggered ones"""
    alerts = _alerts.get(user_id, [])
    triggered = []
    now = datetime.now()
    
    for alert in alerts:
        if not alert["active"]:
            continue
        
        # Check expiry
        if alert.get("expires_at"):
            if datetime.fromisoformat(alert["expires_at"]) < now:
                alert["active"] = False
                continue
        
        # Check cooldown (prevent spam)
        cooldown_key = f"{user_id}:{alert['ticker']}:{alert['alert_type']}"
        if cooldown_key in _cooldowns:
            if _cooldowns[cooldown_key] > now:
                continue
        
        # Price-based alerts
        if alert["alert_type"] == "price":
            price = get_last_price(alert["ticker"])
            if price is None:
                continue
            
            is_triggered = False
            if alert["condition"] == "above" and price > alert["threshold"]:
                is_triggered = True
            elif alert["condition"] == "below" and price < alert["threshold"]:
                is_triggered = True
            
            if is_triggered:
                alert["triggered"] = True
                alert["triggered_at"] = now.isoformat()
                alert["last_price"] = price
                triggered.append(alert)
                
                # Set cooldown (1 hour for price alerts)
                _cooldowns[cooldown_key] = now + timedelta(hours=1)
    
    return triggered


def delete_alert(alert_id: str, user_id: str = "default") -> bool:
    """Delete an alert by ID"""
    alerts = _alerts.get(user_id, [])
    original_count = len(alerts)
    _alerts[user_id] = [a for a in alerts if a["id"] != alert_id]
    return len(_alerts[user_id]) < original_count


def preview_alerts_for_symbol(symbol: str) -> Dict[str, Any]:
    """
    Generate intelligent alert suggestions for a symbol
    
    This is a preview of what alerts would fire based on current market conditions.
    Uses alpha models and volatility data if available.
    """
    symbol = symbol.upper()
    preview_alerts = []
    
    try:
        # Get current price
        price = get_last_price(symbol)
        if price:
            # Suggest price alerts at round numbers
            nearest_5 = round(price / 5) * 5
            preview_alerts.append({
                "type": "price",
                "severity": "low",
                "title": f"Price Alert: ${nearest_5}",
                "description": f"Notify when {symbol} reaches ${nearest_5}",
                "actionable": True
            })
        
        # Try to get momentum data
        try:
            from app.services.alpha_momentum import compute_momentum_score
            momentum_result = compute_momentum_score([symbol], "SPY")
            if momentum_result.get("status") == "success" and momentum_result.get("data"):
                data = momentum_result["data"][0]
                score = data.get("scores", {}).get("score_0_100", 50)
                phase = data.get("classification", {}).get("trend_phase", "Neutral")
                
                if score >= 70:
                    preview_alerts.append({
                        "type": "momentum_leader",
                        "severity": "medium",
                        "title": "Strong Momentum",
                        "description": f"{symbol} has momentum score of {score:.0f} ({phase})",
                        "actionable": False
                    })
                elif score <= 30:
                    preview_alerts.append({
                        "type": "momentum_laggard",
                        "severity": "low",
                        "title": "Weak Momentum",
                        "description": f"{symbol} has momentum score of {score:.0f} ({phase})",
                        "actionable": False
                    })
        except Exception as e:
            logger.debug(f"Could not get momentum for {symbol}: {e}")
        
        # Try to get mean reversion data
        try:
            from app.services.alpha_mean_reversion import compute_mean_reversion
            reversion_result = compute_mean_reversion([symbol], "conservative")
            if reversion_result.get("status") == "success" and reversion_result.get("data"):
                data = reversion_result["data"][0]
                direction = data.get("scores", {}).get("direction", "neutral")
                quality = data.get("scores", {}).get("quality_label", "Low Odds")
                dangerous = data.get("flags", {}).get("dangerous", False)
                
                if direction in ["oversold", "overbought"]:
                    severity = "high" if dangerous else "medium"
                    preview_alerts.append({
                        "type": "dangerous_reversion" if dangerous else "extreme_stretch",
                        "severity": severity,
                        "title": f"{'⚠ Dangerous ' if dangerous else ''}{direction.title()} Signal",
                        "description": f"{symbol} shows {direction} condition ({quality})",
                        "actionable": True
                    })
        except Exception as e:
            logger.debug(f"Could not get reversion for {symbol}: {e}")
        
        # Try to check earnings proximity
        try:
            from app.services.earnings import get_upcoming_earnings_for_symbol
            earnings = get_upcoming_earnings_for_symbol(symbol, days_ahead=14)
            if earnings:
                days_until = earnings.get("days_until", 0)
                if days_until <= 7:
                    preview_alerts.append({
                        "type": "earnings_approaching",
                        "severity": "high",
                        "title": f"Earnings in {days_until} days",
                        "description": f"{symbol} reports {earnings.get('earnings_date', 'soon')}",
                        "actionable": True
                    })
        except Exception as e:
            logger.debug(f"Could not get earnings for {symbol}: {e}")
        
        # Sort by severity
        preview_alerts.sort(key=lambda x: SEVERITY_PRIORITY.get(x["severity"], 0), reverse=True)
        
        return {
            "symbol": symbol,
            "current_price": price,
            "alerts": preview_alerts,
            "total_alerts": len(preview_alerts),
            "high_severity_count": len([a for a in preview_alerts if a["severity"] == "high"])
        }
        
    except Exception as e:
        logger.error(f"Error generating alert preview for {symbol}: {e}")
        return {
            "symbol": symbol,
            "current_price": None,
            "alerts": [],
            "error": str(e)
        }


def get_active_alert_count(user_id: str = "default") -> int:
    """Get count of active alerts"""
    return len([a for a in _alerts.get(user_id, []) if a["active"]])


def clear_triggered_alerts(user_id: str = "default") -> int:
    """Clear all triggered alerts, return count cleared"""
    alerts = _alerts.get(user_id, [])
    count = 0
    for alert in alerts:
        if alert["triggered"]:
            alert["active"] = False
            count += 1
    return count

