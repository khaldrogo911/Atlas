"""Valid specimens of every broker domain model.

Each fixture returns the simplest instance that satisfies every rule. Tests
that check a rule build their invalid case by taking one of these apart, so a
failure points at the field under test rather than at a typo three fields
away.
"""

from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal

import pytest

from atlas.broker.models import (
    Account,
    Candle,
    Connection,
    ConnectionState,
    Execution,
    Order,
    OrderSide,
    OrderStatus,
    OrderType,
    Position,
    PositionSide,
    Symbol,
    SymbolTradeMode,
    Tick,
    Timeframe,
)

#: A fixed instant. Tests must never depend on the wall clock.
#:
#: Each fixture below is named after its model in lower case, so a test can
#: reach any of them with ``request.getfixturevalue(cls.__name__.lower())``.
NOW = datetime(2026, 8, 2, 12, 0, tzinfo=UTC)


@pytest.fixture
def account() -> Account:
    return Account(
        account_id="9001234",
        broker="Example Brokerage",
        server="Example-Live",
        currency="USD",
        balance=Decimal("50000.00"),
        equity=Decimal("50120.50"),
        margin=Decimal("1200.00"),
        free_margin=Decimal("48920.50"),
        margin_level=Decimal("4176.71"),
        leverage=30,
        trade_allowed=True,
        timestamp=NOW,
    )


@pytest.fixture
def symbol() -> Symbol:
    return Symbol(
        symbol="EURUSD",
        description="Euro vs US Dollar",
        base_currency="EUR",
        quote_currency="USD",
        digits=5,
        point=Decimal("0.00001"),
        tick_size=Decimal("0.00001"),
        contract_size=Decimal("100000"),
        min_volume=Decimal("0.01"),
        max_volume=Decimal("100"),
        volume_step=Decimal("0.01"),
        spread=12,
        trade_mode=SymbolTradeMode.FULL,
    )


@pytest.fixture
def tick() -> Tick:
    return Tick(
        symbol="EURUSD",
        bid=Decimal("1.16240"),
        ask=Decimal("1.16252"),
        timestamp=NOW,
    )


@pytest.fixture
def candle() -> Candle:
    return Candle(
        symbol="EURUSD",
        timeframe=Timeframe.M15,
        open=Decimal("1.16200"),
        high=Decimal("1.16310"),
        low=Decimal("1.16180"),
        close=Decimal("1.16245"),
        volume=Decimal("1834"),
        open_time=NOW,
        close_time=NOW.replace(minute=15),
        is_closed=True,
    )


@pytest.fixture
def order() -> Order:
    return Order(
        order_id="ORD-1",
        symbol="EURUSD",
        side=OrderSide.BUY,
        type=OrderType.LIMIT,
        volume=Decimal("0.10"),
        price=Decimal("1.16000"),
        stop_loss=Decimal("1.15500"),
        take_profit=Decimal("1.17000"),
        status=OrderStatus.PENDING,
        created_at=NOW,
        updated_at=NOW,
    )


@pytest.fixture
def position() -> Position:
    return Position(
        position_id="POS-1",
        symbol="EURUSD",
        side=PositionSide.LONG,
        volume=Decimal("0.10"),
        entry_price=Decimal("1.16200"),
        current_price=Decimal("1.16245"),
        profit=Decimal("4.50"),
        swap=Decimal("-0.32"),
        commission=Decimal("-0.70"),
        opened_at=NOW,
    )


@pytest.fixture
def execution() -> Execution:
    return Execution(
        execution_id="DEAL-1",
        order_id="ORD-1",
        symbol="EURUSD",
        price=Decimal("1.16245"),
        volume=Decimal("0.10"),
        commission=Decimal("-0.35"),
        swap=Decimal("0"),
        timestamp=NOW,
    )


@pytest.fixture
def connection() -> Connection:
    return Connection(
        state=ConnectionState.CONNECTED,
        connected=True,
        latency_ms=42.5,
        last_heartbeat=NOW,
        broker="Example Brokerage",
        server="Example-Live",
    )
