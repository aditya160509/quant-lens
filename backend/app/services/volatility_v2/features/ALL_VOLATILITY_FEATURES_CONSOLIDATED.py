"""Consolidated Volatility V2 feature index.

This file used to contain concatenated copies of all feature modules, which
made package-wide compilation fail because repeated `from __future__` imports
appeared mid-file. Runtime uses `feature_01.py` through `feature_09.py`; this
module is intentionally only a lightweight import-safe index.
"""

from __future__ import annotations

FEATURE_MODULES = [f"feature_{i:02d}" for i in range(1, 10)]
