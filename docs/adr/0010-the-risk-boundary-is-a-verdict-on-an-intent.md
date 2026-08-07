# ADR 0010 — The risk boundary is a verdict on an intent

**Status:** Accepted
**Date:** 2026-08-07

## Context

`docs/architecture/overview.md` states as its first invariant that a trade
intent becomes an order only by passing through `atlas.risk`, and that every
other safety property depends on that one. Nine tasks later, nothing said what a
trade intent *is*, or what passing through risk *returns*. The invariant was
prose.

`OrderRequest` had already drawn the line from the other side. Its module says
that whether a request is *wise* — the size against the account, the stop on the
correct side of entry, the instrument permitted by policy — "is a risk decision,
made against state neither this model nor the port can see". The port therefore
validates that a request is *well formed* and deliberately declines to judge it.
Something upstream owes the judgement, and until now no type existed to carry
either the question or the answer.

Left undefined, the shape gets decided by whichever task needs it first, and the
likely accident is easy to name. A strategy package that had to reach execution
would build the thing execution already accepts — an `OrderRequest` — and risk
would become a validator invoked on an order that already exists. At that point
risk is advisory: the object it was asked about is complete, its size already
chosen, and the only power left is to say no to something someone else has
already decided. Every safety property in the overview rests on risk being on
the path rather than beside it, and an intent that is already an order has taken
risk off the path while appearing to leave it there.

The second thing left undefined was sizing. If `TradeIntent` carried the size
that would be traded, risk could only accept or refuse it, and a system that can
only refuse has one response to a portfolio at 90% of its exposure limit: reject
the trade. The useful answer — take it, smaller — has to be expressible, and it
has to be expressible in a way a consumer cannot read as a plain approval.

## Decision

**A strategy produces a `TradeIntent`. `atlas.risk` returns a `RiskVerdict`
about it. `atlas.execution` turns an approved verdict into an `OrderRequest`.
Both contracts live in `atlas.risk`.**

```
TradeIntent ──▶ atlas.risk ──▶ RiskVerdict ──▶ atlas.execution ──▶ OrderRequest ──▶ broker
```

### Risk judges an intent; it never builds an order

`atlas.risk` neither imports, constructs nor re-exports `OrderRequest`, and
names no order type and no working price. How an order is *presented to a venue*
— market or limit, at what price, with what filling policy — is execution's
question. A package that both sized a position and chose how to route it would
be the coupling the overview forbids when it gives execution "order lifecycle,
routing, fills" and denies it the power to "size a position": the same table
denies risk the converse.

This is asserted structurally rather than trusted.
`tests/unit/risk/test_risk_boundary.py` walks the AST of every risk module and
fails if any of `OrderRequest`, `OrderType`, `OrderStatus`, `BrokerAdapter`,
`place_order`, `modify_order`, `cancel_order` or `close_position` is referenced,
and separately asserts that none of them is reachable through the package's
exports.

### A `TradeIntent` is a recommendation, and carries nothing else

Five fields: `symbol`, `side`, `requested_volume`, `stop_loss`, `take_profit`.
That is what risk needs in order to judge one — the instrument, the direction,
the size being asked for, and the levels that determine how much of the account
is at stake.

`requested_volume` is named for the ask rather than for the outcome. The name is
the point: a field called `volume` on an intent and a field called `volume` on
an order invite a consumer to move the number across, which is exactly the
mistake a reduced approval must not permit.

What is absent is absent by decision, and
`tests/unit/risk/test_trade_intent.py` asserts each absence by name so that
adding one is a visible act rather than a plausible edit. An order type or a
working price would make the intent an instruction rather than a
recommendation. An `intent_id` presumes an answer to who mints identifiers and
whether they survive a restart, which belongs to an audit trail that does not
exist yet. A `created_at` would require a clock injected into whatever builds an
intent, and nothing in the contract needs to know when it was built.

### A `RiskVerdict` has two states, and the number carries the nuance

`VerdictStatus` is exactly `APPROVED` and `REJECTED`. A reduced-size approval is
`APPROVED` with an `approved_volume` below the requested one — not a third
status.

A `REDUCED` member would force every consumer to handle two spellings of "yes",
and the first one to handle only the first spelling is a position sized off the
requested volume. The failure is silent, correct-looking in every test that does
not reduce, and wrong only in the case the status was introduced for. Two states
means a consumer that reads `is_approved` and then `approved_volume` is right in
both cases without knowing reduction exists.

