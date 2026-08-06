# Roadmap and Task Tracker

The authoritative record of which ATLAS tasks are complete and what comes next.
A task is **Complete** only when it is merged on `main` and every gate in the
repository's definition of done passed on that commit.

Task identifiers appear in commit subjects, in `TODO(ATLAS-TASK-nnnn)` markers,
and in package documentation. This file is where they resolve to a status.

## Status

| Task | Title | Status | Commit |
|---|---|---|---|
| ATLAS-TASK-0001 | Repository bootstrap and engineering foundation | ✅ Complete | `5427475` |
| ATLAS-TASK-0001A | Repository bootstrap review fixes | ✅ Complete | `b994b18` |
| ATLAS-TASK-0002 | Broker domain models | ✅ Complete | `0498866` |
| ATLAS-TASK-0003 | The `BrokerAdapter` port | ✅ Complete | `4c7a9d7` |
| ATLAS-TASK-0004 | MetaTrader 5 broker adapter (demo foundation) | ✅ Complete | `36fa3e3` |
| ATLAS-TASK-0005 | Broker exception hierarchy | ✅ Complete | `a07dcea` |
| ATLAS-TASK-0006 | `MockBrokerAdapter` | ✅ Complete | `b11b154` |
| ATLAS-TASK-0007 | `BaseBrokerAdapter` | ✅ Complete | `1673f79` |
| ATLAS-TASK-0008 | Adapter concurrency | ✅ Complete | `e451608` |
| ATLAS-TASK-0009 | The `Clock` abstraction | ✅ Complete | `a400530` |
| ATLAS-TASK-0010 | Retry and reconnection policy | ✅ Complete | `de7e905` |

Nothing beyond ATLAS-TASK-0010 is defined, and nothing here declares what
ATLAS-TASK-0011 will be. The tasks above are the ones the repository itself
declares; this file does not speculate past them.

## Completed

### ATLAS-TASK-0001 / 0001A — engineering foundation

Poetry monorepo, PEP 420 namespace packages across 18 source roots, strict
typing, linting, formatting, containerisation, layered configuration and CI.
`atlas.config` is fully implemented because configuration *is* foundation;
every other package was an importable unit with a declared responsibility and
no implementation.

0001A was a cross-file consistency audit of the generated configuration plus
the Git topology fix. No features added.

### ATLAS-TASK-0002 — broker domain models

`Account`, `Symbol`, `Tick`, `Candle`, `Order`, `Position`, `Execution`,
`Connection` and their enumerations. Pydantic v2, frozen, `extra="forbid"`.
`Decimal` for every price, volume and money amount. Timezone-aware timestamps
normalised to UTC on the way in. Depends on no venue SDK, enforced by an AST
import scan rather than by convention.

### ATLAS-TASK-0003 — the `BrokerAdapter` port

One abstract class of 31 methods, five capability protocols, and the request
types the port speaks. Synchronous by policy. Returns domain models only —
never vendor objects, never dictionaries, never `Any`. No implementation.

### ATLAS-TASK-0004 — MetaTrader 5 broker adapter

The first real implementation of the port, for a dedicated demo account. The
port was not changed: the task exists to validate the contract against a live
venue, not to reshape it around one.

24 of 31 methods are implemented. Seven raise `NotImplementedError` with the
missing MT5 capability named at the call site — the four trading methods, plus
`subscribe_ticks` and `subscribe_candles` (the MT5 Python API polls and opens
no push channel) and `server_time` (the terminal exposes no clock).

`MetaTrader5` is imported inside exactly one function, behind a typed protocol,
never at module scope, and is an optional Windows-marked extra — so the
distribution installs and the whole suite runs on a Linux runner with no wheel
and no terminal.

### ATLAS-TASK-0005 — broker exception hierarchy

`atlas/broker/exceptions.py`: the thirteen-class `BrokerError` tree that every
`Raises:` clause in the port already named. Plain `Exception` subclasses, no
pydantic, no third-party dependency, detail carried as attributes rather than
inside the message, and constructors that only assign — these are built while a
venue is unreachable, so one that can itself fail is a liability.

Two placements are load-bearing and are asserted rather than only written down.
`BrokerAuthenticationError` sits outside `BrokerConnectionError`, so a
supervision loop retrying connection faults cannot swallow a credential that
will never work. `BrokerTimeoutError` sits inside it but means the request may
have been *executed*, which is why every state-changing method documents
reconciliation rather than retry.

On the MetaTrader 5 side the eight temporary `MT5*Error` classes are gone,
`constants.py` gained the 40 deferred `TRADE_RETCODE_*` values, and
`error_from_retcode` maps a trade server's verdict to the hierarchy. The two
integer spaces stay separate: `RES_E_*` says whether the terminal could be
spoken to at all, a retcode says what a server did with a request it received,
and each has its own total classifier with its own fallback.

