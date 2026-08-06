"""Cross-cutting primitives shared by every Atlas package.

Value types, identifiers, clock and time-zone helpers, result and error
primitives, and the typing vocabulary the rest of the platform is written
in. Everything here is dependency-free and importable from anywhere.

Boundary:
    May not import any other ``atlas.*`` package, and may not encode domain
    rules of its own.

ATLAS-TASK-0001 established this package as an empty, importable unit with a
declared responsibility. ATLAS-TASK-0009 delivered the first of it: the
:mod:`atlas.common.clock` port and its two implementations. ATLAS-TASK-0010
added :mod:`atlas.common.retry`, which is here rather than in the broker package
because backing off and trying again is not a broker idea — the market data,
notification and execution packages will each want it, and the one that defined
it first would have owned it for everybody. The rest arrives with the tasks that
need it.
"""

from __future__ import annotations

from atlas.common.clock import Clock, ManualClock, SystemClock
from atlas.common.retry import RetryPolicy, retry_call

__all__ = ["Clock", "ManualClock", "RetryPolicy", "SystemClock", "retry_call"]
