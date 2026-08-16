# ADR 0017 — Startup opens a broker session, verifies it and closes it; `atlas-core` is not a long-running process

**Status:** Proposed
**Date:** 2026-08-16

## Context

Three accepted or proposed records converge on a question none of them answers.

ADR-0013 decided that `apps/atlas-core` owns the `BrokerAdapter`, and listed
five responsibilities: construction, holding, governing access, lifecycle
sequencing, and the supervision duty ADR-0007 assigns to a caller. ADR-0015
decided that the application selects `MT5BrokerAdapter` and constructs it during
startup, and drew the line that this record begins at: "Deciding that an adapter
is *constructed* at startup therefore decides nothing about when a session is
*opened*." ADR-0016 refuses broker configuration that cannot open a session, and
names the remaining gap in its own words: "**`BrokerOwner`'s lifecycle**, when
`start()` is called, and by what."

The repository built the mechanism and left it uncalled. `BrokerOwner` exists
with `start()`, `stop()` and a governed `adapter` property; every one of its
transitions is tested against a real `MockBrokerAdapter`, including a refused
second start, a silent no-op stop, a double stop, a propagated connect failure,
and a start that succeeds once the venue stops refusing. `composition.py` builds
one on every startup. And `__main__.py` then drops it on the floor, with a
comment that says why:

> Constructed and dropped. ADR-0015 decided that startup builds the adapter;
> nothing yet decides what holds one afterwards, and inventing a home for it
> here would answer a question no record has answered.

That comment was correct and remains the reason this record exists. The
consequence of leaving it unanswered is not neutral. `__main__.py`'s own
docstring already claims that exit `0` means configuration "describes a broker
session that could be opened", and nothing opens one — the claim is a statement
about four validated values, not about a venue. ADR-0016 makes the mismatch
sharper rather than smaller: it deliberately declines to probe the terminal
path, and routes "a wrong, relative or absent path" into `connect()`, a method
no production code calls. An entire class of unusable deployment was assigned to
a stage the process never reaches.

The question underneath all of this is not "when is `start()` called". It is
what a running `atlas-core` process *is*, and no record poses it. Until it is
answered, every downstream question — what startup success means, what a failed
connection does, who closes the session, whether anything runs afterwards — is
unanswerable, because each has a different answer for a process that checks and
exits than for a process that holds a session and trades.

**The owner has answered it.** `atlas-core` is a startup connectivity check: it
connects to the configured broker, verifies that a session can be established,
cleanly stops the owner, and exits. It is not a long-running trading process.
This record writes that decision down and settles what mechanically follows from
it, and nothing else.

## Decision

**`atlas-core` performs a startup broker connectivity check. It resolves
configuration, constructs the adapter and owner, opens a session, treats the
opening as the verification, closes the session on every path, reports the
outcome and exits. It acquires no run loop, holds no session past its own
startup, and does not become a long-running process.**

### The sequence

1. Resolve `AtlasSettings` (`load_settings`).
2. Build the owner (`build_broker_owner`), which translates `BrokerSettings`
   into an `MT5Config` and constructs an `MT5BrokerAdapter` from it — ADR-0015
   and ADR-0016, unchanged.
3. Retain the owner for the remainder of `main()`.
4. Call `BrokerOwner.start()`, which calls `connect()`.
5. Call `BrokerOwner.stop()` unconditionally, on the success path and on every
   failure path.
6. On success, write the startup record to stdout and exit `0`.
7. On a failed connection, write one JSON object to stderr and exit `3`.

Steps 1 and 2 already exist. Steps 3 through 7 are what this record decides.

### `start()` returning is the verification, and nothing polls

**Verification is exactly that `start()` returns without raising. No further
call is made to confirm it.**

`connect()`'s contract is that it establishes a session or raises, and
`MT5Session.connect` already confirms success by reading the account rather than
by trusting `initialize()` — its own note explains that "a session that claims
to be up but cannot see an account is the state that produces the most confusing
downstream failures". The venue-side confirmation this record would otherwise
have to specify has already been specified, one layer down, and repeating it
here would be second-guessing a contract rather than relying on it.

