import json
from pathlib import Path

import pytest

import slidejunction
from slidejunction.layout import (
    BorderStyle,
    Crop,
    DirectColor,
    ElementKind,
    FillMode,
    FocalPoint,
    LayoutDocument,
    MediaFit,
    PlacementMode,
    SlideKind,
    ThemeColor,
    dump_layout,
    parse_layout,
)

_MINIMAL_CANONICAL = """{
  "format_version": 1,
  "theme": {
    "preset": {
      "name": "slidejunction-default",
      "version": 1
    }
  },
  "configurations": {},
  "inline_formats": {}
}
"""


def _preset_container() -> dict[str, object]:
    return {
        "preset": {"name": "slidejunction-default", "version": 1},
    }


def _minimal() -> dict[str, object]:
    return {"format_version": 1, "theme": _preset_container()}


def test_minimal_input_allows_omitted_definition_containers() -> None:
    source = json.dumps(_minimal())

    result = parse_layout(source, path="layout.json")

    assert result.diagnostics == ()
    assert isinstance(result.document, LayoutDocument)
    assert result.document.configurations == {}
    assert result.document.inline_formats == {}
    assert dump_layout(result.document) == _MINIMAL_CANONICAL


@pytest.mark.parametrize(
    "source",
    ["null", "[]", '[{"x": 1, "x": 2}]', '"layout"', "1", "true"],
)
def test_non_object_root_is_structural_error(source: str) -> None:
    result = parse_layout(source, path="relative/layout.json")

    assert result.document is None
    assert _codes(result) == ["invalid-layout-type"]
    location = result.diagnostics[0].config_pointer
    assert location is not None
    assert location.pointer == ""
    assert location.path == Path("relative/layout.json")


@pytest.mark.parametrize("source", ["{", '{"x": NaN}', '{"x": Infinity}'])
def test_malformed_or_nonstandard_json_has_no_document(source: str) -> None:
    result = parse_layout(source)

    assert result.document is None
    assert _codes(result) == ["invalid-layout-json"]
    assert result.diagnostics[0].config_pointer.pointer == ""


def test_nested_duplicate_key_is_rejected_without_last_wins() -> None:
    source = """{
      "format_version": 1,
      "theme": {
        "preset": {"name": "first", "name": "second", "version": 1}
      }
    }"""

    result = parse_layout(source)

    assert result.document is None
    assert _codes(result) == ["duplicate-layout-json-key"]
    assert result.diagnostics[0].config_pointer.pointer == "/theme/preset/name"


@pytest.mark.parametrize(
    "value, pointer, code",
    [
        (
            {"theme": _preset_container()},
            "/format_version",
            "missing-layout-format-version",
        ),
        (
            {"format_version": None, "theme": _preset_container()},
            "/format_version",
            "invalid-layout-type",
        ),
        (
            {"format_version": 2, "theme": _preset_container()},
            "/format_version",
            "unsupported-layout-format-version",
        ),
        ({"format_version": 1}, "/theme", "missing-layout-property"),
        ({"format_version": 1, "theme": None}, "/theme", "invalid-layout-type"),
        (
            {"format_version": 1, "theme": {}},
            "/theme/preset",
            "missing-layout-property",
        ),
        (
            {"format_version": 1, "theme": {"preset": None}},
            "/theme/preset",
            "invalid-layout-type",
        ),
        (
            {"format_version": 1, "theme": {"preset": {"version": 1}}},
            "/theme/preset/name",
            "missing-layout-property",
        ),
        (
            {
                "format_version": 1,
                "theme": {"preset": {"name": "slidejunction-default"}},
            },
            "/theme/preset/version",
            "missing-layout-property",
        ),
        (
            {
                "format_version": 1,
                "theme": {
                    "preset": {
                        "name": "slidejunction-default",
                        "version": True,
                    }
                },
            },
            "/theme/preset/version",
            "invalid-layout-type",
        ),
    ],
)
def test_required_root_and_preset_structure(
    value: dict[str, object], pointer: str, code: str
) -> None:
    result = parse_layout(json.dumps(value))

    assert result.document is None
    assert code in _codes(result)
    matching = [item for item in result.diagnostics if item.code == code]
    assert matching[0].config_pointer.pointer == pointer


