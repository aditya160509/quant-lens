"""
Series Catalog - Central registry of all data series
Maps internal IDs to source-specific IDs
No module should hardcode external series IDs
"""

from typing import Dict, List, Optional
from dataclasses import dataclass
from enum import Enum


class DataSource(str, Enum):
    FRED = "FRED"
    BLS = "BLS"
    BEA = "BEA"
    EIA = "EIA"
    USDA = "USDA"
    ECB = "ECB"
    WORLD_BANK = "WORLD_BANK"
    RBI = "RBI"
    MOSPI = "MOSPI"
    BIS = "BIS"


class Frequency(str, Enum):
    DAILY = "D"
    WEEKLY = "W"
    MONTHLY = "M"
    QUARTERLY = "Q"
    ANNUAL = "A"


@dataclass
class SeriesConfig:
    internal_id: str
    source: DataSource
    source_series_id: str
    units: str
    frequency: Frequency
    region: str
    category: str
    notes: str = ""
    transform: str = "level"  # level, yoy_pct, mom_pct, diff
    fallback_source: Optional[str] = None
    fallback_series_id: Optional[str] = None


# =============================================================================
# MASTER SERIES CATALOG
# =============================================================================

SERIES_CATALOG: Dict[str, SeriesConfig] = {
    
    # =========================================================================
    # US INFLATION SERIES
    # =========================================================================
    "US_CPI_HEADLINE": SeriesConfig(
        internal_id="US_CPI_HEADLINE",
        source=DataSource.FRED,
        source_series_id="CPIAUCSL",
        units="index",
        frequency=Frequency.MONTHLY,
        region="US",
        category="inflation",
        notes="CPI All Urban Consumers"
    ),
    "US_CPI_CORE": SeriesConfig(
        internal_id="US_CPI_CORE",
        source=DataSource.FRED,
        source_series_id="CPILFESL",
        units="index",
        frequency=Frequency.MONTHLY,
        region="US",
        category="inflation",
        notes="CPI Less Food and Energy"
    ),
    "US_PCE": SeriesConfig(
        internal_id="US_PCE",
        source=DataSource.FRED,
        source_series_id="PCEPI",
        units="index",
        frequency=Frequency.MONTHLY,
        region="US",
        category="inflation",
        notes="PCE Price Index"
    ),
    
    # =========================================================================
    # US GROWTH SERIES
    # =========================================================================
    "US_GDP": SeriesConfig(
        internal_id="US_GDP",
        source=DataSource.BEA,
        source_series_id="NIPA/T10101",
        units="billions_usd",
        frequency=Frequency.QUARTERLY,
        region="US",
        category="growth",
        notes="Real GDP"
    ),
    "US_INDPRO": SeriesConfig(
        internal_id="US_INDPRO",
        source=DataSource.FRED,
        source_series_id="INDPRO",
        units="index",
        frequency=Frequency.MONTHLY,
        region="US",
        category="growth",
        notes="Industrial Production Index"
    ),
    "US_PAYROLLS": SeriesConfig(
        internal_id="US_PAYROLLS",
        source=DataSource.FRED,
        source_series_id="PAYEMS",
        units="thousands",
        frequency=Frequency.MONTHLY,
        region="US",
        category="labor",
        notes="All Employees, Total Nonfarm"
    ),
    "US_UNEMPLOYMENT": SeriesConfig(
        internal_id="US_UNEMPLOYMENT",
        source=DataSource.FRED,
        source_series_id="UNRATE",
        units="percent",
        frequency=Frequency.MONTHLY,
        region="US",
        category="labor",
        notes="Unemployment Rate"
    ),
    
    # =========================================================================
    # US RATES & YIELDS
    # =========================================================================
    "US_FEDFUNDS": SeriesConfig(
        internal_id="US_FEDFUNDS",
        source=DataSource.FRED,
        source_series_id="FEDFUNDS",
        units="percent",
        frequency=Frequency.MONTHLY,
        region="US",
        category="rates",
        notes="Effective Federal Funds Rate"
    ),
    "US_YIELD_3M": SeriesConfig(
        internal_id="US_YIELD_3M",
        source=DataSource.FRED,
        source_series_id="DGS3MO",
        units="percent",
        frequency=Frequency.DAILY,
        region="US",
        category="rates",
        notes="3-Month Treasury Constant Maturity"
    ),
    "US_YIELD_2Y": SeriesConfig(
        internal_id="US_YIELD_2Y",
        source=DataSource.FRED,
        source_series_id="DGS2",
        units="percent",
        frequency=Frequency.DAILY,
        region="US",
        category="rates",
        notes="2-Year Treasury Constant Maturity"
    ),

    "US_YIELD_5Y": SeriesConfig(
        internal_id="US_YIELD_5Y",
        source=DataSource.FRED,
        source_series_id="DGS5",
        units="percent",
        frequency=Frequency.DAILY,
        region="US",
        category="rates",
        notes="5-Year Treasury Constant Maturity"
    ),
    "US_YIELD_10Y": SeriesConfig(
        internal_id="US_YIELD_10Y",
        source=DataSource.FRED,
        source_series_id="DGS10",
        units="percent",
        frequency=Frequency.DAILY,
        region="US",
        category="rates",
        notes="10-Year Treasury Constant Maturity"
    ),
    "US_YIELD_30Y": SeriesConfig(
        internal_id="US_YIELD_30Y",
        source=DataSource.FRED,
        source_series_id="DGS30",
        units="percent",
        frequency=Frequency.DAILY,
        region="US",
        category="rates",
        notes="30-Year Treasury Constant Maturity"
    ),
    
    # =========================================================================
    # US CREDIT SPREADS
    # =========================================================================
    "US_BAA_SPREAD": SeriesConfig(
        internal_id="US_BAA_SPREAD",
        source=DataSource.FRED,
        source_series_id="BAA10Y",
        units="percent",
        frequency=Frequency.DAILY,
        region="US",
        category="credit",
        notes="Moody's BAA Corporate Bond Spread over 10Y"
    ),
    "US_HY_SPREAD": SeriesConfig(
        internal_id="US_HY_SPREAD",
        source=DataSource.FRED,
        source_series_id="BAMLH0A0HYM2",
        units="percent",
        frequency=Frequency.DAILY,
        region="US",
        category="credit",
        notes="ICE BofA High Yield OAS"
    ),
    
    # =========================================================================
    # US LIQUIDITY & MONEY
    # =========================================================================
    "US_M2": SeriesConfig(
        internal_id="US_M2",
        source=DataSource.FRED,
        source_series_id="M2SL",
        units="billions_usd",
        frequency=Frequency.MONTHLY,
        region="US",
        category="liquidity",
        notes="M2 Money Stock"
    ),
    "US_FED_BALANCE_SHEET": SeriesConfig(
        internal_id="US_FED_BALANCE_SHEET",
        source=DataSource.FRED,
        source_series_id="WALCL",
        units="millions_usd",
        frequency=Frequency.WEEKLY,
        region="US",
        category="liquidity",
        notes="Federal Reserve Total Assets"
    ),
    
    # =========================================================================
    # US VOLATILITY & RISK
    # =========================================================================
    "US_VIX": SeriesConfig(
        internal_id="US_VIX",
        source=DataSource.FRED,
        source_series_id="VIXCLS",
        units="index",
        frequency=Frequency.DAILY,
        region="US",
        category="volatility",
        notes="CBOE Volatility Index"
    ),
    
    # =========================================================================
    # US EQUITY
    # =========================================================================
    "US_SP500": SeriesConfig(
        internal_id="US_SP500",
        source=DataSource.FRED,
        source_series_id="SP500",
        units="index",
        frequency=Frequency.DAILY,
        region="US",
        category="equity",
        notes="S&P 500 Index"
    ),
    
    # =========================================================================
    # US FX
    # =========================================================================
    "US_DXY": SeriesConfig(
        internal_id="US_DXY",
        source=DataSource.FRED,
        source_series_id="DTWEXBGS",
        units="index",
        frequency=Frequency.DAILY,
        region="US",
        category="fx",
        notes="Trade Weighted Dollar Index"
    ),
    
    # =========================================================================
    # ENERGY (EIA + FRED fallback)
    # =========================================================================
    "ENERGY_WTI": SeriesConfig(
        internal_id="ENERGY_WTI",
        source=DataSource.FRED,  # Use FRED as primary (more reliable)
        source_series_id="DCOILWTICO",
        units="usd_per_bbl",
        frequency=Frequency.DAILY,
        region="Global",
        category="energy",
        notes="WTI Crude Oil Price",
        fallback_source="EIA",
        fallback_series_id="PET.RWTC.D"
    ),
    "ENERGY_BRENT": SeriesConfig(
        internal_id="ENERGY_BRENT",
        source=DataSource.FRED,
        source_series_id="DCOILBRENTEU",
        units="usd_per_bbl",
        frequency=Frequency.DAILY,
        region="Global",
        category="energy",
        notes="Brent Crude Oil Price"
    ),
    "ENERGY_NATGAS": SeriesConfig(
        internal_id="ENERGY_NATGAS",
        source=DataSource.FRED,
        source_series_id="DHHNGSP",
        units="usd_per_mmbtu",
        frequency=Frequency.DAILY,
        region="US",
        category="energy",
        notes="Henry Hub Natural Gas Spot Price"
    ),
    
    # =========================================================================
    # COMMODITIES
    # =========================================================================
    "COMMODITY_GOLD": SeriesConfig(
        internal_id="COMMODITY_GOLD",
        source=DataSource.FRED,
        source_series_id="GOLDPMGBD228NLBM",  # Gold PM Fix London
        units="usd_per_oz",
        frequency=Frequency.DAILY,
        region="Global",
        category="commodities",
        notes="Gold Fixing Price London PM"
    ),
    "COMMODITY_COPPER": SeriesConfig(
        internal_id="COMMODITY_COPPER",
        source=DataSource.FRED,
        source_series_id="PCOPPUSDM",
        units="usd_per_mt",
        frequency=Frequency.MONTHLY,
        region="Global",
        category="commodities",
        notes="Global Copper Price"
    ),
    "COMMODITY_CORN": SeriesConfig(
        internal_id="COMMODITY_CORN",
        source=DataSource.FRED,
        source_series_id="PMAIZMTUSDM",  # Global maize price
        units="usd_per_mt",
        frequency=Frequency.MONTHLY,
        region="Global",
        category="commodities",
        notes="Global Maize (Corn) Price"
    ),
    "COMMODITY_WHEAT": SeriesConfig(
        internal_id="COMMODITY_WHEAT",
        source=DataSource.FRED,
        source_series_id="PWHEAMTUSDM",
        units="usd_per_mt",
        frequency=Frequency.MONTHLY,
        region="Global",
        category="commodities",
        notes="Global Wheat Price"
    ),
    "COMMODITY_ALUMINUM": SeriesConfig(
        internal_id="COMMODITY_ALUMINUM",
        source=DataSource.FRED,
        source_series_id="PALUMUSDM",
        units="usd_per_mt",
        frequency=Frequency.MONTHLY,
        region="Global",
        category="commodities",
        notes="Global Aluminum Price"
    ),
    "COMMODITY_SILVER": SeriesConfig(
        internal_id="COMMODITY_SILVER",
        source=DataSource.FRED,
        source_series_id="SLVPRUSD",  # Silver Price in USD
        units="usd_per_oz",
        frequency=Frequency.MONTHLY,
        region="Global",
        category="commodities",
        notes="Silver Price USD per Troy Oz"
    ),

    # Farm Products Index (for agriculture bucket)
    "US_FARM_PRODUCTS_PPI": SeriesConfig(
        internal_id="US_FARM_PRODUCTS_PPI",
        source=DataSource.FRED,
        source_series_id="WPU01",
        units="index",
        frequency=Frequency.MONTHLY,
        region="US",
        category="commodities",
        notes="PPI Farm Products"
    ),
    # USD Broad Index for financialization detection
    "US_USD_BROAD": SeriesConfig(
        internal_id="US_USD_BROAD",
        source=DataSource.FRED,
        source_series_id="DTWEXBGS",
        units="index",
        frequency=Frequency.DAILY,
        region="US",
        category="fx",
        notes="Trade Weighted USD Index Broad"
    ),

    
    # =========================================================================
    # EUROZONE (ECB SDW)
    # =========================================================================
    "EU_HICP": SeriesConfig(
        internal_id="EU_HICP",
        source=DataSource.ECB,
        source_series_id="ICP/M.U2.N.000000.4.INX",
        units="index",
        frequency=Frequency.MONTHLY,
        region="Europe",
        category="inflation",
        notes="HICP All Items Eurozone"
    ),
    "EU_GDP": SeriesConfig(
        internal_id="EU_GDP",
        source=DataSource.ECB,
        source_series_id="MNA/Q.Y.I8.W2.S1.S1.B.B1GQ._Z._Z._Z.EUR.LR.N",
        units="index",
        frequency=Frequency.QUARTERLY,
        region="Europe",
        category="growth",
        notes="Eurozone Real GDP"
    ),
    "EU_POLICY_RATE": SeriesConfig(
        internal_id="EU_POLICY_RATE",
        source=DataSource.ECB,
        source_series_id="FM/M.U2.EUR.4F.KR.MRR_FR.LEV",
        units="percent",
        frequency=Frequency.MONTHLY,
        region="Europe",
        category="rates",
        notes="ECB Main Refinancing Rate"
    ),
    
    # =========================================================================
    # INDIA (RBI DBIE)
    # =========================================================================
    "IN_CPI": SeriesConfig(
        internal_id="IN_CPI",
        source=DataSource.RBI,
        source_series_id="CPI_COMBINED",
        units="index",
        frequency=Frequency.MONTHLY,
        region="India",
        category="inflation",
        notes="CPI Combined All India"
    ),
    "IN_WPI": SeriesConfig(
        internal_id="IN_WPI",
        source=DataSource.MOSPI,
        source_series_id="WPI_ALL",
        units="index",
        frequency=Frequency.MONTHLY,
        region="India",
        category="inflation",
        notes="Wholesale Price Index"
    ),
    "IN_IIP": SeriesConfig(
        internal_id="IN_IIP",
        source=DataSource.MOSPI,
        source_series_id="IIP_GENERAL",
        units="index",
        frequency=Frequency.MONTHLY,
        region="India",
        category="growth",
        notes="Index of Industrial Production"
    ),
    "IN_REPO_RATE": SeriesConfig(
        internal_id="IN_REPO_RATE",
        source=DataSource.RBI,
        source_series_id="REPO_RATE",
        units="percent",
        frequency=Frequency.DAILY,
        region="India",
        category="rates",
        notes="RBI Repo Rate"
    ),
    
    # =========================================================================
    # WORLD BANK INDICATORS
    # =========================================================================
    "WB_GDP_GROWTH": SeriesConfig(
        internal_id="WB_GDP_GROWTH",
        source=DataSource.WORLD_BANK,
        source_series_id="NY.GDP.MKTP.KD.ZG",
        units="percent",
        frequency=Frequency.ANNUAL,
        region="Global",
        category="growth",
        notes="GDP Growth Annual %"
    ),
    "WB_INFLATION": SeriesConfig(
        internal_id="WB_INFLATION",
        source=DataSource.WORLD_BANK,
        source_series_id="FP.CPI.TOTL.ZG",
        units="percent",
        frequency=Frequency.ANNUAL,
        region="Global",
        category="inflation",
        notes="Inflation Consumer Prices Annual %"
    ),
    "WB_CURRENT_ACCOUNT": SeriesConfig(
        internal_id="WB_CURRENT_ACCOUNT",
        source=DataSource.WORLD_BANK,
        source_series_id="BN.CAB.XOKA.GD.ZS",
        units="percent_gdp",
        frequency=Frequency.ANNUAL,
        region="Global",
        category="external",
        notes="Current Account Balance % of GDP"
    ),
    
    # =========================================================================
    # BIS (Bank for International Settlements)
    # =========================================================================
    "BIS_CREDIT_GAP": SeriesConfig(
        internal_id="BIS_CREDIT_GAP",
        source=DataSource.BIS,
        source_series_id="TOTAL_CREDIT/Q:US:P:A:M:XDC:A",
        units="percent_gdp",
        frequency=Frequency.QUARTERLY,
        region="US",
        category="credit",
        notes="Credit to GDP Gap"
    ),
}


