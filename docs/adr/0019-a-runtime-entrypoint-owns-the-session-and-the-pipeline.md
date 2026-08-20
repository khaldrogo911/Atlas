# ADR 0019 — `atlas-core` gains a runtime entrypoint; the runtime owns the session, the loop and the pipeline

**Status:** Accepted
**Date:** 2026-08-16

## Context

ADR-0018 deferred the long-lived runtime and process shape and refused to let it
arrive by implementation. It named ten questions the next record must answer,
described four non-exhaustive options without ranking them, and stated that
"the next *record* is the one that answers the ten questions, and it is a
prerequisite for the work this one defers rather than a consequence of it".

That record is this one. The owner has taken the decision, and this record
writes it down, settles what mechanically follows, and states what
implementation may not decide by implication.

The gate was worth holding. Everything downstream sat behind it, and still does
until this record is implemented: `atlas.market`, `atlas.features` and
`atlas.regime` are empty importable units, so nothing produces a strategy input;
`TradeIntent` is defined in `atlas.risk` and constructed nowhere else in the
source tree; `ExecutionPolicy` is supplied per call and nothing stores one; and
seven `BrokerAdapter` methods on the MetaTrader 5 adapter raise
`NotImplementedError`, including every trading verb. None of that changes
because this record exists. What changes is that the shape those pieces attach
to is now decided rather than open.

Two facts about the repository shaped the decision and are recorded here because
the decision is not intelligible without them.

**The MetaTrader 5 API is poll-only.** The adapter states it where
`subscribe_ticks` raises: the API "registers no callbacks and opens no push
channel", and Atlas "can synthesise it by polling `symbol_info_tick` on its own
thread, but that means owning a scheduler, a change-detection rule and a
backpressure policy". A push-based runtime was never available to choose.
Polling is not a preference in this record; it is the only shape the venue
offers.

**The broker substrate is built for threads, not for `asyncio`.**
`packages/broker/src/atlas/broker/base.py` opens by stating that the port
"requires an adapter to tolerate calls from several threads: a strategy thread
reading quotes while a risk thread queries the account is the normal case", and
implements that with the two locks ADR-0007 fixed, in the order ADR-0007 fixed
them. There is no `asyncio`, no `async def` and no `await` anywhere in
`apps/` or `packages/`. A runtime that chose `asyncio` would be redesigning
ADR-0007 rather than building on it.

## Decision

**`atlas-core` gains a second entrypoint. The existing entrypoint remains the
one-shot startup and deployment verification path ADR-0017 decided. The new
runtime entrypoint composes and owns a `BrokerOwner`, holds one broker session
for the life of the runtime process, owns application-level supervision and
recovery, and owns the market → strategy → risk → execution orchestration. It is
synchronous and thread-based. No fourth application is created.**

This record establishes the target runtime architecture and authorises
subsequent implementation of it. It does not implement it, and it creates no
task.

### The runtime shape

One application, `atlas-core`, with two entrypoints:

| Entrypoint | Governed by | Lifetime | Purpose |
|---|---|---|---|
| Verification | ADR-0017 | One `main()` call | Startup and deployment connectivity check |
| Runtime | this record | Until shutdown | Holds a session and runs the pipeline |

Both live in the `atlas.apps.core` package and share `composition.py`. The
verification entrypoint keeps its exit-code surface, its unconditional stop, its
single thread and its single connection attempt, all exactly as ADR-0017 decided
them. Nothing about it is changed by this record.

**No fourth application is created**, and neither `apps/dashboard` nor
`apps/research` is granted anything.

### Session ownership and lifecycle

**`BrokerOwner` owns the broker session, and remains the session boundary.** It
is not turned into the pipeline, not turned into a supervisor, and not given a
new responsibility by this record. The runtime entrypoint composes one through
the existing `build_broker_owner`, holds it, and is the only thing that
sequences its transitions.

One runtime process owns one broker session. The session begins at
`BrokerOwner.start()` and ends at `BrokerOwner.stop()`, and its lifetime is the
runtime process's lifetime.

### The lifecycle semantics this record fixes