A confirming call to `is_connected()` or `health()` after a successful `start()`
would be polling, and polling is the supervision surface. Both are named in
`UNCALLED_PORT_OPERATIONS` in `tests/unit/test_core_broker_boundary.py`,
alongside `reconnect`, `ping` and `latency`, under a comment that identifies
them as "the supervision surface" and "the polling that a supervision loop would
do". This record does not touch that list, and the check it decides is
deliberately shaped so that it does not have to.

### Startup success now means a session was opened

Exit `0` changes meaning, and this is the decision rather than a side effect. It
currently means that configuration resolved and satisfies its invariants. It
comes to mean that, **and** that a session was opened against the configured
venue and closed again.

The startup record is written after `stop()` has run, so a success line is never
emitted by a process that still holds a session open. The record's content is
unchanged (below); only the condition under which it is written moves.

### Shutdown is unconditional, deterministic, and adds no new semantics

`stop()` runs on every exit path, in a `finally` or an equivalent construct that
cannot be skipped by an exception. This requires nothing new from `BrokerOwner`,
because the two cases are already decided and already tested:

- After a successful `start()`, `stop()` calls `disconnect()` and clears the
  started flag.
- After a failed `start()`, the owner was never started, and `stop()` is a
  silent no-op — `tests/unit/test_core_broker_ownership.py` proves both that a
  failed start leaves the owner un-started and that it can still be unwound.

`disconnect()` cannot raise: the port states "Raises: BrokerError: Never" and
requires it to be safe on "a cleanup path that cannot know the current state",
and `MT5Session.disconnect` implements that by suppressing failures inside
`shutdown()`. An unconditional `stop()` therefore cannot convert a successful
check into a failed one, and cannot mask the error that sent the process into
cleanup.

**No context manager, no `atexit` hook and no signal handler is introduced.** A
process whose entire life is one function call does not need a shutdown protocol
beyond the language's own unwinding, and inventing one here would prefigure the
lifetime this record explicitly refuses to give the process.

### A failed connection is its own failure, with its own exit code

`BrokerError` and its subclasses propagate out of `start()` "unchanged and
unwrapped", exactly as `BrokerOwner` documents. `main()` catches `BrokerError` —
the root of the tree, which `exceptions.py` describes as "what a supervision
loop wants" precisely because it catches everything the port can raise — and:

- writes **one JSON object to stderr**, carrying an `event` key and the error's
  message, in the shape the existing `startup_failed` path established;
- leaves **stdout empty**;
- returns **exit code `3`**.

**The exit code is `3`, and it is new.** `0` and `2` are taken and have
published meanings in `__main__.py`'s docstring. `1` is what CPython returns for
an unhandled exception, so reserving it keeps "the check ran and the venue
refused" distinguishable from "the process crashed before it could tell you
anything". `3` is the next free integer and carries one meaning: configuration
was usable, and a session could not be opened.

**The `event` value must differ from `atlas.core.startup_failed`.** The literal
string is left to the implementing task, as ADR-0015 left the wording of a
failure record ("what the failure record says — is an implementation question"),
but its distinctness is decided here, because a log stream in which the two
failures share an event name re-conflates on the way out what the exit codes
separate on the way in.

**No retry, no fallback, no degraded mode.** The process does not try again, does
not substitute `MockBrokerAdapter`, and does not continue without a broker.
ADR-0015 forbade the last two by name and this record adds nothing to that
prohibition; the first is a reconnect decision and is left where ADR-0009 left
it.

### Configuration failure and session failure are different failures

This record turns on the distinction, which is the same one ADR-0016 drew
between "not configured" and "configured but unusable on this machine", now
carried through to the process's observable surface:

| Failure | Stage | Exit | Stream | Meaning |
|---|---|---|---|---|
| Configuration invalid, or broker section untranslatable | rows 1–2 of ADR-0015's table | `2` | stderr, `atlas.core.startup_failed` | nothing about this deployment could ever open a session |
| Session could not be opened | row 4 of ADR-0015's table | `3` | stderr, a distinct event | the configuration was usable; this host, venue or credential was not |

`ConfigurationError` keeps its own `except` branch and its own exit code, ahead
of the broker branch in source order, and **ADR-0016's behaviour is preserved
byte for byte**: the same `ConfigurationError`, the same single JSON line on
stderr, the same empty stdout, the same exit `2`, and — because translation
still precedes construction — no adapter built, no owner created and no session
opened when configuration is refused.

### The lifecycle is in-line and single-threaded

