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
| ATLAS-TASK-0012 † | The strategy boundary: producing a `TradeIntent` | ✅ Complete | `2e567aa5` |
| ATLAS-TASK-0013 † | Documentation and release-metadata debt | ✅ Complete | `19afcf40` § |
| ATLAS-TASK-0014 † | The execution contract: an approved verdict becomes an `OrderRequest` | ✅ Complete | `00364ac24f0479de2cb5278b519dbe97cf2e0d2b` |
| ATLAS-TASK-0015 † | Living-document correction after the execution contract | ✅ Complete | `5e730b4766165a16d994f55251d9eca50df0b842` |
| ATLAS-TASK-0016 † | Completing the living-document correction | ✅ Complete | `c37b0ebba3b4206705dfd8c06ba6e96c9ebfcf48` |
| ATLAS-TASK-0017 † | The first risk control: a portfolio margin-utilisation limit | ✅ Complete | `4147f12c8a52b6095b4380ebbc57c92cd058d633` |
| ATLAS-TASK-0018 † | Index ADR-0012 in `docs/adr/README.md` | ✅ Complete | `dfc1289949dca9f3b8506e6e2b99730495318669` |

† **Newly specified, not recovered.** The unmarked rows are evidenced by the
repository record: the task existed, and the commit it cites is the work.
ATLAS-TASK-0011 through ATLAS-TASK-0018 were each specified and authorised as
new work during the task itself. Their presence in this table is not evidence
that any was previously planned, and none may be described as recovered project
history or as previously completed.

ATLAS-TASK-0012 cites the branch tip rather than the branch's first commit.
`270f57a8` added the package and `2e567aa5` removed the dependency on
`atlas.broker` that it had taken, so `2e567aa5` is the state that reached
`main`. The gates passed on that tree twice — once on the pull request and
again on the merge commit `e909b4b`, whose tree is identical — so unlike
`de7e905` below there is no gap here against the definition above.

‡ **The gates passed one commit later.** `de7e905` is where ATLAS-TASK-0010's
work lives and it is on `main`, which is why it is the commit cited. The tree at
that commit did not itself pass CI: the run covering it failed at Pytest, and CI
was first green at `6cca03d`, which corrected a flaky clock test. The citation
is left as the feature commit — the history is not rewritten — and the gap
against the definition of **Complete** above is recorded here instead.

§ **The commit is cited after the fact.** This file is part of what
ATLAS-TASK-0013 delivered, so the row above could not cite its own commit: the
SHA did not exist until the commit was written. The citation is completed here
after the merge, which is how ATLAS-TASK-0012's row was filled in too, by
`b023f8b`. `19afcf40` is the implementation commit and holds the work; the
merge commit is `1d964186`, and as with `2e567aa5` above it is not what the
row cites.

ATLAS-TASK-0018 is complete and pushed to `main`. Nothing beyond it is defined,
and this file declares no ATLAS-TASK-0019 and no work after it. The tasks above
are the ones the repository itself declares; this file does not speculate past
them.

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

### ATLAS-TASK-0012 — the strategy boundary

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
the four primitives — and it should answer it by superseding ADR-0010, not
in prose.

155 tests were added — 90 for the boundary and 65 for the reference
implementation, 45 of which exist only to assert that the AST scanners can
actually fail, because a scan that inspects nothing passes everything. CI was
green on the merge commit: Ruff, Black and MyPy clean across 94 source files,
3072 passed and 105 skipped of 3177 collected, and total coverage at 99%. The
105 skips are the MetaTrader5 vendor-comparison tests, whose wheel installs on
Windows only; they skip on every Linux run and none of them belong to this
task.

### ATLAS-TASK-0013 — documentation and release-metadata debt

Newly specified rather than recovered from the repository record — see the note
marked † under the status table.

No source file changed. This task closes what the debt section below had
recorded, corrects the one live document ATLAS-TASK-0012 left stale, and settles
a contradiction between two process documents. It implements nothing, decides no
architecture, and adds, edits and supersedes no ADR.

