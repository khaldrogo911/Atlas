"""An open position and its mark-to-market state."""

from __future__ import annotations

from pydantic import BaseModel, Field

from atlas.broker.models.enums import PositionSide
from atlas.broker.models.primitives import (
    BROKER_MODEL_CONFIG,
    Identifier,
    Money,
    Price,
    SymbolCode,
    Timestamp,
    Volume,
)

__all__ = ["Position"]


class Position(BaseModel):
    """Exposure currently held in an instrument, valued by the broker.

    :attr:`profit`, :attr:`swap` and :attr:`commission` are reported figures,
    not derived ones. Atlas deliberately does not recompute profit from the
    entry and current prices: doing so requires the contract size, the
    conversion rate from the quote currency to the deposit currency at the
    broker's own rate, and the broker's rounding — three things this model
    does not have and should not guess at. Where Atlas disagrees with the
    broker's arithmetic, the broker is right, because the broker is the one
    settling the account.
    """

    model_config = BROKER_MODEL_CONFIG

    position_id: Identifier = Field(description="Venue-assigned position ticket.")
    symbol: SymbolCode = Field(description="Instrument the exposure is held in.")
    side: PositionSide = Field(description="Direction of the exposure.")
    volume: Volume = Field(description="Size of the exposure, in lots.")
    entry_price: Price = Field(description="Volume-weighted price the position was opened at.")
    current_price: Price = Field(description="Price the position is currently valued at.")
    profit: Money = Field(
        description=(
            "Unrealised profit in the deposit currency, as reported. Excludes "
            "swap and commission, which are listed separately."
        )
    )
    swap: Money = Field(description="Financing accrued so far. Usually negative.")
    commission: Money = Field(description="Commission charged on the position. Usually negative.")
    opened_at: Timestamp = Field(description="When the position was opened.")
