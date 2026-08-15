# Architecture Overview

> **Status at ATLAS-TASK-0024.** This document describes the intended
> architecture and the boundaries the repository is built to enforce. Three
> packages hold implementation: `atlas.config` in full, `atlas.broker` (domain
> models, the `BrokerAdapter` port, two adapters, the exception hierarchy) and
> `atlas.common` (clock, retry). `atlas.risk` holds its two boundary contracts
> and one of the four controls its responsibility names — a
> portfolio margin-utilisation limit — and none of the sizing, drawdown
> control or kill switches beside it. `atlas.strategy` holds the
> contract a strategy satisfies and an inert reference implementation of it, and
> none of the lifecycle, registry or engine its responsibility names.
> `atlas.execution` holds one thing — the translation of an approved
> `RiskVerdict` into an `OrderRequest` — and none of the routing, fills,
> reconciliation or idempotent retry its responsibility also names. Every other
> package remains an empty, importable unit with a declared responsibility. Where
> this document describes behaviour, read it as the contract a later task must
> satisfy, not as a description of code that exists.
>
> Which tasks are complete is recorded in [the roadmap](../ROADMAP.md), and that
> record is the authoritative one. Where this banner and the roadmap disagree,
> the roadmap is correct.

## Shape

Atlas is a **modular monolith**: strong internal boundaries, deployed as a
small number of processes. Distributed systems buy independent scaling at the
cost of partial failure and eventual consistency. A trading platform of this
size needs neither, and can do without both.

Boundaries are enforced three ways: directory structure makes a violation
visible in review, the import graph makes it mechanical to detect, and
`tests/contract/` asserts the structural invariants that make the namespace
work at all.

## Data flow

```
market ──▶ features ──▶ regime ─┐
                                ├──▶ strategy ──▶ risk ──▶ execution ──▶ broker
                        ai ─────┘                                          │
                                                                           ▼
                                              audit ◀── analytics ◀── notification
```

`events` carries messages between these stages. `common` is dependency-free and
importable anywhere. `learning` runs offline and is never imported by the live
path.

`common` holds two things so far, and they are the first exercise of that rule.
`atlas.common.clock` is a `Clock` port with a wall hand, a monotonic hand and a
`sleep`, a `SystemClock` that reads the host and a `ManualClock` for tests.
`atlas.common.retry` is a frozen `RetryPolicy` and a `retry_call` that executes
one, which waits on a clock it is given and takes the transient exception types
as a parameter — so it names no venue, no domain and no failure of its own.
Both are here rather than in `atlas.broker` for the same reason: market data,
execution and notification will each want to retry something against a clock,
and a definition in a feature package would have to be imported upward, which
the graph forbids.

Six edges between feature packages exist in the graph today, and every one of
them runs downward: `atlas.broker` imports `atlas.common`, `atlas.risk` imports
`atlas.broker` and `atlas.config`, `atlas.strategy` imports `atlas.risk`, and
`atlas.execution` imports `atlas.risk` and `atlas.broker`.

`atlas.broker` imports `atlas.common`;
`tests/unit/broker/test_adapter_contract.py` asserts both halves — that
`atlas.broker` may reach `atlas.common`, and that it still may not reach anything
above the port. See [ADR 0008](../adr/0008-time-is-injected.md) and
[ADR 0009](../adr/0009-retry-is-a-value-and-the-waiting-is-the-clocks.md).

`atlas.risk` imports `atlas.broker`, added by ATLAS-TASK-0011. The risk
contracts are stated in the port's own `SymbolName`, `OrderSide`, `Price` and
`Volume` rather than in risk-local copies, because two definitions of one
concept diverge — and would diverge exactly at the boundary risk exists to
hold. `tests/unit/risk/test_risk_boundary.py` asserts that the imports stay
within the permitted set — `atlas.broker`, and `atlas.config` for the single
name `get_settings`, added by ATLAS-TASK-0017 — that no risk module reaches a
credential-bearing setting, that no risk module can reach an order, and that
`atlas.broker` still contains no import of `atlas.risk`. See
[ADR 0010](../adr/0010-the-risk-boundary-is-a-verdict-on-an-intent.md).

`atlas.strategy` imports `atlas.risk`, added by ATLAS-TASK-0012, and imports
nothing else. This is the edge the data flow leads with, and it exists now: a
`Strategy` is shown an observation and answers with a `TradeIntent` or with
`None`. It brings no second edge with it. A module that *constructed* an intent
would need `SymbolName`, `OrderSide`, `Price` and `Volume` from `atlas.broker`,
because `mypy --strict` with `init_typed` will not accept a bare string where an
`OrderSide` belongs — so no module in the package constructs one. The contract
names `TradeIntent` in an annotation, and the reference implementation is handed
a finished intent by whoever wants one.
`tests/unit/strategy/test_strategy_boundary.py` asserts that the package takes
no name from the port at all, that the eight execution symbols appear nowhere in
it, and that `atlas.risk` still contains no import of `atlas.strategy`.

`atlas.execution` imports `atlas.risk`, added by ATLAS-TASK-0014, which gave the
verdict its consumer. `build_order_request` takes a `RiskVerdict` and an
`ExecutionPolicy` the caller supplies: an approved verdict becomes an
`OrderRequest` carrying the volume risk approved — never the volume the intent
requested — and a rejected verdict becomes `None`. `None` is the ordinary answer
to a refusal rather than an error, because risk declining a trade is risk
working and is not a broker failure. Nothing in the package stores a policy,
reads one from configuration or defaults one; a policy chosen here would be a
trading decision written in the package least likely to be reviewed as one.

