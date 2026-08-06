"""What the adapters guarantee when more than one thread is inside them.

:class:`~atlas.broker.base.BaseBrokerAdapter` now synchronises the session
lifecycle. The claims it makes are set out in its module docstring and in
ADR-0007, and every one of them is asserted here, because a concurrency
guarantee that is only written down is a comment.

These tests are built to be decided rather than won. Three devices do the work:

:func:`_held_elsewhere`
    Holds an adapter's session lock on *another* thread. A call that must wait
    for the lock then provably waits and a call that must not provably does
    not — with no sleeping and no racing. The other thread is the point: the
    session lock is re-entrant, so a test holding it on its own thread would
    prove nothing about anybody being excluded.

:class:`_ParkingVenue` and :class:`_ParkingTerminal`
    Park a real adapter inside its real connect path until a test releases it.
    That is how "supervision still answers during an in-flight connect" is
    checked against the code an operator would be running, rather than against
    a lock held by hand.

:class:`_TracedLock`
    Records every acquisition and release, so lock *ordering* is read off an
    execution instead of being argued about.

Two tests are stress tests — :class:`TestTheSnapshotIsNeverTorn` and
:class:`TestTheLifecycleSurvivesContention`. Their assertions are invariants, so
they cannot fail on correct code however the threads interleave; what luck
changes is only how quickly they would catch a violation.

Every test asserting that something *cannot* happen is paired with one asserting
that the opposite case does. A suite in which connect is never blocked and
health is never blocked would be satisfied just as well by an adapter holding no
locks at all, which is precisely the state this task started from.
"""

from __future__ import annotations

import ast
import contextlib
import inspect
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime
from pathlib import Path
from typing import TYPE_CHECKING, Any, Final, cast

import pytest

from atlas.broker import base as base_module
from atlas.broker.base import BaseBrokerAdapter
from atlas.broker.exceptions import BrokerError
from atlas.broker.mock.adapter import MockBrokerAdapter
from atlas.broker.mock.venue import MockVenue
from atlas.broker.models import Connection, ConnectionState
from atlas.broker.mt5.adapter import MT5BrokerAdapter
from atlas.broker.mt5.connection import MT5Session
from tests.unit.broker.mock.conftest import EURUSD, tick
from tests.unit.broker.mt5.conftest import FakeTerminal, as_terminal
from tests.unit.broker.test_base_adapter import CASES, AdapterCase, _mt5

if TYPE_CHECKING:
    from collections.abc import Callable, Iterator

    from atlas.broker.models import Tick
    from atlas.broker.types import BrokerName, ServerName

pytestmark = pytest.mark.unit

#: How long a call that must complete is given before the test calls it hung.
#: Generous, because it is a watchdog rather than a measurement: it only elapses
#: when something has genuinely deadlocked.
WATCHDOG: Final = 5.0

#: How long a call that must *not* complete is watched for. Short, because the
#: assertion is "it is still waiting", and a call that was going to return
#: without taking the lock would have returned in microseconds.
BLOCKED: Final = 0.05

#: How long a lifecycle hook lingers in the probe below. Long enough that two
#: unsynchronised threads would reliably be inside it at once, short enough that
#: the whole module still runs in under a second.
OVERLAP: Final = 0.01

#: How many threads the contention tests use.
THREADS: Final = 8

#: How many lifecycle round trips each of them makes.
CYCLES: Final = 25

#: How long the churning thread rests in each half of a lifecycle cycle. Without
#: it a cycle completes between two bytecodes and a spinning reader is never
#: scheduled inside it, which would make the reader's assertions vacuous rather
#: than passing.
PAUSE: Final = 0.001

#: The two operations that bring a mock session up. Both are worth parking on:
#: ``reconnect`` establishes its session through a second code path.
ESTABLISHING: Final = frozenset({"connect", "reconnect"})

#: A fixed instant for the probe's readings. Nothing here reads a wall clock.
INSTANT: Final = datetime(2026, 8, 2, 12, 0, tzinfo=UTC)


def _case_id(case: AdapterCase) -> str:
    """Name a parametrised case after its adapter.

    Args:
        case: The case.

    Returns:
        The adapter class's name.
    """
    return case.adapter_type.__name__


# --- Watching a call from outside ---------------------------------------------


