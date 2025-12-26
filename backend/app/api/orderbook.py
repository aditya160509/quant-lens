from fastapi import APIRouter, HTTPException
import yfinance as yf
import numpy as np
import random

router = APIRouter()

@router.get("/{ticker}")
def get_orderbook(ticker: str, depth: int = 10):
    try:
        stock = yf.Ticker(ticker)
        # Fast fetch of just price
        hist = stock.history(period="1d")
        if hist.empty:
            raise HTTPException(status_code=404, detail="Ticker not found")
            
        last_price = float(hist['Close'].iloc[-1])
        
        # Simulate spread based on price (approx 0.05% spread)
        spread = last_price * 0.0005
        mid_price = last_price
        
        bids = []
        asks = []
        
        # Generate bids (below mid)
        current_bid = mid_price - (spread / 2)
        for i in range(depth):
            # Randomize step and size
            step = random.uniform(0.01, 0.05) * (last_price / 100) # Scale step by price
            size = int(np.random.exponential(100)) + 10 # Random size
            
            current_bid -= step
            bids.append({"price": current_bid, "size": size, "total": 0}) # Total calc later
            
        # Generate asks (above mid)
        current_ask = mid_price + (spread / 2)
        for i in range(depth):
            step = random.uniform(0.01, 0.05) * (last_price / 100)
            size = int(np.random.exponential(100)) + 10
            
            current_ask += step
            asks.append({"price": current_ask, "size": size, "total": 0})
            
        # Calculate cumulative totals
        cum_size = 0
        for b in bids:
            cum_size += b["size"]
            b["total"] = cum_size
            
        cum_size = 0
        for a in asks:
            cum_size += a["size"]
            a["total"] = cum_size
            
        return {
            "ticker": ticker,
            "last_price": last_price,
            "bids": bids,
            "asks": asks,
            "spread": asks[0]["price"] - bids[0]["price"],
            "spread_pct": (asks[0]["price"] - bids[0]["price"]) / mid_price
        }

    except Exception as e:
        print(f"Error generating orderbook for {ticker}: {e}")
        raise HTTPException(status_code=500, detail=str(e))
