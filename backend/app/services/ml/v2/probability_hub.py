import numpy as np
import polars as pl
import logging
from arch import arch_model
from typing import Dict, List, Any, Optional

logger = logging.getLogger(__name__)

class MonteCarloSimulator:
    def __init__(self, n_simulations=50000, horizon=30):
        self.n_sims = n_simulations
        self.horizon = horizon

    def simulate_paths(self, returns: np.ndarray, current_price: float = 100.0) -> Dict[str, Any]:
        """
        GARCH(1,1) volatility + 50,000 path simulation with real-world drift.
        """
        try:
            # Fit GARCH for volatility clustering capture
            # Scaling returns by 100 ensures numerical stability for solver
            rescaled_returns = returns * 100
            model = arch_model(rescaled_returns, vol='Garch', p=1, q=1)
            fitted = model.fit(disp='off')

            # Forecast volatility forward
            forecast = fitted.forecast(horizon=self.horizon)
            vols = np.sqrt(forecast.variance.values[-1]) / 100.0 # Re-scale to return units

            # Simulation parameters
            S0 = current_price
            mu = np.mean(returns)
            
            # Vectorized high-speed simulation
            shocks = np.random.normal(mu, vols, (self.n_sims, self.horizon))
            
            # Price path evolution: S_t = S_0 * exp(sum(r_i))
            cum_shocks = np.cumsum(shocks, axis=1)
            paths = S0 * np.exp(cum_shocks)
            
            terminal_prices = paths[:, -1]

            # Strategic sampling for frontend 3D rendering (keep payload lean)
            sample_rate = max(1, self.n_sims // 100)
            sampled_paths = paths[::sample_rate].tolist()

            return {
                'simulated_paths': sampled_paths,
                'current_price': float(S0),
                'horizon': int(self.horizon),
                'percentiles': {
                    'p5': float(np.percentile(terminal_prices, 5)),
                    'p25': float(np.percentile(terminal_prices, 25)),
                    'p50': float(np.percentile(terminal_prices, 50)),
                    'p75': float(np.percentile(terminal_prices, 75)),
                    'p95': float(np.percentile(terminal_prices, 95))
                },
                'terminal_distribution': np.histogram(terminal_prices, bins=50)[0].tolist(),
                'prob_profit': float(np.sum(terminal_prices > S0) / self.n_sims * 100)
            }
        except Exception as e:
            logger.error(f"Error in MonteCarloSimulator simulation: {e}")
            return {"error": str(e)}

class LiquidityCanyonAnalyzer:
    def __init__(self, price_levels=100):
        self.price_levels = price_levels

    def analyze_volume_profile(self, df_dict: List[Dict]) -> Dict[str, Any]:
        """
        High-speed volume clustering using Polars
        """
        try:
            df = pl.DataFrame(df_dict)
            
            p_min = df['Low'].min()
            p_max = df['High'].max()
            p_step = (p_max - p_min) / self.price_levels if p_max > p_min else 1.0

            buckets = []
            for i in range(self.price_levels):
                p_level = p_min + i * p_step
                
                # Volume at level: sum of volume where price was in the High-Low range
                vol = df.filter(
                    (pl.col('Low') <= p_level) & (pl.col('High') >= p_level)
                )['Volume'].sum()
                
                buckets.append({
                    'price': float(p_level),
                    'volume': float(vol)
                })

            # POC, VAH, VAL
            sorted_buckets = sorted(buckets, key=lambda x: x['volume'], reverse=True)
            poc = sorted_buckets[0]['price'] if sorted_buckets else 0
            
            total_vol = sum(b['volume'] for b in buckets)
            target_vol = total_vol * 0.70
            
            va_buckets = []
            acc = 0
            for b in sorted_buckets:
                va_buckets.append(b)
                acc += b['volume']
                if acc >= target_vol:
                    break
            
            vah = max(b['price'] for b in va_buckets) if va_buckets else 0
            val = min(b['price'] for b in va_buckets) if va_buckets else 0

            # Voids
            avg_vol = total_vol / self.price_levels if self.price_levels > 0 else 1
            voids = [b for b in buckets if b['volume'] < avg_vol * 0.3]

            # Resistance Path logic
            curr_price = float(df['Close'][-1])
            summary = self._generate_summary(curr_price, vah, val, poc, voids)

            return {
                'vah': vah,
                'val': val,
                'poc': poc,
                'volume_profile': buckets,
                'liquidity_voids': voids,
                'resistance_path': {
                    'summary': summary,
                    'key_levels': {
                        'nearest_support': val,
                        'poc': poc,
                        'nearest_resistance': vah
                    }
                }
            }
        except Exception as e:
            logger.error(f"Error in LiquidityCanyonAnalyzer: {e}")
            return {"error": str(e)}

    def _generate_summary(self, price, vah, val, poc, voids):
        msgs = []
        if price > vah:
            msgs.append(f"Price (${price:.2f}) is overextended above Value Area High (${vah:.2f}). Expect mean reversion.")
        elif price < val:
            msgs.append(f"Price (${price:.2f}) is in undervalued territory below VAL (${val:.2f}). Accumulation possible.")
        else:
            msgs.append(f"Price is in a balanced consolidation zone (${val:.2f} - ${vah:.2f}).")
            
        if any(abs(v['price'] - price) < (price * 0.005) for v in voids):
            msgs.append("Currently in a LIQUIDITY VOID. Rapid movement likely.")
            
        return " ".join(msgs)
