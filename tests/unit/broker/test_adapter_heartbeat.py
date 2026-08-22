"""Heartbeat freshness, on every adapter, against a clock that is told what time it is.

`BaseBrokerAdapter` has always recorded *when* the venue was last heard from.
ATLAS-TASK-0009 adds the question a supervisor actually asks —
:meth:`~atlas.broker.base.BaseBrokerAdapter.heartbeat_age` and
:meth:`~atlas.broker.base.BaseBrokerAdapter.is_heartbeat_fresh` — and the clock
that makes it answerable without reading the host.

Every adapter is put through the same sequence, discovered rather than named, in
the way ``test_base_adapter.py`` established: the failure mode worth testing for
is two implementations quietly disagreeing about something they used to agree
about, and a per-adapter suite cannot see that. :data:`CASES` says how to build
each one *and* how to move its time, because those are the same fact for the
mock — where the venue owns the clock — and separate facts for MetaTrader 5,
where the clock is injected past a session.

Nothing here sleeps. A test for a one-hour timeout advances an hour and asserts
an exact `timedelta`; a tolerance would be the tell that a real clock had got in.

Two properties are asserted that are about the *shape* of the answer rather than
its value, and both are inherited obligations from ATLAS-TASK-0008:

The readings lock stays a leaf
    The clock is read before the lock is taken, never under it. A clock is
    supplied from outside, so calling one while holding a lock would put an
    arbitrary amount of foreign code inside the critical section that ADR-0007
    proves has no cycle.

Supervision is still never blocked
    Neither method waits on the session lock, so both answer while a connect is
    parked. That is the one moment the age of the last heartbeat is the question
    worth asking.
"""

from __future__ import annotations

import ast
import inspect
import threading
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import TYPE_CHECKING, Any, Final, cast

import pytest
from pydantic import SecretStr

from atlas.broker.base import BaseBrokerAdapter
from atlas.broker.mock import MockBrokerAdapter, MockVenue
from atlas.broker.models import ConnectionState
from atlas.broker.mt5.adapter import MT5BrokerAdapter
from atlas.broker.mt5.connection import MT5Config, MT5Session
from atlas.common.clock import Clock, ManualClock, SystemClock
from tests.unit.broker.mt5.conftest import SERVER_OFFSET, FakeTerminal, as_terminal

if TYPE_CHECKING:
    from collections.abc import Callable

pytestmark = pytest.mark.unit

#: Where every clock in this module starts. The mock venue's own default, so the
#: mock adapter's timestamps read the same here as they do in its own suite.
START: Final = datetime(2020, 1, 1, tzinfo=UTC)

#: Long enough that a thread which is going to finish has finished, short enough
#: that a hang fails the run instead of stopping it. Only ever waited on when
#: something has gone wrong.
WATCHDOG: Final = 5.0

#: The freshness window most tests here use, chosen to be long enough that the
#: advances below can be well inside it or well outside it without either being
#: a boundary case. The boundary has tests of its own.
WINDOW: Final = timedelta(hours=1)

#: The smallest amount of time a `timedelta` can express, used to step just over
#: a boundary. Anything larger would leave the test passing for a version of the
#: comparison that is off by more than it is testing for.
TICK: Final = timedelta(microseconds=1)


@dataclass(frozen=True)
class AdapterCase:
    """One implementation of the port, and the clock its time comes from.

    Attributes:
        name: What to call the case in a test id.
        build: Returns a fresh, unconnected adapter and the manual clock it
            runs on. A factory rather than a fixture because several tests
            below need two independent instances.
    """

    name: str
    build: Callable[[], tuple[BaseBrokerAdapter, ManualClock]]

    def connected(self) -> tuple[BaseBrokerAdapter, ManualClock]:
        """Build an adapter and establish its session.

        Returns:
            The connected adapter and its clock. Connecting records the first
            heartbeat on both adapters, so the age is zero on return.
        """
        adapter, clock = self.build()
        adapter.connect()
        return adapter, clock


def _mock() -> tuple[MockBrokerAdapter, ManualClock]:
    """Build a mock adapter and the venue clock it shares.

    Returns:
        The adapter and its clock. They are the same clock by construction —
        the adapter takes the venue's rather than being given one — which is
        what stops a heartbeat stamped in venue time being aged against
        anything else.
    """
    venue = MockVenue(now=START)
    return MockBrokerAdapter(venue), venue.clock


