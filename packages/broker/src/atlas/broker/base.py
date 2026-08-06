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

Concurrency
-----------
The port requires an adapter to tolerate calls from several threads: a strategy
thread reading quotes while a risk thread queries the account is the normal
case. This class is where that guarantee is implemented, once, for every
adapter. ADR-0007 records the decision and the alternatives; what follows is the
contract a caller and a subclass author can rely on.

**What is owned here.** The session state — established or not — and the two
cached readings. Nothing else. Orders, positions, quotes and subscriptions
belong to the venue, and a real venue is a remote server that Atlas cannot lock
from this process at all.

**Two locks, both created in** :meth:`BaseBrokerAdapter.__init__`.

``_session_lock``
    A :class:`threading.RLock`. Serialises
    :meth:`~atlas.broker.adapter.BrokerAdapter.connect`,
    :meth:`~atlas.broker.adapter.BrokerAdapter.disconnect` and
    :meth:`~atlas.broker.adapter.BrokerAdapter.reconnect`, and is held for the
    whole round trip to the venue, because a half-built session is exactly what
    a second thread must not be able to observe or interleave with. Re-entrant
    on purpose: a subclass composes its reconnect out of the *public* disconnect
    and connect — both adapters here do, and it is the obvious way to write one
    — and a plain lock would turn that into a self-deadlock discovered by
    whoever writes the third adapter.

    That composition is also why :meth:`~atlas.broker.adapter.BrokerAdapter.reconnect`
    takes the lock itself rather than leaving it to the halves it delegates to.
    Each half takes the lock on its own account, so the two never overlap even
    if the outer call holds nothing — but between them the lock would be free,
    and a ``disconnect`` arriving there is silently undone by the connect that
    follows it, leaving a session live that the caller had just closed. The
    outer hold is what makes the pair indivisible.

``_readings_lock``
    A :class:`threading.Lock`, and a leaf: nothing is called while it is held,
    so it cannot participate in a cycle. It guards only the latency and the
    heartbeat, which are written as a pair and must be read as a pair.

**Lock order is session then readings, never the reverse.** It is the only order
that occurs, because the readings lock is never held across a call. With one
ordered pair and a leaf at the bottom, there is no cycle to deadlock on.

**Supervision is never blocked.** :meth:`BaseBrokerAdapter.health` and
:meth:`BaseBrokerAdapter.is_connected` do not take the session lock. A
supervision thread asking "is the venue up" during a connect that is stuck
waiting on a terminal gets an answer immediately — which is the one moment the
question is worth asking, and would be the one moment a single lock made it
unanswerable.

**Requests are not serialised.** Every other port method takes no lock at all.
Locking them would make the adapter single-threaded and put the strategy
thread's quote read behind the risk thread's account query — the arrangement the
port explicitly calls normal. The consequence is stated rather than hidden: a
request that races a ``disconnect`` may fail. It fails with
:class:`~atlas.broker.exceptions.BrokerNotConnectedError`, or with whatever
error the venue produces for a request on a closing session, and both are
already inside that method's documented ``Raises:`` contract. A caller that must
not lose a request has to sequence its own lifecycle calls; no lock inside an
adapter can make "check then act" atomic for a caller.

**No lock is held while user code runs.** Subscription handlers are invoked by
the venue, on the publishing thread, outside every adapter method, and the
subscribe and unsubscribe methods take no adapter lock. A handler is therefore
free to call back into the adapter — including :meth:`disconnect` — without
deadlocking.

**What is not thread-safe, and is not claimed to be.** The mock venue has no
lock of its own and mints identifiers with a non-atomic read-modify-write, so
two adapters driven from two threads against one shared
:class:`~atlas.broker.mock.venue.MockVenue` are outside anything these locks
protect. That is a property of the test double, not of the port; the guarantee
here is per adapter.

