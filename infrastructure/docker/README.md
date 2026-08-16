# Docker Infrastructure

The `Dockerfile` and `docker-compose.yml` live at the repository root, because
both need the repository root as their build context and Docker resolves
context relative to the file's location. This directory holds Docker assets
that are *not* the build itself.

## Current contents

Nothing yet. The build needs no helper scripts at ATLAS-TASK-0001.

## What lands here

| Asset | Arrives with |
|---|---|
| `entrypoint.sh` | a service that needs pre-start ordering beyond compose health checks |
| `docker-compose.override.yml` | a workflow needing source mounts and hot reload |
| `docker-compose.prod.yml` | resource limits and production topology |

## Image design

Multi-stage, defined in `/Dockerfile`:

- **builder** — installs Poetry, resolves dependencies into `/app/.venv` from
  `poetry.lock`, then links the workspace packages. Manifests are copied before
  source so a code change does not invalidate the dependency layer.
- **runtime** — `python:3.12-slim-bookworm`, carries only the virtual
  environment and application source, runs as non-root `atlas` (uid 1000).

Two constraints worth knowing before editing it:

1. **The source tree must land at `/app` in both stages.** The editable install
   records absolute paths; moving the source in the runtime stage breaks every
   `atlas.*` import.
2. **`ATLAS_ENV` defaults to `production` in the image.** An unconfigured
   container fails its own invariant checks rather than starting permissively.
   Compose overrides it for local use.

## Compose services

| Service | Restart policy | Health check |
|---|---|---|
| `postgres` | `unless-stopped` | `pg_isready` |
| `redis` | `unless-stopped` | `redis-cli ping` |
| `atlas-core` | `no` | none |

`atlas-core` deviates deliberately. Configured, it performs a start-up
connectivity check and exits — `0` once a broker session has been opened and
closed again; a restart policy would turn a clean exit into a crash loop, and a
health check has nothing to poll, because the process holds no session once it
returns. Both change when the service acquires a run loop.

Since ATLAS-TASK-0023 that check includes building the trading adapter, so the
compose service requires the four `ATLAS_BROKER__*` values and fails closed on a
missing one rather than defaulting. A container without them exits `2`.

Since ADR-0017 the check also opens the session those four values describe, and
this image cannot open one: MetaTrader5 publishes Windows wheels only, so a
fully configured container exits `3` here by design. Everything before the
session is still proved — settings resolve, the invariants hold, the broker
section translates into an adapter — and the session itself is proved on a
Windows host or not at all.
