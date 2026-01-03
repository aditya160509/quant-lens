"""
Strategy Research Lab - Backend Service
Features 61-64: Backtesting Engine, Strategy Builder, Walk Forward, Parameter Optimization

Now uses robust_data_fetcher for multi-source data with caching and rate limiting.
"""
import numpy as np
import pandas as pd
from datetime import datetime, timedelta
from typing import List, Dict, Any, Optional, Tuple
import logging
from scipy import stats
import math

# Use robust data fetcher - handles rate limiting, caching, multi-source fallback
from app.services.robust_data_fetcher import (
    get_price_data as rdf_get_price,
    get_batch_data as rdf_get_batch
)

logger = logging.getLogger(__name__)

# =============================================================================
# INDICATOR LIBRARY - 20+ Most Important Technical Indicators
# =============================================================================

class IndicatorLibrary:
    """Pre-built indicator library with commonly used technical indicators."""
    
    @staticmethod
    def sma(data: pd.Series, period: int = 20) -> pd.Series:
        """Simple Moving Average"""
        return data.rolling(window=period).mean()
    
    @staticmethod
    def ema(data: pd.Series, period: int = 20) -> pd.Series:
        """Exponential Moving Average"""
        return data.ewm(span=period, adjust=False).mean()
    
    @staticmethod
    def rsi(data: pd.Series, period: int = 14) -> pd.Series:
        """Relative Strength Index"""
        delta = data.diff()
        gain = (delta.where(delta > 0, 0)).rolling(window=period).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(window=period).mean()
        rs = gain / loss
        return 100 - (100 / (1 + rs))
    
    @staticmethod
    def macd(data: pd.Series, fast: int = 12, slow: int = 26, signal: int = 9) -> Dict[str, pd.Series]:
        """MACD - Moving Average Convergence Divergence"""
        ema_fast = data.ewm(span=fast, adjust=False).mean()
        ema_slow = data.ewm(span=slow, adjust=False).mean()
        macd_line = ema_fast - ema_slow
        signal_line = macd_line.ewm(span=signal, adjust=False).mean()
        histogram = macd_line - signal_line
        return {"macd": macd_line, "signal": signal_line, "histogram": histogram}
    
    @staticmethod
    def bollinger_bands(data: pd.Series, period: int = 20, std_dev: float = 2.0) -> Dict[str, pd.Series]:
        """Bollinger Bands"""
        sma = data.rolling(window=period).mean()
        std = data.rolling(window=period).std()
        return {
            "upper": sma + (std * std_dev),
            "middle": sma,
            "lower": sma - (std * std_dev),
            "bandwidth": ((sma + std * std_dev) - (sma - std * std_dev)) / sma * 100
        }
    
    @staticmethod
    def atr(high: pd.Series, low: pd.Series, close: pd.Series, period: int = 14) -> pd.Series:
        """Average True Range"""
        tr1 = high - low
        tr2 = abs(high - close.shift(1))
        tr3 = abs(low - close.shift(1))
        tr = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)
        return tr.rolling(window=period).mean()
    
    @staticmethod
    def stochastic(high: pd.Series, low: pd.Series, close: pd.Series, 
                   k_period: int = 14, d_period: int = 3) -> Dict[str, pd.Series]:
        """Stochastic Oscillator"""
        lowest_low = low.rolling(window=k_period).min()
        highest_high = high.rolling(window=k_period).max()
        k = 100 * (close - lowest_low) / (highest_high - lowest_low)
        d = k.rolling(window=d_period).mean()
        return {"k": k, "d": d}
    
    @staticmethod
    def adx(high: pd.Series, low: pd.Series, close: pd.Series, period: int = 14) -> pd.Series:
        """Average Directional Index"""
        plus_dm = high.diff()
        minus_dm = low.diff()
        plus_dm[plus_dm < 0] = 0
        minus_dm[minus_dm > 0] = 0
        tr = IndicatorLibrary.atr(high, low, close, 1) * period
        plus_di = 100 * (plus_dm.rolling(period).sum() / tr)
        minus_di = 100 * (abs(minus_dm).rolling(period).sum() / tr)
        dx = 100 * abs(plus_di - minus_di) / (plus_di + minus_di)
        return dx.rolling(period).mean()
    
    @staticmethod
    def cci(high: pd.Series, low: pd.Series, close: pd.Series, period: int = 20) -> pd.Series:
        """Commodity Channel Index"""
        tp = (high + low + close) / 3
        sma = tp.rolling(window=period).mean()
        mad = tp.rolling(window=period).apply(lambda x: np.abs(x - x.mean()).mean())
        return (tp - sma) / (0.015 * mad)
    
    @staticmethod
    def williams_r(high: pd.Series, low: pd.Series, close: pd.Series, period: int = 14) -> pd.Series:
        """Williams %R"""
        highest_high = high.rolling(window=period).max()
        lowest_low = low.rolling(window=period).min()
        return -100 * (highest_high - close) / (highest_high - lowest_low)
    
    @staticmethod
    def obv(close: pd.Series, volume: pd.Series) -> pd.Series:
        """On-Balance Volume"""
        direction = np.sign(close.diff())
        direction.iloc[0] = 0
        return (volume * direction).cumsum()
    
    @staticmethod
    def vwap(high: pd.Series, low: pd.Series, close: pd.Series, volume: pd.Series) -> pd.Series:
        """Volume Weighted Average Price"""
        tp = (high + low + close) / 3
        return (tp * volume).cumsum() / volume.cumsum()
    
    @staticmethod
    def momentum(data: pd.Series, period: int = 10) -> pd.Series:
        """Price Momentum"""
        return data - data.shift(period)
    
    @staticmethod
    def roc(data: pd.Series, period: int = 10) -> pd.Series:
        """Rate of Change"""
        return ((data - data.shift(period)) / data.shift(period)) * 100
    
    @staticmethod
    def pivot_points(high: pd.Series, low: pd.Series, close: pd.Series) -> Dict[str, pd.Series]:
        """Pivot Points"""
        pp = (high + low + close) / 3
        r1 = 2 * pp - low
        s1 = 2 * pp - high
        r2 = pp + (high - low)
        s2 = pp - (high - low)
        return {"pivot": pp, "r1": r1, "r2": r2, "s1": s1, "s2": s2}
    
    @staticmethod
    def donchian_channel(high: pd.Series, low: pd.Series, period: int = 20) -> Dict[str, pd.Series]:
        """Donchian Channel"""
        upper = high.rolling(window=period).max()
        lower = low.rolling(window=period).min()
        middle = (upper + lower) / 2
        return {"upper": upper, "middle": middle, "lower": lower}
    
    @staticmethod
    def keltner_channel(high: pd.Series, low: pd.Series, close: pd.Series, 
                        ema_period: int = 20, atr_period: int = 10, multiplier: float = 2.0) -> Dict[str, pd.Series]:
        """Keltner Channel"""
        ema = close.ewm(span=ema_period, adjust=False).mean()
        atr = IndicatorLibrary.atr(high, low, close, atr_period)
        return {
            "upper": ema + (multiplier * atr),
            "middle": ema,
            "lower": ema - (multiplier * atr)
        }
    
    @staticmethod
    def ichimoku(high: pd.Series, low: pd.Series, close: pd.Series) -> Dict[str, pd.Series]:
        """Ichimoku Cloud"""
        tenkan = (high.rolling(9).max() + low.rolling(9).min()) / 2
        kijun = (high.rolling(26).max() + low.rolling(26).min()) / 2
        senkou_a = ((tenkan + kijun) / 2).shift(26)
        senkou_b = ((high.rolling(52).max() + low.rolling(52).min()) / 2).shift(26)
        chikou = close.shift(-26)
        return {
            "tenkan": tenkan, "kijun": kijun,
            "senkou_a": senkou_a, "senkou_b": senkou_b, "chikou": chikou
        }
    
    @staticmethod
    def supertrend(high: pd.Series, low: pd.Series, close: pd.Series, 
                   period: int = 10, multiplier: float = 3.0) -> Dict[str, pd.Series]:
        """SuperTrend Indicator"""
        atr = IndicatorLibrary.atr(high, low, close, period)
        hl2 = (high + low) / 2
        upper_band = hl2 + (multiplier * atr)
        lower_band = hl2 - (multiplier * atr)
        
        supertrend = pd.Series(index=close.index, dtype=float)
        direction = pd.Series(index=close.index, dtype=float)
        
        for i in range(period, len(close)):
            if close.iloc[i] > upper_band.iloc[i-1]:
                supertrend.iloc[i] = lower_band.iloc[i]
                direction.iloc[i] = 1
            elif close.iloc[i] < lower_band.iloc[i-1]:
                supertrend.iloc[i] = upper_band.iloc[i]
                direction.iloc[i] = -1
            else:
                supertrend.iloc[i] = supertrend.iloc[i-1] if not pd.isna(supertrend.iloc[i-1]) else lower_band.iloc[i]
                direction.iloc[i] = direction.iloc[i-1] if not pd.isna(direction.iloc[i-1]) else 1
        
        return {"supertrend": supertrend, "direction": direction}


# Available indicator definitions for frontend
INDICATOR_DEFINITIONS = {
    "sma": {"name": "Simple Moving Average", "params": {"period": {"default": 20, "min": 2, "max": 200}}, "type": "overlay"},
    "ema": {"name": "Exponential Moving Average", "params": {"period": {"default": 20, "min": 2, "max": 200}}, "type": "overlay"},
    "rsi": {"name": "Relative Strength Index", "params": {"period": {"default": 14, "min": 2, "max": 50}}, "type": "oscillator"},
    "macd": {"name": "MACD", "params": {"fast": {"default": 12}, "slow": {"default": 26}, "signal": {"default": 9}}, "type": "oscillator"},
    "bollinger": {"name": "Bollinger Bands", "params": {"period": {"default": 20}, "std_dev": {"default": 2.0}}, "type": "overlay"},
    "atr": {"name": "Average True Range", "params": {"period": {"default": 14, "min": 1, "max": 50}}, "type": "indicator"},
    "stochastic": {"name": "Stochastic Oscillator", "params": {"k_period": {"default": 14}, "d_period": {"default": 3}}, "type": "oscillator"},
    "adx": {"name": "Average Directional Index", "params": {"period": {"default": 14}}, "type": "indicator"},
    "cci": {"name": "Commodity Channel Index", "params": {"period": {"default": 20}}, "type": "oscillator"},
    "williams_r": {"name": "Williams %R", "params": {"period": {"default": 14}}, "type": "oscillator"},
    "obv": {"name": "On-Balance Volume", "params": {}, "type": "volume"},
    "momentum": {"name": "Momentum", "params": {"period": {"default": 10}}, "type": "oscillator"},
    "roc": {"name": "Rate of Change", "params": {"period": {"default": 10}}, "type": "oscillator"},
    "donchian": {"name": "Donchian Channel", "params": {"period": {"default": 20}}, "type": "overlay"},
    "keltner": {"name": "Keltner Channel", "params": {"ema_period": {"default": 20}, "atr_period": {"default": 10}}, "type": "overlay"},
    "supertrend": {"name": "SuperTrend", "params": {"period": {"default": 10}, "multiplier": {"default": 3.0}}, "type": "overlay"}
}


# =============================================================================
# STRATEGY TEMPLATES - Pre-built Commonly Used Strategies
# =============================================================================

