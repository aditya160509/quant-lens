"""
Macro Lab - Data Adapters
Unified adapters for all external data sources
"""

import os
import httpx
from datetime import datetime, timedelta
from typing import Optional, List, Dict, Any
import numpy as np

# Load API keys from environment
FRED_API_KEY = os.getenv("FRED_API_KEY", "")
BLS_API_KEY = os.getenv("BLS_API_KEY", "")
BEA_API_KEY = os.getenv("BEA_API_KEY", "")
EIA_API_KEY = os.getenv("EIA_API_KEY", "")
QUICKSTATS_API_KEY = os.getenv("QUICKSTATS_API_KEY", "")


def build_data_adapter_response(
    series: List[Dict],
    units: str,
    frequency: str,
    source_name: str,
    source_url: str,
    fields_covered: List[str],
    warnings: List[str] = None,
    missing_pct: float = 0.0
) -> Dict:
    """Build standardized DataAdapter response."""
    return {
        "series": series,
        "meta": {
            "timezone": "UTC",
            "units": units,
            "frequency": frequency,
            "revisionPolicy": "as of pull time"
        },
        "provenance": [{
            "sourceName": source_name,
            "sourceUrlOrId": source_url,
            "retrievedAt": datetime.utcnow().isoformat() + "Z",
            "fieldsCovered": fields_covered,
            "licenseNote": "Public data"
        }],
        "quality": {
            "missingPct": missing_pct,
            "stalenessSec": 0,
            "revisionFlag": False,
            "warnings": warnings or []
        }
    }


# =============================================================================
# FRED ADAPTER
# =============================================================================

async def fetch_fred_series(
    series_id: str,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None
) -> Dict:
    """
    Fetch time series from FRED API.
    
    Endpoint: https://api.stlouisfed.org/fred/series/observations
    """
    if not FRED_API_KEY:
        return build_data_adapter_response(
            series=[],
            units="unknown",
            frequency="D",
            source_name="FRED",
            source_url=series_id,
            fields_covered=["value"],
            warnings=["FRED_API_KEY not configured"]
        )
    
    # Default to last 5 years
    if not start_date:
        start_date = (datetime.now() - timedelta(days=365*5)).strftime("%Y-%m-%d")
    if not end_date:
        end_date = datetime.now().strftime("%Y-%m-%d")
    
    url = (
        f"https://api.stlouisfed.org/fred/series/observations"
        f"?series_id={series_id}"
        f"&api_key={FRED_API_KEY}"
        f"&file_type=json"
        f"&observation_start={start_date}"
        f"&observation_end={end_date}"
    )
    
    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.get(url)
            response.raise_for_status()
            data = response.json()
        
        series = []
        missing_count = 0
        
        for obs in data.get("observations", []):
            date_str = obs.get("date", "")
            value_str = obs.get("value", ".")
            
            if value_str == "." or value_str == "":
                missing_count += 1
                continue
            
            try:
                value = float(value_str)
                series.append({
                    "t": date_str,
                    "fields": {"value": value}
                })
            except ValueError:
                missing_count += 1
        
        total = len(data.get("observations", [])) or 1
        missing_pct = missing_count / total
        
        return build_data_adapter_response(
            series=series,
            units="value",
            frequency="D",
            source_name="FRED",
            source_url=series_id,
            fields_covered=["value"],
            missing_pct=missing_pct
        )
        
    except Exception as e:
        return build_data_adapter_response(
            series=[],
            units="unknown",
            frequency="D",
            source_name="FRED",
            source_url=series_id,
            fields_covered=["value"],
            warnings=[f"FRED API error: {str(e)}"]
        )


# =============================================================================
# BLS ADAPTER
# =============================================================================