class _Background:
    """One call, running on a thread of its own, that a test can interrogate.

    Attributes:
        returned: What the call produced, once it has finished.
        raised: What it threw, if anything. Recorded rather than propagated,
            because the thread it happened on is not the thread asserting.
    """

    def __init__(self, work: Callable[[], object]) -> None:
        """Start the call immediately.

        Args:
            work: The call to make.
        """
        self.returned: object = None
        self.raised: Exception | None = None
        self._done = threading.Event()
        self._thread = threading.Thread(target=self._run, args=(work,), daemon=True)
        self._thread.start()

    def _run(self, work: Callable[[], object]) -> None:
        """Make the call and record its outcome either way.

        Args:
            work: The call to make.
        """
        try:
            self.returned = work()
        except Exception as caught:
            self.raised = caught
        finally:
            self._done.set()

    def finished(self, timeout: float) -> bool:
        """Report whether the call has returned yet.

        Args:
            timeout: How long to wait for it.

        Returns:
            ``True`` if it finished inside the window.
        """
        return self._done.wait(timeout)

    def result(self) -> object:
        """Wait for the call and give back what it produced.

        Returns:
            The return value.

        Raises:
            AssertionError: If the call never finished.
            Exception: Whatever the call threw, re-raised on the asserting
                thread so that a failure reads like an ordinary one.
        """
        assert self.finished(WATCHDOG), "the call never returned"
        if self.raised is not None:
            raise self.raised
        return self.returned


@contextlib.contextmanager
def _held_elsewhere(lock: object) -> Iterator[None]:
    """Hold a lock on another thread for the duration of the block.

    Args:
        lock: The lock to hold.

    Yields:
        Nothing. The lock is held throughout and released on the way out.
    """
    target: Any = lock
    taken = threading.Event()
    finish = threading.Event()

    def hold() -> None:
        with target:
            taken.set()
            finish.wait(WATCHDOG)

    thread = threading.Thread(target=hold, daemon=True)
    thread.start()
    assert taken.wait(WATCHDOG), "the holder thread never took the lock"
    try:
        yield
    finally:
        finish.set()
        thread.join(WATCHDOG)


def _free_for_another_thread(lock: object) -> bool:
    """Report whether some *other* thread could take this lock right now.

    Args:
        lock: The lock to try.

    Returns:
        ``True`` if a thread that is not the caller's acquired it. Asked from
        another thread deliberately: a re-entrant lock always says yes to the
        thread already holding it, which is the answer that would hide a lock
        being held across a callback.
    """
    target: Any = lock
    outcome: list[bool] = []

    def attempt() -> None:
        acquired = target.acquire(timeout=BLOCKED)
        outcome.append(bool(acquired))
        if acquired:
            target.release()

    thread = threading.Thread(target=attempt, daemon=True)
    thread.start()
    thread.join(WATCHDOG)
    return bool(outcome) and outcome[0]


# --- Adapters that park inside their own connect path -------------------------


class _ParkingVenue(MockVenue):
    """A venue whose session establishment stops until a test releases it.

    ``take_failure`` is the first thing ``_establish`` does, so blocking there
    parks the adapter inside its lifecycle hook with the session lock held —
    the state every "is supervision still answered" question is about.

    Armed on request rather than by default, so that the same class serves as
    the ordinary one-instrument venue for the tests wanting no parking at all.
    """

    def __init__(self) -> None:
        """Build a venue offering one instrument, with parking disarmed."""
        super().__init__()
        self.add_symbol(EURUSD)
        self.publish_tick(tick())
        self.entered = threading.Event()
        self.release = threading.Event()
        self.release.set()

    def arm(self) -> None:
        """Make the next session attempt park until :attr:`release` is set."""
        self.entered.clear()
        self.release.clear()

    def take_failure(self, operation: str) -> BrokerError | None:
        """Park on the way into a session attempt, then behave normally.

        Args:
            operation: The port method being attempted.

        Returns:
            Whatever the venue was told to raise here, as usual.
        """
        if operation in ESTABLISHING:
            self.entered.set()
            self.release.wait(WATCHDOG)
        return super().take_failure(operation)


class _ParkingTerminal(FakeTerminal):
    """A terminal whose ``initialize`` stops until a test releases it.

    The MetaTrader 5 counterpart of :class:`_ParkingVenue`, and the more
    realistic of the two: a terminal that has stopped answering is the actual
    situation in which somebody asks whether the venue is still up.
    """

    def __init__(self) -> None:
        """Build a healthy terminal with parking disarmed."""
        super().__init__()
        self.entered = threading.Event()
        self.release = threading.Event()
        self.release.set()

    def arm(self) -> None:
        """Make the next login park until :attr:`release` is set."""
        self.entered.clear()
        self.release.clear()

    def initialize(
        self,
        path: str,
        *,
        login: int,
        password: str,
        server: str,
        timeout: int,
        portable: bool,
    ) -> bool:
        """Park, then log in as the ordinary fake would.

        Args:
            path: Terminal location.
            login: Account number.
            password: Account password.
            server: Trade server name.
            timeout: Milliseconds the terminal is given.
            portable: Whether to start in portable mode.

        Returns:
            The scripted outcome.
        """
        self.entered.set()
        self.release.wait(WATCHDOG)
        return super().initialize(
            path,
            login=login,
            password=password,
            server=server,
            timeout=timeout,
            portable=portable,
        )


