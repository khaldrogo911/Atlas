# Project Atlas

**Institutional-grade, AI-assisted quantitative Forex trading platform.**

`v0.2.0-alpha` · Python 3.12+ · MIT licensed

---

## Project Overview

Atlas is a trading platform, not a trading script. It is built on the premise
that in systematic trading the hard part is not the signal — it is everything
around the signal: data integrity, reproducibility, risk enforcement that
cannot be bypassed, execution that survives a broker disconnect, and an audit
trail that can explain any action taken months later.

The repository is therefore organised around **enforceable boundaries**. Each
package owns one responsibility and declares what it is not allowed to do.
Strategies emit intents, never orders. Risk is on the critical path of every
order and cannot be routed around. AI output is advisory input to a decision,
never the decision. Offline learning code is not importable from the live path.
These are architectural constraints, and structural tests in `tests/contract/`
exist to keep them true as the codebase grows.

### Status

Last completed: **ATLAS-TASK-0012 — the strategy boundary**. See
[`docs/ROADMAP.md`](docs/ROADMAP.md) for the full task tracker.

The engineering foundation is complete and enforced: dependency management,
strict typing, linting, formatting, testing, containerisation, layered
configuration and CI.

The broker boundary is built. `atlas.broker` holds the domain models
(TASK-0002), the vendor-neutral `BrokerAdapter` port of 31 methods
(TASK-0003), its first real implementation against MetaTrader 5 (TASK-0004),
which is demo-account only and implements 24 of the 31, and the `BrokerError`
hierarchy every adapter translates its venue's failures into (TASK-0005). The
remaining seven methods raise `NotImplementedError` naming the MT5 capability
that is missing. `MetaTrader5` is an optional Windows-marked extra imported
inside one function, so nothing outside `atlas.broker.mt5` depends on it.

The port now has a second implementation: `atlas.broker.mock` (TASK-0006), an
in-memory venue and a deterministic adapter satisfying all 31 methods,
including the seven MetaTrader 5 cannot. It is what tests hold instead of a
mocked interface, and it is what demonstrates the contract is not shaped around
one vendor. It simulates a venue's bookkeeping and deliberately not its market —
see [ADR-0006](docs/adr/0006-mock-adapter-simulates-bookkeeping-not-price.md).

Both adapters sit on `BaseBrokerAdapter` (TASK-0007), which owns the session
bookkeeping, the lifecycle and the two locks that make an adapter safe to hold
from a strategy thread, a risk thread and a supervisor at once (TASK-0008) —
see [ADR-0007](docs/adr/0007-two-locks-in-the-base-adapter.md). A supervisor is
never blocked by an in-flight connect, which is the one moment it exists for.

`atlas.common` has its first contents: the `Clock` port (TASK-0009), injected
into the base so that a heartbeat's age is measured on a monotonic reading rather
than a wall clock that an NTP step can move in either direction — see
[ADR-0008](docs/adr/0008-time-is-injected.md). It is also what lets a test for a
one-hour timeout advance an hour and assert an exact `timedelta` instead of
waiting one.

`RetryPolicy` joined it (TASK-0010): a frozen value describing how many attempts
and how long between, executed against the injected clock and wired into
`BaseBrokerAdapter`, so `connect` and `reconnect` survive a dropped socket
without either adapter writing a loop. The default is one attempt — retrying is
opted into, because the only symptom of a wrongly retried call is that it took
longer to fail. Which failures are worth another go is read off the exception
hierarchy rather than from a list, so a refused credential still fails at the
first attempt — see
[ADR-0009](docs/adr/0009-retry-is-a-value-and-the-waiting-is-the-clocks.md).

`atlas.risk` has its first contents (TASK-0011): `TradeIntent`, `RiskVerdict`,
`VerdictStatus` and `RejectionReason`. The architecture's first invariant — an
intent becomes an order only by passing through risk — had been prose for ten
tasks, with nothing saying what an intent *was* or what passing through risk
returned. A verdict is risk's answer about an intent and not an order: risk may
approve a smaller volume than was requested and may never enlarge one, and only
`atlas.execution` turns an approved verdict into an `OrderRequest`. The
contracts are stated in the port's own `SymbolName`, `OrderSide`, `Price` and
`Volume` rather than in risk-local copies, because two definitions of one
concept diverge — see
[ADR-0010](docs/adr/0010-the-risk-boundary-is-a-verdict-on-an-intent.md).

`atlas.strategy` has its first contents (TASK-0012): `Strategy`, a
runtime-checkable protocol whose one method is
`propose(observation, /) -> TradeIntent | None`. A strategy is the only thing
in Atlas that originates a `TradeIntent`, and returning one or returning `None`
is the whole of its authority. `atlas.risk` is the one `atlas` package a module
there imports — a module that *constructed* an intent would have to name the
port's four primitives, so no module in the package constructs one.
`ConstantStrategy` is an inert reference implementation that answers with the
intent it was handed, whatever it is shown: it reads no market data, performs
no I/O, holds no clock and draws no randomness, it is not exported from
`atlas.strategy`, and it makes no claim about profitability. There is no
lifecycle, registry, engine or scheduling — the rest of what the package's
responsibility names.

