"""
Labs → ML → Conditional Performance Analyzer (Module 4)
=======================================================
Understand when and why signals work—break down performance by market regime,
volatility, sector rotation, and other conditions.

Responsibilities:
- Group historical signals by contextual variables
- Calculate performance metrics within each group
- Identify conditions where signals consistently outperform/underperform
- Provide "performance fingerprint" for each signal type
"""

import pandas as pd
import numpy as np
from typing import Dict, List, Any, Optional, Tuple
from datetime import datetime
import logging

logger = logging.getLogger(__name__)


# =============================================================================
# CONDITIONAL PERFORMANCE ANALYZER
# =============================================================================

class ConditionalAnalyzer:
    """
    Conditional Performance Analyzer
    
    Breaks down signal performance by market conditions to understand
    when and why signals work or fail.
    """
    
    # Default condition categories
    REGIME_CATEGORIES = ['Bull', 'Bear', 'Neutral', 'Volatile']
    VOLATILITY_CATEGORIES = ['Low', 'Medium', 'High', 'Extreme']
    
    def __init__(self):
        self.performance_cache: Dict[str, Any] = {}
        self.analysis_results: Dict[str, Any] = {}
    
    def analyze_by_conditions(
        self,
        signals_df: pd.DataFrame,
        outcomes: pd.Series,
        regime_labels: pd.Series = None,
        volatility_labels: pd.Series = None
    ) -> Dict[str, Any]:
        """
        Analyze signal performance broken down by market conditions.
        
        Args:
            signals_df: DataFrame with signal metadata (signal_name, strategy, etc.)
            outcomes: Series of returns or binary outcomes for each signal
            regime_labels: Optional market regime at time of each signal
            volatility_labels: Optional volatility state at time of each signal
            
        Returns:
            Comprehensive conditional performance analysis
        """
        if len(signals_df) == 0:
            return {'error': 'No signals provided'}
        
        # Combine into analysis DataFrame
        df = signals_df.copy()
        df['outcome'] = outcomes.values if hasattr(outcomes, 'values') else outcomes
        df['win'] = df['outcome'] > 0
        
        # Add condition labels if provided
        if regime_labels is not None:
            df['regime'] = regime_labels.values if hasattr(regime_labels, 'values') else regime_labels
        else:
            # Generate synthetic regime based on outcome patterns
            df['regime'] = self._infer_regime(df)
        
        if volatility_labels is not None:
            df['volatility'] = volatility_labels.values if hasattr(volatility_labels, 'values') else volatility_labels
        else:
            # Generate volatility buckets from returns
            df['volatility'] = self._infer_volatility(df)
        
        # Calculate overall stats
        overall_stats = self._calculate_overall_stats(df)
        
        # Calculate conditional returns matrix
        regime_return_matrix = self._calculate_regime_returns(df)
        
        # Calculate win rate by condition
        win_rate_by_condition = self._calculate_win_rates(df)
        
        # Identify best and worst conditions
        best_worst = self._identify_best_worst_conditions(df)
        
        # Signal performance fingerprints
        signal_fingerprints = self._create_signal_fingerprints(df)
        
        self.analysis_results = {
            'overall_stats': overall_stats,
            'regime_return_matrix': regime_return_matrix,
            'win_rate_by_condition': win_rate_by_condition,
            'best_worst_conditions': best_worst,
            'signal_fingerprints': signal_fingerprints,
            'sample_size': len(df),
            'analyzed_at': datetime.now().isoformat()
        }
        
        return self.analysis_results
    
    def _infer_regime(self, df: pd.DataFrame) -> pd.Series:
        """Infer regime from return patterns"""
        outcomes = df['outcome']
        rolling_mean = outcomes.rolling(window=20, min_periods=5).mean()
        rolling_std = outcomes.rolling(window=20, min_periods=5).std()
        
        def categorize(idx):
            if pd.isna(rolling_mean.iloc[idx]):
                return 'Neutral'
            mean = rolling_mean.iloc[idx]
            std = rolling_std.iloc[idx]
            
            if std > outcomes.std() * 1.5:
                return 'Volatile'
            elif mean > 0.01:
                return 'Bull'
            elif mean < -0.01:
                return 'Bear'
            else:
                return 'Neutral'
        
        return pd.Series([categorize(i) for i in range(len(df))])
    
    def _infer_volatility(self, df: pd.DataFrame) -> pd.Series:
        """Infer volatility bucket from absolute returns"""
        abs_outcomes = df['outcome'].abs()
        quartiles = abs_outcomes.quantile([0.25, 0.5, 0.75])
        
        def categorize(val):
            if pd.isna(val):
                return 'Medium'
            if val <= quartiles.iloc[0]:
                return 'Low'
            elif val <= quartiles.iloc[1]:
                return 'Medium'
            elif val <= quartiles.iloc[2]:
                return 'High'
            else:
                return 'Extreme'
        
        return abs_outcomes.apply(categorize)
    
    def _calculate_overall_stats(self, df: pd.DataFrame) -> Dict[str, Any]:
        """Calculate overall performance statistics"""
        return {
            'total_signals': len(df),
            'win_rate': float(df['win'].mean()),
            'avg_return': float(df['outcome'].mean()),
            'median_return': float(df['outcome'].median()),
            'std_return': float(df['outcome'].std()),
            'sharpe_approx': float(df['outcome'].mean() / df['outcome'].std() * np.sqrt(252)) if df['outcome'].std() > 0 else 0,
            'max_gain': float(df['outcome'].max()),
            'max_loss': float(df['outcome'].min()),
            'positive_signals': int(df['win'].sum()),
            'negative_signals': int((~df['win']).sum())
        }
    
    def _calculate_regime_returns(self, df: pd.DataFrame) -> Dict[str, Any]:
        """Calculate returns matrix by regime and volatility"""
        # Regime vs Volatility matrix
        matrix = {}
        
        for regime in df['regime'].unique():
            matrix[regime] = {}
            regime_mask = df['regime'] == regime
            
            for vol in df['volatility'].unique():
                vol_mask = df['volatility'] == vol
                combined_mask = regime_mask & vol_mask
                
                subset = df[combined_mask]
                if len(subset) > 0:
                    matrix[regime][vol] = {
                        'avg_return': float(subset['outcome'].mean()),
                        'win_rate': float(subset['win'].mean()),
                        'sample_size': len(subset),
                        'std_return': float(subset['outcome'].std()),
                        'sharpe': float(subset['outcome'].mean() / subset['outcome'].std() * np.sqrt(252)) if subset['outcome'].std() > 0 else 0
                    }
                else:
                    matrix[regime][vol] = None
        
        return matrix
    
    def _calculate_win_rates(self, df: pd.DataFrame) -> Dict[str, Any]:
        """Calculate win rates by various conditions"""
        result = {
            'by_regime': {},
            'by_volatility': {},
            'by_strategy': {},
            'by_signal_name': {}
        }
        
        # By regime
        for regime in df['regime'].unique():
            subset = df[df['regime'] == regime]
            result['by_regime'][regime] = {
                'win_rate': float(subset['win'].mean()),
                'avg_return': float(subset['outcome'].mean()),
                'sample_size': len(subset)
            }
        
        # By volatility
        for vol in df['volatility'].unique():
            subset = df[df['volatility'] == vol]
            result['by_volatility'][vol] = {
                'win_rate': float(subset['win'].mean()),
                'avg_return': float(subset['outcome'].mean()),
                'sample_size': len(subset)
            }
        
        # By strategy (if available)
        if 'strategy' in df.columns:
            for strategy in df['strategy'].unique():
                subset = df[df['strategy'] == strategy]
                if len(subset) >= 5:
                    result['by_strategy'][strategy] = {
                        'win_rate': float(subset['win'].mean()),
                        'avg_return': float(subset['outcome'].mean()),
                        'sample_size': len(subset)
                    }
        
        # By signal name (if available)
        if 'signal_name' in df.columns:
            for signal in df['signal_name'].unique():
                subset = df[df['signal_name'] == signal]
                if len(subset) >= 5:
                    result['by_signal_name'][signal] = {
                        'win_rate': float(subset['win'].mean()),
                        'avg_return': float(subset['outcome'].mean()),
                        'sample_size': len(subset)
                    }
        
        return result
    
    def _identify_best_worst_conditions(self, df: pd.DataFrame) -> Dict[str, Any]:
        """Identify best and worst performing conditions"""
        conditions = []
        
        for regime in df['regime'].unique():
            for vol in df['volatility'].unique():
                mask = (df['regime'] == regime) & (df['volatility'] == vol)
                subset = df[mask]
                
                if len(subset) >= 10:  # Minimum sample size
                    conditions.append({
                        'condition': f"{regime} + {vol} Vol",
                        'regime': regime,
                        'volatility': vol,
                        'win_rate': float(subset['win'].mean()),
                        'avg_return': float(subset['outcome'].mean()),
                        'sample_size': len(subset)
                    })
        
        if not conditions:
            return {'best': [], 'worst': []}
        
        # Sort by win rate
        sorted_by_win = sorted(conditions, key=lambda x: x['win_rate'], reverse=True)
        
        # Sort by return
        sorted_by_return = sorted(conditions, key=lambda x: x['avg_return'], reverse=True)
        
        return {
            'best_by_win_rate': sorted_by_win[:3],
            'worst_by_win_rate': sorted_by_win[-3:],
            'best_by_return': sorted_by_return[:3],
            'worst_by_return': sorted_by_return[-3:],
            'all_conditions': conditions
        }
    
    def _create_signal_fingerprints(self, df: pd.DataFrame) -> Dict[str, Any]:
        """Create performance fingerprint for each signal type"""
        fingerprints = {}
        
        signal_col = 'signal_name' if 'signal_name' in df.columns else 'strategy' if 'strategy' in df.columns else None
        
        if signal_col is None:
            return fingerprints
        
        for signal in df[signal_col].unique():
            signal_df = df[df[signal_col] == signal]
            
            if len(signal_df) < 10:
                continue
            
            # Performance by regime
            regime_perf = {}
            for regime in signal_df['regime'].unique():
                subset = signal_df[signal_df['regime'] == regime]
                if len(subset) >= 3:
                    regime_perf[regime] = {
                        'win_rate': float(subset['win'].mean()),
                        'avg_return': float(subset['outcome'].mean()),
                        'sample_size': len(subset)
                    }
            
            # Find best regime for this signal
            best_regime = max(regime_perf.items(), key=lambda x: x[1]['win_rate'])[0] if regime_perf else None
            worst_regime = min(regime_perf.items(), key=lambda x: x[1]['win_rate'])[0] if regime_perf else None
            
            fingerprints[signal] = {
                'total_signals': len(signal_df),
                'overall_win_rate': float(signal_df['win'].mean()),
                'overall_avg_return': float(signal_df['outcome'].mean()),
                'by_regime': regime_perf,
                'best_regime': best_regime,
                'worst_regime': worst_regime,
                'consistency_score': float(1 - signal_df['outcome'].std() / (abs(signal_df['outcome'].mean()) + 0.001))
            }
        
        return fingerprints
    
    def get_heatmap_data(self) -> Dict[str, Any]:
        """Get data formatted for regime vs return heatmap visualization"""
        if not self.analysis_results:
            return {'error': 'Run analysis first'}
        
        matrix = self.analysis_results.get('regime_return_matrix', {})
        
        regimes = list(matrix.keys())
        volatilities = set()
        for regime_data in matrix.values():
            volatilities.update(regime_data.keys())
        volatilities = list(volatilities)
        
        # Create heatmap grid
        heatmap_data = []
        for regime in regimes:
            row = []
            for vol in volatilities:
                cell = matrix.get(regime, {}).get(vol)
                if cell:
                    row.append({
                        'value': cell['avg_return'],
                        'win_rate': cell['win_rate'],
                        'sample_size': cell['sample_size']
                    })
                else:
                    row.append(None)
            heatmap_data.append(row)
        
        return {
            'regimes': regimes,
            'volatilities': volatilities,
            'data': heatmap_data,
            'value_type': 'avg_return'
        }
    
    def get_drawdown_by_condition(self, df: pd.DataFrame) -> Dict[str, Any]:
        """Calculate drawdowns for each condition"""
        drawdowns = {}
        
        for regime in df['regime'].unique():
            regime_df = df[df['regime'] == regime].sort_index()
            
            if len(regime_df) < 5:
                continue
            
            # Calculate cumulative returns
            cumulative = (1 + regime_df['outcome']).cumprod()
            running_max = cumulative.expanding().max()
            drawdown_series = (cumulative - running_max) / running_max
            
            drawdowns[regime] = {
                'max_drawdown': float(drawdown_series.min()),
                'avg_drawdown': float(drawdown_series.mean()),
                'current_drawdown': float(drawdown_series.iloc[-1]) if len(drawdown_series) > 0 else 0,
                'equity_curve': cumulative.tolist()[-50:],  # Last 50 points
                'drawdown_curve': drawdown_series.tolist()[-50:]
            }
        
        return drawdowns


# =============================================================================
# CONVENIENCE FUNCTIONS
# =============================================================================

def analyze_conditional_performance(
    signals_df: pd.DataFrame,
    outcomes: pd.Series,
    regime_labels: pd.Series = None,
    volatility_labels: pd.Series = None
) -> Tuple[ConditionalAnalyzer, Dict]:
    """Convenience function for conditional analysis"""
    analyzer = ConditionalAnalyzer()
    results = analyzer.analyze_by_conditions(
        signals_df, outcomes, regime_labels, volatility_labels
    )
    return analyzer, results


def get_performance_heatmap(analyzer: ConditionalAnalyzer) -> Dict:
    """Get heatmap data from analyzer"""
    return analyzer.get_heatmap_data()
