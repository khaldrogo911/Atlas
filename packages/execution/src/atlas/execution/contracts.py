"""The contract that turns an approved verdict into an order request.

:mod:`atlas.risk` says what may be traded and in what size. :mod:`atlas.broker`
says what a venue takes. This module is the join between the two, and it is the
consuming half of the boundary ATLAS-TASK-0011 defined: a
:class:`~atlas.risk.RiskVerdict` goes in, an
:class:`~atlas.broker.OrderRequest` comes out, and a refusal comes out as
nothing at all.

Four decisions are load bearing:

The order vocabulary is the broker's, and naming it is not calling it
    ``OrderRequest``, ``OrderType`` and ``Price`` are imported rather than
    restated, for the reason :mod:`atlas.broker.types` gives for its own
    aliases: two definitions of one concept "would create two rules for one
    concept and guarantee they diverge", and a translation layer is exactly
    where two such rules would disagree unobserved. The edge that import
    creates is a type dependency and nothing more. Nothing here obtains,
    constructs or invokes a ``BrokerAdapter``, and an ``OrderRequest`` is inert
    — "an instruction to place an order, before any venue has seen it".
    Producing one changes nothing anywhere; placing one belongs to a layer that
    does not exist yet. See ADR-0011.

Presentation is supplied, not chosen
    A verdict says whether and how much. It deliberately says nothing about how
    the resulting order reaches a venue, because ``TradeIntent`` "that named
    ``LIMIT`` would be instructing rather than recommending". The missing half
    arrives as an :class:`ExecutionPolicy` the caller hands over. Nothing here
    holds a default: choosing MARKET on the caller's behalf would settle
    filling mode and deviation — the two questions
    :mod:`atlas.broker.mt5.adapter` says have no "obviously right answer" — in
    the package least likely to be read as policy.

The approved volume is the only volume there is
    :attr:`~atlas.risk.RiskVerdict.approved_volume`, never
    :attr:`~atlas.risk.TradeIntent.requested_volume`. A reduced approval is an
    approval carrying a smaller number, and reading the requested figure
    instead is precisely the accident a third ``REDUCED`` status was rejected to
    prevent.

Nothing is the answer to a refusal
    A rejected verdict is risk working, not a failure, so it is neither an
    exception nor a value that looks tradeable. The shape is the one
    :meth:`~atlas.strategy.Strategy.propose` already uses one layer up, where a
    sentinel was refused because it "puts a value into the pipeline that
    *looks* tradeable, and the first consumer that forgets to check sends it to
    risk". One layer further on the consumer that forgets would send it to a
    venue.

Boundary:
    Builds a request; never places one. The two ``atlas`` packages a module
    here imports are :mod:`atlas.risk` and :mod:`atlas.broker`, the second for
    its order vocabulary alone. See ``tests/unit/execution/test_execution_boundary.py``,
    which asserts both by walking the AST of every module here rather than by
    trusting this paragraph.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from pydantic import BaseModel, ConfigDict, Field

from atlas.broker import OrderRequest
from atlas.broker.models import OrderType, Price

if TYPE_CHECKING:
    from atlas.risk import RiskVerdict

__all__ = ["ExecutionPolicy", "build_order_request"]


class ExecutionPolicy(BaseModel):
    """How an approved verdict should be presented to a venue.

    The two answers a :class:`~atlas.risk.RiskVerdict` does not carry, and no
    others. It does not size, does not decide whether to trade, and does not see
    the account — those are :mod:`atlas.risk`'s, made against state this model
    cannot see.

    It is supplied per call. Nothing stores one, nothing reads one from
    configuration, and there is no default: a policy chosen here would be a
    trading decision written in the package least likely to be reviewed as one.

    The model is frozen and forbids extra fields, for the reasons
    :data:`~atlas.risk.RISK_MODEL_CONFIG` gives — a policy a later caller could
    edit is not a decision, and a misspelled field should be an error rather
    than a silently missing value. The config is stated here rather than shared
    with another package, because a shared mutable-by-edit default is how one
    package silently changes another's guarantees.

    Notes:
        Nothing here checks a price against its order type. That rule is
        ``OrderRequest``'s and is stated once, where the port states it: a
        policy naming ``LIMIT`` with no price produces a
        :exc:`pydantic.ValidationError` when the request is built, naming the
        field. A second copy of the rule here would be the divergence this
        module's import of the port's vocabulary exists to avoid.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    order_type: OrderType = Field(description="How the order should be presented to the venue.")
    price: Price | None = Field(
        default=None,
        description=(
            "Working price: the limit for a LIMIT order, the trigger for a "
            "STOP order. Omitted on a MARKET order, which has none."
        ),
    )


def build_order_request(verdict: RiskVerdict, policy: ExecutionPolicy) -> OrderRequest | None:
    """Turn an approved verdict into the request a venue would be asked to fill.

    Args:
        verdict: Risk's decision about one intent. Only an approved one
            licences an order.
        policy: How the resulting order should be presented. Supplied by the
            caller, because nothing in this package may choose it.

    Returns:
        An :class:`~atlas.broker.OrderRequest` carrying the intent's
        instrument, direction and protective levels, the volume risk approved,
        and the policy's presentation — or ``None`` if the verdict was
        rejected. ``None`` is an ordinary answer and not an error: risk
        refusing a trade is risk working, and a rejection is not a broker
        failure.

    Raises:
        ValidationError: If the policy contradicts its own order type — a
            ``LIMIT`` with no price, for instance. The rule belongs to
            ``OrderRequest`` and fires there; this function adds none of its
            own.

    Notes:
        The second half of the guard below is what a type checker needs, not a
        second rule. ``RiskVerdict``'s own validator makes ``approved_volume is
        not None`` exactly equivalent to
        :attr:`~atlas.risk.RiskVerdict.is_approved`, and
        ``tests/unit/risk/test_risk_boundary.py`` asserts that equivalence.
    """
    approved_volume = verdict.approved_volume
    if not verdict.is_approved or approved_volume is None:
        return None

    intent = verdict.intent
    return OrderRequest(
        symbol=intent.symbol,
        side=intent.side,
        type=policy.order_type,
        volume=approved_volume,
        price=policy.price,
        stop_loss=intent.stop_loss,
        take_profit=intent.take_profit,
    )
