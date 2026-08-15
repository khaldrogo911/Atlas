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

`atlas-core` deviates deliberately. Configured, it performs a configuration
self-check and exits `0`; a restart policy would turn a clean exit into a crash
loop, and a health check has nothing to poll. Both change when the service
acquires a run loop.

Since ATLAS-TASK-0023 that self-check includes building the trading adapter, so
the compose service requires the four `ATLAS_BROKER__*` values and fails closed
on a missing one rather than defaulting. A container without them exits `2`.
