"""Unit tests for the retry policy and the executor that runs one.

Two things are under test and they are deliberately separable.

:class:`~atlas.common.retry.RetryPolicy` is arithmetic on a frozen value. Its
tests need no clock, no failure and nothing to retry: "exponential backoff
progresses 1, 2, then 4" is asserted against
:meth:`~atlas.common.retry.RetryPolicy.delays`, which is the schedule as data.
A schedule that can only be observed by provoking failures is a schedule that
can only be tested by provoking failures, and the whole point of separating the
value out is that it does not have to be.

:func:`~atlas.common.retry.retry_call` is the part that fails, waits and gives
up. Its tests use a :class:`~atlas.common.clock.ManualClock`, so a policy that
would block for an hour runs instantly and the resulting instant is asserted
exactly rather than within a tolerance. **Nothing in this module sleeps.**

The recurring shape is :class:`_Scripted`: a callable handed a list of
exceptions to raise, one per call, which records the instant of every attempt.
Asserting on those instants rather than on a total is what makes the backoff
tests specific — a total of seven seconds is produced by 1/2/4 and equally by
3/3/1, and only one of those is exponential.
"""

from __future__ import annotations

import ast
import inspect
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import TYPE_CHECKING, Final

import pytest

from atlas.common import ManualClock, RetryPolicy, retry_call

if TYPE_CHECKING:
    from collections.abc import Sequence

pytestmark = pytest.mark.unit

#: Where every clock in this module starts.
START: Final = datetime(2020, 1, 1, tzinfo=UTC)

#: What a successful call returns. A string rather than ``None`` so that "the
#: value came back" is distinguishable from "nothing was raised".
OK: Final = "connected"

#: The message every ordinary transient failure in this module carries, so
#: that a `pytest.raises` names the failure it expects rather than catching
#: whatever happened to escape.
DROPPED: Final = "the venue dropped the socket"

#: The exception types these tests consider transient. Chosen from the standard
#: library on purpose: this module is the one place retrying is tested with no
#: broker anywhere in it, which is how the claim that the policy is
#: adapter-agnostic is checked rather than asserted.
TRANSIENT: Final = (OSError,)

#: A subclass of the transient type that must nevertheless not be retried. The
#: shape the broker package needs — ``BrokerNotConnectedError`` inherits from
#: the retryable branch and is fixed by acting rather than by waiting — with
#: nothing about brokers in it.
PERMANENT: Final = (TimeoutError,)


def _transients(count: int) -> list[OSError]:
    """Build a run of ordinary transient failures.

    Args:
        count: How many.

    Returns:
        Distinct instances rather than one repeated, so that a test
        asserting on identity can tell which attempt raised which.
    """
    return [OSError(DROPPED) for _ in range(count)]


class _Scripted:
    """A callable that fails to order and remembers when it was called.

    Attributes:
        instants: The clock reading at the start of each attempt, in order. Its
            length is the attempt count and its differences are the delays, so
            one recording answers both questions a backoff test asks.
    """

    def __init__(self, clock: ManualClock, failures: Sequence[BaseException]) -> None:
        """Script a sequence of failures.

        Args:
            clock: Read at the top of every attempt.
            failures: Raised one per call, in order. When they run out the call
                succeeds, so a call that never succeeds is written by supplying
                more failures than the policy has attempts.
        """
        self._clock = clock
        self._failures = list(failures)
        self.instants: list[datetime] = []

    def __call__(self) -> str:
        """Record the attempt and either fail or succeed.

        Returns:
            :data:`OK`, once the scripted failures are exhausted.

        Raises:
            BaseException: The next scripted failure.
        """
        self.instants.append(self._clock.now())
        if self._failures:
            raise self._failures.pop(0)
        return OK

    @property
    def attempts(self) -> int:
        """How many times it was called."""
        return len(self.instants)

    @property
    def gaps(self) -> list[float]:
        """The waits between attempts, in seconds."""
        return [
            (later - earlier).total_seconds()
            for earlier, later in zip(self.instants, self.instants[1:], strict=False)
        ]


