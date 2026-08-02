# Integration tests

Reserved for tests that exercise real infrastructure: PostgreSQL, Redis and
DuckDB.

**This directory is intentionally empty at ATLAS-TASK-0001.** There are no
components that talk to a datastore yet, so there is nothing to integrate.

It contains no placeholder or skipped tests. A suite of `pytest.skip` stubs
reports green in CI while verifying nothing, which is strictly worse than an
empty directory — the empty directory is honest about its coverage.

## When tests arrive here

Mark them and bring the services up first:

```python
pytestmark = pytest.mark.integration
```

```bash
docker compose up -d postgres redis
poetry run pytest -m integration
```

The default `pytest` invocation collects this directory and finds nothing,
which is why the standard run needs no services.