**The version says one thing in three places.** ATLAS-TASK-0004 was specified as
`v0.2.0-alpha` and the repository had stayed on `0.1.0a0`. `pyproject.toml` is
the source of truth and now declares `0.2.0a0`; `docker-compose.yml` tags the
`atlas-core` image to match, which `tests/contract/test_repository_structure.py`
already asserted and still does; and `README.md`'s banner reads `v0.2.0-alpha`.
That banner is the one copy no test binds, and it stays that way deliberately —
a test that read prose would make the banner's wording a contract.

**The stale sentence was in one place, not several.**
`packages/risk/src/atlas/risk/README.md` said `atlas.strategy` and
`atlas.execution` were both still empty stubs, which ATLAS-TASK-0012 made half
untrue. It is corrected in place, and says what is now the case: `strategy` has
a contract and an inert reference implementation, no engine drives one, and
`execution` is still a stub. Every other occurrence of that wording was checked
and left alone. `README.md`, `docs/architecture/overview.md`,
`packages/strategy/src/atlas/strategy/README.md` and both boundary tests name
`atlas.execution` alone and are still true. ADR-0010 says the same thing and is
an accepted record, immutable by the rule in `docs/adr/README.md`. The
ATLAS-TASK-0011 section above is a dated account of what that task did not
claim, not a live statement about today.

**Supersession, not amendment.** The ATLAS-TASK-0012 section above told a later
task to answer a question by "amending or superseding" ADR-0010. `docs/adr/`
allows no such thing: an ADR is immutable once accepted, and the statuses
defined there are `Proposed`, `Accepted`, `Superseded by ADR-NNNN` and
`Deprecated`, with no amendment among them. This file was the one in the wrong
and the phrase is gone. Nothing was added to the ADR process to meet it halfway
— removing a mechanism that never existed decides nothing, and inventing an
`Amended` status would have decided a great deal.

No test was added, and none was changed. The changes are documentation and
release metadata; the single claim among them that a test can hold — that the
`atlas-core` image tag and `[project].version` are the same string — was already
covered by a contract test that fails when the two drift, which is why the bump
touched `docker-compose.yml` in the same breath as `pyproject.toml`.

### ATLAS-TASK-0014 — the execution contract

Newly specified rather than recovered from the repository record — see the note
marked † under the status table.

`atlas/execution/contracts.py`: `ExecutionPolicy`, and
`build_order_request(verdict, policy) -> OrderRequest | None`. ATLAS-TASK-0011
gave the first invariant its vocabulary and ATLAS-TASK-0012 gave it a producer;
this gives it a consumer. An approved `RiskVerdict` becomes the `OrderRequest` a
venue would be asked to fill, and a rejected one becomes nothing. The decision
is ADR-0011, accepted with this task.

**The volume is the approved volume.** Never `TradeIntent.requested_volume`.
A reduced approval is an approval carrying a smaller number, and reading the
requested figure instead is the specific accident ADR-0010 rejected a third
`REDUCED` status to prevent. Three tests hold it, all of them at sizes strictly
below the request, because `RiskVerdict` refuses to be constructed the other way
round — risk may reduce an intent but never enlarge one.

**Naming the port is not calling it.** `OrderRequest`, `OrderType` and `Price`
are imported from `atlas.broker` rather than restated, which is the rule
`atlas.broker.types` applies to its own aliases: two definitions of one concept
"would create two rules for one concept and guarantee they diverge". The edge
that import creates is a type dependency and nothing else. The whole identifier
surface of the package is twenty-four names, and `BrokerAdapter`, the port's four
trading verbs and `OrderStatus` are absent from all of them; the only calls
anywhere in the package are `ConfigDict`, `Field` twice, and `OrderRequest`.
A layer that owns broker interaction still does not exist, and this task did not
invent one.

