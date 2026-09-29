"""
Strategy Engine - Institutional-Grade Backtesting & Strategy Management
Features: Event-driven backtesting, slippage models, MAE/MFE, R-Multiple, comprehensive metrics
"""
import numpy as np
import pandas as pd
from datetime import datetime, timedelta
from typing import List, Dict, Any, Optional, Tuple
from dataclasses import dataclass, field, asdict
from enum import Enum
import hashlib
import json
import logging
import yfinance as yf
import math

logger = logging.getLogger(__name__)


# =============================================================================
# DATA CLASSES FOR INSTITUTIONAL-GRADE TRACKING
# =============================================================================

class EventType(Enum):
    MARKET = "market"
    SIGNAL = "signal"
    ORDER = "order"
    FILL = "fill"
    STOP = "stop"
    END_OF_BAR = "eob"
    END_OF_DAY = "eod"


@dataclass
class Trade:
    """Complete trade record with MAE/MFE and R-Multiple"""
    trade_id: int
    symbol: str
    side: str  # long or short
    entry_date: str
    entry_price: float
    entry_reason: str
    exit_date: str = None
    exit_price: float = 0.0
    exit_reason: str = ""
    quantity: int = 0
    gross_pnl: float = 0.0
    commission: float = 0.0
    slippage: float = 0.0
    net_pnl: float = 0.0
    return_pct: float = 0.0
    duration_days: int = 0
    mae: float = 0.0  # Maximum Adverse Excursion
    mae_pct: float = 0.0
    mfe: float = 0.0  # Maximum Favorable Excursion
    mfe_pct: float = 0.0
    r_multiple: float = 0.0
    initial_risk: float = 0.0
    outcome: str = ""  # big_win, small_win, small_loss, big_loss
    flags: List[str] = field(default_factory=list)
    
    def to_dict(self):
        return asdict(self)


@dataclass
class Position:
    """Active position with tracking"""
    symbol: str
    quantity: int
    entry_price: float
    entry_date: datetime
    entry_idx: int
    side: str
    entry_reason: str
    stop_price: float = 0.0
    initial_stop: float = 0.0
    trailing_activated: bool = False
    highest_price: float = 0.0
    lowest_price: float = 0.0
    unrealized_pnl: float = 0.0


@dataclass
class ExecutionConfig:
    """Execution parameters for backtesting"""
    commission_model: str = "fixed"  # fixed, percent, tiered
    commission_fixed: float = 1.0
    commission_percent: float = 0.0005
    slippage_model: str = "fixed"  # fixed, volatility, impact
    slippage_bps: float = 5.0
    slippage_vol_coefficient: float = 50.0
    fill_model: str = "close"  # close, open, limit
    max_participation: float = 0.10
    partial_fills: bool = False


@dataclass
class RiskConfig:
    """Risk management configuration"""
    stop_type: str = "percent"  # percent, atr, trailing
    stop_percent: float = 0.02
    atr_multiple: float = 2.5
    trailing_activation: float = 0.02
    take_profit: float = 0.06
    daily_loss_limit: float = 0.05
    max_positions: int = 10
    max_exposure: float = 1.0


# =============================================================================
# SLIPPAGE & COMMISSION MODELS (Per Specification)
# =============================================================================

class CostModel:
    """Transaction cost calculations per specification"""
    
    @staticmethod
    def calculate_commission(notional: float, config: ExecutionConfig) -> float:
        if config.commission_model == "fixed":
            return config.commission_fixed
        elif config.commission_model == "percent":
            return notional * config.commission_percent
        elif config.commission_model == "tiered":
            if notional < 10000:
                return notional * 0.001  # 10 bps
            elif notional < 100000:
                return notional * 0.0005  # 5 bps
            else:
                return notional * 0.0003  # 3 bps
        return config.commission_fixed
    
    @staticmethod
    def calculate_slippage(price: float, config: ExecutionConfig, 
                          volatility: float = 0.02, participation: float = 0.01,
                          spread: float = 0.001) -> float:
        """Calculate slippage in price terms"""
        if config.slippage_model == "fixed":
            return price * (config.slippage_bps / 10000)
        elif config.slippage_model == "volatility":
            # Base + volatility adjustment
            bps = 2 + (config.slippage_vol_coefficient * volatility)
            return price * (bps / 10000)
        elif config.slippage_model == "impact":
            # Market impact model: a + b*vol + c*participation + d*spread
            a, b, c, d = 2, 50, 100, 20
            bps = a + b * volatility + c * participation + d * spread
            return price * (bps / 10000)
        return price * (config.slippage_bps / 10000)


# =============================================================================
# METRICS CALCULATOR (Per Specification Formulas)
# =============================================================================

