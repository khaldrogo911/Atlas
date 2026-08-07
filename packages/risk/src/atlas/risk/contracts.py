"""The two contracts that make the risk boundary real.

:mod:`atlas.broker` describes what a venue *takes* and what it *reports*. This
module describes the decision that must happen in between: a
:class:`TradeIntent` is what a strategy would like to do, a
:class:`RiskVerdict` is what risk permits, and nothing may become an order
without one.

``OrderRequest`` says where the line is, in its own words: whether a request is
*wise* — the size against the account, the stop on the correct side of entry,
the instrument permitted by policy — "is a risk decision, made against state
neither this model nor the port can see". These are the types that decision is
expressed in.

Three decisions are load bearing:

Risk judges an intent; it never builds an order
    Nothing here imports, re-exports or constructs
    :class:`~atlas.broker.OrderRequest`, and nothing here names an order type or
    a working price. How an order is *presented to the venue* is
    :mod:`atlas.execution`'s question, and a risk package that answered it would
    be sizing and routing in one place — which is the coupling
    ``docs/architecture/overview.md`` forbids by giving execution "order
    lifecycle, routing, fills" and denying it the power to "size a position".

The primitives are the broker's, under the names risk uses
    ``SymbolName``, ``OrderSide``, ``Price`` and ``Volume`` are imported rather
    than redefined, for the reason :mod:`atlas.broker.types` gives for its own
    aliases: defining them side by side "would create two rules for one concept
    and guarantee they diverge". A risk-local ``Volume`` that permitted zero, or
    a ``Price`` that permitted a negative, would be a boundary that disagreed
    with the port it protects.

A verdict is two-valued, and the number carries the nuance
    A reduced-size approval is still an approval. Making it a third status would
    force every consumer to handle two spellings of "yes", and the first one to
    forget the second is a position sized off the requested volume rather than
    the approved one.
"""

from __future__ import annotations

from enum import StrEnum, unique

from pydantic import BaseModel, ConfigDict, Field, model_validator

from atlas.broker import SymbolName
from atlas.broker.models import OrderSide, Price, Volume

__all__ = [
    "RISK_MODEL_CONFIG",
    "RejectionReason",
    "RiskVerdict",
    "TradeIntent",
    "VerdictStatus",
]

#: Configuration applied to every model in this package.
#:
#: The same settings :data:`~atlas.broker.models.BROKER_MODEL_CONFIG` applies,
#: stated here rather than imported: that constant documents itself as applying
#: to "every model in *that* package", and a shared mutable-by-edit default
#: across two packages is how one package silently changes the other's
#: guarantees. ``frozen`` means a verdict cannot be edited after the decision
#: was made — an approved volume that a later caller could raise is not a
#: boundary. ``extra="forbid"`` turns a misspelled field into an immediate
#: error rather than one that reads back as missing.
RISK_MODEL_CONFIG = ConfigDict(frozen=True, extra="forbid")


@unique
class VerdictStatus(StrEnum):
    """Whether risk permits an intent to proceed.

    Exactly two members. A reduced-size approval is ``APPROVED`` with an
    :attr:`RiskVerdict.approved_volume` below the requested one, not a status
    of its own — see this module's docstring.
    """

    APPROVED = "APPROVED"
    REJECTED = "REJECTED"


@unique
class RejectionReason(StrEnum):
    """Which control refused an intent.

    The four members are the controls :mod:`atlas.risk` is declared to own —
    "per-instrument and portfolio exposure limits, drawdown controls,
    correlation caps and the kill switches that halt trading". None of them is
    implemented yet; naming them here is what makes a rejection auditable
    rather than a free-text string that every caller parses differently.

    A new control adds a member in the task that implements it. Inventing one
    ahead of the control it names would put a reason in the audit trail that
    nothing can ever produce.
    """

    EXPOSURE_LIMIT = "EXPOSURE_LIMIT"
    DRAWDOWN_LIMIT = "DRAWDOWN_LIMIT"
    CORRELATION_CAP = "CORRELATION_CAP"
    KILL_SWITCH = "KILL_SWITCH"