def _mt5() -> tuple[MT5BrokerAdapter, ManualClock]:
    """Build a MetaTrader 5 adapter on a manual clock.

    Returns:
        The adapter, wired to the fake terminal the MT5 tests use, and the
        clock injected into it. Nothing here imports the vendor package or
        starts a terminal.
    """
    config = MT5Config(
        login=9001234,
        password=SecretStr("not-a-real-password"),
        server="Example-Demo",
        terminal_path=Path("C:/Program Files/Example/terminal64.exe"),
        server_utc_offset=SERVER_OFFSET,
        deviation_points=20,
        filling_mode_by_instrument={},
    )
    clock = ManualClock(START)
    session = MT5Session(config, terminal_factory=lambda: as_terminal(FakeTerminal()))
    return MT5BrokerAdapter(config, session=session, clock=clock), clock


CASES: Final = (AdapterCase("mock", _mock), AdapterCase("mt5", _mt5))


def _bare() -> BaseBrokerAdapter:
    """Build a subclass whose constructor predates the clock parameter.

    Returns:
        An instance. The port's remaining methods are stubbed the way
        ``test_adapter_concurrency.py`` stubs them, because a subclass that has
        not answered all thirty-one cannot be built. The one line that is real
        is the one under test: a ``super().__init__()`` written exactly as both
        adapters wrote theirs before a clock existed.
    """

    class Bare(BaseBrokerAdapter):
        def __init__(self) -> None:
            """Initialise the way every existing subclass already did."""
            super().__init__()

    members: dict[str, object] = dict.fromkeys(
        Bare.__abstractmethods__, lambda *_args, **_kwargs: None
    )
    return cast("BaseBrokerAdapter", type("BareAdapter", (Bare,), members)())


def _free_for_another_thread(lock: object) -> bool:
    """Report whether a lock could be taken right now, by a thread that is not this one.

    Args:
        lock: The lock to probe.

    Returns:
        ``True`` if a different thread acquired it without blocking. Asked from
        another thread because the session lock is re-entrant, and a re-entrant
        lock answers "free" to the thread already holding it.
    """
    target: Any = lock
    outcome: list[bool] = []

    def probe() -> None:
        acquired = target.acquire(blocking=False)
        outcome.append(acquired)
        if acquired:
            target.release()

    worker = threading.Thread(target=probe)
    worker.start()
    worker.join(WATCHDOG)
    return outcome == [True]


#: Ways of reading the host clock that no module in ``atlas.broker`` may use.
#: Spelled as they appear in source, and matched on the last two dotted parts so
#: that ``datetime.datetime.now`` is caught and ``self._clock.now`` is not.
#:
#: ``datetime.fromtimestamp`` is deliberately absent. It converts an epoch the
#: *venue* sent — which is what ``mt5/mapper.py`` uses it for — and reads nothing
#: from the host, so banning it would be banning translation rather than time.
HOST_CLOCK_READS: Final = frozenset(
    {
        "datetime.now",
        "datetime.utcnow",
        "datetime.today",
        "date.today",
        "time.time",
        "time.time_ns",
        "time.monotonic",
        "time.monotonic_ns",
        "time.perf_counter",
    }
)


def _host_clock_reads(path: Path) -> set[str]:
    """Find every direct read of the host clock in a module.

    Args:
        path: The source file.

    Returns:
        The offending call names, as spelled in the source. Empty for a module
        that gets the time from a clock it was given.
    """
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    found: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute):
            spelled = ast.unparse(node.func)
            if ".".join(spelled.split(".")[-2:]) in HOST_CLOCK_READS:
                found.add(spelled)
    return found


@pytest.fixture(params=CASES, ids=lambda case: case.name)
def case(request: pytest.FixtureRequest) -> AdapterCase:
    """Return one adapter case.

    Args:
        request: Pytest's handle on the parametrisation.

    Returns:
        The case, so that every test in this module runs against every adapter.
    """
    built: AdapterCase = request.param
    return built


