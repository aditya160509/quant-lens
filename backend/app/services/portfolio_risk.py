"""
Portfolio Risk Service - Features 5-10
Category 2: Risk Wiring & Structural Safety

Now uses robust_data_fetcher for multi-source data with caching and rate limiting.
"""
import numpy as np
import pandas as pd
from datetime import datetime
from typing import List, Dict, Optional, Tuple
import logging
import networkx as nx

# Use robust data fetcher - handles rate limiting, caching, multi-source fallback
from app.services.robust_data_fetcher import (
    get_price_data as rdf_get_price,
    get_batch_data as rdf_get_batch
)

from app.models.portfolio_models import (
    Position, PortfolioSnapshot, Quality, Provenance,
    CentralityMetrics, Cluster, CrossImpactOutput,
    LiquidityPosition, LiquidityMap,
    ConcentrationMetrics, DrawdownAttribution,
    Guardrail, GuardrailsOutput, GuardrailStatus,
    Alert, AlertsOutput, Severity
)
from app.services.portfolio_core import (
    log_returns, ledoit_wolf_shrinkage, sample_correlation,
    herfindahl_hirschman_index, effective_n, entropy,
    diversification_ratio, correlation_adjusted_hhi,
    exit_days, market_impact_sqrt, liquidity_score,
    portfolio_volatility, percentage_risk_contribution
)

logger = logging.getLogger(__name__)


# =============================================================================
# GUARDRAIL DEFINITIONS
# =============================================================================

_guardrail_rules = [
    {"id": "gr_position_max", "name": "Max Position Size", "type": "position", "limit": 0.20},
    {"id": "gr_sector_max", "name": "Max Sector Exposure", "type": "sector", "limit": 0.35},
    {"id": "gr_cash_min", "name": "Minimum Cash", "type": "cash", "limit": 0.03},
    {"id": "gr_vol_max", "name": "Max Volatility", "type": "risk", "limit": 0.30},
    {"id": "gr_dd_max", "name": "Max Drawdown", "type": "risk", "limit": -0.20},
    {"id": "gr_concentration", "name": "Concentration Limit", "type": "concentration", "limit": 0.25},
    {"id": "gr_liquidity_min", "name": "Min Liquidity Score", "type": "liquidity", "limit": 40},
]

_alert_rules = [
    {"id": "alert_vol_spike", "condition": "vol_ann > 0.25", "severity": Severity.HIGH, "category": "Risk"},
    {"id": "alert_dd_warn", "condition": "current_dd < -0.10", "severity": Severity.MEDIUM, "category": "Performance"},
    {"id": "alert_dd_crit", "condition": "current_dd < -0.15", "severity": Severity.HIGH, "category": "Performance"},
    {"id": "alert_conc_warn", "condition": "hhi > 0.15", "severity": Severity.MEDIUM, "category": "Concentration"},
    {"id": "alert_liquidity", "condition": "liquidity_score < 50", "severity": Severity.MEDIUM, "category": "Liquidity"},
]

_active_alerts: List[Alert] = []


# =============================================================================
# HELPER FUNCTIONS - Using robust_data_fetcher
# =============================================================================

def _get_returns_matrix(tickers: List[str], period: str = "1y") -> pd.DataFrame:
    """Get aligned returns matrix for multiple tickers using robust_data_fetcher."""
    all_returns = {}
    
    try:
        # Use batch fetcher with rate limiting
        batch_data = rdf_get_batch(tickers, period=period, batch_size=5, delay_between_batches=0.5)
        
        for ticker, df in batch_data.items():
            if df is not None and not df.empty and 'Close' in df.columns:
                close = df['Close']
                if isinstance(close, pd.DataFrame):
                    close = close.squeeze()
                if len(close) > 20:
                    all_returns[ticker] = log_returns(close)
    except Exception as e:
        logger.warning(f"Batch returns fetch failed: {e}")
        # Fallback to individual fetches
        for ticker in tickers:
            try:
                df = rdf_get_price(ticker, period=period)
                if df is not None and not df.empty and 'Close' in df.columns:
                    close = df['Close']
                    if isinstance(close, pd.DataFrame):
                        close = close.squeeze()
                    if len(close) > 20:
                        all_returns[ticker] = log_returns(close)
            except Exception as e:
                logger.warning(f"Failed to get returns for {ticker}: {e}")
    
    if not all_returns:
        return pd.DataFrame()
    
    return pd.DataFrame(all_returns).dropna()


