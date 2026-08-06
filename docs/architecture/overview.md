# Architecture Overview

> **Status at ATLAS-TASK-0001.** This document describes the intended
> architecture and the boundaries the repository is built to enforce. Only
> `atlas.config` is implemented; every other package is an empty, importable
> unit with a declared responsibility. Where this document describes behaviour,
> read it as the contract a later task must satisfy, not as a description of
> code that exists.

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

`atlas.broker` imports `atlas.common`, which is still the only edge between two
feature packages in the graph today. It runs in the permitted direction, and
`tests/unit/broker/test_adapter_contract.py` asserts both halves: that
`atlas.broker` may reach `atlas.common`, and that it still may not reach anything
above the port. See [ADR 0008](../adr/0008-time-is-injected.md) and
[ADR 0009](../adr/0009-retry-is-a-value-and-the-waiting-is-the-clocks.md).

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

At ATLAS-TASK-0001, `atlas-core` has no run loop. Its entrypoint resolves
configuration, enforces the environment's invariants, emits a JSON startup
record and exits — which is why `docker-compose.yml` gives it `restart: "no"`.

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
