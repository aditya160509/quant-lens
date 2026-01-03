"""
Labs → ML → Regime Separation Quality Analyzer (Module 13)
==========================================================
Validate that market regimes discovered are truly distinct.
Analyze if different regimes occupy separate regions in feature space.

Responsibilities:
- Use embeddings to validate regime separation
- Calculate separation metrics between regime clusters
- Identify overlapping regimes that may need merging
- Generate quality scores for regime definitions
"""

import pandas as pd
import numpy as np
from scipy import stats
from scipy.spatial.distance import cdist, pdist, squareform
from sklearn.metrics import silhouette_score, calinski_harabasz_score, davies_bouldin_score
from sklearn.preprocessing import StandardScaler
from typing import Dict, List, Any, Optional, Tuple
from datetime import datetime
import logging

logger = logging.getLogger(__name__)


# =============================================================================
# REGIME SEPARATION QUALITY ANALYZER
# =============================================================================

class RegimeSeparationAnalyzer:
    """
    Regime Separation Quality Analyzer
    
    Validates the quality of discovered market regimes by analyzing
    their separation in feature/embedding space.
    """
    
    def __init__(self):
        self.embeddings: np.ndarray = None
        self.regime_labels: np.ndarray = None
        self.unique_regimes: List = []
        self.analysis_results: Dict[str, Any] = {}
    
    def analyze(
        self,
        embeddings: np.ndarray,
        regime_labels: np.ndarray,
        regime_names: Dict[int, str] = None
    ) -> Dict[str, Any]:
        """
        Analyze regime separation quality.
        
        Args:
            embeddings: 2D or 3D embeddings from UMAP/t-SNE (n_samples, n_dims)
            regime_labels: Regime label for each sample
            regime_names: Optional mapping of label IDs to names
            
        Returns:
            Comprehensive regime quality analysis
        """
        self.embeddings = np.array(embeddings)
        self.regime_labels = np.array(regime_labels)
        self.unique_regimes = list(np.unique(regime_labels))
        
        if len(self.unique_regimes) < 2:
            return {'error': 'Need at least 2 regimes for separation analysis'}
        
        if regime_names is None:
            regime_names = {r: f"Regime_{r}" for r in self.unique_regimes}
        
        # Calculate overall separation metrics
        overall_metrics = self._calculate_overall_metrics()
        
        # Calculate per-regime metrics
        regime_metrics = self._calculate_regime_metrics(regime_names)
        
        # Calculate pairwise overlap
        overlap_matrix = self._calculate_overlap_matrix(regime_names)
        
        # Identify ambiguous observations
        ambiguous = self._identify_ambiguous_observations()
        
        # Generate recommendations
        recommendations = self._generate_recommendations(overall_metrics, overlap_matrix)
        
        self.analysis_results = {
            'overall_metrics': overall_metrics,
            'regime_metrics': regime_metrics,
            'overlap_matrix': overlap_matrix,
            'ambiguous_observations': ambiguous,
            'recommendations': recommendations,
            'n_regimes': len(self.unique_regimes),
            'n_samples': len(self.regime_labels),
            'analyzed_at': datetime.now().isoformat()
        }
        
        return self.analysis_results
    
    def _calculate_overall_metrics(self) -> Dict[str, Any]:
        """Calculate overall regime separation metrics"""
        metrics = {}
        
        try:
            # Silhouette Score (-1 to 1, higher is better)
            silhouette = silhouette_score(self.embeddings, self.regime_labels)
            metrics['silhouette_score'] = float(silhouette)
            
            # Calinski-Harabasz Index (higher is better)
            ch_score = calinski_harabasz_score(self.embeddings, self.regime_labels)
            metrics['calinski_harabasz'] = float(ch_score)
            
            # Davies-Bouldin Index (lower is better)
            db_score = davies_bouldin_score(self.embeddings, self.regime_labels)
            metrics['davies_bouldin'] = float(db_score)
            
        except Exception as e:
            logger.warning(f"Error calculating clustering metrics: {e}")
        
        # Calculate centroid distances
        centroids = self._calculate_centroids()
        if len(centroids) >= 2:
            centroid_distances = pdist(list(centroids.values()))
            metrics['avg_centroid_distance'] = float(np.mean(centroid_distances))
            metrics['min_centroid_distance'] = float(np.min(centroid_distances))
        
        # Overall separation score (0-100)
        separation_score = self._compute_separation_score(metrics)
        metrics['separation_score'] = separation_score
        metrics['separation_grade'] = self._grade_separation(separation_score)
        
        return metrics
    
    def _calculate_centroids(self) -> Dict[Any, np.ndarray]:
        """Calculate centroid for each regime"""
        centroids = {}
        for regime in self.unique_regimes:
            mask = self.regime_labels == regime
            if mask.sum() > 0:
                centroids[regime] = self.embeddings[mask].mean(axis=0)
        return centroids
    
    def _compute_separation_score(self, metrics: Dict) -> float:
        """Compute overall separation score from metrics"""
        score = 50.0  # Base score
        
        # Adjust based on silhouette
        if 'silhouette_score' in metrics:
            sil = metrics['silhouette_score']
            # Silhouette ranges from -1 to 1
            score += sil * 30  # -30 to +30 adjustment
        
        # Adjust based on Davies-Bouldin (lower is better)
        if 'davies_bouldin' in metrics:
            db = metrics['davies_bouldin']
            # DB typically 0-3, lower is better
            score -= (db - 1) * 10  # Penalty for high DB
        
        return float(max(0, min(100, score)))
    
    def _grade_separation(self, score: float) -> str:
        """Grade the separation quality"""
        if score >= 75:
            return 'A'
        elif score >= 60:
            return 'B'
        elif score >= 45:
            return 'C'
        elif score >= 30:
            return 'D'
        else:
            return 'F'
    
    def _calculate_regime_metrics(self, regime_names: Dict) -> Dict[str, Any]:
        """Calculate per-regime metrics"""
        regime_metrics = {}
        centroids = self._calculate_centroids()
        
        for regime in self.unique_regimes:
            mask = self.regime_labels == regime
            regime_points = self.embeddings[mask]
            
            if len(regime_points) == 0:
                continue
            
            # Tightness (intra-cluster variance)
            tightness = np.mean(np.var(regime_points, axis=0))
            
            # Radius (max distance from centroid)
            if regime in centroids:
                distances = cdist(regime_points, [centroids[regime]])
                radius = float(np.max(distances))
                avg_distance = float(np.mean(distances))
            else:
                radius = 0
                avg_distance = 0
            
            # Distance to other centroids
            min_dist_to_other = float('inf')
            nearest_regime = None
            for other in self.unique_regimes:
                if other != regime and other in centroids and regime in centroids:
                    dist = np.linalg.norm(centroids[regime] - centroids[other])
                    if dist < min_dist_to_other:
                        min_dist_to_other = dist
                        nearest_regime = other
            
            regime_name = regime_names.get(regime, f"Regime_{regime}")
            regime_metrics[regime_name] = {
                'regime_id': regime,
                'n_samples': int(mask.sum()),
                'tightness': float(tightness),
                'radius': radius,
                'avg_distance_to_centroid': avg_distance,
                'nearest_regime': regime_names.get(nearest_regime, str(nearest_regime)),
                'distance_to_nearest': float(min_dist_to_other) if min_dist_to_other != float('inf') else None,
                'isolation_score': float(min_dist_to_other / (radius + 0.001)) if radius > 0 else 0
            }
        
        return regime_metrics
    
    def _calculate_overlap_matrix(self, regime_names: Dict) -> Dict[str, Any]:
        """Calculate pairwise overlap between regimes"""
        n_regimes = len(self.unique_regimes)
        overlap_scores = np.zeros((n_regimes, n_regimes))
        
        for i, regime1 in enumerate(self.unique_regimes):
            for j, regime2 in enumerate(self.unique_regimes):
                if i == j:
                    overlap_scores[i, j] = 0  # Self-overlap = 0
                else:
                    overlap = self._calculate_pairwise_overlap(regime1, regime2)
                    overlap_scores[i, j] = overlap
        
        # Find problematic pairs
        high_overlap_pairs = []
        for i, regime1 in enumerate(self.unique_regimes):
            for j, regime2 in enumerate(self.unique_regimes):
                if i < j and overlap_scores[i, j] > 20:  # >20% overlap
                    high_overlap_pairs.append({
                        'regime_1': regime_names.get(regime1, f"Regime_{regime1}"),
                        'regime_2': regime_names.get(regime2, f"Regime_{regime2}"),
                        'overlap_pct': float(overlap_scores[i, j]),
                        'recommendation': 'Consider merging' if overlap_scores[i, j] > 40 else 'Monitor boundary'
                    })
        
        return {
            'regimes': [regime_names.get(r, f"Regime_{r}") for r in self.unique_regimes],
            'overlap_matrix': overlap_scores.tolist(),
            'high_overlap_pairs': high_overlap_pairs,
            'has_overlap_issues': len(high_overlap_pairs) > 0
        }
    
    def _calculate_pairwise_overlap(self, regime1, regime2) -> float:
        """Calculate overlap between two regimes based on point proximity"""
        mask1 = self.regime_labels == regime1
        mask2 = self.regime_labels == regime2
        
        points1 = self.embeddings[mask1]
        points2 = self.embeddings[mask2]
        
        if len(points1) == 0 or len(points2) == 0:
            return 0.0
        
        # Calculate cross-distances
        distances = cdist(points1, points2)
        
        # Count points that are closer to the other regime's points than average
        centroid1 = points1.mean(axis=0)
        centroid2 = points2.mean(axis=0)
        
        inter_centroid_dist = np.linalg.norm(centroid1 - centroid2)
        
        # Points from regime1 that are "close" to regime2
        min_dist_to_2 = distances.min(axis=1)
        close_points_1 = (min_dist_to_2 < inter_centroid_dist * 0.3).sum()
        
        # Points from regime2 that are "close" to regime1
        min_dist_to_1 = distances.min(axis=0)
        close_points_2 = (min_dist_to_1 < inter_centroid_dist * 0.3).sum()
        
        # Overlap percentage
        total_boundary_points = close_points_1 + close_points_2
        total_points = len(points1) + len(points2)
        
        return float(total_boundary_points / total_points * 100)
    
    def _identify_ambiguous_observations(self) -> Dict[str, Any]:
        """Identify points that are near regime boundaries"""
        centroids = self._calculate_centroids()
        
        if len(centroids) < 2:
            return {'ambiguous_count': 0, 'indices': []}
        
        ambiguous_indices = []
        centroid_list = list(centroids.values())
        
        for i, point in enumerate(self.embeddings):
            # Distance to all centroids
            distances = [np.linalg.norm(point - c) for c in centroid_list]
            sorted_dist = sorted(distances)
            
            # Ambiguous if close to multiple centroids
            if len(sorted_dist) >= 2:
                ratio = sorted_dist[0] / (sorted_dist[1] + 0.001)
                if ratio > 0.8:  # Close to boundary
                    ambiguous_indices.append(i)
        
        return {
            'ambiguous_count': len(ambiguous_indices),
            'ambiguous_pct': float(len(ambiguous_indices) / len(self.embeddings) * 100),
            'indices': ambiguous_indices[:100],  # Limit to first 100
            'interpretation': self._interpret_ambiguity(len(ambiguous_indices) / len(self.embeddings))
        }
    
    def _interpret_ambiguity(self, pct: float) -> str:
        """Interpret ambiguity percentage"""
        if pct < 0.1:
            return "Excellent regime definitions - very few ambiguous observations"
        elif pct < 0.2:
            return "Good regime definitions - acceptable boundary uncertainty"
        elif pct < 0.3:
            return "Moderate overlap - consider refining regime boundaries"
        else:
            return "High overlap - regimes may need merging or redefinition"
    
    def _generate_recommendations(
        self, 
        overall: Dict, 
        overlap: Dict
    ) -> List[str]:
        """Generate actionable recommendations"""
        recommendations = []
        
        # Separation score
        score = overall.get('separation_score', 50)
        if score < 45:
            recommendations.append(
                f"🔴 Low separation score ({score:.0f}/100). "
                f"Regimes are not well-separated in feature space."
            )
        elif score < 60:
            recommendations.append(
                f"🟡 Moderate separation score ({score:.0f}/100). "
                f"Consider adjusting number of regimes or clustering parameters."
            )
        else:
            recommendations.append(
                f"✅ Good separation score ({score:.0f}/100). "
                f"Regimes are reasonably distinct."
            )
        
        # High overlap pairs
        high_overlap = overlap.get('high_overlap_pairs', [])
        for pair in high_overlap[:3]:  # Top 3
            if pair['overlap_pct'] > 40:
                recommendations.append(
                    f"🔴 {pair['regime_1']} and {pair['regime_2']} have {pair['overlap_pct']:.0f}% overlap. "
                    f"Consider merging these regimes."
                )
            else:
                recommendations.append(
                    f"🟡 {pair['regime_1']} and {pair['regime_2']} have boundary overlap. "
                    f"Monitor for stable classification."
                )
        
        return recommendations
    
    def get_visualization_data(self) -> Dict[str, Any]:
        """Get data for visualization"""
        if self.embeddings is None:
            return {'error': 'Run analysis first'}
        
        centroids = self._calculate_centroids()
        
        return {
            'embeddings': self.embeddings.tolist(),
            'labels': self.regime_labels.tolist(),
            'centroids': {k: v.tolist() for k, v in centroids.items()},
            'n_dims': self.embeddings.shape[1]
        }
    
    def get_overlap_heatmap_data(self) -> Dict[str, Any]:
        """Get data for overlap heatmap"""
        if not self.analysis_results:
            return {'error': 'Run analysis first'}
        
        return self.analysis_results.get('overlap_matrix', {})


# =============================================================================
# CONVENIENCE FUNCTIONS
# =============================================================================

def analyze_regime_separation(
    embeddings: np.ndarray,
    regime_labels: np.ndarray,
    regime_names: Dict[int, str] = None
) -> Tuple[RegimeSeparationAnalyzer, Dict]:
    """Convenience function for regime separation analysis"""
    analyzer = RegimeSeparationAnalyzer()
    results = analyzer.analyze(embeddings, regime_labels, regime_names)
    return analyzer, results


def get_regime_quality_score(analyzer: RegimeSeparationAnalyzer) -> float:
    """Get overall regime quality score"""
    if not analyzer.analysis_results:
        return 0.0
    return analyzer.analysis_results.get('overall_metrics', {}).get('separation_score', 0.0)
