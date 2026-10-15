"""Own-source IFC4 spatial seed for the official new-project import route.

The slabs are disposable import carriers, not the requested finished BIM model.
The native adapter must verify imported Levels and remove every non-Level
carrier before saving its clean seed project. Direct level setters are separate.
This module is pure Python and includes no vendor code or generated SDK data.
"""
from __future__ import annotations

import hashlib
import json
import math
import unicodedata
import uuid


def validate_level_specs(levels: object) -> list[dict]:
    """Return a copied, explicit list of names and finite elevations in mm.

    Names are kept exactly as requested, including significant spaces. Reject
    controls and surrogate code points because they cannot form safe IFC names.
    Duplicate numeric elevations (including 0/-0) are rejected, not merged.
    """
    if not isinstance(levels, list) or not 1 <= len(levels) <= 1000:
        raise ValueError("levels must be a list of 1 to 1000 explicit level specifications")
    result = []
    names: set[str] = set()
    elevations: set[float] = set()
    for level in levels:
        if not isinstance(level, dict) or set(level) != {"name", "elevation_mm"}:
            raise ValueError("Each level requires exactly name and elevation_mm")
        name = level["name"]
        if (not isinstance(name, str) or not name.strip()
                or any(unicodedata.category(char) in {"Cc", "Cs"} for char in name)):
            raise ValueError("Level name must be a nonempty Unicode string without controls or surrogates")
        if name in names:
            raise ValueError("Level names must be unique")
        elevation = level["elevation_mm"]
        if isinstance(elevation, bool) or not isinstance(elevation, (int, float)):
            raise ValueError("elevation_mm must be an explicit finite number in millimeters")
        try:
            value = float(elevation)
        except (OverflowError, ValueError) as error:
            raise ValueError("elevation_mm must be finite") from error
        if not math.isfinite(value):
            raise ValueError("elevation_mm must be finite")
        if value in elevations:
            raise ValueError("Level elevations must be unique")
        value = 0.0 if value == 0 else value
        names.add(name)
        elevations.add(value)
        result.append({"name": name, "elevation_mm": value})
    return result


def _ifc_string(value: str) -> str:
    """Produce one ASCII STEP string; data cannot escape its quoted literal."""
    pieces = []
    for char in value:
        number = ord(char)
        if char == "'":
            pieces.append("''")
        elif 32 <= number <= 126 and char != "\\":
            pieces.append(char)
        elif number <= 0xFFFF:
            pieces.append(f"\\X2\\{number:04X}\\X0\\")
        else:
            pieces.append(f"\\X4\\{number:08X}\\X0\\")
    return "'" + "".join(pieces) + "'"


def _step_real(value: float) -> str:
    text = repr(value).upper()
    # STEP real syntax needs a decimal point even with an exponent.
    mantissa, separator, exponent = text.partition("E")
    if "." not in mantissa:
        mantissa += "."
    return mantissa + (separator + exponent if separator else "")


