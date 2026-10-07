"""Small observed-data-shaped fixtures shared by Factors V2 acceptance tests."""

import numpy as np
import pandas as pd
import pytest


@pytest.fixture
def factors_data(tmp_path, monkeypatch):
    from app.services.factors_v2.core import data_loader as loader

    backend = tmp_path / "backend"
    factors = tmp_path / "factors"
    (backend / "fundamentals").mkdir(parents=True)
    (backend / "factors_us").mkdir()
    (backend / "canonical").mkdir()
    (factors / "processed").mkdir(parents=True)
    monkeypatch.setattr(loader, "BACKEND_DATA", backend)
    monkeypatch.setattr(loader, "FACTORS_DATA", factors)
    dates = pd.bdate_range("2022-01-03", periods=420)
    symbols = ["SPY"] + [f"T{i:02}" for i in range(30)]
    rng = np.random.default_rng(2025)
    returns = rng.normal(0.0004, 0.01, size=(len(dates), len(symbols)))
    close = 50 * np.exp(np.cumsum(returns, axis=0))
    prices = []
    for j, s in enumerate(symbols):
        prices.append(
            pd.DataFrame(
                {
                    "Ticker": s,
                    "Date": dates,
                    "Open": close[:, j],
                    "High": close[:, j] * 1.01,
                    "Low": close[:, j] * 0.99,
                    "Close": close[:, j],
                    "Volume": 1e6 + j * 1e4,
                }
            )
        )
    market = pd.concat(prices, ignore_index=True)
    market.to_parquet(backend / "market_universe.parquet", index=False)
    funds = []
    for j, s in enumerate(symbols):
        for year in [2021, 2022, 2023]:
            funds.append(
                {
                    "ticker": s,
                    "reportDate": pd.Timestamp(f"{year}-01-01"),
                    "periodType": "12M",
                    "Common Stock Equity": 1e9 + j * 1e7,
                    "Net Income": 1e8 + j * 1e6,
                    "Ordinary Shares Number": 1e8,
                    "Gross Profit": 2e8,
                    "Total Revenue": 1e9 + year * 1e5,
                    "Total Assets": 2e9 + year * 1e5,
                    "marketCap": 9e99,
                    "priceToBook": 99.0,
                    "sector": "Tech" if j % 2 else "Finance",
                    "currency": "USD",
                }
            )
    fundamentals = pd.DataFrame(funds)
    fundamentals.to_parquet(
        backend / "fundamentals/master_fundamentals.parquet", index=False
    )
    ff = pd.DataFrame(
        rng.normal(0.02, 1, size=(len(dates), 7)),
        columns=["Mkt-RF", "SMB", "HML", "RMW", "CMA", "RF", "Mom"],
    )
    ff["Date"] = dates.strftime("%Y%m%d")
    ff[["Date", "Mkt-RF", "SMB", "HML", "RMW", "CMA", "RF"]].to_csv(
        backend / "factors_us/ff5_daily.csv", index=False
    )
    ff[["Date", "Mkt-RF", "SMB", "HML", "RF"]].to_csv(
        backend / "factors_us/ff3_daily.csv", index=False
    )
    ff[["Date", "Mom"]].to_csv(backend / "factors_us/momentum_daily.csv", index=False)
    pd.DataFrame(
        {
            "date": dates,
            "vix_close": np.tile([15.0, 35.0], len(dates) // 2),
            "yc_slope_10y_2y": np.sin(np.arange(len(dates))),
            "ust_10y": 3.0,
        }
    ).to_parquet(factors / "processed/category7_macro_regime.parquet", index=False)
    pd.DataFrame({"Ticker": "USDJPY=X", "Date": dates, "Close": 150.0}).to_parquet(
        backend / "canonical/fx_daily.parquet", index=False
    )
    metadata = {
        s: {
            "quote_currency": "USD",
            "financial_currency": "USD",
            "quoted_units_per_ordinary_share": 1,
        }
        for s in symbols
    }
    return {
        "backend": backend,
        "factors": factors,
        "dates": dates,
        "symbols": symbols,
        "metadata": metadata,
        "prices": market,
        "fundamentals": fundamentals,
    }
