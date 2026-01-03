"""
Labs → ML → Regimes
====================
Market Regime Discovery Engine

Responsibilities:
- Unsupervised regime detection (K-Means, Hierarchical)
- Regime transitions and statistics
- Label time periods with regime states
- Provide regime context to other models
"""

import pandas as pd
import numpy as np
from scipy import stats
from scipy.cluster.hierarchy import linkage, fcluster, dendrogram
from typing import Dict, List, Any, Optional, Tuple
from datetime import datetime
import logging

from sklearn.cluster import KMeans
from sklearn.preprocessing import StandardScaler
from sklearn.metrics import silhouette_score, calinski_harabasz_score

logger = logging.getLogger(__name__)


class RegimeDiscovery:
    """
    Market Regime Discovery Engine
    
    Discovers natural market regimes using unsupervised learning
    and provides regime context for trading signals.
    """
    
    def __init__(self):
        self.regimes: Dict[int, Dict] = {}
        self.regime_labels: pd.Series = None
        self.scaler = StandardScaler()
        self.feature_names: List[str] = []
        self.transition_matrix: np.ndarray = None
        
    def discover_regimes(
        self,
        features: pd.DataFrame,
        n_regimes: int = 4,
        method: str = 'kmeans'
    ) -> Dict[str, Any]:
        """
        Discover market regimes from feature data.
        
        Args:
            features: Feature matrix (volatility, correlation, returns, etc.)
            n_regimes: Number of regimes to discover
            method: 'kmeans' or 'hierarchical'
            
        Returns:
            Regime discovery results with labels and characteristics
        """
        # Clean and scale features
        X = features.select_dtypes(include=[np.number]).dropna()
        if len(X) < 50:
            return {'error': 'Insufficient data for regime discovery'}
        
        self.feature_names = list(X.columns)
        X_scaled = self.scaler.fit_transform(X)
        
        # Cluster
        if method == 'kmeans':
            clusterer = KMeans(n_clusters=n_regimes, random_state=42, n_init=10)
            labels = clusterer.fit_predict(X_scaled)
            centers = clusterer.cluster_centers_
        else:
            # Hierarchical clustering
            linkage_matrix = linkage(X_scaled, method='ward')
            labels = fcluster(linkage_matrix, n_regimes, criterion='maxclust') - 1
            
            # Calculate centers manually
            centers = []
            for i in range(n_regimes):
                mask = labels == i
                if mask.sum() > 0:
                    centers.append(X_scaled[mask].mean(axis=0))
                else:
                    centers.append(np.zeros(X_scaled.shape[1]))
            centers = np.array(centers)
        
        # Store labels
        self.regime_labels = pd.Series(labels, index=X.index)
        
        # Analyze each regime
        self.regimes = {}
        
        for regime_id in range(n_regimes):
            mask = labels == regime_id
            regime_data = X[mask]
            
            # Characteristics
            characteristics = {}
            for col in self.feature_names:
                characteristics[col] = {
                    'mean': float(regime_data[col].mean()),
                    'std': float(regime_data[col].std()),
                    'median': float(regime_data[col].median())
                }
            
            # Identify regime type based on characteristics
            regime_type = self._classify_regime_type(centers[regime_id])
            
            self.regimes[regime_id] = {
                'count': int(mask.sum()),
                'percentage': float(mask.sum() / len(labels) * 100),
                'center': centers[regime_id].tolist(),
                'characteristics': characteristics,
                'type': regime_type
            }
        
        # Compute quality metrics
        silhouette = silhouette_score(X_scaled, labels) if len(np.unique(labels)) > 1 else 0
        calinski = calinski_harabasz_score(X_scaled, labels) if len(np.unique(labels)) > 1 else 0
        
        # Compute transition matrix
        self.transition_matrix = self._compute_transition_matrix(labels, n_regimes)
        
        return {
            'n_regimes': n_regimes,
            'method': method,
            'regimes': self.regimes,
            'quality_metrics': {
                'silhouette_score': float(silhouette),
                'calinski_harabasz_score': float(calinski)
            },
            'transition_matrix': self.transition_matrix.tolist(),
            'total_observations': len(labels)
        }
    
    def _classify_regime_type(self, center: np.ndarray) -> str:
        """Classify regime based on cluster center characteristics"""
        # Heuristic based on common feature patterns
        # Assumes features include volatility, correlation, returns
        
        # Get average of center values
        avg_z = np.mean(center)
        vol_z = center[0] if len(center) > 0 else 0  # Assume first feature is volatility-related
        
        if vol_z > 1.0:
            return 'CRISIS'
        elif vol_z > 0.5:
            return 'HIGH_VOL'
        elif vol_z < -0.5:
            return 'LOW_VOL'
        elif avg_z > 0.3:
            return 'RISK_ON'
        elif avg_z < -0.3:
            return 'RISK_OFF'
        else:
            return 'NEUTRAL'
    
    def _compute_transition_matrix(
        self,
        labels: np.ndarray,
        n_regimes: int
    ) -> np.ndarray:
        """Compute regime transition probability matrix"""
        matrix = np.zeros((n_regimes, n_regimes))
        
        for i in range(len(labels) - 1):
            from_regime = labels[i]
            to_regime = labels[i + 1]
            matrix[from_regime, to_regime] += 1
        
        # Normalize to probabilities
        row_sums = matrix.sum(axis=1, keepdims=True)
        row_sums[row_sums == 0] = 1  # Avoid division by zero
        matrix = matrix / row_sums
        
        return matrix
    
    def get_regime_timeline(self) -> Dict[str, Any]:
        """Get timeline of regime labels"""
        if self.regime_labels is None:
            return {'error': 'No regimes discovered. Run discover_regimes() first.'}
        
        # Convert to timeline format
        timeline = []
        current_regime = None
        start_idx = None
        
        for idx, regime in self.regime_labels.items():
            if regime != current_regime:
                if current_regime is not None:
                    timeline.append({
                        'regime': int(current_regime),
                        'regime_type': self.regimes.get(current_regime, {}).get('type', 'UNKNOWN'),
                        'start': str(start_idx),
                        'end': str(idx)
                    })
                current_regime = regime
                start_idx = idx
        
        # Add last regime
        if current_regime is not None:
            timeline.append({
                'regime': int(current_regime),
                'regime_type': self.regimes.get(current_regime, {}).get('type', 'UNKNOWN'),
                'start': str(start_idx),
                'end': str(self.regime_labels.index[-1])
            })
        
        return {
            'timeline': timeline,
            'dates': [str(d) for d in self.regime_labels.index.tolist()],
            'labels': self.regime_labels.tolist()
        }
    
    def get_current_regime(self) -> Dict[str, Any]:
        """Get the most recent regime"""
        if self.regime_labels is None or len(self.regime_labels) == 0:
            return {'error': 'No regimes discovered'}
        
        current = int(self.regime_labels.iloc[-1])
        
        # Get probabilities of transitioning to each regime
        next_probs = {}
        if self.transition_matrix is not None:
            for i in range(len(self.transition_matrix[current])):
                next_probs[f'regime_{i}'] = float(self.transition_matrix[current][i])
        
        return {
            'current_regime': current,
            'regime_type': self.regimes.get(current, {}).get('type', 'UNKNOWN'),
            'characteristics': self.regimes.get(current, {}).get('characteristics', {}),
            'transition_probabilities': next_probs,
            'as_of': str(self.regime_labels.index[-1])
        }
    
    def get_regime_statistics(self) -> Dict[str, Any]:
        """Get detailed statistics for each regime"""
        if not self.regimes:
            return {'error': 'No regimes discovered'}
        
        stats = {}
        
        for regime_id, regime_data in self.regimes.items():
            # Calculate persistence (average duration)
            if self.regime_labels is not None:
                durations = []
                current_duration = 0
                
                for label in self.regime_labels:
                    if label == regime_id:
                        current_duration += 1
                    else:
                        if current_duration > 0:
                            durations.append(current_duration)
                        current_duration = 0
                
                if current_duration > 0:
                    durations.append(current_duration)
                
                avg_duration = np.mean(durations) if durations else 0
                max_duration = max(durations) if durations else 0
            else:
                avg_duration = 0
                max_duration = 0
            
            # Self-transition probability (persistence)
            self_transition = 0
            if self.transition_matrix is not None:
                self_transition = self.transition_matrix[regime_id][regime_id]
            
            stats[f'regime_{regime_id}'] = {
                'type': regime_data.get('type', 'UNKNOWN'),
                'count': regime_data['count'],
                'percentage': regime_data['percentage'],
                'avg_duration': float(avg_duration),
                'max_duration': int(max_duration),
                'persistence': float(self_transition),
                'center': regime_data['center']
            }
        
        return stats
    
    def predict_regime(
        self,
        features: Dict[str, float]
    ) -> Dict[str, Any]:
        """Predict regime for new observation"""
        if not self.regimes:
            return {'error': 'No regimes trained'}
        
        # Create feature vector
        feature_vec = [features.get(f, 0) for f in self.feature_names]
        X = np.array([feature_vec])
        X_scaled = self.scaler.transform(X)
        
        # Find closest regime (by distance to center)
        min_dist = float('inf')
        predicted_regime = 0
        
        distances = {}
        for regime_id, regime_data in self.regimes.items():
            center = np.array(regime_data['center'])
            dist = np.linalg.norm(X_scaled[0] - center)
            distances[regime_id] = float(dist)
            
            if dist < min_dist:
                min_dist = dist
                predicted_regime = regime_id
        
        return {
            'predicted_regime': predicted_regime,
            'regime_type': self.regimes[predicted_regime]['type'],
            'distance': float(min_dist),
            'all_distances': distances
        }
    
    def get_hierarchical_dendrogram_data(
        self,
        features: pd.DataFrame,
        max_d: float = None
    ) -> Dict[str, Any]:
        """Get data for dendrogram visualization"""
        X = features.select_dtypes(include=[np.number]).dropna()
        X_scaled = self.scaler.fit_transform(X)
        
        # Compute linkage
        Z = linkage(X_scaled, method='ward')
        
        return {
            'linkage_matrix': Z.tolist(),
            'n_samples': len(X),
            'suggested_n_clusters': self._suggest_n_clusters(Z),
            'max_distance': float(Z[-1, 2])
        }
    
    def _suggest_n_clusters(self, Z: np.ndarray) -> int:
        """Suggest optimal number of clusters using elbow method"""
        # Look at distance jumps
        distances = Z[:, 2]
        
        if len(distances) < 3:
            return 2
        
        # Find largest gap
        diffs = np.diff(distances)
        candidates = np.argsort(diffs)[-3:]  # Top 3 gaps
        
        # Prefer 3-6 clusters
        for n in range(3, 7):
            if len(Z) - n in candidates:
                return n
        
        return 4  # Default


# =============================================================================
# CONVENIENCE FUNCTIONS
# =============================================================================

def discover_market_regimes(
    features: pd.DataFrame,
    n_regimes: int = 4
) -> Tuple[RegimeDiscovery, Dict]:
    """Convenience function for regime discovery"""
    discovery = RegimeDiscovery()
    result = discovery.discover_regimes(features, n_regimes)
    return discovery, result


def get_regime_context(
    discovery: RegimeDiscovery,
    features: Dict[str, float]
) -> Dict:
    """Get regime context for a signal"""
    current = discovery.get_current_regime()
    predicted = discovery.predict_regime(features)
    
    return {
        'current_market_regime': current,
        'signal_predicted_regime': predicted,
        'regime_aligned': current.get('current_regime') == predicted.get('predicted_regime')
    }
