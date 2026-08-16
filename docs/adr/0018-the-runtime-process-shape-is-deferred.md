# ADR 0018 — The long-lived runtime and process shape is deferred pending its own decision

**Status:** Accepted
**Date:** 2026-08-16

## Context

ADR-0017 decided what a running `atlas-core` process is today: it resolves
configuration, constructs an adapter and an owner, opens a broker session,
treats the opening as the verification, closes the session on every path,
reports the outcome and exits. It acquires no run loop and holds no session past
its own startup. That record is accepted, and the process it describes is
implemented and running in CI.

It also drew a boundary and named what lay beyond it. Its own words, at the end
of the record: supervision, the health timer, reconnect, failover, a run loop,
threading, the execution pipeline, the `apps/` import rule, a `RetryPolicy`
value and broker startup observability are "explicitly out of scope for that
task, each needing its own decision". ADR-0016's list of what it does not decide
opens with the same subject from the other side — "`BrokerOwner`'s lifecycle,
when `start()` is called, and by what" — and continues into the run loop,
supervision, health checks, reconnection and failover. ADR-0013 assigned
`apps/atlas-core` five responsibilities for the adapter and ADR-0017 implemented
two of them, leaving governing access unexercised because nothing consumes the
adapter, and supervision untouched.

Three separate records therefore converge on one unanswered question, and each
of them declines it in the same terms: *each needing its own decision*. This
record is not that decision. It is the record that says so, names the question
precisely enough that the next record can answer it, and refuses to let the
answer arrive by implementation instead.

The refusal is not theoretical. The repository already contains a statement of
the opposite shape, written before any of this was settled.
`docs/architecture/overview.md`'s process table charters `atlas-core` as a
long-lived container that "Owns the event loop and runs the trading pipeline",
and `apps/atlas-core/src/atlas/apps/core/__init__.py` still opens by describing
"the long-lived process that wires the packages together, owns the event loop,
and runs the trading pipeline end to end". Both predate ADR-0017 and neither was
written as a decision — the first is a responsibility charter and the second is
an ATLAS-TASK-0001 package docstring that also still says its implementation is
"delivered by a later task". They are named here because they are the most
plausible route by which the deferred decision could be taken accidentally: a
future task could read either as authority for building a run loop, and neither
is.

What makes the question urgent rather than merely open is that nothing
downstream can proceed without it. Every remaining capability in the
architecture needs a broker session that outlives `main()`, and no record
decides what holds one:

- `atlas.market`, `atlas.features` and `atlas.regime` are empty importable
  units, so `Strategy[InputT]` is generic because ATLAS-TASK-0012 declined to
  name an observation type "from the package with the least standing to do it".
  Nothing produces a strategy input.
- Nothing constructs a `TradeIntent` outside the test suite. ADR-0010 listed
  "Nothing produces an intent" among what it deliberately does not guarantee,
  when `atlas.strategy` and `atlas.execution` were both stubs. Both have since
  been built, and the sentence is still true: `TradeIntent` is defined in
  `atlas.risk` and constructed nowhere else in the source tree.
- `RiskSettings.max_margin_utilisation` defaults to `Decimal("0")`, whose own
  description reads "Zero permits nothing", and the production invariant refuses
  a value at or below zero. The one implemented risk control is wired to nothing
  and, at its default, would approve nothing.
- `ExecutionPolicy` is supplied per call and nothing stores one;
  `atlas.execution` translates an approved verdict and routes nothing.
- Seven `BrokerAdapter` methods on the MetaTrader 5 adapter raise
  `NotImplementedError`, including every trading verb. No order can be placed
  even if a verdict reached one.

Each of those is a real prerequisite in its own right. All of them sit behind
the same gate, which is why the gate is worth a record.

## Decision

**The long-lived runtime and process shape is intentionally deferred pending an
explicit architectural decision. No persistent broker session, run loop,
supervision, reconnect, failover, strategy lifecycle, risk integration or
execution pipeline may be implemented until a dedicated architecture decision
record defines the process and session shape and is accepted.**

This record decides that the question is open, that it is answered by a record
and not by a task, and what that record must answer. It chooses none of the
available answers.

### What is deferred

