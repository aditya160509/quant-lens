"""Static industry-to-industry-group mapping for Screener V2.

The local fundamentals snapshot generally carries yfinance-style industry labels,
not full GICS tiers. This lookup gives Screener V2 a stable industry-group tier
for relative percentile views without inventing a dynamic data dependency.
"""

from __future__ import annotations

from typing import Any

import pandas as pd


INDUSTRY_TO_GROUP: dict[str, str] = {
    "Aerospace & Defense": "Capital Goods",
    "Agricultural Inputs": "Materials",
    "Auto Manufacturers": "Automobiles & Components",
    "Auto Parts": "Automobiles & Components",
    "Banks - Diversified": "Banks",
    "Banks - Regional": "Banks",
    "Biotechnology": "Pharmaceuticals, Biotechnology & Life Sciences",
    "Building Products & Equipment": "Capital Goods",
    "Chemicals": "Materials",
    "Communication Equipment": "Technology Hardware & Equipment",
    "Computer Hardware": "Technology Hardware & Equipment",
    "Confectioners": "Food, Beverage & Tobacco",
    "Consumer Electronics": "Technology Hardware & Equipment",
    "Credit Services": "Financial Services",
    "Diagnostics & Research": "Health Care Equipment & Services",
    "Drug Manufacturers - General": "Pharmaceuticals, Biotechnology & Life Sciences",
    "Drug Manufacturers - Specialty & Generic": "Pharmaceuticals, Biotechnology & Life Sciences",
    "Electronic Components": "Technology Hardware & Equipment",
    "Engineering & Construction": "Capital Goods",
    "Entertainment": "Media & Entertainment",
    "Farm & Heavy Construction Machinery": "Capital Goods",
    "Gold": "Materials",
    "Healthcare Plans": "Health Care Equipment & Services",
    "Information Technology Services": "Software & Services",
    "Insurance - Diversified": "Insurance",
    "Insurance - Life": "Insurance",
    "Insurance - Property & Casualty": "Insurance",
    "Internet Content & Information": "Media & Entertainment",
    "Medical Devices": "Health Care Equipment & Services",
    "Medical Instruments & Supplies": "Health Care Equipment & Services",
    "Oil & Gas E&P": "Energy",
    "Oil & Gas Equipment & Services": "Energy",
    "Oil & Gas Integrated": "Energy",
    "Oil & Gas Midstream": "Energy",
    "Oil & Gas Refining & Marketing": "Energy",
    "Packaged Foods": "Food, Beverage & Tobacco",
    "REIT - Diversified": "Real Estate",
    "REIT - Healthcare Facilities": "Real Estate",
    "REIT - Industrial": "Real Estate",
    "REIT - Office": "Real Estate",
    "REIT - Residential": "Real Estate",
    "REIT - Retail": "Real Estate",
    "Restaurants": "Consumer Services",
    "Semiconductor Equipment & Materials": "Technology Hardware & Equipment",
    "Semiconductors": "Technology Hardware & Equipment",
    "Software - Application": "Software & Services",
    "Software - Infrastructure": "Software & Services",
    "Specialty Chemicals": "Materials",
    "Specialty Industrial Machinery": "Capital Goods",
    "Steel": "Materials",
    "Telecom Services": "Telecommunication Services",
    "Utilities - Diversified": "Utilities",
    "Utilities - Regulated Electric": "Utilities",
    "Utilities - Regulated Gas": "Utilities",
    "Utilities - Regulated Water": "Utilities",
}


def add_industry_group(df: pd.DataFrame, industry_col: str = "industry") -> pd.Series:
    if df.empty or industry_col not in df.columns:
        return pd.Series("Unclassified", index=df.index)
    return df[industry_col].astype(str).map(INDUSTRY_TO_GROUP).fillna("Unclassified")
