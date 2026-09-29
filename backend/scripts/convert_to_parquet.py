import pandas as pd
import polars as pl
import os
from pathlib import Path
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def convert_csv_to_parquet(directory: Path):
    if not directory.exists():
        logger.warning(f"Directory {directory} does not exist. Skipping.")
        return

    for file in directory.glob("*.csv"):
        parquet_file = file.with_suffix(".parquet")
        logger.info(f"Converting {file} to {parquet_file}...")
        try:
            # First try reading with pandas to handle messy CSVs (like Ken French headers)
            # Fama-French files often have headers that need skipping
            try:
                df = pd.read_csv(file, skiprows=0)
                # Check if it's a FF file with " This file was created using the " header
                if df.columns[0].startswith(" This file"):
                    df = pd.read_csv(file, skiprows=3)
            except Exception as e:
                logger.error(f"Pandas failed for {file}: {e}")
                continue

            # Convert to Polars and save as Parquet
            df_pl = pl.from_pandas(df)
            df_pl.write_parquet(parquet_file)
            logger.info(f"Successfully converted {file}")
        except Exception as e:
            logger.error(f"Failed to convert {file}: {e}")

if __name__ == "__main__":
    base_dir = Path("/Users/adityabalaji/Downloads/quant  2/backend/data")
    
    # 1. Factors
    convert_csv_to_parquet(base_dir / "factors_us")
    convert_csv_to_parquet(base_dir / "factors_india")
    
    # 2. Fundamentals (if any)
    convert_csv_to_parquet(base_dir / "fundamentals")
    
    # 3. Prices (individual CSVs if they exist)
    convert_csv_to_parquet(base_dir / "prices")
    
    logger.info("Batch conversion complete.")