Deferred, and not permitted to arrive by implementation:

- A broker session that outlives the `main()` that opened it.
- A run loop, event loop, scheduler or any construct that keeps `atlas-core`
  resident after its work is done.
- Supervision, liveness checks, health timers and restart policy beyond
  `docker-compose.yml`'s existing `restart: "no"`.
- Reconnection and failover, including any use of `BrokerAdapter.reconnect`,
  which no production code calls today.
- A concurrency or threading model beyond the single thread ADR-0017's sequence
  runs on.
- Market data ingestion, a strategy lifecycle or registry, risk integration, and
  execution routing or order placement.

### The gate

The deferred record must exist and be accepted **before** implementation of any
item above begins, not alongside it and not after it. Acceptance is the owner's
step, as it is for every record here.

This record grants no authorisation. Its existence is not permission to build
the runtime, and neither is the existence of the record it calls for until that
record is accepted. A task that finds itself deciding any question in the next
section has left the boundary this record draws, whatever its stated scope.

### The questions the deferred record must answer

The record that lifts this deferral must answer all of the following
explicitly. Answering some and leaving others to implementation is the failure
mode this record exists to prevent.

1. **Does `atlas-core` remain a one-shot startup check, or become or host a
   long-lived runtime?** ADR-0017 decided the former for today and said so in
   its title. Changing it means superseding ADR-0017, not reinterpreting it.
2. **Does a separate process or application own the persistent session?**
   `apps/` currently holds `atlas-core`, `dashboard` and `research`. Whether a
   fourth application appears, or the runtime lives inside `atlas-core`, or the
   check and the runtime become two entrypoints of one application, is open.
3. **Who owns the broker session after startup?** ADR-0013 gave the application
   five responsibilities and ADR-0017 exercised two. Which component holds the
   adapter once something consumes it, and whether `BrokerOwner` is that
   component or is itself held by one, is undecided.
4. **How long is the session expected to live, and what ends it?** Process
   lifetime, trading session, a fixed interval, or an explicit shutdown signal.
   `BrokerOwner` today refuses a second `start()` with `RuntimeError`, treats a
   redundant `stop()` as a no-op, and raises `BrokerNotConnectedError` before
   start and after stop. Any lifetime longer than one `main()` must state
   whether those semantics survive unchanged.
5. **What component owns the run loop?** Whether the loop belongs to the
   application, to a package, or to an injected scheduler, and whether it is
   synchronous, `asyncio`-based or thread-driven.
6. **What owns supervision and liveness?** Whether the process supervises
   itself, whether the container runtime does, and what replaces
   `restart: "no"` if anything. ADR-0007 assigns a supervision duty to a caller
   and ADR-0013 named it as the application's fifth responsibility; neither says
   what discharges it.
7. **What owns reconnection and failover?** `RetryPolicy.none()` is the default
   today and ADR-0017 made it observable by calling `connect()` for the first
   time without choosing a value. Whether retrying belongs to the owner, the
   loop, or a supervisor, and whether failover across adapters, venues or
   accounts is in scope at all, is open — ADR-0015 hard-coded one adapter and
   recorded that multi-venue support "gets no cheaper" by waiting.
8. **What is the concurrency model?** ADR-0007's two locks in the base adapter
   cover the trivial single-threaded case today. Whether the runtime introduces
   threads, tasks or processes, and what those locks then arbitrate, must be
   decided rather than discovered.
9. **How does market → strategy → risk → execution integration fit the chosen
   shape?** Specifically: what produces the observation a `Strategy` consumes,
   what constructs a `TradeIntent`, how risk obtains the account state ADR-0012
   says it is handed, where `ExecutionPolicy` comes from, and what calls the
   trading verbs that raise `NotImplementedError` today. The chosen process
   shape constrains all five, which is why they cannot be settled first.
10. **What remains outside that record**, stated explicitly, in the manner every
    record here uses.

### The options the deferred record must choose between

Stated so that the deferred decision has something to weigh. **None is chosen
here, and this list is not exhaustive** — a record that finds a better shape is
not bound by it.

#### Option A — `atlas-core` stays one-shot; a new application owns the runtime

`atlas-core` keeps ADR-0017's semantics exactly, and a separate application
under `apps/` holds the persistent session and the loop.