No trading behaviour was added. The four trading methods still refuse, now
naming what is actually missing — filling mode per instrument, a deviation
policy, and a read-back of the resulting deals — rather than the hierarchy.

### ATLAS-TASK-0006 — `MockBrokerAdapter`

The port's second implementation: `atlas/broker/mock/`, a `MockVenue` holding
state in memory and a `MockBrokerAdapter` implementing all 31 methods against
it. Every method that MetaTrader 5 cannot honour is honoured here — the four
trading methods, both subscribe methods, and `server_time` — which is the
evidence the contract was designed against a specification rather than around a
vendor.

The venue owns the state and the adapter owns the session, so a test asserting
through `adapter.venue` and a test asserting through the port's read methods are
two independent readings that can disagree. The venue signals misuse with
`ValueError` and never with a `BrokerError`, so a test's own bug cannot be
swallowed by the error handling it is exercising.

Deterministic by construction: its own clock from 2020-01-01 UTC, sequential
identifiers from 1, no randomness, no read of the host clock.

The simulation boundary is the decision, and it is recorded in
[ADR-0006](adr/0006-mock-adapter-simulates-bookkeeping-not-price.md). A market
order fills at the published quote; nothing else happens on its own. No resting
order triggers on price, no position is revalued, the account does not respond
to trading. An attached `stop_loss` or `take_profit` is *refused* rather than
ignored, because `Position` has nowhere to report one and a silent no-op would
hide the gap for exactly as long as the position is open.

`tests/unit/broker/test_adapter_conformance.py` arrived with it: it discovers
every concrete `BrokerAdapter` in the package by walking it, and holds all of
them — not just this one — to identical signatures and the five capability
protocols.

### ATLAS-TASK-0007 — `BaseBrokerAdapter`

`atlas/broker/base.py`: a class between the port and its implementations, which
both adapters now inherit from. It is not in the port itself because a replay
engine has nothing to reconnect to and should not inherit the concept.

What moved into it is what the two adapters were genuinely duplicating: the two
cached session readings, the `Connection` snapshot assembled from them, and
`is_connected` and `health`, which need nothing but that snapshot. A subclass
answers three properties — where its state lives, and who is at the far end —
and gets both reads for free. The public `BrokerAdapter` interface did not
change, and neither adapter's observable behaviour did.

What did *not* move is the more interesting half, because each case is a real
difference rather than an accident, and lifting it would have been a regression:

- **Connecting.** MT5 re-reads the brokerage name on a redundant connect; the
  mock keys scheduled faults by operation so a test can fail `connect` and
  `reconnect` independently.
- **The clock.** MT5 stamps a heartbeat from the host; the mock stamps it from
  the venue's own clock, which is what makes it deterministic.
- **The not-connected guard.** The mock checks on entry to each method; MT5
  checks once, inside `MT5Session.terminal()`. The refusal a caller sees is
  identical, and a test asserts that across every guarded method on both.
- **Locking.** Left out here, and written next. Serialising access was behaviour
  *neither* adapter had, which made it an addition rather than part of this move
  — the reason it was excluded from a refactor whose brief was not to change
  behaviour. `base.py` was named as where it belonged, and ATLAS-TASK-0008 is
  where it went.

The class is deliberately not exported from `atlas.broker`. That namespace is
what a caller depends on, and a caller has no use for a base class; an adapter
author imports from `atlas.broker.base`. `base.py` is also in the port's AST
import scan, so the same rule that keeps a venue SDK out of the port keeps one
out of the base.

No ADR was added or changed. Nothing recorded in an existing one was reversed —
the boundary above is reasoning about *this* class, and it lives in its module
docstring where an implementer reading the class will find it.

### ATLAS-TASK-0008 — adapter concurrency

`BaseBrokerAdapter` gained two locks and, with them, the lifecycle itself.
`connect`, `disconnect` and `reconnect` are the base's own methods now: each
takes the session lock and delegates to a `_connect`, `_disconnect` or
`_reconnect` hook that the subclass supplies and that runs with the lock already
held. Neither adapter names a lock anywhere, and exactly one module in
`atlas.broker` imports `threading` — asserted by a test rather than left to
review, because duplicated locking is the failure this placement exists to avoid.

The public `BrokerAdapter` interface did not change, and neither adapter's
observable behaviour did. [ADR-0007](adr/0007-two-locks-in-the-base-adapter.md)
records the contract in full: what is guaranteed, what is deliberately not, and
why each rejected alternative was rejected. Two decisions carry it.

- **The session lock is re-entrant; the readings lock is not.** Both adapters
  compose a reconnect out of the public `disconnect` and `connect`, so the
  session lock is re-acquired on every reconnect and a plain lock would make the
  obvious way of writing `_reconnect` a self-deadlock — found in production, by
  whoever writes the third adapter, at the moment a session needed replacing. The
  readings lock is a leaf, and a plain lock there fails loudly if it ever stops
  being one.
