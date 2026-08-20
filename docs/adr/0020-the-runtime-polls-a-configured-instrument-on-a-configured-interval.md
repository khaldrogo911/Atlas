# ADR 0020 — The runtime polls a configured instrument on a configured interval

**Status:** Accepted
**Date:** 2026-08-19

## Context

ADR-0019 decided the runtime's shape and named its hard prerequisites. The third
is **a market-data polling path**, "because nothing else in the pipeline can be
exercised without an observation, and because the MetaTrader 5 adapter offers no
push channel". Nothing downstream — a real strategy, a submitted order, an
exercised risk boundary — is reachable until that prerequisite is met.

ADR-0019 then closed every route by which the polling path could acquire the two
values it cannot run without. It listed "the exact market polling interval" among
the things it does not decide; it stated "**Any new configuration field or
environment variable.** This record adds none"; and it ruled that "Every item in
the section above is closed to implementation… these are answered by a record,
not by a diff". The traded instrument is named nowhere — not in any record, not
in `AtlasSettings`, and not in any file under `config/`.

The implementation that landed under ADR-0019 is explicit about the resulting
hole. `CoreRuntime.__init__` takes `observe`, `strategy`, `policy` and
`poll_interval_seconds` as required keyword parameters with no defaults, and the
module says why: "The poll interval, the observation source, the strategy and the
execution policy are parameters without defaults… A default here would be a
trading decision written into the layer least likely to be read as one, so there
is none: a caller that wants a running process has to state all four." The
runtime is therefore constructible and unrunnable. Nothing in the repository can
supply those four arguments, and two of them are this record's to unblock.

**This record supplies two of the four, and only two.** The strategy and the
execution policy are not this record's business and are named below only to be
refused.

### Three things a synthesised subscription needs, and which of them this is

The MetaTrader 5 adapter states, where `subscribe_ticks` raises, that Atlas "can
synthesise it by polling `symbol_info_tick` on its own thread, but that means
owning a scheduler, a change-detection rule and a backpressure policy". ADR-0019
quoted that sentence and supplied the first: the runtime owns the loop.

This record supplies the second — the rule about what a read means when its value
has not moved — and deliberately does not supply the third. ADR-0019 left
"detailed backpressure policy" open, and the cadence decided below removes the
condition under which one would be needed rather than writing one.

### The precedent already exists, and it was written for exactly this shape

`RiskSettings.max_margin_utilisation` is a trading-policy value that lives in
`atlas.config`, defaults to a value that "permits nothing at all", is enforced by
a production invariant, and is shipped in no layer of the `config/` tree.
`config/production/atlas.toml` says why in a sentence that transfers here without
alteration: "It is deliberately absent from every layer in this tree, because any
value for it is a trading policy and belongs to the deployment, not to the
repository."

Defining a field and shipping no value for it is therefore not a novelty this
record invents. It is how this repository already handles a number nobody but a
deployment is entitled to choose.

### What has happened since this record was proposed

At the time this record was proposed, ADR-0019 and the runtime module it
authorised were written but not committed, and the runtime module had no
roadmap entry and no task file. That gap is closed: ADR-0019 and
ATLAS-TASK-0029 are now committed (`461046b`, `4796fb2`), with a roadmap
entry and a task file (`docs/tasks/ATLAS-TASK-0029.md`). This record's own
prerequisite #1, below, is satisfied as a result.

## Decision

**The runtime polls one configured instrument, at a configured minimum interval.
Both values are configuration, owned by `atlas.config`. A runtime that has either
value missing refuses to start rather than choosing one. Every successful read is
an observation.**

This record establishes the configuration surface and the semantics of the
polling path, and authorises its implementation. It does not implement it, it
supplies no value, and it creates no task.

### The instrument and the interval are configuration

`AtlasSettings` gains a section for them. It is defined in `atlas.config`
alongside the others, in that package's own primitives.

This follows ADR-0012, and for its reason rather than by analogy. If a feature
package or an application owned the model, `atlas.config` would have to import it
to compose the settings tree while the consumer imports `atlas.config` to read the
resolved value — "a bidirectional edge between two packages, which is the shape
ADR-0010 called 'the cheapest way to break a layered graph'".

ADR-0012's *placement* transfers. Its *cost* does not, and the difference is worth
stating: ADR-0012 paid for the first edge from a feature package into
`atlas.config`, and this record pays for no edge at all. The runtime already
imports `atlas.config`, through the same `load_settings` its composition path has
used since ADR-0017.