**Presentation is supplied, not chosen.** The order type and working price
arrive as a caller-supplied `ExecutionPolicy` — frozen, two fields, no default.
A default written here would settle filling-mode selection and a deviation
policy, the two questions `atlas.broker.mt5.adapter` names as having no
"obviously right answer", inside the package least likely to be read as policy.
Nothing stores a policy, nothing reads one from configuration, and
`AtlasSettings` is unchanged: the package's only module-level assignments are
its two `__all__` lists.

**`STOP_LIMIT` is out of reach, deliberately.** It is the one `OrderType` that
needs both a working price and a separate trigger, and a policy with exactly two
answers cannot supply both, so `OrderRequest`'s own validator refuses it. The
specification fixed the policy at two answers; the implementation supplies no
third value rather than inventing one, and a passing test characterises the
refusal so the limit is recorded rather than latent. Widening the policy is a
decision for the task that needs `STOP_LIMIT`, and this was not it.

`tests/unit/execution/test_execution_boundary.py` is the enforcement, since
there are no per-package manifests and the distinction the task rests on is
invisible to both the type checker and the packaging. It follows the scanners in
the risk and strategy boundary tests, and adds the mechanic this package needs:
an allowlist, so that the three vocabulary names pass and every other name taken
from the port is an offence — including `import atlas.broker`, which binds the
module and so reaches `BrokerAdapter` by attribute. Six of its tests splice a
forbidden import into the real source of each shipped module and assert the
scanner reports it, on the ATLAS-TASK-0012 standard that a scan which inspects
nothing passes everything.

CI passed on the merge commit the row above cites. Locally: Ruff, Black and MyPy
clean across 97 source files, 3296 passed, and `atlas.execution` at 100% of both
statements and branches.

### ATLAS-TASK-0015 — living-document correction

Newly specified rather than recovered from the repository record — see the note
marked † under the status table.

No source file changed. ATLAS-TASK-0014 gave the risk verdict its consumer, and
the documents describing that boundary went on saying otherwise:
`atlas.execution` was an empty stub, the graph held three edges, and
`docs/architecture/overview.md` was current as of ATLAS-TASK-0012. Each
statement was true when written and false on merge. This task corrects the three
documents that carried them and does nothing else — no test, script or tool is
added, no ADR is created or edited, and no edge is created, removed or changed.

**The banner is dated forward, not undated.** `docs/architecture/overview.md`
now reads "Status at ATLAS-TASK-0014", enumerates `atlas.execution` as narrowly
as it is implemented, and names this file as the authoritative record of which
tasks are complete, with the roadmap governing where the two disagree. The
alternative was to remove the date entirely. A dated banner that falls behind
announces itself against the last row of the table above; an undated one that
has drifted is silently wrong, which is the failure being corrected here.

**Five edges, named individually.** The overview said three. Naming them is not
stylistic: a wrong list is falsifiable by inspection and a wrong integer is not,
and the integer is what went stale. The count is derived from the AST import
graph rather than counted by hand, because the `atlas.execution → atlas.risk`
import sits under a `TYPE_CHECKING` guard — it is indented, and a line-anchored
grep reports four.

**What is not claimed matters as much as what is.** The chain the data flow
draws is still not joined end to end, and the corrected documents say so:
nothing outside the test suite produces a `TradeIntent`, no function anywhere
turns one into a `RiskVerdict`, and no layer owns a `BrokerAdapter`, so the
request `atlas.execution` builds is received by nothing. `atlas.risk` still
holds its two contracts and none of the controls that reach a decision.

One acceptance criterion had to be corrected before the work could be accepted.
As written it required a `git grep` over `docs/` to return nothing, which no
implementation could satisfy: the string survives in ATLAS-TASK-0014's
out-of-scope section, which is a historical record that later tasks do not edit,
and in the specification's own problem statement, and in the criterion itself.
It is now scoped to `docs/architecture/` and `packages/`, where it returns
nothing.