`BrokerOwner`'s existing semantics are redefined in no respect, and an
implementation may not change them quietly. Stated explicitly, because ADR-0018
question 4 requires any lifetime longer than one `main()` to say so:

Permitted, and decided here:

- **Exactly one `start()` per runtime process**, called once during runtime
  startup.
- **`stop()` on every exit path**, in a construct an exception cannot skip, as
  ADR-0017 requires of the verification entrypoint. The port states that
  `disconnect()` raises "Never, for the ordinary case of an already-closed or
  never-opened session", because it "must be safe to call from a cleanup path
  that cannot know the current state" — so an unconditional stop cannot mask
  the error that sent the runtime into cleanup.
- **`stop()` is terminal for the runtime.** Once the runtime has stopped its
  owner, that runtime process is ending.

Rejected, and decided here:

- **The runtime does not call `start()` after `stop()`.** `BrokerOwner.stop`
  clears the started flag, so the code permits a second session on the same
  owner. This record neither relies on that behaviour nor uses it. Recovering a
  lost session is `reconnect`'s job under the supervision decision below, not a
  stop-then-start cycle, because a stop-then-start would silently redefine "one
  runtime process owns one broker session".
- **An implementation may not tighten `BrokerOwner` to forbid it either.**
  Adding a stopped flag, or converting `stop()` into a terminal state the class
  enforces, changes accepted semantics that the seventeen tests in
  `tests/unit/test_core_broker_ownership.py` pin. That is a change to
  `BrokerOwner`, and it needs its own record.

Unchanged, and not reopened:

- A second `start()` while started raises `RuntimeError`.
- `stop()` before start, and a second `stop()`, are silent no-ops.
- The `adapter` property raises `BrokerNotConnectedError` before start and after
  stop.
- A failed `start()` leaves the owner un-started, propagates the venue's error
  unchanged and unwrapped, and can still be unwound.

### Concurrency model

**The runtime is synchronous and thread-based. `asyncio` is not introduced.**
ADR-0007's two locks, and the lock order it fixed, remain authoritative and are
not redesigned. This record is the first thing in the repository to reach them
with more than one thread, which is what they were built for.

Independent runtime concerns may run on dedicated threads where required:
market-data acquisition, supervision and liveness, and broker recovery. The
number of threads, their scheduling and their shutdown protocol are
implementation.

**`BrokerOwner` is not made thread-safe by this record**, and its docstring's
statement that `start` and `stop` "are not safe to call from two threads at
once" stays true as written. It follows that **the runtime confines `start()`
and `stop()` to the single thread that owns the runtime's lifecycle.** Other
threads reach the venue through the adapter, whose thread-safety ADR-0007
guarantees, and never through the owner's transitions.

### Supervision and liveness

**The runtime owns application-level supervision and liveness. Deployment and
container infrastructure own process restart.** The division is the one ADR-0013
already implies: its fifth responsibility, "the supervision duty ADR-0007
assigns to a caller", is the application's, and this record finally discharges
it. Restarting a process that has decided it cannot continue is not an
application concern and is not made one here.

The runtime uses the existing lock-free substrate rather than inventing one.
Precisely, and this precision matters:

- `is_connected()` "Takes no lock. The read is a single attribute access, and
  answering it is the one thing that must still work while another thread is
  blocked inside a connect that will not return."
- `health()` "Never waits on the session lock, so it answers during an in-flight
  connect or disconnect."
- `ping()` performs the round trip that refreshes what `health()` reports, and
  the port forbids it from raising because "a liveness check that raises when
  the venue is down cannot be used in the supervision loop that exists to notice
  the venue is down."

**`heartbeat_age()` and `is_heartbeat_fresh()` are not on the port.** They are
`BaseBrokerAdapter` methods, and `BaseBrokerAdapter` is a name no application
module may take — `tests/unit/test_core_broker_boundary.py` lists it in
`UNSELECTED_IMPLEMENTATION_NAMES` because "naming it, is reaching past the port
to the shared implementation underneath". The runtime therefore reaches the
heartbeat through `health()`, refreshed by `ping()`, and not through the base
class. This record does not add either method to the port.