The `ExecutionPolicy` counter-precedent does not apply, and it is refused on
ADR-0012's own test. A caller was always entitled to choose how an order is
*presented*; a caller is not entitled to choose *what a process trades* or *how
often it looks*. An instrument supplied per call is an instrument the caller can
change, which would make the traded market a property of whoever composed the
runtime — the same defect `BrokerSettings.terminal_path` refuses when it declines
auto-discovery, because "letting a vendor SDK choose makes which account Atlas
trades a property of the filesystem".

The section is subject to every rule `atlas.config` already carries. It names no
venue and no venue product, it carries no venue-identity field, and it does not
import `atlas.broker` — ADR-0014's separation is untouched, and translating a
configured string into whatever type the port requires is the runtime's work, at
the translation boundary ADR-0016 put venue knowledge behind.

**No field name, no environment-variable name, no TOML key and no value is chosen
here.** ADR-0012 fixed the same split for the exposure limit: "The principle is
fixed here; the mechanism is not."

### Absence is not permission

**A runtime with no configured instrument, or no configured polling interval, does
not start.** It does not poll with a value it chose for itself, and it does not
start without polling.

Specifically, and because each of these is a plausible way to make a process run:

- It does not adopt a broker default.
- It does not call `get_symbols` and select one.
- It does not infer an instrument from the account, the venue or the session.
- It does not inspect the filesystem.
- It does not silently disable polling and run a loop that observes nothing.

This is ADR-0012's fail-closed stance applied one layer over, and it is
ADR-0016's first failure class: a value that is the section's own default, or
empty, "is unusable everywhere, on every host, in every environment, and nothing
about the machine could make it work. This refuses startup."

The second class is not this record's, and is not converted into a startup
failure. An instrument the venue does not offer, or does not offer to this
account, is "configured but unusable on this machine" — a read-time failure, and
it stays one. **The configured instrument is not validated by asking the broker.**
ADR-0016's rule holds without amendment: "No filesystem I/O occurs during
configuration validation", and the same reasoning forbids network I/O and a venue
round trip there. Configuration validation answers whether a configuration is
valid, not whether a venue is reachable.

Whether the refusal is achieved by a required field, by a value that permits
nothing, or by an invariant of the kind `AtlasSettings` already carries is the
implementing task's to choose. The principle is fixed here.

### The interval is a minimum gap, not a period

**The configured interval is the minimum delay between the end of one cycle and
the start of the next. It is not a period the runtime attempts to hit.**

One cycle is: poll, observation, the pipeline evaluation ADR-0019 ordered, cycle
complete, wait the configured interval, next poll.

A cycle that takes longer than the interval delays the next poll and creates
nothing else. Precisely:

- No poll is queued.
- No poll is deferred, and no missed poll is made up.
- No two polls are coalesced.
- No cycle overlaps another.
- The runtime does not measure whether a poll is overdue, because nothing acts on
  the answer.

**No scheduler, queue, worker pool, thread pool or concurrency model is
introduced.** ADR-0019 decided the runtime is synchronous and thread-based, with
a serialised decision pipeline, and the runtime module records the consequence:
"A single thread runs the loop, so one evaluation finishes before the next begins
by construction rather than by policy, and backpressure cannot arise because
nothing is ever queued."

Fixed-delay is what preserves that sentence. A fixed-rate cadence would need a
notion of when a poll is due, a rule for a poll that is late, and a rule for
suppressing catch-up — which is a scheduler, and a scheduler is the thing the
adapter's own note says must not appear as a side effect. **Naming the semantics
is the point of this section**: unnamed, a later change from fixed-delay to
fixed-rate looks like an optimisation rather than the reintroduction of a backlog.

The waiting goes through ADR-0008's injected clock. A loop that reads the wall
clock directly abandons `ManualClock` and makes itself untestable.

**No backpressure machinery is introduced**, and ADR-0019's deferral of detailed
backpressure policy is not lifted. It is left unexercised: a cadence that cannot
produce a backlog needs no policy for one.

### Every successful read is an observation

**A successful configured market-data read produces an observation, including when
its value is identical to the previous read's.** The runtime does not compare one
read against the last, and does not decide whether market data has moved *enough*
to be worth an evaluation.

