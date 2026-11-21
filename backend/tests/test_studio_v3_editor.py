"""Build editor services: look-ahead patterns, strictness, hover, inlay hints, code lens, code actions, imports and formatting, API version."""

import pytest

from app.services.studio_v3.core import editor, pycode
from tests.test_studio_v3_backtest import studio  # noqa: F401  (fixture)

API = "/api/studio-v3/build"
STRATEGY = '''class Strategy:
    def on_bar(self, ctx):
        {body}
'''


def _problems(body, **kw):
    return pycode.lint(STRATEGY.format(body=body), {}, **kw)


@pytest.mark.parametrize("body", [
    "x = ctx.close[1:]", "x = ctx.close[0:5]", "h = ctx.history('close', 5)\n        x = h[1]", "x = ctx.date > '2999-01-01'",
    "x = ctx.next_close", "x = ctx.close[-3:].shift(-1)",
])
def test_look_ahead_patterns_are_errors_with_their_position(body):
    found = [p for p in _problems(body) if p["code"] == "look-ahead"]
    assert found and found[0]["severity"] == "error" and found[0]["line"] >= 3 and found[0]["column"] >= 1


@pytest.mark.parametrize("body", ["x = ctx.close[-20:]", "h = ctx.history('close', 5)\n        x = h[0] + h[-1]", "x = ctx.date > '2015-01-01'", "x = ctx.close[-5:0]"])
def test_past_reads_are_not_look_ahead(body):
    assert not [p for p in _problems(body) if p["code"] == "look-ahead"]


def test_strictness_and_severity_per_rule():
    body = "x = ctx.close[-1]\n        print(x)"
    assert [p["severity"] for p in _problems(body) if p["code"] == "print-in-loop"] == ["warning"]
    assert [p["severity"] for p in _problems(body, severity={"print-in-loop": "error"}) if p["code"] == "print-in-loop"] == ["error"]
    assert not [p for p in _problems(body, severity={"print-in-loop": "off"}) if p["code"] == "print-in-loop"]
    unused = "import math\n" + STRATEGY.format(body="pass")
    assert not [p for p in pycode.lint(unused, {}) if p["code"] in {"F401", "studio-api"}]
    strict = {p["code"]: p for p in pycode.lint(unused, {}, strictness="strict")}
    assert strict["F401"]["severity"] == "warning" and strict["studio-api"]["fix"]["edits"][0]["text"] == "# studio-api: 1\n"
    with pytest.raises(ValueError, match="Severity"):
        pycode.lint(unused, {}, severity={"F401": "loud"})


def test_newer_api_header_is_an_error_and_migrator_stamps_old_code():
    newer = "# studio-api: 9\n" + STRATEGY.format(body="pass")
    assert next(p["message"] for p in pycode.lint(newer, {}) if p["code"] == "studio-api").startswith("This code targets studio-api 9")
    migrated = editor.migrate(STRATEGY.format(body="pass"))
    assert migrated["from_version"] == 0 and migrated["to_version"] == 1 and migrated["code"].startswith("# studio-api: 1\n")
    assert editor.migrate(migrated["code"])["changes"] == []


def test_hover_explains_formula_operators_with_lookback_ctx_members_and_parameters():
    code = 'class Strategy:\n    def on_bar(self, ctx):\n        if ctx.rule("rsi(close, 14) < 30") and ctx.param("fast") > 0:\n            ctx.buy()\n'
    on_rsi = editor.hover(code, 3, code.splitlines()[2].index('rsi') + 2, last_values={"rsi(close, 14) < 30": 1.0})
    assert "rsi" in on_rsi["contents"] and on_rsi["lookback_bars"] == 14 and on_rsi["last_value"] == 1.0
    assert editor.hover(code, 4, 17)["contents"].startswith("`ctx.buy")
    assert "range 5 to 50 step 5" in editor.hover(code, 3, code.splitlines()[2].index('"fast"') + 2, params={"fast": {"value": 10, "min": 5, "max": 50, "step": 5}})["contents"]
    assert editor.hover(code, 1, 1) is None


