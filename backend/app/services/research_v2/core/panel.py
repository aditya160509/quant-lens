"""Point-in-time research panel.

A panel is a set of aligned (date x ticker) matrices sampled at formation
dates: the signal, controls, portfolio weights, and the dependent variable
measured over the holding period that *follows* each formation date.

Look-ahead rules enforced here:

* Price signals at date t use prices up to and including t.
* Fundamental signals use reports only after a filing lag (default 90 days)
  and are never back-filled before the first report.
* Market cap is price(t) x shares outstanding known at t.
* The dependent variable at t is realised over (t, t + h].
"""

from __future__ import annotations

from dataclasses import dataclass, field, replace
import math
import warnings
from typing import Any

import numpy as np
import pandas as pd

from .holdout import get_window, study_key
from .data_loader import (
    UnknownSymbolsError,
    annual_growth,
    fundamentals_coverage_start,
    load_macro,
    load_signal_upload,
    monthly_factor_returns,
    ohlcv_matrices,
    parse_symbols,
    point_in_time_fundamental,
    static_sectors,
)

PRICE_SIGNALS = {"momentum", "reversal", "low_vol", "yang_zhang_vol", "garman_klass_vol", "beta", "ivol"}
FUNDAMENTAL_SIGNALS = {"size", "value", "quality", "profitability", "investment", "leverage"}
SIGNALS = sorted(PRICE_SIGNALS | FUNDAMENTAL_SIGNALS)
CONTROLS = ["size", "value", "momentum", "reversal", "beta", "ivol", "asset_growth", "profitability", "leverage"]
CONTROL_SETS = {
    "none": [],
    "size": ["size"],
    "size,value": ["size", "value"],
    "size,value,momentum": ["size", "value", "momentum"],
    "size,value,momentum,volatility": ["size", "value", "momentum", "ivol"],
    "full": CONTROLS,
}
DEPENDENT_VARIABLES = ["forward_return", "ff3_alpha", "ff5_alpha", "realized_vol", "spread", "dollar_volume"]
UNIVERSE_FILTERS = ["large_cap", "mid_cap", "small_cap", "ex_financials", "ex_utilities", "ex_microcaps"]
REBALANCE_STEP = {"monthly": 1, "quarterly": 3, "annual": 12}


@dataclass
class Panel:
    symbols: list[str]
    dates: pd.DatetimeIndex
    returns: pd.DataFrame          # monthly simple returns (all months)
    signal: pd.DataFrame           # formation dates x tickers
    dependent: pd.DataFrame        # outcome over the holding period after each date
    controls: dict[str, pd.DataFrame]
    weights: pd.DataFrame
    market_cap: pd.DataFrame
    factors: pd.DataFrame          # monthly FF5 + UMD + RF indexed by month end
    macro: pd.DataFrame            # month-end macro indexed by date
    config: dict[str, Any]
    caveats: list[str] = field(default_factory=list)
    context: dict[str, Any] = field(default_factory=dict, repr=False)  # full-history inputs for recomputing signals

    @property
    def holding_months(self) -> int:
        return int(self.config["holding_months"])

    def with_signal(self, signal: pd.DataFrame, **config: Any) -> "Panel":
        return replace(self, signal=signal.reindex_like(self.signal), config={**self.config, **config})

    def subset_dates(self, mask: pd.Series | np.ndarray) -> "Panel":
        keep = self.dates[np.asarray(mask, dtype=bool)]
        return replace(
            self,
            dates=keep,
            signal=self.signal.loc[keep],
            dependent=self.dependent.loc[keep],
            controls={k: v.loc[keep] for k, v in self.controls.items()},
            weights=self.weights.loc[keep],
            market_cap=self.market_cap.loc[keep],
        )

    def subset_symbols(self, symbols: list[str]) -> "Panel":
        cols = [s for s in symbols if s in self.signal.columns]
        return replace(
            self,
            symbols=cols,
            returns=self.returns[cols],
            signal=self.signal[cols],
            dependent=self.dependent[cols],
            controls={k: v[cols] for k, v in self.controls.items()},
            weights=self.weights[cols],
            market_cap=self.market_cap[cols],
        )

    def stacked(self, control_names: list[str] | None = None) -> pd.DataFrame:
        """Long (date, ticker) frame: dependent, signal and controls."""

        names = list(self.controls) if control_names is None else [c for c in control_names if c in self.controls]
        parts = [self.dependent.stack().rename("y"), self.signal.stack().rename("signal")]
        parts += [self.controls[n].stack().rename(n) for n in names]
        out = pd.concat(parts, axis=1).replace([np.inf, -np.inf], np.nan).dropna()
        out.index = out.index.set_names(["date", "ticker"])
        return out


