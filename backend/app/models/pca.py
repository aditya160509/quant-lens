import pandas as pd
import numpy as np
from sklearn.decomposition import PCA
from sklearn.preprocessing import StandardScaler
import logging

logger = logging.getLogger(__name__)

def run_pca(returns_df: pd.DataFrame) -> dict:
    """
    Runs PCA on a DataFrame of asset returns.
    
    Args:
        returns_df (pd.DataFrame): Columns are assets, Index is date.
        
    Returns:
        dict: Explained variance, loadings, and projected data.
    """
    try:
        # Drop missing data
        clean_df = returns_df.dropna()
        if clean_df.empty:
            return {"error": "Not enough data"}
            
        # Standardize
        scaler = StandardScaler()
        X_scaled = scaler.fit_transform(clean_df)
        
        # PCA
        n_components = min(10, min(X_scaled.shape))
        pca = PCA(n_components=n_components)
        pca.fit(X_scaled)
        
        # Loadings (Eigenvectors)
        # components_ is shape (n_components, n_features)
        loadings = pd.DataFrame(
            pca.components_.T, 
            columns=[f"PC{i+1}" for i in range(n_components)],
            index=clean_df.columns
        )
        
        # Explained Variance
        explained_var = pca.explained_variance_ratio_
        
        # Projection (Scores)
        scores = pca.transform(X_scaled)
        scores_df = pd.DataFrame(
            scores,
            columns=[f"PC{i+1}" for i in range(n_components)],
            index=clean_df.index
        )
        
        return {
            "explained_variance": explained_var.tolist(),
            "loadings": loadings.to_dict(orient='index'),
            "scores": {
                "dates": scores_df.index.strftime('%Y-%m-%d').tolist(),
                "values": scores_df.values.tolist()
            },
            "feature_names": clean_df.columns.tolist()
        }
    except Exception as e:
        logger.error(f"PCA failed: {e}")
        return {"error": str(e)}

def get_correlation_matrix(returns_df: pd.DataFrame) -> dict:
    """
    Computes correlation matrix.
    """
    corr = returns_df.corr()
    return {
        "matrix": corr.values.tolist(),
        "labels": corr.columns.tolist()
    }