class MetricsCalculator:
    """Calculate all performance metrics per specification - Institutional Grade"""
    
    @staticmethod
    def calculate_returns(equity_series: pd.Series) -> pd.Series:
        """Simple returns"""
        return equity_series.pct_change().dropna()
    
    @staticmethod
    def calculate_log_returns(equity_series: pd.Series) -> pd.Series:
        """Log returns - additive property"""
        return np.log(equity_series / equity_series.shift(1)).dropna()
    
    @staticmethod
    def calculate_sharpe(returns: pd.Series, rf: float = 0.0, adjusted: bool = True) -> float:
        """
        Annualized Sharpe Ratio with institutional improvements.
        
        Uses sample std (ddof=1) for unbiased estimation.
        Optional Newey-West adjustment for autocorrelation.
        """
        if len(returns) < 2:
            return 0.0
        
        # Use sample std (ddof=1) for unbiased estimation
        std = returns.std(ddof=1)
        if std == 0:
            return 0.0
        
        excess_returns = returns - rf/252
        raw_sharpe = float((excess_returns.mean() * 252) / (std * np.sqrt(252)))
        
        if adjusted and len(returns) > 20:
            # Newey-West style adjustment for autocorrelation
            # Approximation: SR_adjusted = SR * sqrt((1 - rho1) / (1 + rho1))
            try:
                rho1 = returns.autocorr(lag=1)
                if not np.isnan(rho1) and abs(rho1) < 0.99:
                    adjustment = np.sqrt((1 - rho1) / (1 + rho1 + 0.001))
                    raw_sharpe *= min(1.2, max(0.5, adjustment))  # Bound adjustment
            except:
                pass
        
        return float(raw_sharpe)
    
    @staticmethod
    def calculate_sharpe_confidence_interval(returns: pd.Series, confidence: float = 0.95) -> Dict[str, float]:
        """
        Calculate confidence interval for Sharpe ratio using bootstrap.
        """
        if len(returns) < 30:
            sharpe = MetricsCalculator.calculate_sharpe(returns)
            return {"point_estimate": sharpe, "lower": sharpe, "upper": sharpe, "std_error": 0}
        
        n_bootstrap = 1000
        sharpes = []
        
        for _ in range(n_bootstrap):
            sample = returns.sample(n=len(returns), replace=True)
            sharpes.append(MetricsCalculator.calculate_sharpe(sample, adjusted=False))
        
        sharpes = np.array(sharpes)
        alpha = 1 - confidence
        
        return {
            "point_estimate": float(np.mean(sharpes)),
            "lower": float(np.percentile(sharpes, alpha/2 * 100)),
            "upper": float(np.percentile(sharpes, (1 - alpha/2) * 100)),
            "std_error": float(np.std(sharpes))
        }
    
    @staticmethod
    def calculate_sortino(returns: pd.Series, rf: float = 0.0) -> float:
        """Sortino Ratio - downside deviation with sample std"""
        if len(returns) < 2:
            return 0.0
        excess_returns = returns - rf/252
        downside = returns[returns < 0]
        # Use sample std (ddof=1)
        downside_std = downside.std(ddof=1) * np.sqrt(252) if len(downside) > 1 else returns.std(ddof=1) * np.sqrt(252)
        if downside_std == 0 or np.isnan(downside_std):
            return 0.0
        return float((excess_returns.mean() * 252) / downside_std)
    
    @staticmethod
    def calculate_calmar(annual_return: float, max_dd: float) -> float:
        """Calmar Ratio"""
        if max_dd == 0:
            return 0.0
        return float(annual_return / abs(max_dd))
    
    @staticmethod
    def calculate_max_drawdown(equity_series: pd.Series) -> Tuple[float, int, int]:
        """Max drawdown with duration"""
        if len(equity_series) < 2:
            return 0.0, 0, 0
        
        rolling_max = equity_series.cummax()
        drawdown = (equity_series - rolling_max) / rolling_max
        max_dd = float(drawdown.min())
        
        # Find drawdown duration
        in_drawdown = drawdown < 0
        dd_groups = (~in_drawdown).cumsum()
        dd_lengths = in_drawdown.groupby(dd_groups).sum()
        max_duration = int(dd_lengths.max()) if len(dd_lengths) > 0 else 0
        
        return abs(max_dd), max_duration, 0
    
    @staticmethod
    def calculate_var(returns: pd.Series, confidence: float = 0.95, method: str = "historical") -> float:
        """
        Value at Risk with multiple methods.
        
        method: 'historical', 'parametric', or 'cornish_fisher'
        """
        if len(returns) < 10:
            return 0.0
        
        if method == "historical":
            return float(-np.percentile(returns, (1 - confidence) * 100))
        
        elif method == "parametric":
            # Assume normal distribution
            from scipy.stats import norm
            mu = returns.mean()
            sigma = returns.std(ddof=1)
            z = norm.ppf(1 - confidence)
            return float(-(mu + z * sigma))
        
        elif method == "cornish_fisher":
            # Adjust for skewness and kurtosis
            from scipy.stats import norm
            mu = returns.mean()
            sigma = returns.std(ddof=1)
            skew = returns.skew()
            kurt = returns.kurtosis()
            z = norm.ppf(1 - confidence)
            
            # Cornish-Fisher expansion
            z_cf = z + (z**2 - 1) * skew / 6 + (z**3 - 3*z) * (kurt - 3) / 24 - (2*z**3 - 5*z) * skew**2 / 36
            return float(-(mu + z_cf * sigma))
        
        return float(-np.percentile(returns, (1 - confidence) * 100))
    
    @staticmethod
    def calculate_cvar(returns: pd.Series, confidence: float = 0.95) -> float:
        """Conditional VaR (Expected Shortfall)"""
        var = MetricsCalculator.calculate_var(returns, confidence, method="historical")
        tail_returns = returns[returns <= -var]
        if len(tail_returns) == 0:
            return var
        return float(-tail_returns.mean())
    
    @staticmethod
    def calculate_omega(returns: pd.Series, threshold: float = 0.0) -> float:
        """Omega Ratio"""
        gains = returns[returns > threshold].sum()
        losses = abs(returns[returns <= threshold].sum())
        if losses == 0:
            return 0.0
        return float(gains / losses)
    
    @staticmethod
    def calculate_information_ratio(returns: pd.Series, benchmark_returns: pd.Series) -> float:
        """Information Ratio - risk-adjusted alpha"""
        if len(returns) < 2 or len(benchmark_returns) < 2:
            return 0.0
        
        # Align series
        aligned = pd.concat([returns, benchmark_returns], axis=1).dropna()
        if len(aligned) < 2:
            return 0.0
        
        excess = aligned.iloc[:, 0] - aligned.iloc[:, 1]
        te = excess.std(ddof=1)
        
        if te == 0:
            return 0.0
        
        return float((excess.mean() * 252) / (te * np.sqrt(252)))

    
    @staticmethod
    def calculate_trade_metrics(trades: List[Trade]) -> Dict[str, Any]:
        """Calculate trade-level statistics"""
        if not trades:
            return {}
        
        pnls = [t.net_pnl for t in trades]
        winners = [t for t in trades if t.net_pnl > 0]
        losers = [t for t in trades if t.net_pnl <= 0]
        
        return {
            "total_trades": len(trades),
            "winners": len(winners),
            "losers": len(losers),
            "win_rate": len(winners) / len(trades) if trades else 0,
            "avg_win": np.mean([t.net_pnl for t in winners]) if winners else 0,
            "avg_loss": np.mean([t.net_pnl for t in losers]) if losers else 0,
            "largest_win": max([t.net_pnl for t in winners]) if winners else 0,
            "largest_loss": min([t.net_pnl for t in losers]) if losers else 0,
            "profit_factor": abs(sum(t.net_pnl for t in winners) / sum(t.net_pnl for t in losers)) if losers and sum(t.net_pnl for t in losers) != 0 else 0,
            "expectancy": np.mean(pnls) if pnls else 0,
            "avg_duration": np.mean([t.duration_days for t in trades]) if trades else 0,
            "avg_mae": np.mean([t.mae for t in trades]) if trades else 0,
            "avg_mfe": np.mean([t.mfe for t in trades]) if trades else 0,
            "avg_r_multiple": np.mean([t.r_multiple for t in trades if t.r_multiple != 0]) if trades else 0,
        }
    
    @staticmethod
    def calculate_streaks(trades: List[Trade]) -> Dict[str, int]:
        """Win/loss streak analysis"""
        if not trades:
            return {"max_win_streak": 0, "max_loss_streak": 0, "current_streak": 0}
        
        max_win = max_loss = current = 0
        in_win = None
        
        for t in trades:
            if t.net_pnl > 0:
                if in_win == True:
                    current += 1
                else:
                    max_loss = max(max_loss, abs(current))
                    current = 1
                    in_win = True
                max_win = max(max_win, current)
            else:
                if in_win == False:
                    current -= 1
                else:
                    max_win = max(max_win, current)
                    current = -1
                    in_win = False
                max_loss = max(max_loss, abs(current))
        
        return {
            "max_win_streak": max_win,
            "max_loss_streak": max_loss,
            "current_streak": current
        }