**For this slice, `start()` and `stop()` are called from `main()`, on the
process's only thread, with nothing running concurrently.**

This is not a concurrency design; it is a decision not to have one. ADR-0007's
two locks are per instance and remain untouched, and this record neither relies
on them nor adds to them, because there is exactly one caller. `BrokerOwner`'s
documented limit — that `start` and `stop` "are not safe to call from two
threads at once", a limit "recorded here, not solved here" — is not reached, and
that docstring stays true as written rather than becoming stale.

No thread, timer, executor, task, event, lock or condition is created. No
`asyncio` is introduced; ADR-0007 already rejected it as out of scope and cited
ATLAS-TASK-0003's "do not use async", and this record does not reopen either.

### One connection attempt, inherited rather than chosen

`composition.py` passes no `retry` to `MT5BrokerAdapter`, so `BaseBrokerAdapter`
applies its documented default of `RetryPolicy.none()` — one attempt, no delay.
The connectivity check therefore makes exactly one attempt.

**This record chooses no `RetryPolicy` value.** It records the value the
existing composition already produces, which becomes observable for the first
time because `connect()` is called for the first time. ADR-0009's statement that
a policy "is constructed by whoever constructs the adapter" is unchanged, and
supplying a different one remains an open decision — one that would have to
argue for a specific number of attempts and a specific delay, which is a
question about a deployment and not one this record has evidence for.

A check that retried would also be doing something else. ADR-0009 is explicit:
"Nothing decides to reconnect… Noticing a session has gone quiet and deciding to
replace it is the supervision layer's job, and it still does not exist." A
connectivity check that retried a refused connection would be the first
increment of that layer, taken without a record.

### The startup record is unchanged

`build_startup_record` keeps its eight keys. No broker key, no login, no server,
no terminal path and no password enters it. ADR-0015's rule stands verbatim —
"The password may never enter the record under any future decision" — and
`tests/unit/test_core_entrypoint.py`'s assertions that the section is absent and
that neither a login nor a password reaches the rendered line continue to hold.

If a successful connectivity check should be observable in the record, that is
broker startup observability, which ADR-0015 already assigned to "a separate
decision with its own record". This is not that record.

### The process does not become long-running

`atlas-core` acquires no run loop, no scheduler, no supervision timer and no
consumer of the owner. It exits after step 6 or 7 as it exits today.
`docker-compose.yml`'s `restart: "no"` therefore remains correct and is not
modified, and its comment's condition — "This becomes `unless-stopped` once the
service acquires a run loop" — remains untriggered.

`docs/architecture/overview.md`'s charter row, which describes `atlas-core` as
owning an event loop, is unchanged and remains what ATLAS-TASK-0021 and
ATLAS-TASK-0025 each independently ruled it: a charter, not a statement of
implementation status.

## Alternatives considered

**Leave the lifecycle uncalled.** Rejected by the owner decision, and it was
already the weaker of two honest positions: the entrypoint's docstring claims
exit `0` means a session "could be opened", and ADR-0016 deliberately defers a
failure class to a `connect()` nothing calls. Keeping the status quo means
keeping a deployment check that reads stronger than it is.

**Hold the session open for the life of the process.** Rejected: this is the
option the owner did not take. It also cannot be taken by this record, because a
process that opens a session and then has nothing to do with it is a process
that needs a run loop, a consumer and a supervision policy — three decisions
this record is not authorised to make and has no evidence for.

**Reuse exit `2` for a failed connection.** Rejected: it is the failure this
record is required to keep distinguishable. Exit `2` currently means the
configuration is unusable everywhere, on every host; a refused session means it
was usable and something else failed. Collapsing them would tell an operator to
edit configuration that is correct.

**Exit `1`, or let the exception escape.** Rejected: `1` is what CPython
produces for an unhandled exception, so it cannot distinguish a handled venue
refusal from a crash. Letting the exception escape also replaces a single JSON
object on stderr with a traceback, abandoning the machine-readable failure shape
every other path in this entrypoint uses.

**Confirm the session with `is_connected()` or `health()` after `start()`.**
Rejected: those are the supervision surface, `UNCALLED_PORT_OPERATIONS` names
them as such, and a single confirming poll is the shape from which a polling
loop grows. The port already guarantees that `connect()` raises rather than
returning a dead session, and `MT5Session.connect` already reads the account to
prove it.

