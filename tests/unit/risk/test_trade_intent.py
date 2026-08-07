"""Tests for the intent a strategy proposes.

``TradeIntent`` is a recommendation. What is under test is that it carries what
risk needs to judge one, that it refuses a value no risk decision could be made
against, and — the part that is easy to lose later — that it still carries
*nothing* about how an order should reach a venue.
"""

from __future__ import annotations

from decimal import Decimal
from typing import Final

import pytest
from pydantic import ValidationError

from atlas.broker.models import OrderSide
from atlas.risk import TradeIntent

pytestmark = pytest.mark.unit

#: Fields that belong to order *presentation*, which is execution's.
#:
#: An intent that named an order type or a working price would be instructing
#: rather than recommending, and the boundary would have moved without anyone
#: deciding to move it. ``intent_id`` and ``created_at`` are absent for their
#: own reasons, recorded on the model.
FIELDS_THAT_MUST_STAY_ABSENT: Final = (
    "type",
    "order_type",
    "price",
    "stop_price",
    "volume",
    "approved_volume",
    "intent_id",
    "created_at",
)


def _fields(**overrides: object) -> dict[str, object]:
    """Build a well-formed intent payload with the given fields replaced."""
    return {
        "symbol": "EURUSD",
        "side": OrderSide.BUY,
        "requested_volume": Decimal("0.10"),
    } | overrides


class TestWellFormed:
    def test_the_minimal_intent_is_the_three_fields_risk_cannot_judge_without(self) -> None:
        intent = TradeIntent.model_validate(_fields())

        assert intent.symbol == "EURUSD"
        assert intent.side is OrderSide.BUY
        assert intent.requested_volume == Decimal("0.10")

    def test_the_protective_levels_default_to_absent(self) -> None:
        intent = TradeIntent.model_validate(_fields())

        assert intent.stop_loss is None
        assert intent.take_profit is None

    def test_the_protective_levels_are_carried_when_given(self) -> None:
        intent = TradeIntent.model_validate(
            _fields(stop_loss=Decimal("1.0950"), take_profit=Decimal("1.1100"))
        )

        assert intent.stop_loss == Decimal("1.0950")
        assert intent.take_profit == Decimal("1.1100")

    def test_the_symbol_is_canonicalised_the_way_the_broker_layer_canonicalises_it(self) -> None:
        assert TradeIntent.model_validate(_fields(symbol="  eurusd  ")).symbol == "EURUSD"

    def test_either_side_is_expressible(self) -> None:
        assert TradeIntent.model_validate(_fields(side=OrderSide.SELL)).side is OrderSide.SELL


class TestRefusal:
    @pytest.mark.parametrize("missing", ["symbol", "side", "requested_volume"])
    def test_an_intent_missing_a_required_field_is_refused(self, missing: str) -> None:
        payload = _fields()
        del payload[missing]

        with pytest.raises(ValidationError):
            TradeIntent.model_validate(payload)

    @pytest.mark.parametrize("volume", [Decimal("0"), Decimal("-0.01")])
    def test_a_volume_that_is_not_positive_is_refused(self, volume: Decimal) -> None:
        with pytest.raises(ValidationError):
            TradeIntent.model_validate(_fields(requested_volume=volume))

    @pytest.mark.parametrize("field", ["stop_loss", "take_profit"])
    @pytest.mark.parametrize("price", [Decimal("0"), Decimal("-1.10")])
    def test_a_protective_level_that_is_not_a_positive_price_is_refused(
        self, field: str, price: Decimal
    ) -> None:
        with pytest.raises(ValidationError):
            TradeIntent.model_validate(_fields(**{field: price}))

    @pytest.mark.parametrize("symbol", ["", "   "])
    def test_a_symbol_with_no_content_is_refused(self, symbol: str) -> None:
        with pytest.raises(ValidationError):
            TradeIntent.model_validate(_fields(symbol=symbol))

    def test_a_side_the_broker_layer_would_not_recognise_is_refused(self) -> None:
        with pytest.raises(ValidationError):
            TradeIntent.model_validate(_fields(side="buy"))

    def test_an_unknown_field_is_refused_rather_than_ignored(self) -> None:
        with pytest.raises(ValidationError):
            TradeIntent.model_validate(_fields(requested_volumes=Decimal("0.10")))


class TestImmutability:
    def test_an_intent_cannot_be_edited_after_it_is_made(self) -> None:
        intent = TradeIntent.model_validate(_fields())

        with pytest.raises(ValidationError):
            intent.requested_volume = Decimal("5.00")

    def test_an_intent_is_hashable_so_it_can_be_shared_without_copying(self) -> None:
        intent = TradeIntent.model_validate(_fields())
        identical = TradeIntent.model_validate(_fields())

        assert hash(intent) == hash(identical)


class TestTheShapeItself:
    """The absence of a field is a decision, so it is asserted like one."""

    @pytest.mark.parametrize("field", FIELDS_THAT_MUST_STAY_ABSENT)
    def test_the_intent_carries_nothing_about_order_presentation(self, field: str) -> None:
        assert field not in TradeIntent.model_fields

    def test_the_intent_carries_exactly_the_five_specified_fields(self) -> None:
        assert set(TradeIntent.model_fields) == {
            "symbol",
            "side",
            "requested_volume",
            "stop_loss",
            "take_profit",
        }
