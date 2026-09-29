"""PCA V2 backend service package.

This package is intentionally backend-only for now. It mirrors the Factors V2
and Volatility V2 service shape without wiring routers or frontend routes.
"""

from __future__ import annotations

import os

os.environ.setdefault("OMP_NUM_THREADS", "4")
os.environ.setdefault("OPENBLAS_NUM_THREADS", "4")
os.environ.setdefault("MKL_NUM_THREADS", "4")
os.environ.setdefault("NUMEXPR_NUM_THREADS", "4")

from .registry import PCA_V2_FEATURES, get_pca_v2_feature, run_feature

__all__ = ["PCA_V2_FEATURES", "get_pca_v2_feature", "run_feature"]

