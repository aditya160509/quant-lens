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