@pytest.mark.parametrize(
    "preset, code",
    [
        ({"name": "future-preset", "version": 1}, "unknown-theme-preset"),
        (
            {"name": "slidejunction-default", "version": 2},
            "unsupported-theme-preset-version",
        ),
    ],
)
def test_unknown_or_unsupported_preset_is_preserved(
    preset: dict[str, object], code: str
) -> None:
    value = _minimal()
    value["theme"]["preset"] = preset

    result = parse_layout(json.dumps(value))

    assert result.document is not None
    assert _codes(result) == [code]
    assert result.document.theme.preset.name == preset["name"]
    assert result.document.theme.preset.version == preset["version"]
    assert json.loads(dump_layout(result.document))["theme"]["preset"] == preset


def test_unknown_preset_does_not_cascade_missing_preset_token_diagnostic() -> None:
    value = _minimal()
    value["theme"]["preset"] = {"name": "future-preset", "version": 9}
    value["configurations"] = {
        "3": {"typography": {"color": {"theme": "future-accent"}}}
    }

    result = parse_layout(json.dumps(value))

    assert result.document is not None
    assert _codes(result) == ["unknown-theme-preset"]
    color = result.document.configurations[3].typography.color
    assert color == ThemeColor("future-accent")


def test_missing_and_null_optional_containers_are_distinct() -> None:
    missing = parse_layout(json.dumps(_minimal()))
    value = _minimal()
    value["configurations"] = None
    value["inline_formats"] = None
    explicit_null = parse_layout(json.dumps(value))

    assert missing.document is not None
    assert missing.diagnostics == ()
    assert explicit_null.document is not None
    assert _codes(explicit_null) == ["invalid-layout-type", "invalid-layout-type"]
    assert explicit_null.document.configurations == {}
    assert explicit_null.document.inline_formats == {}


def test_null_local_property_is_diagnosed_and_omitted_not_treated_as_missing() -> None:
    value = _minimal()
    value["configurations"] = {"3": {"size": {"width": None, "height": 25}}}

    result = parse_layout(json.dumps(value))

    assert result.document is not None
    assert _codes(result) == ["invalid-layout-type"]
    size = result.document.configurations[3].size
    assert size.width is None
    assert size.height == 25
    written = json.loads(dump_layout(result.document))
    assert written["configurations"]["3"]["size"] == {"height": 25}


def test_invalid_local_properties_recover_without_dropping_valid_siblings() -> None:
    value = _minimal()
    value["configurations"] = {
        "3": {
            "size": {"width": -1, "height": 25},
            "transform": {"rotation": True},
            "appearance": {"opacity": 0.5},
            "unexpected": 1,
        }
    }

    result = parse_layout(json.dumps(value))

    assert result.document is not None
    assert _codes(result) == [
        "config-number-out-of-range",
        "invalid-layout-type",
        "unknown-layout-property",
    ]
    configuration = result.document.configurations[3]
    assert configuration.size.width is None
    assert configuration.size.height == 25
    assert configuration.transform.rotation is None
    assert configuration.appearance.opacity == 0.5