**`docker-compose.yml`'s `restart: "no"` is a deployment consequence of this
record, not a change this record makes.** Its comment already names the
condition — the service acquiring a run loop — and this record satisfies it. The
implementing task changes it, along with any healthcheck the runtime service
needs. Nothing about restart policy or healthchecks is implemented now.

### Reconnection and recovery

**Runtime supervision owns broker reconnection and recovery**, through the
port's `reconnect`. ADR-0009's "Nothing decides to reconnect… Noticing a session
has gone quiet and deciding to replace it is the supervision layer's job, and it
still does not exist" is answered by naming the layer, and by nothing else.

- **No `RetryPolicy` value is chosen here.** ADR-0009's rule that a policy "is
  constructed by whoever constructs the adapter" is unchanged, and
  `composition.py` continues to pass none, which continues to mean
  `RetryPolicy.none()`. Choosing attempts and delays remains an open decision.
- **Multi-venue failover is explicitly out of scope**, as are multiple adapters,
  venues and accounts. ADR-0015 left them open and recorded that multi-venue
  support "gets no cheaper" by waiting; that is still true and this record does
  not buy it down.
- **Reconnect is not implemented now.** This record decides where it lives.

### Pipeline attachment

**The runtime owns the market → strategy → risk → execution orchestration.** The
decided flow:

```
Market polling            (runtime-owned)
    ↓
Market observation        (produced by the runtime)
    ↓
Strategy.propose()        (existing synchronous contract, runtime invokes it)
    ↓
TradeIntent               (built by the strategy/application integration layer)
    ↓
Risk evaluation           (handed the intent and the account state)
    ↓
RiskVerdict
    ↓
ExecutionPolicy
    ↓
OrderRequest              (built by atlas.execution from the verdict and policy)
    ↓
BrokerOwner               (the session boundary, unchanged)
    ↓
BrokerAdapter             (the port)
```

Ownership, stated one line at a time:

- **Market observation is produced by runtime-owned market polling.** The
  runtime reads the venue through the port's market-data operations and builds
  the observation. `Strategy[InputT]` is generic precisely because
  ATLAS-TASK-0012 declined to name an observation type "from the package with
  the least standing to do it"; the runtime supplies the type parameter. Whether
  the observation later moves into `atlas.market` is not decided here.
- **The runtime invokes the existing synchronous `Strategy.propose()`
  contract.** The protocol is not changed, not made asynchronous, and not given
  a lifecycle or a registry.
- **`TradeIntent` is constructed by the strategy/application integration
  layer.** ADR-0010's "Nothing produces an intent" stops being true when this
  record is implemented, and that is the change this record makes to it.
- **Risk receives the intent and the account state and returns its verdict.**
  This is ADR-0012's shape unchanged: risk is handed the state it judges. The
  runtime obtains the account state from the port and hands it over. Risk is not
  given a way to ask the venue what an intent costs, which ADR-0012 forbids.
- **Execution builds the `OrderRequest` from the verdict and an
  `ExecutionPolicy`.** ADR-0011's shape unchanged: execution builds the request
  and another layer owns the port. This record names that layer.
- **The runtime is the application-level caller authorised to invoke broker
  trading operations through the broker boundary.**
- **`BrokerOwner` remains the broker-session owner and is not turned into the
  pipeline itself.** It governs access to the adapter, which is ADR-0013's third
  responsibility and the one ADR-0017 left unexercised because nothing consumed
  the adapter. Something now does.

**This record decides none of the following**, and they are listed here rather
than only in the later section because the flow above is exactly the place an
implementation would be tempted to decide them in passing: the strategy
algorithm; strategy rules; the risk model; execution-policy design; order
lifecycle; routing; fills; reconciliation; idempotency.

### Pipeline cadence — one observation, one ordered evaluation

**Each accepted market observation triggers exactly one synchronous, ordered
strategy → risk → execution evaluation. There is no concurrent evaluation of
multiple observations inside the trading decision pipeline.** Decision
evaluation and order submission are serialised per runtime pipeline.

