# End-to-end tests

Reserved for tests that drive a fully deployed stack: the `atlas-core` service,
its datastores and a simulated broker, exercised through the same entry points
an operator would use.

**This directory is intentionally empty at ATLAS-TASK-0001.** There is no
pipeline to drive end to end yet.

As with `tests/integration/`, it contains no skipped placeholder tests. See that
directory's README for the reasoning.

## When tests arrive here

```python
pytestmark = pytest.mark.e2e
```

```bash
docker compose up -d
poetry run pytest -m e2e
```

An e2e test must never point at a live-funded broker account. The simulated
broker or a demo account is the only permitted target.
