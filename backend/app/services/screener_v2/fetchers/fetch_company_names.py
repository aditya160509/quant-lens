"""Build data/fundamentals/company_names.parquet from the SEC and NSE public symbol lists."""
from __future__ import annotations

import io
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import pandas as pd
import requests
import yfinance as yf

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
    # Earlier Yahoo hits are kept, so a rerun only retries what is still missing.
    if OUT.exists():
        previous = pd.read_parquet(OUT)
        frames.append(previous[previous.source == "yahoo"])
    names = pd.concat(frames).drop_duplicates("ticker")
    from app.services.screener_v2.core.data_loader import available_symbols

    # Symbols the SEC and NSE lists miss (other exchanges, delisted US names) come from Yahoo; still-missing stay unknown.
    known = set(names.ticker)
    todo = [s for s in available_symbols() if not {s, s.replace("_", "-"), s.replace("_", ".")} & known]

    def yahoo(sym: str) -> str | None:
        try:
            head, _, suffix = sym.rpartition("_")
            info = yf.Ticker(f"{head.replace('_', '-')}.{suffix}" if head else sym).get_info()
        except Exception:  # noqa: BLE001 - Yahoo fails in many ways; a miss stays unknown
            return None
        return info.get("longName") or info.get("shortName")

    with ThreadPoolExecutor(2) as pool:
        found = list(pool.map(yahoo, todo))
    extra = pd.DataFrame({"ticker": todo, "company_name": found, "source": "yahoo"}).dropna(subset=["company_name"])
    pd.concat([names, extra]).to_parquet(OUT, index=False)
    print(f"{len(extra)} of {len(todo)} extra names found")


if __name__ == "__main__":
    main()
