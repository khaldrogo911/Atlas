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

from atlas.risk import TradeIntent

if TYPE_CHECKING:
    from atlas.broker import SymbolName
    from atlas.broker.models import OrderSide, Price, Volume

__all__ = ["ConstantStrategy"]


class ConstantStrategy:
    """A strategy whose answer was decided before it was ever asked.

    Satisfies :class:`~atlas.strategy.Strategy` for every input type, because
    it accepts ``object`` and therefore accepts whatever a caller's ``InputT``
    turns out to be. That is what makes it usable as the stand-in wherever a
    strategy is required and no opinion is wanted.

    Constructed directly it abstains::

        ConstantStrategy().propose(anything) is None

    Constructed through :meth:`proposing` it recommends::

        strategy = ConstantStrategy.proposing(
            symbol="EURUSD", side=OrderSide.BUY, volume=Decimal("0.10")
        )
        strategy.propose(anything)  # the same TradeIntent, always

    Notes:
        Both answers are first-class. ``None`` is what a strategy with no
        opinion returns, and a reference implementation that could not express
        it would leave the more common half of the contract unexercised.
    """

    def __init__(self, intent: TradeIntent | None = None) -> None:
        """Fix the single answer this strategy will give.

        Args:
            intent: What :meth:`propose` returns. ``None`` — the default —
                makes a strategy that always abstains, which is the shorter and
                more useful of the two shapes in a test.
        """
        self._intent = intent

    @classmethod
    def proposing(
        cls,
        *,
        symbol: SymbolName,
        side: OrderSide,
        volume: Volume,
        stop_loss: Price | None = None,
        take_profit: Price | None = None,
    ) -> ConstantStrategy:
        """Build a strategy that always proposes one intent, described here.

        The named constructor exists so that the intent is built *by a strategy
        module*, which is the only way this package exercises the permission it
        was granted: a :class:`~atlas.risk.TradeIntent` is stated in
        ``SymbolName``, ``OrderSide``, ``Price`` and ``Volume``, so anything
        that builds one names those four. A reference implementation handed a
        ready-made intent would import none of them, and the import rule in
        ``tests/unit/strategy/test_strategy_boundary.py`` would be asserting
        something about source that does not exist.

        Args:
            symbol: Instrument the proposal names.
            side: Direction the proposal names.
            volume: Quantity to ask for, in lots. The *request*; risk may
                approve less.
            stop_loss: Protective stop to propose, if any.
            take_profit: Profit target to propose, if any.

        Returns:
            A strategy that answers with exactly that intent, always.

        Raises:
            ValidationError: If the arguments do not describe a well-formed
                intent. The check belongs to :class:`~atlas.risk.TradeIntent`
                and is not repeated here — a second copy of a validation rule is
                a second rule, and it diverges.
        """
        return cls(
            TradeIntent(
                symbol=symbol,
                side=side,
                requested_volume=volume,
                stop_loss=stop_loss,
                take_profit=take_profit,
            )
        )

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
