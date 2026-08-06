"""Time as something a component is given, not something it reads.

Anything that has to know what time it is asks two questions, and they are not
the same question. *When did this happen* wants a wall-clock instant: it goes
into a domain model, it is compared against a venue's own timestamp, and a
person reads it. *How long ago was that* wants a duration, and a wall clock is
the wrong instrument for it. An NTP correction or a daylight-saving step moves
a wall clock by an amount that has nothing to do with elapsed time, so a
supervision loop subtracting two wall-clock readings can report an hour of
silence from a venue that answered a second ago — or, worse in this domain,
report a stale session as fresh because the clock stepped backwards.

:class:`Clock` therefore has both hands. :meth:`Clock.now` answers the first
question and :meth:`Clock.monotonic` the second, and an implementation is
required to keep them independent in exactly that way: a wall-clock jump must
not move the monotonic reading, and the monotonic reading must never decrease.

:meth:`Clock.sleep` is the one thing here that is not a reading. It is on the
same port rather than on a second one because waiting and measuring have to
agree: code that sleeps through one object and then asks another how long it
waited is testing two doubles against each other. ATLAS-TASK-0010 added it for
retry backoff, and ADR-0009 records why. On a :class:`ManualClock` it returns
immediately *and moves the clock*, so a backoff schedule is asserted as an exact
instant rather than waited out.

Why this is a port
------------------
Because the alternative is a test that sleeps. Code that calls
:func:`datetime.now` directly can only be tested against durations the test
actually waits out, which makes the suite slow where it is honest and flaky
where it is fast. A component that takes a :class:`Clock` is tested by handing
it a :class:`ManualClock` and moving time by a day in no time at all, and the
assertion is exact rather than a tolerance.

The two implementations here are the whole of it. :class:`SystemClock` is what
production uses and reads the host. :class:`ManualClock` is driven by whoever
holds it and reads nothing, which is what makes a test that uses it
deterministic rather than merely fast.

Boundary:
    This module imports the standard library and nothing else, which is what
    lets any package take a dependency on it without inverting a layer.
"""

from __future__ import annotations

import threading
import time
from datetime import UTC, datetime, timedelta
from typing import Protocol, runtime_checkable

__all__ = ["Clock", "ManualClock", "SystemClock"]


def _require_aware(value: datetime, name: str) -> datetime:
    """Reject a naive datetime and normalise an aware one to UTC.

    Args:
        value: The datetime supplied by the caller.
        name: Parameter name, for the message.

    Returns:
        The same instant, expressed in UTC.

    Raises:
        ValueError: If the datetime carries no offset. A naive instant means
            whatever zone the host happens to be in, which is not a fact about
            the system being modelled.
    """
    if value.utcoffset() is None:
        msg = f"{name} must be timezone aware; got the naive value {value!r}"
        raise ValueError(msg)
    return value.astimezone(UTC)


def _require_non_negative(seconds: float, name: str) -> float:
    """Reject a negative duration.

    Args:
        seconds: The duration supplied by the caller.
        name: Parameter name, for the message.

    Returns:
        The same value.

    Raises:
        ValueError: If ``seconds`` is negative. Checked here rather than left to
            :func:`time.sleep` so that both implementations refuse the same
            input with the same message, and so that a caller cannot discover
            the difference only in production.
    """
    if seconds < 0:
        msg = f"{name} must not be negative; got {seconds!r}"
        raise ValueError(msg)
    return seconds


@runtime_checkable
class Clock(Protocol):
    """A source of time, injected into a component rather than read by it.

    Notes:
        Implementations must be safe to call from several threads. A clock is
        read by whichever thread happens to need the time, and the caller has
        no way to synchronise a dependency it was handed.

        An implementation must not call back into whatever it was injected
        into. Some callers read the clock while holding a lock, and a clock
        that re-entered the caller would put an arbitrary amount of the
        system inside that lock's critical section.
    """

    def now(self) -> datetime:
        """Return the current instant.

        Returns:
            An aware datetime in UTC. Aware because a naive one silently means
            the host's zone, and UTC because every timestamp crossing an Atlas
            boundary is normalised to it.
        """
        ...

    def monotonic(self) -> float:
        """Return a reading for measuring durations.

        Returns:
            Seconds, from an unspecified origin. Only differences between two
            readings are meaningful; the absolute value is not. The sequence
            never decreases and is unaffected by any change to :meth:`now`.
        """
        ...

    def sleep(self, seconds: float) -> None:
        """Wait for a duration.

        Args:
            seconds: How long to wait. Must not be negative. Zero returns
                immediately and is the way a caller says "no delay" without
                branching around the call.

        Returns:
            Nothing.

        Raises:
            ValueError: If ``seconds`` is negative.

        Notes:
            An implementation must leave :meth:`now` and :meth:`monotonic`
            consistent with the wait it performed: after ``sleep(n)`` both hands
            have moved by ``n``, whether that happened by waiting or by
            arithmetic. A clock whose sleep did not move its own readings would
            let a caller wait and then measure no elapsed time, which is the one
            way this port could lie about the thing it exists to model.
        """
        ...


