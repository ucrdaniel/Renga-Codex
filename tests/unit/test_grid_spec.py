"""Grid seed request contract tests; these do not claim native import success."""
from copy import deepcopy

import pytest

from renga_codex_bridge.grid_spec import MAX_GRID_AXES, validate_grid_spec


def sample():
    return {
        "x": [{"name": "1", "position_mm": 0}, {"name": "2", "position_mm": 3000}],
        "y": [{"name": "А", "position_mm": 0}, {"name": "Б'", "position_mm": 6000}],
        "bounds_mm": [-1000, -1000, 7000, 7000],
    }


def test_explicit_names_negative_bounds_and_input_order_are_preserved_without_mutation():
    request = sample()
    before = deepcopy(request)
    result = validate_grid_spec(request)
    assert request == before
    assert result == request
    assert result is not request
    assert result["x"] is not request["x"]
    assert all(isinstance(axis["position_mm"], float) for family in ("x", "y") for axis in result[family])
    assert result["y"][1]["name"] == "Б'"


@pytest.mark.parametrize("bad", [None, [], {}, {"x": [], "y": []}])
def test_missing_or_invalid_grid_shape(bad):
    with pytest.raises(ValueError):
        validate_grid_spec(bad)


def test_unknown_grid_key_cannot_be_silently_ignored():
    request = sample()
    request["z"] = []
    with pytest.raises(ValueError):
        validate_grid_spec(request)


@pytest.mark.parametrize("bounds", [[0, 0, 0, 1], [0, 0, 1, 0], [1, 0, 0, 1],
                                     [0, 0, 1], [True, 0, 1, 1],
                                     [0, 0, float("inf"), 1], [0, 0, 1, float("nan")]])
def test_invalid_or_degenerate_bounds(bounds):
    request = sample()
    request["bounds_mm"] = bounds
    with pytest.raises(ValueError):
        validate_grid_spec(request)


@pytest.mark.parametrize("family", ["x", "y"])
def test_both_axis_families_are_required(family):
    request = sample()
    request[family] = []
    with pytest.raises(ValueError, match="nonempty"):
        validate_grid_spec(request)


@pytest.mark.parametrize("axis", [None, {}, {"name": "1"}, {"name": "1", "position_mm": 1, "z": 0}])
def test_axis_shape_must_be_explicit(axis):
    request = sample()
    request["x"][0] = axis
    with pytest.raises(ValueError):
        validate_grid_spec(request)


@pytest.mark.parametrize("name", [None, 1, "", " ", " A", "A ", "A\nB", "A\x00B", "A\x7f", "A\x85", "A\ud800"])
def test_invalid_axis_names(name):
    request = sample()
    request["x"][0]["name"] = name
    with pytest.raises(ValueError):
        validate_grid_spec(request)


def test_names_are_unique_globally_including_case_collisions():
    request = sample()
    request["x"][0]["name"] = "Axis"
    request["y"][0]["name"] = "AXIS"
    with pytest.raises(ValueError, match="globally unique"):
        validate_grid_spec(request)


@pytest.mark.parametrize("position", [True, "0", float("nan"), float("inf"), -1001, 7001, 10**1000])
def test_positions_must_be_finite_numbers_within_bounds(position):
    request = sample()
    request["x"][0]["position_mm"] = position
    with pytest.raises(ValueError):
        validate_grid_spec(request)


def test_duplicate_coordinate_in_one_family_rejected_including_negative_zero():
    request = sample()
    request["x"][1]["position_mm"] = -0.0
    with pytest.raises(ValueError, match="coordinates must be unique"):
        validate_grid_spec(request)


def test_same_coordinate_across_perpendicular_families_is_valid():
    request = sample()
    request["x"][0]["position_mm"] = request["y"][0]["position_mm"] = 0
    assert validate_grid_spec(request)["x"][0]["position_mm"] == 0


def test_positions_at_boundary_are_valid():
    request = sample()
    request["x"][0]["position_mm"] = -1000
    request["y"][0]["position_mm"] = 7000
    validate_grid_spec(request)


def test_total_axis_limit_applies_across_both_families():
    request = {"x": [{"name": str(i), "position_mm": i} for i in range(MAX_GRID_AXES - 1)],
               "y": [{"name": "Y", "position_mm": 0}], "bounds_mm": [0, 0, MAX_GRID_AXES, 1]}
    assert len(validate_grid_spec(request)["x"]) == MAX_GRID_AXES - 1
    request["y"].append({"name": "Y2", "position_mm": 1})
    with pytest.raises(ValueError, match="1000-axis"):
        validate_grid_spec(request)