`atlas.execution` imports `atlas.broker` as well, added by the same task, and
that edge is a type dependency rather than a call path. The package names
`OrderRequest`, `OrderType` and `Price` instead of restating them, for the
reason the port gives for its own aliases: two definitions of one concept
guarantee divergence, and a translation layer is exactly where two such rules
would disagree unobserved. Nothing here obtains, constructs or invokes a
`BrokerAdapter`, and an `OrderRequest` is inert until some layer places it.
`tests/unit/execution/test_execution_boundary.py` asserts both halves by walking
the AST of every module in the package, including imports written under a
`TYPE_CHECKING` guard. See
[ADR 0011](../adr/0011-execution-builds-the-request-another-layer-owns-the-port.md).

The chain the data flow draws is not joined end to end. Nothing outside the test
suite produces a `TradeIntent` or hands one to `atlas.risk`, and although
`apps/atlas-core` owns the `BrokerAdapter` and builds one at startup from the
broker configuration it resolves, nothing yet holds that adapter afterwards and
no session is opened with it — so the request `atlas.execution` builds is,
today, received by nothing. See
[ADR 0013](../adr/0013-the-application-owns-the-adapter.md) and
[ADR 0015](../adr/0015-broker-adapter-selection.md).

## Package responsibilities

| Package | Owns | Must not |
|---|---|---|
| `common` | Primitives, identifiers, clock, retry policy, typing vocabulary | Import any other `atlas.*` package; encode domain rules |
| `config` | Layered settings, validation, secrets handling | — *(implemented)* |
| `events` | Event contracts, serialisation, message bus | Interpret events |
| `broker` | The `BrokerAdapter` port and its data contracts | Size, route or risk-check anything |
| `market` | Ingestion, normalisation, integrity, storage | Derive signals or features |
| `features` | Deterministic feature computation | Read any input timestamped after *t*; perform I/O |
| `regime` | Market state classification | Decide a trade |
| `strategy` | Strategy contracts, lifecycle, engine | Reach a broker; bypass `risk` |
| `ai` | Inference, LLM assistance, guard rails | Make a decision; substitute for a risk check |
| `risk` | Sizing, exposure limits, drawdown control, kill switches | — *(authoritative and non-bypassable)* |
| `execution` | Order lifecycle, routing, fills, reconciliation | Size a position; override a risk verdict |
| `notification` | Alert delivery, severity routing, de-duplication | Affect trading when delivery fails |
| `analytics` | Attribution, cost and slippage accounting | Write to the trading path |
| `learning` | Training, evaluation, model registry | Be imported by anything on the live path |
| `audit` | Append-only decision and order record | Mutate or delete a record |

## The invariants that matter

**1. Risk is on the critical path.** A trade intent becomes an order only by
passing through `atlas.risk`. `strategy` emits intents; `execution` acts on
approved intents. Neither can reach a broker directly. Every other safety
property depends on this one.

ATLAS-TASK-0011 gave this invariant its vocabulary: `TradeIntent` is what a
strategy would like to do, `RiskVerdict` is what risk permits, and only
`atlas.execution` turns an approved verdict into an `OrderRequest`. Risk decides;
it does not place. A reduced-size approval is an approval carrying a smaller
number, not a third answer.

ATLAS-TASK-0012 gave it a producer: a `Strategy` is the only thing in Atlas that
originates a `TradeIntent`, and its whole authority is to return one or to
return `None`. The structural half of the invariant — that neither package
exposes a path to an order — is enforced by test today; the behavioural half,
that a running pipeline routes every intent through risk, now waits on an engine
alone. ATLAS-TASK-0014 supplied the consumer `execution` was missing; what is
still absent is anything that drives a strategy, reaches a verdict and calls the
translation in sequence.

**2. AI is advisory.** `atlas.ai` produces inputs to decisions. A model output
never becomes an order without passing the same risk gate as any other intent,
and never relaxes one.

**3. Features cannot see the future.** A feature computed for time *t* may read
no input timestamped after *t*. This is the difference between a backtest that
means something and one that does not, and it is a property of the `features`
package, not of the individual strategies that consume it.

**4. The audit trail is append-only.** Every decision, model output, risk
verdict, order and configuration change is recorded with enough provenance to
reconstruct why an action was taken. Application code never mutates a record.

**5. Offline stays offline.** `learning` and `research` do not appear in the
live process's import graph.

## Processes

| App | Role | Deployment |
|---|---|---|
| `atlas-core` | Owns the event loop and runs the trading pipeline | Long-lived container |
| `dashboard` | Operator observation and authorised control | Long-lived, separately scalable |
| `research` | Backtests, datasets, experiments | Ad hoc, never alongside live |

At ATLAS-TASK-0001, `atlas-core` has no run loop. Its entrypoint today resolves
configuration, enforces the environment's invariants, builds the broker adapter
that configuration describes, emits a JSON startup record and exits — which is
why `docker-compose.yml` gives it `restart: "no"`. A run that gets that far
exits `0`; configuration it cannot resolve, or a broker section it cannot
translate, leaves stdout empty and exits `2` instead.

## Persistence

PostgreSQL is the system of record, Redis is cache and event transport, DuckDB
is the analytical store and is never on the live path. The reasoning is in
[ADR 0005](../adr/0005-polyglot-persistence.md).

## Configuration

Layered TOML overlaid by environment variables, validated by Pydantic v2, frozen
after construction, fail-fast on any violation. See
[ADR 0003](../adr/0003-layered-configuration.md) and `config/README.md`.

## Related

- [ADR index](../adr/README.md)
- [Runbooks](../runbooks/README.md)
- [Operations](../operations/README.md)
