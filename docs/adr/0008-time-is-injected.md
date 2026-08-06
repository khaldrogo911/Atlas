# ADR 0008 — Time is injected, and it has two hands

**Status:** Accepted
**Date:** 2026-08-06

## Context

Three modules read the clock, and no two of them read it the same way.
`MT5BrokerAdapter._now` called `datetime.now(UTC)` directly. `MockVenue` held a
private instant it moved by hand. `BaseBrokerAdapter` stamped a heartbeat with
whatever instant the caller passed it and never asked what a heartbeat was for.
ATLAS-TASK-0007 looked at that divergence, decided it was a real venue-specific
difference rather than an accident, and left it in place; ATLAS-TASK-0008 noted
that a clock abstraction was the next thing the design would want.

It is wanted for a reason that is about to become load-bearing. A supervisor's
whole job is deciding that a venue has gone quiet, and the port's own docstring
declined to say when that is — `adapter.py` records that it deliberately imposes
no freshness policy. The policy belongs above the port, but the *measurement*
does not, and there was nothing to measure with: `Connection.last_heartbeat` says
when, and nothing anywhere said how long ago.

Writing that measurement with a wall clock has two failure modes, and the second
is the dangerous one:

1. **A forward step reports a healthy session as dead.** An NTP correction or a
   daylight-saving transition moves the wall clock by an amount unrelated to
   elapsed time. Subtracting two wall readings across one shows an hour of
   silence from a venue that answered a second ago, and a supervisor that
   reconnects on that signal tears down a working session.
2. **A backward step reports a dead session as healthy.** The same correction in
   the other direction makes the age negative, which compares as fresh against
   any threshold. The supervisor goes quiet at exactly the moment it exists for.

Testing it with a wall clock has one failure mode that covers everything: a test
for a one-hour timeout either waits an hour or does not test the timeout.
`tests/unit/broker/mt5/test_mt5_adapter.py` had already reached for the available
workaround and monkeypatched `MT5BrokerAdapter._now` to a constant — which works,
and is a test asserting against a patched private method rather than against the
adapter's own dependencies.

## Decision

**A `Clock` port in `atlas.common`, with two methods, injected into
`BaseBrokerAdapter` and used for heartbeat age.**

```python
@runtime_checkable
class Clock(Protocol):
    def now(self) -> datetime: ...       # an aware UTC instant: "when"
    def monotonic(self) -> float: ...    # seconds from an unspecified origin: "how long"
```

### Two hands, because they answer two questions

`now()` produces something that goes into a domain model, gets compared against a
venue's own timestamp and is read by a person. `monotonic()` produces something
whose absolute value is meaningless and whose *differences* are the only durations
in the system that survive a clock correction. An implementation is required to
keep them independent: a wall-clock jump must not move the monotonic reading, and
the monotonic reading must never decrease.

One method would have been smaller and wrong. A clock offering only `now()` puts
every duration back on the wall clock, which is the bug. A clock offering only
`monotonic()` cannot stamp a `Connection`.

### A `Protocol`, not an abstract base

Nothing needs to inherit from it, and a caller supplying a clock should not have
to import Atlas to do so. `runtime_checkable` is there for the tests that assert
an implementation satisfies the shape; it checks method presence only, which is
all a structural assertion can honestly claim.

### It lives in `atlas.common`

`docs/architecture/overview.md` has assigned the clock to `common` since
ATLAS-TASK-0001, and `common` is the one package every other package may import.
This is the first time anything has taken that dependency, so it is also the
first test of the rule. `atlas/common/clock.py` imports the standard library and
nothing else.

### Two implementations, and the difference between them is the point

| | `now()` | `monotonic()` |
| --- | --- | --- |
| `SystemClock` | `datetime.now(UTC)` | `time.monotonic()` |
| `ManualClock` | The instant it was set to | Total of every `advance` |

`ManualClock.advance(delta)` is **time passing**: both hands move together.
`ManualClock.set_time(moment)` is **the wall clock being corrected**: the instant
jumps, forwards or backwards, and no elapsed time is credited at all. That
asymmetry is not a convenience — it is the only way a test can produce a clock
step, and a clock step is the thing the monotonic hand exists to be immune to.

`ManualClock` takes a required start instant rather than defaulting to one,
because a default epoch in a shared package becomes a second canonical epoch
competing with whatever the caller already has.

### Injection is keyword-only, optional, and defaults to the host

```python
def __init__(self, *, clock: Clock | None = None) -> None:
    self._clock: Clock = SystemClock() if clock is None else clock
```

Every existing `super().__init__()` in a subclass keeps working and keeps meaning
what it meant. `MT5BrokerAdapter` passes one through; construct it without a clock
and it runs on the host, which is what production does. `MockBrokerAdapter`
deliberately accepts **no** clock parameter: it takes its venue's, because a mock
holding a clock that its venue does not is how a deterministic test stops being
deterministic.

### The measurement, and where the policy is not

`BaseBrokerAdapter` gained exactly two methods:

- `heartbeat_age() -> timedelta | None` — the monotonic difference since the last
  heartbeat, or `None` if the venue has never been heard from.
- `is_heartbeat_fresh(within: timedelta) -> bool` — that age against a threshold
  the **caller** supplies, inclusive at the boundary, and `False` when there is no
  heartbeat at all.

No threshold is stored. Nothing schedules, retries, reconnects or logs. An
adapter that remembered a freshness window would be answering a question that
belongs to the supervisor above it, and two callers with different tolerances
could not both be right.