def _get_adv(ticker: str) -> float:
    """Get average daily volume in shares."""
    try:
        df = rdf_get_price(ticker, period="3mo")
        if df is not None and not df.empty and 'Volume' in df.columns:
            return float(df['Volume'].mean())
    except:
        pass
    return 1e6


def _get_adv_dollar(ticker: str) -> float:
    """Get average daily dollar volume."""
    try:
        df = rdf_get_price(ticker, period="3mo")
        if df is not None and not df.empty and 'Volume' in df.columns and 'Close' in df.columns:
            avg_vol = float(df['Volume'].mean())
            avg_price = float(df['Close'].mean())
            return avg_vol * avg_price
    except:
        pass
    return 1e8


# =============================================================================
# FEATURE 5: CROSS-IMPACT MATRIX
# =============================================================================

def compute_cross_impact(positions: List[Position]) -> CrossImpactOutput:
    """
    Compute correlation network with shrinkage, centrality, and cluster analysis.
    """
    if len(positions) < 2:
        return CrossImpactOutput(
            correlation_matrix=[],
            tickers=[],
            centrality=[],
            clusters=[],
            top_connectors=[],
            correlation_stability={}
        )
    
    all_tickers = [p.ticker for p in positions]
    returns_df = _get_returns_matrix(all_tickers)
    
    # Filter to only tickers with valid data
    tickers = list(returns_df.columns) if len(returns_df) >= 30 else []
    
    if len(tickers) < 2:
        # Fallback: return empty but with all tickers listed
        return CrossImpactOutput(
            correlation_matrix=[],
            tickers=all_tickers,
            centrality=[CentralityMetrics(
                ticker=t, degree=0, eigenvector=0, 
                betweenness=0, pagerank=1/len(all_tickers),
                systemic_score=0
            ) for t in all_tickers],
            clusters=[],
            top_connectors=[],
            correlation_stability={}
        )
    
    # Compute shrunk covariance and correlation
    cov, shrinkage = ledoit_wolf_shrinkage(returns_df)
    corr = sample_correlation(returns_df)
    corr_matrix = corr.values.tolist()
    
    # Build network graph
    n = len(tickers)
    G = nx.Graph()
    for i, ticker in enumerate(tickers):
        G.add_node(ticker)
    
    for i in range(n):
        for j in range(i + 1, n):
            weight = abs(corr.iloc[i, j])
            if weight > 0.3:  # Only add significant correlations
                G.add_edge(tickers[i], tickers[j], weight=weight)
    
    # Compute centrality metrics
    centrality = []
    
    try:
        degree_cent = nx.degree_centrality(G)
        eigenvector_cent = nx.eigenvector_centrality_numpy(G) if len(G.edges) > 0 else {t: 0 for t in tickers}
        betweenness_cent = nx.betweenness_centrality(G)
        pagerank = nx.pagerank(G) if len(G.edges) > 0 else {t: 1/n for t in tickers}
    except:
        degree_cent = {t: 0 for t in tickers}
        eigenvector_cent = {t: 0 for t in tickers}
        betweenness_cent = {t: 0 for t in tickers}
        pagerank = {t: 1/n for t in tickers}
    
    for ticker in tickers:
        systemic = (
            0.3 * degree_cent.get(ticker, 0) +
            0.3 * eigenvector_cent.get(ticker, 0) +
            0.2 * betweenness_cent.get(ticker, 0) +
            0.2 * pagerank.get(ticker, 0)
        )
        centrality.append(CentralityMetrics(
            ticker=ticker,
            degree=degree_cent.get(ticker, 0),
            eigenvector=eigenvector_cent.get(ticker, 0),
            betweenness=betweenness_cent.get(ticker, 0),
            pagerank=pagerank.get(ticker, 0),
            systemic_score=systemic
        ))
    
    # Sort by systemic score
    centrality.sort(key=lambda x: x.systemic_score, reverse=True)
    top_connectors = [c.ticker for c in centrality[:3]]
    
    # Detect clusters using community detection
    clusters = []
    try:
        from networkx.algorithms import community
        communities = list(community.greedy_modularity_communities(G))
        
        for i, comm in enumerate(communities[:5]):
            comm_list = list(comm)
            if len(comm_list) < 2:
                continue
            
            # Internal correlation
            internal_corr = []
            for t1 in comm_list:
                for t2 in comm_list:
                    if t1 != t2 and t1 in tickers and t2 in tickers:
                        idx1, idx2 = tickers.index(t1), tickers.index(t2)
                        internal_corr.append(corr.iloc[idx1, idx2])
            
            avg_internal = np.mean(internal_corr) if internal_corr else 0
            total_weight = sum(p.weight for p in positions if p.ticker in comm_list)
            
            clusters.append(Cluster(
                id=i,
                assets=comm_list,
                total_weight=total_weight,
                internal_correlation=avg_internal,
                external_correlation=1 - avg_internal,
                fragility_score=avg_internal * total_weight
            ))
    except Exception as e:
        logger.warning(f"Cluster detection failed: {e}")
    
    # Correlation stability (rolling vs full period)
    stability = {}
    if len(returns_df) >= 60:
        corr_full = corr
        corr_recent = returns_df.tail(60).corr()
        for t1 in tickers[:5]:
            for t2 in tickers[:5]:
                if t1 < t2:
                    key = f"{t1}_{t2}"
                    if t1 in corr_full.columns and t2 in corr_full.columns:
                        diff = abs(corr_full.loc[t1, t2] - corr_recent.loc[t1, t2])
                        stability[key] = 1 - min(1, diff)
    
    return CrossImpactOutput(
        correlation_matrix=corr_matrix,
        tickers=tickers,
        centrality=centrality,
        clusters=clusters,
        top_connectors=top_connectors,
        correlation_stability=stability
    )


