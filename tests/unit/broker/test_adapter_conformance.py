"""What every BrokerAdapter implementation must have in common.

The contract tests next door prove the port is a contract. These prove the
implementations still honour it — all of them, without naming them one at a
time. The adapters are *discovered* by walking :mod:`atlas.broker` and keeping
every concrete subclass of the port, so an adapter added later is conformance
tested the moment it exists rather than the moment somebody remembers to add it
here.

The discovered set is then checked against :data:`EXPECTED_ADAPTERS`. That
assertion is the one that fails on a new adapter, and failing it is the point:
it forces a deliberate edit acknowledging that a second implementation of the
port now exists.

Walking the package imports every module in it. That is safe here, and
deliberately so — the single ``import MetaTrader5`` in Atlas lives inside a
function body, so importing :mod:`atlas.broker.mt5.connection` on a machine
without the vendor wheel resolves cleanly. If that ever stops being true, this
module is where it will be noticed.
"""

from __future__ import annotations

import importlib
import inspect
import pkgutil
from typing import TYPE_CHECKING, Final

import pytest

from atlas.broker import (
    SupportsConnection,
    SupportsDiagnostics,
    SupportsMarketData,
    SupportsStreaming,
    SupportsTrading,
)
from atlas.broker.adapter import BrokerAdapter
from tests.unit.broker.test_adapter_contract import ALL_MANDATED, PINNED_SIGNATURES

if TYPE_CHECKING:
    from collections.abc import Iterator

pytestmark = pytest.mark.unit

#: The package walked for implementations.
BROKER_PACKAGE: Final = "atlas.broker"

#: Every concrete adapter Atlas is expected to contain, by import path.
#:
#: Transcribed rather than derived. A test below asserts that discovery finds
#: exactly this set, so adding an implementation without adding it here fails.
EXPECTED_ADAPTERS: Final = frozenset(
    {
        "atlas.broker.mock.adapter.MockBrokerAdapter",
        "atlas.broker.mt5.adapter.MT5BrokerAdapter",
    }
)

#: The five capability protocols. A full adapter satisfies all of them; the
#: protocols exist so a *caller* can ask for less, not so an adapter can offer
#: less.
CAPABILITIES: Final = (
    SupportsConnection,
    SupportsMarketData,
    SupportsStreaming,
    SupportsTrading,
    SupportsDiagnostics,
)


def _is_adapter(candidate: type) -> bool:
    """Report whether a class is a usable implementation of the port.

    Args:
        candidate: Any class.

    Returns:
        True for a concrete subclass of :class:`~atlas.broker.adapter.BrokerAdapter`,
        excluding the port itself and any abstract layer between.
    """
    return (
        issubclass(candidate, BrokerAdapter)
        and candidate is not BrokerAdapter
        and not inspect.isabstract(candidate)
    )


def _walk_broker_package() -> Iterator[str]:
    """Yield the name of every module under ``atlas.broker``, importing each."""
    package = importlib.import_module(BROKER_PACKAGE)
    for module_info in pkgutil.walk_packages(package.__path__, prefix=f"{BROKER_PACKAGE}."):
        importlib.import_module(module_info.name)
        yield module_info.name


def _discover() -> tuple[tuple[str, ...], dict[str, type[BrokerAdapter]]]:
    """Import the package and collect every concrete adapter in it.

    Returns:
        The modules that were imported, and the adapters found in them keyed by
        import path. Keying by path rather than collecting a list deduplicates
        the same class seen through several modules' namespaces.
    """
    modules = tuple(_walk_broker_package())
    found: dict[str, type[BrokerAdapter]] = {}
    for name in modules:
        module = importlib.import_module(name)
        for _, member in inspect.getmembers(module, inspect.isclass):
            if _is_adapter(member):
                found[f"{member.__module__}.{member.__qualname__}"] = member
    return modules, found


WALKED_MODULES, DISCOVERED = _discover()

#: Parametrisation over the adapters actually present, so an implementation
#: that exists but was never registered above is still put through every
#: behavioural conformance test below rather than skipped.
ADAPTERS: Final = tuple(adapter for _, adapter in sorted(DISCOVERED.items()))


def _adapter_id(adapter: type[BrokerAdapter]) -> str:
    return adapter.__name__


def _path_of(adapter: type[BrokerAdapter]) -> str:
    """Return the import path discovery keyed the adapter by."""
    return f"{adapter.__module__}.{adapter.__qualname__}"


