"""
ML API Routes (Optimized)
==========================
API endpoints for the ML God Stack

Optimizations:
- Thread-safe caching with TTL
- LRU caching for expensive computations
- Background task support for training
- Rate limiting aware
- Connection pooling for data fetching
"""

from fastapi import APIRouter, HTTPException, Query, Body, BackgroundTasks
from pydantic import BaseModel, Field
from typing import Dict, List, Any, Optional
import pandas as pd
import numpy as np
import logging
from datetime import datetime, timedelta
from functools import lru_cache
import threading
import asyncio
from concurrent.futures import ThreadPoolExecutor

# Import ML modules
from app.services.ml.data import DatasetBuilder, build_signal_dataset, get_dataset_overview
from app.services.ml.features import FeatureEngineer, engineer_features, validate_feature_matrix
from app.services.ml.supervised import SignalPredictor, train_signal_classifier
from app.services.ml.conditional import ConditionalAnalyzer, analyze_conditional_performance
from app.services.ml.ensemble import EnsembleEngine, create_ensemble
from app.services.ml.explainability import ExplainabilityEngine, create_explainer
from app.services.ml.monitoring import DriftMonitor, create_monitor
from app.services.ml.errors import ErrorAnalyzer, analyze_model_errors
from app.services.ml.regimes import RegimeDiscovery, discover_market_regimes
from app.services.ml.clustering import ClusteringEngine, analyze_portfolio_clustering
from app.services.ml.strategy_overlap import StrategyOverlapDetector, analyze_strategy_overlap
from app.services.ml.embedding import EmbeddingEngine, create_embedding
from app.services.ml.regime_quality import RegimeSeparationAnalyzer, analyze_regime_separation
from app.services.ml.summary import SummaryEngine, score_signals, compute_position_sizing
from app.services.ml_v2.registry import ML_V2_FEATURES, run_feature as run_ml_v2_feature

logger = logging.getLogger(__name__)

router = APIRouter()


@router.get("/ml/v2/features")
async def list_ml_v2_features():
    """List available ML V2 feature contracts."""
    return {"features": [{"id": f.id, "title": f.title, "status": f.status} for f in ML_V2_FEATURES.values()]}


@router.post("/ml/v2/features/{feature_id}/run")
async def execute_ml_v2_feature(feature_id: str, payload: Dict[str, Any] = Body(default={})):
    """Execute one ML V2 feature without blocking the event loop."""
    try:
        return await asyncio.to_thread(run_ml_v2_feature, feature_id, payload)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc

# =============================================================================
# THREAD-SAFE CACHE WITH TTL
# =============================================================================

class TTLCache:
    """Thread-safe cache with TTL and size limits"""
    
    def __init__(self, max_size: int = 100, ttl_seconds: int = 3600):
        self._cache: Dict[str, Any] = {}
        self._expiry: Dict[str, datetime] = {}
        self._lock = threading.RLock()
        self.max_size = max_size
        self.ttl_seconds = ttl_seconds
    
    def get(self, key: str) -> Optional[Any]:
        with self._lock:
            if key not in self._cache:
                return None
            if datetime.now() > self._expiry.get(key, datetime.max):
                del self._cache[key]
                del self._expiry[key]
                return None
            return self._cache[key]
    
    def set(self, key: str, value: Any, ttl: int = None):
        with self._lock:
            # Evict oldest if at capacity
            if len(self._cache) >= self.max_size:
                oldest = min(self._expiry.items(), key=lambda x: x[1])[0]
                del self._cache[oldest]
                del self._expiry[oldest]
            
            self._cache[key] = value
            self._expiry[key] = datetime.now() + timedelta(seconds=ttl or self.ttl_seconds)
    
    def delete(self, key: str):
        with self._lock:
            self._cache.pop(key, None)
            self._expiry.pop(key, None)
    
    def __contains__(self, key: str) -> bool:
        return self.get(key) is not None
    
    def keys(self):
        with self._lock:
            return list(self._cache.keys())


# Global caches with appropriate TTLs
_model_cache = TTLCache(max_size=20, ttl_seconds=7200)  # 2 hours
_dataset_cache = TTLCache(max_size=10, ttl_seconds=3600)  # 1 hour
_monitor_cache = TTLCache(max_size=5, ttl_seconds=86400)  # 24 hours
_price_cache = TTLCache(max_size=500, ttl_seconds=300)  # 5 minutes for prices

