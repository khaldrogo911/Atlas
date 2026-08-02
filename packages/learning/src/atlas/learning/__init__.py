"""Offline training, evaluation and the model registry.

Dataset assembly, model training, out-of-sample evaluation, versioning
and promotion of models into the registry that ``atlas.ai`` serves.

Boundary:
    Runs offline. No component on the live trading path may import it.

ATLAS-TASK-0001 establishes this package as an empty, importable unit with a
declared responsibility. Its implementation is delivered by a later task.
"""

from __future__ import annotations

__all__: list[str] = []