# ---------------------------------------------------------------------------
# construction


def build_panel(payload: dict[str, Any], default_limit: int = 400) -> Panel:
    cfg = normalize_config(payload, default_limit)
    symbols = parse_symbols({**payload, "max_symbols": cfg["max_symbols"]}, default_limit=cfg["max_symbols"])
    lookback = cfg["lookback_days"]
    daily = ohlcv_matrices(symbols, lookback)
    if not daily:
        raise UnknownSymbolsError(symbols[:10])
    close_d = daily["Close"]
    close_m = close_d.resample("ME").last()
    close_m = close_m.loc[:, close_m.notna().sum() >= 24]
    symbols = list(close_m.columns)
    returns = close_m.pct_change(fill_method=None).replace([np.inf, -np.inf], np.nan)
    returns = returns.where(returns.abs() < 3)  # drop split/bad-print artefacts (>300% in a month)
    all_dates = returns.index
    caveats: list[str] = []

    shares = point_in_time_fundamental("Ordinary Shares Number", all_dates, symbols)
    market_cap = close_m * shares
    factors = _monthly_factors(all_dates)
    macro = _monthly_macro(all_dates)

    step = REBALANCE_STEP[cfg["rebalancing_frequency"]]
    horizon = cfg["holding_months"]
    formation = all_dates[::-1][horizon::step][::-1] if len(all_dates) > horizon else all_dates[:0]
    ctx = {"close_m": close_m, "returns": returns, "daily": daily, "market_cap": market_cap, "factors": factors, "symbols": symbols, "dates": all_dates}

    signal = compute_signal(cfg["signal"], ctx, payload)
    dependent = compute_dependent(cfg["dependent_variable"], horizon, ctx)
    control_names = [c for c in cfg["controls"] if c != _control_alias(cfg["signal"])]
    controls = {name: compute_control(name, ctx) for name in control_names}
    weights = _weights(cfg["weighting"], signal, market_cap)

    universe_mask = _universe_mask(cfg["universe_filters"], market_cap, symbols)
    signal = signal.where(universe_mask)

    if cfg["signal"] in FUNDAMENTAL_SIGNALS or any(c in {"size", "value", "asset_growth", "profitability", "leverage"} for c in control_names) or cfg["weighting"] == "value" or any(f in {"large_cap", "mid_cap", "small_cap", "ex_microcaps"} for f in cfg["universe_filters"]):
        start = fundamentals_coverage_start()
        if start is not None:
            caveats.append(f"Fundamental inputs are point-in-time with a 90-day filing lag; they exist only from {start.date()} onward, so earlier months drop out.")

    # lookback_days defines the formation window; earlier history is fetched (2x) only to warm up signals.
    idx = formation[formation >= all_dates[-1] - pd.Timedelta(days=lookback)] if len(all_dates) else formation
    protected = get_window(study_key(cfg, payload.get("universe")))
    if protected and not payload.get("_evaluate_protected"):
        start_ts = pd.Timestamp(protected["start"])
        idx = idx[idx + pd.DateOffset(months=horizon) < start_ts]
        caveats.append(f"A protected out-of-sample window from {protected['start']} is reserved for this study and excluded here.")
    panel = Panel(
        symbols=symbols,
        dates=idx,
        returns=returns,
        signal=signal.reindex(idx),
        dependent=dependent.reindex(idx),
        controls={k: v.reindex(idx) for k, v in controls.items()},
        weights=weights.reindex(idx),
        market_cap=market_cap.reindex(idx),
        factors=factors,
        macro=macro,
        config=cfg,
        caveats=caveats,
        context=ctx,
    )
    panel = _apply_transform(panel, cfg["signal_transform"])
    usable = panel.signal.notna().sum(axis=1) >= cfg["min_assets"]
    panel = panel.subset_dates(usable.to_numpy())
    if len(panel.dates) < 12:
        raise ValueError(f"Only {len(panel.dates)} formation dates have >= {cfg['min_assets']} assets with the '{cfg['signal']}' signal. Widen the universe or lookback, or choose a price-based signal.")
    return panel


