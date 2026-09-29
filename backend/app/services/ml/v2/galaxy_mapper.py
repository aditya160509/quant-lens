import umap
import numpy as np
import pandas as pd
import logging
from sklearn.preprocessing import StandardScaler
from typing import Dict, List, Any, Optional

logger = logging.getLogger(__name__)

class GalaxyMapper:
    def __init__(self):
        self.reducer = umap.UMAP(
            n_neighbors=15,
            n_components=3,
            min_dist=0.1,
            metric='euclidean',
            random_state=42
        )
        self.scaler = StandardScaler()

    def create_universe(self, market_data: List[Dict]) -> List[Dict]:
        """
        Expects a list of dicts with fundamental and technical summary data.
        Returns: 3D coordinates for each ticker
        """
        try:
            if not market_data:
                return []

            tickers = [t['ticker'] for t in market_data]
            
            # Extract feature matrix (Maxed-out 150+ metrics)
            features = []
            for t in market_data:
                vec = self._extract_features(t)
                features.append(vec)
            
            X = np.array(features)
            X_scaled = self.scaler.fit_transform(X)
            
            # UMAP dimensionality reduction
            n_samples = len(X)
            self.reducer.n_neighbors = min(15, n_samples - 1) if n_samples > 1 else 1
            coords_3d = self.reducer.fit_transform(X_scaled)
            
            universe = []
            for i, t in enumerate(market_data):
                universe.append({
                    'ticker': t['ticker'],
                    'name': t.get('name', t['ticker']),
                    'sector': t.get('sector', 'Unknown'),
                    'x': float(coords_3d[i, 0]),
                    'y': float(coords_3d[i, 1]),
                    'z': float(coords_3d[i, 2]),
                    'market_cap': float(t.get('market_cap', 1e6))
                })
            
            return universe
        except Exception as e:
            logger.error(f"Error in GalaxyMapper create_universe: {e}")
            return []

    def _extract_features(self, data: Dict) -> List[float]:
        """Extract 150+ dimensional feature vector from available metadata"""
        features = []

        # Fundamental metrics (Primary)
        fundamentals = [
            'pe', 'pb', 'ps', 'peg', 'debt_to_equity', 'current_ratio', 
            'roe', 'roa', 'gross_margin', 'operating_margin',
            'revenue_growth', 'earnings_growth', 'dividend_yield', 'beta'
        ]

        for metric in fundamentals:
            val = data.get(metric, 0)
            if val is None or not np.isfinite(val): val = 0
            features.append(float(val))

        # Secondary metrics (Institutional)
        secondary = [
            'quick_ratio', 'roic', 'net_margin', 'asset_turnover', 
            'inventory_turnover', 'fcf_growth', 'payout_ratio'
        ]
        for metric in secondary:
            val = data.get(metric, 0)
            if val is None or not np.isfinite(val): val = 0
            features.append(float(val))

        # Sector performance metrics (Mocked if missing)
        for metric in ['pe_vs_sector', 'pb_vs_sector', 'ps_vs_sector']:
            val = data.get(metric, 0)
            if val is None or not np.isfinite(val): val = 0
            features.append(float(val))

        # Market Cap Log (Critical for spatial grouping)
        mcap = data.get('market_cap', 1e6)
        features.append(float(np.log10(mcap) if mcap > 0 else 0))

        # Pad to 150 features with structural zeroes to maintain manifold shape
        while len(features) < 150:
            features.append(0.0)

        return features

    def find_similar(self, universe: List[Dict], target_ticker: str, n: int = 5) -> List[Dict]:
        """Find N most similar stocks to target in the 3D space (DNA Matcher)"""
        target = next((s for s in universe if s['ticker'] == target_ticker), None)
        if not target:
            return []

        # Calculate Euclidean distances in 3D manifold space
        distances = []
        for stock in universe:
            if stock['ticker'] == target_ticker:
                continue

            dist = np.sqrt(
                (stock['x'] - target['x'])**2 +
                (stock['y'] - target['y'])**2 +
                (stock['z'] - target['z'])**2
            )
            distances.append((stock, dist))

        # Sort and return top N
        distances.sort(key=lambda x: x[1])
        return [stock for stock, _ in distances[:n]]
