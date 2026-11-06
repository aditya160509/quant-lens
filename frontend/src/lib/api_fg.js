/**
 * API client for Cluster F+G features (FG1-FG9)
 */

const API_BASE_URL = "http://127.0.0.1:8000/api";

async function handleResponse(res, context) {
    if (!res.ok) {
        const text = await res.text();
        throw new Error(`${context}: ${res.status} - ${text}`);
    }
    return res.json();
}

// =============================================================================
// FG1: FLOW HEATMAP
// =============================================================================

export async function fetchFlowHeatmap(params = {}) {
    const body = {
        groups: params.groups || ["EQUITIES", "BONDS", "COMMODITIES", "FX", "CRYPTO"],
        tickers_by_group: params.tickers_by_group || {
            "EQUITIES": ["SPY", "QQQ", "IWM"],
            "BONDS": ["TLT", "HYG"],
            "COMMODITIES": ["GLD", "USO"],
            "FX": ["UUP"],
            "CRYPTO": ["BTC-USD"]
        },
        lookback_days: params.lookback_days || 60,
        volume_window: params.volume_window || 20,
        vol_window: params.vol_window || 21
    };

    const res = await fetch(`${API_BASE_URL}/research/fg/flow_heatmap`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(body)
    });
    return handleResponse(res, "fetchFlowHeatmap");
}

// =============================================================================
// FG2: LIQUIDITY RADAR
// =============================================================================

export async function fetchLiquidityRadar(params = {}) {
    const body = {
        tickers: params.tickers || ["SPY", "QQQ", "IWM", "HYG", "GLD", "TLT"],
        lookback_days: params.lookback_days || 120,
        volume_window: params.volume_window || 20,
        vol_window: params.vol_window || 21,
        corr_window: params.corr_window || 21
    };

    const res = await fetch(`${API_BASE_URL}/research/fg/liquidity_radar`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(body)
    });
    return handleResponse(res, "fetchLiquidityRadar");
}

// =============================================================================
// FG3: RECESSION PROBABILITY
// =============================================================================

export async function fetchRecessionProb(params = {}) {
    const body = {
        as_of: params.as_of || null,
        lookback_years: params.lookback_years || 20,
        weights: params.weights || { yield_curve: 0.4, credit: 0.2, macro: 0.25, equity_vol: 0.15 },
        regions: params.regions || ["US"]
    };

    const res = await fetch(`${API_BASE_URL}/research/fg/recession_prob`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(body)
    });
    return handleResponse(res, "fetchRecessionProb");
}

// =============================================================================
// FG4: DRAWDOWN ANATOMY
// =============================================================================

export async function fetchDrawdownAnatomy(ticker, params = {}) {
    const queryParams = new URLSearchParams({
        lookback_years: params.lookback_years || 5,
        min_drawdown: params.min_drawdown || 0.1,
        max_events: params.max_events || 10
    });

    const res = await fetch(`${API_BASE_URL}/security/${ticker}/drawdown_anatomy?${queryParams}`);
    return handleResponse(res, "fetchDrawdownAnatomy");
}

// =============================================================================
// FG5: ETF LOOK THROUGH
// =============================================================================

export async function fetchEtfLookthrough(ticker, params = {}) {
    const queryParams = new URLSearchParams({
        top_n: params.top_n || 10,
        include_factors: params.include_factors !== false
    });

    const res = await fetch(`${API_BASE_URL}/etf/${ticker}/lookthrough?${queryParams}`);
    return handleResponse(res, "fetchEtfLookthrough");
}

// =============================================================================
// FG6: VOLATILITY SURFACE
// =============================================================================

export async function fetchVolSurface(ticker, params = {}) {
    const queryParams = new URLSearchParams({
        min_maturity_days: params.min_maturity_days || 7,
        max_maturity_days: params.max_maturity_days || 365
    });

    if (params.as_of) {
        queryParams.append("as_of", params.as_of);
    }

    const res = await fetch(`${API_BASE_URL}/options/${ticker}/vol_surface?${queryParams}`);
    return handleResponse(res, "fetchVolSurface");
}

// =============================================================================
// FG7: ETF FACTOR DNA
// =============================================================================

export async function fetchEtfFactorDna(params = {}) {
    const body = {
        etf: params.etf || "QQQ",
        peer_etfs: params.peer_etfs || ["SPY", "VUG", "VTV"],
        factors: params.factors || ["value", "momentum", "quality", "size", "volatility"],
        lookback_days: params.lookback_days || 252
    };

    const res = await fetch(`${API_BASE_URL}/research/fg/etf_factor_dna`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(body)
    });
    return handleResponse(res, "fetchEtfFactorDna");
}

// =============================================================================
// FG8: HEDGE SIMULATOR
// =============================================================================

export async function fetchHedgeSim(params = {}) {
    const body = {
        portfolio: params.portfolio || { positions: [] },
        hedges: params.hedges || [],
        benchmark: params.benchmark || "SPY",
        lookback_days: params.lookback_days || 252,
        risk_metrics: params.risk_metrics || ["vol", "beta", "var", "cvar", "max_drawdown"],
        scenarios: params.scenarios || ["rate_hike", "inflation_spike", "equity_crash"]
    };

    const res = await fetch(`${API_BASE_URL}/portfolio/hedge_sim`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(body)
    });
    return handleResponse(res, "fetchHedgeSim");
}

// =============================================================================
// FG9: HEDGE RATIO CALCULATOR
// =============================================================================

export async function fetchHedgeRatio(params = {}) {
    const body = {
        portfolio: params.portfolio || { positions: [] },
        hedge_ticker: params.hedge_ticker || "SPY",
        lookback_days: params.lookback_days || 252,
        mode: params.mode || "beta_neutral"
    };

    const res = await fetch(`${API_BASE_URL}/portfolio/hedge_ratio`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(body)
    });
    return handleResponse(res, "fetchHedgeRatio");
}
