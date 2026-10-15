"""Check a narrow IFC4 grid subset exported by Renga after native reopening.

This is not a general IFC parser, schema validator, or Axis COM geometry getter.
Unsupported units, placements, curves and ambiguous mappings fail closed.
The caller must establish the export's provenance; an input IFC cannot prove
that native geometry was saved. No filesystem or COM access occurs here.
"""
import math
import re
import unicodedata

from .grid_spec import validate_grid_spec


class GridExportVerificationError(ValueError):
    """The exported grid is unreadable, unsupported, or differs from request."""


def _fail(message):
    raise GridExportVerificationError(message)


def _split(text, separator):
    """Split STEP statements/arguments outside literals and nested aggregates."""
    values = []
    start = 0
    depth = 0
    quoted = False
    i = 0
    while i < len(text):
        char = text[i]
        if char == "'":
            if quoted and i + 1 < len(text) and text[i + 1] == "'":
                i += 2
                continue
            quoted = not quoted
        elif not quoted:
            if char == "(":
                depth += 1
            elif char == ")":
                depth -= 1
                if depth < 0:
                    _fail("Unbalanced STEP aggregate")
            elif char == separator and depth == 0:
                values.append(text[start:i].strip())
                start = i + 1
        i += 1
    if quoted or depth:
        _fail("Unterminated STEP literal or aggregate")
    if text[start:].strip():
        values.append(text[start:].strip())
    return values


def _aggregate(value):
    value = value.strip()
    if not (value.startswith("(") and value.endswith(")")):
        _fail("Expected STEP aggregate")
    return _split(value[1:-1], ",")


def decode_step_string(value):
    """Decode one STEP literal: doubled quotes and X2/X4 Unicode blocks only."""
    if len(value) < 2 or value[0] != "'" or value[-1] != "'":
        _fail("Expected STEP string literal")
    value = value[1:-1]
    result = []
    index = 0
    while index < len(value):
        char = value[index]
        if char == "'":
            if value[index:index + 2] != "''":
                _fail("Unescaped apostrophe in STEP string")
            result.append("'")
            index += 2
        elif char == "\\":
            if value[index:index + 4] not in ("\\X2\\", "\\X4\\"):
                _fail("Unsupported STEP string escape")
            kind = value[index + 2]
            end = value.find("\\X0\\", index + 4)
            if end < 0:
                _fail("Unterminated STEP Unicode block")
            digits = value[index + 4:end]
            group = 4 if kind == "2" else 8
            if not digits or len(digits) % group or not re.fullmatch(r"[0-9A-Fa-f]+", digits):
                _fail("Malformed STEP Unicode block")
            try:
                result.append(bytes.fromhex(digits).decode("utf-16-be" if kind == "2" else "utf-32-be"))
            except UnicodeError as error:
                raise GridExportVerificationError("Invalid STEP Unicode code point") from error
            index = end + 4
        else:
            result.append(char)
            index += 1
    decoded = "".join(result)
    if any(unicodedata.category(char) in {"Cc", "Cs"} for char in decoded):
        _fail("Control or surrogate in STEP label")
    return decoded


def _number(value):
    if not re.fullmatch(r"[+-]?(?:\d+(?:\.\d*)?|\.\d+)(?:[Ee][+-]?\d+)?", value):
        _fail("Unsupported STEP coordinate number")
    result = float(value)
    if not math.isfinite(result):
        _fail("Nonfinite STEP coordinate")
    return result


