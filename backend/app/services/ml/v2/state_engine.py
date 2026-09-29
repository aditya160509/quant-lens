import numpy as np
import pandas as pd
import logging
from hmmlearn import hmm
from scipy import signal
from scipy.fft import fft, fftfreq
from sklearn.ensemble import IsolationForest
from typing import Dict, List, Any, Optional

logger = logging.getLogger(__name__)

class QuantumRegimeDetector:
    def __init__(self, n_regimes=3):
        self.model = hmm.GaussianHMM(
            n_components=n_regimes,
            covariance_type="full",
            n_iter=1000
        )

    def detect_regime(self, price_data: np.ndarray, volume_data: np.ndarray) -> Dict[str, Any]:
        """
        Returns: regime_id, stability_index, spectral_energy
        """
        try:
            # Feature engineering
            returns = np.diff(np.log(price_data))
            volatility = self._rolling_volatility(returns, window=20)
            
            # Normalize volume
            vol_mean = np.mean(volume_data)
            vol_std = np.std(volume_data)
            volume_norm = (volume_data - vol_mean) / vol_std if vol_std > 0 else np.zeros_like(volume_data)

            # Stack features (ensure same length)
            # returns length is N-1, vola is N-1, vol_norm is N
            # X needs to be aligned. returns[19:] is length N-20. 
            # vola is length N-1. vola[19:] is length N-20.
            # volume_norm[20:] is length N-20.
            
            X = np.column_stack([
                returns[19:], 
                volatility[19:], 
                volume_norm[20:]
            ])

            # Fit HMM
            self.model.fit(X)
            states = self.model.predict(X)

            # Map states to names dynamically based on return means
            # Return mean is the first column in our feature stack (index 0)
            means = self.model.means_[:, 0]
            sorted_indices = np.argsort(means) # [Bear, Neutral, Bull] order
            
            regime_map = {
                sorted_indices[0]: "Bear",
                sorted_indices[1]: "Neutral",
                sorted_indices[2]: "Bull"
            } if len(sorted_indices) >= 3 else {i: f"State {i}" for i in range(len(sorted_indices))}

            # Current regime
            current_regime = states[-1]

            # Stability Index (transition probability)
            trans_prob = self.model.transmat_[current_regime, current_regime]
            stability_index = int(trans_prob * 100)

            # Spectral decomposition
            spectral_energy = self._spectral_analysis(returns)

            return {
                'regime_id': int(current_regime),
                'regime': regime_map.get(current_regime, "Unknown"),
                'stability': float(stability_index),
                'spectral_energy': spectral_energy,
                'spectral_summary': spectral_energy['summary'],
                'state_means': means.tolist()
            }
        except Exception as e:
            logger.error(f"Error in QuantumRegimeDetector: {e}")
            return {"error": str(e)}

    def _rolling_volatility(self, returns, window):
        vols = []
        for i in range(len(returns)):
            chunk = returns[max(0, i-window+1):i+1]
            vols.append(np.std(chunk) if len(chunk) > 1 else 0)
        return np.array(vols)

    def _spectral_analysis(self, returns):
        """Short-Time Fourier Transform (STFT) for 3D visualization"""
        # Returns a grid of (time, frequency, power)
        n = len(returns)
        window_size = min(n, 64)
        overlap = window_size // 2
        
        f, t, Sxx = signal.spectrogram(returns, nperseg=window_size, noverlap=overlap)
        
        # Convert to a format friendly for 3D rendering (list of points or a grid)
        # We'll return a sample of points to keep payload manageable
        spectrogram_data = []
        for i in range(len(f)): # frequencies
            for j in range(len(t)): # time steps
                # Scale for better visualization
                power = float(Sxx[i, j])
                if power > 0:
                    spectrogram_data.append({
                        'time': float(t[j]),
                        'freq': float(f[i]),
                        'power': 10 * np.log10(power) # dB scale
                    })

        # Also keep summary for quick stats
        power_avg = np.mean(Sxx, axis=1)
        freq_sum = len(f)
        
        return {
            'spectrogram': spectrogram_data[-1000:], # Cap for performance
            'summary': {
                'trend': float(np.sum(power_avg[:freq_sum//4])),
                'swing': float(np.sum(power_avg[freq_sum//4:freq_sum//2])),
                'noise': float(np.sum(power_avg[freq_sum//2:]))
            }
        }

class AnomalyGravityDetector:
    def __init__(self):
        self.model = IsolationForest(
            contamination=0.05,
            random_state=42,
            n_estimators=200
        )
        from sklearn.decomposition import PCA
        self.pca = PCA(n_components=3)

    def detect_anomalies(self, df: pd.DataFrame) -> Dict[str, Any]:
        """
        Expects df with columns: ['close', 'volume', 'rsi', 'macd', 'obv']
        """
        try:
            # Normalize column names to lowercase for the model
            df_norm = df.copy()
            df_norm.columns = [c.lower() for c in df_norm.columns]
            
            # Feature matrix
            cols = ['close', 'volume']
            optional = ['rsi', 'macd', 'obv']
            for col in optional:
                if col in df_norm.columns:
                    cols.append(col)
            
            features = df_norm[cols].fillna(0)

            # Fit and predict
            self.model.fit(features)
            scores = self.model.decision_function(features)
            predictions = self.model.predict(features)

            # Normalize to 0-100 suspicion score
            # DECISION_FUNCTION: The higher, the more normal.
            min_s, max_s = np.min(scores), np.max(scores)
            if max_s > min_s:
                suspicion = 100 * (max_s - scores) / (max_s - min_s)
            else:
                suspicion = np.zeros_like(scores)
            suspicion = np.clip(suspicion, 0, 100)

            # Find historical events
            anomaly_indices = np.where(predictions == -1)[0]
            anomaly_events = []
            
            vol_avg = df_norm['volume'].rolling(20).mean()
            
            for idx in anomaly_indices:
                row = df_norm.iloc[idx]
                v_spike = row['volume'] / vol_avg.iloc[idx] if vol_avg.iloc[idx] > 0 else 1.0
                
                anomaly_events.append({
                    'date': str(df.iloc[idx].get('Date', df.index[idx])),
                    'suspicion': float(suspicion[idx]),
                    'price': float(row['close']),
                    'volume_spike': float(v_spike)
                })

            # Dimensionality reduction for visualization
            n_comp = min(len(features.columns), 3)
            self.pca.n_components = n_comp
            X_pca = self.pca.fit_transform(features)
            
            # Prepare points for frontend
            points = []
            for i in range(len(features)):
                pt = {
                    'x': float(X_pca[i, 0]),
                    'y': float(X_pca[i, 1]) if n_comp > 1 else 0.0,
                    'z': float(X_pca[i, 2]) if n_comp > 2 else 0.0,
                    'is_anomaly': bool(predictions[i] == -1),
                    'score': float(suspicion[i])
                }
                points.append(pt)

            return {
                'suspicion_score': float(suspicion[-1]),
                'is_anomaly': bool(predictions[-1] == -1),
                'historical_anomalies': anomaly_events[-50:],
                'points': points
            }
        except Exception as e:
            logger.error(f"Error in AnomalyGravityDetector: {e}")
            return {"error": str(e)}
