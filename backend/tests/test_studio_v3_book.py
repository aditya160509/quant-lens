"""Paper book (P-20): netting across members and the freeze contract."""

import pytest

from app.services.studio_v3.core import book
from app.services.studio_v3.core.backtest import Refusal


def test_net_orders_cancels_opposite_sides():
    rows, saved = book.net_orders([("a", 1.0, [{"symbol": "AAPL", "action": "buy", "shares": 100}]),
                                   ("b", 1.0, [{"symbol": "AAPL", "action": "short", "shares": 60}, {"symbol": "MSFT", "action": "buy", "shares": 10}])])
    assert rows == [{"symbol": "AAPL", "action": "buy", "shares": 40}, {"symbol": "MSFT", "action": "buy", "shares": 10}]
    assert abs(saved - (1 - 50 / 170)) < 1e-9


def test_freeze_needs_two_members_and_positive_weights():
    with pytest.raises(Refusal):
        book.freeze([{"strategy_id": "x", "version": 1, "weight": 1}], "", None, "human")
    with pytest.raises(Refusal):
        book.freeze([{"strategy_id": "x", "version": 1, "weight": 0}, {"strategy_id": "y", "version": 1, "weight": 0}], "", None, "human")
