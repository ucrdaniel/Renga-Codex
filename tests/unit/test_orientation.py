"""Placement input/readback contracts, with no COM dependencies."""

import math

import pytest

from renga_codex_bridge.orientation import (
    NativePlacementVerificationError,
    assert_pose_matches,
    validate_creation_axes,
    validate_wall_host_orientation,
)


def test_default_creation_axes_are_right_orthonormal_and_explicit():
    assert validate_creation_axes() == {"x_axis": [1.0, 0.0, 0.0], "z_axis": [0.0, 0.0, 1.0]}


@pytest.mark.parametrize("kind", [True, 1, []])
def test_category_name_must_be_explicit_string(kind):
    with pytest.raises(ValueError, match="kind"):
        validate_creation_axes(kind=kind)


@pytest.mark.parametrize("angle", [math.pi / 2, -math.pi / 2, math.pi, math.pi / 4])
def test_horizontal_yaw_keeps_supplied_axis_without_rescaling(angle):
    x = [math.cos(angle), math.sin(angle), 0]
    assert validate_creation_axes(x, [0, 0, 1], kind="Wall")["x_axis"] == x


@pytest.mark.parametrize("axis", [[2, 0, 0], [0.5, 0, 0], [0, 0, 0], [1, 1, 0]])
def test_scaled_or_zero_axes_are_rejected(axis):
    with pytest.raises(ValueError, match="unit vector"):
        validate_creation_axes(axis)


@pytest.mark.parametrize("axis", [None, "1,0,0", [1, 0], [True, 0, 0], [math.nan, 0, 0], [math.inf, 0, 0], [10**1000, 0, 0]])
def test_malformed_or_nonfinite_axes_fail_without_native_calls(axis):
    with pytest.raises(ValueError):
        validate_creation_axes(axis)


def test_unit_but_nonperpendicular_axes_are_rejected():
    with pytest.raises(ValueError, match="perpendicular"):
        validate_creation_axes([1, 0, 0], [1, 0, 0])


@pytest.mark.parametrize("kind", ["Wall", "Floor", "Roof", "Stair", "Room", "Door", "Window"])
def test_horizontal_categories_do_not_advertise_unverified_tilt(kind):
    with pytest.raises(ValueError, match="horizontal placement"):
        validate_creation_axes([1, 0, 0], [0, -1, 0], kind=kind)


def test_nondefault_level_orientation_is_not_silently_accepted():
    with pytest.raises(NotImplementedError, match="Level axes"):
        validate_creation_axes([0, 1, 0], [0, 0, 1], kind="Level")


def test_general_three_dimensional_axes_pass_only_mathematical_validation():
    assert validate_creation_axes([1, 0, 0], [0, -1, 0], kind="Element") == {
        "x_axis": [1.0, 0.0, 0.0], "z_axis": [0.0, -1.0, 0.0]
    }


@pytest.mark.parametrize(
    "axis,direction,relation",
    [([1, 0, 0], [6000, 0, 0], "co_directed"),
     ([-1, 0, 0], [6000, 0, 0], "counter_directed"),
     ([0, 1, 0], [0, 4000, 0], "co_directed"),
     ([0, -1, 0], [0, 4000, 0], "counter_directed")],
)
def test_hosted_opening_side_uses_global_straight_wall_direction(axis, direction, relation):
    assert validate_wall_host_orientation(axis, [0, 0, 1], direction) == relation


def test_fixed_default_axis_is_rejected_for_a_vertical_plan_wall():
    with pytest.raises(ValueError, match="co-directed or counter-directed"):
        validate_wall_host_orientation([1, 0, 0], [0, 0, 1], [0, 6000, 0])


@pytest.mark.parametrize("direction", [[0, 0, 0], [1, 0, 1], [True, 0, 0]])
def test_bad_host_direction_is_not_guessed(direction):
    with pytest.raises(ValueError):
        validate_wall_host_orientation([1, 0, 0], [0, 0, 1], direction)


def test_axis_validation_does_not_mutate_input_lists():
    x, z = [1, 0, 0], [0, 0, 1]
    result = validate_creation_axes(x, z)
    result["x_axis"][0] = -1
    assert x == [1, 0, 0] and z == [0, 0, 1]


def test_unchanged_origin_does_not_hide_wrong_hosted_side_after_reopen():
    expected = {"origin": [100, 200, 0], "x_axis": [-1, 0, 0], "z_axis": [0, 0, 1]}
    observed = {**expected, "x_axis": [1, 0, 0]}
    with pytest.raises(NativePlacementVerificationError, match="x_axis"):
        assert_pose_matches(expected, observed)


def test_axes_and_origin_are_compared_with_explicit_absolute_tolerance():
    expected = {"origin": [0, 0, 0], "x_axis": [1, 0, 0], "z_axis": [0, 0, 1]}
    result = assert_pose_matches(expected, {**expected, "origin": [0.0000005, 0, 0]})
    assert result["compared_fields"] == ["origin", "x_axis", "z_axis"]
    assert result["persistence_verified_by_this_helper"] is False
    with pytest.raises(NativePlacementVerificationError):
        assert_pose_matches(expected, {**expected, "origin": [0.000002, 0, 0]})


@pytest.mark.parametrize("expected", [{}, {"unknown": [1, 0, 0]}, None])
def test_readback_cannot_claim_comparison_without_requested_fields(expected):
    with pytest.raises(ValueError):
        assert_pose_matches(expected, {})


def test_missing_observed_axis_is_a_native_verification_failure():
    with pytest.raises(NativePlacementVerificationError, match="lacks z_axis"):
        assert_pose_matches({"z_axis": [0, 0, 1]}, {"origin": [0, 0, 0]})


@pytest.mark.parametrize("tolerance", [True, -1, math.nan, math.inf, 10**1000])
def test_readback_tolerance_cannot_hide_arbitrary_pose_mismatch(tolerance):
    with pytest.raises(ValueError, match="abs_tol"):
        assert_pose_matches({"origin": [0, 0, 0]}, {"origin": [0, 0, 0]}, abs_tol=tolerance)