def _run(
    policy: RetryPolicy,
    failures: Sequence[BaseException],
    clock: ManualClock | None = None,
) -> tuple[_Scripted, ManualClock]:
    """Run a scripted call under a policy.

    Args:
        policy: The policy to apply.
        failures: What the call raises, one per attempt.
        clock: The clock to use. A fresh one starting at :data:`START` by
            default.

    Returns:
        The call and the clock, for the assertions.

    Raises:
        BaseException: Whatever the final attempt raised.
    """
    resolved = ManualClock(START) if clock is None else clock
    call = _Scripted(resolved, failures)
    retry_call(call, policy=policy, clock=resolved, retry_on=TRANSIENT, give_up_on=PERMANENT)
    return call, resolved


# --- The policy is a value ----------------------------------------------------


class TestTheDefaultPolicyDoesNotRetry:
    """The default is the behaviour every caller had before this class existed.

    Load-bearing rather than conservative. An adapter that retried without being
    asked would change the behaviour of code that never opted in, and the only
    symptom would be that a failure took longer to arrive.
    """

    def test_it_allows_exactly_one_attempt(self) -> None:
        assert RetryPolicy().max_attempts == 1

    def test_the_named_constructor_agrees_with_the_bare_one(self) -> None:
        assert RetryPolicy.none() == RetryPolicy()

    def test_it_schedules_no_waits_at_all(self) -> None:
        assert RetryPolicy.none().delays() == ()

    def test_it_can_never_block(self) -> None:
        assert RetryPolicy.none().total_delay == 0.0

    def test_the_first_attempt_is_never_delayed(self) -> None:
        assert RetryPolicy.none().delay_before(1) == 0.0


class TestThePolicyRefusesWhatItCouldNotMean:
    def test_it_refuses_fewer_than_one_attempt(self) -> None:
        with pytest.raises(ValueError, match="max_attempts must be at least 1"):
            RetryPolicy(max_attempts=0)

    def test_it_refuses_a_negative_attempt_count(self) -> None:
        with pytest.raises(ValueError, match="max_attempts must be at least 1"):
            RetryPolicy(max_attempts=-3)

    def test_it_refuses_a_negative_delay(self) -> None:
        with pytest.raises(ValueError, match="initial_delay must not be negative"):
            RetryPolicy(max_attempts=2, initial_delay=-1.0)

    def test_it_refuses_a_shrinking_multiplier(self) -> None:
        # A growth factor below one inverts the reason backoff exists: each
        # retry would arrive sooner than the last, hardest on the venue exactly
        # when it is least able to answer.
        with pytest.raises(ValueError, match="multiplier must be at least 1"):
            RetryPolicy(max_attempts=3, initial_delay=1.0, multiplier=0.5)

    def test_it_refuses_a_ceiling_below_the_first_delay(self) -> None:
        # Legal arithmetic — the ceiling would clamp every delay including the
        # first — but it makes `initial_delay` a field with no effect, and a
        # silently ignored field is a misconfiguration rather than a choice.
        with pytest.raises(ValueError, match="max_delay must not be below initial_delay"):
            RetryPolicy(max_attempts=3, initial_delay=10.0, max_delay=1.0)

    def test_one_attempt_is_allowed(self) -> None:
        assert RetryPolicy(max_attempts=1).max_attempts == 1

    def test_a_multiplier_of_exactly_one_is_allowed(self) -> None:
        # It is how a fixed delay is spelled, so the boundary has to be open.
        assert RetryPolicy(max_attempts=3, initial_delay=1.0, multiplier=1.0).delays() == (1.0, 1.0)

    def test_a_zero_delay_is_allowed(self) -> None:
        assert RetryPolicy(max_attempts=2, initial_delay=0.0).delays() == (0.0,)

    def test_a_ceiling_equal_to_the_first_delay_is_allowed(self) -> None:
        assert RetryPolicy(max_attempts=3, initial_delay=2.0, max_delay=2.0).delays() == (2.0, 2.0)


