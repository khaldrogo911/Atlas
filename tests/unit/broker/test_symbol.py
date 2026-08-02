"""Unit tests for the Symbol model."""

from __future__ import annotations

from decimal import Decimal

import pytest
from pydantic import ValidationError

from atlas.broker.models import Symbol, SymbolTradeMode

pytestmark = pytest.mark.unit


def _symbol(symbol: Symbol, **overrides: object) -> Symbol:
    """Revalidate a valid symbol with the given fields replaced."""
    return Symbol.model_validate({**symbol.model_dump(), **overrides})


class TestPointAndDigits:
    @pytest.mark.parametrize(
        ("digits", "point"),
        [
            (5, "0.00001"),
            (3, "0.001"),
            (2, "0.01"),
            (0, "1"),
        ],
    )
    def test_a_consistent_pair_is_accepted(self, digits: int, point: str, symbol: Symbol) -> None:
        result = _symbol(symbol, digits=digits, point=Decimal(point), tick_size=Decimal(point))

        assert result.point == Decimal(point)

    def test_a_point_that_contradicts_digits_is_rejected(self, symbol: Symbol) -> None:
        # Off by a power of ten is the classic adapter mis-mapping, and every
        # distance converted through `point` inherits the error.
        with pytest.raises(ValidationError, match="must equal"):
            _symbol(symbol, digits=5, point=Decimal("0.0001"))

    def test_the_rule_compares_value_not_representation(self, symbol: Symbol) -> None:
        # Decimal equality ignores the exponent, so a venue sending 0.00001000
        # is accepted where a string comparison would have rejected it.
        result = _symbol(symbol, digits=5, point=Decimal("0.00001000"))

        assert result.point == Decimal("0.00001")

    def test_tick_size_may_be_a_multiple_of_point(self, symbol: Symbol) -> None:
        # Some instruments are quoted in steps larger than one point.
        result = _symbol(symbol, tick_size=Decimal("0.00005"))

        assert result.tick_size == Decimal("0.00005")


class TestVolumeBounds:
    def test_a_maximum_below_the_minimum_is_rejected(self, symbol: Symbol) -> None:
        with pytest.raises(ValidationError, match="max_volume"):
            _symbol(symbol, min_volume=Decimal("1.0"), max_volume=Decimal("0.5"))

    def test_equal_bounds_are_accepted(self, symbol: Symbol) -> None:
        # A single permitted size is a real, if unusual, venue configuration.
        result = _symbol(symbol, min_volume=Decimal("1.0"), max_volume=Decimal("1.0"))

        assert result.min_volume == result.max_volume

    @pytest.mark.parametrize("field", ["min_volume", "max_volume", "volume_step"])
    def test_a_zero_bound_is_rejected(self, field: str, symbol: Symbol) -> None:
        with pytest.raises(ValidationError, match="greater than 0"):
            _symbol(symbol, **{field: Decimal(0)})


class TestTradeMode:
    @pytest.mark.parametrize("mode", list(SymbolTradeMode))
    def test_every_mode_is_accepted(self, mode: SymbolTradeMode, symbol: Symbol) -> None:
        assert _symbol(symbol, trade_mode=mode).trade_mode is mode

    def test_an_unknown_mode_is_rejected(self, symbol: Symbol) -> None:
        with pytest.raises(ValidationError):
            _symbol(symbol, trade_mode="SOMETIMES")


class TestDescription:
    def test_the_description_defaults_to_empty(self, symbol: Symbol) -> None:
        payload = symbol.model_dump()
        del payload["description"]

        assert Symbol.model_validate(payload).description == ""

    def test_an_over_long_description_is_rejected(self, symbol: Symbol) -> None:
        with pytest.raises(ValidationError, match="at most 256 characters"):
            _symbol(symbol, description="x" * 257)
