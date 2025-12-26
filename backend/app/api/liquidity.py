from fastapi import APIRouter, HTTPException
from app.services import liquidity

router = APIRouter()

@router.get("/{ticker}")
def get_liquidity_metrics(ticker: str):
    metrics = liquidity.get_liquidity_metrics(ticker)
    if not metrics:
        raise HTTPException(status_code=404, detail="No data found or error calculating liquidity")
    return metrics