`approved_volume` is the number execution must use. It is `None` on a rejection,
which is what makes bypassing the status uninteresting rather than merely
forbidden: a consumer that ignores `status` and reaches for the volume of a
rejected verdict gets nothing to trade.

### Risk may reduce; it may never enlarge

A model validator refuses an `approved_volume` greater than
`intent.requested_volume`. Risk exists to bound exposure, and a boundary that
can return a larger number than it was given is not one — it is a second,
unreviewed sizing authority. Equality is permitted: full approval is the common
case.

The verdict carries the whole intent rather than a reference to one, so
"approved for less than was asked" is a comparison inside a single object rather
than a join two callers might perform differently, or forget. Both models are
frozen, so there is nothing to keep in sync.

### The primitives are the broker's

`SymbolName`, `OrderSide`, `Price` and `Volume` are imported from
`atlas.broker`, not redefined. This is the reason `atlas.broker.types` gives for
its own aliases: two definitions of one concept "would create two rules for one
concept and guarantee they diverge". A risk-local `Volume` that permitted zero,
or a `Price` that permitted a negative, would be a boundary that disagreed with
the port it protects — and it would disagree at the moment of translation, where
nobody is looking.

This creates one new edge, `atlas.risk → atlas.broker`, in the permitted
direction. It is the second edge between feature packages in the graph, after
`atlas.broker → atlas.common`. The boundary test enumerates the permitted set
and asserts the edge did not become several, and asserts separately that
`atlas.broker` still contains no import of `atlas.risk`, because the cheapest
way to break a layered graph is to make a downward edge quietly bidirectional.

### The contracts live in `atlas.risk`

A type belongs to the component that owes the guarantee. Risk owes the verdict,
so risk owns both the question and the answer, and `strategy` and `execution`
each depend on the boundary rather than on each other. Putting them in
`atlas.common` would make the dependency-free package encode a domain rule,
which its own row in the responsibilities table forbids. Putting them in
`atlas.events` would make a message envelope the home of a decision contract and
would couple the boundary to a transport that has not been designed.

### Rejection reasons are a closed vocabulary

Four members — `EXPOSURE_LIMIT`, `DRAWDOWN_LIMIT`, `CORRELATION_CAP`,
`KILL_SWITCH` — one for each control `atlas.risk` is declared to own. None is
implemented. Naming them here is what makes a refusal auditable rather than a
free-text string every caller parses differently; `detail` carries the prose,
and is never a substitute for a reason.

A new control adds a member in the task that implements it. Inventing one ahead
of the control it names would put a value in the audit trail that nothing can
produce.

### Recommendation-first, and the half of it that is not yet provable

The invariant this ADR serves has two halves: risk cannot be bypassed, and
execution acts only on approved output. `atlas.strategy` and `atlas.execution`
are both still empty stubs. There is no producer and no consumer, so the
behavioural half is not demonstrable today and this task does not claim it. What
is asserted now is structural — risk exposes no path to an order, and an
approved volume exists nowhere except on an approved verdict — and
`tests/unit/risk/test_risk_boundary.py` records that limitation in its own
docstring rather than leaving a reader to infer the coverage is wider than it
is.

## Consequences

### Guaranteed

- **A verdict cannot contradict itself.** Six validation rules, each asserted
  twice — once with the field that breaks it and once with the field that
  satisfies it, because a rule nobody can satisfy is not a boundary but an
  outage.
- **An approval never exceeds the request.** Enforced at construction, so an
  over-sized verdict cannot be built, logged, persisted or transported.
- **A rejection carries no tradeable number.** `approved_volume` is `None` and
  the validator refuses to let it be anything else.
- **Risk cannot reach an order.** Asserted by AST scan over every risk module,
  over the package's exports, and over the fields of both contracts.
- **The scanners can fail.** Six liveness tests assert that the import rule
  fires on a forbidden import, that the name scan finds real identifiers and
  ignores docstring prose, and that risk source was discovered at all — a scan
  that inspects nothing passes everything.
- **A decision is immutable.** Both models are frozen and forbid unknown
  fields, so a misspelled key is an error rather than a silently missing value.

### Not guaranteed, deliberately

- **Nothing produces an intent.** `atlas.strategy` is still a stub.
- **Nothing consumes a verdict.** `atlas.execution` is still a stub, so "only
  approved intents are executed" is stated and not yet enforced by a test.
- **Nothing reaches a verdict.** No sizing algorithm, no exposure limit, no
  drawdown control, no correlation cap, no kill switch. Constructing an
  `APPROVED` verdict does not make it true; this task states what a well-formed
  decision looks like, not how one is arrived at.
