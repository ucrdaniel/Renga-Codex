"""Input contracts: malformed plans must fail before starting COM."""

import math

import pytest

from renga_codex_bridge.validation import finite_vector, validate_plan


def test_valid_plan_reports_validation_without_native_execution():
    result = validate_plan(
        [
            {
                "action": "create",
                "kind": "Wall",
                "ref": "wall",
                "points": [[0, 0], [6000, 0]],
                "parameters": {"WallHeight": 3000, "WallThickness": 200},
            },
            {"action": "set_parameter", "id": "wall", "name": "WallHeight", "value": 3200},
        ]
    )
    assert result["valid"] is True
    assert result["operation_count"] == 2
    assert result["native_execution_performed"] is False


@pytest.mark.parametrize("value", [None, {}, "plan", 1])
def test_plan_must_be_an_operation_list(value):
    with pytest.raises(ValueError):
        validate_plan(value)


def test_plan_size_limit_applies_before_execution():
    with pytest.raises(ValueError, match="10000"):
        validate_plan([{"action": "delete", "id": 1}] * 10001)


@pytest.mark.parametrize("operation", [{}, {"action": "run_script"}, {"action": []}, {"action": {}}, "create"])
def test_unsupported_actions_are_rejected(operation):
    with pytest.raises(ValueError):
        validate_plan([operation])


@pytest.mark.parametrize("action", ["delete", "baseline", "move", "room_region", "roof_slopes"])
def test_existing_object_operations_require_an_id(action):
    with pytest.raises(ValueError, match="id"):
        validate_plan([{"action": action}])


@pytest.mark.parametrize("value", [None, "", "   ", True, 0, -1, [], {}])
def test_unusable_existing_object_identifiers_are_rejected(value):
    with pytest.raises(ValueError):
        validate_plan([{"action": "delete", "id": value}])


def test_duplicate_plan_references_are_ambiguous():
    with pytest.raises(ValueError, match="ref"):
        validate_plan(
            [
                {"action": "create", "kind": "Wall", "ref": "wall"},
                {"action": "create", "kind": "Floor", "ref": "wall"},
            ]
        )


@pytest.mark.parametrize("ref", ["", 42, True])
def test_create_reference_must_be_a_nonempty_string(ref):
    with pytest.raises(ValueError, match="ref"):
        validate_plan([{"action": "create", "kind": "Wall", "ref": ref}])


@pytest.mark.parametrize("origin", [[0, 0, 3000], [10, 0, 0], [0, -10, 0]])
def test_nonzero_level_origin_is_not_silently_accepted(origin):
    with pytest.raises(NotImplementedError, match="Level"):
        validate_plan([{"action": "create", "kind": "Level", "origin": origin}])


def test_default_level_origin_can_be_validated_without_sdk():
    assert validate_plan([{"action": "create", "kind": "Level", "origin": [0, 0, 0]}])["valid"]


def test_malformed_level_origin_raises_validation_error_before_api_limit_check():
    with pytest.raises(ValueError):
        validate_plan([{"action": "create", "kind": "Level", "origin": None}])


@pytest.mark.parametrize("name", ["", "   ", None])
def test_set_parameter_name_cannot_be_empty(name):
    with pytest.raises(ValueError):
        validate_plan([{"action": "set_parameter", "id": "12345678-1234-4321-9876-123456789ABC", "name": name, "value": 3200}])


def test_move_requires_an_explicit_displacement():
    with pytest.raises(ValueError):
        validate_plan([{"action": "move", "id": 100}])


@pytest.mark.parametrize("action", ["baseline", "baseline3d"])
def test_baseline_replacement_requires_points(action):
    with pytest.raises(ValueError):
        validate_plan([{"action": action, "id": 100}])


def test_host_cannot_reference_a_later_creation():
    with pytest.raises(ValueError):
        validate_plan(
            [
                {"action": "create", "kind": "Window", "host": "wall", "origin": [1000, 0, 900]},
                {"action": "create", "kind": "Wall", "ref": "wall", "points": [[0, 0], [6000, 0]]},
            ]
        )


def test_host_can_reference_an_earlier_creation():
    assert validate_plan(
        [
            {"action": "create", "kind": "Wall", "ref": "wall", "points": [[0, 0], [6000, 0]]},
            {"action": "create", "kind": "Window", "host": "wall", "origin": [1000, 0, 900]},
        ]
    )["valid"]


@pytest.mark.parametrize("identity", [100, "12345678-1234-4321-9876-123456789ABC"])
def test_host_can_use_an_inspected_numeric_or_persistent_identity(identity):
    assert validate_plan([{"action": "create", "kind": "Window", "host": identity, "origin": [1000, 0, 900]}])["valid"]


@pytest.mark.parametrize("coordinate", [math.nan, math.inf, -math.inf, True, "100"])
def test_coordinates_require_finite_real_numbers(coordinate):
    with pytest.raises(ValueError):
        finite_vector([0, coordinate, 0], 3)


@pytest.mark.parametrize("field,value", [("origin", [0, 0]), ("delta", [0, 0, math.nan]), ("point", [1, math.inf])])
def test_malformed_operation_vectors_are_rejected(field, value):
    with pytest.raises(ValueError):
        validate_plan([{"action": "move", "id": 100, "delta": [0, 0, 0], field: value}])


def test_three_dimensional_baseline_is_distinct_from_xy_baseline():
    points = [[0, 0, 3000], [6000, 0, 3000]]
    assert validate_plan([{"action": "baseline3d", "id": 100, "points": points}])["valid"]
    with pytest.raises(ValueError):
        validate_plan([{"action": "baseline", "id": 100, "points": points}])


def test_closed_contour_cannot_be_collinear():
    with pytest.raises(ValueError, match="area"):
        validate_plan([{"action": "create", "kind": "Floor", "closed": True, "points": [[0, 0], [1000, 0], [2000, 0]]}])


@pytest.mark.parametrize("value", [math.nan, math.inf, {"nested": 1}, None])
def test_parameter_values_are_finite_and_primitive(value):
    with pytest.raises(ValueError):
        validate_plan([{"action": "set_parameter", "id": 100, "name": "WallHeight", "value": value}])


def test_property_identifier_requires_a_uuid():
    with pytest.raises(ValueError):
        validate_plan([{"action": "property", "id": 100, "guid": "not-a-uuid", "value": "A"}])


def test_property_with_synthetic_uuid_is_validated_without_renga():
    assert validate_plan([{"action": "property", "id": 100, "guid": "{12345678-1234-4321-9876-123456789ABC}", "value": "A"}])["valid"]
