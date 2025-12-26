import yfinance as yf
import numpy as np

def calculate_liquidity_score(avg_volume, market_cap):
    # Simple heuristic for liquidity score
    # Volume > 1M and Cap > 10B -> High
    # Volume > 100k and Cap > 1B -> Medium
    # Else -> Low
    
    score = 0
    if avg_volume > 1_000_000:
        score += 2
    elif avg_volume > 100_000:
        score += 1
        
    if market_cap > 10_000_000_000:
        score += 2
    elif market_cap > 1_000_000_000:
        score += 1
        
    if score >= 3:
        return "HIGH", "bg-terminal-green text-black"
    elif score >= 2:
        return "MEDIUM", "bg-terminal-yellow text-black"
    else:
        return "LOW", "bg-terminal-red text-black"

def get_liquidity_metrics(ticker):
    try:
        stock = yf.Ticker(ticker)
        info = stock.info
        
        # Get recent data for volume analysis
        hist = stock.history(period="1mo")
        
        if hist.empty:
             return None

        avg_volume = hist['Volume'].mean()
        current_volume = hist['Volume'].iloc[-1] if not hist.empty else 0
        market_cap = info.get('marketCap', 0)
        
        label, color_class = calculate_liquidity_score(avg_volume, market_cap)
        
        spread_bps = 0
        if label == "HIGH":
            spread_bps = np.random.uniform(1, 5) # 1-5 bps
        elif label == "MEDIUM":
            spread_bps = np.random.uniform(5, 20) # 5-20 bps
        else:
            spread_bps = np.random.uniform(20, 100) # 20-100 bps

        return {
            "ticker": ticker,
            "avg_daily_volume": float(avg_volume),
            "current_volume": int(current_volume),
            "market_cap": int(market_cap),
            "liquidity_label": label,
            "liquidity_color": color_class,
            "estimated_spread_bps": float(spread_bps),
            "turnover_ratio": float((avg_volume * hist['Close'].mean()) / market_cap) if market_cap > 0 else 0.0
        }
    except Exception as e:
        print(f"Error calculating liquidity for {ticker}: {e}")
        return None