# =============================================================================
# FEATURE 6: LIQUIDITY MAP
# =============================================================================

def compute_liquidity_map(positions: List[Position], stress_multiplier: float = 2.0) -> LiquidityMap:
    """
    Analyze portfolio liquidity with exit times and bottleneck detection.
    """
    liq_positions = []
    total_mv = sum(p.market_value for p in positions)
    
    for pos in positions:
        adv_dollar = _get_adv_dollar(pos.ticker)
        
        # Normal exit days (10% participation)
        normal_days = exit_days(pos.market_value, adv_dollar, 0.10)
        
        # Stress exit days (5% participation, 50% ADV reduction)
        stress_adv = adv_dollar / stress_multiplier
        stress_days = exit_days(pos.market_value, stress_adv, 0.05)
        
        # Spread cost estimate (simplified)
        spread_cost = 0.001 if adv_dollar > 1e8 else 0.003 if adv_dollar > 1e7 else 0.01
        
        # Market impact (Almgren-Chriss approximation)
        vol = 0.25  # Assume 25% vol for impact calc
        impact = market_impact_sqrt(pos.market_value, adv_dollar, vol)
        
        total_haircut = spread_cost + impact
        liq_scr = liquidity_score(normal_days)
        
        # Status classification
        if normal_days <= 1:
            status = "LIQUID"
        elif normal_days <= 3:
            status = "MODERATE"
        elif normal_days <= 7:
            status = "ILLIQUID"
        else:
            status = "VERY_ILLIQUID"
        
        liq_positions.append(LiquidityPosition(
            ticker=pos.ticker,
            market_value=pos.market_value,
            adv=adv_dollar,
            exit_days_normal=normal_days,
            exit_days_stress=stress_days,
            spread_cost=spread_cost,
            total_haircut=total_haircut,
            liquidity_score=liq_scr,
            status=status
        ))
    
    # Sort by liquidity (worst first)
    liq_positions.sort(key=lambda x: x.exit_days_normal, reverse=True)
    
    # Portfolio-level metrics
    if liq_positions:
        weights = [p.market_value / total_mv for p in liq_positions] if total_mv > 0 else [1/len(liq_positions)] * len(liq_positions)
        scores = [p.liquidity_score for p in liq_positions]
        port_score = sum(w * s for w, s in zip(weights, scores))
        
        # Percentile (vs typical portfolio)
        port_percentile = min(100, max(0, port_score))
    else:
        port_score = 100
        port_percentile = 100
    
    # Bottlenecks (positions that would take >5 days to exit)
    bottlenecks = [p.ticker for p in liq_positions if p.exit_days_normal > 5]
    
    # Exit distribution
    exit_dist = {
        "<1 day": sum(1 for p in liq_positions if p.exit_days_normal < 1) / max(1, len(liq_positions)),
        "1-3 days": sum(1 for p in liq_positions if 1 <= p.exit_days_normal < 3) / max(1, len(liq_positions)),
        "3-7 days": sum(1 for p in liq_positions if 3 <= p.exit_days_normal < 7) / max(1, len(liq_positions)),
        ">7 days": sum(1 for p in liq_positions if p.exit_days_normal >= 7) / max(1, len(liq_positions)),
    }
    
    # Stress test
    stress_test = {
        "scenario": f"{stress_multiplier}x stress",
        "total_exit_days": sum(p.exit_days_stress for p in liq_positions) / max(1, len(liq_positions)),
        "total_haircut": sum(p.total_haircut * p.market_value for p in liq_positions),
        "worst_position": liq_positions[0].ticker if liq_positions else None
    }
    
    return LiquidityMap(
        positions=liq_positions,
        portfolio_score=port_score,
        portfolio_percentile=port_percentile,
        bottlenecks=bottlenecks,
        exit_distribution=exit_dist,
        stress_test=stress_test
    )


