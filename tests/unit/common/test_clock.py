"""Unit tests for the clock port and its two implementations.

The class under test here is mostly :class:`~atlas.common.clock.ManualClock`,
and the reason is that it is the one everything else's determinism rests on. A
test of a timeout, a freshness window or a retry schedule is only as exact as
the clock it advances, so a manual clock that quietly credited the wrong number
of seconds — or moved its monotonic hand when a wall-clock correction should
have left it alone — would make a whole tier of tests agree with a bug.

:class:`~atlas.common.clock.SystemClock` is tested for the properties that can
be asserted without waiting: that its instants are aware and in UTC, that its
monotonic readings do not go backwards, and that the two hands are genuinely
different sources. Nothing here sleeps.
"""

from __future__ import annotations

import sys
import time
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime, timedelta, timezone
from typing import TYPE_CHECKING, Final, Protocol

import pytest

from atlas.common import Clock, ManualClock, SystemClock

if TYPE_CHECKING:
    from collections.abc import Iterator

pytestmark = pytest.mark.unit

#: The instant every manual clock in this module starts at.
START: Final = datetime(2020, 1, 1, tzinfo=UTC)

#: A fixed offset far from UTC, used to prove an aware instant is normalised
#: rather than merely accepted.
TOKYO: Final = timezone(timedelta(hours=9))

#: Threads and repetitions for the concurrency tests. Small, because the
#: contention comes from the switch interval below rather than from volume; the
#: probes at the bottom of this module are what establish that these numbers are
#: enough to lose an unguarded update.
THREADS: Final = 8
ADVANCES: Final = 50

#: How many times a race is run before a conclusion is drawn from it. A race is
#: sampled rather than decided, and the switch interval below raises the odds of
#: an interleave without making one certain: measured over three hundred rounds
#: on CPython 3.12, one round finds a torn read 88% of the time and loses an
#: unguarded update 99% of the time. Asking once and demanding success is
#: therefore a test that fails about one run in nine, which is what it did. The
#: rounds are independent, so thirty-two of them hold even on a host where a
#: single round would succeed only half the time. The probes stop at the first
#: success, so the usual cost is one round; the guarded assertions run all
#: thirty-two, which is thirty-two chances to catch a tear that must never
#: appear rather than one.
RACE_ROUNDS: Final = 32

#: One second, the unit every advance in this module is measured in. An integer
#: number of seconds so that a total is exact in floating point and the
#: assertions can use ``==`` rather than a tolerance.
SECOND: Final = timedelta(seconds=1)

#: How long a thread may hold the interpreter before it is asked to yield, while
#: a concurrency test runs. The default is five milliseconds, which is several
#: thousand of the increments below — long enough that eight threads take turns
#: instead of interleaving, and a test of an unguarded read-modify-write passes
#: because the race never happens. Nothing sleeps and no result depends on how
#: long anything takes; this changes only how often the interpreter switches.
CONTENDED_SWITCH_INTERVAL: Final = 1e-5

#: A reading no clock would ever produce, used to prove which function a value
#: came out of rather than merely that it was a plausible number.
SENTINEL: Final = -12345.5

#: A duration for the wait tests. Never actually waited — the system clock's
#: sleep is intercepted and the manual clock's returns instantly — so the value
#: only has to be recognisable and not round.
PAUSE: Final = 2.5

#: Twenty years in seconds. A wall-clock timestamp is measured from 1970 and a
#: monotonic reading from the host's last boot, so the gap between them is
#: decades; this is the margin by which they must differ before the two hands
#: can be called separate sources. Breaking it would need a host that had been
#: up since the mid-2000s.
EPOCH_GAP: Final = 20 * 365 * 24 * 60 * 60.0


@pytest.fixture
def contended() -> Iterator[None]:
    """Run a test under heavy thread-switching pressure.

    Yields:
        Nothing. The switch interval is restored afterwards, including on
        failure, so no other test inherits it.
    """
    original = sys.getswitchinterval()
    sys.setswitchinterval(CONTENDED_SWITCH_INTERVAL)
    try:
        yield
    finally:
        sys.setswitchinterval(original)


class _MovableClock(Protocol):
    """What the workloads below need: a clock that can be moved forwards."""

    def now(self) -> datetime: ...

    def monotonic(self) -> float: ...

    def advance(self, delta: timedelta) -> datetime: ...


