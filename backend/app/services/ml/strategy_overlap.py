"""
Labs → ML → Strategy Overlap & Crowding Detector (Module 11)
=============================================================
Detect when multiple trading strategies are redundant (correlated returns)
to avoid concentration risk.

Responsibilities:
- Collect equity curves from each strategy
- Calculate correlation matrix of strategy returns
- Cluster strategies by behavior
- Identify overlapping strategies that don't add diversification
"""

import pandas as pd
import numpy as np
from scipy import stats
from scipy.cluster.hierarchy import linkage, fcluster, dendrogram
from scipy.spatial.distance import squareform
from sklearn.cluster import KMeans
from typing import Dict, List, Any, Optional, Tuple
from datetime import datetime
import logging

logger = logging.getLogger(__name__)


# =============================================================================
# STRATEGY OVERLAP DETECTOR
# =============================================================================

class StrategyOverlapDetector:
    """
    Strategy Overlap & Crowding Detector
    
    Identifies redundant strategies to prevent concentration risk
    in multi-strategy portfolios.
    """
    
    OVERLAP_THRESHOLD = 0.7  # Correlation above this = high overlap
    WARNING_THRESHOLD = 0.5  # Correlation above this = moderate overlap
    
    def __init__(self, overlap_threshold: float = 0.7):
        self.overlap_threshold = overlap_threshold
        self.strategy_returns: pd.DataFrame = None
        self.correlation_matrix: pd.DataFrame = None
        self.clusters: Dict[str, int] = {}
        self.linkage_matrix = None
        self.analysis_results: Dict[str, Any] = {}
    
    def fit(
        self,
        strategy_returns: pd.DataFrame,
        strategy_metadata: Dict[str, Dict] = None
    ) -> Dict[str, Any]:
        """
        Analyze strategy overlap and clustering.
        
        Args:
            strategy_returns: DataFrame where each column is a strategy's daily returns
            strategy_metadata: Optional dict with strategy names as keys, metadata as values
            
        Returns:
            Complete overlap analysis
        """
        if strategy_returns.empty or len(strategy_returns.columns) < 2:
            return {'error': 'Need at least 2 strategies for overlap analysis'}
        
        self.strategy_returns = strategy_returns.copy()
        strategies = list(strategy_returns.columns)
        
        # Calculate correlation matrix
        self.correlation_matrix = strategy_returns.corr()
        
        # Perform hierarchical clustering
        self._perform_clustering()
        
        # Identify overlapping pairs
        overlap_pairs = self._identify_overlap_pairs()
        
        # Calculate diversification score
        diversification = self._calculate_diversification_score()
        
        # Get strategy clusters
        cluster_assignments = self._get_cluster_assignments()
        
        # Calculate concentration risk
        concentration = self._calculate_concentration_risk(cluster_assignments)
        
        self.analysis_results = {
            'strategies': strategies,
            'n_strategies': len(strategies),
            'correlation_matrix': self.correlation_matrix.to_dict(),
            'overlap_pairs': overlap_pairs,
            'high_overlap_count': len([p for p in overlap_pairs if p['correlation'] >= self.overlap_threshold]),
            'diversification_score': diversification,
            'clusters': cluster_assignments,
            'concentration_risk': concentration,
            'recommendations': self._generate_recommendations(overlap_pairs, concentration),
            'analyzed_at': datetime.now().isoformat()
        }
        
        return self.analysis_results
    
    def _perform_clustering(self):
        """Perform hierarchical clustering on strategies"""
        if self.correlation_matrix is None:
            return
        
        # Convert correlation to distance (1 - corr)
        distance_matrix = 1 - self.correlation_matrix.abs()
        np.fill_diagonal(distance_matrix.values, 0)
        
        # Use condensed distance matrix for linkage
        condensed = squareform(distance_matrix.values)
        
        # Perform hierarchical clustering
        self.linkage_matrix = linkage(condensed, method='ward')
        
        # Assign clusters (cut tree at appropriate level)
        n_clusters = min(max(2, len(self.correlation_matrix) // 3), 5)
        cluster_labels = fcluster(self.linkage_matrix, n_clusters, criterion='maxclust')
        
        for strategy, label in zip(self.correlation_matrix.columns, cluster_labels):
            self.clusters[strategy] = int(label)
    
    def _identify_overlap_pairs(self) -> List[Dict]:
        """Identify pairs of strategies with significant overlap"""
        overlap_pairs = []
        
        strategies = list(self.correlation_matrix.columns)
        n = len(strategies)
        
        for i in range(n):
            for j in range(i + 1, n):
                corr = self.correlation_matrix.iloc[i, j]
                
                if abs(corr) >= self.WARNING_THRESHOLD:
                    overlap_pairs.append({
                        'strategy_1': strategies[i],
                        'strategy_2': strategies[j],
                        'correlation': float(corr),
                        'overlap_score': float(abs(corr) * 100),
                        'severity': 'HIGH' if abs(corr) >= self.overlap_threshold else 'MODERATE',
                        'recommendation': self._get_pair_recommendation(strategies[i], strategies[j], corr)
                    })
        
        # Sort by correlation (highest first)
        overlap_pairs.sort(key=lambda x: abs(x['correlation']), reverse=True)
        return overlap_pairs
    
    def _get_pair_recommendation(self, s1: str, s2: str, corr: float) -> str:
        """Generate recommendation for overlapping pair"""
        if abs(corr) >= 0.85:
            return f"Consider pausing {s2} or significantly reducing allocation"
        elif abs(corr) >= 0.7:
            return f"Reduce combined exposure; strategies behave similarly"
        elif abs(corr) >= 0.5:
            return f"Monitor correlation; consider gradual rebalancing"
        else:
            return "Acceptable overlap level"
    
    def _calculate_diversification_score(self) -> Dict[str, Any]:
        """Calculate overall portfolio diversification score"""
        if self.correlation_matrix is None:
            return {'score': 0}
        
        # Average pairwise correlation (excluding diagonal)
        n = len(self.correlation_matrix)
        if n < 2:
            return {'score': 100}
        
        corr_values = []
        for i in range(n):
            for j in range(i + 1, n):
                corr_values.append(abs(self.correlation_matrix.iloc[i, j]))
        
        avg_correlation = np.mean(corr_values)
        
        # Convert to diversification score (0-100)
        # Lower average correlation = higher diversification
        diversification_score = (1 - avg_correlation) * 100
        
        return {
            'score': float(diversification_score),
            'avg_correlation': float(avg_correlation),
            'interpretation': self._interpret_diversification(diversification_score),
            'grade': 'A' if diversification_score >= 70 else 'B' if diversification_score >= 50 else 'C' if diversification_score >= 30 else 'D'
        }
    
    def _interpret_diversification(self, score: float) -> str:
        """Interpret diversification score"""
        if score >= 70:
            return "Excellent diversification - strategies are largely independent"
        elif score >= 50:
            return "Good diversification - some overlap but manageable"
        elif score >= 30:
            return "Moderate diversification - consider adding uncorrelated strategies"
        else:
            return "Poor diversification - high strategy overlap, concentration risk"
    
    def _get_cluster_assignments(self) -> Dict[str, Any]:
        """Get strategy cluster assignments with details"""
        if not self.clusters:
            return {}
        
        # Group strategies by cluster
        cluster_groups = {}
        for strategy, cluster_id in self.clusters.items():
            if cluster_id not in cluster_groups:
                cluster_groups[cluster_id] = []
            cluster_groups[cluster_id].append(strategy)
        
        # Calculate cluster statistics
        cluster_stats = {}
        for cluster_id, strategies in cluster_groups.items():
            if self.strategy_returns is not None and len(strategies) > 0:
                cluster_returns = self.strategy_returns[strategies].mean(axis=1)
                cluster_stats[f"Cluster_{cluster_id}"] = {
                    'strategies': strategies,
                    'n_strategies': len(strategies),
                    'avg_return': float(cluster_returns.mean()),
                    'std_return': float(cluster_returns.std()),
                    'sharpe': float(cluster_returns.mean() / cluster_returns.std() * np.sqrt(252)) if cluster_returns.std() > 0 else 0
                }
            else:
                cluster_stats[f"Cluster_{cluster_id}"] = {
                    'strategies': strategies,
                    'n_strategies': len(strategies)
                }
        
        return cluster_stats
    
    def _calculate_concentration_risk(self, clusters: Dict) -> Dict[str, Any]:
        """Calculate concentration risk from cluster distribution"""
        if not clusters:
            return {'risk_level': 'UNKNOWN'}
        
        cluster_sizes = [c['n_strategies'] for c in clusters.values()]
        total = sum(cluster_sizes)
        
        if total == 0:
            return {'risk_level': 'UNKNOWN'}
        
        # Concentration metrics
        max_cluster_pct = max(cluster_sizes) / total
        hhi = sum((s/total)**2 for s in cluster_sizes)  # Herfindahl-Hirschman Index
        
        # Determine risk level
        if max_cluster_pct >= 0.6:
            risk_level = 'HIGH'
        elif max_cluster_pct >= 0.4:
            risk_level = 'MODERATE'
        else:
            risk_level = 'LOW'
        
        return {
            'risk_level': risk_level,
            'largest_cluster_pct': float(max_cluster_pct * 100),
            'hhi': float(hhi),
            'effective_clusters': float(1 / hhi) if hhi > 0 else len(clusters),
            'warning': f"Top cluster contains {max_cluster_pct*100:.1f}% of strategies" if max_cluster_pct >= 0.4 else None
        }
    
    def _generate_recommendations(
        self, 
        overlap_pairs: List[Dict], 
        concentration: Dict
    ) -> List[str]:
        """Generate actionable recommendations"""
        recommendations = []
        
        # High overlap warnings
        high_overlap = [p for p in overlap_pairs if p['severity'] == 'HIGH']
        if high_overlap:
            recommendations.append(
                f"🔴 {len(high_overlap)} strategy pairs have HIGH overlap (>70% correlation). "
                f"Consider consolidating or reducing exposure."
            )
        
        # Concentration risk
        if concentration.get('risk_level') == 'HIGH':
            recommendations.append(
                f"🔴 High concentration risk: {concentration.get('largest_cluster_pct', 0):.1f}% "
                f"of strategies in one cluster. Diversify across more strategy types."
            )
        elif concentration.get('risk_level') == 'MODERATE':
            recommendations.append(
                f"🟡 Moderate concentration: Consider adding uncorrelated strategies."
            )
        
        # Diversification score
        if hasattr(self, 'analysis_results') and 'diversification_score' in self.analysis_results:
            score = self.analysis_results['diversification_score'].get('score', 0)
            if score < 50:
                recommendations.append(
                    f"🟡 Diversification score is {score:.0f}/100. "
                    f"Look for strategies with low correlation to existing ones."
                )
        
        if not recommendations:
            recommendations.append("✅ Strategy portfolio appears well-diversified.")
        
        return recommendations
    
    def get_similarity_heatmap(self) -> Dict[str, Any]:
        """Get data for similarity heatmap visualization"""
        if self.correlation_matrix is None:
            return {'error': 'Run analysis first'}
        
        strategies = list(self.correlation_matrix.columns)
        
        return {
            'strategies': strategies,
            'correlations': self.correlation_matrix.values.tolist(),
            'threshold_high': self.overlap_threshold,
            'threshold_moderate': self.WARNING_THRESHOLD
        }
    
    def get_dendrogram_data(self) -> Dict[str, Any]:
        """Get data for dendrogram visualization"""
        if self.linkage_matrix is None:
            return {'error': 'Run analysis first'}
        
        strategies = list(self.correlation_matrix.columns)
        
        # Convert linkage to JSON-serializable format
        return {
            'strategies': strategies,
            'linkage': self.linkage_matrix.tolist(),
            'clusters': self.clusters,
            'n_clusters': len(set(self.clusters.values()))
        }
    
    def get_allocation_suggestion(
        self,
        current_allocations: Dict[str, float] = None,
        target_diversification: float = 70
    ) -> Dict[str, Any]:
        """Suggest optimal allocation for better diversification"""
        if not self.analysis_results:
            return {'error': 'Run analysis first'}
        
        strategies = self.analysis_results.get('strategies', [])
        n = len(strategies)
        
        if n == 0:
            return {'error': 'No strategies to allocate'}
        
        # Simple heuristic: Inverse correlation-based weights
        if self.correlation_matrix is not None:
            avg_correlations = self.correlation_matrix.abs().mean()
            # Lower correlation = higher weight
            inverse_weights = 1 / (avg_correlations + 0.1)
            normalized_weights = inverse_weights / inverse_weights.sum()
            
            suggestions = {
                strategy: float(weight * 100)
                for strategy, weight in normalized_weights.items()
            }
        else:
            # Equal weight fallback
            equal_weight = 100 / n
            suggestions = {strategy: equal_weight for strategy in strategies}
        
        return {
            'suggested_allocations': suggestions,
            'methodology': 'Inverse correlation weighting',
            'note': 'Strategies with lower average correlation receive higher weights'
        }


# =============================================================================
# CONVENIENCE FUNCTIONS
# =============================================================================

def analyze_strategy_overlap(
    strategy_returns: pd.DataFrame,
    overlap_threshold: float = 0.7
) -> Tuple[StrategyOverlapDetector, Dict]:
    """Convenience function for strategy overlap analysis"""
    detector = StrategyOverlapDetector(overlap_threshold)
    results = detector.fit(strategy_returns)
    return detector, results


def get_overlap_warnings(detector: StrategyOverlapDetector) -> List[Dict]:
    """Get list of overlap warnings"""
    if not detector.analysis_results:
        return []
    return detector.analysis_results.get('overlap_pairs', [])
