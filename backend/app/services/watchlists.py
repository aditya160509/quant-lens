import uuid

# In-memory store for watchlists
# {user_id: {watchlist_id: {id, name, tickers}}}
_watchlists = {
    "default": {
        "wl_default": {
            "id": "wl_default",
            "name": "My Watchlist",
            "tickers": ["AAPL", "MSFT", "GOOGL", "AMZN", "TSLA"]
        }
    }
}

def get_watchlists(user_id="default"):
    return list(_watchlists.get(user_id, {}).values())

def create_watchlist(name, tickers, user_id="default"):
    if user_id not in _watchlists:
        _watchlists[user_id] = {}
        
    wl_id = f"wl_{uuid.uuid4().hex[:8]}"
    wl = {
        "id": wl_id,
        "name": name,
        "tickers": tickers
    }
    _watchlists[user_id][wl_id] = wl
    return wl

def update_watchlist(wl_id, name=None, tickers=None, user_id="default"):
    user_wls = _watchlists.get(user_id)
    if not user_wls or wl_id not in user_wls:
        return None
        
    wl = user_wls[wl_id]
    if name:
        wl["name"] = name
    if tickers is not None:
        wl["tickers"] = tickers
        
    return wl

def delete_watchlist(wl_id, user_id="default"):
    user_wls = _watchlists.get(user_id)
    if not user_wls or wl_id not in user_wls:
        return False
        
    del user_wls[wl_id]
    return True
