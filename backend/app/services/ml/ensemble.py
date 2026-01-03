"""
Labs → ML → Ensemble
====================
Model Consensus & Disagreement Engine

Responsibilities:
- Combine multiple models for robust predictions
- Measure model disagreement
- Weight models by reliability
- Prevent single-model overconfidence
"""

import pandas as pd
import numpy as np
from typing import Dict, List, Any, Optional, Tuple
from datetime import datetime
import logging

from .supervised import SignalPredictor, CLASSIFICATION_MODELS

logger = logging.getLogger(__name__)


class EnsembleEngine:
    """
    Model Consensus & Disagreement Engine
    
    Combines predictions from multiple models to produce robust,
    ensemble probability estimates with disagreement metrics.
    """
    
    def __init__(self):
        self.predictor = SignalPredictor(model_type='classification')
        self.model_weights: Dict[str, float] = {}
        self.historical_accuracy: Dict[str, List[float]] = {}
        
    def fit(
        self,
        X: pd.DataFrame,
        y: pd.Series,
        models: List[str] = None
    ) -> Dict[str, Any]:
        """
        Train ensemble of models.
        
        Args:
            X: Feature matrix
            y: Labels
            models: List of model names to include in ensemble
            
        Returns:
            Training results
        """
        # Default to all available models
        if models is None:
            models = list(CLASSIFICATION_MODELS.keys())
        
        # Train models
        results = self.predictor.fit(X, y, models_to_train=models)
        
        # Initialize equal weights
        trained_models = [m for m in results['models'] if results['models'][m].get('trained', False)]
        self.model_weights = {m: 1.0 / len(trained_models) for m in trained_models}
        
        # Update weights based on CV scores
        self._update_weights_from_cv(results)
        
        return {
            'training_results': results,
            'model_weights': self.model_weights
        }
    
    def _update_weights_from_cv(self, training_results: Dict):
        """Update model weights based on cross-validation performance"""
        cv_means = {}
        
        for model_name, stats in training_results.get('models', {}).items():
            if stats.get('trained', False) and 'cv_mean' in stats:
                cv_means[model_name] = stats['cv_mean']
        
        if not cv_means:
            return
        
        # Convert accuracy to weights (softmax-style)
        total = sum(cv_means.values())
        if total > 0:
            self.model_weights = {k: v / total for k, v in cv_means.items()}
    
    def predict(
        self,
        X: pd.DataFrame,
        weighting: str = 'accuracy'
    ) -> Dict[str, Any]:
        """
        Generate ensemble predictions.
        
        Args:
            X: Feature matrix
            weighting: 'equal', 'accuracy', or 'inverse_variance'
            
        Returns:
            Ensemble predictions with consensus and disagreement
        """
        # Get individual model predictions
        result = self.predictor.predict(X, return_all_models=True)
        model_preds = result['model_predictions']
        
        if not model_preds:
            raise ValueError("No model predictions available")
        
        # Calculate weights for each method
        if weighting == 'equal':
            weights = {m: 1.0 / len(model_preds) for m in model_preds}
        elif weighting == 'accuracy':
            weights = self.model_weights
        elif weighting == 'inverse_variance':
            # Weight inversely by prediction variance
            variances = {}
            for model_name, preds in model_preds.items():
                variances[model_name] = np.var(preds) + 1e-6
            total_inv = sum(1/v for v in variances.values())
            weights = {m: (1/v) / total_inv for m, v in variances.items()}
        else:
            weights = self.model_weights
        
        # Compute weighted consensus
        n_samples = len(list(model_preds.values())[0])
        consensus = np.zeros(n_samples)
        
        for model_name, preds in model_preds.items():
            weight = weights.get(model_name, 1.0 / len(model_preds))
            consensus += weight * np.array(preds)
        
        # Compute disagreement metrics
        all_preds = np.array(list(model_preds.values()))
        
        # Standard deviation across models
        disagreement_std = np.std(all_preds, axis=0)
        
        # Range (max - min) across models
        disagreement_range = np.max(all_preds, axis=0) - np.min(all_preds, axis=0)
        
        # Entropy-based disagreement (for binary predictions)
        mean_pred = np.mean(all_preds, axis=0)
        entropy = -mean_pred * np.log2(mean_pred + 1e-10) - (1 - mean_pred) * np.log2(1 - mean_pred + 1e-10)
        
        # Compute agreement score (0-100)
        agreement_score = (1 - disagreement_std / 0.5) * 100  # Max disagreement ~0.5 for binary
        agreement_score = np.clip(agreement_score, 0, 100)
        
        # Determine confidence tiers
        confidence_tiers = []
        for i in range(n_samples):
            if agreement_score[i] >= 70 and (consensus[i] > 0.65 or consensus[i] < 0.35):
                tier = 'HIGH'
            elif agreement_score[i] >= 50:
                tier = 'MEDIUM'
            else:
                tier = 'LOW'
            confidence_tiers.append(tier)
        
        return {
            'consensus_probability': consensus.tolist(),
            'confidence_tiers': confidence_tiers,
            'agreement_score': agreement_score.tolist(),
            'disagreement': {
                'std': disagreement_std.tolist(),
                'range': disagreement_range.tolist(),
                'entropy': entropy.tolist()
            },
            'model_predictions': {k: v if isinstance(v, list) else v.tolist() 
                                  for k, v in model_preds.items()},
            'model_weights': weights
        }
    
    def get_model_agreement_matrix(
        self,
        X: pd.DataFrame
    ) -> Dict[str, Any]:
        """
        Generate model agreement matrix showing how often models agree.
        
        Returns correlation matrix of model predictions.
        """
        result = self.predictor.predict(X, return_all_models=True)
        model_preds = result['model_predictions']
        
        if len(model_preds) < 2:
            return {'error': 'Need at least 2 models for agreement matrix'}
        
        # Create DataFrame of predictions
        pred_df = pd.DataFrame(model_preds)
        
        # Correlation matrix
        corr_matrix = pred_df.corr()
        
        # Agreement on binary decisions (both predict same class)
        binary_preds = (pred_df > 0.5).astype(int)
        agreement_matrix = {}
        
        models = list(model_preds.keys())
        for i, m1 in enumerate(models):
            agreement_matrix[m1] = {}
            for m2 in models:
                agreement = (binary_preds[m1] == binary_preds[m2]).mean()
                agreement_matrix[m1][m2] = float(agreement)
        
        return {
            'models': models,
            'correlation_matrix': corr_matrix.values.tolist(),
            'agreement_matrix': agreement_matrix,
            'avg_agreement': float(np.mean([
                agreement_matrix[m1][m2] 
                for i, m1 in enumerate(models) 
                for m2 in models[i+1:]
            ]))
        }
    
    def update_weights_from_actuals(
        self,
        predictions: Dict[str, List[float]],
        actuals: List[int]
    ):
        """
        Update model weights based on actual outcomes.
        
        Should be called periodically with recent predictions and outcomes.
        """
        actuals = np.array(actuals)
        
        for model_name, preds in predictions.items():
            preds = np.array(preds)
            binary_preds = (preds > 0.5).astype(int)
            accuracy = np.mean(binary_preds == actuals)
            
            if model_name not in self.historical_accuracy:
                self.historical_accuracy[model_name] = []
            
            self.historical_accuracy[model_name].append(accuracy)
            
            # Keep only last 30 observations
            if len(self.historical_accuracy[model_name]) > 30:
                self.historical_accuracy[model_name] = self.historical_accuracy[model_name][-30:]
        
        # Update weights based on recent accuracy
        recent_accuracy = {
            m: np.mean(accs) 
            for m, accs in self.historical_accuracy.items()
        }
        
        total = sum(recent_accuracy.values())
        if total > 0:
            self.model_weights = {k: v / total for k, v in recent_accuracy.items()}
    
    def get_historical_accuracy(self) -> Dict[str, Any]:
        """Get historical accuracy trends for each model"""
        result = {}
        
        for model_name, accuracies in self.historical_accuracy.items():
            if accuracies:
                result[model_name] = {
                    'accuracy_history': accuracies,
                    'current_accuracy': float(np.mean(accuracies[-10:])) if len(accuracies) >= 10 else float(np.mean(accuracies)),
                    'trend': float(np.mean(accuracies[-5:])) - float(np.mean(accuracies[:5])) if len(accuracies) >= 10 else 0,
                    'weight': self.model_weights.get(model_name, 0)
                }
        
        return result
    
    def get_prediction_breakdown(
        self,
        features: Dict[str, float]
    ) -> Dict[str, Any]:
        """
        Get detailed breakdown of ensemble prediction for a single signal.
        """
        X = pd.DataFrame([features])
        result = self.predict(X)
        
        return {
            'consensus_probability': result['consensus_probability'][0],
            'confidence_tier': result['confidence_tiers'][0],
            'agreement_score': result['agreement_score'][0],
            'model_predictions': {
                k: v[0] for k, v in result['model_predictions'].items()
            },
            'model_weights': result['model_weights'],
            'disagreement': {
                'std': result['disagreement']['std'][0],
                'range': result['disagreement']['range'][0]
            }
        }


# =============================================================================
# CONVENIENCE FUNCTIONS
# =============================================================================

def create_ensemble(
    X: pd.DataFrame,
    y: pd.Series,
    models: List[str] = None
) -> EnsembleEngine:
    """Convenience function to create and train ensemble"""
    engine = EnsembleEngine()
    engine.fit(X, y, models)
    return engine


def get_model_consensus(
    ensemble: EnsembleEngine,
    X: pd.DataFrame
) -> Tuple[np.ndarray, np.ndarray, List[str]]:
    """Get consensus predictions with agreement scores"""
    result = ensemble.predict(X)
    return (
        np.array(result['consensus_probability']),
        np.array(result['agreement_score']),
        result['confidence_tiers']
    )
