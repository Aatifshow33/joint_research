from __future__ import annotations

from joint_research.predmarket_arb.depth import fillable_size_at_or_below


def _asks() -> list[dict[str, str]]:
    return [
        {"price": "0.40", "size": "100"},
        {"price": "0.41", "size": "50"},
        {"price": "0.45", "size": "200"},
    ]


def test_fillable_sums_levels_at_or_below_max_price() -> None:
    assert fillable_size_at_or_below(_asks(), max_price=0.41) == 150


def test_fillable_includes_exact_price_level() -> None:
    assert fillable_size_at_or_below(_asks(), max_price=0.40) == 100


def test_fillable_zero_when_all_levels_too_expensive() -> None:
    assert fillable_size_at_or_below(_asks(), max_price=0.30) == 0


def test_fillable_ignores_malformed_levels() -> None:
    asks = [
        {"price": "x", "size": "100"},
        {"price": "0.40", "size": None},
        {"price": "0.40", "size": "5"},
    ]
    assert fillable_size_at_or_below(asks, max_price=0.5) == 5


def test_fillable_floors_fractional_size() -> None:
    asks = [{"price": "0.4", "size": "10.9"}]
    assert fillable_size_at_or_below(asks, max_price=0.5) == 10