The alternative was a change-detection filter in the runtime, and it is refused
because it is a trading decision in the layer least likely to be read as one.
"Enough" is a threshold; a threshold on price movement is a strategy rule, and
ADR-0019 closed strategy timing rules and trade frequency to implementation. A
runtime that dropped unchanged reads would be answering the strategy's question
before the strategy is asked, and it would answer it identically for every
strategy the runtime is ever given.

The contract this leans on is already written. `Strategy.propose` states that
implementations "should be safe to call more than once with the same observation",
and gives the reason: "a strategy whose answer depends on how many times it has
been asked cannot be replayed, and a result that cannot be replayed cannot be
investigated after the fact." A strategy that wants to act only on movement is
free to hold that rule, where it can be reviewed as one.

Three things this deliberately does **not** introduce: a staleness threshold, a
significance threshold, and deduplication. Whether a quote is too old to act on
remains what the port says it is — "the caller's to judge", with the port imposing
no freshness policy "because what counts as stale differs between a scalper and a
daily system" — and this record does not become the caller that judges it.

`CoreRuntime`'s `observe` callable returns `ObservationT | None`, and this record
does not repurpose that seam as a change filter. What, if anything, produces
`None` is untouched; what is decided is that an unchanged value is not a reason to
produce it.

### The read operation is implementation's, within a rule

ADR-0019 left the read verb open: "Which of them the polling uses — ticks,
candles, symbol lookup or history — is implementation." That stays open, and this
record adds the constraint that keeps it from deciding anything further.

**The polling path may use any market-data read operation the broker port already
exposes, provided two things hold: every parameter the operation requires can be
supplied from the polling configuration section, and no new broker-port
authorisation is required to call it.**

The consequence is the point. The port's read operations take different parameter
lists, and some of those parameters are trading values: a bar length is a strategy
timing rule, and a history window is a lookback. An implementation that chose such
an operation and wrote a literal at the call site, or a default in source, would
be choosing a trading value ADR-0019 closed. Under this rule it cannot: an
operation whose parameters the section cannot supply is unavailable to the polling
path until a record extends the section.

**`UNCALLED_PORT_OPERATIONS` is not widened.** The port's market-data reads are
not in it and need no exemption; the runtime modules reach them under ADR-0019's
module census grant, which is unchanged.

**The subscription verbs stay granted to nothing.** `subscribe_ticks` and
`subscribe_candles` raise `NotImplementedError` on the MetaTrader 5 adapter, a
push model was not chosen, and this record does not reopen ADR-0019's refusal —
polling is what this record is, and a synthesised subscription is what it is not.

Which operation the implementation selects is not decided here, and no operation
is named in this record as the one to use.

### One instrument

**One configured instrument.** Not a list, not a mapping, not a portfolio, not a
venue mapping, not a second account and not a second venue.

This is an initial scope boundary and is recorded as one rather than as a
permanent shape. One instrument is what the prerequisite needs: an observation
exists, and the pipeline can be exercised. A list would require deciding whether
the instruments are read in one snapshot or several, whether one unreadable
instrument stops a cycle, and whether one evaluation covers all of them or one
covers each — none of which is answerable on the evidence of a pipeline that has
never run, and the last of which would reach into ADR-0019's serialisation
boundary.

Widening to more than one instrument is a later record's decision, and this record
takes no position on how it would be shaped.

### The observation type stays application-owned

**The runtime owns the concrete observation type.** `atlas.market` stays an empty
importable unit; no market-data domain model is created; `Strategy[InputT]` is not
changed.

ADR-0019 left this open — "the runtime supplies the type parameter. Whether the
observation later moves into `atlas.market` is not decided here" — and it stays
open. Moving it now would unblock nothing: `tests/unit/strategy/test_strategy_boundary.py`
forbids `atlas.strategy` from naming `atlas.market` at all, for the stated reason
that no market-data contract exists and "naming one of those packages here would
fix its shape before it exists". A strategy could no more name an `atlas.market`
observation than it can name a `Candle`.

`atlas.market`'s charter in `docs/architecture/overview.md` is "Ingestion,
normalisation, integrity, storage", and this record authorises none of those.
Populating the package with an observation type would either leave that charter
half-filled or invite the polling task to fill it, which is a market-data
architecture arriving as a side effect of a polling record.

The permanent home of the observation domain model is not decided here.

### Configuration is resolved once, at runtime startup