class TestNothingInThePackageReadsTheHostClock:
    def test_no_module_calls_the_host_clock_directly(self) -> None:
        # The rule an adapter author has to know, as an assertion rather than a
        # review note. A third adapter reaching for `datetime.now` gets its
        # determinism from wherever it happens to be running, and is caught here
        # on the day it is written rather than the first time a test is flaky.
        package = Path(inspect.getfile(BaseBrokerAdapter)).parent

        offenders = {
            path.name: found for path in package.rglob("*.py") if (found := _host_clock_reads(path))
        }

        assert offenders == {}

    def test_the_scan_notices_a_module_that_does(self, tmp_path: Path) -> None:
        offender = tmp_path / "offender.py"
        offender.write_bytes(b"from datetime import UTC, datetime\nx = datetime.now(UTC)\n")

        assert _host_clock_reads(offender) == {"datetime.now"}

    def test_the_scan_does_not_object_to_an_injected_clock(self, tmp_path: Path) -> None:
        innocent = tmp_path / "innocent.py"
        innocent.write_bytes(b"def f(self):\n    return self._clock.now()\n")

        assert _host_clock_reads(innocent) == set()


class TestTheRegistryCoversEveryAdapter:
    def test_every_concrete_adapter_has_a_case(self) -> None:
        # A third adapter is held to everything below from the moment it
        # exists, rather than from the moment somebody remembers.
        subclasses = {
            found for found in BaseBrokerAdapter.__subclasses__() if not found.__abstractmethods__
        }
        covered = {type(case.build()[0]) for case in CASES}

        assert subclasses <= covered


class TestBeforeTheVenueIsEverHeardFrom:
    def test_there_is_no_age_to_report(self, case: AdapterCase) -> None:
        adapter, _clock = case.build()

        assert adapter.heartbeat_age() is None

    def test_nothing_is_fresh(self, case: AdapterCase) -> None:
        # Never having heard from a venue is reported as not fresh. The other
        # answer makes an adapter that has never connected look healthy to the
        # first supervisor that asks.
        adapter, _clock = case.build()

        assert adapter.is_heartbeat_fresh(WINDOW) is False

    def test_an_enormous_window_does_not_make_it_fresh(self, case: AdapterCase) -> None:
        adapter, _clock = case.build()

        assert adapter.is_heartbeat_fresh(timedelta(days=365 * 100)) is False

    def test_the_snapshot_agrees_that_there_is_no_heartbeat(self, case: AdapterCase) -> None:
        adapter, _clock = case.build()

        assert adapter.health().last_heartbeat is None


class TestFreshnessWhileTimePasses:
    def test_connecting_records_a_heartbeat_of_no_age(self, case: AdapterCase) -> None:
        adapter, _clock = case.connected()

        assert adapter.heartbeat_age() == timedelta(0)

    def test_a_new_heartbeat_is_fresh(self, case: AdapterCase) -> None:
        adapter, _clock = case.connected()

        assert adapter.is_heartbeat_fresh(WINDOW) is True

    def test_the_age_is_exactly_the_time_that_passed(self, case: AdapterCase) -> None:
        adapter, clock = case.connected()

        clock.advance(timedelta(minutes=30))

        assert adapter.heartbeat_age() == timedelta(minutes=30)

    def test_the_age_accumulates_across_several_advances(self, case: AdapterCase) -> None:
        adapter, clock = case.connected()

        for _ in range(4):
            clock.advance(timedelta(minutes=15))

        assert adapter.heartbeat_age() == timedelta(hours=1)

    def test_reading_the_age_does_not_move_it(self, case: AdapterCase) -> None:
        # The reason a wall clock cannot be used for this: two reads of a real
        # clock differ, and an assertion on the age would need a tolerance.
        adapter, _clock = case.connected()

        assert [adapter.heartbeat_age() for _ in range(10)] == [timedelta(0)] * 10

    def test_a_year_of_silence_is_measured_exactly_and_costs_nothing(
        self, case: AdapterCase
    ) -> None:
        adapter, clock = case.connected()

        clock.advance(timedelta(days=365))

        assert adapter.heartbeat_age() == timedelta(days=365)


