import logging

logger = logging.getLogger(__name__)

# In-memory store
# {user_id: {score, badges: [], counters: {}}}
_game_state = {
    "default": {
        "score": 0,
        "badges": [],
        "counters": {
            "backtests_run": 0,
            "scenarios_run": 0,
            "trades_executed": 0
        }
    }
}

BADGES = {
    "first_trade": {"id": "first_trade", "name": "First Steps", "desc": "Executed your first trade", "xp": 100},
    "first_backtest": {"id": "first_backtest", "name": "Time Traveler", "desc": "Ran a backtest", "xp": 50},
    "sharpe_1": {"id": "sharpe_1", "name": "Sharpe Shooter", "desc": "Achieved Sharpe Ratio > 1.0", "xp": 200},
    "diversified": {"id": "diversified", "name": "Diversified", "desc": "Held positions in 5+ sectors", "xp": 150},
    "risk_manager": {"id": "risk_manager", "name": "Risk Manager", "desc": "Checked portfolio risk", "xp": 50}
}

def get_status(user_id="default"):
    if user_id not in _game_state:
        _game_state[user_id] = {"score": 0, "badges": [], "counters": {}}
    return _game_state[user_id]

def record_event(event_type, data=None, user_id="default"):
    state = get_status(user_id)
    new_badges = []
    
    if event_type == "trade":
        state["counters"]["trades_executed"] = state["counters"].get("trades_executed", 0) + 1
        if state["counters"]["trades_executed"] == 1:
            _award_badge(state, "first_trade", new_badges)
            
    elif event_type == "backtest":
        state["counters"]["backtests_run"] = state["counters"].get("backtests_run", 0) + 1
        if state["counters"]["backtests_run"] == 1:
            _award_badge(state, "first_backtest", new_badges)
            
        if data and data.get("sharpe", 0) > 1.0:
            _award_badge(state, "sharpe_1", new_badges)
            
    elif event_type == "scenario":
        state["counters"]["scenarios_run"] = state["counters"].get("scenarios_run", 0) + 1
        
    elif event_type == "risk_check":
        _award_badge(state, "risk_manager", new_badges)

    return {
        "score": state["score"],
        "new_badges": new_badges
    }

def _award_badge(state, badge_id, new_badges_list):
    if badge_id not in [b["id"] for b in state["badges"]]:
        badge = BADGES[badge_id]
        state["badges"].append(badge)
        state["score"] += badge["xp"]
        new_badges_list.append(badge)
        logger.info(f"Awarded badge {badge_id} to user")