What it deliberately does not own
---------------------------------
**Connecting.** :meth:`~atlas.broker.adapter.BrokerAdapter.connect` and
:meth:`~atlas.broker.adapter.BrokerAdapter.reconnect` look alike across adapters
and are not the same. The MetaTrader 5 adapter re-reads the brokerage name on
every connect and treats a redundant connect as a refresh; the mock returns the
existing snapshot untouched, and keys reconnect separately from connect so that
a scheduled fault fires on the call a test named. So this class owns *when* the
lifecycle runs and a subclass owns *what* it does: the public methods here take
the lock and delegate to :meth:`_connect`, :meth:`_disconnect` and
:meth:`_reconnect`.

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
"""

from __future__ import annotations

import threading
from abc import abstractmethod
from typing import TYPE_CHECKING

from atlas.broker.adapter import BrokerAdapter
from atlas.broker.models import Connection

if TYPE_CHECKING:
    from atlas.broker.models import ConnectionState, LatencyMilliseconds, Timestamp
    from atlas.broker.types import BrokerName, ServerName

__all__ = ["BaseBrokerAdapter"]


class BaseBrokerAdapter(BrokerAdapter):
    """Session bookkeeping shared by every adapter, and the locking around it.

    Subclasses say *where* the session state lives, *who* is at the far end, and
    *what* their lifecycle does; this class turns those into the snapshot the
    port promises, answers the two lifecycle reads that need nothing else, and
    provides the synchronisation described in the module docstring.

    Still abstract: it implements five of the port's thirty-one methods and adds
    six of its own, so a subclass that stops halfway cannot be instantiated —
    the same protection the port itself provides.

    Notes:
        A subclass must call ``super().__init__()``. Both locks and both cached
        readings are created there, and an adapter that skips it fails on its
        first :meth:`connect` call rather than at construction.

        No subclass writes a lock. The lifecycle hooks run with the session lock
        already held, and the readings are reached through :meth:`_record_latency`,
        :meth:`_record_heartbeat` and :meth:`_clear_session_readings`, which take
        the readings lock themselves. Duplicated locking is not discouraged here;
        there is nowhere to put it.
    """

    def __init__(self) -> None:
        """Build the locks and start with no session readings.

        Notes:
            Both readings are ``None`` rather than zero, and the distinction is
            the point: a latency of ``0.0`` claims a measurement was taken and
            came back instant, which is a different statement from never having
            measured.

            The locks are per instance, not per class. Two adapters pointed at
            two venues have no reason to queue behind each other, and a class
            level lock would make every adapter in the process share one.
        """
        self._session_lock = threading.RLock()
        self._readings_lock = threading.Lock()
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

        Notes:
            Read without the session lock, by :meth:`is_connected` and
            :meth:`health`, so it must be a plain attribute read that cannot
            block. Every implementation is one, and that is a requirement rather
            than an observation: a hook that made a round trip would put the
            venue's availability inside the question "is the venue available".
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

        Notes:
            Read without the session lock, like :attr:`_session_state`. An
            adapter that caches the name writes it inside its :meth:`_connect`,
            which means a concurrent :meth:`health` sees either the previous
            name or the new one — a single reference assignment either way, and
            never a partially built value.
        """

    @property
    @abstractmethod
    def _session_server(self) -> ServerName:
        """Which trade server or environment the session addresses.

        Returns:
            The server's name. Configuration rather than observation for most
            venues, so it is available before the first connect.
        """

    @abstractmethod
    def _connect(self) -> Connection:
        """Establish a session. Called with the session lock held.

        Returns:
            The snapshot :meth:`connect` returns, normally by way of
            :meth:`_connection`.

        Raises:
            BrokerError: Whatever the venue produced. Propagated unchanged: the
                lock is released by the ``with`` statement in :meth:`connect`,
                so a failed connect leaves nothing held.

        Notes:
            Free to read and write the session state without further
            synchronisation, and free to call the public lifecycle methods,
            which re-enter the same lock.
        """

    @abstractmethod
    def _disconnect(self) -> None:
        """Close the session. Called with the session lock held.

        Returns:
            Nothing.

        Notes:
            Must not raise, because :meth:`disconnect` must not.

            Clear the readings *first*, before the session state changes. A
            concurrent :meth:`health` can then never see a state of
            ``DISCONNECTED`` alongside a latency measured on the session that
            has just gone — the stale reading that makes a supervision
            dashboard actively misleading. Single-threaded behaviour is
            identical either way, which is why the ordering is worth spending.
        """

    @abstractmethod
    def _reconnect(self) -> Connection:
        """Replace the session. Called with the session lock held.

        Returns:
            The snapshot :meth:`reconnect` returns.

        Raises:
            BrokerError: Whatever the venue produced while re-establishing.

        Notes:
            Composed from the public :meth:`disconnect` and :meth:`connect` in
            both adapters here, which is why the session lock is re-entrant.
        """

    # --- What every adapter inherits ------------------------------------------

    def connect(self) -> Connection:
        """Establish a session with the venue.

        Returns:
            The resulting connection state, from the adapter's :meth:`_connect`.

        Raises:
            BrokerError: Whatever the venue produced.

        Notes:
            Serialised against :meth:`disconnect` and :meth:`reconnect`. Two
            threads calling this at once produce one attempt and one waiter; the
            waiter then runs :meth:`_connect` against a session that is already
            established, and every adapter treats that as the port requires —
            as a no-op returning the current snapshot, not a second connection.
        """
        with self._session_lock:
            return self._connect()

    def disconnect(self) -> None:
        """Close the session.

        Returns:
            Nothing.

        Notes:
            Serialised against :meth:`connect` and :meth:`reconnect`, so it
            cannot tear a session down halfway through one being built. Never
            raises, as the port requires of a cleanup path.
        """
        with self._session_lock:
            self._disconnect()

    def reconnect(self) -> Connection:
        """Tear down the session and establish a new one.

        Returns:
            The connection state after the attempt.

        Raises:
            BrokerError: Whatever the venue produced while re-establishing.

        Notes:
            The whole teardown and rebuild is one critical section. A concurrent
            :meth:`connect` cannot slip into the gap between the two halves and
            establish a session this method is about to replace.
        """
        with self._session_lock:
            return self._reconnect()

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

            The two readings are taken together under the readings lock, so the
            pair is never torn: a snapshot cannot show a latency from one
            measurement beside a heartbeat from another. The
            :class:`~atlas.broker.models.Connection` is then built outside the
            lock, because validation is not this lock's business and a leaf lock
            stops being a leaf the moment something is called while it is held.
        """
        state = self._session_state
        with self._readings_lock:
            latency_ms = self._last_latency_ms
            last_heartbeat = self._last_heartbeat
        return Connection(
            state=state,
            connected=state.is_usable,
            latency_ms=latency_ms,
            last_heartbeat=last_heartbeat,
            broker=self._session_broker,
            server=self._session_server,
        )

    def _record_heartbeat(self, at: Timestamp) -> None:
        """Record that the venue answered, and when.

        Args:
            at: The observation time, from whichever clock the adapter has
                decided is authoritative.

        Returns:
            Nothing.
        """
        with self._readings_lock:
            self._last_heartbeat = at

    def _record_latency(self, latency_ms: LatencyMilliseconds, *, at: Timestamp) -> None:
        """Record a round-trip measurement and the heartbeat that comes with it.

        Args:
            latency_ms: The measured round trip.
            at: When it was measured.

        Returns:
            Nothing.

        Notes:
            One call rather than two, because measuring the latency *is* hearing
            from the venue and the two facts have the same instant. Writing them
            under one acquisition also means no reader can see the new latency
            beside the old heartbeat.
        """
        with self._readings_lock:
            self._last_latency_ms = latency_ms
            self._last_heartbeat = at

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
        with self._readings_lock:
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

            Takes no lock. The read is a single attribute access, and answering
            it is the one thing that must still work while another thread is
            blocked inside a connect that will not return.
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

            Never waits on the session lock, so it answers during an in-flight
            connect or disconnect. What it returns then is a reading taken while
            the lifecycle was moving, which is the honest answer to a question
            asked at that moment rather than a stale one.
        """
        return self._connection()
