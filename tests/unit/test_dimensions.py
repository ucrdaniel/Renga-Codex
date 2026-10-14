"""Computed dimension contracts, not native Renga integration evidence."""

from decimal import Decimal
from types import SimpleNamespace

import pytest

from renga_codex_bridge.dimensions import (
    NativeDimensionCreationUnavailable,
    NativeDimensionVerificationError,
    create_native_linear_dimension,
    dimension_capability,
    parse_dimension_display_value,
    read_native_linear_dimension,
    requested_distance_mm,
    verify_native_linear_dimension,
)


OBJECT_UID = "11111111-1111-4111-8111-111111111111"
TYPE_UID = "22222222-2222-4222-8222-222222222222"
MODE_GUID = "33333333-3333-4333-8333-333333333333"
VALUE_GUID = "44444444-4444-4444-8444-444444444444"


def fake_context(mode=1, text="5750", *, missing=None, unset=None, direct_lookup=True):
    values = {
        MODE_GUID: SimpleNamespace(
            HasValue=unset != "mode", ValueType=2, GetIntValue=lambda: mode, IsReadOnly=False
        ),
        VALUE_GUID: SimpleNamespace(
            HasValue=unset != "value", ValueType=4, GetStringValue=lambda: text, IsReadOnly=True
        ),
    }
    if missing is not None:
        del values[missing]
    pc = SimpleNamespace(ContainsS=lambda guid: guid in values, GetS=lambda guid: values[guid])
    obj = SimpleNamespace(
        Id=27, UniqueIdS="{" + OBJECT_UID + "}", ObjectTypeS=TYPE_UID, GetParameters=lambda: pc
    )
    objects = SimpleNamespace(Count=1, GetByIndex=lambda index: obj)
    if direct_lookup:
        objects.GetByUniqueIdS = lambda uid: obj if uid.strip("{}").lower() == OBJECT_UID else None
    model = SimpleNamespace(GetObjects=lambda: objects)
    session = SimpleNamespace(
        model=model,
        sdk=SimpleNamespace(
            types={"LinearDimension": TYPE_UID},
            parameters={"DimensionValueType": MODE_GUID, "DimensionValue": VALUE_GUID},
        ),
    )
    return session, obj


@pytest.mark.parametrize("orientation, expected", [("aligned", 5), ("horizontal", 3), ("vertical", 4)])
def test_independent_requested_distance_has_explicit_orientation(orientation, expected):
    assert requested_distance_mm([[1, 2], [4, 6]], orientation) == expected


@pytest.mark.parametrize(
    "points", [[[0, 0], [0, 0]], [[0, 0], [True, 1]], [[0, 0], [float("nan"), 2]], [[0, 0], [float("inf"), 2]]]
)
def test_invalid_or_zero_geometry_fails_before_native_calls(points):
    with pytest.raises(ValueError):
        requested_distance_mm(points)


def test_unsupported_native_creation_never_accesses_session_or_creates_text():
    class ForbiddenSession:
        def __getattribute__(self, name):
            raise AssertionError("Unexpected session access: " + name)

    refs = [
        {"object_unique_id": OBJECT_UID, "feature_id": 0},
        {"object_unique_id": TYPE_UID, "feature_id": 1},
    ]
    with pytest.raises(NativeDimensionCreationUnavailable) as caught:
        create_native_linear_dimension(ForbiddenSession(), points_mm=[[0, 0], [120, 0]], feature_refs=refs)
    assert caught.value.code == "API_LIMITATION"
    assert caught.value.mutated is False


def test_nil_uuid_and_guessed_feature_id_are_rejected_as_request_data():
    with pytest.raises(ValueError):
        create_native_linear_dimension(
            None, points_mm=[[0, 0], [120, 0]],
            feature_refs=[{"object_unique_id": "00000000-0000-0000-0000-000000000000", "feature_id": 0}] * 2,
        )
    with pytest.raises(ValueError):
        create_native_linear_dimension(
            None, points_mm=[[0, 0], [120, 0]],
            feature_refs=[{"object_unique_id": OBJECT_UID, "feature_id": True}] * 2,
        )