# =============================================================================
# EVENT-DRIVEN BACKTESTING ENGINE (Per Specification)
# =============================================================================

class BacktestEngine:
    """Institutional-grade event-driven backtesting engine"""
    
    def __init__(self, strategy: Dict, execution_config: ExecutionConfig = None,
                 risk_config: RiskConfig = None):
        self.strategy = strategy
        self.exec_config = execution_config or ExecutionConfig()
        self.risk_config = risk_config or RiskConfig()
        
        self.cash = 0.0
        self.initial_capital = 0.0
        self.positions: Dict[str, Position] = {}
        self.trades: List[Trade] = []
        self.equity_curve: List[Dict] = []
        self.trade_counter = 0
        
        # Daily tracking for kill switch
        self.start_of_day_equity = 0.0
        self.trading_blocked = False
        
        # Indicator cache
        self.indicators: Dict[str, Dict] = {}
        self.price_data: pd.DataFrame = None
    
    def run(self, start_date: str, end_date: str, initial_capital: float = 100000,
            benchmark: str = None) -> Dict[str, Any]:
        """Run complete backtest simulation"""
        
        self.cash = initial_capital
        self.initial_capital = initial_capital
        self.start_of_day_equity = initial_capital
        
        universe = self.strategy.get("universe", ["SPY"])
        indicators_config = self.strategy.get("indicators", [])
        entry_rules = self.strategy.get("entry_rules", {})
        exit_rules = self.strategy.get("exit_rules", {})
        
        # Calculate warmup
        max_period = max([
            p.get("default", p) if isinstance(p, dict) else p
            for ind in indicators_config
            for p in ind.get("params", {}).values()
            if isinstance(p, (int, float))
        ] or [20])
        warmup = max(max_period + 20, 60)
        
        # Fetch data with warmup buffer
        fetch_start = (datetime.strptime(start_date, "%Y-%m-%d") - timedelta(days=warmup + 30)).strftime("%Y-%m-%d")
        self.price_data = self._fetch_data(universe, fetch_start, end_date)
        
        if self.price_data.empty:
            return {"error": "Failed to fetch price data"}
        
        # Compute indicators
        for symbol in universe:
            self.indicators[symbol] = self._compute_indicators(symbol, indicators_config)
        
        # Find trading start index
        trading_start_idx = warmup
        for i, dt in enumerate(self.price_data.index):
            if dt.strftime("%Y-%m-%d") >= start_date:
                trading_start_idx = max(i, warmup)
                break
        
        # Main simulation loop
        prev_date = None
        for i in range(trading_start_idx, len(self.price_data)):
            current_date = self.price_data.index[i]
            
            # End of day processing
            if prev_date and current_date.date() != prev_date.date():
                self._process_end_of_day(prev_date)
            
            if self.trading_blocked:
                prev_date = current_date
                continue
            
            # Update portfolio value
            portfolio_value = self._calculate_portfolio_value(i)
            
            # Check exits
            self._check_exits(i, current_date, exit_rules)
            
            # Check entries
            if len(self.positions) < self.risk_config.max_positions:
                self._check_entries(i, current_date, entry_rules, universe, portfolio_value)
            
            # Update trailing stops
            self._update_trailing_stops(i)
            
            # Record equity
            self.equity_curve.append({
                "date": current_date.isoformat(),
                "equity": float(portfolio_value),
                "cash": float(self.cash),
                "positions": len(self.positions),
                "exposure": self._calculate_exposure(i)
            })
            
            prev_date = current_date
        
        # Close remaining positions
        if self.positions:
            last_idx = len(self.price_data) - 1
            last_date = self.price_data.index[last_idx]
            for symbol in list(self.positions.keys()):
                self._close_position(symbol, last_idx, last_date, "end_of_backtest")
        
        # Calculate metrics
        return self._generate_results(start_date, end_date, benchmark)
    
    def _fetch_data(self, symbols: List[str], start: str, end: str) -> pd.DataFrame:
        """Fetch OHLCV data using high-speed Parquet engine with fallback."""
        try:
            from app.services.robust_data_fetcher import get_batch_data
            
            # Calculate approximate period for RDF
            if isinstance(start, str):
                start_dt = datetime.strptime(start, "%Y-%m-%d")
            else:
                start_dt = start
                
            days = (datetime.now() - start_dt).days + 60 # Extra buffer
            if days <= 30: period = "1mo"
            elif days <= 90: period = "3mo"
            elif days <= 185: period = "6mo"
            elif days <= 370: period = "1y"
            elif days <= 740: period = "2y"
            else: period = "5y"
            
            logger.info(f"[StrategyEngine] Fetching {len(symbols)} symbols for {period}")
            
            # Use RDF (which now uses Parquet + CSV first)
            batch = get_batch_data(symbols, period=period)
            
            if batch:
                all_dfs = []
                for sym, df in batch.items():
                    if df is not None and not df.empty:
                        # Clean labels to match YF structure expected by engine
                        # RDF usually returns Open, High, Low, Close, Volume
                        # Ensure we filter to the exact start/end range
                        # Handle timezone alignment for filtering
                        df_idx = df.index
                        target_start = pd.to_datetime(start)
                        target_end = pd.to_datetime(end)
                        
                        if df_idx.tz is not None:
                            if target_start.tz is None: target_start = target_start.tz_localize('UTC')
                            if target_end.tz is None: target_end = target_end.tz_localize('UTC')
                        
                        mask = (df_idx >= target_start) & (df_idx <= target_end)
                        df_filtered = df.loc[mask].copy()
                        
                        if not df_filtered.empty:
                            # Convert to MultiIndex columns: (Attribute, Symbol)
                            df_filtered.columns = pd.MultiIndex.from_product([df_filtered.columns, [sym]])
                            all_dfs.append(df_filtered)
                
                if all_dfs:
                    combined = pd.concat(all_dfs, axis=1)
                    # Handle possible duplicates on index
                    combined = combined[~combined.index.duplicated(keep='first')]
                    logger.info(f"[StrategyEngine] Parquet/RDF success: {len(combined)} bars")
                    return combined

            # Strategy Engine fallback (legacy)
            logger.warning(f"[StrategyEngine] RDF failed, falling back to direct yfinance for {symbols}")
            data = yf.download(
                symbols if len(symbols) > 1 else symbols[0],
                start=start, end=end,
                auto_adjust=True, progress=False
            )
            if data.empty:
                return pd.DataFrame()
            if not isinstance(data.columns, pd.MultiIndex) and len(symbols) == 1:
                data.columns = pd.MultiIndex.from_product([data.columns, symbols])
            return data
        except Exception as e:
            logger.error(f"Strategy data fetch error: {e}")
            return pd.DataFrame()
    
    def _compute_indicators(self, symbol: str, configs: List[Dict]) -> Dict[str, pd.Series]:
        """Compute indicators for symbol"""
        from .strategy_research import IndicatorLibrary
        
        results = {}
        try:
            close = self.price_data[("Close", symbol)]
            high = self.price_data[("High", symbol)]
            low = self.price_data[("Low", symbol)]
            volume = self.price_data[("Volume", symbol)]
            
            for ind in configs:
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
                    m = IndicatorLibrary.macd(close, params.get("fast", 12), params.get("slow", 26), params.get("signal", 9))
                    results[f"{ind_id}.macd"] = m["macd"]
                    results[f"{ind_id}.signal"] = m["signal"]
                elif ind_type == "bollinger":
                    bb = IndicatorLibrary.bollinger_bands(close, params.get("period", 20), params.get("std_dev", 2.0))
                    results[f"{ind_id}.upper"] = bb["upper"]
                    results[f"{ind_id}.middle"] = bb["middle"]
                    results[f"{ind_id}.lower"] = bb["lower"]
                elif ind_type == "atr":
                    results[ind_id] = IndicatorLibrary.atr(high, low, close, params.get("period", 14))
                elif ind_type == "roc":
                    results[ind_id] = IndicatorLibrary.roc(close, params.get("period", 10))
                elif ind_type == "momentum":
                    results[ind_id] = IndicatorLibrary.momentum(close, params.get("period", 10))
            
            results["close"] = close
            results["high"] = high
            results["low"] = low
            results["volume"] = volume
            
        except Exception as e:
            logger.error(f"Indicator error for {symbol}: {e}")
        
        return results
    
    def _evaluate_condition(self, condition: str, indicators: Dict, idx: int) -> bool:
        """Evaluate trading condition"""
        try:
            local_vars = {}
            for key, series in indicators.items():
                if idx < len(series):
                    val = series.iloc[idx]
                    local_vars[key.replace(".", "_")] = float(val) if not pd.isna(val) else 0
                    if idx > 0:
                        prev = series.iloc[idx-1]
                        local_vars[f"{key.replace('.', '_')}_1"] = float(prev) if not pd.isna(prev) else 0
            
            eval_cond = condition
            for key in indicators.keys():
                eval_cond = eval_cond.replace(f"{key}[1]", f"{key.replace('.', '_')}_1")
                eval_cond = eval_cond.replace(key, key.replace(".", "_"))
            eval_cond = eval_cond.replace("AND", "and").replace("OR", "or")
            
            return eval(eval_cond, {"__builtins__": {}}, local_vars)
        except:
            return False
    
    def _calculate_portfolio_value(self, idx: int) -> float:
        """Calculate current portfolio value"""
        value = self.cash
        for sym, pos in self.positions.items():
            try:
                price = float(self.price_data[("Close", sym)].iloc[idx])
                value += pos.quantity * price if pos.side == "long" else -pos.quantity * price
            except:
                pass
        return value
    
    def _calculate_exposure(self, idx: int) -> float:
        """Calculate gross exposure"""
        if not self.positions:
            return 0.0
        exposure = sum(
            abs(pos.quantity * float(self.price_data[("Close", sym)].iloc[idx]))
            for sym, pos in self.positions.items()
        )
        equity = self._calculate_portfolio_value(idx)
        return exposure / equity if equity > 0 else 0.0
    
    def _check_entries(self, idx: int, date: datetime, rules: Dict, 
                       universe: List[str], portfolio_value: float):
        """Check for entry signals"""
        entry_rule = rules.get("long", "")
        if not entry_rule:
            return
        
        for symbol in universe:
            if symbol in self.positions:
                continue
            
            if self._evaluate_condition(entry_rule, self.indicators[symbol], idx):
                self._open_position(symbol, idx, date, portfolio_value, "signal_entry")
    
    def _open_position(self, symbol: str, idx: int, date: datetime, 
                       portfolio_value: float, reason: str):
        """Open new position with proper sizing"""
        try:
            price = float(self.price_data[("Close", symbol)].iloc[idx])
            
            # Position sizing
            position_value = portfolio_value / self.risk_config.max_positions
            
            # Apply slippage
            slippage = CostModel.calculate_slippage(price, self.exec_config)
            fill_price = price + slippage  # Buying higher
            
            # Calculate shares
            shares = int(position_value / fill_price)
            if shares <= 0:
                return
            
            # Calculate costs
            notional = shares * fill_price
            commission = CostModel.calculate_commission(notional, self.exec_config)
            total_cost = notional + commission
            
            if total_cost > self.cash:
                shares = int((self.cash - commission) / fill_price)
                if shares <= 0:
                    return
                notional = shares * fill_price
                total_cost = notional + commission
            
            self.cash -= total_cost
            
            # Calculate stop
            atr_val = self.indicators[symbol].get("atr", pd.Series([0]))
            atr = float(atr_val.iloc[idx]) if idx < len(atr_val) and not pd.isna(atr_val.iloc[idx]) else price * 0.02
            
            if self.risk_config.stop_type == "atr":
                stop_distance = self.risk_config.atr_multiple * atr
            else:
                stop_distance = fill_price * self.risk_config.stop_percent
            
            stop_price = fill_price - stop_distance
            
            self.positions[symbol] = Position(
                symbol=symbol,
                quantity=shares,
                entry_price=fill_price,
                entry_date=date,
                entry_idx=idx,
                side="long",
                entry_reason=reason,
                stop_price=stop_price,
                initial_stop=stop_price,
                highest_price=fill_price,
                lowest_price=fill_price
            )
            
        except Exception as e:
            logger.error(f"Entry error for {symbol}: {e}")
    
    def _check_exits(self, idx: int, date: datetime, rules: Dict):
        """Check for exit conditions"""
        exit_rule = rules.get("long", "")
        
        for symbol in list(self.positions.keys()):
            pos = self.positions[symbol]
            try:
                price = float(self.price_data[("Close", symbol)].iloc[idx])
                
                # Update tracking
                pos.highest_price = max(pos.highest_price, price)
                pos.lowest_price = min(pos.lowest_price, price)
                pos.unrealized_pnl = (price - pos.entry_price) * pos.quantity
                
                pnl_pct = (price - pos.entry_price) / pos.entry_price
                
                # Stop loss
                if price <= pos.stop_price:
                    self._close_position(symbol, idx, date, "stop_loss")
                    continue
                
                # Take profit
                if pnl_pct >= self.risk_config.take_profit:
                    self._close_position(symbol, idx, date, "take_profit")
                    continue
                
                # Signal exit
                if exit_rule and self._evaluate_condition(exit_rule, self.indicators[symbol], idx):
                    self._close_position(symbol, idx, date, "signal_exit")
                    continue
                    
            except Exception as e:
                logger.error(f"Exit check error for {symbol}: {e}")
    
    def _close_position(self, symbol: str, idx: int, date: datetime, reason: str):
        """Close position and record trade"""
        if symbol not in self.positions:
            return
        
        pos = self.positions[symbol]
        try:
            price = float(self.price_data[("Close", symbol)].iloc[idx])
            
            # Apply slippage
            slippage = CostModel.calculate_slippage(price, self.exec_config)
            fill_price = price - slippage  # Selling lower
            
            # Calculate costs
            notional = pos.quantity * fill_price
            commission = CostModel.calculate_commission(notional, self.exec_config)
            proceeds = notional - commission
            
            self.cash += proceeds
            
            # Calculate PnL
            entry_cost = pos.quantity * pos.entry_price
            gross_pnl = notional - entry_cost
            total_slippage = slippage * pos.quantity * 2  # Entry + exit
            total_commission = commission * 2
            net_pnl = gross_pnl - total_commission
            
            # MAE/MFE
            mae = (pos.lowest_price - pos.entry_price) * pos.quantity
            mfe = (pos.highest_price - pos.entry_price) * pos.quantity
            mae_pct = (pos.lowest_price - pos.entry_price) / pos.entry_price * 100
            mfe_pct = (pos.highest_price - pos.entry_price) / pos.entry_price * 100
            
            # R-Multiple
            initial_risk = abs(pos.entry_price - pos.initial_stop) * pos.quantity
            r_multiple = net_pnl / initial_risk if initial_risk > 0 else 0
            
            # Duration
            duration = (date - pos.entry_date).days if hasattr(date, 'date') else idx - pos.entry_idx
            
            # Outcome classification
            if r_multiple > 2:
                outcome = "big_win"
            elif r_multiple > 0:
                outcome = "small_win"
            elif r_multiple > -1:
                outcome = "small_loss"
            else:
                outcome = "big_loss"
            
            self.trade_counter += 1
            trade = Trade(
                trade_id=self.trade_counter,
                symbol=symbol,
                side="long",
                entry_date=pos.entry_date.isoformat() if hasattr(pos.entry_date, 'isoformat') else str(pos.entry_date),
                entry_price=pos.entry_price,
                entry_reason=pos.entry_reason,
                exit_date=date.isoformat() if hasattr(date, 'isoformat') else str(date),
                exit_price=fill_price,
                exit_reason=reason,
                quantity=pos.quantity,
                gross_pnl=float(gross_pnl),
                commission=float(total_commission),
                slippage=float(total_slippage),
                net_pnl=float(net_pnl),
                return_pct=float((fill_price - pos.entry_price) / pos.entry_price * 100),
                duration_days=duration,
                mae=float(mae),
                mae_pct=float(mae_pct),
                mfe=float(mfe),
                mfe_pct=float(mfe_pct),
                r_multiple=float(r_multiple),
                initial_risk=float(initial_risk),
                outcome=outcome
            )
            
            self.trades.append(trade)
            del self.positions[symbol]
            
        except Exception as e:
            logger.error(f"Close position error for {symbol}: {e}")
    
    def _update_trailing_stops(self, idx: int):
        """Update trailing stops"""
        if self.risk_config.stop_type != "trailing":
            return
        
        for symbol, pos in self.positions.items():
            try:
                price = float(self.price_data[("Close", symbol)].iloc[idx])
                pnl_pct = (price - pos.entry_price) / pos.entry_price
                
                if pnl_pct >= self.risk_config.trailing_activation:
                    pos.trailing_activated = True
                
                if pos.trailing_activated:
                    atr_val = self.indicators[symbol].get("atr", pd.Series([0]))
                    atr = float(atr_val.iloc[idx]) if idx < len(atr_val) else price * 0.02
                    new_stop = price - (self.risk_config.atr_multiple * atr)
                    pos.stop_price = max(pos.stop_price, new_stop)
            except:
                pass
    
    def _process_end_of_day(self, date: datetime):
        """End of day processing - check daily loss limit"""
        current_equity = self._calculate_portfolio_value(len(self.price_data) - 1)
        daily_pnl = current_equity - self.start_of_day_equity
        daily_pnl_pct = daily_pnl / self.start_of_day_equity
        
        if daily_pnl_pct <= -self.risk_config.daily_loss_limit:
            self.trading_blocked = True
            # Close all positions
            for symbol in list(self.positions.keys()):
                self._close_position(symbol, len(self.price_data) - 1, date, "daily_loss_limit")
        
        self.start_of_day_equity = current_equity
        self.trading_blocked = False
    
    def _generate_results(self, start_date: str, end_date: str, 
                          benchmark: str = None) -> Dict[str, Any]:
        """Generate comprehensive results"""
        if not self.equity_curve:
            return {"error": "No equity curve generated"}
        
        equity_values = [e["equity"] for e in self.equity_curve]
        equity_series = pd.Series(equity_values)
        returns = MetricsCalculator.calculate_returns(equity_series)
        
        # Core metrics
        total_return = (equity_values[-1] - self.initial_capital) / self.initial_capital
        annual_return = float(returns.mean() * 252) if len(returns) > 0 else 0
        annual_vol = float(returns.std() * np.sqrt(252)) if len(returns) > 0 else 0
        
        sharpe = MetricsCalculator.calculate_sharpe(returns)
        sortino = MetricsCalculator.calculate_sortino(returns)
        max_dd, dd_duration, _ = MetricsCalculator.calculate_max_drawdown(equity_series)
        calmar = MetricsCalculator.calculate_calmar(annual_return, max_dd)
        omega = MetricsCalculator.calculate_omega(returns)
        var_95 = MetricsCalculator.calculate_var(returns)
        cvar_95 = MetricsCalculator.calculate_cvar(returns)
        
        # Trade metrics
        trade_metrics = MetricsCalculator.calculate_trade_metrics(self.trades)
        streaks = MetricsCalculator.calculate_streaks(self.trades)
        
        # Cost analysis
        total_commission = sum(t.commission for t in self.trades)
        total_slippage = sum(t.slippage for t in self.trades)
        
        # Generate unique hash for reproducibility
        run_hash = hashlib.sha256(
            f"{self.strategy}{start_date}{end_date}{self.initial_capital}".encode()
        ).hexdigest()[:12]
        
        return {
            "equity_curve": self.equity_curve[-500:] if len(self.equity_curve) > 500 else self.equity_curve,
            "trades": [t.to_dict() for t in self.trades],
            "metrics": {
                "returns": {
                    "total_return": float(total_return),
                    "cagr": float(annual_return),
                    "best_day": float(returns.max()) if len(returns) > 0 else 0,
                    "worst_day": float(returns.min()) if len(returns) > 0 else 0,
                    "positive_days": float((returns > 0).mean()) if len(returns) > 0 else 0,
                },
                "risk": {
                    "volatility": float(annual_vol),
                    "max_drawdown": float(max_dd),
                    "max_dd_duration": dd_duration,
                    "var_95": float(var_95),
                    "cvar_95": float(cvar_95),
                },
                "risk_adjusted": {
                    "sharpe_ratio": float(sharpe),
                    "sortino_ratio": float(sortino),
                    "calmar_ratio": float(calmar),
                    "omega_ratio": float(omega),
                    "skew": float(returns.skew()) if len(returns) > 0 else 0,
                    "kurtosis": float(returns.kurtosis()) if len(returns) > 0 else 0,
                },
                "trading": trade_metrics,
                "streaks": streaks,
                "costs": {
                    "total_commission": float(total_commission),
                    "total_slippage": float(total_slippage),
                    "total_costs": float(total_commission + total_slippage),
                    "cost_pct_of_returns": float((total_commission + total_slippage) / (total_return * self.initial_capital)) if total_return > 0 else 0,
                },
                "exposure": {
                    "avg_exposure": np.mean([e.get("exposure", 0) for e in self.equity_curve]) if self.equity_curve else 0,
                    "pct_time_invested": sum(1 for e in self.equity_curve if e["positions"] > 0) / len(self.equity_curve) if self.equity_curve else 0,
                }
            },
            "summary": {
                "start_date": start_date,
                "end_date": end_date,
                "initial_capital": self.initial_capital,
                "final_capital": float(equity_values[-1]),
                "strategy_name": self.strategy.get("name", "Unnamed")
            },
            "reproducibility": {
                "run_hash": run_hash,
                "timestamp": datetime.now().isoformat(),
            }
        }