**The polling configuration is resolved once, when the runtime starts, and the
runtime does not read it again.**

No reload, no per-cycle read, no filesystem watch, no change detection, no mutable
configuration. This is the existing model rather than a new one: `AtlasSettings`
is frozen, ADR-0003 states that "Configuration cannot drift at runtime, which
removes a class of 'it worked at startup' bugs", and `get_settings` resolves once
per process.

ADR-0019 recorded the consequence as a cost and left the question open — "Whether
the runtime reloads configuration is not decided here, and until it is, a limit
change requires a restart." That stays open, and this record's values join the
same rule: changing the instrument or the interval is a restart.

### What polling is, and what it is not

The boundary this record draws around itself, because the polling path is exactly
where the next four decisions would be easiest to take in passing.

Inside: what is read, how often it is read, what happens when it cannot be read
for want of configuration, and what a read means.

Outside: whether an observation is tradable; whether a strategy should propose
anything; what repeated observations imply about how often to trade; throttling;
trade frequency; staleness; market significance; sizing; order presentation; and
everything after the intent. Each belongs to a layer that already exists and to a
decision that is either taken elsewhere or not taken at all.

## Implementation authority

ADR-0018's standard applies to this record as it did to ADR-0019: implementation
must not be left to infer which permissions it holds.

An implementing task **may**:

- Add the polling section to `AtlasSettings` in `atlas.config`, and choose its
  field names according to the conventions the configuration package and its tests
  already enforce.
- Add the `ATLAS_`-prefixed environment plumbing that follows from those names
  under ADR-0003's existing precedence, and add TOML structure where the existing
  layers make it appropriate.
- Implement the startup refusal for a missing instrument or interval, by whichever
  of the three mechanisms above it judges correct.
- Select one existing broker-port market-data read operation, subject to the rule
  above.
- Supply the configured instrument and every other parameter that operation
  requires from the polling section.
- Wait through ADR-0008's injected clock.
- Implement minimum-gap polling, preserving ADR-0019's serialised evaluation.
- Extend the boundary tests only within the authority this record and ADR-0019
  state, and only by named module. A positive census of the selected read
  operation is within that authority; a grant expressed by prefix, directory,
  wildcard or package-wide exemption is not, in this record any more than in
  ADR-0019.
- Add behavioural and unit tests.

An implementing task **may not**:

- Choose a production instrument or a production interval, or ship either in
  `config/`.
- Add strategy logic, or a strategy implementation.
- Add an `ExecutionPolicy`, or configuration for one.
- Add a `RetryPolicy` value, attempt count or backoff.
- Add a health, staleness, freshness or significance threshold.
- Add a subscription, or widen `UNCALLED_PORT_OPERATIONS`.
- Add concurrency, a scheduler, a queue, a worker pool or a backlog.
- Create or populate `atlas.market`, or change `Strategy[InputT]`.
- Add multi-instrument, multi-venue, multi-account or failover support.
- Add configuration reload.

## Alternatives considered

**A default instrument or interval in source.** Rejected, and it is the
alternative the rest follow from. A default here is a trading decision written
where nobody reviews trading decisions, which is ADR-0011's reason for refusing
execution a default order type and the runtime module's own stated reason for
having no defaults. It also breaks the property the configured value exists to
have: a value nobody chose is indistinguishable, at the point of use, from one
somebody did.

**Discovering the instrument from the broker, the account or the filesystem.**
Rejected. It makes what Atlas trades a property of the venue's symbol list, the
account's history or the host's disk, which is the defect `BrokerSettings.terminal_path`
already refuses. It also puts a venue round trip inside startup validation, which
ADR-0016 forbids in the same breath as filesystem probes — and an unreachable
venue would then be indistinguishable from an unconfigured process.

**Fixed-rate cadence with catch-up.** Rejected. It requires a due time, a
lateness rule and a catch-up suppression rule, which together are a scheduler; and
a catch-up burst after a slow cycle submits decisions computed from readings taken
while the runtime was busy, which is the correctness argument ADR-0019 used to
serialise the pipeline in the first place. Fixed-delay makes a backlog impossible
by construction rather than by policy.

**Naming a single read operation — `get_tick` — in this record.** Rejected,
though it is the closest call. It is the operation with no further trading
parameter, which is exactly what makes it attractive; it also carries a decision
this record should not take. `Tick` "carries no notion of staleness", and the
port declines to impose a freshness policy, so a record that mandated a quote-only
polling path would owe a staleness judgement — a threshold ADR-0019 declined, and
one the boundary test already describes as "the health policy that record declines
to write". The parameter rule constrains the choice without taking it.