**No trading logic exists yet.** The two boundaries above are contracts, not
controls: there is no sizing rule, no exposure limit, no drawdown control, no
kill switch and no real strategy. `atlas.execution` is still an empty stub, so
nothing consumes a verdict. Every package below other than those named above is
an importable unit with a documented responsibility and no implementation, by
design. `atlas.config` is the exception — configuration *is* foundation, so it
is fully implemented and tested.

---

## Architecture Summary

Atlas is a modular monolith deployed as a small number of processes. Packages
are separately versionable libraries; apps are deployable processes that
compose them.

### Flow

```
                       ┌──────────────┐
   market data ───────▶│    market    │  ingestion, normalisation, integrity
                       └──────┬───────┘
                              ▼
                       ┌──────────────┐
                       │   features   │  deterministic, no look-ahead
                       └──────┬───────┘
                              ▼
                    ┌─────────┴─────────┐
                    ▼                   ▼
             ┌────────────┐      ┌────────────┐
             │   regime   │      │     ai     │  advisory only
             └──────┬─────┘      └──────┬─────┘
                    └─────────┬─────────┘
                              ▼
                       ┌──────────────┐
                       │   strategy   │  emits trade INTENTS
                       └──────┬───────┘
                              ▼
                       ┌──────────────┐
                       │     risk     │  authoritative, non-bypassable
                       └──────┬───────┘
                              ▼
                       ┌──────────────┐      ┌────────────┐
                       │  execution   │─────▶│   broker   │  vendor-neutral port
                       └──────┬───────┘      └────────────┘
                              ▼
        ┌─────────────────────┼─────────────────────┐
        ▼                     ▼                     ▼
  ┌───────────┐        ┌────────────┐        ┌──────────────┐
  │   audit   │        │ analytics  │        │ notification │
  └───────────┘        └────────────┘        └──────────────┘

  events ── asynchronous message bus connecting all of the above
  common ── dependency-free primitives, importable from anywhere
  learning ─ offline only; never imported by the live path
```

### Load-bearing decisions

| Decision | Rationale | ADR |
|---|---|---|
| Monorepo, one lockfile | Every package is upgraded together; no version skew between components that must agree on an event schema | [0002](docs/adr/0002-monorepo-with-namespace-packages.md) |
| PEP 420 namespace package `atlas.*` | Packages split into independent distributions later without a single import changing | [0002](docs/adr/0002-monorepo-with-namespace-packages.md) |
| Layered TOML + environment overlay | Structure in version control, secrets in the environment, one precedence order that is written down and tested | [0003](docs/adr/0003-layered-configuration.md) |
| Strict MyPy from commit one | Retrofitting types onto a trading system is a rewrite; the cost is only bearable if paid from the start | [0004](docs/adr/0004-strict-typing-and-linting.md) |
| Fail-fast configuration | A misconfigured trading process must not start, rather than start and act on wrong values | [0003](docs/adr/0003-layered-configuration.md) |

Full architectural documentation lives in [`docs/architecture/`](docs/architecture/overview.md);
decision records in [`docs/adr/`](docs/adr/README.md).

---

## Technology Stack

| Concern | Choice |
|---|---|
| Language | Python 3.12+ (validated on 3.12–3.14) |
| Dependencies | Poetry 2.x, committed `poetry.lock` |
| Validation & config | Pydantic v2, pydantic-settings |
| System of record | PostgreSQL 16 |
| Cache & event transport | Redis 7 |
| Analytical store | DuckDB |
| Linting & imports | Ruff |
| Formatting | Black |
| Static typing | MyPy (`strict = True`) |
| Testing | Pytest |
| Pre-commit | pre-commit |
| Containers | Docker, Docker Compose |
| CI | GitHub Actions |

---

## Repository Layout

```
atlas/
├── apps/                        deployable processes
│   ├── atlas-core/              the trading service
│   ├── dashboard/               operator-facing interface
│   └── research/                backtesting and experiment workbench
│
├── packages/                    libraries, one responsibility each
│   ├── common/                  dependency-free primitives  (clock, retry)
│   ├── config/                  layered configuration  (implemented)
│   ├── events/                  event contracts and message bus
│   ├── broker/                  vendor-neutral broker port
│   ├── market/                  market data ingestion and storage
│   ├── features/                deterministic feature computation
│   ├── regime/                  market regime classification
│   ├── strategy/                strategy contracts and engine
│   ├── ai/                      model serving, AI-assisted reasoning
│   ├── risk/                    risk engine, limits, capital allocation
│   ├── execution/               order lifecycle and routing
│   ├── notification/            outbound alerting
│   ├── analytics/               performance measurement
│   ├── learning/                offline training and model registry
│   └── audit/                   immutable audit trail
│
├── config/                      layered TOML: default, development, demo, production
├── docs/                        adr, architecture, api, runbooks, operations
├── infrastructure/              docker, database, monitoring, deployment
├── scripts/                     developer and operator entrypoints
├── tests/                       unit, integration, contract, e2e
└── .github/workflows/           CI pipeline
```

