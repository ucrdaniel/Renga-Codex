"""Pure validation for explicit native creation axes; no COM or rotation API.

An orthonormal pair is valid input, not evidence that Renga accepts it for every
entity. Native creation and save/reopen must verify the requested placement.
"""

import math


DEFAULT_X_AXIS = (1.0, 0.0, 0.0)
DEFAULT_Z_AXIS = (0.0, 0.0, 1.0)
AXIS_TOLERANCE = 1e-9
HORIZONTAL_KINDS = frozenset({
    "Wall", "Floor", "Room", "Roof", "Opening", "Stair", "Ramp",
    "WallFoundation", "Door", "Window", "Level",
})


class NativePlacementVerificationError(RuntimeError):
    """The observed placement does not match explicitly requested fields."""


def _vector3(value, name):
    if not isinstance(value, (tuple, list)) or len(value) != 3:
        raise ValueError(name + " requires three explicit coordinates")
    if any(isinstance(v, bool) or not isinstance(v, (int, float)) for v in value):
        raise ValueError(name + " coordinates must be numbers, not booleans")
    try:
        result = tuple(float(v) for v in value)
    except (ValueError, OverflowError) as error:
        raise ValueError(name + " coordinates must be finite") from error
    if not all(math.isfinite(v) for v in result):
        raise ValueError(name + " coordinates must be finite")
    return result


def _close(a, b, tolerance=AXIS_TOLERANCE):
    return math.isclose(a, b, rel_tol=0.0, abs_tol=tolerance)


def validate_creation_axes(x_axis=DEFAULT_X_AXIS, z_axis=DEFAULT_Z_AXIS, *, kind=None):
    """Return explicit unit axes, without silently rescaling or orthogonalizing.

    Horizontal categories support yaw in this contract. Other categories only
    pass mathematical validation; their native tilt behavior needs live tests.
    Nondefault Level axes are rejected until a persistent native path is known.
    """
    if kind is not None and not isinstance(kind, str):
        raise ValueError("kind must be a string or None")
    x = _vector3(x_axis, "x_axis")
    z = _vector3(z_axis, "z_axis")
    for name, vector in (("x_axis", x), ("z_axis", z)):
        if not _close(math.hypot(*vector), 1.0):
            raise ValueError(name + " must be a unit vector; scaled axes are not accepted")
    if not _close(sum(a * b for a, b in zip(x, z)), 0.0):
        raise ValueError("x_axis and z_axis must be perpendicular")
    if kind in HORIZONTAL_KINDS and not all(_close(a, b) for a, b in zip(z, DEFAULT_Z_AXIS)):
        raise ValueError(str(kind) + " creation currently requires horizontal placement with z_axis=[0,0,1]")
    if kind == "Level" and not all(_close(a, b) for a, b in zip(x, DEFAULT_X_AXIS)):
        raise NotImplementedError("Nondefault Level axes are not verified by the native API")
    return {"x_axis": list(x), "z_axis": list(z)}


def validate_wall_host_orientation(x_axis, z_axis, wall_direction):
    """Check co/counterdirection against a real straight wall's global baseline.

    wall_direction is a measured endpoint delta, not a user placement axis: its
    length is discarded explicitly. The caller must reject curved/polycurve
    hosts and obtain endpoints in a declared global XY coordinate system.
    """
    axes = validate_creation_axes(x_axis, z_axis, kind="Door")
    direction = _vector3(wall_direction, "wall_direction")
    if not _close(direction[2], 0.0):
        raise ValueError("wall_direction must be horizontal")
    length = math.hypot(*direction)
    if length <= AXIS_TOLERANCE:
        raise ValueError("wall_direction must have nonzero length")
    tangent = tuple(v / length for v in direction)
    x = axes["x_axis"]
    same = all(_close(a, b) for a, b in zip(x, tangent))
    opposite = all(_close(a, -b) for a, b in zip(x, tangent))
    if not same and not opposite:
        raise ValueError("Door/Window x_axis must be co-directed or counter-directed with the straight host wall")
    return "co_directed" if same else "counter_directed"


def assert_pose_matches(expected, actual, *, abs_tol=1e-6):
    """Compare requested origin/axes with an observation; does not claim reopen.

    expected may contain a subset of origin/x_axis/z_axis. Exact requested axes
    must be supplied by the caller rather than copied from a possibly ignored
    native setter. This also detects a reversed side with an unchanged origin.
    """
    if isinstance(abs_tol, bool) or not isinstance(abs_tol, (int, float)):
        raise ValueError("abs_tol must be a finite nonnegative number")
    try:
        abs_tol = float(abs_tol)
    except OverflowError as error:
        raise ValueError("abs_tol must be a finite nonnegative number") from error
    if not math.isfinite(abs_tol) or abs_tol < 0:
        raise ValueError("abs_tol must be a finite nonnegative number")
    if not isinstance(expected, dict) or not expected or set(expected) - {"origin", "x_axis", "z_axis"}:
        raise ValueError("Expected pose must name origin, x_axis or z_axis")
    if not isinstance(actual, dict):
        raise NativePlacementVerificationError("Native placement observation is absent")
    for field, values in expected.items():
        wanted = _vector3(values, field)
        if field not in actual:
            raise NativePlacementVerificationError("Native placement lacks " + field)
        observed = _vector3(actual[field], "native " + field)
        if not all(_close(a, b, abs_tol) for a, b in zip(wanted, observed)):
            raise NativePlacementVerificationError("Native placement differs from requested " + field
                + "; expected=" + repr(list(wanted)) + "; actual=" + repr(list(observed)))
    return {"compared_fields": list(expected), "persistence_verified_by_this_helper": False}
