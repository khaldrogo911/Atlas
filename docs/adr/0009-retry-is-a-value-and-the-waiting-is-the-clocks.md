# ADR 0009 — Retrying is a value, and the waiting belongs to the clock

**Status:** Accepted
**Date:** 2026-08-06

## Context

A venue connection fails in two ways that look identical at the call site and
are not. The socket dropped, the terminal was mid-restart, the trade server was
briefly unreachable — try again in a moment and it works. Or the credentials are
wrong, the account is disabled, the build is too old — try again forever and it
never works. `BaseBrokerAdapter` treated both the same way: it raised, and every
caller was left to decide what to do about it.

Which means the decision was about to be made several times. A supervision loop
would grow a `for` loop with a `time.sleep` in it. So would whatever starts the
process. So would the market data package when it acquires a session of its own.
Each of those is three decisions welded to one call site — how many attempts,
how long between them, which failures are worth another go — and welded together
they cannot be configured, cannot be tested without provoking the failure they
exist for, and get rewritten slightly differently every time.

The exception hierarchy was already built for this and nothing was reading it.
ATLAS-TASK-0005 put `BrokerAuthenticationError` *outside* `BrokerConnectionError`
specifically so that a supervision loop retrying connection faults could not
swallow a credential that will never work, and `docs/ROADMAP.md` has recorded
that placement as load-bearing since. The tree draws the line. Nothing consulted
it.

ATLAS-TASK-0009 removed the last reason not to do this. Before a `Clock` port
existed, any backoff was a real `time.sleep`, and a test for a three-attempt
exponential schedule either slept for seven seconds or did not test the
schedule.

## Decision

**A `RetryPolicy` value in `atlas.common`, executed by a `retry_call` that waits
on an injected `Clock`, wired into `BaseBrokerAdapter` and nowhere else.**

```python
@dataclass(frozen=True, slots=True)
class RetryPolicy:
    max_attempts: int = 1
    initial_delay: float = 0.0
    multiplier: float = 1.0
    max_delay: float | None = None
```

### The three welded decisions, taken apart

`RetryPolicy` is *how many, and how long between*. It holds no clock, no
exception types, no reference to whatever is being retried, and nothing about
brokers. `retry_call` is *which failures, and the waiting*. Splitting them is
what makes `delays()` possible — the whole schedule as a tuple — so "exponential
backoff progresses 1, 2, 4" is a statement about a value that can be asserted
without provoking a single failure. A schedule observable only by failing is a
schedule testable only by failing.

The named constructors — `none()`, `immediate(n)`, `fixed(n, d)`,
`exponential(n, d, mult, max_delay)` — are the four shapes anyone actually
wants, spelled so that a configuration file reads as an intent rather than as
four numbers.

`__post_init__` rejects a policy that could not mean what it says: fewer than one
attempt, a negative delay, a multiplier below one (which would *shrink* the
delay on each retry, inverting the reason backoff exists), or a ceiling below the
first delay (legal arithmetic, but it makes `initial_delay` a field that is
silently ignored).

### The default is one attempt

`RetryPolicy()` is one attempt with no delay: exactly what every caller got
before this class existed. Retrying is opted into. A policy that retried by
default would change the behaviour of code that never asked for it, and would do
so invisibly — the only symptom of a wrongly retried call is that it took longer
to fail. This is also what makes the regression half of the test suite writable
at all: every pre-existing behaviour is reachable by passing nothing.

### The waiting goes through `Clock`

`Clock` gained a third member, `sleep(seconds)`, alongside the two readings from
ADR-0008. It is the port's only *verb*: `now()` and `monotonic()` report, `sleep`
acts.

It belongs on the same object rather than on a separate `Sleeper` port because
waiting and elapsed time are one fact. `ManualClock.sleep(n)` is exactly
`advance(n)` — after it, both hands have moved by `n` — so a test drives a
hundred-second backoff instantly and then asserts the resulting instant
*exactly*. Two collaborators that must agree about elapsed time and are injected
separately are a bug surface, and the bug is a test that passes while measuring
nothing.

### Which failures, read off the tree rather than listed

```python
RETRYABLE_ERRORS = (BrokerConnectionError,)
PERMANENT_ERRORS = (BrokerNotConnectedError,)
```