def get_series_config(internal_id: str) -> Optional[SeriesConfig]:
    """Get series configuration by internal ID."""
    return SERIES_CATALOG.get(internal_id)


def get_series_by_category(category: str) -> List[SeriesConfig]:
    """Get all series in a category."""
    return [s for s in SERIES_CATALOG.values() if s.category == category]


def get_series_by_region(region: str) -> List[SeriesConfig]:
    """Get all series for a region."""
    return [s for s in SERIES_CATALOG.values() if s.region == region]


def get_series_by_source(source: DataSource) -> List[SeriesConfig]:
    """Get all series from a source."""
    return [s for s in SERIES_CATALOG.values() if s.source == source]


# Module-specific series requirements
MODULE_SERIES = {
    "shock_network": [
        "US_SP500", "US_YIELD_10Y", "US_DXY", "US_BAA_SPREAD", 
        "US_VIX", "ENERGY_WTI", "COMMODITY_GOLD"
    ],
    "earthquake": [
        "US_YIELD_10Y", "US_YIELD_2Y", "US_DXY", "US_BAA_SPREAD",
        "US_VIX", "US_M2", "US_HY_SPREAD"
    ],
    "cb_intent": [
        "US_FEDFUNDS", "EU_POLICY_RATE", "IN_REPO_RATE",
        "US_FED_BALANCE_SHEET"
    ],
    "prob_matrix": [
        "US_CPI_HEADLINE", "US_INDPRO", "US_YIELD_10Y", 
        "US_BAA_SPREAD", "US_VIX"
    ],
    "alignment": [
        "US_CPI_HEADLINE", "US_INDPRO", "US_BAA_SPREAD",
        "US_M2", "US_FEDFUNDS"
    ],
    "heatmap": [
        "WB_GDP_GROWTH", "WB_INFLATION", "WB_CURRENT_ACCOUNT"
    ],
    "liquidity": [
        "US_FED_BALANCE_SHEET", "US_M2", "US_FEDFUNDS"
    ],
    "commodities": [
        # Energy bucket
        "ENERGY_WTI", "ENERGY_BRENT", "ENERGY_NATGAS",
        # Metals bucket  
        "COMMODITY_COPPER", "COMMODITY_ALUMINUM",
        # Precious bucket
        "COMMODITY_GOLD", "COMMODITY_SILVER",
        # Agriculture bucket
        "COMMODITY_CORN", "COMMODITY_WHEAT", "US_FARM_PRODUCTS_PPI",
        # For decomposition
        "US_USD_BROAD", "US_CPI_HEADLINE", "US_INDPRO"
    ],
    "yield_curve_lab": [
        "US_YIELD_3M", "US_YIELD_2Y", "US_YIELD_5Y", 
        "US_YIELD_10Y", "US_YIELD_30Y",
        # For recession probability
        "US_BAA_SPREAD", "US_VIX"
    ],

    "energy": [
        "ENERGY_WTI", "ENERGY_BRENT", "ENERGY_NATGAS"
    ],
    "correlations": [
        "US_SP500", "US_YIELD_10Y", "US_VIX", "US_DXY",
        "COMMODITY_GOLD", "US_BAA_SPREAD"
    ]
}


def get_module_series(module_id: str) -> List[SeriesConfig]:
    """Get all series required for a module."""
    series_ids = MODULE_SERIES.get(module_id, [])
    return [SERIES_CATALOG[sid] for sid in series_ids if sid in SERIES_CATALOG]
