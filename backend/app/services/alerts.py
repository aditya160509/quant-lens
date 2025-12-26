import uuid
from app.services.portfolio import get_last_price

# In-memory store
_alerts = {
    "default": []
}

def get_alerts(user_id="default"):
    return _alerts.get(user_id, [])

def create_alert(ticker, condition, threshold, user_id="default"):
    # condition: "above", "below"
    if user_id not in _alerts:
        _alerts[user_id] = []
        
    alert = {
        "id": str(uuid.uuid4()),
        "ticker": ticker,
        "condition": condition,
        "threshold": float(threshold),
        "active": True,
        "triggered": False
    }
    _alerts[user_id].append(alert)
    return alert

def check_alerts(user_id="default"):
    # This would typically run in a background job
    # For now, we check on demand
    alerts = _alerts.get(user_id, [])
    triggered = []
    
    for alert in alerts:
        if not alert["active"]:
            continue
            
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
            alert["last_price"] = price
            triggered.append(alert)
            
    return triggered

def delete_alert(alert_id, user_id="default"):
    alerts = _alerts.get(user_id, [])
    _alerts[user_id] = [a for a in alerts if a["id"] != alert_id]
    return True
