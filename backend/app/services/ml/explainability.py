"""
Labs → ML → Explainability
===========================
Feature Attribution Suite (SHAP)

Responsibilities:
- Feature attribution for predictions
- Per-prediction explanations
- Global model interpretation
- Answering "why did the model say this"
"""

import pandas as pd
import numpy as np
from typing import Dict, List, Any, Optional, Tuple
from datetime import datetime
import logging

logger = logging.getLogger(__name__)

# Try to import SHAP
try:
    import shap
    SHAP_AVAILABLE = True
except ImportError:
    SHAP_AVAILABLE = False
    logger.warning("SHAP not available. Install with: pip install shap")


class ExplainabilityEngine:
    """
    Feature Attribution Suite
    
    Uses SHAP values to explain model predictions,
    both globally and per-prediction.
    """
    
    def __init__(self):
        self.explainer = None
        self.base_value = None
        self.feature_names: List[str] = []
        self.global_importance: Dict[str, float] = {}
        
    def fit(
        self,
        model: Any,
        X_background: pd.DataFrame,
        model_type: str = 'tree'
    ):
        """
        Initialize the explainer with a model and background data.
        
        Args:
            model: Trained model (sklearn, XGBoost, LightGBM, etc.)
            X_background: Background dataset for SHAP calculations
            model_type: 'tree', 'linear', or 'kernel'
        """
        if not SHAP_AVAILABLE:
            raise ImportError("SHAP is not installed. Install with: pip install shap")
        
        self.feature_names = list(X_background.columns)
        
        # Select appropriate explainer
        if model_type == 'tree':
            try:
                self.explainer = shap.TreeExplainer(model)
            except Exception:
                # Fallback to kernel explainer
                self.explainer = shap.KernelExplainer(
                    model.predict_proba if hasattr(model, 'predict_proba') else model.predict,
                    shap.sample(X_background, min(100, len(X_background)))
                )
        elif model_type == 'linear':
            self.explainer = shap.LinearExplainer(model, X_background)
        else:
            self.explainer = shap.KernelExplainer(
                model.predict_proba if hasattr(model, 'predict_proba') else model.predict,
                shap.sample(X_background, min(100, len(X_background)))
            )
        
        # Compute global importance
        self._compute_global_importance(X_background)
    
    def _compute_global_importance(self, X: pd.DataFrame, sample_size: int = 500):
        """Compute global feature importance using SHAP values"""
        if self.explainer is None:
            return
        
        # Sample data if too large
        if len(X) > sample_size:
            X_sample = X.sample(n=sample_size, random_state=42)
        else:
            X_sample = X
        
        try:
            shap_values = self.explainer.shap_values(X_sample)
            
            # Handle multi-class output
            if isinstance(shap_values, list):
                shap_values = shap_values[1]  # Use positive class for binary
            
            # Mean absolute SHAP value per feature
            mean_abs_shap = np.abs(shap_values).mean(axis=0)
            
            self.global_importance = dict(zip(
                self.feature_names,
                mean_abs_shap.tolist()
            ))
            
            # Store base value
            if hasattr(self.explainer, 'expected_value'):
                ev = self.explainer.expected_value
                self.base_value = ev[1] if isinstance(ev, (list, np.ndarray)) else ev
            
        except Exception as e:
            logger.error(f"Error computing global importance: {e}")
            self.global_importance = {}
    
    def explain_prediction(
        self,
        X: pd.DataFrame,
        index: int = 0
    ) -> Dict[str, Any]:
        """
        Explain a single prediction.
        
        Args:
            X: Feature matrix
            index: Row index to explain
            
        Returns:
            Attribution breakdown for the prediction
        """
        if self.explainer is None:
            return {'error': 'Explainer not initialized. Call fit() first.'}
        
        if not SHAP_AVAILABLE:
            return {'error': 'SHAP not available'}
        
        try:
            # Get SHAP values for this instance
            X_instance = X.iloc[[index]] if isinstance(X, pd.DataFrame) else X[[index]]
            shap_values = self.explainer.shap_values(X_instance)
            
            # Handle multi-class
            if isinstance(shap_values, list):
                shap_values = shap_values[1]
            
            shap_values = shap_values[0]  # First (only) instance
            
            # Get feature values
            feature_values = X.iloc[index].to_dict() if isinstance(X, pd.DataFrame) else dict(zip(self.feature_names, X[index]))
            
            # Create attribution dictionary
            attributions = []
            for i, (name, value) in enumerate(zip(self.feature_names, shap_values)):
                attributions.append({
                    'feature': name,
                    'shap_value': float(value),
                    'feature_value': float(feature_values.get(name, 0)),
                    'direction': 'positive' if value > 0 else 'negative',
                    'abs_importance': abs(float(value))
                })
            
            # Sort by absolute importance
            attributions.sort(key=lambda x: x['abs_importance'], reverse=True)
            
            # Compute prediction breakdown
            base = self.base_value if self.base_value is not None else 0.5
            prediction = base + sum(a['shap_value'] for a in attributions)
            
            return {
                'base_value': float(base),
                'prediction': float(prediction),
                'attributions': attributions,
                'top_positive': [a for a in attributions if a['direction'] == 'positive'][:5],
                'top_negative': [a for a in attributions if a['direction'] == 'negative'][:5]
            }
            
        except Exception as e:
            logger.error(f"Error explaining prediction: {e}")
            return {'error': str(e)}
    
    def get_global_importance(
        self,
        top_n: int = 20
    ) -> Dict[str, Any]:
        """
        Get global feature importance.
        
        Returns:
            Ranked list of features by importance
        """
        if not self.global_importance:
            return {'error': 'No global importance computed. Call fit() first.'}
        
        # Sort by importance
        sorted_importance = sorted(
            self.global_importance.items(),
            key=lambda x: x[1],
            reverse=True
        )
        
        if top_n:
            sorted_importance = sorted_importance[:top_n]
        
        return {
            'features': [f[0] for f in sorted_importance],
            'importance': [f[1] for f in sorted_importance],
            'importance_dict': dict(sorted_importance),
            'total_features': len(self.global_importance)
        }
    
    def get_waterfall_data(
        self,
        X: pd.DataFrame,
        index: int = 0
    ) -> Dict[str, Any]:
        """
        Get data for waterfall chart visualization.
        
        Shows how each feature contributes to the prediction,
        starting from base value to final prediction.
        """
        explanation = self.explain_prediction(X, index)
        
        if 'error' in explanation:
            return explanation
        
        # Build waterfall data
        waterfall = []
        running_total = explanation['base_value']
        
        # Add base value
        waterfall.append({
            'feature': 'Base Value',
            'contribution': 0,
            'cumulative': running_total,
            'is_base': True
        })
        
        # Add top contributors (limit to 10 for visualization)
        attributions = explanation['attributions'][:10]
        
        for attr in attributions:
            running_total += attr['shap_value']
            waterfall.append({
                'feature': attr['feature'],
                'contribution': attr['shap_value'],
                'feature_value': attr['feature_value'],
                'cumulative': running_total,
                'is_base': False
            })
        
        # Add "other" if there are more features
        if len(explanation['attributions']) > 10:
            other_sum = sum(a['shap_value'] for a in explanation['attributions'][10:])
            running_total += other_sum
            waterfall.append({
                'feature': 'Other Features',
                'contribution': other_sum,
                'cumulative': running_total,
                'is_base': False
            })
        
        # Add final prediction
        waterfall.append({
            'feature': 'Prediction',
            'contribution': 0,
            'cumulative': explanation['prediction'],
            'is_base': True
        })
        
        return {
            'waterfall': waterfall,
            'base_value': explanation['base_value'],
            'prediction': explanation['prediction']
        }
    
    def get_dependence_data(
        self,
        X: pd.DataFrame,
        feature: str,
        interaction_feature: str = None,
        sample_size: int = 500
    ) -> Dict[str, Any]:
        """
        Get data for dependence plot showing how a feature affects predictions.
        
        Args:
            X: Feature matrix
            feature: Feature to analyze
            interaction_feature: Optional second feature for coloring
            sample_size: Max samples to compute
            
        Returns:
            Data for scatter plot of feature value vs SHAP value
        """
        if self.explainer is None:
            return {'error': 'Explainer not initialized'}
        
        if feature not in self.feature_names:
            return {'error': f"Feature '{feature}' not found"}
        
        try:
            # Sample if needed
            if len(X) > sample_size:
                X_sample = X.sample(n=sample_size, random_state=42)
            else:
                X_sample = X
            
            # Compute SHAP values
            shap_values = self.explainer.shap_values(X_sample)
            if isinstance(shap_values, list):
                shap_values = shap_values[1]
            
            # Get feature index
            feature_idx = self.feature_names.index(feature)
            
            # Get feature values and SHAP values
            feature_values = X_sample[feature].values.tolist()
            shap_feature_values = shap_values[:, feature_idx].tolist()
            
            result = {
                'feature': feature,
                'feature_values': feature_values,
                'shap_values': shap_feature_values
            }
            
            # Add interaction feature if specified
            if interaction_feature and interaction_feature in self.feature_names:
                result['interaction_feature'] = interaction_feature
                result['interaction_values'] = X_sample[interaction_feature].values.tolist()
            
            return result
            
        except Exception as e:
            logger.error(f"Error computing dependence data: {e}")
            return {'error': str(e)}
    
    def get_summary_table(
        self,
        X: pd.DataFrame,
        sample_size: int = 100
    ) -> Dict[str, Any]:
        """
        Get summary table with feature impacts for multiple samples.
        
        Returns table suitable for display showing feature values
        and their contributions across samples.
        """
        if self.explainer is None:
            return {'error': 'Explainer not initialized'}
        
        try:
            # Sample
            if len(X) > sample_size:
                X_sample = X.sample(n=sample_size, random_state=42)
            else:
                X_sample = X
            
            # Compute SHAP values
            shap_values = self.explainer.shap_values(X_sample)
            if isinstance(shap_values, list):
                shap_values = shap_values[1]
            
            # Create summary
            rows = []
            for i in range(len(X_sample)):
                row = {
                    'index': int(X_sample.index[i]),
                    'base_value': float(self.base_value) if self.base_value else 0.5
                }
                
                # Add top 5 contributors
                sorted_idx = np.argsort(np.abs(shap_values[i]))[::-1][:5]
                
                for rank, idx in enumerate(sorted_idx):
                    row[f'feature_{rank+1}'] = self.feature_names[idx]
                    row[f'value_{rank+1}'] = float(X_sample.iloc[i, idx])
                    row[f'shap_{rank+1}'] = float(shap_values[i, idx])
                
                row['prediction'] = float(row['base_value'] + shap_values[i].sum())
                rows.append(row)
            
            return {
                'rows': rows,
                'columns': ['index', 'base_value'] + 
                          [f'{p}_{i+1}' for i in range(5) for p in ['feature', 'value', 'shap']] +
                          ['prediction']
            }
            
        except Exception as e:
            logger.error(f"Error computing summary table: {e}")
            return {'error': str(e)}


