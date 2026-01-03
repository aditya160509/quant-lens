from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import List, Optional
from app.services import options
from app.services.options_calculator import calculate_payoff, calculate_probability_of_profit

router = APIRouter()


class OptionLeg(BaseModel):
    type: str  # 'call' or 'put'
    strike: float
    expiry_days: int = 30
    iv: float = 0.25
    quantity: int = 1  # Positive = long, negative = short
    premium: Optional[float] = None


class CalculatorRequest(BaseModel):
    legs: List[OptionLeg]
    spot: float
    rate: float = 0.05


@router.get("/{ticker}")
def get_options(ticker: str):
    """
    Get options chain and Greeks for a ticker.
    """
    res = options.get_option_chain(ticker)
    if "error" in res:
        if "No data" in res["error"]:
            raise HTTPException(status_code=404, detail=res["error"])
        raise HTTPException(status_code=500, detail=res["error"])
    return res


@router.post("/calculator")
def calculate_options_payoff(request: CalculatorRequest):
    """
    Calculate multi-leg options strategy payoff
    
    Returns payoff curve, break-evens, max profit/loss, and aggregated Greeks.
    
    Example request:
    {
        "legs": [
            {"type": "call", "strike": 100, "quantity": 1, "iv": 0.25, "expiry_days": 30},
            {"type": "put", "strike": 100, "quantity": -1, "iv": 0.25, "expiry_days": 30}
        ],
        "spot": 100,
        "rate": 0.05
    }
    """
    legs = [leg.model_dump() for leg in request.legs]
    
    result = calculate_payoff(legs, request.spot, request.rate)
    
    if "error" in result:
        raise HTTPException(status_code=400, detail=result["error"])
    
    # Add probability of profit
    if result.get("break_evens"):
        avg_iv = sum(leg["iv"] for leg in legs) / len(legs)
        avg_expiry = sum(leg["expiry_days"] for leg in legs) / len(legs)
        result["probability_of_profit"] = calculate_probability_of_profit(
            request.spot, 
            result["break_evens"], 
            avg_iv, 
            avg_expiry
        )
    
    return result

