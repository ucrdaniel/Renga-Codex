"""Pure contract tests; native persistence is tested by the live test harness."""
from types import SimpleNamespace

import pytest

from renga_codex_bridge.room_markers import (
    assert_room_marker_matches, read_room_marker, set_room_marker, validate_marker_point,
)

ROOM_TYPE = "11111111-1111-4111-8111-111111111111"
OTHER_TYPE = "22222222-2222-4222-8222-222222222222"


def context():
    point = lambda x, y: SimpleNamespace(X=x, Y=y)
    room = SimpleNamespace(MarkerPosition=point(400, 500), Automatic=False)
    queried = []
    obj = SimpleNamespace(
        ObjectTypeS="{" + ROOM_TYPE.upper() + "}", UniqueIdS="synthetic-room-identity",
        QueryInterface=lambda iface: queried.append(iface) or room,
    )
    session = SimpleNamespace(sdk=SimpleNamespace(types={"Room": ROOM_TYPE}),
                              r=SimpleNamespace(IRoom="typed-room", Point2D=point))
    return session, obj, room, queried


@pytest.mark.parametrize("point", [None, [], [1], [1, 2, 3], "1,2", [True, 2], [1, False],
                                  [float("nan"), 2], [1, float("inf")], ["1", 2], [10**1000, 2]])
def test_invalid_point_rejected(point):
    with pytest.raises(ValueError):
        validate_marker_point(point)


def test_setter_uses_global_xy_and_does_not_require_automatic_room():
    session, obj, room, queried = context()
    response = set_room_marker(session, obj, [-1200.25, 3300])
    assert (room.MarkerPosition.X, room.MarkerPosition.Y) == (-1200.25, 3300)
    assert queried == ["typed-room"]
    assert response["status"] == "provisional"


def test_reader_distinguishes_intrinsic_marker_from_standalone_tag_and_persistence():
    session, obj, room, _ = context()
    result = read_room_marker(session, obj)
    assert result["point"] == [400, 500]
    assert result["coordinate_system"] == "global_xy"
    assert result["marker_kind"] == "intrinsic_room_marker"
    assert result["standalone_tag"] is False
    assert result["persistence_verified_by_this_reader"] is False


def test_assertion_uses_absolute_mm_tolerance_and_raises_on_ignored_setter():
    session, obj, room, _ = context()
    assert assert_room_marker_matches(session, obj, [400 + 1e-7, 500])["matches_expected"]
    with pytest.raises(RuntimeError, match="does not match"):
        assert_room_marker_matches(session, obj, [400, 550])
    room.MarkerPosition.X = 1e12
    with pytest.raises(RuntimeError):
        assert_room_marker_matches(session, obj, [1e12 + 1, 500])


@pytest.mark.parametrize("tolerance", [True, -1, float("inf"), float("nan"), "1"])
def test_assertion_rejects_invalid_tolerance(tolerance):
    session, obj, _, _ = context()
    with pytest.raises(ValueError):
        assert_room_marker_matches(session, obj, [400, 500], tolerance_mm=tolerance)


def test_wrong_native_type_is_rejected_before_interface_query_or_write():
    session, obj, room, queried = context()
    obj.ObjectTypeS = OTHER_TYPE
    with pytest.raises(ValueError, match="genuine native Room"):
        set_room_marker(session, obj, [1, 2])
    assert queried == []
    assert room.MarkerPosition.X == 400


def test_missing_sdk_type_fails_before_query():
    session, obj, _, queried = context()
    session.sdk.types.clear()
    with pytest.raises(ValueError, match="SDK"):
        read_room_marker(session, obj)
    assert queried == []
