# ADR 0004 — Strict typing and linting from the first commit

**Status:** Accepted
**Date:** 2026-08-02

## Context

Retrofitting static typing onto a mature Python codebase is not a refactor, it
is a rewrite: every untyped boundary hides assumptions that only surface when
you try to state them. The cost of `mypy --strict` is roughly linear when paid
from the first commit and roughly quadratic when deferred.

The domain sharpens this. A trading platform passes around quantities that are
all numbers and all mean different things — prices, lot sizes, risk fractions,
R multiples. The type system is the cheapest place to stop a risk fraction
being used as a lot size.

## Decision

Four tools, each with one job, enforced identically on commit and in CI:

| Tool | Job | Configuration |
|---|---|---|
| Ruff | Lint and import order | `ruff.toml` |
| Black | Formatting | `[tool.black]` in `pyproject.toml` |
| MyPy | Static typing, `strict = True` | `mypy.ini` |
| Pytest | Tests | `pytest.ini` |

**Ruff lints, Black formats.** Ruff's formatter is deliberately not enabled;
two formatters in one toolchain is a source of churn with no benefit.

**Strict means strict.** `disallow_untyped_defs`, `disallow_any_generics`,
`warn_unreachable`, `strict_equality`, `no_implicit_reexport`, plus
`warn_unused_ignores` so that stale suppressions surface instead of
accumulating. The pydantic MyPy plugin is enabled with `init_typed` and
`init_forbid_extra`.

The Ruff rule set is broad and includes `ANN` (annotations), `D` (Google-style
docstrings), `S` (bandit), `TRY`, `PTH`, `DTZ` and `ERA`. Tests relax exactly
three rules: `S101` (assert is the point), `PLR2004` (literal comparisons read
better in assertions) and the docstring rules for test classes and methods,
whose names are the documentation.

**Pre-commit runs the project's own tools**, via `language: system` against the
Poetry environment, rather than pinned mirror repositories. This trades
hermeticity for something worth more: the version enforced on commit is by
construction the version CI enforces, with `poetry.lock` as the single source
of truth.

## Consequences

- Every function in the codebase is annotated and documented, including the
  ones written under time pressure.
- CI fails on the first violated gate. There is no "warnings" tier, because a
  warning nobody fails on is a warning nobody fixes.
- `DTZ` bans naive `datetime` construction. For a platform whose correctness
  depends on session boundaries and broker time zones, this is a domain rule
  enforced by the linter.
- A new `# type: ignore` requires a comment justifying it, and
  `warn_unused_ignores` deletes the ones that stop being needed.
- The friction is real and highest at the start, when there is little code and
  the rules feel like overhead. That is precisely when the decision has to be
  made — it cannot be made later.

## Alternatives considered

**Gradual typing, strict later.** Rejected on the cost argument above. "Later"
in practice means "at the point where it is too expensive".

**A minimal Ruff rule set (`E`, `F`, `I` only).** Rejected: the rules that
matter most here are the ones that encode domain hazards — `DTZ` on time zones,
`S` on unsafe calls, `TRY` on exception handling. Those are the ones a minimal
set omits.

**MyPy in non-strict mode.** Rejected: non-strict MyPy silently passes untyped
functions, which is the state it is meant to detect.