# Thread pool for background tasks
_executor = ThreadPoolExecutor(max_workers=4)

# Training status tracking
_training_status: Dict[str, Any] = {}
_training_lock = threading.Lock()

# =============================================================================
# PYDANTIC MODELS (with validation)
# =============================================================================

class SignalInput(BaseModel):
    ticker: str = Field(..., min_length=1, max_length=10, pattern=r'^[A-Z0-9.]+$')
    signal_date: str = Field(..., pattern=r'^\d{4}-\d{2}-\d{2}$')
    signal_name: str = "unknown"
    strategy: str = "unknown"
    entry_price: Optional[float] = Field(None, gt=0)
    features: Optional[Dict[str, float]] = None

class DatasetRequest(BaseModel):
    signals: List[SignalInput] = Field(..., max_length=1000)  # Limit signals
    labeling_method: str = Field("binary", pattern=r'^(binary|threshold|continuous|sharpe|stop_loss)$')
    horizon: int = Field(5, ge=1, le=60)
    threshold: float = Field(0.02, ge=0, le=0.5)

class PredictionRequest(BaseModel):
    features: Dict[str, float] = Field(..., max_length=100)

class ScoreRequest(BaseModel):
    ml_probability: float = Field(..., ge=0, le=1)
    historical_win_rate: Optional[float] = Field(0.5, ge=0, le=1)
    sharpe_ratio: Optional[float] = Field(0.5, ge=-10, le=10)
    regime_fit: Optional[float] = Field(0.5, ge=0, le=1)
    model_confidence: Optional[float] = Field(0.5, ge=0, le=1)
    momentum_score: Optional[float] = Field(0, ge=-5, le=5)
    volume_score: Optional[float] = Field(1.0, ge=0, le=10)

class PositionSizeRequest(BaseModel):
    signal: ScoreRequest
    portfolio_value: float = Field(..., gt=0, le=1e12)
    risk_per_trade: float = Field(0.02, ge=0.001, le=0.25)


# =============================================================================
# HELPER FUNCTIONS
# =============================================================================

def get_cached_prices(tickers: List[str], period: str = '1y') -> pd.DataFrame:
    """Get prices with caching - uses centralized robust_data_fetcher"""
    from app.services.robust_data_fetcher import get_batch_data
    
    cache_key = f"prices_{'_'.join(sorted(tickers))}_{period}"
    cached = _price_cache.get(cache_key)
    if cached is not None:
        return cached
    
    try:
        # Use centralized data fetcher with rate limiting
        data_dict = get_batch_data(tickers, period=period)
        
        if not data_dict:
            return pd.DataFrame()
        
        # Extract close prices from each ticker's data
        close_data = {}
        for ticker, df in data_dict.items():
            if df is not None and not df.empty and 'Close' in df.columns:
                close_data[ticker] = df['Close']
        
        if not close_data:
            return pd.DataFrame()
        
        data = pd.DataFrame(close_data)
        _price_cache.set(cache_key, data)
        return data
    except Exception as e:
        logger.error(f"Price fetch error: {e}")
        return pd.DataFrame()


def run_in_background(func, *args, **kwargs):
    """Run function in background thread pool"""
    return _executor.submit(func, *args, **kwargs)


# =============================================================================
# LABS → ML → DATA
# =============================================================================

@router.get("/ml/data/demo")
async def get_demo_dataset():
    """Get a demo dataset for testing"""
    demo_signals = []
    tickers = ['AAPL', 'MSFT', 'GOOGL', 'AMZN', 'META']
    
    for ticker in tickers:
        # Increase to 30 signals per ticker to ensure we hit the 100 sample threshold
        for i in range(30):
            # Spread over 2 years to ensure sufficient history
            date = (datetime.now() - timedelta(days=30 + i*15)).strftime('%Y-%m-%d')
            demo_signals.append({
                'ticker': ticker,
                'signal_date': date,
                'signal_name': 'momentum_crossover',
                'strategy': 'momentum'
            })
    
    return {
        'demo_signals': demo_signals,
        'total_signals': len(demo_signals),
        'instructions': 'POST these signals to /api/ml/data/build to create a dataset'
    }


