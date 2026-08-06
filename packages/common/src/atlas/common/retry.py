"""Retrying as a value the caller owns, separate from the thing being retried.

A retry loop written inline is three decisions welded to one call site: how many
attempts, how long between them, and which failures are worth another go. Welded
together they cannot be configured, cannot be tested without provoking the
failure they exist for, and get rewritten slightly differently at the next call
site. This module takes the three apart.

:class:`RetryPolicy`
    *How many, and how long between.* A frozen value with no behaviour beyond
    arithmetic — it holds no clock, no exception types, no reference to whatever
    is being retried, and nothing about brokers. It can be constructed in a
    config module, compared, logged, and asserted on. :meth:`RetryPolicy.delays`
    is the whole schedule as data, which is what makes "exponential backoff
    progresses 1, 2, 4" a statement about a value rather than about a run.

:func:`retry_call`
    *Which failures, and the waiting.* Given a policy, a clock and the exception
    types the caller considers transient, it runs a callable until it succeeds or
    the attempts run out. The exception types are a parameter because which
    failures are worth retrying is a fact about a domain, and this module has
    none.

The waiting goes through :meth:`~atlas.common.clock.Clock.sleep`, so a test
drives a hundred-second backoff with a :class:`~atlas.common.clock.ManualClock`
in no time and then asserts the resulting instant exactly. Nothing here reads the
host clock or sleeps on its own.

What is deliberately absent
---------------------------
**Jitter.** Randomised backoff is the correct answer to a thundering herd, and it
would need a source of randomness injected the way the clock is. Until something
in Atlas has enough concurrent clients for a herd to exist, adding it would trade
a real property — a schedule that is exactly reproducible — for a hypothetical
one. ADR-0009 records this as a decision rather than an oversight.

**A budget or deadline.** "Give up after thirty seconds regardless" is a
different policy shape, and one that a caller can already approximate with
:attr:`RetryPolicy.total_delay`.

**Logging and callbacks.** Nothing here reports what it did. Atlas has no logging
port yet; inventing one here would put it in the wrong package.

Boundary:
    This module imports the standard library and
    :mod:`atlas.common.clock`, and nothing else.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Final

if TYPE_CHECKING:
    from collections.abc import Callable

    from atlas.common.clock import Clock

__all__ = ["RetryPolicy", "retry_call"]

#: A policy must permit the first attempt. Zero attempts is not a cautious
#: policy, it is a call that never happens, and a caller that wants that should
#: not be calling.
_MIN_ATTEMPTS: Final = 1

#: A growth factor below one shrinks the delay on every retry, which inverts the
#: reason backoff exists. Exactly one is a fixed delay and is permitted.
_MIN_MULTIPLIER: Final = 1.0


@dataclass(frozen=True, slots=True)
class RetryPolicy:
    """How many attempts to make, and how long to wait between them.

    The default is **no retry at all**: one attempt, no delay, which is what
    every caller got before this class existed. Retrying is something a caller
    opts into, because a policy that retried by default would change the
    behaviour of code that never asked for it, and would do so invisibly — the
    only symptom of a wrongly retried call is that it took longer to fail.

    Delays are measured in seconds and are the gaps *between* attempts, so a
    policy with ``max_attempts`` of ``n`` has ``n - 1`` of them. The first
    attempt is never delayed.

    Attributes:
        max_attempts: Total attempts, including the first. ``1`` means no retry.
        initial_delay: Seconds to wait before the second attempt.
        multiplier: What each delay is multiplied by to get the next. ``1.0`` is
            a fixed delay; ``2.0`` is the usual exponential doubling.
        max_delay: A ceiling on any single delay, or ``None`` for none. Bounds
            an exponential schedule without bounding the attempts.

    Notes:
        Frozen, so a policy shared between adapters cannot be edited by one of
        them, and hashable, so it can be a dictionary key or a frozen default.
    """

    max_attempts: int = 1
    initial_delay: float = 0.0
    multiplier: float = 1.0
    max_delay: float | None = None

    def __post_init__(self) -> None:
        """Reject a policy that could not mean what it says.

        Raises:
            ValueError: If the attempt count is below one, either duration is
                negative, the multiplier is below one, or the ceiling is below
                the first delay. The last of those is legal arithmetic — the
                ceiling would simply clamp every delay including the first — but
                it means ``initial_delay`` has no effect, and a field that is
                silently ignored is a misconfiguration rather than a choice.
        """
        if self.max_attempts < _MIN_ATTEMPTS:
            msg = f"max_attempts must be at least {_MIN_ATTEMPTS}; got {self.max_attempts!r}"
            raise ValueError(msg)
        if self.initial_delay < 0:
            msg = f"initial_delay must not be negative; got {self.initial_delay!r}"
            raise ValueError(msg)
        if self.multiplier < _MIN_MULTIPLIER:
            msg = f"multiplier must be at least {_MIN_MULTIPLIER}; got {self.multiplier!r}"
            raise ValueError(msg)
        if self.max_delay is not None and self.max_delay < self.initial_delay:
            msg = (
                f"max_delay must not be below initial_delay; got max_delay="
                f"{self.max_delay!r} and initial_delay={self.initial_delay!r}"
            )
            raise ValueError(msg)

    @classmethod
    def none(cls) -> RetryPolicy:
        """Make the policy that does not retry.

        Returns:
            One attempt, no delay. The default, named so that a caller passing
            it is visibly choosing it rather than forgetting to pass anything.
        """
        return cls()

    @classmethod
    def immediate(cls, max_attempts: int) -> RetryPolicy:
        """Make a policy that retries at once, without waiting.

        Args:
            max_attempts: Total attempts, including the first.

        Returns:
            A policy whose every delay is zero.

        Notes:
            The right shape when a failure is expected to be already over by the
            time it is reported — a stale handle, a connection the venue closed
            while it was idle — and the wrong shape for anything caused by load,
            where retrying at once is what makes the load worse.
        """
        return cls(max_attempts=max_attempts)

    @classmethod
    def fixed(cls, max_attempts: int, delay: float) -> RetryPolicy:
        """Make a policy that waits the same amount every time.

        Args:
            max_attempts: Total attempts, including the first.
            delay: Seconds between attempts.

        Returns:
            A policy whose delays are all ``delay``.
        """
        return cls(max_attempts=max_attempts, initial_delay=delay)

    @classmethod
    def exponential(
        cls,
        max_attempts: int,
        initial_delay: float,
        multiplier: float = 2.0,
        max_delay: float | None = None,
    ) -> RetryPolicy:
        """Make a policy whose delay grows with each failure.

        Args:
            max_attempts: Total attempts, including the first.
            initial_delay: Seconds before the second attempt.
            multiplier: Growth factor per retry. Defaults to doubling.
            max_delay: A ceiling on any single delay, or ``None`` for none.

        Returns:
            A policy whose delays are ``initial_delay`` multiplied by
            ``multiplier`` once more on each retry, each clamped to ``max_delay``.
        """
        return cls(
            max_attempts=max_attempts,
            initial_delay=initial_delay,
            multiplier=multiplier,
            max_delay=max_delay,
        )

    def delay_before(self, attempt: int) -> float:
        """Return how long to wait before an attempt.

        Args:
            attempt: Which attempt, counting the first as ``1``.

        Returns:
            Seconds. Zero for the first attempt, which is never delayed.

        Raises:
            ValueError: If ``attempt`` is below one or above
                :attr:`max_attempts`. Asking about an attempt this policy will
                never make is a bug in the caller, and returning a plausible
                number for it would hide an off-by-one in a retry loop.
        """
        if not _MIN_ATTEMPTS <= attempt <= self.max_attempts:
            msg = (
                f"attempt must be between {_MIN_ATTEMPTS} and {self.max_attempts}; "
                f"got {attempt!r}"
            )
            raise ValueError(msg)
        if attempt == _MIN_ATTEMPTS:
            return 0.0
        raw = self.initial_delay * self.multiplier ** (attempt - 2)
        return raw if self.max_delay is None else min(raw, self.max_delay)

    def delays(self) -> tuple[float, ...]:
        """Return the whole schedule of waits, in order.

        Returns:
            One entry per retry, so ``max_attempts - 1`` of them, and an empty
            tuple for a policy that does not retry.

        Notes:
            The schedule is data, which is what lets a test state "1, 2, then 4"
            about the policy itself rather than inferring it from a run.
        """
        return tuple(self.delay_before(attempt) for attempt in range(2, self.max_attempts + 1))

    @property
    def total_delay(self) -> float:
        """Return the longest this policy can spend waiting.

        Returns:
            The sum of every delay, in seconds. Excludes the time the attempts
            themselves take, which this class knows nothing about.
        """
        return sum(self.delays())


def retry_call[T](
    call: Callable[[], T],
    *,
    policy: RetryPolicy,
    clock: Clock,
    retry_on: tuple[type[BaseException], ...],
    give_up_on: tuple[type[BaseException], ...] = (),
) -> T:
    """Run a callable until it succeeds or the policy runs out of attempts.

    Args:
        call: What to run. Takes no arguments — a caller with arguments binds
            them, which keeps this function from having an opinion about them.
            It is called once per attempt and must be safe to call again.
        policy: How many attempts and how long between them.
        clock: What to wait on. The only thing in this function that touches
            time, so a manual clock makes the whole schedule instant and exact.
        retry_on: The exception types worth another attempt. Anything not
            matching propagates from the attempt that raised it, untouched.
        give_up_on: Exception types carved *out* of ``retry_on``. For a domain
            whose transient failures are a base class with a permanent subclass,
            this is how the subclass is excluded without abandoning the base.
            Types outside ``retry_on`` need no entry here; they already
            propagate.

    Returns:
        Whatever the successful attempt returned.

    Raises:
        BaseException: Whatever the final attempt raised. A caller sees the
            failure it would have seen without any retrying, from the last
            attempt rather than the first, and never a wrapper type — a retry
            policy is not a reason to change what a failure is called.

    Notes:
        The callable is invoked, not the venue: whether a retry is *safe* is the
        caller's judgement, and this function assumes it has been made. Retrying
        something that may have already taken effect at the far end is how a
        request gets duplicated.

        Nothing is caught on the final attempt, so ``retry_on`` and
        ``give_up_on`` are consulted only where they can change what happens.
    """
    for attempt in range(_MIN_ATTEMPTS, policy.max_attempts):
        try:
            return call()
        except retry_on as error:
            if isinstance(error, give_up_on):
                raise
            clock.sleep(policy.delay_before(attempt + 1))
    return call()