- **Supervision is never blocked.** `health()` and `is_connected()` take no
  session lock, so a supervisor still answers while a connect is parked inside an
  unresponsive terminal — the one moment it exists for. That is asserted against
  the real connect path, by parking a real adapter inside it, rather than against
  a lock held by hand. The other twenty-six port methods take no lock at all.

One behavioural adjustment was needed, and it is a write ordering rather than a
third lock: both adapters now clear the cached readings *before* taking the
session down, which closes the window in which a racing `health()` reports no
session and a live latency in the same snapshot.

65 concurrency tests were added in `tests/unit/broker/test_adapter_concurrency.py`.
Every test asserting that something *cannot* happen is paired with one asserting
that the opposite case does, because a suite in which nothing is ever blocked is
satisfied just as well by an adapter holding no locks — which is the state this
task started from.

An 18-mutant campaign over the new synchronisation — each lock removed, weakened,
widened, aliased, shared between instances, and the teardown write order reversed
— killed 16 on the first run. Both survivors were gaps in the tests rather than
equivalent mutants: removing the lock from `reconnect` alone, and building the
`Connection` model under the readings lock. Both are killed now. The first is the
more instructive: because each half of a reconnect takes the lock on its own
account, the halves never overlap even when the outer call holds nothing, so the
tests had to be rewritten to assert the lock's *hold depth* instead.

### ATLAS-TASK-0009 — the `Clock` abstraction

`atlas/common/clock.py`: a `Clock` protocol with two methods, a `SystemClock`
that reads the host, and a `ManualClock` that moves only when told to. The first
thing `atlas.common` has ever contained, and the first time any package has taken
the dependency the architecture has permitted since ATLAS-TASK-0001.

The port has **two hands because there are two questions**, and conflating them
is the bug it exists to prevent. `now()` answers *when* — an aware UTC instant
that goes into a `Connection` and that a person reads. `monotonic()` answers *how
long ago*, and its differences are the only durations in the system that survive
a clock correction. A wall-clock step forwards reports a healthy session as an
hour silent; a step backwards makes the age negative, which compares as fresh
against every threshold and silences a supervisor at the moment it exists for.

That is what the two ways of moving a `ManualClock` encode. `advance` is time
passing and moves both hands; `set_time` is the wall clock being *corrected* — an
NTP step, an operator, a zone change — and credits no elapsed time at all. Tests
for immunity to a clock step are only worth anything against a clock that can
actually be stepped.

`BaseBrokerAdapter` gained the measurement the port had been declining to provide:
`heartbeat_age()` and `is_heartbeat_fresh(within)`. Neither stores a threshold,
schedules anything or reconnects — `adapter.py` records that the port imposes no
freshness policy, and that is still true. The policy is the supervisor's; only the
measurement moved down. Both are on the base and **not** on the 31-method port,
because widening a contract every adapter implements, for something the base gives
all of them for free, is a breaking change that buys no capability.

Injection is keyword-only and optional, so every existing `super().__init__()`
kept working. `MT5BrokerAdapter` passes a clock through and defaults to the host,
which is what production runs on. `MockBrokerAdapter` deliberately accepts **no**
clock: it takes its venue's, because a mock holding a clock its venue does not is
how a deterministic test stops being deterministic.

[ADR-0008](adr/0008-time-is-injected.md) records the decision, including why
`set_time` crediting elapsed time would have made every clock-step test pass
against a clock with no such immunity.

The lock rules from ADR-0007 constrained the implementation rather than being
revisited by it: the clock is read *before* the readings lock in all three places
that take it, because a clock arrives from outside the package and calling one
under a leaf lock is how a leaf stops being one. Neither new method touches the
session lock, so supervision is still never blocked.

130 tests were added — 36 for the clock itself, 91 for heartbeat freshness across
every discovered adapter, and 3 for the widened import rule. Nothing sleeps: a
365-day silence is asserted as an exact `timedelta`. Two are structural. No module
in `atlas.broker` may call the host clock directly, the same shape of assertion
that keeps `threading` in one file; and `test_adapter_contract.py`'s "imports
nothing but `atlas.broker`" was widened to name `atlas.common`, with the three
new tests proving the widened rule still refuses `atlas.risk`,
`atlas.execution`, `atlas.strategy` and `atlas.config`.

A 17-mutant campaign killed 16 on the first run. The survivor was a gap rather
than an equivalent mutant: `SystemClock.monotonic` returning a wall-clock
timestamp satisfied every property the tests asserted, because a wall clock is
also a float that does not go backwards within a run. It is killed now, by
asserting where the reading comes from and that the two hands have unrelated
origins. One equivalent mutant remains and is left alone — reading the venue
clock's private instant instead of calling `now()` differs only by a lock
acquisition on a value whose read is already atomic.

