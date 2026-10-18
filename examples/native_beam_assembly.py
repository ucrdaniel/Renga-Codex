"""Independent native Assembly/Beam factory example; NEW test projects only.

No vendor model, copied graph, private UUID, proprietary SDK content, GUI,
clipboard or mesh substitution is embedded. This example is derived from a
genuine saved/reopened one-Beam prototype, not a claim of a universal clone API.
Source-specific native evidence and remaining limits are linked in the docs.
"""
from __future__ import annotations

import argparse
import json
import math
import uuid

from renga_codex_bridge.audit import event, save_plan
from renga_codex_bridge.geometry import extract
from renga_codex_bridge.model import parameters, set_parameter
from renga_codex_bridge.resources import _resource_operation, parse_profile_namespace
from renga_codex_bridge.safety import checked_path, fingerprint
from renga_codex_bridge.session import Session


def validate_dimensions(length_mm, width_mm, depth_mm):
    values = []
    for name, value in zip(('length_mm', 'width_mm', 'depth_mm'), (length_mm, width_mm, depth_mm)):
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            raise ValueError(name + ' must be an explicit finite positive number in millimeters')
        try:
            value = float(value)
        except OverflowError as error:
            raise ValueError(name + ' must be finite') from error
        if not math.isfinite(value) or value <= 0:
            raise ValueError(name + ' must be finite and positive')
        values.append(value)
    return dict(zip(('length_mm', 'width_mm', 'depth_mm'), values))


def _uuid(value):
    return str(uuid.UUID(value.strip('{}')))


def _find(collection, identifier):
    # IModelObjectCollection has GetByUniqueId(GUID), no GetByUniqueIdS(BSTR).
    matches = [collection.GetByIndex(i) for i in range(collection.Count)
               if _uuid(collection.GetByIndex(i).UniqueIdS) == identifier]
    if len(matches) != 1:
        raise RuntimeError('Expected one saved native persistent identity')
    return matches[0]


def _profile_double(s, style, guid):
    container = style.QueryInterface(s.r.IParameterContainer)
    if not container.ContainsS(guid):
        raise RuntimeError('Requested native profile dimension is absent')
    value = container.GetS(guid)
    if not value.HasValue or value.ValueType != 3:
        raise RuntimeError('Requested native profile dimension is unset or not Double')
    return value.GetDoubleValue()


def _mesh_bounds(exported, expected_size):
    """Require finite native geometry and an actual nondegenerate triangle."""
    vertices = [v for g in exported['grids'] for v in g['vertices']] if exported else []
    if not vertices:
        raise RuntimeError('Native AssemblyInstance has no exported mesh')
    for point in vertices:
        if (len(point) != 3 or any(isinstance(v, bool) or not isinstance(v, (int, float)) for v in point)
                or any(not math.isfinite(v) for v in point)):
            raise RuntimeError('Nonfinite or invalid native AssemblyInstance mesh vertex')
    triangle_count = 0
    nondegenerate = 0
    for grid in exported['grids']:
        for triangle in grid['triangles']:
            if len(triangle) != 3 or any(type(i) is not int or not 0 <= i < len(grid['vertices']) for i in triangle):
                raise RuntimeError('Invalid native AssemblyInstance triangle')
            a, b, c = [grid['vertices'][i] for i in triangle]
            ab = [b[i]-a[i] for i in range(3)]
            ac = [c[i]-a[i] for i in range(3)]
            cross = [ab[1]*ac[2]-ab[2]*ac[1], ab[2]*ac[0]-ab[0]*ac[2], ab[0]*ac[1]-ab[1]*ac[0]]
            area = math.hypot(*cross)/2
            if not math.isfinite(area):
                raise RuntimeError('Nonfinite native triangle area')
            triangle_count += 1
            nondegenerate += area > 0
    if not nondegenerate:
        raise RuntimeError('No nondegenerate native AssemblyInstance mesh triangles')
    low, high = list(map(min, zip(*vertices))), list(map(max, zip(*vertices)))
    size = [b-a for a, b in zip(low, high)]
    if any(not math.isfinite(v) for v in size) or any(abs(a-b) > .1 for a, b in zip(size, expected_size)):
        raise RuntimeError('Native instance mesh extents differ from requested lengths')
    return {'min': low, 'max': high, 'size': size, 'triangle_count': triangle_count,
            'nondegenerate_triangle_count': nondegenerate,
            'scope': 'finite_mesh_presence_and_extents_not_closed_solid_or_full_shape_equivalence'}


