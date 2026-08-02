"""Order lifecycle and execution management.

Translation of approved trade intents into broker orders, routing, fill
and partial-fill handling, reconciliation against broker state, and
idempotent retry of in-flight instructions.

Boundary:
    Executes only what ``atlas.risk`` has approved. Never sizes a position
    and never overrides a risk verdict.

ATLAS-TASK-0001 establishes this package as an empty, importable unit with a
declared responsibility. Its implementation is delivered by a later task.
"""

from __future__ import annotations

__all__: list[str] = []
