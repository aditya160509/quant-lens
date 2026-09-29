"""Fast bounded bootstrap paths for completed backtests."""

from __future__ import annotations

from typing import Any

import numpy as np
import pandas as pd


def bootstrap_paths(returns: Any, *, initial_value: float = 1.0,
                    paths: int = 200, seed: int = 42) -> dict[str, Any]:
    values = pd.Series(returns, dtype=float).replace([np.inf, -np.inf], np.nan).dropna().to_numpy()
    count = int(paths)
    if count < 0 or count > 1_000:
        raise ValueError("monte_carlo_paths must be between 0 and 1000")
    if count == 0:
        return {"paths": [], "path_count": 0, "seed": int(seed), "disabled": True}
    if len(values) < 2:
        return {"paths": [], "path_count": 0, "seed": int(seed),
                "warning": "at least two daily returns are required"}
    rng = np.random.default_rng(int(seed))
    samples = rng.choice(values, size=(count, len(values)), replace=True)
    wealth = float(initial_value) * np.cumprod(1.0 + samples, axis=1)
    wealth = np.concatenate([np.full((count, 1), float(initial_value)), wealth], axis=1)
    running_max = np.maximum.accumulate(wealth, axis=1)
    drawdowns = np.divide(wealth, running_max, out=np.ones_like(wealth), where=running_max != 0) - 1.0
    terminal = wealth[:, -1]
    return {
        "paths": wealth.tolist(),
        "path_count": count,
        "observations_per_path": int(wealth.shape[1]),
        "seed": int(seed),
        "median_terminal": float(np.median(terminal)),
        "loss_probability": float(np.mean(terminal < float(initial_value))),
        "drawdown_95": float(np.percentile(drawdowns.min(axis=1), 5)),
        "terminal_percentiles": {
            key: float(value) for key, value in zip(
                ("p5", "p25", "p50", "p75", "p95"), np.percentile(terminal, [5, 25, 50, 75, 95])
            )
        },
        "method": "iid_daily_return_bootstrap",
    }