class TestTheScheduleIsData:
    def test_a_policy_has_one_wait_fewer_than_it_has_attempts(self) -> None:
        # The off-by-one this class exists to settle once. Delays are the gaps
        # *between* attempts, and the first attempt is not one of them.
        assert len(RetryPolicy.fixed(max_attempts=5, delay=1.0).delays()) == 4

    def test_the_schedule_matches_the_per_attempt_answer(self) -> None:
        policy = RetryPolicy.exponential(max_attempts=4, initial_delay=1.0)

        assert policy.delays() == tuple(policy.delay_before(n) for n in (2, 3, 4))

    def test_the_first_attempt_is_not_delayed_even_on_a_policy_that_waits(self) -> None:
        # The same claim as the one `RetryPolicy.none()` makes, asked of a policy
        # whose `initial_delay` is not zero — so that returning `initial_delay`
        # here would be a different answer rather than the same one by accident.
        assert RetryPolicy.exponential(max_attempts=4, initial_delay=1.5).delay_before(1) == 0.0

    def test_the_total_is_the_sum_of_the_schedule(self) -> None:
        assert RetryPolicy.exponential(max_attempts=4, initial_delay=1.0).total_delay == 7.0

    def test_asking_before_the_first_attempt_is_refused(self) -> None:
        with pytest.raises(ValueError, match="attempt must be between 1 and 3"):
            RetryPolicy.immediate(3).delay_before(0)

    def test_asking_beyond_the_last_attempt_is_refused(self) -> None:
        # Returning a plausible number for an attempt that will never happen is
        # how an off-by-one in a retry loop stays hidden.
        with pytest.raises(ValueError, match="attempt must be between 1 and 3"):
            RetryPolicy.immediate(3).delay_before(4)

    def test_a_policy_is_frozen(self) -> None:
        policy = RetryPolicy.immediate(3)

        with pytest.raises(AttributeError):
            policy.max_attempts = 9  # type: ignore[misc]  # the point of the test

    def test_two_policies_with_the_same_fields_are_equal(self) -> None:
        assert RetryPolicy.fixed(max_attempts=3, delay=1.0) == RetryPolicy(
            max_attempts=3, initial_delay=1.0
        )

    def test_a_policy_can_be_shared_as_a_key(self) -> None:
        # Frozen and hashable, so one policy is safely shared between adapters
        # and can be a default in a mapping.
        assert len({RetryPolicy.immediate(3), RetryPolicy.immediate(3)}) == 1


class TestTheNamedConstructors:
    def test_immediate_retries_without_waiting(self) -> None:
        assert RetryPolicy.immediate(3).delays() == (0.0, 0.0)

    def test_immediate_still_makes_every_attempt(self) -> None:
        assert RetryPolicy.immediate(3).max_attempts == 3

    def test_fixed_waits_the_same_amount_every_time(self) -> None:
        assert RetryPolicy.fixed(max_attempts=4, delay=0.5).delays() == (0.5, 0.5, 0.5)

    def test_exponential_doubles_by_default(self) -> None:
        schedule = RetryPolicy.exponential(max_attempts=4, initial_delay=1.0).delays()

        assert schedule == (1.0, 2.0, 4.0)

    def test_exponential_takes_another_growth_factor(self) -> None:
        schedule = RetryPolicy.exponential(
            max_attempts=5, initial_delay=1.0, multiplier=3.0
        ).delays()

        assert schedule == (1.0, 3.0, 9.0, 27.0)

    def test_a_ceiling_flattens_the_schedule_without_shortening_it(self) -> None:
        # The reason `max_delay` is separate from `max_attempts`: a caller that
        # wants to keep trying for a long time rarely wants to keep waiting
        # longer each time.
        schedule = RetryPolicy.exponential(
            max_attempts=6, initial_delay=1.0, max_delay=4.0
        ).delays()

        assert schedule == (1.0, 2.0, 4.0, 4.0, 4.0)

    def test_a_fixed_schedule_is_not_an_exponential_one(self) -> None:
        # The control. Both of these total six seconds over three waits, so a
        # test asserting only on a total would pass for either.
        fixed = RetryPolicy.fixed(max_attempts=4, delay=2.0)
        growing = RetryPolicy.exponential(max_attempts=4, initial_delay=1.0)

        assert fixed.total_delay != growing.total_delay or fixed.delays() != growing.delays()
        assert fixed.delays() == (2.0, 2.0, 2.0)
        assert growing.delays() == (1.0, 2.0, 4.0)


# --- Running under a policy ---------------------------------------------------


class TestACallThatSucceeds:
    def test_it_is_made_once(self) -> None:
        call, _ = _run(RetryPolicy.exponential(max_attempts=5, initial_delay=1.0), [])

        assert call.attempts == 1

    def test_its_value_is_returned(self) -> None:
        clock = ManualClock(START)

        assert (
            retry_call(lambda: OK, policy=RetryPolicy.immediate(3), clock=clock, retry_on=TRANSIENT)
            == OK
        )

    def test_no_time_passes(self) -> None:
        # A policy that waited before the first attempt would delay every
        # healthy call in the system, which is the expensive way to be wrong.
        _, clock = _run(RetryPolicy.exponential(max_attempts=5, initial_delay=1.0), [])

        assert clock.now() == START


