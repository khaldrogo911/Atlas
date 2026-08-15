# ADR 0015 — The application selects `MT5BrokerAdapter` and constructs it at startup

**Status:** Accepted
**Date:** 2026-08-15

## Context

Three records have now converged on one missing act.

[ADR-0013](0013-the-application-owns-the-adapter.md) named the layer that owns a
`BrokerAdapter` and gave it five responsibilities, the first of which is
Construction: "The application builds the adapter. Nothing below it does." It
then declined to say what gets built — "**The broker or venue surface in
`AtlasSettings` is not decided here**" — and listed adapter selection nowhere in
its decision at all, because it had no configuration to select from.

[ADR-0014](0014-broker-settings-are-restated-not-imported.md) supplied that
configuration and stopped one step short on purpose. It drew the missing arrow

```
AtlasSettings ──✗──▶ MT5Config ──▶ MT5BrokerAdapter
```

and answered only its left-hand side: "This record supplies the values that
assembly reads; it does not build the assembly." Its own list of what it does
not decide opens with the four questions this record answers — "**Adapter
selection.** Whether the application constructs a `MockBrokerAdapter` or an
`MT5BrokerAdapter`, and on what basis", "**When an adapter is constructed**, if
it is constructed at all", "**Where the composition or wiring point exists**",
and "**Whether construction occurs at startup**".

ATLAS-TASK-0022 implemented ADR-0014's section and preserved the gap
deliberately. Its Decision J records the correspondence
`BrokerSettings.* → MT5Config.*` and then forbids acting on it — "**TR-1.** No
code in this task performs, prepares or names this mapping" — and its **TR-4**
hands this record its third question: "the settings section accepts `login=0`
and `server=""`; `MT5Config` rejects them. The task that builds the translation
decides what a rejection means at that point."

Four facts constrain the answer rather than following from it.

**Both halves of the seam are built, and nothing joins them.** `BrokerOwner`
exists in `apps/atlas-core`, holds one adapter, sequences `start`/`stop` and
refuses access outside that window. `MT5BrokerAdapter` and `MT5Config` exist in
`packages/broker`. `AtlasSettings.broker` exists in `atlas.config` and carries
exactly the four values `MT5Config` cannot default. Every part is present and
tested; no production code constructs any of them. `BrokerOwner` is
instantiated only in tests.

**The application already refuses to start on bad configuration.**
`apps/atlas-core/src/atlas/apps/core/__main__.py` resolves settings, and a
`ConfigurationError` produces a `startup_failed` record on stderr and exit 2.
A process that cannot be configured does not run. That principle exists; this
record extends its reach rather than inventing it.

**Selection cannot be read off the settings section, and that was the point.**
`BrokerSettings` names four primitives and no venue — ADR-0014: "A section of
`int`, `SecretStr`, `str` and `Path` is compatible with an MT5 adapter and
commits to nothing." Nothing in configuration says which adapter to build, so
the answer has to be a composition decision or no decision at all.

**A shipped test forbids the act, and says who may lift the prohibition.**
`tests/unit/test_core_broker_boundary.py:76` lists `MT5Config`,
`MT5BrokerAdapter`, `MockBrokerAdapter`, `MockVenue` and `BaseBrokerAdapter` as
"Names that would mean an application had chosen an implementation", and scans
every file under `apps/` for them. Its reason is stated as a temporary one:
"the settings a live adapter would be built from do not exist and choosing an
implementation without them is the decision this task declines to make." Those
settings now exist. The same file's docstring `:10-19` says the rule that
governs `apps/` "would begin with a decision record rather than with a test
file". This is that decision record, for this one authorisation.

## Decision

**`apps/atlas-core` selects `MT5BrokerAdapter` as this runtime's broker
implementation, translates `BrokerSettings` into `MT5Config` at its own
composition boundary, constructs the adapter during startup, and hands it to a
`BrokerOwner`. An unusable broker configuration fails startup at the
translation.**

### The selected implementation

`MT5BrokerAdapter` is the implementation the Atlas application runtime
constructs. The choice is a property of this application's composition, not of
the port, not of the configuration package, and not of any venue-neutral rule.

