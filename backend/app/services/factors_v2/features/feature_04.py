"""Feature 4: Factor Timing and Probabilistic Regime Analysis."""

from typing import Any, Dict

import numpy as np
import pandas as pd
from hmmlearn.hmm import GaussianHMM
from sklearn.mixture import GaussianMixture

from app.services.factors_v2.core.analytics import factor_returns, matrix_records, response
from app.services.factors_v2.core.data_loader import load_category7_macro
from app.services.factors_v2.core.performance import batch_covariance_upper, compute_mode, runtime_meta, stable_cache_key


def run(payload: Dict[str, Any]) -> Dict[str, Any]:
    mode = compute_mode(payload)
    rets = factor_returns(payload).dropna().tail(int(payload.get("window_days", 1260)))
    macro = load_category7_macro().dropna(subset=["date"]).set_index("date").sort_index()
    if rets.empty:
        return response("feature_04", "warning", meta={"warning": "No factor returns available"})
    common_macro = macro.reindex(rets.index).ffill()
    stress_prob = (
        (common_macro.get("vix_close", pd.Series(index=rets.index)) > float(payload.get("vix_threshold", 25))).astype(float)
        + (common_macro.get("yc_slope_10y_2y", pd.Series(index=rets.index)) < 0).astype(float)
        + (common_macro.get("ust_10y", pd.Series(index=rets.index)).fillna(0) > 4.5).astype(float)
    ) / 3.0
    rules = pd.DataFrame({"expansion": 1 - stress_prob, "stress": stress_prob}, index=rets.index).fillna(0.5)
    obs = rets.rolling(21).mean().dropna()
    states = int(payload.get("states", 3))
    try:
        hmm = GaussianHMM(n_components=states, covariance_type="diag", n_iter=100, random_state=7).fit(obs.values)
        hmm_probs = pd.DataFrame(hmm.predict_proba(obs.values), index=obs.index, columns=[f"hmm_state_{i}" for i in range(states)])
        hmm_binary = _state_probs_to_binary(hmm_probs, obs)
        transition = hmm.transmat_
    except Exception as exc:
        hmm_probs = pd.DataFrame(index=obs.index)
        hmm_binary = pd.DataFrame(index=obs.index)
        transition = np.eye(states)
        hmm_error = str(exc)
    vectors, dates = [], []
    cols = list(rets.columns)
    include_gmm = bool(payload.get("include_gmm", False)) or mode == "research"
    if include_gmm:
        step = 5 if mode == "realtime" else 1
        obs_values = rets.reindex(obs.index).to_numpy(dtype=np.float32)
        if obs_values.shape[0] >= 63:
            all_vectors = batch_covariance_upper(obs_values, 63, step)
            dates = list(obs.index[62::step][: len(all_vectors)])
            vectors = [row for row in all_vectors]
        try:
            gmm = GaussianMixture(n_components=min(states, len(vectors)), random_state=7).fit(np.asarray(vectors))
            gmm_probs = pd.DataFrame(gmm.predict_proba(np.asarray(vectors)), index=dates, columns=[f"gmm_state_{i}" for i in range(gmm.n_components)])
            gmm_probs = _interpolate_probabilities(gmm_probs, obs.index)
            gmm_binary = _state_probs_to_binary(gmm_probs, rets)
        except Exception as exc:
            gmm_probs = pd.DataFrame(index=obs.index)
            gmm_binary = pd.DataFrame(index=obs.index)
            gmm_error = str(exc)
    else:
        gmm_probs = pd.DataFrame(index=obs.index)
        gmm_binary = pd.DataFrame(index=obs.index)
    composite, method_weights = _combine_regime_probabilities(rules, hmm_binary, gmm_binary, rets)
    confidence = float(composite.iloc[-1].max()) if not composite.empty else None
    current_regime = str(composite.iloc[-1].idxmax()) if not composite.empty else "unknown"
    transition_alert = []
    if len(composite) > 1:
        old = str(composite.iloc[-2].idxmax())
        new = current_regime
        shift = float(abs(composite.iloc[-1].max() - composite.iloc[-2].max()))
        if old != new or shift > 0.25:
            transition_alert.append({"level": "medium", "message": "Regime transition sensitivity alert", "old_state": old, "new_state": new, "probability_shift": shift})
    dominant = pd.cut(rules["stress"], bins=[-0.01, 0.34, 0.67, 1.01], labels=["expansion", "transition", "stress"])
    cond = rets.groupby(dominant, observed=False).agg(["mean", "std", "count"])
    heatmap = [{"factor": f, "regime": str(reg), "avg_daily_return": float(cond.loc[reg, (f, "mean")]), "sample": int(cond.loc[reg, (f, "count")])} for reg in cond.index for f in rets.columns]
    sharpe_rows = [
        {
            "factor": f,
            "regime": str(reg),
            "sharpe": float(cond.loc[reg, (f, "mean")] / cond.loc[reg, (f, "std")] * np.sqrt(252)) if cond.loc[reg, (f, "std")] else None,
            "sample": int(cond.loc[reg, (f, "count")]),
        }
        for reg in cond.index
        for f in rets.columns
    ]
    current_vector = [{"regime": str(key), "probability": float(value)} for key, value in (composite.iloc[-1] if not composite.empty else rules.iloc[-1]).items()]
    current_trend = _current_regime_trend(composite if not composite.empty else rules)
    timing = _factor_timing_regression(rets, rules, int(payload.get("timing_horizon_days", 21)))
    momentum = _factor_momentum_backtest(rets, int(payload.get("momentum_lookback_days", 63)))
    seasonality = _factor_seasonality(rets)
    sensitivity = _regime_sensitivity_table(heatmap, payload)
    return response(
        "feature_04",
        "ok",
        summary_cards=[
            {"label": "Composite Regime", "value": current_regime},
            {"label": "Composite Confidence", "value": confidence},
            {"label": "Current Stress Probability", "value": float(composite["stress"].iloc[-1]) if "stress" in composite else float(rules["stress"].iloc[-1])},
        ],
        charts={
            "rules_probability": rules.tail(260).reset_index().to_dict("records"),
            "hmm_probability": hmm_probs.tail(260).reset_index().to_dict("records"),
            "gmm_probability": gmm_probs.tail(260).reset_index().to_dict("records"),
            "composite_probability": composite.tail(260).reset_index().to_dict("records"),
            "current_regime": current_vector,
            "current_regime_trend": current_trend,
            "factor_sharpe_by_regime": sharpe_rows,
            "factor_momentum_backtest": momentum,
            "regime_sensitivity": sensitivity,
        },
        tables={"conditional_returns": heatmap, "transition_matrix": matrix_records(pd.DataFrame(transition)), "method_weights": method_weights, "factor_timing_regression": timing, "factor_seasonality": seasonality, "regime_sensitivity": sensitivity},
        alerts=([{"level": "high", "message": "Stress regime probability is elevated"}] if rules["stress"].iloc[-1] > 0.66 else []) + transition_alert + ([{"level": "medium", "message": "Regime uncertain", "confidence": confidence}] if confidence is not None and confidence < 0.5 else []),
        meta={
            **runtime_meta("feature_04", payload, ["HMM primary and macro/rules secondary; GMM is toggle/cached weekly in realtime"]),
            "macro_rows": int(len(macro)),
            "probability_combination": "log-space natural-parameter averaging with rolling volatility IC weights",
            "hmm_error": locals().get("hmm_error"),
            "gmm_error": locals().get("gmm_error"),
            "gmm_policy": "computed weekly/toggle in realtime or fully in Research Mode" if include_gmm else "skipped in realtime default; use include_gmm=true or compute_mode=research",
            "weekly_gmm_cache_key": stable_cache_key("feature_04", payload, "weekly_gmm_covariance"),
            "gmm_sampling": _gmm_metadata_block(mode, locals().get("step", None), len(obs), len(vectors) if include_gmm else 0, states) if include_gmm else None,
            "audit_closures": ["factor timing regression", "factor momentum backtest", "calendar-month seasonality"],
        },
    )


