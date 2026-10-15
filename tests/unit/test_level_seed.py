"""Pure IFC seed validation; these tests do not claim native Renga coverage."""
import math
import re

import pytest

from renga_codex_bridge.level_seed import build_level_seed_ifc, validate_level_specs


def test_specs_preserve_names_and_explicit_negative_elevations_without_mutation():
    source = [{"name": " Basement ", "elevation_mm": -2750}, {"name": "Ground", "elevation_mm": 0}]
    result = validate_level_specs(source)
    assert result == [{"name": " Basement ", "elevation_mm": -2750.0}, {"name": "Ground", "elevation_mm": 0.0}]
    result[0]["name"] = "Changed"
    assert source[0]["name"] == " Basement "


@pytest.mark.parametrize("value", [None, {}, (), [], [None], [{}], [{"name": "X"}], [{"name": "X", "elevation_mm": 1, "ignored": 2}]])
def test_missing_or_ambiguous_specs_are_rejected(value):
    with pytest.raises(ValueError):
        validate_level_specs(value)


@pytest.mark.parametrize("value", [True, False, None, "3000", math.nan, math.inf, -math.inf, 10 ** 1000])
def test_elevations_cannot_be_coerced_or_nonfinite(value):
    with pytest.raises(ValueError):
        validate_level_specs([{"name": "X", "elevation_mm": value}])


@pytest.mark.parametrize("name", [None, True, "", "  ", "\tX", "X\nY", "X\0Y", "X\ud800Y"])
def test_names_must_be_nonempty_printable_unicode(name):
    with pytest.raises(ValueError):
        validate_level_specs([{"name": name, "elevation_mm": 0}])


@pytest.mark.parametrize("levels", [
    [{"name": "X", "elevation_mm": 0}, {"name": "X", "elevation_mm": 3000}],
    [{"name": "X", "elevation_mm": 0}, {"name": "Y", "elevation_mm": -0.0}],
    [{"name": "X", "elevation_mm": 3000}, {"name": "Y", "elevation_mm": 3000.0}],
])
def test_duplicate_names_or_numeric_elevations_are_rejected(levels):
    with pytest.raises(ValueError, match="unique"):
        validate_level_specs(levels)


def test_large_seed_is_bounded_before_generation():
    levels = [{"name": str(i), "elevation_mm": i * 3000} for i in range(1000)]
    assert len(validate_level_specs(levels)) == 1000
    with pytest.raises(ValueError, match="1000"):
        validate_level_specs(levels + [{"name": "extra", "elevation_mm": 3_000_000}])


def test_step_strings_escape_quote_backslash_and_unicode_without_line_injection():
    name = "Этаж 'O\\X2\\' 😀;#999=EVIL()"
    text = build_level_seed_ifc([{"name": name, "elevation_mm": 3000}])
    text.encode("ascii")
    storey_line = next(line for line in text.splitlines() if "=IFCBUILDINGSTOREY(" in line)
    assert "''O\\X2\\005C\\X0\\X2\\X2\\005C\\X0\\''" in storey_line
    assert "\\X2\\042D\\X0\\" in storey_line
    assert "\\X4\\0001F600\\X0\\" in storey_line
    assert not any(line.startswith("#999=") for line in text.splitlines())


def test_deterministic_seed_has_unique_valid_global_ids_and_consistent_spatial_graph():
    specs = [{"name": "L0", "elevation_mm": 0}, {"name": "L1", "elevation_mm": 3000}, {"name": "L2", "elevation_mm": 6000}]
    text = build_level_seed_ifc(specs)
    assert text == build_level_seed_ifc(specs)
    roots = re.findall(r"=IFC(?:PROJECT|SITE|BUILDING|BUILDINGSTOREY|SLAB|RELAGGREGATES|RELCONTAINEDINSPATIALSTRUCTURE)\('([^']+)'", text)
    assert len(roots) == 15
    assert len(set(roots)) == len(roots)
    assert all(re.fullmatch(r"[0-3][0-9A-Za-z_$]{21}", value) for value in roots)
    declarations = set(re.findall(r"^#(\d+)=", text, re.MULTILINE))
    references = set(re.findall(r"#(\d+)", text))
    assert references == declarations
    assert text.count("=IFCBUILDINGSTOREY(") == 3
    assert text.count("=IFCSLAB(") == 3
    assert text.count("=IFCRELCONTAINEDINSPATIALSTRUCTURE(") == 3
    assert "IFCSIUNIT(*,.LENGTHUNIT.,.MILLI.,.METRE.)" in text
    assert "FILE_SCHEMA(('IFC4'))" in text
    assert "IFCCARTESIANPOINT((0.,0.,3000.0))" in text
    assert ".ELEMENT.,3000.0)" in text


