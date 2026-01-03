"""
Labs → ML → Errors
====================
Error & Failure Regime Analyzer

Responsibilities:
- Misclassification analysis
- Failure clustering
- Dangerous condition discovery
- Improve future models by understanding failures
"""

import pandas as pd
import numpy as np
from scipy import stats
from typing import Dict, List, Any, Optional, Tuple
from datetime import datetime
import logging

from sklearn.cluster import KMeans, DBSCAN
from sklearn.preprocessing import StandardScaler
from sklearn.decomposition import PCA

logger = logging.getLogger(__name__)


class ErrorAnalyzer:
    """
    Error & Failure Regime Analyzer
    
    Clusters model errors to identify high-risk conditions
    and provide actionable insights for model improvement.
    """
    
    def __init__(self):
        self.error_data: pd.DataFrame = None
        self.clusters: Dict[int, Dict] = {}
        self.high_risk_conditions: List[Dict] = []
        self.scaler = StandardScaler()
        
    def analyze_errors(
        self,
        predictions: pd.Series,
        actuals: pd.Series,
        features: pd.DataFrame,
        metadata: pd.DataFrame = None
    ) -> Dict[str, Any]:
        """
        Analyze prediction errors.
        
        Args:
            predictions: Model predictions (probabilities)
            actuals: Actual outcomes (0/1)
            features: Feature matrix at prediction time
            metadata: Optional metadata (dates, tickers, etc.)
            
        Returns:
            Comprehensive error analysis
        """
        # Compute errors
        binary_preds = (predictions > 0.5).astype(int)
        
        # Error types
        errors = binary_preds != actuals
        false_positives = (binary_preds == 1) & (actuals == 0)
        false_negatives = (binary_preds == 0) & (actuals == 1)
        
        # Store error data
        self.error_data = features[errors].copy()
        self.error_data['prediction'] = predictions[errors].values
        self.error_data['actual'] = actuals[errors].values
        self.error_data['error_type'] = np.where(
            false_positives[errors], 'false_positive', 'false_negative'
        )
        
        if metadata is not None:
            for col in metadata.columns:
                self.error_data[col] = metadata.loc[errors.index, col].values
        
        # Basic error statistics
        total = len(predictions)
        n_errors = errors.sum()
        
        result = {
            'total_predictions': int(total),
            'total_errors': int(n_errors),
            'error_rate': float(n_errors / total) if total > 0 else 0,
            'false_positives': int(false_positives.sum()),
            'false_negatives': int(false_negatives.sum()),
            'fp_rate': float(false_positives.sum() / (binary_preds == 1).sum()) if (binary_preds == 1).sum() > 0 else 0,
            'fn_rate': float(false_negatives.sum() / (binary_preds == 0).sum()) if (binary_preds == 0).sum() > 0 else 0
        }
        
        # Analyze error distribution by feature
        result['feature_error_analysis'] = self._analyze_errors_by_feature(
            features, errors
        )
        
        return result
    
    def _analyze_errors_by_feature(
        self,
        features: pd.DataFrame,
        errors: pd.Series
    ) -> Dict[str, Any]:
        """Analyze error rates across feature quantiles"""
        analysis = {}
        
        for col in features.select_dtypes(include=[np.number]).columns:
            try:
                # Split into quantiles
                quantiles = pd.qcut(features[col], q=4, labels=['Q1', 'Q2', 'Q3', 'Q4'], duplicates='drop')
                
                error_by_q = {}
                for q in quantiles.unique():
                    mask = quantiles == q
                    if mask.sum() > 0:
                        error_by_q[q] = float(errors[mask].mean())
                
                if len(error_by_q) >= 2:
                    max_error_q = max(error_by_q, key=error_by_q.get)
                    min_error_q = min(error_by_q, key=error_by_q.get)
                    
                    analysis[col] = {
                        'error_by_quantile': error_by_q,
                        'highest_error_quantile': max_error_q,
                        'lowest_error_quantile': min_error_q,
                        'error_range': error_by_q[max_error_q] - error_by_q[min_error_q]
                    }
            except Exception as e:
                logger.debug(f"Could not analyze {col}: {e}")
        
        return analysis
    
    def cluster_errors(
        self,
        n_clusters: int = 5,
        method: str = 'kmeans'
    ) -> Dict[str, Any]:
        """
        Cluster errors to find patterns in failures.
        
        Args:
            n_clusters: Number of clusters (for kmeans)
            method: 'kmeans' or 'dbscan'
            
        Returns:
            Cluster analysis results
        """
        if self.error_data is None or len(self.error_data) < 10:
            return {'error': 'Insufficient error data. Run analyze_errors() first.'}
        
        # Select numeric features
        feature_cols = [c for c in self.error_data.columns 
                       if c not in ['prediction', 'actual', 'error_type'] 
                       and np.issubdtype(self.error_data[c].dtype, np.number)]
        
        if not feature_cols:
            return {'error': 'No numeric features for clustering'}
        
        X = self.error_data[feature_cols].fillna(0)
        X_scaled = self.scaler.fit_transform(X)
        
        # Cluster
        if method == 'kmeans':
            clusterer = KMeans(n_clusters=n_clusters, random_state=42, n_init=10)
            labels = clusterer.fit_predict(X_scaled)
        else:
            clusterer = DBSCAN(eps=0.5, min_samples=5)
            labels = clusterer.fit_predict(X_scaled)
        
        self.error_data['cluster'] = labels
        
        # Analyze each cluster
        self.clusters = {}
        
        for cluster_id in np.unique(labels):
            if cluster_id == -1:  # DBSCAN noise
                continue
            
            cluster_mask = labels == cluster_id
            cluster_data = self.error_data[cluster_mask]
            
            # Cluster statistics
            cluster_stats = {
                'size': int(cluster_mask.sum()),
                'percentage': float(cluster_mask.sum() / len(labels) * 100),
                'error_type_distribution': cluster_data['error_type'].value_counts().to_dict()
            }
            
            # Feature characteristics
            feature_means = {}
            for col in feature_cols:
                cluster_mean = cluster_data[col].mean()
                overall_mean = self.error_data[col].mean()
                overall_std = self.error_data[col].std()
                
                if overall_std > 0:
                    z_score = (cluster_mean - overall_mean) / overall_std
                else:
                    z_score = 0
                
                if abs(z_score) > 0.5:  # Notable difference
                    feature_means[col] = {
                        'cluster_mean': float(cluster_mean),
                        'overall_mean': float(overall_mean),
                        'z_score': float(z_score),
                        'direction': 'high' if z_score > 0 else 'low'
                    }
            
            # Get top distinguishing features
            sorted_features = sorted(
                feature_means.items(),
                key=lambda x: abs(x[1]['z_score']),
                reverse=True
            )[:5]
            
            cluster_stats['distinguishing_features'] = dict(sorted_features)
            
            # Generate description
            if sorted_features:
                desc_parts = []
                for feat, stats in sorted_features[:3]:
                    desc_parts.append(f"{stats['direction']} {feat}")
                cluster_stats['description'] = ', '.join(desc_parts)
            else:
                cluster_stats['description'] = 'No distinguishing features'
            
            self.clusters[int(cluster_id)] = cluster_stats
        
        return {
            'n_clusters': len(self.clusters),
            'clusters': self.clusters,
            'noise_points': int((labels == -1).sum()) if method == 'dbscan' else 0
        }
    
    def identify_high_risk_conditions(
        self,
        error_threshold: float = 0.4
    ) -> List[Dict]:
        """
        Identify specific conditions where model errors are high.
        
        Args:
            error_threshold: Error rate threshold to flag as high risk
            
        Returns:
            List of high-risk condition definitions
        """
        if self.error_data is None:
            return []
        
        self.high_risk_conditions = []
        
        feature_cols = [c for c in self.error_data.columns 
                       if c not in ['prediction', 'actual', 'error_type', 'cluster']
                       and np.issubdtype(self.error_data[c].dtype, np.number)]
        
        # Analyze pairs of conditions
        for col in feature_cols[:10]:  # Limit for performance
            try:
                # Check high/low values separately
                median = self.error_data[col].median()
                
                high_mask = self.error_data[col] > self.error_data[col].quantile(0.75)
                low_mask = self.error_data[col] < self.error_data[col].quantile(0.25)
                
                # Note: In error_data, ALL rows are errors, so we can't compute error rate
                # Instead, we identify which feature ranges have more errors (larger clusters)
                
                for mask, condition_name in [(high_mask, 'high'), (low_mask, 'low')]:
                    if mask.sum() > 10:
                        # Check if this condition appears more in errors than expected
                        pct_in_errors = mask.mean()
                        
                        self.high_risk_conditions.append({
                            'feature': col,
                            'condition': condition_name,
                            'threshold': float(self.error_data[col].quantile(0.75 if condition_name == 'high' else 0.25)),
                            'error_concentration': float(pct_in_errors),
                            'sample_size': int(mask.sum()),
                            'description': f"Errors concentrated when {col} is {condition_name}"
                        })
            except Exception as e:
                logger.debug(f"Could not analyze {col}: {e}")
        
        # Sort by error concentration
        self.high_risk_conditions.sort(
            key=lambda x: x['error_concentration'],
            reverse=True
        )
        
        return self.high_risk_conditions[:10]
    
    def get_error_heatmap_data(
        self,
        feature1: str,
        feature2: str,
        n_bins: int = 5
    ) -> Dict[str, Any]:
        """
        Generate heatmap data showing error rate by two feature dimensions.
        """
        if self.error_data is None:
            return {'error': 'No error data available'}
        
        if feature1 not in self.error_data.columns or feature2 not in self.error_data.columns:
            return {'error': 'Features not found in data'}
        
        # Create bins
        try:
            bins1 = pd.qcut(self.error_data[feature1], q=n_bins, labels=False, duplicates='drop')
            bins2 = pd.qcut(self.error_data[feature2], q=n_bins, labels=False, duplicates='drop')
        except Exception:
            bins1 = pd.cut(self.error_data[feature1], bins=n_bins, labels=False)
            bins2 = pd.cut(self.error_data[feature2], bins=n_bins, labels=False)
        
        # Count errors in each cell
        heatmap = np.zeros((n_bins, n_bins))
        
        for i in range(n_bins):
            for j in range(n_bins):
                mask = (bins1 == i) & (bins2 == j)
                heatmap[i, j] = mask.sum()
        
        # Get bin edges for labels
        edges1 = pd.qcut(self.error_data[feature1], q=n_bins, retbins=True, duplicates='drop')[1]
        edges2 = pd.qcut(self.error_data[feature2], q=n_bins, retbins=True, duplicates='drop')[1]
        
        return {
            'feature1': feature1,
            'feature2': feature2,
            'heatmap': heatmap.tolist(),
            'feature1_bins': edges1.tolist(),
            'feature2_bins': edges2.tolist(),
            'total_errors': int(len(self.error_data))
        }
    
    def get_error_distribution_2d(
        self,
        n_components: int = 2
    ) -> Dict[str, Any]:
        """
        Project errors into 2D space for visualization.
        """
        if self.error_data is None or len(self.error_data) < 10:
            return {'error': 'Insufficient error data'}
        
        # Select numeric features
        feature_cols = [c for c in self.error_data.columns 
                       if c not in ['prediction', 'actual', 'error_type', 'cluster']
                       and np.issubdtype(self.error_data[c].dtype, np.number)]
        
        X = self.error_data[feature_cols].fillna(0)
        X_scaled = self.scaler.fit_transform(X)
        
        # PCA reduction
        pca = PCA(n_components=n_components)
        X_reduced = pca.fit_transform(X_scaled)
        
        return {
            'x': X_reduced[:, 0].tolist(),
            'y': X_reduced[:, 1].tolist(),
            'error_type': self.error_data['error_type'].tolist(),
            'cluster': self.error_data['cluster'].tolist() if 'cluster' in self.error_data.columns else None,
            'explained_variance': pca.explained_variance_ratio_.tolist()
        }
    
    def get_risk_flags(
        self,
        current_features: Dict[str, float]
    ) -> List[Dict]:
        """
        Check if current conditions match any high-risk patterns.
        
        Args:
            current_features: Current feature values
            
        Returns:
            List of active risk flags
        """
        active_flags = []
        
        for condition in self.high_risk_conditions:
            feat = condition['feature']
            if feat not in current_features:
                continue
            
            value = current_features[feat]
            threshold = condition['threshold']
            
            is_triggered = (
                (condition['condition'] == 'high' and value > threshold) or
                (condition['condition'] == 'low' and value < threshold)
            )
            
            if is_triggered:
                active_flags.append({
                    'feature': feat,
                    'condition': condition['condition'],
                    'current_value': value,
                    'threshold': threshold,
                    'error_concentration': condition['error_concentration'],
                    'description': condition['description'],
                    'severity': 'HIGH' if condition['error_concentration'] > 0.3 else 'MEDIUM'
                })
        
        return active_flags
    
    def get_failure_summary(self) -> Dict[str, Any]:
        """Get summary of failure analysis"""
        if self.error_data is None:
            return {'status': 'NO_DATA'}
        
        return {
            'total_errors_analyzed': len(self.error_data),
            'error_type_breakdown': self.error_data['error_type'].value_counts().to_dict(),
            'clusters_identified': len(self.clusters),
            'high_risk_conditions': len(self.high_risk_conditions),
            'top_risk_conditions': self.high_risk_conditions[:3],
            'cluster_summary': {
                k: {'size': v['size'], 'description': v['description']}
                for k, v in list(self.clusters.items())[:5]
            }
        }


# =============================================================================
# CONVENIENCE FUNCTIONS
# =============================================================================

def analyze_model_errors(
    predictions: pd.Series,
    actuals: pd.Series,
    features: pd.DataFrame,
    n_clusters: int = 5
) -> Tuple[ErrorAnalyzer, Dict]:
    """Convenience function for full error analysis"""
    analyzer = ErrorAnalyzer()
    
    analysis = analyzer.analyze_errors(predictions, actuals, features)
    clusters = analyzer.cluster_errors(n_clusters)
    high_risk = analyzer.identify_high_risk_conditions()
    
    return analyzer, {
        'error_analysis': analysis,
        'clusters': clusters,
        'high_risk_conditions': high_risk,
        'summary': analyzer.get_failure_summary()
    }
