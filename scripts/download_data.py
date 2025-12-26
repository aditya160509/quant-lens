import yfinance as yf
import pandas as pd
import os
import logging

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Define the universe of tickers
TICKERS = [
    # Indices / ETFs
    "SPY", "QQQ", "DIA", "IWM", "GLD", "TLT", "AGG", "VXX",
    # Sectors
    "XLK", "XLF", "XLY", "XLP", "XLE", "XLV", "XLRE", "XLU", "XLI", "XLB", "XLC",
    # Tech / Mega Cap
    "AAPL", "MSFT", "AMZN", "GOOGL", "META", "TSLA", "NVDA", "AMD", "INTC", "IBM",
    # Finance
    "JPM", "BAC", "WFC", "C", "GS", "MS",
    # Consumer
    "WMT", "TGT", "COST", "HD", "MCD", "SBUX", "KO", "PEP",
    # Healthcare
    "JNJ", "PFE", "UNH", "ABBV", "LLY",
    # Energy / Industrial
    "XOM", "CVX", "BA", "CAT", "GE",
    # International (optional, for variety)
    "EFA", "EEM"
]

DATA_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data", "prices")

def download_data():
    if not os.path.exists(DATA_DIR):
        os.makedirs(DATA_DIR)
        logger.info(f"Created directory: {DATA_DIR}")

    logger.info(f"Downloading data for {len(TICKERS)} tickers...")
    
    for ticker in TICKERS:
        try:
            logger.info(f"Fetching {ticker}...")
            # Download 5 years of data to be safe
            df = yf.download(ticker, period="5y", progress=False, auto_adjust=False)
            
            if df.empty:
                logger.warning(f"No data found for {ticker}")
                continue
            
            # Flatten columns if MultiIndex (yfinance sometimes does this)
            if isinstance(df.columns, pd.MultiIndex):
                df.columns = df.columns.get_level_values(0)
            
            # Ensure index is datetime
            df.index = pd.to_datetime(df.index)
            
            # Save to CSV
            file_path = os.path.join(DATA_DIR, f"{ticker}.csv")
            df.to_csv(file_path)
            logger.info(f"Saved {ticker} to {file_path}")
            
        except Exception as e:
            logger.error(f"Failed to download {ticker}: {e}")

    logger.info("Data download complete.")

if __name__ == "__main__":
    download_data()
