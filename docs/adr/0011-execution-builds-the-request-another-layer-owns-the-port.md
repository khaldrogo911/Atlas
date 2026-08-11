# ADR 0011 — Execution builds the request; another layer owns the port

**Status:** Accepted
**Date:** 2026-08-08

## Context

[ADR-0010](0010-the-risk-boundary-is-a-verdict-on-an-intent.md) closes by naming
what it could not demonstrate: "Nothing consumes a verdict. `atlas.execution` is
still a stub, so 'only approved intents are executed' is stated and not yet
enforced by a test." `docs/architecture/overview.md` records the same gap twice
— once as the flow's missing half, and once as the invariant whose behavioural
half "waits on `execution` and an engine existing". `atlas.risk` says it a third
time in its own README. Three documents, one absence.

`atlas.execution` has carried its responsibility in a module docstring since
ATLAS-TASK-0001 and nothing else: "Translation of approved trade intents into
broker orders, routing, fill and partial-fill handling, reconciliation against
broker state, and idempotent retry of in-flight instructions." That is a large
responsibility, and the first slice of it — the translation — is the one the
repository already has both ends of.

The slice does not close cleanly, and the reason is a type. `OrderRequest`
requires an order type: `type: OrderType` has no default, because
`atlas.broker.models.OrderType` decides "how the order should be presented to
the venue" and a LIMIT order with no limit price is, in the port's own words,
"not a risky order, it is an incompletely built one". `TradeIntent` carries no
order type, deliberately: ADR-0010 omitted it on the grounds that "an order type
or a working price would make the intent an instruction rather than a
recommendation", and `atlas.risk` "names no order type and no working price"
because "how an order is *presented to a venue* … is execution's question". A
verdict therefore does not contain enough to build a request, and whatever
supplies the difference must name types that live in `atlas.broker`.

That is the collision this record resolves. The dependency graph has exactly
three edges between feature packages, every one of them downward:
`atlas.broker → atlas.common`, `atlas.risk → atlas.broker`, and
`atlas.strategy → atlas.risk`. `atlas.execution` has none. Adding one reads, at
a glance, like the thing the architecture exists to prevent — a package above
the port acquiring a route to a venue — and the reading is wrong in a way that
is worth writing down, because the next person to see the edge will make it.

None of this is enforced by packaging. There are no per-package manifests; one
root `pyproject.toml` declares all eighteen source roots, so a stray import
installs, imports and type-checks without complaint. The boundaries are held by
AST-walking tests and by records like this one.

## Decision

**`atlas.execution` turns an approved `RiskVerdict` into an `OrderRequest`, and
answers with nothing for a rejected one. It names the broker's order vocabulary
in order to do that, and it reaches no broker: it does not own, construct or
invoke a `BrokerAdapter`. A layer outside `atlas.execution` owns broker
interaction.**

```
TradeIntent ──▶ atlas.risk ──▶ RiskVerdict ──▶ atlas.execution ──▶ OrderRequest ──▶ broker-owning layer ──▶ BrokerAdapter ──▶ venue
```

### The order vocabulary stays the broker's

`OrderRequest`, `OrderType` and `Price` are used as they are defined in
`atlas.broker`, not restated in `atlas.execution`. This is the rule ADR-0010
applied to `SymbolName`, `OrderSide`, `Price` and `Volume` and that
`atlas.broker.types` applies to its own aliases: two definitions of one concept
"would create two rules for one concept and guarantee they diverge". A
parallel execution-side order vocabulary would diverge at the point of
translation, which is the least visible and most expensive place for two rules
about one concept to disagree.

The port validates that a request is *well formed*. Risk judges whether it is
*wise*. Execution decides how it is *presented*. Three questions, three owners,
one type carrying the answer to the third.

### The new edge is a type dependency, and it is not a route to a venue

`atlas.execution → atlas.broker` is authorised, downward, and specific: it
exists so that execution can name the existing order-presentation contract. It
is the fourth edge in the graph and it is not permission for anything else.

ADR-0010 already drew this distinction, for `atlas.strategy`, in the sentence
that matters most here: "a transitive type dependency is not a call path".
`atlas.strategy` was permitted to handle the port's primitives through
`TradeIntent`'s field types while remaining unable to obtain a `BrokerAdapter`,
construct an `OrderRequest`, or reach a venue. `atlas.execution` sits one step
further along: it may name and construct an `OrderRequest`, because building one
is its declared job. It may still not obtain, construct or call a
`BrokerAdapter`.

