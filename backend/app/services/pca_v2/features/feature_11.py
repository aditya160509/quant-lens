"""Feature 11: PCA-enhanced liquidity risk module.

Illiquidity measures available via payload["illiquidity_measure"]:
  - "amihud"           : Amihud (2002) ILLIQ ratio (default)
  - "pastor_stambaugh" : Pastor-Stambaugh (2003) gamma (signed-reversal regression)
  - "kyle_lambda"      : Kyle's lambda from daily price impact regression

Standard errors on liquidity-beta regression use Newey-West HAC (3 lags) to account
for autocorrelation in the illiquidity factor.

Quant unwind threshold: payload["quant_unwind_threshold"] (default 0.15).
"""

from __future__ import annotations

from app.services.pca_v2.core.analytics import compact_records, matrix_records, metadata, response, rmt_model
from app.services.pca_v2.core.analytics import liquidity_outputs


def run(payload=None):
    payload = payload or {}
    model = rmt_model(payload)
    liq = liquidity_outputs(model, payload)

    illiq_measure = liq.get("illiquidity_measure", "amihud")
    quant_score = liq["quant_unwind_score"]
    quant_thresh = liq["quant_unwind_threshold"]

    return response(
        "11",
        [
            {"label": "Port Liq Beta", "value": liq["portfolio_liquidity_beta"], "unit": "beta"},
            {"label": "LaVaR", "value": liq["lavar"], "unit": "return"},
            {"label": "Quant Unwind Score", "value": quant_score, "unit": "score"},
            {"label": "Quant Unwind Risk", "value": "HIGH" if quant_score > quant_thresh else "LOW", "unit": "flag"},
            {"label": "Illiq Measure", "value": illiq_measure, "unit": "type"},
        ],
        charts={
            "illiquidity_surface_heatmap": matrix_records(liq["amihud_panel"], limit=200),
            "latent_liquidity_factor": compact_records(liq["latent_liquidity"].rename_axis("date").reset_index(), limit=400),
            "liquidity_beta_ranking": liq["liquidity_betas"],
            "position_sizing_liquidity_overlay": liq["liquidation"],
            "lavar_decomposition": [{"lavar": liq["lavar"], "quant_unwind_score": quant_score, "liquidity_variance_contribution": liq["liquidity_variance_contribution"]}],
            "illiquidity_driven_correlation_heatmap": matrix_records(liq["liquidity_driven_corr"], limit=200),
            "augmented_risk_decomposition": liq["augmented_risk_decomposition"],
        },
        tables={
            "liquidity_risk_scorecard": liq["liquidity_betas"],
            "liquidation_cost_table": liq["liquidation"],
            "quant_unwind_monitor": [{"quant_unwind_score": quant_score, "quant_unwind_threshold": quant_thresh, "liquidity_factor_percentile": liq["liquidity_factor_percentile"], "top20_liquidity_corr": liq["top20_liquidity_corr"], "signals": liq["unwind_signals"], "signal_count": liq["unwind_signal_count"], "flag": "HIGH" if liq["unwind_signal_count"] == 3 else "WATCH" if liq["unwind_signal_count"] else "LOW"}],
            "illiquidity_augmented_risk_table": liq["augmented_risk_decomposition"],
            "illiquidity_measure_metadata": [{"measure": illiq_measure, "note": "Amihud=ILLIQ ratio; PS=signed-reversal gamma; Kyle=price-impact lambda. Newey-West HAC (3 lags) SEs reported."}],
        },
        meta=metadata(model, {
            "implemented_outputs": 9,
            "illiquidity_measure": illiq_measure,
            "newey_west_lags": 3,
            "quant_unwind_threshold": quant_thresh,
        }),
    )
