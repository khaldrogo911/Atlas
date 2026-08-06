# `atlas.common`

The package every other package may import, and that may import none of them.

```python
from atlas.common import Clock, ManualClock, RetryPolicy, SystemClock, retry_call
```

---

## What belongs here

One test: **would two feature packages otherwise define it separately, and would
neither be the right owner?** Time is like that. So is retrying. Neither is a
broker idea, a strategy idea or a market-data idea, and the package that defined
one first would have owned it for everybody — which is the import the dependency
graph forbids.

What does *not* belong here is anything that encodes a domain rule. A `Symbol`,
an order side, a risk limit: those have an owner, and putting them here to avoid
choosing one is how a shared package becomes the place everything ends up.

`atlas/common/*` imports the standard library and, within the package, only
`atlas.common.clock`. Nothing else. `tests/unit/broker/test_adapter_contract.py`
asserts that from the other side: `atlas.broker` may reach `atlas.common`, and
`atlas.common` carries no Atlas dependency of its own.

---

## `clock` — what time is it, how long has it been, and waiting

*[ADR-0008](../../../../../docs/adr/0008-time-is-injected.md)*

```python
@runtime_checkable
class Clock(Protocol):
    def now(self) -> datetime: ...        # an aware UTC instant: "when"
    def monotonic(self) -> float: ...     # seconds from an unspecified origin: "how long"
    def sleep(self, seconds: float) -> None: ...
```

**Two hands, because there are two questions.** `now()` produces something that
goes into a domain model and that a person reads. `monotonic()` produces
something whose absolute value is meaningless and whose *differences* are the
only durations in the system that survive a clock correction. An implementation
must keep them independent: a wall-clock jump must not move the monotonic
reading, and the monotonic reading must never decrease.

Conflating them is the bug the port exists to prevent. A wall-clock step forward
reports a healthy session as an hour silent; a step backward makes an age
negative, which compares as fresh against every threshold and silences a
supervisor at the moment it exists for.

`sleep` is the port's only verb. It is here rather than on a separate `Sleeper`
because waiting and elapsed time are one fact, and two collaborators that must
agree about elapsed time are a bug surface.

| | `now()` | `monotonic()` | `sleep(n)` |
| --- | --- | --- | --- |
| `SystemClock` | `datetime.now(UTC)` | `time.monotonic()` | `time.sleep(n)` |
| `ManualClock` | The instant it was set to | Total of every `advance` | `advance(n)` |

`ManualClock` has two ways to move, and the asymmetry is the point.
`advance(delta)` is **time passing**: both hands move together.
`set_time(moment)` is **the wall clock being corrected** — an NTP step, an
operator, a zone change: the instant jumps, forwards or backwards, and no elapsed
time is credited at all. A test for immunity to a clock step is worth nothing
against a clock that cannot be stepped.

It takes a required start instant rather than defaulting to one, because a
default epoch in a shared package becomes a second canonical epoch competing with
whatever the caller already has.

---

## `retry` — how many attempts, how long between, which failures

*[ADR-0009](../../../../../docs/adr/0009-retry-is-a-value-and-the-waiting-is-the-clocks.md)*

A retry loop written inline is three decisions welded to one call site. Welded,
they cannot be configured, cannot be tested without provoking the failure they
exist for, and get rewritten slightly differently at the next call site. This
module takes them apart.

### `RetryPolicy` — *how many, and how long between*

A frozen value with no behaviour beyond arithmetic. It holds no clock, no
exception types and no reference to whatever is being retried, so it can be
built in a config module, compared, logged and asserted on.

```python
RetryPolicy.none()                                  # one attempt — the default
RetryPolicy.immediate(3)                            # 3 attempts, no waiting
RetryPolicy.fixed(3, 2.0)                           # waits 2s, 2s
RetryPolicy.exponential(4, 1.0)                     # waits 1s, 2s, 4s
RetryPolicy.exponential(5, 1.0, 2.0, max_delay=2.0) # waits 1s, 2s, 2s, 2s
```

`delays()` returns the whole schedule as a tuple, which is what makes
"exponential backoff progresses 1, 2, 4" a statement about a value rather than
about a run. `total_delay` is the sum — the longest the policy can spend waiting,
excluding the attempts themselves.

The constructor refuses a policy that could not mean what it says: fewer than one
attempt, a negative delay, a multiplier below one (which would *shrink* the delay
on each retry), or a ceiling below the first delay, which would make
`initial_delay` a field that is silently ignored.

**The default is no retry.** Retrying is opted into, because a policy that
retried by default would change the behaviour of code that never asked for it,
and the only symptom of a wrongly retried call is that it took longer to fail.

### `retry_call` — *which failures, and the waiting*

```python
retry_call(
    lambda: session.connect(),
    policy=policy,
    clock=clock,
    retry_on=(BrokerConnectionError,),
    give_up_on=(BrokerNotConnectedError,),
)
```

`retry_on` is a parameter because which failures are worth retrying is a fact
about a domain, and this module has none. `give_up_on` carves types back *out* of
`retry_on`, which is how a domain whose transient failures are a base class with
a permanent subclass excludes the subclass without abandoning the base.

The waiting goes through `clock.sleep`, so a test drives a hundred-second backoff
with a `ManualClock` in no time and then asserts the resulting instant exactly.
Nothing here reads the host clock or sleeps on its own, and a static scan in
`tests/unit/common/test_retry.py` asserts it — because a real sleep would leave a
manual clock exactly where the assertions expect it, and pass.

The final attempt is not wrapped, so the caller sees the failure it would have
seen without any retrying, from the last attempt rather than the first, and never
a wrapper type.

**Idempotence is the caller's judgement.** `retry_call` re-invokes a callable it
was handed; whether repeating that is *safe* is a question about the far end that
this module cannot answer. `BaseBrokerAdapter` wraps only `connect` and
`reconnect` for exactly that reason.

### Deliberately absent

- **Jitter.** The right answer to a thundering herd, and it needs a randomness
  port injected the way the clock is. Until something in Atlas has enough
  concurrent clients for a herd to exist, adding it trades an exactly
  reproducible schedule for a hypothetical property.
- **A budget or deadline.** A different policy shape; `total_delay` approximates
  it.
- **Logging and callbacks.** Atlas has no logging port yet, and inventing one
  inside a retry module would put it in the wrong package.

---

## Using it

Both are injected, keyword-only, and default to something that behaves the way
the code did before they existed:

```python
class MyAdapter(BaseBrokerAdapter):
    def __init__(self, *, clock: Clock | None = None, retry: RetryPolicy | None = None) -> None:
        super().__init__(clock=clock, retry=retry)   # SystemClock, RetryPolicy.none()
```

In a test, pass a `ManualClock` and assert the instant:

```python
clock = ManualClock(datetime(2020, 1, 1, tzinfo=UTC))
adapter = MyAdapter(clock=clock, retry=RetryPolicy.exponential(4, 1.0))

with pytest.raises(BrokerConnectionError):
    adapter.connect()

assert clock.now() == datetime(2020, 1, 1, 0, 0, 7, tzinfo=UTC)   # 1 + 2 + 4
```

Do not reach for `datetime.now`, `time.monotonic` or `time.sleep` in a package
that has a clock available. `tests/unit/broker/test_adapter_heartbeat.py` scans
`atlas.broker` for exactly that and fails the run.
