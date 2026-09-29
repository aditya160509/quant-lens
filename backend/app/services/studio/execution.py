"""Fail-closed container execution for user-authored Studio strategies."""

from __future__ import annotations

import ast
import json
import os
import subprocess
from dataclasses import dataclass
from typing import Any, Protocol
from uuid import uuid4

import pandas as pd


DEFAULT_IMAGE = "quant360-studio-runner:1.0"
MAX_CODE_BYTES = 64 * 1024
MAX_RESPONSE_BYTES = 4 * 1024 * 1024
MAX_SIGNALS = 100_000


class ExecutionUnavailableError(RuntimeError):
    """Raised when the approved isolated runtime is unavailable."""


class StrategyPolicyError(ValueError):
    """Raised when strategy source violates the bounded execution policy."""


class StrategyExecutionError(ValueError):
    """Raised when an isolated strategy fails."""


class ExecutionProvider(Protocol):
    def execute(self, code: str, data: pd.DataFrame) -> list[dict[str, Any]]: ...


_DENIED_NAMES = {
    "breakpoint", "compile", "eval", "exec", "globals", "help", "input",
    "locals", "open", "quit", "exit", "__import__",
}
_DENIED_ATTRIBUTES = {
    "__bases__", "__builtins__", "__class__", "__code__", "__dict__",
    "__globals__", "__mro__", "__subclasses__", "__getattribute__",
}


def validate_strategy_source(code: str) -> ast.Module:
    if not code.strip():
        raise StrategyPolicyError("Strategy code is required.")
    if len(code.encode("utf-8")) > MAX_CODE_BYTES:
        raise StrategyPolicyError(f"Strategy code exceeds {MAX_CODE_BYTES} bytes.")
    try:
        tree = ast.parse(code, filename="<studio-strategy>", mode="exec")
    except SyntaxError as exc:
        raise StrategyPolicyError(f"Strategy syntax error at line {exc.lineno}: {exc.msg}") from exc
    if not any(isinstance(node, ast.ClassDef) and node.name == "Strategy" for node in tree.body):
        raise StrategyPolicyError("Script must define class Strategy.")
    for node in ast.walk(tree):
        if isinstance(node, (ast.Import, ast.ImportFrom)):
            raise StrategyPolicyError("Imports are disabled; use the provided pd and np modules.")
        if isinstance(node, ast.Name) and node.id in _DENIED_NAMES:
            raise StrategyPolicyError(f"Name '{node.id}' is not allowed.")
        if isinstance(node, ast.Attribute) and node.attr in _DENIED_ATTRIBUTES:
            raise StrategyPolicyError(f"Attribute '{node.attr}' is not allowed.")
    return tree


_RUNNER = r'''
import ast, contextlib, json, sys
import numpy as np
import pandas as pd

payload = json.load(sys.stdin)
code = payload["code"]
frame = pd.DataFrame.from_records(payload["records"])
frame.index = pd.to_datetime(payload["index"])
safe_builtins = {
    "__build_class__": __build_class__, "abs": abs, "all": all, "any": any,
    "bool": bool, "dict": dict, "enumerate": enumerate, "float": float,
    "int": int, "len": len, "list": list, "max": max, "min": min,
    "object": object, "range": range, "round": round, "set": set,
    "str": str, "sum": sum, "tuple": tuple, "zip": zip,
}
globals_ns = {"pd": pd, "np": np, "__builtins__": safe_builtins, "__name__": "studio_strategy"}
locals_ns = {}
class Sink:
    def write(self, value): return len(value)
    def flush(self): pass
with contextlib.redirect_stdout(Sink()), contextlib.redirect_stderr(Sink()):
    exec(compile(code, "<studio-strategy>", "exec"), globals_ns, locals_ns)
    strategy = locals_ns.get("strategy")
    if strategy is None or not hasattr(strategy, "generate_signals"):
        raise ValueError("Script must instantiate strategy with generate_signals(data).")
    signals = strategy.generate_signals(frame)
if not isinstance(signals, list):
    raise ValueError("generate_signals(data) must return a list.")
if len(signals) > 100000:
    raise ValueError("Strategy returned too many signals.")
def clean(value):
    if isinstance(value, dict): return {str(k): clean(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)): return [clean(v) for v in value]
    if isinstance(value, np.generic): return value.item()
    return value
sys.stdout.write(json.dumps({"signals": clean(signals)}, allow_nan=False))
'''


@dataclass(frozen=True)
class DockerExecutionProvider:
    image: str = DEFAULT_IMAGE
    timeout_seconds: int = 15

    def _command(self, container_name: str) -> list[str]:
        return [
            "docker", "run", "--rm", "--name", container_name, "--interactive", "--network", "none",
            "--read-only", "--cap-drop", "ALL", "--security-opt", "no-new-privileges",
            "--pids-limit", "64", "--memory", "512m", "--memory-swap", "512m",
            "--cpus", "1", "--user", "65534:65534",
            "--tmpfs", "/tmp:rw,noexec,nosuid,nodev,size=64m",
            "--env", "PYTHONDONTWRITEBYTECODE=1", self.image,
            "python", "-I", "-c", _RUNNER,
        ]

    def execute(self, code: str, data: pd.DataFrame) -> list[dict[str, Any]]:
        validate_strategy_source(code)
        normalized = data.copy()
        for column in list(normalized.columns):
            if column.lower() not in normalized.columns:
                normalized[column.lower()] = normalized[column]
        payload = json.dumps({
            "code": code,
            "records": normalized.reset_index(drop=True).to_dict(orient="records"),
            "index": [pd.Timestamp(value).isoformat() for value in normalized.index],
        }, allow_nan=False)
        environment = {"PATH": os.environ.get("PATH", "")}
        container_name = f"quant360-studio-{uuid4().hex}"
        try:
            completed = subprocess.run(
                self._command(container_name), input=payload, text=True, capture_output=True,
                timeout=self.timeout_seconds, check=False, env=environment,
            )
        except FileNotFoundError as exc:
            raise ExecutionUnavailableError("The isolated Studio runner is not installed.") from exc
        except subprocess.TimeoutExpired as exc:
            subprocess.run(
                ["docker", "rm", "--force", container_name],
                text=True, capture_output=True, timeout=5, check=False, env=environment,
            )
            raise StrategyExecutionError("Strategy exceeded the execution time limit.") from exc
        if completed.returncode in (125, 126, 127):
            raise ExecutionUnavailableError("The isolated Studio runner is unavailable.")
        if completed.returncode != 0:
            message = completed.stderr.strip().splitlines()[-1] if completed.stderr.strip() else "Strategy failed."
            raise StrategyExecutionError(message[:500])
        if len(completed.stdout.encode("utf-8")) > MAX_RESPONSE_BYTES:
            raise StrategyExecutionError("Strategy output exceeded the response limit.")
        try:
            result = json.loads(completed.stdout)
        except json.JSONDecodeError as exc:
            raise StrategyExecutionError("Strategy returned an invalid response.") from exc
        signals = result.get("signals")
        if not isinstance(signals, list) or len(signals) > MAX_SIGNALS:
            raise StrategyExecutionError("Strategy returned an invalid signal collection.")
        return signals