STRATEGY_TEMPLATES = {
    "golden_cross": {
        "name": "Golden Cross / Death Cross",
        "description": "Buy when 50 SMA crosses above 200 SMA, sell when crosses below",
        "indicators": [
            {"id": "sma_fast", "type": "sma", "params": {"period": 50}},
            {"id": "sma_slow", "type": "sma", "params": {"period": 200}}
        ],
        "entry_rules": {"long": "sma_fast > sma_slow AND sma_fast[1] <= sma_slow[1]"},
        "exit_rules": {"long": "sma_fast < sma_slow"},
        "category": "trend"
    },
    "rsi_oversold": {
        "name": "RSI Mean Reversion",
        "description": "Buy when RSI drops below 30, sell when above 70",
        "indicators": [{"id": "rsi", "type": "rsi", "params": {"period": 14}}],
        "entry_rules": {"long": "rsi < 30"},
        "exit_rules": {"long": "rsi > 70"},
        "category": "mean_reversion"
    },
    "macd_crossover": {
        "name": "MACD Signal Crossover",
        "description": "Buy when MACD crosses above signal line, sell when crosses below",
        "indicators": [{"id": "macd", "type": "macd", "params": {"fast": 12, "slow": 26, "signal": 9}}],
        "entry_rules": {"long": "macd.macd > macd.signal AND macd.macd[1] <= macd.signal[1]"},
        "exit_rules": {"long": "macd.macd < macd.signal"},
        "category": "momentum"
    },
    "bollinger_breakout": {
        "name": "Bollinger Band Breakout",
        "description": "Buy when price breaks above upper band, sell when drops below lower",
        "indicators": [{"id": "bb", "type": "bollinger", "params": {"period": 20, "std_dev": 2.0}}],
        "entry_rules": {"long": "close > bb.upper"},
        "exit_rules": {"long": "close < bb.lower"},
        "category": "volatility"
    },
    "supertrend_follow": {
        "name": "SuperTrend Trend Following",
        "description": "Follow SuperTrend direction for entries and exits",
        "indicators": [{"id": "st", "type": "supertrend", "params": {"period": 10, "multiplier": 3.0}}],
        "entry_rules": {"long": "st.direction == 1 AND st.direction[1] == -1"},
        "exit_rules": {"long": "st.direction == -1"},
        "category": "trend"
    },
    "dual_momentum": {
        "name": "Dual Momentum",
        "description": "Enter when both short and long term momentum are positive",
        "indicators": [
            {"id": "mom_short", "type": "roc", "params": {"period": 21}},
            {"id": "mom_long", "type": "roc", "params": {"period": 126}}
        ],
        "entry_rules": {"long": "mom_short > 0 AND mom_long > 0"},
        "exit_rules": {"long": "mom_short < 0 OR mom_long < 0"},
        "category": "momentum"
    },
    "donchian_turtle": {
        "name": "Turtle Trading (Donchian)",
        "description": "Classic turtle trading system using Donchian channels",
        "indicators": [{"id": "dc", "type": "donchian", "params": {"period": 20}}],
        "entry_rules": {"long": "close > dc.upper[1]"},
        "exit_rules": {"long": "close < dc.lower[1]"},
        "category": "trend"
    },
    "mean_reversion_bb": {
        "name": "Bollinger Mean Reversion",
        "description": "Buy at lower band, sell at middle/upper band",
        "indicators": [{"id": "bb", "type": "bollinger", "params": {"period": 20, "std_dev": 2.0}}],
        "entry_rules": {"long": "close < bb.lower"},
        "exit_rules": {"long": "close > bb.middle"},
        "category": "mean_reversion"
    }
}


# =============================================================================
# FEATURE 62: STRATEGY BUILDER
# =============================================================================

def get_indicators() -> Dict[str, Any]:
    """Return available indicators with their definitions."""
    return {
        "indicators": INDICATOR_DEFINITIONS,
        "total": len(INDICATOR_DEFINITIONS)
    }


def get_strategy_templates() -> Dict[str, Any]:
    """Return pre-built strategy templates."""
    return {
        "templates": STRATEGY_TEMPLATES,
        "total": len(STRATEGY_TEMPLATES)
    }


def build_strategy(strategy_config: Dict[str, Any]) -> Dict[str, Any]:
    """
    Build and validate a strategy definition.
    
    strategy_config should contain:
    - name: str
    - universe: List[str] - ticker symbols
    - indicators: List[Dict] - indicator configurations
    - entry_rules: Dict - long/short entry conditions
    - exit_rules: Dict - exit conditions
    - position_sizing: Dict - sizing method and params
    - risk_management: Dict - stops, targets
    """
    try:
        # Validate required fields
        required = ["name", "universe", "indicators", "entry_rules", "exit_rules"]
        for field in required:
            if field not in strategy_config:
                return {"error": f"Missing required field: {field}"}
        
        # Validate universe
        universe = strategy_config.get("universe", [])
        if not universe or len(universe) == 0:
            return {"error": "Universe must contain at least one symbol"}
        
        # Validate indicators
        indicators = strategy_config.get("indicators", [])
        for ind in indicators:
            if ind.get("type") not in INDICATOR_DEFINITIONS:
                return {"error": f"Unknown indicator type: {ind.get('type')}"}
        
        # Calculate complexity and warm-up period
        max_period = 0
        for ind in indicators:
            params = ind.get("params", {})
            for k, v in params.items():
                if "period" in k.lower() and isinstance(v, (int, float)):
                    max_period = max(max_period, int(v))
        
        warmup_period = max(max_period + 50, 100)  # Buffer for calculations
        
        # Build strategy object
        strategy = {
            "id": f"strategy_{datetime.now().strftime('%Y%m%d_%H%M%S')}",
            "name": strategy_config["name"],
            "description": strategy_config.get("description", ""),
            "universe": universe,
            "indicators": indicators,
            "entry_rules": strategy_config["entry_rules"],
            "exit_rules": strategy_config["exit_rules"],
            "position_sizing": strategy_config.get("position_sizing", {"method": "equal_weight"}),
            "risk_management": strategy_config.get("risk_management", {
                "stop_loss": 0.02,
                "take_profit": 0.06,
                "max_positions": 10
            }),
            "warmup_period": warmup_period,
            "complexity": "simple" if len(indicators) <= 2 else "moderate" if len(indicators) <= 5 else "complex",
            "created_at": datetime.now().isoformat(),
            "valid": True
        }
        
        return {"strategy": strategy}
        
    except Exception as e:
        logger.error(f"Strategy build error: {e}")
        return {"error": str(e)}


# =============================================================================
# FEATURE 61: BACKTESTING ENGINE - Using robust_data_fetcher
# =============================================================================

def _fetch_price_data(symbols: List[str], start_date: str, end_date: str) -> pd.DataFrame:
    """Fetch OHLCV data for symbols using robust_data_fetcher."""
    try:
        # Determine period based on date range
        start = datetime.strptime(start_date, "%Y-%m-%d")
        end = datetime.strptime(end_date, "%Y-%m-%d")
        days_diff = (end - start).days
        
        if days_diff <= 30:
            period = "1mo"
        elif days_diff <= 90:
            period = "3mo"
        elif days_diff <= 180:
            period = "6mo"
        elif days_diff <= 365:
            period = "1y"
        elif days_diff <= 730:
            period = "2y"
        else:
            period = "5y"
        
        # Use robust batch fetcher with rate limiting
        batch_data = rdf_get_batch(symbols, period=period, batch_size=5, delay_between_batches=0.5)
        
        if not batch_data:
            return pd.DataFrame()
        
        # Combine into multi-index DataFrame like yf.download returns
        all_data = {}
        for col in ['Open', 'High', 'Low', 'Close', 'Volume']:
            for symbol, df in batch_data.items():
                if df is not None and not df.empty and col in df.columns:
                    # Filter to date range
                    df_filtered = df[(df.index >= start) & (df.index <= end)]
                    if not df_filtered.empty:
                        all_data[(col, symbol)] = df_filtered[col]
        
        if not all_data:
            return pd.DataFrame()
        
        result = pd.DataFrame(all_data)
        result.columns = pd.MultiIndex.from_tuples(result.columns)
        return result
            
    except Exception as e:
        logger.error(f"Data fetch error: {e}")
        return pd.DataFrame()


def _compute_indicators(data: pd.DataFrame, symbol: str, indicators: List[Dict]) -> Dict[str, pd.Series]:
    """Compute all indicators for a symbol."""
    results = {}
    
    try:
        # Extract OHLCV for symbol
        if isinstance(data.columns, pd.MultiIndex):
            close = data[("Close", symbol)]
            high = data[("High", symbol)]
            low = data[("Low", symbol)]
            volume = data[("Volume", symbol)]
        else:
            close = data["Close"]
            high = data["High"]
            low = data["Low"]
            volume = data["Volume"]
        
        for ind in indicators:
            ind_id = ind.get("id", ind.get("type"))
            ind_type = ind.get("type")
            params = ind.get("params", {})
            
            if ind_type == "sma":
                results[ind_id] = IndicatorLibrary.sma(close, params.get("period", 20))
            elif ind_type == "ema":
                results[ind_id] = IndicatorLibrary.ema(close, params.get("period", 20))
            elif ind_type == "rsi":
                results[ind_id] = IndicatorLibrary.rsi(close, params.get("period", 14))
            elif ind_type == "macd":
                macd_result = IndicatorLibrary.macd(close, params.get("fast", 12), params.get("slow", 26), params.get("signal", 9))
                results[f"{ind_id}.macd"] = macd_result["macd"]
                results[f"{ind_id}.signal"] = macd_result["signal"]
                results[f"{ind_id}.histogram"] = macd_result["histogram"]
            elif ind_type == "bollinger":
                bb = IndicatorLibrary.bollinger_bands(close, params.get("period", 20), params.get("std_dev", 2.0))
                results[f"{ind_id}.upper"] = bb["upper"]
                results[f"{ind_id}.middle"] = bb["middle"]
                results[f"{ind_id}.lower"] = bb["lower"]
            elif ind_type == "atr":
                results[ind_id] = IndicatorLibrary.atr(high, low, close, params.get("period", 14))
            elif ind_type == "stochastic":
                stoch = IndicatorLibrary.stochastic(high, low, close, params.get("k_period", 14), params.get("d_period", 3))
                results[f"{ind_id}.k"] = stoch["k"]
                results[f"{ind_id}.d"] = stoch["d"]
            elif ind_type == "momentum":
                results[ind_id] = IndicatorLibrary.momentum(close, params.get("period", 10))
            elif ind_type == "roc":
                results[ind_id] = IndicatorLibrary.roc(close, params.get("period", 10))
            elif ind_type == "donchian":
                dc = IndicatorLibrary.donchian_channel(high, low, params.get("period", 20))
                results[f"{ind_id}.upper"] = dc["upper"]
                results[f"{ind_id}.lower"] = dc["lower"]
            elif ind_type == "supertrend":
                st = IndicatorLibrary.supertrend(high, low, close, params.get("period", 10), params.get("multiplier", 3.0))
                results[f"{ind_id}.supertrend"] = st["supertrend"]
                results[f"{ind_id}.direction"] = st["direction"]
        
        # Add close price
        results["close"] = close
        results["high"] = high
        results["low"] = low
        
    except Exception as e:
        logger.error(f"Indicator computation error: {e}")
    
    return results


def _evaluate_condition(condition: str, indicators: Dict[str, pd.Series], idx: int) -> bool:
    """Evaluate a condition string at a specific index."""
    try:
        # Simple condition parser
        # Supports: >, <, >=, <=, ==, AND, OR
        
        # Create local namespace with indicator values
        local_vars = {}
        for key, series in indicators.items():
            if idx < len(series):
                local_vars[key.replace(".", "_")] = float(series.iloc[idx]) if not pd.isna(series.iloc[idx]) else 0
                # Previous value
                if idx > 0:
                    local_vars[f"{key.replace('.', '_')}_1"] = float(series.iloc[idx-1]) if not pd.isna(series.iloc[idx-1]) else 0
        
        # Replace condition syntax
        eval_condition = condition
        for key in indicators.keys():
            eval_condition = eval_condition.replace(f"{key}[1]", f"{key.replace('.', '_')}_1")
            eval_condition = eval_condition.replace(key, key.replace(".", "_"))
        
        eval_condition = eval_condition.replace("AND", "and").replace("OR", "or")
        
        return eval(eval_condition, {"__builtins__": {}}, local_vars)
        
    except Exception as e:
        return False