@router.post("/ml/data/build")
async def build_dataset(request: DatasetRequest, background_tasks: BackgroundTasks):
    """Build ML dataset from signals"""
    try:
        # Check if already building
        if _training_status.get('building_dataset'):
            return {'status': 'in_progress', 'message': 'Dataset build already in progress'}
        
        signals = [s.dict() for s in request.signals]
        
        # For small datasets, build synchronously
        if len(signals) <= 50:
            builder = DatasetBuilder()
            X, y, metadata = builder.build_dataset(
                signals,
                labeling_method=request.labeling_method,
                horizon=request.horizon,
                threshold=request.threshold
            )
            
            if X.empty:
                return {'status': 'error', 'message': 'No valid data could be built from signals'}
            
            # Cache for later use
            _dataset_cache.set('latest', {'X': X, 'y': y, 'metadata': metadata})
            
            stats = builder.get_dataset_stats(X, y, metadata)
            missing = builder.get_missing_data_heatmap(X)
            
            # Replace NaN/None values for JSON serialization
            sample_features = X.head(5).fillna(0).to_dict('records')
            
            return {
                'status': 'success',
                'stats': stats,
                'missing_data': missing,
                'sample_features': sample_features
            }
        else:
            # For large datasets, build in background
            with _training_lock:
                _training_status['building_dataset'] = True
            
            def build_async():
                try:
                    builder = DatasetBuilder()
                    X, y, metadata = builder.build_dataset(
                        signals,
                        labeling_method=request.labeling_method,
                        horizon=request.horizon,
                        threshold=request.threshold
                    )
                    if not X.empty:
                        _dataset_cache.set('latest', {'X': X, 'y': y, 'metadata': metadata})
                        _training_status['last_build_stats'] = builder.get_dataset_stats(X, y, metadata)
                finally:
                    with _training_lock:
                        _training_status['building_dataset'] = False
            
            background_tasks.add_task(build_async)
            
            return {
                'status': 'building',
                'message': f'Building dataset with {len(signals)} signals in background',
                'check_endpoint': '/api/ml/data/overview'
            }
            
    except Exception as e:
        logger.error(f"Dataset build error: {e}")
        with _training_lock:
            _training_status['building_dataset'] = False
        raise HTTPException(status_code=500, detail="Internal server error")


@router.get("/ml/data/overview")
async def get_data_overview():
    """Get overview of cached dataset"""
    cached = _dataset_cache.get('latest')
    if not cached:
        return {
            'status': 'no_data', 
            'message': 'No dataset built yet',
            'building': _training_status.get('building_dataset', False)
        }
    
    data = cached
    builder = DatasetBuilder()
    
    return {
        'status': 'success',
        'overview': get_dataset_overview(data['X'], data['y'], data['metadata'])
    }


# =============================================================================
# LABS → ML → FEATURES
# =============================================================================

@router.get("/ml/features/validate")
async def validate_features():
    """Validate features in cached dataset"""
    cached = _dataset_cache.get('latest')
    if not cached:
        return {'status': 'no_data', 'message': 'No dataset built yet'}
    
    X = cached['X']
    y = cached['y']
    
    # Cache validation result
    cache_key = f"validation_{id(X)}"
    cached_result = _model_cache.get(cache_key)
    if cached_result:
        return {'status': 'success', 'validation': cached_result}
    
    validation = validate_feature_matrix(X, y)
    _model_cache.set(cache_key, validation, ttl=600)
    
    return {'status': 'success', 'validation': validation}


@router.get("/ml/features/correlation")
async def get_feature_correlation():
    """Get feature correlation matrix"""
    cached = _dataset_cache.get('latest')
    if not cached:
        return {'status': 'no_data', 'message': 'No dataset built yet'}
    
    X = cached['X']
    engineer = FeatureEngineer()
    
    return engineer.get_correlation_matrix(X)


# =============================================================================
# LABS → ML → SUPERVISED
# =============================================================================

