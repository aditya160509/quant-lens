from fastapi import APIRouter, HTTPException
from app.services import options

router = APIRouter()

@router.get("/{ticker}")
def get_options(ticker: str):
    """
    Get options chain and Greeks for a ticker.
    """
    res = options.get_option_chain(ticker)
    if "error" in res:
        # If it's just no data, maybe 404 is better, but 400 is okay for now
        # If it says "No data for ticker", return 404
        if "No data" in res["error"]:
            raise HTTPException(status_code=404, detail=res["error"])
        raise HTTPException(status_code=500, detail=res["error"])
    return res
