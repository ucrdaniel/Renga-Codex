"""Inspect genuine native model dimensions; do not emulate dimension creation.

Renga API 2.50 documents LinearDimension parameter inspection but no constructor
or defining-feature binding interface. Creation therefore fails before any COM
mutation. Read/verification helpers operate on the caller's already owned
Session. The caller remains responsible for save, close and reopen.
"""
from decimal import Decimal, InvalidOperation
import math
import re
from uuid import UUID


class NativeDimensionCreationUnavailable(NotImplementedError):
    """There is no documented implementation for native dimension creation."""

    code = "API_LIMITATION"
    mutated = False


class NativeDimensionVerificationError(RuntimeError):
    """The object is not a readable, computed native model dimension."""


def dimension_capability(api_version="2.50"):
    """Return researched support, without claiming a live test of this module."""
    assessed = str(api_version) == "2.50"
    return {
        "assessed_api_version": "2.50",
        "requested_api_version": str(api_version),
        "creation_status": "API_LIMITATION" if assessed else "NOT_VERIFIED",
        "read_status": "NOT_VERIFIED",
        "read_contract": "native LinearDimension parameter inspection",
        "reason": (
            "API 2.50's IModel.CreateObject table does not include LinearDimension; "
            "INewEntityArgs has no dimension points or feature bindings. "
            "No documented defining-feature constructor was found."
            if assessed else "This API version has not been researched by this module."
        ),
        "computer_use": False,
        "text_emulation": False,
    }


def requested_distance_mm(points_mm, orientation="aligned"):
    """Independently compute an intended distance; this creates no BIM object."""
    if not isinstance(points_mm, (list, tuple)) or len(points_mm) != 2:
        raise ValueError("Exactly two explicit XY points in millimetres are required")
    points = []
    for point in points_mm:
        if not isinstance(point, (list, tuple)) or len(point) != 2:
            raise ValueError("Each point must be an explicit XY pair")
        if any(isinstance(value, bool) or not isinstance(value, (int, float)) for value in point):
            raise ValueError("Point coordinates must be finite numbers, not booleans")
        xy = tuple(float(value) for value in point)
        if not all(math.isfinite(value) for value in xy):
            raise ValueError("Point coordinates must be finite")
        points.append(xy)
    dx = points[1][0] - points[0][0]
    dy = points[1][1] - points[0][1]
    if orientation == "aligned":
        value = math.hypot(dx, dy)
    elif orientation == "horizontal":
        value = abs(dx)
    elif orientation == "vertical":
        value = abs(dy)
    else:
        raise ValueError("Orientation must be aligned, horizontal or vertical")
    if not math.isfinite(value) or value <= 0:
        raise ValueError("The requested dimension distance must be positive and finite")
    return value


def _uuid(value):
    try:
        parsed = UUID(str(value))
    except (ValueError, TypeError, AttributeError) as error:
        raise ValueError("An explicit persistent object UUID is required") from error
    if parsed.int == 0:
        raise ValueError("A nil UUID is not a valid object reference")
    return str(parsed)


def create_native_linear_dimension(session, *, points_mm, feature_refs, orientation="aligned"):
    """Reject unsupported native creation without calling COM or model.create.

    feature_refs are explicit request data, not discovered native enum values.
    Validating their shape does not prove that a feature ID has a native meaning.
    No default endpoint IDs, axis IDs or guessed binding enums are supplied.
    """
    requested_distance_mm(points_mm, orientation)
    if not isinstance(feature_refs, (list, tuple)) or len(feature_refs) != 2:
        raise ValueError("Two explicit feature references are required")
    for reference in feature_refs:
        if not isinstance(reference, dict):
            raise ValueError("Each feature reference must be a mapping")
        _uuid(reference.get("object_unique_id"))
        feature_id = reference.get("feature_id")
        if isinstance(feature_id, bool) or not isinstance(feature_id, int) or feature_id < 0:
            raise ValueError("feature_id must be explicit nonnegative integer request data")
    raise NativeDimensionCreationUnavailable(
        "Native LinearDimension creation/feature binding has no documented Renga "
        "API 2.50 implementation. No object, line or text label was created. "
        "See docs/DIMENSION_API_RESEARCH.md."
    )


def parse_dimension_display_value(text, *, decimal_separator="."):
    """Parse an unadorned native getter string under an explicit decimal rule.

    Units, prefixes, thousands grouping, formulae and combined separators are
    deliberately rejected. The result is a numeric DISPLAY value, which may be
    rounded by Renga; it is not a hidden full-precision geometric measurement.
    """
    if decimal_separator not in (".", ","):
        raise ValueError("decimal_separator must be '.' or ','")
    if not isinstance(text, str):
        raise ValueError("The native dimension display value must be a string")
    value = text.strip()
    separator = re.escape(decimal_separator)
    if not re.fullmatch(r"[+-]?\d+(?:" + separator + r"\d+)?", value, flags=re.ASCII):
        raise ValueError("Dimension value is not an unadorned number under the supplied decimal rule")
    try:
        number = Decimal(value.replace(decimal_separator, "."))
    except InvalidOperation as error:
        raise ValueError("Invalid numeric dimension display value") from error
    if not number.is_finite():
        raise ValueError("The dimension display value must be finite")
    return number