async def fetch_bls_series(
    series_ids: List[str],
    start_year: int = 2019,
    end_year: int = 2025
) -> Dict:
    """
    Fetch time series from BLS API v2.
    
    Endpoint: https://api.bls.gov/publicAPI/v2/timeseries/data/
    """
    if not BLS_API_KEY:
        return build_data_adapter_response(
            series=[],
            units="unknown",
            frequency="M",
            source_name="BLS",
            source_url=",".join(series_ids),
            fields_covered=["value"],
            warnings=["BLS_API_KEY not configured"]
        )
    
    url = "https://api.bls.gov/publicAPI/v2/timeseries/data/"
    payload = {
        "seriesid": series_ids,
        "startyear": str(start_year),
        "endyear": str(end_year),
        "registrationkey": BLS_API_KEY
    }
    
    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.post(url, json=payload)
            response.raise_for_status()
            data = response.json()
        
        series = []
        
        if data.get("status") == "REQUEST_SUCCEEDED":
            for result in data.get("Results", {}).get("series", []):
                for item in result.get("data", []):
                    year = item.get("year", "")
                    period = item.get("period", "")
                    value_str = item.get("value", "")
                    
                    # Convert M01 -> 01, etc.
                    if period.startswith("M"):
                        month = period[1:]
                        date_str = f"{year}-{month}-01"
                    else:
                        continue
                    
                    try:
                        value = float(value_str)
                        series.append({
                            "t": date_str,
                            "fields": {"value": value}
                        })
                    except ValueError:
                        continue
        
        # Sort by date
        series.sort(key=lambda x: x["t"])
        
        return build_data_adapter_response(
            series=series,
            units="index",
            frequency="M",
            source_name="BLS",
            source_url=",".join(series_ids),
            fields_covered=["value"]
        )
        
    except Exception as e:
        return build_data_adapter_response(
            series=[],
            units="unknown",
            frequency="M",
            source_name="BLS",
            source_url=",".join(series_ids),
            fields_covered=["value"],
            warnings=[f"BLS API error: {str(e)}"]
        )


# =============================================================================
# ECB SDW ADAPTER (No API Key)
# =============================================================================

async def fetch_ecb_series(
    flow: str,
    key: str,
    start_period: Optional[str] = None,
    end_period: Optional[str] = None
) -> Dict:
    """
    Fetch time series from ECB Statistical Data Warehouse.
    
    Endpoint: https://sdw-wsrest.ecb.europa.eu/service/data/FLOW/KEY
    """
    if not start_period:
        start_period = (datetime.now() - timedelta(days=365*5)).strftime("%Y-%m")
    if not end_period:
        end_period = datetime.now().strftime("%Y-%m")
    
    url = (
        f"https://sdw-wsrest.ecb.europa.eu/service/data/{flow}/{key}"
        f"?startPeriod={start_period}&endPeriod={end_period}"
    )
    
    headers = {"Accept": "application/vnd.sdmx.data+json;version=1.0.0-wd"}
    
    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.get(url, headers=headers)
            response.raise_for_status()
            data = response.json()
        
        series = []
        
        # Parse SDMX-JSON structure
        datasets = data.get("dataSets", [])
        if datasets:
            observations = datasets[0].get("series", {})
            time_periods = data.get("structure", {}).get("dimensions", {}).get("observation", [])
            
            time_values = []
            for dim in time_periods:
                if dim.get("id") == "TIME_PERIOD":
                    time_values = [v.get("id") for v in dim.get("values", [])]
            
            for series_key, series_data in observations.items():
                obs = series_data.get("observations", {})
                for idx, values in obs.items():
                    if int(idx) < len(time_values):
                        period = time_values[int(idx)]
                        value = values[0] if values else None
                        if value is not None:
                            series.append({
                                "t": period,
                                "fields": {"value": float(value)}
                            })
        
        series.sort(key=lambda x: x["t"])
        
        return build_data_adapter_response(
            series=series,
            units="value",
            frequency="M",
            source_name="ECB",
            source_url=f"{flow}/{key}",
            fields_covered=["value"]
        )
        
    except Exception as e:
        return build_data_adapter_response(
            series=[],
            units="unknown",
            frequency="M",
            source_name="ECB",
            source_url=f"{flow}/{key}",
            fields_covered=["value"],
            warnings=[f"ECB API error: {str(e)}"]
        )


# =============================================================================
# WORLD BANK ADAPTER (No API Key)
# =============================================================================