**Creating `atlas.market` now.** Rejected. It unblocks no strategy, because the
strategy boundary forbids the package by name; it exceeds the package's charter,
which is ingestion, normalisation, integrity and storage; and it would fix the
shape of a market-data model on the evidence of a single consumer that has never
run. ADR-0019 left the question open and it costs nothing to leave it open.

**Treating an unchanged read as not an observation.** Rejected. "Unchanged
enough to skip" is a threshold, and a threshold on price movement is a strategy
rule held in the runtime, applied identically to every strategy the runtime is
ever given. `Strategy.propose` is already contracted to tolerate being asked
twice about the same observation, so the filter buys correctness nothing and costs
a decision this record has no standing to make.

**Multi-instrument configuration now.** Rejected as premature. It requires
deciding snapshot semantics, partial-failure semantics and whether one evaluation
covers several instruments — the last of which touches ADR-0019's serialisation
boundary — on the evidence of a pipeline that has produced no observation yet.

**Deferring polling until a real strategy exists.** Rejected: it inverts
ADR-0019's own ordering, which makes the polling path a prerequisite because "a
real `Strategy` implementation… depends on the observation type and nothing else".
A strategy written first would fix the observation type by being first, which is
the shape ADR-0018 exists to prevent.

## Consequences

### Guaranteed

- The polling path's two withheld values have a home, an owner and a refusal, and
  they arrive by a record rather than by a diff.
- A running runtime polls an instrument somebody chose, at an interval somebody
  chose, and a runtime missing either does not run.
- The repository ships neither value. Both come from a deployment, as
  `risk.max_margin_utilisation` already does.
- The cadence cannot produce a backlog, and the runtime acquires no scheduler,
  queue, worker pool or additional thread.
- ADR-0019's serialised decision pipeline is unchanged, and so are ADR-0007's
  locks.
- Configuration validation still performs no I/O of any kind, and still does not
  ask a venue anything.
- The broker boundary is not widened. `UNCALLED_PORT_OPERATIONS` keeps its eight
  names, the six runtime grants stay six, and no subscription verb is granted.
- `atlas.market` stays empty, `Strategy[InputT]` stays generic, and no market-data
  domain model is created.
- The configuration package still names no venue and still does not import
  `atlas.broker`.

### Not guaranteed, deliberately

- **That Atlas becomes deployable or tradable.** It does not. `place_order` raises
  `NotImplementedError` on the MetaTrader 5 adapter, no deployable strategy
  exists, and no `ExecutionPolicy` is supplied by anything. Each remains a
  separate prerequisite, and none is collapsed into this record.
- **That an observation reaches a strategy that has an opinion.** `Strategy` has
  one reference implementation that returns a constant.
- **That a poll succeeds.** The instrument is not validated against the venue, by
  decision. A configured instrument the venue does not offer fails at the read.
- **That the interval is sensible.** It is the deployment's to choose, and no
  bound on it is decided here.
- **That the observation type is where it will finally live.** It is
  application-owned for this stage, and its permanent home is undecided.
- **That polling is efficient.** Every successful read is an observation and every
  observation is evaluated, which is more evaluation than a change filter would
  produce. That is the decision, not an oversight.

### Costs

- **A second trading-policy value lives in `atlas.config`.** Anyone reading the
  configuration package to learn about infrastructure now finds an instrument and
  a polling interval there beside the exposure limit. The alternative was an
  import cycle, and the mitigation is that this is where the layering, the
  validation and the review surface already are.
- **Two more values must be supplied to run the runtime**, on top of the four
  broker values ADR-0016 already requires. Every one of them is a value a process
  cannot trade without.
- **The section list grows, and a test pins it.** Adding a section is a visible
  diff in the configuration tests, which is what those tests are for.
- **Changing the instrument or the interval requires a restart**, because
  configuration is resolved once. This is ADR-0019's existing cost extended to two
  more values rather than a new one.
- **Every unchanged read costs a full evaluation.** Over a weekend, a quote that
  has not moved since Friday is proposed on, once per cycle. The alternative was a
  threshold in the wrong layer, and the cost is accepted knowingly.
