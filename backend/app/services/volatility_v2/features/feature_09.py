"""Feature 09: causal volatility targeting, risk budgets and self-financing replay."""

from __future__ import annotations

import json
import numpy as np
import pandas as pd
from app.services.volatility_v2.core.analytics import (
    DEFAULT_ASSETS,
    load_assets,
    parse_weights,
    response,
    summary_card,
)
from app.services.volatility_v2.core.currency import portfolio_returns, quote_currencies
from app.services.volatility_v2.core.data_loader import resolve_symbols
from app.services.volatility_v2.core.covariance import portfolio_attribution
from app.services.volatility_v2.core.allocation import (
    risk_budget_weights,
    two_step_alignment,
)
from app.services.volatility_v2.core.budget_forecasts import (
    covariances,
    regime_targets,
    btz_returns,
    kelly_target,
)
from app.services.volatility_v2.core.liquidity import observed_adv
from app.services.volatility_v2.core.execution import simulate, performance, trade_cost


def run(payload=None):
    payload = payload or {}
    fixed = float(payload.get("vol_target", payload.get("target_vol", 0.1)))
    gross_cap = float(payload.get("gross_exposure_cap", 3))
    if not 0 < fixed <= 2 or gross_cap <= 0:
        raise ValueError(
            "Volatility target and gross cap must be positive; target must not exceed 200%"
        )
    mode = payload.get("target_mode", "fixed")
    cost_model = payload.get("cost_model", "flat")
    if mode not in ("fixed", "regime", "kelly") or cost_model not in (
        "flat",
        "almgren_chriss_temporary",
    ):
        raise ValueError("Unknown target mode or cost model")
    assets, ohlcv = load_assets(payload, default=DEFAULT_ASSETS[:8])
    returns, currency_meta = portfolio_returns(ohlcv, payload, log_returns=False)
    returns = returns.reindex(columns=assets)
    weights = parse_weights(payload, assets)
    vector = weights.to_numpy()
    annualization = int(payload.get("annualization", 252))
    cov_path, latest_cov, forecast_meta = covariances(returns, payload)
    warnings = []
    targets = {"fixed": pd.Series(fixed, index=returns.index)}
    current_targets = {"fixed": fixed}
    probabilities = None
    regime_meta = {"status": "unavailable"}
    if (
        mode == "regime"
        or payload.get("include_regime_comparison", True)
        or payload.get("regime_targets") is not None
    ):
        try:
            historical, current, probabilities, regime_meta = regime_targets(
                ohlcv, assets[0], returns, payload, fixed
            )
            targets["regime"], current_targets["regime"] = historical, current
        except ValueError as exc:
            if mode == "regime" or payload.get("regime_targets") is not None:
                raise
            warnings.append(f"Regime comparison unavailable: {exc}")
            regime_meta = {"status": "unavailable", "reason": str(exc)}
    cash_rate = float(payload.get("cash_rate_annual", 0))
    kelly = {
        "status": "unavailable",
        "reason": "Matching observed IV and matured BTZ labels required",
    }
    if mode == "kelly" or payload.get("include_kelly", True):
        try:
            currencies = quote_currencies(assets, payload)
            if any(currency != "USD" for currency in currencies.values()):
                raise ValueError(
                    "BTZ Kelly requires matching USD-underlying IV; native-currency IV cannot identify FX-adjusted portfolio VRP"
                )
            log_expected, details = btz_returns(returns, payload, probabilities)
            prior_expected = log_expected.reindex(returns.index).shift(1)
            kelly_history = pd.Series(np.nan, index=returns.index)
            for date, covariance in cov_path.items():
                if prior_expected.loc[date].isna().any():
                    continue
                kelly_history.loc[date] = kelly_target(
                    prior_expected.loc[date], covariance, vector, gross_cap, cash_rate
                )["kelly_optimal_vol_target"]
            current_kelly = kelly_target(
                log_expected.iloc[-1], latest_cov, vector, gross_cap, cash_rate
            )
            target = current_kelly["kelly_optimal_vol_target"]
            targets["kelly"], current_targets["kelly"] = kelly_history, target
            kelly = {
                "status": "ok",
                **current_kelly,
                "source": details,
                "policy": "Nonnegative leverage in the reference-portfolio direction, bounded by gross cap",
                "model": "Continuous-time Kelly mu/variance; BTZ log-return forecasts converted using the conditional diffusion variance correction",
            }
        except (ValueError, np.linalg.LinAlgError) as exc:
            if mode == "kelly":
                raise ValueError(f"Selected Kelly target unavailable: {exc}") from exc
            kelly = {"status": "unavailable", "reason": str(exc)}
    adv = None
    adv_meta = {}
    try:
        adv, adv_meta = observed_adv(ohlcv, payload, int(payload.get("adv_window", 63)))
        adv = adv.reindex(columns=assets)
    except ValueError as exc:
        if cost_model == "almgren_chriss_temporary":
            raise ValueError(f"Selected impact model unavailable: {exc}") from exc
        adv_meta = {"status": "unavailable", "reason": str(exc)}
    start = max(
        [
            cov_path.index[0],
            *(
                series.first_valid_index()
                for series in targets.values()
                if series.first_valid_index() is not None
            ),
        ]
    )
    dates = cov_path.index[cov_path.index >= start]
    if len(dates) < 30:
        raise ValueError(
            "At least 30 aligned held-out portfolio return dates are required"
        )
    for name, series in list(targets.items()):
        if series.reindex(dates).isna().any():
            if name == mode:
                raise ValueError(
                    f"Missing {name} targets inside the replay; no stale probabilities or targets are substituted"
                )
            warnings.append(
                f"{name} comparison unavailable: missing interior target dates"
            )
            targets.pop(name)
    replay_returns = returns.reindex(dates)
    historical_adv = (
        adv.reindex(returns.index).shift(1).reindex(dates) if adv is not None else None
    )
    impact_available = (
        historical_adv is not None
        and historical_adv.notna().all().all()
        and historical_adv.gt(0).all().all()
    )
    if not impact_available and cost_model == "almgren_chriss_temporary":
        raise ValueError(
            "Selected temporary impact replay lacks positive observed USD ADV on every formation date"
        )
    controls = {
        "schedule": payload.get(
            "rebalance_trigger", payload.get("rebalance_frequency", "daily")
        ),
        "signal_threshold": float(payload.get("rebalance_threshold", 0.2)),
        "gross_cap": gross_cap,
        "aum": float(payload.get("aum", 1e8)),
        "annualization": annualization,
        "cash_rate_annual": cash_rate,
    }
    explicit = float(payload.get("explicit_bps", 5))
    gamma = float(payload.get("market_impact_gamma", 0.1))
    legs = {}
    for name, series in targets.items():
        legs[name] = simulate(
            replay_returns,
            cov_path.reindex(dates),
            weights,
            target=series.reindex(dates),
            explicit_bps=explicit,
            impact_gamma=gamma if cost_model == "almgren_chriss_temporary" else None,
            adv=historical_adv if cost_model == "almgren_chriss_temporary" else None,
            **controls,
        )
    equal = pd.Series(1 / len(assets), index=assets)
    for name, reference in (("reference", weights), ("equal_weight", equal)):
        legs[name] = simulate(
            replay_returns,
            cov_path.reindex(dates),
            reference,
            explicit_bps=explicit,
            **controls,
        )
    flat = (
        simulate(
            replay_returns,
            cov_path.reindex(dates),
            weights,
            target=targets[mode].reindex(dates),
            explicit_bps=explicit,
            **controls,
        )
        if cost_model != "flat"
        else legs[mode]
    )
    impact = (
        simulate(
            replay_returns,
            cov_path.reindex(dates),
            weights,
            target=targets[mode].reindex(dates),
            explicit_bps=explicit,
            impact_gamma=gamma,
            adv=historical_adv,
            **controls,
        )
        if impact_available
        else None
    )
    if not impact_available:
        warnings.append(
            "Temporary impact comparison unavailable: verified positive USD ADV is missing; no liquidity proxy is used"
        )
    target = current_targets[mode]
    attribution = portfolio_attribution(latest_cov, weights)
    budgets_raw = payload.get("risk_budgets")
    if isinstance(budgets_raw, str):
        budgets_raw = json.loads(budgets_raw)
    if budgets_raw is None:
        budgets = pd.Series(1 / len(assets), index=assets)
    else:
        if not isinstance(budgets_raw, dict):
            raise ValueError("risk_budgets must be a JSON object")
        mapping = {
            resolve_symbols([asset])[0]: float(value)
            for asset, value in budgets_raw.items()
        }
        if set(mapping) != set(assets) or len(mapping) != len(budgets_raw):
            raise ValueError(
                "risk_budgets must contain each requested asset exactly once"
            )
        budgets = pd.Series(mapping).reindex(assets)
        if (
            not np.isfinite(budgets).all()
            or (budgets <= 0).any()
            or not np.isclose(budgets.sum(), 1)
        ):
            raise ValueError("Risk budgets must be finite, positive and sum to one")
    if target > 0:
        risk_weights, risk_meta = risk_budget_weights(
            latest_cov.to_numpy(), vector, budgets.to_numpy(), target, gross_cap
        )
        uniform, aligned, alignment_meta = two_step_alignment(
            latest_cov.to_numpy(), vector, budgets.to_numpy(), target, gross_cap
        )
    else:
        risk_weights = uniform = aligned = np.zeros(len(assets))
        risk_meta = alignment_meta = {"policy": "Nonpositive BTZ Kelly edge: all cash"}
    budget = []
    for row in attribution["assets"]:
        asset = row["asset"]
        budget.append(
            {
                **row,
                "assigned_budget": float(budgets[asset]),
                "budget_fraction_deviation": row["fraction_total_risk"]
                - float(budgets[asset]),
                "volatility_budget_deviation_bps": (
                    row["component_volatility"]
                    - float(budgets[asset]) * attribution["volatility"]
                )
                * 10000,
            }
        )
    recommendation = [
        {
            "asset": asset,
            "current_weight": float(vector[i]),
            "uniform_scaled_weight": float(uniform[i]),
            "risk_budget_weight": float(risk_weights[i]),
            "net_preserving_budget_aligned_weight": float(aligned[i]),
            "weight_change": float(aligned[i] - vector[i]),
        }
        for i, asset in enumerate(assets)
    ]
    current_costs = []
    for model_name, coefficient in (
        ("flat", None),
        ("almgren_chriss_temporary", gamma),
    ):
        if coefficient is not None and (
            adv is None or adv.reindex([returns.index[-1]]).isna().any().any()
        ):
            current_costs.append(
                {
                    "model": model_name,
                    "status": "unavailable",
                    "reason": adv_meta.get("reason", "No observed current USD ADV"),
                }
            )
            continue
        cost = trade_cost(
            vector,
            aligned,
            explicit,
            controls["aum"],
            coefficient,
            np.sqrt(np.diag(latest_cov) / annualization),
            adv.loc[returns.index[-1]].to_numpy() if coefficient is not None else None,
        )
        current_costs.append(
            {
                "model": model_name,
                "status": "ok",
                "cost_fraction": cost["cost_fraction"],
                "cost_usd": cost["cost_fraction"] * controls["aum"],
                "gross_traded_notional_fraction": cost[
                    "gross_traded_notional_fraction"
                ],
                "one_way_turnover_including_cash": cost[
                    "one_way_turnover_including_cash"
                ],
            }
        )
    selected = legs[mode]
    history = selected.reset_index().to_dict("records")
    backtest = pd.DataFrame(
        {f"{name}_net": frame.net_nav for name, frame in legs.items()}
    )
    backtest[f"{mode}_gross"] = selected.gross_nav
    performance_rows = []
    for name, frame in legs.items():
        performance_rows.append(
            {
                "portfolio": f"{name}_net",
                **performance(frame.net_return, annualization, cash_rate),
                "cost_usd": float(frame.cost_usd.sum()),
            }
        )
    performance_rows.append(
        {
            "portfolio": f"{mode}_gross",
            **performance(selected.gross_return, annualization, cash_rate),
        }
    )
    comparisons = [
        {
            "cost_model": "flat",
            **performance(flat.net_return, annualization, cash_rate),
            "total_cost_usd": float(flat.cost_usd.sum()),
        }
    ]
    if impact is not None:
        comparisons.append(
            {
                "cost_model": "almgren_chriss_temporary",
                **performance(impact.net_return, annualization, cash_rate),
                "total_cost_usd": float(impact.cost_usd.sum()),
            }
        )
    realized = float((returns @ weights).tail(21).std(ddof=1) * np.sqrt(annualization))
    breach = selected.loc[
        (selected.reference_forecast_volatility - selected.target_volatility).abs()
        > float(payload.get("breach_threshold", 0.15)) * selected.target_volatility
    ]
    result = response(
        "09",
        [
            summary_card("Reference Trailing 21d Vol", realized, "annual decimal"),
            summary_card(
                "Next Observation Forecast Vol",
                attribution["volatility"],
                "annual decimal",
            ),
            summary_card("Target Vol", target, "annual decimal"),
            summary_card(
                "Scaling Factor",
                float(np.abs(uniform).sum() / np.abs(vector).sum()),
                "x",
            ),
        ],
        charts={
            "portfolio_vol_dashboard": [
                {"metric": "reference_realized_21d", "value": realized},
                {
                    "metric": "forecast_next_observation",
                    "value": attribution["volatility"],
                },
                {"metric": "target", "value": target},
            ],
            "vol_to_target_gap_gauge": [
                {"label": "forecast_gap", "value": attribution["volatility"] - target}
            ],
            "vol_budget_attribution_waterfall": budget,
            "scaling_factor_history": history,
            "regime_conditional_target_evolution": [
                {
                    "date": date,
                    "fixed_target": fixed,
                    "regime_target": float(targets["regime"].loc[date])
                    if "regime" in targets
                    else None,
                }
                for date in dates
            ],
            "kelly_vs_fixed_target": [
                {
                    "date": date,
                    "fixed_target": fixed,
                    "kelly_target": float(targets["kelly"].loc[date])
                    if "kelly" in targets
                    else None,
                }
                for date in dates
            ],
            "historical_vol_targeting_backtest": backtest.rename_axis("date")
            .reset_index()
            .to_dict("records"),
        },
        tables={
            "portfolio_vol_budget_table": budget,
            "rebalancing_recommendation": recommendation,
            "two_step_rebalancing_detail": [
                {
                    "step": name,
                    "portfolio_volatility": float(
                        np.sqrt(proposal @ latest_cov.to_numpy() @ proposal)
                    ),
                    "gross_exposure": float(np.abs(proposal).sum()),
                    "net_exposure": float(proposal.sum()),
                }
                for name, proposal in (
                    ("uniform_scale", uniform),
                    ("constrained_budget_alignment", aligned),
                )
            ],
            "transaction_cost_comparison": current_costs,
            "kelly_vol_target": [kelly],
            "vol_budget_breach_log": breach.reset_index().to_dict("records"),
            "historical_backtest_performance": performance_rows,
            "backtest_cost_comparison": comparisons,
            "regime_probability_input": [
                {"regime": name, "probability": value}
                for name, value in regime_meta.get("current_probabilities", {}).items()
            ],
        },
        meta={
            "assets": assets,
            **currency_meta,
            **forecast_meta,
            "target_mode": mode,
            "cost_model": cost_model,
            "annualization": annualization,
            "risk_budget_solver": risk_meta,
            "two_step_solver": alignment_meta,
            "regime": regime_meta,
            "liquidity": adv_meta,
            "warnings": warnings,
            "execution_assumptions": {
                "explicit_bps_per_traded_notional": explicit,
                "temporary_impact_gamma_assumed": gamma,
                "cash_and_borrow_rate_annual_assumed": cash_rate,
                "aum_initial_usd": controls["aum"],
                "permanent_impact": "not modeled",
                "short_borrow_fees": "not modeled",
            },
            "backtest_policy": "Counterfactual fixed reference weights; forecasts/targets through prior close; drifted holdings; post-cost NAV trade sizes; equal evaluation dates; warmup excluded",
            "target_defaults": "Declared preferences: low 1.2x, transition 1.0x, high 0.8x, crisis 0.6x fixed target; user overrides are honored",
            "budget_sign_policy": "Nonzero reference-position signs preserved; zero positions enter the long cone",
            "known_limitations": "Close adjustment/total-return conventions are not guaranteed; impact coefficient is assumed, not calibrated execution data",
        },
    )
    if warnings:
        result["status"] = "warning"
    return result
