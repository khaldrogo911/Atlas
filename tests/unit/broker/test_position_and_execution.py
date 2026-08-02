"""Unit tests for the Position and Execution models."""

from __future__ import annotations

from decimal import Decimal

import pytest
from pydantic import ValidationError

from atlas.broker.models import Execution, Position, PositionSide

pytestmark = pytest.mark.unit


def _position(position: Position, **overrides: object) -> Position:
    """Revalidate a valid position with the given fields replaced."""
    return Position.model_validate({**position.model_dump(), **overrides})


def _execution(execution: Execution, **overrides: object) -> Execution:
    """Revalidate a valid execution with the given fields replaced."""
    return Execution.model_validate({**execution.model_dump(), **overrides})


class TestPositionAmounts:
    @pytest.mark.parametrize("field", ["profit", "swap", "commission"])
    def test_a_signed_amount_may_be_negative(self, field: str, position: Position) -> None:
        # Swap and commission are usually negative; a constraint here would
        # reject the ordinary case.
        result = _position(position, **{field: Decimal("-12.34")})

        assert getattr(result, field) == Decimal("-12.34")

    @pytest.mark.parametrize("field", ["profit", "swap", "commission"])
    def test_a_signed_amount_may_be_zero(self, field: str, position: Position) -> None:
        assert getattr(_position(position, **{field: Decimal(0)}), field) == 0

    def test_profit_is_not_recomputed_from_prices(self, position: Position) -> None:
        # Deriving it would need the contract size, the broker's own quote-to-
        # deposit conversion rate and the broker's rounding. This layer has
        # none of those and must not guess at them.
        result = _position(
            position,
            entry_price=Decimal("1.16200"),
            current_price=Decimal("1.16245"),
            profit=Decimal("999.99"),
        )

        assert result.profit == Decimal("999.99")

    def test_a_zero_volume_position_is_rejected(self, position: Position) -> None:
        with pytest.raises(ValidationError, match="greater than 0"):
            _position(position, volume=Decimal(0))

    @pytest.mark.parametrize("side", list(PositionSide))
    def test_both_sides_are_representable(self, side: PositionSide, position: Position) -> None:
        assert _position(position, side=side).side is side


class TestExecution:
    def test_a_fill_records_its_own_price_and_size(self, execution: Execution) -> None:
        result = _execution(execution, price=Decimal("1.16250"), volume=Decimal("0.05"))

        assert result.price == Decimal("1.16250")
        assert result.volume == Decimal("0.05")

    def test_a_zero_volume_fill_is_rejected(self, execution: Execution) -> None:
        # A fill of nothing is not a fill.
        with pytest.raises(ValidationError, match="greater than 0"):
            _execution(execution, volume=Decimal(0))

    def test_a_non_positive_price_is_rejected(self, execution: Execution) -> None:
        with pytest.raises(ValidationError, match="greater than 0"):
            _execution(execution, price=Decimal(0))

    def test_several_fills_may_share_one_order(self, execution: Execution) -> None:
        # A partial fill is an additional record, not a modified order.
        first = _execution(execution, execution_id="DEAL-1", volume=Decimal("0.04"))
        second = _execution(execution, execution_id="DEAL-2", volume=Decimal("0.06"))

        assert first.order_id == second.order_id
        assert first != second
        assert len({first, second}) == 2

    def test_swap_may_be_settled_on_a_closing_fill(self, execution: Execution) -> None:
        assert _execution(execution, swap=Decimal("-1.87")).swap == Decimal("-1.87")

    def test_an_execution_requires_an_order(self, execution: Execution) -> None:
        payload = execution.model_dump()
        del payload["order_id"]

        with pytest.raises(ValidationError, match="Field required"):
            Execution.model_validate(payload)
