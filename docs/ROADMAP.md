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
| ATLAS-TASK-0010 | Retry and reconnection policy | ✅ Complete | `de7e905` ‡ |
| ATLAS-TASK-0011 † | The risk boundary: `TradeIntent` and `RiskVerdict` | ✅ Complete | `f54ad613` |
| ATLAS-TASK-0012 † | The strategy boundary: producing a `TradeIntent` | 🚧 In progress | `PENDING` |

† **Newly specified, not recovered.** The unmarked rows are evidenced by the
repository record: the task existed, and the commit it cites is the work.
ATLAS-TASK-0011 and ATLAS-TASK-0012 were each specified and authorised as new
work during the task itself. Their presence in this table is not evidence that
either was previously planned, and neither may be described as recovered project
history or as previously completed.

ATLAS-TASK-0012 is **not complete**, and the row says so. Work exists on a local
branch, it is not on `main`, and CI has never run on it. The definition at the
top of this file is the one that governs: a task is Complete when it is merged
and every gate passed on that commit, and neither has happened. The commit
column stays `PENDING` until it can cite a commit that is actually on `main`.

‡ **The gates passed one commit later.** `de7e905` is where ATLAS-TASK-0010's
work lives and it is on `main`, which is why it is the commit cited. The tree at
that commit did not itself pass CI: the run covering it failed at Pytest, and CI
was first green at `6cca03d`, which corrected a flaky clock test. The citation
is left as the feature commit — the history is not rewritten — and the gap
against the definition of **Complete** above is recorded here instead.

Nothing beyond ATLAS-TASK-0012 is defined, and nothing here declares what
ATLAS-TASK-0013 will be. The tasks above are the ones the repository itself
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

### ATLAS-TASK-0011 — the risk boundary

Newly specified rather than recovered from the repository record — see the note
marked † under the status table.

`atlas/risk/contracts.py`: `TradeIntent`, `RiskVerdict`, `VerdictStatus` and
`RejectionReason`. The architecture's first invariant — a trade intent becomes
an order only by passing through `atlas.risk`, and every other safety property
depends on it — had been prose for ten tasks. Nothing said what an intent *was*,
or what passing through risk *returned*. This gives the invariant its
vocabulary.

**The shape that was avoided.** Left undefined, the boundary gets decided by
whichever task needs it first, and the likely accident is a strategy that builds
the thing execution already accepts — an `OrderRequest` — with risk invoked to
validate it afterwards. At that point risk is advisory: the object exists, its
size is chosen, and the only power left is to veto a decision someone else has
made. `OrderRequest` had already said where the line is, in its own words: whether
a request is *wise* "is a risk decision, made against state neither this model nor
the port can see". These are the types that decision is expressed in.

**A verdict is two-valued, and the number carries the nuance.** A reduced-size
approval is `APPROVED` with a smaller `approved_volume`, not a third status. A
`REDUCED` member would force every consumer to handle two spellings of "yes",
and the first one to handle only `APPROVED` sizes the position off the requested
volume — silent, correct-looking in every test that does not reduce, and wrong
only in the case the status was added for. `approved_volume` is `None` on a
rejection, which makes ignoring the status uninteresting rather than merely
forbidden: there is no number to bypass with.

**Risk may reduce; it may never enlarge.** A validator refuses an
`approved_volume` above the requested one. A boundary that can return a larger
number than it was given is a second, unreviewed sizing authority.

**The primitives are the broker's.** `SymbolName`, `OrderSide`, `Price` and
`Volume` are imported rather than redefined, for the reason `broker/types.py`
gives for its own aliases — two definitions of one concept diverge, and these
would diverge exactly at the translation boundary, where nobody is looking. That
adds `atlas.risk → atlas.broker`, the second edge between feature packages in
the graph and the first since `broker → common`. It runs downward, and
`tests/unit/risk/test_risk_boundary.py` asserts it did not become several, that
no risk module names `OrderRequest`, `OrderType`, `BrokerAdapter` or any order
verb, and that `atlas.broker` still contains no import of `atlas.risk`.

**What this task does not claim.** `atlas.strategy` and `atlas.execution` remain
empty stubs, so nothing produces an intent and nothing consumes a verdict. The
invariant has two halves — risk cannot be bypassed, and execution acts only on
approved output — and only the structural half is provable today. The boundary
test records that limitation in its own docstring rather than leaving a reader
to infer the coverage is wider than it is. No sizing algorithm, exposure limit,
drawdown control, correlation cap or kill switch exists; constructing an
`APPROVED` verdict does not make it true.

[ADR-0010](adr/0010-the-risk-boundary-is-a-verdict-on-an-intent.md) records the
decision and eleven rejected alternatives.
`packages/risk/src/atlas/risk/README.md` was written.

117 tests were added — 29 for the intent, 37 for the verdict and 51 for the
boundary, including six that assert the AST scanners can actually fail, because
a scan that inspects nothing passes everything. A 30-mutant campaign killed 29.
The survivor is equivalent and is left alone: removing `@unique` from
`VerdictStatus` changes no behaviour while the members' values stay distinct,
and `enum.unique` leaves no runtime marker to assert against — it guards a
future edit rather than a current one.

## In progress

