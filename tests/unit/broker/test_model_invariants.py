"""Cross-cutting invariants that every broker domain model must satisfy.

Written once and parametrised over the models rather than repeated per module,
so a model added later is covered the moment it is exported.
"""

from __future__ import annotations

import ast
import inspect
from pathlib import Path
from typing import TYPE_CHECKING, Any

import pytest
from pydantic import BaseModel, ValidationError

from atlas.broker import models as models_package
from atlas.broker.models import (
    Account,
    Candle,
    Connection,
    Execution,
    Order,
    Position,
    Symbol,
    Tick,
)

if TYPE_CHECKING:
    from collections.abc import Iterator

pytestmark = pytest.mark.unit

MODEL_CLASSES: tuple[type[BaseModel], ...] = (
    Account,
    Candle,
    Connection,
    Execution,
    Order,
    Position,
    Symbol,
    Tick,
)

PACKAGE_DIR = Path(inspect.getfile(models_package)).parent

# Nothing outside this set may be imported by the domain model layer. A broker
# SDK appearing here is the failure this test exists to prevent.
PERMITTED_IMPORT_ROOTS = frozenset(
    {
        "__future__",
        "datetime",
        "decimal",
        "enum",
        "typing",
        "pydantic",
        "atlas",
    }
)

FORBIDDEN_IMPORT_ROOTS = frozenset(
    {
        "MetaTrader5",
        "mt5",
        "ccxt",
        "ib_insync",
        "oandapyV20",
        "requests",
        "httpx",
        "aiohttp",
        "socket",
        "asyncio",
        "sqlalchemy",
        "psycopg",
        "redis",
    }
)


def _imported_roots(path: Path) -> Iterator[str]:
    """Yield the top-level module of every import in a source file."""
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                yield alias.name.split(".")[0]
        elif isinstance(node, ast.ImportFrom) and node.module is not None:
            yield node.module.split(".")[0]


SOURCE_FILES = sorted(PACKAGE_DIR.glob("*.py"))


def _model_fixture(model_class: type[BaseModel], request: pytest.FixtureRequest) -> BaseModel:
    """Resolve the valid specimen fixture that matches a model class."""
    instance = request.getfixturevalue(model_class.__name__.lower())
    assert isinstance(instance, model_class)
    return instance


class TestCoverage:
    def test_every_exported_model_is_under_test(self) -> None:
        # Without this, adding a ninth model would quietly opt it out of every
        # invariant below.
        exported = {
            getattr(models_package, name)
            for name in models_package.__all__
            if isinstance(getattr(models_package, name), type)
            and issubclass(getattr(models_package, name), BaseModel)
        }

        assert exported == set(MODEL_CLASSES)

    def test_the_package_exports_what_it_declares(self) -> None:
        for name in models_package.__all__:
            assert hasattr(models_package, name), f"{name} is declared but not exported"


class TestImmutability:
    @pytest.mark.parametrize("model_class", MODEL_CLASSES, ids=lambda cls: cls.__name__)
    def test_the_model_is_frozen(
        self, model_class: type[BaseModel], request: pytest.FixtureRequest
    ) -> None:
        model = _model_fixture(model_class, request)
        field_name = next(iter(model_class.model_fields))

        with pytest.raises(ValidationError) as caught:
            setattr(model, field_name, getattr(model, field_name))

        assert caught.value.errors()[0]["type"] == "frozen_instance"

    @pytest.mark.parametrize("model_class", MODEL_CLASSES, ids=lambda cls: cls.__name__)
    def test_the_model_is_hashable(
        self, model_class: type[BaseModel], request: pytest.FixtureRequest
    ) -> None:
        # Frozen models are safe to use as dictionary keys and set members,
        # which is what lets callers share them without defensive copying.
        model = _model_fixture(model_class, request)

        assert len({model, model}) == 1

    @pytest.mark.parametrize("model_class", MODEL_CLASSES, ids=lambda cls: cls.__name__)
    def test_equality_is_by_value(
        self, model_class: type[BaseModel], request: pytest.FixtureRequest
    ) -> None:
        model = _model_fixture(model_class, request)
        twin = model_class.model_validate(model.model_dump())

        assert twin == model
        assert twin is not model

    @pytest.mark.parametrize("model_class", MODEL_CLASSES, ids=lambda cls: cls.__name__)
    def test_model_copy_with_an_update_bypasses_validation(
        self, model_class: type[BaseModel], request: pytest.FixtureRequest
    ) -> None:
        # Pinned because it is a trap, not a feature: `model_copy(update=...)`
        # writes the value straight in. Callers making a state transition must
        # go through `model_validate`, and the README says so.
        model = _model_fixture(model_class, request)
        field_name = next(iter(model_class.model_fields))
        sentinel = object()

        mutated = model.model_copy(update={field_name: sentinel})

        assert getattr(mutated, field_name) is sentinel