def _instance_placement(s, instance, expected_level_uuid):
    """Read native pose and persistent host level; constructor return is not proof."""
    native = instance.QueryInterface(s.r.ILevelObject)
    pose = native.GetPlacement()
    xyz = lambda point: [point.X, point.Y, point.Z]
    actual = {'origin_mm': xyz(pose.Origin), 'x_axis': xyz(pose.AxisX), 'z_axis': xyz(pose.AxisZ)}
    wanted = {'origin_mm': [0, 0, 0], 'x_axis': [1, 0, 0], 'z_axis': [0, 0, 1]}
    if any(not math.isfinite(value) for values in actual.values() for value in values):
        raise RuntimeError('Nonfinite native AssemblyInstance placement')
    if any(not math.isclose(value, expected, rel_tol=0, abs_tol=1e-6)
           for key in wanted for value, expected in zip(actual[key], wanted[key])):
        raise RuntimeError('Native AssemblyInstance origin/axes differ from the explicit default placement')
    level = s.model.GetObjects().GetById(native.LevelId)
    if (not level or _uuid(level.ObjectTypeS) != _uuid(s.sdk.types['Level'])
            or _uuid(level.UniqueIdS) != expected_level_uuid):
        raise RuntimeError('Native AssemblyInstance host Level UUID/type changed')
    elevation = parameters(s, level).get('LevelElevation', {})
    if not elevation.get('has_value') or elevation.get('value') != 0:
        raise RuntimeError('Saved native AssemblyInstance host Level is not at zero elevation')
    return {'placement': actual, 'level': {'uuid': _uuid(level.UniqueIdS), 'id': level.Id,
                                          'elevation_mm': elevation['value']}}


def _inspect(s, ids, requested, profile_guid, dimensions):
    assembly = s.project.Assemblies.GetByUniqueIdS(ids['assembly_uuid'])
    if not assembly or _uuid(assembly.TypeIdS) != _uuid(s.sdk.types['Assembly']):
        raise RuntimeError('Native Assembly UUID/type missing')
    children = assembly.QueryInterface(s.r.IModel).GetObjects()
    beam = _find(children, ids['beam_uuid'])
    if _uuid(beam.ObjectTypeS) != _uuid(s.sdk.types['Beam']):
        raise RuntimeError('Saved child is not a native Beam')
    child_values = parameters(s, beam)
    style = s.project.BeamStyles.GetById(child_values['BeamStyleId']['value'])
    if not style or _uuid(style.UniqueIdS) != ids['style_uuid']:
        raise RuntimeError('Saved BeamStyle reference UUID changed')
    style_values = parameters(s, style)
    profile = s.project.Profiles.GetById(style_values['ProfileId']['value'])
    if not profile or _uuid(profile.UniqueIdS) != _uuid(profile_guid):
        raise RuntimeError('Saved built-in profile UUID changed')
    actual_width = _profile_double(s, style, dimensions['Width'])
    actual_depth = _profile_double(s, style, dimensions['Depth'])
    for actual, wanted in ((actual_width, requested['width_mm']), (actual_depth, requested['depth_mm'])):
        if not math.isclose(actual, wanted, abs_tol=1e-6, rel_tol=0):
            raise RuntimeError('Saved profile dimension differs from requested millimeters')
    baseline = beam.QueryInterface(s.r.IBaseline3DObject).GetBaseline()
    xyz = lambda p: [p.X, p.Y, p.Z]
    actual_baseline = [xyz(baseline.GetBeginPoint()), xyz(baseline.GetEndPoint())]
    wanted_baseline = [[0, 0, 0], [requested['length_mm'], 0, 0]]
    if (baseline.Curve3DType != s.r.Curve3DType_LineSegment
            or any(not math.isfinite(v) for point in actual_baseline for v in point)
            or any(abs(a-b) > 1e-6 for p, q in zip(actual_baseline, wanted_baseline) for a, b in zip(p, q))
            or not math.isclose(baseline.GetLength(), requested['length_mm'], abs_tol=1e-6, rel_tol=0)):
        raise RuntimeError('Saved native Beam baseline differs from explicit line')
    instance = _find(s.model.GetObjects(), ids['instance_uuid'])
    if _uuid(instance.ObjectTypeS) != _uuid(s.sdk.types['AssemblyInstance']):
        raise RuntimeError('Saved instance is not a native AssemblyInstance')
    actual_instance = _instance_placement(s, instance, ids['level_uuid'])
    instance_values = parameters(s, instance)
    referenced = s.project.Assemblies.GetById(instance_values['AssemblyId']['value'])
    if not referenced or _uuid(referenced.UniqueIdS) != ids['assembly_uuid']:
        raise RuntimeError('Saved AssemblyInstance reference UUID changed')
    exported = next((obj for obj in extract(s)['objects'] if obj['uuid'] == ids['instance_uuid']), None)
    expected_size = [requested['length_mm'], requested['width_mm'], requested['depth_mm']]
    mesh_bounds = _mesh_bounds(exported, expected_size)
    return {'identities': ids, 'native_baseline_mm': actual_baseline, 'profile_uuid': _uuid(profile_guid),
            'instance_placement': actual_instance['placement'], 'instance_level': actual_instance['level'],
            'profile_dimensions_mm': {'width': actual_width, 'depth': actual_depth},
            'current_numeric_ids': {'assembly': assembly.Id, 'beam': beam.Id, 'style': style.Id,
                                    'instance': instance.Id, 'profile': profile.Id, 'level': actual_instance['level']['id']},
            'mesh_bounds_mm': mesh_bounds,
            'assembly_child_uuid_types': {_uuid(children.GetByIndex(i).UniqueIdS): children.GetByIndex(i).ObjectTypeS
                                          for i in range(children.Count)},
            'building_uuid_types': {_uuid(s.model.GetObjects().GetByIndex(i).UniqueIdS): s.model.GetObjects().GetByIndex(i).ObjectTypeS
                                   for i in range(s.model.GetObjects().Count)}}


