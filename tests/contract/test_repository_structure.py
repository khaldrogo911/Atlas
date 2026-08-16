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

COMPOSE_FILE = REPO_ROOT / "docker-compose.yml"
ENV_TEMPLATE = REPO_ROOT / ".env.example"

#: The four values a trading session cannot be established without. ADR-0015
#: made start-up construct the adapter they describe, so a process without them
#: exits 2 rather than starting.
BROKER_VARIABLES = (
    "ATLAS_BROKER__LOGIN",
    "ATLAS_BROKER__PASSWORD",
    "ATLAS_BROKER__SERVER",
    "ATLAS_BROKER__TERMINAL_PATH",
)


#: Names of the three steps that run the built image. Read by step rather than
#: by whole file: all three pass ``ATLAS_BROKER__PASSWORD``, so a file-wide
#: search cannot tell which one dropped a value.
#:
#: ``RECORD_STEP`` exists because ADR-0017 moved the startup record out of the
#: reach of a Linux container: the configured check now ends at a session it
#: cannot open. The record's shape is still proved in the image, one step short
#: of the venue.
CONFIGURED_STEP = "Run the image start-up check with broker configuration"
RECORD_STEP = "Verify the image still builds its startup record"
UNCONFIGURED_STEP = "Run the image self-check without broker configuration"

#: The two steps that hand the image a complete broker section.
CONFIGURED_STEPS = (CONFIGURED_STEP, RECORD_STEP)


def _declared_in_workflow(variable: str) -> str:
    """Return the value the CI workflow declares for an environment variable."""
    pattern = re.compile(rf'^\s*{re.escape(variable)}:\s*"?([^"\n]+?)"?\s*$', re.MULTILINE)
    matches = pattern.findall(CI_WORKFLOW.read_text(encoding="utf-8"))
    assert matches, f"{variable} is not declared in {CI_WORKFLOW.name}"
    return str(matches[0])


def _workflow_step(name: str) -> str:
    """Return the body of one named workflow step, up to the next step."""
    pattern = re.compile(
        rf"^(\s*)- name: {re.escape(name)}$(.*?)(?=^\1- name: |\Z)",
        re.MULTILINE | re.DOTALL,
    )
    match = pattern.search(CI_WORKFLOW.read_text(encoding="utf-8"))
    assert match, f"{CI_WORKFLOW.name} declares no step named {name!r}"
    return match.group(2)


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


class TestBrokerConfigurationIsADeploymentFact:
    """Where the four broker values may come from, and where they may not.

    ATLAS-TASK-0023 made start-up construct the trading adapter, which turned a
    missing broker section from something nobody read into something that stops
    a container. Two places have to supply it and one must never: a default in
    the repository would let a deployment that cannot trade start up looking
    like one that can, which is the failure ADR-0015 rejected a mock fallback
    to avoid.
    """

    @pytest.mark.parametrize("variable", BROKER_VARIABLES)
    def test_compose_requires_the_variable_and_fails_closed(self, variable: str) -> None:
        # `:?` refuses the file and names the value, before anything starts.
        compose = COMPOSE_FILE.read_text(encoding="utf-8")
        assert f"${{{variable}:?" in compose, f"{variable} is not required by compose"

    @pytest.mark.parametrize("variable", BROKER_VARIABLES)
    def test_compose_invents_no_default_for_the_variable(self, variable: str) -> None:
        # `:-` would substitute a credential the repository made up.
        compose = COMPOSE_FILE.read_text(encoding="utf-8")
        assert f"${{{variable}:-" not in compose, f"{variable} has a default in compose"

    @pytest.mark.parametrize("variable", BROKER_VARIABLES)
    def test_the_environment_template_ships_no_value_for_the_variable(self, variable: str) -> None:
        # Commented guidance is the point of the template; a live value in it
        # would be committed configuration for an account nobody owns.
        live = re.compile(rf"^\s*{re.escape(variable)}=(.*)$", re.MULTILINE)
        assert not live.findall(ENV_TEMPLATE.read_text(encoding="utf-8"))

    @pytest.mark.parametrize("step_name", CONFIGURED_STEPS)
    @pytest.mark.parametrize("variable", BROKER_VARIABLES)
    def test_ci_hands_the_variable_to_every_configured_check(
        self, variable: str, step_name: str
    ) -> None:
        # Both steps assert that a value did not leak, and an assertion that a
        # withheld value is absent proves nothing at all.
        step = _workflow_step(step_name)
        assert f"-e {variable}" in step, f"{step_name!r} does not pass {variable}"

    @pytest.mark.parametrize("variable", ["LOGIN", "SERVER", "TERMINAL_PATH"])
    def test_ci_withholds_the_variable_from_the_unconfigured_check(self, variable: str) -> None:
        # The negative check earns its exit code by being short of a session, so
        # it may name the password but nothing that would complete the section.
        step = _workflow_step(UNCONFIGURED_STEP)
        assert f"-e ATLAS_BROKER__{variable}" not in step

    @pytest.mark.parametrize("variable", BROKER_VARIABLES)
    def test_ci_declares_a_usable_value_for_the_variable(self, variable: str) -> None:
        # Stated explicitly rather than left to the empty password and bare path
        # MT5Config still accepts, so closing either gap does not break CI.
        assert _declared_in_workflow(variable).strip()

    def test_the_ci_login_would_survive_the_validation_it_already_faces(self) -> None:
        assert int(_declared_in_workflow("ATLAS_BROKER__LOGIN")) > 0

    def test_ci_proves_a_configured_container_reports_the_session_it_cannot_open(
        self,
    ) -> None:
        # ADR-0017: a configured container on Linux gets as far as the venue and
        # no further. The whole outcome is pinned — the code, the event, and the
        # silence on stdout — because a step that only awaited an exit code
        # would pass just as happily on the wrong failure.
        step = _workflow_step(CONFIGURED_STEP)
        assert '"atlas.core.broker_connect_failed"' in step
        assert "status != 3" in step
        assert "wrote to stdout" in step

    def test_ci_proves_a_configured_container_leaks_no_credential(self) -> None:
        # The step reads both streams, so the check has to be shown to cover
        # both; asserting it against stdout alone would test an empty string.
        step = _workflow_step(CONFIGURED_STEP)
        assert 'os.environ["ATLAS_BROKER__PASSWORD"] in out + err' in step

    def test_ci_still_proves_the_startup_record_inside_the_image(self) -> None:
        # ADR-0017 stopped the entrypoint short of this record on Linux; it did
        # not retire the record. The eight keys and the absence of every broker
        # value stay proved in the image that ships them.
        step = _workflow_step(RECORD_STEP)
        assert '"atlas.core.startup"' in step
        assert "build_startup_record" in step
        assert "the startup record's keys changed" in step
        assert "the startup record carried" in step

    def test_ci_proves_an_unconfigured_container_refuses_to_start(self) -> None:
        # The refusal ADR-0015 decided is observed rather than assumed.
        assert '"atlas.core.startup_failed"' in _workflow_step(UNCONFIGURED_STEP)


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