@router.post("/ml/supervised/train")
async def train_models(
    models: List[str] = Body(default=['logistic', 'random_forest']),
    background_tasks: BackgroundTasks = None
):
    """Train supervised models on cached dataset"""
    cached = _dataset_cache.get('latest')
    if not cached:
        raise HTTPException(status_code=400, detail="No dataset available. Build dataset first.")
    
    # Check if already training
    if _training_status.get('training_models'):
        return {'status': 'in_progress', 'message': 'Training already in progress'}
    
    X = cached['X']
    y = cached['y']
    
    # Validate models list
    valid_models = ['logistic', 'random_forest', 'gradient_boosting', 'xgboost', 'lightgbm']
    models = [m for m in models if m in valid_models]
    
    if not models:
        raise HTTPException(status_code=400, detail="No valid models specified")
    
    # For small datasets or few models, train synchronously
    if len(X) < 500 and len(models) <= 2:
        try:
            predictor = SignalPredictor(model_type='classification')
            results = predictor.fit(X, y, models_to_train=models)
            _model_cache.set('predictor', predictor)
            
            return {'status': 'success', 'training_results': results}
        except Exception as e:
            logger.error(f"Training error: {e}")
            raise HTTPException(status_code=500, detail="Internal server error")
    else:
        # Train in background for large datasets
        with _training_lock:
            _training_status['training_models'] = True
            _training_status['training_started'] = datetime.now().isoformat()
        
        def train_async():
            try:
                predictor = SignalPredictor(model_type='classification')
                results = predictor.fit(X, y, models_to_train=models)
                _model_cache.set('predictor', predictor)
                _training_status['last_training_results'] = results
            except Exception as e:
                logger.error(f"Background training error: {e}")
                _training_status['training_error'] = str(e)
            finally:
                with _training_lock:
                    _training_status['training_models'] = False
        
        background_tasks.add_task(train_async)
        
        return {
            'status': 'training',
            'message': f'Training {len(models)} models on {len(X)} samples in background',
            'check_endpoint': '/api/ml/supervised/status'
        }


@router.get("/ml/supervised/status")
async def get_training_status():
    """Get training status"""
    return {
        'training': _training_status.get('training_models', False),
        'started': _training_status.get('training_started'),
        'last_results': _training_status.get('last_training_results'),
        'error': _training_status.get('training_error'),
        'model_ready': _model_cache.get('predictor') is not None
    }


@router.post("/ml/supervised/predict")
async def predict_signal(request: PredictionRequest):
    """Predict for a single signal"""
    predictor = _model_cache.get('predictor')
    if not predictor:
        raise HTTPException(status_code=400, detail="No model trained. Train model first.")
    
    try:
        result = predictor.predict_single(request.features)
        return {'status': 'success', 'prediction': result}
    except Exception as e:
        logger.error(f"Prediction error: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")


@router.get("/ml/supervised/importance")
async def get_feature_importance(model_name: str = None):
    """Get feature importance from trained model"""
    predictor = _model_cache.get('predictor')
    if not predictor:
        raise HTTPException(status_code=400, detail="No model trained")
    
    importance = predictor.get_feature_importance(model_name)
    sorted_importance = sorted(importance.items(), key=lambda x: x[1], reverse=True)
    
    return {
        'status': 'success',
        'importance': dict(sorted_importance[:20]),
        'total_features': len(importance)
    }


# =============================================================================
# LABS → ML → ENSEMBLE
# =============================================================================

@router.post("/ml/ensemble/consensus")
async def get_ensemble_consensus(request: PredictionRequest):
    """Get ensemble consensus prediction"""
    predictor = _model_cache.get('predictor')
    if not predictor:
        raise HTTPException(status_code=400, detail="No model trained")
    
    X = pd.DataFrame([request.features])
    result = predictor.predict(X, return_all_models=True)
    
    return {
        'status': 'success',
        'consensus': {
            'probability': result['predictions'][0],
            'confidence_tier': result['confidence_tiers'][0],
            'disagreement': result['disagreement'][0]
        },
        'model_predictions': {k: v[0] for k, v in result['model_predictions'].items()}
    }


@router.get("/ml/ensemble/agreement")
async def get_model_agreement():
    """Get model agreement matrix"""
    predictor = _model_cache.get('predictor')
    cached = _dataset_cache.get('latest')
    
    if not predictor or not cached:
        raise HTTPException(status_code=400, detail="No model or data available")
    
    ensemble = EnsembleEngine()
    ensemble.predictor = predictor
    
    # Use sample for efficiency
    X = cached['X'].head(min(100, len(cached['X'])))
    
    return ensemble.get_model_agreement_matrix(X)


# =============================================================================
# LABS → ML → EXPLAINABILITY
# =============================================================================

