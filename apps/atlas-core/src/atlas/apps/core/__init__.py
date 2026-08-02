"""The Atlas core trading service.

The long-lived process that wires the packages together, owns the event
loop, and runs the trading pipeline end to end.

Boundary:
    Composition and process lifecycle only. All behaviour lives in
    ``atlas.*`` packages so that it remains testable without a process.

ATLAS-TASK-0001 establishes this package as an empty, importable unit with a
declared responsibility. Its implementation is delivered by a later task.
"""

from __future__ import annotations

__all__: list[str] = []
