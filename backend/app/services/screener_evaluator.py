"""
Screener Evaluation Engine
==========================
The unified evaluation endpoint that takes ScreenerState and returns matching symbols.
All asset types flow through this single pipeline.
"""

from typing import List, Dict, Any, Optional
from dataclasses import dataclass
import logging
import time

from app.services.screener_state import (
    ScreenerState, Condition, ConditionGroup, 
    get_universe_asset_type, get_disabled_features
)

logger = logging.getLogger(__name__)


# =============================================================================
# INDICATOR REGISTRY (Task 5.1)
# =============================================================================

@dataclass
class IndicatorDefinition:
    """Metadata for a registered indicator."""
    id: str  # e.g., "RSI_14"
    name: str  # e.g., "Relative Strength Index"
    category: str  # Trend/Momentum/Volatility/Volume
    parameters: Dict[str, Any]  # e.g., {"period": 14}
    output_fields: List[str]  # Fields this indicator produces
    description: str = ""
    requires_volume: bool = False


# The indicator registry - adding new indicators only requires adding here
INDICATOR_REGISTRY: Dict[str, IndicatorDefinition] = {
    # Trend Indicators
    "SMA_20": IndicatorDefinition("SMA_20", "Simple MA 20", "Trend", {"period": 20}, ["SMA_20", "price_vs_SMA_20"]),
    "SMA_50": IndicatorDefinition("SMA_50", "Simple MA 50", "Trend", {"period": 50}, ["SMA_50", "price_vs_SMA_50"]),
    "SMA_200": IndicatorDefinition("SMA_200", "Simple MA 200", "Trend", {"period": 200}, ["SMA_200", "price_vs_SMA_200"]),
    "EMA_12": IndicatorDefinition("EMA_12", "Exponential MA 12", "Trend", {"period": 12}, ["EMA_12"]),
    "EMA_26": IndicatorDefinition("EMA_26", "Exponential MA 26", "Trend", {"period": 26}, ["EMA_26"]),
    
    # Momentum Indicators
    "RSI_14": IndicatorDefinition("RSI_14", "RSI 14", "Momentum", {"period": 14}, ["RSI_14"]),
    "RSI_7": IndicatorDefinition("RSI_7", "RSI 7", "Momentum", {"period": 7}, ["RSI_7"]),
    "RSI_21": IndicatorDefinition("RSI_21", "RSI 21", "Momentum", {"period": 21}, ["RSI_21"]),
    "STOCH_K": IndicatorDefinition("STOCH_K", "Stochastic %K", "Momentum", {"period": 14}, ["STOCH_K", "STOCH_D"]),
    "CCI_20": IndicatorDefinition("CCI_20", "CCI 20", "Momentum", {"period": 20}, ["CCI_20"]),
    "ROC_10": IndicatorDefinition("ROC_10", "Rate of Change 10", "Momentum", {"period": 10}, ["ROC_10"]),
    "ROC_20": IndicatorDefinition("ROC_20", "Rate of Change 20", "Momentum", {"period": 20}, ["ROC_20"]),
    
    # Volatility Indicators
    "ATR_14": IndicatorDefinition("ATR_14", "ATR 14", "Volatility", {"period": 14}, ["ATR_14", "atr_pct"]),
    "BB_20": IndicatorDefinition("BB_20", "Bollinger Bands 20", "Volatility", {"period": 20, "std": 2}, ["BB_upper", "BB_lower", "BB_width"]),
    "REALIZED_VOL": IndicatorDefinition("REALIZED_VOL", "Realized Vol", "Volatility", {"period": 20}, ["realized_vol"]),
    
    # Volume Indicators
    "OBV": IndicatorDefinition("OBV", "On Balance Volume", "Volume", {}, ["OBV"], requires_volume=True),
    "MFI_14": IndicatorDefinition("MFI_14", "Money Flow Index", "Volume", {"period": 14}, ["MFI_14"], requires_volume=True),
    "VWAP": IndicatorDefinition("VWAP", "VWAP", "Volume", {}, ["VWAP"], requires_volume=True),
    "VOL_SMA_20": IndicatorDefinition("VOL_SMA_20", "Volume SMA 20", "Volume", {"period": 20}, ["VOL_SMA_20", "vol_ratio"], requires_volume=True),
    
    # Trend Strength
    "ADX_14": IndicatorDefinition("ADX_14", "ADX 14", "Trend", {"period": 14}, ["ADX_14", "DI_plus", "DI_minus"]),
    "AROON_25": IndicatorDefinition("AROON_25", "Aroon 25", "Trend", {"period": 25}, ["AROON_up", "AROON_down"]),
    
    # MACD
    "MACD": IndicatorDefinition("MACD", "MACD", "Momentum", {"fast": 12, "slow": 26, "signal": 9}, ["MACD_line", "MACD_signal", "MACD_hist"]),
}


