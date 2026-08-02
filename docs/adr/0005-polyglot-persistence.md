# ADR 0005 — PostgreSQL, Redis and DuckDB for three distinct jobs

**Status:** Accepted
**Date:** 2026-08-02

## Context

Atlas has three storage workloads with genuinely different shapes:

1. **Transactional state** — orders, positions, risk verdicts, the audit trail.
   Small writes, absolute durability, must be correct under concurrency.
2. **Ephemeral coordination** — caches, locks, the event transport. Low
   latency, tolerant of loss, high churn.
3. **Analytical scans** — backtests and research over years of bar data.
   Column-oriented reads across hundreds of millions of rows.

One store forced to serve all three does at least one of them badly. The
question is whether the operational cost of three is justified.

## Decision

| Store | Workload | Why |
|---|---|---|
| **PostgreSQL 16** | System of record | Real transactions, real constraints, mature operational story. The audit trail's append-only guarantee is enforceable here. |
| **Redis 7** | Cache and event transport | Sub-millisecond, the right primitives for coordination. Configured with AOF plus an RDB rule — the event transport must survive a restart. |
| **DuckDB** | Analytical store | Column-oriented, embedded, no server. A backtest scanning years of bars is a single-process analytical query, which is precisely what DuckDB is for. |

The boundary rule: **DuckDB is never on the live trading path.** It serves
`atlas.research` and `atlas.learning`. Live components use PostgreSQL and Redis
only. In production the DuckDB layer sets `read_only = true`.

## Consequences

- Each workload runs on a store suited to it, and none is compromised to
  accommodate another.
- Three technologies to operate, back up and monitor. PostgreSQL and Redis are
  containerised with health checks and named volumes; DuckDB is a file, and its
  durability story is the durability story of the volume it sits on.
- Analytical load cannot degrade trading: it runs in a different process
  against a different store.
- Client libraries (`psycopg[binary,pool]`, `redis`, `duckdb`) are declared in
  the main dependency group from the outset so the platform's committed stack
  is visible in `pyproject.toml`. They are unused at ATLAS-TASK-0001 — the
  packages that will use them are empty by design.

## Alternatives considered

**PostgreSQL only.** Tempting, and the right call for a smaller system.
Rejected on the analytical workload: full scans over years of bars in a
row-store either run slowly or require a materialisation layer that becomes its
own maintenance burden. Using `LISTEN`/`NOTIFY` as an event bus also couples
transport availability to the system of record.

**Redis only.** Rejected: no durable transactional guarantees. An audit trail
that can be lost on failover is not an audit trail.

**TimescaleDB in place of DuckDB.** A reasonable alternative — time-series
extensions on the store already being run. Rejected for now because it puts
analytical load on the transactional server, which is the coupling this
decision exists to avoid. Worth revisiting if operating three stores proves
more expensive than the isolation is worth.

**Parquet files with an in-process query engine.** Effectively what DuckDB
provides, plus a query planner and SQL. No reason to build it by hand.
