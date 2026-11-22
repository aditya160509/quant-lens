from tests.test_studio_v3_backtest import studio  # noqa: F401  (fixture)

MAIN = "def sma(xs, n):\n    return sum(xs[-n:]) / n\n"
TESTS = """from main import sma
from studio.testing import bars


def test_ok():
    b = bars(50, seed=1)
    assert len(b["close"]) == 50 and b["high"][0] >= b["low"][0]
    assert sma([1, 2, 3], 2) == 2.5


def test_assert_line():
    x = sma([1, 2, 3], 3)
    assert x == 3


def test_boom():
    return 1 / 0
"""


def run(client, **body):
    r = client.post("/api/studio-v3/build/test", json={"code": MAIN, "files": {"test_main.py": TESTS}, **body})
    assert r.status_code == 200, r.text
    return {t["name"]: t for t in r.json()["tests"]}


def test_statuses_and_lines(studio):  # noqa: F811
    t = run(studio)
    assert t["test_ok"]["status"] == "passed"
    assert (t["test_assert_line"]["status"], t["test_assert_line"]["error_line"], t["test_assert_line"]["message"]) == ("failed", 13, "assert x == 3")
    assert t["test_boom"]["status"] == "error" and "ZeroDivisionError" in t["test_boom"]["message"] and t["test_boom"]["line"] == 16


def test_filters(studio):  # noqa: F811
    assert list(run(studio, name="test_ok")) == ["test_ok"]
    assert run(studio, file="other.py") == {}


def test_sandbox_refuses_os(studio):  # noqa: F811
    t = run(studio, files={"test_x.py": "import os\n\ndef test_a():\n    pass\n"})
    assert t["test_a"]["status"] == "error" and "not allowed" in t["test_a"]["message"]


def test_cells_sql_and_plot():
    from app.services.studio_v3.core import strategy_tests

    src = "# %%\nimport pandas as pd\nfrom studio.research import plot, sql\ndf = pd.DataFrame({'a': [1, 2, 3], 'b': [4.0, 5.0, 6.0]})\nplot(df['b'])\n# %%\nsql('select sum(a) as s from df where b > 4')\n"
    out = strategy_tests.run_cells({"main.py": "", "nb.py": src}, "nb.py", 1, only=False, symbols=[])["outputs"]
    assert not out[0]["error"] and out[0]["plots"][0]["series"]["b"] == [4.0, 5.0, 6.0]
    assert not out[1]["error"] and "5" in str(out[1]["value"])


def test_percent_cells_run_in_order_and_show_values():
    from app.services.studio_v3.core import strategy_tests

    src = "# %% load\nfrom studio.testing import bars\nb = bars(10)\nprint('n', len(b['close']))\n# %% stats\nclass K:\n    pass\nx = sum(b['close']) / 10\nx > 0\n# %% boom\n1 / 0\n"
    assert [c["line"] for c in strategy_tests.cells(src)] == [1, 5, 10]
    out = strategy_tests.run_cells({"main.py": "", "research.py": src}, "research.py", 1, only=False, symbols=[])["outputs"]
    assert [o["index"] for o in out] == [0, 1] and out[0]["stdout"] == "n 10\n" and out[1]["value"] is True and not out[1]["error"]
    err = strategy_tests.run_cells({"main.py": "", "research.py": src}, "research.py", 2, only=True, symbols=[])["outputs"]
    assert err[-1]["error"].startswith("ZeroDivisionError") and err[-1]["error_line"] == 11
