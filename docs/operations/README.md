# Operations

How Atlas is run: environments, deployment, observability, backup and the
controls that stop it trading.

Runbooks answer "something is wrong, what do I do". This section answers "how
does this system operate normally".

## Environments

| Environment | `ATLAS_ENV` | Account | Purpose |
|---|---|---|---|
| Development | `development` | none | Local work. Debug logging, console format, small pools. |
| Demo | `demo` | non-funded | Production topology against a demo account. Configured like production in every respect except the money. |
| Production | `production` | funded | Live trading. |

Demo exists to make the step to production boring. If demo is configured like
development, it validates nothing about production.

## Production invariants

`AtlasSettings` refuses to start a production process unless:

- `debug` is false,
- `logging.format` is `json`,
- `postgres.password` is supplied through the environment.

All violations are reported in one message. These are enforced in
`atlas.config.settings`, not by convention, and are covered by tests.

## Configuration and secrets

- Structure lives in `config/`, secrets live in the environment.
- No file in this repository may contain a credential; a contract test asserts
  it for every committed TOML layer.
- Credentials are typed `SecretStr` and stay out of `repr`, logs and tracebacks.
- Anything logging a connection string uses `safe_dsn` / `safe_url`.
- `ATLAS_ENV` must be exported into the process environment.

## Deployment

Containerised. The image is a multi-stage build running as a non-root user
(uid 1000) with only the virtual environment and application source in the
runtime layer. The image defaults `ATLAS_ENV=production` on purpose: an
unconfigured container fails its own invariant checks rather than starting in a
permissive mode.

Target platform and rollout procedure are recorded in
`infrastructure/deployment/` once chosen.

## Observability

Not yet implemented. `infrastructure/monitoring/` records what is planned and
what each signal is for. The first observable behaviour is the `atlas-core`
startup record, which is machine-readable JSON on stdout by design.

## Backup and recovery

| Store | Contains | Loss tolerance |
|---|---|---|
| PostgreSQL | Orders, positions, risk verdicts, audit trail | None — this is the system of record |
| Redis | Cache, event transport | Restart-survivable via AOF; not a source of truth |
| DuckDB | Historical bars, research artefacts | Rebuildable from source data, at a cost in time |

Backup schedules and restore drills belong in this directory once there is
production data. **A restore procedure that has never been executed is a
hypothesis, not a backup.**

## Operational controls

The kill switches, drawdown halts and reconciliation procedures live in
`atlas.risk` and `atlas.execution`. They are documented here as they are built.
The constraint they exist to serve is in
[the architecture overview](../architecture/overview.md): risk is on the
critical path of every order and cannot be routed around.
