"""A strategy that exists to be checked against, not to be traded.

An abstraction with no implementations is an abstraction nobody has tried.
:class:`~atlas.broker.mock.MockBrokerAdapter` is here for the same reason on the
other side of the system: the second implementation is what demonstrates a
contract was designed against a specification rather than around one caller.

:class:`ConstantStrategy` is that demonstration for
:class:`~atlas.strategy.Strategy`, and it is deliberately the least interesting
one that can be written. It answers with the intent it was constructed with,
every time, whatever it is shown. It reads no market data, performs no I/O,
holds no clock, draws no random number and calls no venue. Its output is a
function of its constructor arguments and of nothing else.

That inertness is the design, not a limitation to be lifted later. A reference
implementation that could see a price is one edit away from being a trading
strategy, and the edit is the kind nobody reviews closely because the file
already existed. ``MockVenue`` records the same hazard from the venue side —
simulated fills produce "a strategy that appears to make money" — and
[ADR-0006](../../../../../docs/adr/0006-mock-adapter-simulates-bookkeeping-not-price.md)
calls that the worst kind of wrong answer. Nothing here can produce one,
because nothing here can observe anything.

Not a trading strategy:
    This class makes no claim about profitability, has no edge, and must not be
    deployed, extended into something that trades, or used as the starting
    point for one. A real strategy belongs in the task that specifies it, with
    the inputs, the evidence and the review that implies.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from atlas.risk import TradeIntent

__all__ = ["ConstantStrategy"]


class ConstantStrategy:
    """A strategy whose answer was decided before it was ever asked.

    Satisfies :class:`~atlas.strategy.Strategy` for every input type, because
    it accepts ``object`` and therefore accepts whatever a caller's ``InputT``
    turns out to be. That is what makes it usable as the stand-in wherever a
    strategy is required and no opinion is wanted.

    Constructed directly it abstains::

        ConstantStrategy().propose(anything) is None

    Handed an intent it recommends that one, always::

        ConstantStrategy(intent).propose(anything) is intent

    Notes:
        Both answers are first-class. ``None`` is what a strategy with no
        opinion returns, and a reference implementation that could not express
        it would leave the more common half of the contract unexercised.
    """

    def __init__(self, intent: TradeIntent | None = None) -> None:
        """Fix the single answer this strategy will give.

        The intent is *given* rather than built here, and that is the whole
        reason this module imports nothing from :mod:`atlas.broker`. A
        :class:`~atlas.risk.TradeIntent` is stated in ``SymbolName``,
        ``OrderSide``, ``Price`` and ``Volume``, so whoever constructs one names
        those four — which makes constructing one the job of the caller, not of
        a package that must not depend on the port. Whatever needs a concrete
        intent to hand over builds it itself.

        No validation happens here and none is repeated: an intent that reaches
        this constructor is already well-formed, because
        :class:`~atlas.risk.TradeIntent` refused to exist otherwise. A second
        copy of a validation rule is a second rule, and it diverges.

        Args:
            intent: What :meth:`propose` returns. ``None`` — the default —
                makes a strategy that always abstains, which is the shorter and
                more useful of the two shapes in a test.
        """
        self._intent = intent

    def propose(self, _observation: object, /) -> TradeIntent | None:
        """Return the fixed answer, ignoring the observation completely.

        Args:
            _observation: Accepted and discarded. Named for what happens to it,
                because a reference implementation that appeared to read its
                input would invite someone to make it actually do so.

        Returns:
            The intent this strategy was constructed with, or ``None``.
        """
        return self._intent