class TestATransientFailureIsRetried:
    def test_the_call_eventually_succeeds(self) -> None:
        clock = ManualClock(START)
        call = _Scripted(clock, _transients(1))

        assert (
            retry_call(
                call,
                policy=RetryPolicy.fixed(max_attempts=3, delay=1.0),
                clock=clock,
                retry_on=TRANSIENT,
            )
            == OK
        )

    def test_it_takes_exactly_as_many_attempts_as_it_needed(self) -> None:
        call, _ = _run(RetryPolicy.fixed(max_attempts=5, delay=1.0), _transients(2))

        assert call.attempts == 3

    def test_the_remaining_attempts_are_not_spent(self) -> None:
        # A loop that ran to `max_attempts` regardless would pass every
        # assertion about the return value and none about the clock.
        _, clock = _run(RetryPolicy.fixed(max_attempts=5, delay=1.0), _transients(2))

        assert clock.now() == START + timedelta(seconds=2)


class TestRetryExhaustion:
    def test_the_last_failure_reaches_the_caller(self) -> None:
        clock = ManualClock(START)
        final = OSError("the last one")
        call = _Scripted(clock, [OSError("first"), OSError("second"), final])

        with pytest.raises(OSError, match="the last one") as raised:
            retry_call(
                call,
                policy=RetryPolicy.fixed(max_attempts=3, delay=1.0),
                clock=clock,
                retry_on=TRANSIENT,
            )

        assert raised.value is final

    def test_the_caller_sees_the_venues_own_error_and_not_a_wrapper(self) -> None:
        # A retry policy is not a reason to change what a failure is called. A
        # caller's `except OSError` has to keep working.
        clock = ManualClock(START)

        with pytest.raises(OSError, match="still down"):
            retry_call(
                _Scripted(clock, [OSError("still down")] * 2),
                policy=RetryPolicy.immediate(2),
                clock=clock,
                retry_on=TRANSIENT,
            )

    def test_every_attempt_is_made(self) -> None:
        clock = ManualClock(START)
        call = _Scripted(clock, _transients(10))

        with pytest.raises(OSError, match=DROPPED):
            retry_call(call, policy=RetryPolicy.immediate(4), clock=clock, retry_on=TRANSIENT)

        assert call.attempts == 4

    def test_no_wait_follows_the_final_attempt(self) -> None:
        # Three attempts means two waits. A loop that slept after the last
        # failure would hold up the caller for a delay that buys nothing.
        clock = ManualClock(START)

        with pytest.raises(OSError, match=DROPPED):
            retry_call(
                _Scripted(clock, _transients(5)),
                policy=RetryPolicy.fixed(max_attempts=3, delay=10.0),
                clock=clock,
                retry_on=TRANSIENT,
            )

        assert clock.now() == START + timedelta(seconds=20)


class TestTheBackoffProgression:
    def test_an_exponential_policy_waits_longer_each_time(self) -> None:
        clock = ManualClock(START)
        call = _Scripted(clock, _transients(3))

        retry_call(
            call,
            policy=RetryPolicy.exponential(max_attempts=4, initial_delay=1.0),
            clock=clock,
            retry_on=TRANSIENT,
        )

        assert call.gaps == [1.0, 2.0, 4.0]

    def test_the_attempts_land_on_the_instants_the_schedule_names(self) -> None:
        # The same fact stated absolutely rather than as differences, because a
        # clock that advanced twice per wait would produce the right gaps from
        # the wrong instants.
        clock = ManualClock(START)
        call = _Scripted(clock, _transients(3))

        retry_call(
            call,
            policy=RetryPolicy.exponential(max_attempts=4, initial_delay=1.0),
            clock=clock,
            retry_on=TRANSIENT,
        )

        assert call.instants == [START + timedelta(seconds=n) for n in (0, 1, 3, 7)]

    def test_a_fixed_policy_waits_the_same_each_time(self) -> None:
        clock = ManualClock(START)
        call = _Scripted(clock, _transients(3))

        retry_call(
            call,
            policy=RetryPolicy.fixed(max_attempts=4, delay=2.0),
            clock=clock,
            retry_on=TRANSIENT,
        )

        assert call.gaps == [2.0, 2.0, 2.0]

    def test_a_ceiling_stops_the_waits_growing(self) -> None:
        clock = ManualClock(START)
        call = _Scripted(clock, _transients(4))

        retry_call(
            call,
            policy=RetryPolicy.exponential(max_attempts=5, initial_delay=1.0, max_delay=2.0),
            clock=clock,
            retry_on=TRANSIENT,
        )

        assert call.gaps == [1.0, 2.0, 2.0, 2.0]

    def test_the_total_wait_is_what_the_policy_promised(self) -> None:
        policy = RetryPolicy.exponential(max_attempts=4, initial_delay=1.0)
        clock = ManualClock(START)

        with pytest.raises(OSError, match=DROPPED):
            retry_call(
                _Scripted(clock, _transients(9)),
                policy=policy,
                clock=clock,
                retry_on=TRANSIENT,
            )

        assert clock.now() == START + timedelta(seconds=policy.total_delay)


