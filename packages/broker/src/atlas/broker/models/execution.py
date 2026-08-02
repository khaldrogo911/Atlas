"""A fill: the immutable record of an order transacting."""

from __future__ import annotations

from pydantic import BaseModel, Field

from atlas.broker.models.primitives import (
    BROKER_MODEL_CONFIG,
    Identifier,
    Money,
    Price,
    SymbolCode,
    Timestamp,
    Volume,
)

__all__ = ["Execution"]


class Execution(BaseModel):
    """One quantity of one order transacting at one price.

    An order may produce several executions; a partial fill is not a modified
    order but an additional record. This is the layer's only genuinely
    append-only model, and the one that reconciliation and audit are built on,
    so it is immutable in the strongest sense: an execution that has been
    reported has happened, and no later event revises it.
    """

    model_config = BROKER_MODEL_CONFIG

    execution_id: Identifier = Field(description="Venue-assigned deal ticket.")
    order_id: Identifier = Field(description="Ticket of the order this fill belongs to.")
    symbol: SymbolCode = Field(description="Instrument transacted.")
    price: Price = Field(description="Price the fill transacted at.")
    volume: Volume = Field(description="Quantity filled, in lots.")
    commission: Money = Field(description="Commission charged on this fill. Usually negative.")
    swap: Money = Field(
        description=(
            "Financing settled by this fill. Non-zero when the fill closes a "
            "position that was held overnight."
        )
    )
    timestamp: Timestamp = Field(description="When the fill occurred.")