- **The first configured trading value that names an instrument exists.** Until
  now `atlas.config` held infrastructure and one limit. It now holds an answer to
  "what does this process trade", which is a question a reader would not have
  thought to look there for.

## What this record does not decide

- **The concrete instrument.** No symbol is chosen, named or implied.
- **The concrete polling interval.** No number is chosen, and no bound on one.
- **Field names, environment-variable names and TOML keys**, and any value for
  any of them in any layer of `config/`.
- **Which broker read operation the polling path uses.**
- **The strategy implementation**, its rules, its placement, and anything about
  the observation's permanent ownership beyond this stage.
- **Backtesting**, in any form.
- **`ExecutionPolicy`**, its design, and any configuration surface for it.
- **`place_order`'s implementation**, filling mode and deviation policy.
- **`RetryPolicy` value, attempt count and backoff.**
- **Health, staleness and freshness thresholds**, and what a stale answer costs.
- **Broker startup observability**, reserved by ADR-0015 and ADR-0017 to a
  separate record.
- **Order lifecycle, routing, idempotency, fills and reconciliation.**
- **Account and portfolio state ownership.**
- **Persistence wiring.** Nothing here connects the runtime to PostgreSQL, Redis
  or DuckDB.
- **Multi-instrument, multi-venue and multi-account support, and failover.**
- **Configuration reload.**
- **The runtime's thread count and shutdown signal handling.**
- **Deployment restart policy and healthchecks.**
- **The general `apps/` import rule**, open since ADR-0013 and left open here.
- **A change to `BrokerOwner`'s public semantics**, in either direction.
- **Detailed backpressure policy**, which stays where ADR-0019 left it and is left
  unexercised rather than answered.
- **Trade frequency, throttling and strategy timing rules.**
- **Stale-documentation repair**, which remains a separately authorised task.

## Implementation cannot decide these by implication

**Every item in the section above is closed to implementation.** A task that finds
itself choosing one has left this record, whatever its stated scope, and the test
is ADR-0018's and ADR-0019's: these are answered by a record, not by a diff.
Nothing above is released by this record's silence on it.

Four cases are worth naming because each is a step a reasonable implementation
would take without noticing:

- **Writing a bar length, a count or a lookback at the call site** to make a
  chosen read operation compile. That is a trading value, and the parameter rule
  exists to make it a configuration question or a blocker rather than a literal.
- **Adding a staleness check** to avoid acting on a weekend quote. The port
  declines to impose a freshness policy on purpose; a runtime that adds one has
  written the health policy ADR-0019 declined.
- **Skipping an unchanged read** as an efficiency improvement. That is the
  decision this record took the other way, and taking it back is a record's job.
- **Turning fixed-delay into fixed-rate** because a poll drifted. That
  reintroduces catch-up, and with it the backlog the cadence exists to make
  impossible.

## Relationship to ADR-0019

**ADR-0019 is not edited, not superseded, and its status is not changed.** This
record is downstream of it and supplies the specification layer of its third hard
prerequisite.

It answers two items from ADR-0019's **What this record does not decide** — the
market polling interval, and, by supplying the polling path's configuration, the
traded instrument — by the mechanism ADR-0019 itself specified: "these are
answered by a record, not by a diff". It also answers a question ADR-0019 raised
without listing. ADR-0019's cadence section says "Each **accepted** market
observation triggers exactly one synchronous, ordered… evaluation" and defines
acceptance nowhere; **Every successful read is an observation** above defines it.

ADR-0019's guarantee that it adds no configuration field or environment variable
stays true **of ADR-0019** and is lifted only here — the same construction ADR-0016
used when it lifted ADR-0015's "No new field, no new invariant, no new environment
variable" for the invariant half alone.

Everything else on ADR-0019's undecided list stays undecided, and is repeated in
**What this record does not decide** above so that no item is released by silence.
Its module-bounded grants, its six port operations, its eight withheld ones, its
serialised pipeline and its refusal of the subscription verbs are unchanged.

## Relationship to ADR-0018

**ADR-0018 is not edited, not reopened, and its status is not changed.** Its
deferral was closed by ADR-0019, and this record does not reopen it. What binds
here is the standard ADR-0018 set for the record that lifts it: "Answering some
and leaving others to implementation is the failure mode this record exists to
prevent." That standard is why the observation question above is answered in this
record rather than left to the polling task.

## Relationship to ADR-0012