@pytest.mark.parametrize(
    "atomic_property, atomic_value, code",
    [
        ("crop", {"x": -1, "width": 50}, "config-number-out-of-range"),
        ("crop", {"x": None}, "invalid-layout-type"),
        ("crop", {"x": 100}, "config-number-out-of-range"),
        ("crop", {"x": 80, "width": 30}, "config-number-out-of-range"),
        ("focal_point", {"x": -1, "y": 50}, "config-number-out-of-range"),
        ("focal_point", {"x": "left"}, "invalid-layout-type"),
        ("focal_point", {"x": 101}, "config-number-out-of-range"),
    ],
)
def test_invalid_atomic_media_value_is_rejected_but_media_sibling_is_retained(
    atomic_property: str,
    atomic_value: dict[str, object],
    code: str,
) -> None:
    value = _minimal()
    value["configurations"] = {
        "3": {"media": {"fit": "cover", atomic_property: atomic_value}}
    }

    result = parse_layout(json.dumps(value))

    assert result.document is not None
    assert _codes(result) == [code]
    media = result.document.configurations[3].media
    assert media.fit is MediaFit.COVER
    assert getattr(media, atomic_property) is None
    written_media = json.loads(dump_layout(result.document))["configurations"]["3"][
        "media"
    ]
    assert written_media == {"fit": "cover"}


def test_missing_atomic_members_are_valid_sparse_values() -> None:
    value = _minimal()
    value["configurations"] = {
        "3": {"media": {"crop": {"x": 10}, "focal_point": {"x": 50}}}
    }

    result = parse_layout(json.dumps(value))

    assert result.document is not None
    assert result.diagnostics == ()
    media = result.document.configurations[3].media
    assert media.crop == Crop(x=10)
    assert media.focal_point == FocalPoint(x=50)


@pytest.mark.parametrize("atomic_property", ["crop", "focal_point"])
def test_unknown_atomic_property_rejects_only_that_value_object(
    atomic_property: str,
) -> None:
    value = _minimal()
    value["configurations"] = {
        "3": {
            "media": {
                "fit": "contain",
                atomic_property: {"x": 10, "unexpected": 1},
            }
        }
    }

    result = parse_layout(json.dumps(value))

    assert result.document is not None
    assert _codes(result) == ["unknown-layout-property"]
    media = result.document.configurations[3].media
    assert getattr(media, atomic_property) is None
    assert media.fit is MediaFit.CONTAIN
    written_media = json.loads(dump_layout(result.document))["configurations"]["3"][
        "media"
    ]
    assert written_media == {"fit": "contain"}


def test_non_finite_and_out_of_range_numbers_use_stable_codes() -> None:
    source = """{
      "format_version": 1,
      "theme": {"preset": {"name": "slidejunction-default", "version": 1}},
      "configurations": {
        "3": {
          "size": {"width": 1e400, "height": 0},
          "appearance": {"opacity": 2}
        }
      }
    }"""

    result = parse_layout(source)

    assert result.document is not None
    assert _codes(result) == [
        "config-number-out-of-range",
        "config-number-out-of-range",
        "non-finite-config-number",
    ]


def test_lowercase_direct_colors_are_canonicalized_without_mutating_source(
    tmp_path: Path,
) -> None:
    value = _minimal()
    value["theme"]["colors"] = {"warning": "#ff3b30"}
    value["configurations"] = {"3": {"typography": {"color": "#aabbcc"}}}
    source = json.dumps(value, indent=4)
    path = tmp_path / "layout.json"
    original_file = "This file must not be read or rewritten.\n"
    path.write_text(original_file, encoding="utf-8")

    result = parse_layout(source, path=path)

    assert result.document is not None
    assert result.diagnostics == ()
    assert result.document.theme.colors["warning"] == DirectColor("#FF3B30")
    assert result.document.configurations[3].typography.color == DirectColor("#AABBCC")
    assert source == json.dumps(value, indent=4)
    assert path.read_text(encoding="utf-8") == original_file
    assert "#AABBCC" in dump_layout(result.document)


@pytest.mark.parametrize("color", ["red", "rgb(255, 0, 0)", "#11223344"])
def test_layout_loader_rejects_color_names_rgb_and_alpha_hex(color: str) -> None:
    value = _minimal()
    value["configurations"] = {"3": {"typography": {"color": color}}}

    result = parse_layout(json.dumps(value))

    assert result.document is not None
    assert _codes(result) == ["invalid-color-value"]
    assert result.document.configurations[3].typography.color is None