# =============================================================================
# FEATURE 7: CROWDING & CONCENTRATION SCANNER
# =============================================================================

def compute_concentration(positions: List[Position]) -> ConcentrationMetrics:
    """
    Analyze concentration and crowding using multiple metrics.
    """
    if not positions:
        return ConcentrationMetrics(
            hhi=0, effective_n=0, entropy=0, diversification_ratio=1,
            correlation_adjusted_hhi=0, top_5_concentration=0,
            sector_concentration={}, factor_concentration={},
            crowding_alerts=[]
        )
    
    weights = np.array([p.weight for p in positions])
    weights = weights / weights.sum() if weights.sum() > 0 else weights
    
    # Basic metrics
    hhi = herfindahl_hirschman_index(weights)
    eff_n = effective_n(weights)
    ent = entropy(weights)
    
    # Top 5 concentration
    sorted_weights = sorted(weights, reverse=True)
    top_5 = sum(sorted_weights[:5])
    
    # Get correlation matrix for correlation-adjusted metrics
    tickers = [p.ticker for p in positions]
    returns_df = _get_returns_matrix(tickers, period="6mo")
    
    if len(returns_df) >= 30:
        corr = sample_correlation(returns_df).values
        cov, _ = ledoit_wolf_shrinkage(returns_df)
        
        # Correlation-adjusted HHI
        corr_hhi = correlation_adjusted_hhi(weights, corr)
        
        # Diversification ratio
        vols = np.sqrt(np.diag(cov.values)) if len(cov) > 0 else np.ones(len(weights)) * 0.2
        port_vol = portfolio_volatility(weights, cov.values)
        div_ratio = diversification_ratio(weights, vols, cov.values)
    else:
        corr_hhi = hhi
        div_ratio = 1.0
    
    # Sector concentration
    sector_weights = {}
    for pos in positions:
        sector = pos.sector if pos.sector else "Unknown"
        sector_weights[sector] = sector_weights.get(sector, 0) + pos.weight
    
    # Factor concentration (simplified)
    factor_concentration = {
        "market": 1.0,  # Always fully exposed to market
        "size": 0.0,
        "value": 0.0,
        "momentum": 0.0
    }
    
    # Generate alerts
    alerts = []
    if hhi > 0.20:
        alerts.append(f"Very high concentration: HHI = {hhi:.2%}")
    elif hhi > 0.15:
        alerts.append(f"High concentration: HHI = {hhi:.2%}")
    
    if eff_n < 5:
        alerts.append(f"Low effective diversification: N_eff = {eff_n:.1f}")
    
    if top_5 > 0.70:
        alerts.append(f"Top 5 positions = {top_5:.1%} of portfolio")
    
    for sector, weight in sector_weights.items():
        if weight > 0.35:
            alerts.append(f"Sector overweight: {sector} = {weight:.1%}")
    
    return ConcentrationMetrics(
        hhi=hhi,
        effective_n=eff_n,
        entropy=ent,
        diversification_ratio=div_ratio,
        correlation_adjusted_hhi=corr_hhi,
        top_5_concentration=top_5,
        sector_concentration=sector_weights,
        factor_concentration=factor_concentration,
        crowding_alerts=alerts
    )