async def fetch_world_bank_indicator(
    country: str,
    indicator: str,
    start_year: int = 2010,
    end_year: int = 2024
) -> Dict:
    """
    Fetch indicator from World Bank API.
    
    Endpoint: https://api.worldbank.org/v2/country/COUNTRY/indicator/INDICATOR
    """
    url = (
        f"https://api.worldbank.org/v2/country/{country}/indicator/{indicator}"
        f"?format=json&date={start_year}:{end_year}&per_page=500"
    )
    
    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.get(url)
            response.raise_for_status()
            data = response.json()
        
        series = []
        
        # World Bank returns [metadata, data_array]
        if isinstance(data, list) and len(data) > 1:
            for item in data[1] or []:
                date = item.get("date", "")
                value = item.get("value")
                
                if value is not None:
                    series.append({
                        "t": f"{date}-01-01",
                        "fields": {"value": float(value)}
                    })
        
        series.sort(key=lambda x: x["t"])
        
        return build_data_adapter_response(
            series=series,
            units="value",
            frequency="A",
            source_name="WORLD_BANK",
            source_url=f"{country}/{indicator}",
            fields_covered=["value"]
        )
        
    except Exception as e:
        return build_data_adapter_response(
            series=[],
            units="unknown",
            frequency="A",
            source_name="WORLD_BANK",
            source_url=f"{country}/{indicator}",
            fields_covered=["value"],
            warnings=[f"World Bank API error: {str(e)}"]
        )


# =============================================================================
# EIA ADAPTER (v2 API)
# =============================================================================

# EIA v2 series mapping - maps old series IDs to v2 route patterns
EIA_V2_MAPPING = {
    "PET.RWTC.D": {
        "route": "petroleum/pri/spt/data",
        "params": {"product": "EPCWTI", "frequency": "daily", "data[0]": "value"},
        "name": "WTI Crude Oil"
    },
    "PET.RBRTE.D": {
        "route": "petroleum/pri/spt/data", 
        "params": {"product": "EPCBRENT", "frequency": "daily", "data[0]": "value"},
        "name": "Brent Crude"
    },
    "NG.RNGWHHD.D": {
        "route": "natural-gas/pri/sum/data",
        "params": {"series": "RNGWHHD", "frequency": "daily", "data[0]": "value"},
        "name": "Natural Gas Henry Hub"
    }
}

async def fetch_eia_series(
    series_id: str,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None
) -> Dict:
    """
    Fetch energy data from EIA API v2.
    
    EIA v2 endpoint pattern:
    https://api.eia.gov/v2/{category}/{route}/data/?api_key=KEY&frequency=weekly&data[0]=value
    """
    if not EIA_API_KEY:
        return build_data_adapter_response(
            series=[],
            units="unknown",
            frequency="D",
            source_name="EIA",
            source_url=series_id,
            fields_covered=["value"],
            warnings=["EIA_API_KEY not configured"]
        )
    
    # Default dates
    if not start_date:
        start_date = (datetime.now() - timedelta(days=365)).strftime("%Y-%m-%d")
    if not end_date:
        end_date = datetime.now().strftime("%Y-%m-%d")
    
    try:
        # Check if we have a v2 mapping
        if series_id in EIA_V2_MAPPING:
            mapping = EIA_V2_MAPPING[series_id]
            base_url = f"https://api.eia.gov/v2/{mapping['route']}"
            params = {
                "api_key": EIA_API_KEY,
                "start": start_date,
                "end": end_date,
                **mapping["params"]
            }
            
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.get(base_url, params=params)
                response.raise_for_status()
                data = response.json()
            
            series = []
            response_data = data.get("response", {}).get("data", [])
            
            for item in response_data:
                period = item.get("period", "")
                value = item.get("value")
                
                if value is not None:
                    series.append({
                        "t": period,
                        "fields": {"value": float(value)}
                    })
            
            series.sort(key=lambda x: x["t"])
            
            return build_data_adapter_response(
                series=series,
                units="$/bbl" if "petroleum" in mapping["route"] else "$/MMBtu",
                frequency="D",
                source_name="EIA",
                source_url=series_id,
                fields_covered=["value"]
            )
        
        # Fallback: Try the open data API
        url = f"https://api.eia.gov/v2/seriesid/{series_id}?api_key={EIA_API_KEY}"
        
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.get(url)
            
            if response.status_code == 404:
                # Return empty with warning, don't crash
                return build_data_adapter_response(
                    series=[],
                    units="unknown",
                    frequency="D",
                    source_name="EIA",
                    source_url=series_id,
                    fields_covered=["value"],
                    warnings=[f"EIA series {series_id} not found in v2 API. Consider using FRED alternative."]
                )
            
            response.raise_for_status()
            data = response.json()
        
        series = []
        response_data = data.get("response", {}).get("data", [])
        
        for item in response_data:
            period = item.get("period", "")
            value = item.get("value")
            
            if value is not None:
                series.append({
                    "t": period,
                    "fields": {"value": float(value)}
                })
        
        series.sort(key=lambda x: x["t"])
        
        return build_data_adapter_response(
            series=series,
            units="value",
            frequency="D",
            source_name="EIA",
            source_url=series_id,
            fields_covered=["value"]
        )
        
    except Exception as e:
        # Never crash - return empty with warning
        return build_data_adapter_response(
            series=[],
            units="unknown",
            frequency="D",
            source_name="EIA",
            source_url=series_id,
            fields_covered=["value"],
            warnings=[f"EIA API error: {str(e)}. Data may be stale."]
        )


