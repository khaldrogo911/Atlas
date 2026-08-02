"""The health and identity of a session with a broker."""

from __future__ import annotations

from pydantic import BaseModel, Field, model_validator

from atlas.broker.models.enums import ConnectionState
from atlas.broker.models.primitives import (
    BROKER_MODEL_CONFIG,
    LatencyMilliseconds,
    Name,
    Timestamp,
)

__all__ = ["Connection"]


class Connection(BaseModel):
    """What Atlas currently knows about its link to a venue.

    :attr:`state` and :attr:`connected` describe the same thing at two levels
    of detail, which is a standing invitation for them to disagree. They are
    both present because callers want both, and a validator keeps them
    consistent, so no code has to decide which of two contradictory fields to
    believe.
    """

    model_config = BROKER_MODEL_CONFIG

    state: ConnectionState = Field(description="Lifecycle state of the session.")
    connected: bool = Field(
        description=(
            "Whether the session can carry a request. True exactly when "
            "``state`` is CONNECTED or DEGRADED."
        )
    )
    latency_ms: LatencyMilliseconds | None = Field(
        default=None,
        description=(
            "Last measured round-trip latency. ``None`` when no measurement "
            "has been taken, which is not the same as a measurement of zero."
        ),
    )
    last_heartbeat: Timestamp | None = Field(
        default=None,
        description="When the venue last confirmed liveness. ``None`` before the first.",
    )
    broker: Name = Field(description="Name of the brokerage at the far end.")
    server: Name = Field(description="Trade server the session is established with.")

    @model_validator(mode="after")
    def _check_connected_agrees_with_state(self) -> Connection:
        """Reject a session that reports a state and a flag that contradict.

        The failure this prevents is specific: a reconnect loop that sets
        ``state`` correctly but leaves a stale ``connected=True`` behind, so
        health checks reading the boolean see nothing wrong while every request
        fails.

        Returns:
            The validated instance.

        Raises:
            ValueError: If ``connected`` does not match ``state``.
        """
        if self.connected != self.state.is_usable:
            msg = (
                f"connected={self.connected} contradicts state={self.state}; "
                f"expected connected={self.state.is_usable}"
            )
            raise ValueError(msg)
        return self
