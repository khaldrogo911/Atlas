"""Event contracts and the asynchronous message bus.

Immutable event definitions, their serialisation, topic naming, and the
publish/subscribe transport that decouples producers from consumers.

Boundary:
    Carries events; never interprets them. No domain decision is made here.

ATLAS-TASK-0001 establishes this package as an empty, importable unit with a
declared responsibility. Its implementation is delivered by a later task.
"""

from __future__ import annotations

__all__: list[str] = []