class _Unguarded:
    """:class:`~atlas.common.clock.ManualClock` with the lock left out.

    The control for the concurrency tests. It exists to be raced and to lose,
    which is what proves the assertions against the real clock are capable of
    failing rather than merely true.
    """

    def __init__(self) -> None:
        self._instant = START
        self._elapsed = 0.0

    def now(self) -> datetime:
        return self._instant

    def monotonic(self) -> float:
        return self._elapsed

    def advance(self, delta: timedelta) -> datetime:
        self._instant += delta
        self._elapsed += delta.total_seconds()
        return self._instant


def _advance_from_many_threads(clock: _MovableClock) -> None:
    """Advance a clock by one second, ``ADVANCES`` times, on ``THREADS`` threads."""

    def push(_index: int) -> None:
        for _ in range(ADVANCES):
            clock.advance(SECOND)

    with ThreadPoolExecutor(max_workers=THREADS) as pool:
        list(pool.map(push, range(THREADS)))


def _torn_readings(clock: _MovableClock) -> list[tuple[datetime, float]]:
    """Read a clock on one thread while another advances it.

    Args:
        clock: The clock to race.

    Returns:
        Every reading in which the instant had moved further than the elapsed
        count — which only a half-completed advance can produce.
    """
    torn: list[tuple[datetime, float]] = []
    total = THREADS * ADVANCES

    def read() -> None:
        for _ in range(total):
            instant = clock.now()
            elapsed = clock.monotonic()
            if instant - START > timedelta(seconds=elapsed):
                torn.append((instant, elapsed))

    def write() -> None:
        for _ in range(total):
            clock.advance(SECOND)

    with ThreadPoolExecutor(max_workers=2) as pool:
        reader = pool.submit(read)
        writer = pool.submit(write)
        reader.result()
        writer.result()

    return torn


class TestTheProtocol:
    def test_the_system_clock_satisfies_it(self) -> None:
        assert isinstance(SystemClock(), Clock)

    def test_the_manual_clock_satisfies_it(self) -> None:
        assert isinstance(ManualClock(START), Clock)

    def test_something_with_only_one_hand_does_not(self) -> None:
        # The control. A protocol both implementations satisfy proves nothing
        # unless something fails it, and half a clock is the failure that
        # matters: a type offering `now` alone is exactly what this port exists
        # to stop being passed where a duration will be measured.
        class WallOnly:
            def now(self) -> datetime:
                return START

        assert not isinstance(WallOnly(), Clock)

    def test_something_that_cannot_wait_does_not(self) -> None:
        # The second control, and the one ATLAS-TASK-0010 added the method for.
        # A type with both readings and no way to wait is what the port looked
        # like before, so this is the assertion that would still pass if `sleep`
        # were quietly dropped from the protocol again.
        class ReadingsOnly:
            def now(self) -> datetime:
                return START

            def monotonic(self) -> float:
                return 0.0

        assert not isinstance(ReadingsOnly(), Clock)


