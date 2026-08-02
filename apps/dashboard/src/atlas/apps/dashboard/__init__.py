"""Operator-facing dashboard service.

The read-oriented interface operators use to observe platform state,
positions, risk utilisation and system health.

Boundary:
    Observation and explicitly-authorised control actions only. No trading
    logic is implemented here.

ATLAS-TASK-0001 establishes this package as an empty, importable unit with a
declared responsibility. Its implementation is delivered by a later task.
"""

from __future__ import annotations

__all__: list[str] = []
