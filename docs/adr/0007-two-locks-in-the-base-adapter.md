# ADR 0007 — Two locks in the base adapter, and none below it

**Status:** Accepted
**Date:** 2026-08-06

## Context

`atlas.broker.adapter.BrokerAdapter` already promised, in prose, that an adapter
tolerates calls from several threads. Nothing implemented the promise. Both
adapters mutated session state — a `ConnectionState`, a cached brokerage name, a
last latency, a last heartbeat — with no synchronisation at all, and ATLAS-TASK-0007
recorded thread safety as the next architectural concern precisely because the
refactor that produced `BaseBrokerAdapter` put all of that state in one place for
the first time.

The promise is not decorative. The system it is being built for has at least
three threads that will hold the same adapter:

- a **strategy** thread reading quotes and placing orders,
- a **risk** thread reading the account and open positions,
- a **supervisor** thread asking `health()` on a timer and calling `reconnect()`
  when the answer stops being reassuring.

The third is the hard one. A supervisor exists to notice that the venue has
stopped answering; if its `health()` call queues behind the very connect attempt
that is stuck, the supervisor goes silent at the only moment it was built for.
Any locking scheme that treats the adapter as one critical section fails that
requirement, however correct it is about state.

Three further facts about the code constrained the design rather than being
consequences of it:

1. **Both adapters compose `reconnect` out of the *public* `disconnect` and
   `connect`.** That is the obvious way to write it and it re-enters whatever
   lock those methods take.
2. **A venue is remote.** Orders, positions, quotes and fills live on a server in
   another process, frequently on another continent. No lock in this process
   makes a sequence of requests atomic there, so a lock that pretends otherwise
   is worse than none: it costs contention and buys a guarantee that is false.
3. **Subscription handlers are user code.** They are invoked by the venue on the
   publishing thread, and a handler that decides to call `disconnect()` is a
   reasonable thing to write.

## Decision

**Two locks, both owned by `BaseBrokerAdapter`, created in its `__init__`, and
never mentioned in a subclass.**

| Lock | Kind | Guards | Held across |
| --- | --- | --- | --- |
| `_session_lock` | `threading.RLock` | The session lifecycle | The whole venue round trip |
| `_readings_lock` | `threading.Lock` | `_last_latency_ms`, `_last_heartbeat` | Nothing — two assignments |

### The session lock

`connect`, `disconnect` and `reconnect` are the base class's own methods now.
Each takes `_session_lock` and delegates to an abstract `_connect`, `_disconnect`
or `_reconnect` that the subclass supplies and that runs with the lock held. The
lock spans the venue call, not merely the bookkeeping after it, because a
half-built session — a terminal started but not yet logged in, a state moved but
a brokerage name not yet cached — is exactly what a second thread must not
observe or interleave with.

It is **re-entrant on purpose**, not defensively. Fact 1 above means the second
acquisition happens on every reconnect in both adapters; a plain `Lock` would
make the standard way of writing `_reconnect` a self-deadlock, discovered by
whoever writes the third adapter, in production, at the moment a session needed
replacing.

The outer acquisition in `reconnect` is **load-bearing, not redundant**, and this
is the least obvious claim in the design. Because each half takes the lock on its
own account, a reconnect looks synchronised even with the outer hold removed —
the halves still never overlap. What the outer hold buys is that the *pair* is
indivisible. The two adapters differ in how much of that they would survive
losing: `MockBrokerAdapter` reaches its venue through the private `_establish`,
so nothing but the outer hold covers its establishing half at all, while
`MT5BrokerAdapter` goes through the public `connect`, which re-takes the lock and
incidentally covers it. Neither is safe without it: a competing `disconnect`
landing between the halves is silently undone by the reconnect that follows it,
leaving a session live that the caller had explicitly closed. This was not
reasoned out in advance — removing the lock from `reconnect` alone survived the
first mutation campaign, and the tests that now kill it assert the hold *depth*
rather than the absence of overlap.

### The readings lock

The latency and the heartbeat are written as a pair by `_record_latency` and read
as a pair by `_connection`. A separate lock keeps that pair coherent without
putting `health()` behind a connect. It is a **leaf**: nothing is called while it
is held. `_connection` copies the two values under the lock and constructs the
`Connection` model outside it.

### Lock order

**Session, then readings. Never the reverse.** With exactly one ordered pair and
a leaf at the bottom, the wait-for graph has no cycle, so there is no deadlock to
argue about — the property is structural rather than reviewed.

### What takes no lock

`health()` and `is_connected()` read the state through the subclass's
`_session_state` property, which is contractually a plain attribute read, and
then take only the readings lock. **A supervision thread is never blocked by an
in-flight lifecycle call.**

Every other port method — all twenty-six of them — takes no lock at all. Adapters
are not made single-threaded, and the strategy thread's quote read does not queue
behind the risk thread's account query.

### One ordering rule inside `_disconnect`

Both adapters clear the cached readings *before* taking the session down. Single
threaded the order is unobservable; concurrently it closes the window in which a
racing `health()` returns "no session — and here is its latency", a snapshot that
is internally contradictory and would be read as a live venue by anything
scanning for one. It is a write-ordering fix rather than a third lock.

