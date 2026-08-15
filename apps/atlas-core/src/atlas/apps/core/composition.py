"""Selection and construction of this process's broker adapter.

ADR-0015 gives ``apps/atlas-core`` one implementation to select and one place to
select it. This module is that place: it translates the broker section of
:class:`~atlas.config.AtlasSettings` into an ``MT5Config``, constructs the
adapter that configuration describes, and hands the result to a
:class:`~atlas.apps.core.broker_ownership.BrokerOwner`.

It is the only module under ``apps/`` that may name the selected
implementation, and the permission is bounded by the purpose ADR-0015 gave it:
translation and construction. Nothing here names the implementation that was not
selected, calls a port operation, or says anything about what an application may
import in general.

Construction is not connection
    Building an adapter contacts no terminal and imports no vendor package, so
    this runs unchanged on a host where MetaTrader 5 is absent. Opening the
    session belongs to :meth:`~atlas.apps.core.broker_ownership.BrokerOwner.start`,
    and no accepted decision yet says when that happens.

Where the refusal lands
    ``BrokerSettings`` accepts its own not-configured defaults, because settings
    must resolve for a process that holds no trading configuration. ``MT5Config``
    accepts no such thing. ADR-0015 decided what the gap between the two means:
    a deployment whose broker section could not open a session does not start.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from pydantic import ValidationError as PydanticValidationError

from atlas.apps.core.broker_ownership import BrokerOwner
from atlas.broker.mt5 import MT5BrokerAdapter, MT5Config
from atlas.config import ConfigurationError

if TYPE_CHECKING:
    from atlas.config import AtlasSettings

__all__ = ["build_broker_owner"]


def build_broker_owner(settings: AtlasSettings) -> BrokerOwner:
    """Build the owner of this process's broker adapter.

    Translates the four values a session cannot be established without, and
    passes no others: ``timeout_ms``, ``portable`` and ``server_utc_offset``
    keep the defaults ``MT5Config`` gives them, because no setting corresponds
    to any of the three and inventing one would be a decision this task does not
    hold.

    Args:
        settings: Resolved application settings. Only the broker section is
            read.

    Returns:
        An owner holding a newly constructed adapter that is not connected.

    Raises:
        ConfigurationError: If the broker section does not describe a session
            that could be opened. Raised in the configuration package's own
            vocabulary so that the entrypoint's existing handler reports it,
            rather than giving startup a second way to fail.
    """
    try:
        config = MT5Config(
            login=settings.broker.login,
            password=settings.broker.password,
            server=settings.broker.server,
            terminal_path=settings.broker.terminal_path,
        )
    except PydanticValidationError as exc:
        msg = f"invalid broker configuration:\n{exc}"
        raise ConfigurationError(msg) from exc

    return BrokerOwner(MT5BrokerAdapter(config))