@router.post("/ml/explain/global")
async def get_global_explanation(top_n: int = Query(20, ge=1, le=100)):
    """Get global feature importance explanation"""
    predictor = _model_cache.get('predictor')
    if not predictor:
        raise HTTPException(status_code=400, detail="No model trained")
    
    importance = predictor.get_feature_importance()
    sorted_imp = sorted(importance.items(), key=lambda x: x[1], reverse=True)[:top_n]
    
    total_importance = sum(v for k, v in importance.items())
    
    return {
        'status': 'success',
        'global_importance': dict(sorted_imp),
        'total_features': len(importance),
        'top_n_coverage': sum(v for k, v in sorted_imp) / total_importance if total_importance > 0 else 0
    }


@router.post("/ml/explain/signal")
async def explain_signal(request: PredictionRequest):
    """Explain a single signal prediction"""
    predictor = _model_cache.get('predictor')
    if not predictor:
        raise HTTPException(status_code=400, detail="No model trained")
    
    pred = predictor.predict_single(request.features)
    importance = predictor.get_feature_importance()
    
    contributions = {}
    for feat, value in request.features.items():
        imp = importance.get(feat, 0)
        contributions[feat] = {
            'feature_value': float(value),
            'importance': float(imp),
            'direction': 'positive' if value > 0 else 'negative'
        }
    
    sorted_contrib = sorted(contributions.items(), key=lambda x: x[1]['importance'], reverse=True)
    
    return {
        'status': 'success',
        'prediction': pred,
        'top_contributors': dict(sorted_contrib[:10])
    }


# =============================================================================
# LABS → ML → MONITORING
# =============================================================================

@router.post("/ml/monitor/initialize")
async def initialize_monitor():
    """Initialize drift monitor with training data"""
    cached = _dataset_cache.get('latest')
    if not cached:
        raise HTTPException(status_code=400, detail="No dataset available")
    
    X = cached['X']
    monitor = create_monitor(X)
    
    _monitor_cache.set('default', monitor)
    
    return {
        'status': 'success',
        'features_monitored': len(monitor.feature_baselines),
        'message': 'Monitor initialized with baseline distributions'
    }


@router.post("/ml/monitor/check-drift")
async def check_drift(features: Dict[str, List[float]] = Body(...)):
    """Check for feature drift in new data"""
    monitor = _monitor_cache.get('default')
    if not monitor:
        raise HTTPException(status_code=400, detail="Monitor not initialized")
    
    X_current = pd.DataFrame(features)
    drift_result = monitor.compute_feature_drift(X_current)
    
    return {'status': 'success', 'drift_analysis': drift_result}


@router.get("/ml/monitor/summary")
async def get_monitor_summary():
    """Get monitoring summary"""
    monitor = _monitor_cache.get('default')
    if not monitor:
        return {'status': 'not_initialized'}
    
    return monitor.get_monitoring_summary()


@router.get("/ml/monitor/alerts")
async def get_alerts(limit: int = Query(50, ge=1, le=500)):
    """Get recent alerts"""
    monitor = _monitor_cache.get('default')
    if not monitor:
        return {'alerts': []}
    
    return {'alerts': monitor.get_alert_log(limit)}


# =============================================================================
# LABS → ML → ERRORS
# =============================================================================

@router.post("/ml/errors/analyze")
async def analyze_errors():
    """Analyze model errors on test data"""
    predictor = _model_cache.get('predictor')
    cached = _dataset_cache.get('latest')
    
    if not predictor or not cached:
        raise HTTPException(status_code=400, detail="Model and data required")
    
    X = cached['X']
    y = cached['y']
    
    preds = predictor.predict(X)
    
    analyzer, results = analyze_model_errors(
        pd.Series(preds['predictions']),
        y,
        X,
        n_clusters=5
    )
    
    _model_cache.set('error_analyzer', analyzer)
    
    return {
        'status': 'success',
        'error_analysis': results['error_analysis'],
        'clusters': results['clusters'],
        'high_risk_conditions': results['high_risk_conditions'][:5],
        'summary': results['summary']
    }


@router.post("/ml/errors/risk-flags")
async def check_risk_flags(request: PredictionRequest):
    """Check if current conditions trigger any risk flags"""
    analyzer = _model_cache.get('error_analyzer')
    if not analyzer:
        return {'risk_flags': [], 'message': 'Run error analysis first'}
    
    flags = analyzer.get_risk_flags(request.features)
    
    return {'active_flags': flags, 'total_flags': len(flags)}


# =============================================================================
# LABS → ML → REGIMES
# =============================================================================

