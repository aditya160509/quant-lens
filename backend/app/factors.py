import pandas as pd
import os
import logging

logger = logging.getLogger(__name__)

# Cache for loaded dataframes
_factors_cache = {}

DATA_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "data", "factors_us")

def _load_csv(filename):
    """
    Helper to load Fama-French CSVs.
    - Robustly finds the header row.
    - Parses dates.
    - Converts percentages to decimals.
    """
    path = os.path.join(DATA_DIR, filename)
    if not os.path.exists(path):
        logger.error(f"Factor file not found: {path}")
        return pd.DataFrame()
        
    try:
        # Read file lines to find header
        with open(path, 'r') as f:
            lines = f.readlines()
            
        header_row = 0
        for i, line in enumerate(lines):
            if "Date" in line or "date" in line or "Mkt-RF" in line:
                header_row = i
                break
                
        # Read CSV skipping rows before header
        df = pd.read_csv(path, skiprows=header_row)
        
        # Rename first column to Date if it's unnamed or something else
        # Sometimes the first column is unnamed if it's the index in the CSV
        if "Date" not in df.columns and "date" not in df.columns:
             # Check if the first column looks like a date (YYYYMMDD)
             df.rename(columns={df.columns[0]: "Date"}, inplace=True)
        elif "date" in df.columns:
            df.rename(columns={"date": "Date"}, inplace=True)
            
        # Parse dates. FF dates are often YYYYMMDD or YYYYMM. Daily is YYYYMMDD.
        df["Date"] = pd.to_datetime(df["Date"], format="%Y%m%d", errors="coerce")
        df = df.dropna(subset=["Date"])
        df = df.set_index("Date").sort_index()
        
        # Convert percent to decimal
        # FF data is usually in percent (e.g., 0.5 for 0.5%)
        df = df / 100.0
        
        return df
    except Exception as e:
        logger.error(f"Error loading {filename}: {e}")
        return pd.DataFrame()

def load_ff3_daily():
    if "ff3" in _factors_cache:
        return _factors_cache["ff3"]
    
    df = _load_csv("ff3_daily.csv")
    # Expected columns: Mkt-RF, SMB, HML, RF
    # Rename if necessary to match standard names
    # usually they are 'Mkt-RF', 'SMB', 'HML', 'RF'
    
    _factors_cache["ff3"] = df
    return df

def load_ff5_daily():
    if "ff5" in _factors_cache:
        return _factors_cache["ff5"]
        
    df = _load_csv("ff5_daily.csv")
    _factors_cache["ff5"] = df
    return df

def load_mom_daily():
    if "mom" in _factors_cache:
        return _factors_cache["mom"]
        
    df = _load_csv("momentum_daily.csv")
    # Usually column is 'Mom' or 'MOM'
    _factors_cache["mom"] = df
    return df
