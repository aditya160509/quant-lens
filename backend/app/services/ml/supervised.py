"""
Labs → ML → Supervised
======================
Signal Success Probability Engine - The Prediction Engine

Responsibilities:
- Classification models for signal success prediction
- Regression models for return prediction
- Probability estimation with confidence tiers
"""

import pandas as pd
import numpy as np
from scipy import stats
from typing import Dict, List, Any, Optional, Tuple, Literal, Union
from datetime import datetime
import logging
import pickle
import json
from pathlib import Path

# ML Libraries
from sklearn.linear_model import LogisticRegression, Ridge, Lasso, ElasticNet
from sklearn.ensemble import RandomForestClassifier, RandomForestRegressor
from sklearn.ensemble import GradientBoostingClassifier, GradientBoostingRegressor
from sklearn.model_selection import TimeSeriesSplit, cross_val_score
from sklearn.preprocessing import StandardScaler
from sklearn.metrics import (
    accuracy_score, precision_score, recall_score, f1_score,
    roc_auc_score, precision_recall_curve, roc_curve,
    mean_squared_error, mean_absolute_error, r2_score
)

# XGBoost and LightGBM
try:
    import xgboost as xgb
    XGBOOST_AVAILABLE = True
except ImportError:
    XGBOOST_AVAILABLE = False
    
try:
    import lightgbm as lgb
    LIGHTGBM_AVAILABLE = True
except ImportError:
    LIGHTGBM_AVAILABLE = False

logger = logging.getLogger(__name__)

# =============================================================================
# MODEL CONFIGURATIONS
# =============================================================================

CLASSIFICATION_MODELS = {
    'logistic': {
        'class': LogisticRegression,
        'params': {'max_iter': 1000, 'random_state': 42, 'class_weight': 'balanced'},
        'name': 'Logistic Regression'
    },
    'random_forest': {
        'class': RandomForestClassifier,
        'params': {'n_estimators': 200, 'max_depth': 10, 'random_state': 42, 'n_jobs': -1},
        'name': 'Random Forest'
    },
    'gradient_boosting': {
        'class': GradientBoostingClassifier,
        'params': {'n_estimators': 100, 'max_depth': 5, 'random_state': 42},
        'name': 'Gradient Boosting'
    }
}

if XGBOOST_AVAILABLE:
    CLASSIFICATION_MODELS['xgboost'] = {
        'class': xgb.XGBClassifier,
        'params': {
            'n_estimators': 200, 
            'max_depth': 6, 
            'learning_rate': 0.05,
            'random_state': 42,
            'use_label_encoder': False,
            'eval_metric': 'logloss'
        },
        'name': 'XGBoost'
    }

if LIGHTGBM_AVAILABLE:
    CLASSIFICATION_MODELS['lightgbm'] = {
        'class': lgb.LGBMClassifier,
        'params': {
            'n_estimators': 200,
            'max_depth': 6,
            'learning_rate': 0.05,
            'random_state': 42,
            'verbose': -1
        },
        'name': 'LightGBM'
    }

REGRESSION_MODELS = {
    'ridge': {
        'class': Ridge,
        'params': {'alpha': 1.0, 'random_state': 42},
        'name': 'Ridge Regression'
    },
    'lasso': {
        'class': Lasso,
        'params': {'alpha': 0.1, 'random_state': 42},
        'name': 'Lasso Regression'
    },
    'elastic_net': {
        'class': ElasticNet,
        'params': {'alpha': 0.1, 'l1_ratio': 0.5, 'random_state': 42},
        'name': 'Elastic Net'
    },
    'random_forest': {
        'class': RandomForestRegressor,
        'params': {'n_estimators': 200, 'max_depth': 10, 'random_state': 42, 'n_jobs': -1},
        'name': 'Random Forest Regressor'
    }
}


# =============================================================================
# SIGNAL PREDICTOR
# =============================================================================