@router.post("/ml/regimes/discover")
async def discover_regimes(
    n_regimes: int = Query(4, ge=2, le=10),
    method: str = Query('kmeans', pattern=r'^(kmeans|hierarchical)$')
):
    """Discover market regimes from feature data"""
    cached = _dataset_cache.get('latest')
    if not cached:
        raise HTTPException(status_code=400, detail="No dataset available")
    
    X = cached['X']
    
    discovery, results = discover_market_regimes(X, n_regimes)
    _model_cache.set('regime_discovery', discovery)
    
    return {'status': 'success', 'discovery': results}


@router.get("/ml/regimes/current")
async def get_current_regime():
    """Get current market regime"""
    discovery = _model_cache.get('regime_discovery')
    if not discovery:
        return {'error': 'Regimes not discovered yet'}
    
    return discovery.get_current_regime()


@router.get("/ml/regimes/timeline")
async def get_regime_timeline():
    """Get regime timeline"""
    discovery = _model_cache.get('regime_discovery')
    if not discovery:
        return {'error': 'Regimes not discovered yet'}
    
    return discovery.get_regime_timeline()


@router.get("/ml/regimes/statistics")
async def get_regime_statistics():
    """Get detailed regime statistics"""
    discovery = _model_cache.get('regime_discovery')
    if not discovery:
        return {'error': 'Regimes not discovered yet'}
    
    return discovery.get_regime_statistics()


# =============================================================================
# LABS → ML → CLUSTERING
# =============================================================================

@router.post("/ml/clustering/assets")
async def cluster_assets(
    tickers: List[str] = Body(..., max_length=100),
    n_clusters: int = Body(default=5, ge=2, le=20)
):
    """Cluster assets by return correlation"""
    # Use cached prices
    returns = get_cached_prices(tickers, '1y')
    
    if returns.empty:
        raise HTTPException(status_code=400, detail="Could not fetch price data")
    
    returns = returns.pct_change().dropna()
    
    try:
        engine, results = analyze_portfolio_clustering(returns, n_clusters)
        _model_cache.set('clustering_engine', engine)
        
        return {
            'status': 'success',
            'clustering': results['clusters'],
            'redundancy': results['redundancy'],
            'diversification': results['diversification']
        }
    except Exception as e:
        logger.error(f"Clustering error: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")


@router.get("/ml/clustering/dendrogram")
async def get_dendrogram():
    """Get dendrogram data for visualization"""
    engine = _model_cache.get('clustering_engine')
    if not engine:
        return {'error': 'Run clustering first'}
    
    return engine.get_dendrogram_data()


@router.get("/ml/clustering/network")
async def get_network_graph(threshold: float = Query(0.5, ge=0, le=1)):
    """Get network graph data for visualization"""
    engine = _model_cache.get('clustering_engine')
    if not engine:
        return {'error': 'Run clustering first'}
    
    return engine.get_network_graph_data(threshold)


# =============================================================================
# LABS → ML → EMBEDDING
# =============================================================================

@router.post("/ml/embedding/compute")
async def compute_embedding(
    method: str = Query('umap', pattern=r'^(umap|tsne|pca)$'),
    n_components: int = Query(2, ge=2, le=3)
):
    """Compute feature space embedding"""
    cached = _dataset_cache.get('latest')
    if not cached:
        raise HTTPException(status_code=400, detail="No dataset available")
    
    X = cached['X']
    
    # Limit to 5000 samples for performance
    if len(X) > 5000:
        X = X.sample(5000, random_state=42)
    
    engine, result = create_embedding(X, method, n_components)
    _model_cache.set('embedding_engine', engine)
    
    return {'status': 'success', 'embedding': result}


@router.get("/ml/embedding/separation")
async def compute_separation():
    """Compute regime separation metrics in embedding space"""
    engine = _model_cache.get('embedding_engine')
    cached = _dataset_cache.get('latest')
    
    if not engine:
        return {'error': 'Compute embedding first'}
    if not cached:
        return {'error': 'No dataset available'}
    
    y = cached['y']
    
    return engine.compute_separation_metrics(y)


# =============================================================================
# LABS → ML → SUMMARY (Scorecards)
# =============================================================================

@router.post("/ml/summary/score")
async def score_single_signal(request: ScoreRequest):
    """Score a single signal"""
    signal = request.dict()
    
    engine = SummaryEngine()
    result = engine.compute_signal_score(signal)
    
    return {'status': 'success', 'score': result}