**Not superseded, not edited, not reopened.** No exposure limit, risk model or
`RiskSettings` field is touched.

This record follows ADR-0012's placement, its authority argument, its
fail-closed stance and its split between a fixed principle and an open mechanism.
It does not follow its cost: ADR-0012 paid for the first edge from a feature
package into `atlas.config`, and this record pays for none, because the runtime
already imports the configuration package.

Neither does it copy ADR-0012's mechanism prematurely. Whether the polling values
are enforced by a required field, a permits-nothing default or a production
invariant is left open here exactly as ADR-0012 left it there.

## Relationship to ADR-0016

**Not superseded, not edited, not reopened.** The four broker fields, their
invariants, the translation site and the existing refusal surface are all
untouched.

What this record reuses is ADR-0016's distinction between a value that is
unusable everywhere and a value this machine cannot honour, and its rule that
configuration validation performs no I/O. The configured instrument is validated
as configuration and never by asking a venue, which is that rule applied to a
network call rather than a filesystem probe.

## Relationship to ADR-0011

**Not superseded, not edited, not reopened.** Execution still builds the request
and reaches no port; no order type is chosen; no `ExecutionPolicy` is created,
stored or configured by this record.

One premise of ADR-0011 is worth naming so that nobody resolves it in a diff. It
justified execution not reading a policy from configuration partly on the grounds
that "no configuration for them exists: `AtlasSettings` holds `logging`,
`postgres`, `redis` and `duckdb`, and there is no broker or venue surface anywhere
in it." That statement has been overtaken — by `BrokerSettings`, by
`RiskSettings`, and now by this section. **ADR-0011's decision is untouched by
that.** Its reason for refusing execution a default was never only that
configuration was absent; it was that a default chosen inside execution "would
settle both by accident, in the package least likely to be read as policy". The
existence of a polling section is not permission to add an execution-policy one,
and ADR-0011 is not edited to say so — a later record answers an earlier record's
premise without editing it.

## Relationship to ADR-0010

**Not superseded, not edited, not reopened.** This record produces observations
and constructs no `TradeIntent`; ADR-0010's "Nothing produces an intent" is
untouched by it. The risk boundary, the two-valued verdict and the refusal to
define account or portfolio state are all unchanged.

## Relationship to ADR-0003

**Untouched.** The new section obeys the existing precedence order, the
`extra="forbid"` typo protection, the fail-fast validation and the frozen settings
object. "Structure in files, secrets in the environment" is unaffected: an
instrument and an interval are structure, not credentials, and no file under
`config/` gains a secret. That neither value is shipped in `config/` is this
record's decision about trading policy, not an exception to ADR-0003.

## Relationship to ADR-0008

**Untouched.** The interval is waited through the injected clock, as ADR-0019
already requires of the runtime's timing. No module in the polling path calls
`time.sleep` or reads the wall clock directly, and `ManualClock` remains able to
drive many cycles without spending the wall time.

## Dependency and implementation sequencing

**No task is created by this record.** This section describes the boundary a
future task would work inside, so that its scope can be judged before it is
authorised.

Hard prerequisites, in order:

1. **ADR-0019 and the runtime module it authorised, committed and represented in
   the roadmap.** **Satisfied.** Committed as `461046b` (feat) and `4796fb2`
   (docs), with a roadmap entry and `docs/tasks/ATLAS-TASK-0029.md`.
2. **This record, accepted.** **Satisfied.** This record is `Accepted`.
3. **The polling implementation**, which is the specification above turned into a
   configuration section, a refusal and a loop.

Independent of the above, and safe to do in any order:

- `place_order` on the MetaTrader 5 adapter, and the remaining trading verbs,
  which are port conformance and touch no application module.
- Broker startup observability, which needs its own record first.

Downstream, and not sequenced here:

- A deployable strategy, which depends on the observation type this record leaves
  application-owned.
- An `ExecutionPolicy`, which nothing supplies.
- Order lifecycle, routing, idempotency, fills and reconciliation.

Premature under this record, and named because each looks safe:

- **A change filter added to the observe path** to reduce evaluations.
- **A second instrument added to the section** because the field would take a
  list as easily as a string.
- **A staleness threshold** added to make a weekend quote behave sensibly.
- **A concrete instrument or interval committed to `config/`** to make the
  runtime runnable locally. Local runs supply them through the environment, as
  `risk.max_margin_utilisation` already is.
