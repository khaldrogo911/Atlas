"""Market data ingestion, normalisation and storage.

Acquisition of tick and bar data, timestamp and session normalisation,
gap and integrity validation, and persistence into the historical store.

Boundary:
    Produces trustworthy data. Derives no signals and computes no features.

ATLAS-TASK-0001 establishes this package as an empty, importable unit with a
declared responsibility. Its implementation is delivered by a later task.
"""

from __future__ import annotations

__all__: list[str] = []
