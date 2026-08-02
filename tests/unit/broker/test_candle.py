"""Unit tests for the Candle model."""

from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal

import pytest
from pydantic import ValidationError

from atlas.broker.models import Candle, Timeframe

pytestmark = pytest.mark.unit


def _candle(candle: Candle, **overrides: object) -> Candle:
    """Revalidate a valid candle with the given fields replaced."""
    return Candle.model_validate({**candle.model_dump(), **overrides})


class TestOhlcOrdering:
    def test_a_high_below_the_open_is_rejected(self, candle: Candle) -> None:
        with pytest.raises(ValidationError, match="must be the greatest"):
            _candle(candle, high=Decimal("1.16100"))

    def test_a_high_below_the_close_is_rejected(self, candle: Candle) -> None:
        with pytest.raises(ValidationError, match="must be the greatest"):
            _candle(
                candle, open=Decimal("1.16200"), close=Decimal("1.16400"), high=Decimal("1.16300")
            )

    def test_a_low_above_the_open_is_rejected(self, candle: Candle) -> None:
        with pytest.raises(ValidationError, match="must be the least"):
            _candle(candle, low=Decimal("1.16250"))

    def test_a_low_above_the_high_is_rejected(self, candle: Candle) -> None:
        with pytest.raises(ValidationError, match="must be the"):
            _candle(candle, low=Decimal("1.16500"), high=Decimal("1.16300"))

    def test_a_flat_bar_is_accepted(self, candle: Candle) -> None:
        # Every price equal is a real bar on an illiquid instrument.
        flat = Decimal("1.16200")
        result = _candle(candle, open=flat, high=flat, low=flat, close=flat)

        assert result.price_range == 0

    def test_price_range_is_high_minus_low(self, candle: Candle) -> None:
        assert candle.price_range == candle.high - candle.low
        assert candle.price_range > 0


class TestPeriod:
    def test_a_close_time_before_the_open_time_is_rejected(self, candle: Candle) -> None:
        with pytest.raises(ValidationError, match="must be after"):
            _candle(candle, close_time=datetime(2026, 8, 2, 11, 0, tzinfo=UTC))

    def test_an_instantaneous_bar_is_rejected(self, candle: Candle) -> None:
        # Equal bounds describe no timeframe at all.
        with pytest.raises(ValidationError, match="must be after"):
            _candle(candle, close_time=candle.open_time)

    def test_the_period_may_exceed_the_nominal_timeframe(self, candle: Candle) -> None:
        # A daily bar spanning a weekend, or a session shortened by a daylight
        # saving change, is normal. The model does not police bar length.
        result = _candle(
            candle,
            timeframe=Timeframe.D1,
            close_time=datetime(2026, 8, 5, 12, 0, tzinfo=UTC),
        )

        assert result.close_time - result.open_time > Timeframe.D1.duration


class TestClosedFlag:
    def test_the_closed_flag_is_required(self, candle: Candle) -> None:
        # No default: an adapter must state whether the bar can still change.
        # A feature computed from a forming bar and compared against history
        # built from closed bars is how live and backtest silently diverge.
        payload = candle.model_dump()
        del payload["is_closed"]

        with pytest.raises(ValidationError, match="Field required"):
            Candle.model_validate(payload)

    def test_a_forming_bar_is_representable(self, candle: Candle) -> None:
        assert _candle(candle, is_closed=False).is_closed is False


class TestTimeframeField:
    @pytest.mark.parametrize("timeframe", list(Timeframe))
    def test_every_timeframe_is_accepted(self, timeframe: Timeframe, candle: Candle) -> None:
        assert _candle(candle, timeframe=timeframe).timeframe is timeframe

    def test_an_unknown_timeframe_is_rejected(self, candle: Candle) -> None:
        with pytest.raises(ValidationError):
            _candle(candle, timeframe="M7")