def normalize_config(payload: dict[str, Any], default_limit: int = 400) -> dict[str, Any]:
    signal = str(payload.get("signal") or payload.get("signal_definition") or "momentum").lower()
    aliases = {"book_to_market": "value", "market_cap": "size", "short_reversal": "reversal", "1m_reversal": "reversal", "volatility": "low_vol", "realized_vol": "low_vol", "asset_growth": "investment", "roe": "quality"}
    signal = aliases.get(signal, signal)
    upload = payload.get("signal_csv_path") or payload.get("signal_upload_path")
    if upload:
        signal = "uploaded"
    elif signal not in SIGNALS:
        raise ValueError(f"Unknown signal '{signal}'. Choose one of: {', '.join(SIGNALS)}")
    controls = payload.get("controls") if payload.get("controls") is not None else "none"
    if isinstance(controls, str):
        key = controls.strip().lower()
        controls = CONTROL_SETS.get(key, [c.strip() for c in key.split(",") if c.strip()])
    # A control identical to the signal makes every cross-section singular
    controls = [str(c).lower() for c in controls if str(c).lower() != signal]
    unknown = [c for c in controls if c not in CONTROLS]
    if unknown:
        raise ValueError(f"Unknown controls: {', '.join(unknown)}")
    freq = str(payload.get("rebalancing_frequency") or "monthly").lower()
    freq = {"month": "monthly", "quarter": "quarterly", "year": "annual", "annually": "annual"}.get(freq, freq)
    if freq not in REBALANCE_STEP:
        raise ValueError("rebalancing_frequency must be monthly, quarterly or annual")
    holding = int(payload.get("forward_months") or payload.get("horizon_months") or REBALANCE_STEP[freq])
    dv = str(payload.get("dependent_variable") or "forward_return").lower()
    if dv not in DEPENDENT_VARIABLES:
        raise ValueError(f"dependent_variable must be one of {DEPENDENT_VARIABLES}")
    filters = payload.get("universe_filters") or []
    if isinstance(filters, str):
        filters = [f.strip() for f in filters.split(",") if f.strip() and f.strip() != "none"]
    bad = [f for f in filters if f not in UNIVERSE_FILTERS]
    if bad:
        raise ValueError(f"Unknown universe filters: {', '.join(bad)}")
    return {
        "signal": signal,
        "signal_upload": upload,
        "controls": controls,
        "weighting": str(payload.get("weighting") or payload.get("weighting_scheme") or "equal").lower(),
        "rebalancing_frequency": freq,
        "holding_months": holding,
        "dependent_variable": dv,
        "universe_filters": filters,
        "signal_transform": str(payload.get("signal_transform") or "raw").lower(),
        "lookback_days": int(payload.get("lookback_days") or 3650),
        "max_symbols": int(payload.get("max_symbols") or default_limit),
        "min_assets": int(payload.get("min_assets") or 30),
        "nw_lag": payload.get("nw_lag"),
        "second_signal": str(payload.get("second_signal") or "low_vol").lower(),
    }


def _control_alias(signal: str) -> str:
    return {"investment": "asset_growth", "quality": "profitability", "low_vol": "ivol"}.get(signal, signal)


# ---------------------------------------------------------------------------
# signals and controls