**No discriminator is added to `BrokerSettings`.** No `provider`, `venue`,
`broker` or `adapter` field, no enum, no string key. The section keeps the four
primitives ADR-0014 gave it and ATLAS-TASK-0022 implemented, and it stays
compatible with an implementation that is not this one.

**Adapter selection does not move into `atlas.config`.** The configuration
package does not learn which adapter exists, does not name one, and does not
gain a branch. **`atlas.broker` does not read `atlas.config`**, and
`tests/unit/broker/test_adapter_contract.py`'s permitted set of `atlas.broker`
and `atlas.common` is untouched by this record.

### Selecting `MT5BrokerAdapter` does not make `atlas.config` MetaTrader-specific

These are two different statements about two different layers, and the
distinction is the reason this record can be written at all.

`atlas.config` owns four primitive values that describe a trading account: a
login, a password, a server name and a terminal path. Every one of them is a
fact about a deployment. None of them names MetaTrader 5, and after this record
none of them does. What is MT5-specific is `MT5Config` — its `gt=0`, its
`min_length=1`, its `timeout_ms`, its `portable`, its `server_utc_offset` — and
that type stays in `atlas.broker.mt5`, where it already is.

The application is the only layer that holds both facts at once: what the
deployment configured, and which adapter this runtime builds. That is what a
composition boundary is for, and ADR-0013 already put it there:
"`apps/atlas-core` is responsible for obtaining and assembling whatever an
adapter needs in order to be constructed, and for handing it over."

### The translation boundary

The application translates:

```
atlas.config.BrokerSettings  ──▶  atlas.broker.mt5.MT5Config
```

The translation lives in `apps/atlas-core`. `BrokerSettings` remains the
repository-facing configuration surface — the thing a deployment sets through
`ATLAS_BROKER__*`. `MT5Config` remains the broker package's own representation,
the one `MT5BrokerAdapter` requires. Neither absorbs the other.

The dependency direction is unchanged and is fixed here explicitly:

```
        apps/atlas-core
         ↓            ↓
   atlas.config   atlas.broker
                       ↓
                   the adapter
```

and the edge this record **rejects**, as ADR-0014 rejected it:

```
atlas.config ──✗──▶ atlas.broker
```

`atlas.config` must not import `atlas.broker`, must not name `MT5Config`, and
must not gain a `.to_mt5_config()` or any other translating member. ADR-0014's
"No edge `atlas.config → atlas.broker` is created, because none is needed"
survives this record intact, and ATLAS-TASK-0022's **TR-2** — the mapping does
not appear in `packages/config/src` "in any form, including in a comment or
docstring" — stays in force.

### Unusable configuration fails startup

`BrokerSettings` permits values that open nothing: `login=0`, `password=""`,
`server=""`, `terminal_path=Path()`. `MT5Config` refuses them — `login` is
`gt=0` and `server` is `min_length=1`. ATLAS-TASK-0022 called the asymmetry
deliberate and left its meaning to this record.

**Its meaning is that the process does not start.** A deployment whose broker
configuration cannot produce an `MT5Config` is a deployment that cannot trade,
and it says so at startup rather than at the first order.

The application must not:

- continue silently without a broker;
- substitute `MockBrokerAdapter`, or any other implementation, as a fallback;
- invent a default login, server, password or terminal path;
- defer the failure to first use, or to an indefinite later point;
- treat an unusable production configuration as a valid "no broker" mode.

Four things happen in sequence and this record keeps them distinct, because
they fail differently and a later task needs to know which one it is handling:

| Stage | What it is | What can go wrong |
|---|---|---|
| Configuration representation | `AtlasSettings.broker` resolves | `ConfigurationError`, already handled |
| Translation validation | `MT5Config` is built from the four values | rejects `login=0`, empty `server` |
| Adapter construction | `MT5BrokerAdapter(config)` | no terminal contact |
| Terminal connection | `connect()`, via `BrokerOwner.start()` | the venue, the SDK, the network |

The refusal this record decides belongs to the second row. What error surface
it takes — which exception reaches `main()`, what exit code it produces, what
the failure record says — is an implementation question the entrypoint's
existing `startup_failed` path already answers for its own case, and it is not
decided here.

