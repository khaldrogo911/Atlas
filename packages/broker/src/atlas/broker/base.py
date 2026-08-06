"""What every adapter has to do about its session, written once.

An adapter is mostly translation: a venue's answer in, a domain model out. The
session is the exception. Every implementation of
:class:`~atlas.broker.adapter.BrokerAdapter` has to remember the same three
things — the lifecycle state, the last latency it measured, and the last time
the venue confirmed it was alive — and has to assemble the same
:class:`~atlas.broker.models.Connection` out of them for
:meth:`~atlas.broker.adapter.BrokerAdapter.health`. Both adapters in this
repository did that separately, in the same shape, for the same reason.

:class:`BaseBrokerAdapter` owns that bookkeeping. It sits *between* the port and
an implementation rather than inside the port, because the port must stay
implementable by something that has no session at all: a replay engine reading a
file has nothing to connect to, and it should not inherit the concept in order
to satisfy a contract about market data.

What it deliberately does not own
---------------------------------
**Connecting.** :meth:`~atlas.broker.adapter.BrokerAdapter.connect` and
:meth:`~atlas.broker.adapter.BrokerAdapter.reconnect` look alike across adapters
and are not the same. The MetaTrader 5 adapter re-reads the brokerage name on
every connect and treats a redundant connect as a refresh; the mock returns the
existing snapshot untouched, and keys reconnect separately from connect so that
a scheduled fault fires on the call a test named. Lifting a common shape over
those would change both.

**The clock.** The base holds *when* the venue was last heard from and never
decides what time it is. MetaTrader 5 stamps the host clock, because the fact it
records is when Atlas observed the terminal; the mock stamps its own venue
clock, because determinism is the reason that adapter exists. A base that read a
clock would have to pick one and would be wrong for the other.

**The not-connected guard.** Both adapters refuse a request that has no session,
and they refuse it in structurally different places: the mock checks on entry to
each port method, naming the method; MetaTrader 5 checks inside
:meth:`~atlas.broker.mt5.connection.MT5Session.terminal`, at the single point
every data path passes through. Both are correct for their venue, and neither is
a copy of the other, so there is nothing here to unify yet. The observable
behaviour is held identical by ``tests/unit/broker/test_base_adapter.py``, which
puts every discovered adapter through the same refusal.

**Locking.** The port requires adapters to tolerate calls from several threads
and neither adapter does. That is a behaviour to add, not duplication to move,
and adding it under a refactor would change what every existing test exercises.
It remains the strongest candidate for this class's next piece of work.
"""

from __future__ import annotations

from abc import abstractmethod
from typing import TYPE_CHECKING

from atlas.broker.adapter import BrokerAdapter
from atlas.broker.models import Connection

if TYPE_CHECKING:
    from atlas.broker.models import ConnectionState, LatencyMilliseconds, Timestamp
    from atlas.broker.types import BrokerName, ServerName

__all__ = ["BaseBrokerAdapter"]


class BaseBrokerAdapter(BrokerAdapter):
    """Session bookkeeping shared by every adapter.

    Subclasses say *where* the session state lives and *who* is at the far end;
    this class turns those into the snapshot the port promises and answers the
    two lifecycle reads that need nothing else.

    Still abstract: it implements two of the port's thirty-one methods and adds
    three of its own, so a subclass that stops halfway cannot be instantiated —
    the same protection the port itself provides.

    Notes:
        A subclass must call ``super().__init__()``. The two cached readings are
        created there, and an adapter that skips it fails on its first
        :meth:`health` call rather than at construction.
    """

    def __init__(self) -> None:
        """Start with no session readings.

        Notes:
            Both readings are ``None`` rather than zero, and the distinction is
            the point: a latency of ``0.0`` claims a measurement was taken and
            came back instant, which is a different statement from never having
            measured.
        """
        self._last_latency_ms: LatencyMilliseconds | None = None
        self._last_heartbeat: Timestamp | None = None

    # --- What a subclass supplies ---------------------------------------------

    @property
    @abstractmethod
    def _session_state(self) -> ConnectionState:
        """Where the adapter keeps its lifecycle state.

        Returns:
            The current state. Read on every call rather than cached here,
            because an adapter may keep the authoritative copy elsewhere — the
            MetaTrader 5 adapter's lives on its session object — and two copies
            of a connection state is precisely the bug
            :class:`~atlas.broker.models.Connection` validates against.
        """

    @property
    @abstractmethod
    def _session_broker(self) -> BrokerName:
        """Who is at the far end.

        Returns:
            The brokerage's name, as the adapter currently understands it. Must
            answer while disconnected, since :meth:`health` must, so an adapter
            that learns the name from the venue caches it or names its
            ignorance.
        """

    @property
    @abstractmethod
    def _session_server(self) -> ServerName:
        """Which trade server or environment the session addresses.

        Returns:
            The server's name. Configuration rather than observation for most
            venues, so it is available before the first connect.
        """

    # --- What every adapter inherits ------------------------------------------

    def _connection(self) -> Connection:
        """Assemble the connectivity snapshot from local state.

        Returns:
            What the adapter currently believes about its session. Performs no
            round trip, which is what allows :meth:`health` and
            :meth:`is_connected` to be safe to call at any time — including at
            the only time they are interesting, which is when the venue is
            unreachable.

        Notes:
            ``connected`` is derived from the state here rather than tracked
            separately. The model rejects the two disagreeing, and the way they
            come to disagree is a reconnect path that updates one of them.
        """
        state = self._session_state
        return Connection(
            state=state,
            connected=state.is_usable,
            latency_ms=self._last_latency_ms,
            last_heartbeat=self._last_heartbeat,
            broker=self._session_broker,
            server=self._session_server,
        )

    def _clear_session_readings(self) -> None:
        """Forget the latency and heartbeat a closing session left behind.

        Returns:
            Nothing.

        Notes:
            Called from ``disconnect``. The readings describe a session that no
            longer exists, and a stale measurement presented as current is what
            makes a supervision dashboard actively misleading — it reports a
            healthy latency for a venue nothing can reach.
        """
        self._last_latency_ms = None
        self._last_heartbeat = None

    def is_connected(self) -> bool:
        """Report whether a session is established, without a round trip.

        Returns:
            ``True`` if requests can be attempted.

        Notes:
            Local and cheap, as the port requires, and never raises. Reads the
            state each time: an adapter whose session drops underneath it
            reports the drop here without anything having to notify this class.
        """
        return self._session_state.is_usable

    def health(self) -> Connection:
        """Return the connectivity snapshot.

        Returns:
            The current state, with the last measured latency and heartbeat,
            both ``None`` before the first measurement.

        Notes:
            Never raises. A disconnected adapter is described rather than
            refused, which is the whole point of the method. Use ``ping`` or
            ``latency`` to refresh the underlying measurements first.
        """
        return self._connection()