*Consequences.* ADR-0017 survives unedited and its exit-code surface stays
meaningful as a deployment check. The `apps/` import rule, open since ADR-0013,
must finally be decided, because a second application makes the question
concrete. Two deployables must be built, configured and documented, and the
container and compose surface roughly doubles. The startup check and the runtime
can be deployed independently, which is the main reason to want this.

#### Option B — `atlas-core` becomes the long-lived runtime

ADR-0017 is superseded by the deferred record, and `atlas-core` acquires the
loop it was originally chartered for.

*Consequences.* The overview's process table and the package docstring become
correct without being edited into correctness first, which is a genuine
attraction and also the reason to be careful: neither is evidence for the
choice. ADR-0017 must be superseded explicitly, never edited. The three-outcome
exit surface needs restating, because a process that does not exit has no exit
code to report and CI's container job currently asserts exit `3` on Linux.
`restart: "no"` is revisited.

#### Option C — one application, two entrypoints

`atlas-core` keeps the check as one entrypoint and gains a runtime entrypoint
beside it, sharing composition.

*Consequences.* One image, one configuration surface, and `composition.py` is
reused rather than duplicated. ADR-0017 is narrowed rather than superseded —
its decision becomes a statement about one entrypoint instead of about the
application — which needs care to state honestly, because ADR-0017's title is a
claim about `atlas-core` and not about a module. The import allowlists that
police `atlas.risk → atlas.broker` and `atlas.execution → atlas.broker` say
nothing about applications, so a second entrypoint reaching the port has no
allowlist to widen; it meets the open `apps/` import rule head-on, exactly as
Option A does.

#### Option D — continue deferring

The runtime is not built; the repository stays a validated startup check.

*Consequences.* No decision is taken and no cost is incurred, which is the state
this record describes. It is listed because it is legitimate and because the
alternative to deciding is not automatically deciding — but nothing downstream
in the architecture can proceed while it holds.

## Alternatives considered

**Let the implementing task decide the process shape.** Rejected on the
repository's own evidence. ADR-0015 recorded that "Deciding that an adapter is
*constructed* at startup therefore decides nothing about when a session is
*opened*", and the gap that observation left sat open across ADR-0016 and two
tasks until ADR-0017 closed it deliberately. A process shape chosen inside a
task would be a larger version of the same mistake, taken with less visibility.

**Write the runtime record now and accept it.** Rejected because the owner has
deferred the decision, and because this record has no answer to offer. Producing
a record that picks Option A, B or C without the owner having chosen would be
exactly the substitution of implementation for decision that the deferral
exists to prevent.

**Record the deferral in the roadmap instead of an ADR.** Rejected. The roadmap
records which tasks are complete and what each ADR decided; it is not where
architectural constraints are established, and it says of itself that it "does
not speculate past" the tasks it declares. A prohibition binding all future work
is a decision, and decisions live here.

**Reopen or edit ADR-0017 to say the question is open.** Rejected on
`docs/adr/README.md`'s rule that accepted records are never edited in place.
ADR-0017 already says the question is open, in its own closing section. Nothing
needs changing there.

**Say nothing and rely on the existing "out of scope" lists.** Rejected. Those
lists bind the tasks the records were written for. Neither ADR-0016 nor ADR-0017
binds a task nobody has written yet, and the two stale documents named in the
context section are a standing invitation to read the opposite intent.

## Consequences

### Guaranteed

- The runtime question has a single place to be answered, and the answer must be
  a record.
- No task may implement a persistent session, run loop, supervision, reconnect,
  failover, strategy lifecycle, risk integration or execution pipeline while
  this record stands. The prohibition is checkable by reading a diff against the
  list in **What is deferred**.
- ADR-0013, ADR-0015, ADR-0016 and ADR-0017 are unchanged, unedited and
  unsuperseded by this record.
- The repository's behaviour is unchanged. This record adds no source file, no
  test, no configuration field, no environment variable and no CI step.

### Not guaranteed, deliberately

- **That the deferred decision will choose any particular option.** Options A
  through D are described so that a decision has something to weigh, not ranked.