class TestImmediateRetry:
    def test_it_makes_every_attempt(self) -> None:
        call, _ = _run(RetryPolicy.immediate(4), _transients(3))

        assert call.attempts == 4

    def test_no_time_passes_between_them(self) -> None:
        call, clock = _run(RetryPolicy.immediate(4), _transients(3))

        assert call.gaps == [0.0, 0.0, 0.0]
        assert clock.now() == START

    def test_no_delay_is_not_the_same_as_no_retry(self) -> None:
        # Both leave the clock exactly where it was, so the clock cannot tell
        # them apart and the attempt count is the only thing that can.
        clock = ManualClock(START)
        call = _Scripted(clock, _transients(2))

        with pytest.raises(OSError, match=DROPPED):
            retry_call(call, policy=RetryPolicy.none(), clock=clock, retry_on=TRANSIENT)

        assert call.attempts == 1
        assert clock.now() == START


class TestAPermanentFailureIsNotRetried:
    def test_something_outside_the_retryable_set_propagates_at_once(self) -> None:
        clock = ManualClock(START)
        call = _Scripted(clock, [ValueError("wrong password")])

        with pytest.raises(ValueError, match="wrong password"):
            retry_call(
                call,
                policy=RetryPolicy.fixed(max_attempts=5, delay=10.0),
                clock=clock,
                retry_on=TRANSIENT,
            )

        assert call.attempts == 1
        assert clock.now() == START

    def test_a_carved_out_subclass_propagates_at_once(self) -> None:
        # The case the `give_up_on` parameter exists for: a type that *is* in
        # the retryable set by inheritance and is nothing like one in meaning.
        # Without the carve-out this would be retried five times.
        clock = ManualClock(START)
        call = _Scripted(clock, [TimeoutError("no session")])

        with pytest.raises(TimeoutError):
            retry_call(
                call,
                policy=RetryPolicy.fixed(max_attempts=5, delay=10.0),
                clock=clock,
                retry_on=TRANSIENT,
                give_up_on=PERMANENT,
            )

        assert call.attempts == 1
        assert clock.now() == START

    def test_the_carve_out_is_what_stops_it(self) -> None:
        # The control for the test above. The same exception under the same
        # policy, with the exclusion removed, is retried — so the assertion is
        # about `give_up_on` rather than about `TimeoutError` happening not to
        # match.
        clock = ManualClock(START)
        call = _Scripted(clock, [TimeoutError("no session")] * 9)

        with pytest.raises(TimeoutError):
            retry_call(call, policy=RetryPolicy.immediate(5), clock=clock, retry_on=TRANSIENT)

        assert call.attempts == 5

    def test_a_permanent_failure_after_a_transient_one_still_stops(self) -> None:
        # Each attempt is judged on what it raised. A run that has already
        # retried once does not thereby become committed to retrying.
        clock = ManualClock(START)
        call = _Scripted(clock, [OSError(DROPPED), TimeoutError("no session")])

        with pytest.raises(TimeoutError):
            retry_call(
                call,
                policy=RetryPolicy.fixed(max_attempts=5, delay=1.0),
                clock=clock,
                retry_on=TRANSIENT,
                give_up_on=PERMANENT,
            )

        assert call.attempts == 2
        assert clock.now() == START + timedelta(seconds=1)

    def test_an_empty_retryable_set_retries_nothing(self) -> None:
        clock = ManualClock(START)
        call = _Scripted(clock, _transients(5))

        with pytest.raises(OSError, match=DROPPED):
            retry_call(call, policy=RetryPolicy.immediate(5), clock=clock, retry_on=())

        assert call.attempts == 1


