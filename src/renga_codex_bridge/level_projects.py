"""New native project with explicit levels through the official IFC importer.

This does not modify elevations in an existing project. Temporary own IFC slab
carriers are removed from the newly imported model before it is ever saved.
"""
import math
import uuid
from .session import Session
from .safety import checked_path,fingerprint
from .audit import save_plan,event
from .level_seed import validate_level_specs,build_level_seed_ifc
from .grid_spec import validate_grid_spec


def read_levels(s):
    rows=[]
    objects=s.model.GetObjects()
    for index in range(objects.Count):
        obj=objects.GetByIndex(index)
        if obj.ObjectTypeS.upper()!=s.sdk.types['Level']:continue
        native=obj.QueryInterface(s.r.ILevel)
        rows.append({'id':obj.Id,'uuid':obj.UniqueIdS.strip('{}').lower(),
                     'name':native.LevelName,'elevation_mm':native.Elevation,
                     'origin_z_mm':native.Placement.Origin.Z,'native_type':'Level'})
    return rows


def assert_requested_levels(actual,expected):
    if len(actual)!=len(expected):raise RuntimeError('Native level count differs from requested count')
    by_name={row['name']:row for row in actual}
    if len(by_name)!=len(actual):raise RuntimeError('Duplicate native level names')
    for spec in expected:
        if spec['name'] not in by_name:raise RuntimeError('Requested native level name absent after import')
        row=by_name[spec['name']]
        for key in ('elevation_mm','origin_z_mm'):
            if not math.isclose(row[key],spec['elevation_mm'],rel_tol=0,abs_tol=1e-6):
                raise RuntimeError('Native level elevation/placement differs from requested millimeters')


def read_axes(s):
    rows=[];objects=s.model.GetObjects()
    for i in range(objects.Count):
        obj=objects.GetByIndex(i)
        if obj.ObjectTypeS.upper()==s.sdk.types['Axis']:
            name=obj.GetParameters().GetS(s.sdk.parameters['GridLineName']).GetStringValue()
            rows.append({'id':obj.Id,'uuid':obj.UniqueIdS.strip('{}').lower(),'name':name,'native_type':'Axis'})
    return rows


def assert_requested_axes(actual,grid):
    expected={axis['name'] for family in ('x','y') for axis in grid[family]} if grid else set()
    if len(actual)!=len(expected) or {row['name'] for row in actual}!=expected:
        raise RuntimeError('Native axis names/count differ from requested grid')


def identity_map(rows):
    identifiers=[]
    for row in rows:
        try:identifier=uuid.UUID(row['uuid'])
        except (ValueError,TypeError,AttributeError) as error:raise RuntimeError('Invalid native persistent identity') from error
        if not identifier.int:raise RuntimeError('Empty native persistent identity')
        identifiers.append(str(identifier))
    if len(set(identifiers))!=len(rows):raise RuntimeError('Duplicate native persistent identities')
    return {row['name']:identifier for row,identifier in zip(rows,identifiers)}


def create_levels_project(project,levels,grid=None):
    specs=validate_level_specs(levels)
    grid=validate_grid_spec(grid) if grid is not None else None
    target=checked_path(project,write=True,new=True)
    if target.suffix.lower()!='.rnp':raise ValueError('New native .rnp target required')
    plan=save_plan({'action':'create_levels_project','project':str(target),'levels':specs,'grid':grid,
                    'unit':'mm','method':'ImportIfcProject','remove_own_import_carriers':True})
    source=checked_path(target.parent/(target.stem+'-seed-'+uuid.uuid4().hex+'.ifc'),write=True,new=True)
    source.parent.mkdir(parents=True,exist_ok=True)
    with source.open('x',encoding='ascii',newline='\n') as stream:stream.write(build_level_seed_ifc(specs,grid))
    source_sha=fingerprint(source)
    with Session(target,create=True) as s:
        s.check(s.app.CloseProject(True),'Close default before IFC import')
        s.check(s.app.ImportIfcProject(str(source)),'ImportIfcProject')
        if not s.app.HasProject():raise RuntimeError('IFC import returned without a project')
        s.project=s.app.Project;s.model=s.project.Model
        assert_requested_levels(read_levels(s),specs)
        assert_requested_axes(read_axes(s),grid)
        objects=s.model.GetObjects()
        carriers=[objects.GetByIndex(i).Id for i in range(objects.Count)
                  if objects.GetByIndex(i).ObjectTypeS.upper() not in {s.sdk.types['Level'],s.sdk.types['Axis']}]
        with s.operation():
            for identifier in carriers:s.model.DeleteObjectById(identifier)
        before=read_levels(s);assert_requested_levels(before,specs)
        axes_before=read_axes(s);assert_requested_axes(axes_before,grid)
        identities_before=identity_map(before);axis_identities_before=identity_map(axes_before)
        if s.model.GetObjects().Count!=len(before)+len(axes_before):raise RuntimeError('Import carrier cleanup incomplete')
        s.save()
    with Session(target) as reopened:
        actual=read_levels(reopened);assert_requested_levels(actual,specs)
        if identity_map(actual)!=identities_before:raise RuntimeError('Level identities changed after reopen')
        axes=read_axes(reopened);assert_requested_axes(axes,grid)
        if identity_map(axes)!=axis_identities_before:raise RuntimeError('Axis identities changed after reopen')
        if reopened.model.GetObjects().Count!=len(actual)+len(axes):raise RuntimeError('Saved seed contains import carriers')
        grid_verification=None
        if grid:
            from .documentation import export_ifc
            from .ifc_grid_verify import verify_exported_grid
            exported=export_ifc(reopened,target.parent/(target.stem+'-grid-check-'+uuid.uuid4().hex+'.ifc'))
            from pathlib import Path
            grid_verification=verify_exported_grid(Path(exported['output']).read_text(encoding='utf-8-sig'),grid)
            grid_verification['export_provenance_verified_by_this_reader']=True
        if fingerprint(source)!=source_sha:raise RuntimeError('IFC seed changed during import')
        event('native_levels_project_reopened_verified',path=str(target),plan=plan,
              levels=actual,removed_import_carriers=len(carriers),computer_use_calls=0)
        return {'status':'saved_reopened_verified','project':str(target),'levels':actual,
                'axes':axes,'grid_verification':grid_verification,'removed_import_carriers':len(carriers),
                'only_native_levels':not bool(axes),'only_native_levels_and_axes':True,
                'scope':'new_project_only','method':'official_ImportIfcProject',
                'plan':plan,'seed_ifc':str(source),'computer_use_calls':0}