# =============================================================================
# PUBLIC API FUNCTIONS
# =============================================================================

def run_institutional_backtest(
    strategy: Dict[str, Any],
    start_date: str = None,
    end_date: str = None,
    initial_capital: float = 100000,
    commission_model: str = "fixed",
    commission_value: float = 1.0,
    slippage_model: str = "fixed",
    slippage_bps: float = 5.0,
    stop_type: str = "percent",
    stop_value: float = 0.02,
    atr_multiple: float = 2.5,
    take_profit: float = 0.06,
    daily_loss_limit: float = 0.05,
    max_positions: int = 10,
    benchmark: str = None
) -> Dict[str, Any]:
    """Run institutional-grade backtest with full configuration"""
    
    if not end_date:
        end_date = datetime.now().strftime("%Y-%m-%d")
    if not start_date:
        start_date = (datetime.now() - timedelta(days=365*3)).strftime("%Y-%m-%d")
    
    exec_config = ExecutionConfig(
        commission_model=commission_model,
        commission_fixed=commission_value if commission_model == "fixed" else 1.0,
        commission_percent=commission_value if commission_model == "percent" else 0.0005,
        slippage_model=slippage_model,
        slippage_bps=slippage_bps
    )
    
    risk_config = RiskConfig(
        stop_type=stop_type,
        stop_percent=stop_value if stop_type == "percent" else 0.02,
        atr_multiple=atr_multiple,
        take_profit=take_profit,
        daily_loss_limit=daily_loss_limit,
        max_positions=max_positions
    )
    
    engine = BacktestEngine(strategy, exec_config, risk_config)
    return engine.run(start_date, end_date, initial_capital, benchmark)


