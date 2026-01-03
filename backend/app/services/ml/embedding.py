"""
Labs → ML → Embedding
======================
Feature Space Embedding Explorer

Responsibilities:
- Dimensionality reduction (UMAP, t-SNE)
- Feature space visualization
- Regime separation validation
- Make ML spaces interpretable
"""

import pandas as pd
import numpy as np
from typing import Dict, List, Any, Optional, Tuple
from datetime import datetime
import logging

from sklearn.preprocessing import StandardScaler
from sklearn.decomposition import PCA
from sklearn.manifold import TSNE
from sklearn.metrics import silhouette_score, calinski_harabasz_score

# Try to import UMAP
try:
    import umap
    UMAP_AVAILABLE = True
except ImportError:
    UMAP_AVAILABLE = False

logger = logging.getLogger(__name__)


class EmbeddingEngine:
    """
    Feature Space Embedding Explorer
    
    Projects high-dimensional feature spaces into 2D/3D for
    visualization and regime separation analysis.
    """
    
    def __init__(self):
        self.scaler = StandardScaler()
        self.embedding: np.ndarray = None
        self.method: str = None
        self.feature_names: List[str] = []
        
    def compute_embedding(
        self,
        X: pd.DataFrame,
        method: str = 'umap',
        n_components: int = 2,
        **kwargs
    ) -> Dict[str, Any]:
        """
        Compute dimensionality reduction embedding.
        
        Args:
            X: Feature matrix
            method: 'umap', 'tsne', or 'pca'
            n_components: Number of output dimensions (2 or 3)
            **kwargs: Method-specific parameters
            
        Returns:
            Embedding coordinates and metadata
        """
        # Clean and scale
        X_clean = X.select_dtypes(include=[np.number]).dropna()
        if len(X_clean) < 10:
            return {'error': 'Insufficient data for embedding'}
        
        self.feature_names = list(X_clean.columns)
        X_scaled = self.scaler.fit_transform(X_clean)
        
        self.method = method
        
        if method == 'umap':
            if not UMAP_AVAILABLE:
                logger.warning("UMAP not available, falling back to t-SNE")
                method = 'tsne'
            else:
                reducer = umap.UMAP(
                    n_components=n_components,
                    n_neighbors=kwargs.get('n_neighbors', 15),
                    min_dist=kwargs.get('min_dist', 0.1),
                    metric=kwargs.get('metric', 'euclidean'),
                    random_state=42
                )
                self.embedding = reducer.fit_transform(X_scaled)
        
        if method == 'tsne':
            perplexity = min(kwargs.get('perplexity', 30), len(X_scaled) // 4)
            reducer = TSNE(
                n_components=n_components,
                perplexity=perplexity,
                learning_rate=kwargs.get('learning_rate', 'auto'),
                random_state=42,
                init='pca'
            )
            self.embedding = reducer.fit_transform(X_scaled)
        
        elif method == 'pca':
            reducer = PCA(n_components=n_components)
            self.embedding = reducer.fit_transform(X_scaled)
        
        # Prepare output
        result = {
            'method': method,
            'n_components': n_components,
            'n_samples': len(X_clean),
            'x': self.embedding[:, 0].tolist(),
            'y': self.embedding[:, 1].tolist(),
            'indices': X_clean.index.tolist()
        }
        
        if n_components == 3:
            result['z'] = self.embedding[:, 2].tolist()
        
        if method == 'pca':
            result['explained_variance'] = reducer.explained_variance_ratio_.tolist()
        
        return result
    
    def get_colored_embedding(
        self,
        labels: pd.Series = None,
        continuous_values: pd.Series = None,
        label_name: str = 'label'
    ) -> Dict[str, Any]:
        """
        Get embedding with color values for visualization.
        
        Args:
            labels: Categorical labels for coloring (e.g., regime, outcome)
            continuous_values: Continuous values for color gradient
            label_name: Name of the coloring variable
        """
        if self.embedding is None:
            return {'error': 'No embedding computed. Run compute_embedding() first.'}
        
        result = {
            'x': self.embedding[:, 0].tolist(),
            'y': self.embedding[:, 1].tolist()
        }
        
        if self.embedding.shape[1] == 3:
            result['z'] = self.embedding[:, 2].tolist()
        
        if labels is not None:
            result['color_labels'] = labels.tolist()
            result['color_type'] = 'categorical'
            result['label_name'] = label_name
            result['unique_labels'] = labels.unique().tolist()
        
        elif continuous_values is not None:
            result['color_values'] = continuous_values.tolist()
            result['color_type'] = 'continuous'
            result['label_name'] = label_name
            result['value_range'] = [float(continuous_values.min()), float(continuous_values.max())]
        
        return result
    
    def compute_cluster_overlay(
        self,
        n_clusters: int = 5
    ) -> Dict[str, Any]:
        """
        Add cluster overlay to embedding.
        """
        if self.embedding is None:
            return {'error': 'No embedding computed'}
        
        from sklearn.cluster import KMeans
        
        clusterer = KMeans(n_clusters=n_clusters, random_state=42, n_init=10)
        labels = clusterer.fit_predict(self.embedding)
        centers = clusterer.cluster_centers_
        
        return {
            'cluster_labels': labels.tolist(),
            'cluster_centers': centers.tolist(),
            'n_clusters': n_clusters
        }
    
    def compute_density_contours(
        self,
        n_levels: int = 10
    ) -> Dict[str, Any]:
        """
        Compute density contour data for 2D embedding.
        """
        if self.embedding is None or self.embedding.shape[1] < 2:
            return {'error': 'No 2D embedding available'}
        
        from scipy import stats
        
        x = self.embedding[:, 0]
        y = self.embedding[:, 1]
        
        # Create grid
        xmin, xmax = x.min() - 0.5, x.max() + 0.5
        ymin, ymax = y.min() - 0.5, y.max() + 0.5
        
        xx, yy = np.meshgrid(
            np.linspace(xmin, xmax, 50),
            np.linspace(ymin, ymax, 50)
        )
        
        # Compute KDE
        try:
            kernel = stats.gaussian_kde(np.vstack([x, y]))
            positions = np.vstack([xx.ravel(), yy.ravel()])
            density = kernel(positions).reshape(xx.shape)
        except Exception as e:
            logger.error(f"Density computation failed: {e}")
            return {'error': str(e)}
        
        # Compute contour levels
        levels = np.linspace(density.min(), density.max(), n_levels)
        
        return {
            'x_grid': xx.tolist(),
            'y_grid': yy.tolist(),
            'density': density.tolist(),
            'levels': levels.tolist()
        }
    
    def compute_separation_metrics(
        self,
        labels: pd.Series
    ) -> Dict[str, Any]:
        """
        Compute metrics for how well labels are separated in embedding space.
        """
        if self.embedding is None:
            return {'error': 'No embedding computed'}
        
        labels_array = labels.values
        n_labels = len(np.unique(labels_array))
        
        if n_labels < 2:
            return {'error': 'Need at least 2 label values'}
        
        # Silhouette score
        try:
            silhouette = silhouette_score(self.embedding, labels_array)
        except Exception:
            silhouette = 0
        
        # Calinski-Harabasz score
        try:
            calinski = calinski_harabasz_score(self.embedding, labels_array)
        except Exception:
            calinski = 0
        
        # Compute per-class metrics
        class_metrics = {}
        for label in np.unique(labels_array):
            mask = labels_array == label
            class_points = self.embedding[mask]
            other_points = self.embedding[~mask]
            
            # Within-class spread
            within_spread = np.std(class_points, axis=0).mean() if len(class_points) > 1 else 0
            
            # Distance to other classes
            if len(other_points) > 0:
                class_center = class_points.mean(axis=0)
                other_center = other_points.mean(axis=0)
                between_distance = np.linalg.norm(class_center - other_center)
            else:
                between_distance = 0
            
            class_metrics[str(label)] = {
                'count': int(mask.sum()),
                'within_spread': float(within_spread),
                'between_distance': float(between_distance),
                'separation_ratio': float(between_distance / (within_spread + 1e-6))
            }
        
        return {
            'silhouette_score': float(silhouette),
            'calinski_harabasz_score': float(calinski),
            'n_classes': n_labels,
            'class_metrics': class_metrics,
            'overall_separation': 'GOOD' if silhouette > 0.3 else 'MODERATE' if silhouette > 0.1 else 'POOR'
        }
    
    def compute_overlap_matrix(
        self,
        labels: pd.Series,
        threshold: float = 1.0
    ) -> Dict[str, Any]:
        """
        Compute overlap matrix between label groups in embedding space.
        
        Two groups overlap if their points are within threshold distance.
        """
        if self.embedding is None:
            return {'error': 'No embedding computed'}
        
        labels_array = labels.values
        unique_labels = np.unique(labels_array)
        n_labels = len(unique_labels)
        
        overlap_matrix = np.zeros((n_labels, n_labels))
        
        for i, label1 in enumerate(unique_labels):
            mask1 = labels_array == label1
            points1 = self.embedding[mask1]
            
            for j, label2 in enumerate(unique_labels):
                if i == j:
                    overlap_matrix[i, j] = 1.0
                    continue
                
                mask2 = labels_array == label2
                points2 = self.embedding[mask2]
                
                # Count points that are close to the other group
                overlap_count = 0
                for p1 in points1:
                    min_dist = np.min(np.linalg.norm(points2 - p1, axis=1))
                    if min_dist < threshold:
                        overlap_count += 1
                
                overlap_matrix[i, j] = overlap_count / len(points1) if len(points1) > 0 else 0
        
        return {
            'labels': [str(l) for l in unique_labels],
            'overlap_matrix': overlap_matrix.tolist(),
            'threshold': threshold
        }
    
    def get_embedding_statistics(self) -> Dict[str, Any]:
        """Get statistics about the current embedding"""
        if self.embedding is None:
            return {'error': 'No embedding computed'}
        
        return {
            'method': self.method,
            'n_samples': len(self.embedding),
            'n_dimensions': self.embedding.shape[1],
            'x_range': [float(self.embedding[:, 0].min()), float(self.embedding[:, 0].max())],
            'y_range': [float(self.embedding[:, 1].min()), float(self.embedding[:, 1].max())],
            'n_features': len(self.feature_names),
            'features': self.feature_names[:20]  # First 20
        }


# =============================================================================
# CONVENIENCE FUNCTIONS
# =============================================================================

def create_embedding(
    X: pd.DataFrame,
    method: str = 'umap',
    n_components: int = 2
) -> Tuple[EmbeddingEngine, Dict]:
    """Convenience function to create embedding"""
    engine = EmbeddingEngine()
    result = engine.compute_embedding(X, method, n_components)
    return engine, result


def visualize_regimes(
    X: pd.DataFrame,
    regime_labels: pd.Series,
    method: str = 'umap'
) -> Dict:
    """Create embedding colored by regime labels"""
    engine = EmbeddingEngine()
    engine.compute_embedding(X, method)
    
    colored = engine.get_colored_embedding(labels=regime_labels, label_name='regime')
    separation = engine.compute_separation_metrics(regime_labels)
    
    return {
        'embedding': colored,
        'separation': separation
    }