This task reached `main` by direct push rather than through a pull request,
unlike ATLAS-TASK-0011 through ATLAS-TASK-0014, so there is no merge commit for
the row above to cite and it cites the implementation commit, as the rows for
ATLAS-TASK-0011, ATLAS-TASK-0012 and ATLAS-TASK-0013 do. CI passed on that
commit itself, both jobs green, so there is no gap of the kind recorded at ‡.
Locally: Ruff, Black and MyPy clean across 97 source files, 3296 passed.

### ATLAS-TASK-0016 — completing the living-document correction

Newly specified rather than recovered from the repository record — see the note
marked † under the status table.

No source file changed. ATLAS-TASK-0013 enumerated by name every location
carrying the claim that `atlas.execution` was an empty stub consuming no
verdict; ATLAS-TASK-0014 made all four false, and ATLAS-TASK-0015 corrected two
of them. This task corrects the remaining two — `README.md` and the module
docstrings of the risk and strategy boundary tests — and empties that list. It
is the third pass at the same drift.

**The duplicated status line is removed rather than re-dated.** `README.md` read
"Last completed: **ATLAS-TASK-0012 — the strategy boundary**", three tasks
behind. That line restated the last row of the table above and then linked to
the table, so it carried no fact this file does not, and it was the only line in
the file that had gone stale — the Status section's inline references,
`(TASK-0011)` and `(TASK-0012)`, pin facts that have not moved and are still
correct. It now names this file as the authoritative record of which tasks are
complete and names no task itself. Re-dating it to ATLAS-TASK-0015 was
considered and rejected: it cures the defect for exactly one task and re-arms
it on the next. That is the opposite of the answer ATLAS-TASK-0015 reached for
the overview banner, and the difference is the content: that banner enumerates
which packages hold implementation, which this file does not record, so not
duplicating it was never an option there. Here it was, and no dated banner
replaces the removed line.

**The reason was stale; the conclusion was not.** Both test docstrings concluded
that only the structural half of the first invariant is provable today, and gave
"`atlas.execution` is still an empty stub" as the reason. The conclusion is
still true and survives verbatim; the reason is replaced with the true one —
nothing outside the test suite produces a `TradeIntent`, and nothing anywhere
turns one into a `RiskVerdict`, so there is no pipeline to observe. Neither
docstring claims wider coverage than it claimed before, which is the specific
way this correction could have gone wrong. `README.md` gained a paragraph naming
what `atlas.execution` actually holds, and the two neighbouring sentences that
addition would otherwise have falsified were dealt with rather than left: the
count of boundaries, corrected from two to three, and the sentence asserting by
omission that every package not named above has no implementation, which stands
verbatim and is true again because `atlas.execution` is now named above it.

**No test behaviour changed, and that is proved rather than asserted.** For each
of the two test files, the abstract syntax tree with the module docstring
removed is identical to the baseline's, compared as `ast.dump` output with
attributes excluded. No test, fixture, helper or assertion was added, deleted or
altered, and the suite still collects 3296 tests. The five dependency edges are
unchanged, derived from the AST import graph rather than counted by hand.
`tests/unit/execution/test_execution_boundary.py` was not touched: its docstring
matches the same search patterns this task worked from and is about a consumer
of the `OrderRequest`, which is still true.

**What was not built.** No risk control and no producer of a `RiskVerdict`, no
layer owning a `BrokerAdapter`, no run loop, no message bus, no market
ingestion, no MT5 trading method, no configuration surface, and no ADR — none of
the architecture the repository has deliberately deferred. The two substantive
directions remain blocked behind decisions this file does not make, and nothing
in this task's diff is groundwork for either. The corrected documents say the
chain is still not joined end to end, because it is not.

This task reached `main` by direct push rather than through a pull request, as
ATLAS-TASK-0015 did, so there is no merge commit for the row above to cite. It
has two commits. The first, `d0364dd9ef28de52ef8245a2f90263d16c9d9f78`, applied
the three corrections and added the specification; the second,
`c37b0ebba3b4206705dfd8c06ba6e96c9ebfcf48`, corrected the specification's own
account of coverage, which had said no baseline figure existed to compare
against when what is true is narrower — the local quality gate does not measure
coverage and CI does, and this task altered neither. The row above cites the
second, which holds the final state. CI passed on both, verified by `head_sha`
rather than by recency: run `31655632275` against `c37b0ebb`, Quality Gate and
Container & Compose both green, so there is no gap of the kind recorded at ‡.
Locally: Ruff, Black and MyPy clean, 3296 passed — the baseline count,
unchanged, which is the evidence that nothing outside the scope was touched.

