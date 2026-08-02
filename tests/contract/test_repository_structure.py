"""Structural contracts for the Atlas repository.

These tests exist because the monorepo's guarantees are structural, not
behavioural. A package that is declared but has no source root, a stray
``atlas/__init__.py`` that silently collapses the PEP 420 namespace, or a
library shipped without ``py.typed`` are all defects that no unit test of
application behaviour would ever catch.
"""

from __future__ import annotations

import importlib
import re
import tomllib
from pathlib import Path
from typing import TYPE_CHECKING

import pytest

import atlas
from atlas.config import Environment

if TYPE_CHECKING:
    from collections.abc import Iterator, Mapping

pytestmark = pytest.mark.contract

REPO_ROOT = Path(__file__).resolve().parents[2]

REQUIRED_ROOT_FILES = (
    ".dockerignore",
    ".editorconfig",
    ".env.example",
    ".gitattributes",
    ".gitignore",
    ".pre-commit-config.yaml",
    "docker-compose.yml",
    "Dockerfile",
    "LICENSE",
    "mypy.ini",
    "poetry.lock",
    "pyproject.toml",
    "pytest.ini",
    "README.md",
    "ruff.toml",
)

REQUIRED_DIRECTORIES = (
    "apps",
    "packages",
    "config",
    "docs/adr",
    "docs/architecture",
    "docs/api",
    "docs/runbooks",
    "docs/operations",
    "infrastructure/docker",
    "infrastructure/database",
    "infrastructure/monitoring",
    "infrastructure/deployment",
    "scripts",
    "tests/unit",
    "tests/integration",
    "tests/contract",
    "tests/e2e",
    ".github/workflows",
)


def _pyproject() -> dict[str, object]:
    with (REPO_ROOT / "pyproject.toml").open("rb") as handle:
        return tomllib.load(handle)


def _declared_source_roots() -> list[Path]:
    """Source roots declared in ``[tool.poetry].packages``."""
    tool = _pyproject()["tool"]
    assert isinstance(tool, dict)
    poetry = tool["poetry"]
    assert isinstance(poetry, dict)
    entries = poetry["packages"]
    assert isinstance(entries, list)
    roots: list[Path] = []
    for entry in entries:
        assert isinstance(entry, dict)
        roots.append(REPO_ROOT / str(entry["from"]))
    return roots


def _leaf_modules(root: Path) -> Iterator[str]:
    """Yield the dotted module name of every package under a source root."""
    for init in sorted((root / "atlas").rglob("__init__.py")):
        yield ".".join(init.parent.relative_to(root).parts)


SECRET_KEY_MARKERS = ("password", "secret", "token", "credential", "api_key", "private")


def _secret_bearing_keys(document: Mapping[str, object], prefix: str = "") -> Iterator[str]:
    """Yield dotted paths of keys that look like a credential and hold a value.

    A comment mentioning a password is fine; a *key* holding one is not. Only
    populated values are reported, so an explicit empty placeholder does not
    trip the check.
    """
    for key, value in document.items():
        path = f"{prefix}{key}"
        if isinstance(value, dict):
            yield from _secret_bearing_keys(value, prefix=f"{path}.")
        elif any(marker in key.lower() for marker in SECRET_KEY_MARKERS) and value:
            yield path


SOURCE_ROOTS = _declared_source_roots()
LEAF_MODULES = sorted({module for root in SOURCE_ROOTS for module in _leaf_modules(root)})

QUALITY_TOOLS = frozenset({"ruff", "black", "mypy", "pytest"})

CI_WORKFLOW = REPO_ROOT / ".github" / "workflows" / "ci.yml"
QUALITY_SH = REPO_ROOT / "scripts" / "quality.sh"
QUALITY_PS1 = REPO_ROOT / "scripts" / "quality.ps1"

# `poetry run <tool>` in shell and YAML; `@('run', '<tool>', ...)` in PowerShell.
_POETRY_RUN = re.compile(r"poetry run (\w+)")
_POWERSHELL_RUN = re.compile(r"'run',\s*'(\w+)'")

