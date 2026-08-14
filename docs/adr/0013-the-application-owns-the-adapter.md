# ADR 0013 — The application owns the adapter; the port stays in the broker package

**Status:** Accepted
**Date:** 2026-08-14

## Context

[ADR-0011](0011-execution-builds-the-request-another-layer-owns-the-port.md)
named a layer and did not fill it. Its decision reads "A layer outside
`atlas.execution` owns broker interaction", its diagram calls that layer the
*broker-owning layer*, and its first non-guarantee states the consequence
plainly: "Nothing places an order. The broker-owning layer this record names
does not exist."

[ADR-0012](0012-risk-is-handed-its-state-and-reads-its-own-limits.md) recorded
the same absence from the other side. Risk is handed the account and positions
it judges rather than fetching them, and the reason the handing does not happen
is that there is nobody to do it: "whoever hands it state calls them, and that
layer does not exist yet." Its list of what it does not decide ends "not who
calls the control, not who hands it state, not who owns a `BrokerAdapter`."

Three facts constrain the answer rather than following from it.

**Nothing constructs an adapter.** Every construction site in the repository is
a test — `tests/unit/broker/**` and one string literal in
`tests/unit/execution/test_execution_boundary.py` that exists to prove a scanner
can fail. `BrokerAdapter` is named in source only inside `atlas.broker`.
ADR-0011's observation is still exactly true: "There is no `BrokerAdapter`
construction anywhere outside `atlas.broker` today."

**Two documents already use the vocabulary of the answer, and neither decides
it.** `apps/atlas-core`'s package docstring has said since ATLAS-TASK-0001 that
it is "the long-lived process that wires the packages together, owns the event
loop, and runs the trading pipeline end to end", with the boundary "Composition
and process lifecycle only. All behaviour lives in `atlas.*` packages so that it
remains testable without a process". `atlas.broker.mt5.connection.MT5Config`
says it is "Constructed by the composition root from `atlas.config` and handed
to the adapter", and gives the reason: "an adapter that sources its own
credentials cannot be pointed at a second account in a test, and Atlas would
have two configuration systems." `docs/architecture/overview.md` gives
`atlas-core` the row "Owns the event loop and runs the trading pipeline", and
`README.md` says "apps are deployable processes that compose them". None of
these is an accepted decision — the overview's own banner instructs that its
behavioural descriptions be read as "the contract a later task must satisfy, not
as a description of code that exists" — but four places in the repository were
already written expecting this record.

**Holding an adapter is a job with a written specification.**
[ADR-0007](0007-two-locks-in-the-base-adapter.md) designed its locking around
three threads that "will hold the same adapter": a strategy thread, a risk
thread, and "a supervisor thread asking `health()` on a timer and calling
`reconnect()` when the answer stops being reassuring". It also pushed one duty
outside the adapter deliberately: "'Check then act' is not atomic and cannot be
made so from inside an adapter. A caller that must not lose a request has to
sequence its own lifecycle calls." ADR-0007 has been describing this record's
subject as "a caller" since it was written, and this record names it.

## Decision

**`apps/atlas-core` owns the `BrokerAdapter`. It constructs the instance, holds
it for the life of the process, governs what receives access to it, sequences
its lifecycle, and carries the supervision duty ADR-0007 assigns to a caller.**

**The port and its implementations do not move.** `BrokerAdapter`,
`BaseBrokerAdapter`, `MockBrokerAdapter` and `MT5BrokerAdapter` stay in
`packages/broker`. This record decides which layer owns *an instance and its
use*, not where the code that defines it lives.

```
TradeIntent ──▶ atlas.risk ──▶ RiskVerdict ──▶ atlas.execution ──▶ OrderRequest ──▶ apps/atlas-core ──▶ BrokerAdapter ──▶ venue
```

### The five responsibilities

1. **Construction.** The application builds the adapter. Nothing below it does.
2. **Holding.** The instance is the application's, and its lifetime is the
   process's.
3. **Governing access.** The application decides what is handed the adapter and
   what is not. A package does not reach up for one.
