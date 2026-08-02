"""Types the broker port speaks that are not domain models.

:mod:`atlas.broker.models` describes what a venue *reports*. This module
describes what the port *takes*: the vocabulary of identifiers, the shape of an
order that has not been placed yet, the callback signatures a subscription
delivers through, and the sentinel that separates "leave this alone" from
"clear this".

Two decisions are load bearing:

Aliases are defined *in terms of* the domain primitives
    ``SymbolName`` is not a second spelling of ``SymbolCode`` — it is that
    type, under the name the port uses. Defining them side by side would create
    two rules for one concept and guarantee they diverge. Because the aliases
    resolve to ``Annotated`` primitives, a value used as a plain argument is an
    ordinary ``str``, and the same alias used as a model field still validates.

The aliases are transparent, not opaque
    ``type OrderID = Identifier`` makes ``OrderID`` a synonym for ``str`` to a
    type checker, so ``cancel_order(order.order_id)`` needs no wrapping. It
    documents intent and gives one place to change the representation; it does
    *not* stop an order id being passed where a position id was meant. Making
    that a checked error needs :func:`typing.NewType`, which the domain models
    would have to adopt in the same change. See ``README.md``.
"""

from __future__ import annotations

from collections.abc import Callable
from enum import Enum, auto
from typing import Final

from pydantic import BaseModel, Field, model_validator

from atlas.broker.models import (
    BROKER_MODEL_CONFIG,
    Candle,
    Identifier,
    Name,
    OrderSide,
    OrderType,
    Price,
    SymbolCode,
    Tick,
    Volume,
)

__all__ = [
    "UNSET",
    "BrokerName",
    "BrokerVersion",
    "CandleHandler",
    "ExecutionID",
    "OrderID",
    "OrderRequest",
    "PositionID",
    "ServerName",
    "SubscriptionID",
    "SymbolName",
    "TickHandler",
    "Unset",
]

# --- Identity -----------------------------------------------------------------

#: The name of a broker, as Atlas refers to it: ``"IC Markets"``, ``"OANDA"``.
type BrokerName = Name

#: The name of a specific trade server or environment within a broker.
type ServerName = Name

#: An instrument code. Canonicalised to upper case when it enters a model.
type SymbolName = SymbolCode

#: A venue-assigned order ticket.
type OrderID = Identifier

#: A venue-assigned position ticket.
type PositionID = Identifier

#: A venue-assigned deal or fill ticket.
type ExecutionID = Identifier

#: A handle returned by a subscribe call, used to cancel that subscription.
#:
#: Subscriptions are cancelled by handle rather than by symbol because two
#: components may independently subscribe to the same instrument. Unsubscribing
#: by symbol would silently cut off the other one.
type SubscriptionID = Identifier

# --- Delivery -----------------------------------------------------------------

#: Called once per quote update on a tick subscription.
#:
#: Delivery is a plain callback rather than an event bus: the port defines the
#: contract, and an implementation is free to publish events on top of it.
type TickHandler = Callable[[Tick], None]

#: Called once per bar update on a candle subscription.
#:
#: Whether the bar is final is carried by :attr:`~atlas.broker.models.Candle.is_closed`,
#: so a handler that acts only on completed bars can say so explicitly.
type CandleHandler = Callable[[Candle], None]


# --- Partial updates ----------------------------------------------------------


class Unset(Enum):
    """Sentinel type distinguishing "not supplied" from an explicit ``None``.

    :meth:`~atlas.broker.adapter.BrokerAdapter.modify_order` needs three
    outcomes per field: leave it as it is, change it to a value, or remove it
    altogether. ``None`` can only express two of those. A single-member
    enumeration is used because type checkers narrow ``is UNSET`` correctly,
    which an ``object()`` sentinel does not achieve.
    """

    SENTINEL = auto()

    def __repr__(self) -> str:
        """Render as the exported constant, so signatures read ``= UNSET``."""
        return "UNSET"


#: The value meaning "leave this field as the venue currently has it".
UNSET: Final = Unset.SENTINEL


# --- Requests -----------------------------------------------------------------


class OrderRequest(BaseModel):
    """An instruction to place an order, before any venue has seen it.

    Distinct from :class:`~atlas.broker.models.Order`, which is what a venue
    reports back. An order carries a ticket, a status and timestamps that only
    the venue can assign; requiring a caller to invent them in order to ask for
    a fill would make every one of those fields a lie.

    The structural rules are the same ones
    :class:`~atlas.broker.models.Order` applies, and for the same reason: a
    LIMIT order with no limit price is not a risky order, it is an
    incompletely built one. Both read the requirement off
    :class:`~atlas.broker.models.OrderType`, so the rule itself is stated once.

    Whether the request is *wise* — the size against the account, the stop on
    the correct side of entry, the instrument permitted by policy — is a risk
    decision, made against state neither this model nor the port can see.
    """

    model_config = BROKER_MODEL_CONFIG

    symbol: SymbolName = Field(description="Instrument to transact in.")
    side: OrderSide = Field(description="Direction of the order.")
    type: OrderType = Field(description="How the order should be presented to the venue.")
    volume: Volume = Field(description="Requested quantity, in lots.")
    price: Price | None = Field(
        default=None,
        description=(
            "Working price: the limit for a LIMIT or STOP_LIMIT order, the "
            "trigger for a STOP order. Omitted on a MARKET order."
        ),
    )
    stop_price: Price | None = Field(
        default=None,
        description=(
            "Trigger price of a STOP_LIMIT order, which needs one price to "
            "activate and a second to bound the fill. Must be absent on every "
            "other type."
        ),
    )
    stop_loss: Price | None = Field(
        default=None, description="Protective stop to attach to the resulting position."
    )
    take_profit: Price | None = Field(
        default=None, description="Profit target to attach to the resulting position."
    )

    @model_validator(mode="after")
    def _check_request_is_well_formed(self) -> OrderRequest:
        """Reject a request whose prices do not match its order type.

        Returns:
            The validated instance.

        Raises:
            ValueError: If a required price is missing, or a price is present
                on a type that has no use for it.
        """
        if self.type.requires_price and self.price is None:
            msg = f"price is required for a {self.type} order"
            raise ValueError(msg)
        if self.type.requires_stop_price and self.stop_price is None:
            msg = f"stop_price is required for a {self.type} order"
            raise ValueError(msg)
        if not self.type.requires_stop_price and self.stop_price is not None:
            msg = (
                f"stop_price must be None for a {self.type} order; only STOP_LIMIT "
                "carries a trigger separate from its working price"
            )
            raise ValueError(msg)
        return self


class BrokerVersion(BaseModel):
    """Identity and build of the venue interface an adapter is speaking to.

    Structured rather than a bare string because callers compare builds — to
    gate a workaround, or to refuse to trade against a build older than a
    known-bad release. Returning a string would push venue-specific version
    parsing into business logic, which is the leak this port exists to stop.
    """

    model_config = BROKER_MODEL_CONFIG

    name: Name = Field(description="Product name, such as 'MetaTrader 5' or 'OANDA v20'.")
    version: Name = Field(description="Version as the venue reports it, such as '5.0.4620'.")
    build: int | None = Field(
        default=None, ge=0, description="Build number, where the venue exposes one separately."
    )
    api_version: Name | None = Field(
        default=None,
        description="Version of the API or protocol, where it is versioned apart from the product.",
    )