## Consequences

### Guaranteed

- **Lifecycle calls are mutually exclusive per adapter.** No two threads are ever
  inside `connect`, `disconnect` or `reconnect` on the same adapter.
- **The lifecycle is atomic to the venue round trip.** A second thread never sees
  a session that is half established or half torn down.
- **A reconnect is one critical section, not two.** No lifecycle call from another
  thread is applied between its teardown and its re-establishment.
- **`health()` and `is_connected()` always answer**, including while a connect is
  parked in an unresponsive terminal. This is asserted against the real connect
  path in `tests/unit/broker/test_adapter_concurrency.py`, not against a lock held
  by hand.
- **`health()` never returns a torn snapshot.** The state, the latency and the
  heartbeat in one `Connection` are mutually consistent.
- **No adapter lock is held while user code runs.** A subscription handler may
  call any port method, including `disconnect()` and `reconnect()`, without
  deadlocking.
- **Repeated and concurrent connect/disconnect cycles leave the adapter usable.**
- **Locks are per instance.** Two adapters at two venues never contend.

### Not guaranteed, deliberately

- **A request racing a lifecycle change may fail.** It fails with
  `BrokerNotConnectedError`, or with whatever the venue produces for a request on
  a closing session — both already inside that method's documented `Raises:`
  contract. What it does not do is return a wrong answer or raise something
  undeclared.
- **"Check then act" is not atomic and cannot be made so from inside an adapter.**
  A caller that must not lose a request has to sequence its own lifecycle calls.
  This is a property of a remote venue, not a gap in the implementation.
- **Requests are not ordered against each other.** The MetaTrader 5 Python API is
  a single IPC channel with its own ordering; Atlas does not add a second one on
  top of it.
- **`MockVenue` is not thread-safe.** It has no lock and mints identifiers with a
  non-atomic read-modify-write. One venue shared between two adapters driven from
  two threads is outside everything above. It is a test double for a remote
  server, and a remote server is not something this process could lock either.
- **Nothing is guaranteed across adapters.** There is no global broker lock, and
  no ordering between two adapters is implied.

### Costs

- Every lifecycle call pays an uncontended lock acquisition, and every `health()`
  pays one on a leaf lock. Both are nanoseconds and neither is on a hot path.
- A subclass author now has a rule to know: `_session_state`, `_session_broker`
  and `_session_server` must be plain attribute reads, because they are read
  without the session lock. This is documented on each abstract member.
- The public `connect`/`disconnect`/`reconnect` are now final in practice. A
  subclass that overrode one would silently skip the lock, so
  `tests/unit/broker/test_base_adapter.py` asserts that no discovered adapter
  defines any of the three.

## Alternatives considered

**One lock around every port method.** Rejected, and it is the alternative that
looks safest. It makes an adapter single-threaded: the strategy thread's quote
read queues behind the risk thread's account query, and — fatally — the
supervisor's `health()` queues behind the stuck connect it exists to detect. It
also buys less than it appears to, because fact 2 means it cannot make a sequence
of venue operations atomic anyway. Maximum contention for a guarantee that stops
at the process boundary.

**A lock per method, or per piece of state.** Rejected. More locks means more
orderings, and the deadlock argument stops being structural. The state that
actually needs guarding is two fields and one lifecycle; two locks with one
ordered pair is the smallest arrangement that covers it.

**A lock inside each adapter.** Rejected on the task's own "avoid duplicated
locking logic", and on evidence: the two adapters had already independently grown
the same four pieces of session state, which is what ATLAS-TASK-0007 consolidated.
Locking would have been the same duplication one layer down, drifting the first
time one adapter's author thought harder than the other's. A structural assertion
now enforces it — exactly one module in `atlas.broker` imports `threading`, and it
is `base.py`.

**A re-entrant lock everywhere, including the readings.** Rejected. `RLock` is
slower and, more importantly, a re-entrant leaf lock hides the very mistake the
leaf property exists to prevent: someone calling out from under it. A plain
`Lock` deadlocks loudly if the leaf ever stops being a leaf.

**Lock-free: an atomic state field and volatile reads.** Rejected. Python offers
no memory model to reason with, and the invariant is not "one field is read
consistently" but "a state change and a venue round trip happen together". That
is a critical section, not an atomic write.

**Make `MockVenue` thread-safe.** Rejected, for now and on purpose. It would
imply a guarantee the real venue cannot honour, and a test suite that only passes
because the double is stricter than the thing it doubles is testing the double.
The limitation is documented in `mock/adapter.py` and above instead.

**`asyncio` and a single-threaded event loop.** Rejected — out of scope, and
already excluded by ATLAS-TASK-0003's "do not use async". Recorded here because it
is the honest answer to "why lock at all", and because the port's synchronous
shape is what makes the locking necessary.

**Copy-on-write session snapshots instead of a lock.** Rejected. It solves
reading and not the part that needed solving: two threads must not both run a
connect, and an immutable snapshot does nothing about that.
