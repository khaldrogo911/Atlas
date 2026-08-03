"""MetaTrader 5 integration: the venue adapter and everything it needs.

The only package in Atlas that knows MetaTrader 5 exists. Nothing outside it
imports the ``MetaTrader5`` package, and no MetaTrader 5 value leaves it —
callers receive :mod:`atlas.broker.models` types or an exception::

    from atlas.broker.mt5 import MT5BrokerAdapter, MT5Config

Importing this package does *not* import the vendor SDK. The single
``import MetaTrader5`` in Atlas is inside a function body in
:mod:`~atlas.broker.mt5.connection`, so the package resolves on a Linux CI
runner where the wheel does not exist and fails only when a session is actually
opened.

Layout, in strict dependency order:

:mod:`~atlas.broker.mt5.constants`
    Wire values and the translation tables. Imports nothing but the domain.

:mod:`~atlas.broker.mt5.mapper`
    Pure translation into domain models, plus the protocols describing the
    vendor structures Atlas reads.

:mod:`~atlas.broker.mt5.connection`
    Configuration, the lazy vendor import, the session state machine, and the
    two tables that turn a MetaTrader 5 error code into an
    :mod:`atlas.broker.exceptions` type.

:mod:`~atlas.broker.mt5.adapter`
    The :class:`~atlas.broker.adapter.BrokerAdapter` implementation, which
    chooses terminal calls and delegates every conversion to the mapper.

Boundary:
    Translation only. No sizing, no signal, no retry policy, no scheduling.

Status:
    Demo accounts only. The four trading methods raise
    :class:`NotImplementedError` rather than sending anything to a venue. See
    ``README.md`` in this directory for the full coverage table and the reason
    behind each gap.
"""

from __future__ import annotations

from atlas.broker.mt5.adapter import MT5BrokerAdapter
from atlas.broker.mt5.connection import MT5Config

__all__ = ["MT5BrokerAdapter", "MT5Config"]
