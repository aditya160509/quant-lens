"""
Sovereign Algo Studio - Backend Execution Engine
Institutional-grade strategy backtesting and Monte Carlo simulation.
"""

import numpy as np
import pandas as pd
import polars as pl
import logging
import hashlib
import json
import asyncio
import uuid
import os
from functools import lru_cache
from pathlib import Path
from typing import Dict, List, Optional, Any, Literal
from datetime import datetime, timedelta
from pydantic import BaseModel, Field, field_validator, model_validator
from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import Response, StreamingResponse

from app.services.data_engine import engine as data_engine
from app.services.studio.metrics import (
    ENGINE_VERSION as METRICS_ENGINE_VERSION,
    calculate_performance_metrics,
    legacy_metric_aliases,
)
from app.services.studio.execution import (
    DockerExecutionProvider,
    ExecutionProvider,
    ExecutionUnavailableError,
    StrategyExecutionError,
    StrategyPolicyError,
)
from app.services.studio.conventions import (
    DEFAULT_CURRENCY,
    MAX_COMMISSION_PCT,
    MAX_LOOKBACK_YEARS,
    MAX_RETURN_OBSERVATIONS,
    MAX_SIMULATIONS,
    MAX_SLIPPAGE_BPS,
    MAX_WALK_FORWARD_FOLDS,
    MIN_RETURNS_FOR_MONTE_CARLO,
    MIN_RETURNS_FOR_WALK_FORWARD,
    STUDIO_TIMEZONE_NAME,
    TRADING_DAYS_PER_YEAR,
    TRADING_CALENDAR,
)
from app.services.studio.jobs import store as job_store
from app.services.studio.portfolio import PortfolioOptimizationError, optimize_portfolio
from app.services.studio.paper import PaperLifecycle, PaperLifecycleError
from app.services.studio.reports import ReportComposer, ReportError
from app.services.studio.advanced_validation import (
    AdvancedValidationError,
    data_substitution_sensitivity,
    implementation_feasibility,
    parameter_instability,
    sharpe_evidence,
)
from app.services.studio.certification import CertificationError, CertificationService
from app.services.studio.security import (
    SecretMaterialError,
    UnsafeFilenameError,
    assert_no_secret_material,
    assert_no_secret_material_in_export,
    validate_filename,
)
from app.services.studio.tenancy import (
    OwnerMismatchError,
    check_indexed_owner,
    indexed_visible,
    owner_from_request,
    owner_matches,
    remember_owner,
    require_owner_match,
    stamp_owner,
)
from app.services.studio.quotas import get_quota, snapshot as quota_snapshot
from app.services.studio.feature_flags import snapshot as flag_snapshot
from app.studio_v2.shared.observability import current_request_id
from app.studio_v2.shared.persistence import SQLiteStore
from app.services.studio.schemas import (
    ContractVersionedModel,
    DataQuality,
    Provenance,
    StudioErrorEnvelope,
    StudioResultMetadata,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/studio", tags=["Sovereign Algo Studio"])


def _ensure_no_secrets(request: BaseModel) -> None:
    try:
        assert_no_secret_material(request.model_dump())
    except SecretMaterialError as exc:
        raise _error(422, "SECRET_MATERIAL_REJECTED", str(exc)) from exc


def _owner(http_request: Request) -> str:
    """Resolve the caller owner digest (never echoed in responses)."""
    return owner_from_request(http_request)


def _forbidden(location: str) -> HTTPException:
    return _error(403, "STUDIO_FORBIDDEN", f"Record at {location} belongs to a different owner.")


def _require_job_owner(job: dict | None, digest: str, location: str = "job") -> dict:
    if not job:
        raise _error(404, "JOB_NOT_FOUND", "Job not found.")
    try:
        require_owner_match(job, digest, location)
    except OwnerMismatchError:
        raise _forbidden(location) from None
    return job


def _require_indexed_owner(store: object, record_id: str, digest: str, location: str) -> None:
    try:
        check_indexed_owner(store, record_id, digest, location)
    except OwnerMismatchError:
        raise _forbidden(location) from None

# ═══════════════════════════════════════════════════════════════════════════════
# REQUEST/RESPONSE MODELS
# ═══════════════════════════════════════════════════════════════════════════════

class ExecuteStrategyRequest(ContractVersionedModel):
    code: str
    ticker: str = "SPY"
    universe: str = "US_TOP50"
    lookback_years: int = Field(default=5, ge=1, le=MAX_LOOKBACK_YEARS)
    end_date: str = "2026-01-13"
    slippage_bps: float = Field(default=0.0, ge=0, le=MAX_SLIPPAGE_BPS)
    commission_pct: float = Field(default=0.0, ge=0, le=MAX_COMMISSION_PCT)

class MonteCarloRequest(ContractVersionedModel):
    returns: List[float] = Field(min_length=MIN_RETURNS_FOR_MONTE_CARLO, max_length=MAX_RETURN_OBSERVATIONS)
    simulations: int = Field(default=10000, ge=100, le=MAX_SIMULATIONS)
    time_horizon: int = Field(default=252, ge=1, le=2520)
    seed: int = 42
    method: Literal["gaussian", "historical_bootstrap", "moving_block_bootstrap"] = "gaussian"
    block_size: int = Field(default=5, ge=2, le=252)
    source_artifact_id: Optional[str] = Field(default=None, max_length=128)

class WalkForwardRequest(ContractVersionedModel):
    returns: List[float] = Field(min_length=MIN_RETURNS_FOR_WALK_FORWARD, max_length=MAX_RETURN_OBSERVATIONS)
    oos_days: int = Field(default=90, ge=5)
    n_folds: int = Field(default=5, ge=2, le=MAX_WALK_FORWARD_FOLDS)
    purge_days: int = Field(default=0, ge=0, le=252)
    embargo_days: int = Field(default=0, ge=0, le=252)
    min_oos_sharpe: float = Field(default=0.5, ge=-5.0, le=5.0)
    min_consistency_pct: float = Field(default=50.0, ge=0.0, le=100.0)
    source_artifact_id: Optional[str] = Field(default=None, max_length=128)


class SensitivityRequest(ContractVersionedModel):
    closes: List[float] = Field(min_length=30, max_length=10000)
    lookbacks: List[int] = Field(min_length=1, max_length=10)
    thresholds: List[float] = Field(min_length=1, max_length=10)
    slippage_bps: float = Field(default=0.0, ge=0, le=MAX_SLIPPAGE_BPS)
    commission_pct: float = Field(default=0.0, ge=0, le=MAX_COMMISSION_PCT)

    @field_validator("lookbacks")
    @classmethod
    def lookbacks_bounded(cls, value: List[int]) -> List[int]:
        if any(not isinstance(item, int) or item < 2 or item > 252 for item in value):
            raise ValueError("each lookback must be an integer in [2, 252]")
        return value

    @field_validator("thresholds")
    @classmethod
    def thresholds_bounded(cls, value: List[float]) -> List[float]:
        if any(not isinstance(item, (int, float)) or not np.isfinite(item) or item < 0 or item > 1 for item in value):
            raise ValueError("each threshold must be finite in [0, 1]")
        return value

    @model_validator(mode="after")
    def bound_grid(self):
        if len(self.lookbacks) * len(self.thresholds) > 100:
            raise ValueError("sensitivity grid is bounded to 100 cells")
        if any(not np.isfinite(item) or item <= 0 for item in self.closes):
            raise ValueError("closes must contain only finite positive values")
        return self


class ScenarioRequest(ContractVersionedModel):
    returns: List[float] = Field(min_length=MIN_RETURNS_FOR_WALK_FORWARD, max_length=MAX_RETURN_OBSERVATIONS)
    oos_days: int = Field(default=20, ge=5)
    n_folds: int = Field(default=5, ge=2, le=MAX_WALK_FORWARD_FOLDS)
    purge_days: int = Field(default=0, ge=0, le=252)
    embargo_days: int = Field(default=0, ge=0, le=252)
    cost_shock_bps: float = Field(default=10.0, ge=0, le=1000)
    missing_pct: float = Field(default=5.0, ge=0, le=50)
    delay_bars: int = Field(default=1, ge=1, le=5)
    seed: int = 42


class PortfolioOptimizeRequest(ContractVersionedModel):
    assets: List[str] = Field(min_length=2, max_length=50)
    expected_returns: Optional[List[float]] = Field(default=None, max_length=50)
    covariance: Optional[List[List[float]]] = Field(default=None, max_length=50)
    return_observations: Optional[List[List[float]]] = Field(default=None, max_length=10000)
    current_weights: Optional[List[float]] = None
    objective: Literal["min_variance", "max_sharpe", "max_return", "diversification", "tracking_error", "multi_objective"] = "max_sharpe"
    expected_return_model: Literal["supplied", "historical_mean", "zero"] = "supplied"
    covariance_model: Literal["supplied", "sample", "diagonal_shrinkage"] = "supplied"
    periods_per_year: int = Field(default=252, ge=1, le=366)
    shrinkage: float = Field(default=0.2, ge=0.0, le=1.0)
    min_weight: float = Field(default=0.0, ge=-2.0, le=1.0)
    max_weight: float = Field(default=1.0, ge=-1.0, le=2.0)
    gross_leverage: float = Field(default=1.0, ge=1.0, le=5.0)
    risk_free_rate: float = Field(default=0.0, ge=-1.0, le=1.0)
    turnover_penalty: float = Field(default=0.0, ge=0.0, le=10.0)
    max_turnover: Optional[float] = Field(default=None, ge=0.0, le=10.0)
    target_return: Optional[float] = Field(default=None, ge=-10.0, le=10.0)
    benchmark_weights: Optional[List[float]] = None
    risk_aversion: float = Field(default=0.5, ge=0.0, le=1.0)
    linear_constraints: List[Dict[str, Any]] = Field(default_factory=list, max_length=100)
    scenarios: List[Dict[str, Any]] = Field(default_factory=list, max_length=100)
    source: Dict[str, Any] = Field(default_factory=lambda: {"kind": "manual"})
    cost_bps: float = Field(default=0.0, ge=0.0, le=1000.0)

    @model_validator(mode="after")
    def validate_dimensions(self):
        size = len(self.assets)
        if self.source.get("kind") not in {"manual", "holdings_csv", "returns_csv", "saved_version", "factor_recipe"}:
            raise ValueError("unsupported portfolio source kind")
        if self.expected_return_model == "supplied" and (self.expected_returns is None or len(self.expected_returns) != size):
            raise ValueError("supplied expected returns must match assets")
        if self.covariance_model == "supplied":
            if self.covariance is None or len(self.covariance) != size or any(len(row) != size for row in self.covariance):
                raise ValueError("supplied covariance must be square and match assets")
        if self.expected_return_model == "historical_mean" or self.covariance_model != "supplied":
            if self.return_observations is None or len(self.return_observations) < 3:
                raise ValueError("selected return and covariance models require at least 3 return observations")
            if any(len(row) != size for row in self.return_observations):
                raise ValueError("each return observation must match assets")
        if self.current_weights is not None and len(self.current_weights) != size:
            raise ValueError("current_weights must match assets")
        if self.benchmark_weights is not None and len(self.benchmark_weights) != size:
            raise ValueError("benchmark_weights must match assets")
        if self.objective == "tracking_error" and self.benchmark_weights is None:
            raise ValueError("tracking_error requires benchmark_weights")
        for constraint in self.linear_constraints:
            if len(constraint.get("coefficients", [])) != size:
                raise ValueError("every linear constraint must provide one coefficient per asset")
        for scenario in self.scenarios:
            if len(scenario.get("shocks", [])) != size:
                raise ValueError("every scenario must provide one shock per asset")
        return self


class PortfolioOptimizeRequest(ContractVersionedModel):
    assets: List[str] = Field(min_length=2, max_length=50)
    expected_returns: Optional[List[float]] = Field(default=None, max_length=50)
    covariance: Optional[List[List[float]]] = Field(default=None, max_length=50)
    return_observations: Optional[List[List[float]]] = Field(default=None, max_length=10000)
    current_weights: Optional[List[float]] = None
    objective: Literal["min_variance", "max_sharpe", "max_return", "diversification", "tracking_error", "multi_objective"] = "max_sharpe"
    expected_return_model: Literal["supplied", "historical_mean", "zero"] = "supplied"
    covariance_model: Literal["supplied", "sample", "diagonal_shrinkage"] = "supplied"
    periods_per_year: int = Field(default=252, ge=1, le=366)
    shrinkage: float = Field(default=0.2, ge=0.0, le=1.0)
    min_weight: float = Field(default=0.0, ge=-2.0, le=1.0)
    max_weight: float = Field(default=1.0, ge=-1.0, le=2.0)
    gross_leverage: float = Field(default=1.0, ge=1.0, le=5.0)
    risk_free_rate: float = Field(default=0.0, ge=-1.0, le=1.0)
    turnover_penalty: float = Field(default=0.0, ge=0.0, le=10.0)
    max_turnover: Optional[float] = Field(default=None, ge=0.0, le=10.0)
    target_return: Optional[float] = Field(default=None, ge=-10.0, le=10.0)
    benchmark_weights: Optional[List[float]] = None
    risk_aversion: float = Field(default=0.5, ge=0.0, le=1.0)
    linear_constraints: List[Dict[str, Any]] = Field(default_factory=list, max_length=100)
    scenarios: List[Dict[str, Any]] = Field(default_factory=list, max_length=100)
    source: Dict[str, Any] = Field(default_factory=lambda: {"kind": "manual"})
    cost_bps: float = Field(default=0.0, ge=0.0, le=1000.0)

    @model_validator(mode="after")
    def validate_dimensions(self):
        size = len(self.assets)
        if self.source.get("kind") not in {"manual", "holdings_csv", "returns_csv", "saved_version", "factor_recipe"}:
            raise ValueError("unsupported portfolio source kind")
        if self.expected_return_model == "supplied" and (self.expected_returns is None or len(self.expected_returns) != size):
            raise ValueError("supplied expected returns must match assets")
        if self.covariance_model == "supplied":
            if self.covariance is None or len(self.covariance) != size or any(len(row) != size for row in self.covariance):
                raise ValueError("supplied covariance must be square and match assets")
        if self.expected_return_model == "historical_mean" or self.covariance_model != "supplied":
            if self.return_observations is None or len(self.return_observations) < 3:
                raise ValueError("selected return and covariance models require at least 3 return observations")
            if any(len(row) != size for row in self.return_observations):
                raise ValueError("each return observation must match assets")
        if self.current_weights is not None and len(self.current_weights) != size:
            raise ValueError("current_weights must match assets")
        if self.benchmark_weights is not None and len(self.benchmark_weights) != size:
            raise ValueError("benchmark_weights must match assets")
        if self.objective == "tracking_error" and self.benchmark_weights is None:
            raise ValueError("tracking_error requires benchmark_weights")
        for constraint in self.linear_constraints:
            if len(constraint.get("coefficients", [])) != size:
                raise ValueError("every linear constraint must provide one coefficient per asset")
        for scenario in self.scenarios:
            if len(scenario.get("shocks", [])) != size:
                raise ValueError("every scenario must provide one shock per asset")
        return self


class PortfolioVersionRequest(ContractVersionedModel):
    name: str = Field(min_length=1, max_length=100)
    artifact_id: str = Field(pattern=r"^portfolio_[a-f0-9]{16}$")
    inputs: PortfolioOptimizeRequest

class TradeLogEntry(BaseModel):
    id: str
    entry_date: str
    exit_date: Optional[str] = None
    direction: int
    entry_price: float
    exit_price: Optional[float] = None
    pnl: Optional[float] = None
    pnl_pct: Optional[float] = None
    mae_pct: Optional[float] = None
    mfe_pct: Optional[float] = None
    holding_period: Optional[int] = None # Bars

class StudioDataUnavailableError(ValueError):
    """Raised when an analytical request has no observed market data."""


def _error(status_code: int, code: str, message: str, *, retryable: bool = False) -> HTTPException:
    envelope = StudioErrorEnvelope(code=code, message=message, retryable=retryable)
    return HTTPException(status_code=status_code, detail=envelope.model_dump())


def _metadata(
    df: pd.DataFrame,
    *,
    engine_version: str,
    parameters: Dict[str, Any],
    code_hash: Optional[str] = None,
    warnings: Optional[List[Dict[str, Any]]] = None,
    dataset_id: str = "market_universe_daily",
) -> Dict[str, Any]:
    metadata = StudioResultMetadata(
        data_quality=DataQuality(
            status="observed",
            observations=len(df),
            source=dataset_id,
            as_of=df.index.max().isoformat() if len(df) else None,
            timezone=STUDIO_TIMEZONE_NAME,
            currency=DEFAULT_CURRENCY,
            calendar=TRADING_CALENDAR,
            corporate_actions="unknown",
            look_ahead_check="not_verified",
        ),
        provenance=Provenance(
            engine_version=engine_version,
            code_hash=code_hash,
            dataset_id=dataset_id,
            parameters=parameters,
        ),
        warnings=warnings or [],
    )
    return metadata.model_dump()


def _benchmark_buy_and_hold(closes: np.ndarray) -> List[float]:
    """Deterministic buy-and-hold benchmark from the same observed closes.

    Normalized to 1.0 at the first bar. Returns [] when closes are unusable
    so callers render an explicit unavailable state instead of zeros.
    """
    try:
        values = np.asarray(closes, dtype=float)
    except (TypeError, ValueError):
        return []
    if values.size < 1 or np.any(~np.isfinite(values)) or values[0] <= 0:
        return []
    return [float(value / values[0]) for value in values]


def _orders_from_signals(signals: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Expose observed order intent derived ONLY from persisted signals.

    Each nonzero-direction signal already persisted by the execution artifact
    becomes one order record. No fill is synthesized here; fills remain
    explicitly unavailable until a governed fill artifact exists.
    """
    orders: List[Dict[str, Any]] = []
    for position, signal in enumerate(signals):
        try:
            direction = int(signal.get("direction", 0))
        except (TypeError, ValueError):
            continue
        if direction == 0:
            continue
        orders.append({
            "order_id": f"order-{position + 1}",
            "date": signal.get("date"),
            "timestamp": signal.get("timestamp"),
            "direction": direction,
            "price": signal.get("price"),
            "bar_index": signal.get("idx"),
            "source": "observed_signal",
        })
    return orders


FILLS_UNAVAILABLE = {
    "status": "unavailable",
    "reason": "The execution contract carries no governed fill records; fills are not synthesized from signals or trades.",
}


def _safe_numeric(value: Any) -> Optional[float]:
    """Convert a scalar to a finite float without inventing a value."""
    try:
        cast = float(value)
    except (TypeError, ValueError):
        return None
    return cast if np.isfinite(cast) else None


def _sanitize_for_json(value: Any) -> Any:
    """Recursively normalize payload values so JSON serialization cannot fail."""
    if isinstance(value, dict):
        return {k: _sanitize_for_json(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [_sanitize_for_json(v) for v in value]
    if isinstance(value, np.ndarray):
        return [_sanitize_for_json(v) for v in value.tolist()]
    if isinstance(value, (np.floating, float)):
        return _safe_numeric(value)
    if isinstance(value, (np.integer,)):
        return int(value)
    return value

# ═══════════════════════════════════════════════════════════════════════════════
# CORE STRATEGY ENGINE
# ═══════════════════════════════════════════════════════════════════════════════

class StrategyExecutor:
    """
    Executes user-defined strategies against Parquet price data.
    """
    
    def __init__(
        self,
        universe: str,
        lookback_years: int,
        end_date: str,
        slippage_bps: float = 0.0,
        commission_pct: float = 0.0,
        execution_provider: Optional[ExecutionProvider] = None,
    ):
        self.universe = universe
        self.lookback_days = lookback_years * 252
        self.end_date = datetime.strptime(end_date, "%Y-%m-%d").date()
        self.start_date = self.end_date - timedelta(days=lookback_years * 365)
        self.slippage = slippage_bps / 10000.0
        self.commission = commission_pct / 100.0
        self.execution_provider = execution_provider or DockerExecutionProvider()
        
    def get_price_data(self, ticker: str = "SPY") -> pd.DataFrame:
        """Fetch OHLCV data from DataEngine."""
        try:
            df = data_engine.get_full_ohlcv(ticker, lookback_days=self.lookback_days + 100)
            if df.empty:
                raise StudioDataUnavailableError(f"No observed OHLCV data is available for {ticker}.")
            
            # Filter to date range
            df = df.reset_index()
            df['Date'] = pd.to_datetime(df['Date'])
            mask = (df['Date'].dt.date >= self.start_date) & (df['Date'].dt.date <= self.end_date)
            filtered = df[mask].set_index('Date')
            if filtered.empty:
                raise StudioDataUnavailableError(
                    f"No observed OHLCV data is available for {ticker} in the requested date range."
                )
            return filtered
        except StudioDataUnavailableError:
            raise
        except Exception as e:
            logger.error(f"Error fetching data: {e}")
            raise StudioDataUnavailableError(f"Observed OHLCV data could not be loaded for {ticker}.") from e

    @staticmethod
    def _trade_excursion(
        df: pd.DataFrame,
        entry_idx: int,
        exit_idx: int,
        direction: int,
        entry_price: float,
    ) -> tuple[float, float]:
        path = df.iloc[entry_idx : exit_idx + 1]
        if direction > 0:
            adverse = float(path["Low"].min() / entry_price - 1.0)
            favorable = float(path["High"].max() / entry_price - 1.0)
        else:
            adverse = float(1.0 - path["High"].max() / entry_price)
            favorable = float(1.0 - path["Low"].min() / entry_price)
        return min(adverse, 0.0), max(favorable, 0.0)
    
    def run_momentum_strategy(self, df: pd.DataFrame, lookback: int = 20, threshold: float = 0.02) -> Dict:
        """
        Execute a momentum-based strategy.
        Returns signals, trades, and performance metrics.
        """
        signals = []
        trades = []
        equity_curve = [1.0]
        position = 0
        entry_price = 0
        entry_idx = 0
        
        closes = df['Close'].values
        dates = df.index.tolist()
        
        for i in range(lookback, len(closes)):
            # Calculate momentum signal
            ret = (closes[i] / closes[i - lookback]) - 1
            if i > 20:
                vol_raw = np.std(np.diff(closes[i-20:i]) / closes[i-20:i-1])
                vol = float(vol_raw) if np.isfinite(vol_raw) and vol_raw > 0 else None
            else:
                vol = None
            confidence = min(abs(ret) / (vol * 2 + 0.001), 1.0) if vol is not None else None
            
            signal = {
                'date': dates[i].isoformat() if hasattr(dates[i], 'isoformat') else str(dates[i]),
                'timestamp': int(pd.Timestamp(dates[i]).timestamp() * 1000),
                'price': float(closes[i]),
                'direction': 0,
                'confidence': float(confidence) if confidence is not None and np.isfinite(confidence) else None,
                'momentum': float(ret) if np.isfinite(ret) else None,
                'idx': i
            }
            
            # Generate entry/exit signals
            if ret > threshold and position <= 0:
                signal['direction'] = 1  # Long
                if position < 0:
                    # Close short — include slippage/commission drag via conventions
                    raw = (entry_price - closes[i]) / entry_price
                    pnl = raw - self.slippage - self.commission
                    mae, mfe = self._trade_excursion(df, entry_idx, i, -1, float(entry_price))
                    trades.append({
                        'entry_date': dates[entry_idx].isoformat() if hasattr(dates[entry_idx], 'isoformat') else str(dates[entry_idx]),
                        'exit_date': signal['date'],
                        'direction': -1,
                        'entry_price': float(entry_price),
                        'exit_price': float(closes[i]),
                        'pnl': float(pnl),
                        'mae': mae,
                        'mfe': mfe,
                        'holding_period': i - entry_idx,
                    })
                position = 1
                entry_price = closes[i]
                entry_idx = i
                
            elif ret < -threshold and position >= 0:
                signal['direction'] = -1  # Short
                if position > 0:
                    # Close long — include slippage/commission drag via conventions
                    raw = (closes[i] - entry_price) / entry_price
                    pnl = raw - self.slippage - self.commission
                    mae, mfe = self._trade_excursion(df, entry_idx, i, 1, float(entry_price))
                    trades.append({
                        'entry_date': dates[entry_idx].isoformat() if hasattr(dates[entry_idx], 'isoformat') else str(dates[entry_idx]),
                        'exit_date': signal['date'],
                        'direction': 1,
                        'entry_price': float(entry_price),
                        'exit_price': float(closes[i]),
                        'pnl': float(pnl),
                        'mae': mae,
                        'mfe': mfe,
                        'holding_period': i - entry_idx,
                    })
                position = -1
                entry_price = closes[i]
                entry_idx = i
            
            signals.append(signal)
            
            # Update equity curve
            if position != 0:
                daily_pnl = (closes[i] - closes[i-1]) / closes[i-1] * position
                equity_curve.append(equity_curve[-1] * (1 + daily_pnl))
            else:
                equity_curve.append(equity_curve[-1])
        
        # Compute performance metrics
        metrics = self._compute_metrics(equity_curve, trades)

        benchmark_full = _benchmark_buy_and_hold(np.asarray(closes, dtype=float))
        benchmark_equity = benchmark_full[lookback - 1:] if len(benchmark_full) == len(closes) else []

        return {
            'signals': signals,
            'trades': trades,
            'orders': _orders_from_signals(signals),
            'fills': None,
            'fills_status': dict(FILLS_UNAVAILABLE),
            'equity_curve': [float(e) for e in equity_curve],
            'series': {
                'benchmark_equity': [float(value) for value in benchmark_equity],
            } if benchmark_equity and len(benchmark_equity) == len(equity_curve) else None,
            'metrics': metrics,
            'candles': self._format_candles(df)
        }
    
    def _format_candles(self, df: pd.DataFrame) -> List[Dict]:
        """Format OHLCV data for frontend canvas."""
        candles = []
        for idx, row in df.iterrows():
            candles.append({
                'time': int(pd.Timestamp(idx).timestamp()),
                'open': float(row['Open']) if 'Open' in row else float(row['Close']),
                'high': float(row['High']) if 'High' in row else float(row['Close']),
                'low': float(row['Low']) if 'Low' in row else float(row['Close']),
                'close': float(row['Close']),
                'volume': int(row['Volume']) if 'Volume' in row else 0
            })
        return candles
    
    def _compute_metrics(
        self,
        equity_curve: List[float],
        trades: List[Dict],
        *,
        gross_equity_curve: Optional[List[float]] = None,
        turnover: Optional[float] = None,
        average_exposure: Optional[float] = None,
    ) -> Dict:
        """Delegate financial truth to the canonical Studio calculator."""
        bundle = calculate_performance_metrics(
            equity_curve,
            trades,
            gross_equity_curve=gross_equity_curve,
            turnover=turnover,
            average_exposure=average_exposure,
        )
        return {
            **legacy_metric_aliases(bundle),
            "warnings": [warning.model_dump() for warning in bundle.warnings],
        }

    def execute_custom_code(self, code: str, df: pd.DataFrame) -> Dict:
        """
        Execute user-submitted Python code dynamically.
        Expected interface: 
        1. A class 'Strategy' with 'generate_signals(self, data)'
        2. A global instance 'strategy = Strategy()'
        """
        try:
            raw_signals = self.execution_provider.execute(code, df)
            return self._process_strategy_results(df, raw_signals)
        except (ExecutionUnavailableError, StrategyPolicyError, StrategyExecutionError):
            raise
        except Exception as e:
            logger.error(f"Failed to execute custom strategy: {e}")
            raise StrategyExecutionError("The isolated strategy runner failed.") from e

    def _process_strategy_results(self, df: pd.DataFrame, raw_signals: List[Dict]) -> Dict:
        """Convert raw signals into trades, equity curve, and metrics."""
        signals = []
        trades = []
        closes = df['Close'].values
        dates = df.index.tolist()
        
        equity_curve = [1.0] * len(closes)
        gross_equity_curve = [1.0] * len(closes)
        exposure_series = [0.0] * len(closes)
        turnover_series = [0.0] * len(closes)
        cost_series = [0.0] * len(closes)
        position = 0
        entry_price = 0
        entry_idx = 0
        try:
            signal_map = {int(s['idx']): int(s['dir']) for s in raw_signals}
        except (TypeError, KeyError, ValueError) as exc:
            raise ValueError("Signals must contain integer 'idx' and 'dir' fields") from exc
        
        for i in range(1, len(closes)):
            daily_ret = (closes[i] / closes[i-1]) - 1
            if position != 0:
                equity_curve[i] = equity_curve[i-1] * (1 + (daily_ret * position))
                gross_equity_curve[i] = gross_equity_curve[i-1] * (1 + (daily_ret * position))
            else:
                equity_curve[i] = equity_curve[i-1]
                gross_equity_curve[i] = gross_equity_curve[i-1]
            
            sig_dir = signal_map.get(i, 0)
            
            if sig_dir != 0:
                if sig_dir != position:
                    traded_notional = abs(sig_dir - position)
                    turnover_series[i] = float(traded_notional)
                    cost_rate = traded_notional * (self.slippage + self.commission)
                    cost_series[i] = float(cost_rate)
                    equity_curve[i] *= max(0.0, 1.0 - cost_rate)
                    if position != 0:
                        exit_price_adj = closes[i] * (1 - self.slippage if position > 0 else 1 + self.slippage)
                        pnl_abs = (exit_price_adj - entry_price) if position > 0 else (entry_price - exit_price_adj)
                        pnl_pct = pnl_abs / entry_price
                        pnl_pct -= (self.commission * 2)
                        mae, mfe = self._trade_excursion(
                            df, entry_idx, i, int(position), float(entry_price)
                        )
                        
                        trades.append({
                            'id': f"T-{len(trades)+1}",
                            'entry_date': dates[entry_idx].isoformat(),
                            'exit_date': dates[i].isoformat(),
                            'direction': int(position),
                            'entry_price': float(entry_price),
                            'exit_price': float(exit_price_adj),
                            'pnl': float(pnl_pct),
                            'mae': mae,
                            'mfe': mfe,
                            'holding_period': i - entry_idx,
                        })
                    
                    entry_price_adj = closes[i] * (1 + self.slippage if sig_dir > 0 else 1 - self.slippage)
                    
                    position = sig_dir
                    entry_price = entry_price_adj
                    entry_idx = i
                    signals.append({
                        'date': dates[i].isoformat(),
                        'timestamp': int(pd.Timestamp(dates[i]).timestamp() * 1000),
                        'price': float(entry_price_adj),
                        'direction': int(sig_dir),
                        'confidence': 1.0,
                        'idx': i
                    })
            exposure_series[i] = float(abs(position))

        running_peak = np.maximum.accumulate(np.asarray(equity_curve, dtype=float))
        drawdown_series = (np.asarray(equity_curve, dtype=float) / running_peak - 1.0).tolist()
        benchmark_equity = _benchmark_buy_and_hold(np.asarray(closes, dtype=float))
        periods = max(1, len(closes) - 1)
        metrics_result = self._compute_metrics(
            equity_curve,
            trades,
            gross_equity_curve=gross_equity_curve,
            turnover=float(sum(turnover_series) / periods),
            average_exposure=float(sum(exposure_series[1:]) / periods),
        )
        
        return {
            'signals': signals,
            'trades': trades,
            'orders': _orders_from_signals(signals),
            'fills': None,
            'fills_status': dict(FILLS_UNAVAILABLE),
            'equity_curve': [float(e) for e in equity_curve],
            'series': {
                'equity_net': [float(value) for value in equity_curve],
                'equity_gross': [float(value) for value in gross_equity_curve],
                'drawdown': [float(value) for value in drawdown_series],
                'exposure': exposure_series,
                'turnover': turnover_series,
                'costs': cost_series,
                'benchmark_equity': [float(value) for value in benchmark_equity],
            },
            'metrics': metrics_result,
            'candles': self._format_candles(df)
        }

# ═══════════════════════════════════════════════════════════════════════════════
# MONTE CARLO ENGINE
# ═══════════════════════════════════════════════════════════════════════════════

class MonteCarloEngine:
    """
    High-performance Monte Carlo simulation engine.
    Supports bounded parametric and empirical resampling with vectorized numpy operations.
    """
    
    @staticmethod
    def run_simulation(
        returns: np.ndarray,
        n_simulations: int = 10000,
        time_horizon: int = 252,
        initial_capital: float = 1.0,
        seed: int = 42,
        method: str = "gaussian",
        block_size: int = 5,
    ) -> Dict:
        """
        Run Monte Carlo simulation to analyze risk of ruin.
        
        Args:
            returns: Historical daily returns
            n_simulations: Number of simulation paths (bounded by the request contract)
            time_horizon: Forecast horizon in trading days
            initial_capital: Starting capital (normalized to 1.0)
        
        Returns:
            Dict with simulation results and risk metrics
        """
        n_simulations = min(n_simulations, MAX_SIMULATIONS)
        
        # Estimate return distribution
        mu = np.mean(returns)
        sigma = np.std(returns)
        
        rng = np.random.default_rng(seed)
        if method == "gaussian":
            random_returns = rng.normal(mu, sigma, (n_simulations, time_horizon))
        elif method == "historical_bootstrap":
            random_returns = rng.choice(returns, size=(n_simulations, time_horizon), replace=True)
        elif method == "moving_block_bootstrap":
            effective_block = min(max(2, int(block_size)), len(returns))
            block_count = int(np.ceil(time_horizon / effective_block))
            starts = rng.integers(0, len(returns), size=(n_simulations, block_count))
            offsets = np.arange(effective_block)
            indices = (starts[..., None] + offsets) % len(returns)
            random_returns = returns[indices.reshape(n_simulations, -1)[:, :time_horizon]]
        else:
            raise ValueError(f"Unsupported Monte Carlo method: {method}")
        
        # Inputs are simple returns, so compound simple gross returns. The floor
        # prevents a Gaussian tail draw below -100% from creating negative equity.
        gross_returns = np.clip(1.0 + random_returns, 1e-9, None)
        equity_paths = initial_capital * np.cumprod(gross_returns, axis=1)
        
        # Prepend initial capital
        equity_paths = np.column_stack([np.ones(n_simulations) * initial_capital, equity_paths])
        
        # Calculate key metrics
        final_values = equity_paths[:, -1]
        max_values = np.max(equity_paths, axis=1)
        min_values = np.min(equity_paths, axis=1)
        
        # Drawdown analysis
        running_max = np.maximum.accumulate(equity_paths, axis=1)
        drawdowns = (equity_paths - running_max) / running_max
        max_drawdowns = np.min(drawdowns, axis=1)
        
        # Risk of ruin (capital below 50%)
        ruin_threshold = 0.5
        ruin_count = np.sum(min_values < ruin_threshold)
        risk_of_ruin = ruin_count / n_simulations * 100
        
        # Percentile analysis
        percentiles = [5, 10, 25, 50, 75, 90, 95]
        final_percentiles = {f"p{p}": float(np.percentile(final_values, p)) for p in percentiles}
        dd_percentiles = {f"dd_p{p}": float(np.percentile(max_drawdowns, p) * 100) for p in percentiles}
        
        # Sample paths for visualization (100 representative paths)
        sample_indices = np.linspace(0, n_simulations - 1, min(100, n_simulations), dtype=int)
        sample_paths = equity_paths[sample_indices].tolist()
        
        # Histogram bins for final value distribution
        hist_counts, hist_edges = np.histogram(final_values, bins=50)
        histogram = {
            'counts': hist_counts.tolist(),
            'edges': hist_edges.tolist()
        }
        
        return {
            'summary': {
                'simulations': n_simulations,
                'timeHorizon': time_horizon,
                'meanFinalValue': float(np.mean(final_values)),
                'medianFinalValue': float(np.median(final_values)),
                'stdFinalValue': float(np.std(final_values)),
                'riskOfRuin': round(risk_of_ruin, 2),
                'ruinThreshold': ruin_threshold,
                'meanMaxDrawdown': float(np.mean(max_drawdowns) * 100),
                'worstDrawdown': float(np.min(max_drawdowns) * 100),
                'bestFinal': float(np.max(final_values)),
                'worstFinal': float(np.min(final_values)),
                'probPositive': float(np.sum(final_values > 1.0) / n_simulations * 100),
                'probDouble': float(np.sum(final_values > 2.0) / n_simulations * 100),
                'var95': float(np.percentile(final_values, 5)),
                'p10': float(np.percentile(final_values, 10)),
                'p90': float(np.percentile(final_values, 90))
            },
            'percentiles': {**final_percentiles, **dd_percentiles},
            'samplePaths': sample_paths,
            'histogram': histogram,
            'dailyReturns': {
                'mean': float(mu),
                'std': float(sigma),
                'sharpeImplied': float(mu / sigma * np.sqrt(252)) if sigma > 0 else None
            },
            'assumptions': {
                'method': method,
                'seed': seed,
                'blockSize': block_size if method == 'moving_block_bootstrap' else None,
                'inputObservations': int(len(returns)),
                'returnConvention': 'simple',
            },
        }


# ═══════════════════════════════════════════════════════════════════════════════
# WALK-FORWARD ENGINE
# ═══════════════════════════════════════════════════════════════════════════════

class WalkForwardEngine:
    """
    Walk-forward analysis with out-of-sample validation.
    """
    
    @staticmethod
    def run_analysis(
        returns: np.ndarray,
        oos_days: int = 90,
        n_folds: int = 12,
        purge_days: int = 0,
        embargo_days: int = 0,
        min_oos_sharpe: float = 0.5,
        min_consistency_pct: float = 50.0,
    ) -> Dict:
        """
        Perform walk-forward analysis with OOS validation.
        
        Args:
            returns: Full return series
            oos_days: Out-of-sample window size
            n_folds: Number of walk-forward folds
        
        Returns:
            Dict with IS/OOS performance comparison
        """
        total_days = len(returns)
        gap = purge_days + embargo_days
        first_test_start = total_days - n_folds * oos_days
        if first_test_start - gap < 20:
            raise ValueError("Insufficient observations for expanding walk-forward folds and leakage gaps")
        
        results = []
        monthly_heatmap = []
        
        for i in range(n_folds):
            test_start = first_test_start + i * oos_days
            test_end = test_start + oos_days
            train_end = test_start - gap
            is_returns = returns[:train_end]
            oos_returns = returns[test_start:test_end]
            
            if len(is_returns) < 20 or len(oos_returns) < 5:
                continue
            
            # Calculate metrics for each period
            is_std = np.std(is_returns)
            oos_std = np.std(oos_returns)
            is_sharpe = float(np.mean(is_returns) / is_std * np.sqrt(252)) if is_std > 0 else None
            oos_sharpe = float(np.mean(oos_returns) / oos_std * np.sqrt(252)) if oos_std > 0 else None
            
            # Inputs are simple returns, so period returns must compound rather
            # than add. This keeps fold summaries consistent with the equity path.
            is_return = np.prod(1.0 + is_returns) - 1.0
            oos_return = np.prod(1.0 + oos_returns) - 1.0
            
            results.append({
                'fold': i + 1,
                'isSharpe': is_sharpe,
                'oosSharpe': oos_sharpe,
                'isReturn': float(is_return * 100),
                'oosReturn': float(oos_return * 100),
                'degradation': (
                    float((is_sharpe - oos_sharpe) / is_sharpe * 100)
                    if is_sharpe not in (None, 0) and oos_sharpe is not None else None
                ),
                'trainStart': 0,
                'trainEnd': train_end,
                'testStart': test_start,
                'testEnd': test_end,
                'purgeDays': purge_days,
                'embargoDays': embargo_days,
            })
            
            # Heatmap data (monthly performance)
            monthly_heatmap.append({
                'period': f"Period {i+1}",
                'is_perf': float(is_return * 100),
                'oos_perf': float(oos_return * 100),
                'alpha_preserved': (
                    float(oos_sharpe / is_sharpe * 100)
                    if is_sharpe not in (None, 0) and oos_sharpe is not None else None
                ),
            })
        
        # Aggregate statistics
        if results:
            valid_is = [r['isSharpe'] for r in results if r['isSharpe'] is not None]
            valid_oos = [r['oosSharpe'] for r in results if r['oosSharpe'] is not None]
            avg_is_sharpe = float(np.mean(valid_is)) if valid_is else None
            avg_oos_sharpe = float(np.mean(valid_oos)) if valid_oos else None
            consistency = sum(value > 0 for value in valid_oos) / len(valid_oos) * 100 if valid_oos else None
            alpha_decay = (
                (avg_is_sharpe - avg_oos_sharpe) / avg_is_sharpe * 100
                if avg_is_sharpe not in (None, 0) and avg_oos_sharpe is not None else None
            )
        else:
            raise ValueError("Insufficient observations to form the requested walk-forward folds")

        oos_test = {
            'id': 'minimum_oos_sharpe',
            'label': 'Average out-of-sample Sharpe',
            'value': avg_oos_sharpe,
            'operator': '>=',
            'threshold': min_oos_sharpe,
            'status': 'unavailable' if avg_oos_sharpe is None else ('pass' if avg_oos_sharpe >= min_oos_sharpe else 'fail'),
        }
        consistency_test = {
            'id': 'minimum_profitable_fold_consistency',
            'label': 'Profitable out-of-sample folds',
            'value': consistency,
            'operator': '>=',
            'threshold': min_consistency_pct,
            'unit': 'percent',
            'status': 'unavailable' if consistency is None else ('pass' if consistency >= min_consistency_pct else 'fail'),
        }
        verdict_tests = [oos_test, consistency_test]
        if any(test['status'] == 'unavailable' for test in verdict_tests):
            verdict_status = 'UNAVAILABLE'
        elif all(test['status'] == 'pass' for test in verdict_tests):
            verdict_status = 'PASSED'
        else:
            verdict_status = 'FAILED'
        verdict = {
            'status': verdict_status,
            'tests': verdict_tests,
            'thresholds': {
                'minOosSharpe': min_oos_sharpe,
                'minConsistencyPct': min_consistency_pct,
            },
            'methodology': 'deterministic_threshold_rules_not_statistical_confidence',
        }
        # Compatibility for older clients. The mounted UI uses `verdict` and
        # does not present this deterministic score as statistical confidence.
        alpha_shield = {
            'status': 'STRONG' if verdict_status == 'PASSED' else verdict_status,
            'confidence': None,
        }
        
        return {
            'summary': {
                'avgIsSharpe': round(avg_is_sharpe, 2) if avg_is_sharpe is not None else None,
                'avgOosSharpe': round(avg_oos_sharpe, 2) if avg_oos_sharpe is not None else None,
                'consistency': round(consistency, 1) if consistency is not None else None,
                'alphaDecay': round(alpha_decay, 1) if alpha_decay is not None else None,
                'oosWindow': oos_days,
                'totalFolds': len(results)
            },
            'folds': results,
            'heatmap': monthly_heatmap,
            'alphaShield': alpha_shield,
            'verdict': verdict,
        }


def _sensitivity_sharpe(closes: np.ndarray, lookback: int, threshold: float, slippage: float, commission: float) -> Dict[str, Any]:
    """Deterministic momentum Sharpe for one grid cell via the canonical metrics engine."""
    position = 0
    equity = [1.0]
    trades = 0
    for index in range(1, len(closes)):
        daily = closes[index] / closes[index - 1] - 1.0
        if index >= lookback:
            momentum = closes[index] / closes[index - lookback] - 1.0
            if momentum > threshold:
                target = 1
            elif momentum < -threshold:
                target = -1
            else:
                target = position
            if target != position:
                cost_rate = abs(target - position) * (slippage + commission)
                equity[-1] *= max(0.0, 1.0 - cost_rate)
                if position != 0:
                    trades += 1
                position = target
        equity.append(equity[-1] * (1.0 + daily * position) if position != 0 else equity[-1])
    bundle = calculate_performance_metrics(list(equity), [])
    sharpe = bundle.metrics["sharpe"].value
    total_return = bundle.metrics["total_return"].value
    return {
        "lookback": lookback,
        "threshold": threshold,
        "sharpe": sharpe,
        "total_return": total_return,
        "status": "observed" if sharpe is not None else "unavailable",
    }


def _apply_cost_shock(returns: np.ndarray, cost_bps: float) -> np.ndarray:
    return returns - (cost_bps / 10000.0)


def _apply_missing_data(returns: np.ndarray, missing_pct: float, seed: int) -> np.ndarray:
    """Deterministically drop N% of bars by zeroing them (no invented values)."""
    if missing_pct <= 0:
        return returns.copy()
    rng = np.random.default_rng(seed)
    mask = rng.random(len(returns)) < (missing_pct / 100.0)
    result = returns.copy()
    result[mask] = 0.0
    return result


def _apply_delay(returns: np.ndarray, delay_bars: int) -> np.ndarray:
    result = np.zeros_like(returns)
    result[delay_bars:] = returns[:-delay_bars]
    return result


@router.post("/validation/sensitivity")
async def run_sensitivity(request: SensitivityRequest):
    _ensure_no_secrets(request)
    try:
        closes = np.asarray(request.closes, dtype=float)
        slippage = request.slippage_bps / 10000.0
        commission = request.commission_pct / 100.0
        cells = [
            _sensitivity_sharpe(closes, lookback, threshold, slippage, commission)
            for lookback in request.lookbacks
            for threshold in request.thresholds
        ]
        return _sanitize_for_json({
            "status": "success",
            "contract_version": "1.0",
            "methodology": "deterministic_momentum_sharpe_per_grid_cell_canonical_metrics",
            "render": "table_plus_canvas2d_heatmap_no_3d",
            "lookbacks": request.lookbacks,
            "thresholds": request.thresholds,
            "cells": cells,
        })
    except HTTPException:
        raise
    except ValueError as exc:
        raise _error(422, "SENSITIVITY_INVALID", str(exc)) from exc
    except Exception as exc:
        logger.error(f"Sensitivity grid failed: {exc}")
        raise _error(500, "SENSITIVITY_FAILED", "Sensitivity grid failed.") from exc


SKIPPED_SCENARIOS = [
    {"id": "liquidity", "status": "skipped", "reason": "No governed volume/participation input was provided."},
    {"id": "regime", "status": "skipped", "reason": "No governed regime labels exist in this execution artifact."},
    {"id": "adversarial", "status": "skipped", "reason": "No adversarial shock specification was provided."},
]


@router.post("/validation/scenarios")
async def run_scenarios(request: ScenarioRequest):
    _ensure_no_secrets(request)
    try:
        returns = np.asarray(request.returns, dtype=float)
        if len(returns) < 100:
            raise _error(422, "INSUFFICIENT_RETURNS", "At least 100 return observations are required.")
        if np.any(~np.isfinite(returns)):
            raise _error(422, "INVALID_RETURNS", "Returns must contain only finite values.")
        variants = {
            "baseline": returns,
            "cost_shock": _apply_cost_shock(returns, request.cost_shock_bps),
            "missing_data": _apply_missing_data(returns, request.missing_pct, request.seed),
            "delayed_data": _apply_delay(returns, request.delay_bars),
        }
        scenarios = []
        for name, variant in variants.items():
            try:
                analysis = WalkForwardEngine.run_analysis(
                    variant,
                    oos_days=request.oos_days,
                    n_folds=request.n_folds,
                    purge_days=request.purge_days,
                    embargo_days=request.embargo_days,
                )
                scenarios.append({
                    "id": name,
                    "status": "observed",
                    "avg_oos_sharpe": analysis["summary"]["avgOosSharpe"],
                    "consistency": analysis["summary"]["consistency"],
                    "methodology": "walk_forward_engine_reused",
                })
            except ValueError as exc:
                scenarios.append({"id": name, "status": "unavailable", "reason": str(exc)})
        return _sanitize_for_json({
            "status": "success",
            "contract_version": "1.0",
            "methodology": "walk_forward_reused_per_scenario_deterministic_transforms",
            "parameters": {
                "cost_shock_bps": request.cost_shock_bps,
                "missing_pct": request.missing_pct,
                "delay_bars": request.delay_bars,
                "seed": request.seed,
            },
            "scenarios": scenarios,
            "skipped": SKIPPED_SCENARIOS,
        })
    except HTTPException:
        raise
    except Exception as exc:
        logger.error(f"Scenario evidence failed: {exc}")
        raise _error(500, "SCENARIOS_FAILED", "Scenario evidence failed.") from exc


@router.get("/data")
async def get_price_data(
    ticker: str = "SPY",
    lookback_years: int = 5,
    end_date: Optional[str] = None
):
    """Fetch OHLCV data for a specific ticker."""
    try:
        if end_date is None:
            end_date = datetime.now().strftime("%Y-%m-%d")
            
        executor = StrategyExecutor(
            universe="US_TOP50",
            lookback_years=lookback_years,
            end_date=end_date
        )
        df = executor.get_price_data(ticker)
        
        # Format for frontend
        candles = []
        for i in range(len(df)):
            candles.append({
                "time": int(df.index[i].timestamp()),
                "open": float(df['Open'].iloc[i]),
                "high": float(df['High'].iloc[i]),
                "low": float(df['Low'].iloc[i]),
                "close": float(df['Close'].iloc[i]),
                "volume": float(df['Volume'].iloc[i])
            })
            
        return {
            "status": "success",
            "ticker": ticker,
            "candles": candles,
            "metadata": _metadata(
                df,
                engine_version="studio-data/1.0.0",
                parameters={"ticker": ticker, "lookback_years": lookback_years, "end_date": end_date},
            ),
        }
    except StudioDataUnavailableError as exc:
        raise _error(404, "DATA_UNAVAILABLE", str(exc), retryable=True) from exc
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to fetch price data: {e}")
        raise _error(500, "DATA_LOAD_FAILED", "Observed market data could not be loaded.", retryable=True) from e

@router.post("/execute")
async def execute_strategy(request: ExecuteStrategyRequest):
    _ensure_no_secrets(request)
    """
    Execute a strategy against the Parquet dataset (Dynamic Code Injection).
    """
    try:
        executor = StrategyExecutor(
            universe=request.universe,
            lookback_years=request.lookback_years,
            end_date=request.end_date,
            slippage_bps=request.slippage_bps,
            commission_pct=request.commission_pct
        )
        
        ticker = request.ticker or "SPY"
        df = executor.get_price_data(ticker)
        
        if not request.code.strip():
            raise _error(422, "STRATEGY_REQUIRED", "Strategy code is required.")
        result = executor.execute_custom_code(request.code, df)
        metric_warnings = result.get("metrics", {}).get("warnings", [])
        parameters = {
            "ticker": ticker,
            "universe": request.universe,
            "lookback_years": request.lookback_years,
            "end_date": request.end_date,
            "slippage_bps": request.slippage_bps,
            "commission_pct": request.commission_pct,
            "return_convention": "simple_returns_compounded_to_net_equity",
        }
        
        return _sanitize_for_json({
            "status": "success",
            "universe": request.universe,
            "dateRange": {
                "start": executor.start_date.isoformat(),
                "end": executor.end_date.isoformat()
            },
            "metadata": _metadata(
                df,
                engine_version=METRICS_ENGINE_VERSION,
                parameters=parameters,
                code_hash=hashlib.sha256(request.code.encode("utf-8")).hexdigest(),
                warnings=metric_warnings,
            ),
            **result
        })
    except StudioDataUnavailableError as exc:
        raise _error(404, "DATA_UNAVAILABLE", str(exc), retryable=True) from exc
    except ExecutionUnavailableError as exc:
        raise _error(503, "EXECUTION_UNAVAILABLE", str(exc), retryable=True) from exc
    except HTTPException:
        raise
    except (ValueError, StrategyPolicyError, StrategyExecutionError) as exc:
        raise _error(422, "STRATEGY_INVALID", str(exc)) from exc
    except Exception as e:
        logger.error(f"Strategy execution failed: {e}")
        raise _error(500, "STRATEGY_EXECUTION_FAILED", "Strategy execution failed.") from e


@router.post("/monte-carlo")
async def run_monte_carlo(request: MonteCarloRequest):
    _ensure_no_secrets(request)
    """
    Run Monte Carlo simulation for risk analysis.
    Supports bounded named resampling methods with reproducible seeds.
    """
    try:
        returns = np.asarray(request.returns, dtype=float)
        if len(returns) < 20:
            raise _error(422, "INSUFFICIENT_RETURNS", "At least 20 return observations are required.")
        if np.any(~np.isfinite(returns)):
            raise _error(422, "INVALID_RETURNS", "Returns must contain only finite values.")
        
        result = MonteCarloEngine.run_simulation(
            returns=returns,
            n_simulations=request.simulations,
            time_horizon=request.time_horizon,
            seed=request.seed,
            method=request.method,
            block_size=request.block_size,
        )
        
        return {"status": "success", "seed": request.seed, "source_artifact_id": request.source_artifact_id, **_sanitize_for_json(result)}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Monte Carlo simulation failed: {e}")
        raise _error(500, "MONTE_CARLO_FAILED", "Monte Carlo simulation failed.") from e


@router.post("/walk-forward")
async def run_walk_forward(request: WalkForwardRequest):
    _ensure_no_secrets(request)
    """
    Run walk-forward analysis with OOS validation.
    """
    try:
        returns = np.asarray(request.returns, dtype=float)
        if len(returns) < 100:
            raise _error(422, "INSUFFICIENT_RETURNS", "At least 100 return observations are required.")
        if np.any(~np.isfinite(returns)):
            raise _error(422, "INVALID_RETURNS", "Returns must contain only finite values.")
        
        result = WalkForwardEngine.run_analysis(
            returns=returns,
            oos_days=request.oos_days,
            n_folds=request.n_folds,
            purge_days=request.purge_days,
            embargo_days=request.embargo_days,
            min_oos_sharpe=request.min_oos_sharpe,
            min_consistency_pct=request.min_consistency_pct,
        )
        
        return {"status": "success", "source_artifact_id": request.source_artifact_id, **_sanitize_for_json(result)}
    except HTTPException:
        raise
    except ValueError as exc:
        raise _error(422, "WALK_FORWARD_INVALID", str(exc)) from exc
    except Exception as e:
        logger.error(f"Walk-forward analysis failed: {e}")
        raise _error(500, "WALK_FORWARD_FAILED", "Walk-forward analysis failed.") from e


@lru_cache(maxsize=1)
def _load_universes() -> Dict[str, List[str]]:
    universes_path = Path(__file__).parent.parent / "data" / "universes.json"
    with universes_path.open("r", encoding="utf-8") as f:
        return json.load(f)

@router.get("/tickers")
async def get_tickers(q: str = "", universe: str = "all"):
    """Get ticker universe with optional search filter."""
    try:
        universes = _load_universes()
    except (OSError, json.JSONDecodeError) as exc:
        logger.error("Studio ticker catalog failed: %s", exc)
        raise _error(503, "TICKER_CATALOG_UNAVAILABLE", "The ticker catalog is unavailable.", retryable=True) from exc
    if not isinstance(universes, dict) or not all(
        isinstance(name, str) and isinstance(tickers, list) and all(isinstance(ticker, str) for ticker in tickers)
        for name, tickers in universes.items()
    ):
        raise _error(503, "TICKER_CATALOG_INVALID", "The ticker catalog has an invalid format.")
    
    # Combine all tickers or filter by universe
    if universe == "all":
        all_tickers = []
        for key, tickers in universes.items():
            all_tickers.extend(tickers)
        all_tickers = list(set(all_tickers))
    elif universe in universes:
        all_tickers = universes[universe]
    else:
        raise _error(422, "UNIVERSE_UNKNOWN", f"Unknown ticker universe: {universe}.")
    
    # Filter by search query
    if q:
        q_upper = q.upper()
        all_tickers = [t for t in all_tickers if q_upper in t.upper()]
    
    # Sort and limit
    all_tickers.sort()
    return {
        "status": "success",
        "contract_version": "1.0",
        "tickers": all_tickers[:100],
        "total": len(all_tickers),
        "universes": list(universes.keys())
    }


class CreateJobRequest(ContractVersionedModel):
    type: Literal["execute", "monte-carlo", "walk-forward"]
    params: Dict[str, Any] = Field(default_factory=dict)
    idempotency_key: Optional[str] = Field(default=None, min_length=8, max_length=200)

    @model_validator(mode="after")
    def validate_params_for_type(self):
        model = {
            "execute": ExecuteStrategyRequest,
            "monte-carlo": MonteCarloRequest,
            "walk-forward": WalkForwardRequest,
        }[self.type]
        validated = model.model_validate({"contract_version": self.contract_version, **self.params})
        if self.type == "execute" and not validated.code.strip():
            raise ValueError("code must be non-empty")
        self.params = validated.model_dump(exclude={"contract_version"})
        return self


class PromotionAuditRequest(ContractVersionedModel):
    action: Literal["promote", "reject", "override"]
    actor: str = Field(min_length=1, max_length=200)
    rationale: str = Field(min_length=1, max_length=4000)

    @field_validator("actor", "rationale")
    @classmethod
    def require_nonblank_audit_text(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("must not be blank")
        return value.strip()


class PaperDeploymentRequest(ContractVersionedModel):
    name: str = Field(min_length=1, max_length=200)
    source_version_id: str = Field(min_length=1, max_length=128)
    validation_job_id: str = Field(min_length=1, max_length=128)
    promotion_audit_id: str = Field(min_length=1, max_length=128)
    schedule: Dict[str, Any] = Field(default_factory=dict)
    universe: List[str] = Field(min_length=1, max_length=500)
    limits: Dict[str, Any] = Field(default_factory=dict)

    @field_validator("name")
    @classmethod
    def paper_name_nonblank(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("must not be blank")
        return value.strip()


class PaperEventRequest(ContractVersionedModel):
    event_type: Literal["signal", "intended_order", "submitted_order", "fill", "position", "valuation", "alert"]
    payload: Dict[str, Any]
    parent_event_id: Optional[str] = Field(default=None, max_length=128)
    occurred_at: Optional[str] = Field(default=None, max_length=64)


class PaperKillSwitchRequest(ContractVersionedModel):
    engaged: bool
    actor: str = Field(min_length=1, max_length=200)
    reason: str = Field(min_length=1, max_length=4000)


paper_lifecycle = PaperLifecycle()
report_composer = ReportComposer(job_store=job_store)
certification_service = CertificationService(job_store=job_store)


class OutputRecipeRequest(ContractVersionedModel):
    recipe_id: Optional[str] = Field(default=None, max_length=128)
    name: str = Field(min_length=1, max_length=200)
    template: Literal["strategy_review", "validation", "portfolio_review", "paper_reconciliation", "custom"] = "custom"
    blocks: List[Dict[str, Any]] = Field(min_length=1, max_length=100)
    views: Optional[List[Dict[str, Any]]] = Field(default=None, max_length=20)


class RecipeViewRequest(ContractVersionedModel):
    view_id: Optional[str] = Field(default=None, max_length=128)
    name: str = Field(min_length=1, max_length=200)
    layouts: Dict[str, Dict[str, Any]] = Field(min_length=1, max_length=100)


class ResearchNoteRequest(ContractVersionedModel):
    note_id: Optional[str] = Field(default=None, max_length=128)
    title: str = Field(min_length=1, max_length=300)
    content: str = Field(max_length=200000)
    reference: Dict[str, str]


class SharpeEvidenceRequest(ContractVersionedModel):
    returns: List[float] = Field(min_length=30, max_length=MAX_RETURN_OBSERVATIONS)
    trials: int = Field(ge=1, le=100000)
    periods_per_year: int = Field(default=252, ge=1, le=366)
    benchmark_sharpe: float = Field(default=0.0, ge=-20, le=20)


class ParameterInstabilityRequest(ContractVersionedModel):
    segments: List[Dict[str, Any]] = Field(min_length=2, max_length=100)
    periods_per_year: int = Field(default=252, ge=1, le=366)

    @model_validator(mode="after")
    def bound_segment_observations(self):
        if sum(len(segment.get("returns", [])) for segment in self.segments) > 100000:
            raise ValueError("parameter segments exceed the 100000 observation budget")
        return self


class ImplementationFeasibilityRequest(ContractVersionedModel):
    trades: List[Dict[str, Any]] = Field(min_length=1, max_length=10000)
    impact_coefficient: float = Field(default=1.0, ge=0, le=100)
    participation_limit: float = Field(default=0.1, gt=0, le=1)
    portfolio_value: Optional[float] = Field(default=None, gt=0)
    holding_days: int = Field(default=1, ge=1, le=3660)


class DataSubstitutionRequest(ContractVersionedModel):
    primary: List[float] = Field(min_length=30, max_length=MAX_RETURN_OBSERVATIONS)
    alternatives: Dict[str, List[float]]
    periods_per_year: int = Field(default=252, ge=1, le=366)

    @model_validator(mode="after")
    def bound_alternatives(self):
        if not self.alternatives or len(self.alternatives) > 20:
            raise ValueError("one to twenty alternative sources are required")
        if sum(len(values) for values in self.alternatives.values()) > 200000:
            raise ValueError("alternative sources exceed the 200000 observation budget")
        return self


class CertificationRequest(ContractVersionedModel):
    source: Dict[str, str]
    validation_job_id: str = Field(min_length=1, max_length=128)
    tests: List[Dict[str, Any]] = Field(min_length=1, max_length=200)
    thresholds: Dict[str, Any] = Field(default_factory=dict)
    overrides: List[Dict[str, Any]] = Field(default_factory=list, max_length=100)


def _estimate_job(job_type: str, params: Dict[str, Any]) -> Dict[str, Any]:
    """Return a deterministic relative-work estimate for an already validated job."""
    if job_type == "execute":
        work_units = int(params["lookback_years"] * TRADING_DAYS_PER_YEAR)
        budget_units = MAX_LOOKBACK_YEARS * TRADING_DAYS_PER_YEAR
        basis = "requested daily lookback observations"
    elif job_type == "monte-carlo":
        work_units = int(params["simulations"] * params["time_horizon"])
        budget_units = MAX_SIMULATIONS * 2520
        basis = "simulation paths × horizon bars"
    elif job_type == "walk-forward":
        work_units = int(len(params["returns"]) * params["n_folds"])
        budget_units = MAX_RETURN_OBSERVATIONS * MAX_WALK_FORWARD_FOLDS
        basis = "return observations × folds"
    else:
        raise ValueError(f"Unsupported Studio job type: {job_type}")

    utilization = work_units / budget_units if budget_units else 0.0
    size = "small" if utilization <= 0.1 else "standard" if utilization <= 0.5 else "large"
    return {
        "work_units": work_units,
        "budget_units": budget_units,
        "budget_utilization_pct": round(utilization * 100, 2),
        "size": size,
        "basis": basis,
    }


def _execute_job(job_type: str, params: Dict[str, Any]) -> Dict[str, Any]:
    """Invoke the canonical Studio operation from a worker thread."""
    if job_type == "execute":
        return asyncio.run(execute_strategy(ExecuteStrategyRequest(**params)))
    if job_type == "monte-carlo":
        return asyncio.run(run_monte_carlo(MonteCarloRequest(**params)))
    if job_type == "walk-forward":
        return asyncio.run(run_walk_forward(WalkForwardRequest(**params)))
    raise ValueError(f"Unsupported Studio job type: {job_type}")


def _public_job(job: Dict[str, Any]) -> Dict[str, Any]:
    """Return job state without reflecting strategy source or idempotency secrets."""
    return {key: value for key, value in job.items() if key not in {"params", "idempotency_key"}}


@router.post("/portfolio/optimize")
async def optimize_studio_portfolio(request: PortfolioOptimizeRequest):
    _ensure_no_secrets(request)
    try:
        portfolio = await asyncio.to_thread(optimize_portfolio, request.model_dump(exclude={"contract_version"}))
    except PortfolioOptimizationError as exc:
        raise _error(422, "PORTFOLIO_INFEASIBLE", str(exc)) from exc
    return {"status": "success", "contract_version": "1.0", "portfolio": portfolio}


@router.post("/portfolio/versions")
async def save_studio_portfolio_version(request: PortfolioVersionRequest, http_request: Request):
    _ensure_no_secrets(request)
    digest = _owner(http_request)
    inputs = request.inputs.model_dump(exclude={"contract_version"})
    try:
        portfolio = await asyncio.to_thread(optimize_portfolio, inputs)
    except PortfolioOptimizationError as exc:
        raise _error(422, "PORTFOLIO_INFEASIBLE", str(exc)) from exc
    if portfolio["artifact_id"] != request.artifact_id:
        raise _error(409, "PORTFOLIO_ARTIFACT_MISMATCH", "Submitted artifact identity does not match recomputed inputs.")
    if SQLiteStore().count("studio_portfolio_versions") >= get_quota("STUDIO_MAX_PORTFOLIO_VERSIONS"):
        raise _error(429, "PORTFOLIO_VERSION_QUOTA_EXCEEDED", "Saved portfolio version quota exceeded.")
    version_id = f"pfv_{uuid.uuid4().hex[:16]}"
    record = SQLiteStore().put("studio_portfolio_versions", version_id, stamp_owner({
        "version_id": version_id,
        "name": request.name.strip(),
        "artifact_id": request.artifact_id,
        "inputs": inputs,
        "portfolio": portfolio,
    }, digest), create_only=True)
    return {"status": "success", "contract_version": "1.0", "version": record}


@router.get("/portfolio/versions")
async def list_studio_portfolio_versions(http_request: Request, limit: int = 50):
    digest = _owner(http_request)
    records = SQLiteStore().list("studio_portfolio_versions", limit=min(max(limit, 1), 200))
    summaries = [{key: row[key] for key in ("version_id", "name", "artifact_id", "created_at", "updated_at")}
                 for row in records if owner_matches(row, digest)]
    return {"status": "success", "contract_version": "1.0", "versions": summaries}


@router.get("/portfolio/versions/{version_id}")
async def get_studio_portfolio_version(version_id: str, http_request: Request):
    try:
        record = SQLiteStore().get("studio_portfolio_versions", version_id)
    except KeyError as exc:
        raise _error(404, "PORTFOLIO_VERSION_NOT_FOUND", "Portfolio version not found.") from exc
    try:
        require_owner_match(record, _owner(http_request), "portfolio version")
    except OwnerMismatchError:
        raise _forbidden("portfolio version") from None
    return {"status": "success", "contract_version": "1.0", "version": record}


@router.get("/portfolio/versions/{left_id}/compare/{right_id}")
async def compare_studio_portfolio_versions(left_id: str, right_id: str, http_request: Request):
    digest = _owner(http_request)
    store = SQLiteStore()
    try:
        left = store.get("studio_portfolio_versions", left_id)
        right = store.get("studio_portfolio_versions", right_id)
    except KeyError as exc:
        raise _error(404, "PORTFOLIO_VERSION_NOT_FOUND", "One or both portfolio versions were not found.") from exc
    try:
        require_owner_match(left, digest, "portfolio version")
        require_owner_match(right, digest, "portfolio version")
    except OwnerMismatchError:
        raise _forbidden("portfolio version") from None
    assets = sorted(set(left["portfolio"]["assets"]) | set(right["portfolio"]["assets"]))
    weight_delta = {asset: right["portfolio"]["weights"].get(asset, 0.0) - left["portfolio"]["weights"].get(asset, 0.0) for asset in assets}
    metric_names = ("expected_return", "volatility", "sharpe", "tracking_error", "turnover", "estimated_cost_fraction", "concentration_hhi")
    metric_delta = {}
    for name in metric_names:
        left_value, right_value = left["portfolio"]["metrics"].get(name), right["portfolio"]["metrics"].get(name)
        metric_delta[name] = right_value - left_value if left_value is not None and right_value is not None else None
    return {"status": "success", "contract_version": "1.0", "comparison": {
        "left": {"version_id": left_id, "artifact_id": left["artifact_id"], "name": left["name"]},
        "right": {"version_id": right_id, "artifact_id": right["artifact_id"], "name": right["name"]},
        "weight_delta": weight_delta,
        "metric_delta": metric_delta,
    }}


@router.post("/jobs")
async def create_job(request: CreateJobRequest, http_request: Request):
    _ensure_no_secrets(request)
    estimate = _estimate_job(request.type, request.params)
    job = job_store.create(
        job_type=request.type,
        params=request.params,
        idempotency_key=request.idempotency_key,
        request_id=http_request.headers.get("X-Request-ID") or current_request_id(),
        estimate=estimate,
        owner_hash=_owner(http_request),
    )
    if job["status"] == "queued":
        job_store.submit(job["job_id"], _execute_job, request.type, request.params)
    return {"status": "success", "contract_version": "1.0", "job": _public_job(job)}


@router.get("/jobs/{job_id}")
async def get_job(job_id: str, http_request: Request):
    job = _require_job_owner(job_store.get(job_id), _owner(http_request))
    return {"status": "success", "contract_version": "1.0", "job": _public_job(job)}


@router.post("/jobs/{job_id}/cancel")
async def cancel_job(job_id: str, http_request: Request):
    digest = _owner(http_request)
    existing = job_store.get(job_id)
    _require_job_owner(existing, digest)
    job = job_store.cancel(job_id)
    if not job:
        raise _error(404, "JOB_NOT_FOUND", "Job not found.")
    return {"status": "success", "contract_version": "1.0", "job": _public_job(job)}


@router.post("/jobs/{job_id}/promotion-audit")
async def create_promotion_audit(job_id: str, request: PromotionAuditRequest, http_request: Request):
    _ensure_no_secrets(request)
    job = _require_job_owner(job_store.get(job_id), _owner(http_request))
    result = job.get("result") or {}
    verdict = result.get("verdict")
    if not isinstance(verdict, dict):
        raise _error(422, "VERDICT_UNAVAILABLE", "The validation job has no promotion verdict.")
    try:
        record = job_store.append_audit(job_id, {
            "action": request.action,
            "actor": request.actor.strip(),
            "rationale": request.rationale.strip(),
            "verdict": verdict,
            "thresholds": verdict.get("thresholds", {}),
            "input_hash": job.get("input_hash"),
        })
    except ValueError as exc:
        raise _error(409, "PROMOTION_NOT_READY", str(exc)) from exc
    return {"status": "success", "contract_version": "1.0", "audit": record}


@router.get("/jobs/{job_id}/promotion-audit")
async def get_promotion_audit(job_id: str, http_request: Request):
    _require_job_owner(job_store.get(job_id), _owner(http_request))
    try:
        records = job_store.get_audit(job_id)
    except KeyError as exc:
        raise _error(404, "JOB_NOT_FOUND", "Job not found.") from exc
    return {"status": "success", "contract_version": "1.0", "records": records}


def _paper_error(exc: PaperLifecycleError) -> HTTPException:
    return _error(exc.status_code, exc.code, str(exc))


@router.post("/paper/deployments")
async def create_paper_deployment(request: PaperDeploymentRequest, http_request: Request):
    _ensure_no_secrets(request)
    digest = _owner(http_request)
    store = SQLiteStore()
    try:
        source_version = store.get("studio_portfolio_versions", request.source_version_id)
    except KeyError as exc:
        raise _error(404, "PORTFOLIO_VERSION_NOT_FOUND", "Portfolio version not found.") from exc
    try:
        require_owner_match(source_version, digest, "portfolio version")
    except OwnerMismatchError:
        raise _forbidden("portfolio version") from None
    validation_job = _require_job_owner(job_store.get(request.validation_job_id), digest)
    audits = job_store.get_audit(request.validation_job_id)
    promotion = next((row for row in audits if row.get("audit_id") == request.promotion_audit_id), None)
    if not promotion:
        raise _error(404, "PROMOTION_AUDIT_NOT_FOUND", "Promotion audit record not found.")
    try:
        deployment = paper_lifecycle.create_deployment(
            name=request.name,
            source_version=source_version,
            validation_job=validation_job,
            promotion=promotion,
            schedule=request.schedule,
            universe=request.universe,
            limits=request.limits,
        )
    except PaperLifecycleError as exc:
        raise _paper_error(exc) from exc
    remember_owner(store, deployment["deployment_id"], digest)
    return {"status": "success", "contract_version": "1.0", "deployment": deployment}


@router.get("/paper/deployments")
async def list_paper_deployments(http_request: Request, limit: int = 100):
    digest = _owner(http_request)
    store = SQLiteStore()
    deployments = paper_lifecycle.list_deployments(min(max(limit, 1), 200))
    visible = [row for row in deployments
               if indexed_visible(store, row.get("deployment_id", ""), digest)]
    return {"status": "success", "contract_version": "1.0", "deployments": visible}


@router.get("/paper/deployments/{deployment_id}")
async def get_paper_deployment(deployment_id: str, http_request: Request):
    _require_indexed_owner(SQLiteStore(), deployment_id, _owner(http_request), "paper deployment")
    try:
        deployment = paper_lifecycle.get_deployment(deployment_id)
    except PaperLifecycleError as exc:
        raise _paper_error(exc) from exc
    return {"status": "success", "contract_version": "1.0", "deployment": deployment}


@router.post("/paper/deployments/{deployment_id}/events")
async def append_paper_event(deployment_id: str, request: PaperEventRequest, http_request: Request):
    _ensure_no_secrets(request)
    _require_indexed_owner(SQLiteStore(), deployment_id, _owner(http_request), "paper deployment")
    _ensure_no_secrets(request)
    try:
        event = paper_lifecycle.append_event(
            deployment_id, request.event_type, request.payload,
            request.parent_event_id, request.occurred_at,
        )
    except PaperLifecycleError as exc:
        raise _paper_error(exc) from exc
    return {"status": "success", "contract_version": "1.0", "event": event}


@router.get("/paper/deployments/{deployment_id}/events")
async def list_paper_events(deployment_id: str, http_request: Request, limit: int = 500):
    _require_indexed_owner(SQLiteStore(), deployment_id, _owner(http_request), "paper deployment")
    try:
        events = paper_lifecycle.list_events(deployment_id, min(max(limit, 1), 1000))
    except PaperLifecycleError as exc:
        raise _paper_error(exc) from exc
    return {"status": "success", "contract_version": "1.0", "events": events}


@router.get("/paper/deployments/{deployment_id}/events/{event_id}/trace")
async def trace_paper_event(deployment_id: str, event_id: str, http_request: Request):
    _require_indexed_owner(SQLiteStore(), deployment_id, _owner(http_request), "paper deployment")
    try:
        trace = paper_lifecycle.trace(deployment_id, event_id)
    except PaperLifecycleError as exc:
        raise _paper_error(exc) from exc
    return {"status": "success", "contract_version": "1.0", "trace": trace}


@router.get("/paper/deployments/{deployment_id}/reconciliation")
async def reconcile_paper_deployment(deployment_id: str, http_request: Request):
    _require_indexed_owner(SQLiteStore(), deployment_id, _owner(http_request), "paper deployment")
    try:
        reconciliation = paper_lifecycle.reconciliation(deployment_id)
    except PaperLifecycleError as exc:
        raise _paper_error(exc) from exc
    return {"status": "success", "contract_version": "1.0", "reconciliation": reconciliation}


@router.post("/paper/deployments/{deployment_id}/kill-switch")
async def set_paper_kill_switch(deployment_id: str, request: PaperKillSwitchRequest, http_request: Request):
    _ensure_no_secrets(request)
    _require_indexed_owner(SQLiteStore(), deployment_id, _owner(http_request), "paper deployment")
    _ensure_no_secrets(request)
    try:
        deployment = paper_lifecycle.set_kill_switch(
            deployment_id, engaged=request.engaged, actor=request.actor, reason=request.reason,
        )
    except PaperLifecycleError as exc:
        raise _paper_error(exc) from exc
    return {"status": "success", "contract_version": "1.0", "deployment": deployment}


def _report_error(exc: ReportError) -> HTTPException:
    return _error(exc.status_code, exc.code, str(exc))


def _advanced_error(exc: AdvancedValidationError) -> HTTPException:
    return _error(422, "ADVANCED_VALIDATION_INVALID", str(exc))


@router.post("/validation/advanced/sharpe")
async def run_advanced_sharpe(request: SharpeEvidenceRequest):
    _ensure_no_secrets(request)
    try:
        result = sharpe_evidence(request.returns, trials=request.trials, periods_per_year=request.periods_per_year, benchmark_sharpe=request.benchmark_sharpe)
    except AdvancedValidationError as exc:
        raise _advanced_error(exc) from exc
    return {"status": "success", "contract_version": "1.0", "evidence": result}


@router.post("/validation/advanced/parameter-instability")
async def run_parameter_instability(request: ParameterInstabilityRequest):
    _ensure_no_secrets(request)
    try:
        result = parameter_instability(request.segments, periods_per_year=request.periods_per_year)
    except AdvancedValidationError as exc:
        raise _advanced_error(exc) from exc
    return {"status": "success", "contract_version": "1.0", "evidence": result}


@router.post("/validation/advanced/implementation")
async def run_implementation_feasibility(request: ImplementationFeasibilityRequest):
    _ensure_no_secrets(request)
    try:
        result = implementation_feasibility(request.trades, impact_coefficient=request.impact_coefficient, participation_limit=request.participation_limit, portfolio_value=request.portfolio_value, holding_days=request.holding_days)
    except AdvancedValidationError as exc:
        raise _advanced_error(exc) from exc
    return {"status": "success", "contract_version": "1.0", "evidence": result}


@router.post("/validation/advanced/data-substitution")
async def run_data_substitution(request: DataSubstitutionRequest):
    _ensure_no_secrets(request)
    try:
        result = data_substitution_sensitivity(request.primary, request.alternatives, periods_per_year=request.periods_per_year)
    except AdvancedValidationError as exc:
        raise _advanced_error(exc) from exc
    return {"status": "success", "contract_version": "1.0", "evidence": result}


@router.post("/validation/certifications")
async def create_certification(request: CertificationRequest, http_request: Request):
    _ensure_no_secrets(request)
    digest = _owner(http_request)
    _require_job_owner(job_store.get(request.validation_job_id), digest, "validation job")
    try:
        bundle = certification_service.create(source=request.source, validation_job_id=request.validation_job_id, tests=request.tests, thresholds=request.thresholds, overrides=request.overrides)
    except CertificationError as exc:
        raise _error(exc.status_code, "CERTIFICATION_INVALID", str(exc)) from exc
    remember_owner(SQLiteStore(), bundle["certification_id"], digest)
    return {"status": "success", "contract_version": "1.0", "certification": bundle}


@router.get("/validation/certifications/{certification_id}")
async def get_certification(certification_id: str, http_request: Request):
    _require_indexed_owner(SQLiteStore(), certification_id, _owner(http_request), "certification")
    try:
        bundle = certification_service.get(certification_id)
    except CertificationError as exc:
        raise _error(404, "CERTIFICATION_NOT_FOUND", str(exc)) from exc
    return {"status": "success", "contract_version": "1.0", "certification": bundle}


@router.get("/validation/certifications/{certification_id}/reproduce")
async def reproduce_certification(certification_id: str, http_request: Request):
    _require_indexed_owner(SQLiteStore(), certification_id, _owner(http_request), "certification")
    try:
        result = certification_service.reproduce(certification_id)
    except (CertificationError, ReportError) as exc:
        raise _error(409, "CERTIFICATION_NOT_REPRODUCIBLE", str(exc)) from exc
    return {"status": "success", "contract_version": "1.0", "reproduction": result}


@router.post("/reports/recipes")
async def save_output_recipe(request: OutputRecipeRequest, http_request: Request):
    _ensure_no_secrets(request)
    try:
        recipe = report_composer.save_recipe(request.name, request.template, request.blocks, request.recipe_id, request.views)
    except ReportError as exc:
        raise _report_error(exc) from exc
    remember_owner(SQLiteStore(), recipe["recipe_id"], _owner(http_request))
    return {"status": "success", "contract_version": "1.0", "recipe": recipe}


@router.get("/reports/templates")
async def list_report_templates():
    from app.services.studio.reports import TEMPLATE_DEFAULTS, TEMPLATE_REQUIRED_PATHS
    return {"status": "success", "contract_version": "1.0", "templates": [
        {"name": name, "label": spec["label"], "description": spec["description"],
         "required_paths": TEMPLATE_REQUIRED_PATHS.get(name, []), "block_count": len(spec["blocks"])}
        for name, spec in TEMPLATE_DEFAULTS.items()
    ]}


@router.get("/reports/templates/{template_name}")
async def get_report_template(template_name: str):
    from app.services.studio.reports import TEMPLATE_DEFAULTS, TEMPLATE_REQUIRED_PATHS, template_block_list
    if template_name not in TEMPLATE_DEFAULTS:
        raise _error(404, "REPORT_TEMPLATE_NOT_FOUND", f"Unknown report template: {template_name}.")
    spec = TEMPLATE_DEFAULTS[template_name]
    return {"status": "success", "contract_version": "1.0", "template": {
        "name": template_name, "label": spec["label"], "description": spec["description"],
        "required_paths": TEMPLATE_REQUIRED_PATHS.get(template_name, []),
        "blocks": template_block_list(template_name),
    }}


@router.post("/reports/recipes/{recipe_id}/views")
async def save_recipe_view(recipe_id: str, request: RecipeViewRequest, http_request: Request):
    _ensure_no_secrets(request)
    _require_indexed_owner(SQLiteStore(), recipe_id, _owner(http_request), "output recipe")
    _ensure_no_secrets(request)
    try:
        recipe = report_composer.save_view(recipe_id, request.name, request.layouts, request.view_id)
    except ReportError as exc:
        raise _report_error(exc) from exc
    return {"status": "success", "contract_version": "1.0", "recipe": recipe}


@router.get("/reports/recipes")
async def list_output_recipes(http_request: Request):
    digest = _owner(http_request)
    store = SQLiteStore()
    recipes = report_composer.list_recipes()
    return {"status": "success", "contract_version": "1.0", "recipes": [
        row for row in recipes if indexed_visible(store, row.get("recipe_id", ""), digest)]}


@router.get("/reports/recipes/{recipe_id}")
async def get_output_recipe(recipe_id: str, http_request: Request):
    _require_indexed_owner(SQLiteStore(), recipe_id, _owner(http_request), "output recipe")
    try:
        recipe = report_composer.get_recipe(recipe_id)
    except ReportError as exc:
        raise _report_error(exc) from exc
    return {"status": "success", "contract_version": "1.0", "recipe": recipe}


@router.get("/reports/recipes/{recipe_id}/render")
async def render_output_recipe(recipe_id: str, http_request: Request):
    _require_indexed_owner(SQLiteStore(), recipe_id, _owner(http_request), "output recipe")
    try:
        report = report_composer.render(recipe_id)
    except ReportError as exc:
        raise _report_error(exc) from exc
    return {"status": "success", "contract_version": "1.0", "report": report}


@router.get("/reports/recipes/{recipe_id}/export/{format_name}")
async def export_output_recipe(recipe_id: str, format_name: Literal["html", "json", "csv", "arrow"], http_request: Request):
    _require_indexed_owner(SQLiteStore(), recipe_id, _owner(http_request), "output recipe")
    try:
        safe_name = validate_filename(f"{recipe_id}.{format_name}", location="export filename")
    except UnsafeFilenameError as exc:
        raise _error(400, "EXPORT_FILENAME_INVALID", str(exc)) from exc
    try:
        content = getattr(report_composer, f"export_{format_name}")(recipe_id)
    except ReportError as exc:
        raise _report_error(exc) from exc
    try:
        assert_no_secret_material_in_export(content, location="export.body")
    except SecretMaterialError as exc:
        raise _error(422, "SECRET_MATERIAL_REJECTED", str(exc)) from exc
    media = {"html": "text/html; charset=utf-8", "json": "application/json", "csv": "text/csv; charset=utf-8", "arrow": "application/vnd.apache.arrow.stream"}[format_name]
    return Response(content=content, media_type=media, headers={"Content-Disposition": f'attachment; filename="{safe_name}"'})


@router.post("/reports/notes")
async def save_research_note(request: ResearchNoteRequest, http_request: Request):
    _ensure_no_secrets(request)
    try:
        note = report_composer.save_note(request.title, request.content, request.reference, request.note_id)
    except ReportError as exc:
        raise _report_error(exc) from exc
    remember_owner(SQLiteStore(), note["note_id"], _owner(http_request))
    return {"status": "success", "contract_version": "1.0", "note": note}


@router.get("/reports/notes")
async def list_research_notes(http_request: Request):
    digest = _owner(http_request)
    store = SQLiteStore()
    notes = report_composer.list_notes()
    return {"status": "success", "contract_version": "1.0", "notes": [
        row for row in notes if indexed_visible(store, row.get("note_id", ""), digest)]}


@router.get("/jobs/{job_id}/events")
async def job_events(job_id: str, request: Request):
    stored = job_store.get(job_id)
    if not stored:
        raise _error(404, "JOB_NOT_FOUND", "Job not found.")
    try:
        require_owner_match(stored, _owner(request), "job")
    except OwnerMismatchError:
        raise _forbidden("job") from None
    # EventSource cannot send headers, so browsers correlate streams via
    # ?request_id=; the middleware request ID stays authoritative in logs.
    stream_request_id = request.query_params.get("request_id") or stored.get("request_id") or current_request_id()

    raw_last_id = request.headers.get("Last-Event-ID", "0")
    try:
        resume_after = max(0, int(raw_last_id))
    except ValueError:
        raise _error(400, "LAST_EVENT_ID_INVALID", "Last-Event-ID must be an integer.")

    async def event_stream():
        cursor = resume_after
        idle_ticks = 0
        while not await request.is_disconnected():
            snapshot = job_store.get(job_id)
            if not snapshot:
                return
            fresh = [event for event in snapshot.get("events", []) if int(event["id"]) > cursor]
            for event in fresh:
                cursor = int(event["id"])
                payload = {**event, "job_id": job_id, "progress": snapshot.get("progress")}
                yield f"id: {cursor}\nevent: {event['status']}\ndata: {json.dumps(payload)}\n\n"
            if snapshot["status"] in {"completed", "failed", "cancelled", "partial"}:
                return
            idle_ticks += 1
            if idle_ticks % 40 == 0:
                yield f"event: heartbeat\ndata: {json.dumps({'job_id': job_id, 'status': snapshot['status']})}\n\n"
            await asyncio.sleep(0.25)

    return StreamingResponse(event_stream(), media_type="text/event-stream", headers={
        "Cache-Control": "no-cache",
        "X-Accel-Buffering": "no",
        "X-Request-ID": str(stream_request_id or current_request_id() or ""),
    })


def _job_status_counts() -> dict[str, int]:
    counts: dict[str, int] = {}
    try:
        records = job_store._jobs
    except AttributeError:
        return counts
    for job in records.values():
        status = str(job.get("status", "unknown"))
        counts[status] = counts.get(status, 0) + 1
    return counts


@router.get("/health")
async def health_check():
    """Report liveness plus P15 job/queue/storage diagnostics.

    No secrets, payloads, or artifact ids are returned: counts, route
    templates (via observability aggregates), quota values, and flag states
    only. ``request_id`` carries the middleware-propagated ID (via the
    observability contextvar) so operators can join health output with
    structured logs; it is null outside a middleware-handled request.
    """
    store = SQLiteStore()
    namespaces = (
        "studio_portfolio_versions",
        "studio_paper_deployments",
        "studio_output_recipes",
        "studio_research_notes",
        "studio_certifications",
    )
    storage = {}
    for namespace in namespaces:
        try:
            storage[namespace] = store.count(namespace)
        except Exception:
            storage[namespace] = -1
    return {
        "status": "ok",
        "contract_version": "1.0",
        "check": "liveness",
        "engine": "Sovereign Algo Studio",
        "version": "1.0.0",
        "request_id": current_request_id(),
        "execution": {
            "mode": "isolated_one_shot",
            "readiness": "not_checked",
            "note": "Execution readiness is determined by an actual bounded run and fails closed when unavailable.",
        },
        "jobs": {
            "by_status": _job_status_counts(),
            "max_concurrent": get_quota("STUDIO_MAX_CONCURRENT_JOBS"),
        },
        "storage": storage,
        "quotas": quota_snapshot(),
        "feature_flags": flag_snapshot(),
    }