def test_null_color_is_invalid_type_and_extra_color_property_is_ignored() -> None:
    value = _minimal()
    value["configurations"] = {
        "3": {
            "typography": {"color": None},
            "appearance": {
                "fill": {"color": {"theme": "accent-1", "unexpected": True}}
            },
        }
    }

    result = parse_layout(json.dumps(value))

    assert result.document is not None
    assert _codes(result) == ["unknown-layout-property", "invalid-layout-type"]
    configuration = result.document.configurations[3]
    assert configuration.typography.color is None
    assert configuration.appearance.fill.color == ThemeColor("accent-1")


def test_enum_values_are_exact_canonical_strings() -> None:
    value = _minimal()
    value["configurations"] = {
        "3": {
            "placement": {"mode": "flow"},
            "typography": {"font_weight": "Bold"},
            "appearance": {
                "fill": {"mode": "gradient"},
                "border": {"style": "double"},
                "shadow": {"mode": "inner"},
            },
            "media": {"fit": "scale-down"},
            "code": {"theme": "solarized"},
        }
    }

    result = parse_layout(json.dumps(value))

    assert result.document is not None
    assert _codes(result) == ["invalid-config-enum"] * 7


def test_color_token_names_and_missing_tokens_are_validated() -> None:
    value = _minimal()
    value["theme"]["colors"] = {"Bad_Name": "#112233"}
    value["configurations"] = {
        "3": {
            "typography": {"color": {"theme": "missing-token"}},
            "appearance": {"fill": {"color": {"theme": "Bad_Name"}}},
        }
    }

    result = parse_layout(json.dumps(value))

    assert result.document is not None
    assert _codes(result) == [
        "invalid-theme-color-token-name",
        "missing-theme-color-token",
        "invalid-theme-color-token-name",
    ]


def test_invalid_ref_keys_and_inline_forbidden_properties_are_ignored() -> None:
    value = _minimal()
    value["configurations"] = {"03": {}, "3": {}}
    value["inline_formats"] = {
        "8": {
            "placement": {"mode": "free", "x": 1, "y": 2},
            "typography": {"font_size": 18, "text_align": "center"},
        }
    }

    result = parse_layout(json.dumps(value))

    assert result.document is not None
    assert tuple(result.document.configurations) == (3,)
    assert _codes(result) == [
        "invalid-ref-key",
        "property-not-allowed-in-inline-format",
        "property-not-allowed-in-inline-format",
    ]
    inline = result.document.inline_formats[8]
    assert inline.typography.font_size == 18
    assert not hasattr(inline.typography, "text_align")


def test_cross_namespace_ref_validation_is_deferred_to_milestone_3() -> None:
    value = _minimal()
    value["configurations"] = {"3": {}}
    value["inline_formats"] = {"3": {}}

    result = parse_layout(json.dumps(value))

    assert result.document is not None
    assert result.diagnostics == ()
    assert 3 in result.document.configurations
    assert 3 in result.document.inline_formats