- **That the list of ten questions is complete.** It is the set the repository's
  existing records leave open. A record answering it may find more, and should
  say so rather than quietly widen.
- **That the two stale documents will be corrected.** Naming them here is not a
  task to fix them, and this record changes neither.

### Costs

- **Work that is ready to start cannot start.** That is the decision rather than
  a side effect. The alternative is a process shape chosen by whoever writes the
  first pipeline task.
- **A record must be written and accepted before the next substantive step**,
  which is slower than building and is meant to be.
- **This record will be short-lived if the runtime decision is taken soon**, and
  it will then read as a gate that existed briefly. That is the correct shape
  for a gate.

## What this record does not decide

- **Which process shape is right.** All four options remain open.
- **When the deferred decision is taken**, or by whom it is drafted.
- **Whether `atlas-core` is eventually superseded**, renamed or split.
- **The general `apps/` import rule.** Open since ADR-0013 `:242-249` and left
  there by ADR-0014, ADR-0015, ADR-0016 and ADR-0017. This record adds no import
  anywhere and leaves it open too, while noting that Option A would force it.
- **Any `RetryPolicy` value**, and whether retrying belongs to the owner, a loop
  or a supervisor.
- **Broker startup observability**, which ADR-0017 left to a separate record and
  which this record does not claim.
- **Dependency injection, registries, factories, service containers and
  locators.** None is defined and none should be inferred.
- **Order lifecycle, routing, idempotency, fills and reconciliation.**
- **Account and portfolio state ownership.**
- **Any new configuration field or environment variable.** This record adds
  none.
- **The correction of `docs/architecture/overview.md` or the `atlas.apps.core`
  package docstring.** Both are named as hazards, not scheduled for repair.

## Relationship to ADR-0017

**Not superseded, not edited, not reopened.** ADR-0017 decided the process shape
that exists today and this record leaves it exactly as decided. What this record
adds is a constraint on the *next* change to that shape: ADR-0017 may be
superseded by a record, and by nothing else.

ADR-0017 ends by listing the questions out of scope for the task implementing
it, "each needing its own decision". This record does not answer any of them. It
converts that list from a scope boundary on one task into a standing
prerequisite on all future work, which is a different thing and is why it needs
its own record rather than an amendment to that one.

## Relationship to ADR-0016

**Not superseded, not edited, not reopened.** ADR-0016 is accepted, and this
record depends on none of its invariants. The first item on its own list of what
it does not decide — "`BrokerOwner`'s lifecycle, when `start()` is called, and
by what" — was answered by ADR-0017 for the one-shot shape, and is reopened by
nothing here; what remains open is the lifecycle beyond startup, which is
question 3 and question 4 above.

## Relationship to ADR-0013

**Not superseded, not edited, not reopened.** ADR-0013's five responsibilities
stand. ADR-0017 exercised construction, holding and lifecycle sequencing for the
duration of `main()`. Governing access remains unexercised because nothing
consumes the adapter, and supervision remains untouched. Both become live the
moment a session outlives startup, which is why they are questions 3 and 6 above
rather than anything this record settles.

## Relationship to ADR-0007 and ADR-0009

**Neither is superseded, edited or reopened.** ADR-0007's two locks arbitrate a
single thread today; question 8 asks what they arbitrate under a runtime, and
answers nothing. ADR-0009's rule that retrying is a value and the waiting
belongs to the clock is unchanged; question 7 asks who holds that value, and
chooses none.

## Relationship to ADR-0010, ADR-0011 and ADR-0012

**None is superseded, edited or reopened.** Nothing here constructs a
`TradeIntent`, an `ExecutionPolicy` or an `OrderRequest`, calls
`evaluate_exposure` or `build_order_request`, or reaches a strategy. ADR-0011's
observation that nothing places an order remains true, and ADR-0012's exposure
control is still handed nothing by nobody. Question 9 names the integration
those three records anticipate and defers it with the rest.

## Implementation implications

**No task is created by this record, and none may be created to implement it.**
There is nothing to implement: the record's whole effect is a prohibition and a
list of questions.

The next task under this record is whatever the owner authorises that does not
touch the deferred list. The next *record* is the one that answers the ten
questions, and it is a prerequisite for the work this one defers rather than a
consequence of it.
