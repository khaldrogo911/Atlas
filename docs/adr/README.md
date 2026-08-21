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
| [0008](0008-time-is-injected.md) | Time is injected, and it has two hands | Accepted |
| [0009](0009-retry-is-a-value-and-the-waiting-is-the-clocks.md) | Retrying is a value, and the waiting belongs to the clock | Accepted |
| [0010](0010-the-risk-boundary-is-a-verdict-on-an-intent.md) | The risk boundary is a verdict on an intent | Accepted |
| [0011](0011-execution-builds-the-request-another-layer-owns-the-port.md) | Execution builds the request; another layer owns the port | Accepted |
| [0012](0012-risk-is-handed-its-state-and-reads-its-own-limits.md) | Risk is handed its state and reads its own limits | Accepted |
| [0013](0013-the-application-owns-the-adapter.md) | The application owns the adapter; the port stays in the broker package | Accepted |
| [0014](0014-broker-settings-are-restated-not-imported.md) | Broker settings are restated in the configuration package, not imported | Accepted |
| [0015](0015-broker-adapter-selection.md) | The application selects `MT5BrokerAdapter` and constructs it at startup | Accepted |
| [0016](0016-unusable-broker-configuration-refuses-startup.md) | Unusable broker configuration refuses startup; the terminal path is not probed | Accepted |
| [0017](0017-startup-opens-a-session-and-closes-it.md) | Startup opens a broker session, verifies it and closes it; `atlas-core` is not a long-running process | Accepted |
| [0018](0018-the-runtime-process-shape-is-deferred.md) | The long-lived runtime and process shape is deferred pending its own decision | Accepted |
| [0019](0019-a-runtime-entrypoint-owns-the-session-and-the-pipeline.md) | `atlas-core` gains a runtime entrypoint; the runtime owns the session, the loop and the pipeline | Accepted |
| [0020](0020-the-runtime-polls-a-configured-instrument-on-a-configured-interval.md) | The runtime polls a configured instrument on a configured interval | Accepted |
| [0021](0021-filling-mode-and-deviation-are-configured-not-chosen.md) | Filling mode and deviation are configured, not chosen | Accepted |

## Writing one

Copy the structure of ADR 0001: **Status**, **Context**, **Decision**,
**Consequences**, **Alternatives considered**. Number sequentially. Keep it to
a page — an ADR nobody reads protects nothing.

Statuses: `Proposed`, `Accepted`, `Superseded by ADR-NNNN`, `Deprecated`.