def _state_probs_to_binary(probs: pd.DataFrame, rets: pd.DataFrame) -> pd.DataFrame:
    if probs.empty:
        return probs
    vol = rets.reindex(probs.index).rolling(21, min_periods=5).std().mean(axis=1).bfill().fillna(0)
    scores = {}
    for col in probs:
        w = probs[col]
        scores[col] = float((w * vol).sum() / max(w.sum(), 1e-12))
    stress_state = max(scores, key=scores.get)
    stress = probs[stress_state].clip(1e-4, 1 - 1e-4)
    return pd.DataFrame({"expansion": 1 - stress, "stress": stress}, index=probs.index)


def _combine_regime_probabilities(rules: pd.DataFrame, hmm: pd.DataFrame, gmm: pd.DataFrame, rets: pd.DataFrame):
    parts = {"rules": rules[["expansion", "stress"]].dropna()}
    if not hmm.empty:
        parts["hmm"] = hmm[["expansion", "stress"]].dropna()
    if not gmm.empty:
        parts["gmm"] = gmm[["expansion", "stress"]].dropna()
    idx = sorted(set().union(*[set(p.index) for p in parts.values()]))
    realized_vol = rets.rolling(21).std().mean(axis=1).shift(-21).reindex(idx)
    weights = {}
    for name, p in parts.items():
        stress = _align_probabilities(p, idx)["stress"]
        ic = stress.corr(realized_vol, method="spearman")
        weights[name] = max(float(ic) if np.isfinite(ic) else 0.0, 0.0)
    if sum(weights.values()) == 0:
        weights = {k: 1.0 for k in parts}
    total = sum(weights.values())
    weights = {k: v / total for k, v in weights.items()}
    logits = []
    for name, p in parts.items():
        aligned = _align_probabilities(p, idx).fillna(0.5).clip(1e-4, 1 - 1e-4)
        logits.append(np.log(aligned) * weights[name])
    log_avg = sum(logits)
    exp = np.exp(log_avg.sub(log_avg.max(axis=1), axis=0))
    comp = exp.div(exp.sum(axis=1), axis=0)
    return comp, [{"method": k, "weight": v} for k, v in weights.items()]


