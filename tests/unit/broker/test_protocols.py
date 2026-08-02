"""Structural typing tests for the broker capability protocols.

A protocol earns its place by *discriminating*: it must accept what satisfies
it and reject what does not. A runtime-checkable protocol that accepts
everything would pass a naive conformance test while asserting nothing, so
every protocol here is checked against a stub built from another protocol's
members as well as against the port itself.
"""

from __future__ import annotations

import inspect
from typing import Final, Protocol, runtime_checkable

import pytest

from atlas.broker import (
    BrokerAdapter,
    SupportsConnection,
    SupportsDiagnostics,
    SupportsMarketData,
    SupportsStreaming,
    SupportsTrading,
)
from atlas.broker import protocols as protocols_module

pytestmark = pytest.mark.unit

#: The intended split of the port's surface into capabilities a consumer can
#: depend on alone. Declared here rather than read back off the source, so that
#: moving a method between protocols is a decision recorded in a test.
PROTOCOL_MEMBERS: Final[dict[type, tuple[str, ...]]] = {
    SupportsConnection: ("connect", "disconnect", "reconnect", "is_connected", "health"),
    SupportsMarketData: (
        "get_symbols",
        "get_symbol",
        "get_tick",
        "get_ticks",
        "get_candle",
        "get_candles",
        "get_historical_data",
    ),
    SupportsStreaming: (
        "subscribe_ticks",
        "unsubscribe_ticks",
        "subscribe_candles",
        "unsubscribe_candles",
    ),
    SupportsTrading: ("place_order", "modify_order", "cancel_order", "close_position"),
    SupportsDiagnostics: ("ping", "latency", "server_time", "version"),
}

ALL_PROTOCOLS: Final = tuple(PROTOCOL_MEMBERS)

#: Deliberately outside every protocol. Account state and risk arithmetic have
#: no consumer that wants them without a session, so factoring them out would
#: add a name without removing a dependency. Recorded so the omission reads as
#: a choice rather than an oversight.
UNCOVERED_METHODS: Final = frozenset(
    {
        "get_account",
        "get_positions",
        "get_orders",
        "get_open_positions",
        "margin_required",
        "margin_available",
        "can_trade",
    }
)


def _noop(self: object, *args: object, **kwargs: object) -> None:
    """Stand in for a protocol member in a structural conformance check."""


def _stub_for(protocol: type) -> object:
    """Build an instance carrying exactly one protocol's members and nothing else."""
    body: dict[str, object] = dict.fromkeys(PROTOCOL_MEMBERS[protocol], _noop)
    body["__doc__"] = f"Carries exactly the members of {protocol.__name__}."
    return type(f"{protocol.__name__}Stub", (), body)()


def _runtime_members(protocol: type) -> set[str]:
    """Return the non-dunder callables a protocol declares."""
    return {name for name in vars(protocol) if not name.startswith("_")}


def _ids(protocol: type) -> str:
    return protocol.__name__


class TestProtocolDeclaration:
    @pytest.mark.parametrize("protocol", ALL_PROTOCOLS, ids=_ids)
    def test_the_protocol_is_a_protocol(self, protocol: type) -> None:
        assert issubclass(protocol, Protocol)  # type: ignore[arg-type]

    @pytest.mark.parametrize("protocol", ALL_PROTOCOLS, ids=_ids)
    def test_the_protocol_is_runtime_checkable(self, protocol: type) -> None:
        # Without this, every isinstance check below would raise instead of
        # answering, and the discrimination tests would be vacuous.
        assert getattr(protocol, "_is_runtime_protocol", False)

    @pytest.mark.parametrize("protocol", ALL_PROTOCOLS, ids=_ids)
    def test_the_protocol_cannot_be_instantiated(self, protocol: type) -> None:
        with pytest.raises(TypeError):
            protocol()

    @pytest.mark.parametrize("protocol", ALL_PROTOCOLS, ids=_ids)
    def test_the_protocol_declares_the_expected_members(self, protocol: type) -> None:
        assert _runtime_members(protocol) == set(PROTOCOL_MEMBERS[protocol])

    @pytest.mark.parametrize("protocol", ALL_PROTOCOLS, ids=_ids)
    def test_the_protocol_is_documented(self, protocol: type) -> None:
        assert protocol.__doc__
        for member in PROTOCOL_MEMBERS[protocol]:
            assert getattr(
                protocol, member
            ).__doc__, f"{protocol.__name__}.{member} is undocumented"

    def test_the_module_exports_every_protocol(self) -> None:
        assert set(protocols_module.__all__) == {protocol.__name__ for protocol in ALL_PROTOCOLS}

    def test_the_module_is_documented(self) -> None:
        assert protocols_module.__doc__