Two entries, in `base.py`, because *which failures are transient* is a fact about
brokers and `atlas.common` has no brokers in it. `retry_call` takes both as
parameters and holds no opinion.

`BrokerAuthenticationError` needs no entry: it is deliberately not a
`BrokerConnectionError`, so it already propagates. A list naming every permanent
error would need editing every time the hierarchy grew, and the hierarchy is
where that information already lives. `BrokerNotConnectedError` is the one
carve-out — it *is* inside the retryable branch, and it means "there is no
session", which is fixed by acting rather than by waiting.

`BrokerTimeoutError` is retried, because it is inside `BrokerConnectionError`.
That is correct for the two methods a policy actually reaches. It would not be
correct for an order submission, which is why nothing but the lifecycle is
wrapped — a timeout on a state-changing call means the request may have been
executed, and every such method already documents reconciliation rather than
retry.

### Integrated into the base, and into nothing else

`connect` and `reconnect` route their subclass hook through `_with_retry`.
`disconnect` does not. Neither adapter names a policy, implements a loop, or
gained a line: `MockBrokerAdapter` and `MT5BrokerAdapter` accept a keyword and
pass it to `super().__init__`, exactly as they did for the clock. The public
`BrokerAdapter` port is untouched — `connect`, `disconnect` and `reconnect` still
take nothing but `self`, so no call site anywhere changes.

`disconnect` is excluded on purpose. It is a cleanup path that the port forbids
from raising, and cleanup that retries is cleanup that hangs.

### Attempts do not multiply

Both adapters compose `_reconnect` out of the public `disconnect` and `connect`
— the shape ADR-0007 made safe by choosing a re-entrant session lock. Applied
naively, a policy would then run at both entry points and a three-attempt
reconnect would make nine round trips, tearing the terminal down nine times.

A `_retrying` flag suppresses the inner policy for the duration of one lifecycle
call. It is a plain boolean with no lock of its own, because it is read and
written only under the re-entrant session lock — the same lock the outer call
already holds — and it is cleared in a `finally`, so a failure leaves nothing
armed.

### The backoff waits inside the session lock

This is the cost being accepted, and it is accepted for ADR-0007's reason: a
reconnect is one critical section, not several. Releasing the lock between
attempts would let another thread observe, and act on, a half-replaced session
between the teardown and the successful attempt.

So a lifecycle call from a second thread waits out the whole backoff. What bounds
that is the other half of ADR-0007's contract, which is unchanged: `health()`,
`is_connected()` and `heartbeat_age()` take no session lock, so a supervisor
still answers throughout — asserted from another thread, mid-backoff, against the
real retry loop rather than against a lock held by hand.

No new lock is introduced. The lock order is the one ADR-0007 fixed.

### `RetryPolicy` lives in `atlas.common`, not in `atlas.broker`

The same argument ADR-0007 used for locking. Market data, execution and
notification will each want to retry something, and a policy defined in the
broker package would either be imported upward — which the architecture forbids
— or written again. `atlas/common/retry.py` imports the standard library and
`atlas.common.clock`, and nothing else. The `broker → common` edge already
exists; this adds no new one.

## Consequences

### Guaranteed

- **Nothing retries unless it was told to.** Both adapters default to
  `RetryPolicy.none()`, a subclass calling `super().__init__()` with no arguments
  still works, and every behaviour that existed before this task is reachable by
  passing nothing.
- **The schedule an operator configures is the schedule the venue sees.**
  Asserted as exact attempt instants — `0, 1, 3, 7` for `exponential(4, 1.0)` —
  on both adapters, through two entirely unrelated failure mechanisms.
- **No test sleeps.** A seven-second backoff and a five-minute one cost the same
  and run instantly. A static scan asserts `atlas/common/retry.py` contains no
  call to `time.sleep` or to the host clock, because a real sleep would leave the
  manual clock exactly where the assertions expect it and pass anyway.
- **A permanent failure fails at the first attempt.** A refused login raises
  immediately and advances the clock by nothing, under a policy that provably
  retries a transient failure — the control is asserted alongside.
- **A retried reconnect makes the policy's attempts, not their square.**
- **The caller sees the failure it always saw.** The last attempt's exception
  propagates unwrapped and untyped-over. A retry policy is not a reason to change
  what a failure is called.
