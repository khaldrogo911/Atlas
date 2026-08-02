"""Strategy contracts and the strategy engine.

The strategy interface, its lifecycle, registration and the engine that
drives registered strategies against incoming events to produce proposed
trade intents.

Boundary:
    Emits intents, not orders. Nothing here may reach a broker directly, and
    nothing here may bypass ``atlas.risk``.

ATLAS-TASK-0001 establishes this package as an empty, importable unit with a
declared responsibility. Its implementation is delivered by a later task.
"""

from __future__ import annotations

__all__: list[str] = []