def _records(text):
    if not isinstance(text, str) or len(text) > 64 * 1024 * 1024:
        _fail("Expected an IFC text export below 64 MiB")
    # Comments are uncommon in the exporter subset. Reject rather than remove
    # them with a regex that could alter comment-looking text inside a literal.
    statements = _split(text, ";")
    if not statements or statements[0] != "ISO-10303-21" or statements[-1] != "END-ISO-10303-21":
        _fail("Expected a complete STEP exchange file")
    records = {}
    inside = False
    sections = 0
    schema = False
    for statement in statements:
        if re.fullmatch(r"FILE_SCHEMA\s*\(\s*\(\s*'IFC4'\s*\)\s*\)", statement):
            schema = True
        if statement == "DATA":
            if inside:
                _fail("Nested IFC DATA section")
            inside = True
            sections += 1
            continue
        if statement == "ENDSEC":
            inside = False
            continue
        if not inside:
            continue
        match = re.fullmatch(r"#([1-9]\d*)\s*=\s*([A-Z][A-Z0-9_]*)\s*\((.*)\)", statement, re.S)
        if not match:
            _fail("Unsupported IFC DATA record syntax")
        identifier = "#" + match[1]
        if identifier in records:
            _fail("Duplicate IFC instance identifier")
        records[identifier] = (match[2], _split(match[3], ","))
    if not schema or sections != 1 or inside or not records:
        _fail("Expected one complete IFC4 DATA section")
    return records


