"""Own synthetic IFC4 storey/grid fixture; no COM or third-party runtime.

This augments generate_storey_fixture's own content with six IfcGridAxis
objects in a rectangular IfcGrid. It tests import mapping, not native Renga
axis creation. Output is restricted to the configured bridge write root.

IFC4 ADD2 TC1 signatures and FootPrint representation rules:
https://standards.buildingsmart.org/IFC/RELEASE/IFC4/ADD2_TC1/HTML/schema/ifcproductextension/lexical/ifcgrid.htm
https://standards.buildingsmart.org/IFC/RELEASE/IFC4/ADD2_TC1/HTML/schema/ifcgeometricconstraintresource/lexical/ifcgridaxis.htm
"""
from __future__ import annotations

import argparse
from pathlib import Path
import re
import uuid

from generate_storey_fixture import fixture_ifc


def grid_fixture_ifc() -> str:
    """Return three own storeys plus one 6x6 m grid on the zero storey.

    U labels A/B/C lie at Y=0/3000/6000, V labels 1/2/3 at
    X=0/3000/6000 mm. Axis curves extend from -1000 to 7000 mm.
    IFC axes have a two-dimensional curve, belong to one grid list each,
    and share the same curves with the grid's FootPrint representation.
    """
    base = fixture_ifc()
    body_end = base.index("\nENDSEC;", base.index("\nDATA;"))
    body = base[:body_end]
    rows = dict(re.findall(r"^#(\d+)=(.*);$", body, re.M))

    def reference(kind):
        return "#" + next(identifier for identifier, value in rows.items()
                         if value.startswith(kind + "("))

    owner = reference("IFCOWNERHISTORY")
    context = reference("IFCGEOMETRICREPRESENTATIONCONTEXT")
    storey = reference("IFCBUILDINGSTOREY")
    # Six preceding inherited attributes include placement in position 6.
    # The fixture's storey has no quoted comma, so this deliberately narrow
    # extraction does not pretend to be an arbitrary STEP parser.
    storey_record = rows[storey[1:]]
    storey_placement = storey_record.split(",")[5]
    identity = reference("IFCAXIS2PLACEMENT3D")
    count = max(map(int, rows))
    lines = []

    def entity(value):
        nonlocal count
        count += 1
        lines.append(f"#{count}={value};")
        return f"#{count}"

    def gid(seed):
        alphabet = "0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz_$"
        number = uuid.uuid5(uuid.NAMESPACE_URL, "renga-bridge-grid-fixture/" + seed).int
        encoded = ""
        for _ in range(22):
            encoded = alphabet[number % 64] + encoded
            number //= 64
        return encoded

    axes = [[], []]
    curves = []
    for family, labels in enumerate((("A", "B", "C"), ("1", "2", "3"))):
        for coordinate, label in zip((0, 3000, 6000), labels):
            endpoints = ((-1000, coordinate), (7000, coordinate)) if family == 0 else (
                (coordinate, -1000), (coordinate, 7000))
            points = [entity(f"IFCCARTESIANPOINT(({x}.,{y}.))") for x, y in endpoints]
            curve = entity(f"IFCPOLYLINE(({','.join(points)}))")
            curves.append(curve)
            axes[family].append(entity(f"IFCGRIDAXIS('{label}',{curve},.T.)"))
    curve_set = entity(f"IFCGEOMETRICCURVESET(({','.join(curves)}))")
    footprint = entity(f"IFCSHAPEREPRESENTATION({context},'FootPrint','GeometricCurveSet',({curve_set}))")
    shape = entity(f"IFCPRODUCTDEFINITIONSHAPE($,$,({footprint}))")
    placement = entity(f"IFCLOCALPLACEMENT({storey_placement},{identity})")
    grid = entity(f"IFCGRID('{gid('grid')}',{owner},'Bridge rectangular grid',$,$,{placement},"
                  f"{shape},({','.join(axes[0])}),({','.join(axes[1])}),$,.RECTANGULAR.)")
    entity(f"IFCRELCONTAINEDINSPATIALSTRUCTURE('{gid('contained-grid')}',{owner},$,$,({grid}),{storey})")
    return body + "\n" + "\n".join(lines) + base[body_end:]


def write_grid_fixture(output: Path) -> Path:
    from renga_codex_bridge.safety import checked_path
    output = checked_path(output, write=True, new=True)
    if output.suffix.lower() != ".ifc":
        raise ValueError("Output must be a new .ifc inside the configured write root")
    # Resolve the existing parent first to reject junction escapes. Never
    # overwrite an existing artifact or create the user's parent directories.
    if not output.parent.is_dir():
        raise ValueError("Create the intended test subfolder before generation")
    with output.open("x", encoding="ascii", newline="\n") as stream:
        stream.write(grid_fixture_ifc())
    return output


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    try:
        print(write_grid_fixture(args.output))
    except (ValueError, FileExistsError) as error:
        parser.error(str(error))