# =============================================================================
# FEATURE 8: DRAWDOWN SENSITIVITY SCANNER
# =============================================================================

def compute_drawdown_sensitivity(positions: List[Position], returns_df: Optional[pd.DataFrame] = None) -> DrawdownAttribution:
    """
    Attribute drawdowns to positions and compute sensitivities.
    """
    if not positions:
        return DrawdownAttribution(
            period_start="", period_end="", total_drawdown=0,
            position_contributions={}, sector_contributions={},
            factor_contributions={}, top_loss_drivers=[],
            sensitivity_matrix={}
        )
    
    tickers = [p.ticker for p in positions]
    
    if returns_df is None or len(returns_df) < 30:
        returns_df = _get_returns_matrix(tickers, period="1y")
    
    if len(returns_df) < 30:
        return DrawdownAttribution(
            period_start="", period_end="", total_drawdown=0,
            position_contributions={}, sector_contributions={},
            factor_contributions={}, top_loss_drivers=[],
            sensitivity_matrix={}
        )
    
    # Compute portfolio NAV
    weights = np.array([p.weight for p in positions if p.ticker in returns_df.columns])
    weights = weights / weights.sum() if weights.sum() > 0 else weights
    
    aligned_returns = returns_df[[t for t in tickers if t in returns_df.columns]]
    port_returns = (aligned_returns.values @ weights[:len(aligned_returns.columns)])
    nav = (1 + pd.Series(port_returns, index=aligned_returns.index)).cumprod()
    
    # Find max drawdown period
    peak = nav.expanding().max()
    drawdown = (nav - peak) / peak
    max_dd = drawdown.min()
    
    if max_dd >= 0:
        return DrawdownAttribution(
            period_start=str(nav.index[0].date()),
            period_end=str(nav.index[-1].date()),
            total_drawdown=0,
            position_contributions={},
            sector_contributions={},
            factor_contributions={},
            top_loss_drivers=[],
            sensitivity_matrix={}
        )
    
    # Find dd period
    trough_idx = drawdown.idxmin()
    peak_idx = nav.loc[:trough_idx].idxmax()
    
    # Attribution during DD period
    dd_returns = aligned_returns.loc[peak_idx:trough_idx]
    
    position_contributions = {}
    for i, ticker in enumerate(aligned_returns.columns):
        if i < len(weights):
            contrib = dd_returns[ticker].sum() * weights[i]
            position_contributions[ticker] = float(contrib)
    
    # Sort and get top drivers
    sorted_contribs = sorted(position_contributions.items(), key=lambda x: x[1])
    top_loss_drivers = [
        {"ticker": t, "contribution": c, "pct_of_loss": c / max_dd if max_dd != 0 else 0}
        for t, c in sorted_contribs[:5]
    ]
    
    # Sector contributions
    sector_contributions = {}
    for pos in positions:
        if pos.ticker in position_contributions:
            sector = pos.sector if pos.sector else "Unknown"
            sector_contributions[sector] = sector_contributions.get(sector, 0) + position_contributions[pos.ticker]
    
    # Sensitivity matrix (correlation of position returns to portfolio DD)
    sensitivity_matrix = {}
    for ticker in aligned_returns.columns:
        corr_to_port = aligned_returns[ticker].corr(pd.Series(port_returns, index=aligned_returns.index))
        sensitivity_matrix[ticker] = {"correlation_to_portfolio": float(corr_to_port)}
    
    return DrawdownAttribution(
        period_start=str(peak_idx.date()) if hasattr(peak_idx, 'date') else str(peak_idx),
        period_end=str(trough_idx.date()) if hasattr(trough_idx, 'date') else str(trough_idx),
        total_drawdown=float(max_dd),
        position_contributions=position_contributions,
        sector_contributions=sector_contributions,
        factor_contributions={},
        top_loss_drivers=top_loss_drivers,
        sensitivity_matrix=sensitivity_matrix
    )


