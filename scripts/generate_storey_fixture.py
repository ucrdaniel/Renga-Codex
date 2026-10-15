"""Own synthetic IFC4 fixture for testing the official ImportIfcProject route.

This is a deliberately small test generator, not a general IFC exporter. It has
no Renga, SDK, UI or third-party dependency. The importer still needs native
save/reopen checks before nonzero Renga levels can be claimed as supported.
"""
from __future__ import annotations

import argparse
from pathlib import Path
import uuid


def fixture_ifc() -> str:
    """Return three storeys at 0/3000/6000 mm, each containing a 6 m wall."""
    alphabet = "0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz_$"

    def gid(seed: str) -> str:
        number = uuid.uuid5(uuid.NAMESPACE_URL, "renga-bridge-storey-fixture/" + seed).int
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
    organization = entity("IFCORGANIZATION($,'Bridge Test',$,$,$)")
    actor = entity(f"IFCPERSONANDORGANIZATION({person},{organization},$)")
    application = entity(f"IFCAPPLICATION({organization},'0.1.0','Synthetic IFC fixture','BRIDGE')")
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
    project = entity(f"IFCPROJECT('{gid('project')}',{owner},'Synthetic storeys',$,$,$,$,({context}),{units})")
    site = entity(f"IFCSITE('{gid('site')}',{owner},'Test site',$,$,{world},$,$,.ELEMENT.,$,$,$,$,$)")
    building_placement = entity(f"IFCLOCALPLACEMENT({world},{coordinate_system})")
    building = entity(f"IFCBUILDING('{gid('building')}',{owner},'Test building',$,$,{building_placement},$,$,.ELEMENT.,$,$,$)")
    entity(f"IFCRELAGGREGATES('{gid('project-sites')}',{owner},$,$,{project},({site}))")
    entity(f"IFCRELAGGREGATES('{gid('site-buildings')}',{owner},$,$,{site},({building}))")
    storeys = []
    for index, elevation in enumerate((0, 3000, 6000)):
        origin = entity(f"IFCCARTESIANPOINT((0.,0.,{elevation}.))")
        axis = entity(f"IFCAXIS2PLACEMENT3D({origin},{vertical},{horizontal})")
        placement = entity(f"IFCLOCALPLACEMENT({building_placement},{axis})")
        storey = entity(f"IFCBUILDINGSTOREY('{gid('storey-' + str(index))}',{owner},'Bridge Level {index}',$,$,{placement},$,$,.ELEMENT.,{elevation}.)")
        storeys.append(storey)
        wall_placement = entity(f"IFCLOCALPLACEMENT({placement},{coordinate_system})")
        profile_origin = entity("IFCCARTESIANPOINT((3000.,0.))")
        profile_axis = entity(f"IFCAXIS2PLACEMENT2D({profile_origin},$)")
        profile = entity(f"IFCRECTANGLEPROFILEDEF(.AREA.,'6000x200 mm',{profile_axis},6000.,200.)")
        solid = entity(f"IFCEXTRUDEDAREASOLID({profile},{coordinate_system},{vertical},2800.)")
        representation = entity(f"IFCSHAPEREPRESENTATION({context},'Body','SweptSolid',({solid}))")
        shape = entity(f"IFCPRODUCTDEFINITIONSHAPE($,$,({representation}))")
        wall = entity(f"IFCWALL('{gid('wall-' + str(index))}',{owner},'Fixture wall {index}',$,$,{wall_placement},{shape},'W{index}',.STANDARD.)")
        entity(f"IFCRELCONTAINEDINSPATIALSTRUCTURE('{gid('contained-' + str(index))}',{owner},$,$,({wall}),{storey})")
    entity(f"IFCRELAGGREGATES('{gid('building-storeys')}',{owner},$,$,{building},({','.join(storeys)}))")
    header = (
        "ISO-10303-21;\nHEADER;\n"
        "FILE_DESCRIPTION(('ViewDefinition [DesignTransferView]'),'2;1');\n"
        "FILE_NAME('synthetic-storeys.ifc','2026-10-15T00:00:00',('Bridge'),('Bridge'),"
        "'Renga Codex Bridge','Renga Codex Bridge','');\n"
        "FILE_SCHEMA(('IFC4'));\nENDSEC;\nDATA;\n"
    )
    return header + "\n".join(lines) + "\nENDSEC;\nEND-ISO-10303-21;\n"


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", required=True, type=Path)
    from renga_codex_bridge.safety import checked_path
    output = checked_path(parser.parse_args().output, write=True, new=True)
    if output.suffix.lower() != ".ifc":
        parser.error("Output must have .ifc extension")
    # Refuse every existing file, including links; this test generator never edits.
    with output.open("x", encoding="ascii", newline="\n") as stream:
        stream.write(fixture_ifc())
    print(output)
