"""The contract a strategy satisfies, and the only thing it may produce.

:mod:`atlas.risk` says what a proposal *is* — a :class:`~atlas.risk.TradeIntent`
— and what judging one returns. This module says who produces one, and it says
it as narrowly as the architecture allows: a strategy is anything with a
:meth:`Strategy.propose` method that answers with an intent or with nothing.

Three decisions are load bearing:

A strategy is a protocol, not a base class
    Structural typing, for the reason :mod:`atlas.broker.protocols` gives for
    the capability protocols: "nothing has to inherit from these". A strategy is
    a *behaviour*, and requiring inheritance would mean a research notebook, a
    replay harness and a production component could not all be the same thing
    unless they all imported the same base. It would also give this package a
    concrete class to put shared behaviour in, and the first thing that lands
    there is a lifecycle — which is not this task's, and which the responsibility
    table does not let a contract module own.

The input is a type parameter, and this package does not name it
    A strategy is shown *something* and forms an opinion about it. What that
    something is — a bar, a tick, a feature vector, a regime label — is owned by
    packages that are still stubs, and fixing it here would fix their shape
    before they exist. ``InputT`` is therefore whatever the component wiring a
    strategy up decides it is, and this module stays honest about knowing
    nothing else. The parameter appears only as an argument, so the protocol is
    contravariant in it: a strategy that will look at ``object`` satisfies
    ``Strategy[Candle]``, and not the other way round.

Nothing is the answer to "no opinion"
    :meth:`Strategy.propose` returns ``TradeIntent | None``, and ``None`` means
    the strategy has nothing to say. The alternative — an empty intent, or a
    sentinel that means "ignore me" — puts a value into the pipeline that
    *looks* tradeable, and the first consumer that forgets to check sends it to
    risk. There is no such object here to forget about.

Boundary:
    A strategy proposes; it does not decide and it does not place. Nothing in
    this package may reach :mod:`atlas.execution`, and nothing here may reach a
    broker directly — :mod:`atlas.risk` is the one ``atlas`` package a module
    here imports, and :class:`~atlas.risk.TradeIntent` is the one contract it
    names. See this package's README, and
    ``tests/unit/strategy/test_strategy_boundary.py``, which asserts both by
    walking the AST of every module here rather than by trusting this
    paragraph.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Protocol, runtime_checkable

if TYPE_CHECKING:
    from atlas.risk import TradeIntent

__all__ = ["Strategy"]


@runtime_checkable
class Strategy[InputT](Protocol):
    """Something that looks at an observation and may propose a trade.

    The producing half of the boundary ATLAS-TASK-0011 defined. A strategy is
    the only thing in Atlas that originates a :class:`~atlas.risk.TradeIntent`,
    and an intent is a recommendation rather than an instruction — what happens
    to it next is :mod:`atlas.risk`'s decision and nothing here can presume it.

    Notes:
        Implementations should be safe to call more than once with the same
        observation. Nothing in Atlas currently calls :meth:`propose` twice for
        one observation, but a strategy whose answer depends on how many times
        it has been asked cannot be replayed, and a result that cannot be
        replayed cannot be investigated after the fact.
    """

    def propose(self, observation: InputT, /) -> TradeIntent | None:
        """Form an opinion about one observation.

        Args:
            observation: Whatever this strategy was written to look at.
                Positional-only, so an implementation may name it whatever
                reads best without breaking the protocol — a caller holding a
                ``Strategy`` has no business knowing what one implementation
                calls its argument.

        Returns:
            A :class:`~atlas.risk.TradeIntent` describing what the strategy
            would like to do, or ``None`` if it has no opinion about this
            observation. ``None`` is an ordinary answer and not an error: a
            strategy that only trades one session out of five returns it four
            times as often as it returns anything else.

        Notes:
            An intent is a proposal. Returning one asserts nothing about
            whether the trade is affordable, permitted or wise — those are
            :mod:`atlas.risk`'s questions, asked against state a strategy
            cannot see.
        """
