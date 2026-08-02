"""Cross-cutting primitives shared by every Atlas package.

Value types, identifiers, clock and time-zone helpers, result and error
primitives, and the typing vocabulary the rest of the platform is written
in. Everything here is dependency-free and importable from anywhere.

Boundary:
    May not import any other ``atlas.*`` package, and may not encode domain
    rules of its own.

ATLAS-TASK-0001 establishes this package as an empty, importable unit with a
declared responsibility. Its implementation is delivered by a later task.
"""

from __future__ import annotations

__all__: list[str] = []