# =============================================================================
# INSTITUTIONAL ENHANCEMENTS: ANOMALY DETECTION & QUALITY METRICS
# =============================================================================

def detect_trade_anomalies(trades: List[Trade], avg_slippage_bps: float = 10) -> List[Dict[str, Any]]:
    """
    Detect trade anomalies that may indicate data quality issues or unusual execution.
    
    Flags:
    - high_slippage: Slippage > 3x average
    - gap_fill: Entry/exit on gap (>2% overnight move)
    - extreme_duration: Hold time > 60 days or < 1 day
    - r_outlier: R-Multiple > 5 or < -3
    """
    anomalies = []
    
    for trade in trades:
        flags = []
        
        # High slippage detection
        if trade.slippage > 0:
            implied_bps = (trade.slippage / (trade.entry_price * trade.quantity)) * 10000
            if implied_bps > avg_slippage_bps * 3:
                flags.append({
                    "type": "high_slippage",
                    "severity": "medium",
                    "value": round(implied_bps, 1),
                    "threshold": avg_slippage_bps * 3
                })
        
        # Extreme duration
        if trade.duration_days > 60:
            flags.append({
                "type": "long_hold",
                "severity": "low",
                "value": trade.duration_days,
                "threshold": 60
            })
        elif trade.duration_days < 1 and trade.exit_reason != "stop_loss":
            flags.append({
                "type": "flash_trade",
                "severity": "medium",
                "value": trade.duration_days,
                "threshold": 1
            })
        
        # R-Multiple outliers
        if trade.r_multiple > 5:
            flags.append({
                "type": "extreme_winner",
                "severity": "low",
                "value": round(trade.r_multiple, 2),
                "threshold": 5
            })
        elif trade.r_multiple < -3:
            flags.append({
                "type": "catastrophic_loss",
                "severity": "high",
                "value": round(trade.r_multiple, 2),
                "threshold": -3
            })
        
        if flags:
            anomalies.append({
                "trade_id": trade.trade_id,
                "symbol": trade.symbol,
                "flags": flags,
                "anomaly_count": len(flags)
            })
    
    return anomalies