@router.post("/ml/summary/rank")
async def rank_signals_endpoint(
    signals: List[ScoreRequest] = Body(..., max_length=1000),
    top_n: int = Query(20, ge=1, le=100)
):
    """Rank multiple signals by quality"""
    signals_dict = [s.dict() for s in signals]
    result = score_signals(signals_dict)
    
    # Return only top_n
    result['ranked_signals'] = result.get('ranked_signals', [])[:top_n]
    
    return {'status': 'success', 'ranking': result}


# =============================================================================
# PORTFOLIO INTEGRATION
# =============================================================================

@router.post("/ml/portfolio/position-size")
async def get_position_size(request: PositionSizeRequest):
    """Get ML-driven position size recommendation"""
    signal = request.signal.dict()
    result = compute_position_sizing(signal, request.portfolio_value, request.risk_per_trade)
    
    return {'status': 'success', 'recommendation': result}


@router.post("/ml/portfolio/allocation")
async def get_portfolio_allocation(
    signals: List[ScoreRequest] = Body(..., max_length=100),
    portfolio_value: float = Body(default=100000, gt=0, le=1e12),
    max_exposure: float = Body(default=0.80, ge=0.1, le=1.0)
):
    """Get optimal allocation across signals"""
    signals_dict = [s.dict() for s in signals]
    
    engine = SummaryEngine()
    result = engine.get_portfolio_allocation(signals_dict, portfolio_value, max_exposure)
    
    return {'status': 'success', 'allocation': result}


@router.post("/ml/portfolio/stress-test")
async def run_stress_test(
    position_value: float = Body(..., gt=0, le=1e12),
    scenarios: List[str] = Body(default=['crash', 'volatility_spike', 'flash_crash'], max_length=20)
):
    """Run stress test scenarios"""
    engine = SummaryEngine()
    result = engine.run_stress_scenarios(position_value, scenarios)
    
    return {'status': 'success', 'stress_test': result}


# =============================================================================
# HEALTH CHECK & CACHE MANAGEMENT
# =============================================================================

# =============================================================================
# LABS → ML → CONDITIONAL PERFORMANCE (Module 4)
# =============================================================================

@router.post("/ml/conditional/analyze")
async def analyze_conditional():
    """Analyze signal performance by market conditions"""
    cached = _dataset_cache.get('latest')
    if not cached:
        raise HTTPException(status_code=400, detail="No dataset available")
    
    metadata = cached.get('metadata', pd.DataFrame())
    y = cached['y']
    
    if metadata.empty:
        return {'error': 'No signal metadata available'}
    
    analyzer = ConditionalAnalyzer()
    results = analyzer.analyze_by_conditions(metadata, y)
    
    _model_cache.set('conditional_analyzer', analyzer)
    
    return {'status': 'success', 'analysis': results}


@router.get("/ml/conditional/heatmap")
async def get_conditional_heatmap():
    """Get heatmap data for regime vs return visualization"""
    analyzer = _model_cache.get('conditional_analyzer')
    if not analyzer:
        return {'error': 'Run conditional analysis first'}
    
    return analyzer.get_heatmap_data()


@router.get("/ml/conditional/fingerprints")
async def get_signal_fingerprints():
    """Get performance fingerprints for each signal type"""
    analyzer = _model_cache.get('conditional_analyzer')
    if not analyzer:
        return {'error': 'Run conditional analysis first'}
    
    return {
        'fingerprints': analyzer.analysis_results.get('signal_fingerprints', {}),
        'best_worst': analyzer.analysis_results.get('best_worst_conditions', {})
    }


# =============================================================================
# LABS → ML → STRATEGY OVERLAP (Module 11)
# =============================================================================

@router.post("/ml/strategies/analyze")
async def analyze_strategy_overlap_endpoint(
    strategy_returns: Dict[str, List[float]] = Body(...),
    overlap_threshold: float = Body(default=0.7)
):
    """Analyze strategy overlap and crowding"""
    returns_df = pd.DataFrame(strategy_returns)
    
    if len(returns_df.columns) < 2:
        raise HTTPException(status_code=400, detail="Need at least 2 strategies")
    
    detector, results = analyze_strategy_overlap(returns_df, overlap_threshold)
    _model_cache.set('strategy_detector', detector)
    
    return {'status': 'success', 'analysis': results}


@router.get("/ml/strategies/heatmap")
async def get_strategy_heatmap():
    """Get strategy similarity heatmap data"""
    detector = _model_cache.get('strategy_detector')
    if not detector:
        return {'error': 'Run strategy analysis first'}
    
    return detector.get_similarity_heatmap()