4. **Lifecycle sequencing.** `connect`, `disconnect` and `reconnect` are called
   by the owner, in an order the owner chooses. This is the duty ADR-0007
   `:147-148` left to a caller because a remote venue makes it unavailable from
   inside an adapter.
5. **Supervision.** The `health()` timer ADR-0007 designed for is the
   application's to run. `BaseBrokerAdapter` guarantees the call is never
   blocked by an in-flight lifecycle call; somebody still has to make it.

### The application assembles the configuration; the port stays agnostic

`apps/atlas-core` is responsible for obtaining and assembling whatever an
adapter needs in order to be constructed, and for handing it over.
`atlas.broker` remains configuration-source agnostic: it reads no environment
and imports no configuration package, which is what
`tests/unit/broker/test_adapter_contract.py` already asserts by permitting the
port only `atlas.broker` and `atlas.common`.

`MT5Config` remains what it is — an adapter-facing configuration object, frozen,
`extra="forbid"`, constructed by somebody else and handed in. Its docstring
already names that somebody by role, and this record supplies the layer.

**The broker or venue surface in `AtlasSettings` is not decided here.** ADR-0011
recorded that none exists — "there is no broker or venue surface anywhere in
it" — and that is still true. What section it becomes, what it is called, what
fields it carries and how credentials reach it are a separate decision. This
record fixes only which layer is responsible for the assembly.

### Access is governed, not brokered

The application hands the adapter to what needs it. It does not do so through a
registry, a service container, a factory or a locator, and this record defines
none: naming a mechanism here would decide an implementation on the evidence of
zero call sites. What is fixed is the direction — access is *granted downward by
the owner*, never *acquired upward by a package* — and the four boundary tests
already enforce the second half of that for every package that has one.

## Why `atlas-core`

**It is the layer the repository already describes this way.** Four documents —
the app's own charter, `MT5Config`'s docstring, the overview's process table and
the README — describe an application composing packages and a composition root
constructing adapter configuration. This record makes an existing description
authoritative rather than introducing a new idea.

**It reads configuration already, and that edge is the only one of its kind.**
`apps/atlas-core/src/atlas/apps/core/__main__.py` imports `load_settings`, and
ADR-0012 `:107` records the edge as the accepted baseline: "until now only
`apps/core` imported it."

**It creates no new dependency direction between feature packages.** The six
edges the overview enumerates stay six. An application sits above every package
by construction, so composing them adds nothing to the graph the boundary tests
guard. Every alternative below either changes what an existing edge *means* or
adds edges to that graph.

**Process lifecycle is where supervision belongs.** ADR-0007's supervisor is a
thread on a timer in a long-lived process. The application is the only layer in
Atlas that has a process.

**The abstraction survives.** The application holds a `BrokerAdapter`. ADR-0006
kept `MockBrokerAdapter` exported from `atlas.broker.mock` and never from
`atlas.broker` "so business logic still cannot discover which adapter it holds",
and an owner that holds the port rather than an implementation preserves that
for everything it hands the adapter to.

## Alternatives considered

**`atlas.execution` owns the `BrokerAdapter`.** Rejected, and rejected already:
ADR-0011 `:214-221` considered and refused it, on the grounds that it "collapses
two questions into one package: what an order should look like, and how a
connection to a venue is obtained, authenticated, retried and reconciled", and
that it "would require what does not exist — an adapter construction site,
broker configuration, credential handling". Choosing it now would mean
superseding an accepted record rather than answering the question it left open,
and would require deleting `BrokerAdapter` from the `VENUE_ACCESS_SYMBOLS` that
`tests/unit/execution/test_execution_boundary.py` exists to enforce. ADR-0011's
implementation constraint — "`atlas.execution` may not name, obtain, construct
or invoke a `BrokerAdapter`" — is untouched by this record.

**`atlas.broker` owns it.** Rejected, and it is the closest call among the
three. Every adapter, `MockVenue` and `MT5Config` already live there, so it
would add no edge at all. It fails on configuration and on abstraction. The port
package deliberately does not read configuration — `MT5Config`'s own docstring
gives the reason, "an adapter that sources its own credentials cannot be pointed
at a second account in a test, and Atlas would have two configuration systems" —
so an owning `atlas.broker` would either reverse that statement or hold an
adapter it could not configure. It also makes the package that defines the port
the place that knows which venue Atlas trades, which is the property
`MT5Config`'s `terminal_path` field refuses to let the filesystem decide.

