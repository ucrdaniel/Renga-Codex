"""Move a Room's intrinsic marker through IRoom; never create standalone Tags.

Coordinates are global XY millimetres. Callers own the undo transaction and
must call the read/assert helpers again after save, close and reopen.
"""
import math
from uuid import UUID


def validate_marker_point(point):
    """Return an explicit finite XY pair without guessing coordinates."""
    if not isinstance(point, (list, tuple)) or len(point) != 2:
        raise ValueError("Room marker point must be an explicit global XY pair in mm")
    if any(isinstance(v, bool) or not isinstance(v, (int, float)) for v in point):
        raise ValueError("Room marker coordinates must be numbers, not booleans")
    try:
        values = [float(v) for v in point]
    except OverflowError as error:
        raise ValueError("Room marker coordinates must be finite") from error
    if not all(math.isfinite(v) for v in values):
        raise ValueError("Room marker coordinates must be finite")
    return values


def _room_interface(session, obj):
    room_type = session.sdk.types.get("Room")
    if room_type is None:
        raise ValueError("Local SDK has no Room type identifier")
    try:
        genuine_room = UUID(str(obj.ObjectTypeS).strip("{}")) == UUID(str(room_type).strip("{}"))
    except (ValueError, AttributeError, TypeError) as error:
        raise ValueError("Invalid native room type identifier") from error
    if not genuine_room:
        raise ValueError("room_marker requires a genuine native Room, not a Tag or text")
    return obj.QueryInterface(session.r.IRoom)


def read_room_marker(session, obj):
    """Read the native marker without implying a save/reopen was performed."""
    native = _room_interface(session, obj).MarkerPosition
    point = validate_marker_point([native.X, native.Y])
    return {
        "unique_id": obj.UniqueIdS,
        "point": point,
        "coordinate_system": "global_xy",
        "unit": "mm",
        "marker_kind": "intrinsic_room_marker",
        "standalone_tag": False,
        "persistence_verified_by_this_reader": False,
    }


def set_room_marker(session, obj, point):
    """Request a native setter inside the caller's active undo operation.

    A setter return is provisional. No getter/persistence claim is made here;
    some native properties can only safely be read after operation.Apply().
    """
    xy = validate_marker_point(point)
    room = _room_interface(session, obj)
    room.MarkerPosition = session.r.Point2D(*xy)
    return {"unique_id": obj.UniqueIdS, "requested_point": xy, "status": "provisional"}


def assert_room_marker_matches(session, obj, expected_point, *, tolerance_mm=1e-6):
    """Assert an actual native getter; caller establishes the reopened session."""
    expected = validate_marker_point(expected_point)
    if isinstance(tolerance_mm, bool) or not isinstance(tolerance_mm, (int, float)):
        raise ValueError("Room marker tolerance must be a finite nonnegative number")
    if not math.isfinite(tolerance_mm) or tolerance_mm < 0:
        raise ValueError("Room marker tolerance must be a finite nonnegative number")
    observation = read_room_marker(session, obj)
    if any(not math.isclose(a, b, rel_tol=0, abs_tol=tolerance_mm)
           for a, b in zip(observation["point"], expected)):
        raise RuntimeError("Native room marker does not match the requested global XY point")
    observation.update(expected_point=expected, tolerance_mm=tolerance_mm, matches_expected=True)
    return observation