### ATLAS-TASK-0017 — the first risk control

Newly specified rather than recovered from the repository record — see the note
marked † under the status table.

`packages/risk/src/atlas/risk/exposure.py` holds `evaluate_exposure(intent,
account) -> RiskVerdict`, a portfolio margin-utilisation limit. ATLAS-TASK-0011
gave the first invariant its vocabulary, ATLAS-TASK-0012 gave it a producer and
ATLAS-TASK-0014 gave it a consumer; this is the first thing in `atlas.risk` that
reaches a decision. An intent is approved unchanged while `Account.margin` over
`Account.equity` is strictly below the maximum the process is configured to
permit, and rejected with `EXPOSURE_LIMIT` otherwise. There is no reduction path
and no third answer. The decision it implements is
[ADR 0012](adr/0012-risk-is-handed-its-state-and-reads-its-own-limits.md).

**The verdict does not depend on the size of the intent, and that is written
down.** ADR-0012 forbids risk from calling the port, so this control cannot ask
what an intent would cost in margin — the port's `margin_required` is exactly
the operation the boundary test asserts no risk module can reach. It judges the
exposure the account already carries, which means a 0.01-lot intent and a
100-lot intent against the same `Account` get the same answer. That is a real
limitation of a portfolio-level control that may not consult the venue, and it
is stated in the module's own docstring and asserted by a test rather than left
for a reader to infer from the code.

**The comparison is exact integer arithmetic, not decimal arithmetic.**
`margin / equity < limit` rounds the quotient to the ambient decimal context and
at the interpreter's default precision approves cases that should reject;
`margin < limit * equity` rounds the product instead and raises
`decimal.Overflow` on a large finite limit. Both borrow a precision from a
context nothing in this repository sets. Instead each operand is taken apart
with `Decimal.as_integer_ratio()` and the inequality is cross-multiplied in
unbounded integers, so there is no rounding step, no precision, no context and
no trap, and the comparison is total on every finite `Decimal` — including
`1E+999999`, which is where the two rejected formulations fail.

**An unusable account state is not a reason to permit new exposure.** A
non-finite margin, equity or limit fails closed, and so does non-positive
equity, checked in that order: a non-finite `Decimal` has no integer ratio, and
cross-multiplying an inequality is valid only where equity is positive. Nothing
raises. A control that threw where it was asked to judge would be bypassable by
an exception handler one layer up, so a blown account and a venue reporting a
non-finite amount are refusals rather than errors. `status` and `reason` are
identical for every refusal this control makes, which leaves `detail` as the
only field that tells an operator which refusal it was.

**The default permits nothing, and the deployment supplies the number.**
`RiskSettings.max_margin_utilisation` is a `Decimal` defaulting to `0`,
constrained `ge=0` with `allow_inf_nan=False` and no upper bound. Because the
comparison is strict, that default refuses every intent — absence of
configuration is not permission. No file under `config/` sets a value, because
any positive value is a trading policy and belongs to the deployment rather than
to the repository, for the reason ATLAS-TASK-0014 gave for refusing to default
an `ExecutionPolicy`. A process resolved to `production` **or** `demo` refuses
to start until the limit is above zero. `Environment.is_live` still means
`production` alone, and the debug, logging-format and postgres-password
invariants still apply to `production` alone; the start-up check was restructured
to collect violations from two conditions rather than one, not widened.