@router.get("/ml/strategies/dendrogram")
async def get_strategy_dendrogram():
    """Get strategy dendrogram data"""
    detector = _model_cache.get('strategy_detector')
    if not detector:
        return {'error': 'Run strategy analysis first'}
    
    return detector.get_dendrogram_data()


@router.get("/ml/strategies/allocation")
async def get_strategy_allocation():
    """Get suggested allocation for diversification"""
    detector = _model_cache.get('strategy_detector')
    if not detector:
        return {'error': 'Run strategy analysis first'}
    
    return detector.get_allocation_suggestion()


# =============================================================================
# LABS → ML → REGIME SEPARATION QUALITY (Module 13)
# =============================================================================

@router.post("/ml/regime-quality/analyze")
async def analyze_regime_quality():
    """Analyze regime separation quality in embedding space"""
    embedding_engine = _model_cache.get('embedding_engine')
    regime_discovery = _model_cache.get('regime_discovery')
    
    if not embedding_engine:
        return {'error': 'Compute embeddings first'}
    if not regime_discovery:
        return {'error': 'Discover regimes first'}
    
    # Get embeddings and regime labels
    embeddings = embedding_engine.embedding_
    regime_labels = regime_discovery.regime_labels_ if hasattr(regime_discovery, 'regime_labels_') else None
    
    if embeddings is None:
        return {'error': 'No embeddings available'}
    
    # Generate regime labels if not available
    if regime_labels is None:
        cached = _dataset_cache.get('latest')
        if cached:
            # Use binary labels as proxy
            regime_labels = cached['y'].values
        else:
            return {'error': 'No regime labels available'}
    
    analyzer, results = analyze_regime_separation(embeddings, regime_labels)
    _model_cache.set('regime_quality_analyzer', analyzer)
    
    return {'status': 'success', 'analysis': results}


@router.get("/ml/regime-quality/overlap")
async def get_regime_overlap():
    """Get regime overlap matrix"""
    analyzer = _model_cache.get('regime_quality_analyzer')
    if not analyzer:
        return {'error': 'Run regime quality analysis first'}
    
    return analyzer.get_overlap_heatmap_data()


@router.get("/ml/regime-quality/visualization")
async def get_regime_quality_viz():
    """Get visualization data for regime separation"""
    analyzer = _model_cache.get('regime_quality_analyzer')
    if not analyzer:
        return {'error': 'Run regime quality analysis first'}
    
    return analyzer.get_visualization_data()


# =============================================================================
# HEALTH CHECK & CACHE MANAGEMENT
# =============================================================================

@router.get("/ml/health")
async def ml_health_check():
    """Check ML system health"""
    return {
        'status': 'healthy',
        'version': '2.0.0',
        'modules': 15,
        'dataset_cached': 'latest' in _dataset_cache.keys(),
        'model_trained': _model_cache.get('predictor') is not None,
        'monitor_initialized': _monitor_cache.get('default') is not None,
        'training_in_progress': _training_status.get('training_models', False),
        'building_in_progress': _training_status.get('building_dataset', False),
        'cache_stats': {
            'models': len(_model_cache.keys()),
            'datasets': len(_dataset_cache.keys()),
            'prices': len(_price_cache.keys())
        },
        'available_endpoints': [
            '/ml/data/*', '/ml/features/*', '/ml/supervised/*',
            '/ml/conditional/*', '/ml/ensemble/*', '/ml/explain/*',
            '/ml/monitor/*', '/ml/errors/*', '/ml/regimes/*',
            '/ml/clustering/*', '/ml/strategies/*', '/ml/embedding/*',
            '/ml/regime-quality/*', '/ml/summary/*', '/ml/portfolio/*'
        ]
    }


@router.post("/ml/cache/clear")
async def clear_ml_caches(cache_type: str = Body(default='all')):
    """Clear ML caches"""
    if cache_type in ['all', 'models']:
        for key in list(_model_cache.keys()):
            _model_cache.delete(key)
    
    if cache_type in ['all', 'datasets']:
        for key in list(_dataset_cache.keys()):
            _dataset_cache.delete(key)
    
    if cache_type in ['all', 'prices']:
        for key in list(_price_cache.keys()):
            _price_cache.delete(key)
    
    return {'status': 'success', 'message': f'Cleared {cache_type} caches'}