def create_native_beam_assembly(project, *, length_mm, width_mm, depth_mm):
    """Create one new editable native elliptical Beam assembly and instance.

    Supported example scope is a straight beam, stock Ellipse profile, default
    base level and constructor orientation. No existing file/resource is edited;
    no automatic general assembly clone, custom profile or arc authoring is claimed.
    """
    requested = validate_dimensions(length_mm, width_mm, depth_mm)
    target = checked_path(project, write=True, new=True)
    if target.suffix.lower() != '.rnp':
        raise ValueError('NEW native .rnp target required')
    plan = save_plan({'action': 'new_native_single_beam_assembly_example', 'project': str(target),
                      'units': 'mm', **requested,
                      'profile': 'existing_builtin_EllipseProfileId', 'instance_origin_mm': [0, 0, 0],
                      'instance_x_axis': [1, 0, 0], 'instance_z_axis': [0, 0, 1],
                      'baseline_own_mm': [[0, 0, 0], [requested['length_mm'], 0, 0]],
                      'full_graph_clone': False})
    with Session(target, create=True, write=True) as s:
        profile_guid = s.sdk.read_guids('ProfileIds')['EllipseProfileId']
        profile = s.project.Profiles.GetByUniqueIdS(profile_guid)
        if not profile:
            raise RuntimeError('New project lacks the exact installed SDK stock Ellipse profile')
        header = (s.sdk.root/'C++/Include/Renga/ProfileParameters.h').read_text(encoding='utf-8-sig')
        dimensions = parse_profile_namespace(header, 'EllipseParameters')
        if not {'Width', 'Depth'} <= set(dimensions):
            raise RuntimeError('Local SDK Ellipse dimension GUIDs absent')
        with _resource_operation(s):
            args = s.project.BeamStyles.CreateNewEntityArgs()
            args.TypeIdS = s.sdk.types['BeamStyle']
            style = s.project.BeamStyles.Create(args)
        with _resource_operation(s):
            set_parameter(s, style, 'ProfileId', profile.Id)
        with _resource_operation(s):
            set_parameter(s, style, 'EntityName', 'Native assembly example beam style')
            set_parameter(s, style, dimensions['Width'], requested['width_mm'])
            set_parameter(s, style, dimensions['Depth'], requested['depth_mm'])
        with _resource_operation(s):
            args = s.project.Assemblies.CreateNewEntityArgs()
            args.TypeIdS = s.sdk.types['Assembly']
            assembly = s.project.Assemblies.Create(args)
            set_parameter(s, assembly, 'EntityName', 'Native assembly example')
        am = assembly.QueryInterface(s.r.IModel)
        with s.operation(am):
            args = am.CreateNewEntityArgs()
            args.TypeIdS = s.sdk.types['Beam']
            args.Placement3D = s.r.Placement3D(s.r.Point3D(0,0,0), s.r.Vector3D(1,0,0), s.r.Vector3D(0,0,1))
            beam = am.CreateObject(args)
            if not beam:
                raise RuntimeError('Native child Beam factory returned no object')
        with s.operation(am):
            set_parameter(s, beam, 'BeamStyleId', style.Id)
        with s.operation(am):
            beam.QueryInterface(s.r.IBaseline3DObject).SetBaseline(s.app.Math.CreateLineSegment3D(
                s.r.Point3D(0,0,0), s.r.Point3D(requested['length_mm'],0,0)))
        objects = s.model.GetObjects()
        levels = [objects.GetByIndex(i) for i in range(objects.Count)
                  if _uuid(objects.GetByIndex(i).ObjectTypeS) == _uuid(s.sdk.types['Level'])]
        if len(levels) != 1:
            raise RuntimeError('Expected exactly one native base level in NEW project')
        level = parameters(s, levels[0]).get('LevelElevation', {})
        if not level.get('has_value') or level.get('value') != 0:
            raise RuntimeError('NEW project base level is not at zero elevation')
        with s.operation():
            args = s.model.CreateNewEntityArgs()
            args.TypeIdS = s.sdk.types['AssemblyInstance']
            args.HostObjectId = levels[0].Id
            args.Placement3D = s.r.Placement3D(s.r.Point3D(0,0,0), s.r.Vector3D(1,0,0), s.r.Vector3D(0,0,1))
            instance = s.model.CreateObject(args)
            if not instance:
                raise RuntimeError('Native AssemblyInstance factory returned no object')
        with s.operation():
            set_parameter(s, instance, 'AssemblyId', assembly.Id)
        ids = {'assembly_uuid': _uuid(assembly.UniqueIdS), 'style_uuid': _uuid(style.UniqueIdS),
               'beam_uuid': _uuid(beam.UniqueIdS), 'instance_uuid': _uuid(instance.UniqueIdS),
               'level_uuid': _uuid(levels[0].UniqueIdS)}
        committed = _inspect(s, ids, requested, profile_guid, dimensions)
        s.save()
        # Reopen uses only plain UUIDs/expectations, never live COM pointers
        # from the process that just saved the project.
        profile = style = assembly = am = beam = instance = levels = objects = args = None
    with Session(target) as reopened:
        actual = _inspect(reopened, ids, requested, profile_guid, dimensions)
        for key in ('building_uuid_types', 'assembly_child_uuid_types'):
            if actual[key] != committed[key]:
                raise RuntimeError('Native persistent identities/types changed on reopen')
        event('native_single_beam_assembly_example_reopened_verified', path=str(target), plan=plan,
              identities=ids, actual_parameters=actual, computer_use_calls=0)
    return {'status': 'saved_reopened_verified', 'project': str(target), 'sha256': fingerprint(target),
            'requested_mm': requested, 'observed': actual, 'plan': plan,
            'computer_use_calls': 0, 'pdf_exports': 0, 'full_graph_transfer_verified': False,
            'scope': 'new_native_one_straight_elliptical_Beam_Assembly_definition_and_instance_only'}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--project', required=True)
    parser.add_argument('--length-mm', required=True, type=float)
    parser.add_argument('--width-mm', required=True, type=float)
    parser.add_argument('--depth-mm', required=True, type=float)
    args = parser.parse_args()
    print(json.dumps(create_native_beam_assembly(args.project, length_mm=args.length_mm,
              width_mm=args.width_mm, depth_mm=args.depth_mm), ensure_ascii=False, indent=2, allow_nan=False))


if __name__ == '__main__':
    main()
