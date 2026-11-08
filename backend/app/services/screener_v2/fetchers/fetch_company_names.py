"""Build data/fundamentals/company_names.parquet from the SEC and NSE public symbol lists."""
from __future__ import annotations

import io
from pathlib import Path

import pandas as pd
import requests

BACKEND = Path(__file__).resolve().parents[4]
OUT = BACKEND / "data/fundamentals/company_names.parquet"
HEADERS = {"User-Agent": "Mozilla/5.0 (compatible; QuantLens research tool)"}
SEC = "https://www.sec.gov/files/company_tickers.json"
NSE = "https://nsearchives.nseindia.com/content/equities/EQUITY_L.csv"


def main() -> None:
    frames = []
    sec = requests.get(SEC, headers=HEADERS, timeout=30)
    sec.raise_for_status()
    us = pd.DataFrame(sec.json().values())
    frames.append(pd.DataFrame({"ticker": us.ticker.str.replace(".", "-", regex=False), "company_name": us.title.str.title(), "source": "sec"}))
    nse = requests.get(NSE, headers=HEADERS, timeout=30)
    nse.raise_for_status()
    india = pd.read_csv(io.StringIO(nse.text))
    india.columns = india.columns.str.strip()
    frames.append(pd.DataFrame({"ticker": india.SYMBOL + ".NS", "company_name": india["NAME OF COMPANY"], "source": "nse"}))
    pd.concat(frames).drop_duplicates("ticker").to_parquet(OUT, index=False)


if __name__ == "__main__":
    main()
