"""Unit tests for the broker domain enumerations."""

from __future__ import annotations

import json
from datetime import timedelta
from typing import TYPE_CHECKING

import pytest

from atlas.broker.models import (
    ConnectionState,
    OrderSide,
    OrderStatus,
    OrderType,
    PositionSide,
    SymbolTradeMode,
    Timeframe,
)

if TYPE_CHECKING:
    from enum import StrEnum

pytestmark = pytest.mark.unit

ALL_ENUMS: tuple[type[StrEnum], ...] = (
    ConnectionState,
    OrderSide,
    OrderStatus,
    OrderType,
    PositionSide,
    SymbolTradeMode,
    Timeframe,
)

ALL_MEMBERS = [member for enum_class in ALL_ENUMS for member in enum_class]


class TestWireFormat:
    """The serialised form of a member is its name, and nothing else."""

    @pytest.mark.parametrize("member", ALL_MEMBERS, ids=str)
    def test_value_equals_name(self, member: StrEnum) -> None:
        assert member.value == member.name

    @pytest.mark.parametrize("member", ALL_MEMBERS, ids=str)
    def test_member_is_a_string(self, member: StrEnum) -> None:
        assert isinstance(member, str)
        assert json.dumps(member) == f'"{member.value}"'

    @pytest.mark.parametrize("enum_class", ALL_ENUMS, ids=lambda cls: cls.__name__)
    def test_values_are_unique(self, enum_class: type[StrEnum]) -> None:
        values = [member.value for member in enum_class]
        assert len(values) == len(set(values))


class TestMembership:
    """Pinned membership. Adding or removing a member is a contract change."""

    def test_order_side(self) -> None:
        assert {member.name for member in OrderSide} == {"BUY", "SELL"}

    def test_order_type(self) -> None:
        assert {member.name for member in OrderType} == {
            "MARKET",
            "LIMIT",
            "STOP",
            "STOP_LIMIT",
        }

    def test_order_status(self) -> None:
        assert {member.name for member in OrderStatus} == {
            "CREATED",
            "PENDING",
            "FILLED",
            "PARTIALLY_FILLED",
            "CANCELLED",
            "REJECTED",
            "EXPIRED",
        }

    def test_position_side(self) -> None:
        assert {member.name for member in PositionSide} == {"LONG", "SHORT"}

    def test_connection_state(self) -> None:
        assert {member.name for member in ConnectionState} == {
            "DISCONNECTED",
            "CONNECTING",
            "CONNECTED",
            "RECONNECTING",
            "DEGRADED",
            "DISCONNECTING",
        }

    def test_timeframe(self) -> None:
        assert {member.name for member in Timeframe} == {
            "M1",
            "M5",
            "M15",
            "M30",
            "H1",
            "H4",
            "D1",
        }


class TestSideBehaviour:
    @pytest.mark.parametrize(
        ("side", "expected"),
        [(OrderSide.BUY, OrderSide.SELL), (OrderSide.SELL, OrderSide.BUY)],
    )
    def test_order_side_opposite(self, side: OrderSide, expected: OrderSide) -> None:
        assert side.opposite is expected

    @pytest.mark.parametrize("side", list(OrderSide))
    def test_order_side_opposite_is_an_involution(self, side: OrderSide) -> None:
        assert side.opposite.opposite is side

    @pytest.mark.parametrize("side", list(PositionSide))
    def test_position_side_opposite_is_an_involution(self, side: PositionSide) -> None:
        assert side.opposite is not side
        assert side.opposite.opposite is side


class TestOrderTypeBehaviour:
    @pytest.mark.parametrize(
        ("order_type", "expected"),
        [
            (OrderType.MARKET, False),
            (OrderType.LIMIT, True),
            (OrderType.STOP, True),
            (OrderType.STOP_LIMIT, True),
        ],
    )
    def test_requires_price(self, order_type: OrderType, expected: bool) -> None:
        assert order_type.requires_price is expected

    @pytest.mark.parametrize(
        ("order_type", "expected"),
        [
            (OrderType.MARKET, False),
            (OrderType.LIMIT, False),
            (OrderType.STOP, False),
            (OrderType.STOP_LIMIT, True),
        ],
    )
    def test_requires_stop_price(self, order_type: OrderType, expected: bool) -> None:
        assert order_type.requires_stop_price is expected

    def test_a_type_needing_a_stop_price_also_needs_a_price(self) -> None:
        # A trigger without a limit is not a STOP_LIMIT order.
        for order_type in OrderType:
            if order_type.requires_stop_price:
                assert order_type.requires_price