@pytest.mark.parametrize("text", ["5750 mm", "R5750", "1,234.5", "1 234", "NaN", "1e3", "\u0661\u0662\u0663"])
def test_display_parser_does_not_guess_units_grouping_or_numeric_locale(text):
    with pytest.raises(ValueError):
        parse_dimension_display_value(text)


def test_display_parser_requires_explicit_decimal_rule():
    assert parse_dimension_display_value(" 5750.25 ") == Decimal("5750.25")
    assert parse_dimension_display_value("5750,25", decimal_separator=",") == Decimal("5750.25")
    with pytest.raises(ValueError):
        parse_dimension_display_value("5750,25")


@pytest.mark.parametrize("direct_lookup", [True, False])
def test_computed_value_read_preserves_scope_and_does_not_claim_persistence(direct_lookup):
    session, obj = fake_context(direct_lookup=direct_lookup)
    value = read_native_linear_dimension(session, OBJECT_UID)
    assert value["computed"] is True
    assert value["dimension_value_type"] == 1
    assert value["numeric_display_value"] == "5750"
    assert value["display_unit"] is None
    assert value["dimension_value_read_only"] is True
    assert value["persistence_verified_by_this_reader"] is False


def test_numeric_text_override_cannot_be_verified_as_a_computed_dimension():
    session, obj = fake_context(mode=2, text="5750")
    with pytest.raises(NativeDimensionVerificationError, match="not 1"):
        read_native_linear_dimension(session, OBJECT_UID)


@pytest.mark.parametrize("missing", [MODE_GUID, VALUE_GUID])
def test_missing_native_parameter_is_not_a_zero_or_inferred_value(missing):
    session, obj = fake_context(missing=missing)
    with pytest.raises(NativeDimensionVerificationError, match="lacks"):
        read_native_linear_dimension(session, OBJECT_UID)


@pytest.mark.parametrize("unset", ["mode", "value"])
def test_unset_native_parameter_cannot_prove_a_computed_value(unset):
    session, obj = fake_context(unset=unset)
    with pytest.raises(NativeDimensionVerificationError):
        read_native_linear_dimension(session, OBJECT_UID)


def test_wrong_native_object_type_is_rejected_even_with_dimension_parameters():
    session, obj = fake_context()
    obj.ObjectTypeS = VALUE_GUID
    with pytest.raises(NativeDimensionVerificationError, match="not a native"):
        read_native_linear_dimension(session, OBJECT_UID)


@pytest.mark.parametrize("guid, wrong_type", [(MODE_GUID, 1), (VALUE_GUID, 3)])
def test_incorrect_native_parameter_type_is_rejected_before_a_typed_getter(guid, wrong_type):
    session, obj = fake_context()
    obj.GetParameters().GetS(guid).ValueType = wrong_type
    with pytest.raises(NativeDimensionVerificationError, match="unexpected value type"):
        read_native_linear_dimension(session, OBJECT_UID)


def test_display_verification_honors_explicit_rounding_tolerance():
    session, obj = fake_context(text="5750.3")
    result = verify_native_linear_dimension(session, OBJECT_UID, "5750.25", tolerance="0.05")
    assert result["matches_expected_display_value"] is True
    assert result["absolute_difference_display_units"] == "0.05"
    assert verify_native_linear_dimension(session, OBJECT_UID, "5750.25", tolerance="0.049")["matches_expected_display_value"] is False


@pytest.mark.parametrize("tolerance", [True, "NaN", "Infinity", "-0.1"])
def test_bad_tolerance_fails_before_reading_session(tolerance):
    with pytest.raises(ValueError):
        verify_native_linear_dimension(None, OBJECT_UID, "5750", tolerance=tolerance)


def test_capability_does_not_promote_mock_tests_or_unknown_versions_to_native_support():
    assert dimension_capability()["creation_status"] == "API_LIMITATION"
    assert dimension_capability()["read_status"] == "NOT_VERIFIED"
    assert dimension_capability("3.00")["creation_status"] == "NOT_VERIFIED"