Market-data acquisition, supervision and liveness, and broker recovery may run
on dedicated threads alongside it, as the concurrency section allows. The
serialisation constraint binds the decision pipeline, not the runtime.

This is an architectural concurrency boundary. It is **not** a decision about
the polling interval, trade frequency, throttling, strategy timing rules, or how
backpressure is implemented. Those remain open, and the boundary is what stops
them from being answered by whichever thread happens to win a race.

### The ten questions ADR-0018 asked

1. `atlas-core` becomes the host of a long-lived runtime, beside the one-shot
   check, which is retained.
2. No separate application. The check and the runtime become two entrypoints of
   one application.
3. `BrokerOwner` owns the session; the runtime entrypoint owns `BrokerOwner`.
4. The session lives as long as the runtime process; `stop()` ends it; the
   semantics are fixed above.
5. The runtime entrypoint owns the loop. It is synchronous and thread-based.
6. The runtime owns application-level supervision and liveness; deployment owns
   process restart.
7. Runtime supervision owns reconnection; failover is out of scope; no
   `RetryPolicy` value is chosen.
8. Synchronous and thread-based, with a serialised decision pipeline.
9. Answered by **Pipeline attachment** above, for all five of its parts.
10. Answered by **What this record does not decide** below.

## Implementation authority

ADR-0018 required that the answer not arrive by implementation. The same
requirement runs the other way now: implementation must not be left to invent
which permissions it needs. This section states them.

### The runtime modules

The runtime is one or more new modules inside `atlas.apps.core`. Every grant
below is bounded by those modules, and
`tests/unit/test_core_broker_boundary.py` must name each of them individually,
as it already names `OWNERSHIP_MODULE`, `COMPOSITION_MODULE` and
`ENTRYPOINT_MODULE`. **No grant may be expressed as a directory, a prefix, a
wildcard or a package-wide exemption.** The test that scans every application
on disk stays as it is, so any module the implementation adds and does not name
is bound by every existing rule and fails.

The exact filenames are implementation's to choose. Which permissions attach to
them is not.

### The pipeline-package grant

`PIPELINE_PACKAGES` is not deleted and not emptied. It becomes bounded by
module: forbidden to every module under `apps/` except the named runtime
modules, which may take exactly these names and no others.

| Package | Names granted |
|---|---|
| `atlas.strategy` | `Strategy` |
| `atlas.risk` | `TradeIntent`, `RiskVerdict`, `evaluate_exposure` |
| `atlas.execution` | `ExecutionPolicy`, `build_order_request` |

`RejectionReason`, `VerdictStatus` and `RISK_MODEL_CONFIG` are **not** granted.
An approved verdict is distinguishable without them, because
`build_order_request` returns `None` for a verdict that does not licence an
order, which is ADR-0011's own shape.

### The broker grant

From `atlas.broker`, the runtime modules may take `BrokerError` and
`OrderRequest`, and from `atlas.broker.models` the account type
`evaluate_exposure` consumes. `SELECTED_IMPLEMENTATION_NAMES` stays bounded to
the composition module, and `UNSELECTED_IMPLEMENTATION_NAMES` —
`MockBrokerAdapter`, `MockVenue`, `BaseBrokerAdapter` — is granted to nothing,
anywhere.

**`BrokerAdapter` itself is not granted.** The runtime reaches the adapter
through `BrokerOwner`, so the assertion that exactly one module names the
abstraction, and that it is the ownership module, **stays at one and does not
change.** That is the load-bearing check on this grant: a runtime that names
`BrokerAdapter` has acquired an adapter rather than been handed one, and has
left this record.

Two census assertions do change, and only by the runtime modules:

- the census of modules importing `atlas.broker` itself, currently two — the
  ownership module and the entrypoint;
- the census of modules reaching anywhere within `atlas.broker`, currently
  three — those two and the composition module.

The runtime modules join both, for `BrokerError`, `OrderRequest` and the
account type. Nothing else joins either.

`UNCALLED_PORT_OPERATIONS` is narrowed by **exactly six names**, granted to the
runtime modules only:

| Name | Granted for |
|---|---|
| `is_connected` | Liveness, lock-free |
| `health` | Liveness snapshot, lock-free |
| `ping` | The round trip that refreshes the heartbeat |
| `reconnect` | Recovery, owned by runtime supervision |
| `get_account` | The account state risk is handed |
| `place_order` | Order submission, the end of the decided flow |

**Eight names stay in `UNCALLED_PORT_OPERATIONS` and are granted to nothing:**
`latency`, `modify_order`, `cancel_order`, `close_position`, `get_positions`,
`margin_required`, `margin_available`, `can_trade`. The four trading verbs after
`place_order` are order lifecycle, which this record does not decide.
`margin_required`, `margin_available` and `can_trade` are the venue-side cost
questions ADR-0012 forbids risk to ask, and granting them to the runtime would
route around that refusal. `latency` is measurement rather than liveness, and
belongs to broker observability, which is a separate record's question.

The port's market-data read operations are **not** in
`UNCALLED_PORT_OPERATIONS` today and no widening of that constant is needed for
them; the runtime modules reach them under the module census grant above. Which
of them the polling uses — ticks, candles, symbol lookup or history — is
implementation. **The subscription verbs are not granted**: `subscribe_ticks`
and `subscribe_candles` raise `NotImplementedError` on the MetaTrader 5 adapter,
a push model was not chosen, and a synthesised subscription is the scheduler
that the adapter's own note says must not appear as a side effect.

### What the boundary test may not be made to say

`test_this_file_states_two_bounded_permissions_and_nothing_wider` pins the whole
set of module-scope constants in that file, so a new constant fails there before
it can permit anything. That test is updated to match the grants above and is
not weakened. Specifically, an implementation has left this record if it:

- adds a grant constant this record does not name;
- expresses a grant by prefix, directory or wildcard rather than by module;
- removes a name from `UNCALLED_PORT_OPERATIONS` other than the six above;
- widens the census of modules naming `BrokerAdapter` beyond the ownership
  module;
- grants any name to `apps/dashboard` or `apps/research`;
- deletes `PIPELINE_PACKAGES`, `test_every_application_on_disk_is_scanned`, or
  `test_no_module_level_assignment_binds_an_adapter`;
- binds an adapter at module scope, or behind `lru_cache` or `cache`.

### The `apps/` import rule is not closed by this record

The general `apps/` import rule has been open since ADR-0013 and was left there
by ADR-0014 through ADR-0018. **It stays open.** The chosen architecture has one
application, so a second entrypoint raises no question about what a *different*
application may import. What the boundary test must do is distinguish the
verification entrypoint from the runtime modules, which is a statement about
modules inside one application and not a general rule about `apps/`.

Nothing here should be read as authority to write that general rule. As
`tests/unit/test_core_broker_boundary.py` says of itself, it "would begin with a
decision record rather than with a test file".

## Alternatives considered

**A fourth application owning the runtime.** Rejected by the owner. It would
have forced the general `apps/` import rule closed as a prerequisite, doubled
the container and configuration surface, and required either a second
composition root or a decision about where a shared one lives — none of which
buys anything the two-entrypoint shape does not.

**Superseding ADR-0017 and making `atlas-core` only a runtime.** Rejected. It
would discard a deployment check that works, and a process that does not return
has no exit code, which would invalidate CI's assertions that the image exits
`3` with broker configuration and `2` without it. Keeping both entrypoints keeps
both, and the verification path is the only thing in this repository that can
demonstrate anything on Linux.

**Continuing to defer.** Rejected: the owner has decided, and ADR-0018 described
itself as a gate that "will be short-lived if the runtime decision is taken
soon", which is "the correct shape for a gate".

**A one-shot process invoked on a schedule.** Rejected: it was not the owner's
choice, and it has a structural problem the decided shape does not — nothing
survives between invocations, so a live order has nowhere to be watched from
between cycles.

**`asyncio`.** Rejected. `base.py` is built for threads and ADR-0007 fixed a
lock order for them; ADR-0017 recorded that ADR-0007 "already rejected it as out
of scope and cited ATLAS-TASK-0003's 'do not use async'". Choosing it would mean
redesigning the substrate rather than using it.

