# ADR 0012 — Risk is handed its state and reads its own limits

**Status:** Accepted
**Date:** 2026-08-13

## Context

ADR-0010 defined what a risk decision *is* and listed five things it did not
guarantee. The third and fourth were that nothing reaches a verdict — "no sizing
algorithm, no exposure limit, no drawdown control, no correlation cap, no kill
switch" — and that there is no account or portfolio state, because "inventing one
here would fix its shape before the controls that read it exist".

That reason has now expired in the only way it could: a control is about to be
written. The first one is `EXPOSURE_LIMIT`, and its limit comes from
configuration. Both were owner decisions, and this record decides what follows
from them and nothing else.

### Why the two questions had to be answered together

Whether the broker's existing models are *sufficient* depends on which control
reads them, so the state question could not have been settled first.

An exposure control needs the open positions, the contract size that turns a
volume into a notional, and an account value to state a limit against. The port
already reports all three: `get_positions` returns `Position`, `Symbol` carries
`contract_size` and the volume constraints, and `Account` carries `balance` and
`equity`. `SymbolName` is `SymbolCode` under the name the port uses, so the
instrument on an intent and the instrument on a position are the same type, with
nothing to translate between them.

A drawdown control would not have been sufficient. `Account` is documented as "an
observation, not a ledger" and carries no start-of-day equity and no high-water
mark; a reference point over time would have had to be invented. A correlation
cap would have needed price history from `atlas.market`, which the risk boundary
forbids. Naming the control is what turns "no new state contract" into a finding
rather than a preference.

### Why the limit could not simply follow the nearest precedent

The repository already answered a structurally similar question one layer up, and
the answer does not transfer. `ExecutionPolicy` is supplied per call, and
`atlas.execution` neither stores one nor reads one from configuration, because "a
policy chosen here would be a trading decision written in the package least
likely to be reviewed as one".

That is right for presentation and wrong for a limit. A caller was always
entitled to choose market or limit; a caller is not entitled to choose how much
exposure is permitted. `docs/architecture/overview.md` gives `risk` the row
"authoritative and non-bypassable", and a limit the caller supplies is a limit
the caller can raise. Applied here, the precedent would make the second half of
that row false while leaving it written down — which is the failure mode ADR-0010
was written to prevent one level up, where a strategy that emitted an
`OrderRequest` would have made risk advisory while appearing to leave it on the
path.

## Decision

**The exposure control is handed the state it judges, and reads the limit it
judges against. It fetches neither from a broker nor from its caller.**

### State is handed in, and it stays the broker's

The producer that maps a `TradeIntent` to a `RiskVerdict` may consume
`atlas.broker`'s `Account`, `Position` and `Symbol`. They arrive as arguments.

They remain the broker's, and they remain what their own modules say they are:
observations of what a venue reported, not a ledger Atlas maintains. Nothing here
recomputes equity from balance and open profit, nets two opposing tickets into
one number, or otherwise disagrees with the venue's arithmetic — "where Atlas
disagrees with the broker's arithmetic, the broker is right".

**No account or portfolio state contract is created.** ADR-0010's fourth
non-guarantee is honoured rather than overturned: the way to avoid fixing the
shape of portfolio state before the controls that read it exist is to reuse what
the port already reports, not to invent a parallel description of it. ADR-0011's
restatement stands unchanged — the venue-reported account surface "is per-call
state read from a broker, not the portfolio-state contract ADR-0010 declined to
invent", and this record does not turn it into one either. What it does is permit
one control to be shown those observations.

The reason state is handed in rather than fetched is the same reason the risk
contracts reuse the port's primitives: two rules for one concept diverge. A risk
package that could ask a venue for an account would own a second, unreviewed
opinion about when to ask, what to do when the answer is late, and which answer
is current.

### `BrokerAdapter` remains unreachable from `atlas.risk`

This is restated, not reopened. No risk module may name `BrokerAdapter`,
`OrderRequest`, `OrderType`, `OrderStatus`, `place_order`, `modify_order`,
`cancel_order` or `close_position`, and `tests/unit/risk/test_risk_boundary.py`
fails on any of them by walking the AST of every module in the package.

Naming a model is not obtaining one. It is the distinction ADR-0011 drew for
`atlas.execution → atlas.broker`, running the other way and with a narrower
purpose: execution names three types in order to build a request, and risk names
three models in order to read one. Neither acquires a route to a venue. Risk
therefore never calls `get_account`, `get_positions`, `margin_required`,
`margin_available` or `can_trade`; whoever hands it state calls them, and that
layer does not exist yet.

### The limit is configuration, and risk reads it rather than receiving it

**`atlas.risk` may import `atlas.config`.** This is a new edge, and it is the
first from a feature package into the configuration package — until now only
`apps/core` imported it.

The exposure limit is **not a parameter of the decision**. A limit passed in is a
limit the caller chose, and `load_settings(**overrides)` means a caller who can
pass a settings object can pass any settings object. The only construction that
makes the overview's "non-bypassable" true is one in which there is no argument
to substitute: the control asks the process what it is configured to permit.