# =============================================================================
# BEA ADAPTER (GDP, PCE, Trade)
# =============================================================================

async def fetch_bea_data(
    dataset: str = "NIPA",
    table_name: str = "T10101",
    frequency: str = "Q",
    start_year: int = 2020
) -> Dict:
    """
    Fetch data from BEA API.
    
    Endpoint: https://apps.bea.gov/api/data/
    Datasets: NIPA, FixedAssets, ITA, etc.
    """
    if not BEA_API_KEY:
        return build_data_adapter_response(
            series=[],
            units="unknown",
            frequency=frequency,
            source_name="BEA",
            source_url=f"{dataset}/{table_name}",
            fields_covered=["value"],
            warnings=["BEA_API_KEY not configured"]
        )
    
    url = (
        f"https://apps.bea.gov/api/data/"
        f"?UserID={BEA_API_KEY}"
        f"&method=GetData"
        f"&datasetname={dataset}"
        f"&TableName={table_name}"
        f"&Frequency={frequency}"
        f"&Year={','.join(str(y) for y in range(start_year, 2026))}"
        f"&ResultFormat=JSON"
    )
    
    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.get(url)
            response.raise_for_status()
            data = response.json()
        
        series = []
        
        results = data.get("BEAAPI", {}).get("Results", {}).get("Data", [])
        for item in results:
            time_period = item.get("TimePeriod", "")
            value_str = item.get("DataValue", "")
            
            # Parse TimePeriod (e.g., "2024Q1" -> "2024-01-01")
            if "Q" in time_period:
                year = time_period[:4]
                quarter = int(time_period[5])
                month = (quarter - 1) * 3 + 1
                date_str = f"{year}-{month:02d}-01"
            elif len(time_period) == 4:
                date_str = f"{time_period}-01-01"
            else:
                date_str = time_period
            
            try:
                # Remove commas from value
                value = float(value_str.replace(",", ""))
                series.append({
                    "t": date_str,
                    "fields": {"value": value}
                })
            except (ValueError, AttributeError):
                continue
        
        series.sort(key=lambda x: x["t"])
        
        return build_data_adapter_response(
            series=series,
            units="billions_usd",
            frequency=frequency,
            source_name="BEA",
            source_url=f"{dataset}/{table_name}",
            fields_covered=["value"]
        )
        
    except Exception as e:
        return build_data_adapter_response(
            series=[],
            units="unknown",
            frequency=frequency,
            source_name="BEA",
            source_url=f"{dataset}/{table_name}",
            fields_covered=["value"],
            warnings=[f"BEA API error: {str(e)}"]
        )


# =============================================================================
# USDA NASS QUICKSTATS ADAPTER (Agriculture)
# =============================================================================