def test_inlay_hints_show_parameter_values_warmup_and_argument_names():
    code = 'class Strategy:\n    def on_data(self, ctx):\n        n = ctx.param("n")\n        v = ctx.value("sma(close, 50)", "SPY")\n        ctx.market_order("SPY", 10)\n'
    hints = editor.inlay_hints(code, {"n": 20}, {"sma(close, 50)": 101.5})
    assert {"label": "= 20", "kind": "parameter"}.items() <= {k: hints[0][k] for k in ("label", "kind")}.items()
    assert any(h["label"] == "50 bars = 101.5" for h in hints) and any(h["label"] == "quantity:" and h["line"] == 5 for h in hints)


def test_code_actions_extract_convert_wrap_and_add_on_fill():
    code = 'class Strategy:\n    def on_bar(self, ctx):\n        x = ctx.value("sma(close, 50)")\n        ctx.buy()\n'
    titles = {a["title"]: a for a in editor.code_actions(code, 3, 24, 4, 18)}
    extract = titles["Extract 50 to parameter sma_window"]
    assert extract["parameter"] == {"name": "sma_window", "value": 50.0} and "sma(close, sma_window)" in extract["edits"][0]["text"]
    assert titles["Convert to an indicator object"]["edits"][0]["text"] == 'ctx.indicator("sma", period=50).value'
    assert "if ctx.position == 0:" in titles["Wrap in if ctx.position == 0"]["edits"][0]["text"]
    assert "Add on_fill" in titles and "def on_fill(self, ctx, fill)" in titles["Add on_fill"]["edits"][0]["text"]


def test_organise_imports_and_format_selection():
    assert editor.organise_imports("import sys\nimport math\nx = math.pi\n") == "import math\n\nx = math.pi\n"
    assert editor.format_range("x=1\ny  =  2\nz=3\n", 2, 2) == "x=1\ny = 2\nz=3\n"
    assert editor.format_range("def (:\n", 1, 1) == "def (:\n"


def test_editor_routes_and_codelens_true_rate(studio):  # noqa: F811
    code = 'class Strategy:\n    def on_bar(self, ctx):\n        if ctx.rule("close > 0"):\n            ctx.buy()\n'
    lenses = studio.post(f"{API}/codelens", json={"code": code, "symbol": "SPY", "debug_from": "2016-03-01"}).json()
    assert [x["title"] for x in lenses][:3] == ["Run on SPY", "Run on universe", "Debug from 2016-03-01"]
    assert lenses[-1]["title"].startswith("true on 100% of bars") and lenses[-1]["line"] == 3
    checked = studio.post(f"{API}/check", json={"code": code, "strictness": "strict", "severity": {"studio-api": "off"}}).json()
    assert not [p for p in checked["problems"] if p["code"] == "studio-api"]
    assert studio.post(f"{API}/organise-imports", json={"code": "import sys\n"}).json() == {"code": ""}
    assert studio.post(f"{API}/migrate", json={"code": "x = 1\n"}).json()["to_version"] == 1
    assert studio.post(f"{API}/hover", json={"code": code, "line": 3, "column": 23}).json()["lookback_bars"] == 0


def test_extract_variable_extract_function_and_quick_fixes():
    code = "import os\n\n\ndef f(a, b):\n    t = 0\n    x = (a + b) * 2\n    y = x + 1\n    return y + t\n"
    acts = {a["title"]: a for a in editor.code_actions(code, 6, 10, 6, 15)}
    assert acts["Extract variable value"]["edits"][0]["text"] == "    value = a + b\n" and acts["Extract variable value"]["edits"][1]["text"] == "value"
    fn = {a["title"]: a for a in editor.code_actions(code, 6, 1, 7, 14)}["Extract function extracted"]["edits"]
    assert "def extracted(a, b):" in fn[0]["text"] and "return y" in fn[0]["text"]
    assert fn[1]["text"] == "    y = extracted(a, b)"
    assert "Organise imports" in {a["title"]: a for a in editor.code_actions(code, 1, 1)}
    fixes = {p["code"]: p["fix"]["title"] for p in pycode.lint("import os\n\n\ndef f():\n    z = 1\n", {}, strictness="strict") if p.get("fix")}
    assert fixes["F401"] == "Remove unused import" and fixes["F841"] == "Prefix with _"
