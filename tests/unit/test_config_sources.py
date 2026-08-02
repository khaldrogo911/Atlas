"""Unit tests for the layered TOML settings source."""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

from atlas.config import (
    AtlasSettings,
    ConfigurationError,
    LayeredTomlSource,
    deep_merge,
    load_layer,
)

if TYPE_CHECKING:
    from pathlib import Path

pytestmark = pytest.mark.unit


class TestDeepMerge:
    def test_overlay_wins_for_scalars(self) -> None:
        assert deep_merge({"a": 1}, {"a": 2}) == {"a": 2}

    def test_disjoint_keys_are_unioned(self) -> None:
        assert deep_merge({"a": 1}, {"b": 2}) == {"a": 1, "b": 2}

    def test_nested_mappings_merge_key_by_key(self) -> None:
        base = {"pg": {"host": "localhost", "port": 5432}}
        overlay = {"pg": {"port": 6000}}
        assert deep_merge(base, overlay) == {"pg": {"host": "localhost", "port": 6000}}

    def test_lists_are_replaced_not_concatenated(self) -> None:
        assert deep_merge({"a": [1, 2]}, {"a": [3]}) == {"a": [3]}

    def test_inputs_are_not_mutated(self) -> None:
        base = {"pg": {"host": "localhost"}}
        overlay = {"pg": {"host": "db"}}
        deep_merge(base, overlay)
        assert base == {"pg": {"host": "localhost"}}
        assert overlay == {"pg": {"host": "db"}}

    def test_mapping_replaced_by_scalar(self) -> None:
        assert deep_merge({"a": {"b": 1}}, {"a": 5}) == {"a": 5}


class TestLoadLayer:
    def test_missing_directory_yields_empty_layer(self, tmp_path: Path) -> None:
        assert load_layer(tmp_path / "absent") == {}

    def test_directory_without_toml_yields_empty_layer(self, tmp_path: Path) -> None:
        (tmp_path / "notes.md").write_text("ignored", encoding="utf-8")
        assert load_layer(tmp_path) == {}

    def test_files_merge_in_filename_order(self, tmp_path: Path) -> None:
        (tmp_path / "10-base.toml").write_text('name = "first"\nkept = 1\n', encoding="utf-8")
        (tmp_path / "20-over.toml").write_text('name = "second"\n', encoding="utf-8")
        assert load_layer(tmp_path) == {"name": "second", "kept": 1}

    def test_invalid_toml_is_reported_with_the_offending_path(self, tmp_path: Path) -> None:
        broken = tmp_path / "broken.toml"
        broken.write_text("this is not = = toml", encoding="utf-8")
        with pytest.raises(ConfigurationError, match=r"broken\.toml"):
            load_layer(tmp_path)


class TestLayeredTomlSource:
    def test_later_layers_override_earlier_ones(self, tmp_path: Path) -> None:
        default = tmp_path / "default"
        override = tmp_path / "development"
        default.mkdir()
        override.mkdir()
        (default / "a.toml").write_text('debug = false\napp_name = "atlas"\n', encoding="utf-8")
        (override / "a.toml").write_text("debug = true\n", encoding="utf-8")

        source = LayeredTomlSource(AtlasSettings, layers=[default, override])

        assert source() == {"debug": True, "app_name": "atlas"}

    def test_no_layers_yields_empty_document(self) -> None:
        assert LayeredTomlSource(AtlasSettings, layers=[])() == {}

    def test_layers_are_exposed_in_precedence_order(self, tmp_path: Path) -> None:
        source = LayeredTomlSource(AtlasSettings, layers=[tmp_path / "a", tmp_path / "b"])
        assert source.layers == (tmp_path / "a", tmp_path / "b")

    def test_repr_names_every_layer(self, tmp_path: Path) -> None:
        source = LayeredTomlSource(AtlasSettings, layers=[tmp_path / "default"])
        assert "LayeredTomlSource" in repr(source)
        assert "default" in repr(source)

    def test_per_field_resolution_is_explicitly_unsupported(self) -> None:
        source = LayeredTomlSource(AtlasSettings, layers=[])
        field = AtlasSettings.model_fields["app_name"]
        with pytest.raises(NotImplementedError):
            source.get_field_value(field, "app_name")