**Concurrent evaluation of observations.** Rejected as the default. Two
evaluations in flight against one account means two risk verdicts computed
against the same account state and two orders submitted on the strength of it,
which is a correctness question rather than a throughput one. Serialising is the
decision; making it faster later is a decision that will have evidence.

## Consequences

### Guaranteed

- The runtime question has an answer, and ADR-0018's deferral is closed by a
  record rather than by a task.
- `atlas-core` remains one application. No fourth application, no second image,
  no second composition root, and no second configuration surface.
- The verification entrypoint is untouched: same three exit codes, same
  unconditional stop, same single thread, same one attempt, same startup record
  with its eight keys and no credential.
- One runtime process holds one session, opened once and closed once, and no
  runtime process exits holding a session.
- `BrokerOwner`'s semantics are unchanged in every respect, and the seventeen
  tests that pin them keep their meaning.
- ADR-0007's locks are not redesigned, and `asyncio` is not introduced.
- The permissions an implementation may add are enumerated, bounded by module,
  and closed: six port operations, six pipeline names, two broker names and one
  account type.
- Eight port operations remain granted to nothing, including every order
  lifecycle verb and every venue-side cost question.
- The general `apps/` import rule stays open, and `apps/dashboard` and
  `apps/research` are granted nothing.

### Not guaranteed, deliberately

- **That anything can be traded.** `place_order` raises `NotImplementedError` on
  the MetaTrader 5 adapter, as do `modify_order`, `cancel_order`,
  `close_position`, `subscribe_ticks`, `subscribe_candles` and `server_time`.
  This record authorises an architecture; it does not make an order placeable
  and it does not implement a single verb.
- **That the pipeline is operational.** It is not. Nothing produces an
  observation, nothing constructs a `TradeIntent` outside the test suite, and
  `RiskSettings.max_margin_utilisation` still defaults to a value whose own
  description reads "Zero permits nothing".
- **That a strategy exists.** `Strategy` is a protocol with one reference
  implementation that returns a constant.
- **That the runtime survives a venue outage.** Reconnect has a home now. It has
  no implementation, and no `RetryPolicy` value.
- **That the two stale documents become correct.** The process table in
  `docs/architecture/overview.md` and the `atlas.apps.core` package docstring
  describe a long-lived process that owns an event loop, and this record moves
  the architecture toward them. **That is not evidence for the decision and was
  not a reason for it**, exactly as ADR-0018 warned. Neither document is edited
  here, and repairing them remains a separately authorised documentation task.

### Costs

- **`atlas-core` acquires a second deployable shape from one image**, and
  operators gain a second thing to run and reason about.
- **`BrokerOwner`'s "not synchronised" limit is reached for the first time.**
  Until now the single-threaded lifecycle meant the limit was never approached.
  Confining `start` and `stop` to one thread is a constraint the implementation
  must actually hold, and nothing in the class enforces it.
- **The boundary test becomes a per-module document rather than a per-
  application one.** It currently asserts uniformly across `APP_SOURCES`; making
  it distinguish the runtime modules is more structure to maintain, and the
  file's self-pinning test exists to make that structure hard to widen quietly.
- **Configuration becomes frozen for the runtime's life.** `get_settings` is
  cached with `lru_cache(maxsize=1)`, and `atlas.risk` reads its limit through
  it at call time. A process that never exits never re-reads it. Whether the
  runtime reloads configuration is not decided here, and until it is, a limit
  change requires a restart.
- **`restart: "no"` stops being correct**, and the local stack and runbook prose
  describing a process that exits will need revising. That is the implementing
  task's work, not this record's.
- **Six port operations that no application could name yesterday can be named
  tomorrow.** That is the point, and it is also the largest single widening of
  the broker boundary since it was drawn.

## What this record does not decide

- **`RetryPolicy` value, attempt count and backoff.**
- **Broker startup observability**, which ADR-0015 and ADR-0017 both reserved to
  a separate record.
- **Order lifecycle, routing, idempotency, fills and reconciliation.**
- **Account and portfolio state ownership.** The runtime reads account state
  from the port and hands it to risk; who owns, caches or derives portfolio
  state is untouched, and ADR-0012's "not who calls the control, not who hands
  it state" is not reopened beyond naming the caller.
