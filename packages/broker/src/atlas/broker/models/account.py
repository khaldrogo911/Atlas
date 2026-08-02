"""The state of a funded trading account at a point in time."""

from __future__ import annotations

from pydantic import BaseModel, Field, model_validator

from atlas.broker.models.primitives import (
    BROKER_MODEL_CONFIG,
    CurrencyCode,
    Identifier,
    Leverage,
    Money,
    Name,
    NonNegativeMoney,
    Percentage,
    Timestamp,
)

__all__ = ["Account"]


class Account(BaseModel):
    """A snapshot of a trading account as reported by the broker.

    An ``Account`` is an observation, not a ledger. It carries the values the
    venue reported at :attr:`timestamp` and nothing derived from them: Atlas
    does not recompute equity from balance and open profit, because the broker
    is the authority on its own arithmetic and disagreeing with it silently
    would be worse than disagreeing with it loudly.
    """

    model_config = BROKER_MODEL_CONFIG

    account_id: Identifier = Field(description="Broker-assigned account number or login.")
    broker: Name = Field(description="Name of the brokerage holding the account.")
    server: Name = Field(description="Trade server the account is hosted on.")
    currency: CurrencyCode = Field(description="Deposit currency; every amount below is in it.")
    balance: Money = Field(description="Realised funds, excluding profit on open positions.")
    equity: Money = Field(description="Balance plus the mark-to-market value of open positions.")
    margin: NonNegativeMoney = Field(description="Funds currently pledged against open positions.")
    free_margin: Money = Field(
        description="Equity available for new positions. Negative under a margin call."
    )
    margin_level: Percentage | None = Field(
        default=None,
        description=(
            "Equity as a percentage of margin in use. ``None`` when no margin is "
            "pledged, because the ratio is undefined rather than zero."
        ),
    )
    leverage: Leverage = Field(description="Denominator of the account's leverage ratio.")
    trade_allowed: bool = Field(description="Whether the venue currently permits trading.")
    timestamp: Timestamp = Field(description="When this snapshot was taken.")

    @model_validator(mode="after")
    def _check_margin_level_is_defined(self) -> Account:
        """Reject a margin level reported against zero margin.

        Several venues send ``0`` for the margin level when no position is
        open. Carried through verbatim, that reads as the most severe margin
        call possible, and any rule of the form ``margin_level < threshold``
        fires on a flat account. The undefined case is ``None``; mapping the
        venue's placeholder onto it is the adapter's job.

        Returns:
            The validated instance.

        Raises:
            ValueError: If a margin level accompanies zero margin.
        """
        if self.margin == 0 and self.margin_level is not None:
            msg = (
                f"margin_level must be None when margin is zero, got {self.margin_level}; "
                "the ratio is undefined, not zero"
            )
            raise ValueError(msg)
        return self