def calculate_exit_efficiency(trades: List[Trade]) -> Dict[str, Any]:
    """
    Calculate exit efficiency score.
    
    Exit efficiency = how much of the MFE was captured.
    A perfect exit would capture 100% of MFE.
    """
    if not trades:
        return {"score": 0, "interpretation": "No trades"}
    
    efficiencies = []
    for trade in trades:
        if trade.mfe_pct > 0:
            # How much of the max favorable move did we capture?
            captured_pct = trade.return_pct
            efficiency = (captured_pct / trade.mfe_pct) * 100 if trade.mfe_pct > 0 else 0
            efficiencies.append(min(100, max(0, efficiency)))
    
    if not efficiencies:
        return {"score": 0, "interpretation": "No winning trades"}
    
    avg_efficiency = np.mean(efficiencies)
    
    return {
        "score": round(avg_efficiency, 1),
        "median": round(np.median(efficiencies), 1),
        "best": round(max(efficiencies), 1),
        "worst": round(min(efficiencies), 1),
        "interpretation": (
            "Excellent" if avg_efficiency > 80 else
            "Good" if avg_efficiency > 60 else
            "Average" if avg_efficiency > 40 else
            "Poor - exits too early" if avg_efficiency > 20 else
            "Very poor - missing most upside"
        )
    }


