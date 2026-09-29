"""Volatility V2 service package.

This package is intentionally scaffolded separately from Factors V2 so the
volatility stack can be built without disturbing the live factor module.
"""

from __future__ import annotations

import os

# Keep nested BLAS/OpenMP pools from oversubscribing request workers. These are
# set before importing the numerical stack through the registry.
os.environ.setdefault("OMP_NUM_THREADS", "4")
os.environ.setdefault("OPENBLAS_NUM_THREADS", "4")
os.environ.setdefault("MKL_NUM_THREADS", "4")
os.environ.setdefault("NUMEXPR_NUM_THREADS", "4")

from .registry import VOLATILITY_V2_FEATURES, get_volatility_v2_feature

__all__ = ["VOLATILITY_V2_FEATURES", "get_volatility_v2_feature"]