**Retry the connection before giving up.** Rejected: choosing attempts and
delays is a `RetryPolicy` decision ADR-0009 assigned to whoever constructs the
adapter, and deciding *when* to try again is the supervision question ADR-0009
says nothing has yet decided.

**Make the check conditional — skip it outside production, or on hosts without a
terminal.** Rejected, and this is the alternative that looked most attractive.
It would make the meaning of a successful startup a property of the machine that
performed it, which is exactly what ADR-0016 refused when it declined to
validate the terminal path's existence: "each makes configuration validity a
property of the machine doing the validating rather than of the configuration."
A check that passes because it did not run is worse than no check, because it
reports success.

**Emit the check's outcome in the startup record.** Rejected: it adds a key to a
record ADR-0015 froze, and observability of broker startup is already reserved
to a separate record.

## Consequences

### Guaranteed

- A process that exits `0` has opened a session against the configured venue and
  closed it again. The claim in `__main__.py`'s docstring becomes true rather
  than aspirational.
- No process exits holding a broker session. `stop()` runs on every path, and
  after a failed start it is a no-op that is already tested.
- Configuration failure and session failure are distinguishable by exit code
  (`2` versus `3`), by event name, and by which of ADR-0015's four stages
  produced them.
- ADR-0016's refusal is untouched: same exception, same record, same exit `2`,
  same empty stdout, and still no adapter, no owner and no session when
  configuration is refused.
- The startup record keeps its eight keys, and no credential reaches stdout.
- The password cannot reach either stream. It is read only to build an
  `MT5Config` and is passed only into the terminal's `initialize`; no code path
  that formats a broker error message reads it.
- `apps/atlas-core` acquires exactly one new import, and it is an exception
  type. `start` and `stop` are not in `UNCALLED_PORT_OPERATIONS`,
  `PIPELINE_PACKAGES` is unchanged, and no adapter is bound at module scope.
  What does change is the import census: reporting a session that would not open
  means naming `BrokerError` in `__main__.py`, and
  `tests/unit/test_core_broker_boundary.py` currently pins the set of modules
  that reach `atlas.broker` to the two that own and construct an adapter.
  **That contract must be widened by the task that implements this record**, to
  permit the entrypoint that one name and nothing else — the same course
  ADR-0015 `:263-268` set when its decision contradicted the same file, and
  which ATLAS-TASK-0023 then carried out. Widening it further, or touching
  `UNCALLED_PORT_OPERATIONS` or `PIPELINE_PACKAGES`, would mean the
  implementation had left the seam ADR-0013 drew.
- Exactly one thread, one adapter, one owner, one process. `BrokerOwner`'s
  "not synchronised" limit stays unreached and its docstring stays accurate.

### Not guaranteed, deliberately

- **That the venue is reachable a moment later.** The check is a point-in-time
  observation taken at startup, and this record schedules no second one. Nothing
  detects a session that goes away, because nothing holds one.
- **That the credential is still valid, or the terminal still installed.** Both
  were true once, at startup, on that host.
- **That a process which exits `0` can trade.** It can open a session. Trading
  requires the pipeline, which remains unwired.
- **That `stop()` closed anything.** After a failed start it is a no-op by
  design, and the record does not distinguish the two in its exit status,
  because in both cases the process holds nothing.

### Costs

- **`atlas-core` can no longer complete successfully in the container this
  repository builds.** `pyproject.toml` declares the MetaTrader5 package under a
  `sys_platform == "win32"` marker; the image is `python:3.12-slim-bookworm`.
  `MT5Session.connect` raises `BrokerConnectionError` when "the package is not
  installed", so under this decision `docker compose up atlas-core` on Linux
  exits `3`, always, and CI's `ubuntu-latest` runner is in the same position.
  **This is the decision working, not failing** — a connectivity check on a host
  that cannot reach the venue should say so — but it changes what the local
  stack can demonstrate, and it is the largest consequence of this record. The
  runbook's "runs the config self-check, then exits 0" and `docker-compose.yml`'s
  comment describing a process that "performs a configuration self-check and
  exits 0" both become incomplete, and correcting them is work for the
  implementing task.
- **Existing entrypoint tests stop passing unmodified.**
  `test_valid_configuration_exits_zero_and_emits_one_json_line` runs `main()`
  with a fully configured broker section and asserts exit `0`; under this record
  it reaches a real `connect()` on a runner with no terminal. That test must
  change, and adjusting it is implementation, not decision.