This is the deliberate widening the boundary test anticipated when it excluded
`atlas.config` "because contracts need no configuration, and widening the
permitted set must be a deliberate act in the task that needs it — the way
`atlas.common` was admitted to the port's set in ATLAS-TASK-0009". `atlas.risk`
is no longer only contracts, and the task that needs it is the one that
implements this control.

### The configuration section belongs to `atlas.config`

`AtlasSettings` gains a risk section. It is defined in `atlas.config` alongside
the others, not in `atlas.risk`.

The alternative is a cycle. If `atlas.risk` owned the limits model, `atlas.config`
would have to import it to compose the settings tree, while `atlas.risk` imports
`atlas.config` to read the resolved value — a bidirectional edge between two
packages, which is the shape ADR-0010 called "the cheapest way to break a layered
graph".

The cost is real and is accepted below: a trading-policy value now lives in the
configuration package. `atlas.config` is not forbidden this — unlike
`atlas.common`, whose row in the responsibilities table bars it from encoding
domain rules and which is why ADR-0010 refused to put the risk contracts there —
and it already encodes judgements of the same kind, refusing to start a
production process that carries no database password or logs in the wrong format.

### How a configured limit stays authoritative

Four properties the configuration package already has, and one that follows:

- **`AtlasSettings` is frozen.** ADR-0003: "Configuration cannot drift at
  runtime, which removes a class of 'it worked at startup' bugs."
- **`get_settings` resolves once per process** and takes no arguments, so there
  is one limit in a process and no seam to pass a different one through.
- **Configuration is validated at construction**, and section models use
  `extra="forbid"`, so a misspelled limit key is a start-up failure rather than a
  silently ignored line.
- **A misconfigured process refuses to start rather than starting wrong.** That
  is ADR-0003's first stated failure mode — "silent misconfiguration in a trading
  system costs money" — and it is the property this decision leans on hardest.
- Consequently the limit can only be changed by changing the process's
  environment or its `config/` tree and restarting: an operator act against a
  reviewable file, not a caller's argument.

What this does **not** claim is that the limit is unforgeable. `load_settings`
accepts overrides and is documented as being for tests and administrative
scripts; a process that builds its own settings object rather than asking
`get_settings` holds whatever it built. The guarantee is that the limit is the
process's configured limit, and that no code path *through the decision* can
substitute one.

### Absence is not permission

A process whose exposure configuration is missing or unusable must not decide as
though there were no limit. Fail-closed is the existing stance — ADR-0003 chose
refusing to start over starting wrong — and a risk control is the last place to
depart from it.

Whether that is achieved by a required field, by a conservative default, or by a
production invariant of the kind `AtlasSettings` already carries is a matter for
the task that writes it. The principle is fixed here; the mechanism is not.

### The edge is admitted for one thing

`atlas.risk` reads the settings it needs to decide. It does not become a second
route to the rest of the configuration tree, and in particular not to the
`SecretStr` credentials on the Postgres and Redis sections, which have no bearing
on whether a trade is within an exposure limit.

That limit is structural, not advisory, and belongs in
`tests/unit/risk/test_risk_boundary.py` — which today permits packages and
forbids names, and which has the allowlist mechanic it would need already written
next door, in the execution boundary's `PERMITTED_BROKER_NAMES`. Which names are
admitted is the implementing task's to enumerate. That some enumeration exists is
this record's.

### What this record does not decide

Not the exposure calculation, not the fields of the configuration section, not
any threshold, not the file layout, not when settings are resolved within the
process, and not the signature of the producer. Not sizing, not drawdown, not
correlation, not the kill switch. Not who calls the control, not who hands it
state, not who owns a `BrokerAdapter`. Nothing is persisted and nothing is
transported.

## Consequences

### Guaranteed

- **The state a decision is made against is stated.** The first control reads
  broker-reported observations, and which ones is written down rather than
  discovered by the first task that needs them.
- **Risk still cannot reach a venue.** The AST scan that already fails on
  `BrokerAdapter` and the four trading verbs is unchanged, and this record adds
  nothing that could be used to obtain one.
- **The limit cannot be supplied by a caller.** It is not an argument, so there
  is no parameter to override, and the settings object it comes from is frozen
  and resolved once.
- **Widening the risk boundary is visible.** Moving `atlas.config` out of the
  forbidden set is a diff in the test that forbids it, which is what the test's
  own comment asked for.
- **`atlas.broker` keeps its models.** No parallel `Account` or `Position`
  appears in `atlas.risk`, so there is no second description to diverge.

### Not guaranteed, deliberately

- **Nothing hands the control any state.** No layer owns a `BrokerAdapter`, so
  in a running system there is still nothing to produce an `Account` or a
  `Position` to judge. This record decides the shape of the read; it does not
  supply the reader.
- **Risk is not yet demonstrably on the path.** ADR-0010's and ADR-0011's
  standing non-guarantee is unchanged: nothing outside the test suite produces a
  `TradeIntent`, and no pipeline routes one. "Non-bypassable" is now true of the
  *limit*; it is still not demonstrable of the *boundary*.
