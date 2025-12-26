import yfinance as yf
import time

print("Testing yfinance...")
start = time.time()
try:
    df = yf.download("SPY", period="1d")
    print(f"Download took {time.time() - start:.2f}s")
    print(df.head())
except Exception as e:
    print(f"Error: {e}")