- **Dependency injection, registries, factories, service containers and
  locators.** None is defined and none should be inferred.
- **Any new configuration field or environment variable.** This record adds
  none.
- **Multi-venue support and multi-venue failover**, and multiple adapters or
  accounts.
- **The strategy implementation, the risk model and execution-policy design.**
- **Persistence wiring.** Nothing here connects the runtime to PostgreSQL,
  Redis or DuckDB.
- **The exact market polling interval**, trade frequency, throttling and
  strategy timing rules.
- **Detailed backpressure policy.**
- **Which broker verbs are implemented first.**
- **Stale-documentation repair**, which remains a separately authorised task.
- **The general `apps/` import rule.**
- **A change to `BrokerOwner`'s public semantics**, in either direction.
- **The runtime's shutdown signal handling and thread count.**

## Implementation cannot decide these by implication

**Every item in the section above is closed to implementation.** A task that
finds itself choosing one has left this record, whatever its stated scope, and
the same test applies that ADR-0018 applied to the runtime question itself:
these are answered by a record, not by a diff.

Three cases are worth naming because they are the ones a reasonable
implementation would walk into:

- **Choosing a `RetryPolicy` value to make reconnect useful.** Reconnect has a
  home under this record; it does not have a policy, and supplying one is a
  decision about a deployment.
- **Adding a port operation "because the loop needs it".** The six granted names
  are the whole grant. A seventh requires a record.
- **Widening a grant to a package or a directory to avoid naming modules.** The
  grants are bounded by module deliberately, and the self-pinning test exists to
  make a wider one fail before it permits anything.

## Relationship to ADR-0017

**ADR-0017 is not edited, not reopened, and its status is not changed.** It
remains `Accepted`, and its decision remains in force for the entrypoint it was
written about. **ADR-0017 was not wrong.** It decided what a running
`atlas-core` process was, at a time when the alternative was a process shape
chosen by whoever wrote the first pipeline task, and the check it produced is
the only thing in this repository that verifies a deployment today.

What this record changes is narrow and worth stating exactly. ADR-0017's title
carries a claim about the application — "`atlas-core` is not a long-running
process" — and its decision says the application "acquires no run loop". Under
this record the application acquires one, in a second entrypoint. **That claim
is superseded as a statement about the application, and only that far.**
Everything ADR-0017 decided about the verification entrypoint stands unchanged:
the sequence, the three exit codes, the unconditional stop, the single thread,
the single attempt, the frozen startup record, and its refusal to poll after
`start()`.

**No new ADR status is invented.** `docs/adr/README.md` offers `Proposed`,
`Accepted`, `Superseded by ADR-NNNN` and `Deprecated`, and there is no status
for a record whose decision is partly superseded. Marking ADR-0017
`Superseded by ADR-0019` would be false, because its decision still governs the
verification entrypoint in full. Editing its body is forbidden by the rule that
accepted records "are never edited in place". The relationship is therefore
recorded here, in the later record, which is the mechanism ADR-0017 itself used
when it answered ADR-0016's open question: "a later record answers an earlier
record's open question without editing it."

## Relationship to ADR-0018

**ADR-0018 is not edited and its status is not changed.** Its deferral is
closed by this record, which is the mechanism ADR-0018 specified for itself:
"The next *record* is the one that answers the ten questions, and it is a
prerequisite for the work this one defers rather than a consequence of it."

Its ten questions are answered above. Its prohibition — that no persistent
session, run loop, supervision, reconnect, failover, strategy lifecycle, risk
integration or execution pipeline may be implemented until a record defines the
process and session shape and is accepted — is satisfied rather than overridden,
and the items on its **What is deferred** list are released only to the extent
this record decides them. Everything on its **What this record does not decide**
list that this record does not answer stays deferred, and is repeated above so
that no item is released by silence.

ADR-0018's option list was explicitly not exhaustive. The shape decided here is
its Option C.

## Relationship to ADR-0013

