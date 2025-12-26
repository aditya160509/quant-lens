import pandas as pd
import numpy as np
import os
from datetime import datetime, timedelta

# Setup directories
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(BASE_DIR, "data")
PRICES_DIR = os.path.join(DATA_DIR, "prices")
FACTORS_DIR = os.path.join(DATA_DIR, "factors_us")

os.makedirs(PRICES_DIR, exist_ok=True)
os.makedirs(FACTORS_DIR, exist_ok=True)

# Date range
end_date = datetime.now()
start_date = end_date - timedelta(days=365*5)
dates = pd.date_range(start=start_date, end=end_date, freq='B')

# Generate Factors
print("Generating Factors...")
np.random.seed(42)
n = len(dates)

# FF3
mkt_rf = np.random.normal(0.0005, 0.01, n)
smb = np.random.normal(0.0001, 0.005, n)
hml = np.random.normal(0.0001, 0.005, n)
rf = np.full(n, 0.0001)

ff3_df = pd.DataFrame({
    'Mkt-RF': mkt_rf,
    'SMB': smb,
    'HML': hml,
    'RF': rf
}, index=dates)
ff3_df.index.name = 'Date'
ff3_df.to_csv(os.path.join(FACTORS_DIR, "ff3_daily.csv"))

# Momentum
mom = np.random.normal(0.0002, 0.008, n)
mom_df = pd.DataFrame({'Mom': mom}, index=dates)
mom_df.index.name = 'Date'
mom_df.to_csv(os.path.join(FACTORS_DIR, "momentum_daily.csv"))

# Generate Prices
tickers = ["SPY", "QQQ", "DIA", "IWM", "TLT", "GLD", "XLF", "XLK", "NVDA", "AAPL", "MSFT", "TSLA", "GOOGL", "AMZN", "META", "AMD", "XLE", "XLY", "XLP", "XLI", "XLB", "XLU", "XLRE"]

print("Generating Prices...")
for ticker in tickers:
    # Generate random returns with some correlation to market
    # Beta varies by ticker
    beta = 1.0
    if ticker in ["QQQ", "XLK", "NVDA", "AAPL", "MSFT", "TSLA", "AMD"]: beta = 1.2
    if ticker in ["TLT", "XLU", "XLP"]: beta = 0.5
    if ticker in ["GLD"]: beta = 0.1
    
    idiosyncratic = np.random.normal(0, 0.01, n)
    ret = beta * mkt_rf + idiosyncratic
    
    # Price path
    price = 100 * (1 + ret).cumprod()
    
    df = pd.DataFrame({'Close': price}, index=dates)
    df.index.name = 'Date'
    df.to_csv(os.path.join(PRICES_DIR, f"{ticker}.csv"))

print("Data generation complete.")
