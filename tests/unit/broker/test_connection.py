"""Unit tests for the Connection model."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from atlas.broker.models import Connection, ConnectionState

pytestmark = pytest.mark.unit


def _connection(connection: Connection, **overrides: object) -> Connection:
    """Revalidate a valid connection with the given fields replaced."""
    return Connection.model_validate({**connection.model_dump(), **overrides})


class TestStateAgreement:
    @pytest.mark.parametrize("state", list(ConnectionState))
    def test_the_flag_must_match_the_state(
        self, state: ConnectionState, connection: Connection
    ) -> None:
        result = _connection(connection, state=state, connected=state.is_usable)

        assert result.connected is state.is_usable

    @pytest.mark.parametrize("state", list(ConnectionState))
    def test_a_contradictory_flag_is_rejected(
        self, state: ConnectionState, connection: Connection
    ) -> None:
        # The failure this prevents: a reconnect loop that updates `state` but
        # leaves a stale `connected=True`, so health checks reading the boolean
        # see nothing wrong while every request fails.
        with pytest.raises(ValidationError, match="contradicts state"):
            _connection(connection, state=state, connected=not state.is_usable)

    def test_a_degraded_session_still_counts_as_connected(self, connection: Connection) -> None:
        # Degraded means up but underperforming. Whether to keep trading
        # through it is a policy decision made above this layer.
        result = _connection(connection, state=ConnectionState.DEGRADED, connected=True)

        assert result.connected is True

    def test_a_session_being_torn_down_does_not_count_as_connected(
        self, connection: Connection
    ) -> None:
        # The socket may still be open, but nothing new should be sent.
        result = _connection(connection, state=ConnectionState.DISCONNECTING, connected=False)

        assert result.connected is False


class TestOptionalTelemetry:
    def test_latency_is_absent_before_the_first_measurement(self, connection: Connection) -> None:
        # `None` and `0.0` mean different things and must stay distinguishable.
        assert _connection(connection, latency_ms=None).latency_ms is None

    def test_a_zero_latency_measurement_is_accepted(self, connection: Connection) -> None:
        assert _connection(connection, latency_ms=0.0).latency_ms == 0.0

    def test_a_negative_latency_is_rejected(self, connection: Connection) -> None:
        with pytest.raises(ValidationError, match="greater than or equal to 0"):
            _connection(connection, latency_ms=-1.0)

    def test_a_heartbeat_is_absent_before_the_first_one(self, connection: Connection) -> None:
        assert _connection(connection, last_heartbeat=None).last_heartbeat is None


class TestIdentity:
    @pytest.mark.parametrize("field", ["broker", "server"])
    def test_identity_is_required(self, field: str, connection: Connection) -> None:
        payload = connection.model_dump()
        del payload[field]

        with pytest.raises(ValidationError, match="Field required"):
            Connection.model_validate(payload)

    @pytest.mark.parametrize("field", ["broker", "server"])
    def test_a_blank_identity_is_rejected(self, field: str, connection: Connection) -> None:
        with pytest.raises(ValidationError):
            _connection(connection, **{field: "   "})