Each package is a source root: `packages/<name>/src/atlas/<name>/`. There is no
`__init__.py` at the `atlas/` level — that is what makes `atlas` a PEP 420
namespace shared across every source root.

---

## Development Setup

### Prerequisites

- Python 3.12, 3.13 or 3.14
- Poetry 2.0+
- Docker and Docker Compose (only for the containerised workflow)

### Install

```bash
git clone <repository-url> atlas
cd atlas

poetry install --with dev,test                      # add --with docs for MkDocs

cp .env.example .env                                # then edit it
poetry run pre-commit install
```

`poetry install` links every package in `packages/` and `apps/` in editable
mode, so `import atlas.config` resolves without a build step. The committed
`poetry.toml` places the virtual environment at `./.venv`, so every contributor
and every editor finds the interpreter in the same place.

### Quality gate

Run the exact checks CI runs, in the same order:

```bash
scripts/quality.sh          # macOS / Linux
scripts\quality.ps1         # Windows
```

Or individually:

```bash
poetry run ruff check .
poetry run black --check .
poetry run mypy .
poetry run pytest
```

---

## Running Locally

Start the datastores, then run the core service:

```bash
docker compose up -d postgres redis
poetry run atlas-core
```

`atlas-core` resolves configuration from every layer, enforces the active
environment's invariants, writes a JSON startup record to stdout, and exits `0`.
It exits `2` with a diagnostic on stderr if configuration is invalid. Until the
trading pipeline exists, this is the whole of the core service, and it is
genuinely useful: it is the fastest way to prove a deployment's configuration
resolves the way you think it does.

```bash
ATLAS_ENV=demo poetry run atlas-core        # check the demo layer
python -m atlas.apps.core                   # equivalent, without the script shim
```

`ATLAS_ENV` must be exported into the process environment — it is read *before*
the settings model is built, so setting it only in `.env` will not select the
configuration layer.

---

## Testing

```bash
poetry run pytest                       # everything runnable without services
poetry run pytest -m unit               # isolated, no I/O
poetry run pytest -m contract           # repository structural invariants
poetry run pytest --cov --cov-report=term-missing
```

| Suite | Directory | Requires |
|---|---|---|
| `unit` | `tests/unit/` | nothing |
| `contract` | `tests/contract/` | nothing |
| `integration` | `tests/integration/` | live PostgreSQL, Redis, DuckDB |
| `e2e` | `tests/e2e/` | a fully deployed stack |

`tests/integration/` and `tests/e2e/` are established but empty: there are no
services to integrate against yet. They contain no skipped placeholder tests —
a suite that always skips reports green while testing nothing, which is worse
than an empty directory.

Markers are declared in `pytest.ini` and enforced with `--strict-markers`; an
undeclared marker fails the run rather than silently doing nothing.

---

## Docker

```bash
docker compose config          # validate the compose file
docker compose build
docker compose up -d           # postgres + redis + a core config self-check
docker compose logs -f atlas-core
docker compose down -v         # -v also drops the data volumes
```

Services:

| Service | Image | Notes |
|---|---|---|
| `postgres` | `postgres:16-alpine` | healthcheck via `pg_isready`, named volume, init SQL in `infrastructure/database/init/` |
| `redis` | `redis:7-alpine` | healthcheck via `redis-cli ping`, AOF persistence, named volume |
| `atlas-core` | built from `Dockerfile` | waits for both datastores to report healthy |

`atlas-core` uses `restart: "no"` deliberately. It currently performs a
configuration self-check and exits `0`; a restart policy that resurrects a
cleanly-exited container would produce an infinite loop. It becomes
`unless-stopped` when the service acquires a run loop.

The image is a multi-stage build: dependencies are resolved in a builder stage
and only the virtual environment and application source are copied into a slim
runtime stage, which runs as a non-root user.

---

## Contribution Guidelines

### Branching and commits

- Branch from `main`: `feat/<scope>`, `fix/<scope>`, `chore/<scope>`.
- [Conventional Commits](https://www.conventionalcommits.org/): `feat(risk): add per-instrument exposure cap`.
- Reference the task identifier where one applies, e.g. `ATLAS-TASK-0001`.

### Definition of done

A change is complete when all of the following hold:

1. `ruff check .` is clean.
2. `black --check .` is clean.
3. `mypy .` is clean — no new `# type: ignore` without a comment justifying it.
4. `pytest` passes, and new behaviour is covered by a test that can actually fail.
5. Public functions and classes carry Google-style docstrings.
6. Any architectural decision is recorded as an ADR in `docs/adr/`.
7. `poetry.lock` is committed alongside any dependency change.

### Boundaries

The package boundaries in the architecture section are contracts, not
suggestions. If a change appears to require crossing one — a strategy reaching
for a broker, an AI module writing an order, live code importing `learning` —
that is a design problem to resolve, not a boundary to widen. Raise it before
implementing.

### Pre-commit

```bash
poetry run pre-commit install
poetry run pre-commit run --all-files
```

The hooks are the same tools CI runs, so a clean pre-commit run means a clean
pipeline.

---

## License

MIT — see [LICENSE](LICENSE).