### ATLAS-TASK-0012 — the strategy boundary

**Not complete.** What follows describes work on a local branch. It is not on
`main`, no PR exists, and no CI run has covered it. It is recorded here rather
than under **Completed** because the definition of Complete at the top of this
file is not met, and describing it as met would make this file wrong.

Newly specified rather than recovered from the repository record — see the note
marked † under the status table.

`atlas/strategy/contracts.py`: `Strategy`, a runtime-checkable protocol with one
method, `propose(observation, /) -> TradeIntent | None`. ATLAS-TASK-0011 gave the
first invariant its vocabulary; this gives it a producer. A strategy is the only
thing in Atlas that originates a `TradeIntent`, and returning one or returning
`None` is the whole of its authority.

**A protocol, not a base class.** Structural typing, for the reason
`atlas/broker/protocols.py` gives for the capability protocols: nothing has to
inherit from these. A strategy is a behaviour, and a required base class would
mean a research notebook, a replay harness and a live component could not be the
same thing unless all three imported it. It would also hand this package a
concrete class to put shared behaviour in, and the first thing that lands in one
is a lifecycle — which this task does not own.

**The input is a type parameter this package does not name.** `Strategy[InputT]`
is generic because what a strategy looks at belongs to `atlas.market`,
`atlas.features` and `atlas.regime`, which are all still stubs. Naming a
concrete input here would fix their shape before they exist, from the package
with the least standing to do it. No market-data contract is defined by this
task. `observation` is positional-only, so an implementation may name it
whatever reads best.

**`None` is the answer to "no opinion".** The alternative — an empty intent, or
a sentinel meaning "ignore me" — puts a value into the pipeline that looks
tradeable, and the first consumer that forgets to check it sends it to risk.
There is no such object to forget about.

**No dependency on `atlas.broker` at all.** `atlas.risk` is the only `atlas`
package a strategy module imports. A `TradeIntent` is stated in `SymbolName`,
`OrderSide`, `Price` and `Volume`, and under `mypy --strict` with `init_typed`
anything that *builds* one must name them — `TradeIntent(side="BUY")` is a type
error even though the string works at runtime. The conclusion drawn is that
nothing in the package builds one: the contract names `TradeIntent` in an
annotation, and a concrete intent is constructed by whoever hands one over,
which today is test code. `BrokerAdapter`, `OrderRequest`, `OrderType`,
`OrderStatus` and the four order verbs appear nowhere in the package, and
nothing was re-exported through `atlas.risk` to get around the rule.

**An inert reference implementation.** `atlas/strategy/reference.py` holds
`ConstantStrategy`, which answers with the intent it was constructed with,
whatever it is shown — `ConstantStrategy()` abstains and
`ConstantStrategy(intent)` recommends that intent. It reads no market data,
performs no I/O, holds no clock, draws no randomness, calls no venue and raises
nothing of its own, and the tests assert each of those against its source rather
than trusting the sentence. That inertness is the design: a reference
implementation that could see a price is one edit away from being a trading
strategy, and it is the kind of edit nobody reviews closely because the file
already existed. It takes a finished intent rather than building one from
`symbol`, `side` and `volume`, which reads less nicely and is what keeps the
port out of the package. It is not exported from `atlas.strategy`, for the
reason `MockBrokerAdapter` is absent from `atlas.broker`. It makes no claim
about profitability and must not be deployed or extended into something that
trades.

**What this task does not claim.** There is no lifecycle, no registry, no engine,
no scheduling and no event subscription — the rest of what the responsibilities
table gives `strategy`. `atlas.execution` remains an empty stub, so nothing
consumes a `RiskVerdict`, and the behavioural half of the first invariant still
waits on a pipeline to observe. No risk control, sizing rule or real strategy was
written.

**No ADR was added, and none was reversed.**
[ADR-0010](adr/0010-the-risk-boundary-is-a-verdict-on-an-intent.md) records that
`atlas.strategy` would depend on the port's types *transitively*, quotes the
strategy stub's "nothing here may reach a broker directly", and rules that the
wording survives that. This task takes no such dependency, so the ADR's ruling
stands untouched and the sentence it quotes is still in the stub verbatim. The
decisions above are recorded in the module docstrings, in
`packages/strategy/src/atlas/strategy/README.md` and in the boundary test.

A later task that gives a real strategy the job of constructing its own intent
will meet the question this one sidestepped — that strategy will have to name
the four primitives — and it should answer it by amending or superseding
ADR-0010, not in prose.

Tests were added for the boundary and for the reference implementation, a
substantial share of which exist only to assert that the AST scanners can
actually fail, because a scan that inspects nothing passes everything. Exact
counts and gate results are not recorded here until CI has produced them; the
numbers that belong in this file are the ones a CI run can be pointed at.

## Known documentation debt

- **ADR-015 and ADR-016** were declared dependencies of ATLAS-TASK-0004 but do
  not exist. `docs/adr/` currently ends at 0010.
- **Version.** ATLAS-TASK-0004 was specified as `v0.2.0-alpha`; `pyproject.toml`
  and `README.md` still declare `v0.1.0-alpha`. A contract test ties the
  `atlas-core` image tag to `[project].version`, so a bump touches all three.