def run_backtest(
    strategy: Dict[str, Any],
    start_date: str = None,
    end_date: str = None,
    initial_capital: float = 100000,
    commission: float = 0.001,
    slippage: float = 0.0005
) -> Dict[str, Any]:
    """
    Run a complete backtest simulation.
    
    Returns equity curve, trade log, and performance metrics.
    """
    try:
        # Default dates
        if not end_date:
            end_date = datetime.now().strftime("%Y-%m-%d")
        if not start_date:
            start_date = (datetime.now() - timedelta(days=365*3)).strftime("%Y-%m-%d")
        
        universe = strategy.get("universe", ["SPY"])
        indicators_config = strategy.get("indicators", [])
        entry_rules = strategy.get("entry_rules", {})
        exit_rules = strategy.get("exit_rules", {})
        risk_mgmt = strategy.get("risk_management", {})
        
        stop_loss = risk_mgmt.get("stop_loss", 0.02)
        take_profit = risk_mgmt.get("take_profit", 0.06)
        max_positions = risk_mgmt.get("max_positions", 10)
        
        # Calculate warmup period based on indicator periods
        max_period = 0
        for ind in indicators_config:
            params = ind.get("params", {})
            for k, v in params.items():
                if "period" in k.lower() and isinstance(v, (int, float)):
                    max_period = max(max_period, int(v))
        
        warmup = max(max_period + 10, 50)  # Minimum warmup for indicator calculation
        
        # Extend fetch start to accommodate warmup
        actual_start = datetime.strptime(start_date, "%Y-%m-%d")
        fetch_start = (actual_start - timedelta(days=warmup + 30)).strftime("%Y-%m-%d")  # Extra buffer for weekends/holidays
        
        # Fetch data
        data = _fetch_price_data(universe, fetch_start, end_date)
        if data.empty:
            return {"error": "Failed to fetch price data"}
        
        # Find index of actual start date for trading
        trading_start_idx = 0
        for i, dt in enumerate(data.index):
            if dt.strftime("%Y-%m-%d") >= start_date:
                trading_start_idx = max(i, warmup)
                break
        else:
            trading_start_idx = warmup
        
        # Initialize tracking
        cash = initial_capital
        positions = {}  # symbol -> {shares, entry_price, entry_date, entry_idx}
        equity_curve = []
        trades = []
        
        # Compute indicators for all symbols
        all_indicators = {}
        for symbol in universe:
            all_indicators[symbol] = _compute_indicators(data, symbol, indicators_config)
        
        # Simulation loop - start from trading_start_idx (after warmup and actual start date)
        for i in range(trading_start_idx, len(data)):
            current_date = data.index[i]
            
            # Calculate current portfolio value
            portfolio_value = cash
            for sym, pos in positions.items():
                try:
                    if isinstance(data.columns, pd.MultiIndex):
                        current_price = float(data[("Close", sym)].iloc[i])
                    else:
                        current_price = float(data["Close"].iloc[i])
                    portfolio_value += pos["shares"] * current_price
                except:
                    pass
            
            # Check exits for existing positions
            for sym in list(positions.keys()):
                pos = positions[sym]
                try:
                    if isinstance(data.columns, pd.MultiIndex):
                        current_price = float(data[("Close", sym)].iloc[i])
                    else:
                        current_price = float(data["Close"].iloc[i])
                    
                    pnl_pct = (current_price - pos["entry_price"]) / pos["entry_price"]
                    
                    exit_trade = False
                    exit_reason = ""
                    
                    # Stop loss
                    if pnl_pct <= -stop_loss:
                        exit_trade = True
                        exit_reason = "stop_loss"
                    # Take profit
                    elif pnl_pct >= take_profit:
                        exit_trade = True
                        exit_reason = "take_profit"
                    # Exit signal
                    elif exit_rules.get("long") and _evaluate_condition(exit_rules["long"], all_indicators[sym], i):
                        exit_trade = True
                        exit_reason = "signal_exit"
                    
                    if exit_trade:
                        # Execute exit
                        exit_price = current_price * (1 - slippage)
                        proceeds = pos["shares"] * exit_price * (1 - commission)
                        cash += proceeds
                        
                        trade_pnl = proceeds - (pos["shares"] * pos["entry_price"] * (1 + commission))
                        
                        trades.append({
                            "symbol": sym,
                            "direction": "long",
                            "entry_date": pos["entry_date"].isoformat() if hasattr(pos["entry_date"], 'isoformat') else str(pos["entry_date"]),
                            "entry_price": pos["entry_price"],
                            "exit_date": current_date.isoformat() if hasattr(current_date, 'isoformat') else str(current_date),
                            "exit_price": exit_price,
                            "shares": pos["shares"],
                            "pnl": float(trade_pnl),
                            "pnl_pct": float(pnl_pct * 100),
                            "duration_days": (current_date - pos["entry_date"]).days if hasattr(current_date, 'days') or hasattr(pos["entry_date"], 'days') else i - pos["entry_idx"],
                            "exit_reason": exit_reason
                        })
                        
                        del positions[sym]
                        
                except Exception as e:
                    logger.error(f"Exit evaluation error for {sym}: {e}")
            
            # Check entries for new positions
            if len(positions) < max_positions:
                for sym in universe:
                    if sym in positions:
                        continue
                    
                    try:
                        # Evaluate entry condition
                        if entry_rules.get("long") and _evaluate_condition(entry_rules["long"], all_indicators[sym], i):
                            if isinstance(data.columns, pd.MultiIndex):
                                entry_price = float(data[("Close", sym)].iloc[i])
                            else:
                                entry_price = float(data["Close"].iloc[i])
                            
                            # Position sizing (equal weight)
                            position_value = portfolio_value / max_positions
                            shares = int(position_value / (entry_price * (1 + slippage + commission)))
                            
                            if shares > 0 and cash >= shares * entry_price * (1 + slippage + commission):
                                cost = shares * entry_price * (1 + slippage) * (1 + commission)
                                cash -= cost
                                
                                positions[sym] = {
                                    "shares": shares,
                                    "entry_price": entry_price * (1 + slippage),
                                    "entry_date": current_date,
                                    "entry_idx": i
                                }
                                
                                if len(positions) >= max_positions:
                                    break
                                    
                    except Exception as e:
                        logger.error(f"Entry evaluation error for {sym}: {e}")
            
            # Record equity
            equity_curve.append({
                "date": current_date.isoformat() if hasattr(current_date, 'isoformat') else str(current_date),
                "equity": float(portfolio_value),
                "cash": float(cash),
                "positions": len(positions)
            })
        
        # Calculate performance metrics
        if not equity_curve:
            return {"error": "No equity curve generated"}
        
        equity_values = [e["equity"] for e in equity_curve]
        equity_series = pd.Series(equity_values)
        returns = equity_series.pct_change().dropna()
        
        # Metrics
        total_return = (equity_values[-1] - initial_capital) / initial_capital
        
        if len(returns) > 0:
            annual_return = float(returns.mean() * 252)
            annual_vol = float(returns.std() * np.sqrt(252))
            sharpe = annual_return / annual_vol if annual_vol > 0 else 0
            
            downside = returns[returns < 0]
            downside_std = float(downside.std() * np.sqrt(252)) if len(downside) > 0 else annual_vol
            sortino = annual_return / downside_std if downside_std > 0 else 0
            
            # Drawdown
            cumulative = (1 + returns).cumprod()
            rolling_max = cumulative.cummax()
            drawdowns = (cumulative - rolling_max) / rolling_max
            max_drawdown = float(abs(drawdowns.min()))
            
            calmar = annual_return / max_drawdown if max_drawdown > 0 else 0
        else:
            annual_return = 0
            annual_vol = 0
            sharpe = 0
            sortino = 0
            max_drawdown = 0
            calmar = 0
        
        # Trade statistics
        if trades:
            winning_trades = [t for t in trades if t["pnl"] > 0]
            losing_trades = [t for t in trades if t["pnl"] <= 0]
            
            win_rate = len(winning_trades) / len(trades) if trades else 0
            avg_win = np.mean([t["pnl"] for t in winning_trades]) if winning_trades else 0
            avg_loss = np.mean([t["pnl"] for t in losing_trades]) if losing_trades else 0
            profit_factor = abs(sum(t["pnl"] for t in winning_trades) / sum(t["pnl"] for t in losing_trades)) if losing_trades and sum(t["pnl"] for t in losing_trades) != 0 else 0
            
            avg_duration = np.mean([t["duration_days"] for t in trades])
        else:
            win_rate = 0
            avg_win = 0
            avg_loss = 0
            profit_factor = 0
            avg_duration = 0
        
        # Downsample equity curve for large datasets
        if len(equity_curve) > 500:
            step = len(equity_curve) // 500
            equity_curve = equity_curve[::step]
        
        return {
            "equity_curve": equity_curve,
            "trades": trades,
            "metrics": {
                "total_return": float(total_return),
                "annual_return": float(annual_return),
                "annual_volatility": float(annual_vol),
                "sharpe_ratio": float(sharpe),
                "sortino_ratio": float(sortino),
                "calmar_ratio": float(calmar),
                "max_drawdown": float(max_drawdown),
                "total_trades": len(trades),
                "win_rate": float(win_rate),
                "profit_factor": float(profit_factor),
                "avg_win": float(avg_win),
                "avg_loss": float(avg_loss),
                "avg_duration_days": float(avg_duration)
            },
            "summary": {
                "start_date": start_date,
                "end_date": end_date,
                "initial_capital": initial_capital,
                "final_capital": float(equity_values[-1]) if equity_values else initial_capital,
                "strategy_name": strategy.get("name", "Unnamed")
            }
        }
        
    except Exception as e:
        logger.error(f"Backtest error: {e}")
        return {"error": str(e)}


# =============================================================================
# FEATURE 64: PARAMETER OPTIMIZATION
# =============================================================================

def optimize_parameters(
    strategy: Dict[str, Any],
    param_space: Dict[str, Dict],
    method: str = "grid",
    objective: str = "sharpe",
    n_iterations: int = 100,
    constraints: Dict = None,
    start_date: str = None,
    end_date: str = None
) -> Dict[str, Any]:
    """
    Optimize strategy parameters.
    
    param_space: {
        "indicator_id.param_name": {"min": 5, "max": 50, "step": 5}
    }
    
    method: "grid", "random"
    objective: "sharpe", "return", "calmar", "sortino"
    """
    try:
        if constraints is None:
            constraints = {"max_drawdown": 0.25, "min_trades": 10}
        
        # Generate parameter combinations
        param_sets = []
        
        if method == "grid":
            # Grid search
            param_names = list(param_space.keys())
            param_values = []
            
            for name in param_names:
                spec = param_space[name]
                values = np.arange(spec["min"], spec["max"] + spec.get("step", 1), spec.get("step", 1))
                param_values.append(values.tolist())
            
            # Generate all combinations (limit to avoid explosion)
            from itertools import product
            all_combos = list(product(*param_values))
            if len(all_combos) > n_iterations:
                # Random sample
                indices = np.random.choice(len(all_combos), n_iterations, replace=False)
                all_combos = [all_combos[i] for i in indices]
            
            for combo in all_combos:
                param_set = {param_names[i]: combo[i] for i in range(len(param_names))}
                param_sets.append(param_set)
                
        else:  # random
            for _ in range(n_iterations):
                param_set = {}
                for name, spec in param_space.items():
                    if spec.get("step"):
                        values = np.arange(spec["min"], spec["max"] + spec["step"], spec["step"])
                        param_set[name] = float(np.random.choice(values))
                    else:
                        param_set[name] = float(np.random.uniform(spec["min"], spec["max"]))
                param_sets.append(param_set)
        
        # Run backtests
        results = []
        
        for params in param_sets:
            # Apply parameters to strategy
            test_strategy = strategy.copy()
            test_strategy["indicators"] = []
            
            for ind in strategy.get("indicators", []):
                new_ind = ind.copy()
                new_params = ind.get("params", {}).copy()
                
                for param_key, param_value in params.items():
                    parts = param_key.split(".")
                    if len(parts) == 2 and parts[0] == ind.get("id"):
                        new_params[parts[1]] = int(param_value) if param_value == int(param_value) else param_value
                
                new_ind["params"] = new_params
                test_strategy["indicators"].append(new_ind)
            
            # Run backtest
            bt_result = run_backtest(test_strategy, start_date, end_date)
            
            if "error" in bt_result:
                continue
            
            metrics = bt_result.get("metrics", {})
            
            # Check constraints
            passed = True
            if metrics.get("max_drawdown", 1) > constraints.get("max_drawdown", 1):
                passed = False
            if metrics.get("total_trades", 0) < constraints.get("min_trades", 0):
                passed = False
            
            # Get objective value
            obj_value = metrics.get(f"{objective}_ratio" if objective in ["sharpe", "sortino", "calmar"] else objective, 0)
            
            results.append({
                "params": params,
                "metrics": metrics,
                "objective": float(obj_value) if not math.isnan(obj_value) else 0,
                "passed_constraints": passed
            })
        
        if not results:
            return {"error": "No valid parameter combinations found"}
        
        # Sort by objective
        results.sort(key=lambda x: x["objective"], reverse=True)
        
        # Get passed results
        passed_results = [r for r in results if r["passed_constraints"]]
        
        # Calculate robustness metrics
        if len(passed_results) >= 3:
            objectives = [r["objective"] for r in passed_results[:20]]
            robustness_score = 100 - (np.std(objectives) / (np.mean(objectives) + 0.001) * 100)
            robustness_score = max(0, min(100, robustness_score))
        else:
            robustness_score = 0
        
        # Best parameters
        best = passed_results[0] if passed_results else results[0]
        
        return {
            "best_params": best["params"],
            "best_metrics": best["metrics"],
            "best_objective": best["objective"],
            "all_results": results[:50],  # Top 50
            "passed_count": len(passed_results),
            "total_tested": len(results),
            "robustness_score": float(robustness_score),
            "method": method,
            "objective": objective,
            "recommendation": {
                "params": best["params"],
                "confidence": "high" if robustness_score > 70 else "medium" if robustness_score > 40 else "low",
                "warnings": [] if robustness_score > 50 else ["Low robustness - parameters may be overfit"]
            }
        }
        
    except Exception as e:
        logger.error(f"Optimization error: {e}")
        return {"error": str(e)}


# =============================================================================
# FEATURE 63: WALK FORWARD ANALYSIS
# =============================================================================