### Construction happens during startup

The intended lifecycle, in `apps/atlas-core`:

1. Resolve `AtlasSettings`.
2. Read `settings.broker`.
3. Translate `BrokerSettings` into an `MT5Config`.
4. Construct `MT5BrokerAdapter` from it.
5. Hand the adapter to a `BrokerOwner`.
6. `BrokerOwner` governs lifecycle and access on its existing terms.

This record describes a responsibility and its boundary. It does not implement
the sequence, and it names no function, method, class or module that will carry
it beyond those the repository already establishes — `main()`, `load_settings()`
and `BrokerOwner`. Whether the translation is a function, a classmethod, a
module or something else is an implementation choice with zero call sites
today, and ADR-0013's refusal applies to it verbatim: "naming a mechanism here
would decide an implementation on the evidence of zero call sites."

Construction is not connection. `MT5BrokerAdapter`'s docstring: "The terminal
is not touched until `connect()` is called, so an instance can be built during
composition on a machine where the MetaTrader5 package is not installed — the
import failure surfaces on connect, where it is actionable, rather than at
startup." Deciding that an adapter is *constructed* at startup therefore
decides nothing about when a session is *opened*.

### `BrokerOwner` is unchanged

`BrokerOwner` remains the ownership and lifecycle abstraction, exactly as
ATLAS-TASK-0020 delivered it. This record redefines none of its semantics:
`start()` connects and raises `RuntimeError` on a second call; `stop()` is a
no-op unless started; `adapter` raises `BrokerNotConnectedError` before start
and after stop; construction connects nothing; there is no module-level
instance and no lookup by name.

**Construction is upstream of ownership.** An owner is handed an adapter that
already exists. Its module says so — "An owner is handed an adapter. It never
builds one and never chooses one, and it does not look at which one it was
given" — and this record puts the building and the choosing where that sentence
always implied they were: above the owner, in composition.

`BrokerOwner` is therefore not the selector, and gains no knowledge of which
implementation it holds. It continues to hold a `BrokerAdapter`.

### The startup record is unchanged

No broker key, no broker value and no credential enters `build_startup_record`
because construction is now decided. The record keeps the eight keys it has.

`tests/unit/test_core_entrypoint.py` asserts this directly — the section is
absent, and neither a login nor a password reaches the rendered line — and that
test stands. The password may never enter the record under any future decision.
If broker startup observability is wanted, it is a separate decision with its
own record.

### Secrets are unchanged

Broker credentials keep the single route ADR-0003 defines and ADR-0014
extended: `BrokerSettings.password` is a `SecretStr` supplied through the
process environment, and no file under `config/` may carry it. This record
introduces no TOML password, no secrets service, no configuration service, no
`safe_*` accessor and no logging policy. The one new thing a translation does
with the password is read it in order to build an `MT5Config`, which is the
purpose it was configured for.

### The application composition layer may name the implementation it selects

**`apps/atlas-core` is authorised to import and name `atlas.broker.mt5`,
`MT5Config` and `MT5BrokerAdapter` to the extent required to perform the
translation and construction this record decides.**

That authorisation is what was missing. It is bounded by its purpose: it
permits naming the selected implementation for translation and construction. It
does not permit an application to reach past the port for anything else, and it
grants nothing to `apps/dashboard` or `apps/research`.

`tests/unit/test_core_broker_boundary.py` is **not modified by this record**,
and no boundary test is. Three of its assertions currently contradict this
decision — the implementation-name scan, the implementation-package scan, and
the rule that exactly one module reaches the port. Updating that contract to
match this decision is work for the task that implements it, and doing it here
would be implementing rather than deciding.

The general `apps/` import rule remains exactly as undecided as ADR-0013
`:242-249` left it. This record authorises one named layer to name one selected
implementation for one purpose. It "does not create, imply or prefigure a
general rule for what an application may import", and the task that eventually
writes that rule is still free to constrain `apps/atlas-core` further than this
record does.

## Six distinctions this record depends on