# =============================================================================
# FALLBACK EXPLAINER (when SHAP not available)
# =============================================================================

class FallbackExplainer:
    """
    Simple feature importance explainer when SHAP is not available.
    Uses model's built-in feature importance or coefficients.
    """
    
    def __init__(self, model, feature_names: List[str]):
        self.model = model
        self.feature_names = feature_names
        self.importance = self._extract_importance()
    
    def _extract_importance(self) -> Dict[str, float]:
        """Extract importance from model"""
        if hasattr(self.model, 'feature_importances_'):
            return dict(zip(self.feature_names, self.model.feature_importances_.tolist()))
        elif hasattr(self.model, 'coef_'):
            coef = self.model.coef_[0] if self.model.coef_.ndim > 1 else self.model.coef_
            return dict(zip(self.feature_names, np.abs(coef).tolist()))
        else:
            return {f: 1.0 / len(self.feature_names) for f in self.feature_names}
    
    def get_global_importance(self) -> Dict[str, Any]:
        sorted_imp = sorted(self.importance.items(), key=lambda x: x[1], reverse=True)
        return {
            'features': [f[0] for f in sorted_imp],
            'importance': [f[1] for f in sorted_imp],
            'importance_dict': dict(sorted_imp)
        }
    
    def explain_prediction(self, X: pd.DataFrame, index: int = 0) -> Dict[str, Any]:
        """Simple explanation based on feature importance × feature value"""
        instance = X.iloc[index]
        
        attributions = []
        for feat in self.feature_names:
            value = instance.get(feat, 0)
            importance = self.importance.get(feat, 0)
            # Approximate contribution
            contrib = importance * (value if abs(value) < 10 else np.sign(value) * np.log(abs(value)))
            
            attributions.append({
                'feature': feat,
                'shap_value': float(contrib),  # Approximate
                'feature_value': float(value),
                'importance': float(importance)
            })
        
        attributions.sort(key=lambda x: abs(x['shap_value']), reverse=True)
        
        return {
            'attributions': attributions,
            'note': 'Approximate explanation (SHAP not available)'
        }


# =============================================================================
# CONVENIENCE FUNCTIONS
# =============================================================================

def create_explainer(
    model: Any,
    X_background: pd.DataFrame,
    model_type: str = 'tree'
) -> ExplainabilityEngine:
    """Convenience function to create explainer"""
    if not SHAP_AVAILABLE:
        logger.warning("Using fallback explainer (SHAP not installed)")
        return FallbackExplainer(model, list(X_background.columns))
    
    engine = ExplainabilityEngine()
    engine.fit(model, X_background, model_type)
    return engine


def explain_signal(
    explainer: ExplainabilityEngine,
    features: Dict[str, float]
) -> Dict[str, Any]:
    """Explain a single signal prediction"""
    X = pd.DataFrame([features])
    return explainer.explain_prediction(X, 0)