def build_level_seed_ifc(levels: object, grid: object = None) -> str:
    """Return deterministic ASCII IFC4 with storeys, carriers and optional grid.

    Every coordinate/elevation is in explicitly declared millimeters. Storey
    local placement and Elevation agree. Native importing, carrier removal,
    identity/quantity checks and save/reopen remain the adapter's responsibility.
    """
    specs = validate_level_specs(levels)
    if grid is not None:
        from .grid_spec import validate_grid_spec
        grid = validate_grid_spec(grid)
    content = specs if grid is None else {"levels": specs, "grid": grid}
    seed = hashlib.sha256(json.dumps(content, ensure_ascii=True, separators=(",", ":")).encode("ascii")).hexdigest()
    alphabet = "0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz_$"

    def gid(label: str) -> str:
        number = uuid.uuid5(uuid.NAMESPACE_URL, "renga-codex-bridge/level-seed/" + seed + "/" + label).int
        encoded = ""
        for _ in range(22):
            encoded = alphabet[number % 64] + encoded
            number //= 64
        return encoded

    lines: list[str] = []

    def entity(value: str) -> str:
        lines.append(f"#{len(lines) + 1}={value};")
        return f"#{len(lines)}"

    person = entity("IFCPERSON($,$,'Bridge Test',$,$,$,$,$)")
    organization = entity("IFCORGANIZATION($,'Renga Codex Bridge',$,$,$)")
    actor = entity(f"IFCPERSONANDORGANIZATION({person},{organization},$)")
    application = entity(f"IFCAPPLICATION({organization},'1','Spatial seed generator','BRIDGE')")
    owner = entity(f"IFCOWNERHISTORY({actor},{application},$,.ADDED.,$,$,$,0)")
    zero = entity("IFCCARTESIANPOINT((0.,0.,0.))")
    vertical = entity("IFCDIRECTION((0.,0.,1.))")
    horizontal = entity("IFCDIRECTION((1.,0.,0.))")
    coordinate_system = entity(f"IFCAXIS2PLACEMENT3D({zero},{vertical},{horizontal})")
    world = entity(f"IFCLOCALPLACEMENT($,{coordinate_system})")
    context = entity(f"IFCGEOMETRICREPRESENTATIONCONTEXT($,'Model',3,0.00001,{coordinate_system},$)")
    length = entity("IFCSIUNIT(*,.LENGTHUNIT.,.MILLI.,.METRE.)")
    area = entity("IFCSIUNIT(*,.AREAUNIT.,$,.SQUARE_METRE.)")
    volume = entity("IFCSIUNIT(*,.VOLUMEUNIT.,$,.CUBIC_METRE.)")
    units = entity(f"IFCUNITASSIGNMENT(({length},{area},{volume}))")
    project = entity(f"IFCPROJECT('{gid('project')}',{owner},'Level seed',$,$,$,$,({context}),{units})")
    site = entity(f"IFCSITE('{gid('site')}',{owner},'Seed site',$,$,{world},$,$,.ELEMENT.,$,$,$,$,$)")
    building_placement = entity(f"IFCLOCALPLACEMENT({world},{coordinate_system})")
    building = entity(f"IFCBUILDING('{gid('building')}',{owner},'Seed building',$,$,{building_placement},$,$,.ELEMENT.,$,$,$)")
    entity(f"IFCRELAGGREGATES('{gid('project-sites')}',{owner},$,$,{project},({site}))")
    entity(f"IFCRELAGGREGATES('{gid('site-buildings')}',{owner},$,$,{site},({building}))")
    storeys = []
    for index, spec in enumerate(specs):
        elevation = _step_real(spec["elevation_mm"])
        origin = entity(f"IFCCARTESIANPOINT((0.,0.,{elevation}))")
        axis = entity(f"IFCAXIS2PLACEMENT3D({origin},{vertical},{horizontal})")
        placement = entity(f"IFCLOCALPLACEMENT({building_placement},{axis})")
        storey = entity(f"IFCBUILDINGSTOREY('{gid('storey-' + str(index))}',{owner},{_ifc_string(spec['name'])},$,$,{placement},$,$,.ELEMENT.,{elevation})")
        storeys.append(storey)
        slab_placement = entity(f"IFCLOCALPLACEMENT({placement},{coordinate_system})")
        profile_origin = entity("IFCCARTESIANPOINT((3000.,2000.))")
        profile_axis = entity(f"IFCAXIS2PLACEMENT2D({profile_origin},$)")
        profile = entity(f"IFCRECTANGLEPROFILEDEF(.AREA.,'Temporary carrier',{profile_axis},6000.,4000.)")
        solid = entity(f"IFCEXTRUDEDAREASOLID({profile},{coordinate_system},{vertical},200.)")
        representation = entity(f"IFCSHAPEREPRESENTATION({context},'Body','SweptSolid',({solid}))")
        shape = entity(f"IFCPRODUCTDEFINITIONSHAPE($,$,({representation}))")
        slab = entity(f"IFCSLAB('{gid('carrier-' + str(index))}',{owner},'Disposable level carrier',$,$,{slab_placement},{shape},'C{index}',.FLOOR.)")
        entity(f"IFCRELCONTAINEDINSPATIALSTRUCTURE('{gid('contained-' + str(index))}',{owner},$,$,({slab}),{storey})")
    entity(f"IFCRELAGGREGATES('{gid('building-storeys')}',{owner},$,$,{building},({','.join(storeys)}))")
    if grid is not None:
        xmin, ymin, xmax, ymax = grid["bounds_mm"]
        axis_families: list[list[str]] = [[], []]
        curves = []
        # IFC U curves are horizontal (constant Y); V curves are vertical
        # (constant X). Input x/y names denote their coordinate, not direction.
        for family, specs_at_coordinate in enumerate((grid["y"], grid["x"])):
            for spec in specs_at_coordinate:
                coordinate = spec["position_mm"]
                endpoints = ((xmin, coordinate), (xmax, coordinate)) if family == 0 else (
                    (coordinate, ymin), (coordinate, ymax))
                points = [entity(f"IFCCARTESIANPOINT(({_step_real(x)},{_step_real(y)}))") for x, y in endpoints]
                curve = entity(f"IFCPOLYLINE(({','.join(points)}))")
                curves.append(curve)
                axis_families[family].append(entity(f"IFCGRIDAXIS({_ifc_string(spec['name'])},{curve},.T.)"))
        curve_set = entity(f"IFCGEOMETRICCURVESET(({','.join(curves)}))")
        footprint = entity(f"IFCSHAPEREPRESENTATION({context},'FootPrint','GeometricCurveSet',({curve_set}))")
        shape = entity(f"IFCPRODUCTDEFINITIONSHAPE($,$,({footprint}))")
        # Coordinates are world XY regardless of the first storey's elevation.
        placement = entity(f"IFCLOCALPLACEMENT({building_placement},{coordinate_system})")
        grid_entity = entity(f"IFCGRID('{gid('grid')}',{owner},'Bridge rectangular grid',$,$,{placement},"
                             f"{shape},({','.join(axis_families[0])}),({','.join(axis_families[1])}),$,.RECTANGULAR.)")
        entity(f"IFCRELCONTAINEDINSPATIALSTRUCTURE('{gid('contained-grid')}',{owner},$,$,({grid_entity}),{storeys[0]})")
    header = (
        "ISO-10303-21;\nHEADER;\n"
        "FILE_DESCRIPTION(('ViewDefinition [DesignTransferView]'),'2;1');\n"
        "FILE_NAME('level-seed.ifc','2026-10-15T00:00:00',('Bridge'),('Bridge'),"
        "'Renga Codex Bridge','Renga Codex Bridge','');\n"
        "FILE_SCHEMA(('IFC4'));\nENDSEC;\nDATA;\n"
    )
    return header + "\n".join(lines) + "\nENDSEC;\nEND-ISO-10303-21;\n"