def _align_probabilities(probs: pd.DataFrame, idx) -> pd.DataFrame:
    aligned = probs.reindex(pd.Index(idx).union(probs.index)).sort_index()
    if isinstance(aligned.index, pd.DatetimeIndex):
        aligned = aligned.interpolate(method="time", limit_direction="both")
    else:
        aligned = aligned.interpolate(limit_direction="both")
    return aligned.reindex(idx).fillna(0.5)


def _interpolate_probabilities(probs: pd.DataFrame, full_index: pd.Index) -> pd.DataFrame:
    if probs.empty:
        return probs
    expanded = probs.reindex(full_index.union(probs.index)).sort_index()
    if isinstance(expanded.index, pd.DatetimeIndex):
        interpolated = expanded.interpolate(method="time", limit_direction="both")
    else:
        interpolated = expanded.interpolate(limit_direction="both")
    row_sums = interpolated.sum(axis=1).clip(lower=1e-8)
    return interpolated.div(row_sums, axis=0).reindex(full_index)


def _gmm_metadata_block(mode: str, step, n_obs: int, n_vectors: int, states: int):
    if step is None:
        return None
    return {
        "gmm_realtime_step": int(step),
        "gmm_sampling_policy": (
            f"GMM covariance vectors computed every {int(step)} trading days in realtime mode "
            f"({n_vectors} vectors from {n_obs} observations). Probabilities are linearly interpolated between sampled dates."
        ) if mode == "realtime" else "GMM computed at every eligible date in Research Mode.",
        "gmm_gap_filling": "linear interpolation between sampled dates" if mode == "realtime" else "none/full density",
        "regime_persistence_note": "Realtime GMM probability bands reflect the sampling cadence; do not interpret within-step flatness as high-confidence persistence.",
        "states_requested": int(states),
    }