class TestPortConformance:
    """The port must satisfy every capability it was decomposed into."""

    @pytest.mark.parametrize("protocol", ALL_PROTOCOLS, ids=_ids)
    def test_the_port_satisfies_the_protocol(self, protocol: type) -> None:
        assert issubclass(BrokerAdapter, protocol)

    @pytest.mark.parametrize("protocol", ALL_PROTOCOLS, ids=_ids)
    def test_the_port_does_not_inherit_the_protocol(self, protocol: type) -> None:
        # Conformance must be structural. Inheriting would mean a third-party
        # adapter had to import these to be accepted, which is the coupling
        # protocols exist to avoid.
        assert protocol not in BrokerAdapter.__mro__

    @pytest.mark.parametrize("protocol", ALL_PROTOCOLS, ids=_ids)
    def test_every_member_is_a_method_of_the_port(self, protocol: type) -> None:
        for member in PROTOCOL_MEMBERS[protocol]:
            assert callable(getattr(BrokerAdapter, member, None)), f"port lacks {member}"

    @pytest.mark.parametrize("protocol", ALL_PROTOCOLS, ids=_ids)
    def test_every_signature_matches_the_port(self, protocol: type) -> None:
        # Two copies of a signature drift. This is the test that stops it.
        for member in PROTOCOL_MEMBERS[protocol]:
            expected = str(inspect.signature(getattr(BrokerAdapter, member)))
            actual = str(inspect.signature(getattr(protocol, member)))

            assert actual == expected, f"{protocol.__name__}.{member} has drifted from the port"


class TestCoverage:
    def test_the_protocols_are_disjoint(self) -> None:
        counted = sum(len(members) for members in PROTOCOL_MEMBERS.values())
        distinct = {member for members in PROTOCOL_MEMBERS.values() for member in members}

        assert counted == len(distinct)

    def test_the_protocols_and_the_uncovered_set_account_for_the_whole_port(self) -> None:
        covered = {member for members in PROTOCOL_MEMBERS.values() for member in members}

        assert covered | UNCOVERED_METHODS == set(BrokerAdapter.__abstractmethods__)

    def test_nothing_is_both_covered_and_uncovered(self) -> None:
        covered = {member for members in PROTOCOL_MEMBERS.values() for member in members}

        assert not covered & UNCOVERED_METHODS

    def test_market_data_excludes_streaming(self) -> None:
        # A replay engine or a REST-only venue must be able to satisfy
        # SupportsMarketData while streaming nothing.
        assert not set(PROTOCOL_MEMBERS[SupportsMarketData]) & set(
            PROTOCOL_MEMBERS[SupportsStreaming]
        )


class TestStructuralTyping:
    @pytest.mark.parametrize("protocol", ALL_PROTOCOLS, ids=_ids)
    def test_a_matching_stub_satisfies_the_protocol(self, protocol: type) -> None:
        # Nothing inherits from anything here: the stub is accepted purely on
        # the shape of its members.
        assert isinstance(_stub_for(protocol), protocol)

    @pytest.mark.parametrize("protocol", ALL_PROTOCOLS, ids=_ids)
    def test_a_stub_for_another_capability_is_rejected(self, protocol: type) -> None:
        for other in ALL_PROTOCOLS:
            if other is protocol:
                continue

            assert not isinstance(
                _stub_for(other), protocol
            ), f"{protocol.__name__} accepted a {other.__name__} stub"

    @pytest.mark.parametrize("protocol", ALL_PROTOCOLS, ids=_ids)
    def test_an_empty_object_is_rejected(self, protocol: type) -> None:
        assert not isinstance(object(), protocol)

    @pytest.mark.parametrize("protocol", ALL_PROTOCOLS, ids=_ids)
    def test_removing_one_member_breaks_conformance(self, protocol: type) -> None:
        # Proves the check reads every member, not just the first one it finds.
        for omitted in PROTOCOL_MEMBERS[protocol]:
            body: dict[str, object] = {
                member: _noop for member in PROTOCOL_MEMBERS[protocol] if member != omitted
            }
            incomplete = type("Incomplete", (), body)()

            assert not isinstance(incomplete, protocol), f"conformance survived losing {omitted}"

    def test_a_consumer_can_depend_on_one_capability(self) -> None:
        # The point of the decomposition: a function that only reads bars is
        # satisfiable without a venue, a session or an order router.
        @runtime_checkable
        class _Consumer(Protocol):
            def get_candles(self, symbol: str, timeframe: object, count: int) -> object:
                """Match by name only."""

        assert isinstance(_stub_for(SupportsMarketData), _Consumer)
        assert not isinstance(_stub_for(SupportsTrading), _Consumer)