class TestTheExecutorHoldsNoOpinions:
    def test_it_returns_whatever_the_call_returns(self) -> None:
        # Generic in the call's return type, so nothing about it is broker
        # shaped. A retry policy that only worked for one payload type would be
        # a broker helper wearing a general name.
        clock = ManualClock(START)

        assert retry_call(
            lambda: [1, 2, 3], policy=RetryPolicy.none(), clock=clock, retry_on=TRANSIENT
        ) == [1, 2, 3]

    def test_it_returns_none_without_complaint(self) -> None:
        clock = ManualClock(START)

        assert (
            retry_call(lambda: None, policy=RetryPolicy.none(), clock=clock, retry_on=TRANSIENT)
            is None
        )

    def test_the_clock_is_the_only_thing_it_waits_on(self) -> None:
        # A hundred seconds of backoff, exhausted, in a test that blocks for
        # none of it. This is the assertion that would fail if anything in the
        # module reached for `time.sleep` directly.
        clock = ManualClock(START)

        with pytest.raises(OSError, match=DROPPED):
            retry_call(
                _Scripted(clock, _transients(9)),
                policy=RetryPolicy.fixed(max_attempts=5, delay=25.0),
                clock=clock,
                retry_on=TRANSIENT,
            )

        assert clock.now() == START + timedelta(seconds=100)

    def test_giving_up_on_is_optional(self) -> None:
        clock = ManualClock(START)
        call = _Scripted(clock, [OSError()])

        assert (
            retry_call(call, policy=RetryPolicy.immediate(2), clock=clock, retry_on=TRANSIENT) == OK
        )


#: Calls that read the host's clock or block on it. The sleeps are in the set as
#: well as the reads, because this is the one module in Atlas whose whole job is
#: to wait — a ``time.sleep`` here would be the single most plausible way for the
#: injected clock to be quietly bypassed, and the behavioural test above would
#: still pass, since a real sleep leaves the manual clock exactly where it was.
HOST_CLOCK_CALLS: Final = frozenset(
    {
        "date.today",
        "datetime.now",
        "datetime.today",
        "datetime.utcnow",
        "time.monotonic",
        "time.monotonic_ns",
        "time.perf_counter",
        "time.sleep",
        "time.time",
        "time.time_ns",
    }
)


def _host_clock_calls(path: Path) -> set[str]:
    """Find every direct use of the host clock in a module.

    Args:
        path: The source file.

    Returns:
        The offending call names, as spelled in the source. Empty for a module
        that reads and waits only through a clock it was given.
    """
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    found: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute):
            spelled = ast.unparse(node.func)
            if ".".join(spelled.split(".")[-2:]) in HOST_CLOCK_CALLS:
                found.add(spelled)
    return found


class TestNothingHereTouchesTheHostClock:
    def test_the_module_reads_no_clock_and_sleeps_on_none(self) -> None:
        # Asserted statically rather than behaviourally, because the behaviour
        # of a real sleep is indistinguishable from correctness in a test that
        # only checks the manual clock — it would simply take the time.
        assert _host_clock_calls(Path(inspect.getfile(retry_call))) == set()

    def test_the_scan_notices_a_module_that_sleeps(self, tmp_path: Path) -> None:
        offender = tmp_path / "offender.py"
        offender.write_bytes(b"import time\n\n\ndef f() -> None:\n    time.sleep(1)\n")

        assert _host_clock_calls(offender) == {"time.sleep"}

    def test_the_scan_notices_a_module_that_reads_the_time(self, tmp_path: Path) -> None:
        offender = tmp_path / "reader.py"
        offender.write_bytes(b"from datetime import UTC, datetime\n\nx = datetime.now(UTC)\n")

        assert _host_clock_calls(offender) == {"datetime.now"}

    def test_the_scan_does_not_object_to_an_injected_clock(self, tmp_path: Path) -> None:
        innocent = tmp_path / "innocent.py"
        innocent.write_bytes(b"def f(clock: object) -> None:\n    clock.sleep(1)\n")

        assert _host_clock_calls(innocent) == set()