def compute_signal(name: str, ctx: dict[str, Any], payload: dict[str, Any] | None = None) -> pd.DataFrame:
    close_m, returns, dates, symbols = ctx["close_m"], ctx["returns"], ctx["dates"], ctx["symbols"]
    if name == "uploaded":
        upload = load_signal_upload((payload or {}).get("signal_csv_path") or (payload or {}).get("signal_upload_path"))
        if upload.empty:
            raise ValueError("Signal upload has no rows with date, ticker and signal columns.")
        wide = upload.pivot_table(index="date", columns="ticker", values="signal", aggfunc="last")
        wide = wide.resample("ME").last()
        return wide.reindex(index=dates, columns=symbols)
    if name == "momentum":  # 12-1 month return, skipping the most recent month
        return close_m.shift(1) / close_m.shift(12) - 1
    if name == "reversal":
        return -returns
    if name == "low_vol":
        return -returns.rolling(12, min_periods=10).std()
    if name in {"yang_zhang_vol", "garman_klass_vol"}:
        return -_range_volatility(ctx["daily"], name).reindex(index=dates, columns=symbols)
    if name == "beta":
        return compute_control("beta", ctx)
    if name == "ivol":
        return -compute_control("ivol", ctx)
    if name == "size":
        return compute_control("size", ctx)
    if name == "value":
        return compute_control("value", ctx)
    if name == "quality":
        ni = point_in_time_fundamental("Net Income Common Stockholders", dates, symbols)
        eq = point_in_time_fundamental("Stockholders Equity", dates, symbols)
        return ni / eq.where(eq > 0)
    if name == "profitability":
        return compute_control("profitability", ctx)
    if name == "investment":
        return -compute_control("asset_growth", ctx)  # low investment earns more (CMA sign)
    if name == "leverage":
        return compute_control("leverage", ctx)
    raise ValueError(f"Unknown signal {name}")


def compute_control(name: str, ctx: dict[str, Any]) -> pd.DataFrame:
    close_m, returns, dates, symbols, mcap = ctx["close_m"], ctx["returns"], ctx["dates"], ctx["symbols"], ctx["market_cap"]
    if name == "size":
        return np.log(mcap.where(mcap > 0))
    if name == "value":
        book = point_in_time_fundamental("Stockholders Equity", dates, symbols)
        return np.log((book / mcap).where(book > 0))
    if name == "momentum":
        return close_m.shift(1) / close_m.shift(12) - 1
    if name == "reversal":
        return returns.copy()
    if name in {"beta", "ivol"}:
        beta, ivol = _rolling_beta_ivol(returns, ctx["factors"])
        return beta if name == "beta" else ivol
    if name == "asset_growth":
        return annual_growth("Total Assets", dates, symbols)
    if name == "profitability":  # Novy-Marx gross profitability
        gp = point_in_time_fundamental("Gross Profit", dates, symbols)
        assets = point_in_time_fundamental("Total Assets", dates, symbols)
        return gp / assets.where(assets > 0)
    if name == "leverage":
        debt = point_in_time_fundamental("Total Debt", dates, symbols)
        assets = point_in_time_fundamental("Total Assets", dates, symbols)
        return debt / assets.where(assets > 0)
    raise ValueError(f"Unknown control {name}")


def _rolling_beta_ivol(returns: pd.DataFrame, factors: pd.DataFrame, window: int = 36) -> tuple[pd.DataFrame, pd.DataFrame]:
    if factors.empty or "mkt_rf" not in factors:
        mkt = returns.mean(axis=1)
        rf = pd.Series(0.0, index=returns.index)
    else:
        mkt = factors["mkt_rf"].reindex(returns.index)
        rf = factors["rf"].reindex(returns.index).fillna(0) if "rf" in factors else pd.Series(0.0, index=returns.index)
    ex = returns.sub(rf, axis=0)
    mp = window * 2 // 3
    cov = ex.rolling(window, min_periods=mp).cov(mkt)
    var = mkt.rolling(window, min_periods=mp).var()
    beta = cov.div(var, axis=0)
    mean_ex = ex.rolling(window, min_periods=mp).mean()
    mean_m = mkt.rolling(window, min_periods=mp).mean()
    alpha = mean_ex.sub(beta.mul(mean_m, axis=0))
    resid = ex.sub(alpha).sub(beta.mul(mkt, axis=0))
    ivol = resid.rolling(window, min_periods=mp).std()
    return beta, ivol