Naming a type the port defines and calling the port are different acts, and the
distance between them is the whole of this decision. An `OrderRequest` is inert.
It is a description of an order that no venue has seen, which is precisely what
its own module says: "An instruction to place an order, before any venue has
seen it." Producing one changes nothing anywhere. Placing one is somebody else's
authority.

### Execution does not invent the answers it needs

The order type and the working price are supplied to `atlas.execution` by an
execution policy that it receives. It does not choose them from a rule of its
own, and it does not read them from configuration, because no configuration for
them exists: `AtlasSettings` holds `logging`, `postgres`, `redis` and `duckdb`,
and there is no broker or venue surface anywhere in it.

The alternative was to let execution hold a default — always MARKET, say — and
that is a policy decision wearing an implementation's clothes. Filling-mode
selection per instrument and a deviation policy are named in
`atlas.broker.mt5.adapter` as the two questions order submission still has to
answer, with the observation that "neither has an obviously right answer, which
is why they are not settled here". A default chosen inside execution would
settle both by accident, in the package least likely to be read as policy.

### A rejected verdict is not a failure

An approved verdict yields an `OrderRequest`. A rejected verdict yields nothing.
Nothing is not an error condition, and it is not represented as one: risk
refusing a trade is risk working.

The existing broker exception hierarchy describes venue and transport failure —
`BrokerOrderRejectedError` is a *venue* declining an order it was sent. Reusing
it for a verdict the system itself declined would mean an order that was never
built raising the error of an order that was sent and refused, and it would put
a venue's vocabulary on a decision no venue participated in. Inventing an
execution-specific exception instead would create a second failure vocabulary
for a case that is not a failure.

The repository already has the shape for this. `Strategy.propose` returns
`TradeIntent | None`, where `None` means the strategy has nothing to say, and
`atlas.strategy.contracts` gives the reason a sentinel was refused there: it
"puts a value into the pipeline that *looks* tradeable, and the first consumer
that forgets to check sends it to risk". The same hazard one layer further on is
worse, because the consumer that forgets to check sends it to a venue. There is
no such value here to forget about.

### Nothing here holds state, and nothing here leaves the process

The translation is per call and keeps nothing between calls. There is no
execution state, no in-flight registry, no reconciliation ledger and no
persistence. `atlas.execution` gains no lifecycle: no start, no stop, no run
loop, no long-lived service.

ADR-0010's refusal to define account or portfolio state **remains in force**.
The venue-reported account surface the port already exposes — `Account`,
`Position`, `margin_required`, `margin_available`, `can_trade` — is per-call
state read from a broker, not the portfolio-state contract ADR-0010 declined to
invent, and this record does not turn it into one. Nothing in this decision
reads it.

There is no external integration of any kind: no MetaTrader 5, no broker
connection, no venue, no datastore, no network. `MetaTrader5` remains a
Windows-only optional extra, CI remains two `ubuntu-latest` jobs with no
services, and neither fact needs to change for this decision to be implemented
or tested.

## Consequences

### Guaranteed

- **A verdict has a consumer.** The type that reads a `RiskVerdict` and the type
  that a venue-facing layer eventually receives are connected by something
  written down rather than by prose in three READMEs.
- **Risk stays on the path.** Execution is handed a decision it did not make and
  cannot revisit. It never sizes, and the approved volume is the only volume it
  can carry forward, because that is the only one an approved verdict holds.
- **Presentation stays out of risk and out of strategy.** Order type and working
  price are answered where the responsibilities table puts them, and neither
  `atlas.risk` nor `atlas.strategy` acquires a name it is currently forbidden to
  mention.
- **The edge is legible.** `atlas.execution → atlas.broker` has a written reason,
  a written limit, and a test that will hold the limit.

### Not guaranteed, deliberately

- **Nothing places an order.** The broker-owning layer this record names does not
  exist. What execution produces is received by nobody today, which is the same
  position `TradeIntent` was in between ATLAS-TASK-0011 and ATLAS-TASK-0012.
- **No routing, no fills, no reconciliation, no idempotent retry.** The other
  four responsibilities in the execution stub's docstring are untouched. Each
  needs state, a venue, or both.
- **No order type is chosen.** The policy supplies it; nothing in the repository
  yet supplies the policy.
- **Nothing is persisted or transported.** No store and no envelope is defined —
  ADR-0010's fifth non-guarantee is unchanged.
- **No account or portfolio state contract.** ADR-0010's fourth non-guarantee is
  unchanged and is restated above so that nobody reads the new broker edge as
  having relaxed it.

### Costs

- **A fourth edge, and the one that will be misread.** `execution → broker` looks
  like venue access from the outside. The mitigation is this record and a
  boundary test; the residual cost is that every future reader has to be told the
  difference, and some of them will be told by a review comment rather than by
  the document.
