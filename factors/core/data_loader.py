from pathlib import Path
import pandas as pd

ROOT = Path(__file__).resolve().parents[2]


def load_universe(path: str = 'backend/data/market_universe.parquet') -> pd.DataFrame:
    return pd.read_parquet(ROOT / path)


def load_fundamentals(path: str = 'backend/data/fundamentals/master_fundamentals.parquet') -> pd.DataFrame:
    return pd.read_parquet(ROOT / path)


def load_prices_dir(path: str = 'backend/data/prices') -> Path:
    p = ROOT / path
    if not p.exists():
        raise FileNotFoundError(p)
    return p


def load_category7(path: str = 'factors/data/processed/category7_macro_regime.parquet') -> pd.DataFrame:
    return pd.read_parquet(ROOT / path)
