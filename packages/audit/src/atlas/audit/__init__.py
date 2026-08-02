"""Immutable audit trail.

Append-only recording of every decision, model output, risk verdict,
order and configuration change, with the provenance needed to reconstruct
why any action was taken.

Boundary:
    Append-only. Records are never mutated or deleted by application code.

ATLAS-TASK-0001 establishes this package as an empty, importable unit with a
declared responsibility. Its implementation is delivered by a later task.
"""

from __future__ import annotations

__all__: list[str] = []