def walk_forward_analysis(
    strategy: Dict[str, Any],
    param_space: Dict[str, Dict] = None,
    train_period_days: int = 252,
    test_period_days: int = 63,
    step_days: int = 63,
    method: str = "rolling",
    optimize_each_window: bool = True,
    n_opt_iterations: int = 50,
    start_date: str = None,
    end_date: str = None
) -> Dict[str, Any]:
    """
    Run walk-forward analysis.
    
    method: "rolling" or "expanding"
    """
    try:
        if not end_date:
            end_date = datetime.now().strftime("%Y-%m-%d")
        if not start_date:
            start_date = (datetime.now() - timedelta(days=365*5)).strftime("%Y-%m-%d")
        
        start_dt = datetime.strptime(start_date, "%Y-%m-%d")
        end_dt = datetime.strptime(end_date, "%Y-%m-%d")
        
        windows = []
        window_results = []
        all_oos_equity = []
        param_evolution = []
        
        current_start = start_dt
        window_num = 0
        
        while current_start + timedelta(days=train_period_days + test_period_days) <= end_dt:
            window_num += 1
            
            if method == "rolling":
                train_start = current_start
            else:  # expanding
                train_start = start_dt
            
            train_end = current_start + timedelta(days=train_period_days)
            test_start = train_end
            test_end = test_start + timedelta(days=test_period_days)
            
            if test_end > end_dt:
                break
            
            windows.append({
                "window": window_num,
                "train_start": train_start.strftime("%Y-%m-%d"),
                "train_end": train_end.strftime("%Y-%m-%d"),
                "test_start": test_start.strftime("%Y-%m-%d"),
                "test_end": test_end.strftime("%Y-%m-%d")
            })
            
            # Optimize on training data (if param_space provided)
            if optimize_each_window and param_space:
                opt_result = optimize_parameters(
                    strategy,
                    param_space,
                    method="random",
                    n_iterations=n_opt_iterations,
                    start_date=train_start.strftime("%Y-%m-%d"),
                    end_date=train_end.strftime("%Y-%m-%d")
                )
                
                if "error" not in opt_result:
                    best_params = opt_result.get("best_params", {})
                    param_evolution.append({
                        "window": window_num,
                        "params": best_params
                    })
                    
                    # Apply best params to strategy
                    test_strategy = strategy.copy()
                    test_strategy["indicators"] = []
                    for ind in strategy.get("indicators", []):
                        new_ind = ind.copy()
                        new_params = ind.get("params", {}).copy()
                        for param_key, param_value in best_params.items():
                            parts = param_key.split(".")
                            if len(parts) == 2 and parts[0] == ind.get("id"):
                                new_params[parts[1]] = int(param_value) if param_value == int(param_value) else param_value
                        new_ind["params"] = new_params
                        test_strategy["indicators"].append(new_ind)
                else:
                    test_strategy = strategy
            else:
                test_strategy = strategy
            
            # Run out-of-sample backtest
            oos_result = run_backtest(
                test_strategy,
                start_date=test_start.strftime("%Y-%m-%d"),
                end_date=test_end.strftime("%Y-%m-%d")
            )
            
            if "error" not in oos_result:
                metrics = oos_result.get("metrics", {})
                window_results.append({
                    "window": window_num,
                    "sharpe": metrics.get("sharpe_ratio", 0),
                    "return": metrics.get("total_return", 0),
                    "max_dd": metrics.get("max_drawdown", 0),
                    "trades": metrics.get("total_trades", 0),
                    "win_rate": metrics.get("win_rate", 0),
                    "passed": metrics.get("sharpe_ratio", 0) > 0 and metrics.get("max_drawdown", 1) < 0.25
                })
                
                # Collect OOS equity
                for eq in oos_result.get("equity_curve", []):
                    all_oos_equity.append(eq)
            else:
                window_results.append({
                    "window": window_num,
                    "sharpe": 0,
                    "return": 0,
                    "max_dd": 0,
                    "trades": 0,
                    "win_rate": 0,
                    "passed": False
                })
            
            current_start += timedelta(days=step_days)
        
        if not window_results:
            return {"error": "No windows completed"}
        
        # Aggregate metrics
        sharpes = [w["sharpe"] for w in window_results]
        returns = [w["return"] for w in window_results]
        drawdowns = [w["max_dd"] for w in window_results]
        passed_count = sum(1 for w in window_results if w["passed"])
        
        consistency_rate = passed_count / len(window_results) * 100
        sharpe_variance = float(np.var(sharpes))
        avg_sharpe = float(np.mean(sharpes))
        avg_return = float(np.mean(returns))
        avg_drawdown = float(np.mean(drawdowns))
        
        # Calculate parameter stability
        if len(param_evolution) > 1:
            param_drifts = []
            for key in param_evolution[0]["params"].keys():
                values = [pe["params"].get(key, 0) for pe in param_evolution]
                param_drifts.append(np.std(values) / (np.mean(values) + 0.001))
            param_stability = 100 - float(np.mean(param_drifts) * 100)
            param_stability = max(0, min(100, param_stability))
        else:
            param_stability = 100
        
        # Deployment verdict
        if consistency_rate >= 70 and avg_sharpe > 0.5 and param_stability > 50:
            verdict = "PASS"
            verdict_color = "green"
        elif consistency_rate >= 50 and avg_sharpe > 0:
            verdict = "CONDITIONAL"
            verdict_color = "yellow"
        else:
            verdict = "FAIL"
            verdict_color = "red"
        
        # Confidence score
        confidence = min(100, consistency_rate * 0.4 + (avg_sharpe * 20) + param_stability * 0.3)
        confidence = max(0, confidence)
        
        return {
            "windows": windows,
            "window_results": window_results,
            "oos_equity": all_oos_equity[-500:] if len(all_oos_equity) > 500 else all_oos_equity,  # Limit size
            "param_evolution": param_evolution,
            "stability_metrics": {
                "consistency_rate": consistency_rate,
                "sharpe_variance": sharpe_variance,
                "param_stability": param_stability,
                "avg_sharpe": avg_sharpe,
                "avg_return": avg_return,
                "avg_drawdown": avg_drawdown
            },
            "verdict": {
                "decision": verdict,
                "color": verdict_color,
                "confidence": float(confidence),
                "reasons": [
                    f"Consistency: {consistency_rate:.0f}% of windows passed",
                    f"Avg Sharpe: {avg_sharpe:.2f}",
                    f"Param Stability: {param_stability:.0f}%"
                ]
            },
            "total_windows": len(window_results),
            "passed_windows": passed_count
        }
        
    except Exception as e:
        logger.error(f"Walk-forward error: {e}")
        return {"error": str(e)}


# =============================================================================
# FEATURE 12: MONTE CARLO SIMULATION
# =============================================================================

