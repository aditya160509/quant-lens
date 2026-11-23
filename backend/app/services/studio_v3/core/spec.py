"""The one strategy object (PLAN §3.1): blocks, formula and Python all compile to this spec."""

from __future__ import annotations

import ast
import hashlib
import json
import re
import sys
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from . import fills
from .engine import Params


class _Model(BaseModel):
    model_config = ConfigDict(extra="forbid")


class Param(_Model):
    value: float
    min: float | None = None
    max: float | None = None
    step: float | None = None
    log: bool = False  # search on a log scale (random and Bayesian)


class Exits(_Model):
    stop: float = Field(0.0, ge=0, lt=1)  # fraction of entry price
    stop_atr: float = Field(0.0, ge=0)  # multiple of ATR(14) at the signal bar; wins over `stop` when set
    target: float = Field(0.0, ge=0)
    trail: float = Field(0.0, ge=0, lt=1)
    time_stop: int = Field(0, ge=0)
    breakeven: float = Field(0.0, ge=0)
    scale_at: float = Field(0.0, ge=0)
    scale_frac: float = Field(0.0, ge=0, le=1)
    scale_at2: float = Field(0.0, ge=0)  # second rung, above the first
    scale_frac2: float = Field(0.0, ge=0, le=1)
    opposite_signal: bool = False  # a short entry closes longs and a long entry closes shorts
    end_of_week: bool = False  # close every position on the last observed bar of the week


class Sizing(_Model):
    mode: Literal["shares", "cash", "pct_equity", "risk", "equal", "vol_target", "score", "kelly", "risk_parity"] = "equal"
    value: float = Field(0.0, ge=0)
    max_positions: int = Field(10, ge=0)


class Risk(_Model):
    """Account-level stops (B-54) and exposure caps (B-121); zero means off. Studio holds daily bars, so one bar is one session."""

    max_drawdown: float = Field(0.0, ge=0, le=1)  # flatten every position and stop trading at this fall from the peak
    max_daily_loss: float = Field(0.0, ge=0, le=1)  # same, at this fall from the previous session's close
    max_position: float = Field(0.0, ge=0, le=10)  # share of equity per name; 0 = off
    max_gross: float = Field(0.0, ge=0, le=10)  # share of equity across all names; 0 = off


class Limits(_Model):
    """My limits: walk-away conditions, saved with the version."""

    max_drawdown: float | None = Field(0.25, gt=0, le=1)
    max_drawdown_months: float | None = Field(None, gt=0)
    min_trades: int | None = Field(30, ge=0)
    min_years: float | None = Field(None, ge=0)
    max_beta: float | None = None
    max_cost_share: float | None = Field(None, ge=0)
    min_start_pass: float | None = Field(None, ge=0, le=1)


MAX_GROUP_DEPTH, MAX_GROUP_RULES = 10, 200
GROUP_ROLES = ("entry_long", "exit_long", "entry_short", "exit_short", "market_filter")


def group_formula(node, depth: int = 1, count: list[int] | None = None) -> str:
    """An Any/All group as one formula: a rule is a string or {"rule", "enabled"}; a group is {"op": "all"|"any", "items": [...]}, nested to 10 deep.
    Disabled rules and groups left empty by them drop out (B-105, B-107)."""
    count = count if count is not None else [0]
    if isinstance(node, str) or (isinstance(node, dict) and "rule" in node):
        if isinstance(node, dict) and node.get("enabled") is False:
            return ""
        text = (node if isinstance(node, str) else str(node["rule"])).strip()
        if not text:
            raise ValueError("A group holds an empty rule")
        count[0] += 1
        if count[0] > MAX_GROUP_RULES:
            raise ValueError(f"A group holds at most {MAX_GROUP_RULES} rules")
        return f"({text})"
    if not isinstance(node, dict) or node.get("op") not in {"all", "any"} or not isinstance(node.get("items"), list):
        raise ValueError('A group is {"op": "all" or "any", "items": [...]}')
    if depth > MAX_GROUP_DEPTH:
        raise ValueError(f"Groups nest at most {MAX_GROUP_DEPTH} deep")
    parts = [part for item in node["items"] if (part := group_formula(item, depth + 1, count))]
    return "(" + (" & " if node["op"] == "all" else " | ").join(parts) + ")" if parts else ""