# =============================================================================
# FEATURE 9: CAPITAL GUARDRAILS
# =============================================================================

def evaluate_guardrails(snapshot: PortfolioSnapshot, risk_metrics: Dict) -> GuardrailsOutput:
    """
    Evaluate all guardrails and return status.
    """
    guardrails = []
    breaches = []
    near_breaches = []
    blocked_actions = []
    
    total_mv = snapshot.nav
    cash_pct = snapshot.cash / total_mv if total_mv > 0 else 1
    
    for rule in _guardrail_rules:
        current = 0.0
        limit = rule["limit"]
        
        if rule["type"] == "position":
            # Max position size
            if snapshot.positions:
                max_weight = max(p.weight for p in snapshot.positions)
                current = max_weight
            
        elif rule["type"] == "sector":
            # Max sector exposure
            sector_weights = {}
            for pos in snapshot.positions:
                sector = pos.sector if pos.sector else "Unknown"
                sector_weights[sector] = sector_weights.get(sector, 0) + pos.weight
            current = max(sector_weights.values()) if sector_weights else 0
            
        elif rule["type"] == "cash":
            # Minimum cash
            current = cash_pct
            # Invert for "minimum" logic
            limit = 1 - limit  # Convert to "max allowable non-cash"
            current = 1 - current
            
        elif rule["type"] == "risk" and "vol" in rule["id"]:
            current = risk_metrics.get("vol_ann", 0)
            
        elif rule["type"] == "risk" and "dd" in rule["id"]:
            current = risk_metrics.get("current_dd", 0)
            # For drawdown, current is negative, limit is negative max
            
        elif rule["type"] == "concentration":
            if snapshot.positions:
                weights = np.array([p.weight for p in snapshot.positions])
                current = herfindahl_hirschman_index(weights)
            
        elif rule["type"] == "liquidity":
            if snapshot.positions:
                scores = [liquidity_score(p.exit_days) for p in snapshot.positions]
                weights = [p.weight for p in snapshot.positions]
                current = sum(w * s for w, s in zip(weights, scores))
                # Invert: lower score is worse
                limit = 100 - limit  # Convert to "max bad score"
                current = 100 - current
        
        # Calculate utilization
        if abs(limit) > 0.0001:
            utilization = current / limit
        else:
            utilization = 0
        
        # Determine status
        if utilization >= 1.0:
            status = GuardrailStatus.RED
            breaches.append(rule["name"])
        elif utilization >= 0.85:
            status = GuardrailStatus.ORANGE
            near_breaches.append(rule["name"])
        elif utilization >= 0.70:
            status = GuardrailStatus.YELLOW
        else:
            status = GuardrailStatus.GREEN
        
        buffer = (limit - current) / limit if limit != 0 else 1.0
        
        guardrails.append(Guardrail(
            id=rule["id"],
            name=rule["name"],
            type=rule["type"],
            limit=limit,
            current=current,
            utilization=utilization,
            status=status,
            buffer=buffer,
            days_to_breach=None,
            breach_probability=min(1, utilization)
        ))
    
    # System stress score (0-100)
    stress_score = sum(g.utilization * (1 if g.status == GuardrailStatus.GREEN else 2 if g.status == GuardrailStatus.YELLOW else 3) for g in guardrails) / len(guardrails) * 33
    
    return GuardrailsOutput(
        guardrails=guardrails,
        system_stress_score=min(100, stress_score),
        breaches=breaches,
        near_breaches=near_breaches,
        blocked_actions=blocked_actions
    )


