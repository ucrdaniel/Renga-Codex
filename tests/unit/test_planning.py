"""Independent geometry and fit expectations, using millimeter inputs."""

import math

import pytest

from renga_codex_bridge.planning import facade_spacing, polygon_area, rectangle_plan
from renga_codex_bridge.validation import validate_plan


def test_rectangle_area_converts_square_millimeters_to_square_meters():
    assert polygon_area([[0, 0], [6000, 0], [6000, 4000], [0, 4000]]) == pytest.approx(24.0)


def test_concave_area_and_orientation_are_handled():
    outline = [[0, 0], [4000, 0], [4000, 1000], [1000, 1000], [1000, 4000], [0, 4000]]
    # Two 4x1 rectangles, with their shared 1x1 corner counted once.
    assert polygon_area(outline) == pytest.approx(7.0)
    assert polygon_area(list(reversed(outline))) == pytest.approx(7.0)


@pytest.mark.parametrize("points", [[[0, 0], [1, 1]], [[0, 0], [1, math.inf], [2, 0]], [[0, 0], [1, 2, 3], [2, 0]]])
def test_invalid_polygon_coordinates_are_rejected(points):
    with pytest.raises(ValueError):
        polygon_area(points)


@pytest.mark.parametrize("coordinate", [True, "1000"])
def test_polygon_requires_numeric_coordinates_without_boolean_coercion(coordinate):
    with pytest.raises(ValueError):
        polygon_area([[0, 0], [coordinate, 0], [1000, 1000]])


def test_three_windows_have_requested_end_piers_and_equal_internal_piers():
    result = facade_spacing(length=12000, width=1200, count=3, end_pier=600, min_pier=600)
    assert result["offsets_mm"] == pytest.approx([600, 5400, 10200])
    assert result["intermediate_pier_mm"] == pytest.approx(3600)
    assert 12000 - result["offsets_mm"][-1] - 1200 == pytest.approx(600)


def test_exact_minimum_pier_fit_is_allowed():
    result = facade_spacing(length=6000, width=1200, count=3, end_pier=600, min_pier=600)
    assert result["intermediate_pier_mm"] == pytest.approx(600)


def test_single_window_is_centered_with_no_internal_pier():
    result = facade_spacing(length=4000, width=1200, count=1, end_pier=600)
    assert result["offsets_mm"] == [1400]
    assert result["intermediate_pier_mm"] is None
    assert result["end_pier_mm"] == 1400


@pytest.mark.parametrize("count", [True, False, 0, -1, 1.5, "2"])
def test_window_count_is_a_positive_integer_not_a_boolean(count):
    with pytest.raises(ValueError):
        facade_spacing(6000, 1200, count)


def test_facade_rejects_oversized_windows_and_insufficient_piers():
    with pytest.raises(ValueError, match="pier"):
        facade_spacing(length=5999, width=1200, count=3, end_pier=600, min_pier=600)
    with pytest.raises(ValueError):
        facade_spacing(length=2200, width=1200, count=1, end_pier=600)


@pytest.mark.parametrize("dimension", [0, -1, math.nan, math.inf])
def test_facade_dimensions_must_be_positive_and_finite(dimension):
    with pytest.raises(ValueError):
        facade_spacing(dimension, 1200, 3)


@pytest.mark.parametrize("dimension", [True, "6000"])
def test_facade_does_not_coerce_booleans_or_strings_into_dimensions(dimension):
    with pytest.raises(ValueError):
        facade_spacing(6000, 1200, 3, end_pier=dimension)


@pytest.mark.parametrize("dimension", [True, "6000"])
def test_rectangle_does_not_coerce_booleans_or_strings_into_dimensions(dimension):
    with pytest.raises(ValueError):
        rectangle_plan(height=dimension)


def test_rectangle_plan_is_reviewable_and_structurally_valid():
    plan = rectangle_plan(width=6000, depth=4000, height=3200, thickness=200)
    assert validate_plan(plan)["operation_count"] == 6
    assert {item["kind"] for item in plan} == {"Wall", "Room", "Floor"}
    walls = [item for item in plan if item["kind"] == "Wall"]
    assert len(walls) == 4
    assert all(item["parameters"]["WallHeight"] == 3200 for item in walls)
    floor = next(item for item in plan if item["kind"] == "Floor")
    assert polygon_area(floor["points"]) == pytest.approx(24.0)


def test_rectangle_wall_thickness_cannot_consume_room():
    with pytest.raises(ValueError):
        rectangle_plan(width=1000, depth=2000, thickness=500)
