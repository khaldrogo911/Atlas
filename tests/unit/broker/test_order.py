"""Unit tests for the Order model."""

from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal

import pytest
from pydantic import ValidationError

from atlas.broker.models import Order, OrderSide, OrderStatus, OrderType

pytestmark = pytest.mark.unit


def _order(order: Order, **overrides: object) -> Order:
    """Revalidate a valid order with the given fields replaced."""
    return Order.model_validate({**order.model_dump(), **overrides})


class TestPriceRequirements:
    def test_a_market_order_needs_no_price(self, order: Order) -> None:
        result = _order(order, type=OrderType.MARKET, price=None)

        assert result.price is None

    def test_a_market_order_may_carry_an_indicative_price(self, order: Order) -> None:
        result = _order(order, type=OrderType.MARKET, price=Decimal("1.16240"))

        assert result.price == Decimal("1.16240")

    @pytest.mark.parametrize("order_type", [OrderType.LIMIT, OrderType.STOP, OrderType.STOP_LIMIT])
    def test_a_working_order_without_a_price_is_rejected(
        self, order_type: OrderType, order: Order
    ) -> None:
        # Not a risky order — an incompletely mapped one. The venue would
        # reject it with an opaque code; this names the field.
        with pytest.raises(ValidationError, match="price is required"):
            _order(order, type=order_type, price=None, stop_price=Decimal("1.16000"))


class TestStopPrice:
    def test_a_stop_limit_order_carries_both_prices(self, order: Order) -> None:
        result = _order(
            order,
            type=OrderType.STOP_LIMIT,
            price=Decimal("1.16300"),
            stop_price=Decimal("1.16280"),
        )

        assert result.price == Decimal("1.16300")
        assert result.stop_price == Decimal("1.16280")

    def test_a_stop_limit_order_without_a_trigger_is_rejected(self, order: Order) -> None:
        with pytest.raises(ValidationError, match="stop_price is required"):
            _order(order, type=OrderType.STOP_LIMIT, price=Decimal("1.16300"), stop_price=None)

    @pytest.mark.parametrize("order_type", [OrderType.MARKET, OrderType.LIMIT, OrderType.STOP])
    def test_a_trigger_on_any_other_type_is_rejected(
        self, order_type: OrderType, order: Order
    ) -> None:
        # A STOP order's trigger is its `price`; a second one would leave two
        # fields claiming to be the trigger and no rule for which wins.
        with pytest.raises(ValidationError, match="stop_price must be None"):
            _order(
                order,
                type=order_type,
                price=Decimal("1.16300"),
                stop_price=Decimal("1.16280"),
            )


class TestTimestamps:
    def test_an_update_before_creation_is_rejected(self, order: Order) -> None:
        with pytest.raises(ValidationError, match="must not precede"):
            _order(order, updated_at=datetime(2026, 8, 2, 11, 0, tzinfo=UTC))

    def test_an_unmodified_order_may_share_both_timestamps(self, order: Order) -> None:
        result = _order(order, updated_at=order.created_at)

        assert result.updated_at == result.created_at


class TestAttachedLevels:
    def test_protective_levels_are_optional(self, order: Order) -> None:
        result = _order(order, stop_loss=None, take_profit=None)

        assert result.stop_loss is None
        assert result.take_profit is None

    def test_an_inverted_stop_loss_is_accepted_here(self, order: Order) -> None:
        # Deliberate. Whether a stop sits on the correct side of the entry is a
        # risk decision, made against account state this model cannot see. The
        # model layer refuses only what is structurally malformed.
        result = _order(
            order,
            side=OrderSide.BUY,
            price=Decimal("1.16000"),
            stop_loss=Decimal("1.17000"),
        )

        assert result.stop_loss == Decimal("1.17000")


class TestLifecycle:
    @pytest.mark.parametrize("status", list(OrderStatus))
    def test_every_status_is_representable(self, status: OrderStatus, order: Order) -> None:
        assert _order(order, status=status).status is status

    def test_a_status_change_produces_a_new_instance(self, order: Order) -> None:
        # The model is frozen, so an order's history is a sequence of values
        # rather than one object that forgets where it has been.
        filled = Order.model_validate({**order.model_dump(), "status": OrderStatus.FILLED})

        assert order.status is OrderStatus.PENDING
        assert filled.status is OrderStatus.FILLED
        assert filled != order

    @pytest.mark.parametrize("side", list(OrderSide))
    def test_both_sides_are_representable(self, side: OrderSide, order: Order) -> None:
        assert _order(order, side=side).side is side