**Not superseded, not edited, not reopened.** This record discharges the three
responsibilities ADR-0013 assigned that ADR-0017 left standing.

Governing access, the third, was "unexercised: nothing is handed the adapter,
because nothing consumes it". The runtime consumes it, through `BrokerOwner`,
which is the mechanism ADR-0013 declined to name and this record does not name
either — it names the owner that already exists.

Lifecycle sequencing, the fourth, gains `reconnect`, which ADR-0013 listed among
the calls "called by the owner, in an order the owner chooses" and which
ADR-0017 explicitly did not call.

Supervision, the fifth — "The `health()` timer ADR-0007 designed for is the
application's to run… somebody still has to make it" — is assigned by this
record to the runtime entrypoint. ADR-0013's pipeline diagram, ending
`OrderRequest ──▶ apps/atlas-core ──▶ BrokerAdapter ──▶ venue`, is the flow this
record adopts.

## Relationship to ADR-0007, ADR-0008 and ADR-0009

**None is superseded, edited or reopened.**

ADR-0007's two locks stay where they are and keep the order they were given.
This record adds the concurrency they were designed to arbitrate, and adds no
lock of its own. `asyncio` stays rejected.

ADR-0008's injected clock is what the runtime's timing must go through. A loop
that calls the wall clock directly abandons `ManualClock` and makes itself
untestable; the clock is already injected into the adapters and the runtime has
no reason to reach around it.

ADR-0009's retry mechanism is unchanged and no policy value is chosen. Its
observation that "Nothing decides to reconnect" is answered by naming the layer
that will, not by writing it.

## Relationship to ADR-0010, ADR-0011 and ADR-0012

**None is superseded, edited or reopened, and no contract in them changes.**

ADR-0010's risk boundary is unchanged; what changes is that something will
produce an intent, which ADR-0010 listed among the things it deliberately did
not guarantee. ADR-0011's "execution builds the request; another layer owns the
port" is satisfied exactly: the runtime is that layer, and execution still
routes nothing. ADR-0012's exposure control is still handed the state it judges
rather than fetching it, and is still not permitted to ask the venue what an
intent costs — which is why `margin_required`, `margin_available` and
`can_trade` are granted to nothing above.

## Relationship to ADR-0015 and ADR-0016

**Neither is superseded, edited or reopened.** ADR-0015's selection, its
translation boundary and its placement of construction at startup all stand;
the runtime composes through the same `build_broker_owner`, and
`MockBrokerAdapter` is still not a fallback for anything. "Construction is not
connection" remains the sentence that keeps these decisions separable.

ADR-0016's refusal is untouched. Unusable broker configuration still fails
before an adapter is built, in both entrypoints, with the same exception, the
same single JSON line on stderr and the same exit `2` in the verification path.

## Dependency and implementation sequencing

**No task is created by this record**, and this section describes the boundary a
future task would work inside so that its scope can be judged before it is
authorised.

Hard prerequisites, in order:

1. **This record, accepted.** It is.
2. **The boundary-test restructuring**, which must land with or before the first
   runtime module, because `test_every_application_on_disk_is_scanned` binds a
   new module the moment it exists.
3. **A market-data polling path**, because nothing else in the pipeline can be
   exercised without an observation, and because the MetaTrader 5 adapter offers
   no push channel.
4. **`place_order` on the MetaTrader 5 adapter**, before any order can be
   submitted. It raises `NotImplementedError` today.

Independent of the above, and safe to do in any order:

- Implementing the remaining trading verbs in `packages/broker`, which is port
  conformance and touches no application module.
- A real `Strategy` implementation, which depends on the observation type and
  nothing else.
- Broker startup observability, which concerns the existing verification path
  and needs its own record first.

Deliberately not sequenced here: how many tasks this becomes, what each is
called, and in what order the owner authorises them.

Premature under this record, and named because each looks safe:

- **A supervision loop written before the polling path**, which would decide the
  thread model by being first.
- **A `RetryPolicy` value added to `composition.py`** to make reconnect do
  something.
- **A healthcheck or restart-policy change made now.** Both are consequences of
  this record and belong to the implementing task, which has not been
  authorised.