- **The policy is a hole in the contract.** Execution cannot act without one, and
  nothing produces one. That is honest — the alternatives were a default chosen
  in the wrong package or an intent that instructs — but it means this slice is
  provably correct and not yet usable.
- **Two packages now name `OrderRequest`, and only one may call the port.** The
  distinction between naming and calling is real and is enforced by an AST scan.
  It is not enforced by anything a type checker or the packaging can see.

## Alternatives considered

**A new `ExecutionInstruction` contract, to avoid the broker edge.** Rejected.
It duplicates order-presentation vocabulary the repository already owns and
tested, and it does not remove the dependency — it defers it to whoever converts
the new type into an `OrderRequest`, who needs exactly the edge this would have
avoided. Two descriptions of one order diverge, and they diverge at the
conversion, which is where ADR-0010 says a disagreement is least visible. The
same reasoning that rejected risk-local `Price` and `Volume` aliases rejects
this.

**`atlas.execution` owns the `BrokerAdapter`.** Rejected. It is the shortest
path from a verdict to a venue and it collapses two questions into one package:
what an order should look like, and how a connection to a venue is obtained,
authenticated, retried and reconciled. It would also require what does not exist
— an adapter construction site, broker configuration, credential handling — and
would drag venue integration, connection lifecycle and retry into a decision
about a type. There is no `BrokerAdapter` construction anywhere outside
`atlas.broker` today, and this record does not create one.

**Stop before `OrderRequest`: let execution accept a verdict and produce
nothing.** Rejected. It honours the layering by leaving the architecture
unfinished. `docs/architecture/overview.md` already assigns the translation to
execution by name — "only `atlas.execution` turns an approved verdict into an
`OrderRequest`" — so a boundary that consumed a verdict and answered with
nothing useful would not be the boundary the overview describes, and the gap
ADR-0010 recorded would still be open afterwards.

**Give execution the account or portfolio state it would need to size or price
an order.** Rejected, and it is rejected by ADR-0010 rather than here.
Execution does not size — the responsibilities table forbids it and the approved
volume is already on the verdict — so the state is not needed for this decision,
and inventing it would fix the shape of a contract before the controls that read
it exist. The port's existing `Account` and `Position` surface is not a
counter-example: venue-reported state read per call is not the portfolio-state
contract ADR-0010 declined to invent.

**Add the order type to `TradeIntent`.** Rejected. It reverses ADR-0010's
deliberate omission and makes a recommendation into an instruction, which puts
routing knowledge in the strategy layer — the outcome the first alternative in
ADR-0010's own list was rejected to prevent.

**Let execution choose the order type itself, defaulting to MARKET.** Rejected.
It is a policy with no owner, written in the package least likely to be reviewed
as policy, and it silently answers the two questions
`atlas.broker.mt5.adapter` explicitly declines to answer.

## Relationship to ADR-0010

ADR-0010 is **not superseded and not edited**. It is immutable, and everything it
decided still holds: risk judges an intent and never builds an order; the
verdict is two-valued; the primitives are the broker's; the contracts live in
`atlas.risk`; rejection reasons are a closed vocabulary; and there is no account
or portfolio state contract.

This record answers a question ADR-0010 left open rather than reversing one it
closed. Where ADR-0010 says "`atlas.execution` turns an approved verdict into an
`OrderRequest`" as a statement of intent, this says how the boundary is shaped
and what the dependency it requires does and does not permit.

One consequence is worth stating plainly. When this decision is implemented,
ADR-0010's second non-guarantee — "Nothing consumes a verdict" — becomes
inaccurate, exactly as its first non-guarantee did when ATLAS-TASK-0012 gave
`TradeIntent` a producer. That is the immutability rule working as designed and
not a defect: the correction belongs in the roadmap's completed record and in
the living documents, never in ADR-0010 itself.

## Implementation constraints

These bind the task that implements this decision, and they are not restated as
suggestions:

- `atlas.execution` may import `atlas.risk` and `atlas.broker`. No other
  `atlas` package edge is authorised.
- `atlas.execution` may not name, obtain, construct or invoke a
  `BrokerAdapter`.
- The implementation is stateless and contract-only: no lifecycle, no run loop,
  no service object holding state between calls.
- No new exception type, no new retry mechanism, no persistence, no
  configuration key, no external integration.
- `tests/unit/execution/test_execution_boundary.py` is required. It is the only
  thing that will hold the naming-versus-calling distinction, since neither the
  packaging nor the type checker can see it, and by the standard ATLAS-TASK-0012
  set it must include cases proving the scanner can fail.