def _parking_mock() -> tuple[MockBrokerAdapter, _ParkingVenue]:
    """Build a mock adapter whose venue can be told to park.

    Returns:
        The adapter and its venue, as a pair. The venue is handed back
        separately because ``adapter.venue`` is typed as the ordinary
        :class:`~atlas.broker.mock.venue.MockVenue`, which cannot park.
    """
    venue = _ParkingVenue()
    return MockBrokerAdapter(venue), venue


def _parking_mt5() -> tuple[MT5BrokerAdapter, _ParkingTerminal]:
    """Build a MetaTrader 5 adapter whose terminal can be told to park.

    Returns:
        The adapter and its terminal, as a pair. The configuration is borrowed
        from the shared fixture builder so that credentials, server name and
        clock offset stay defined in one place.
    """
    terminal = _ParkingTerminal()
    config = _mt5()._session.config
    session = MT5Session(config, terminal_factory=lambda: as_terminal(terminal))
    return MT5BrokerAdapter(config, session=session), terminal


# --- A probe that reports on its own lifecycle --------------------------------


class _RecordingLifecycle(BaseBrokerAdapter):
    """A base subclass whose lifecycle hooks report whether they ever overlap.

    The mutual exclusion under test is the *base class's*, so this is where it
    is measured: a probe with no venue, no clock and no translation, whose only
    job is to notice a second thread arriving while the first is still inside.
    Every hook lingers for :data:`OVERLAP`, which is long enough that an
    unsynchronised implementation shows an overlap on the first run.

    That the two real adapters inherit this is asserted separately, in
    ``test_base_adapter.py``: neither defines ``connect``, ``disconnect`` or
    ``reconnect`` at all, so there is no path by which they could not.

    Attributes:
        state: The lifecycle state the base reads back.
        calls: Which hooks ran, in order.
        overlaps: How many times a hook was entered while another was running.
    """

    def __init__(self) -> None:
        """Start disconnected, having recorded nothing."""
        super().__init__()
        self.state = ConnectionState.DISCONNECTED
        self.calls: list[str] = []
        self.overlaps = 0
        self._inside = 0
        self._tally = threading.Lock()

    @property
    def _session_state(self) -> ConnectionState:
        """The probe's lifecycle state."""
        return self.state

    @property
    def _session_broker(self) -> BrokerName:
        """A fixed brokerage name."""
        return "Probe Brokerage"

    @property
    def _session_server(self) -> ServerName:
        """A fixed server name."""
        return "Probe-Demo"

    @contextlib.contextmanager
    def _section(self, name: str) -> Iterator[None]:
        """Record one pass through a lifecycle hook.

        Args:
            name: Which hook.

        Yields:
            Nothing. Entries and exits are counted around the block, and a count
            above one at any instant is an overlap.
        """
        with self._tally:
            self.calls.append(name)
            self._inside += 1
            if self._inside > 1:
                self.overlaps += 1
        try:
            time.sleep(OVERLAP)
            yield
        finally:
            with self._tally:
                self._inside -= 1

    def _connect(self) -> Connection:
        """Come up, slowly enough to be caught overlapping.

        Returns:
            The resulting snapshot.
        """
        with self._section("connect"):
            self.state = ConnectionState.CONNECTED
            self._record_latency(12.5, at=INSTANT)
        return self._connection()

    def _disconnect(self) -> None:
        """Go down, slowly enough to be caught overlapping."""
        with self._section("disconnect"):
            self._clear_session_readings()
            self.state = ConnectionState.DISCONNECTED

    def _reconnect(self) -> Connection:
        """Replace the session, by way of the public methods.

        Returns:
            The resulting snapshot.

        Notes:
            Written the way both real adapters write it — out of the public
            :meth:`disconnect` and :meth:`connect` — because that composition is
            the whole reason the session lock has to be re-entrant.
        """
        self.disconnect()
        return self.connect()


def _recorder() -> _RecordingLifecycle:
    """Build an instantiable probe.

    Returns:
        An instance. The port's remaining methods are filled in with stubs,
        because a subclass that has not answered all thirty-one cannot be built.
    """
    members: dict[str, object] = dict.fromkeys(
        _RecordingLifecycle.__abstractmethods__, lambda *_args, **_kwargs: None
    )
    built = type("RecordingAdapter", (_RecordingLifecycle,), members)
    return cast("_RecordingLifecycle", built())


# --- Locks that say what happened to them -------------------------------------


