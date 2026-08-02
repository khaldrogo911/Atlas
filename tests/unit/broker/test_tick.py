"""Unit tests for the Tick model."""

from __future__ import annotations

from decimal import Decimal

import pytest
from pydantic import ValidationError

from atlas.broker.models import Tick

pytestmark = pytest.mark.unit


def _tick(tick: Tick, **overrides: object) -> Tick:
    """Revalidate a valid tick with the given fields replaced."""
    return Tick.model_validate({**tick.model_dump(), **overrides})


class TestSpread:
    def test_a_crossed_quote_is_rejected(self, tick: Tick) -> None:
        # Bid above ask from a single venue means the two were mapped the wrong
        # way round, which presents as a strategy that profits on every tick.
        with pytest.raises(ValidationError, match="greater than or equal to bid"):
            _tick(tick, bid=Decimal("1.16300"), ask=Decimal("1.16200"))

    def test_a_zero_spread_is_accepted(self, tick: Tick) -> None:
        result = _tick(tick, bid=Decimal("1.16240"), ask=Decimal("1.16240"))

        assert result.spread == 0

    def test_spread_is_the_difference(self, tick: Tick) -> None:
        result = _tick(tick, bid=Decimal("1.16240"), ask=Decimal("1.16252"))

        assert result.spread == Decimal("0.00012")

    def test_spread_is_never_negative(self, tick: Tick) -> None:
        assert _tick(tick).spread >= 0


class TestMid:
    def test_mid_is_the_midpoint(self, tick: Tick) -> None:
        result = _tick(tick, bid=Decimal("1.16240"), ask=Decimal("1.16260"))

        assert result.mid == Decimal("1.16250")

    def test_mid_lies_between_the_quotes(self, tick: Tick) -> None:
        result = _tick(tick, bid=Decimal("1.16240"), ask=Decimal("1.16253"))

        assert result.bid <= result.mid <= result.ask


class TestLastPrice:
    def test_last_is_optional(self, tick: Tick) -> None:
        # Spot FX venues report no trades, so absence is the normal case.
        assert _tick(tick, last=None).last is None

    def test_last_is_carried_when_reported(self, tick: Tick) -> None:
        assert _tick(tick, last=Decimal("1.16245")).last == Decimal("1.16245")

    def test_a_non_positive_last_is_rejected(self, tick: Tick) -> None:
        with pytest.raises(ValidationError, match="greater than 0"):
            _tick(tick, last=Decimal(0))


class TestVolume:
    def test_volume_defaults_to_zero(self, tick: Tick) -> None:
        payload = tick.model_dump()
        del payload["volume"]

        assert Tick.model_validate(payload).volume == 0
