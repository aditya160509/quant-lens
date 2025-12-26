import pandas as pd
import os
from pathlib import Path
import logging

logger = logging.getLogger(__name__)

# Define paths relative to this file
# backend/app/factor_data.py -> ../data/factors_us
BASE_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = BASE_DIR / "data" / "factors_us"

FILES = {
    "ff3": "ff3_daily.csv",
    "ff5": "ff5_daily.csv",
    "momentum": "momentum_daily.csv"
}

def load_factors(model: str = "ff3") -> pd.DataFrame:
    """
    Loads factor data for a given model.
    
    Args:
        model (str): "ff3", "ff5", or "momentum".
        
    Returns:
        pd.DataFrame: DataFrame with DatetimeIndex and factor returns (as decimals).
    """
    if model not in FILES:
        logger.error(f"Unknown factor model: {model}")
        return pd.DataFrame()
        
    file_path = DATA_DIR / FILES[model]
    if not file_path.exists():
        logger.error(f"Factor file not found: {file_path}")
        return pd.DataFrame()
        
    try:
        # Fama French files usually have 4 lines of metadata
        # We'll try to detect the header line or just skip 4
        # The date column is the first one
        
        # Read first few lines to check
        with open(file_path, 'r') as f:
            lines = [next(f) for _ in range(10)]
            
        skip_rows = 0
        for i, line in enumerate(lines):
            if line.strip().startswith(",Mkt-RF") or line.strip().startswith("Date") or line.strip().startswith(","):
                # Found header candidate
                # FF files often start with empty string for date column name in header
                if "Mkt-RF" in line or "Mom" in line:
                    skip_rows = i
                    break
        
        df = pd.read_csv(file_path, skiprows=skip_rows, index_col=0)
        
        # Parse index to datetime - try multiple formats
        # Format could be YYYYMMDD or ISO datetime
        try:
            df.index = pd.to_datetime(df.index, format="%Y%m%d", errors='raise')
        except (ValueError, TypeError):
            # Try ISO format or infer
            df.index = pd.to_datetime(df.index, errors='coerce')
        
        df.dropna(how='all', inplace=True)
        
        # Rename index to Date
        df.index.name = "Date"
        
        # Note: Data is already in decimal form (0.01 = 1%)
        # No conversion needed
        
        return df
        
    except Exception as e:
        logger.error(f"Error loading factors from {file_path}: {e}")
        return pd.DataFrame()

def get_combined_factors() -> pd.DataFrame:
    """
    Loads and combines FF5 and Momentum factors.
    """
    ff5 = load_factors("ff5")
    mom = load_factors("momentum")
    
    if ff5.empty:
        return pd.DataFrame()
        
    if mom.empty:
        return ff5
        
    # Join momentum
    # Momentum file might have 'Mom' column
    # Check column names
    # Usually Mom file has just 'Mom' or similar
    
    # Clean column names
    mom.columns = [c.strip() for c in mom.columns]
    
    # If Mom has 'Mom' column, use it
    # Sometimes it has 'Mom   '
    
    combined = ff5.join(mom, how='inner', rsuffix='_mom')
    
    # Handle duplicate RF if present (usually FF5 has RF, Mom might not or might)
    # If Mom has RF, drop it
    if 'RF_mom' in combined.columns:
        combined.drop(columns=['RF_mom'], inplace=True)
        
    return combined

def sync_factors():
    """
    Downloads latest factor data from Ken French website if files are missing or old.
    """
    import requests
    import zipfile
    import io
    from datetime import datetime
    
    BASE_URL = "https://mba.tuck.dartmouth.edu/pages/faculty/ken.french/ftp"
    SOURCES = {
        "ff3": "F-F_Research_Data_Factors_daily_CSV.zip",
        "ff5": "F-F_Research_Data_5_Factors_2x3_daily_CSV.zip",
        "momentum": "F-F_Momentum_Factor_daily_CSV.zip"
    }
    
    os.makedirs(DATA_DIR, exist_ok=True)
    
    for model, filename in SOURCES.items():
        target_path = DATA_DIR / FILES[model]
        
        # Check if needs update (older than 7 days)
        needs_update = True
        if target_path.exists():
            mtime = os.path.getmtime(target_path)
            age_days = (datetime.now().timestamp() - mtime) / 86400
            if age_days < 7:
                needs_update = False
                
        if not needs_update:
            continue
            
        logger.info(f"Syncing factor data for {model}...")
        try:
            r = requests.get(f"{BASE_URL}/{filename}")
            r.raise_for_status()
            
            with zipfile.ZipFile(io.BytesIO(r.content)) as z:
                # Find the CSV inside the zip
                csv_files = [f for f in z.namelist() if f.lower().endswith('.csv')]
                if csv_files:
                    csv_name = csv_files[0]
                    with z.open(csv_name) as f:
                        content = f.read().decode('latin-1')
                        with open(target_path, 'w') as out:
                            out.write(content)
                    logger.info(f"Successfully updated {target_path}")
        except Exception as e:
            logger.error(f"Failed to sync {model}: {e}")

# Try sync on module load
try:
    sync_factors()
except Exception:
    pass
