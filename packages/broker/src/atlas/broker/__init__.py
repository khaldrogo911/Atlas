"""Vendor-neutral broker abstraction.

The ``BrokerAdapter`` port and its supporting types: account state, order
acknowledgements, position snapshots, and connectivity lifecycle. Concrete
venue integrations are adapters behind this port.

Boundary:
    Defines the port and its data contracts only. Order sizing, routing and
    risk decisions belong to ``atlas.execution`` and ``atlas.risk``.

ATLAS-TASK-0001 establishes this package as an empty, importable unit with a
declared responsibility. Its implementation is delivered by a later task.
"""

from __future__ import annotations

__all__: list[str] = []