_POETRY_VERSION_IN_DOCKERFILE = re.compile(r"^ARG POETRY_VERSION=(\S+)", re.MULTILINE)
_POETRY_VERSION_IN_WORKFLOW = re.compile(r'^\s*POETRY_VERSION:\s*"?([^"\s]+)"?', re.MULTILINE)
_CORE_IMAGE_TAG_IN_COMPOSE = re.compile(r"^\s*image:\s*atlas/atlas-core:(\S+)", re.MULTILINE)


def _tool_order(path: Path, pattern: re.Pattern[str]) -> list[str]:
    """Return the quality tools a file invokes, in first-invocation order.

    Repeat invocations are collapsed, because ``--fix`` mode runs Ruff and Black
    a second time; what is being compared is which tools run and in what order,
    not how many times.
    """
    seen: list[str] = []
    for match in pattern.finditer(path.read_text(encoding="utf-8")):
        tool = match.group(1)
        if tool in QUALITY_TOOLS and tool not in seen:
            seen.append(tool)
    return seen


def _sole_match(pattern: re.Pattern[str], path: Path) -> str:
    matches = pattern.findall(path.read_text(encoding="utf-8"))
    assert matches, f"{pattern.pattern} matched nothing in {path.name}"
    assert len(set(matches)) == 1, f"{path.name} declares conflicting values: {matches}"
    return str(matches[0])


class TestRepositoryLayout:
    @pytest.mark.parametrize("filename", REQUIRED_ROOT_FILES)
    def test_required_root_file_exists(self, filename: str) -> None:
        assert (REPO_ROOT / filename).is_file()

    @pytest.mark.parametrize("directory", REQUIRED_DIRECTORIES)
    def test_required_directory_exists(self, directory: str) -> None:
        assert (REPO_ROOT / directory).is_dir()

    def test_at_least_one_source_root_is_declared(self) -> None:
        assert SOURCE_ROOTS


class TestPackageDeclarations:
    @pytest.mark.parametrize("root", SOURCE_ROOTS, ids=lambda path: path.name)
    def test_declared_source_root_exists(self, root: Path) -> None:
        assert root.is_dir(), f"{root} is declared in pyproject.toml but does not exist"

    @pytest.mark.parametrize("root", SOURCE_ROOTS, ids=lambda path: path.name)
    def test_declared_source_root_carries_the_atlas_namespace(self, root: Path) -> None:
        assert (root / "atlas").is_dir()

    def test_every_package_directory_is_declared(self) -> None:
        on_disk = {path.name for path in (REPO_ROOT / "packages").iterdir() if path.is_dir()}
        declared = {root.parent.name for root in SOURCE_ROOTS}
        assert on_disk <= declared, f"undeclared packages: {sorted(on_disk - declared)}"

    def test_every_app_directory_is_declared(self) -> None:
        on_disk = {path.name for path in (REPO_ROOT / "apps").iterdir() if path.is_dir()}
        declared = {root.parent.name for root in SOURCE_ROOTS}
        assert on_disk <= declared, f"undeclared apps: {sorted(on_disk - declared)}"


class TestNamespaceIntegrity:
    @pytest.mark.parametrize("root", SOURCE_ROOTS, ids=lambda path: path.name)
    def test_namespace_root_has_no_initialiser(self, root: Path) -> None:
        # An __init__.py here would make `atlas` a regular package in one
        # distribution and shadow every other source root at import time.
        assert not (root / "atlas" / "__init__.py").exists()

    def test_the_apps_namespace_level_has_no_initialiser(self) -> None:
        for root in SOURCE_ROOTS:
            apps_namespace = root / "atlas" / "apps"
            if apps_namespace.is_dir():
                assert not (apps_namespace / "__init__.py").exists()

    def test_the_namespace_spans_every_declared_source_root(self) -> None:
        assert len(list(atlas.__path__)) == len(SOURCE_ROOTS)


