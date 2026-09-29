"""Feature 09: PCA stress scenario generator and PC-shock P&L attribution.

Historical worst-day scenarios: finds the 5 worst historical realizations of each PC
and replays the exact portfolio P&L.

Joint multi-PC shock: payload["joint_shocks"] = {"PC1": 2.0, "PC3": -1.5} (sigma multiples)
Simultaneously applies user-specified shocks to multiple PCs in a single pass.

Stress VaR now uses 2K parametric + 10K Monte Carlo draws for reliable quantile estimation.
"""

from __future__ import annotations

from app.services.pca_v2.core.analytics import metadata, response, rmt_model, stress_pdf_report_base64, stress_scenarios


def run(payload=None):
    payload = payload or {}
    model = rmt_model(payload)
    stress = stress_scenarios(model, payload)
    pdf_base64 = stress_pdf_report_base64(model, stress)

    hist_worst = stress.get("historical_worst_day_scenarios", [])
    joint_result = stress.get("joint_scenario", None)

    return response(
        "09",
        [
            {"label": "Worst Scenario", "value": stress["worst_scenario"].get("scenario"), "unit": "name"},
            {"label": "Worst P&L", "value": stress["worst_scenario"].get("portfolio_pnl_pct"), "unit": "return"},
            {"label": "Stress VaR (MC+Param)", "value": stress["stress_var"], "unit": "return"},
            {"label": "Stress CVaR", "value": stress["stress_cvar"], "unit": "return"},
        ],
        charts={
            "pc_scenario_pnl_heatmap": stress["scenario_rows"],
            "scenario_sensitivity_table_chart": stress["scenario_rows"],
            "maximum_loss_scenario_identifier": [stress["worst_scenario"]],
            "mahalanobis_historical_analog": stress["analogs"],
            "historical_worst_day_scenarios_chart": hist_worst,
            "joint_scenario_pnl_chart": [joint_result] if joint_result else [],
        },
        tables={
            "scenario_sensitivity_table": stress["scenario_rows"],
            "position_level_pnl_waterfall": stress["waterfall"],
            "historical_analog_table": stress["analogs"],
            "stress_var_cvar": [{"stress_var": stress["stress_var"], "stress_cvar": stress["stress_cvar"], "method": "10K MC + parametric"}],
            "historical_worst_day_table": hist_worst,
            "joint_scenario_table": [joint_result] if joint_result else [],
            "pdf_export": [{"pdf_base64": pdf_base64, "available": bool(pdf_base64)}],
        },
        meta=metadata(model, {
            "implemented_outputs": 12,
            "pdf_export": "generated" if pdf_base64 else "reportlab_unavailable",
            "stress_var_method": "10K Monte Carlo + 2K parametric",
            "joint_shocks_applied": bool(joint_result),
        }),
    )
