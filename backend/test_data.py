import sys
import os
sys.path.append(os.getcwd())
from app import data_loader
import pandas as pd

print("Testing data_loader...")
try:
    df = data_loader.get_price_history(["AAPL"], start="2024-01-01", end="2024-01-10")
    print("AAPL Data:")
    print(df)
    
    if df.empty:
        print("ERROR: AAPL data is empty")
    else:
        print("SUCCESS: AAPL data fetched")
        
except Exception as e:
    print(f"EXCEPTION: {e}")