class TradeIntent(BaseModel):
    """What a strategy would like to do, before risk has looked at it.

    A recommendation, not an instruction. It carries what risk needs in order
    to judge it — the instrument, the direction, the size being asked for, and
    the protective levels that determine how much of the account is at stake —
    and nothing about how the resulting order should reach a venue.

    Deliberately absent, and not to be added without the task that needs them:

    * **An order type and a working price.** ``OrderType`` is documented as
      "how the order should be presented to the venue", and presentation is
      :mod:`atlas.execution`'s. An intent that named ``LIMIT`` would be
      instructing rather than recommending.
    * **An identifier.** Who mints intent ids, and whether they survive a
      restart, is a question for the audit trail that does not exist yet. A
      field invented now would be a second answer to it.
    * **A creation timestamp.** It would require a clock to be injected into
      whatever builds an intent, and nothing here needs to know when it was
      built.
    """

    model_config = RISK_MODEL_CONFIG

    symbol: SymbolName = Field(description="Instrument the strategy proposes to transact in.")
    side: OrderSide = Field(description="Direction the strategy proposes.")
    requested_volume: Volume = Field(
        description=(
            "Quantity the strategy is asking for, in lots. Named for the ask "
            "rather than for the outcome, because risk may approve less."
        )
    )
    stop_loss: Price | None = Field(
        default=None,
        description=(
            "Protective stop the strategy proposes. Optional on the contract "
            "because a risk control, not this model, decides whether an intent "
            "without one may proceed."
        ),
    )
    take_profit: Price | None = Field(
        default=None, description="Profit target the strategy proposes."
    )


class RiskVerdict(BaseModel):
    """Risk's decision about one intent.

    The only thing that may licence an order. An approved verdict carries the
    volume that risk is willing to see traded, which is the number execution
    must use — never :attr:`TradeIntent.requested_volume`, which is what was
    asked for rather than what was allowed.

    The verdict carries the whole intent rather than a reference to one. Both
    models are frozen, so there is nothing to keep in sync, and it means
    "approved for less than was asked" is a comparison inside a single object
    rather than a join two callers might perform differently — or forget.

    Constructing one does not make it true. This model states what a
    well-formed decision looks like; the controls that reach a decision belong
    to later tasks.
    """

    model_config = RISK_MODEL_CONFIG

    intent: TradeIntent = Field(description="The intent this verdict judges.")
    status: VerdictStatus = Field(description="Whether the intent may proceed.")
    approved_volume: Volume | None = Field(
        default=None,
        description=(
            "Quantity risk permits, in lots. Required on an approval, absent on a rejection."
        ),
    )
    reason: RejectionReason | None = Field(
        default=None,
        description=(
            "Which control refused the intent. Required on a rejection and "
            "absent on an approval."
        ),
    )
    detail: str | None = Field(
        default=None,
        description=(
            "Human-readable context for the decision, such as the limit that "
            "was reached. Optional in either state, and never a substitute for "
            "``reason``: a machine reads the reason, a person reads this."
        ),
    )

    @property
    def is_approved(self) -> bool:
        """Whether the intent may proceed to execution."""
        return self.status is VerdictStatus.APPROVED

    @property
    def is_reduced(self) -> bool:
        """Whether risk approved less than was asked for.

        ``False`` on a rejection: nothing was approved, so nothing was reduced.
        """
        if self.approved_volume is None:
            return False
        return self.approved_volume < self.intent.requested_volume

    @model_validator(mode="after")
    def _check_verdict_is_well_formed(self) -> RiskVerdict:
        """Reject a decision whose fields contradict its status.

        Returns:
            The validated instance.

        Raises:
            ValueError: If an approval carries no volume, carries more volume
                than was requested, or carries a rejection reason; or if a
                rejection carries a volume or carries no reason.
        """
        if self.status is VerdictStatus.APPROVED:
            if self.approved_volume is None:
                msg = "approved_volume is required on an APPROVED verdict"
                raise ValueError(msg)
            if self.approved_volume > self.intent.requested_volume:
                msg = (
                    f"approved_volume {self.approved_volume} exceeds the requested "
                    f"{self.intent.requested_volume}; risk may reduce an intent but "
                    "never enlarge one"
                )
                raise ValueError(msg)
            if self.reason is not None:
                msg = "reason must be None on an APPROVED verdict"
                raise ValueError(msg)
        else:
            if self.approved_volume is not None:
                msg = "approved_volume must be None on a REJECTED verdict"
                raise ValueError(msg)
            if self.reason is None:
                msg = "reason is required on a REJECTED verdict"
                raise ValueError(msg)
        return self