class Strategy(_Model):
    name: str = "Untitled"
    entry_long: str = ""
    exit_long: str = ""
    entry_short: str = ""
    exit_short: str = ""
    score: str = ""  # which candidates take the free slots first (higher first)
    market_filter: str = ""  # trade only while true; when it turns false every position is closed and the book sits in cash
    scale_in: str = ""  # while long, add one first-entry's size each bar this is true (B-124)
    max_entries: int = Field(3, ge=1, le=20)  # fills that may build one position when scale_in is set
    defensive: str = Field("", max_length=12)  # else-branch of the market rule: hold this symbol (it must be in the universe) instead of cash (B-122)
    params: dict[str, Param] = Field(default_factory=dict)
    frequency: Literal["daily", "week_start", "month_start"] = "daily"  # entries only on these bars; exits always run
    exits: Exits = Field(default_factory=Exits)
    sizing: Sizing = Field(default_factory=Sizing)
    risk: Risk = Field(default_factory=Risk)
    limits: Limits = Field(default_factory=Limits)
    code: str = ""  # Python source when the strategy was written as code
    files: dict[str, str] = Field(default_factory=dict, max_length=49)
    groups: dict[str, dict | str] = Field(default_factory=dict)  # role -> Any/All tree; the role's formula is generated from it
    blocks: list[dict] = Field(default_factory=list)  # the editor's block rows, kept so Blocks reopens as written
    hypothesis: str = ""
    regime_claim: str = ""
    notes: str = ""

    @model_validator(mode="after")
    def _generate_group_formulas(self):
        for role, node in self.groups.items():
            if role not in GROUP_ROLES:
                raise ValueError(f"Groups apply to {', '.join(GROUP_ROLES)}, not {role}")
            setattr(self, role, group_formula(node))
        return self

    @field_validator("files")
    @classmethod
    def validate_files(cls, files: dict[str, str]) -> dict[str, str]:
        for name, source in files.items():
            if name == "main.py" or not re.fullmatch(r"[A-Za-z][A-Za-z0-9_]{0,119}\.py|README\.md|params\.json", name):
                raise ValueError(f"Invalid helper filename: {name}")
            if len(source.encode("utf-8")) > 200_000:
                raise ValueError(f"{name} exceeds 200 KB")
        return files

    def project_files(self) -> dict[str, str]:
        return {"main.py": self.code, **self.files}

    def hash(self) -> str:
        """Identity of the trading rule: text fields that do not trade are left out."""
        body = self.model_dump(exclude={"name", "hypothesis", "regime_claim", "notes", "blocks", "limits"})
        if not self.files:
            body.pop("files")
        if not self.groups:
            body.pop("groups")
        return hashlib.sha256(json.dumps(body, sort_keys=True, separators=(",", ":")).encode()).hexdigest()[:16]

    def parameter_definitions(self) -> dict[str, Param]:
        declared = {}
        if self.code.strip():
            try:
                tree = ast.parse(self.code)
            except SyntaxError:
                return self.params
            for strategy in tree.body:
                if not isinstance(strategy, ast.ClassDef):
                    continue
                # Strategy.params, and any other class's `inputs` (indicators run by self.use) as `Class_name`.
                attr, prefix = ("params", "") if strategy.name in ("Strategy", "Indicator") else ("inputs", f"{strategy.name}_")
                for assignment in strategy.body:
                    if not isinstance(assignment, ast.Assign) or not any(
                        isinstance(target, ast.Name) and target.id == attr for target in assignment.targets
                    ) or not isinstance(assignment.value, ast.Dict):
                        continue
                    for key, item in zip(assignment.value.keys, assignment.value.values, strict=True):
                        if not isinstance(key, ast.Constant) or not isinstance(key.value, str) or not key.value.isidentifier():
                            continue
                        try:
                            values = ast.literal_eval(item)
                        except (ValueError, SyntaxError, TypeError):
                            continue
                        if not isinstance(values, tuple) or len(values) != 4 or not all(
                            type(value) in (int, float) and abs(value) <= sys.float_info.max for value in values
                        ):
                            continue
                        default, minimum, maximum, step = values
                        if minimum <= default <= maximum and step > 0:
                            declared[prefix + key.value] = Param(value=default, min=minimum, max=maximum, step=step)
        return {**declared, **self.params}

    def values(self) -> dict[str, float]:
        return {k: p.value for k, p in self.parameter_definitions().items()}


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

    @model_validator(mode="before")
    @classmethod
    def _drop_retired(cls, v):  # saved runs from before hourly bars were removed still carry `magnifier`
        return {k: x for k, x in v.items() if k != "magnifier"} if isinstance(v, dict) else v

    symbols: list[str] = Field(default_factory=list)
    top_n: int = Field(100, ge=1, le=5000)  # top names by liquidity when `symbols` is empty
    start: str | None = None
    end: str | None = None
    holdout: float = Field(0.2, ge=0, lt=0.9)
    fill: Literal["next_open", "same_close"] = "next_open"
    costs: Costs = Field(default_factory=Costs)
    delist_haircut: float = Field(0.0, ge=0, le=1)
    capital: float = Field(100_000.0, gt=0)
    leverage: float = Field(1.0, gt=0, le=10)
    benchmark: str = "SPY"
    benchmark_mode: Literal["ticker", "equal_weight", "cash"] = "ticker"  # ticker: the symbol above; equal_weight: the run's universe, rebalanced daily; cash: flat
    seed: int = 7
    rule_target: float = Field(0.10, gt=0, le=10)  # Backtest > Paths > Rule check
    rule_daily_loss: float = Field(0.05, gt=0, le=1)
    rule_max_dd: float = Field(0.10, gt=0, le=1)
    rule_min_days: int = Field(5, ge=0)

    def hash(self) -> str:
        return hashlib.sha256(json.dumps(self.model_dump(), sort_keys=True, separators=(",", ":")).encode()).hexdigest()[:16]