**A second edge out of risk, under a name allowlist.** `atlas.risk` →
`atlas.config` is the sixth edge between feature packages and the second out of
`atlas.risk`. It carries exactly one name, `get_settings` — enough to read this
package's own limit and nothing else — and the limit is read on every call
rather than held, so nothing caches a settings object, a section or a number at
import time. `tests/unit/risk/test_risk_boundary.py` gained the allowlist of
permitted names, and a separate scan asserting that no risk module reaches a
credential-bearing configuration name: reaching a database password through a
settings object requires no import at all, so an import allowlist cannot see
that far on its own. The graph is still acyclic, and `atlas.config` still
imports no feature package.

**ADR-0012 was brought under version control unmodified.** It had been accepted
and was present on disk but untracked, which is why this task treats committing
an unmodified file as distinct from writing or changing one: its blob is
`497ab06f8bfb5aad3b5344fd27319c34d3dd6537` both before the task and in the
commit, and it entered history as an addition. No ADR's content was created or
altered here.

**What this task does not claim.** There is no sizing algorithm, no drawdown
control, no correlation cap and no kill switch; the other three `RejectionReason`
members remain unimplemented, and the package's responsibility in the overview's
table still names four things this delivers one of. There is no risk engine and
no pipeline: nothing outside the test suite produces a `TradeIntent` or hands
one to `evaluate_exposure`, and no layer owns a `BrokerAdapter`, so the chain
the data flow draws is still not joined end to end. The behavioural half of the
first invariant still waits on something that drives a strategy, reaches a
verdict and calls the translation in sequence.

Fourteen places propagated the change. Eleven were prose statements that became
false: `README.md`, three passages in `docs/architecture/overview.md`, three in
`packages/risk/src/atlas/risk/README.md`, the package docstring, the
`RejectionReason` docstring, and the risk and strategy boundary-test docstrings.
The `config/production` header comment became incomplete rather than wrong — an
operator satisfying every invariant it listed would still have been refused
start-up. Three copies of the `atlas.risk.__all__` assertion are test assertions
rather than prose, and would have failed. `.env.example` stated nothing false;
it catalogued no variable for a limit a demo or production process now cannot
start without. One of the overview passages — a sentence in the overview
describing what the risk boundary test asserts — was found during implementation
rather than during specification, and the specification was amended once, after
its own final audit, to authorise that single sentence rather than let the
implementation quietly widen its own scope. That amendment is recorded in the
specification's §1.

84 tests were added: 29 for the control, 41 for the widened boundary and the
credential scan, and 14 for the configuration field and its start-up invariant.
The final count reconciles rather than being discovered — `3296 − 1 + 10 + 84 =
3389`, where the `−1` is `atlas.config` leaving the forbidden-package
parametrisation and the `+10` is the new module joining `RISK_SOURCES` in two
files. Six mutations of the control were each observed to fail at least one
test: `<` widened to `<=`, both disqualified arithmetic formulations, each of
the two guards removed, and a real credential access injected into the module.
Removing the equity guard is caught by exactly one test, which is the test that
exists because the specification shows that guard changes no verdict — only the
`detail` an operator reads.

This task reached `main` by direct push rather than through a pull request, as
ATLAS-TASK-0015 and ATLAS-TASK-0016 did, so there is no merge commit for the row
above to cite. It has one commit, `4147f12c`, covering 17 files. CI passed on
it, verified by `head_sha` rather than by recency: run `31733801506` against
`4147f12c`, concluded successful, so there is no gap of the kind recorded at ‡.
Locally: Ruff, Black and MyPy `--strict` clean, 3389 passed.

### ATLAS-TASK-0018 — indexing ADR-0012

Newly specified rather than recovered from the repository record — see the note
marked † under the status table.

`docs/adr/README.md` received exactly one inserted row, for ADR-0012. ADR-0012
was accepted, and ATLAS-TASK-0017 committed it, but that task's forbidden list
held the index, so the repository carried a committed ADR that its own committed
index did not list. This task added the row and did nothing else: one file, one
insertion, no deletion.

