"""
ScreenerState & Condition System
=================================
Unified state management for Quant360 Screener.
All UI interactions modify this state, which is sent to the evaluation engine.
"""

from dataclasses import dataclass, field, asdict
from typing import List, Dict, Any, Optional, Literal
from datetime import datetime
import json
import hashlib


# =============================================================================
# CONDITION OBJECT SYSTEM (Task 2.1)
# =============================================================================

@dataclass
class Condition:
    """
    Normalized representation for every possible filter.
    Every UI slider, checkbox, dropdown maps to one or more Condition objects.
    """
    # Core fields
    field: str  # e.g., "RSI_14", "PE_Ratio", "close", "volume"
    operator: Literal[
        "lt", "gt", "lte", "gte", "eq", "neq",
        "between", "not_between",
        "crosses_above", "crosses_below",
        "contains", "not_contains",
        "is_true", "is_false"
    ]
    value: Any  # number, tuple for range, string, bool
    
    # Classification
    condition_type: Literal[
        "indicator", "fundamental", "pattern", "price", "volume", "custom"
    ] = "indicator"
    
    # Behavior
    missing_policy: Literal["include", "exclude"] = "exclude"
    weight: float = 1.0  # For scoring mode
    
    # Metadata
    source_tab: Optional[str] = None  # Which tab created this condition
    label: Optional[str] = None  # Human-readable description
    
    def to_dict(self) -> Dict:
        return asdict(self)
    
    @classmethod
    def from_dict(cls, data: Dict) -> "Condition":
        return cls(**data)
    
    def evaluate(self, symbol_data: Dict) -> bool:
        """Evaluate this condition against a symbol's data."""
        val = symbol_data.get(self.field)
        
        # Handle missing data
        if val is None:
            return self.missing_policy == "include"
        
        try:
            if self.operator == "lt":
                return val < self.value
            elif self.operator == "gt":
                return val > self.value
            elif self.operator == "lte":
                return val <= self.value
            elif self.operator == "gte":
                return val >= self.value
            elif self.operator == "eq":
                return val == self.value
            elif self.operator == "neq":
                return val != self.value
            elif self.operator == "between":
                low, high = self.value
                return low <= val <= high
            elif self.operator == "not_between":
                low, high = self.value
                return val < low or val > high
            elif self.operator == "is_true":
                return bool(val)
            elif self.operator == "is_false":
                return not bool(val)
            elif self.operator == "contains":
                return self.value in str(val)
            elif self.operator == "not_contains":
                return self.value not in str(val)
            else:
                return True  # Unknown operator, pass through
        except (TypeError, ValueError):
            return self.missing_policy == "include"


@dataclass
class ConditionGroup:
    """Group of conditions with AND/OR logic."""
    conditions: List[Condition] = field(default_factory=list)
    logic: Literal["AND", "OR"] = "AND"
    
    def evaluate(self, symbol_data: Dict) -> bool:
        if not self.conditions:
            return True
        
        if self.logic == "AND":
            return all(c.evaluate(symbol_data) for c in self.conditions)
        else:  # OR
            return any(c.evaluate(symbol_data) for c in self.conditions)


# =============================================================================
# SCREENER STATE OBJECT (Task 1.2)
# =============================================================================

@dataclass
class ScreenerState:
    """
    The single JSON object representing the complete state of any screening session.
    Every UI interaction modifies this state.
    """
    # Universe selection
    universe: str = "INDIA"  # INDIA, US, CRYPTO, FX, INDEX, ETF
    asset_types: List[str] = field(default_factory=lambda: ["EQUITY"])
    
    # Time window
    time_window: str = "60D"  # 20D, 60D, 120D, 252D, 1Y, 5Y
    lookback_days: int = 60
    
    # Active tab
    active_tab: str = "tradeable"
    
    # Filter conditions (from all tabs)
    conditions: List[Condition] = field(default_factory=list)
    condition_groups: List[ConditionGroup] = field(default_factory=list)
    
    # Formula mode
    formula_mode: bool = False
    filter_formula: Optional[str] = None
    rank_formula: Optional[str] = None
    
    # Sort configuration
    sort_by: str = "score"
    sort_desc: bool = True
    
    # Display preferences
    display_columns: List[str] = field(default_factory=lambda: [
        "ticker", "sector", "price", "change_1d", "change_5d", "score"
    ])
    max_results: int = 100
    
    # Auto-refresh settings
    auto_refresh: bool = False
    refresh_interval_seconds: int = 300
    
    # Metadata
    version: int = 1
    created_at: Optional[str] = None
    updated_at: Optional[str] = None
    
    def __post_init__(self):
        if self.created_at is None:
            self.created_at = datetime.utcnow().isoformat()
        self.updated_at = datetime.utcnow().isoformat()
    
    def add_condition(self, condition: Condition):
        """Add a condition to the state."""
        self.conditions.append(condition)
        self.updated_at = datetime.utcnow().isoformat()
    
    def remove_condition(self, field: str):
        """Remove conditions by field name."""
        self.conditions = [c for c in self.conditions if c.field != field]
        self.updated_at = datetime.utcnow().isoformat()
    
    def clear_conditions(self, source_tab: Optional[str] = None):
        """Clear all conditions (optionally from a specific tab)."""
        if source_tab:
            self.conditions = [c for c in self.conditions if c.source_tab != source_tab]
        else:
            self.conditions = []
        self.updated_at = datetime.utcnow().isoformat()
    
    def get_conditions_by_tab(self, tab: str) -> List[Condition]:
        """Get conditions created by a specific tab."""
        return [c for c in self.conditions if c.source_tab == tab]
    
    def get_condition_count(self) -> int:
        """Get total number of active conditions."""
        return len(self.conditions)
    
    def to_dict(self) -> Dict:
        """Serialize to JSON-compatible dict."""
        data = asdict(self)
        # Convert conditions to dicts
        data["conditions"] = [c.to_dict() for c in self.conditions]
        data["condition_groups"] = [
            {"conditions": [c.to_dict() for c in g.conditions], "logic": g.logic}
            for g in self.condition_groups
        ]
        return data
    
    @classmethod
    def from_dict(cls, data: Dict) -> "ScreenerState":
        """Deserialize from dict."""
        conditions = [Condition.from_dict(c) for c in data.pop("conditions", [])]
        groups = [
            ConditionGroup(
                conditions=[Condition.from_dict(c) for c in g["conditions"]],
                logic=g.get("logic", "AND")
            )
            for g in data.pop("condition_groups", [])
        ]
        state = cls(**data)
        state.conditions = conditions
        state.condition_groups = groups
        return state
    
    def to_json(self) -> str:
        """Serialize to JSON string."""
        return json.dumps(self.to_dict(), indent=2)
    
    @classmethod
    def from_json(cls, json_str: str) -> "ScreenerState":
        """Deserialize from JSON string."""
        return cls.from_dict(json.loads(json_str))
    
    def get_cache_key(self) -> str:
        """Generate cache key for this state."""
        # Hash the essential screening parameters
        key_data = {
            "universe": self.universe,
            "time_window": self.time_window,
            "conditions": [c.to_dict() for c in self.conditions],
            "formula": self.filter_formula,
        }
        return hashlib.md5(json.dumps(key_data, sort_keys=True).encode()).hexdigest()