async def fetch_usda_quickstats(
    commodity: str = "CORN",
    stat_category: str = "PRICE RECEIVED",
    year_start: int = 2020
) -> Dict:
    """
    Fetch agricultural data from USDA NASS QuickStats.
    
    Endpoint: https://quickstats.nass.usda.gov/api/api_GET/
    """
    if not QUICKSTATS_API_KEY:
        return build_data_adapter_response(
            series=[],
            units="unknown",
            frequency="M",
            source_name="USDA",
            source_url=f"{commodity}/{stat_category}",
            fields_covered=["value"],
            warnings=["QUICKSTATS_API_KEY not configured"]
        )
    
    url = (
        f"https://quickstats.nass.usda.gov/api/api_GET/"
        f"?key={QUICKSTATS_API_KEY}"
        f"&commodity_desc={commodity}"
        f"&statisticcat_desc={stat_category}"
        f"&year__GE={year_start}"
        f"&format=JSON"
    )
    
    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.get(url)
            response.raise_for_status()
            data = response.json()
        
        series = []
        
        for item in data.get("data", []):
            year = item.get("year", "")
            # Try to get reference_period_desc for month
            period = item.get("reference_period_desc", "ANNUAL")
            value_str = item.get("Value", "")
            
            # Build date
            month_map = {
                "JAN": "01", "FEB": "02", "MAR": "03", "APR": "04",
                "MAY": "05", "JUN": "06", "JUL": "07", "AUG": "08",
                "SEP": "09", "OCT": "10", "NOV": "11", "DEC": "12",
                "ANNUAL": "06", "YEAR": "06"
            }
            month = month_map.get(period.upper()[:3], "06")
            date_str = f"{year}-{month}-01"
            
            try:
                # Remove commas and convert
                value = float(value_str.replace(",", ""))
                series.append({
                    "t": date_str,
                    "fields": {"value": value}
                })
            except (ValueError, AttributeError):
                continue
        
        # Deduplicate by date (keep first)
        seen_dates = set()
        unique_series = []
        for s in series:
            if s["t"] not in seen_dates:
                seen_dates.add(s["t"])
                unique_series.append(s)
        
        unique_series.sort(key=lambda x: x["t"])
        
        return build_data_adapter_response(
            series=unique_series,
            units="usd_per_unit",
            frequency="M",
            source_name="USDA",
            source_url=f"{commodity}/{stat_category}",
            fields_covered=["value"]
        )
        
    except Exception as e:
        return build_data_adapter_response(
            series=[],
            units="unknown",
            frequency="M",
            source_name="USDA",
            source_url=f"{commodity}/{stat_category}",
            fields_covered=["value"],
            warnings=[f"USDA API error: {str(e)}"]
        )


# =============================================================================
# UNIFIED FETCH FUNCTION
# =============================================================================

async def fetch_series(
    source: str,
    series_id: str,
    region: str = "US",
    start: Optional[str] = None,
    end: Optional[str] = None
) -> Dict:
    """
    Unified function to fetch from any supported source.
    Routes to the appropriate adapter based on source.
    """
    source_upper = source.upper()
    
    if source_upper == "FRED":
        return await fetch_fred_series(series_id, start, end)
    
    elif source_upper == "BLS":
        return await fetch_bls_series([series_id])
    
    elif source_upper == "ECB":
        # ECB series_id format: FLOW/KEY
        parts = series_id.split("/", 1)
        if len(parts) == 2:
            return await fetch_ecb_series(parts[0], parts[1])
        return await fetch_ecb_series("FM", series_id)
    
    elif source_upper == "WORLD_BANK":
        # Format: COUNTRY/INDICATOR
        parts = series_id.split("/", 1)
        if len(parts) == 2:
            return await fetch_world_bank_indicator(parts[0], parts[1])
        return await fetch_world_bank_indicator(region, series_id)
    
    elif source_upper == "EIA":
        return await fetch_eia_series(series_id, start, end)
    
    elif source_upper == "BEA":
        # Format: DATASET/TABLE
        parts = series_id.split("/", 1)
        if len(parts) == 2:
            return await fetch_bea_data(dataset=parts[0], table_name=parts[1])
        return await fetch_bea_data(table_name=series_id)
    
    elif source_upper == "USDA":
        # Format: COMMODITY/STAT_CATEGORY
        parts = series_id.split("/", 1)
        if len(parts) == 2:
            return await fetch_usda_quickstats(commodity=parts[0], stat_category=parts[1])
        return await fetch_usda_quickstats(commodity=series_id)
    
    else:
        return build_data_adapter_response(
            series=[],
            units="unknown",
            frequency="D",
            source_name=source_upper,
            source_url=series_id,
            fields_covered=["value"],
            warnings=[f"Unknown source: {source}"]
        )