class _TracedLock:
    """A lock that appends to a shared log every time it is entered or left."""

    def __init__(self, name: str, inner: object, log: list[tuple[str, str]]) -> None:
        """Wrap a real lock.

        Args:
            name: What to call it in the log.
            inner: The lock being wrapped. Genuinely acquired, so the code under
                test keeps the synchronisation it asked for.
            log: Where to record. Shared with the other lock, so that the record
                is one ordered sequence rather than two.
        """
        self._name = name
        self._inner: Any = inner
        self._log = log

    def __enter__(self) -> bool:
        """Take the lock and record it.

        Returns:
            ``True``, as a lock's own ``__enter__`` does.
        """
        self._inner.acquire()
        self._log.append(("acquire", self._name))
        return True

    def __exit__(self, *_exc_info: object) -> None:
        """Record the release and let the lock go."""
        self._log.append(("release", self._name))
        self._inner.release()


def _traced(adapter: BaseBrokerAdapter) -> list[tuple[str, str]]:
    """Replace both of an adapter's locks with recording wrappers.

    Args:
        adapter: The adapter to instrument.

    Returns:
        The log the wrappers write to, in the order the events happened.
    """
    log: list[tuple[str, str]] = []
    session: Any = _TracedLock("session", adapter._session_lock, log)
    readings: Any = _TracedLock("readings", adapter._readings_lock, log)
    adapter._session_lock = session
    adapter._readings_lock = readings
    return log


def _exercise(adapter: BaseBrokerAdapter) -> None:
    """Put an adapter through every method that touches either lock.

    Args:
        adapter: A disconnected adapter.
    """
    adapter.connect()
    adapter.ping()
    adapter.latency()
    adapter.health()
    adapter.is_connected()
    adapter.reconnect()
    adapter.disconnect()
    adapter.health()


# --- The locks themselves -----------------------------------------------------


@pytest.mark.parametrize("case", CASES, ids=_case_id)
class TestEveryAdapterGetsTheLocks:
    def test_it_has_both_locks_without_having_asked_for_them(self, case: AdapterCase) -> None:
        adapter = case.build()

        assert adapter._session_lock is not None
        assert adapter._readings_lock is not None

    def test_the_session_lock_is_re_entrant(self, case: AdapterCase) -> None:
        # Both adapters compose reconnect out of the public disconnect and
        # connect, so the lock is taken twice on one thread. A plain lock would
        # deadlock on the second acquisition, and this is that acquisition.
        lock = case.build()._session_lock

        assert lock.acquire(blocking=False)
        try:
            assert lock.acquire(blocking=False)
            lock.release()
        finally:
            lock.release()

    def test_the_readings_lock_is_not_re_entrant(self, case: AdapterCase) -> None:
        # The counterpart, and the reason it is safe for it to be the cheap
        # kind: nothing is called while it is held, so it can never be
        # re-entered.
        lock = case.build()._readings_lock

        assert lock.acquire(blocking=False)
        try:
            assert not lock.acquire(blocking=False)
        finally:
            lock.release()

    def test_two_adapters_do_not_share_a_lock(self, case: AdapterCase) -> None:
        # A class-level lock would make every adapter in the process queue
        # behind every other one, including adapters at unrelated venues.
        first, second = case.build(), case.build()

        assert first._session_lock is not second._session_lock
        assert first._readings_lock is not second._readings_lock


# --- Supervision is never blocked ---------------------------------------------


@pytest.mark.parametrize("case", CASES, ids=_case_id)
class TestSupervisionDoesNotWaitForTheSessionLock:
    def test_health_answers_while_the_session_lock_is_held(self, case: AdapterCase) -> None:
        adapter = case.build()

        with _held_elsewhere(adapter._session_lock):
            watched = _Background(adapter.health)

            assert watched.finished(WATCHDOG)
        assert isinstance(watched.result(), Connection)

    def test_is_connected_answers_while_the_session_lock_is_held(self, case: AdapterCase) -> None:
        adapter = case.build()

        with _held_elsewhere(adapter._session_lock):
            watched = _Background(adapter.is_connected)

            assert watched.finished(WATCHDOG)
        assert watched.result() is False

    @pytest.mark.parametrize("method", ["connect", "disconnect", "reconnect"])
    def test_the_lifecycle_method_does_wait_for_it(self, case: AdapterCase, method: str) -> None:
        # The control for the two tests above. An adapter taking no lock at all
        # would satisfy them both and fail this.
        adapter = case.build()

        with _held_elsewhere(adapter._session_lock):
            watched = _Background(getattr(adapter, method))

            assert not watched.finished(BLOCKED)

        assert watched.finished(WATCHDOG)


