"""Model serving and AI-assisted reasoning.

Inference against trained models, prompt and response handling for
language-model assistance, provider abstraction, and the guard rails that
bound what a model output is permitted to influence.

Boundary:
    Advisory only. A model output is an input to a decision, never the
    decision itself, and never a substitute for a risk check.

ATLAS-TASK-0001 establishes this package as an empty, importable unit with a
declared responsibility. Its implementation is delivered by a later task.
"""

from __future__ import annotations

__all__: list[str] = []