class SignalPredictor:
    """
    Signal Success Probability Engine
    
    Trains classification/regression models and provides predictions
    with probability estimates and confidence tiers.
    """
    
    def __init__(self, model_type: Literal['classification', 'regression'] = 'classification'):
        self.model_type = model_type
        self.models: Dict[str, Any] = {}
        self.scaler = StandardScaler()
        self.feature_names: List[str] = []
        self.is_fitted = False
        self.training_stats: Dict[str, Any] = {}
        
    def fit(
        self,
        X: pd.DataFrame,
        y: pd.Series,
        models_to_train: List[str] = None,
        cv_splits: int = 5
    ) -> Dict[str, Any]:
        """
        Train models on the dataset.
        
        Args:
            X: Feature matrix
            y: Labels
            models_to_train: List of model names to train (None = all)
            cv_splits: Number of time-series CV splits
            
        Returns:
            Training results with cross-validation scores
        """
        # Clean data
        X_clean = X.replace([np.inf, -np.inf], np.nan).dropna()
        y_clean = y.loc[X_clean.index]
        
        if len(X_clean) < 40:
            raise ValueError(f"Insufficient data: {len(X_clean)} samples (need at least 40)")
        
        self.feature_names = list(X_clean.columns)
        
        # Scale features
        X_scaled = self.scaler.fit_transform(X_clean)
        X_scaled = pd.DataFrame(X_scaled, columns=self.feature_names, index=X_clean.index)
        
        # Select model configs
        if self.model_type == 'classification':
            model_configs = CLASSIFICATION_MODELS
        else:
            model_configs = REGRESSION_MODELS
        
        if models_to_train:
            model_configs = {k: v for k, v in model_configs.items() if k in models_to_train}
        
        # Time-series cross-validation
        tscv = TimeSeriesSplit(n_splits=cv_splits)
        
        results = {}
        
        for model_name, config in model_configs.items():
            try:
                logger.info(f"Training {config['name']}...")
                
                # Initialize model
                model = config['class'](**config['params'])
                
                # Cross-validation
                if self.model_type == 'classification':
                    cv_scores = cross_val_score(
                        model, X_scaled, y_clean, 
                        cv=tscv, scoring='accuracy'
                    )
                else:
                    cv_scores = cross_val_score(
                        model, X_scaled, y_clean,
                        cv=tscv, scoring='neg_mean_squared_error'
                    )
                    cv_scores = -cv_scores  # Convert to positive MSE
                
                # Fit on full data
                model.fit(X_scaled, y_clean)
                
                self.models[model_name] = model
                
                results[model_name] = {
                    'name': config['name'],
                    'cv_scores': cv_scores.tolist(),
                    'cv_mean': float(cv_scores.mean()),
                    'cv_std': float(cv_scores.std()),
                    'trained': True
                }
                
                # Feature importance (if available)
                if hasattr(model, 'feature_importances_'):
                    importance = dict(zip(
                        self.feature_names,
                        model.feature_importances_.tolist()
                    ))
                    results[model_name]['feature_importance'] = importance
                elif hasattr(model, 'coef_'):
                    coef = model.coef_
                    if coef.ndim > 1:
                        coef = coef[0]
                    importance = dict(zip(
                        self.feature_names,
                        np.abs(coef).tolist()
                    ))
                    results[model_name]['feature_importance'] = importance
                    
            except Exception as e:
                logger.error(f"Error training {model_name}: {e}")
                results[model_name] = {
                    'name': config['name'],
                    'error': str(e),
                    'trained': False
                }
        
        # Only set is_fitted if at least one model trained successfully
        successful_models = [name for name, result in results.items() if result.get('trained')]
        self.is_fitted = len(successful_models) > 0
        
        if not self.is_fitted:
            raise ValueError("No models trained successfully. Check data quality and model configurations.")
        
        self.training_stats = {
            'n_samples': len(X_clean),
            'n_features': len(self.feature_names),
            'models': results,
            'successful_models': successful_models,
            'failed_models': [name for name, result in results.items() if not result.get('trained')],
            'trained_at': datetime.now().isoformat()
        }
        
        return self.training_stats
    
    def predict(
        self,
        X: pd.DataFrame,
        return_all_models: bool = False
    ) -> Dict[str, Any]:
        """
        Generate predictions for new data.
        
        Returns:
            - probability: Consensus probability (classification) or predicted value (regression)
            - confidence_tier: HIGH, MEDIUM, or LOW
            - model_predictions: Individual model outputs
        """
        if not self.is_fitted:
            raise ValueError("Model not fitted. Call fit() first.")
        
        # Ensure feature alignment
        X_aligned = X.reindex(columns=self.feature_names, fill_value=0)
        X_clean = X_aligned.replace([np.inf, -np.inf], np.nan).fillna(0)
        
        # Scale
        X_scaled = self.scaler.transform(X_clean)
        
        predictions = {}
        
        for model_name, model in self.models.items():
            try:
                if self.model_type == 'classification':
                    if hasattr(model, 'predict_proba'):
                        proba = model.predict_proba(X_scaled)[:, 1]
                    else:
                        proba = model.predict(X_scaled).astype(float)
                    predictions[model_name] = proba
                else:
                    pred = model.predict(X_scaled)
                    predictions[model_name] = pred
            except Exception as e:
                logger.error(f"Error predicting with {model_name}: {e}")
        
        if not predictions:
            raise ValueError("No models produced predictions")
        
        # Compute consensus
        all_preds = np.array(list(predictions.values()))
        consensus = np.mean(all_preds, axis=0)
        
        # Compute disagreement (std across models)
        disagreement = np.std(all_preds, axis=0)
        
        # Determine confidence tier
        confidence_tiers = []
        for i in range(len(consensus)):
            if self.model_type == 'classification':
                # High confidence: probability far from 0.5 AND low disagreement
                prob_confidence = abs(consensus[i] - 0.5) * 2  # 0-1 scale
                disagree_penalty = min(disagreement[i] * 2, 0.5)  # Cap at 0.5
                confidence_score = prob_confidence - disagree_penalty
                
                if confidence_score > 0.5:
                    tier = 'HIGH'
                elif confidence_score > 0.2:
                    tier = 'MEDIUM'
                else:
                    tier = 'LOW'
            else:
                # For regression, use coefficient of variation
                cv = disagreement[i] / (abs(consensus[i]) + 1e-6)
                if cv < 0.1:
                    tier = 'HIGH'
                elif cv < 0.3:
                    tier = 'MEDIUM'
                else:
                    tier = 'LOW'
            
            confidence_tiers.append(tier)
        
        result = {
            'predictions': consensus.tolist(),
            'confidence_tiers': confidence_tiers,
            'disagreement': disagreement.tolist()
        }
        
        if return_all_models:
            result['model_predictions'] = {
                k: v.tolist() for k, v in predictions.items()
            }
        
        return result
    
    def predict_single(
        self,
        features: Dict[str, float]
    ) -> Dict[str, Any]:
        """Predict for a single signal"""
        X = pd.DataFrame([features])
        result = self.predict(X, return_all_models=True)
        
        return {
            'probability': result['predictions'][0],
            'confidence_tier': result['confidence_tiers'][0],
            'disagreement': result['disagreement'][0],
            'model_predictions': {
                k: v[0] for k, v in result['model_predictions'].items()
            }
        }
    
    def get_expected_return_distribution(
        self,
        probability: float,
        historical_returns: pd.Series = None,
        n_bins: int = 10
    ) -> Dict[str, Any]:
        """
        Estimate expected return distribution given success probability.
        
        Uses historical return distribution conditioned on predicted probability
        or theoretical model if historical data not provided.
        """
        if historical_returns is not None and len(historical_returns) > 50:
            # Use historical distribution
            returns = historical_returns.dropna()
            
            # Create probability-weighted return distribution
            # Higher probability = right-shifted distribution
            mean_return = returns.mean()
            std_return = returns.std()
            
            # Adjust mean based on probability
            adjusted_mean = mean_return + (probability - 0.5) * 2 * std_return
            
            # Generate distribution bins
            bins = np.linspace(
                adjusted_mean - 3 * std_return,
                adjusted_mean + 3 * std_return,
                n_bins + 1
            )
            
            # Create probability distribution (normal approximation)
            bin_centers = (bins[:-1] + bins[1:]) / 2
            probabilities = stats.norm.pdf(bin_centers, adjusted_mean, std_return)
            probabilities = probabilities / probabilities.sum()
            
        else:
            # Use theoretical model
            # Mean return proportional to probability
            mean_return = (probability - 0.5) * 0.10  # ±5% range
            std_return = 0.03  # 3% volatility
            
            bins = np.linspace(-0.10, 0.15, n_bins + 1)
            bin_centers = (bins[:-1] + bins[1:]) / 2
            probabilities = stats.norm.pdf(bin_centers, mean_return, std_return)
            probabilities = probabilities / probabilities.sum()
        
        return {
            'bins': bins.tolist(),
            'bin_centers': bin_centers.tolist(),
            'probabilities': probabilities.tolist(),
            'expected_return': float(np.sum(bin_centers * probabilities)),
            'std_return': float(std_return)
        }
    
    def evaluate(
        self,
        X: pd.DataFrame,
        y: pd.Series
    ) -> Dict[str, Any]:
        """Evaluate model performance on test data"""
        predictions = self.predict(X, return_all_models=True)
        
        results = {'models': {}}
        
        if self.model_type == 'classification':
            y_pred_proba = np.array(predictions['predictions'])
            y_pred = (y_pred_proba > 0.5).astype(int)
            
            results['consensus'] = {
                'accuracy': float(accuracy_score(y, y_pred)),
                'precision': float(precision_score(y, y_pred, zero_division=0)),
                'recall': float(recall_score(y, y_pred, zero_division=0)),
                'f1': float(f1_score(y, y_pred, zero_division=0)),
                'roc_auc': float(roc_auc_score(y, y_pred_proba)) if len(np.unique(y)) > 1 else 0.5
            }
            
            # Per-model metrics
            for model_name, preds in predictions['model_predictions'].items():
                preds = np.array(preds)
                y_pred_model = (preds > 0.5).astype(int)
                
                results['models'][model_name] = {
                    'accuracy': float(accuracy_score(y, y_pred_model)),
                    'precision': float(precision_score(y, y_pred_model, zero_division=0)),
                    'recall': float(recall_score(y, y_pred_model, zero_division=0)),
                    'f1': float(f1_score(y, y_pred_model, zero_division=0))
                }
            
            # ROC curve data
            fpr, tpr, thresholds = roc_curve(y, y_pred_proba)
            results['roc_curve'] = {
                'fpr': fpr.tolist(),
                'tpr': tpr.tolist(),
                'thresholds': thresholds.tolist()
            }
            
            # Precision-Recall curve
            precision, recall, pr_thresholds = precision_recall_curve(y, y_pred_proba)
            results['pr_curve'] = {
                'precision': precision.tolist(),
                'recall': recall.tolist(),
                'thresholds': pr_thresholds.tolist()
            }
            
        else:
            y_pred = np.array(predictions['predictions'])
            
            results['consensus'] = {
                'mse': float(mean_squared_error(y, y_pred)),
                'rmse': float(np.sqrt(mean_squared_error(y, y_pred))),
                'mae': float(mean_absolute_error(y, y_pred)),
                'r2': float(r2_score(y, y_pred))
            }
            
            for model_name, preds in predictions['model_predictions'].items():
                preds = np.array(preds)
                results['models'][model_name] = {
                    'mse': float(mean_squared_error(y, preds)),
                    'mae': float(mean_absolute_error(y, preds)),
                    'r2': float(r2_score(y, preds))
                }
        
        return results
    
    def get_feature_importance(self, model_name: str = None) -> Dict[str, float]:
        """Get feature importance from a specific model or averaged across models"""
        if not self.is_fitted:
            return {}
        
        if model_name:
            if model_name in self.models:
                model = self.models[model_name]
                if hasattr(model, 'feature_importances_'):
                    return dict(zip(self.feature_names, model.feature_importances_.tolist()))
                elif hasattr(model, 'coef_'):
                    coef = model.coef_[0] if model.coef_.ndim > 1 else model.coef_
                    return dict(zip(self.feature_names, np.abs(coef).tolist()))
            return {}
        
        # Average across all models
        all_importance = {}
        count = {}
        
        for name, model in self.models.items():
            if hasattr(model, 'feature_importances_'):
                for i, feat in enumerate(self.feature_names):
                    all_importance[feat] = all_importance.get(feat, 0) + model.feature_importances_[i]
                    count[feat] = count.get(feat, 0) + 1
            elif hasattr(model, 'coef_'):
                coef = model.coef_[0] if model.coef_.ndim > 1 else model.coef_
                for i, feat in enumerate(self.feature_names):
                    all_importance[feat] = all_importance.get(feat, 0) + abs(coef[i])
                    count[feat] = count.get(feat, 0) + 1
        
        # Average
        return {k: v / count[k] for k, v in all_importance.items() if count.get(k, 0) > 0}
    
    def save(self, path: str):
        """Save trained models to disk"""
        save_data = {
            'models': self.models,
            'scaler': self.scaler,
            'feature_names': self.feature_names,
            'model_type': self.model_type,
            'training_stats': self.training_stats,
            'is_fitted': self.is_fitted
        }
        
        with open(path, 'wb') as f:
            pickle.dump(save_data, f)
    
    def load(self, path: str):
        """Load trained models from disk"""
        with open(path, 'rb') as f:
            save_data = pickle.load(f)
        
        self.models = save_data['models']
        self.scaler = save_data['scaler']
        self.feature_names = save_data['feature_names']
        self.model_type = save_data['model_type']
        self.training_stats = save_data['training_stats']
        self.is_fitted = save_data['is_fitted']


# =============================================================================
# CONVENIENCE FUNCTIONS
# =============================================================================

def train_signal_classifier(
    X: pd.DataFrame,
    y: pd.Series,
    models: List[str] = None
) -> SignalPredictor:
    """Convenience function to train a signal classifier"""
    predictor = SignalPredictor(model_type='classification')
    predictor.fit(X, y, models_to_train=models)
    return predictor


def train_return_predictor(
    X: pd.DataFrame,
    y: pd.Series,
    models: List[str] = None
) -> SignalPredictor:
    """Convenience function to train a return predictor"""
    predictor = SignalPredictor(model_type='regression')
    predictor.fit(X, y, models_to_train=models)
    return predictor