- **Supervision still answers mid-backoff**, from another thread, while the
  session lock is provably held — both halves asserted, because either alone
  would be satisfied by an adapter holding no locks.

### Not guaranteed, deliberately

- **Nothing decides to reconnect.** A policy governs an attempt that a caller
  makes. Noticing a session has gone quiet and deciding to replace it is the
  supervision layer's job, and it still does not exist.
- **No jitter.** Randomised backoff is the right answer to a thundering herd and
  would need a randomness port injected the way the clock is. Until something in
  Atlas has enough concurrent clients for a herd to exist, adding it trades a real
  property — an exactly reproducible schedule — for a hypothetical one.
- **No budget or deadline.** "Give up after thirty seconds regardless" is a
  different policy shape. `total_delay` lets a caller approximate it.
- **Nothing is logged.** Atlas has no logging port; inventing one inside a retry
  module would put it in the wrong package.
- **Idempotence is the caller's judgement.** `retry_call` re-invokes a callable
  it was handed. Whether repeating that is *safe* is why only the lifecycle is
  wrapped.
- **`RetryPolicy` is not configuration yet.** Nothing in `atlas.config` builds
  one. It is constructed by whoever constructs the adapter.

### Costs

- **A lifecycle call from a second thread now waits out the backoff.** Bounded by
  supervision never taking the session lock, and by the default being no retry at
  all, but real.
- **`Clock` implementations gained a method.** Any third implementation must
  supply `sleep`, and must keep the invariant that after `sleep(n)` both hands
  have moved by `n` — which `ManualClock` gets by delegating to `advance`.
- **`_retrying` is mutable state on the adapter.** It is correct only because the
  session lock is re-entrant and held across every read and write of it. That is
  a coupling between two decisions, and it is why the flag is documented in
  `base.py` rather than only named.
- **An adapter author has one more thing to know:** a lifecycle hook is *one
  attempt*, must be safe to call again, and must leave the session in a state the
  next attempt can start from. Both adapters' hook docstrings now say so.

## Alternatives considered

**A `Sleeper` port separate from `Clock`.** Rejected. Waiting and elapsed time
are one fact, and two objects that must agree about it are a bug surface: a test
could sleep on one and assert on the other and measure nothing at all. The
requirement was that all timing be deterministic through the injected clock, and
one object is the only way to mean that.

**A retry decorator on the hook methods.** Rejected. It applies the policy where
the subclass is, so it would run once in `_reconnect` and once again in the
`connect` that `_reconnect` calls — the attempts-squared bug, with no single
place to suppress it. It also puts the policy outside the session lock, or
requires each subclass to think about which.

**Retry in the `BrokerAdapter` port.** Rejected on ADR-0008's grounds. 31 methods
are pinned by conformance tests and implemented by every adapter including
third-party ones; widening the contract for something the base can give all of
them for free is a breaking change that buys no capability.

**A per-adapter policy, or a policy argument on `connect()`.** Rejected. A
parameter changes the port's signature and therefore every implementation. A
policy chosen per call is a policy nobody can configure centrally, and the
question "how does this deployment treat a flaky venue" stops having one answer.

**A predicate — `should_retry: Callable[[Exception], bool]` — instead of
exception tuples.** Rejected. It is more expressive and strictly less checkable:
an exception tuple is a value a test can compare, and the fact that
`BrokerAuthenticationError` is not retried becomes a statement about the class
hierarchy rather than about a lambda someone wrote.

**A list of every permanent error class.** Rejected. It duplicates what the
hierarchy already encodes and needs editing every time the hierarchy grows.
`BrokerNotConnectedError` is the single carve-out precisely because it is the
single case the tree gets wrong for this purpose.

**Retry `disconnect` too, for symmetry.** Rejected. It is a cleanup path the port
forbids from raising, and a cleanup path that retries is a shutdown that hangs.

**Release the session lock between attempts.** Rejected. It would let another
thread see and act on a half-replaced session, which is exactly the state
ADR-0007's one-critical-section rule exists to make unobservable.

**Retry by default, with `RetryPolicy.none()` to opt out.** Rejected. It changes
the behaviour of every existing caller invisibly — the only symptom of a wrongly
retried call is that it took longer to fail — and it would make the regression
tests in this task impossible to write, because there would be no way to ask for
the old behaviour without editing every construction site.