### ATLAS-TASK-0010 — retry and reconnection policy

`atlas/common/retry.py`: a frozen `RetryPolicy` and a `retry_call` that executes
one. A retry loop written inline is three decisions welded to a call site — how
many attempts, how long between them, and which failures are worth repeating —
and welded they cannot be configured, cannot be tested without provoking the
failure they exist for, and get rewritten slightly differently at the next call
site. This takes them apart.

**The policy is a value.** It holds no clock, no exception types and no reference
to whatever is being retried, so it can be built in a config module, compared,
logged and asserted on. `delays()` returns the whole schedule as a tuple, which
is what makes "exponential backoff progresses 1, 2, 4" a statement about a value
rather than about a run. Four named constructors — `none`, `immediate`, `fixed`,
`exponential` — and a constructor that refuses a policy that could not mean what
it says: fewer than one attempt, a negative delay, a multiplier below one that
would *shrink* each wait, or a ceiling below the first delay that would make
`initial_delay` a silently ignored field.

**The default is one attempt.** Retrying is opted into. A policy that retried by
default would change the behaviour of code that never asked for it, and the only
symptom of a wrongly retried call is that it took longer to fail — which is also
what makes the regression evidence possible: every adapter constructed the way it
was before this task behaves exactly as it did.

**The waiting belongs to the clock.** `Clock` gained a third member, `sleep`, and
it is the port's only *verb*. It is there rather than on a separate `Sleeper`
because waiting and elapsed time are one fact, and two collaborators that must
agree about elapsed time are a bug surface. `ManualClock.sleep` is `advance`, so
a hundred-second backoff runs in no time and the resulting instant is asserted
exactly. Nothing in `retry.py` reads the host clock, and a static scan in
`tests/unit/common/test_retry.py` asserts it — a real sleep would leave a manual
clock exactly where the assertions expect it, and pass.

**Which failures is a domain fact, so it is a parameter.** `retry_call` takes
`retry_on` and a `give_up_on` that carves types back out of it, and `base.py`
states the broker's answer by reading the exception tree that already existed:
`RETRYABLE_ERRORS = (BrokerConnectionError,)`, `PERMANENT_ERRORS =
(BrokerNotConnectedError,)`. `BrokerAuthenticationError` needs no entry because
ATLAS-TASK-0005 deliberately did not make it a `BrokerConnectionError` — a
credential the venue refused is not going to be accepted on the third ask. The
tree had encoded that distinction for five tasks and nothing had ever read it.

Integration is in `BaseBrokerAdapter` and nowhere else. `connect` and `reconnect`
are wrapped; `disconnect` is not, because the port requires it to succeed and
retrying a teardown is repeating an operation the venue may already have honoured.
Both adapters inherit it and neither implements any of it.

Two consequences the lock rules forced. **Attempts do not multiply**: MT5's
`_reconnect` is composed from the public `disconnect` and `connect`, so a naive
wrapper would make a three-attempt policy mean nine attempts there and three on
the mock. A `_retrying` flag, read and written only under the re-entrant session
lock and cleared in a `finally`, makes only the outermost call retry. And **the
backoff waits inside the session lock**, because ADR-0007 fixed that a reconnect
is one critical section and not two; `health()`, `is_connected()` and
`heartbeat_age()` take no session lock, so supervision still answers throughout a
sixty-second backoff, and both halves of that are asserted from a second thread.

[ADR-0009](adr/0009-retry-is-a-value-and-the-waiting-is-the-clocks.md) records
the decision and nine rejected alternatives. `packages/common/src/atlas/common/README.md`
was written, closing the gap ATLAS-TASK-0009 observed.

183 tests were added — 61 for the policy and `retry_call`, 110 across every
discovered adapter, and 13 for `Clock.sleep`. A 34-mutant campaign killed 33 on
the first run. The survivor was a gap rather than an equivalent mutant: the first
attempt's delay being zero was asserted only against `RetryPolicy.none()`, whose
`initial_delay` is zero anyway, so returning `initial_delay` there was the same
answer by accident. It is killed now by asking the same question of a policy that
actually waits.

## Known documentation debt

- **ADR-015 and ADR-016** were declared dependencies of ATLAS-TASK-0004 but do
  not exist. `docs/adr/` currently ends at 0009.
- **Version.** ATLAS-TASK-0004 was specified as `v0.2.0-alpha`; `pyproject.toml`
  and `README.md` still declare `v0.1.0-alpha`. A contract test ties the
  `atlas-core` image tag to `[project].version`, so a bump touches all three.
- Several `docs/` pages carry a "Status at ATLAS-TASK-0001" banner that predates
  the broker work.
