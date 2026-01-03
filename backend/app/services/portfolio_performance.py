"""
Portfolio Performance Service - Features 32-33, 44-45
Sharpe/Sortino/Calmar, Drawdowns, Benchmark Comparison, Attribution
"""
import numpy as np
import pandas as pd
from typing import List, Dict, Optional, Any
import yfinance as yf
import logging
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)


# =============================================================================
# HELPER FUNCTIONS
# =============================================================================

def _get_portfolio_returns(positions: List[Dict], period: str = "1y") -> pd.Series:
    """Compute weighted portfolio returns."""
    tickers = [p.get("ticker") for p in positions]
    weights = {p.get("ticker"): p.get("weight", 0) for p in positions}
    
    try:
        data = yf.download(tickers, period=period, progress=False, auto_adjust=True)
        
        if data.empty:
            return pd.Series()
        
        # Get Close prices - handle MultiIndex
        if 'Close' in data.columns:
            close_data = data['Close']
        elif isinstance(data.columns, pd.MultiIndex):
            if 'Close' in data.columns.get_level_values(0):
                close_data = data['Close']
            else:
                close_data = data.iloc[:, :len(tickers)]
        else:
            close_data = data
        
        if isinstance(close_data, pd.Series):
            close_data = close_data.to_frame(tickers[0])
        
        returns = close_data.pct_change().dropna()
        
        # Ensure column names match tickers
        if isinstance(returns.columns, pd.MultiIndex):
            returns.columns = returns.columns.get_level_values(-1)
        
        # Weighted returns
        port_returns = pd.Series(0, index=returns.index)
        for ticker in tickers:
            if ticker in returns.columns:
                port_returns += returns[ticker] * weights.get(ticker, 0)
        
        return port_returns
    except Exception as e:
        logger.error(f"Error computing portfolio returns: {e}")
        return pd.Series()


def _get_benchmark_returns(symbol: str = "SPY", period: str = "1y") -> pd.Series:
    """Fetch benchmark returns."""
    try:
        data = yf.download(symbol, period=period, progress=False, auto_adjust=True)
        if data.empty:
            return pd.Series(dtype=float)
        
        # Handle MultiIndex columns from yfinance
        if isinstance(data.columns, pd.MultiIndex):
            # For single symbol, get the Close column and squeeze to Series
            if 'Close' in data.columns.get_level_values(0):
                close_data = data['Close']
                # If still DataFrame (MultiIndex), squeeze or take first column
                if isinstance(close_data, pd.DataFrame):
                    close_data = close_data.iloc[:, 0]
            else:
                close_data = data.iloc[:, 0]
        elif 'Close' in data.columns:
            close_data = data['Close']
        else:
            close_data = data.iloc[:, 0] if isinstance(data, pd.DataFrame) else data
        
        # Ensure it's a Series
        if isinstance(close_data, pd.DataFrame):
            close_data = close_data.iloc[:, 0]
        
        returns = close_data.pct_change().dropna()
        return returns
    except Exception as e:
        logger.error(f"Error fetching benchmark: {e}")
        return pd.Series(dtype=float)


# =============================================================================
# FEATURE 32: SHARPE, SORTINO, CALMAR RATIOS
# =============================================================================