class TestOrderStatusBehaviour:
    @pytest.mark.parametrize(
        ("status", "expected"),
        [
            (OrderStatus.CREATED, False),
            (OrderStatus.PENDING, False),
            (OrderStatus.PARTIALLY_FILLED, False),
            (OrderStatus.FILLED, True),
            (OrderStatus.CANCELLED, True),
            (OrderStatus.REJECTED, True),
            (OrderStatus.EXPIRED, True),
        ],
    )
    def test_is_terminal(self, status: OrderStatus, expected: bool) -> None:
        assert status.is_terminal is expected

    @pytest.mark.parametrize("status", list(OrderStatus))
    def test_terminal_and_active_partition_the_enum(self, status: OrderStatus) -> None:
        assert status.is_terminal is not status.is_active

    def test_both_sides_of_the_partition_are_populated(self) -> None:
        # A classification where every member lands on one side tests nothing.
        assert any(status.is_terminal for status in OrderStatus)
        assert any(status.is_active for status in OrderStatus)


class TestConnectionStateBehaviour:
    @pytest.mark.parametrize(
        ("state", "expected"),
        [
            (ConnectionState.DISCONNECTED, False),
            (ConnectionState.CONNECTING, False),
            (ConnectionState.CONNECTED, True),
            (ConnectionState.RECONNECTING, False),
            (ConnectionState.DEGRADED, True),
            (ConnectionState.DISCONNECTING, False),
        ],
    )
    def test_is_usable(self, state: ConnectionState, expected: bool) -> None:
        assert state.is_usable is expected

    @pytest.mark.parametrize(
        ("state", "expected"),
        [
            (ConnectionState.DISCONNECTED, False),
            (ConnectionState.CONNECTING, True),
            (ConnectionState.CONNECTED, False),
            (ConnectionState.RECONNECTING, True),
            (ConnectionState.DEGRADED, False),
            (ConnectionState.DISCONNECTING, True),
        ],
    )
    def test_is_transitional(self, state: ConnectionState, expected: bool) -> None:
        assert state.is_transitional is expected

    @pytest.mark.parametrize("state", list(ConnectionState))
    def test_no_state_is_both_usable_and_transitional(self, state: ConnectionState) -> None:
        assert not (state.is_usable and state.is_transitional)


class TestTimeframeBehaviour:
    @pytest.mark.parametrize("timeframe", list(Timeframe))
    def test_every_member_has_a_length(self, timeframe: Timeframe) -> None:
        # A missing table entry would raise KeyError, not return a wrong number.
        assert timeframe.minutes > 0

    @pytest.mark.parametrize(
        ("timeframe", "minutes"),
        [
            (Timeframe.M1, 1),
            (Timeframe.M5, 5),
            (Timeframe.M15, 15),
            (Timeframe.M30, 30),
            (Timeframe.H1, 60),
            (Timeframe.H4, 240),
            (Timeframe.D1, 1440),
        ],
    )
    def test_minutes(self, timeframe: Timeframe, minutes: int) -> None:
        assert timeframe.minutes == minutes

    @pytest.mark.parametrize("timeframe", list(Timeframe))
    def test_duration_agrees_with_minutes(self, timeframe: Timeframe) -> None:
        assert timeframe.duration == timedelta(minutes=timeframe.minutes)

    def test_declaration_order_is_ascending(self) -> None:
        lengths = [timeframe.minutes for timeframe in Timeframe]
        assert lengths == sorted(lengths)
        assert len(set(lengths)) == len(lengths)


class TestStrictParsing:
    @pytest.mark.parametrize(
        ("enum_class", "text"),
        [
            (OrderSide, "buy"),
            (OrderType, "market"),
            (OrderStatus, "filled"),
            (PositionSide, "long"),
            (ConnectionState, "connected"),
            (Timeframe, "m15"),
            (SymbolTradeMode, "full"),
        ],
        ids=lambda value: value if isinstance(value, str) else value.__name__,
    )
    def test_lowercase_spelling_is_rejected(self, enum_class: type[StrEnum], text: str) -> None:
        # Accepting a venue's own casing here would push the canonicalisation
        # decision to whichever caller happened to compare strings next.
        with pytest.raises(ValueError, match="is not a valid"):
            enum_class(text)