**Configuration representation is not adapter selection.** `BrokerSettings` is
generic; the application's choice is specific. Both statements are true at once,
and collapsing them is what would force a discriminator into configuration.

**Selecting `MT5BrokerAdapter` does not make `atlas.config` MT5-specific.**
`atlas.config` still owns four primitive values and nothing else.

**Translation is not construction.** `BrokerSettings → MT5Config` is
translation. `MT5BrokerAdapter(config)` is construction. They fail differently:
the first fails on unusable configuration, the second does not fail on it at
all.

**Construction is not connection.** Building the adapter touches no terminal.
`connect()` does, and `BrokerOwner.start()` is what calls it.

**`BrokerOwner` is not the selector.** It owns and governs an adapter after
construction, and never learns which one it has.

**`MockBrokerAdapter` is not a fallback.** It is a shipped implementation for
testing, exactly as ADR-0006 made it. Missing or invalid configuration does not
produce a mock, and there is no "mock if unconfigured" mode.

## Alternatives considered

**A discriminator field in `BrokerSettings`.** Rejected. It would put venue
identity in the configuration root — the precise thing ADR-0014 refused when it
declined to type the section as `MT5Config`, on the ground that doing so
"decides which venue Atlas is configured for". It would also buy nothing: a
discriminator is only useful when there is more than one adapter a deployment
may legitimately select, and multi-venue support is deliberately open. Adding
the field now would ship a configuration surface for a capability no decision
has authorised.

**Construct lazily, at first use rather than at startup.** Rejected. It would
move a configuration failure from a moment when a deployment is being validated
to a moment when it is being traded, which inverts the property the entrypoint
was built around — "the most valuable thing this entrypoint can do is prove
that contract holds in the environment it was deployed into". It would also
leave `BrokerOwner` holding nothing for part of its life, which its constructor
signature makes impossible by design.

**Fall back to `MockBrokerAdapter` when configuration is absent.** Rejected,
and the strongest reason is not architectural. A process that silently
substitutes a simulator for a trading connection looks healthy while placing no
orders, and the failure is discovered by absence. ADR-0006 built the mock to
simulate bookkeeping for tests; making it a runtime fallback would give a
production process a way to be wrong quietly.

**Select the adapter by environment — mock in `development`, MT5 elsewhere.**
Rejected here, but it is the closest call and it is not unreasonable. It would
spare a developer from configuring a terminal path to run the entrypoint. What
it costs is that `development` and `production` would then run different code
through different objects, and the one thing the entrypoint exists to prove —
that this deployment's configuration works — would be proven only in the
environments that need proving least. If the developer-experience cost of the
decision above turns out to bite, the answer is a new decision with a record,
not an environment branch introduced quietly.

**Leave selection to the implementation task.** Rejected, because that is what
the last three records did, and TASK-0023's discovery established that the
result is a repository where every component exists and nothing can legitimately
be joined. A test written by ATLAS-TASK-0020 blocks the join specifically so
that it cannot be made by implementation. Answering it in a task rather than a
record would decide architecture in a diff.

## Consequences

### Guaranteed

- **The last arrow has an owner.** `AtlasSettings ──▶ MT5Config ──▶
  MT5BrokerAdapter` is decided end to end for the first time. ADR-0014 answered
  the left side; this answers the rest.
- **`atlas.config` stays decoupled from `atlas.broker`.** No edge in either
  direction, no `MT5Config` in `packages/config/src`, no discriminator, and
  `test_adapter_contract.py`'s permitted set is untouched.
- **MT5-specific representation stays inside `atlas.broker`.** `MT5Config`
  keeps its constraints, its `frozen=True` and its `extra="forbid"`, and stays
  the type the adapter requires.
- **Start-up cannot proceed on an unusable broker configuration.** The
  asymmetry TASK-0022 preserved now has a meaning, and it is refusal.
- **`BrokerOwner` can be handed a real adapter through a stated boundary.** The
  near side of the seam stops being unreachable, and it acquires no new
  semantics in the process.
- **The implementation task may legitimately change the app→broker boundary
  contract.** That change now traces to an accepted record, which is the
  condition `test_core_broker_boundary.py:10-19` set for it.