def verify_exported_grid(text, grid):
    """Verify names and global endpoints against explicit grid request.

    Supports straight two-point polylines/indexed polycurves and translation
    chains with identity orientations only. Requires the project's actual
    assigned length unit to be SI millimetres. Endpoints may be reversed.
    A successful result establishes this text comparison; the caller proves
    native Axis identities and that this export followed save/close/reopen.
    """
    expected = validate_grid_spec(grid)
    records = _records(text)

    def record(reference, kind=None, count=None):
        if not re.fullmatch(r"#[1-9]\d*", reference) or reference not in records:
            _fail("Missing or invalid IFC reference")
        name, args = records[reference]
        if kind is not None and name != kind:
            _fail("Unsupported IFC entity: expected " + kind + ", got " + name)
        if count is not None and len(args) != count:
            _fail("Unexpected IFC argument count for " + name)
        return name, args

    projects = [args for kind, args in records.values() if kind == "IFCPROJECT"]
    if len(projects) != 1 or len(projects[0]) != 9:
        _fail("Expected exactly one IFC project")
    _, assignment = record(projects[0][8], "IFCUNITASSIGNMENT", 1)
    length_units = []
    for reference in _aggregate(assignment[0]):
        name, args = record(reference)
        if ".LENGTHUNIT." in args:
            length_units.append((name, args))
    if len(length_units) != 1 or length_units[0] != ("IFCSIUNIT", ["*", ".LENGTHUNIT.", ".MILLI.", ".METRE."]):
        _fail("Project length unit must be unambiguous SI millimetres")

    def tuple_numbers(value, dimension):
        numbers = [_number(part) for part in _aggregate(value)]
        if len(numbers) != dimension:
            _fail("Unexpected IFC point/direction dimensionality")
        return numbers

    def point3(reference):
        _, args = record(reference, "IFCCARTESIANPOINT", 1)
        return tuple_numbers(args[0], 3)

    def direction(reference, expected_direction):
        if reference == "$":
            return
        _, args = record(reference, "IFCDIRECTION", 1)
        values = tuple_numbers(args[0], 3)
        norm = math.hypot(*values)
        if norm == 0 or not all(math.isclose(v / norm, e, rel_tol=0, abs_tol=1e-12)
                                for v, e in zip(values, expected_direction)):
            _fail("Grid verification supports identity placement orientation only")

    def axis_translation(reference):
        _, args = record(reference, "IFCAXIS2PLACEMENT3D", 3)
        direction(args[1], (0, 0, 1))
        direction(args[2], (1, 0, 0))
        return point3(args[0])

    # Nontrivial context world frames are deliberately outside this narrow
    # subset; local placement translations are checked below independently.
    contexts = _aggregate(projects[0][7])
    if not contexts:
        _fail("Expected a project representation context")
    for reference in contexts:
        _, args = record(reference, "IFCGEOMETRICREPRESENTATIONCONTEXT", 6)
        if args[2] != "3" or any(abs(v) > 1e-6 for v in axis_translation(args[4])):
            _fail("Unsupported IFC representation world frame")

    def translation(reference):
        total = [0., 0., 0.]
        seen = set()
        while reference != "$":
            if reference in seen or len(seen) >= 256:
                _fail("Cyclic or excessive IFC placement chain")
            seen.add(reference)
            _, args = record(reference, "IFCLOCALPLACEMENT", 2)
            delta = axis_translation(args[1])
            total = [a + b for a, b in zip(total, delta)]
            reference = args[0]
        if not all(math.isfinite(v) for v in total):
            _fail("Nonfinite aggregate IFC translation")
        return total

    def endpoints(reference):
        kind, args = record(reference)
        if kind == "IFCINDEXEDPOLYCURVE":
            if len(args) != 3 or args[1] != "$" or args[2] not in {"$", ".F."}:
                _fail("Only unsegmented non-self-intersecting indexed polylines are supported")
            _, point_args = record(args[0], "IFCCARTESIANPOINTLIST2D", 1)
            values = [tuple_numbers(value, 2) for value in _aggregate(point_args[0])]
        elif kind == "IFCPOLYLINE":
            if len(args) != 1:
                _fail("Unexpected polyline argument count")
            values = []
            for reference in _aggregate(args[0]):
                _, point_args = record(reference, "IFCCARTESIANPOINT", 1)
                values.append(tuple_numbers(point_args[0], 2))
        else:
            _fail("Unsupported IFC grid curve: " + kind)
        if len(values) != 2 or values[0] == values[1]:
            _fail("Grid axis must have exactly two distinct endpoints")
        return values

    grids = [args for kind, args in records.values() if kind == "IFCGRID"]
    if len(grids) != 1 or len(grids[0]) != 11:
        _fail("Expected exactly one exported IFC4 grid")
    args = grids[0]
    if args[9] != "$" or args[10] not in {"$", ".RECTANGULAR."}:
        _fail("Only a rectangular U/V grid is supported")
    offset = translation(args[5])
    if abs(offset[2]) > 1e-6:
        _fail("Expected grid in the global XY plane at Z=0")
    axis_refs = _aggregate(args[7]) + _aggregate(args[8])
    if not _aggregate(args[7]) or not _aggregate(args[8]) or len(set(axis_refs)) != len(axis_refs):
        _fail("Grid axes must occur once in nonempty U/V lists")
    all_axis_refs = {ref for ref, (kind, _) in records.items() if kind == "IFCGRIDAXIS"}
    if set(axis_refs) != all_axis_refs:
        _fail("Unassigned or unexpected exported grid axes")

    xmin, ymin, xmax, ymax = expected["bounds_mm"]
    wanted = {}
    for family in ("x", "y"):
        for spec in expected[family]:
            coordinate = spec["position_mm"]
            points = [[coordinate, ymin], [coordinate, ymax]] if family == "x" else [
                [xmin, coordinate], [xmax, coordinate]]
            wanted[spec["name"]] = (family, points)
    observed = {}
    for reference in axis_refs:
        _, axis = record(reference, "IFCGRIDAXIS", 3)
        name = decode_step_string(axis[0])
        if axis[2] not in {".T.", ".F."}:
            _fail("Expected explicit grid axis SameSense boolean")
        if name not in wanted or name in observed:
            _fail("Unexpected or duplicate exported grid axis name")
        points = [[p[0] + offset[0], p[1] + offset[1]] for p in endpoints(axis[1])]
        family, requested = wanted[name]

        def points_match(first, second):
            return all(math.isclose(a, b, rel_tol=0, abs_tol=1e-6)
                       for p, q in zip(first, second) for a, b in zip(p, q))

        if not (points_match(points, requested) or points_match(points[::-1], requested)):
            _fail("Exported endpoints differ from requested grid for axis " + name)
        observed[name] = {"name": name, "family": family, "endpoints_mm": points, "z_mm": offset[2]}
    if set(observed) != set(wanted):
        _fail("Exported grid is missing requested axes")
    return {
        "status": "passed", "axis_count": len(observed), "grid_count": 1,
        "unit": "mm", "tolerance_mm": 1e-6,
        "verification_scope": "exported_ifc_grid_coordinates",
        "direct_axis_com_geometry_getter": False,
        "export_provenance_verified_by_this_reader": False,
        "axes": [observed[spec["name"]] for family in ("x", "y") for spec in expected[family]],
    }
