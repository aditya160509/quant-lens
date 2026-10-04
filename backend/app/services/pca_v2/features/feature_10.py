"""Feature 10: Cross-asset RMT covariance with hedged block decomposition."""

from __future__ import annotations

from app.services.pca_v2.core.analytics import clean_json, metadata, response
from app.services.pca_v2.core.cross_asset import cross_asset_feature_outputs


def run(payload=None):
    payload = payload or {}
    out = cross_asset_feature_outputs(payload)
    if out.get("status") != "ok":
        return response(
            "10",
            [{"label": "Coverage", "value": 0, "unit": "assets"}],
            charts={},
            tables=out.get("tables", {}),
            alerts=[{"severity": "error", "message": out.get("meta", {}).get("error", "No cross-asset data available")}],
            meta=out.get("meta", {}),
            status="error",
        )

    coverage = out["tables"].get("coverage", [])
    missing_blocks = [row for row in coverage if row.get("loaded", 0) == 0]
    alerts = []
    if missing_blocks:
        alerts.append({"severity": "warning", "message": f"{len(missing_blocks)} cross-asset blocks have no loaded symbols."})
    if out["tables"].get("crypto_volume_filter"):
        flagged = [r for r in out["tables"]["crypto_volume_filter"] if r.get("wash_trading_proxy_flag")]
        if flagged:
            alerts.append({"severity": "warning", "message": f"{len(flagged)} crypto symbols failed the local positive-volume quality screen."})

    return response(
        "10",
        out["summary"],
        charts=out["charts"],
        tables=out["tables"],
        alerts=alerts,
        meta=clean_json(
            {
                **out["meta"],
                "implemented_outputs": [
                    "asset_class_specific_covariance_estimators",
                    "dcc_cross_block_conditional_correlation",
                    "calendar_alignment_audit",
                    "crypto_volume_filter",
                    "crypto_cornish_fisher_mp_threshold",
                    "fx_minimum_variance_hedge_ratios",
                    "rolling_block_correlation_monitor",
                    "casci_index",
                    "stress_date_block_correlation_overlay",
                    "hourly_parquet_inventory",
                ],
            }
        ),
        status="ok",
    )


from .inputs import inputs_for
INPUTS = inputs_for("10")
OUTPUTS = [{'key': 'unified_cross_asset_covariance_heatmap', 'source': 'charts', 'label': 'Unified Cross Asset Covariance Heatmap', 'render': 'heatmap', 'primary': True}, {'key': 'unified_cross_asset_correlation_heatmap', 'source': 'charts', 'label': 'Unified Cross Asset Correlation Heatmap', 'render': 'heatmap', 'primary': False}, {'key': 'block_correlation_monitor', 'source': 'charts', 'label': 'Block Correlation Monitor', 'render': 'bar', 'primary': False}, {'key': 'casci_index', 'source': 'charts', 'label': 'Casci Index', 'render': 'bar', 'primary': False}, {'key': 'asset_class_pc_loading_share', 'source': 'charts', 'label': 'Asset Class Pc Loading Share', 'render': 'bar', 'primary': False}, {'key': 'unified_spectrum_mp', 'source': 'charts', 'label': 'Unified Spectrum Mp', 'render': 'bar', 'primary': False}, {'key': 'block_mp_bounds', 'source': 'charts', 'label': 'Block Mp Bounds', 'render': 'bar', 'primary': False}, {'key': 'cross_asset_loading_heatmap', 'source': 'charts', 'label': 'Cross Asset Loading Heatmap', 'render': 'heatmap', 'primary': False}, {'key': 'cross_asset_factor_returns', 'source': 'charts', 'label': 'Cross Asset Factor Returns', 'render': 'bar', 'primary': False}, {'key': 'dcc_latest_correlation', 'source': 'charts', 'label': 'Dcc Latest Correlation', 'render': 'heatmap', 'primary': False}, {'key': 'dcc_average_correlation', 'source': 'charts', 'label': 'Dcc Average Correlation', 'render': 'bar', 'primary': False}, {'key': 'stress_date_block_correlation_overlay', 'source': 'charts', 'label': 'Stress Date Block Correlation Overlay', 'render': 'bar', 'primary': False}, {'key': 'coverage', 'source': 'tables', 'label': 'Coverage', 'render': 'table', 'primary': False}, {'key': 'block_decomposition', 'source': 'tables', 'label': 'Block Decomposition', 'render': 'table', 'primary': False}, {'key': 'block_estimator_audit', 'source': 'tables', 'label': 'Block Estimator Audit', 'render': 'table', 'primary': False}, {'key': 'fx_hedge_ratio_table', 'source': 'tables', 'label': 'Fx Hedge Ratio Table', 'render': 'table', 'primary': False}, {'key': 'crypto_volume_filter', 'source': 'tables', 'label': 'Crypto Volume Filter', 'render': 'table', 'primary': False}, {'key': 'crypto_cornish_fisher_mp', 'source': 'tables', 'label': 'Crypto Cornish Fisher Mp', 'render': 'table', 'primary': False}, {'key': 'calendar_alignment_audit', 'source': 'tables', 'label': 'Calendar Alignment Audit', 'render': 'table', 'primary': False}, {'key': 'cross_asset_eigenvalues', 'source': 'tables', 'label': 'Cross Asset Eigenvalues', 'render': 'table', 'primary': False}, {'key': 'asset_class_mp_bounds', 'source': 'tables', 'label': 'Asset Class Mp Bounds', 'render': 'table', 'primary': False}, {'key': 'dcc_parameters', 'source': 'tables', 'label': 'Dcc Parameters', 'render': 'table', 'primary': False}, {'key': 'hourly_data_inventory', 'source': 'tables', 'label': 'Hourly Data Inventory', 'render': 'table', 'primary': False}, {'key': 'coverage', 'source': 'tables', 'label': 'Coverage', 'render': 'table', 'primary': False}]
