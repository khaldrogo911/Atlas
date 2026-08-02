# ADR 0002 — Monorepo with PEP 420 namespace packages

**Status:** Accepted
**Date:** 2026-08-02

## Context

Atlas is fifteen libraries and three deployable processes that must agree
exactly on event schemas, configuration shape and domain types. Two structural
questions had to be settled before any code was written:

1. One repository or many?
2. How do the libraries expose themselves to Python's import system?

The failure mode we are most concerned about is **version skew**: `execution`
built against one version of an event contract while `strategy` emits another.
In a trading system that surfaces as a malformed order, not a stack trace.

## Decision

**One repository, one lock file.** All packages and apps live in this
repository and resolve against a single `poetry.lock`. There is exactly one
dependency graph, and it is upgraded atomically.

**One namespace, many source roots.** Every library is a PEP 420 implicit
namespace package under `atlas`:

```
packages/<name>/src/atlas/<name>/__init__.py
apps/<name>/src/atlas/apps/<module>/__init__.py
```

There is deliberately **no `atlas/__init__.py`** anywhere. Each source root is
registered in `[tool.poetry].packages`; Poetry's editable install puts all
eighteen on `sys.path`, and `atlas` resolves as one namespace spanning them.

## Consequences

- A cross-cutting change — a new event field, a renamed type — lands in one
  commit, reviewed as one unit, and CI verifies every consumer against it.
- Imports read as `from atlas.risk import ...`, matching the architecture
  diagram exactly. There is no `atlas_risk` / `atlas.risk` naming split between
  libraries and apps.
- If a package is later extracted into its own distribution, it keeps its
  import path. Not one consuming line changes.
- A stray `atlas/__init__.py` in any source root would silently collapse the
  namespace: that root would shadow all seventeen others at import time, and
  the symptom would be a confusing `ModuleNotFoundError` far from the cause.
  `tests/contract/test_repository_structure.py` asserts this file never exists,
  and that the live namespace spans exactly as many roots as are declared.
- Adding a package means adding an entry to `[tool.poetry].packages`. Forgetting
  is caught by the contract tests, not discovered in production.
- Tooling needs the source roots spelled out: `mypy.ini` lists all eighteen on
  `mypy_path`. This is a real maintenance cost, paid in one file.

## Alternatives considered

**Polyrepo, one repository per package.** Rejected: it converts every
cross-cutting change into a co-ordinated multi-repository release, and
reintroduces exactly the version skew this decision exists to prevent. It is
the right structure when packages have independent consumers and release
cadences; ours have neither.

**Flat top-level modules (`atlas_common`, `atlas_risk`).** Rejected: no
namespace machinery, but the import names stop matching the architecture, and
apps and libraries end up with visibly different naming conventions.

**A single `src/atlas/` tree with no package boundaries.** Rejected: package
directories are what make a boundary violation visible in review. Without them,
"strategy must not import broker" is a convention nobody can enforce.