def _factor_timing_regression(rets: pd.DataFrame, rules: pd.DataFrame, horizon: int) -> list[dict[str, Any]]:
    rows = []
    signals = pd.DataFrame(index=rets.index)
    signals["stress_probability"] = rules["stress"].reindex(rets.index).ffill()
    signals["factor_momentum_cross_section"] = rets.rolling(63, min_periods=21).sum().mean(axis=1)
    signals["volatility_state"] = rets.rolling(21, min_periods=10).std().mean(axis=1)
    for factor in rets.columns:
        fwd = rets[factor].rolling(horizon, min_periods=max(3, horizon // 4)).sum().shift(-horizon)
        for signal in signals.columns:
            df = pd.concat([signals[signal].rename("x"), fwd.rename("y")], axis=1).dropna()
            if len(df) < 40 or df["x"].std() == 0:
                continue
            X = np.column_stack([np.ones(len(df)), df["x"].values])
            y = df["y"].values
            coef, *_ = np.linalg.lstsq(X, y, rcond=None)
            yhat = X @ coef
            resid = y - yhat
            dof = max(len(df) - 2, 1)
            sigma2 = float((resid @ resid) / dof)
            try:
                cov = sigma2 * np.linalg.inv(X.T @ X)
            except np.linalg.LinAlgError:
                cov = sigma2 * np.linalg.pinv(X.T @ X)
            se = float(np.sqrt(max(cov[1, 1], 0.0)))
            beta = float(coef[1])
            r2 = float(1 - np.sum(resid ** 2) / max(np.sum((y - y.mean()) ** 2), 1e-12))
            current = float(signals[signal].dropna().iloc[-1])
            rows.append({"factor": factor, "signal": signal, "horizon_days": horizon, "coefficient": beta, "t_stat": beta / se if se else None, "r_squared": r2, "current_signal": current, "current_timing_score": float(coef[0] + beta * current), "observations": int(len(df))})
    return rows


def _current_regime_trend(probs: pd.DataFrame) -> list[dict[str, Any]]:
    if probs.empty:
        return []
    latest = probs.iloc[-1]
    prev30 = probs.iloc[max(0, len(probs) - 31)]
    prev90 = probs.iloc[max(0, len(probs) - 91)]
    rows = []
    for col in probs.columns:
        now = float(latest.get(col, 0.0))
        rows.append(
            {
                "state": str(col),
                "prob_now": now,
                "probability": now,
                "prob_30d_ago": float(prev30.get(col, now)),
                "prob_90d_ago": float(prev90.get(col, now)),
                "change_30d": float(now - prev30.get(col, now)),
                "change_90d": float(now - prev90.get(col, now)),
            }
        )
    return rows


def _factor_momentum_backtest(rets: pd.DataFrame, lookback: int) -> list[dict[str, Any]]:
    if rets.shape[1] < 2 or len(rets) < lookback + 30:
        return []
    mom = rets.rolling(lookback, min_periods=max(20, lookback // 3)).sum()
    strat = []
    for idx in range(lookback, len(rets)):
        ranks = mom.iloc[idx - 1].dropna().sort_values()
        if len(ranks) < 2:
            strat.append(np.nan)
            continue
        half = max(1, len(ranks) // 2)
        long = ranks.index[-half:]
        short = ranks.index[:half]
        strat.append(float(rets.iloc[idx][long].mean() - rets.iloc[idx][short].mean()))
    s = pd.Series(strat, index=rets.index[lookback:]).dropna()
    eq = (1 + s).cumprod()
    if len(eq) > 260:
        eq = eq.iloc[np.linspace(0, len(eq) - 1, 260).astype(int)]
    return [{"date": str(idx.date()), "factor_momentum_equity": float(val)} for idx, val in eq.items()]


def _factor_seasonality(rets: pd.DataFrame) -> list[dict[str, Any]]:
    if not isinstance(rets.index, pd.DatetimeIndex):
        return []
    rows = []
    grouped = rets.groupby(rets.index.month)
    for month, frame in grouped:
        for factor in rets.columns:
            s = frame[factor].dropna()
            if len(s):
                rows.append({"month": int(month), "factor": factor, "avg_daily_return": float(s.mean()), "annualized_return_proxy": float(s.mean() * 252), "sample": int(len(s))})
    return rows


def _regime_sensitivity_table(conditional_rows: list[dict[str, Any]], payload: Dict[str, Any]) -> list[dict[str, Any]]:
    if not conditional_rows:
        return []
    weights = payload.get("factor_exposures") or payload.get("portfolio_weights") or {}
    factors = sorted({row.get("factor") for row in conditional_rows if row.get("factor")})
    if not weights:
        weights = {factor: 1.0 / max(len(factors), 1) for factor in factors}
    rows = []
    by_regime = sorted({row.get("regime") for row in conditional_rows if row.get("regime")})
    for regime in by_regime:
        subset = [row for row in conditional_rows if row.get("regime") == regime]
        weighted = 0.0
        gross = 0.0
        contributors = []
        for row in subset:
            factor = row.get("factor")
            w = float(weights.get(factor, 0.0))
            ret = float(row.get("avg_daily_return") or 0.0)
            contribution = w * ret * 252
            weighted += contribution
            gross += abs(contribution)
            contributors.append((factor, contribution))
        top = max(contributors, key=lambda item: abs(item[1])) if contributors else (None, 0.0)
        rows.append(
            {
                "regime": regime,
                "portfolio_return_sensitivity": float(weighted),
                "gross_factor_sensitivity": float(gross),
                "dominant_factor": top[0],
                "dominant_contribution": float(top[1]),
                "method": "conditional_return_times_supplied_or_equal_factor_exposure",
            }
        )
    return rows