- **No account or portfolio state.** The state a real decision is made against
  has no contract yet, and inventing one here would fix its shape before the
  controls that read it exist.
- **Nothing is persisted or transported.** Both models serialise, which is why
  the enums are `StrEnum` with values equal to their names, but no store and no
  envelope is defined.

### Costs

- **A second edge into `atlas.broker`.** Reusing the port's primitives means
  `atlas.risk` cannot be understood without it. The alternative was divergence,
  and the edge runs downward.
- **`atlas.strategy` will depend on `atlas.broker` types transitively.** A
  strategy that builds a `TradeIntent` reaches `SymbolName`, `OrderSide`,
  `Price` and `Volume` through its field types, and the strategy stub says
  "nothing here may reach a broker directly". This is accepted, and the wording
  survives it: a transitive type dependency is not a call path. Strategy depends
  on the vocabulary the port defines, not on the port — it still cannot obtain a
  `BrokerAdapter`, cannot construct an `OrderRequest`, and has no route to place
  anything. The alternative is risk-local primitives, which is the divergence
  this record rejects two sections above; the cost of avoiding that divergence
  is that the type names a strategy handles are the broker's names.
- **A verdict duplicates the intent it judges.** Carrying the whole object
  rather than a reference costs a copy, and buys a self-contained decision that
  needs no lookup to interpret.
- **Reduction is a comparison, not a state.** A consumer that wants to log
  "approved smaller" reads `is_reduced` rather than matching on a status. That
  is a property to know about, and it is the price of there being one spelling
  of "yes".
- **`RiskVerdict` states rules the objects it judges cannot enforce alone.**
  The four validator rules live on the verdict rather than in the type system,
  because "approved implies a volume" is a relationship between two fields.

## Alternatives considered

**A strategy emits an `OrderRequest`; risk validates it.** Rejected, and it is
the alternative the rest follow from. It makes risk advisory: the object exists,
its size is chosen, and risk can only veto a decision already made. It also
forces every strategy to answer execution's questions — order type, working
price, filling policy — which is how routing knowledge ends up in the strategy
layer.

**A third `REDUCED` status.** Rejected. It reads as more explicit and is
strictly more dangerous: every consumer must handle two spellings of "yes", and
the one that handles only `APPROVED` trades the requested size in exactly the
case the status was added to make visible. The reduction is already legible from
the number, and `is_reduced` names it without splitting the state.

**A boolean `approved: bool` instead of an enum.** Rejected. It has no room for
the reason a refusal happened, and the audit trail the architecture requires
needs to record which control fired, not merely that one did.

**Free-text rejection reasons.** Rejected. A string is unqueryable, unstable
across call sites, and cannot be asserted on. The closed enum plus an optional
`detail` gives both — a machine reads `reason`, a person reads `detail`.

**Contracts in `atlas.common`.** Rejected. `common` is dependency-free and
forbidden by its own row in the responsibilities table from encoding domain
rules. A trade intent is nothing but a domain rule.

**Contracts in `atlas.events`.** Rejected. It would make the decision boundary
depend on a transport that does not exist yet, and conflates *what a decision
is* with *how it is delivered*. If verdicts are later published, an event
envelope will carry one; it will not become one.

**A generic `Result`/`Decision` type in `atlas.common`, parameterised over the
payload.** Rejected. It is the shape that fits every domain and constrains none:
`Result[Volume]` cannot express "an approved volume must not exceed the
requested one", which is the single rule this contract exists to enforce. The
generality would have to be paid back with a validator per use anyway.

**Risk-local `Price` and `Volume` aliases, to avoid the edge into
`atlas.broker`.** Rejected. Two definitions of one concept diverge — the port's
own module says so about its own aliases — and they would diverge at the
translation boundary, which is where a disagreement is least visible and most
expensive.

**Risk constructs the `OrderRequest` itself, since it knows the approved
size.** Rejected. It is the shortest path from a verdict to a venue and it puts
sizing and routing in one package, which the responsibilities table separates
deliberately. The approved volume is on the verdict; execution needs no help
reading it.

**An `intent_id` now, so verdicts can be correlated later.** Rejected as
premature. Who mints identifiers, whether they survive a restart, and whether
they are the audit trail's key are questions the audit package will answer, and
a field invented now would be a second answer competing with it. The verdict
carries the whole intent, so correlation needs no key today.

**Let `strategy` own `TradeIntent` and `risk` own `RiskVerdict`.** Rejected. It
splits one boundary across two packages and makes `atlas.risk` import
`atlas.strategy` — an upward edge, and the exact inversion the boundary exists
to prevent.