They are added to `BaseBrokerAdapter` and **not** to the `BrokerAdapter` port.
The port is 31 pinned methods that a replay engine and a third-party adapter
implement in full; widening it for a convenience that the base can provide to
every subclass for free would be a breaking change to every implementation, in
service of no new capability.

### The lock rules from ADR-0007 still hold, and they constrain this

The clock is read **before** the readings lock is taken, never under it — in
`_record_heartbeat`, in `_record_latency` and in `heartbeat_age`. A clock arrives
from outside the package and may be anything; calling one while holding the lock
would put an arbitrary amount of foreign code inside the critical section whose
freedom from cycles ADR-0007 establishes structurally. The readings lock stays a
leaf. Neither new method touches the session lock, so supervision is still never
blocked.

## Consequences

### Guaranteed

- **A wall-clock correction cannot change a heartbeat's age.** Stepping the clock
  a day forward or a day back leaves the age exactly where it was, in both
  directions, on both adapters.
- **A timeout is tested by asserting an exact `timedelta`.** A test for a
  365-day silence advances 365 days and costs nothing. No test in the suite
  sleeps for a clock.
- **Both adapters answer identically.** `tests/unit/broker/test_adapter_heartbeat.py`
  runs one sequence against every discovered adapter and asserts that a third one
  is covered from the moment it exists.
- **Production still reads the host.** `MT5BrokerAdapter` built without a clock
  gets a `SystemClock`, and `SystemClock.monotonic` is `time.monotonic` — asserted,
  because a wall-clock timestamp would satisfy every other property a monotonic
  reading has.
- **External behaviour is unchanged.** The port is untouched, `health()` returns
  what it returned, and `Connection.last_heartbeat` is still stamped from the same
  instant it was stamped from before.

### Not guaranteed, deliberately

- **Nothing acts on staleness.** These are two questions with answers. Who asks
  them, how often, and what a stale answer costs are all decisions for the
  supervision layer, which does not exist yet.
- **The two hands are not related by any offset.** `monotonic()` is not the number
  of seconds since `now()`'s epoch and no arithmetic between them means anything.
- **`SystemClock` inherits the host's resolution.** Two calls close together may
  return the same reading. Code that requires distinct readings is measuring
  something too small for this port.
- **`Clock` says nothing about time zones beyond UTC.** Converting to a venue's
  local time is `ServerClock`'s job in the MT5 package, which is a timezone
  translator and not a source of time. The two are unrelated despite the name.

### Costs

- `atlas.broker` now depends on `atlas.common`. That is one new edge in the
  import graph, in the permitted direction, and
  `tests/unit/broker/test_adapter_contract.py` was widened from "imports nothing
  but `atlas.broker`" to name `atlas.common` explicitly — with three added tests
  proving the widened rule still refuses `atlas.risk`, `atlas.execution`,
  `atlas.strategy` and `atlas.config`, and that `atlas.common` carries no Atlas
  dependency of its own.
- A `ManualClock` acquires a lock on every read. It is a leaf and the cost is
  nanoseconds, but it is a lock in a test double, and it exists because `advance`
  moves two values that a reader must never see disagree.
- An adapter author has one more thing to know: stamp instants from `self._clock`,
  not from `datetime.now`. A test asserts that no module in `atlas.broker` calls
  the latter.

## Alternatives considered

**Keep patching `datetime.now` in tests.** Rejected. It is a global mutation with
a blast radius of the whole interpreter, it cannot express two components at two
different times, and — as it was actually being used here — it patched a private
method, so the test passed for an implementation the production path did not have.

**One method: `now()` only.** Rejected. It is the smaller port and it reintroduces
the bug: every duration in the system goes back on the wall clock, and the
backward-step case turns a dead session fresh. The whole reason for this ADR is
that "what time is it" and "how long has it been" are different questions.

**A module-level `clock` singleton that tests replace.** Rejected. It is a global,
so two adapters cannot be at two different times, and a test that forgets to
restore it fails a later, unrelated test. Injection makes the dependency visible
in the constructor signature, which is where a reader looks for it.

**Freeze time with a third-party library.** Rejected on the same grounds as any
new dependency in this repository, and on a stronger one: a library that patches
`datetime` globally makes the production code look like it reads the clock
directly, which means the design never gets fixed — the tests just stop noticing.

**Put `heartbeat_age` on the `BrokerAdapter` port.** Rejected. 31 methods are
pinned by conformance tests and implemented by every adapter; adding a 32nd for
something the base can give all of them for free breaks every implementation,
including third-party ones, and buys nothing.

**Let the adapter own a freshness threshold and expose `is_stale()`.** Rejected.
It is a policy, it differs per caller — a risk thread and a dashboard do not agree
on what "too quiet" means — and an adapter that held one would be making a
supervision decision from inside the transport layer.

**Have `set_time` also credit elapsed time.** Rejected, and this is the decision
the class turns on. It would make `ManualClock` a clock whose monotonic hand
follows its wall hand, which is precisely the implementation the port forbids —
and it would make the tests for clock-step immunity pass against a clock that has
no such immunity.

**Give `MockBrokerAdapter` a `clock` parameter for symmetry with MT5.** Rejected.
Two clocks in one deterministic test double is one clock too many: heartbeats
stamped in venue time and aged against a second source produce an age that depends
on how long the test took to run, which is the property the mock exists to not
have.