class SystemClock:
    """The host's clock: the default, and what production runs on.

    Notes:
        Stateless, so one instance is as good as any other and sharing one
        between components costs nothing.
    """

    def now(self) -> datetime:
        """Return the host's current instant.

        Returns:
            :func:`datetime.now` in UTC.
        """
        return datetime.now(UTC)

    def monotonic(self) -> float:
        """Return the host's monotonic reading.

        Returns:
            :func:`time.monotonic`, which the standard library guarantees never
            goes backwards and which is unaffected by a system clock update.
        """
        return time.monotonic()

    def sleep(self, seconds: float) -> None:
        """Block the calling thread.

        Args:
            seconds: How long to wait. Must not be negative.

        Returns:
            Nothing.

        Raises:
            ValueError: If ``seconds`` is negative.

        Notes:
            The host's own clocks move on their own, so nothing has to be
            credited here. This is the one method on this class that a test
            must never reach: a suite that blocks for a real backoff is the
            thing :class:`ManualClock` exists to prevent.
        """
        time.sleep(_require_non_negative(seconds, "seconds"))


class ManualClock:
    """A clock that moves only when told to.

    Time starts at the instant given to the constructor and stays there until
    :meth:`advance` or :meth:`set_time` moves it. Nothing on the host is read,
    so a test built on this clock produces the same result on a loaded CI runner
    as on a laptop, and a test for a one-hour timeout takes no time to run.

    The two ways of moving it are deliberately different, and the difference is
    the point of the class:

    :meth:`advance`
        Time *passing*. Both hands move together: the instant moves forward by
        the delta and the monotonic reading by the same number of seconds.

    :meth:`set_time`
        The wall clock being *corrected* — an NTP step, an operator, a zone
        change. The instant jumps and the monotonic reading does not move at
        all, which is what a real monotonic clock does and therefore what a
        test asserting immunity to a clock step needs.

    :meth:`sleep`
        Time passing because something waited for it. Identical to
        :meth:`advance` in effect and instant in duration, which is what lets a
        test assert a retry backoff schedule as an exact final instant.

    Notes:
        Thread safe, and a leaf: nothing is called while its lock is held, so
        it cannot take part in a deadlock cycle no matter where it is read
        from. The lock exists because :meth:`advance` moves two values that
        must move together — a reader must never see the new instant beside the
        old monotonic reading.
    """

    def __init__(self, start: datetime) -> None:
        """Start a clock at an instant.

        Args:
            start: Where the clock begins. Must be timezone aware. Required
                rather than defaulted, because a default would become a second
                canonical epoch competing with whatever the caller already has.

        Raises:
            ValueError: If ``start`` is naive.
        """
        self._lock = threading.Lock()
        self._instant = _require_aware(start, "start")
        self._elapsed = 0.0

    def now(self) -> datetime:
        """Return the instant the clock is currently at.

        Returns:
            The current instant, aware and in UTC.
        """
        with self._lock:
            return self._instant

    def monotonic(self) -> float:
        """Return the seconds this clock has been advanced by.

        Returns:
            Zero at construction, and thereafter the total of every
            :meth:`advance`. A :meth:`set_time` contributes nothing.
        """
        with self._lock:
            return self._elapsed

    def advance(self, delta: timedelta) -> datetime:
        """Move time forwards.

        Args:
            delta: How far forwards. Must not be negative.

        Returns:
            The new instant.

        Raises:
            ValueError: If ``delta`` is negative. Time passing backwards is not
                a thing the clock is being asked to model — a wall clock that
                needs to move backwards is corrected with :meth:`set_time`, and
                the monotonic reading is not permitted to move backwards at all.
        """
        if delta.total_seconds() < 0:
            msg = f"delta must not be negative; got {delta!r}"
            raise ValueError(msg)
        with self._lock:
            self._instant += delta
            self._elapsed += delta.total_seconds()
            return self._instant

    def set_time(self, moment: datetime) -> None:
        """Correct the wall clock, leaving the monotonic reading alone.

        Args:
            moment: The instant to jump to, forwards or backwards. Must be
                timezone aware.

        Returns:
            Nothing.

        Raises:
            ValueError: If ``moment`` is naive.

        Notes:
            This models the clock being *wrong and then fixed*, which is why no
            elapsed time is credited. Anything measuring a duration across this
            call sees no time pass, and that is the behaviour a monotonic
            reading exists to provide.
        """
        aware = _require_aware(moment, "moment")
        with self._lock:
            self._instant = aware

    def sleep(self, seconds: float) -> None:
        """Credit a wait without performing one.

        Args:
            seconds: How long the caller believes it waited. Must not be
                negative.

        Returns:
            Nothing, and it returns straight away.

        Raises:
            ValueError: If ``seconds`` is negative.

        Notes:
            This is :meth:`advance` under another name, and that identity is
            the whole value of the method. Code under test that backs off for a
            minute and then stamps a heartbeat produces the same instants it
            would produce in production, in no time at all, so a backoff
            schedule is asserted as an exact instant rather than a tolerance.
        """
        self.advance(timedelta(seconds=_require_non_negative(seconds, "seconds")))
