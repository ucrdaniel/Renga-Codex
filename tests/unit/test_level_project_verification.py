"""Fail-closed readback checks; these fakes make no native-coverage claim."""
import copy
import math
from types import SimpleNamespace

import pytest

from renga_codex_bridge.level_projects import (
    assert_requested_axes, assert_requested_levels, read_axes, read_levels,
)


LEVEL_TYPE = "00000000-0000-0000-0000-000000000001"
AXIS_TYPE = "00000000-0000-0000-0000-000000000002"
OTHER_TYPE = "00000000-0000-0000-0000-000000000003"
UUID_ONE = "12345678-ABCD-1234-ABCD-123456789012"


def level_specs():
    return [{"name": "Basement", "elevation_mm": -2750.0},
            {"name": "First", "elevation_mm": 3000.0}]


def level_rows():
    return [{"id": 1, "uuid": UUID_ONE.lower(), "name": "Basement",
             "elevation_mm": -2750.0, "origin_z_mm": -2750.0, "native_type": "Level"},
            {"id": 2, "uuid": "22345678-abcd-1234-abcd-123456789012", "name": "First",
             "elevation_mm": 3000.0, "origin_z_mm": 3000.0, "native_type": "Level"}]


def grid_specs():
    return {"x": [{"name": "1", "position_mm": 0}, {"name": "2", "position_mm": 3000}],
            "y": [{"name": "А", "position_mm": 0}],
            "bounds_mm": [-1000, -1000, 4000, 7000]}


def axis_rows():
    return [{"name": name, "uuid": f"{i}2345678-abcd-1234-abcd-123456789012", "native_type": "Axis"}
            for i, name in enumerate(("1", "2", "А"), start=1)]


def test_requested_levels_compare_names_and_both_native_elevation_fields_without_requiring_order():
    actual = level_rows()[::-1]
    expected = level_specs()
    before = copy.deepcopy(actual)
    assert_requested_levels(actual, expected)
    assert actual == before


@pytest.mark.parametrize("actual", [[], level_rows()[:1], level_rows() + [level_rows()[0]]])
def test_level_missing_or_extra_objects_are_rejected(actual):
    with pytest.raises(RuntimeError, match="count"):
        assert_requested_levels(actual, level_specs())


@pytest.mark.parametrize("name", ["basement", "Basement ", "Unknown"])
def test_level_name_identity_is_exact_and_not_silently_normalized(name):
    actual = level_rows()
    actual[0]["name"] = name
    with pytest.raises(RuntimeError, match="name"):
        assert_requested_levels(actual, level_specs())


def test_duplicate_level_names_are_rejected_even_when_counts_match():
    actual = level_rows()
    actual[1]["name"] = actual[0]["name"]
    with pytest.raises(RuntimeError, match="Duplicate"):
        assert_requested_levels(actual, level_specs())


@pytest.mark.parametrize("key", ["elevation_mm", "origin_z_mm"])
@pytest.mark.parametrize("value", [0, 3000.001, math.nan, math.inf, -math.inf])
def test_level_checks_reject_wrong_or_nonfinite_saved_elevation_and_placement(key, value):
    actual = level_rows()
    actual[1][key] = value
    with pytest.raises(RuntimeError, match="elevation/placement"):
        assert_requested_levels(actual, level_specs())


def test_native_level_precision_uses_absolute_mm_tolerance_not_relative_height():
    actual = level_rows()
    expected = level_specs()
    actual[1]["elevation_mm"] = expected[1]["elevation_mm"] = 1e10
    actual[1]["origin_z_mm"] = 1e10 + 0.001
    with pytest.raises(RuntimeError, match="elevation/placement"):
        assert_requested_levels(actual, expected)


def test_requested_axis_names_are_verified_without_claiming_geometry_from_names():
    assert_requested_axes(axis_rows()[::-1], grid_specs())
    assert_requested_axes([], None)


@pytest.mark.parametrize("actual", [[], axis_rows()[:2], axis_rows() + [axis_rows()[0]],
                                    [axis_rows()[0], axis_rows()[0], axis_rows()[2]]])
def test_axis_missing_extra_or_duplicate_labels_cannot_pass_readback(actual):
    with pytest.raises(RuntimeError, match="names/count"):
        assert_requested_axes(actual, grid_specs())


@pytest.mark.parametrize("replacement", ["A", "а", "А ", "Other"])
def test_axis_labels_are_exact_including_unicode_and_case(replacement):
    actual = axis_rows()
    actual[2]["name"] = replacement
    with pytest.raises(RuntimeError, match="names/count"):
        assert_requested_axes(actual, grid_specs())


def test_unrequested_axis_in_level_only_project_is_rejected():
    with pytest.raises(RuntimeError, match="names/count"):
        assert_requested_axes(axis_rows(), None)


class Objects:
    def __init__(self, values):
        self.values = values
        self.Count = len(values)

    def GetByIndex(self, index):
        return self.values[index]


def fake_session(objects):
    collection = Objects(objects)
    return SimpleNamespace(model=SimpleNamespace(GetObjects=lambda: collection),
                           r=SimpleNamespace(ILevel=object()),
                           sdk=SimpleNamespace(types={"Level": LEVEL_TYPE, "Axis": AXIS_TYPE},
                                               parameters={"GridLineName": "grid-name-parameter"}))


def test_native_level_reader_requires_actual_ilevel_interface_and_getters():
    calls = []
    native = SimpleNamespace(LevelName="Этаж 2", Elevation=3000,
                             Placement=SimpleNamespace(Origin=SimpleNamespace(Z=3000)))
    obj = SimpleNamespace(ObjectTypeS=LEVEL_TYPE.lower(), Id=71, UniqueIdS="{" + UUID_ONE + "}")
    obj.QueryInterface = lambda interface: calls.append(interface) or native
    foreign = SimpleNamespace(ObjectTypeS=OTHER_TYPE)
    session = fake_session([foreign, obj])
    assert read_levels(session) == [{"id": 71, "uuid": UUID_ONE.lower(), "name": "Этаж 2",
                                    "elevation_mm": 3000, "origin_z_mm": 3000, "native_type": "Level"}]
    assert calls == [session.r.ILevel]


def test_native_type_label_without_ilevel_interface_cannot_be_reported_as_verified_level():
    obj = SimpleNamespace(ObjectTypeS=LEVEL_TYPE, Id=71, UniqueIdS="{" + UUID_ONE + "}")

    def unavailable(interface):
        raise RuntimeError("ILevel unavailable")

    obj.QueryInterface = unavailable
    with pytest.raises(RuntimeError, match="ILevel unavailable"):
        read_levels(fake_session([obj]))


def test_axis_reader_reads_native_parameter_instead_of_object_display_name():
    calls = []
    parameter = SimpleNamespace(GetStringValue=lambda: "А")
    parameters = SimpleNamespace(GetS=lambda identifier: calls.append(identifier) or parameter)
    obj = SimpleNamespace(ObjectTypeS=AXIS_TYPE.lower(), Id=81, UniqueIdS="{" + UUID_ONE + "}",
                          Name="Unrelated display title", GetParameters=lambda: parameters)
    assert read_axes(fake_session([SimpleNamespace(ObjectTypeS=OTHER_TYPE), obj])) == [
        {"id": 81, "uuid": UUID_ONE.lower(), "name": "А", "native_type": "Axis"}]
    assert calls == ["grid-name-parameter"]