class TestDetectingAStaleHeartbeat:
    def test_a_heartbeat_older_than_the_window_is_not_fresh(self, case: AdapterCase) -> None:
        adapter, clock = case.connected()

        clock.advance(WINDOW * 2)

        assert adapter.is_heartbeat_fresh(WINDOW) is False

    def test_it_becomes_stale_at_the_moment_it_passes_the_window(self, case: AdapterCase) -> None:
        adapter, clock = case.connected()

        clock.advance(WINDOW)
        fresh_at_the_boundary = adapter.is_heartbeat_fresh(WINDOW)
        clock.advance(TICK)

        assert fresh_at_the_boundary is True
        assert adapter.is_heartbeat_fresh(WINDOW) is False

    def test_a_stale_adapter_still_reports_the_instant_it_last_heard(
        self, case: AdapterCase
    ) -> None:
        # Stale is not forgotten. The snapshot keeps saying when, which is what
        # a person reads; the age says how long ago, which is what a supervisor
        # branches on.
        adapter, clock = case.connected()

        clock.advance(WINDOW * 2)

        assert adapter.health().last_heartbeat == START
        assert adapter.is_heartbeat_fresh(WINDOW) is False

    def test_a_stale_adapter_still_reports_itself_connected(self, case: AdapterCase) -> None:
        # Freshness is not a second connection state, and this method does not
        # take the session down. Silence is evidence a caller weighs; only a
        # failed request or an explicit disconnect changes the session.
        adapter, clock = case.connected()

        clock.advance(WINDOW * 2)

        assert adapter.is_connected() is True
        assert adapter.health().state is ConnectionState.CONNECTED

    def test_a_ping_makes_a_stale_adapter_fresh_again(self, case: AdapterCase) -> None:
        adapter, clock = case.connected()
        clock.advance(WINDOW * 2)

        assert adapter.ping() is True

        assert adapter.heartbeat_age() == timedelta(0)
        assert adapter.is_heartbeat_fresh(WINDOW) is True

    def test_measuring_latency_makes_a_stale_adapter_fresh_again(self, case: AdapterCase) -> None:
        adapter, clock = case.connected()
        clock.advance(WINDOW * 2)

        adapter.latency()

        assert adapter.heartbeat_age() == timedelta(0)


class TestTheWindowIsTheCallersAndTheBoundaryIsInclusive:
    def test_a_zero_window_accepts_a_heartbeat_of_no_age(self, case: AdapterCase) -> None:
        # The boundary is inclusive so that a supervisor polling on its own
        # timeout does not fail on the tick it was scheduled for.
        adapter, _clock = case.connected()

        assert adapter.is_heartbeat_fresh(timedelta(0)) is True

    def test_a_zero_window_rejects_any_age_at_all(self, case: AdapterCase) -> None:
        adapter, clock = case.connected()

        clock.advance(TICK)

        assert adapter.is_heartbeat_fresh(timedelta(0)) is False

    def test_a_negative_window_accepts_nothing(self, case: AdapterCase) -> None:
        adapter, _clock = case.connected()

        assert adapter.is_heartbeat_fresh(-TICK) is False

    def test_two_callers_may_hold_different_windows(self, case: AdapterCase) -> None:
        # The threshold is not remembered anywhere. An adapter that held one
        # would be answering a question about the strategy above it.
        adapter, clock = case.connected()

        clock.advance(timedelta(minutes=30))

        assert adapter.is_heartbeat_fresh(timedelta(hours=1)) is True
        assert adapter.is_heartbeat_fresh(timedelta(minutes=10)) is False


class TestAWallClockCorrectionIsNotTimePassing:
    def test_jumping_the_clock_forwards_does_not_age_the_heartbeat(self, case: AdapterCase) -> None:
        # The reason the age is measured from the monotonic hand. An NTP step
        # or a zone change moving the wall clock a day ahead would otherwise
        # report a live session as a day silent.
        adapter, clock = case.connected()

        clock.set_time(START + timedelta(days=1))

        assert adapter.heartbeat_age() == timedelta(0)
        assert adapter.is_heartbeat_fresh(WINDOW) is True

    def test_jumping_the_clock_backwards_does_not_rejuvenate_a_stale_heartbeat(
        self, case: AdapterCase
    ) -> None:
        # The dangerous direction: a wall-clock subtraction would go negative
        # here and report a dead session as freshly heard from.
        adapter, clock = case.connected()
        clock.advance(WINDOW * 2)

        clock.set_time(START - timedelta(days=1))

        assert adapter.heartbeat_age() == WINDOW * 2
        assert adapter.is_heartbeat_fresh(WINDOW) is False

    def test_time_still_passes_normally_after_a_correction(self, case: AdapterCase) -> None:
        adapter, clock = case.connected()
        clock.set_time(START + timedelta(days=1))

        clock.advance(timedelta(minutes=30))

        assert adapter.heartbeat_age() == timedelta(minutes=30)


