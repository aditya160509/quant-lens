"""The one strategy object (PLAN §3.1): blocks, formula and Python all compile to this spec."""

from __future__ import annotations

import hashlib
import json
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from . import fills
from .engine import Params


class _Model(BaseModel):
    model_config = ConfigDict(extra="forbid")


class Param(_Model):
    value: float
    min: float | None = None
    max: float | None = None
    step: float | None = None


class Exits(_Model):
    stop: float = Field(0.0, ge=0, lt=1)  # fraction of entry price
    stop_atr: float = Field(0.0, ge=0)  # multiple of ATR(14) at the signal bar; wins over `stop` when set
    target: float = Field(0.0, ge=0)
    trail: float = Field(0.0, ge=0, lt=1)
    time_stop: int = Field(0, ge=0)
    breakeven: float = Field(0.0, ge=0)
    scale_at: float = Field(0.0, ge=0)
    scale_frac: float = Field(0.0, ge=0, le=1)


class Sizing(_Model):
    mode: Literal["shares", "cash", "pct_equity", "risk", "equal", "vol_target"] = "equal"
    value: float = Field(0.0, ge=0)
    max_positions: int = Field(10, ge=0)


class Limits(_Model):
    """My limits: walk-away conditions, saved with the version."""

    max_drawdown: float | None = Field(0.25, gt=0, le=1)
    max_drawdown_months: float | None = Field(None, gt=0)
    min_trades: int | None = Field(30, ge=0)
    min_years: float | None = Field(None, ge=0)
    max_beta: float | None = None
    max_cost_share: float | None = Field(None, ge=0)
    min_start_pass: float | None = Field(None, ge=0, le=1)


class Strategy(_Model):
    name: str = "Untitled"
    entry_long: str = ""
    exit_long: str = ""
    entry_short: str = ""
    exit_short: str = ""
    score: str = ""  # which candidates take the free slots first (higher first)
    params: dict[str, Param] = Field(default_factory=dict)
    exits: Exits = Field(default_factory=Exits)
    sizing: Sizing = Field(default_factory=Sizing)
    limits: Limits = Field(default_factory=Limits)
    code: str = ""  # Python source when the strategy was written as code
    blocks: list[dict] = Field(default_factory=list)  # the editor's block rows, kept so Blocks reopens as written
    hypothesis: str = ""
    regime_claim: str = ""
    notes: str = ""

    def hash(self) -> str:
        """Identity of the trading rule: text fields that do not trade are left out."""
        body = self.model_dump(exclude={"name", "hypothesis", "regime_claim", "notes", "blocks", "limits"})
        return hashlib.sha256(json.dumps(body, sort_keys=True, separators=(",", ":")).encode()).hexdigest()[:16]

    def values(self) -> dict[str, float]:
        return {k: p.value for k, p in self.params.items()}


class Costs(_Model):
    profile: str = "US retail"
    commission_bps: float = Field(1.0, ge=0)
    commission_share: float = Field(0.0, ge=0)
    commission_min: float = Field(0.0, ge=0)
    slippage_bps: float = Field(2.0, ge=0)
    slippage_range: float = Field(0.0, ge=0, le=1)
    borrow_bps: float = Field(50.0, ge=0)
    volume_cap: float = Field(0.0, ge=0, le=1)

    def off(self) -> bool:
        return not (self.commission_bps or self.commission_share or self.commission_min or self.slippage_bps or self.slippage_range)


class Settings(_Model):
    """Shared run inputs (PAGES §0.1)."""

    symbols: list[str] = Field(default_factory=list)
    top_n: int = Field(100, ge=1, le=5000)  # top names by liquidity when `symbols` is empty
    start: str | None = None
    end: str | None = None
    holdout: float = Field(0.2, ge=0, lt=0.9)
    fill: Literal["next_open", "same_close"] = "next_open"
    magnifier: bool = True
    costs: Costs = Field(default_factory=Costs)
    delist_haircut: float = Field(0.0, ge=0, le=1)
    capital: float = Field(100_000.0, gt=0)
    leverage: float = Field(1.0, gt=0, le=10)
    benchmark: str = "SPY"
    seed: int = 7

    def hash(self) -> str:
        return hashlib.sha256(json.dumps(self.model_dump(), sort_keys=True, separators=(",", ":")).encode()).hexdigest()[:16]


_SIZE = {"shares": fills.SHARES, "cash": fills.CASH, "pct_equity": fills.PCT_EQUITY, "risk": fills.RISK, "equal": fills.EQUAL, "vol_target": fills.VOL}


def engine_params(spec: Strategy, settings: Settings, cost_multiple: float = 1.0) -> Params:
    e, c = spec.exits, settings.costs
    return Params(
        fill=float(settings.fill == "same_close"), stop=e.stop, target=e.target, trail=e.trail, time_stop=e.time_stop, breakeven=e.breakeven,
        scale_at=e.scale_at, scale_frac=e.scale_frac, size_mode=_SIZE[spec.sizing.mode], size=spec.sizing.value, max_positions=spec.sizing.max_positions,
        commission_bps=c.commission_bps * cost_multiple, commission_share=c.commission_share * cost_multiple, commission_min=c.commission_min * cost_multiple,
        slippage_bps=c.slippage_bps * cost_multiple, slippage_range=c.slippage_range * cost_multiple, borrow_bps=c.borrow_bps * cost_multiple,
        volume_cap=c.volume_cap, delist_haircut=settings.delist_haircut, leverage=settings.leverage, capital=settings.capital)