_SIZE = {"shares": fills.SHARES, "cash": fills.CASH, "pct_equity": fills.PCT_EQUITY, "risk": fills.RISK, "equal": fills.EQUAL, "vol_target": fills.VOL, "score": fills.SCORE, "kelly": fills.KELLY, "risk_parity": fills.PARITY}


def engine_params(spec: Strategy, settings: Settings, cost_multiple: float = 1.0) -> Params:
    e, c, r = spec.exits, settings.costs, spec.risk
    return Params(
        fill=float(settings.fill == "same_close"), stop=e.stop, target=e.target, trail=e.trail, time_stop=e.time_stop, breakeven=e.breakeven,
        scale_at=e.scale_at, scale_frac=e.scale_frac, size_mode=_SIZE[spec.sizing.mode], size=spec.sizing.value, max_positions=spec.sizing.max_positions,
        scale_at2=e.scale_at2, scale_frac2=e.scale_frac2,
        commission_bps=c.commission_bps * cost_multiple, commission_share=c.commission_share * cost_multiple, commission_min=c.commission_min * cost_multiple,
        slippage_bps=c.slippage_bps * cost_multiple, slippage_range=c.slippage_range * cost_multiple, borrow_bps=c.borrow_bps * cost_multiple,
        volume_cap=c.volume_cap, delist_haircut=settings.delist_haircut, leverage=settings.leverage, capital=settings.capital,
        max_dd=r.max_drawdown, max_daily_loss=r.max_daily_loss, max_position=r.max_position, max_gross=r.max_gross)