def test_small_and_large_finite_elevations_emit_step_reals():
    text = build_level_seed_ifc([{"name": "small", "elevation_mm": 1e-10}, {"name": "large", "elevation_mm": 1e20}])
    assert "1.E-10" in text and "1.E+20" in text


def _grid():
    return {"x": [{"name": "1", "position_mm": 0}, {"name": "2", "position_mm": 3000}],
            "y": [{"name": "A", "position_mm": 1000}, {"name": "B", "position_mm": 6000}],
            "bounds_mm": [-1000, -2000, 7000, 8000]}


def test_optional_grid_has_shared_footprint_curves_and_world_coordinate_extents():
    text = build_level_seed_ifc([{"name": "Basement", "elevation_mm": -3000}], _grid())
    rows = dict(re.findall(r"^#(\d+)=(.*);$", text, re.MULTILINE))
    axes = [value for value in rows.values() if value.startswith("IFCGRIDAXIS(")]
    assert len(axes) == 4
    curves = [re.search(r",(#\d+),\.T\.\)", value).group(1) for value in axes]
    curve_set = next(value for value in rows.values() if value.startswith("IFCGEOMETRICCURVESET("))
    assert set(re.findall(r"#\d+", curve_set)) == set(curves)
    # Independent expected endpoints: labels 1/2 are constant-X; A/B constant-Y.
    expected = {"1": [(0, -2000), (0, 8000)], "2": [(3000, -2000), (3000, 8000)],
                "A": [(-1000, 1000), (7000, 1000)], "B": [(-1000, 6000), (7000, 6000)]}
    for axis in axes:
        name = re.search(r"IFCGRIDAXIS\('([^']+)'", axis).group(1)
        curve = rows[re.search(r",#(\d+),", axis).group(1)]
        coordinates = []
        for reference in re.findall(r"#(\d+)", curve):
            record = rows[reference]
            values = re.search(r"IFCCARTESIANPOINT\(\(([^)]+)\)\)", record).group(1)
            coordinates.append(tuple(float(value) for value in values.split(",")))
        assert coordinates == expected[name]
    assert "'FootPrint','GeometricCurveSet'" in text
    assert ".RECTANGULAR.)" in text
    # The grid is not translated down to the basement elevation.
    grid = next(value for value in rows.values() if value.startswith("IFCGRID("))
    placement_id = grid.split(",")[5]
    placement = rows[placement_id[1:]]
    building = next(value for value in rows.values() if value.startswith("IFCBUILDING("))
    assert placement.startswith("IFCLOCALPLACEMENT(" + building.split(",")[5] + ",")


def test_omitted_grid_keeps_plain_seed_and_explicit_grid_changes_identifiers():
    levels = [{"name": "Ground", "elevation_mm": 0}]
    plain = build_level_seed_ifc(levels)
    assert plain == build_level_seed_ifc(levels, None)
    assert "IFCGRID(" not in plain
    grid = build_level_seed_ifc(levels, _grid())
    assert grid == build_level_seed_ifc(levels, _grid())
    plain_guid = re.search(r"IFCPROJECT\('([^']+)'", plain).group(1)
    grid_guid = re.search(r"IFCPROJECT\('([^']+)'", grid).group(1)
    assert plain_guid != grid_guid


def test_grid_labels_receive_same_unicode_and_step_literal_protection():
    grid = _grid()
    grid["x"][0]["name"] = "Ось '😀'\\"
    text = build_level_seed_ifc([{"name": "Ground", "elevation_mm": 0}], grid)
    text.encode("ascii")
    assert "\\X4\\0001F600\\X0\\" in text
    assert "\\X2\\005C\\X0\\" in text
    assert "''" in text


def test_builder_rejects_invalid_grid_instead_of_silently_omitting_it():
    with pytest.raises(ValueError):
        build_level_seed_ifc([{"name": "Ground", "elevation_mm": 0}], {})