- **The account number may appear on stderr.** `MT5Session` formats one error
  message as "terminal started but account `<login>` is not available", so a
  broker failure record can carry the login. The password cannot, and stdout is
  unaffected. This is accepted rather than solved: redacting it would mean
  introducing a logging or masking policy, which ADR-0015 explicitly declined to
  add. A future observability record may revisit it.
- **Startup gets slower and gains a network dependency.** A process that
  resolved configuration and exited now waits for a terminal to start and a trade
  server to answer, with `RetryPolicy.none()` and whatever timeout `MT5Config`
  carries. Startup time becomes a property of the venue.
- **A third exit code is a public interface.** Anything that reads
  `atlas-core`'s exit status — an operator, a runbook, an orchestrator — now has
  three cases to handle instead of two.

## What this record does not decide

- **The run loop.** `atlas-core` acquires none, and this record explicitly
  declines to give it one. A long-running process is a separate decision.
- **Supervision, the health timer, and any scheduled check.** ADR-0013's fifth
  responsibility stays assigned and unimplemented, exactly where ADR-0015 and
  ADR-0016 left it.
- **Reconnect triggering, and failover of any kind on any signal.** ADR-0009's
  "nothing decides to reconnect" stands.
- **A production `RetryPolicy` value.** This record reports the value the
  existing composition already produces and chooses none.
- **Background threading, `asyncio`, or any concurrency design.** One thread,
  in-line. Anything else needs a record.
- **Multiple adapters, multiple venues or multiple accounts.** One adapter, one
  owner, one process, as ADR-0015 left it.
- **The execution pipeline, `ExecutionPolicy` production, and strategy → risk →
  execution wiring.** Every symbol in that chain remains defined and
  unconstructed, and this record wires none of it. `apps/atlas-core` imports no
  pipeline package and the boundary test that forbids it is unchanged.
- **Risk-state ownership.** ADR-0012's "not who calls the control, not who hands
  it state" is untouched, and its revisit condition stays as satisfied and as
  unexercised as ATLAS-TASK-0023 left it.
- **The general `apps/` import rule.** Unchanged from ADR-0013 and left there by
  ADR-0014, ADR-0015 and ADR-0016. This record adds no import to any application
  and grants nothing to `apps/dashboard` or `apps/research`.
- **Dependency injection, registries, factories, service containers and
  locators.** None is defined and none should be inferred; ADR-0015's rule that
  an implementation task must argue for one on its own evidence is unchanged.
- **Order lifecycle, routing, idempotency, fills and reconciliation.**
- **Account and portfolio state ownership.**
- **`server_utc_offset`, and any new configuration field or environment
  variable.** This record adds none.
- **Broker startup observability.** Whether a successful check appears anywhere
  other than the process's exit status remains a separate record's question.
- **The literal `event` string of the new failure record**, beyond the
  requirement that it differ from `atlas.core.startup_failed`.
- **Filesystem instrumentation in the MT5 connection tests.** Unrelated and
  untouched.

## Relationship to ADR-0013

**Not superseded, not edited, not reopened.** This record implements the second
and fourth of ADR-0013's five responsibilities and no more. Holding: the owner
is retained for the process's life, which for this process is the body of
`main()`. Lifecycle sequencing: "`connect`, `disconnect` and `reconnect` are
called by the owner, in an order the owner chooses" — the order chosen here is
connect, then disconnect, and `reconnect` is not called at all.

Responsibility three, governing access, is unexercised: nothing is handed the
adapter, because nothing consumes it. ADR-0013's refusal to name a mechanism
therefore still applies with full force, and this record names none.
Responsibility five, supervision, is untouched.

## Relationship to ADR-0015

**Not superseded, not edited, not reopened.** Its selection, its translation
boundary, its placement of construction at startup and its four-stage table all
stand. This record occupies the fourth row of that table — "Terminal connection
| `connect()`, via `BrokerOwner.start()`" — and decides the error surface for it,
which ADR-0015 answered only for the second row.

ADR-0015's six-step intended lifecycle ends at "`BrokerOwner` governs lifecycle
and access on its existing terms". This record supplies the terms: start once at
startup, stop unconditionally, never reconnect, never poll. `BrokerOwner`'s
semantics are redefined in no respect — the same `RuntimeError` on a second
start, the same no-op stop, the same `BrokerNotConnectedError` before start and
after stop.

