"""
QUANT360 ML GOD STACK
=====================
Institutional-grade ML infrastructure with 15 integrated modules across 6 capability levels.

LEVEL 1 - DATA & TRUTH LAYER:
- Module 1: data - Signal Outcome Dataset Builder
- Module 2: features - Feature Engineering & Validation

LEVEL 2 - SIGNAL INTELLIGENCE:
- Module 3: supervised - Signal Success Probability Engine
- Module 4: conditional - Conditional Performance Analyzer
- Module 5: ensemble - Model Consensus & Disagreement

LEVEL 3 - EXPLAINABILITY & FAILURE ANALYSIS:
- Module 6: explainability - Feature Attribution Suite (SHAP)
- Module 7: monitoring - Model Drift & Decay Monitor
- Module 8: errors - Error & Failure Regime Analyzer

LEVEL 4 - STRUCTURE DISCOVERY:
- Module 9: regimes - Market Regime Discovery
- Module 10: clustering - Asset Similarity & Redundancy Map
- Module 11: strategy_overlap - Strategy Overlap & Crowding Detector

LEVEL 5 - HUMAN UNDERSTANDABILITY:
- Module 12: embedding - Feature Space Embedding Explorer
- Module 13: regime_quality - Regime Separation Quality Analyzer

LEVEL 6 - EXECUTIVE & DECISION SUPPORT:
- Module 14: summary - Signal Quality Scorecard
- Module 15: summary - ML-Driven Position Sizing Advisor
"""

# Level 1 - Data & Truth Layer
from .data import DatasetBuilder, build_signal_dataset, get_dataset_overview
from .features import FeatureEngineer, engineer_features, validate_feature_matrix

# Level 2 - Signal Intelligence
from .supervised import SignalPredictor, train_signal_classifier
from .conditional import ConditionalAnalyzer, analyze_conditional_performance, get_performance_heatmap
from .ensemble import EnsembleEngine, create_ensemble, get_model_consensus

# Level 3 - Explainability & Failure Analysis
from .explainability import ExplainabilityEngine, create_explainer
from .monitoring import DriftMonitor, create_monitor, check_for_drift
from .errors import ErrorAnalyzer, analyze_model_errors

# Level 4 - Structure Discovery
from .regimes import RegimeDiscovery, discover_market_regimes
from .clustering import ClusteringEngine, analyze_portfolio_clustering
from .strategy_overlap import StrategyOverlapDetector, analyze_strategy_overlap, get_overlap_warnings

# Level 5 - Human Understandability
from .embedding import EmbeddingEngine, create_embedding
from .regime_quality import RegimeSeparationAnalyzer, analyze_regime_separation, get_regime_quality_score

# Level 6 - Executive & Decision Support
from .summary import SummaryEngine, score_signals, compute_position_sizing

__all__ = [
    # Level 1
    'DatasetBuilder', 'build_signal_dataset', 'get_dataset_overview',
    'FeatureEngineer', 'engineer_features', 'validate_feature_matrix',
    
    # Level 2
    'SignalPredictor', 'train_signal_classifier',
    'ConditionalAnalyzer', 'analyze_conditional_performance', 'get_performance_heatmap',
    'EnsembleEngine', 'create_ensemble', 'get_model_consensus',
    
    # Level 3
    'ExplainabilityEngine', 'create_explainer',
    'DriftMonitor', 'create_monitor', 'check_for_drift',
    'ErrorAnalyzer', 'analyze_model_errors',
    
    # Level 4
    'RegimeDiscovery', 'discover_market_regimes',
    'ClusteringEngine', 'analyze_portfolio_clustering',
    'StrategyOverlapDetector', 'analyze_strategy_overlap', 'get_overlap_warnings',
    
    # Level 5
    'EmbeddingEngine', 'create_embedding',
    'RegimeSeparationAnalyzer', 'analyze_regime_separation', 'get_regime_quality_score',
    
    # Level 6
    'SummaryEngine', 'score_signals', 'compute_position_sizing'
]

# Version info
__version__ = '2.0.0'
__modules__ = 15
