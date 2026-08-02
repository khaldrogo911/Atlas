"""An order and its lifecycle state at the venue."""

from __future__ import annotations

from pydantic import BaseModel, Field, model_validator

from atlas.broker.models.enums import OrderSide, OrderStatus, OrderType
from atlas.broker.models.primitives import (
    BROKER_MODEL_CONFIG,
    Identifier,
    Price,
    SymbolCode,
    Timestamp,
    Volume,
)

__all__ = ["Order"]


class Order(BaseModel):
    """An instruction placed with a venue, and what became of it.

    The model is frozen, so a status change produces a new instance rather
    than mutating an existing one. That is deliberate: an order's history is
    the sequence of states it passed through, and a mutable object throws that
    away the moment it is updated.

    What this model does *not* check is whether the order is a good idea.
    Whether a stop loss sits on the profitable side of the entry, whether the
    volume fits the account, whether the instrument is permitted — those are
    risk decisions, made against state this model cannot see.
    """

    model_config = BROKER_MODEL_CONFIG

    order_id: Identifier = Field(description="Venue-assigned order ticket.")
    symbol: SymbolCode = Field(description="Instrument the order transacts in.")
    side: OrderSide = Field(description="Direction of the order.")
    type: OrderType = Field(description="How the order is presented to the venue.")
    volume: Volume = Field(description="Requested quantity, in lots.")
    price: Price | None = Field(
        default=None,
        description=(
            "The order's working price: the limit for a LIMIT or STOP_LIMIT "
            "order, the trigger for a STOP order. Optional on a MARKET order, "
            "where it carries the indicative price at submission if the venue "
            "reports one."
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
        default=None, description="Attached protective stop, if the venue holds one."
    )
    take_profit: Price | None = Field(
        default=None, description="Attached profit target, if the venue holds one."
    )
    status: OrderStatus = Field(description="Last state reported by the venue.")
    created_at: Timestamp = Field(description="When the order was created.")
    updated_at: Timestamp = Field(description="When the venue last changed the order.")

    @model_validator(mode="after")
    def _check_order_is_well_formed(self) -> Order:
        """Reject an order whose prices do not match its type.

        These are structural rules, not trading rules. A LIMIT order with no
        limit price is not a risky order; it is an incompletely mapped one, and
        the venue would reject it. Catching it here names the field, whereas
        the venue returns an opaque code.

        Returns:
            The validated instance.

        Raises:
            ValueError: If a required price is missing, a price is present on a
                type that has no use for it, or the timestamps run backwards.
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
        if self.updated_at < self.created_at:
            msg = (
                f"updated_at ({self.updated_at.isoformat()}) must not precede "
                f"created_at ({self.created_at.isoformat()})"
            )
            raise ValueError(msg)
        return self