class TestTheSystemClock:
    def test_its_instants_are_timezone_aware(self) -> None:
        assert SystemClock().now().tzinfo is not None

    def test_its_instants_are_in_utc(self) -> None:
        assert SystemClock().now().utcoffset() == timedelta(0)

    def test_its_monotonic_reading_is_a_number_of_seconds(self) -> None:
        assert isinstance(SystemClock().monotonic(), float)

    def test_its_monotonic_reading_never_goes_backwards(self) -> None:
        clock = SystemClock()

        readings = [clock.monotonic() for _ in range(100)]

        assert readings == sorted(readings)

    def test_its_instants_never_go_backwards(self) -> None:
        clock = SystemClock()

        readings = [clock.now() for _ in range(100)]

        assert readings == sorted(readings)

    def test_its_monotonic_hand_carries_the_standard_library_guarantee(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        # The host's wall clock cannot be stepped from inside a test, so the
        # property that actually matters here — that a clock correction does not
        # move this reading — is not directly observable. What is observable is
        # where the reading comes from: `time.monotonic`, which the standard
        # library documents as unaffected by a system clock update. That is the
        # guarantee, and this is the assertion that Atlas is relying on it.
        monkeypatch.setattr(time, "monotonic", lambda: SENTINEL)

        assert SystemClock().monotonic() == SENTINEL

    def test_its_two_hands_are_genuinely_different_sources(self) -> None:
        # An implementation returning a wall-clock timestamp for both would
        # satisfy every other assertion in this class: it is a float, it does
        # not go backwards within a run, and it looks like seconds. It differs
        # only in origin, so origin is what is measured.
        clock = SystemClock()

        assert abs(clock.now().timestamp() - clock.monotonic()) > EPOCH_GAP

    def test_two_instances_read_the_same_host(self) -> None:
        # Stateless, so one instance is as good as another and nothing is
        # gained by threading a single one through the system.
        first = SystemClock().now()
        second = SystemClock().now()

        assert second - first < timedelta(seconds=1)


class TestTheSystemClockWaits:
    def test_it_waits_by_calling_the_standard_library(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        # Nothing in this suite may block, so the wait is intercepted rather
        # than performed. What is asserted is the only thing worth asserting
        # about this method: that the duration reaches `time.sleep` unchanged.
        waited: list[float] = []
        monkeypatch.setattr(time, "sleep", waited.append)

        SystemClock().sleep(PAUSE)

        assert waited == [PAUSE]

    def test_a_zero_wait_still_reaches_it(self, monkeypatch: pytest.MonkeyPatch) -> None:
        # An immediate-retry policy asks for zero, and the caller does not
        # branch around it. Short-circuiting here would be a plausible
        # optimisation that silently changed thread-yielding behaviour.
        waited: list[float] = []
        monkeypatch.setattr(time, "sleep", waited.append)

        SystemClock().sleep(0.0)

        assert waited == [0.0]

    def test_it_refuses_a_negative_wait(self, monkeypatch: pytest.MonkeyPatch) -> None:
        waited: list[float] = []
        monkeypatch.setattr(time, "sleep", waited.append)

        with pytest.raises(ValueError, match="seconds must not be negative"):
            SystemClock().sleep(-PAUSE)

        assert waited == []


class TestTheManualClockStartsWhereItIsTold:
    def test_it_reports_the_instant_it_was_built_with(self) -> None:
        assert ManualClock(START).now() == START

    def test_it_normalises_an_aware_instant_to_utc(self) -> None:
        tokyo_noon = datetime(2020, 1, 1, 12, tzinfo=TOKYO)

        moment = ManualClock(tokyo_noon).now()

        assert moment == tokyo_noon
        assert moment.utcoffset() == timedelta(0)

    def test_it_refuses_a_naive_instant(self) -> None:
        with pytest.raises(ValueError, match="timezone aware"):
            ManualClock(datetime(2020, 1, 1))  # noqa: DTZ001 — the point of the test

    def test_its_monotonic_reading_starts_at_zero(self) -> None:
        assert ManualClock(START).monotonic() == 0.0

    def test_it_does_not_move_on_its_own(self) -> None:
        # The whole reason the class exists: reading it twice is not the
        # passage of time. A test that asserts an age of exactly one hour is
        # only exact because of this.
        clock = ManualClock(START)

        assert [clock.now() for _ in range(100)] == [START] * 100
        assert [clock.monotonic() for _ in range(100)] == [0.0] * 100


class TestAdvancingTheManualClock:
    def test_it_moves_the_instant_by_the_delta(self) -> None:
        clock = ManualClock(START)

        clock.advance(timedelta(hours=1))

        assert clock.now() == START + timedelta(hours=1)

    def test_it_moves_the_monotonic_reading_by_the_same_amount(self) -> None:
        clock = ManualClock(START)

        clock.advance(timedelta(hours=1))

        assert clock.monotonic() == timedelta(hours=1).total_seconds()

    def test_it_returns_the_new_instant(self) -> None:
        clock = ManualClock(START)

        assert clock.advance(timedelta(minutes=5)) == START + timedelta(minutes=5)

    def test_repeated_advances_accumulate(self) -> None:
        clock = ManualClock(START)

        for _ in range(10):
            clock.advance(timedelta(seconds=1))

        assert clock.now() == START + timedelta(seconds=10)
        assert clock.monotonic() == 10.0

    def test_a_zero_advance_moves_nothing(self) -> None:
        clock = ManualClock(START)

        clock.advance(timedelta(0))

        assert clock.now() == START
        assert clock.monotonic() == 0.0

    def test_it_refuses_a_negative_delta(self) -> None:
        clock = ManualClock(START)

        with pytest.raises(ValueError, match="must not be negative"):
            clock.advance(timedelta(seconds=-1))

    def test_a_refused_advance_leaves_both_hands_alone(self) -> None:
        clock = ManualClock(START)

        with pytest.raises(ValueError, match="must not be negative"):
            clock.advance(timedelta(seconds=-1))

        assert clock.now() == START
        assert clock.monotonic() == 0.0

    def test_a_year_of_advancing_costs_nothing_to_run(self) -> None:
        # Deterministic advancement is the feature. Moving a year forwards is
        # the same amount of work as moving a second, which is what makes a
        # test for a long timeout worth writing at all.
        clock = ManualClock(START)

        clock.advance(timedelta(days=365))

        assert clock.now() == datetime(2020, 12, 31, tzinfo=UTC)


class TestCorrectingTheManualClock:
    def test_set_time_moves_the_instant(self) -> None:
        clock = ManualClock(START)

        clock.set_time(START + timedelta(days=1))

        assert clock.now() == START + timedelta(days=1)

    def test_set_time_may_move_the_instant_backwards(self) -> None:
        clock = ManualClock(START)

        clock.set_time(START - timedelta(days=1))

        assert clock.now() == START - timedelta(days=1)

    def test_a_forward_correction_credits_no_elapsed_time(self) -> None:
        # The distinction the class is built around. A wall clock jumping an
        # hour ahead is not an hour passing, and anything measuring a duration
        # across it must see nothing happen.
        clock = ManualClock(START)

        clock.set_time(START + timedelta(hours=1))

        assert clock.monotonic() == 0.0

    def test_a_backward_correction_credits_no_elapsed_time(self) -> None:
        clock = ManualClock(START)
        clock.advance(timedelta(hours=1))

        clock.set_time(START - timedelta(days=1))

        assert clock.monotonic() == timedelta(hours=1).total_seconds()

    def test_time_still_passes_normally_after_a_correction(self) -> None:
        clock = ManualClock(START)
        clock.set_time(START + timedelta(days=1))

        clock.advance(timedelta(minutes=1))

        assert clock.now() == START + timedelta(days=1, minutes=1)
        assert clock.monotonic() == 60.0

    def test_it_normalises_an_aware_instant_to_utc(self) -> None:
        clock = ManualClock(START)
        tokyo_noon = datetime(2020, 6, 1, 12, tzinfo=TOKYO)

        clock.set_time(tokyo_noon)

        assert clock.now() == tokyo_noon
        assert clock.now().utcoffset() == timedelta(0)

    def test_it_refuses_a_naive_instant(self) -> None:
        clock = ManualClock(START)

        with pytest.raises(ValueError, match="timezone aware"):
            clock.set_time(datetime(2020, 1, 1))  # noqa: DTZ001 — the point of the test

    def test_a_refused_correction_leaves_the_instant_alone(self) -> None:
        clock = ManualClock(START)

        with pytest.raises(ValueError, match="timezone aware"):
            clock.set_time(datetime(2020, 1, 1))  # noqa: DTZ001 — the point of the test

        assert clock.now() == START


class TestSleepingOnTheManualClock:
    """That a wait is credited as time passing, and takes none.

    The whole value of this method is that it is :meth:`advance` under another
    name. Code that backs off for a minute and then stamps a heartbeat has to
    produce the instants it would produce in production; a sleep that returned
    without moving the clock would let a caller wait and then measure nothing.
    """

    def test_it_returns_without_waiting(self) -> None:
        # A real wait of a day would end this suite. The assertion is on the
        # host's clock precisely because nothing else can tell the difference
        # between an instant return and a correct one.
        clock = ManualClock(START)
        before = time.monotonic()

        clock.sleep(timedelta(days=1).total_seconds())

        assert time.monotonic() - before < 1.0

    def test_it_moves_the_instant_forwards(self) -> None:
        clock = ManualClock(START)

        clock.sleep(PAUSE)

        assert clock.now() == START + timedelta(seconds=PAUSE)

    def test_it_credits_the_elapsed_time(self) -> None:
        # The half a `set_time` deliberately does not do. A backoff is time
        # passing, so a heartbeat aged across one must be that much older.
        clock = ManualClock(START)

        clock.sleep(PAUSE)

        assert clock.monotonic() == PAUSE

    def test_successive_waits_accumulate(self) -> None:
        clock = ManualClock(START)

        clock.sleep(1.0)
        clock.sleep(2.0)
        clock.sleep(4.0)

        assert clock.now() == START + timedelta(seconds=7)
        assert clock.monotonic() == 7.0

    def test_a_zero_wait_moves_nothing(self) -> None:
        clock = ManualClock(START)

        clock.sleep(0.0)

        assert clock.now() == START
        assert clock.monotonic() == 0.0

    def test_it_refuses_a_negative_wait(self) -> None:
        clock = ManualClock(START)

        with pytest.raises(ValueError, match="seconds must not be negative"):
            clock.sleep(-PAUSE)

    def test_a_refused_wait_moves_nothing(self) -> None:
        # Guarded before the delegation rather than after it, so a rejected
        # duration cannot have already moved one hand.
        clock = ManualClock(START)

        with pytest.raises(ValueError, match="seconds must not be negative"):
            clock.sleep(-PAUSE)

        assert clock.now() == START
        assert clock.monotonic() == 0.0

    def test_it_names_seconds_rather_than_the_delta_it_delegates_to(self) -> None:
        # `advance` refuses a negative `delta`, so the check could have been
        # left to it. The message a caller then gets names a parameter it never
        # passed and a `timedelta` it never built.
        clock = ManualClock(START)

        with pytest.raises(ValueError, match=r"got -2\.5"):
            clock.sleep(-PAUSE)

    def test_waiting_and_advancing_are_the_same_movement(self) -> None:
        # Stated as an equality between two clocks rather than as two separate
        # assertions, so that the two ways of moving time cannot drift apart
        # without this failing.
        slept = ManualClock(START)
        advanced = ManualClock(START)

        slept.sleep(PAUSE)
        advanced.advance(timedelta(seconds=PAUSE))

        assert (slept.now(), slept.monotonic()) == (advanced.now(), advanced.monotonic())


@pytest.mark.usefixtures("contended")
class TestTheManualClockUnderThreads:
    """That the two hands move under one acquisition, and that saying so counts.

    Both assertions here are about a race, and a race that does not happen
    proves nothing. Removing the lock from ``advance`` and running these at the
    interpreter's default switch interval leaves them passing — 400 unguarded
    increments across eight threads simply never interleave. That is the shape
    of test ATLAS-TASK-0008 went looking for and found: green because nothing
    was exercised.

    So three things are done about it. The ``contended`` fixture shortens the
    switch interval, which makes the interleaving common rather than rare
    without anything sleeping or any result depending on elapsed time.
    :class:`_Unguarded` — the same two writes with the lock left out — is run
    through the identical workload, so the power of each assertion is *asserted*
    rather than assumed. And every race here is run ``RACE_ROUNDS`` times,
    because common is not the same as certain: a shortened switch interval
    raises the odds of an interleave, and a probe that asks once is a test that
    fails whenever the odds do not land.

    The repetition applies to the guarded assertions too, and not only for
    symmetry. If a tear takes several rounds to provoke, then one clean round
    against the real clock is evidence that a tear is rare, which is not the
    claim; the same rounds on both sides are what make it evidence about the
    lock.
    """

    def test_concurrent_advances_are_all_credited(self) -> None:
        for _ in range(RACE_ROUNDS):
            clock = ManualClock(START)

            _advance_from_many_threads(clock)

            assert clock.monotonic() == float(THREADS * ADVANCES)
            assert clock.now() == START + timedelta(seconds=THREADS * ADVANCES)

    def test_the_lost_update_probe_can_actually_fire(self) -> None:
        # `self._elapsed += n` is a read, an add and a store, and the store can
        # land on a value another thread has already replaced. This is that
        # happening, so the test above is known to be capable of failing. The
        # smallest total across the rounds is the one that lost the most, and
        # taking the minimum reports it rather than merely that one existed.
        def elapsed_after_a_race() -> float:
            unguarded = _Unguarded()
            _advance_from_many_threads(unguarded)
            return unguarded.monotonic()

        assert min(elapsed_after_a_race() for _ in range(RACE_ROUNDS)) < float(THREADS * ADVANCES)

    def test_a_reader_never_sees_the_two_hands_disagree(self) -> None:
        # The instant is read before the elapsed count on purpose, which makes
        # the two outcomes distinguishable: a benign interleave — the writer
        # advancing between the two reads — can only leave the *elapsed* count
        # ahead, whereas a torn write is the only thing that can leave the
        # *instant* ahead. So this flags tearing and nothing else.
        torn = [
            readings for _ in range(RACE_ROUNDS) if (readings := _torn_readings(ManualClock(START)))
        ]

        assert torn == []

    def test_the_tear_probe_can_actually_fire(self) -> None:
        # Stops at the first round that tears, so this costs one race unless the
        # scheduler is being unhelpful, and reports the readings it caught
        # rather than only that it caught some.
        found = next(
            (torn for _ in range(RACE_ROUNDS) if (torn := _torn_readings(_Unguarded()))),
            [],
        )

        assert found != []