**A new package under `packages/`.** Rejected. It is a defensible reading of
ADR-0011's "a layer outside `atlas.execution`", and it would arrive with a
boundary test of the kind the repository already writes four of. What it costs
is a second composition abstraction: the repository's architectural vocabulary
already has one composition point, chartered and named, and a package that
composed the feature packages would leave `apps/atlas-core` holding a charter
for a job something else was doing. It would also add a sixteenth package, a
nineteenth source root, a new charter row, a new boundary rule and four new
edges into the graph the six-edge invariant describes — all to avoid using a
layer that already exists for this.

## Consequences

### Guaranteed

- **The layer ADR-0011 named has a home.** The diagram's `broker-owning layer`
  is `apps/atlas-core`, and three documents that record its absence can be
  corrected against a decision rather than against prose.
- **The graph between feature packages is unchanged.** Six edges before, six
  after. No boundary test changes, and none is weakened.
- **The port stays where the tests guard it.** `atlas.broker` keeps its
  permitted set of `atlas.broker` and `atlas.common`, and its implementations
  stay importable by any package that wants to test against the mock, which is
  what ADR-0006 shipped them in `packages/broker` to allow.
- **ADR-0007's caller exists.** Lifecycle sequencing and supervision have an
  owner, and neither is expected of the adapter.
- **Execution and risk are unchanged.** Both keep the boundaries their ADRs and
  their AST scans give them, and neither acquires a name it was forbidden.

### Not guaranteed, deliberately

- **No adapter is constructed by this record.** Nothing in `apps/` reaches
  `atlas.broker` today, and this decision writes no code. The construction site
  ADR-0011 said does not exist still does not exist.
- **No composition root is implemented.** This record designates the
  application layer as the ownership and composition point *for a
  `BrokerAdapter`*. It does not claim that a runtime composition root, an
  engine, a registry, a scheduler or a trading pipeline exists — none does. The
  wiring is downstream work.
- **Nothing is placed.** `apps/atlas-core` has no run loop; its entrypoint
  resolves configuration, emits a startup record and exits. An `OrderRequest` is
  still received by nothing.
- **No configuration surface is created.** The broker section of `AtlasSettings`
  remains undecided and unwritten.
- **No policy is produced.** ADR-0011's `ExecutionPolicy` hole is unchanged:
  "Execution cannot act without one, and nothing produces one."
- **No boundary test guards this.** Unlike every previous ownership decision,
  this one lands in a directory with no import rule. See below.

### Costs

- **The responsibility lands where no rule governs it.** `apps/` has no
  import-boundary test. `tests/contract/test_repository_structure.py` constrains
  applications structurally — each must be declared, and `atlas/apps` must carry
  no initialiser — and nothing constrains what one may import. The four boundary
  tests seal the reverse direction, because each uses a closed permitted-set that
  names no application; the forward direction is unruled. This record is
  therefore the first to place a capability in the least-constrained directory
  in the repository, and it does so knowingly.
- **Credentials will end up in an application.** Whatever broker configuration
  is eventually decided, this record puts the layer that assembles it in `apps/`.
  That is where `atlas.config` is already read, and it is still a concentration.
- **`atlas-core` acquires four future edges.** Composing the pipeline means
  importing `broker`, `execution`, `risk` and eventually `strategy`. None
  disturbs the feature-package graph, and all four are invisible to every test
  that exists.
- **A second application has a charter that touches this.** `apps/dashboard` is
  chartered for "observation and explicitly-authorised control actions", and
  this record does not say whether that includes an adapter. See below.

## What this record does not decide

- **The `apps/` import rule.** `apps/atlas-core` is selected *despite* the
  absence of one, not because the question was settled. This record does not
  create, imply or prefigure a general rule for what an application may import,
  and it must not be read as establishing that every application may import
  every package. Whether such a rule is a forward allowlist, a reverse
  prohibition, a construction-site rule or a content rule remains open, and the
  task that decides it is free to constrain `apps/atlas-core` further than this
  record does.