def get_available_indicators(asset_type: str) -> List[IndicatorDefinition]:
    """Get indicators available for an asset type."""
    features = get_disabled_features(asset_type)
    indicators = []
    
    for indicator in INDICATOR_REGISTRY.values():
        # Skip volume indicators if volume not available
        if indicator.requires_volume and not features["volume_indicators"]:
            continue
        indicators.append(indicator)
    
    return indicators


# =============================================================================
# EVALUATION ENGINE (Task 2.2)
# =============================================================================

@dataclass
class EvaluationResult:
    """Result from evaluating a screener state."""
    symbols: List[Dict[str, Any]]  # Matching symbols with computed values
    total_scanned: int
    total_matched: int
    execution_time_ms: float
    cache_hit: bool = False
    errors: List[str] = None
    
    def to_dict(self) -> Dict:
        return {
            "symbols": self.symbols,
            "meta": {
                "total_scanned": self.total_scanned,
                "total_matched": self.total_matched,
                "execution_time_ms": self.execution_time_ms,
                "cache_hit": self.cache_hit,
            },
            "errors": self.errors or []
        }


class ScreenerEvaluator:
    """
    The unified evaluation engine.
    Takes ScreenerState, returns matching symbols.
    All asset types flow through this single pipeline.
    """
    
    def __init__(self):
        self._cache: Dict[str, EvaluationResult] = {}
        self._cache_ttl = 900  # 15 minutes
        self._cache_timestamps: Dict[str, float] = {}
    
    async def evaluate(self, state: ScreenerState) -> EvaluationResult:
        """
        Main evaluation method.
        Takes ScreenerState and returns matching symbols.
        """
        start_time = time.time()
        errors = []
        
        # Check cache
        cache_key = state.get_cache_key()
        if cache_key in self._cache:
            cache_time = self._cache_timestamps.get(cache_key, 0)
            if time.time() - cache_time < self._cache_ttl:
                result = self._cache[cache_key]
                result.cache_hit = True
                return result
        
        try:
            # 1. Get symbols from universe
            symbols_data = await self._load_universe_data(state)
            total_scanned = len(symbols_data)
            
            # 2. Apply all conditions
            matching_symbols = []
            for symbol_data in symbols_data:
                if self._evaluate_symbol(symbol_data, state):
                    matching_symbols.append(symbol_data)
            
            # 3. Score symbols if weights provided
            if any(c.weight != 1.0 for c in state.conditions):
                matching_symbols = self._score_symbols(matching_symbols, state)
            
            # 4. Sort results
            matching_symbols = self._sort_results(matching_symbols, state)
            
            # 5. Limit results
            if state.max_results:
                matching_symbols = matching_symbols[:state.max_results]
            
            execution_time = (time.time() - start_time) * 1000
            
            result = EvaluationResult(
                symbols=matching_symbols,
                total_scanned=total_scanned,
                total_matched=len(matching_symbols),
                execution_time_ms=execution_time,
                cache_hit=False,
                errors=errors if errors else None
            )
            
            # Cache the result
            self._cache[cache_key] = result
            self._cache_timestamps[cache_key] = time.time()
            
            return result
            
        except Exception as e:
            logger.error(f"Evaluation error: {e}")
            execution_time = (time.time() - start_time) * 1000
            return EvaluationResult(
                symbols=[],
                total_scanned=0,
                total_matched=0,
                execution_time_ms=execution_time,
                errors=[str(e)]
            )
    
    async def _load_universe_data(self, state: ScreenerState) -> List[Dict]:
        """Load precomputed data for all symbols in universe."""
        from app.services.screener_quant360 import get_screener_service
        
        service = get_screener_service()
        
        # Get sample data based on universe
        df = service._generate_sample_data(state.universe)
        
        # Convert to list of dicts
        symbols_data = df.to_dict('records')
        
        return symbols_data
    
    def _evaluate_symbol(self, symbol_data: Dict, state: ScreenerState) -> bool:
        """Evaluate all conditions against a single symbol."""
        # Evaluate individual conditions with AND logic
        for condition in state.conditions:
            if not condition.evaluate(symbol_data):
                return False
        
        # Evaluate condition groups
        for group in state.condition_groups:
            if not group.evaluate(symbol_data):
                return False
        
        return True
    
    def _score_symbols(self, symbols: List[Dict], state: ScreenerState) -> List[Dict]:
        """Calculate scores for symbols based on condition weights."""
        for symbol in symbols:
            score = 0
            total_weight = 0
            
            for condition in state.conditions:
                if condition.weight != 1.0:
                    # Get normalized value for this field
                    val = symbol.get(condition.field, 0)
                    if val is not None:
                        # Simple scoring: higher values = higher score
                        # This can be made more sophisticated
                        score += val * condition.weight
                        total_weight += abs(condition.weight)
            
            symbol["score"] = score / max(total_weight, 1) if total_weight else 0
        
        return symbols
    
    def _sort_results(self, symbols: List[Dict], state: ScreenerState) -> List[Dict]:
        """Sort results according to state configuration."""
        sort_field = state.sort_by
        reverse = state.sort_desc
        
        # Handle missing values
        def sort_key(s):
            val = s.get(sort_field)
            if val is None:
                return float('-inf') if reverse else float('inf')
            return val
        
        return sorted(symbols, key=sort_key, reverse=reverse)
    
    def clear_cache(self):
        """Clear the evaluation cache."""
        self._cache.clear()
        self._cache_timestamps.clear()


