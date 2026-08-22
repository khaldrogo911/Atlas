"""Retrying a lifecycle call, on every adapter, without a second of real time passing.

ATLAS-TASK-0010 gives :class:`~atlas.broker.base.BaseBrokerAdapter` a
:class:`~atlas.common.retry.RetryPolicy`. The policy's own arithmetic is settled
in ``tests/unit/common/test_retry.py``; what is settled here is everything that
only becomes true once an adapter is holding one — that both adapters inherit it
without implementing anything, that the schedule an operator configures is the
schedule the venue actually sees, that a permanent failure is still permanent,
and that none of the guarantees ATLAS-TASK-0008 and ATLAS-TASK-0009 established
were traded away to get it.

Every claim is made against both real adapters, discovered rather than named, in
the way ``test_base_adapter.py`` established. :data:`CASES` says how to build
each one, and :class:`Rig` is the small vocabulary the tests share: *when did the
venue get called*, *make the next call fail transiently*, *make it refuse
outright*. The two adapters answer those questions through completely different
machinery — a scheduled failure queue on the mock venue, an ``initialize`` that
returns ``False`` on the MetaTrader 5 terminal — which is the point. A retry
count asserted through one implementation's private state would be a test of the
implementation.

Nothing here sleeps. The backoff runs on a
:class:`~atlas.common.clock.ManualClock`, so a seven-second exponential schedule
is asserted as the exact instants ``0, 1, 3, 7`` and costs nothing to run. A
tolerance anywhere below would be the tell that a real clock had got in.

Three things are asserted that are about what retrying must *not* have broken:

Attempts do not multiply
    Both adapters compose ``reconnect`` out of the public ``disconnect`` and
    ``connect``, so a policy applied naively at every entry point would give a
    three-attempt reconnect nine round trips. The base class suppresses the
    inner policy, and :class:`TestAttemptsDoNotMultiply` counts.

The lock order is the one ADR-0007 fixed
    Waiting happens inside the session lock, deliberately, so that a reconnect
    stays one critical section rather than several. That costs something, and
    the cost is bounded by the other half of the claim: supervision never takes
    the session lock, so :meth:`~atlas.broker.base.BaseBrokerAdapter.health`,
    :meth:`~atlas.broker.base.BaseBrokerAdapter.is_connected` and
    :meth:`~atlas.broker.base.BaseBrokerAdapter.heartbeat_age` still answer from
    another thread in the middle of a backoff. Both halves are asserted, because
    either alone would be satisfied by an adapter that locked nothing.

The default is one attempt
    Nothing retries unless it was told to, so every existing behaviour is
    reachable by not passing a policy — which is what makes the regression class
    at the bottom of this module possible to write at all.
"""

from __future__ import annotations

import inspect
import itertools
import threading
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import TYPE_CHECKING, Any, Final, cast

import pytest
from pydantic import SecretStr

from atlas.broker import base as base_module
from atlas.broker.base import PERMANENT_ERRORS, RETRYABLE_ERRORS, BaseBrokerAdapter
from atlas.broker.exceptions import (
    BrokerAuthenticationError,
    BrokerConnectionError,
    BrokerNotConnectedError,
)
from atlas.broker.mock import MockBrokerAdapter, MockVenue
from atlas.broker.mock.venue import VENUE
from atlas.broker.models import ConnectionState
from atlas.broker.mt5.adapter import MT5BrokerAdapter
from atlas.broker.mt5.connection import MT5Config, MT5Session
from atlas.broker.mt5.constants import RES_E_AUTH_FAILED, RES_E_INTERNAL_FAIL_CONNECT
from atlas.common.clock import ManualClock, SystemClock
from atlas.common.retry import RetryPolicy
from tests.unit.broker.mt5.conftest import SERVER_OFFSET, FakeTerminal, as_terminal
from tests.unit.broker.test_adapter_concurrency import _traced
from tests.unit.broker.test_adapter_heartbeat import _bare, _free_for_another_thread

if TYPE_CHECKING:
    from collections.abc import Callable, Sequence

    from atlas.broker.models import Connection
    from atlas.broker.types import BrokerName, ServerName

pytestmark = pytest.mark.unit

#: Where every clock in this module starts. Attempt instants are reported as
#: seconds from here, so a schedule reads as the arithmetic it is.
START: Final = datetime(2020, 1, 1, tzinfo=UTC)

#: Long enough that a thread which is going to finish has finished, short enough
#: that a hang fails the run instead of stopping it.
WATCHDOG: Final = 5.0

#: What a transient failure says. Distinct from :data:`REFUSED` so that a test
#: matching on one cannot pass on the other.
DROPPED: Final = "the venue dropped the socket"

#: What a permanent failure says.
REFUSED: Final = "Authorization failed"

#: The two lifecycle operations a failure can be aimed at.
CONNECT: Final = "connect"
RECONNECT: Final = "reconnect"

#: More failures than any policy in this module has attempts, so a test for
#: exhaustion cannot accidentally succeed on the last one.
PLENTY: Final = 6


# --- One vocabulary, two completely different adapters ------------------------