- **The abstraction survives selection.** The application names an
  implementation at one point, for construction. What it hands onward is a
  `BrokerAdapter`, so ADR-0006's property — business logic cannot discover
  which adapter it holds — is preserved everywhere below composition.
- **Credentials keep one route and the startup record keeps eight keys.**

### Costs

- **This runtime is now explicitly MetaTrader-backed.** It was venue-neutral in
  its accepted decisions until this record, and it is not any more. That
  neutrality bought optionality that was never exercised, and the cost of
  keeping it was that nothing could be built.
- **Changing the selected adapter later requires a decision, not an edit.**
  This record must be superseded to select a different implementation. That is
  the immutability rule working as intended, and it is a real cost measured in
  process.
- **An unconfigured process will fail rather than run.** This is broader than
  production and should be read plainly: once construction happens at startup,
  *any* process reaching that step without usable broker configuration exits
  instead of starting, including a developer's. Today `ATLAS_ENV=development`
  with no `ATLAS_BROKER__*` set resolves settings and exits 0. After this
  decision is implemented, it will not. Softening that — by environment, by a
  flag, by a construction-optional mode — is a new decision and must arrive as
  one, not as an implementation convenience.
- **Configuration and broker construction now meet in an application.**
  ADR-0013 recorded this as a cost before it was concrete — "Credentials will
  end up in an application" — and this record makes it concrete. `apps/` is
  still the least-constrained directory in the repository, and the general
  import rule that would constrain it still does not exist.
- **A boundary test is now knowingly out of step with an accepted decision.**
  Between this record and its implementation, `test_core_broker_boundary.py`
  forbids what ADR-0015 authorises. The suite passes, because nothing does the
  forbidden thing yet, but the gap is real and belongs to the next task.
- **Multi-venue support stays open and gets no cheaper.** Nothing here designs
  for a second adapter, a second venue or a selection mechanism, and a future
  record that wants them will find one hard-coded choice to displace.

## What this record does not decide

- **Reconnect policy.** ADR-0007's `reconnect()` is still nobody's routine.
- **Health checks and the supervision timer.** ADR-0013's fifth responsibility
  is assigned and still unimplemented; this record neither schedules it nor
  designs it.
- **Failover**, of any kind, on any signal.
- **Multiple adapters, multiple venues or multiple accounts.** One adapter, one
  owner, one process.
- **Whether `apps/dashboard` may hold or invoke a `BrokerAdapter`.** ADR-0013
  opened that question and this record does not touch it. The same goes for
  `apps/research`.
- **External configuration or secrets services.** Still deferred on ADR-0003's
  own trigger.
- **Whether `server_utc_offset`, `timeout_ms` or `portable` are exposed.** All
  three keep `MT5Config`'s defaults, and ADR-0014's cost note about a non-UTC
  trade server stands unanswered.
- **Start-up record expansion.** No key, now or as a consequence of this.
- **Any production configuration schema beyond the four values TASK-0022
  implemented.** No new field, no new invariant, no new environment variable.
- **A dependency-injection framework, a service locator, a registry or a
  factory abstraction.** None is defined and none should be inferred. If an
  implementation task proves one necessary, it argues for it then, on evidence
  this record does not have.
- **The general `apps/` import rule.** Unchanged from ADR-0013 `:242-249`.
- **The run loop, the trading pipeline, and what receives the adapter.**
  `apps/atlas-core` still has no run loop, `atlas.execution` still hands its
  `OrderRequest` to nobody, and this record connects the owner to nothing
  downstream.
- **Order identity, idempotency, routing, fills, reconciliation, and account or
  portfolio state ownership.** Refused by ADR-0010, restated by ADR-0011 and
  ADR-0012, and not reopened.

## Relationship to ADR-0013

**ADR-0013 is not superseded, not edited and not reopened.** Its five
responsibilities stand as written, and `apps/atlas-core` remains the layer that
constructs, holds, governs access to, sequences and supervises a
`BrokerAdapter`.