class TestPackageContracts:
    @pytest.mark.parametrize("module", LEAF_MODULES)
    def test_package_is_importable(self, module: str) -> None:
        assert importlib.import_module(module) is not None

    @pytest.mark.parametrize("module", LEAF_MODULES)
    def test_package_is_documented(self, module: str) -> None:
        docstring = importlib.import_module(module).__doc__
        assert docstring is not None
        assert docstring.strip(), f"{module} has an empty module docstring"

    @pytest.mark.parametrize("module", LEAF_MODULES)
    def test_package_declares_its_public_surface(self, module: str) -> None:
        assert hasattr(importlib.import_module(module), "__all__")

    @pytest.mark.parametrize("module", LEAF_MODULES)
    def test_package_ships_a_py_typed_marker(self, module: str) -> None:
        imported = importlib.import_module(module)
        locations = list(getattr(imported, "__path__", []))
        assert locations, f"{module} is not a package"
        assert (Path(locations[0]) / "py.typed").is_file()


class TestToolchainParity:
    """The local gate and CI must run the same checks in the same order.

    A local gate weaker than CI is worse than no local gate: it teaches you to
    trust a green run that means nothing. These tests read the actual files, so
    the guarantee cannot rot into a stale comment.
    """

    def test_ci_runs_the_full_quality_gate(self) -> None:
        assert _tool_order(CI_WORKFLOW, _POETRY_RUN) == ["ruff", "black", "mypy", "pytest"]

    def test_the_shell_gate_matches_ci(self) -> None:
        assert _tool_order(QUALITY_SH, _POETRY_RUN) == _tool_order(CI_WORKFLOW, _POETRY_RUN)

    def test_the_powershell_gate_matches_ci(self) -> None:
        assert _tool_order(QUALITY_PS1, _POWERSHELL_RUN) == _tool_order(CI_WORKFLOW, _POETRY_RUN)

    def test_the_tool_order_extractor_can_actually_fire(self) -> None:
        # Proves the parity tests above are comparing something real rather than
        # two empty lists produced by a regex that stopped matching.
        assert _tool_order(CI_WORKFLOW, _POETRY_RUN)
        assert _tool_order(QUALITY_PS1, _POWERSHELL_RUN)
        assert _tool_order(QUALITY_SH, _POWERSHELL_RUN) == []

    def test_the_compose_image_tag_matches_the_project_version(self) -> None:
        # Two hand-maintained copies of one number drift the moment either is
        # bumped alone; pyproject.toml is the source of truth.
        project = _pyproject()["project"]
        assert isinstance(project, dict)
        tag = _sole_match(_CORE_IMAGE_TAG_IN_COMPOSE, REPO_ROOT / "docker-compose.yml")
        assert tag == project["version"]

    def test_the_image_and_ci_pin_the_same_poetry(self) -> None:
        # poetry.lock records the version that generated it; a builder on an
        # older Poetry can reject the lock outright.
        image = _sole_match(_POETRY_VERSION_IN_DOCKERFILE, REPO_ROOT / "Dockerfile")
        assert image == _sole_match(_POETRY_VERSION_IN_WORKFLOW, CI_WORKFLOW)


class TestConfigurationTree:
    def test_the_default_layer_exists(self) -> None:
        assert (REPO_ROOT / "config" / "default").is_dir()

    @pytest.mark.parametrize("environment", list(Environment), ids=lambda env: env.value)
    def test_every_environment_has_a_layer(self, environment: Environment) -> None:
        assert (REPO_ROOT / "config" / environment.value).is_dir()

    @pytest.mark.parametrize("environment", list(Environment), ids=lambda env: env.value)
    def test_every_layer_is_populated(self, environment: Environment) -> None:
        layer = REPO_ROOT / "config" / environment.value
        assert list(layer.glob("*.toml")), f"{layer} contains no TOML"

    def test_the_credential_detector_can_actually_fire(self) -> None:
        # A scanner that never fires reports green while checking nothing.
        planted = {
            "postgres": {"password": "hunter2", "user": "atlas"},
            "note": "password rotation is documented in the runbook",
            "redis": {"password": ""},
        }
        assert list(_secret_bearing_keys(planted)) == ["postgres.password"]

    def test_no_committed_layer_carries_a_credential(self) -> None:
        offenders: list[str] = []
        for path in sorted((REPO_ROOT / "config").rglob("*.toml")):
            with path.open("rb") as handle:
                document = tomllib.load(handle)
            offenders.extend(f"{path.name}:{key}" for key in _secret_bearing_keys(document))
        assert not offenders, f"credentials must never be committed: {offenders}"