- **Whether `apps/dashboard` may hold or invoke a `BrokerAdapter`.** Its charter
  names authorised control actions and this record rules on neither direction.
  It is an open question created by this decision and explicitly outside it.
- **The broker or venue configuration schema.** No section name, field,
  environment variable or secrets mechanism is decided or invented here.
- **Any mechanism for granting access.** No registry, factory, service
  container or locator is defined, and none should be inferred from "governs
  access".
- **The run loop, the supervisor's implementation, or any threading design.**
  ADR-0007's locking model is untouched; `health()` and `is_connected()` remain
  non-blocking against the session lock exactly as decided there.
- **Order identity, idempotency, routing, fills or reconciliation.** ADR-0011's
  second non-guarantee is unchanged.
- **Account or portfolio state ownership.** Refused by ADR-0010, restated by
  ADR-0011 and ADR-0012, and not reopened here.

## Relationship to ADR-0011

**ADR-0011 is not superseded and not edited.** Everything it decided stands:
`atlas.execution` turns an approved verdict into an `OrderRequest`, answers
`None` for a rejected one, names exactly three types from the port, holds no
state, and may not name, obtain, construct or invoke a `BrokerAdapter`.

This record answers the question ADR-0011 left open. Where ADR-0011 says "a
layer outside `atlas.execution` owns broker interaction", this says which layer.
Its rejection of `atlas.execution` is adopted here rather than revisited, and
its reasoning — that ownership drags in construction, configuration, credentials,
connection lifecycle and retry — is the criterion the alternatives above were
judged against.

When this decision is implemented, ADR-0011's non-guarantee "the broker-owning
layer this record names does not exist" becomes inaccurate. That is the
immutability rule working as designed: the correction belongs in the roadmap and
the living documents, never in ADR-0011 itself.

## Relationship to ADR-0012

**ADR-0012 is not superseded, not edited and not reopened.** The exposure limit
is still read by the control from frozen process configuration and is still not
a parameter any caller can supply. Nothing here permits `atlas.risk` to obtain
or call a `BrokerAdapter`, and `tests/unit/risk/test_risk_boundary.py` continues
to fail on the name and on the five port operations ADR-0012 forbids it.

ADR-0012 rejected a composition root that hands risk its resolved limits, and
set a revisit condition: "when a single wiring point exists and can be pointed
at." **That condition is not satisfied by this record and this record does not
satisfy it.** Designating an owner for a `BrokerAdapter` is not the same act as
building a wiring point, and none exists: no engine, no registry, no consumer,
no run loop. The rejected alternative stays rejected on ADR-0012's own terms,
and nothing here should be read as reopening how risk obtains its limits.

Who hands the risk control its state — one of the three things ADR-0012 says it
does not decide — is also not decided here. This record names the layer that
will be able to call `get_account` and `get_positions`. It does not decide that
it does, when, or to whom it passes the result.

## Relationship to ADR-0006 and ADR-0007

**ADR-0006 is preserved.** `MockBrokerAdapter` remains a shipped implementation
in `atlas.broker.mock`, importable by any package for testing, and exported from
`atlas.broker.mock` and never from `atlas.broker`. The owner holds a
`BrokerAdapter`; what it hands onward is a `BrokerAdapter`; and business logic
still cannot discover which implementation it has. An owner that could only hold
one concrete adapter would break the property ADR-0006 shipped a second
implementation to establish.

**ADR-0007 is preserved and this record completes it.** The two locks, their
ordering, the leaf property of the readings lock, the finality of
`connect`/`disconnect`/`reconnect`, and the guarantee that `health()` and
`is_connected()` never queue behind a lifecycle call are all untouched. What
ADR-0007 left to "a caller" — sequencing lifecycle calls so a request is not
lost, and running the supervision timer — is assigned here for the first time.

Two of ADR-0007's non-guarantees now have an owner to bind. "Nothing is
guaranteed across adapters. There is no global broker lock" means that if
`apps/atlas-core` ever holds two adapters, coordinating them is its problem and
not the port's. "`MockVenue` is not thread-safe" means the owner may not share
one venue between two adapters driven from two threads. Both were true before;
this record names who they are true *of*.
