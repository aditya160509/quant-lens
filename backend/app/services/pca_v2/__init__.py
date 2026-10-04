"""PCA V2 backend service package.

The registry defers feature imports. HTTP routes are mounted at /api/labs/pca/v2;
the frontend rebuild remains a separate responsibility.
"""

from __future__ import annotations

import os

os.environ.setdefault("OMP_NUM_THREADS", "4")
os.environ.setdefault("OPENBLAS_NUM_THREADS", "4")
os.environ.setdefault("MKL_NUM_THREADS", "4")
os.environ.setdefault("NUMEXPR_NUM_THREADS", "4")

from .registry import PCA_V2_FEATURES, get_pca_v2_feature, run_feature

__all__ = ["PCA_V2_FEATURES", "get_pca_v2_feature", "run_feature"]

