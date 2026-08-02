"""Outbound notification and alerting.

Delivery of operational alerts, trade notifications and health events to
their channels, with severity routing, rate limiting and de-duplication.

Boundary:
    Delivery only. A failed notification must never affect trading.

ATLAS-TASK-0001 establishes this package as an empty, importable unit with a
declared responsibility. Its implementation is delivered by a later task.
"""

from __future__ import annotations

__all__: list[str] = []