class TestSupervisionDuringAnInFlightConnect:
    def test_the_mock_answers_health_while_a_connect_is_parked(self) -> None:
        adapter, venue = _parking_mock()
        venue.arm()
        connecting = _Background(adapter.connect)
        assert venue.entered.wait(WATCHDOG)

        snapshot = _Background(adapter.health)

        assert snapshot.finished(WATCHDOG)
        assert cast("Connection", snapshot.result()).connected is False
        venue.release.set()
        assert connecting.finished(WATCHDOG)

    def test_mt5_answers_health_while_the_terminal_is_not_responding(self) -> None:
        adapter, terminal = _parking_mt5()
        terminal.arm()
        connecting = _Background(adapter.connect)
        assert terminal.entered.wait(WATCHDOG)

        snapshot = _Background(adapter.health)

        assert snapshot.finished(WATCHDOG)
        # CONNECTING, not DISCONNECTED: the session has already moved, and
        # health reports where it actually is rather than a value cached before
        # the attempt started.
        assert cast("Connection", snapshot.result()).state is ConnectionState.CONNECTING
        terminal.release.set()
        assert connecting.finished(WATCHDOG)

    def test_ping_answers_while_a_connect_is_parked(self) -> None:
        # The other half of the claim: it is the *session* that is serialised,
        # not the adapter. A request path queueing behind the same lock would
        # make one stalled connect look like a stalled adapter.
        adapter, venue = _parking_mock()
        venue.arm()
        connecting = _Background(adapter.connect)
        assert venue.entered.wait(WATCHDOG)

        pinging = _Background(adapter.ping)

        assert pinging.finished(WATCHDOG)
        venue.release.set()
        assert connecting.finished(WATCHDOG)

    def test_a_second_lifecycle_call_waits_for_the_parked_connect(self) -> None:
        # The control, on the real path this time: the session lock is genuinely
        # held across the venue round trip, not merely around the bookkeeping
        # that follows it.
        adapter, terminal = _parking_mt5()
        terminal.arm()
        connecting = _Background(adapter.connect)
        assert terminal.entered.wait(WATCHDOG)

        closing = _Background(adapter.disconnect)

        assert not closing.finished(BLOCKED)
        terminal.release.set()
        assert connecting.finished(WATCHDOG)
        assert closing.finished(WATCHDOG)

    def test_the_parked_connect_still_completes_normally(self) -> None:
        adapter, venue = _parking_mock()
        venue.arm()
        connecting = _Background(adapter.connect)
        assert venue.entered.wait(WATCHDOG)

        venue.release.set()

        assert cast("Connection", connecting.result()).connected is True
        assert adapter.is_connected() is True


# --- Mutual exclusion ---------------------------------------------------------


class TestOnlyOneThreadIsEverInsideTheLifecycle:
    def test_concurrent_connects_do_not_overlap(self) -> None:
        adapter = _recorder()

        with ThreadPoolExecutor(max_workers=THREADS) as pool:
            list(pool.map(lambda _index: adapter.connect(), range(THREADS)))

        assert adapter.overlaps == 0
        assert adapter.calls.count("connect") == THREADS

    def test_concurrent_disconnects_do_not_overlap(self) -> None:
        adapter = _recorder()
        adapter.connect()

        with ThreadPoolExecutor(max_workers=THREADS) as pool:
            list(pool.map(lambda _index: adapter.disconnect(), range(THREADS)))

        assert adapter.overlaps == 0

    def test_connects_and_disconnects_do_not_overlap_each_other(self) -> None:
        adapter = _recorder()
        work: list[Callable[[], object]] = [
            adapter.connect if index % 2 == 0 else adapter.disconnect for index in range(THREADS)
        ]

        with ThreadPoolExecutor(max_workers=THREADS) as pool:
            list(pool.map(lambda call: call(), work))

        assert adapter.overlaps == 0

    def test_a_reconnect_is_one_critical_section_and_not_two(self) -> None:
        # reconnect re-enters the lock twice. Nothing else may get in between,
        # or a concurrent connect would establish the very session that the
        # reconnect is about to replace. Absence of overlap is too weak to say
        # so — each half takes the lock on its own account, so the halves never
        # overlap even when the outer call holds nothing. Strict alternation is
        # the claim: every disconnect is followed by its own connect.
        adapter = _recorder()

        with ThreadPoolExecutor(max_workers=THREADS) as pool:
            list(pool.map(lambda _index: adapter.reconnect(), range(THREADS)))

        assert adapter.overlaps == 0
        assert adapter.calls[0::2] == ["disconnect"] * THREADS
        assert adapter.calls[1::2] == ["connect"] * THREADS

    def test_nothing_reaches_the_session_between_the_halves_of_a_reconnect(self) -> None:
        # The same claim, decided rather than raced, and on a real adapter.
        # Parked between the two halves, a competing disconnect must still be
        # waiting; an unheld outer call would let it through, and the reconnect
        # would then come up on top of a session the caller had just closed.
        #
        # The mock is the adapter that can be asked. Its establishing half is
        # the private _establish, so the outer hold is the only thing covering
        # the parked region. The MetaTrader 5 one reaches its venue through the
        # public connect, which takes the lock again on its own account, so the
        # same experiment there would pass without the outer hold and prove
        # nothing. That adapter is covered by the hold-depth test instead.
        adapter, venue = _parking_mock()
        adapter.connect()
        venue.arm()
        replacing = _Background(adapter.reconnect)
        assert venue.entered.wait(WATCHDOG)

        closing = _Background(adapter.disconnect)

        assert not closing.finished(BLOCKED)
        venue.release.set()
        assert replacing.finished(WATCHDOG)
        assert closing.finished(WATCHDOG)
        assert adapter.is_connected() is False

    def test_a_parked_venue_does_not_block_a_disconnect_by_itself(self) -> None:
        # The control for both. Parking is armed on session establishment only,
        # so the disconnect that waits above is waiting on the lock rather than
        # on the venue that happens to be parked at the time.
        adapter, venue = _parking_mock()
        adapter.connect()
        venue.arm()

        closing = _Background(adapter.disconnect)

        assert closing.finished(WATCHDOG)

    def test_the_probe_would_notice_an_overlap(self) -> None:
        # The control for every assertion above. Calling the hook directly
        # bypasses the base's public method and therefore the lock, which is the
        # only way to get an overlap past a correct implementation — and it is
        # what those tests would be measuring if the lock were removed.
        adapter = _recorder()

        with ThreadPoolExecutor(max_workers=THREADS) as pool:
            list(pool.map(lambda _index: adapter._connect(), range(THREADS)))

        assert adapter.overlaps > 0


