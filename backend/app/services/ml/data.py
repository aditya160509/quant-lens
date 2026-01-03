"""
Labs → ML → Data
=================
Signal Outcome Dataset Builder - The Ground Truth Layer

Responsibilities:
- Turn signals into labeled ML rows
- Ensure labels are correct (no look-ahead bias)  
- Ensure reproducibility
- Dataset versioning

Now uses robust_data_fetcher for multi-source data with caching and rate limiting.
"""

import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from typing import Dict, List, Any, Optional, Tuple, Literal
import hashlib
import json
import logging

# Use robust data fetcher - handles rate limiting, caching, multi-source fallback
from app.services.robust_data_fetcher import (
    get_price_data as rdf_get_price,
    get_batch_data as rdf_get_batch
)

logger = logging.getLogger(__name__)

# =============================================================================
# LABELING STRATEGIES
# =============================================================================

class LabelingStrategy:
    """Base class for outcome labeling strategies"""
    
    @staticmethod
    def binary_fixed_horizon(
        entry_price: float,
        prices_after: pd.Series,
        horizon: int = 5
    ) -> Tuple[int, float]:
        """
        Binary label: 1 if price goes up within horizon, 0 otherwise
        Returns: (label, actual_return)
        """
        if len(prices_after) < horizon:
            return None, None
        
        exit_price = prices_after.iloc[horizon - 1]
        ret = (exit_price - entry_price) / entry_price
        label = 1 if ret > 0 else 0
        return label, ret
    
    @staticmethod
    def binary_threshold(
        entry_price: float,
        prices_after: pd.Series,
        horizon: int = 5,
        threshold: float = 0.02
    ) -> Tuple[Optional[int], Optional[float]]:
        """
        Binary label with threshold: 1 if return > threshold, 0 if < -threshold, None otherwise
        """
        if len(prices_after) < horizon:
            return None, None
        
        exit_price = prices_after.iloc[horizon - 1]
        ret = (exit_price - entry_price) / entry_price
        
        if ret > threshold:
            return 1, ret
        elif ret < -threshold:
            return 0, ret
        else:
            return None, ret  # Neutral, exclude from training
    
    @staticmethod
    def continuous_return(
        entry_price: float,
        prices_after: pd.Series,
        horizon: int = 5
    ) -> Tuple[Optional[float], Optional[float]]:
        """
        Continuous label: actual return percentage
        """
        if len(prices_after) < horizon:
            return None, None
        
        exit_price = prices_after.iloc[horizon - 1]
        ret = (exit_price - entry_price) / entry_price
        return ret, ret
    
    @staticmethod
    def risk_adjusted_sharpe(
        entry_price: float,
        prices_after: pd.Series,
        horizon: int = 20
    ) -> Tuple[Optional[float], Optional[float]]:
        """
        Risk-adjusted label: Sharpe ratio over holding period
        """
        if len(prices_after) < horizon:
            return None, None
        
        holding_prices = prices_after.iloc[:horizon]
        daily_returns = holding_prices.pct_change().dropna()
        
        if len(daily_returns) < 2 or daily_returns.std() == 0:
            return None, None
        
        sharpe = (daily_returns.mean() / daily_returns.std()) * np.sqrt(252)
        total_ret = (holding_prices.iloc[-1] - entry_price) / entry_price
        return sharpe, total_ret
    
    @staticmethod
    def stop_loss_take_profit(
        entry_price: float,
        prices_after: pd.Series,
        stop_loss: float = -0.05,
        take_profit: float = 0.10,
        max_horizon: int = 20
    ) -> Tuple[Optional[int], Optional[float], Optional[str]]:
        """
        Label based on which exit triggered first
        Returns: (label, return, exit_reason)
        """
        for i, price in enumerate(prices_after.iloc[:max_horizon]):
            ret = (price - entry_price) / entry_price
            
            if ret <= stop_loss:
                return 0, ret, 'stop_loss'
            elif ret >= take_profit:
                return 1, ret, 'take_profit'
        
        # Max horizon reached
        if len(prices_after) >= max_horizon:
            final_ret = (prices_after.iloc[max_horizon - 1] - entry_price) / entry_price
            label = 1 if final_ret > 0 else 0
            return label, final_ret, 'timeout'
        
        return None, None, None


# =============================================================================
# DATASET BUILDER - Using robust_data_fetcher
# =============================================================================