def _range_volatility(daily: dict[str, pd.DataFrame], kind: str, window_days: int = 63) -> pd.DataFrame:
    o, h, l, c = (daily[k] for k in ("Open", "High", "Low", "Close"))
    log_hl = np.log(h / l)
    log_co = np.log(c / o)
    if kind == "garman_klass_vol":
        var = 0.5 * log_hl ** 2 - (2 * math.log(2) - 1) * log_co ** 2
        vol = var.rolling(window_days, min_periods=window_days // 2).mean().clip(lower=0) ** 0.5
    else:  # Yang-Zhang (2000)
        log_oc = np.log(o / c.shift(1))
        log_ho, log_lo = np.log(h / o), np.log(l / o)
        rs = log_ho * (log_ho - log_co) + log_lo * (log_lo - log_co)
        n = window_days
        k = 0.34 / (1.34 + (n + 1) / (n - 1))
        vo = log_oc.rolling(n, min_periods=n // 2).var()
        vc = log_co.rolling(n, min_periods=n // 2).var()
        vrs = rs.rolling(n, min_periods=n // 2).mean()
        vol = (vo + k * vc + (1 - k) * vrs).clip(lower=0) ** 0.5
    return (vol * math.sqrt(252)).resample("ME").last()


# ---------------------------------------------------------------------------
# dependent variables


def compute_dependent(name: str, horizon: int, ctx: dict[str, Any]) -> pd.DataFrame:
    returns, factors, daily = ctx["returns"], ctx["factors"], ctx["daily"]
    growth = (1 + returns).rolling(horizon).apply(np.prod, raw=True) - 1
    forward = growth.shift(-horizon)
    if name == "forward_return":
        return forward
    if name in {"ff3_alpha", "ff5_alpha"}:
        cols = ["mkt_rf", "smb", "hml"] + (["rmw", "cma"] if name == "ff5_alpha" else [])
        if factors.empty or not set(cols).issubset(factors.columns):
            raise ValueError("Fama-French factors are unavailable for the alpha dependent variable.")
        f = factors[cols].reindex(returns.index)
        rf = factors["rf"].reindex(returns.index).fillna(0)
        ex = returns.sub(rf, axis=0)
        betas = {c: ex.rolling(36, min_periods=24).cov(f[c]).div(f[c].rolling(36, min_periods=24).var(), axis=0) for c in cols}
        # Characteristic-adjusted one-month abnormal return using betas known at t.
        abnormal = ex.copy()
        for c in cols:
            abnormal = abnormal - betas[c].shift(1).mul(f[c], axis=0)
        return ((1 + abnormal).rolling(horizon).apply(np.prod, raw=True) - 1).shift(-horizon)
    if name == "realized_vol":
        vol = daily["Close"].pct_change(fill_method=None).resample("ME").std() * math.sqrt(21)
        return vol.reindex(returns.index).rolling(horizon).mean().shift(-horizon)
    if name == "spread":  # Corwin-Schultz (2012) high-low spread estimator
        spread = _corwin_schultz(daily["High"], daily["Low"]).resample("ME").mean()
        return spread.reindex(returns.index).rolling(horizon).mean().shift(-horizon)
    if name == "dollar_volume":
        dv = np.log((daily["Close"] * daily["Volume"]).resample("ME").sum().replace(0, np.nan))
        return dv.reindex(returns.index).rolling(horizon).mean().shift(-horizon)
    raise ValueError(name)


def _corwin_schultz(high: pd.DataFrame, low: pd.DataFrame) -> pd.DataFrame:
    beta = np.log(high / low) ** 2 + np.log(high.shift(1) / low.shift(1)) ** 2
    gamma = np.log(np.maximum(high, high.shift(1)) / np.minimum(low, low.shift(1))) ** 2
    denom = 3 - 2 * math.sqrt(2)
    alpha = (np.sqrt(2 * beta) - np.sqrt(beta)) / denom - np.sqrt(gamma / denom)
    return (2 * (np.exp(alpha) - 1) / (1 + np.exp(alpha))).clip(lower=0)


# ---------------------------------------------------------------------------
# weights, universe filters, transforms


def _weights(scheme: str, signal: pd.DataFrame, market_cap: pd.DataFrame) -> pd.DataFrame:
    if scheme in {"equal", "ew"}:
        return pd.DataFrame(1.0, index=signal.index, columns=signal.columns)
    if scheme in {"value", "vw"}:
        return market_cap.reindex_like(signal)
    if scheme in {"rank", "rank_weight"}:
        return signal.rank(axis=1, pct=True)
    raise ValueError("weighting must be equal, value or rank")


def _universe_mask(filters: list[str], market_cap: pd.DataFrame, symbols: list[str]) -> pd.DataFrame:
    mask = pd.DataFrame(True, index=market_cap.index, columns=symbols)
    if not filters:
        return mask
    sectors = static_sectors().reindex(symbols)
    if "ex_financials" in filters:
        mask &= pd.DataFrame(np.broadcast_to((sectors != "Financial Services").to_numpy(), mask.shape), index=mask.index, columns=symbols)
    if "ex_utilities" in filters:
        mask &= pd.DataFrame(np.broadcast_to((sectors != "Utilities").to_numpy(), mask.shape), index=mask.index, columns=symbols)
    size_rank = market_cap.rank(axis=1, pct=True)
    if "ex_microcaps" in filters:
        mask &= size_rank > 0.2
    if "large_cap" in filters:
        mask &= size_rank > 2 / 3
    if "mid_cap" in filters:
        mask &= (size_rank > 1 / 3) & (size_rank <= 2 / 3)
    if "small_cap" in filters:
        mask &= size_rank <= 1 / 3
    return mask


def _transform_frame(sig: pd.DataFrame, kind: str) -> pd.DataFrame:
    """Cross-sectional signal transform on a formation-date x ticker frame (numpy for the hot paths)."""

    v = sig.to_numpy(dtype=np.float64)
    if kind == "winsorize":
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            lo, hi = np.nanquantile(v, [0.01, 0.99], axis=1)
        return pd.DataFrame(np.minimum(np.maximum(v, lo[:, None]), hi[:, None]), index=sig.index, columns=sig.columns)
    if kind == "rank":
        return sig.rank(axis=1, pct=True)
    if kind == "zscore":
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            mean = np.nanmean(v, axis=1)
            std = np.nanstd(v, axis=1, ddof=1)
        std[std == 0] = np.nan
        return pd.DataFrame((v - mean[:, None]) / std[:, None], index=sig.index, columns=sig.columns)
    if kind == "decile":
        return np.ceil(sig.rank(axis=1, pct=True) * 10)
    raise ValueError("signal_transform must be raw, winsorize, rank, zscore or decile")


def _apply_transform(panel: Panel, kind: str) -> Panel:
    if kind == "raw":
        return panel
    return panel.with_signal(_transform_frame(panel.signal, kind), signal_transform=kind)


def _monthly_factors(dates: pd.DatetimeIndex) -> pd.DataFrame:
    f = monthly_factor_returns()
    if f.empty:
        return pd.DataFrame(index=dates)
    daily = f.set_index("Date")
    return daily.reindex(dates)


def _monthly_macro(dates: pd.DatetimeIndex) -> pd.DataFrame:
    m = load_macro()
    if m.empty:
        return pd.DataFrame(index=dates)
    return m.set_index("Date").sort_index().resample("ME").last().reindex(dates)


def signal_for(panel: Panel, name: str, payload: dict[str, Any] | None = None) -> pd.DataFrame:
    """Compute another signal on the same panel (used by double sorts and robustness)."""

    return compute_signal(name, panel.context, payload).reindex(index=panel.dates, columns=panel.symbols)


def control_for(panel: Panel, name: str) -> pd.DataFrame:
    return compute_control(name, panel.context).reindex(index=panel.dates, columns=panel.symbols)
