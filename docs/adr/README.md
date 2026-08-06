# Architecture Decision Records

An ADR captures one architecturally significant decision: what was decided, the
forces that led there, and what it costs. ADRs are immutable once accepted — a
decision that changes is superseded by a new record, never edited in place, so
the history of the system's reasoning stays intact.

## Index

| ID | Title | Status |
|---|---|---|
| [0001](0001-record-architecture-decisions.md) | Record architecture decisions | Accepted |
| [0002](0002-monorepo-with-namespace-packages.md) | Monorepo with PEP 420 namespace packages | Accepted |
| [0003](0003-layered-configuration.md) | Layered TOML configuration with environment overlay | Accepted |
| [0004](0004-strict-typing-and-linting.md) | Strict typing and linting from the first commit | Accepted |
| [0005](0005-polyglot-persistence.md) | PostgreSQL, Redis and DuckDB for three distinct jobs | Accepted |
| [0006](0006-mock-adapter-simulates-bookkeeping-not-price.md) | The mock adapter simulates bookkeeping, not price | Accepted |
| [0007](0007-two-locks-in-the-base-adapter.md) | Two locks in the base adapter, and none below it | Accepted |

## Writing one

Copy the structure of ADR 0001: **Status**, **Context**, **Decision**,
**Consequences**, **Alternatives considered**. Number sequentially. Keep it to
a page — an ADR nobody reads protects nothing.

Statuses: `Proposed`, `Accepted`, `Superseded by ADR-NNNN`, `Deprecated`.