def _object_by_unique_id(model, unique_id):
    objects = model.GetObjects()
    method = getattr(objects, "GetByUniqueIdS", None)
    if method is not None:
        obj = method("{" + unique_id + "}")
        if obj is None:
            raise KeyError("Native object UUID was not found")
        if _uuid(obj.UniqueIdS) != unique_id:
            raise NativeDimensionVerificationError("Native UUID lookup returned a different object")
        return obj
    for index in range(objects.Count):
        obj = objects.GetByIndex(index)
        if _uuid(obj.UniqueIdS) == unique_id:
            return obj
    raise KeyError("Native object UUID was not found")


def read_native_linear_dimension(session, unique_id, *, model=None, decimal_separator="."):
    """Read an existing computed model dimension by persistent identity.

    This method neither saves nor reopens a project and does not claim persistence
    merely because its getter succeeded. Sheet annotation objects not exposed as
    LinearDimension by the SDK are intentionally outside this reader's scope.
    """
    uid = _uuid(unique_id)
    obj = _object_by_unique_id(session.model if model is None else model, uid)
    native_type = session.sdk.types.get("LinearDimension")
    if native_type is None:
        raise NativeDimensionVerificationError("The locally supplied SDK has no LinearDimension type")
    if _uuid(obj.ObjectTypeS) != _uuid(native_type):
        raise NativeDimensionVerificationError("Object is not a native model LinearDimension")
    parameters = obj.GetParameters()
    if parameters is None:
        raise NativeDimensionVerificationError("Native dimension has no parameter container")
    found = {}
    for name in ("DimensionValueType", "DimensionValue"):
        guid = session.sdk.parameters.get(name)
        if guid is None or not parameters.ContainsS(guid):
            raise NativeDimensionVerificationError("Native dimension lacks " + name)
        found[name] = parameters.GetS(guid)
        if found[name] is None or not found[name].HasValue:
            raise NativeDimensionVerificationError("Native dimension has no value for " + name)
        expected_type = 2 if name == "DimensionValueType" else 4
        if found[name].ValueType != expected_type:
            raise NativeDimensionVerificationError("Native dimension parameter has unexpected value type: " + name)
    mode = found["DimensionValueType"].GetIntValue()
    if mode != 1:
        raise NativeDimensionVerificationError(
            "DimensionValueType is not 1: text overrides are not computed dimension evidence"
        )
    text = found["DimensionValue"].GetStringValue()
    numeric = parse_dimension_display_value(text, decimal_separator=decimal_separator)
    return {
        "unique_id": uid,
        "id": int(obj.Id),
        "native_type": "LinearDimension",
        "dimension_value_type": mode,
        "computed": True,
        "display_text": text,
        "numeric_display_value": str(numeric),
        "decimal_separator": decimal_separator,
        "dimension_value_read_only": bool(found["DimensionValue"].IsReadOnly),
        "measurement_scope": "native_computed_display_value",
        "display_unit": None,
        "persistence_verified_by_this_reader": False,
    }


def verify_native_linear_dimension(session, unique_id, expected_display_value, *,
                                   tolerance="0.000001", decimal_separator=".", model=None):
    """Compare native computed display value; call on a freshly reopened Session.

    Expected value and tolerance use the native display's unit. No unit is inferred
    from the text and no precision beyond the native display is claimed.
    """
    if isinstance(expected_display_value, bool) or isinstance(tolerance, bool):
        raise ValueError("Expected value and tolerance cannot be booleans")
    try:
        expected = Decimal(str(expected_display_value))
        allowed = Decimal(str(tolerance))
    except InvalidOperation as error:
        raise ValueError("Expected value and tolerance must be numbers") from error
    if not expected.is_finite() or not allowed.is_finite() or allowed < 0:
        raise ValueError("Expected value and tolerance must be finite; tolerance must be nonnegative")
    observation = read_native_linear_dimension(
        session, unique_id, model=model, decimal_separator=decimal_separator
    )
    actual = Decimal(observation["numeric_display_value"])
    observation.update({
        "expected_display_value": str(expected),
        "tolerance_display_units": str(allowed),
        "absolute_difference_display_units": str(abs(actual - expected)),
        "matches_expected_display_value": abs(actual - expected) <= allowed,
    })
    return observation
