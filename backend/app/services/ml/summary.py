"""
Labs → ML → Summary
====================
Signal Quality Scorecard & Position Sizing

Responsibilities:
- Aggregate metrics into composite scores
- Signal quality ranking
- ML-driven position sizing with Kelly criterion
- Portfolio-level recommendations
"""

import pandas as pd
import numpy as np
from typing import Dict, List, Any, Optional, Tuple
from datetime import datetime
import logging

logger = logging.getLogger(__name__)


# =============================================================================
# DEFAULT SCORING WEIGHTS
# =============================================================================

DEFAULT_SCORE_WEIGHTS = {
    'ml_probability': 0.25,      # ML model predicted probability
    'historical_win_rate': 0.20, # Historical win rate of this signal type
    'sharpe_ratio': 0.15,        # Expected Sharpe if trade executed
    'regime_fit': 0.15,          # How well signal fits current regime
    'model_confidence': 0.10,    # Ensemble agreement/confidence
    'momentum_score': 0.10,      # Recent price momentum
    'volume_score': 0.05         # Volume confirmation
}


class SummaryEngine:
    """
    Signal Quality Scorecard & Position Sizing Advisor
    
    Aggregates ML insights into actionable scores and sizing recommendations.
    """
    
    def __init__(self, weights: Dict[str, float] = None):
        self.weights = weights or DEFAULT_SCORE_WEIGHTS.copy()
        self.signal_scores: Dict[str, Dict] = {}
        
    def compute_signal_score(
        self,
        signal: Dict[str, Any],
        normalize: bool = True
    ) -> Dict[str, Any]:
        """
        Compute composite quality score for a single signal.
        
        Args:
            signal: Dict containing signal metrics:
                - ml_probability: float (0-1)
                - historical_win_rate: float (0-1)
                - sharpe_ratio: float (-3 to 3 typically)
                - regime_fit: float (0-1)
                - model_confidence: float (0-1)
                - momentum_score: float (-1 to 1)
                - volume_score: float (0-2 typically)
            normalize: Whether to normalize each component to 0-1
            
        Returns:
            Score breakdown and composite score
        """
        breakdown = {}
        total_weight = 0
        weighted_sum = 0
        
        for metric, weight in self.weights.items():
            value = signal.get(metric)
            
            if value is None:
                continue
            
            # Normalize to 0-1 range
            if normalize:
                if metric in ['ml_probability', 'historical_win_rate', 'regime_fit', 'model_confidence']:
                    norm_value = np.clip(value, 0, 1)
                elif metric == 'sharpe_ratio':
                    # Sharpe typically -3 to 3, normalize to 0-1
                    norm_value = np.clip((value + 3) / 6, 0, 1)
                elif metric == 'momentum_score':
                    # Momentum -1 to 1, normalize to 0-1
                    norm_value = np.clip((value + 1) / 2, 0, 1)
                elif metric == 'volume_score':
                    # Volume ratio 0 to 2+, normalize to 0-1
                    norm_value = np.clip(value / 2, 0, 1)
                else:
                    norm_value = np.clip(value, 0, 1)
            else:
                norm_value = value
            
            breakdown[metric] = {
                'raw_value': float(value),
                'normalized': float(norm_value),
                'weight': float(weight),
                'contribution': float(norm_value * weight)
            }
            
            weighted_sum += norm_value * weight
            total_weight += weight
        
        # Compute final score
        if total_weight > 0:
            composite_score = weighted_sum / total_weight
        else:
            composite_score = 0.5
        
        # Determine tier
        if composite_score >= 0.7:
            tier = 'A'
        elif composite_score >= 0.55:
            tier = 'B'
        elif composite_score >= 0.4:
            tier = 'C'
        else:
            tier = 'D'
        
        return {
            'composite_score': float(composite_score),
            'tier': tier,
            'breakdown': breakdown,
            'metrics_used': len(breakdown),
            'total_weight': float(total_weight)
        }
    
    def rank_signals(
        self,
        signals: List[Dict[str, Any]],
        top_n: int = None
    ) -> Dict[str, Any]:
        """
        Rank multiple signals by quality score.
        
        Returns ranked list with scores and tiers.
        """
        scored_signals = []
        
        for i, signal in enumerate(signals):
            score_result = self.compute_signal_score(signal)
            
            scored_signals.append({
                'signal_id': signal.get('signal_id', f'signal_{i}'),
                'ticker': signal.get('ticker', 'UNKNOWN'),
                'signal_name': signal.get('signal_name', 'Unknown'),
                'composite_score': score_result['composite_score'],
                'tier': score_result['tier'],
                'breakdown': score_result['breakdown']
            })
        
        # Sort by score
        scored_signals.sort(key=lambda x: x['composite_score'], reverse=True)
        
        # Apply ranking
        for rank, signal in enumerate(scored_signals):
            signal['rank'] = rank + 1
        
        if top_n:
            scored_signals = scored_signals[:top_n]
        
        # Tier distribution
        tier_counts = {}
        for s in scored_signals:
            tier_counts[s['tier']] = tier_counts.get(s['tier'], 0) + 1
        
        return {
            'ranked_signals': scored_signals,
            'total_signals': len(signals),
            'returned_signals': len(scored_signals),
            'tier_distribution': tier_counts,
            'avg_score': float(np.mean([s['composite_score'] for s in scored_signals]))
        }
    
    def compute_kelly_size(
        self,
        win_probability: float,
        avg_win: float,
        avg_loss: float,
        fraction: float = 0.5
    ) -> Dict[str, Any]:
        """
        Compute Kelly Criterion position size.
        
        Args:
            win_probability: Probability of winning (0-1)
            avg_win: Average gain on winning trades
            avg_loss: Average loss on losing trades (positive number)
            fraction: Kelly fraction to use (0.5 = half-Kelly)
            
        Returns:
            Position sizing recommendation
        """
        if avg_loss == 0:
            return {'error': 'Average loss cannot be zero'}
        
        # Kelly formula: f = (bp - q) / b
        # where b = win/loss ratio, p = win prob, q = loss prob
        b = avg_win / avg_loss
        p = win_probability
        q = 1 - p
        
        kelly_pct = (b * p - q) / b
        
        # Apply fraction
        recommended_pct = kelly_pct * fraction
        
        # Cap at reasonable levels
        recommended_pct = np.clip(recommended_pct, 0, 0.25)  # Max 25%
        
        return {
            'full_kelly_pct': float(kelly_pct * 100),
            'fractional_kelly_pct': float(recommended_pct * 100),
            'fraction_used': fraction,
            'win_probability': float(win_probability),
            'win_loss_ratio': float(b),
            'recommendation': 'AGGRESSIVE' if recommended_pct > 0.15 else 'MODERATE' if recommended_pct > 0.05 else 'CONSERVATIVE'
        }
    
    def compute_position_size(
        self,
        signal: Dict[str, Any],
        portfolio_value: float,
        risk_per_trade: float = 0.02,
        max_position_pct: float = 0.10
    ) -> Dict[str, Any]:
        """
        Compute recommended position size based on ML metrics.
        
        Args:
            signal: Signal dict with ML probability and other metrics
            portfolio_value: Total portfolio value
            risk_per_trade: Max risk per trade as fraction (0.02 = 2%)
            max_position_pct: Max position size as fraction of portfolio (0.10 = 10%)
            
        Returns:
            Position sizing recommendation
        """
        # Get score
        score_result = self.compute_signal_score(signal)
        composite_score = score_result['composite_score']
        
        # Base position size from risk budget
        base_size_pct = risk_per_trade
        
        # Scale by confidence score (capped multiplier)
        # Higher score = slightly larger position (within limits)
        confidence_multiplier = 0.8 + (composite_score * 0.4)  # Range: 0.8 to 1.2
        
        # Adjust for regime fit if available (capped)
        regime_fit = signal.get('regime_fit', 0.5)
        regime_multiplier = 0.9 + 0.2 * regime_fit  # Range: 0.9 to 1.1
        
        # Adjust for model agreement (capped)
        model_confidence = signal.get('model_confidence', 0.5)
        agreement_multiplier = 0.9 + 0.2 * model_confidence  # Range: 0.9 to 1.1
        
        # Calculate final position size
        total_multiplier = confidence_multiplier * regime_multiplier * agreement_multiplier
        # Cap total multiplier to prevent runaway position sizes
        total_multiplier = min(total_multiplier, 1.5)
        
        adjusted_size_pct = base_size_pct * total_multiplier
        
        # Apply max constraint
        final_size_pct = min(adjusted_size_pct, max_position_pct)
        
        # Dollar values
        position_value = portfolio_value * final_size_pct
        
        # Stop loss suggestion based on volatility
        atr_normalized = signal.get('atr_normalized', 0.02)
        suggested_stop_pct = min(atr_normalized * 2, 0.08)  # Max 8% stop
        
        return {
            'position_size_pct': float(final_size_pct * 100),  # Convert to percentage for display
            'position_value': float(position_value),
            'base_risk_pct': float(risk_per_trade * 100),
            'adjustments': {
                'confidence_multiplier': float(confidence_multiplier),
                'regime_multiplier': float(regime_multiplier),
                'agreement_multiplier': float(agreement_multiplier),
                'total_multiplier': float(total_multiplier)
            },
            'suggested_stop_pct': float(suggested_stop_pct * 100),
            'max_loss': float(position_value * suggested_stop_pct),
            'signal_tier': score_result['tier'],
            'composite_score': float(composite_score)
        }
    
    def get_portfolio_allocation(
        self,
        signals: List[Dict[str, Any]],
        portfolio_value: float,
        max_total_exposure: float = 0.80,
        max_per_position: float = 0.10
    ) -> Dict[str, Any]:
        """
        Get optimal allocation across multiple signals.
        
        Considers:
        - Signal quality scores
        - Correlation between positions
        - Total exposure limits
        """
        # Rank signals
        ranked = self.rank_signals(signals)
        
        allocations = []
        total_allocated = 0
        
        for signal_data in ranked['ranked_signals']:
            if total_allocated >= max_total_exposure:
                break
            
            # Find original signal
            original = next(
                (s for s in signals if s.get('signal_id') == signal_data['signal_id']), 
                {}
            )
            
            # Base allocation from score
            score = signal_data['composite_score']
            base_alloc = score * max_per_position
            
            # Apply tier discount
            tier_multiplier = {'A': 1.0, 'B': 0.8, 'C': 0.6, 'D': 0.4}.get(signal_data['tier'], 0.5)
            adjusted_alloc = base_alloc * tier_multiplier
            
            # Ensure we don't exceed limits
            remaining = max_total_exposure - total_allocated
            final_alloc = min(adjusted_alloc, remaining, max_per_position)
            
            if final_alloc > 0.01:  # Min 1% to include
                allocations.append({
                    'signal_id': signal_data['signal_id'],
                    'ticker': signal_data['ticker'],
                    'allocation_pct': float(final_alloc * 100),
                    'allocation_value': float(portfolio_value * final_alloc),
                    'tier': signal_data['tier'],
                    'score': signal_data['composite_score']
                })
                total_allocated += final_alloc
        
        return {
            'allocations': allocations,
            'total_allocated_pct': float(total_allocated * 100),
            'cash_pct': float((1 - total_allocated) * 100),
            'n_positions': len(allocations),
            'portfolio_value': float(portfolio_value)
        }
    
    def run_stress_scenarios(
        self,
        position_value: float,
        scenarios: List[str] = None
    ) -> Dict[str, Any]:
        """
        Run stress test scenarios on position.
        """
        if scenarios is None:
            scenarios = ['crash', 'volatility_spike', 'sector_rotation', 'flash_crash']
        
        results = {}
        
        scenario_impacts = {
            'crash': {'return': -0.20, 'description': '20% market crash'},
            'volatility_spike': {'return': -0.10, 'description': 'VIX spike to 40'},
            'sector_rotation': {'return': -0.08, 'description': 'Sector rotation out'},
            'flash_crash': {'return': -0.15, 'description': 'Flash crash event'},
            'fed_surprise': {'return': -0.05, 'description': 'Surprise rate hike'},
            'earnings_miss': {'return': -0.12, 'description': 'Major earnings miss'}
        }
        
        for scenario in scenarios:
            if scenario in scenario_impacts:
                impact = scenario_impacts[scenario]
                loss = position_value * impact['return']
                
                results[scenario] = {
                    'description': impact['description'],
                    'expected_return_pct': float(impact['return'] * 100),
                    'expected_loss': float(abs(loss)),
                    'position_value_after': float(position_value + loss)
                }
        
        # Summary
        worst_case = min(results.values(), key=lambda x: x['expected_return_pct'])
        
        return {
            'scenarios': results,
            'worst_case_scenario': worst_case,
            'original_position': float(position_value)
        }
    
    def get_scorecard_summary(
        self,
        signals: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """
        Get executive summary of all signals.
        """
        if not signals:
            return {'error': 'No signals provided'}
        
        ranked = self.rank_signals(signals)
        
        # Top performers
        top_5 = ranked['ranked_signals'][:5]
        
        # Score distribution
        scores = [s['composite_score'] for s in ranked['ranked_signals']]
        
        return {
            'total_signals': len(signals),
            'avg_score': ranked['avg_score'],
            'tier_distribution': ranked['tier_distribution'],
            'top_5_signals': top_5,
            'score_stats': {
                'min': float(min(scores)),
                'max': float(max(scores)),
                'median': float(np.median(scores)),
                'std': float(np.std(scores))
            },
            'actionable_signals': len([s for s in ranked['ranked_signals'] if s['tier'] in ['A', 'B']])
        }
    
    def update_weights(self, new_weights: Dict[str, float]):
        """Update scoring weights"""
        self.weights.update(new_weights)
        # Normalize to sum to 1
        total = sum(self.weights.values())
        self.weights = {k: v/total for k, v in self.weights.items()}


# =============================================================================
# CONVENIENCE FUNCTIONS
# =============================================================================

def score_signals(
    signals: List[Dict],
    weights: Dict[str, float] = None
) -> Dict:
    """Convenience function to score signals"""
    engine = SummaryEngine(weights)
    return engine.rank_signals(signals)


def compute_position_sizing(
    signal: Dict,
    portfolio_value: float,
    risk_pct: float = 0.02
) -> Dict:
    """Convenience function for position sizing"""
    engine = SummaryEngine()
    return engine.compute_position_size(signal, portfolio_value, risk_pct)