- **The other three controls remain unimplemented.** `DRAWDOWN_LIMIT`,
  `CORRELATION_CAP` and `KILL_SWITCH` are named in the enum and produced by
  nothing, and neither the state nor the configuration this record admits is
  claimed to be sufficient for any of them. Drawdown in particular needs a
  reference point over time that no contract here carries.
- **Sizing is untouched.** A reduced approval remains expressible and remains
  unproduced.
- **Nothing is persisted or transported.** ADR-0010's fifth non-guarantee is
  unchanged. An exposure limit needs no history, which is why it could be first.

### Costs

- **A trading-policy value lives in `atlas.config`.** Anyone reading the
  configuration package to learn about infrastructure now finds a risk limit
  there. The alternative was an import cycle, and the mitigation is that this is
  where the layering, the validation and the review surface already are.
- **A sixth edge, and the first into `config`.** `atlas.risk` can no longer be
  understood without the configuration package, and a reader of the dependency
  graph will see a feature package reaching a support package for the first time.
- **`atlas.execution` acquires `atlas.config` transitively.** It imports
  `atlas.risk`, which now imports `atlas.config`. The execution boundary still
  forbids the direct edge and the reason it gives is undisturbed — a translation
  needs no configuration, and broker or venue configuration is the specific thing
  ADR-0011 refuses it. A transitive dependency is not a call path, which is the
  same accounting ADR-0010 accepted when `atlas.strategy` acquired the port's
  types through its field annotations.
- **The limit is only as good as the deployment.** Configuration is reviewable
  and frozen, but it is also editable by whoever can edit the environment. This
  moves the trust boundary from the calling code to the operator, which is where
  it belongs and is not where it was.
- **`atlas.risk` stops being only contracts.** Until now the package held two
  frozen models and no behaviour, which is why it needed no configuration at all.
  Every argument in the boundary test that begins "a contract needs no…" is now
  narrower than the package it guards.

## Alternatives considered

**The caller supplies the exposure limit per call, as `ExecutionPolicy` is
supplied.** Rejected, and it is the alternative the rest follow from. It is the
repository's own nearest precedent and it inverts the property risk exists to
have: a caller that chooses the limit can choose one that approves everything,
and the overview's "authoritative and non-bypassable" becomes a sentence rather
than a property. The precedent is right where it stands, because how an order is
*presented* was always the caller's to choose. How much exposure is *permitted*
was never.

**A composition root reads configuration and hands the resolved limits to the
control.** Rejected, though it is the closest call here. A frozen limits object
constructed from settings is indistinguishable, at the type level, from one
constructed by hand, so the guarantee would rest on there being no other
construction site — which nothing enforces. It also presumes a composition root,
and there is none: no engine, no registry, no consumer. The design would be worth
revisiting when a single wiring point exists and can be pointed at.

**A new account or portfolio state contract owned by `atlas.risk`.** Rejected on
ADR-0010's own reasoning, which has not weakened. Inventing one would fix the
shape of portfolio state on the evidence of a single control, and the control
that most needs a richer shape — drawdown — is not this one. It would also be a
contract with no producer, which is the position `TradeIntent` was in for two
tasks and is not a position to enter on purpose.

**A minimal risk-owned contract carrying only the exposure inputs.** Rejected. It
would restate fields `Position` and `Symbol` already carry, and the restatement
is the divergence ADR-0010 rejected twice — once for risk-local `Price` and
`Volume`, once when ADR-0011 rejected an `ExecutionInstruction`. Two descriptions
of one position would disagree at the point of judgement, which is where a
disagreement is least visible and most expensive.

**`atlas.risk` owns the limits model and `atlas.config` composes it.** Rejected:
it makes the edge bidirectional, which is the specific failure ADR-0010 warns
about, and it would put the configuration package in the position of importing a
feature package to know its own shape.

**The limits live in `atlas.common`.** Rejected for the reason ADR-0010 gave when
it refused to put the risk contracts there: `common` is dependency-free and
forbidden by its own row in the responsibilities table from encoding domain
rules. An exposure limit is nothing but a domain rule.

**`atlas.risk` reads environment variables directly.** Rejected. It would bypass
the layered precedence ADR-0003 established, and with it the validation, the
`extra="forbid"` typo protection and the fail-fast start-up that are the reasons
a configured limit can be trusted at all. A second way to configure Atlas is a
second precedence order, and nobody would be able to state either from memory.

**`atlas.risk` obtains a `BrokerAdapter` and reads the account itself.**
Rejected. It is the shortest path to the state a control needs and it gives risk
a venue connection, a retry policy, a staleness question and a failure mode, none
of which is a risk decision. It would also make the AST scan that has guarded
this package since ATLAS-TASK-0011 the first casualty of the first control.

**Defer the limit source until an engine exists.** Rejected. It leaves the first
control able to describe a decision and unable to reach one, which is the state
ADR-0010 already put the package in and the state this direction was chosen to
leave.
