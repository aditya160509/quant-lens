"""Stable imports for PCA feature callers; implementations live in focused modules."""
from .data_loader import annualization_factor, dollar_volume_matrix, latest_market_caps, load_category7_macro, ohlcv_for_symbols, parse_symbols, returns_matrix, sector_map

def optimize_portfolio(model, payload=None):
    from .optimization import optimize
    return optimize(model, payload or {})


def liquidity_outputs(model, payload=None):
    from .liquidity import outputs
    return outputs(model, payload or {})


def optimize_portfolio_with_duals(model, payload=None):
    from .optimization import optimize
    return optimize(model, payload or {}, duals=True)

# Stable compatibility exports for existing feature modules.
from .pca_math import covariance_estimator, eig_sorted, mp_threshold, scree_elbow, choose_k, fit_mp_sigma2, preprocess_returns, blend_covariance
from .factors import factor_returns, loading_records, explained_variance_records, varimax, promax, hoyer_sparsity, asset_r2, hierarchical_pca
from .risk import active_risk_attribution, rolling_risk_decomposition, portfolio_weights, risk_decomposition
from .ou import volume_time_residuals, residual_matrix, ou_signal_table, signal_decay_analysis, residual_ou_backtest, _average_signal_holding_period, ou_mle
from .regimes import rolling_pca_metrics, cusum_table, bai_perron_breakpoints, tensor_hosvd, rolling_loading_evolution, pc1_percentile_rank
from .bootstrap import bai_ng_criteria, block_bootstrap_sample, subsampling_stability, subspace_principal_angles, bootstrap_validation
from .contagion import rolling_group_residual_corr, residual_contagion, residual_tensor_hosvd
from .scenarios import historical_worst_day_scenarios, joint_scenario_pnl, stress_scenarios, stress_pdf_report_base64

from .common import clean_json, number_like, response, compact_records, matrix_records, metadata, model_annualization, parse_compute_mode
from .model import load_context, rmt_model, _cached_rmt_key
from .stats import pastor_stambaugh_gamma, newey_west_se
from .allocation import k_sensitivity_sweep, black_litterman_posterior, robust_frontier_ellipsoidal