# --- Lock ordering ------------------------------------------------------------


@pytest.mark.parametrize("case", CASES, ids=_case_id)
class TestLockOrdering:
    def test_the_readings_lock_is_a_leaf(self, case: AdapterCase) -> None:
        # Nothing at all happens between taking the readings lock and releasing
        # it — no nested acquisition, no model construction, no venue call. A
        # lock that calls nothing cannot take part in a cycle, which is why
        # there is no deadlock left to reason about beyond the ordering below.
        adapter = case.build()
        log = _traced(adapter)

        _exercise(adapter)

        for index, event in enumerate(log):
            if event == ("acquire", "readings"):
                assert log[index + 1] == ("release", "readings")

    def test_the_session_lock_is_never_taken_under_the_readings_lock(
        self, case: AdapterCase
    ) -> None:
        adapter = case.build()
        log = _traced(adapter)

        _exercise(adapter)

        held: list[str] = []
        for action, name in log:
            if action == "acquire":
                assert not (name == "session" and "readings" in held)
                held.append(name)
            else:
                held.remove(name)

    def test_the_exercise_actually_takes_both_locks(self, case: AdapterCase) -> None:
        # Without this the two tests above pass on an adapter that locks
        # nothing, which is the state this task started from.
        adapter = case.build()
        log = _traced(adapter)

        _exercise(adapter)

        assert ("acquire", "session") in log
        assert ("acquire", "readings") in log

    def test_health_takes_the_readings_lock_and_not_the_session_lock(
        self, case: AdapterCase
    ) -> None:
        adapter = case.build()
        log = _traced(adapter)

        adapter.health()

        assert [name for action, name in log if action == "acquire"] == ["readings"]

    def test_is_connected_takes_no_lock_at_all(self, case: AdapterCase) -> None:
        adapter = case.build()
        log = _traced(adapter)

        adapter.is_connected()

        assert log == []

    @pytest.mark.parametrize("method", ["ping", "latency"])
    def test_recording_a_reading_takes_the_readings_lock_and_nothing_else(
        self, case: AdapterCase, method: str
    ) -> None:
        # Both readings are written as a pair, so both writers have to take the
        # lock; and neither may take the session lock, or a heartbeat would
        # queue behind a connect.
        adapter = case.build()
        adapter.connect()
        log = _traced(adapter)

        getattr(adapter, method)()

        assert [name for action, name in log if action == "acquire"] == ["readings"]

    def test_the_session_lock_is_never_dropped_midway_through_a_reconnect(
        self, case: AdapterCase
    ) -> None:
        # Read the trace as a hold depth. Both adapters build a reconnect out of
        # the public lifecycle methods, so the inner halves take the lock again
        # on their own account — which is what makes "the halves never overlap"
        # too weak to say the pair is atomic. Two things say it: the depth
        # reaches two, so the outer hold really was in force while an inner half
        # ran, and it does not touch zero until the whole reconnect is over.
        # A reconnect holding nothing of its own shows a depth that never
        # exceeds one, and that is the window a competitor would use.
        adapter = case.build()
        adapter.connect()
        log = _traced(adapter)
        adapter.reconnect()
        depth = 0
        depths: list[int] = []
        for action, name in log:
            if name != "session":
                continue
            depth += 1 if action == "acquire" else -1
            depths.append(depth)

        assert max(depths) >= 2
        assert min(depths[:-1]) >= 1
        assert depths[-1] == 0

    def test_the_snapshot_is_built_after_the_readings_lock_is_released(
        self, case: AdapterCase, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        # The readings lock covers copying two cached fields out and nothing
        # else. Building the model under it would still be correct, and would
        # make every heartbeat queue behind a dataclass construction — which is
        # contention bought for nothing. The broker name is read while the
        # model's arguments are being assembled, so asking there answers which
        # side of the release the construction happens on.
        adapter = case.build()
        adapter.connect()
        owner: Any = type(adapter)
        original = owner._session_broker
        free: list[bool] = []

        def spy(instance: BaseBrokerAdapter) -> BrokerName:
            free.append(_free_for_another_thread(adapter._readings_lock))
            return cast("BrokerName", original.fget(instance))

        monkeypatch.setattr(owner, "_session_broker", property(spy))

        assert adapter.health().broker == case.broker
        assert free == [True]

    def test_the_freedom_probe_would_notice_the_readings_lock_held(self, case: AdapterCase) -> None:
        # The control for the test above. A probe that answered "free"
        # unconditionally would pass it whatever the base did with the lock.
        adapter = case.build()

        assert _free_for_another_thread(adapter._readings_lock) is True
        with adapter._readings_lock:
            assert _free_for_another_thread(adapter._readings_lock) is False

    def test_disconnect_takes_both_locks(self, case: AdapterCase) -> None:
        # The session lock because it is a lifecycle call, and the readings lock
        # because the session's measurements go with the session.
        adapter = case.build()
        adapter.connect()
        adapter.latency()
        log = _traced(adapter)

        adapter.disconnect()

        assert ("acquire", "session") in log
        assert ("acquire", "readings") in log


# --- Callbacks ----------------------------------------------------------------


class TestNoLockIsHeldWhileUserCodeRuns:
    @staticmethod
    def _subscribed(handler: Callable[[Tick], None]) -> tuple[MockBrokerAdapter, _ParkingVenue]:
        """Build a connected adapter with one quote subscription.

        Args:
            handler: What to call on each quote.

        Returns:
            The adapter and its venue.
        """
        adapter, venue = _parking_mock()
        adapter.connect()
        adapter.subscribe_ticks(["EURUSD"], handler)
        return adapter, venue

    def test_both_locks_are_free_while_a_handler_runs(self) -> None:
        seen: list[tuple[bool, bool]] = []
        held: list[BaseBrokerAdapter] = []

        def handler(_tick: Tick) -> None:
            seen.append(
                (
                    _free_for_another_thread(held[0]._session_lock),
                    _free_for_another_thread(held[0]._readings_lock),
                )
            )

        adapter, venue = self._subscribed(handler)
        held.append(adapter)
        venue.publish_tick(tick())

        assert seen == [(True, True)]
        assert venue.handler_failures == ()

    def test_a_handler_may_disconnect_the_adapter_it_was_called_from(self) -> None:
        held: list[MockBrokerAdapter] = []

        def handler(_tick: Tick) -> None:
            held[0].disconnect()

        adapter, venue = self._subscribed(handler)
        held.append(adapter)
        venue.publish_tick(tick())

        assert adapter.is_connected() is False
        assert venue.handler_failures == ()

    def test_a_handler_may_reconnect_the_adapter_it_was_called_from(self) -> None:
        held: list[MockBrokerAdapter] = []

        def handler(_tick: Tick) -> None:
            held[0].reconnect()

        adapter, venue = self._subscribed(handler)
        held.append(adapter)
        venue.publish_tick(tick())

        assert adapter.is_connected() is True
        assert venue.handler_failures == ()

    def test_a_handler_may_read_health_and_gets_a_coherent_snapshot(self) -> None:
        seen: list[Connection] = []
        held: list[MockBrokerAdapter] = []

        def handler(_tick: Tick) -> None:
            seen.append(held[0].health())

        adapter, venue = self._subscribed(handler)
        held.append(adapter)
        adapter.latency()
        venue.publish_tick(tick())

        assert len(seen) == 1
        assert seen[0].connected is True
        assert seen[0].latency_ms is not None

    def test_delivery_and_a_lifecycle_call_do_not_deadlock_against_each_other(self) -> None:
        # Delivery happens on the publishing thread and takes no adapter lock;
        # the lifecycle takes one and delivers nothing. Neither waits for the
        # other, and running both at once is the assertion that says so.
        delivered = threading.Event()

        def handler(_tick: Tick) -> None:
            delivered.set()
            time.sleep(OVERLAP)

        adapter, venue = self._subscribed(handler)
        publishing = _Background(lambda: venue.publish_tick(tick()))
        assert delivered.wait(WATCHDOG)
        churning = _Background(adapter.reconnect)

        assert publishing.finished(WATCHDOG)
        assert churning.finished(WATCHDOG)
        publishing.result()
        churning.result()
        assert venue.handler_failures == ()


# --- Contention ---------------------------------------------------------------


class TestTheLifecycleSurvivesContention:
    def test_repeated_cycles_leave_the_adapter_usable(self) -> None:
        adapter, _venue = _parking_mock()

        for _cycle in range(THREADS * CYCLES):
            adapter.connect()
            adapter.disconnect()

        assert adapter.is_connected() is False
        assert adapter.health().latency_ms is None
        assert adapter.connect().connected is True

    @pytest.mark.parametrize("case", CASES, ids=_case_id)
    def test_concurrent_cycles_raise_nothing_undocumented(self, case: AdapterCase) -> None:
        # The claim is not that a racing call succeeds — the base's docstring
        # says plainly that it may not. It is that a call losing a race fails
        # the way its own contract says it fails, rather than with an
        # AttributeError out of a half-built session.
        #
        # Driving one venue from eight threads is inside the guarantee here
        # precisely because of the lock: every venue mutation these calls make
        # happens inside a lifecycle hook, and the unlocked calls only read.
        adapter = case.build()

        def churn(_index: int) -> None:
            for _cycle in range(CYCLES):
                with contextlib.suppress(BrokerError):
                    adapter.connect()
                    adapter.ping()
                    adapter.health()
                    adapter.reconnect()
                    adapter.disconnect()

        with ThreadPoolExecutor(max_workers=THREADS) as pool:
            list(pool.map(churn, range(THREADS)))

        assert adapter.connect().connected is True

    def test_concurrent_reads_all_answer_on_a_connected_adapter(self) -> None:
        adapter, _venue = _parking_mock()
        adapter.connect()

        def read(_index: int) -> tuple[int, bool]:
            return len(adapter.get_symbols()), adapter.health().connected

        with ThreadPoolExecutor(max_workers=THREADS) as pool:
            answers = list(pool.map(read, range(THREADS * CYCLES)))

        assert answers == [(1, True)] * (THREADS * CYCLES)


class TestTheSnapshotIsNeverTorn:
    """Why ``_disconnect`` clears the readings before it takes the session down.

    A supervisor reading ``health()`` while a disconnect runs must never be told
    "no session, and here is its latency". The window is one statement wide, so
    racing for it would be a lottery: the first test below settles the ordering
    by observation instead, and the second is the stress run that would notice a
    variant the ordering test did not anticipate.
    """

    @pytest.mark.parametrize("case", CASES, ids=_case_id)
    def test_the_readings_are_cleared_before_the_session_goes_down(self, case: AdapterCase) -> None:
        # Read at the only moment that settles the question: from inside the
        # clear itself, asking what the session state still is. True means the
        # readings went first. Swapping the two statements in either adapter
        # turns this into False, deterministically and on every run.
        adapter = case.build()
        patched: Any = adapter
        original = adapter._clear_session_readings
        still_up: list[bool] = []

        def record() -> None:
            still_up.append(adapter._session_state.is_usable)
            original()

        patched._clear_session_readings = record
        adapter.connect()
        adapter.latency()
        adapter.disconnect()

        assert still_up == [True]
        assert adapter.health().latency_ms is None

    def test_a_concurrent_reader_never_sees_a_dead_session_with_a_live_latency(self) -> None:
        adapter, _venue = _parking_mock()
        stop = threading.Event()
        torn: list[Connection] = []
        states: set[bool] = set()

        def watch() -> None:
            while not stop.is_set():
                snapshot = adapter.health()
                states.add(snapshot.connected)
                if not snapshot.connected and snapshot.latency_ms is not None:
                    torn.append(snapshot)

        watcher = threading.Thread(target=watch, daemon=True)
        watcher.start()
        try:
            for _cycle in range(CYCLES):
                adapter.connect()
                adapter.latency()
                time.sleep(PAUSE)
                adapter.disconnect()
                time.sleep(PAUSE)
        finally:
            stop.set()
            watcher.join(WATCHDOG)

        assert torn == []
        # The control: a reader that only ever sampled one side of the cycle
        # would satisfy the assertion above without having looked at anything.
        assert states == {True, False}


# --- Where the locking lives --------------------------------------------------


def _imports_threading(path: Path) -> bool:
    """Report whether a module imports ``threading`` at all.

    Args:
        path: The source file.

    Returns:
        ``True`` if the name appears in any import statement.
    """
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    for node in ast.walk(tree):
        if isinstance(node, ast.Import) and any(
            alias.name.split(".")[0] == "threading" for alias in node.names
        ):
            return True
        if isinstance(node, ast.ImportFrom) and (node.module or "").split(".")[0] == "threading":
            return True
    return False


class TestTheLockingIsNotDuplicated:
    def test_exactly_one_module_in_the_package_imports_threading(self) -> None:
        # The task's "avoid duplicated locking logic", as an assertion rather
        # than a review note. An adapter that grew a lock of its own would be
        # caught here on the day it was written.
        package = Path(inspect.getfile(base_module)).parent

        importers = {path.name for path in package.rglob("*.py") if _imports_threading(path)}

        assert importers == {"base.py"}