This record answers three of the questions ADR-0013 left outside itself. Where
ADR-0013 says the application constructs the adapter, this says which adapter
and when. Where it says the application assembles whatever an adapter needs,
and ADR-0014 says what it reads, this says what the reading produces. Its
non-guarantee "No adapter is constructed by this record" was true of ADR-0013
and remains true of this one — deciding that construction happens is not
construction — but it ceases to be true of the repository when this decision is
implemented, and that correction belongs in the roadmap and the living
documents, never in ADR-0013.

Its access rule is adopted unchanged: access is granted downward by the owner,
never acquired upward by a package. Selecting an implementation at the
composition point is the owner deciding what it builds, not a package reaching
for one.

## Relationship to ADR-0014

**ADR-0014 is not superseded, not edited and not reopened.** The section is
still four values in `atlas.config`'s own primitives; `atlas.config` still does
not import `atlas.broker`; `MT5Config` is still neither embedded in the settings
model nor named by it.

This record answers four entries from ADR-0014's own list of what it does not
decide — adapter selection, when construction happens, where the composition
point is, and whether construction occurs at startup — and answers them in the
direction ADR-0014's reasoning pointed. Its guarantee that "Adapter selection
stays open" was a statement about what a section of primitives commits to, and
it stays true of the section: `BrokerSettings` still chooses nothing. What
changes is that the application now does.

Two of its costs come due here. The drift risk between `MT5Config` and the
section is now a runtime concern rather than a hypothetical, because there will
be a translation for a missing required field to surface at — ADR-0014
predicted exactly this: "the failure would surface at the wiring point rather
than at validation". And ADR-0012's revisit condition, "when a single wiring
point exists and can be pointed at", is **still not satisfied by this record**,
which decides that one will exist rather than building it. It will be satisfied
by the implementation, not here.

## Relationship to ADR-0006 and ADR-0007

**ADR-0006 is preserved.** `MockBrokerAdapter` stays a shipped implementation
in `atlas.broker.mock`, exported from there and never from `atlas.broker`,
importable by any package that wants to test against it. Selecting a different
implementation for the application runtime removes nothing from it. What ADR-0006
established — that business logic cannot discover which adapter it holds —
survives because the selection is confined to composition and what leaves
composition is a `BrokerAdapter`. ADR-0013's warning that "An owner that could
only hold one concrete adapter would break the property ADR-0006 shipped a
second implementation to establish" is respected: `BrokerOwner.__init__` still
takes a `BrokerAdapter` and still records nothing about which one arrived.

**ADR-0007 is untouched.** The two locks, their ordering, the finality of
`connect`/`disconnect`/`reconnect` and the non-blocking guarantee for `health()`
and `is_connected()` are unchanged. Its caller — assigned by ADR-0013 and
implemented as `BrokerOwner` — will for the first time have a real session to
sequence. Its supervision duty is still unclaimed by any implementation, and
this record does not claim it.

## Relationship to ATLAS-TASK-0022 and the TASK-0023 discovery

ATLAS-TASK-0022 implemented ADR-0014's section, and did so while leaving this
decision untaken by explicit instruction. Its Decision J holds the translation
table this record adopts; **TR-1** through **TR-3** kept the mapping, its
naming and its location out of that task; and **TR-4** deferred the meaning of a
validation rejection to "the task that builds the translation". This record
answers TR-4 before that task is written, because what a rejection means is
architecture and not implementation: it decides whether a misconfigured Atlas
runs.

The TASK-0023 read-only discovery found no missing code. It found that
`BrokerOwner` was built and unused, `MT5BrokerAdapter` built and unconstructed,
and the four values they needed configured and CI-validated — with one
undecided question between them. It also established, by running the scanners
in `tests/unit/test_core_broker_boundary.py` against a hypothetical translation
module, that three assertions in that file fail the moment an application names
`MT5Config`, and that the file's `APP_SOURCES` glob scans any new file under
`apps/` automatically. That is the prohibition this record lifts, on the terms
the file itself set: by a decision record, not by an edit to a test.

Nothing in this record is implemented. No adapter is constructed, no
translation exists, no boundary test changes, and `apps/atlas-core`'s entrypoint
still resolves configuration, emits a startup record and exits.