def calculate_overfitting_probability(
    in_sample_sharpe: float,
    out_sample_sharpe: float,
    n_parameters: int,
    n_observations: int,
    n_trials: int = 1
) -> Dict[str, Any]:
    """
    Calculate probability of overfitting using the Probability of Backtest Overfitting (PBO).
    
    Based on: Bailey, Borwein, Lopez de Prado, Zhu (2014)
    
    Higher probability = more likely overfit.
    """
    # Deflated Sharpe Ratio approach
    # DSR = Sharpe * sqrt((n - 1) / (1 + 0.5 * skew * Sharpe - (kurtosis-3)/4 * Sharpe^2))
    
    # Simple approximation based on parameter count and sample size
    # More parameters relative to data = higher overfitting risk
    
    param_penalty = n_parameters / max(1, n_observations / 252)  # Parameters per year
    
    # Sharpe degradation
    if in_sample_sharpe > 0 and out_sample_sharpe > 0:
        sharpe_degradation = 1 - (out_sample_sharpe / in_sample_sharpe)
    elif in_sample_sharpe > 0:
        sharpe_degradation = 1.0  # Total degradation
    else:
        sharpe_degradation = 0
    
    # Multiple testing penalty (Bonferroni-like)
    trial_penalty = np.log(max(1, n_trials)) / 10
    
    # Combine factors
    raw_prob = (
        0.3 * min(1.0, param_penalty) +  # Parameter complexity
        0.5 * min(1.0, sharpe_degradation) +  # Performance degradation
        0.2 * min(1.0, trial_penalty)  # Multiple testing
    )
    
    probability = min(0.99, max(0.01, raw_prob))
    
    return {
        "probability": round(probability, 3),
        "probability_pct": round(probability * 100, 1),
        "sharpe_degradation_pct": round(sharpe_degradation * 100, 1),
        "param_complexity": round(param_penalty, 2),
        "interpretation": (
            "Very high overfitting risk" if probability > 0.7 else
            "High overfitting risk" if probability > 0.5 else
            "Moderate risk" if probability > 0.3 else
            "Low risk" if probability > 0.15 else
            "Very low risk - robust strategy"
        ),
        "recommendation": (
            "Do not deploy - likely curve-fitted" if probability > 0.5 else
            "Use caution - validate with more data" if probability > 0.3 else
            "Reasonable to deploy with monitoring"
        )
    }


