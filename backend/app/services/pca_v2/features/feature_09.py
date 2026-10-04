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
    comparison = []
    portfolios = payload.get("portfolios") or []
    if not isinstance(portfolios, list) or len(portfolios)>4:
        raise ValueError("portfolios must be a list of at most four named weight objects")
    for index, portfolio in enumerate(portfolios):
        if not isinstance(portfolio, dict) or not isinstance(portfolio.get("weights"), dict):
            raise ValueError("Each comparison portfolio requires weights")
        result = stress_scenarios(model, {**payload, "weights": portfolio["weights"]})
        comparison += [{"portfolio":portfolio.get("name",f"Portfolio {index+1}"), **row} for row in result["scenario_rows"]]
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
            "pc_scenario_pnl_heatmap": comparison or stress["scenario_rows"],
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
            "stress_var_method": "10K Monte Carlo from full empirical factor covariance + 2K parametric",
            "joint_shocks_applied": bool(joint_result),
        }),
    )


from .inputs import inputs_for
INPUTS = inputs_for("09")
OUTPUTS = [{'key': 'pc_scenario_pnl_heatmap', 'source': 'charts', 'label': 'Pc Scenario Pnl Heatmap', 'render': 'heatmap', 'primary': True}, {'key': 'scenario_sensitivity_table_chart', 'source': 'charts', 'label': 'Scenario Sensitivity Table Chart', 'render': 'bar', 'primary': False}, {'key': 'maximum_loss_scenario_identifier', 'source': 'charts', 'label': 'Maximum Loss Scenario Identifier', 'render': 'bar', 'primary': False}, {'key': 'mahalanobis_historical_analog', 'source': 'charts', 'label': 'Mahalanobis Historical Analog', 'render': 'bar', 'primary': False}, {'key': 'historical_worst_day_scenarios_chart', 'source': 'charts', 'label': 'Historical Worst Day Scenarios Chart', 'render': 'bar', 'primary': False}, {'key': 'joint_scenario_pnl_chart', 'source': 'charts', 'label': 'Joint Scenario Pnl Chart', 'render': 'bar', 'primary': False}, {'key': 'scenario_sensitivity_table', 'source': 'tables', 'label': 'Scenario Sensitivity Table', 'render': 'table', 'primary': False}, {'key': 'position_level_pnl_waterfall', 'source': 'tables', 'label': 'Position Level Pnl Waterfall', 'render': 'table', 'primary': False}, {'key': 'historical_analog_table', 'source': 'tables', 'label': 'Historical Analog Table', 'render': 'table', 'primary': False}, {'key': 'stress_var_cvar', 'source': 'tables', 'label': 'Stress Var Cvar', 'render': 'table', 'primary': False}, {'key': 'historical_worst_day_table', 'source': 'tables', 'label': 'Historical Worst Day Table', 'render': 'table', 'primary': False}, {'key': 'joint_scenario_table', 'source': 'tables', 'label': 'Joint Scenario Table', 'render': 'table', 'primary': False}, {'key': 'pdf_export', 'source': 'tables', 'label': 'Pdf Export', 'render': 'table', 'primary': False}]
