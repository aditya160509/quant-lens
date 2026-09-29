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
        
        # Determine universe key from asset type or use default
        u_key = state.universe
        
        # Try to get market state which has richer data than sample generator
        market_state = await service.get_market_state(u_key)
        
        if market_state:
            # Construct rich row data for each ticker
            symbols_data = []
            for ticker in market_state.tickers:
                try:
                    # Get basic info
                    current_price = market_state.prices[ticker].iloc[-1] if ticker in market_state.prices else 0
                    current_vol = market_state.volumes[ticker].iloc[-1] if ticker in market_state.volumes else 0
                    
                    symbol_data = {
                        "ticker": ticker,
                        "universe": u_key,
                        "asset_type": get_universe_asset_type(u_key),
                        "price": current_price,
                        "close": current_price,
                        "CLOSE": current_price,
                        "volume": current_vol,
                        "VOLUME": current_vol,
                        "change_1d": ((market_state.prices[ticker].iloc[-1] / market_state.prices[ticker].iloc[-2]) - 1) * 100 if ticker in market_state.prices and len(market_state.prices) > 1 else 0,
                        "dollar_volume": (current_price * current_vol),
                        "sector": "Equity" if u_key in ["INDIA", "US"] else u_key.title()
                    }
                    
                    # Real calculations using ScreenerMathEngine
                    from app.services.screener_quant360 import ScreenerMathEngine as math
                    
                    # Extract series and align
                    prices = market_state.prices[ticker].dropna()
                    if len(prices) < 20: continue
                    
                    common_idx = prices.index
                    volumes = market_state.volumes[ticker].reindex(common_idx).fillna(0)
                    highs = market_state.high[ticker].reindex(common_idx).fillna(method='ffill')
                    lows = market_state.low[ticker].reindex(common_idx).fillna(method='ffill')
                    opens = market_state.open_prices[ticker].reindex(common_idx).fillna(method='ffill')
                    
                    # Compute indicators using requested window
                    w = state.lookback_days
                    rets = math.compute_returns(prices)
                    dollar_vol = math.compute_dollar_volume(prices, volumes)
                    atr = math.compute_atr(highs, lows, prices, window=min(w, 14))
                    atr_pct_series = math.compute_atr_percent(atr, prices)
                    
                    realized_vol = math.compute_realized_vol(rets, window=min(w, 20))
                    
                    symbol_data.update({
                        "rsi": math.compute_rsi(prices, min(w, 14)),
                        "RSI_14": math.compute_rsi(prices, 14),
                        "realized_vol": realized_vol,
                        "volatility": realized_vol,
                        "VOLATILITY": realized_vol,
                        "atr_pct": float(atr_pct_series.iloc[-1]) if not atr_pct_series.empty else 0,
                        "ma20_dist": math.compute_ma_distance(prices, 20),
                        "ma50_dist": math.compute_ma_distance(prices, 50),
                        "momentum_current": math.compute_momentum(prices, w) * 100,
                        "momentum_20d": math.compute_momentum(prices, 20) * 100,
                        "trend_persistence": math.compute_trend_persistence(rets, "up", w),
                        "liq_persistence": math.compute_liquidity_persistence(dollar_vol, 1),
                        "gap_freq": math.compute_gap_frequency(math.compute_gap_percent(math.compute_gaps(opens, prices), prices), 2.0, w),
                        "illiq_accel": math.compute_illiq_acceleration(math.compute_amihud_illiquidity(rets, dollar_vol, min(w, 20)), min(w, 20)),
                        "sparkline": prices.tail(20).tolist()
                    })
                    
                    symbols_data.append(symbol_data)
                except Exception as e:
                    logger.warning(f"Error hydrating {ticker}: {e}")
                    continue
            return symbols_data
        
        # Fallback to sample generator if MarketState fails
        df = service._generate_sample_data(state.universe)
        return df.to_dict('records')
    
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

    # Keyword aliases to internal field names
    METRIC_ALIASES = {
        "RSI": "RSI_14",
        "PRICE": "price",
        "CLOSE": "price",
        "VOL": "dollar_volume",
        "VOLUME": "dollar_volume",
        "CHANGE": "change_1d",
        "MOMENTUM": "momentum_20d",
        "VOLATILITY": "realized_vol",
        "RV": "realized_vol",
        "ATR": "atr_pct",
        "LIQUIDITY": "liq_persistence"
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
                    field = parts[0].strip().upper()
                    # Resolve aliases
                    internal_field = self.METRIC_ALIASES.get(field, field.lower())
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
                        field=internal_field,
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