def calculate_long_short_breakdown(trades: List[Trade]) -> Dict[str, Any]:
    """
    Calculate performance breakdown by long vs short trades.
    """
    long_trades = [t for t in trades if t.side == "long"]
    short_trades = [t for t in trades if t.side == "short"]
    
    def calc_side_metrics(side_trades):
        if not side_trades:
            return {"count": 0, "win_rate": 0, "avg_return": 0, "total_pnl": 0}
        
        winners = [t for t in side_trades if t.net_pnl > 0]
        return {
            "count": len(side_trades),
            "win_rate": round(len(winners) / len(side_trades) * 100, 1),
            "avg_return": round(np.mean([t.return_pct for t in side_trades]), 2),
            "total_pnl": round(sum(t.net_pnl for t in side_trades), 2),
            "avg_duration": round(np.mean([t.duration_days for t in side_trades]), 1),
            "avg_r_multiple": round(np.mean([t.r_multiple for t in side_trades]), 2)
        }
    
    long_metrics = calc_side_metrics(long_trades)
    short_metrics = calc_side_metrics(short_trades)
    
    # Determine which side is stronger
    long_score = (long_metrics["win_rate"] * 0.5 + min(100, long_metrics["avg_return"]) * 0.5) if long_trades else 0
    short_score = (short_metrics["win_rate"] * 0.5 + min(100, short_metrics["avg_return"]) * 0.5) if short_trades else 0
    
    return {
        "long": long_metrics,
        "short": short_metrics,
        "dominant_side": "long" if long_score > short_score else "short" if short_score > long_score else "balanced",
        "recommendation": (
            "Consider long-only strategy" if long_score > short_score * 1.5 else
            "Consider short-only strategy" if short_score > long_score * 1.5 else
            "Both sides contribute value"
        )
    }


def validate_backtest_quality(result: Dict[str, Any]) -> Dict[str, Any]:
    """
    Validate backtest quality and flag potential issues.
    
    Returns quality score and list of concerns.
    """
    concerns = []
    score = 100
    
    trades = result.get("trades", [])
    metrics = result.get("metrics", {})
    equity = result.get("equity_curve", [])
    
    # Check sample size
    if len(trades) < 30:
        concerns.append({
            "type": "low_sample_size",
            "severity": "high",
            "message": f"Only {len(trades)} trades - need 30+ for statistical significance"
        })
        score -= 20
    
    # Check win rate extremes
    win_rate = metrics.get("trading", {}).get("win_rate", 0.5)
    if win_rate > 0.8:
        concerns.append({
            "type": "suspiciously_high_win_rate",
            "severity": "medium",
            "message": f"Win rate of {win_rate:.0%} may indicate lookahead bias"
        })
        score -= 15
    
    # Check Sharpe extremes
    sharpe = metrics.get("risk_adjusted", {}).get("sharpe_ratio", 0)
    if sharpe > 3:
        concerns.append({
            "type": "extreme_sharpe",
            "severity": "high",
            "message": f"Sharpe of {sharpe:.2f} is unrealistically high"
        })
        score -= 25
    
    # Check drawdown
    max_dd = metrics.get("risk", {}).get("max_drawdown", 0)
    if max_dd < 0.01 and len(trades) > 10:
        concerns.append({
            "type": "suspiciously_low_drawdown",
            "severity": "medium",
            "message": f"Max DD of {max_dd:.1%} with {len(trades)} trades is unusual"
        })
        score -= 10
    
    # Check for gaps in equity curve
    if len(equity) > 0:
        dates = [e.get("date", "") for e in equity]
        # Simple check for missing data
        if len(set(dates)) < len(dates) * 0.9:
            concerns.append({
                "type": "duplicate_dates",
                "severity": "low",
                "message": "Equity curve has duplicate dates"
            })
            score -= 5
    
    return {
        "quality_score": max(0, score),
        "interpretation": (
            "Excellent" if score >= 90 else
            "Good" if score >= 70 else
            "Fair - review concerns" if score >= 50 else
            "Poor - significant concerns"
        ),
        "concerns": concerns,
        "is_valid": score >= 50
    }

