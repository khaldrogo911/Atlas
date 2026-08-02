# ADR 0003 — Layered TOML configuration with environment overlay

**Status:** Accepted
**Date:** 2026-08-02

## Context

A trading process needs configuration that differs by environment — pool sizes,
log verbosity, whether DuckDB is read-only — and credentials that must never be
committed. Two failure modes matter more than convenience:

1. A process starts with configuration the operator did not intend, and trades
   on it. Silent misconfiguration in a trading system costs money.
2. A credential reaches version control.

We also need the precedence order to be something a person can state from
memory and a test can verify, rather than something discovered by experiment.

## Decision

**Structure in files, secrets in the environment.**

`config/` holds one base layer plus one layer per environment. Within a layer,
every `*.toml` merges in filename order; layers merge `default` first, then the
environment layer. No file in `config/` may contain a credential.

Precedence, highest first:

1. Explicit arguments to `AtlasSettings(...)`
2. Process environment variables (`ATLAS_` prefix, `__` nesting delimiter)
3. `.env`
4. `config/<ATLAS_ENV>/*.toml`
5. `config/default/*.toml`
6. Field defaults

This is implemented as a custom `LayeredTomlSource` registered *below* the
environment sources in `settings_customise_sources`, so the ordering is a
property of the code rather than a convention.

**Fail fast, and fail loudly.** Settings are validated at construction:
out-of-range ports, unsatisfiable pool bounds, malformed memory limits and
unknown keys inside a section are all errors. Section models use
`extra="forbid"`, so a typo like `hozt` is a start-up failure, not a silently
ignored line. Production carries additional invariants: `debug` must be false,
logging must be JSON, and a database password must be supplied. All violations
are reported together, not one per restart.

**Credentials are `SecretStr`.** `PostgresSettings.safe_dsn` and
`RedisSettings.safe_url` exist so that anything reaching a log has a masked
form available; a test asserts the startup record contains no secret.

## Consequences

- Reviewing an environment's configuration means reading one small TOML file.
- A misconfigured process refuses to start rather than starting wrong. For
  `atlas-core` this is the entire current behaviour: exit `0` or exit `2`.
- `AtlasSettings` is frozen. Configuration cannot drift at runtime, which
  removes a class of "it worked at startup" bugs.
- **`ATLAS_ENV` must be a real process environment variable.** It selects the
  layer, and is read before the settings model exists, so a value set only in
  `.env` will not select a layer. Every deployment path in this repository
  exports it explicitly, and this is called out in `config/README.md`.
- The root `AtlasSettings` uses `extra="ignore"` rather than `forbid`, because
  `ATLAS_CONFIG_DIR` is consumed outside the model. A typo in a *top-level*
  variable name is therefore not caught; typos in section keys are.

## Alternatives considered

**Environment variables only, no files.** Rejected: twenty-plus variables per
environment with no structure, no comments, no review surface, and no way to
see what changed between two deployments.

**YAML.** Rejected: TOML parses with `tomllib` from the standard library — one
fewer dependency on the critical start-up path — and has no equivalent of
YAML's type-coercion surprises.

**`pydantic-settings`' built-in `TomlConfigSettingsSource`.** Rejected: the
precedence between multiple files is a property of the library rather than
something stated in our own code, and the layered-directory semantics we want
are not what it provides.

**A configuration service (Consul, etcd, Vault).** Deferred, not rejected. It is
the right answer for secret rotation at scale and worth revisiting when there is
a fleet to configure. It is not worth a network dependency on process start-up
today.