def compute_ratios(
    positions: List[Dict],
    window: str = "1y",
    risk_free_rate: float = 0.05,
    downside_threshold: float = 0.0,
    benchmark: str = "SPY"
) -> Dict[str, Any]:
    """
    Compute risk-adjusted return ratios.
    
    Args:
        positions: List of position dicts with ticker and weight
        window: Time window (1M, 3M, 6M, 1Y, 3Y, 5Y)
        risk_free_rate: Annual risk-free rate
        downside_threshold: Threshold for downside deviation (Sortino)
        benchmark: Benchmark symbol for comparison
    
    Returns:
        Dict with sharpe, sortino, calmar ratios and rolling analysis
    """
    try:
        port_returns = _get_portfolio_returns(positions, window)
        if port_returns.empty:
            return {"error": "Failed to compute portfolio returns"}
        
        bench_returns = _get_benchmark_returns(benchmark, window)
        
        # Daily risk-free rate
        rf_daily = risk_free_rate / 252
        
        # Annualization factor
        ann_factor = 252
        
        # === Sharpe Ratio ===
        excess_returns = port_returns - rf_daily
        mean_excess = float(excess_returns.mean()) * ann_factor
        total_vol = float(port_returns.std()) * np.sqrt(ann_factor)
        sharpe = mean_excess / total_vol if total_vol > 0 else 0.0
        
        # === Sortino Ratio ===
        downside_returns = port_returns[port_returns < downside_threshold]
        downside_std = float(downside_returns.std()) * np.sqrt(ann_factor) if len(downside_returns) > 0 else total_vol
        sortino = mean_excess / downside_std if downside_std > 0 else 0.0
        
        # === Calmar Ratio ===
        cumulative = (1 + port_returns).cumprod()
        rolling_max = cumulative.cummax()
        drawdowns = (cumulative - rolling_max) / rolling_max
        max_drawdown = float(abs(drawdowns.min()))
        annual_return = float(port_returns.mean()) * ann_factor
        calmar = annual_return / max_drawdown if max_drawdown > 0 else 0.0
        
        # === Rolling Ratios (90-day window) ===
        rolling_window = min(90, len(port_returns) // 2)
        if rolling_window < 10:
            rolling_window = min(10, len(port_returns))
        
        rolling_sharpe = []
        rolling_sortino = []
        rolling_calmar = []
        rolling_dates = []
        
        for i in range(rolling_window, len(port_returns)):
            window_returns = port_returns.iloc[i-rolling_window:i]
            
            # Rolling Sharpe
            w_mean = (float(window_returns.mean()) - rf_daily) * ann_factor
            w_std = float(window_returns.std()) * np.sqrt(ann_factor)
            r_sharpe = w_mean / w_std if w_std > 0 else 0.0
            
            # Rolling Sortino
            w_down = window_returns[window_returns < 0]
            w_down_std = float(w_down.std()) * np.sqrt(ann_factor) if len(w_down) > 0 else w_std
            r_sortino = w_mean / w_down_std if w_down_std > 0 else 0.0
            
            # Rolling Calmar
            w_cum = (1 + window_returns).cumprod()
            w_max = w_cum.cummax()
            w_dd = float(abs(((w_cum - w_max) / w_max).min()))
            w_ret = float(window_returns.mean()) * ann_factor
            r_calmar = w_ret / w_dd if w_dd > 0 else 0.0
            
            rolling_sharpe.append(float(r_sharpe))
            rolling_sortino.append(float(r_sortino))
            rolling_calmar.append(float(r_calmar))
            rolling_dates.append(port_returns.index[i].isoformat() if hasattr(port_returns.index[i], 'isoformat') else str(port_returns.index[i]))
        
        # === Benchmark Comparison ===
        bench_sharpe = 0.0
        bench_sortino = 0.0
        bench_calmar = 0.0
        if not bench_returns.empty and isinstance(bench_returns, pd.Series):
            b_excess = (float(bench_returns.mean()) - rf_daily) * ann_factor
            b_vol = float(bench_returns.std()) * np.sqrt(ann_factor)
            bench_sharpe = b_excess / b_vol if b_vol > 0 else 0.0
            
            b_down = bench_returns[bench_returns < 0]
            b_down_std = float(b_down.std()) * np.sqrt(ann_factor) if len(b_down) > 0 else b_vol
            bench_sortino = b_excess / b_down_std if b_down_std > 0 else 0.0
            
            b_cum = (1 + bench_returns).cumprod()
            b_max = b_cum.cummax()
            b_dd = float(abs(((b_cum - b_max) / b_max).min()))
            b_ret = float(bench_returns.mean()) * ann_factor
            bench_calmar = b_ret / b_dd if b_dd > 0 else 0.0
        
        # Color coding
        def ratio_color(ratio):
            ratio = float(ratio) if not np.isnan(ratio) else 0.0
            if ratio >= 2.0:
                return "excellent"
            elif ratio >= 1.0:
                return "good"
            elif ratio >= 0.5:
                return "fair"
            else:
                return "poor"
        
        # Quality score (composite)
        quality_score = min(100, max(0, (float(sharpe) * 25 + float(sortino) * 20 + float(calmar) * 15)))
        
        return {
            "ratios": {
                "sharpe": {"value": float(sharpe), "color": ratio_color(sharpe)},
                "sortino": {"value": float(sortino), "color": ratio_color(sortino)},
                "calmar": {"value": float(calmar), "color": ratio_color(calmar)}
            },
            "benchmark_ratios": {
                "sharpe": float(bench_sharpe),
                "sortino": float(bench_sortino),
                "calmar": float(bench_calmar)
            },
            "rolling": {
                "dates": rolling_dates,
                "sharpe": rolling_sharpe,
                "sortino": rolling_sortino,
                "calmar": rolling_calmar
            },
            "metrics": {
                "annual_return": float(annual_return),
                "annual_volatility": float(total_vol),
                "max_drawdown": float(max_drawdown),
                "downside_deviation": float(downside_std)
            },
            "quality_score": float(quality_score),
            "window": window,
            "benchmark": benchmark
        }
        
    except Exception as e:
        logger.error(f"Ratio computation error: {e}")
        return {"error": str(e)}


# =============================================================================
# FEATURE 33: MAX DRAWDOWN ANALYSIS
# =============================================================================

def compute_drawdowns(
    positions: List[Dict],
    period: str = "3y",
    threshold: float = 0.05,
    benchmark: str = "SPY"
) -> Dict[str, Any]:
    """
    Deep dive into portfolio drawdowns.
    
    Args:
        positions: List of position dicts
        period: Analysis period
        threshold: Minimum drawdown to report
        benchmark: Benchmark for comparison
    
    Returns:
        Dict with underwater_chart, drawdown_table, distribution, comparison
    """
    try:
        port_returns = _get_portfolio_returns(positions, period)
        if port_returns.empty:
            return {"error": "Failed to compute portfolio returns"}
        
        bench_returns = _get_benchmark_returns(benchmark, period)
        
        # Compute underwater chart
        cumulative = (1 + port_returns).cumprod()
        rolling_max = cumulative.cummax()
        drawdowns = (cumulative - rolling_max) / rolling_max
        
        # Identify individual drawdown periods
        drawdown_periods = []
        in_drawdown = False
        start_idx = 0
        trough_idx = 0
        trough_val = 0
        
        for i, dd in enumerate(drawdowns):
            if not in_drawdown and dd < -0.01:  # Drawdown started
                in_drawdown = True
                start_idx = i
                trough_idx = i
                trough_val = dd
            elif in_drawdown:
                if dd < trough_val:
                    trough_idx = i
                    trough_val = dd
                if dd >= 0:  # Recovered
                    in_drawdown = False
                    if abs(trough_val) >= threshold:
                        drawdown_periods.append({
                            "start_date": str(drawdowns.index[start_idx].date()) if hasattr(drawdowns.index[start_idx], 'date') else str(drawdowns.index[start_idx]),
                            "trough_date": str(drawdowns.index[trough_idx].date()) if hasattr(drawdowns.index[trough_idx], 'date') else str(drawdowns.index[trough_idx]),
                            "end_date": str(drawdowns.index[i].date()) if hasattr(drawdowns.index[i], 'date') else str(drawdowns.index[i]),
                            "depth": float(trough_val),
                            "duration_days": int(i - start_idx),
                            "recovery_days": int(i - trough_idx)
                        })
        
        # Handle ongoing drawdown
        if in_drawdown and abs(trough_val) >= threshold:
            drawdown_periods.append({
                "start_date": str(drawdowns.index[start_idx].date()) if hasattr(drawdowns.index[start_idx], 'date') else str(drawdowns.index[start_idx]),
                "trough_date": str(drawdowns.index[trough_idx].date()) if hasattr(drawdowns.index[trough_idx], 'date') else str(drawdowns.index[trough_idx]),
                "end_date": "ongoing",
                "depth": float(trough_val),
                "duration_days": int(len(drawdowns) - start_idx),
                "recovery_days": None
            })
        
        # Sort by depth
        drawdown_periods.sort(key=lambda x: x["depth"])
        
        # Underwater chart data
        underwater_chart = [
            {
                "date": str(d.date()) if hasattr(d, 'date') else str(d),
                "drawdown": float(v),
                "cumulative_return": float(cumulative.iloc[i] - 1)
            }
            for i, (d, v) in enumerate(zip(drawdowns.index, drawdowns.values))
        ]
        
        # Downsample if too many points
        if len(underwater_chart) > 500:
            step = len(underwater_chart) // 500
            underwater_chart = underwater_chart[::step]
        
        # Distribution analysis
        drawdown_depths = [p["depth"] for p in drawdown_periods]
        recovery_times = [p["recovery_days"] for p in drawdown_periods if p["recovery_days"] is not None]
        
        # Benchmark comparison
        bench_dd = None
        if not bench_returns.empty:
            b_cum = (1 + bench_returns).cumprod()
            b_max = b_cum.cummax()
            b_dd = (b_cum - b_max) / b_max
            bench_dd = {
                "max_drawdown": float(b_dd.min()),
                "current_drawdown": float(b_dd.iloc[-1])
            }
        
        # Current status
        current_drawdown = float(drawdowns.iloc[-1])
        max_drawdown = float(drawdowns.min())
        avg_drawdown = float(np.mean(drawdown_depths)) if drawdown_depths else 0
        
        return {
            "metrics": {
                "max_drawdown": max_drawdown,
                "current_drawdown": current_drawdown,
                "avg_drawdown": avg_drawdown,
                "drawdown_count": len(drawdown_periods),
                "avg_recovery_days": float(np.mean(recovery_times)) if recovery_times else None
            },
            "underwater_chart": underwater_chart,
            "drawdown_table": drawdown_periods[:10],  # Top 10
            "distribution": {
                "depth_histogram": np.histogram(drawdown_depths, bins=10)[0].tolist() if drawdown_depths else [],
                "recovery_histogram": np.histogram(recovery_times, bins=10)[0].tolist() if recovery_times else []
            },
            "benchmark": bench_dd,
            "period": period
        }
        
    except Exception as e:
        logger.error(f"Drawdown analysis error: {e}")
        return {"error": str(e)}


# =============================================================================
# FEATURE 44: BENCHMARK COMPARISON
# =============================================================================

def compute_benchmark_comparison(
    positions: List[Dict],
    benchmark: str = "SPY",
    period: str = "1y"
) -> Dict[str, Any]:
    """
    Compare portfolio performance vs benchmark.
    
    Args:
        positions: List of position dicts
        benchmark: Benchmark symbol
        period: Analysis period
    
    Returns:
        Dict with relative_performance, capture_ratios, rolling_alpha
    """
    try:
        port_returns = _get_portfolio_returns(positions, period)
        bench_returns = _get_benchmark_returns(benchmark, period)
        
        if port_returns.empty or bench_returns.empty:
            return {"error": "Failed to get returns data"}
        
        # Ensure bench_returns is a Series
        if isinstance(bench_returns, pd.DataFrame):
            bench_returns = bench_returns.iloc[:, 0]
        
        # Align dates
        common_idx = port_returns.index.intersection(bench_returns.index)
        if len(common_idx) == 0:
            return {"error": "No overlapping dates between portfolio and benchmark"}
        
        port_returns = port_returns.loc[common_idx]
        bench_returns = bench_returns.loc[common_idx]
        
        # Cumulative returns
        port_cumulative = (1 + port_returns).cumprod()
        bench_cumulative = (1 + bench_returns).cumprod()
        relative_cumulative = port_cumulative / bench_cumulative
        
        # Total returns
        port_total = float(port_cumulative.iloc[-1] - 1)
        bench_total = float(bench_cumulative.iloc[-1] - 1)
        
        # Tracking error
        relative_returns = port_returns - bench_returns
        tracking_error = float(relative_returns.std()) * np.sqrt(252)
        
        # Information ratio
        excess_return = (float(port_returns.mean()) - float(bench_returns.mean())) * 252
        info_ratio = float(excess_return / tracking_error) if tracking_error > 0 else 0.0
        
        # Capture ratios
        up_days = bench_returns > 0
        down_days = bench_returns < 0
        
        upside_capture = 0.0
        downside_capture = 0.0
        
        if up_days.sum() > 0:
            port_up = float(port_returns[up_days].sum())
            bench_up = float(bench_returns[up_days].sum())
            upside_capture = float((port_up / bench_up) * 100) if bench_up != 0 else 100.0
        
        if down_days.sum() > 0:
            port_down = float(port_returns[down_days].sum())
            bench_down = float(bench_returns[down_days].sum())
            downside_capture = float((port_down / bench_down) * 100) if bench_down != 0 else 100.0
        
        capture_efficiency = upside_capture - downside_capture
        
        # Rolling alpha (60-day window)
        rolling_window = min(60, len(port_returns) // 2)
        if rolling_window < 5:
            rolling_window = min(5, len(port_returns))
        
        rolling_alpha = []
        rolling_dates = []
        
        for i in range(rolling_window, len(port_returns)):
            w_port = port_returns.iloc[i-rolling_window:i]
            w_bench = bench_returns.iloc[i-rolling_window:i]
            
            # Simple alpha: excess return
            alpha = (float(w_port.mean()) - float(w_bench.mean())) * 252
            rolling_alpha.append(float(alpha))
            rolling_dates.append(str(port_returns.index[i].date()) if hasattr(port_returns.index[i], 'date') else str(port_returns.index[i]))
        
        # Beta calculation
        if len(port_returns) > 1:
            covariance = float(port_returns.cov(bench_returns))
            bench_variance = float(bench_returns.var())
            beta = float(covariance / bench_variance) if bench_variance > 0 else 1.0
        else:
            beta = 1.0
        
        # Cumulative chart data
        cumulative_chart = [
            {
                "date": str(d.date()) if hasattr(d, 'date') else str(d),
                "portfolio": float(port_cumulative.iloc[i] - 1),
                "benchmark": float(bench_cumulative.iloc[i] - 1),
                "relative": float(relative_cumulative.iloc[i] - 1)
            }
            for i, d in enumerate(port_returns.index)
        ]
        
        # Downsample
        if len(cumulative_chart) > 300:
            step = len(cumulative_chart) // 300
            cumulative_chart = cumulative_chart[::step]
        
        # Outperformance score
        outperformance_score = min(100, max(0, 50 + (port_total - bench_total) * 200 + info_ratio * 20))
        
        return {
            "returns": {
                "portfolio_total": port_total,
                "benchmark_total": bench_total,
                "excess_return": float(port_total - bench_total),
                "portfolio_annual": float(port_returns.mean() * 252),
                "benchmark_annual": float(bench_returns.mean() * 252)
            },
            "risk_metrics": {
                "tracking_error": tracking_error,
                "information_ratio": info_ratio,
                "beta": beta
            },
            "capture_ratios": {
                "upside": upside_capture,
                "downside": downside_capture,
                "efficiency": capture_efficiency
            },
            "rolling_alpha": {
                "dates": rolling_dates,
                "values": rolling_alpha
            },
            "cumulative_chart": cumulative_chart,
            "outperformance_score": float(outperformance_score),
            "benchmark": benchmark,
            "period": period
        }
        
    except Exception as e:
        logger.error(f"Benchmark comparison error: {e}")
        return {"error": str(e)}


# =============================================================================
# FEATURE 45: PERFORMANCE ATTRIBUTION
# =============================================================================

def compute_attribution(
    positions: List[Dict],
    benchmark: str = "SPY",
    period: str = "1y",
    frequency: str = "monthly"
) -> Dict[str, Any]:
    """
    Brinson performance attribution analysis.
    
    Decomposes excess returns into allocation, selection, and interaction effects.
    
    Args:
        positions: List of position dicts with ticker, weight, sector
        benchmark: Benchmark symbol
        period: Analysis period
        frequency: Attribution frequency (daily, monthly, quarterly)
    
    Returns:
        Dict with attribution_summary, by_sector, time_series
    """
    try:
        tickers = [p.get("ticker") for p in positions]
        weights = {p.get("ticker"): p.get("weight", 0) for p in positions}
        sectors = {p.get("ticker"): p.get("sector", "Other") for p in positions}
        
        # Fetch returns
        all_tickers = tickers + [benchmark]
        data = yf.download(all_tickers, period=period, progress=False, auto_adjust=True)
        
        if data.empty:
            return {"error": "Failed to fetch price data"}
        
        # Get Close prices - handle MultiIndex
        if 'Close' in data.columns:
            close_data = data['Close']
        elif isinstance(data.columns, pd.MultiIndex):
            if 'Close' in data.columns.get_level_values(0):
                close_data = data['Close']
            else:
                close_data = data.iloc[:, :len(all_tickers)]
        else:
            close_data = data
        
        if isinstance(close_data, pd.Series):
            close_data = close_data.to_frame()
        
        returns = close_data.pct_change().dropna()
        
        # Ensure column names match tickers
        if isinstance(returns.columns, pd.MultiIndex):
            returns.columns = returns.columns.get_level_values(-1)
        
        if benchmark not in returns.columns:
            return {"error": f"Benchmark {benchmark} not found"}
        
        bench_returns = returns[benchmark]
        
        # Compute portfolio returns
        port_returns = pd.Series(0, index=returns.index)
        for ticker in tickers:
            if ticker in returns.columns:
                port_returns += returns[ticker] * weights.get(ticker, 0)
        
        # Group by sector for Brinson attribution
        sector_groups = {}
        for ticker in tickers:
            sector = sectors.get(ticker, "Other")
            if sector not in sector_groups:
                sector_groups[sector] = {"tickers": [], "total_weight": 0}
            sector_groups[sector]["tickers"].append(ticker)
            sector_groups[sector]["total_weight"] += weights.get(ticker, 0)
        
        # Compute sector-level attribution
        attribution_by_sector = {}
        total_allocation = 0
        total_selection = 0
        total_interaction = 0
        
        for sector, info in sector_groups.items():
            sector_tickers = info["tickers"]
            port_sector_weight = info["total_weight"]
            
            # Sector return in portfolio
            sector_return = 0
            for ticker in sector_tickers:
                if ticker in returns.columns:
                    ticker_weight = weights.get(ticker, 0) / port_sector_weight if port_sector_weight > 0 else 0
                    sector_return += returns[ticker].mean() * ticker_weight * 252
            
            # Benchmark sector weight and return (simplified: assume equal sectors)
            bench_sector_weight = 1 / len(sector_groups)
            bench_sector_return = float(bench_returns.mean() * 252)
            
            # Brinson formulas
            allocation_effect = (port_sector_weight - bench_sector_weight) * bench_sector_return
            selection_effect = bench_sector_weight * (sector_return - bench_sector_return)
            interaction_effect = (port_sector_weight - bench_sector_weight) * (sector_return - bench_sector_return)
            
            attribution_by_sector[sector] = {
                "portfolio_weight": float(port_sector_weight),
                "benchmark_weight": float(bench_sector_weight),
                "weight_diff": float(port_sector_weight - bench_sector_weight),
                "portfolio_return": float(sector_return),
                "benchmark_return": float(bench_sector_return),
                "allocation_effect": float(allocation_effect),
                "selection_effect": float(selection_effect),
                "interaction_effect": float(interaction_effect),
                "total_effect": float(allocation_effect + selection_effect + interaction_effect)
            }
            
            total_allocation += allocation_effect
            total_selection += selection_effect
            total_interaction += interaction_effect
        
        # Time series attribution (simplified: cumulative)
        total_excess = float(port_returns.sum() - bench_returns.sum())
        
        # Skill persistence score
        selection_positive_pct = sum(1 for s in attribution_by_sector.values() if s["selection_effect"] > 0) / len(attribution_by_sector) * 100
        skill_persistence = min(100, max(0, selection_positive_pct))
        
        return {
            "summary": {
                "total_excess_return": total_excess,
                "allocation_effect": float(total_allocation),
                "selection_effect": float(total_selection),
                "interaction_effect": float(total_interaction),
                "explained_excess": float(total_allocation + total_selection + total_interaction)
            },
            "by_sector": attribution_by_sector,
            "skill_persistence": float(skill_persistence),
            "benchmark": benchmark,
            "period": period,
            "frequency": frequency
        }
        
    except Exception as e:
        logger.error(f"Attribution error: {e}")
        return {"error": str(e)}