class TestDiscovery:
    def test_the_walk_reaches_the_subpackages(self) -> None:
        # Guards every parametrisation in this module: a walk that imported
        # nothing would report a clean sweep over an empty set.
        assert "atlas.broker.mt5.adapter" in WALKED_MODULES
        assert "atlas.broker.mock.adapter" in WALKED_MODULES

    def test_importing_the_package_does_not_need_the_vendor_sdk(self) -> None:
        # The walk above already imported every module. Reaching this line at
        # all is the assertion; the explicit check names what was proved.
        assert "atlas.broker.mt5.connection" in WALKED_MODULES

    def test_the_predicate_recognises_a_new_implementation(self) -> None:
        newcomer = type(
            "NewcomerAdapter",
            (BrokerAdapter,),
            dict.fromkeys(BrokerAdapter.__abstractmethods__, lambda *_args, **_kwargs: None),
        )

        assert _is_adapter(newcomer)

    def test_the_predicate_rejects_the_port_itself(self) -> None:
        assert not _is_adapter(BrokerAdapter)

    def test_the_predicate_rejects_an_incomplete_implementation(self) -> None:
        partial = type("PartialAdapter", (BrokerAdapter,), {"connect": lambda _self: None})

        assert not _is_adapter(partial)

    def test_discovery_finds_exactly_the_expected_implementations(self) -> None:
        assert set(DISCOVERED) == EXPECTED_ADAPTERS


class TestEveryAdapterImplementsThePort:
    @pytest.mark.parametrize("adapter", ADAPTERS, ids=_adapter_id)
    def test_it_is_a_subclass_of_the_port(self, adapter: type[BrokerAdapter]) -> None:
        assert issubclass(adapter, BrokerAdapter)

    @pytest.mark.parametrize("adapter", ADAPTERS, ids=_adapter_id)
    def test_it_has_no_abstract_methods_left(self, adapter: type[BrokerAdapter]) -> None:
        assert adapter.__abstractmethods__ == frozenset()

    @pytest.mark.parametrize("adapter", ADAPTERS, ids=_adapter_id)
    def test_no_method_is_left_inherited_from_the_abstract_base(
        self, adapter: type[BrokerAdapter]
    ) -> None:
        # `__abstractmethods__` being empty is not the same thing: a subclass
        # of a subclass inherits concrete methods and would pass that check
        # while defining nothing itself. This asks where each method came from.
        inherited = [
            name for name in ALL_MANDATED if getattr(adapter, name) is getattr(BrokerAdapter, name)
        ]

        assert inherited == [], f"{_path_of(adapter)} still inherits the port's stubs: {inherited}"

    @pytest.mark.parametrize("adapter", ADAPTERS, ids=_adapter_id)
    @pytest.mark.parametrize("capability", CAPABILITIES, ids=lambda proto: proto.__name__)
    def test_it_satisfies_every_capability_protocol(
        self, adapter: type[BrokerAdapter], capability: type
    ) -> None:
        assert issubclass(
            adapter, capability
        ), f"{_path_of(adapter)} does not satisfy {capability.__name__}"


class TestEveryAdapterKeepsThePinnedSignatures:
    @pytest.mark.parametrize("adapter", ADAPTERS, ids=_adapter_id)
    @pytest.mark.parametrize("method", ALL_MANDATED)
    def test_the_signature_is_identical_to_the_ports(
        self, adapter: type[BrokerAdapter], method: str
    ) -> None:
        # Identity, not compatibility. A widened parameter or a renamed keyword
        # is substitutable in principle and a breaking change in practice, because
        # callers written against one adapter are meant to run against another.
        signature = str(inspect.signature(getattr(adapter, method)))

        assert signature == PINNED_SIGNATURES[method], f"{_path_of(adapter)}.{method} has drifted"

    @pytest.mark.parametrize("adapter", ADAPTERS, ids=_adapter_id)
    def test_it_adds_no_public_method_the_port_does_not_declare(
        self, adapter: type[BrokerAdapter]
    ) -> None:
        # An adapter may hold public *attributes* of its own — the mock exposes
        # its venue — but a public method outside the port is an API a caller
        # can reach only by knowing which venue it is talking to.
        declared = {
            name
            for name, member in vars(adapter).items()
            if not name.startswith("_") and inspect.isfunction(member)
        }

        assert declared <= set(
            ALL_MANDATED
        ), f"{_path_of(adapter)} adds {sorted(declared - set(ALL_MANDATED))}"
