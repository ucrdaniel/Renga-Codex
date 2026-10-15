"""Validate explicit orthogonal IFC grid seed requests, in millimetres.

The validator creates no IFC or native object. The bootstrap's import/save/
reopen checks establish whether Renga has produced genuine native axes.
"""
import math
import unicodedata


MAX_GRID_AXES = 1000


def _number(value, label):
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError(label + " must be a finite number, not a boolean")
    try:
        result = float(value)
    except OverflowError as error:
        raise ValueError(label + " must be finite") from error
    if not math.isfinite(result):
        raise ValueError(label + " must be finite")
    return result


def validate_grid_spec(grid):
    """Return canonical x/y families and explicit [xmin,ymin,xmax,ymax].

    x axes have constant X, run parallel to Y, and use the supplied names.
    y axes have constant Y and run parallel to X. Both are required. Labels
    are explicit, globally unique case-insensitively and preserved verbatim;
    there is no generated numbering or naming convention. Coordinates are
    unique within each family and lie within the requested bounds.
    """
    if not isinstance(grid, dict) or set(grid) != {"x", "y", "bounds_mm"}:
        raise ValueError("grid requires exactly x, y and bounds_mm")
    raw_bounds = grid["bounds_mm"]
    if not isinstance(raw_bounds, (list, tuple)) or len(raw_bounds) != 4:
        raise ValueError("grid bounds_mm must be [xmin,ymin,xmax,ymax]")
    bounds = [_number(value, "grid bounds_mm") for value in raw_bounds]
    xmin, ymin, xmax, ymax = bounds
    if xmin >= xmax or ymin >= ymax:
        raise ValueError("grid bounds_mm must have positive width and height")
    if not all(isinstance(grid[family], (list, tuple)) and grid[family] for family in ("x", "y")):
        raise ValueError("grid x and y must both be nonempty axis lists")
    if len(grid["x"]) + len(grid["y"]) > MAX_GRID_AXES:
        raise ValueError("grid exceeds the 1000-axis limit")

    canonical = {"x": [], "y": [], "bounds_mm": bounds}
    all_names = set()
    for family, low, high in (("x", xmin, xmax), ("y", ymin, ymax)):
        coordinates = set()
        for axis in grid[family]:
            if not isinstance(axis, dict) or set(axis) != {"name", "position_mm"}:
                raise ValueError("Each grid axis requires exactly name and position_mm")
            name = axis["name"]
            if (not isinstance(name, str) or not name or name != name.strip()
                    or any(unicodedata.category(char) in {"Cc", "Cs"} for char in name)):
                raise ValueError("Grid axis name must be nonempty text without edge whitespace or controls")
            key = name.casefold()
            if key in all_names:
                raise ValueError("Grid axis names must be globally unique, ignoring case")
            position = _number(axis["position_mm"], "Grid axis position_mm")
            if position in coordinates:
                raise ValueError("Grid axis coordinates must be unique within each family")
            if position < low or position > high:
                raise ValueError("Grid axis position_mm lies outside bounds_mm")
            all_names.add(key)
            coordinates.add(position)
            canonical[family].append({"name": name, "position_mm": position})
    return canonical