# =============================================================================
# PRESET CONDITIONS (Common screening patterns)
# =============================================================================

def create_rsi_oversold_condition(threshold: float = 30, period: int = 14) -> Condition:
    """RSI below threshold (oversold)."""
    return Condition(
        field=f"RSI_{period}",
        operator="lt",
        value=threshold,
        condition_type="indicator",
        source_tab="trend",
        label=f"RSI({period}) < {threshold}"
    )

def create_rsi_overbought_condition(threshold: float = 70, period: int = 14) -> Condition:
    """RSI above threshold (overbought)."""
    return Condition(
        field=f"RSI_{period}",
        operator="gt",
        value=threshold,
        condition_type="indicator",
        source_tab="trend",
        label=f"RSI({period}) > {threshold}"
    )

def create_price_above_ma_condition(ma_period: int = 50) -> Condition:
    """Price above moving average."""
    return Condition(
        field=f"price_vs_SMA_{ma_period}",
        operator="gt",
        value=0,
        condition_type="indicator",
        source_tab="trend",
        label=f"Price > SMA({ma_period})"
    )

def create_volume_filter_condition(min_volume: float) -> Condition:
    """Minimum volume filter."""
    return Condition(
        field="avg_volume_20d",
        operator="gte",
        value=min_volume,
        condition_type="volume",
        source_tab="liquidity",
        label=f"Volume >= {min_volume:,.0f}"
    )

def create_pe_ratio_condition(max_pe: float = 25) -> Condition:
    """PE ratio filter."""
    return Condition(
        field="PE_Ratio",
        operator="lte",
        value=max_pe,
        condition_type="fundamental",
        source_tab="company",
        label=f"P/E <= {max_pe}"
    )

def create_volatility_condition(min_atr_pct: float, max_atr_pct: float) -> Condition:
    """ATR percentage range."""
    return Condition(
        field="atr_pct",
        operator="between",
        value=(min_atr_pct, max_atr_pct),
        condition_type="indicator",
        source_tab="volatility",
        label=f"ATR% {min_atr_pct}-{max_atr_pct}"
    )


# =============================================================================
# HELPER FUNCTIONS
# =============================================================================

def parse_time_window(window: str) -> int:
    """Convert time window string to days."""
    mappings = {
        "20D": 20, "60D": 60, "120D": 120, "252D": 252,
        "1M": 20, "3M": 60, "6M": 126, "1Y": 252, "2Y": 504, "5Y": 1260
    }
    return mappings.get(window.upper(), 60)


def get_universe_asset_type(universe: str) -> str:
    """Map universe key to asset type."""
    mappings = {
        "INDIA": "EQUITY",
        "US": "EQUITY",
        "CRYPTO": "CRYPTO",
        "FX": "FX",
        "INDEX": "INDEX",
        "ETF": "ETF"
    }
    return mappings.get(universe.upper(), "EQUITY")


def get_disabled_features(asset_type: str) -> Dict[str, bool]:
    """Get feature availability for asset type."""
    features = {
        "fundamentals": True,
        "technicals": True,
        "volume_indicators": True,
        "patterns": True,
        "trading_actions": True,
    }
    
    if asset_type == "CRYPTO":
        features["fundamentals"] = False
    elif asset_type == "FX":
        features["fundamentals"] = False
        features["volume_indicators"] = False
    elif asset_type == "INDEX":
        features["fundamentals"] = False
        features["trading_actions"] = False
    elif asset_type == "ETF":
        features["fundamentals"] = False
    
    return features
