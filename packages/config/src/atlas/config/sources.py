"""A layered TOML settings source for pydantic-settings.

Files are merged deepest-layer-last: every ``*.toml`` in ``config/default/`` is
merged in filename order, then every ``*.toml`` in ``config/<environment>/``
overlays it. The resulting mapping is registered *below* the environment
variable sources, so process environment always wins over files on disk.
"""

from __future__ import annotations

import tomllib
from typing import TYPE_CHECKING, Any

from pydantic_settings import PydanticBaseSettingsSource

from atlas.config.errors import ConfigurationError

if TYPE_CHECKING:
    from collections.abc import Sequence
    from pathlib import Path

    from pydantic.fields import FieldInfo
    from pydantic_settings import BaseSettings

__all__ = ["LayeredTomlSource", "deep_merge", "load_layer"]

_FIELD_VALUE_UNSUPPORTED = (
    "LayeredTomlSource materialises every layer in __call__; per-field resolution is not used."
)


def deep_merge(base: dict[str, Any], overlay: dict[str, Any]) -> dict[str, Any]:
    """Recursively merge *overlay* into *base* without mutating either.

    Nested mappings are merged key by key; every other value, including lists,
    is replaced wholesale by the overlay.

    Args:
        base: The lower-precedence mapping.
        overlay: The higher-precedence mapping.

    Returns:
        A new mapping containing the merged result.
    """
    merged = dict(base)
    for key, value in overlay.items():
        existing = merged.get(key)
        if isinstance(existing, dict) and isinstance(value, dict):
            merged[key] = deep_merge(existing, value)
        else:
            merged[key] = value
    return merged


def load_layer(directory: Path) -> dict[str, Any]:
    """Merge every ``*.toml`` file in *directory*, in filename order.

    Args:
        directory: Layer directory. A missing directory yields an empty layer.

    Returns:
        The merged contents of the layer.

    Raises:
        ConfigurationError: If a file in the layer is not valid TOML.
    """
    merged: dict[str, Any] = {}
    if not directory.is_dir():
        return merged
    for path in sorted(directory.glob("*.toml")):
        try:
            with path.open("rb") as handle:
                document = tomllib.load(handle)
        except tomllib.TOMLDecodeError as exc:
            msg = f"{path!s} is not valid TOML: {exc}"
            raise ConfigurationError(msg) from exc
        merged = deep_merge(merged, document)
    return merged


class LayeredTomlSource(PydanticBaseSettingsSource):
    """Settings source that reads an ordered list of TOML layer directories."""

    def __init__(self, settings_cls: type[BaseSettings], layers: Sequence[Path]) -> None:
        """Initialise the source.

        Args:
            settings_cls: The settings class this source feeds.
            layers: Layer directories, lowest precedence first.
        """
        super().__init__(settings_cls)
        self._layers = tuple(layers)

    @property
    def layers(self) -> tuple[Path, ...]:
        """The layer directories this source reads, lowest precedence first."""
        return self._layers

    def get_field_value(self, field: FieldInfo, field_name: str) -> tuple[Any, str, bool]:
        """Unused. The whole document is materialised by :meth:`__call__`.

        Args:
            field: Unused.
            field_name: Unused.

        Raises:
            NotImplementedError: Always.
        """
        raise NotImplementedError(_FIELD_VALUE_UNSUPPORTED)

    def __call__(self) -> dict[str, Any]:
        """Merge all configured layers.

        Returns:
            The merged configuration document.
        """
        document: dict[str, Any] = {}
        for layer in self._layers:
            document = deep_merge(document, load_layer(layer))
        return document

    def __repr__(self) -> str:
        """Return a debugging representation naming the layers in order."""
        rendered = ", ".join(str(layer) for layer in self._layers)
        return f"{type(self).__name__}(layers=[{rendered}])"
