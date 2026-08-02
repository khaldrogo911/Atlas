"""Deterministic feature computation.

Pure, reproducible transformations from normalised market data into the
feature vectors consumed by regime detection, strategies and models.

Boundary:
    Must be free of look-ahead: a feature at time *t* may read no input
    timestamped after *t*. No I/O, no model inference.

ATLAS-TASK-0001 establishes this package as an empty, importable unit with a
declared responsibility. Its implementation is delivered by a later task.
"""

from __future__ import annotations

__all__: list[str] = []
