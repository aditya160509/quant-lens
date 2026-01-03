"""
Labs → ML → Monitoring
=======================
Model Drift & Decay Monitor

Responsibilities:
- Performance decay detection
- Feature drift detection
- Prediction stability monitoring
- Trigger warnings when models stop working
"""

import pandas as pd
import numpy as np
from scipy import stats
from typing import Dict, List, Any, Optional, Tuple
from datetime import datetime, timedelta
import logging
from collections import deque

logger = logging.getLogger(__name__)


class DriftMonitor:
    """
    Model Drift & Decay Monitor
    
    Tracks model performance over time and detects
    when models need retraining due to drift or decay.
    """
    
    def __init__(self, alert_threshold: float = 0.10):
        """
        Args:
            alert_threshold: Drop in accuracy that triggers alert (0.10 = 10%)
        """
        self.alert_threshold = alert_threshold
        self.prediction_history: deque = deque(maxlen=10000)
        self.feature_baselines: Dict[str, Dict] = {}
        self.performance_history: List[Dict] = []
        self.alerts: List[Dict] = []
        self.baseline_accuracy: float = None
        
    def record_prediction(
        self,
        prediction: float,
        features: Dict[str, float],
        timestamp: datetime = None
    ):
        """Record a prediction for monitoring"""
        self.prediction_history.append({
            'prediction': prediction,
            'features': features,
            'timestamp': timestamp or datetime.now(),
            'actual': None  # To be filled in later
        })
    
    def record_outcome(
        self,
        prediction_id: int,
        actual: int
    ):
        """Record actual outcome for a prediction"""
        if prediction_id < len(self.prediction_history):
            self.prediction_history[prediction_id]['actual'] = actual
    
    def set_feature_baselines(
        self,
        X_train: pd.DataFrame
    ):
        """Set baseline distributions from training data"""
        for col in X_train.columns:
            series = X_train[col].dropna()
            if len(series) > 10:
                self.feature_baselines[col] = {
                    'mean': float(series.mean()),
                    'std': float(series.std()),
                    'median': float(series.median()),
                    'q25': float(series.quantile(0.25)),
                    'q75': float(series.quantile(0.75)),
                    'min': float(series.min()),
                    'max': float(series.max()),
                    'reference_distribution': series.values.tolist()[:1000]  # Store sample
                }
    
    def compute_rolling_accuracy(
        self,
        window: int = 100
    ) -> Dict[str, Any]:
        """
        Compute rolling accuracy over predictions with known outcomes.
        """
        # Filter predictions with outcomes
        completed = [
            p for p in self.prediction_history 
            if p['actual'] is not None
        ]
        
        if len(completed) < window:
            return {
                'error': f'Need at least {window} predictions with outcomes',
                'current_count': len(completed)
            }
        
        # Compute rolling accuracy
        timestamps = []
        accuracies = []
        
        for i in range(window, len(completed) + 1):
            batch = completed[i-window:i]
            correct = sum(
                1 for p in batch 
                if (p['prediction'] > 0.5) == p['actual']
            )
            accuracy = correct / window
            
            timestamps.append(batch[-1]['timestamp'].isoformat() if batch[-1]['timestamp'] else i)
            accuracies.append(accuracy)
        
        # Compute current vs baseline
        current_accuracy = accuracies[-1] if accuracies else None
        
        if self.baseline_accuracy is None and len(accuracies) > 0:
            self.baseline_accuracy = accuracies[0]
        
        accuracy_change = None
        if self.baseline_accuracy and current_accuracy:
            accuracy_change = current_accuracy - self.baseline_accuracy
        
        return {
            'timestamps': timestamps,
            'accuracies': accuracies,
            'current_accuracy': current_accuracy,
            'baseline_accuracy': self.baseline_accuracy,
            'accuracy_change': accuracy_change,
            'window_size': window,
            'is_declining': accuracy_change and accuracy_change < -self.alert_threshold
        }
    
    def compute_feature_drift(
        self,
        X_current: pd.DataFrame
    ) -> Dict[str, Any]:
        """
        Detect drift in feature distributions using statistical tests.
        
        Uses:
        - Population Stability Index (PSI)
        - Kolmogorov-Smirnov test
        """
        if not self.feature_baselines:
            return {'error': 'No baselines set. Call set_feature_baselines() first.'}
        
        drift_results = {}
        
        for col in X_current.columns:
            if col not in self.feature_baselines:
                continue
            
            baseline = self.feature_baselines[col]
            current = X_current[col].dropna()
            
            if len(current) < 10:
                continue
            
            # Compute PSI
            psi = self._compute_psi(
                baseline['reference_distribution'],
                current.values.tolist()
            )
            
            # Compute KS statistic
            ks_stat, ks_pvalue = stats.ks_2samp(
                baseline['reference_distribution'],
                current.values
            )
            
            # Mean/Std shift
            mean_shift = (current.mean() - baseline['mean']) / (baseline['std'] + 1e-6)
            std_ratio = current.std() / (baseline['std'] + 1e-6)
            
            # Determine drift severity
            if psi > 0.25 or ks_pvalue < 0.001:
                severity = 'HIGH'
            elif psi > 0.1 or ks_pvalue < 0.05:
                severity = 'MEDIUM'
            else:
                severity = 'LOW'
            
            drift_results[col] = {
                'psi': float(psi),
                'ks_statistic': float(ks_stat),
                'ks_pvalue': float(ks_pvalue),
                'mean_shift': float(mean_shift),
                'std_ratio': float(std_ratio),
                'severity': severity,
                'current_mean': float(current.mean()),
                'baseline_mean': baseline['mean'],
                'current_std': float(current.std()),
                'baseline_std': baseline['std']
            }
        
        # Overall drift score
        psi_values = [r['psi'] for r in drift_results.values()]
        overall_drift = np.mean(psi_values) if psi_values else 0
        
        high_drift_features = [
            k for k, v in drift_results.items() 
            if v['severity'] == 'HIGH'
        ]
        
        return {
            'features': drift_results,
            'overall_drift_score': float(overall_drift),
            'high_drift_features': high_drift_features,
            'has_significant_drift': len(high_drift_features) > 0
        }
    
    def _compute_psi(
        self,
        expected: List[float],
        actual: List[float],
        n_bins: int = 10
    ) -> float:
        """
        Compute Population Stability Index.
        
        PSI < 0.1: No significant change
        0.1 <= PSI < 0.25: Moderate change
        PSI >= 0.25: Significant change
        """
        expected = np.array(expected)
        actual = np.array(actual)
        
        # Create bins based on expected distribution
        bins = np.percentile(expected, np.linspace(0, 100, n_bins + 1))
        bins[0] = -np.inf
        bins[-1] = np.inf
        
        # Count in each bin
        expected_counts = np.histogram(expected, bins)[0]
        actual_counts = np.histogram(actual, bins)[0]
        
        # Convert to percentages
        expected_pct = expected_counts / len(expected)
        actual_pct = actual_counts / len(actual)
        
        # Avoid division by zero
        expected_pct = np.maximum(expected_pct, 0.001)
        actual_pct = np.maximum(actual_pct, 0.001)
        
        # PSI formula
        psi = np.sum((actual_pct - expected_pct) * np.log(actual_pct / expected_pct))
        
        return psi
    
    def detect_concept_drift(
        self,
        X: pd.DataFrame,
        y: pd.Series,
        predictions: pd.Series,
        window: int = 100
    ) -> Dict[str, Any]:
        """
        Detect concept drift - when relationship between features and target changes.
        
        Uses error rate analysis across different feature value ranges.
        """
        results = {}
        
        # Compute errors
        y_pred = (predictions > 0.5).astype(int)
        errors = (y_pred != y).astype(int)
        
        for col in X.columns:
            if len(X[col].dropna()) < window:
                continue
            
            # Split into quantiles
            quantiles = pd.qcut(X[col], q=4, labels=['Q1', 'Q2', 'Q3', 'Q4'], duplicates='drop')
            
            # Error rate by quantile
            error_by_quantile = {}
            for q in quantiles.unique():
                mask = quantiles == q
                if mask.sum() > 0:
                    error_by_quantile[q] = float(errors[mask].mean())
            
            # Check for non-uniform error distribution
            if len(error_by_quantile) >= 2:
                error_rates = list(error_by_quantile.values())
                error_variance = np.var(error_rates)
                max_error_diff = max(error_rates) - min(error_rates)
                
                results[col] = {
                    'error_by_quantile': error_by_quantile,
                    'error_variance': float(error_variance),
                    'max_error_diff': float(max_error_diff),
                    'has_concept_drift': max_error_diff > 0.2  # 20% difference in error rates
                }
        
        # Features with concept drift
        drifting_features = [
            k for k, v in results.items() 
            if v.get('has_concept_drift', False)
        ]
        
        return {
            'features': results,
            'drifting_features': drifting_features,
            'has_concept_drift': len(drifting_features) > 0
        }
    
    def generate_alerts(
        self,
        accuracy_result: Dict = None,
        drift_result: Dict = None,
        concept_result: Dict = None
    ) -> List[Dict]:
        """Generate alerts based on monitoring results"""
        new_alerts = []
        timestamp = datetime.now()
        
        # Accuracy decay alert
        if accuracy_result and accuracy_result.get('is_declining'):
            new_alerts.append({
                'type': 'PERFORMANCE_DECAY',
                'severity': 'HIGH',
                'message': f"Model accuracy dropped from {accuracy_result['baseline_accuracy']:.1%} to {accuracy_result['current_accuracy']:.1%}",
                'timestamp': timestamp.isoformat(),
                'details': accuracy_result
            })
        
        # Feature drift alert
        if drift_result and drift_result.get('has_significant_drift'):
            new_alerts.append({
                'type': 'FEATURE_DRIFT',
                'severity': 'MEDIUM',
                'message': f"Significant drift detected in {len(drift_result['high_drift_features'])} features: {', '.join(drift_result['high_drift_features'][:5])}",
                'timestamp': timestamp.isoformat(),
                'details': {'features': drift_result['high_drift_features']}
            })
        
        # Concept drift alert
        if concept_result and concept_result.get('has_concept_drift'):
            new_alerts.append({
                'type': 'CONCEPT_DRIFT',
                'severity': 'HIGH',
                'message': f"Concept drift detected in {len(concept_result['drifting_features'])} features",
                'timestamp': timestamp.isoformat(),
                'details': {'features': concept_result['drifting_features']}
            })
        
        self.alerts.extend(new_alerts)
        return new_alerts
    
    def get_drift_heatmap_data(
        self,
        X_history: pd.DataFrame,
        date_column: str = None,
        n_periods: int = 10
    ) -> Dict[str, Any]:
        """
        Generate data for drift heatmap visualization.
        
        Shows drift score for each feature over time periods.
        """
        if not self.feature_baselines:
            return {'error': 'No baselines set'}
        
        # Split data into time periods
        if date_column and date_column in X_history.columns:
            X_history = X_history.sort_values(date_column)
            period_size = len(X_history) // n_periods
        else:
            period_size = len(X_history) // n_periods
        
        features = [c for c in X_history.columns if c in self.feature_baselines and c != date_column]
        
        heatmap_data = []
        period_labels = []
        
        for i in range(n_periods):
            start_idx = i * period_size
            end_idx = (i + 1) * period_size if i < n_periods - 1 else len(X_history)
            period_data = X_history.iloc[start_idx:end_idx]
            
            period_labels.append(f"Period {i+1}")
            
            period_drift = []
            for feat in features:
                if feat in self.feature_baselines:
                    psi = self._compute_psi(
                        self.feature_baselines[feat]['reference_distribution'],
                        period_data[feat].dropna().values.tolist()
                    )
                    period_drift.append(float(psi))
                else:
                    period_drift.append(0)
            
            heatmap_data.append(period_drift)
        
        return {
            'features': features,
            'periods': period_labels,
            'drift_scores': heatmap_data,
            'threshold_moderate': 0.1,
            'threshold_high': 0.25
        }
    
    def get_alert_log(
        self,
        limit: int = 50
    ) -> List[Dict]:
        """Get recent alerts"""
        return self.alerts[-limit:][::-1]  # Most recent first
    
    def get_monitoring_summary(self) -> Dict[str, Any]:
        """Get overall monitoring summary"""
        completed_predictions = [
            p for p in self.prediction_history 
            if p['actual'] is not None
        ]
        
        if not completed_predictions:
            return {
                'status': 'INSUFFICIENT_DATA',
                'message': 'No predictions with recorded outcomes yet'
            }
        
        # Recent accuracy
        recent = completed_predictions[-100:] if len(completed_predictions) > 100 else completed_predictions
        recent_accuracy = sum(
            1 for p in recent 
            if (p['prediction'] > 0.5) == p['actual']
        ) / len(recent)
        
        # Trend
        if len(completed_predictions) > 200:
            older = completed_predictions[-200:-100]
            older_accuracy = sum(
                1 for p in older 
                if (p['prediction'] > 0.5) == p['actual']
            ) / len(older)
            trend = recent_accuracy - older_accuracy
        else:
            trend = 0
        
        # Status
        if recent_accuracy > 0.65:
            status = 'HEALTHY'
        elif recent_accuracy > 0.55:
            status = 'MODERATE'
        else:
            status = 'POOR'
        
        if trend < -0.05:
            status = 'DECLINING'
        
        return {
            'status': status,
            'recent_accuracy': float(recent_accuracy),
            'accuracy_trend': float(trend),
            'total_predictions': len(self.prediction_history),
            'predictions_with_outcomes': len(completed_predictions),
            'recent_alerts': len([a for a in self.alerts if a.get('severity') == 'HIGH']),
            'features_monitored': len(self.feature_baselines)
        }


# =============================================================================
# CONVENIENCE FUNCTIONS
# =============================================================================

def create_monitor(
    X_train: pd.DataFrame,
    alert_threshold: float = 0.10
) -> DriftMonitor:
    """Create and initialize a drift monitor"""
    monitor = DriftMonitor(alert_threshold)
    monitor.set_feature_baselines(X_train)
    return monitor


def check_for_drift(
    monitor: DriftMonitor,
    X_current: pd.DataFrame
) -> Dict[str, Any]:
    """Quick drift check"""
    return monitor.compute_feature_drift(X_current)
