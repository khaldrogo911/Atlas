"""An in-memory venue and a complete adapter for it, for testing against the port.

The second implementation of :class:`~atlas.broker.adapter.BrokerAdapter`, and
the one tests are meant to hold::

    from atlas.broker.mock import MockBrokerAdapter, MockVenue

Use this instead of mocking the port. A mock agrees with whatever the test
asserts, including the wrong thing; this is a real implementation bound by the
same contract tests as every other adapter, so a suite built on it is checked
against the contract rather than against itself.

Two objects, deliberately:

:class:`~atlas.broker.mock.venue.MockVenue`
    Everything a broker holds — a clock, instruments, quotes, bars, an account,
    orders, positions, fills, subscriptions — plus the fault queue that makes a
    caller's failure branches reachable. A test arranges the world here and
    asserts on it here.

:class:`~atlas.broker.mock.adapter.MockBrokerAdapter`
    The port over that state: session checks, symbol resolution, argument
    validation, and the decision about which
    :class:`~atlas.broker.exceptions.BrokerError` a venue condition amounts to.

They are separate so that a test asserting through ``adapter.venue`` and a test
asserting through the port's read methods are two independent readings. Using
``get_positions`` to check what ``place_order`` did is the adapter checking
itself, which is the failure mocking causes and the one this package exists to
remove.

Boundary:
    Reports what it was told. It fills a market order at a published quote and
    invents nothing else — no price triggers, no revaluation, no ledger. What
    it declines to simulate, and why, is in ``README.md`` in this directory and
    in ADR-0006.

Determinism:
    Nothing here reads the host clock or any source of randomness. Identifiers
    count from one and time moves only when a test moves it, so two runs of the
    same test produce byte-identical objects.
"""

from __future__ import annotations

from atlas.broker.mock.adapter import MockBrokerAdapter
from atlas.broker.mock.venue import DEFAULT_ACCOUNT, DEFAULT_START, SERVER, VENUE, MockVenue

__all__ = [
    "DEFAULT_ACCOUNT",
    "DEFAULT_START",
    "SERVER",
    "VENUE",
    "MockBrokerAdapter",
    "MockVenue",
]