@dataclass(frozen=True)
class Rig:
    """An adapter, plus the four things a retry test needs to ask of it.

    The two implementations record attempts and manufacture failures by
    unrelated means, so the tests are written against these callables rather
    than against either one's internals.

    Attributes:
        adapter: The subject.
        clock: The clock its backoff runs on. The same object the adapter was
            given, so an assertion about ``clock.now()`` is an assertion about
            how long the adapter thinks it waited.
        attempts: The instant of every round trip to the venue so far, in order.
        forget: Discard the recorded attempts, so a test can count only the ones
            it caused.
        fail: Queue *n* transient failures against an operation. On MetaTrader 5
            the operation is ignored — a terminal that will not initialise fails
            whichever lifecycle method reached it — and on the mock it is not,
            because the venue keeps a separate queue per operation.
        refuse: Make the operation fail permanently, with a failure that is
            deliberately outside the retryable branch of the exception tree.
    """

    adapter: BaseBrokerAdapter
    clock: ManualClock
    attempts: Callable[[], tuple[datetime, ...]]
    forget: Callable[[], None]
    fail: Callable[[str, int], None]
    refuse: Callable[[str], None]


@dataclass(frozen=True)
class AdapterCase:
    """One implementation of the port, and how to build a rig around it.

    Attributes:
        name: What to call the case in a test id.
        build: Takes the policy under test, or ``None`` to leave the adapter on
            its default. A factory rather than a fixture because the policy
            varies per test and several tests need two independent instances.
    """

    name: str
    build: Callable[[RetryPolicy | None], Rig]

    def connected(self, retry: RetryPolicy | None = None) -> Rig:
        """Build a rig and establish its session.

        Args:
            retry: The policy under test, or ``None`` for the default.

        Returns:
            The rig, connected, with the connecting round trip already
            forgotten so a following count starts at zero.
        """
        rig = self.build(retry)
        rig.adapter.connect()
        rig.forget()
        return rig


class _CountingMockAdapter(MockBrokerAdapter):
    """A mock adapter that remembers when it went to the venue.

    :meth:`~atlas.broker.mock.adapter.MockBrokerAdapter._establish` is the one
    place both lifecycle hooks reach the venue, so counting there counts
    attempts and nothing else — a ``connect`` that returns early because a
    session already exists never arrives.

    Attributes:
        establishes: The instant of each round trip, in order.
    """

    def __init__(self, venue: MockVenue, *, retry: RetryPolicy | None = None) -> None:
        """Wrap a venue, having recorded nothing.

        Args:
            venue: The venue to trade against. Supplies the clock.
            retry: The policy under test, or ``None`` for the default.
        """
        super().__init__(venue, retry=retry)
        self.establishes: list[datetime] = []

    def _establish(self, operation: str) -> Connection:
        """Record the attempt, then make it.

        Args:
            operation: Which port method is establishing the session.

        Returns:
            Whatever the real implementation returns.
        """
        self.establishes.append(self._clock.now())
        return super()._establish(operation)


class _FlakyTerminal(FakeTerminal):
    """A fake terminal that can be told to refuse a few logins and then relent.

    Attributes:
        transient: How many further ``initialize`` calls will fail with a code
            the adapter classifies as a connection error. Decremented per call.
        initialisations: The instant of each ``initialize`` call, in order.
    """

    def __init__(self, clock: ManualClock) -> None:
        """Start willing, having recorded nothing.

        Args:
            clock: Read to stamp each login attempt. The adapter's own clock, so
                the stamps and the backoff cannot disagree.
        """
        super().__init__()
        self._clock = clock
        self.transient = 0
        self.initialisations: list[datetime] = []
        self.error = (RES_E_INTERNAL_FAIL_CONNECT, DROPPED)

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
        """Record the login attempt and fail it if any failures are still owed.

        Args:
            path: Terminal executable.
            login: Account number.
            password: Account password.
            server: Trade server name.
            timeout: Milliseconds to wait.
            portable: Whether to start in portable mode.

        Returns:
            ``False`` while failures are owed, otherwise the scripted outcome.
        """
        self.initialisations.append(self._clock.now())
        started = super().initialize(
            path,
            login=login,
            password=password,
            server=server,
            timeout=timeout,
            portable=portable,
        )
        if self.transient > 0:
            self.transient -= 1
            return False
        return started


def _mock_rig(retry: RetryPolicy | None) -> Rig:
    """Build a rig around the mock adapter.

    Args:
        retry: The policy under test, or ``None`` for the default.

    Returns:
        The rig. Failures are scheduled on the venue, which is how every other
        mock test provokes one, so nothing here is a special path.
    """
    venue = MockVenue(now=START)
    adapter = _CountingMockAdapter(venue, retry=retry)

    def fail(operation: str, count: int) -> None:
        for _ in range(count):
            venue.schedule_failure(operation, BrokerConnectionError(DROPPED, venue=VENUE))

    def refuse(operation: str) -> None:
        venue.schedule_failure(operation, BrokerAuthenticationError(REFUSED, venue=VENUE))

    return Rig(
        adapter=adapter,
        clock=venue.clock,
        attempts=lambda: tuple(adapter.establishes),
        forget=adapter.establishes.clear,
        fail=fail,
        refuse=refuse,
    )