**Both cells were transcribed rather than written.** The index's Title column
has carried each ADR's own H1 with the `# ADR NNNN — ` prefix removed, and its
Status column that ADR's `**Status:**` field, for all eleven rows preceding this
one — checked against the eleven files rather than assumed. The new row's title
is ADR-0012's H1 less that prefix and its status is `Accepted`, the status the
ADR itself carries, so nothing about the decision is restated here in different
words. ADR-0012's content did not change: its blob is
`497ab06f8bfb5aad3b5344fd27319c34d3dd6537` before this task and in its commit.

**Nothing else was touched.** No source file, no test, no configuration, no
`.env` catalogue, no ADR's content, no task specification and no other document
changed. This roadmap did not change either — the entry you are reading is a
separate closeout, as ATLAS-TASK-0016 and ATLAS-TASK-0017 were closed out.

**The test suite does not verify this change.** No test reads
`docs/adr/README.md`. `tests/contract/test_repository_structure.py` asserts that
the directory `docs/adr` exists and asserts nothing about its contents, and no
other test parses the index or enumerates the ADR files. The suite would have
passed identically had the row been omitted, misspelled, given a status the ADR
does not carry, or pointed at a file that does not exist. Acceptance therefore
rested on mechanical checks of the file and its diff, not on a green suite: the
table parses to twelve rows numbered `0001` through `0012`, the link resolves to
a file on disk, the diff is one insertion and zero deletions, and deleting the
inserted line reproduces the previous blob byte for byte. The 3389 passing tests
— the baseline count, unchanged — are evidence that nothing else moved, which is
the only thing they can be evidence of here. A test that parsed the index and
required every ADR on disk to appear in it would close that gap; writing one was
outside this task's authorised scope.

**No specification file was written.** ATLAS-TASK-0014 through ATLAS-TASK-0017
each have one under `docs/tasks/`; this task has none. The change is one row in
one table, and a specification of the weight those carry would have cost more to
review than the line it governed. The scope was fixed and approved before any
edit was made, and the same gates were run, but that record is not in the
repository.

This task reached `main` by direct push rather than through a pull request, as
ATLAS-TASK-0015 through ATLAS-TASK-0017 did, so there is no merge commit for the
row above to cite. It has one commit, `dfc12899`, covering one file, and the
push was a fast-forward from `eb21d82f`: that commit is an ancestor of this one,
`main` advanced by exactly one commit, and `main` and `origin/main` are now the
same commit. CI passed, verified by `head_sha` rather than by recency: run
`31754787621` against `dfc12899`, Quality Gate and Container & Compose both
successful, so there is no gap of the kind recorded at ‡. Locally only the test
suite was run, because the change is documentation and touches no Python; Ruff,
Black and MyPy ran in CI's Quality Gate rather than on this machine.

## Known documentation debt

- **ADR-015 and ADR-016 do not exist and cannot be reconstructed.** They were
  named as dependencies of ATLAS-TASK-0004 by a specification that is not part
  of this repository, and no file here records what either was to decide.
  Writing them now would be inventing two architectural decisions and dating
  them to a task that is long closed, so they stay unwritten. The numbers do
  not fit either: `docs/adr/` numbers sequentially in four digits and ended at
  `0010` when this was written, so `015` and `016` name positions the sequence
  never reached. ATLAS-TASK-0014 has since written `0011`, and ADR-0012 was
  accepted for ATLAS-TASK-0017 and committed by it.

- **`docs/adr/README.md` did not index ADR-0012. Discharged by
  ATLAS-TASK-0018.** The index listed ADR-0001 through ADR-0011 while ADR-0012
  was accepted and, from ATLAS-TASK-0017, committed — so the repository held a
  committed ADR that its own committed index did not list. The omission predated
  ATLAS-TASK-0017, which recorded it rather than folding an unrelated correction
  into a diff that was to be reviewed against its own list of permitted files,
  which is why `docs/adr/README.md` was on that task's forbidden list.
  ATLAS-TASK-0018 added the one row it needed, in `dfc12899`, and the index now
  lists ADR-0001 through ADR-0012. This entry is kept as the record of a debt
  that is closed rather than one that is open.
