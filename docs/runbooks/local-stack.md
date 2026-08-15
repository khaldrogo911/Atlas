# Runbook — Local development stack

## Symptom

The local stack will not start, or `atlas-core` exits non-zero.

## Impact

Development only. No live trading component exists at ATLAS-TASK-0001.

## Normal startup

```bash
cp .env.example .env          # once; then fill in POSTGRES_PASSWORD and the
                              # four ATLAS_BROKER__* values. None has a default,
                              # and compose refuses the file until all are set.
docker compose config         # validate before starting anything
docker compose up -d postgres redis
docker compose ps             # both must report (healthy)
docker compose up atlas-core  # runs the config self-check, then exits 0
```

Expected `atlas-core` output — one JSON line, exit code `0`:

```json
{"event":"atlas.core.startup","app_name":"atlas-core","environment":"development", ...}
```

## Checks

### 1. Compose refuses to validate

```
error: required variable POSTGRES_PASSWORD is missing a value
error: required variable ATLAS_BROKER__LOGIN is missing a value
```

**Diagnosis:** no `.env`, or that variable is unset in it. Five values fail
closed — `POSTGRES_PASSWORD` and the four `ATLAS_BROKER__*` — and compose
interpolates the whole file, so this refusal applies to `docker compose up -d
postgres redis` as much as to `atlas-core`. It is deliberate: no service in this
repository carries a default credential, and a plausible-looking default broker
login would let a deployment that cannot trade start up looking like one that
can.

**Resolution:** `cp .env.example .env`, set `POSTGRES_PASSWORD`, and uncomment
and fill in all four `ATLAS_BROKER__*` values. They ship commented out; the file
explains why.

### 2. `atlas-core` exits `2`

The entrypoint reports the failure as JSON on **stderr**:

```json
{"event":"atlas.core.startup_failed","error":"invalid Atlas configuration: ..."}
```

Read the `error` field; it names every violated field at once rather than one
per restart. Common causes:

| Error fragment | Cause | Resolution |
|---|---|---|
| `postgres.password must be supplied in production` | `ATLAS_ENV=production` with no password | Supply `ATLAS_POSTGRES__PASSWORD`, or use a non-production environment |
| `debug must be false in production` | `ATLAS_DEBUG=true` under production | Unset it; production forbids debug |
| `logging.format must be 'json' in production` | Console logging under production | Set `ATLAS_LOGGING__FORMAT=json` |
| `pool_max_size ... must be greater than or equal to` | Pool bounds inverted | Correct the pool settings |
| `Extra inputs are not permitted` | Typo in a TOML section key | Section models forbid unknown keys; fix the key name |
| `invalid broker configuration` | The broker section describes no session a terminal could be opened with — `login` is `0` or `server` is empty | Set all four `ATLAS_BROKER__*` values. Since ATLAS-TASK-0023 start-up builds the trading adapter, so this is a start-up failure rather than a later one |

Outside compose the same refusal applies, and there it is the likelier surprise:
`poetry run atlas-core` reads `.env` from the working directory, so a shell whose
`.env` lacks the broker values exits `2` even though nothing about the datastores
changed.

Reproduce outside the container, which is faster:

```bash
ATLAS_ENV=development poetry run atlas-core
```

### 3. Configuration is not what you expect

`ATLAS_ENV` selects the layer and is read **before** the settings model is
built. If it is set only in `.env`, the layer will not be selected.

```bash
echo $ATLAS_ENV                        # must be exported, not just in .env
docker compose exec atlas-core env | grep ATLAS_    # inside the container
```

Confirm the resolved values by reading the startup record — it reports the
effective environment, log level, and masked connection strings.

### 4. A datastore never reports healthy

```bash
docker compose ps
docker compose logs postgres
docker compose logs redis
```

| Cause | Resolution |
|---|---|
| Port already bound on the host | Set `POSTGRES_PORT` / `REDIS_PORT` in `.env` |
| Password changed after first start | The volume keeps the original credentials: `docker compose down -v` **destroys local data** and re-initialises |
| Init SQL failed | `docker compose logs postgres`; scripts in `infrastructure/database/init/` run **only** on an empty data volume |

### 5. Imports fail outside Docker

```
ModuleNotFoundError: No module named 'atlas.config'
```

**Diagnosis:** the editable install is missing or stale — most often after
adding a package without registering its source root.

**Resolution:**

```bash
poetry install --with dev,test
poetry run pytest -m contract      # asserts every package is declared and importable
```

## Escalation

Local-only at this stage; there is nothing to escalate to. Once live components
exist, this section names the on-call rotation and the conditions that justify
waking it.