"Construction is not connection" is not weakened. It is the sentence that made
this record necessary and separable: because construction decided nothing about
when a session opens, the decision was available to be taken here.

## Relationship to ADR-0016

**ADR-0016 is not accepted, not edited, not reopened, and its status is
unchanged.** It remains `Proposed`, and this record neither treats it as
accepted nor depends on its acceptance. Its behaviour is preserved as
implemented, and its refusal keeps its own exception, exit code, stream and
record.

This record answers, and only for the process shape the owner has chosen, the
first item on ADR-0016's own list of what it does not decide. That is the normal
relationship between records here: a later record answers an earlier record's
open question without editing it.

One dependency runs the other way and is worth stating. ADR-0016 chose not to
probe the terminal path and accepted that "a wrong, relative or absent path
still fails at `connect()`". Under this record, that failure now has somewhere
to land: it becomes a startup failure with exit `3` rather than a failure at a
call site that does not exist. If ADR-0016 were ever rejected rather than
accepted, what a usable configuration means would change, and this record's
division between exit `2` and exit `3` would need revisiting.

## Relationship to ADR-0007 and ADR-0009

**Neither is superseded, edited or reopened, and neither is redesigned.**

ADR-0007's two locks stay where they are, doing what they do. This record adds
no concurrency for them to arbitrate; its single thread is the trivial case they
already cover. The caller ADR-0007 left to sequence its own lifecycle calls is
the one ADR-0013 named and this record finally instantiates, with the simplest
possible sequence.

ADR-0009's retry mechanism is unchanged and unwired beyond what already exists.
This record calls `connect()` for the first time, which makes the existing
`RetryPolicy.none()` default observable, and chooses nothing.

## Relationship to ADR-0011 and ADR-0012

**Neither is superseded, edited or reopened.** Nothing here constructs a
`TradeIntent`, an `ExecutionPolicy` or an `OrderRequest`, calls
`evaluate_exposure` or `build_order_request`, or reaches a strategy. ADR-0011's
"nothing places an order" and its observation that the policy remains "a hole in
the contract" are both still true after this record, and ADR-0012's exposure
control is still handed nothing by nobody.

## Implementation implications and future task boundary

**No task is created by this record.** What follows describes the boundary a
future task would work inside, so that its scope can be judged before it is
authorised.

Definitely required:

- `apps/atlas-core/src/atlas/apps/core/__main__.py` — retain the owner, call
  `start()`, call `stop()` on every path, add the third exit code and the broker
  failure branch, and update the module docstring's exit-code list.
- `tests/unit/test_core_entrypoint.py` — the valid-configuration test reaches a
  real `connect()` under this record and cannot pass unmodified. New tests for
  the success sequence, the unconditional stop and the exit-`3` path belong
  here, and must be shown to be capable of failing.

Potentially required, depending on how the task is written:

- `docker-compose.yml` and `docs/runbooks/local-stack.md` — both describe a
  process that exits `0` after a configuration self-check, which stops being the
  whole truth. `restart: "no"` stays correct; only the prose is affected.
- `docs/ROADMAP.md` — a row, as every prior task added one.

Explicitly out of scope for that task, each needing its own decision:
supervision, the health timer, reconnect, failover, a run loop, threading, the
execution pipeline, the `apps/` import rule, a `RetryPolicy` value, broker
startup observability, and ADR-0016's status.

A third file is definitely required, and it is stated apart from the list above
because it is the load-bearing check on this record's scope:
**`tests/unit/test_core_broker_boundary.py` must be widened, and by exactly one
name.** That file pins the set of modules permitted to reach `atlas.broker`,
and reporting a session that would not open means naming `BrokerError` in
`__main__.py`. The task that implements this record therefore widens the import
census to grant the entrypoint that one name and nothing else — no adapter, no
configuration type, no second error — and leaves every other constraint in the
file standing, the same course ADR-0015 `:263-268` set and ATLAS-TASK-0023 then
carried out. If an implementation finds itself editing
`UNCALLED_PORT_OPERATIONS` or `PIPELINE_PACKAGES`, or granting the entrypoint a
name beyond `BrokerError`, it has left the decision this record makes.