# Singleton instance
_evaluator: Optional[ScreenerEvaluator] = None

def get_evaluator() -> ScreenerEvaluator:
    """Get or create the screener evaluator singleton."""
    global _evaluator
    if _evaluator is None:
        _evaluator = ScreenerEvaluator()
    return _evaluator


# =============================================================================
# FORMULA PARSER (Task 7.1) - Basic Implementation
# =============================================================================

class FormulaParser:
    """Parse formula strings into Condition objects."""
    
    # Supported operators
    OPERATORS = {
        '<': 'lt', '<=': 'lte', '>': 'gt', '>=': 'gte',
        '=': 'eq', '==': 'eq', '!=': 'neq', '<>': 'neq'
    }
    
    def parse(self, formula: str) -> List[Condition]:
        """
        Parse formula string into conditions.
        Example: "RSI_14 < 30 AND close > SMA_50"
        """
        if not formula or not formula.strip():
            return []
        
        conditions = []
        
        # Split by AND (simple implementation)
        parts = formula.upper().replace(" AND ", "\n").split("\n")
        
        for part in parts:
            part = part.strip()
            if not part:
                continue
            
            condition = self._parse_single_condition(part)
            if condition:
                conditions.append(condition)
        
        return conditions
    
    def _parse_single_condition(self, expr: str) -> Optional[Condition]:
        """Parse a single condition expression."""
        import re
        
        # Match pattern: FIELD OPERATOR VALUE
        for op_str, op_code in sorted(self.OPERATORS.items(), key=lambda x: -len(x[0])):
            if op_str in expr:
                parts = expr.split(op_str)
                if len(parts) == 2:
                    field = parts[0].strip()
                    value_str = parts[1].strip()
                    
                    # Parse value
                    try:
                        if value_str.replace('.', '').replace('-', '').isdigit():
                            value = float(value_str)
                        elif value_str.lower() in ('true', 'false'):
                            value = value_str.lower() == 'true'
                        else:
                            value = value_str
                    except:
                        value = value_str
                    
                    return Condition(
                        field=field,
                        operator=op_code,
                        value=value,
                        condition_type="indicator",
                        source_tab="formula",
                        label=expr
                    )
        
        return None
    
    def validate(self, formula: str) -> tuple[bool, str]:
        """Validate a formula and return (is_valid, error_message)."""
        try:
            conditions = self.parse(formula)
            if not conditions:
                return False, "No valid conditions found in formula"
            return True, ""
        except Exception as e:
            return False, str(e)


# Singleton parser
_parser: Optional[FormulaParser] = None

def get_formula_parser() -> FormulaParser:
    global _parser
    if _parser is None:
        _parser = FormulaParser()
    return _parser
