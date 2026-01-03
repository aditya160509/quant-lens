"""
Labs → ML → Clustering
=======================
Asset Similarity & Strategy Overlap Engine

Responsibilities:
- Asset similarity/redundancy detection
- Strategy overlap analysis
- Crowding detection
- Portfolio diversification insights
"""

import pandas as pd
import numpy as np
from scipy import stats
from scipy.cluster.hierarchy import linkage, fcluster, leaves_list
from scipy.spatial.distance import squareform, pdist
from typing import Dict, List, Any, Optional, Tuple
from datetime import datetime
import logging

from sklearn.cluster import DBSCAN, AgglomerativeClustering
from sklearn.preprocessing import StandardScaler

logger = logging.getLogger(__name__)


class ClusteringEngine:
    """
    Asset Similarity & Strategy Overlap Engine
    
    Detects hidden correlations, redundancy, and crowding
    in portfolios and trading strategies.
    """
    
    def __init__(self):
        self.asset_clusters: Dict[int, List[str]] = {}
        self.strategy_clusters: Dict[int, List[str]] = {}
        self.similarity_matrix: pd.DataFrame = None
        self.linkage_matrix: np.ndarray = None
        
    def cluster_assets_by_returns(
        self,
        returns: pd.DataFrame,
        n_clusters: int = None,
        method: str = 'hierarchical'
    ) -> Dict[str, Any]:
        """
        Cluster assets based on return correlations.
        
        Args:
            returns: DataFrame of asset returns (columns = assets)
            n_clusters: Number of clusters (auto if None)
            method: 'hierarchical' or 'dbscan'
            
        Returns:
            Clustering results with asset groups
        """
        # Compute correlation matrix
        corr_matrix = returns.corr()
        
        # Convert to distance matrix (1 - correlation)
        distance_matrix = 1 - corr_matrix.abs()
        distance_matrix = distance_matrix.clip(lower=0)  # Ensure non-negative
        
        # Fill NaN with max distance
        distance_matrix = distance_matrix.fillna(1)
        
        self.similarity_matrix = corr_matrix
        
        assets = list(returns.columns)
        n_assets = len(assets)
        
        if n_assets < 2:
            return {'error': 'Need at least 2 assets'}
        
        # Cluster
        if method == 'hierarchical':
            # Condensed distance matrix for linkage
            condensed = squareform(distance_matrix.values, checks=False)
            self.linkage_matrix = linkage(condensed, method='ward')
            
            # Determine number of clusters
            if n_clusters is None:
                n_clusters = min(5, n_assets // 2 + 1)
            
            labels = fcluster(self.linkage_matrix, n_clusters, criterion='maxclust') - 1
            
        else:  # DBSCAN
            clustering = DBSCAN(eps=0.5, min_samples=2, metric='precomputed')
            labels = clustering.fit_predict(distance_matrix.values)
        
        # Group assets by cluster
        self.asset_clusters = {}
        for i, asset in enumerate(assets):
            cluster_id = int(labels[i])
            if cluster_id not in self.asset_clusters:
                self.asset_clusters[cluster_id] = []
            self.asset_clusters[cluster_id].append(asset)
        
        # Compute cluster characteristics
        cluster_info = {}
        for cluster_id, cluster_assets in self.asset_clusters.items():
            if cluster_id == -1:  # Noise in DBSCAN
                cluster_info[cluster_id] = {
                    'assets': cluster_assets,
                    'type': 'NOISE',
                    'avg_correlation': 0
                }
                continue
            
            # Average correlation within cluster
            if len(cluster_assets) > 1:
                sub_corr = corr_matrix.loc[cluster_assets, cluster_assets]
                # Get off-diagonal elements
                mask = ~np.eye(len(cluster_assets), dtype=bool)
                avg_corr = sub_corr.values[mask].mean()
            else:
                avg_corr = 1.0
            
            # Average return and volatility
            cluster_returns = returns[cluster_assets]
            avg_return = cluster_returns.mean().mean() * 252  # Annualized
            avg_vol = cluster_returns.std().mean() * np.sqrt(252)
            
            cluster_info[cluster_id] = {
                'assets': cluster_assets,
                'size': len(cluster_assets),
                'avg_correlation': float(avg_corr),
                'avg_annual_return': float(avg_return),
                'avg_annual_volatility': float(avg_vol)
            }
        
        return {
            'n_clusters': len(self.asset_clusters),
            'clusters': cluster_info,
            'asset_labels': dict(zip(assets, labels.tolist()))
        }
    
    def compute_redundancy_scores(
        self,
        returns: pd.DataFrame,
        threshold: float = 0.7
    ) -> Dict[str, Any]:
        """
        Compute redundancy scores for each asset.
        
        An asset is redundant if highly correlated with others in portfolio.
        """
        corr_matrix = returns.corr()
        assets = list(returns.columns)
        
        redundancy = {}
        pairs = []
        
        for asset in assets:
            # Get correlations with other assets
            correlations = corr_matrix[asset].drop(asset)
            
            # Count highly correlated assets
            high_corr_count = (correlations.abs() > threshold).sum()
            max_corr = correlations.abs().max()
            most_similar = correlations.abs().idxmax()
            
            redundancy[asset] = {
                'redundancy_score': float(high_corr_count / (len(assets) - 1)),
                'high_correlation_count': int(high_corr_count),
                'max_correlation': float(max_corr),
                'most_similar_asset': most_similar,
                'is_redundant': high_corr_count >= 2
            }
            
            # Record pairs above threshold (only once per pair)
            for other in correlations.index:
                if corr_matrix.columns.get_loc(asset) < corr_matrix.columns.get_loc(other):
                    corr_val = abs(correlations[other])
                    if corr_val > threshold:
                        pairs.append({
                            'asset1': asset,
                            'asset2': other,
                            'correlation': float(corr_val)
                        })
        
        # Sort pairs by correlation
        pairs.sort(key=lambda x: x['correlation'], reverse=True)
        
        # Overall portfolio redundancy
        total_redundancy = np.mean([v['redundancy_score'] for v in redundancy.values()])
        
        return {
            'assets': redundancy,
            'redundant_pairs': pairs,
            'portfolio_redundancy_score': float(total_redundancy),
            'n_redundant_assets': sum(1 for v in redundancy.values() if v['is_redundant'])
        }
    
    def get_diversification_score(
        self,
        returns: pd.DataFrame,
        weights: Dict[str, float] = None
    ) -> Dict[str, Any]:
        """
        Compute portfolio diversification score.
        
        Uses diversification ratio and effective number of bets.
        """
        if weights is None:
            # Equal weight
            n = len(returns.columns)
            weights = {col: 1/n for col in returns.columns}
        
        # Ensure weights align with returns
        assets = list(weights.keys())
        w = np.array([weights[a] for a in assets])
        w = w / w.sum()  # Normalize
        
        returns_subset = returns[assets]
        cov_matrix = returns_subset.cov() * 252  # Annualized
        corr_matrix = returns_subset.corr()
        
        # Portfolio volatility
        port_var = w @ cov_matrix.values @ w
        port_vol = np.sqrt(port_var)
        
        # Weighted average individual volatility
        individual_vols = np.sqrt(np.diag(cov_matrix.values))
        avg_vol = w @ individual_vols
        
        # Diversification ratio
        diversification_ratio = avg_vol / port_vol if port_vol > 0 else 1
        
        # Effective number of assets (based on weights)
        effective_n = 1 / (w ** 2).sum()
        
        # Maximum diversification ratio (if perfectly uncorrelated)
        max_div_ratio = np.sqrt(len(assets))
        
        return {
            'diversification_ratio': float(diversification_ratio),
            'normalized_div_ratio': float(diversification_ratio / max_div_ratio),
            'effective_n_assets': float(effective_n),
            'actual_n_assets': len(assets),
            'portfolio_volatility': float(port_vol),
            'weighted_avg_volatility': float(avg_vol),
            'diversification_benefit': float((avg_vol - port_vol) / avg_vol) if avg_vol > 0 else 0
        }
    
    def cluster_strategies(
        self,
        equity_curves: pd.DataFrame,
        n_clusters: int = None
    ) -> Dict[str, Any]:
        """
        Cluster trading strategies based on equity curve similarity.
        
        Args:
            equity_curves: DataFrame of strategy equity curves (columns = strategies)
            n_clusters: Number of clusters (auto if None)
        """
        # Compute returns from equity curves
        returns = equity_curves.pct_change().dropna()
        
        # Use return correlation for clustering
        result = self.cluster_assets_by_returns(returns, n_clusters)
        
        # Rename for strategies
        self.strategy_clusters = self.asset_clusters.copy()
        
        return {
            'n_strategy_clusters': result['n_clusters'],
            'clusters': result['clusters'],
            'strategy_labels': result['asset_labels']
        }
    
    def detect_strategy_overlap(
        self,
        equity_curves: pd.DataFrame,
        threshold: float = 0.7
    ) -> Dict[str, Any]:
        """
        Detect overlapping strategies that may be too similar.
        """
        returns = equity_curves.pct_change().dropna()
        corr_matrix = returns.corr()
        
        strategies = list(returns.columns)
        overlaps = []
        
        for i, s1 in enumerate(strategies):
            for j, s2 in enumerate(strategies):
                if i < j:
                    corr = abs(corr_matrix.loc[s1, s2])
                    if corr > threshold:
                        overlaps.append({
                            'strategy1': s1,
                            'strategy2': s2,
                            'correlation': float(corr),
                            'overlap_warning': 'HIGH' if corr > 0.85 else 'MEDIUM'
                        })
        
        overlaps.sort(key=lambda x: x['correlation'], reverse=True)
        
        return {
            'overlapping_pairs': overlaps,
            'n_overlaps': len(overlaps),
            'total_strategies': len(strategies),
            'has_significant_overlap': len([o for o in overlaps if o['overlap_warning'] == 'HIGH']) > 0
        }
    
    def get_dendrogram_data(self) -> Dict[str, Any]:
        """Get data for dendrogram visualization"""
        if self.linkage_matrix is None:
            return {'error': 'No hierarchical clustering performed'}
        
        # Get optimal leaf ordering
        order = leaves_list(self.linkage_matrix)
        
        return {
            'linkage_matrix': self.linkage_matrix.tolist(),
            'leaf_order': order.tolist(),
            'n_leaves': len(order)
        }
    
    def get_similarity_matrix_data(self) -> Dict[str, Any]:
        """Get correlation/similarity matrix for heatmap"""
        if self.similarity_matrix is None:
            return {'error': 'No similarity matrix computed'}
        
        return {
            'assets': list(self.similarity_matrix.columns),
            'matrix': self.similarity_matrix.values.tolist()
        }
    
    def get_network_graph_data(
        self,
        threshold: float = 0.5
    ) -> Dict[str, Any]:
        """
        Get data for correlation network graph visualization.
        
        Nodes = assets, Edges = high correlations
        """
        if self.similarity_matrix is None:
            return {'error': 'No similarity matrix computed'}
        
        assets = list(self.similarity_matrix.columns)
        
        # Create nodes
        nodes = [{'id': asset, 'label': asset} for asset in assets]
        
        # Create edges for correlations above threshold
        edges = []
        for i, a1 in enumerate(assets):
            for j, a2 in enumerate(assets):
                if i < j:
                    corr = abs(self.similarity_matrix.loc[a1, a2])
                    if corr > threshold:
                        edges.append({
                            'source': a1,
                            'target': a2,
                            'weight': float(corr),
                            'color': 'green' if self.similarity_matrix.loc[a1, a2] > 0 else 'red'
                        })
        
        return {
            'nodes': nodes,
            'edges': edges,
            'threshold': threshold
        }
    
    def find_diversifying_assets(
        self,
        current_portfolio: List[str],
        candidate_assets: List[str],
        returns: pd.DataFrame
    ) -> List[Dict]:
        """
        Find assets that would best diversify the current portfolio.
        """
        if not current_portfolio or not candidate_assets:
            return []
        
        current_returns = returns[current_portfolio]
        portfolio_return = current_returns.mean(axis=1)
        
        results = []
        
        for candidate in candidate_assets:
            if candidate not in returns.columns:
                continue
            
            candidate_return = returns[candidate]
            
            # Correlation with portfolio
            corr_with_portfolio = portfolio_return.corr(candidate_return)
            
            # Individual correlations with each holding
            correlations = [returns[h].corr(candidate_return) for h in current_portfolio]
            avg_corr = np.mean(correlations)
            min_corr = min(correlations)
            
            # Diversification potential (lower correlation = better)
            div_potential = 1 - abs(corr_with_portfolio)
            
            results.append({
                'asset': candidate,
                'correlation_with_portfolio': float(corr_with_portfolio),
                'avg_correlation_with_holdings': float(avg_corr),
                'min_correlation': float(min_corr),
                'diversification_potential': float(div_potential),
                'recommendation': 'STRONG' if div_potential > 0.7 else 'MODERATE' if div_potential > 0.4 else 'WEAK'
            })
        
        # Sort by diversification potential
        results.sort(key=lambda x: x['diversification_potential'], reverse=True)
        
        return results


# =============================================================================
# CONVENIENCE FUNCTIONS
# =============================================================================

def analyze_portfolio_clustering(
    returns: pd.DataFrame,
    n_clusters: int = None
) -> Tuple[ClusteringEngine, Dict]:
    """Full portfolio clustering analysis"""
    engine = ClusteringEngine()
    
    clusters = engine.cluster_assets_by_returns(returns, n_clusters)
    redundancy = engine.compute_redundancy_scores(returns)
    diversification = engine.get_diversification_score(returns)
    
    return engine, {
        'clusters': clusters,
        'redundancy': redundancy,
        'diversification': diversification,
        'dendrogram': engine.get_dendrogram_data(),
        'similarity_matrix': engine.get_similarity_matrix_data()
    }