def run_monte_carlo(
    strategy: Dict[str, Any],
    n_simulations: int = 1000,
    horizon_days: int = 252,
    initial_capital: float = 100000,
    target_wealth: float = None,
    ruin_threshold: float = 0.5,
    use_fat_tails: bool = True,
    vol_clustering: bool = True,
    start_date: str = None,
    end_date: str = None
) -> Dict[str, Any]:
    """
    Monte Carlo simulation for strategy outcomes.
    
    Generates probability distributions of terminal wealth, drawdowns, and time-to-recovery.
    Uses optional fat-tailed distribution and volatility clustering.
    """
    try:
        # First, run backtest to get historical returns
        bt_result = run_backtest(strategy, start_date, end_date, initial_capital)
        
        if "error" in bt_result:
            return bt_result
        
        equity_curve = bt_result.get("equity_curve", [])
        if len(equity_curve) < 20:
            return {"error": "Insufficient backtest data for Monte Carlo"}
        
        # Calculate historical returns
        equity_values = pd.Series([e["equity"] for e in equity_curve])
        returns = equity_values.pct_change().dropna()
        
        mu = float(returns.mean())
        sigma = float(returns.std())
        skew = float(returns.skew()) if len(returns) > 3 else 0
        kurt = float(returns.kurtosis()) if len(returns) > 4 else 0
        
        # Run simulations
        terminal_wealth = []
        max_drawdowns = []
        paths = []
        ruin_count = 0
        target_count = 0
        
        for sim in range(n_simulations):
            np.random.seed(sim)
            
            # Generate returns
            if use_fat_tails and kurt > 0:
                # Student-t distribution for fat tails
                df = max(4, 6 / (1 + kurt / 3))
                sim_returns = stats.t.rvs(df, loc=mu, scale=sigma, size=horizon_days)
            else:
                sim_returns = np.random.normal(mu, sigma, horizon_days)
            
            # Add volatility clustering if enabled
            if vol_clustering:
                vol_factor = np.ones(horizon_days)
                current_vol = 1.0
                for i in range(1, horizon_days):
                    # Simple GARCH-like process
                    shock = abs(sim_returns[i-1]) / sigma
                    current_vol = 0.9 * current_vol + 0.1 * shock
                    vol_factor[i] = current_vol
                sim_returns = sim_returns * vol_factor
            
            # Simulate equity path
            equity = initial_capital
            path = [equity]
            peak = equity
            max_dd = 0
            
            for r in sim_returns:
                equity *= (1 + r)
                path.append(equity)
                peak = max(peak, equity)
                dd = (peak - equity) / peak
                max_dd = max(max_dd, dd)
            
            terminal_wealth.append(path[-1])
            max_drawdowns.append(max_dd)
            
            # Check ruin and target
            if path[-1] < initial_capital * ruin_threshold:
                ruin_count += 1
            if target_wealth and path[-1] >= target_wealth:
                target_count += 1
            
            # Store sampled paths for fan chart
            if sim < 100:
                paths.append(path[::max(1, len(path)//50)])  # Downsample
        
        # Calculate statistics
        tw_array = np.array(terminal_wealth)
        dd_array = np.array(max_drawdowns)
        
        percentiles = [5, 10, 25, 50, 75, 90, 95]
        wealth_percentiles = {p: float(np.percentile(tw_array, p)) for p in percentiles}
        dd_percentiles = {p: float(np.percentile(dd_array, p)) for p in percentiles}
        
        # Generate fan chart data (percentile bands over time)
        fan_chart = []
        path_array = np.array(paths)
        for i in range(path_array.shape[1]):
            col = path_array[:, i]
            fan_chart.append({
                "step": i,
                "p5": float(np.percentile(col, 5)),
                "p25": float(np.percentile(col, 25)),
                "p50": float(np.percentile(col, 50)),
                "p75": float(np.percentile(col, 75)),
                "p95": float(np.percentile(col, 95))
            })
        
        # Confidence score
        prob_profit = float((tw_array > initial_capital).mean())
        expected_return = float((tw_array.mean() - initial_capital) / initial_capital)
        confidence = min(100, max(0, prob_profit * 50 + (1 - dd_percentiles[50]) * 50))
        
        return {
            "n_simulations": n_simulations,
            "horizon_days": horizon_days,
            "terminal_wealth": {
                "mean": float(tw_array.mean()),
                "std": float(tw_array.std()),
                "percentiles": wealth_percentiles,
                "min": float(tw_array.min()),
                "max": float(tw_array.max())
            },
            "drawdowns": {
                "mean": float(dd_array.mean()),
                "percentiles": dd_percentiles,
                "max_observed": float(dd_array.max())
            },
            "probabilities": {
                "prob_profit": prob_profit,
                "prob_ruin": float(ruin_count / n_simulations),
                "prob_target": float(target_count / n_simulations) if target_wealth else None,
                "expected_return": expected_return
            },
            "fan_chart": fan_chart,
            "confidence_score": float(confidence),
            "input_stats": {
                "historical_mu": mu * 252,
                "historical_sigma": sigma * math.sqrt(252),
                "skew": skew,
                "kurtosis": kurt
            }
        }
        
    except Exception as e:
        logger.error(f"Monte Carlo error: {e}")
        return {"error": str(e)}


# =============================================================================
# FEATURE 9: STRATEGY COMPARISON
# =============================================================================

def compare_strategies(
    strategies: List[Dict[str, Any]],
    start_date: str = None,
    end_date: str = None,
    initial_capital: float = 100000,
    benchmark: str = "SPY"
) -> Dict[str, Any]:
    """
    Compare multiple strategies side-by-side.
    
    Includes dominance testing, efficiency frontier, and correlation analysis.
    """
    try:
        results = []
        all_returns = {}
        all_equity = {}
        
        # Run backtests for each strategy
        for i, strategy in enumerate(strategies):
            bt_result = run_backtest(strategy, start_date, end_date, initial_capital)
            
            if "error" in bt_result:
                continue
            
            name = strategy.get("name", f"Strategy_{i+1}")
            metrics = bt_result.get("metrics", {})
            equity = [e["equity"] for e in bt_result.get("equity_curve", [])]
            
            if len(equity) > 1:
                returns = pd.Series(equity).pct_change().dropna()
                all_returns[name] = returns
                all_equity[name] = equity
            
            results.append({
                "name": name,
                "total_return": metrics.get("total_return", 0),
                "annual_return": metrics.get("annual_return", 0),
                "annual_volatility": metrics.get("annual_volatility", 0),
                "sharpe_ratio": metrics.get("sharpe_ratio", 0),
                "sortino_ratio": metrics.get("sortino_ratio", 0),
                "calmar_ratio": metrics.get("calmar_ratio", 0),
                "max_drawdown": metrics.get("max_drawdown", 0),
                "win_rate": metrics.get("win_rate", 0),
                "profit_factor": metrics.get("profit_factor", 0),
                "total_trades": metrics.get("total_trades", 0)
            })
        
        if not results:
            return {"error": "No valid strategy results"}
        
        # Calculate correlation matrix
        if len(all_returns) >= 2:
            returns_df = pd.DataFrame(all_returns)
            corr_matrix = returns_df.corr().to_dict()
        else:
            corr_matrix = {}
        
        # Dominance testing
        dominance_matrix = {}
        for i, r1 in enumerate(results):
            name1 = r1["name"]
            dominance_matrix[name1] = {}
            for j, r2 in enumerate(results):
                if i == j:
                    continue
                name2 = r2["name"]
                # Strategy 1 dominates if: higher return AND lower vol AND lower DD
                dominates = (
                    r1["annual_return"] > r2["annual_return"] and
                    r1["annual_volatility"] <= r2["annual_volatility"] and
                    r1["max_drawdown"] <= r2["max_drawdown"]
                )
                dominance_matrix[name1][name2] = dominates
        
        # Efficiency frontier points (return vs volatility)
        frontier_points = []
        for r in results:
            frontier_points.append({
                "name": r["name"],
                "return": r["annual_return"],
                "volatility": r["annual_volatility"],
                "sharpe": r["sharpe_ratio"]
            })
        
        # Sort by return
        frontier_points.sort(key=lambda x: x["return"])
        
        # Find efficient strategies (not dominated)
        efficient = []
        for i, p in enumerate(frontier_points):
            is_efficient = True
            for j, q in enumerate(frontier_points):
                if i != j:
                    if q["return"] >= p["return"] and q["volatility"] < p["volatility"]:
                        is_efficient = False
                        break
            if is_efficient:
                efficient.append(p["name"])
        
        # Create overlaid equity curves data
        equity_curves = {}
        for name, equity in all_equity.items():
            # Normalize to 100
            if equity:
                normalized = [100 * e / equity[0] for e in equity]
                equity_curves[name] = normalized[::max(1, len(normalized)//500)]
        
        # Best use case recommendations
        recommendations = []
        best_sharpe = max(results, key=lambda x: x["sharpe_ratio"])
        best_return = max(results, key=lambda x: x["annual_return"])
        lowest_dd = min(results, key=lambda x: x["max_drawdown"])
        
        recommendations.append(f"Best risk-adjusted: {best_sharpe['name']} (Sharpe: {best_sharpe['sharpe_ratio']:.2f})")
        recommendations.append(f"Highest return: {best_return['name']} ({best_return['annual_return']*100:.1f}%)")
        recommendations.append(f"Lowest drawdown: {lowest_dd['name']} ({lowest_dd['max_drawdown']*100:.1f}%)")
        
        # Redundancy check (high correlation strategies)
        redundant_pairs = []
        if corr_matrix:
            for n1 in corr_matrix:
                for n2, corr in corr_matrix[n1].items():
                    if n1 < n2 and corr > 0.9:
                        redundant_pairs.append({"strategy1": n1, "strategy2": n2, "correlation": corr})
        
        return {
            "strategies": results,
            "correlation_matrix": corr_matrix,
            "dominance_matrix": dominance_matrix,
            "efficiency_frontier": frontier_points,
            "efficient_strategies": efficient,
            "equity_curves": equity_curves,
            "recommendations": recommendations,
            "redundant_pairs": redundant_pairs
        }
        
    except Exception as e:
        logger.error(f"Strategy comparison error: {e}")
        return {"error": str(e)}


# =============================================================================
# FEATURE 13: CAPACITY ANALYSIS
# =============================================================================

def analyze_capacity(
    strategy: Dict[str, Any],
    start_date: str = None,
    end_date: str = None,
    test_capitals: List[float] = None
) -> Dict[str, Any]:
    """
    Analyze strategy capacity constraints.
    
    Tests performance degradation at different capital levels.
    """
    try:
        if test_capitals is None:
            test_capitals = [100000, 500000, 1000000, 5000000, 10000000, 50000000]
        
        results = []
        base_sharpe = None
        
        for capital in test_capitals:
            # Scale slippage with capital (more capital = more market impact)
            impact_factor = 1 + math.log10(capital / 100000) * 0.1
            adjusted_slippage = 0.0005 * impact_factor
            
            bt_result = run_backtest(
                strategy, start_date, end_date, 
                initial_capital=capital,
                slippage=adjusted_slippage
            )
            
            if "error" in bt_result:
                continue
            
            metrics = bt_result.get("metrics", {})
            sharpe = metrics.get("sharpe_ratio", 0)
            
            if base_sharpe is None:
                base_sharpe = sharpe
            
            degradation = (base_sharpe - sharpe) / base_sharpe if base_sharpe > 0 else 0
            
            results.append({
                "capital": capital,
                "sharpe": sharpe,
                "return": metrics.get("annual_return", 0),
                "degradation": degradation,
                "marginal_efficiency": sharpe / (capital / 100000) if capital > 0 else 0
            })
        
        if not results:
            return {"error": "No valid capacity results"}
        
        # Find capacity ceiling (where degradation exceeds 20%)
        capacity_ceiling = test_capitals[-1]
        for r in results:
            if r["degradation"] > 0.2:
                capacity_ceiling = r["capital"]
                break
        
        # Generate saturation curve
        saturation_curve = [
            {"capital": r["capital"], "efficiency": 1 - r["degradation"]}
            for r in results
        ]
        
        # Deployment recommendation
        if capacity_ceiling >= 10000000:
            recommendation = "High capacity - suitable for institutional deployment"
        elif capacity_ceiling >= 1000000:
            recommendation = "Medium capacity - suitable for prop trading"
        else:
            recommendation = "Low capacity - suitable for personal accounts only"
        
        return {
            "test_results": results,
            "capacity_ceiling": capacity_ceiling,
            "saturation_curve": saturation_curve,
            "base_sharpe": base_sharpe,
            "recommendation": recommendation,
            "crowding_risk": "low" if capacity_ceiling > 5000000 else "medium" if capacity_ceiling > 1000000 else "high"
        }
        
    except Exception as e:
        logger.error(f"Capacity analysis error: {e}")
        return {"error": str(e)}


# =============================================================================
# FEATURE 4: PERFORMANCE TEARSHEET
# =============================================================================

def generate_performance_tearsheet(
    strategy: Dict[str, Any],
    start_date: str = None,
    end_date: str = None,
    initial_capital: float = 100000,
    benchmark: str = "SPY"
) -> Dict[str, Any]:
    """
    Generate comprehensive performance tearsheet.
    
    Includes monthly returns heatmap, rolling metrics, distribution stats.
    """
    try:
        # Run backtest
        bt_result = run_backtest(strategy, start_date, end_date, initial_capital)
        if "error" in bt_result:
            return bt_result
        
        equity_curve = bt_result.get("equity_curve", [])
        if len(equity_curve) < 20:
            return {"error": "Insufficient data for tearsheet"}
        
        # Create equity series
        dates = pd.to_datetime([e["date"] for e in equity_curve])
        equity = pd.Series([e["equity"] for e in equity_curve], index=dates)
        returns = equity.pct_change().dropna()
        
        # Monthly returns for heatmap
        monthly_returns = returns.resample('M').apply(lambda x: (1 + x).prod() - 1)
        monthly_heatmap = []
        for date, ret in monthly_returns.items():
            monthly_heatmap.append({
                "year": date.year,
                "month": date.month,
                "return": float(ret) if not pd.isna(ret) else 0
            })
        
        # Annual returns
        annual_returns = returns.resample('Y').apply(lambda x: (1 + x).prod() - 1)
        yearly_stats = [{"year": d.year, "return": float(r)} for d, r in annual_returns.items()]
        
        # Rolling metrics (252-day window)
        rolling_sharpe = []
        rolling_vol = []
        window = min(252, len(returns) - 1)
        if window > 20:
            roll_mean = returns.rolling(window).mean() * 252
            roll_std = returns.rolling(window).std() * np.sqrt(252)
            roll_sharpe_series = roll_mean / roll_std
            for i, (date, val) in enumerate(roll_sharpe_series.dropna().items()):
                if i % 5 == 0:  # Downsample
                    rolling_sharpe.append({"date": date.isoformat(), "value": float(val) if not pd.isna(val) else 0})
            for i, (date, val) in enumerate(roll_std.dropna().items()):
                if i % 5 == 0:
                    rolling_vol.append({"date": date.isoformat(), "value": float(val) if not pd.isna(val) else 0})
        
        # Return distribution
        return_hist, bin_edges = np.histogram(returns.dropna().values, bins=30)
        distribution = {
            "counts": return_hist.tolist(),
            "bins": [(bin_edges[i] + bin_edges[i+1])/2 for i in range(len(bin_edges)-1)],
            "mean": float(returns.mean()),
            "std": float(returns.std()),
            "skew": float(returns.skew()),
            "kurtosis": float(returns.kurtosis())
        }
        
        # Benchmark comparison
        benchmark_data = {}
        try:
            bench_prices = yf.download(benchmark, start=dates.min(), end=dates.max(), progress=False)["Close"]
            if len(bench_prices) > 20:
                bench_returns = bench_prices.pct_change().dropna()
                # Align returns
                common_idx = returns.index.intersection(bench_returns.index)
                if len(common_idx) > 20:
                    strat_aligned = returns.loc[common_idx]
                    bench_aligned = bench_returns.loc[common_idx]
                    
                    # Beta and Alpha
                    cov = np.cov(strat_aligned.values, bench_aligned.values)
                    beta = cov[0, 1] / cov[1, 1] if cov[1, 1] != 0 else 0
                    alpha = (strat_aligned.mean() - beta * bench_aligned.mean()) * 252
                    
                    # Correlation
                    correlation = strat_aligned.corr(bench_aligned)
                    
                    benchmark_data = {
                        "benchmark": benchmark,
                        "alpha": float(alpha),
                        "beta": float(beta),
                        "correlation": float(correlation),
                        "information_ratio": float(alpha / (strat_aligned - bench_aligned).std() / np.sqrt(252)) if (strat_aligned - bench_aligned).std() > 0 else 0
                    }
        except:
            pass
        
        return {
            "metrics": bt_result.get("metrics", {}),
            "monthly_heatmap": monthly_heatmap,
            "yearly_returns": yearly_stats,
            "rolling_sharpe": rolling_sharpe,
            "rolling_volatility": rolling_vol,
            "distribution": distribution,
            "benchmark": benchmark_data,
            "summary": {
                "total_days": len(equity_curve),
                "start_date": str(dates.min().date()),
                "end_date": str(dates.max().date()),
                "total_return": float((equity.iloc[-1] - equity.iloc[0]) / equity.iloc[0])
            }
        }
        
    except Exception as e:
        logger.error(f"Tearsheet error: {e}")
        return {"error": str(e)}


# =============================================================================
# FEATURE 5: DRAWDOWN ANALYSIS
# =============================================================================

def analyze_drawdowns(
    strategy: Dict[str, Any],
    start_date: str = None,
    end_date: str = None,
    initial_capital: float = 100000,
    top_n: int = 10
) -> Dict[str, Any]:
    """
    Comprehensive drawdown analysis.
    
    Includes drawdown episodes, underwater chart, recovery analysis.
    """
    try:
        bt_result = run_backtest(strategy, start_date, end_date, initial_capital)
        if "error" in bt_result:
            return bt_result
        
        equity_curve = bt_result.get("equity_curve", [])
        if len(equity_curve) < 20:
            return {"error": "Insufficient data for drawdown analysis"}
        
        dates = pd.to_datetime([e["date"] for e in equity_curve])
        equity = pd.Series([e["equity"] for e in equity_curve], index=dates)
        
        # Calculate drawdown series
        rolling_max = equity.cummax()
        drawdown = (equity - rolling_max) / rolling_max
        
        # Underwater chart data
        underwater = [{"date": d.isoformat(), "drawdown": float(dd)} for d, dd in drawdown.items()]
        
        # Detect drawdown episodes
        episodes = []
        in_drawdown = False
        episode_start = None
        episode_peak = 0
        trough_date = None
        trough_value = 0
        
        for i, (date, dd) in enumerate(drawdown.items()):
            if not in_drawdown and dd < -0.001:
                in_drawdown = True
                episode_start = date
                episode_peak = rolling_max.iloc[i]
                trough_value = dd
                trough_date = date
            elif in_drawdown:
                if dd < trough_value:
                    trough_value = dd
                    trough_date = date
                if dd >= -0.001:
                    # Episode ended
                    episodes.append({
                        "start": str(episode_start.date()),
                        "trough": str(trough_date.date()),
                        "end": str(date.date()),
                        "depth": float(abs(trough_value)),
                        "duration_days": (date - episode_start).days,
                        "recovery_days": (date - trough_date).days,
                        "peak_value": float(episode_peak)
                    })
                    in_drawdown = False
        
        # Handle ongoing drawdown
        if in_drawdown:
            episodes.append({
                "start": str(episode_start.date()),
                "trough": str(trough_date.date()),
                "end": "ongoing",
                "depth": float(abs(trough_value)),
                "duration_days": (dates.max() - episode_start).days,
                "recovery_days": None,
                "peak_value": float(episode_peak)
            })
        
        # Sort by depth and get top N
        episodes.sort(key=lambda x: x["depth"], reverse=True)
        top_drawdowns = episodes[:top_n]
        
        # Drawdown frequency histogram
        dd_depths = [e["depth"] for e in episodes]
        if dd_depths:
            dd_hist, dd_bins = np.histogram(dd_depths, bins=10)
            dd_frequency = {
                "counts": dd_hist.tolist(),
                "bins": [(dd_bins[i] + dd_bins[i+1])/2 for i in range(len(dd_bins)-1)]
            }
        else:
            dd_frequency = {"counts": [], "bins": []}
        
        # Recovery time distribution
        recovery_times = [e["recovery_days"] for e in episodes if e["recovery_days"] is not None]
        avg_recovery = np.mean(recovery_times) if recovery_times else 0
        max_recovery = max(recovery_times) if recovery_times else 0
        
        return {
            "max_drawdown": float(drawdown.min()),
            "current_drawdown": float(drawdown.iloc[-1]),
            "underwater_chart": underwater[::max(1, len(underwater)//200)],  # Downsample
            "top_drawdowns": top_drawdowns,
            "total_episodes": len(episodes),
            "frequency_histogram": dd_frequency,
            "recovery_stats": {
                "avg_recovery_days": float(avg_recovery),
                "max_recovery_days": int(max_recovery),
                "median_recovery": float(np.median(recovery_times)) if recovery_times else 0
            },
            "time_underwater": float((drawdown < -0.01).mean()),
            "avg_drawdown_depth": float(np.mean(dd_depths)) if dd_depths else 0
        }
        
    except Exception as e:
        logger.error(f"Drawdown analysis error: {e}")
        return {"error": str(e)}


# =============================================================================
# FEATURE 8: REGIME CONDITIONAL BACKTESTING
# =============================================================================

def run_regime_backtest(
    strategy: Dict[str, Any],
    regimes: Dict[str, List[Tuple[str, str]]] = None,
    start_date: str = None,
    end_date: str = None,
    initial_capital: float = 100000
) -> Dict[str, Any]:
    """
    Backtest with regime filtering and per-regime metrics.
    
    regimes: {"bull": [("2021-01-01", "2021-12-31"), ...], "bear": [...]}
    """
    try:
        # Default regimes based on market volatility if not provided
        if regimes is None:
            # Run full backtest first to detect regimes
            bt_result = run_backtest(strategy, start_date, end_date, initial_capital)
            if "error" in bt_result:
                return bt_result
            
            equity_curve = bt_result.get("equity_curve", [])
            dates = pd.to_datetime([e["date"] for e in equity_curve])
            equity = pd.Series([e["equity"] for e in equity_curve], index=dates)
            returns = equity.pct_change().dropna()
            
            # Simple regime detection based on rolling volatility
            rolling_vol = returns.rolling(20).std() * np.sqrt(252)
            vol_median = rolling_vol.median()
            
            regimes = {"low_vol": [], "high_vol": []}
            current_regime = None
            regime_start = None
            
            for date, vol in rolling_vol.dropna().items():
                new_regime = "low_vol" if vol < vol_median else "high_vol"
                if current_regime != new_regime:
                    if current_regime is not None:
                        regimes[current_regime].append((str(regime_start.date()), str(date.date())))
                    regime_start = date
                    current_regime = new_regime
            
            # Close last regime
            if current_regime:
                regimes[current_regime].append((str(regime_start.date()), str(dates.max().date())))
        
        # Run backtest for each regime
        regime_results = {}
        for regime_name, periods in regimes.items():
            regime_returns = []
            total_trades = 0
            total_pnl = 0
            
            for period_start, period_end in periods:
                bt = run_backtest(strategy, period_start, period_end, initial_capital)
                if "error" not in bt:
                    metrics = bt.get("metrics", {})
                    regime_returns.append(metrics.get("total_return", 0))
                    total_trades += metrics.get("total_trades", 0)
                    # Approximate PnL
                    eq = bt.get("equity_curve", [])
                    if eq:
                        total_pnl += eq[-1].get("equity", initial_capital) - initial_capital
            
            if regime_returns:
                regime_results[regime_name] = {
                    "avg_return": float(np.mean(regime_returns)),
                    "total_trades": total_trades,
                    "periods": len(periods),
                    "total_pnl": float(total_pnl),
                    "win_rate": float((np.array(regime_returns) > 0).mean())
                }
        
        # Calculate regime dependency score
        if len(regime_results) >= 2:
            returns_by_regime = [r["avg_return"] for r in regime_results.values()]
            regime_variance = np.var(returns_by_regime)
            dependency_score = min(100, regime_variance * 10000)  # Higher = more regime dependent
        else:
            dependency_score = 0
        
        return {
            "regimes": regimes,
            "regime_results": regime_results,
            "dependency_score": float(dependency_score),
            "recommendation": "Strategy is regime-neutral" if dependency_score < 30 else 
                           "Strategy shows moderate regime dependency" if dependency_score < 60 else
                           "Strategy is highly regime-dependent - consider regime filtering"
        }
        
    except Exception as e:
        logger.error(f"Regime backtest error: {e}")
        return {"error": str(e)}


# =============================================================================
# FEATURE 6: TRANSACTION COST MODEL
# =============================================================================

def analyze_transaction_costs(
    strategy: Dict[str, Any],
    start_date: str = None,
    end_date: str = None,
    slippage_scenarios: List[float] = None
) -> Dict[str, Any]:
    """
    Analyze transaction cost impact on strategy performance.
    
    Includes cost attribution, slippage elasticity curve.
    """
    try:
        if slippage_scenarios is None:
            slippage_scenarios = [0, 0.0001, 0.0005, 0.001, 0.002, 0.005, 0.01]
        
        results = []
        base_return = None
        
        for slip in slippage_scenarios:
            bt = run_backtest(strategy, start_date, end_date, slippage=slip)
            if "error" in bt:
                continue
            
            metrics = bt.get("metrics", {})
            total_return = metrics.get("total_return", 0)
            
            if base_return is None:
                base_return = total_return
            
            degradation = (base_return - total_return) / base_return if base_return != 0 else 0
            
            results.append({
                "slippage_bps": slip * 10000,
                "total_return": float(total_return),
                "sharpe": float(metrics.get("sharpe_ratio", 0)),
                "return_degradation": float(degradation)
            })
        
        if not results:
            return {"error": "No valid cost analysis results"}
        
        # Calculate cost elasticity
        if len(results) >= 2:
            x = np.array([r["slippage_bps"] for r in results])
            y = np.array([r["total_return"] for r in results])
            if len(x) > 1:
                elasticity = (y[-1] - y[0]) / (x[-1] - x[0]) if (x[-1] - x[0]) != 0 else 0
            else:
                elasticity = 0
        else:
            elasticity = 0
        
        # Find breakeven slippage (where return hits 0)
        breakeven = None
        for i, r in enumerate(results):
            if r["total_return"] <= 0 and i > 0:
                breakeven = results[i-1]["slippage_bps"]
                break
        
        return {
            "slippage_curve": results,
            "elasticity": float(elasticity),
            "breakeven_slippage_bps": breakeven,
            "base_return": float(base_return) if base_return else 0,
            "cost_sensitivity": "low" if abs(elasticity) < 0.01 else "medium" if abs(elasticity) < 0.05 else "high"
        }
        
    except Exception as e:
        logger.error(f"Transaction cost analysis error: {e}")
        return {"error": str(e)}


# =============================================================================
# PHASE COMPLETION: ALL REMAINING SPEC ITEMS
# =============================================================================

# -----------------------------------------------------------------------------
# SIGNAL CONFIDENCE & DECAY (Phase 1)
# -----------------------------------------------------------------------------

def calculate_signal_confidence(
    indicator_values: Dict[str, float],
    thresholds: Dict[str, Dict[str, float]],
    weights: Optional[Dict[str, float]] = None
) -> Dict[str, Any]:
    """
    Calculate signal confidence with normalization and weighting.
    
    Args:
        indicator_values: Current indicator readings
        thresholds: Dict with 'bullish' and 'bearish' thresholds per indicator
        weights: Optional weights per indicator (default equal)
    
    Returns:
        Normalized confidence score -1 to +1 with breakdown
    """
    if not indicator_values:
        return {"confidence": 0, "direction": "neutral", "breakdown": {}}
    
    if weights is None:
        weights = {k: 1.0 / len(indicator_values) for k in indicator_values}
    
    breakdown = {}
    total_score = 0
    
    for ind_name, value in indicator_values.items():
        thresh = thresholds.get(ind_name, {"bullish": 0, "bearish": 0})
        weight = weights.get(ind_name, 1.0 / len(indicator_values))
        
        bullish_thresh = thresh.get("bullish", 0)
        bearish_thresh = thresh.get("bearish", 0)
        
        # Normalize to -1 to +1
        if value >= bullish_thresh:
            score = min(1.0, (value - bullish_thresh) / max(0.01, abs(bullish_thresh)))
        elif value <= bearish_thresh:
            score = max(-1.0, (value - bearish_thresh) / max(0.01, abs(bearish_thresh)))
        else:
            # Between thresholds - linear interpolation
            range_size = bullish_thresh - bearish_thresh
            if range_size > 0:
                score = 2 * (value - bearish_thresh) / range_size - 1
            else:
                score = 0
        
        breakdown[ind_name] = {
            "value": float(value),
            "score": round(float(score), 3),
            "weight": round(float(weight), 3),
            "contribution": round(float(score * weight), 3)
        }
        total_score += score * weight
    
    # Normalize total
    total_weight = sum(weights.values())
    normalized_confidence = total_score / total_weight if total_weight > 0 else 0
    
    return {
        "confidence": round(float(normalized_confidence), 3),
        "direction": "bullish" if normalized_confidence > 0.2 else "bearish" if normalized_confidence < -0.2 else "neutral",
        "strength": "strong" if abs(normalized_confidence) > 0.6 else "moderate" if abs(normalized_confidence) > 0.3 else "weak",
        "breakdown": breakdown
    }


def apply_signal_decay(
    signals: List[Dict[str, Any]],
    decay_type: str = "exponential",
    half_life_bars: int = 5
) -> List[Dict[str, Any]]:
    """
    Apply signal decay to reduce stale signal influence.
    
    Args:
        signals: List of signals with 'bar_age' field
        decay_type: 'exponential', 'linear', or 'step'
        half_life_bars: Bars until signal strength halves
    """
    decayed = []
    
    for signal in signals:
        age = signal.get("bar_age", 0)
        original_strength = signal.get("strength", 1.0)
        
        if decay_type == "exponential":
            decay_factor = 0.5 ** (age / half_life_bars)
        elif decay_type == "linear":
            decay_factor = max(0, 1 - age / (2 * half_life_bars))
        elif decay_type == "step":
            decay_factor = 1.0 if age < half_life_bars else 0.5 if age < 2 * half_life_bars else 0
        else:
            decay_factor = 1.0
        
        decayed.append({
            **signal,
            "original_strength": original_strength,
            "decayed_strength": round(original_strength * decay_factor, 3),
            "decay_factor": round(decay_factor, 3)
        })
    
    return decayed


# -----------------------------------------------------------------------------
# SIGNAL DEPENDENCY DAG (Phase 1)
# -----------------------------------------------------------------------------

def build_signal_dependency_dag(strategy: Dict) -> Dict[str, Any]:
    """
    Build a Directed Acyclic Graph of signal dependencies.
    
    Analyzes which indicators depend on which inputs.
    """
    indicators = strategy.get("indicators", [])
    entry_rules = strategy.get("entry_rules", {})
    exit_rules = strategy.get("exit_rules", {})
    
    # Build nodes
    nodes = []
    edges = []
    
    # Price inputs
    price_inputs = ["close", "open", "high", "low", "volume"]
    for inp in price_inputs:
        nodes.append({"id": inp, "type": "input", "level": 0})
    
    # Indicator nodes
    indicator_deps = {
        "sma": ["close"],
        "ema": ["close"],
        "rsi": ["close"],
        "macd": ["close"],
        "bollinger": ["close"],
        "atr": ["high", "low", "close"],
        "stochastic": ["high", "low", "close"],
        "adx": ["high", "low", "close"],
        "vwap": ["high", "low", "close", "volume"],
        "obv": ["close", "volume"]
    }
    
    for ind in indicators:
        ind_id = ind.get("id", ind.get("type"))
        ind_type = ind.get("type", "unknown")
        
        nodes.append({
            "id": ind_id,
            "type": "indicator",
            "indicator_type": ind_type,
            "level": 1
        })
        
        deps = indicator_deps.get(ind_type, ["close"])
        for dep in deps:
            edges.append({"from": dep, "to": ind_id})
    
    # Entry/exit signal nodes
    for rule_type, rule in [("entry_long", entry_rules.get("long", "")), 
                            ("entry_short", entry_rules.get("short", "")),
                            ("exit_long", exit_rules.get("long", "")),
                            ("exit_short", exit_rules.get("short", ""))]:
        if rule:
            nodes.append({"id": rule_type, "type": "signal", "level": 2})
            # Find indicators used in rule
            for ind in indicators:
                ind_id = ind.get("id", ind.get("type"))
                if ind_id in rule:
                    edges.append({"from": ind_id, "to": rule_type})
    
    # Calculate complexity
    complexity = len(nodes) + len(edges) * 0.5
    
    return {
        "nodes": nodes,
        "edges": edges,
        "node_count": len(nodes),
        "edge_count": len(edges),
        "complexity_score": round(complexity, 1),
        "depth": max(n["level"] for n in nodes) if nodes else 0
    }


# -----------------------------------------------------------------------------
# STRATEGY EXPLAINABILITY REPORT (Phase 1)
# -----------------------------------------------------------------------------

def generate_explainability_report(strategy: Dict, backtest_result: Dict) -> Dict[str, Any]:
    """
    Generate a comprehensive strategy explainability report.
    """
    indicators = strategy.get("indicators", [])
    entry_rules = strategy.get("entry_rules", {})
    exit_rules = strategy.get("exit_rules", {})
    trades = backtest_result.get("trades", [])
    metrics = backtest_result.get("metrics", {})
    
    # Indicator descriptions
    indicator_explanations = {
        "sma": "Simple Moving Average - trend following, smooths price action",
        "ema": "Exponential Moving Average - trend following, weights recent prices more",
        "rsi": "Relative Strength Index - momentum oscillator, identifies overbought/oversold",
        "macd": "MACD - trend and momentum, uses moving average crossovers",
        "bollinger": "Bollinger Bands - volatility indicator, identifies breakouts",
        "atr": "Average True Range - volatility measure, used for position sizing",
        "stochastic": "Stochastic Oscillator - momentum, compares close to range"
    }
    
    ind_breakdown = []
    for ind in indicators:
        ind_type = ind.get("type", "unknown")
        ind_breakdown.append({
            "name": ind.get("id", ind_type),
            "type": ind_type,
            "parameters": ind.get("params", {}),
            "explanation": indicator_explanations.get(ind_type, "Technical indicator"),
            "role": "Entry/exit signal generation"
        })
    
    # Entry/exit logic explanation
    entry_explanation = f"Long entry triggered when: {entry_rules.get('long', 'N/A')}"
    exit_explanation = f"Long exit triggered when: {exit_rules.get('long', 'N/A')}"
    
    # Trade analysis
    if trades:
        exit_reasons = {}
        for t in trades:
            reason = t.get("exit_reason", "unknown")
            exit_reasons[reason] = exit_reasons.get(reason, 0) + 1
        
        avg_hold = np.mean([t.get("duration_days", 0) for t in trades])
        win_rate = len([t for t in trades if t.get("net_pnl", 0) > 0]) / len(trades)
    else:
        exit_reasons = {}
        avg_hold = 0
        win_rate = 0
    
    # Risk profile
    sharpe = metrics.get("risk_adjusted", {}).get("sharpe_ratio", 0)
    max_dd = metrics.get("risk", {}).get("max_drawdown", 0)
    
    if sharpe > 1.5 and max_dd < 0.15:
        risk_profile = "Conservative - good risk-adjusted returns with limited downside"
    elif sharpe > 1.0:
        risk_profile = "Moderate - reasonable risk-reward balance"
    elif sharpe > 0.5:
        risk_profile = "Aggressive - higher risk for returns"
    else:
        risk_profile = "High Risk - consider strategy refinement"
    
    return {
        "strategy_name": strategy.get("name", "Unnamed Strategy"),
        "summary": f"This is a {'trend-following' if 'sma' in str(indicators) or 'ema' in str(indicators) else 'momentum'} strategy using {len(indicators)} indicators.",
        "indicators": ind_breakdown,
        "entry_logic": {
            "description": entry_explanation,
            "type": "rule-based"
        },
        "exit_logic": {
            "description": exit_explanation,
            "exit_distribution": exit_reasons
        },
        "trading_characteristics": {
            "avg_holding_period_days": round(avg_hold, 1),
            "win_rate": round(win_rate * 100, 1),
            "total_trades": len(trades)
        },
        "risk_profile": risk_profile,
        "key_metrics": {
            "sharpe_ratio": round(sharpe, 2),
            "max_drawdown_pct": round(max_dd * 100, 1),
            "annual_return_pct": round(metrics.get("returns", {}).get("cagr", 0) * 100, 1)
        },
        "recommendations": [
            "Monitor during high volatility periods" if max_dd > 0.1 else "Strategy shows good drawdown control",
            "Consider reducing position size" if win_rate < 0.4 else "Win rate is acceptable",
            "Strategy may benefit from additional filters" if len(indicators) < 3 else "Indicator coverage seems adequate"
        ]
    }


# -----------------------------------------------------------------------------
# CORPORATE ACTIONS ADJUSTMENT (Phase 2)
# -----------------------------------------------------------------------------

def adjust_for_corporate_actions(
    prices: pd.DataFrame,
    ticker: str,
    actions: Optional[List[Dict]] = None
) -> pd.DataFrame:
    """
    Adjust historical prices for splits and dividends.
    
    Note: yfinance auto_adjust=True handles this, but this provides manual override.
    """
    if actions is None:
        # Try to fetch from yfinance
        try:
            stock = yf.Ticker(ticker)
            splits = stock.splits
            dividends = stock.dividends
            
            actions = []
            for date, ratio in splits.items():
                actions.append({
                    "type": "split",
                    "date": date.strftime("%Y-%m-%d"),
                    "ratio": float(ratio)
                })
            for date, amount in dividends.items():
                actions.append({
                    "type": "dividend",
                    "date": date.strftime("%Y-%m-%d"),
                    "amount": float(amount)
                })
        except:
            actions = []
    
    adjusted = prices.copy()
    
    for action in sorted(actions, key=lambda x: x["date"], reverse=True):
        action_date = pd.to_datetime(action["date"])
        
        if action["type"] == "split":
            mask = adjusted.index < action_date
            ratio = action["ratio"]
            for col in ["Open", "High", "Low", "Close"]:
                if col in adjusted.columns:
                    adjusted.loc[mask, col] = adjusted.loc[mask, col] / ratio
            if "Volume" in adjusted.columns:
                adjusted.loc[mask, "Volume"] = adjusted.loc[mask, "Volume"] * ratio
        
        elif action["type"] == "dividend":
            mask = adjusted.index < action_date
            div_amount = action["amount"]
            for col in ["Open", "High", "Low", "Close"]:
                if col in adjusted.columns:
                    adjusted.loc[mask, col] = adjusted.loc[mask, col] - div_amount
    
    return adjusted


# -----------------------------------------------------------------------------
# BENCHMARK-RELATIVE DRAWDOWN (Phase 5)
# -----------------------------------------------------------------------------

def calculate_benchmark_relative_drawdown(
    strategy_equity: pd.Series,
    benchmark_equity: pd.Series
) -> Dict[str, Any]:
    """
    Calculate drawdown relative to benchmark.
    """
    # Calculate relative equity (strategy / benchmark)
    aligned_bench = benchmark_equity.reindex(strategy_equity.index).ffill()
    relative = strategy_equity / aligned_bench
    relative = relative / relative.iloc[0]  # Normalize to 100
    
    # Calculate drawdown on relative equity
    rolling_max = relative.cummax()
    drawdown = (relative - rolling_max) / rolling_max
    
    # Find episodes
    in_dd = drawdown < 0
    dd_groups = (~in_dd).cumsum()
    
    episodes = []
    for group in dd_groups.unique():
        mask = dd_groups == group
        if in_dd[mask].any():
            dd_series = drawdown[mask]
            episodes.append({
                "start": str(dd_series.index[0].date()),
                "trough": str(dd_series.idxmin().date()),
                "end": str(dd_series.index[-1].date()),
                "depth": round(float(dd_series.min()) * 100, 2)
            })
    
    return {
        "max_relative_drawdown": round(float(drawdown.min()) * 100, 2),
        "current_relative_drawdown": round(float(drawdown.iloc[-1]) * 100, 2),
        "relative_outperformance": round(float(relative.iloc[-1] - 1) * 100, 2),
        "episodes": sorted(episodes, key=lambda x: x["depth"])[:10]
    }


# -----------------------------------------------------------------------------
# COST ATTRIBUTION BY SIGNAL (Phase 6)
# -----------------------------------------------------------------------------

def calculate_cost_attribution(trades: List[Dict]) -> Dict[str, Any]:
    """
    Attribute transaction costs by entry signal type.
    """
    if not trades:
        return {"error": "No trades to analyze"}
    
    by_entry_reason = {}
    by_exit_reason = {}
    
    for trade in trades:
        entry = trade.get("entry_reason", "unknown")
        exit_r = trade.get("exit_reason", "unknown")
        commission = trade.get("commission", 0)
        slippage = trade.get("slippage", 0)
        total_cost = commission + slippage
        
        if entry not in by_entry_reason:
            by_entry_reason[entry] = {"count": 0, "total_cost": 0, "trades": []}
        by_entry_reason[entry]["count"] += 1
        by_entry_reason[entry]["total_cost"] += total_cost
        
        if exit_r not in by_exit_reason:
            by_exit_reason[exit_r] = {"count": 0, "total_cost": 0}
        by_exit_reason[exit_r]["count"] += 1
        by_exit_reason[exit_r]["total_cost"] += total_cost
    
    # Calculate averages
    for k, v in by_entry_reason.items():
        v["avg_cost"] = round(v["total_cost"] / v["count"], 2)
    for k, v in by_exit_reason.items():
        v["avg_cost"] = round(v["total_cost"] / v["count"], 2)
    
    total_costs = sum(t.get("commission", 0) + t.get("slippage", 0) for t in trades)
    gross_pnl = sum(t.get("gross_pnl", 0) for t in trades)
    
    return {
        "by_entry_signal": by_entry_reason,
        "by_exit_signal": by_exit_reason,
        "total_costs": round(total_costs, 2),
        "cost_as_pct_of_gross": round(total_costs / abs(gross_pnl) * 100, 2) if gross_pnl else 0,
        "costliest_entry_type": max(by_entry_reason.items(), key=lambda x: x[1]["total_cost"])[0] if by_entry_reason else None,
        "costliest_exit_type": max(by_exit_reason.items(), key=lambda x: x[1]["total_cost"])[0] if by_exit_reason else None
    }


# -----------------------------------------------------------------------------
# CORRELATION-AWARE POSITION SIZING (Phase 7)
# -----------------------------------------------------------------------------

def calculate_correlation_adjusted_weights(
    returns: pd.DataFrame,
    target_portfolio_vol: float = 0.15
) -> Dict[str, Any]:
    """
    Calculate position weights that account for correlations.
    
    Uses risk parity approach adjusted for correlations.
    """
    if returns.empty or len(returns.columns) < 2:
        return {"weights": {}, "error": "Need multiple assets"}
    
    # Covariance matrix
    cov = returns.cov() * 252
    
    # Correlation matrix
    corr = returns.corr()
    
    # Marginal contribution to risk
    vol = returns.std() * np.sqrt(252)
    
    # Simple inverse volatility weights
    inv_vol = 1 / vol
    base_weights = inv_vol / inv_vol.sum()
    
    # Adjust for correlation (penalize highly correlated assets)
    avg_corr = corr.mean()
    corr_penalty = 1 - (avg_corr - avg_corr.min()) / (avg_corr.max() - avg_corr.min() + 0.01)
    
    adjusted_weights = base_weights * corr_penalty
    adjusted_weights = adjusted_weights / adjusted_weights.sum()
    
    # Scale to target volatility
    port_vol = np.sqrt(adjusted_weights @ cov @ adjusted_weights)
    if port_vol > 0:
        leverage = target_portfolio_vol / port_vol
    else:
        leverage = 1
    
    final_weights = adjusted_weights * min(leverage, 2.0)
    
    return {
        "weights": {col: round(float(w), 4) for col, w in final_weights.items()},
        "correlation_matrix": corr.round(3).to_dict(),
        "individual_vols": vol.round(4).to_dict(),
        "portfolio_vol": round(float(port_vol), 4),
        "leverage_applied": round(float(min(leverage, 2.0)), 2)
    }


# -----------------------------------------------------------------------------
# REBALANCING SCHEDULER (Phase 7)
# -----------------------------------------------------------------------------

def generate_rebalance_schedule(
    start_date: str,
    end_date: str,
    frequency: str = "monthly",
    custom_dates: Optional[List[str]] = None
) -> List[Dict[str, Any]]:
    """
    Generate rebalancing schedule.
    
    frequency: 'daily', 'weekly', 'monthly', 'quarterly', 'custom'
    """
    start = pd.to_datetime(start_date)
    end = pd.to_datetime(end_date)
    
    if frequency == "custom" and custom_dates:
        dates = [pd.to_datetime(d) for d in custom_dates]
    elif frequency == "daily":
        dates = pd.date_range(start, end, freq='B')
    elif frequency == "weekly":
        dates = pd.date_range(start, end, freq='W-FRI')
    elif frequency == "monthly":
        dates = pd.date_range(start, end, freq='BME')
    elif frequency == "quarterly":
        dates = pd.date_range(start, end, freq='BQE')
    else:
        dates = pd.date_range(start, end, freq='BME')
    
    schedule = []
    for i, date in enumerate(dates):
        schedule.append({
            "date": date.strftime("%Y-%m-%d"),
            "rebalance_number": i + 1,
            "type": frequency
        })
    
    return schedule


# -----------------------------------------------------------------------------
# REGIME TRANSITION ANALYSIS (Phase 8)
# -----------------------------------------------------------------------------

def analyze_regime_transitions(
    regime_series: pd.Series,
    returns: pd.Series
) -> Dict[str, Any]:
    """
    Analyze performance around regime transitions.
    """
    # Find transition points
    transitions = []
    prev_regime = None
    
    for date, regime in regime_series.items():
        if prev_regime is not None and regime != prev_regime:
            transitions.append({
                "date": str(date),
                "from_regime": prev_regime,
                "to_regime": regime
            })
        prev_regime = regime
    
    # Analyze performance around transitions
    window = 10  # Days before/after
    transition_analysis = []
    
    for trans in transitions[-20:]:  # Last 20 transitions
        trans_date = pd.to_datetime(trans["date"])
        try:
            idx = returns.index.get_loc(trans_date)
            before = returns.iloc[max(0, idx-window):idx].sum()
            after = returns.iloc[idx:min(len(returns), idx+window)].sum()
            
            transition_analysis.append({
                **trans,
                "return_before_5d": round(float(before), 4),
                "return_after_5d": round(float(after), 4),
                "regime_change_impact": round(float(after - before), 4)
            })
        except:
            pass
    
    # Transition matrix
    transition_matrix = {}
    for trans in transitions:
        key = f"{trans['from_regime']}_to_{trans['to_regime']}"
        transition_matrix[key] = transition_matrix.get(key, 0) + 1
    
    return {
        "total_transitions": len(transitions),
        "transition_frequency_per_year": len(transitions) / max(1, len(regime_series) / 252),
        "transition_matrix": transition_matrix,
        "recent_transitions": transition_analysis[-10:],
        "most_common_transition": max(transition_matrix.items(), key=lambda x: x[1])[0] if transition_matrix else None
    }


# -----------------------------------------------------------------------------
# BAYESIAN OPTIMIZATION (Phase 10)
# -----------------------------------------------------------------------------

def bayesian_optimize(
    strategy: Dict,
    param_ranges: Dict[str, Tuple[float, float]],
    start_date: str,
    end_date: str,
    n_iterations: int = 20,
    objective: str = "sharpe"
) -> Dict[str, Any]:
    """
    Simple Bayesian-inspired optimization using Gaussian process approximation.
    
    Uses a simplified approach without sklearn dependency.
    """
    results = []
    best_params = None
    best_score = float('-inf')
    
    # Initial random exploration
    n_explore = min(5, n_iterations // 3)
    
    for i in range(n_iterations):
        # Generate candidate parameters
        if i < n_explore:
            # Random exploration
            params = {k: np.random.uniform(v[0], v[1]) for k, v in param_ranges.items()}
        else:
            # Exploitation: sample near best + some exploration
            if best_params:
                params = {}
                for k, (low, high) in param_ranges.items():
                    # 70% near best, 30% exploration
                    if np.random.random() < 0.7:
                        noise = (high - low) * 0.1 * np.random.randn()
                        params[k] = np.clip(best_params[k] + noise, low, high)
                    else:
                        params[k] = np.random.uniform(low, high)
            else:
                params = {k: np.random.uniform(v[0], v[1]) for k, v in param_ranges.items()}
        
        # Update strategy with params
        test_strategy = strategy.copy()
        for ind in test_strategy.get("indicators", []):
            for param_name, param_val in params.items():
                if param_name in ind.get("params", {}):
                    ind["params"][param_name] = int(param_val) if isinstance(ind["params"][param_name], int) else param_val
        
        # Run backtest
        try:
            result = run_backtest(test_strategy, start_date, end_date)
            if "error" not in result:
                metrics = result.get("metrics", {})
                if objective == "sharpe":
                    score = metrics.get("sharpe_ratio", 0)
                elif objective == "return":
                    score = metrics.get("total_return", 0)
                elif objective == "calmar":
                    dd = metrics.get("max_drawdown", 0.01)
                    ret = metrics.get("annual_return", 0)
                    score = ret / dd if dd > 0 else 0
                else:
                    score = metrics.get("sharpe_ratio", 0)
                
                results.append({
                    "iteration": i + 1,
                    "params": {k: round(v, 4) for k, v in params.items()},
                    "score": round(float(score), 4),
                    "is_best": score > best_score
                })
                
                if score > best_score:
                    best_score = score
                    best_params = params.copy()
        except:
            pass
    
    return {
        "best_params": {k: round(v, 4) for k, v in best_params.items()} if best_params else {},
        "best_score": round(float(best_score), 4),
        "iterations": results,
        "convergence_history": [r["score"] for r in results],
        "method": "bayesian_inspired",
        "exploration_ratio": n_explore / n_iterations
    }


# -----------------------------------------------------------------------------
# SURVIVAL PROBABILITY & LIFESPAN (Phase 11)
# -----------------------------------------------------------------------------

def calculate_survival_probability(
    walk_forward_results: List[Dict],
    min_sharpe: float = 0.5
) -> Dict[str, Any]:
    """
    Calculate probability that strategy survives N periods.
    
    Based on walk-forward analysis results.
    """
    if not walk_forward_results:
        return {"error": "No walk-forward data"}
    
    # Calculate survival at each period
    survivals = []
    for i, window in enumerate(walk_forward_results):
        sharpe = window.get("out_sample_sharpe", window.get("sharpe", 0))
        survivals.append(sharpe >= min_sharpe)
    
    # Survival curve
    n = len(survivals)
    survival_curve = []
    cumulative_survival = 1.0
    
    for i, survived in enumerate(survivals):
        if survived:
            survival_rate = 1.0
        else:
            survival_rate = 0.0
        cumulative_survival *= (1 - (1 - survival_rate) * 0.5)  # Partial failure
        survival_curve.append({
            "period": i + 1,
            "survival_prob": round(cumulative_survival, 3)
        })
    
    # Estimate lifespan (periods until 50% survival probability)
    lifespan_50 = next((i+1 for i, s in enumerate(survival_curve) if s["survival_prob"] < 0.5), n)
    
    # Failure analysis
    failures = [i+1 for i, s in enumerate(survivals) if not s]
    
    return {
        "survival_curve": survival_curve,
        "final_survival_prob": round(float(cumulative_survival), 3),
        "median_lifespan_periods": lifespan_50,
        "failure_periods": failures,
        "failure_rate": round(len(failures) / n, 3),
        "interpretation": (
            "Very robust" if cumulative_survival > 0.8 else
            "Robust" if cumulative_survival > 0.6 else
            "Moderate" if cumulative_survival > 0.4 else
            "Fragile" if cumulative_survival > 0.2 else
            "Very fragile"
        )
    }


# -----------------------------------------------------------------------------
# CACHING LAYER (Phase 16)
# -----------------------------------------------------------------------------

# Simple in-memory cache
_indicator_cache = {}
_cache_max_size = 1000


def get_cached_indicator(cache_key: str) -> Optional[pd.Series]:
    """Get indicator from cache."""
    return _indicator_cache.get(cache_key)


def set_cached_indicator(cache_key: str, data: pd.Series):
    """Store indicator in cache."""
    global _indicator_cache
    if len(_indicator_cache) >= _cache_max_size:
        # Remove oldest entries
        keys = list(_indicator_cache.keys())[:len(_indicator_cache)//2]
        for k in keys:
            del _indicator_cache[k]
    _indicator_cache[cache_key] = data


def clear_indicator_cache():
    """Clear indicator cache."""
    global _indicator_cache
    _indicator_cache = {}


def compute_indicator_cached(
    indicator_type: str,
    data: pd.Series,
    params: Dict
) -> pd.Series:
    """Compute indicator with caching."""
    # Generate cache key
    cache_key = f"{indicator_type}_{hash(str(data.index[0]))}_{hash(str(data.index[-1]))}_{str(params)}"
    
    cached = get_cached_indicator(cache_key)
    if cached is not None:
        return cached
    
    # Compute
    if indicator_type == "sma":
        result = IndicatorLibrary.sma(data, params.get("period", 20))
    elif indicator_type == "ema":
        result = IndicatorLibrary.ema(data, params.get("period", 20))
    elif indicator_type == "rsi":
        result = IndicatorLibrary.rsi(data, params.get("period", 14))
    else:
        result = data
    
    set_cached_indicator(cache_key, result)
    return result


# -----------------------------------------------------------------------------
# RESULT SNAPSHOTS & EXPERIMENT TRACKING (Phase 16)
# -----------------------------------------------------------------------------

_experiment_history = []


def save_experiment_snapshot(
    strategy: Dict,
    result: Dict,
    tags: Optional[List[str]] = None
) -> Dict[str, Any]:
    """
    Save experiment snapshot for comparison.
    """
    import hashlib
    import json
    
    snapshot = {
        "id": hashlib.sha256(f"{datetime.now().isoformat()}{json.dumps(strategy, default=str)}".encode()).hexdigest()[:12],
        "timestamp": datetime.now().isoformat(),
        "strategy_name": strategy.get("name", "Unnamed"),
        "strategy_hash": hashlib.sha256(json.dumps(strategy, sort_keys=True, default=str).encode()).hexdigest()[:8],
        "metrics_summary": {
            "sharpe": result.get("metrics", {}).get("risk_adjusted", {}).get("sharpe_ratio", 0),
            "return": result.get("metrics", {}).get("returns", {}).get("total_return", 0),
            "max_dd": result.get("metrics", {}).get("risk", {}).get("max_drawdown", 0)
        },
        "trade_count": len(result.get("trades", [])),
        "tags": tags or []
    }
    
    _experiment_history.append(snapshot)
    
    # Keep last 100 experiments
    if len(_experiment_history) > 100:
        _experiment_history.pop(0)
    
    return snapshot


def get_experiment_history(tags_filter: Optional[List[str]] = None) -> List[Dict]:
    """Get experiment history, optionally filtered by tags."""
    if tags_filter:
        return [e for e in _experiment_history if any(t in e.get("tags", []) for t in tags_filter)]
    return _experiment_history


def compare_experiments(exp_ids: List[str]) -> Dict[str, Any]:
    """Compare multiple experiments."""
    experiments = [e for e in _experiment_history if e["id"] in exp_ids]
    
    if len(experiments) < 2:
        return {"error": "Need at least 2 experiments to compare"}
    
    comparison = {
        "experiments": experiments,
        "best_by_sharpe": max(experiments, key=lambda x: x["metrics_summary"]["sharpe"])["id"],
        "best_by_return": max(experiments, key=lambda x: x["metrics_summary"]["return"])["id"],
        "lowest_drawdown": min(experiments, key=lambda x: x["metrics_summary"]["max_dd"])["id"]
    }
    
    return comparison