class TestStrictness:
    @pytest.mark.parametrize("model_class", MODEL_CLASSES, ids=lambda cls: cls.__name__)
    def test_an_unknown_field_is_rejected(
        self, model_class: type[BaseModel], request: pytest.FixtureRequest
    ) -> None:
        model = _model_fixture(model_class, request)
        payload = {**model.model_dump(), "not_a_real_field": 1}

        with pytest.raises(ValidationError, match="Extra inputs are not permitted"):
            model_class.model_validate(payload)

    @pytest.mark.parametrize("model_class", MODEL_CLASSES, ids=lambda cls: cls.__name__)
    def test_a_missing_required_field_is_rejected(
        self, model_class: type[BaseModel], request: pytest.FixtureRequest
    ) -> None:
        model = _model_fixture(model_class, request)
        required = [name for name, field in model_class.model_fields.items() if field.is_required()]
        assert required, f"{model_class.__name__} has no required fields"
        payload = model.model_dump()
        del payload[required[0]]

        with pytest.raises(ValidationError, match="Field required"):
            model_class.model_validate(payload)

    @pytest.mark.parametrize("model_class", MODEL_CLASSES, ids=lambda cls: cls.__name__)
    def test_no_field_is_typed_as_any(self, model_class: type[BaseModel]) -> None:
        for name, field in model_class.model_fields.items():
            assert field.annotation is not Any, f"{model_class.__name__}.{name} is Any"

    @pytest.mark.parametrize("model_class", MODEL_CLASSES, ids=lambda cls: cls.__name__)
    def test_every_field_is_annotated(self, model_class: type[BaseModel]) -> None:
        for name, field in model_class.model_fields.items():
            assert field.annotation is not None, f"{model_class.__name__}.{name} is unannotated"


class TestSerialisation:
    @pytest.mark.parametrize("model_class", MODEL_CLASSES, ids=lambda cls: cls.__name__)
    def test_json_round_trip_is_lossless(
        self, model_class: type[BaseModel], request: pytest.FixtureRequest
    ) -> None:
        model = _model_fixture(model_class, request)

        assert model_class.model_validate_json(model.model_dump_json()) == model

    @pytest.mark.parametrize("model_class", MODEL_CLASSES, ids=lambda cls: cls.__name__)
    def test_python_round_trip_is_lossless(
        self, model_class: type[BaseModel], request: pytest.FixtureRequest
    ) -> None:
        model = _model_fixture(model_class, request)

        assert model_class.model_validate(model.model_dump()) == model

    @pytest.mark.parametrize("model_class", MODEL_CLASSES, ids=lambda cls: cls.__name__)
    def test_a_json_schema_can_be_generated(self, model_class: type[BaseModel]) -> None:
        schema = model_class.model_json_schema()

        assert schema["title"] == model_class.__name__
        assert set(schema["properties"]) == set(model_class.model_fields)


class TestDocumentation:
    @pytest.mark.parametrize("model_class", MODEL_CLASSES, ids=lambda cls: cls.__name__)
    def test_the_model_is_documented(self, model_class: type[BaseModel]) -> None:
        assert model_class.__doc__
        assert model_class.__doc__.strip()

    @pytest.mark.parametrize("path", SOURCE_FILES, ids=lambda path: path.name)
    def test_the_module_is_documented(self, path: Path) -> None:
        assert ast.get_docstring(ast.parse(path.read_text(encoding="utf-8")))

    def test_the_package_ships_a_readme(self) -> None:
        readme = PACKAGE_DIR / "README.md"

        assert readme.is_file()
        assert readme.read_text(encoding="utf-8").strip()

    def test_the_package_ships_a_py_typed_marker(self) -> None:
        assert (PACKAGE_DIR / "py.typed").is_file()


class TestBrokerIndependence:
    """The layer must not acquire a dependency on any venue or transport.

    This is the constraint that makes the models reusable across adapters. It
    is enforced by reading the source rather than by convention, because the
    day someone imports a broker SDK "just for a type hint" is the day the
    contract stops being a contract.
    """

    def test_the_import_scanner_finds_something(self) -> None:
        # A scanner returning nothing would pass every test below while
        # checking no source at all.
        assert SOURCE_FILES
        found = {root for path in SOURCE_FILES for root in _imported_roots(path)}
        assert "pydantic" in found

    @pytest.mark.parametrize("path", SOURCE_FILES, ids=lambda path: path.name)
    def test_no_module_imports_outside_the_permitted_set(self, path: Path) -> None:
        offenders = sorted(set(_imported_roots(path)) - PERMITTED_IMPORT_ROOTS)

        assert not offenders, f"{path.name} imports {offenders}"

    @pytest.mark.parametrize("path", SOURCE_FILES, ids=lambda path: path.name)
    def test_no_module_imports_a_broker_sdk_or_transport(self, path: Path) -> None:
        offenders = sorted(set(_imported_roots(path)) & FORBIDDEN_IMPORT_ROOTS)

        assert not offenders, f"{path.name} imports {offenders}"

    @pytest.mark.parametrize("path", SOURCE_FILES, ids=lambda path: path.name)
    def test_no_module_depends_on_another_atlas_package(self, path: Path) -> None:
        # `atlas` is permitted only for this package's own modules; a
        # dependency on atlas.config or atlas.risk would invert the layering.
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        atlas_imports = [
            node.module
            for node in ast.walk(tree)
            if isinstance(node, ast.ImportFrom)
            and node.module is not None
            and node.module.startswith("atlas")
        ]

        for module in atlas_imports:
            assert module.startswith("atlas.broker.models"), f"{path.name} imports {module}"

    def test_the_forbidden_and_permitted_sets_do_not_overlap(self) -> None:
        assert not (PERMITTED_IMPORT_ROOTS & FORBIDDEN_IMPORT_ROOTS)