class TestTheLifecycleClearsAndRestoresIt:
    def test_disconnecting_leaves_no_age_to_report(self, case: AdapterCase) -> None:
        adapter, _clock = case.connected()

        adapter.disconnect()

        assert adapter.heartbeat_age() is None

    def test_a_disconnected_adapter_is_not_fresh(self, case: AdapterCase) -> None:
        adapter, _clock = case.connected()

        adapter.disconnect()

        assert adapter.is_heartbeat_fresh(WINDOW) is False

    def test_a_disconnect_does_not_report_the_old_session_as_silent(
        self, case: AdapterCase
    ) -> None:
        # `None` rather than a growing age. The readings describe a session that
        # no longer exists, and an age computed against it would be a
        # measurement of nothing presented as a measurement of something.
        adapter, clock = case.connected()
        adapter.disconnect()

        clock.advance(WINDOW * 2)

        assert adapter.heartbeat_age() is None

    def test_reconnecting_starts_the_measurement_again(self, case: AdapterCase) -> None:
        adapter, clock = case.connected()
        clock.advance(WINDOW * 2)

        adapter.reconnect()

        assert adapter.heartbeat_age() == timedelta(0)
        assert adapter.is_heartbeat_fresh(WINDOW) is True


class TestTheLocksAreStillWhatADR0007Says:
    def test_the_clock_is_read_before_the_readings_lock_is_taken(
        self, case: AdapterCase, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        # The readings lock is a leaf, and a leaf stops being one the moment
        # anything is called while it is held. The clock is supplied from
        # outside the package, so calling one under the lock would put an
        # unknown amount of foreign code inside a critical section ADR-0007
        # proves has no cycle.
        adapter, clock = case.connected()
        free: list[bool] = []
        original = clock.monotonic

        def spy() -> float:
            free.append(_free_for_another_thread(adapter._readings_lock))
            return original()

        monkeypatch.setattr(clock, "monotonic", spy)

        assert adapter.heartbeat_age() == timedelta(0)
        assert free == [True]

    def test_the_freedom_probe_would_notice_the_readings_lock_held(self, case: AdapterCase) -> None:
        adapter, _clock = case.connected()

        assert _free_for_another_thread(adapter._readings_lock) is True
        with adapter._readings_lock:
            assert _free_for_another_thread(adapter._readings_lock) is False

    def test_the_clock_is_read_before_the_readings_lock_when_recording_too(
        self, case: AdapterCase, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        adapter, clock = case.connected()
        free: list[bool] = []
        original = clock.monotonic

        def spy() -> float:
            free.append(_free_for_another_thread(adapter._readings_lock))
            return original()

        monkeypatch.setattr(clock, "monotonic", spy)

        assert adapter.ping() is True
        assert free == [True]

    def test_the_age_answers_while_the_session_lock_is_held(self, case: AdapterCase) -> None:
        # Supervision is never blocked, which is the one guarantee that makes
        # these methods worth having: a supervisor asks how long the venue has
        # been silent precisely when a lifecycle call is stuck inside it.
        adapter, _clock = case.connected()
        holding = threading.Event()
        release = threading.Event()

        def hold() -> None:
            with adapter._session_lock:
                holding.set()
                release.wait(WATCHDOG)

        worker = threading.Thread(target=hold, daemon=True)
        worker.start()
        try:
            assert holding.wait(WATCHDOG)
            assert _free_for_another_thread(adapter._session_lock) is False

            assert adapter.heartbeat_age() == timedelta(0)
            assert adapter.is_heartbeat_fresh(WINDOW) is True
        finally:
            release.set()
            worker.join(WATCHDOG)


class TestNothingThatUsedToWorkStoppedWorking:
    def test_the_snapshot_still_stamps_the_instant_the_venue_was_heard(
        self, case: AdapterCase
    ) -> None:
        adapter, _clock = case.connected()

        assert adapter.health().last_heartbeat == START

    def test_the_snapshot_still_follows_the_clock_forwards(self, case: AdapterCase) -> None:
        adapter, clock = case.connected()
        later = clock.advance(timedelta(minutes=5))

        assert adapter.ping() is True

        assert adapter.health().last_heartbeat == later

    def test_measuring_latency_still_stamps_a_heartbeat_with_it(self, case: AdapterCase) -> None:
        adapter, clock = case.connected()
        later = clock.advance(timedelta(minutes=5))

        measured = adapter.latency()

        snapshot = adapter.health()
        assert snapshot.latency_ms == measured
        assert snapshot.last_heartbeat == later

    def test_a_disconnect_still_clears_the_snapshot_readings(self, case: AdapterCase) -> None:
        adapter, _clock = case.connected()
        adapter.latency()

        adapter.disconnect()

        snapshot = adapter.health()
        assert snapshot.latency_ms is None
        assert snapshot.last_heartbeat is None

    def test_asking_for_the_age_changes_no_reading(self, case: AdapterCase) -> None:
        adapter, _clock = case.connected()
        adapter.latency()
        before = adapter.health()

        adapter.heartbeat_age()
        adapter.is_heartbeat_fresh(WINDOW)

        assert adapter.health() == before


class TestHowAnAdapterGetsItsClock:
    def test_a_subclass_that_passes_no_clock_gets_the_host_one(self) -> None:
        # The parameter is keyword-only with a default, so every existing
        # `super().__init__()` keeps working and keeps meaning what it meant.
        assert isinstance(_bare()._clock, SystemClock)

    def test_a_subclass_that_passes_no_clock_can_still_report_an_age(self) -> None:
        # The default is a real clock, not a placeholder that raises the first
        # time somebody asks it the time.
        adapter = _bare()
        adapter._record_heartbeat(START)

        age = adapter.heartbeat_age()

        assert age is not None
        assert age >= timedelta(0)

    def test_the_default_clock_satisfies_the_port(self) -> None:
        assert isinstance(_bare()._clock, Clock)

    def test_the_mt5_adapter_takes_the_host_clock_unless_told_otherwise(self) -> None:
        # Production time, through the default implementation: this adapter
        # talks to a real venue, and the instant it stamps is the instant Atlas
        # observed one.
        config = MT5Config(
            login=9001234,
            password=SecretStr("not-a-real-password"),
            server="Example-Demo",
            terminal_path=Path("C:/Program Files/Example/terminal64.exe"),
            server_utc_offset=SERVER_OFFSET,
            deviation_points=20,
            filling_mode_by_instrument={},
        )

        adapter = MT5BrokerAdapter(config)

        assert isinstance(adapter._clock, SystemClock)

    def test_the_mt5_adapter_uses_the_clock_it_is_given(self) -> None:
        adapter, clock = _mt5()

        assert adapter._clock is clock

    def test_the_mock_adapter_runs_on_its_venues_clock(self) -> None:
        # Not a copy and not a second clock: the same object. A mock stamping
        # heartbeats in venue time and ageing them against anything else would
        # produce an age that depends on how long the test took to run.
        venue = MockVenue(now=START)

        adapter = MockBrokerAdapter(venue)

        assert adapter._clock is venue.clock

    def test_a_mock_adapter_built_without_a_venue_still_gets_a_manual_clock(self) -> None:
        adapter = MockBrokerAdapter()

        assert adapter._clock is adapter.venue.clock
        assert isinstance(adapter._clock, ManualClock)

    def test_two_adapters_on_one_venue_share_its_clock(self) -> None:
        venue = MockVenue(now=START)

        first = MockBrokerAdapter(venue)
        second = MockBrokerAdapter(venue)

        assert first._clock is second._clock

    def test_two_adapters_on_two_venues_do_not(self) -> None:
        assert MockBrokerAdapter()._clock is not MockBrokerAdapter()._clock


class TestTheVenueClockStillBehavesAsItsOwnSuiteExpects:
    def test_it_starts_where_it_is_told(self) -> None:
        assert MockVenue(now=START).now() == START

    def test_advancing_it_returns_the_new_time(self) -> None:
        venue = MockVenue(now=START)

        assert venue.advance(timedelta(hours=2)) == START + timedelta(hours=2)

    def test_it_refuses_to_run_backwards(self) -> None:
        venue = MockVenue(now=START)

        with pytest.raises(ValueError, match="must not be negative"):
            venue.advance(-TICK)

    def test_setting_it_moves_it(self) -> None:
        venue = MockVenue(now=START)

        venue.set_time(START + timedelta(days=3))

        assert venue.now() == START + timedelta(days=3)

    def test_it_refuses_a_naive_instant(self) -> None:
        venue = MockVenue(now=START)

        with pytest.raises(ValueError, match="timezone aware"):
            venue.set_time(datetime(2020, 1, 2))  # noqa: DTZ001 — the point of the test

    def test_it_refuses_a_naive_start(self) -> None:
        with pytest.raises(ValueError, match="timezone aware"):
            MockVenue(now=datetime(2020, 1, 1))  # noqa: DTZ001 — the point of the test