def _mt5_rig(retry: RetryPolicy | None) -> Rig:
    """Build a rig around the MetaTrader 5 adapter.

    Args:
        retry: The policy under test, or ``None`` for the default.

    Returns:
        The rig, wired to the fake terminal the MT5 tests use. Nothing here
        imports the vendor package or starts a terminal, and the failures are
        vendor error codes rather than exceptions — so the classification the
        session does on the way out is part of what is under test.
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
    terminal = _FlakyTerminal(clock)
    session = MT5Session(config, terminal_factory=lambda: as_terminal(terminal))
    adapter = MT5BrokerAdapter(config, session=session, clock=clock, retry=retry)

    def fail(_operation: str, count: int) -> None:
        terminal.transient += count

    def refuse(_operation: str) -> None:
        terminal.initialize_result = False
        terminal.error = (RES_E_AUTH_FAILED, REFUSED)

    return Rig(
        adapter=adapter,
        clock=clock,
        attempts=lambda: tuple(terminal.initialisations),
        forget=terminal.initialisations.clear,
        fail=fail,
        refuse=refuse,
    )


CASES: Final = (AdapterCase("mock", _mock_rig), AdapterCase("mt5", _mt5_rig))


@pytest.fixture(params=CASES, ids=lambda case: case.name)
def case(request: pytest.FixtureRequest) -> AdapterCase:
    """Yield each adapter in turn.

    Args:
        request: Supplies the parametrised case.

    Returns:
        The case under test.
    """
    return cast("AdapterCase", request.param)


# --- A probe for the claims that are about the base class itself --------------


class _Probe(BaseBrokerAdapter):
    """A base subclass that fails to a script, with no venue behind it.

    Some of what ATLAS-TASK-0010 promises is a property of the base class rather
    than of either adapter — that a
    :class:`~atlas.broker.exceptions.BrokerNotConnectedError` is carved out of
    the retryable branch, that ``disconnect`` is never wrapped, that the
    re-entrancy guard is cleared on both exits. None of those can be provoked
    through a real adapter, because a real adapter has no way to raise them on
    demand. They are provoked here instead, against the code that makes them.

    Attributes:
        clock: The manual clock the backoff runs on.
        failures: Raised one per connect attempt, in order, until empty.
        attempts: The instant of each connect attempt.
        disconnects: How many times the disconnect hook ran.
        refuse_disconnect: Raised by the disconnect hook when set. Nothing in
            Atlas does this — the port forbids it — but the base class must not
            be *retrying* the hook, and the only way to see that is to make it
            raise.
        state: The lifecycle state the base reads back.
    """

    def __init__(
        self,
        failures: Sequence[BaseException],
        *,
        retry: RetryPolicy | None = None,
    ) -> None:
        """Start disconnected, with a queue of failures to raise.

        Args:
            failures: Raised one per connect attempt, in order. An empty queue
                means the attempt succeeds.
            retry: The policy under test, or ``None`` for the default.
        """
        self.clock = ManualClock(START)
        super().__init__(clock=self.clock, retry=retry)
        self.failures = list(failures)
        self.attempts: list[datetime] = []
        self.disconnects = 0
        self.refuse_disconnect: BaseException | None = None
        self.state = ConnectionState.DISCONNECTED

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

    def _connect(self) -> Connection:
        """Come up, or raise the next scripted failure.

        Returns:
            The resulting snapshot.

        Raises:
            BaseException: The next entry in the failure queue.
        """
        self.attempts.append(self.clock.now())
        if self.failures:
            self.state = ConnectionState.DISCONNECTED
            raise self.failures.pop(0)
        self.state = ConnectionState.CONNECTED
        self._record_heartbeat(self.clock.now())
        return self._connection()

    def _disconnect(self) -> None:
        """Go down, raising afterwards if a test asked for it.

        Raises:
            BaseException: Whatever ``refuse_disconnect`` holds.
        """
        self.disconnects += 1
        self._clear_session_readings()
        self.state = ConnectionState.DISCONNECTED
        if self.refuse_disconnect is not None:
            raise self.refuse_disconnect

    def _reconnect(self) -> Connection:
        """Replace the session, by way of the public methods.

        Returns:
            The resulting snapshot.

        Notes:
            Written the way both real adapters write it, because the attempt
            multiplication this shape would otherwise cause is exactly what is
            being counted.
        """
        self.disconnect()
        return self.connect()


def _probe(
    failures: Sequence[BaseException],
    *,
    retry: RetryPolicy | None = None,
) -> _Probe:
    """Build an instantiable probe.

    Args:
        failures: Raised one per connect attempt, in order.
        retry: The policy under test, or ``None`` for the default.

    Returns:
        An instance. The port's remaining methods are filled in with stubs,
        because a subclass that has not answered all thirty-one cannot be built.
    """
    members: dict[str, object] = dict.fromkeys(
        _Probe.__abstractmethods__, lambda *_args, **_kwargs: None
    )
    built = type("ProbeAdapter", (_Probe,), members)
    return cast("_Probe", built(failures, retry=retry))


def _transients(count: int) -> list[BaseException]:
    """Build a queue of retryable failures.

    Args:
        count: How many.

    Returns:
        That many distinct connection errors, numbered so a test can tell which
        attempt an error came from.
    """
    return [BrokerConnectionError(f"{DROPPED} ({index})", venue=VENUE) for index in range(count)]


# --- Reading a schedule off a run ---------------------------------------------


def _seconds(rig: Rig) -> tuple[float, ...]:
    """Report when each attempt happened, as seconds since the start.

    Args:
        rig: The rig whose attempts to read.

    Returns:
        One entry per attempt. The first is always ``0.0``, because the first
        attempt is never delayed.
    """
    return tuple((moment - START).total_seconds() for moment in rig.attempts())


def _from_another_thread[T](question: Callable[[], T]) -> T:
    """Ask something from a thread that is not this one, and insist on an answer.

    Args:
        question: What to ask.

    Returns:
        The answer.

    Notes:
        The other thread is the whole point. The session lock is re-entrant, so
        a question asked from the thread that is retrying would be answered by
        the lock it is meant to be excluded by.
    """
    answers: list[T] = []
    thread = threading.Thread(target=lambda: answers.append(question()))
    thread.start()
    thread.join(WATCHDOG)
    assert not thread.is_alive(), "the question was still blocked when the watchdog expired"
    assert len(answers) == 1
    return answers[0]


def _during_the_backoff[T](
    rig: Rig,
    monkeypatch: pytest.MonkeyPatch,
    question: Callable[[], T],
) -> list[T]:
    """Arrange for a question to be asked from another thread inside every wait.

    Args:
        rig: The rig whose clock to intercept.
        monkeypatch: Undoes the interception afterwards.
        question: What to ask, once per wait.

    Returns:
        The answers, filled in as the retrying call runs. Empty until it does,
        and one entry shorter than the attempt count, because the last attempt
        is not followed by a wait.

    Notes:
        The clock is where the waiting is, so this is the only moment that is
        both inside the retry loop and outside the adapter — no adapter internal
        is patched, and the loop being measured is the real one.
    """
    answers: list[T] = []
    original = rig.clock.sleep

    def spy(seconds: float) -> None:
        answers.append(_from_another_thread(question))
        original(seconds)

    monkeypatch.setattr(rig.clock, "sleep", spy)
    return answers


# --- The registry -------------------------------------------------------------


class TestTheRegistryCoversEveryAdapter:
    def test_every_concrete_adapter_is_behind_a_case(self) -> None:
        # Compared against the ancestry rather than the exact type, because the
        # mock case builds a subclass in order to count. Without this, a third
        # adapter would inherit the policy and be tested by nobody.
        concrete = {
            subclass
            for subclass in BaseBrokerAdapter.__subclasses__()
            if not subclass.__abstractmethods__
        }
        covered = {
            ancestor for case in CASES for ancestor in type(case.build(None).adapter).__mro__
        }

        assert concrete
        assert concrete <= covered

    def test_the_counting_subclass_is_still_a_mock_adapter(self) -> None:
        # If it ever stopped being one, every mock case below would be testing
        # something other than the adapter that ships.
        assert issubclass(_CountingMockAdapter, MockBrokerAdapter)


# --- The default is what it always was ----------------------------------------


class TestTheDefaultIsStillOneAttempt:
    def test_an_adapter_built_without_a_policy_does_not_retry(self, case: AdapterCase) -> None:
        rig = case.build(None)
        rig.fail(CONNECT, 1)

        with pytest.raises(BrokerConnectionError, match=DROPPED):
            rig.adapter.connect()

        assert len(rig.attempts()) == 1

    def test_the_default_policy_is_the_named_one(self, case: AdapterCase) -> None:
        assert case.build(None).adapter._retry == RetryPolicy.none()

    def test_a_subclass_written_before_policies_existed_still_builds(self) -> None:
        # `_bare` calls `super().__init__()` with no arguments, exactly as both
        # adapters did before TASK-0009 and TASK-0010 added parameters. Neither
        # addition may become mandatory.
        adapter = _bare()

        assert adapter._retry == RetryPolicy.none()
        assert isinstance(adapter._clock, SystemClock)

    def test_a_connect_that_does_not_fail_makes_one_round_trip(self, case: AdapterCase) -> None:
        rig = case.build(RetryPolicy.fixed(4, 2.0))

        rig.adapter.connect()

        assert len(rig.attempts()) == 1
        assert rig.clock.now() == START


# --- Recovery -----------------------------------------------------------------


class TestASuccessfulReconnectAfterATransientFailure:
    def test_connect_recovers(self, case: AdapterCase) -> None:
        rig = case.build(RetryPolicy.fixed(3, 2.0))
        rig.fail(CONNECT, 1)

        connection = rig.adapter.connect()

        assert connection.state is ConnectionState.CONNECTED
        assert len(rig.attempts()) == 2

    def test_reconnect_recovers(self, case: AdapterCase) -> None:
        rig = case.connected(RetryPolicy.fixed(3, 2.0))
        rig.fail(RECONNECT, 1)

        connection = rig.adapter.reconnect()

        assert connection.state is ConnectionState.CONNECTED
        assert len(rig.attempts()) == 2

    def test_the_recovered_session_is_a_real_one(self, case: AdapterCase) -> None:
        rig = case.build(RetryPolicy.fixed(3, 2.0))
        rig.fail(CONNECT, 2)

        rig.adapter.connect()

        assert rig.adapter.is_connected()
        assert rig.adapter.health().connected
        assert rig.adapter.health().state is ConnectionState.CONNECTED

    def test_recovery_costs_exactly_the_delays_it_used(self, case: AdapterCase) -> None:
        rig = case.build(RetryPolicy.fixed(3, 2.0))
        rig.fail(CONNECT, 1)

        rig.adapter.connect()

        # One retry, so one delay — and none after the attempt that worked.
        assert rig.clock.now() == START + timedelta(seconds=2)

    def test_the_heartbeat_is_stamped_when_the_session_came_up(self, case: AdapterCase) -> None:
        # Not when the first attempt was made. A heartbeat dated before the
        # backoff would make a fresh session look stale by the length of it.
        rig = case.build(RetryPolicy.fixed(3, 2.0))
        rig.fail(CONNECT, 1)

        connection = rig.adapter.connect()

        assert connection.last_heartbeat == START + timedelta(seconds=2)
        assert rig.adapter.heartbeat_age() == timedelta(0)


# --- Exhaustion ---------------------------------------------------------------


class TestRetryExhaustion:
    def test_every_attempt_the_policy_allows_is_made(self, case: AdapterCase) -> None:
        rig = case.build(RetryPolicy.immediate(4))
        rig.fail(CONNECT, PLENTY)

        with pytest.raises(BrokerConnectionError):
            rig.adapter.connect()

        assert len(rig.attempts()) == 4

    def test_the_failure_reaches_the_caller_unwrapped(self, case: AdapterCase) -> None:
        rig = case.build(RetryPolicy.immediate(3))
        rig.fail(CONNECT, PLENTY)

        with pytest.raises(BrokerConnectionError, match=DROPPED) as raised:
            rig.adapter.connect()

        # The type a caller would have seen with no policy at all. A retry
        # policy is not a reason to change what a failure is called.
        assert type(raised.value) is BrokerConnectionError

    def test_the_adapter_is_left_disconnected(self, case: AdapterCase) -> None:
        rig = case.build(RetryPolicy.immediate(3))
        rig.fail(CONNECT, PLENTY)

        with pytest.raises(BrokerConnectionError):
            rig.adapter.connect()

        assert not rig.adapter.is_connected()
        assert rig.adapter.health().state is ConnectionState.DISCONNECTED

    def test_exhaustion_waited_the_whole_schedule_and_no_more(self, case: AdapterCase) -> None:
        policy = RetryPolicy.fixed(3, 2.0)
        rig = case.build(policy)
        rig.fail(CONNECT, PLENTY)

        with pytest.raises(BrokerConnectionError):
            rig.adapter.connect()

        assert rig.clock.now() == START + timedelta(seconds=policy.total_delay)

    def test_a_later_call_gets_a_full_set_of_attempts_again(self, case: AdapterCase) -> None:
        rig = case.build(RetryPolicy.immediate(3))
        rig.fail(CONNECT, 3)
        with pytest.raises(BrokerConnectionError):
            rig.adapter.connect()
        rig.forget()

        # The policy is a value, not a budget that runs down.
        rig.adapter.connect()

        assert len(rig.attempts()) == 1
        assert rig.adapter.is_connected()


# --- The schedule the operator configured is the one the venue sees -----------


class TestTheBackoffProgression:
    def test_an_exponential_schedule_doubles(self, case: AdapterCase) -> None:
        rig = case.build(RetryPolicy.exponential(4, 1.0))
        rig.fail(CONNECT, PLENTY)

        with pytest.raises(BrokerConnectionError):
            rig.adapter.connect()

        # Delays of 1, 2, 4 — so attempts at 0, 1, 3, 7.
        assert _seconds(rig) == (0.0, 1.0, 3.0, 7.0)

    def test_a_fixed_schedule_does_not_grow(self, case: AdapterCase) -> None:
        rig = case.build(RetryPolicy.fixed(4, 2.0))
        rig.fail(CONNECT, PLENTY)

        with pytest.raises(BrokerConnectionError):
            rig.adapter.connect()

        assert _seconds(rig) == (0.0, 2.0, 4.0, 6.0)

    def test_a_ceiling_flattens_the_growth_without_capping_the_attempts(
        self, case: AdapterCase
    ) -> None:
        rig = case.build(RetryPolicy.exponential(5, 1.0, 2.0, max_delay=2.0))
        rig.fail(CONNECT, PLENTY)

        with pytest.raises(BrokerConnectionError):
            rig.adapter.connect()

        # Delays of 1, 2, 2, 2 — the third would have been 4 without the ceiling.
        assert _seconds(rig) == (0.0, 1.0, 3.0, 5.0, 7.0)

    def test_the_run_realises_the_schedule_the_policy_states(self, case: AdapterCase) -> None:
        # `delays()` is data and is asserted directly in the common suite. This
        # is the statement that the adapter does not quietly do something else.
        policy = RetryPolicy.exponential(4, 1.5, 3.0)
        rig = case.build(policy)
        rig.fail(CONNECT, PLENTY)

        with pytest.raises(BrokerConnectionError):
            rig.adapter.connect()

        instants = _seconds(rig)
        gaps = tuple(later - earlier for earlier, later in itertools.pairwise(instants))
        assert len(instants) == policy.max_attempts
        assert gaps == policy.delays()

    def test_a_reconnect_backs_off_on_the_same_schedule(self, case: AdapterCase) -> None:
        rig = case.connected(RetryPolicy.exponential(4, 1.0))
        rig.fail(RECONNECT, PLENTY)

        with pytest.raises(BrokerConnectionError):
            rig.adapter.reconnect()

        assert _seconds(rig) == (0.0, 1.0, 3.0, 7.0)


# --- Immediate ----------------------------------------------------------------


class TestImmediateRetry:
    def test_no_time_passes(self, case: AdapterCase) -> None:
        rig = case.build(RetryPolicy.immediate(4))
        rig.fail(CONNECT, PLENTY)

        with pytest.raises(BrokerConnectionError):
            rig.adapter.connect()

        assert rig.clock.now() == START
        assert _seconds(rig) == (0.0, 0.0, 0.0, 0.0)

    def test_it_is_not_the_same_as_not_retrying(self, case: AdapterCase) -> None:
        # Both take zero time, so time cannot tell them apart; the attempt count
        # is the only thing that can.
        immediate = case.build(RetryPolicy.immediate(3))
        immediate.fail(CONNECT, 2)
        never = case.build(RetryPolicy.none())
        never.fail(CONNECT, 2)

        immediate.adapter.connect()
        with pytest.raises(BrokerConnectionError):
            never.adapter.connect()

        assert len(immediate.attempts()) == 3
        assert len(never.attempts()) == 1

    def test_it_still_stops_at_the_attempt_limit(self, case: AdapterCase) -> None:
        # A zero delay must not turn into an unbounded loop.
        rig = case.build(RetryPolicy.immediate(3))
        rig.fail(CONNECT, PLENTY)

        with pytest.raises(BrokerConnectionError):
            rig.adapter.connect()

        assert len(rig.attempts()) == 3


# --- Permanent failures -------------------------------------------------------


class TestAPermanentFailureIsNotRetried:
    def test_a_refusal_stops_at_the_first_attempt(self, case: AdapterCase) -> None:
        rig = case.build(RetryPolicy.fixed(4, 2.0))
        rig.refuse(CONNECT)

        with pytest.raises(BrokerAuthenticationError, match=REFUSED):
            rig.adapter.connect()

        assert len(rig.attempts()) == 1
        assert rig.clock.now() == START

    def test_the_same_policy_does_retry_a_transient_failure(self, case: AdapterCase) -> None:
        # The control. Without it the test above would pass on an adapter that
        # had no policy at all.
        rig = case.build(RetryPolicy.fixed(4, 2.0))
        rig.fail(CONNECT, 1)

        rig.adapter.connect()

        assert len(rig.attempts()) == 2

    def test_a_refusal_leaves_the_adapter_disconnected(self, case: AdapterCase) -> None:
        rig = case.build(RetryPolicy.fixed(4, 2.0))
        rig.refuse(CONNECT)

        with pytest.raises(BrokerAuthenticationError):
            rig.adapter.connect()

        assert not rig.adapter.is_connected()

    def test_the_line_is_drawn_by_the_exception_tree_not_by_a_list(self) -> None:
        # Bad credentials are not a connection problem, and saying so in the
        # hierarchy is what makes the retryable set one entry long. A list of
        # every permanent error would need editing for every new one.
        assert not issubclass(BrokerAuthenticationError, BrokerConnectionError)
        assert list(RETRYABLE_ERRORS) == [BrokerConnectionError]

    def test_the_carve_out_is_one_entry_too(self) -> None:
        assert list(PERMANENT_ERRORS) == [BrokerNotConnectedError]


class TestTheNotConnectedCarveOut:
    def test_not_connected_is_inside_the_retryable_branch(self) -> None:
        # Which is why the carve-out has to exist: without it, "there is no
        # session" would be retried as though the session might appear.
        assert issubclass(BrokerNotConnectedError, BrokerConnectionError)

    def test_it_is_not_retried(self) -> None:
        refusals = [BrokerNotConnectedError("no session", venue=VENUE) for _ in range(3)]
        adapter = _probe(refusals, retry=RetryPolicy.immediate(4))

        with pytest.raises(BrokerNotConnectedError, match="no session"):
            adapter.connect()

        assert len(adapter.attempts) == 1

    def test_the_same_probe_retries_a_plain_connection_error(self) -> None:
        # The control: the carve-out is what stops it, not the probe.
        adapter = _probe(_transients(3), retry=RetryPolicy.immediate(4))

        adapter.connect()

        assert len(adapter.attempts) == 4


# --- Attempts do not multiply -------------------------------------------------


class TestAttemptsDoNotMultiply:
    def test_a_retried_reconnect_makes_the_policys_attempts(self, case: AdapterCase) -> None:
        # Both adapters build `reconnect` out of the public `connect`. A policy
        # applied at both entry points would make this nine.
        rig = case.connected(RetryPolicy.immediate(3))
        rig.fail(RECONNECT, PLENTY)

        with pytest.raises(BrokerConnectionError):
            rig.adapter.reconnect()

        assert len(rig.attempts()) == 3

    def test_the_probe_agrees(self) -> None:
        adapter = _probe(_transients(PLENTY), retry=RetryPolicy.immediate(3))

        with pytest.raises(BrokerConnectionError):
            adapter.reconnect()

        assert len(adapter.attempts) == 3
        assert adapter.disconnects == 3

    def test_the_guard_is_clear_after_a_success(self) -> None:
        adapter = _probe(_transients(1), retry=RetryPolicy.immediate(3))

        adapter.connect()

        assert adapter._retrying is False

    def test_the_guard_is_clear_after_a_failure(self) -> None:
        adapter = _probe(_transients(PLENTY), retry=RetryPolicy.immediate(3))

        with pytest.raises(BrokerConnectionError):
            adapter.connect()

        assert adapter._retrying is False

    def test_a_later_call_retries_again(self, case: AdapterCase) -> None:
        # The guard suppresses the inner policy for the duration of one
        # lifecycle call, not for the life of the adapter.
        rig = case.connected(RetryPolicy.immediate(3))
        rig.fail(RECONNECT, 3)
        with pytest.raises(BrokerConnectionError):
            rig.adapter.reconnect()
        rig.forget()
        rig.fail(RECONNECT, 1)

        rig.adapter.reconnect()

        assert len(rig.attempts()) == 2


# --- Disconnect ---------------------------------------------------------------


class TestDisconnectIsNeverRetried:
    def test_the_hook_runs_once_even_when_it_raises(self) -> None:
        # No adapter does this — the port forbids `disconnect` from raising —
        # but making it raise is the only way to observe that the base class is
        # not wrapping it. Cleanup that retries is cleanup that hangs.
        adapter = _probe([], retry=RetryPolicy.immediate(4))
        adapter.connect()
        adapter.refuse_disconnect = BrokerConnectionError(DROPPED, venue=VENUE)

        with pytest.raises(BrokerConnectionError, match=DROPPED):
            adapter.disconnect()

        assert adapter.disconnects == 1

    def test_no_time_is_spent_waiting_to_try_again(self) -> None:
        adapter = _probe([], retry=RetryPolicy.fixed(4, 30.0))
        adapter.connect()
        adapter.refuse_disconnect = BrokerConnectionError(DROPPED, venue=VENUE)

        with pytest.raises(BrokerConnectionError):
            adapter.disconnect()

        assert adapter.clock.now() == START

    def test_an_ordinary_disconnect_is_unaffected(self, case: AdapterCase) -> None:
        rig = case.connected(RetryPolicy.fixed(4, 30.0))

        rig.adapter.disconnect()

        assert not rig.adapter.is_connected()
        assert rig.clock.now() == START


# --- What ATLAS-TASK-0008 and 0009 guaranteed is still guaranteed -------------


class TestSupervisionAnswersDuringTheBackoff:
    def test_the_session_lock_really_is_held_throughout(
        self, case: AdapterCase, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        # This is the cost being accepted, stated as a test rather than left in
        # a docstring: a lifecycle call from another thread waits out the whole
        # backoff. It is also what stops the three tests below being vacuous.
        rig = case.connected(RetryPolicy.fixed(3, 1.0))
        rig.fail(RECONNECT, PLENTY)
        free = _during_the_backoff(
            rig, monkeypatch, lambda: _free_for_another_thread(rig.adapter._session_lock)
        )

        with pytest.raises(BrokerConnectionError):
            rig.adapter.reconnect()

        assert free == [False, False]

    def test_the_probe_would_notice_a_lock_that_was_free(self, case: AdapterCase) -> None:
        rig = case.connected(RetryPolicy.fixed(3, 1.0))

        assert _free_for_another_thread(rig.adapter._session_lock) is True

    def test_health_still_answers(self, case: AdapterCase, monkeypatch: pytest.MonkeyPatch) -> None:
        rig = case.connected(RetryPolicy.fixed(3, 1.0))
        rig.fail(RECONNECT, PLENTY)
        answers = _during_the_backoff(rig, monkeypatch, lambda: rig.adapter.health().state)

        with pytest.raises(BrokerConnectionError):
            rig.adapter.reconnect()

        # The session is down between attempts, and health says so — from
        # another thread, while the retrying thread holds the session lock.
        assert answers == [ConnectionState.DISCONNECTED, ConnectionState.DISCONNECTED]

    def test_is_connected_still_answers(
        self, case: AdapterCase, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        rig = case.connected(RetryPolicy.fixed(3, 1.0))
        rig.fail(RECONNECT, PLENTY)
        answers = _during_the_backoff(rig, monkeypatch, rig.adapter.is_connected)

        with pytest.raises(BrokerConnectionError):
            rig.adapter.reconnect()

        assert answers == [False, False]

    def test_heartbeat_age_still_answers(
        self, case: AdapterCase, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        rig = case.connected(RetryPolicy.fixed(3, 1.0))
        rig.fail(RECONNECT, PLENTY)
        answers = _during_the_backoff(rig, monkeypatch, rig.adapter.heartbeat_age)

        with pytest.raises(BrokerConnectionError):
            rig.adapter.reconnect()

        # `None`, because the reconnect cleared the readings before its first
        # attempt. The value is not the claim; that it came back at all is.
        assert answers == [None, None]


class TestTheLockOrderIsUnchanged:
    def test_retrying_introduces_no_third_lock(self, case: AdapterCase) -> None:
        rig = case.build(RetryPolicy.immediate(3))
        log = _traced(rig.adapter)
        rig.fail(CONNECT, 1)

        rig.adapter.connect()

        assert {name for _action, name in log} == {"session", "readings"}

    def test_the_readings_lock_is_still_a_leaf(self, case: AdapterCase) -> None:
        rig = case.build(RetryPolicy.immediate(3))
        log = _traced(rig.adapter)
        rig.fail(CONNECT, 1)

        rig.adapter.connect()

        for index, event in enumerate(log):
            if event == ("acquire", "readings"):
                assert log[index + 1] == ("release", "readings")

    def test_the_session_lock_is_still_never_taken_under_the_readings_lock(
        self, case: AdapterCase
    ) -> None:
        rig = case.connected(RetryPolicy.immediate(3))
        log = _traced(rig.adapter)
        rig.fail(RECONNECT, 1)

        rig.adapter.reconnect()

        held: list[str] = []
        for action, name in log:
            if action == "acquire":
                assert not (name == "session" and "readings" in held)
                held.append(name)
            else:
                held.remove(name)

    def test_a_retried_reconnect_really_did_take_both(self, case: AdapterCase) -> None:
        rig = case.connected(RetryPolicy.immediate(3))
        log = _traced(rig.adapter)
        rig.fail(RECONNECT, 1)

        rig.adapter.reconnect()

        assert ("acquire", "session") in log
        assert ("acquire", "readings") in log

    def test_the_session_lock_is_taken_once_and_released_once(self, case: AdapterCase) -> None:
        # Three attempts, one critical section. A policy that released the lock
        # between attempts would show three of each, and ADR-0007's claim that a
        # reconnect is indivisible would be gone.
        rig = case.build(RetryPolicy.immediate(3))
        log = _traced(rig.adapter)
        rig.fail(CONNECT, 2)

        rig.adapter.connect()

        assert [action for action, name in log if name == "session"] == ["acquire", "release"]


# --- How an adapter gets its policy -------------------------------------------


class TestHowAnAdapterGetsItsPolicy:
    def test_every_adapter_accepts_one_by_keyword(self, case: AdapterCase) -> None:
        policy = RetryPolicy.exponential(3, 0.5)

        assert case.build(policy).adapter._retry is policy

    def test_no_adapter_implements_any_of_it(self, case: AdapterCase) -> None:
        # The requirement is that existing adapters inherit the behaviour
        # without duplicating code, which is checkable rather than assertable in
        # prose: neither subclass may define these at all.
        adapter_type = type(case.build(None).adapter)

        for name in ("connect", "disconnect", "reconnect", "_with_retry"):
            assert getattr(adapter_type, name) is getattr(BaseBrokerAdapter, name)

    def test_the_base_hands_the_executor_the_policy_the_clock_and_the_tree(
        self, case: AdapterCase, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        policy = RetryPolicy.immediate(3)
        rig = case.build(policy)
        seen: list[dict[str, Any]] = []

        def spy(call: Callable[[], Connection], **passed: Any) -> Connection:  # noqa: ANN401
            seen.append(passed)
            return call()

        monkeypatch.setattr(base_module, "retry_call", spy)
        rig.adapter.connect()

        assert seen == [
            {
                "policy": policy,
                "clock": rig.clock,
                "retry_on": RETRYABLE_ERRORS,
                "give_up_on": PERMANENT_ERRORS,
            }
        ]

    def test_the_clock_it_hands_over_is_the_one_it_was_given(self, case: AdapterCase) -> None:
        rig = case.build(None)

        assert rig.adapter._clock is rig.clock


# --- Regression ---------------------------------------------------------------


class TestNothingThatUsedToWorkStoppedWorking:
    @pytest.mark.parametrize("method", ["connect", "disconnect", "reconnect"])
    def test_the_public_signatures_are_unchanged(self, method: str) -> None:
        # The policy is constructor configuration. Nothing about it appears at a
        # call site, so no caller of the port has to change.
        signature = inspect.signature(getattr(BaseBrokerAdapter, method))

        assert list(signature.parameters) == ["self"]

    def test_connect_is_still_idempotent(self, case: AdapterCase) -> None:
        rig = case.connected(RetryPolicy.immediate(3))

        connection = rig.adapter.connect()

        assert connection.state is ConnectionState.CONNECTED
        assert rig.attempts() == ()

    def test_a_second_connect_does_not_consume_the_policy(self, case: AdapterCase) -> None:
        # A call that is contractually not an error must not become one, and
        # must not spend attempts on a session that already exists.
        rig = case.connected(RetryPolicy.immediate(3))

        rig.adapter.connect()

        assert rig.clock.now() == START

    def test_disconnect_is_still_safe_on_a_session_that_never_opened(
        self, case: AdapterCase
    ) -> None:
        rig = case.build(RetryPolicy.immediate(3))

        rig.adapter.disconnect()

        assert not rig.adapter.is_connected()

    def test_reconnect_still_replaces_the_session(self, case: AdapterCase) -> None:
        rig = case.connected(RetryPolicy.immediate(3))

        connection = rig.adapter.reconnect()

        assert connection.state is ConnectionState.CONNECTED
        assert len(rig.attempts()) == 1

    def test_an_unretried_failure_is_the_failure_it_always_was(self, case: AdapterCase) -> None:
        rig = case.build(RetryPolicy.none())
        rig.refuse(CONNECT)

        with pytest.raises(BrokerAuthenticationError, match=REFUSED):
            rig.adapter.connect()

    def test_a_policy_does_not_make_an_unfailing_adapter_slower(self, case: AdapterCase) -> None:
        rig = case.build(RetryPolicy.exponential(5, 60.0))

        rig.adapter.connect()
        rig.adapter.reconnect()
        rig.adapter.disconnect()

        assert rig.clock.now() == START
