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