def check_trade_guardrails(ticker: str, action: str, quantity: float, 
                          snapshot: PortfolioSnapshot) -> Tuple[bool, List[str]]:
    """
    Check if a proposed trade would violate any guardrails.
    Returns: (approved, list of violation reasons)
    """
    violations = []
    
    # Get all current positions and simulate the trade
    current_positions = {p.ticker: p for p in snapshot.positions}
    
    # This is a simplified check - in production would need full simulation
    if action.upper() == "BUY":
        # Check if this would exceed position limit
        current_weight = current_positions[ticker].weight if ticker in current_positions else 0
        estimated_new_weight = current_weight + 0.05  # Rough estimate
        
        if estimated_new_weight > 0.20:
            violations.append(f"Would exceed 20% position limit for {ticker}")
    
    return len(violations) == 0, violations


# =============================================================================
# FEATURE 10: AUTO-ALERT BRAIN
# =============================================================================

def evaluate_alerts(snapshot: PortfolioSnapshot, risk_metrics: Dict) -> AlertsOutput:
    """
    Evaluate alert rules and generate alerts.
    """
    global _active_alerts
    
    new_alerts = []
    timestamp = datetime.utcnow().isoformat()
    
    # Evaluate each rule
    for rule in _alert_rules:
        triggered = False
        evidence = []
        
        if "vol_ann" in rule["condition"]:
            vol = risk_metrics.get("vol_ann", 0)
            if vol > 0.25:
                triggered = True
                evidence.append(f"Volatility = {vol:.1%}")
                
        elif "current_dd" in rule["condition"]:
            dd = risk_metrics.get("current_dd", 0)
            if "< -0.10" in rule["condition"] and dd < -0.10:
                triggered = True
                evidence.append(f"Drawdown = {dd:.1%}")
            elif "< -0.15" in rule["condition"] and dd < -0.15:
                triggered = True
                evidence.append(f"Critical drawdown = {dd:.1%}")
                
        elif "hhi" in rule["condition"]:
            if snapshot.positions:
                weights = np.array([p.weight for p in snapshot.positions])
                hhi_val = herfindahl_hirschman_index(weights)
                if hhi_val > 0.15:
                    triggered = True
                    evidence.append(f"HHI = {hhi_val:.2%}")
                    
        elif "liquidity_score" in rule["condition"]:
            if snapshot.positions:
                scores = [liquidity_score(p.exit_days) for p in snapshot.positions]
                avg_score = np.mean(scores)
                if avg_score < 50:
                    triggered = True
                    evidence.append(f"Avg liquidity score = {avg_score:.0f}")
        
        if triggered:
            # Check for duplicates
            existing_ids = {a.id for a in _active_alerts if a.status != "RESOLVED"}
            if rule["id"] not in existing_ids:
                new_alerts.append(Alert(
                    id=rule["id"],
                    severity=rule["severity"],
                    category=rule["category"],
                    message=f"{rule['category']}: {rule['condition']}",
                    evidence=evidence,
                    timestamp=timestamp,
                    status="NEW",
                    related_alerts=[]
                ))
    
    # Add new alerts to active list
    _active_alerts.extend(new_alerts)
    
    # Keep only last 50 alerts
    _active_alerts = _active_alerts[-50:]
    
    # Count by severity
    severity_counts = {}
    for alert in _active_alerts:
        if alert.status != "RESOLVED":
            sev = alert.severity.value if hasattr(alert.severity, 'value') else str(alert.severity)
            severity_counts[sev] = severity_counts.get(sev, 0) + 1
    
    # Escalation required (HIGH or CRITICAL unacknowledged)
    escalation = [a.id for a in _active_alerts 
                  if a.status == "NEW" and a.severity in [Severity.HIGH, Severity.CRITICAL]]
    
    return AlertsOutput(
        active_alerts=[a for a in _active_alerts if a.status != "RESOLVED"],
        alert_count_by_severity=severity_counts,
        false_positive_rate=0.05,  # Placeholder
        escalation_required=escalation
    )


def acknowledge_alert(alert_id: str):
    """Acknowledge an alert."""
    for alert in _active_alerts:
        if alert.id == alert_id:
            alert.status = "ACKNOWLEDGED"
            break


def resolve_alert(alert_id: str):
    """Resolve an alert."""
    for alert in _active_alerts:
        if alert.id == alert_id:
            alert.status = "RESOLVED"
            break