def test_full_configuration_round_trips_through_canonical_model() -> None:
    value = {
        "format_version": 1,
        "theme": {
            "preset": {"name": "slidejunction-default", "version": 1},
            "colors": {"warning": "#ff3b30"},
            "slide": {"appearance": {"fill": {"mode": "solid"}}},
            "elements": {"paragraph": {"typography": {"font_size": 24}}},
            "roles": {"slide-title": {"typography": {"font_weight": "bold"}}},
            "slides": {
                "h1": {
                    "self": {"appearance": {"opacity": 1}},
                    "elements": {"image-block": {"size": {"width": 50}}},
                    "roles": {
                        "slide-title": {
                            "typography": {
                                "font_size": 48,
                                "color": "#ffffff",
                            }
                        }
                    },
                }
            },
        },
        "configurations": {
            "7": {
                "placement": {"mode": "free", "x": 20, "y": 25},
                "size": {"width": 45, "height": 30},
                "transform": {"rotation": -25},
                "typography": {
                    "font_family": {
                        "latin": "liberation-serif",
                        "japanese": "biz-udgothic",
                    },
                    "font_size": 32,
                    "font_weight": "bold",
                    "font_style": "italic",
                    "color": {"theme": "accent-1"},
                    "underline": False,
                    "strikethrough": "double",
                    "script": "normal",
                    "text_align": "right",
                    "vertical_align": "bottom",
                },
                "text_effects": {"outline": {"color": "#000000", "width": 1.5}},
                "appearance": {
                    "fill": {"mode": "none", "color": "#ffffff", "opacity": 0.8},
                    "border": {"style": "dashed", "color": "#000000", "width": 2},
                    "corner_radius": 8,
                    "opacity": 1,
                    "shadow": {
                        "mode": "drop",
                        "color": "#000000",
                        "opacity": 0.25,
                        "offset_x": -2,
                        "offset_y": 3,
                        "blur": 6,
                    },
                },
                "media": {
                    "aspect_ratio_locked": False,
                    "crop": {"x": 10, "y": 5, "width": 70, "height": 90},
                    "fit": "cover",
                    "focal_point": {"x": 74, "y": 32},
                },
                "stacking": {"z_index": -5},
                "code": {"theme": "dark"},
            }
        },
        "inline_formats": {
            "8": {
                "typography": {
                    "font_size": 18,
                    "color": {"theme": "warning"},
                    "underline": True,
                },
                "text_effects": {"outline": {"width": 1}},
            }
        },
    }

    first = parse_layout(json.dumps(value))
    assert first.document is not None
    assert first.diagnostics == ()
    second = parse_layout(dump_layout(first.document))

    assert second.diagnostics == ()
    assert second.document == first.document
    configuration = first.document.configurations[7]
    assert configuration.placement.mode is PlacementMode.FREE
    assert configuration.appearance.fill.mode is FillMode.NONE
    assert configuration.appearance.border.style is BorderStyle.DASHED
    assert configuration.media.fit is MediaFit.COVER
    assert first.document.theme.elements[ElementKind.PARAGRAPH]
    assert first.document.theme.slides[SlideKind.H1]


def test_writer_cleans_empty_nested_objects_but_preserves_empty_definitions() -> None:
    source = """{
      "format_version": 1,
      "theme": {
        "preset": {"name": "slidejunction-default", "version": 1},
        "slide": {"appearance": {"border": {}}},
        "slides": {"h1": {"self": {}}}
      },
      "configurations": {
        "10": {"size": {}},
        "2": {"appearance": {"opacity": 0}, "stacking": {"z_index": 0}}
      },
      "inline_formats": {"8": {}}
    }"""

    result = parse_layout(source)
    assert result.document is not None
    written = json.loads(dump_layout(result.document))

    assert written["theme"] == {
        "preset": {"name": "slidejunction-default", "version": 1}
    }
    assert list(written["configurations"]) == ["2", "10"]
    assert written["configurations"]["10"] == {}
    assert written["configurations"]["2"] == {
        "appearance": {"opacity": 0},
        "stacking": {"z_index": 0},
    }
    assert written["inline_formats"] == {"8": {}}


def test_json_pointer_escaping_and_diagnostic_order_are_deterministic() -> None:
    value = _minimal()
    value["configurations"] = {
        "3": {"z-last": 1, "a/b~c": 2},
    }

    result = parse_layout(json.dumps(value), path="layout.json")

    assert [item.config_pointer.pointer for item in result.diagnostics] == [
        "/configurations/3/a~1b~0c",
        "/configurations/3/z-last",
    ]
    assert all(item.location is item.config_pointer for item in result.diagnostics)
    assert all(
        item.config_pointer.path == Path("layout.json") for item in result.diagnostics
    )


def test_layout_module_does_not_expand_package_top_level_api() -> None:
    assert slidejunction.__all__ == ["Deck"]
    assert not hasattr(slidejunction, "parse_layout")


def _codes(result) -> list[str]:
    return [diagnostic.code for diagnostic in result.diagnostics]