class DatasetBuilder:
    """
    Signal Outcome Dataset Builder
    
    Transforms raw trading signals into ML-ready training data with proper labels
    and features, ensuring no look-ahead bias.
    
    Now uses robust_data_fetcher for:
    - Multi-source fallback (NSE -> Yahoo Direct -> yfinance)
    - Built-in rate limiting
    - Persistent disk caching
    - Input validation
    """
    
    def __init__(self, cache_dir: str = None):
        self.cache_dir = cache_dir
        # Local cache for date-filtered data (robust_data_fetcher handles main caching)
        self._local_cache: Dict[str, pd.DataFrame] = {}
    
    def fetch_prices(self, ticker: str, start: str, end: str) -> pd.DataFrame:
        """Fetch OHLCV data for ticker using robust_data_fetcher"""
        cache_key = f"{ticker}_{start}_{end}"
        
        if cache_key in self._local_cache:
            return self._local_cache[cache_key]
        
        try:
            # Calculate period based on date range
            start_dt = datetime.strptime(start, '%Y-%m-%d')
            end_dt = datetime.strptime(end, '%Y-%m-%d')
            days_diff = (end_dt - start_dt).days
            
            if days_diff <= 30:
                period = "1mo"
            elif days_diff <= 90:
                period = "3mo"
            elif days_diff <= 180:
                period = "6mo"
            elif days_diff <= 365:
                period = "1y"
            elif days_diff <= 730:
                period = "2y"
            else:
                period = "5y"
            
            # Use robust data fetcher - always fetch max period to ensure we have data
            # The filtering happens after fetching
            df = rdf_get_price(ticker, period="5y")  # Always get max to cover any date range
            
            if df is None or df.empty:
                logger.warning(f"No data for {ticker}")
                return pd.DataFrame()
            
            # Filter to date range
            df_filtered = df[(df.index >= start_dt) & (df.index <= end_dt)]
            
            if not df_filtered.empty:
                self._local_cache[cache_key] = df_filtered
            else:
                logger.warning(f"No data for {ticker} in date range {start}-{end}")
                
            return df_filtered
            
        except Exception as e:
            logger.error(f"Error fetching {ticker}: {e}")
            return pd.DataFrame()
    
    def fetch_prices_batch(self, tickers: List[str], start: str, end: str) -> Dict[str, pd.DataFrame]:
        """Batch fetch prices for multiple tickers using robust_data_fetcher"""
        result = {}
        uncached_tickers = []
        
        # Check local cache first
        for ticker in tickers:
            cache_key = f"{ticker}_{start}_{end}"
            if cache_key in self._local_cache:
                result[ticker] = self._local_cache[cache_key]
            else:
                uncached_tickers.append(ticker)
        
        # Batch download uncached using robust fetcher
        if uncached_tickers:
            try:
                # Calculate period based on date range
                start_dt = datetime.strptime(start, '%Y-%m-%d')
                end_dt = datetime.strptime(end, '%Y-%m-%d')
                days_diff = (end_dt - start_dt).days
                
                if days_diff <= 30:
                    period = "1mo"
                elif days_diff <= 90:
                    period = "3mo"
                elif days_diff <= 180:
                    period = "6mo"
                elif days_diff <= 365:
                    period = "1y"
                elif days_diff <= 730:
                    period = "2y"
                else:
                    period = "5y"
                
                # Use robust batch fetcher with rate limiting
                batch_data = rdf_get_batch(
                    uncached_tickers, 
                    period=period, 
                    batch_size=5, 
                    delay_between_batches=0.5
                )
                
                for ticker, df in batch_data.items():
                    if df is not None and not df.empty:
                        # Filter to date range
                        df_filtered = df[(df.index >= start_dt) & (df.index <= end_dt)]
                        if not df_filtered.empty:
                            result[ticker] = df_filtered
                            cache_key = f"{ticker}_{start}_{end}"
                            self._local_cache[cache_key] = df_filtered
                            
            except Exception as e:
                logger.error(f"Batch download error: {e}")
        
        return result
    
    def build_dataset(
        self,
        signals: List[Dict[str, Any]],
        labeling_method: Literal['binary', 'threshold', 'continuous', 'sharpe', 'stop_loss'] = 'binary',
        horizon: int = 5,
        threshold: float = 0.02,
        stop_loss: float = -0.05,
        take_profit: float = 0.10,
        feature_lags: List[int] = [1, 5, 20],
        include_market_context: bool = True
    ) -> Tuple[pd.DataFrame, pd.Series, pd.DataFrame]:
        """
        Build ML-ready dataset from signals.
        
        Args:
            signals: List of signal dicts with keys:
                - ticker: str
                - signal_date: str (YYYY-MM-DD)
                - signal_name: str
                - strategy: str (optional)
                - entry_price: float (optional, will be fetched if missing)
                - features: dict (optional, additional features)
            labeling_method: How to label outcomes
            horizon: Holding period in days
            threshold: For threshold labeling
            stop_loss: For stop_loss labeling
            take_profit: For stop_loss labeling
            feature_lags: Days to lag features
            include_market_context: Add market regime features
            
        Returns:
            X: Feature matrix (DataFrame)
            y: Labels (Series)
            metadata: Signal metadata for tracking (DataFrame)
        """
        rows = []
        labels = []
        metadata_rows = []
        
        # Get date range to fetch prices
        all_dates = [s.get('signal_date') for s in signals if s.get('signal_date')]
        if not all_dates:
            return pd.DataFrame(), pd.Series(), pd.DataFrame()
        
        min_date = min(all_dates)
        max_date = max(all_dates)
        
        # Extend range for features and outcomes
        start_date = (datetime.strptime(min_date, '%Y-%m-%d') - timedelta(days=max(feature_lags) + 30)).strftime('%Y-%m-%d')
        end_date = (datetime.strptime(max_date, '%Y-%m-%d') + timedelta(days=horizon + 30)).strftime('%Y-%m-%d')
        
        # Process each signal
        for signal in signals:
            try:
                ticker = signal.get('ticker')
                signal_date = signal.get('signal_date')
                
                if not ticker or not signal_date:
                    logger.debug(f"Skipping signal: missing ticker or date")
                    continue
                
                # Fetch price data
                prices = self.fetch_prices(ticker, start_date, end_date)
                logger.debug(f"Fetched {len(prices)} rows for {ticker}")
                if prices.empty:
                    logger.warning(f"Empty prices for {ticker}")
                    continue
                
                # Find signal date in data
                signal_dt = pd.Timestamp(signal_date)
                # Make timezone-naive for comparison
                if hasattr(signal_dt, 'tz') and signal_dt.tz is not None:
                    signal_dt = signal_dt.tz_localize(None)
                if hasattr(prices.index, 'tz') and prices.index.tz is not None:
                    prices.index = prices.index.tz_localize(None)
                
                if signal_dt not in prices.index:
                    # Find closest trading day
                    idx = prices.index.get_indexer([signal_dt], method='nearest')[0]
                    if idx < 0 or idx >= len(prices):
                        logger.debug(f"Signal date {signal_date} not in price range for {ticker}")
                        continue
                    signal_dt = prices.index[idx]
                
                signal_idx = prices.index.get_loc(signal_dt)
                logger.debug(f"Signal {ticker} at index {signal_idx}")
                    
                close_at_signal = prices.loc[signal_dt, 'Close']
                if pd.isna(close_at_signal):
                    continue
                     
                entry_price = signal.get('entry_price')
                if entry_price is None or pd.isna(entry_price):
                    entry_price = float(close_at_signal)
                
                # Validate entry price is a valid number
                if not isinstance(entry_price, (int, float)) or pd.isna(entry_price):
                    continue
                
                # Get prices after signal for labeling
                prices_after = prices['Close'].iloc[signal_idx + 1:]
                
                if len(prices_after) < horizon:
                    continue
                
                # Compute label
                label, actual_return, exit_reason = None, None, None
                
                if labeling_method == 'binary':
                    label, actual_return = LabelingStrategy.binary_fixed_horizon(
                        entry_price, prices_after, horizon
                    )
                elif labeling_method == 'threshold':
                    label, actual_return = LabelingStrategy.binary_threshold(
                        entry_price, prices_after, horizon, threshold
                    )
                elif labeling_method == 'continuous':
                    label, actual_return = LabelingStrategy.continuous_return(
                        entry_price, prices_after, horizon
                    )
                elif labeling_method == 'sharpe':
                    label, actual_return = LabelingStrategy.risk_adjusted_sharpe(
                        entry_price, prices_after, horizon
                    )
                elif labeling_method == 'stop_loss':
                    label, actual_return, exit_reason = LabelingStrategy.stop_loss_take_profit(
                        entry_price, prices_after, stop_loss, take_profit, horizon
                    )
                
                if label is None:
                    continue
                
                # Extract features (using data BEFORE signal date only - no leakage)
                features = self._extract_features(
                    prices, signal_idx, feature_lags, 
                    include_market_context, signal
                )
                
                if features is None:
                    continue
                
                rows.append(features)
                labels.append(label)
                
                # Metadata for tracking
                metadata_rows.append({
                    'signal_id': signal.get('signal_id', f"{ticker}_{signal_date}"),
                    'ticker': ticker,
                    'signal_date': signal_date,
                    'signal_name': signal.get('signal_name', 'unknown'),
                    'strategy': signal.get('strategy', 'unknown'),
                    'entry_price': entry_price,
                    'actual_return': actual_return,
                    'exit_reason': exit_reason,
                    'label': label
                })
                
            except Exception as e:
                logger.error(f"Error processing signal {signal}: {e}")
                continue
        
        if not rows:
            return pd.DataFrame(), pd.Series(), pd.DataFrame()
        
        X = pd.DataFrame(rows)
        y = pd.Series(labels, name='label')
        metadata = pd.DataFrame(metadata_rows)
        
        return X, y, metadata
    
    def _extract_features(
        self,
        prices: pd.DataFrame,
        signal_idx: int,
        feature_lags: List[int],
        include_market_context: bool,
        signal: Dict
    ) -> Optional[Dict[str, float]]:
        """
        Extract features from price data at signal time.
        Uses only data BEFORE signal date to prevent look-ahead bias.
        """
        features = {}
        
        # Need enough history for features
        max_lag = max(feature_lags) if feature_lags else 20
        if signal_idx < max_lag:
            logger.debug(f"Insufficient history: signal_idx={signal_idx}, need>={max_lag}")
            return None
        
        # Historical data up to signal date (exclusive - no leakage)
        hist = prices.iloc[:signal_idx]
        
        if len(hist) < 30:  # Relaxed from 60 to 30
            logger.debug(f"Insufficient hist length: {len(hist)}")
            return None
        
        close = hist['Close']
        high = hist['High'] if 'High' in hist else close
        low = hist['Low'] if 'Low' in hist else close
        volume = hist['Volume'] if 'Volume' in hist else pd.Series([1] * len(close))
        
        # Returns
        returns = close.pct_change()
        
        # Feature extraction for each lag
        for lag in feature_lags:
            if lag > len(close):
                continue
            
            # Return over lag period
            features[f'return_{lag}d'] = (close.iloc[-1] - close.iloc[-lag]) / close.iloc[-lag]
            
            # Volatility over lag period
            features[f'volatility_{lag}d'] = returns.tail(lag).std() * np.sqrt(252)
            
            # RSI approximation
            gains = returns.tail(lag).clip(lower=0).mean()
            losses = (-returns.tail(lag).clip(upper=0)).mean()
            if losses > 0:
                rs = gains / losses
                features[f'rsi_{lag}d'] = 100 - (100 / (1 + rs))
            else:
                features[f'rsi_{lag}d'] = 100
            
            # Moving average distance
            ma = close.tail(lag).mean()
            features[f'ma_dist_{lag}d'] = (close.iloc[-1] - ma) / ma
            
            # Volume ratio
            avg_vol = volume.tail(lag).mean()
            if avg_vol > 0:
                features[f'vol_ratio_{lag}d'] = volume.iloc[-1] / avg_vol
            else:
                features[f'vol_ratio_{lag}d'] = 1.0
        
        # Technical indicators (using most recent data)
        # Bollinger Band position
        bb_period = 20
        if len(close) >= bb_period:
            ma20 = close.tail(bb_period).mean()
            std20 = close.tail(bb_period).std()
            if std20 > 0:
                features['bb_position'] = (close.iloc[-1] - ma20) / (2 * std20)
            else:
                features['bb_position'] = 0
        
        # ATR (normalized)
        if len(high) >= 14:
            tr = pd.concat([
                high.tail(14) - low.tail(14),
                abs(high.tail(14) - close.shift(1).tail(14)),
                abs(low.tail(14) - close.shift(1).tail(14))
            ], axis=1).max(axis=1)
            atr = tr.mean()
            features['atr_normalized'] = atr / close.iloc[-1] if close.iloc[-1] > 0 else 0
        
        # Momentum
        if len(close) >= 10:
            features['momentum_10d'] = close.iloc[-1] - close.iloc[-10]
        
        # Trend strength (price above/below various MAs)
        for period in [10, 20, 50]:
            if len(close) >= period:
                ma = close.tail(period).mean()
                features[f'above_ma{period}'] = 1 if close.iloc[-1] > ma else 0
        
        # Volume trend
        if len(volume) >= 20:
            vol_ma = volume.tail(20).mean()
            if vol_ma > 0:
                features['volume_trend'] = volume.tail(5).mean() / vol_ma
            else:
                features['volume_trend'] = 1.0
        
        # Add any custom features from signal
        if signal.get('features'):
            features.update(signal['features'])
        
        # Market context features
        if include_market_context:
            # These would typically come from regime detection
            # For now, add volatility regime proxy
            if len(returns) >= 60:
                current_vol = returns.tail(20).std() * np.sqrt(252)
                historical_vol = returns.tail(60).std() * np.sqrt(252)
                if historical_vol > 0:
                    features['vol_regime'] = current_vol / historical_vol
                else:
                    features['vol_regime'] = 1.0
        
        return features
    
    def get_dataset_stats(
        self,
        X: pd.DataFrame,
        y: pd.Series,
        metadata: pd.DataFrame
    ) -> Dict[str, Any]:
        """Get statistics about the built dataset"""
        if X.empty:
            return {'error': 'Empty dataset'}
        
        stats = {
            'total_signals': len(y),
            'positive_labels': int((y == 1).sum()) if y.dtype != float else int((y > 0).sum()),
            'negative_labels': int((y == 0).sum()) if y.dtype != float else int((y <= 0).sum()),
            'label_balance': float((y == 1).mean()) if y.dtype != float else float((y > 0).mean()),
            'feature_count': len(X.columns),
            'features': list(X.columns),
            'missing_data': {
                col: float(X[col].isna().mean()) 
                for col in X.columns
            },
            'date_range': {
                'start': metadata['signal_date'].min() if 'signal_date' in metadata else None,
                'end': metadata['signal_date'].max() if 'signal_date' in metadata else None
            },
            'tickers': list(metadata['ticker'].unique()) if 'ticker' in metadata else [],
            'strategies': list(metadata['strategy'].unique()) if 'strategy' in metadata else []
        }
        
        return stats
    
    def get_missing_data_heatmap(self, X: pd.DataFrame) -> Dict[str, Any]:
        """Generate missing data heatmap data"""
        missing = X.isna()
        
        # Summarize by feature
        feature_missing = {
            col: {
                'missing_pct': float(missing[col].mean() * 100),
                'missing_count': int(missing[col].sum()),
                'total': len(X)
            }
            for col in X.columns
        }
        
        # Sample of missing pattern (first 100 rows)
        sample_size = min(100, len(X))
        heatmap_data = missing.iloc[:sample_size].values.tolist()
        
        return {
            'features': list(X.columns),
            'feature_stats': feature_missing,
            'heatmap_sample': heatmap_data,
            'sample_size': sample_size
        }
    
    def version_dataset(
        self,
        X: pd.DataFrame,
        y: pd.Series,
        metadata: pd.DataFrame,
        name: str
    ) -> str:
        """Create a versioned snapshot of the dataset"""
        # Create hash of dataset
        content = f"{X.to_json()}{y.to_json()}{metadata.to_json()}"
        version_hash = hashlib.md5(content.encode()).hexdigest()[:8]
        
        version_info = {
            'name': name,
            'hash': version_hash,
            'created_at': datetime.now().isoformat(),
            'stats': self.get_dataset_stats(X, y, metadata)
        }
        
        return f"{name}_v{version_hash}"


# =============================================================================
# CONVENIENCE FUNCTIONS
# =============================================================================

def build_signal_dataset(
    signals: List[Dict],
    labeling_method: str = 'binary',
    horizon: int = 5,
    **kwargs
) -> Tuple[pd.DataFrame, pd.Series, pd.DataFrame]:
    """Convenience function for building datasets"""
    builder = DatasetBuilder()
    return builder.build_dataset(signals, labeling_method, horizon, **kwargs)


def get_dataset_overview(X: pd.DataFrame, y: pd.Series, metadata: pd.DataFrame) -> Dict:
    """Get comprehensive dataset overview"""
    builder = DatasetBuilder()
    stats = builder.get_dataset_stats(X, y, metadata)
    missing = builder.get_missing_data_heatmap(X)
    
    return {
        'stats': stats,
        'missing_data': missing,
        'label_distribution': {
            'bins': [0, 0.1, 0.2, 0.3, 0.4, 0.5, 0.6, 0.7, 0.8, 0.9, 1.0],
            'counts': np.histogram(y, bins=10)[0].tolist() if len(y) > 0 else []
        }
    }
