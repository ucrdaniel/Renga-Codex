"""Append native model/entity views to existing Drawing sheets only.

This module does not construct a Section or Elevation, alter its source plane,
open a source view, create sheets, or render. Source projection and sheet layout
remain separate native/visual checks. New source support is not established by
portable tests or by a nonempty HasContent flag.
"""
from __future__ import annotations

import copy
import json

from .audit import event, save_plan
from .model import object_by_id, parameters
from .operations import matches
from .presentation import (INT_VIEW_PARAMETERS, KINDS, VIEW_PARAMETERS, VIEW_RESOURCE_REFERENCES,
                           _configure_embedded, _native_rect, _number, _positive_id,
                           _preflight_view_references, _rect, _set_content_center, _string)
from .presentation_edits import _bounds, _matches, _pose
from .session import Session
from .sheet_additions import (_drawings, assert_appended_identities, assert_resource_identity_subset,
                             resource_identity_snapshot)
from .sheet_metadata import _uuid, sheet_identity_snapshot


def validate_view_additions(additions):
    if not isinstance(additions, list) or not 1 <= len(additions) <= 100:
        raise ValueError('additions must contain1..100 explicit existing-sheet view requests')
    result = copy.deepcopy(additions)
    seen = set()
    for row in result:
        allowed = {'drawing_uuid', 'kind', 'source_entity_id', 'object_mark', 'scale_id',
                   'origin_mm', 'bounds_mm', 'fit_inset_mm', 'view_parameters'}
        required = {'drawing_uuid', 'kind', 'source_entity_id', 'scale_id', 'origin_mm'}
        if not isinstance(row, dict) or set(row) - allowed or not required <= set(row):
            raise ValueError('Existing drawing UUID, native source/scale IDs and explicit origin_mm required')
        row['drawing_uuid'] = _uuid(row['drawing_uuid'])
        if not isinstance(row['kind'], str) or row['kind'] not in {'model', 'entity'}:
            raise ValueError('Existing-sheet view kind must be model or entity')
        _positive_id(row['source_entity_id'], 'source_entity_id')
        _positive_id(row['scale_id'], 'scale_id')
        if row['kind'] == 'entity':
            _string(row.get('object_mark'), 'object_mark')
        elif 'object_mark' in row:
            raise ValueError('object_mark applies only to entity views')
        origin = row['origin_mm']
        if not isinstance(origin, (list, tuple)) or len(origin) != 2:
            raise ValueError('origin_mm requires two explicit sheet millimeter coordinates')
        row['origin_mm'] = [_number(value, 'origin_mm') for value in origin]
        if 'bounds_mm' in row:
            row['bounds_mm'] = _rect(row['bounds_mm'])
        row['fit_inset_mm'] = _number(row.get('fit_inset_mm', 1), 'fit_inset_mm', minimum=0)
        values = row.get('view_parameters', {})
        if not isinstance(values, dict) or set(values) - VIEW_PARAMETERS[row['kind']]:
            raise ValueError('Unsupported embedded-view parameter')
        for key, value in values.items():
            if key in INT_VIEW_PARAMETERS and (type(value) is not int or not -(2**31) <= value < 2**31):
                raise ValueError(key + ' requires a strict native int32')
            if key in {*VIEW_RESOURCE_REFERENCES, 'ViewDepthLevelId'}:
                _positive_id(value, key)
            if key == 'ObjectPartBeyondViewDepthPlane' and type(value) is not bool:
                raise ValueError(key + ' requires a strict boolean')
            if type(value) not in (bool, int, float, str):
                raise ValueError('View parameters require primitive finite values')
            if isinstance(value, (int, float)) and not isinstance(value, bool):
                _number(value, key)
        identity = (row['drawing_uuid'], row['kind'], row['source_entity_id'], row['scale_id'],
                    row.get('object_mark'), json.dumps(values, sort_keys=True))
        if identity in seen:
            raise ValueError('Duplicate source/scale/view-parameter request in one drawing')
        seen.add(identity)
    return result


def _preflight(session, additions):
    drawings = _drawings(session)
    pending = []
    for request in additions:
        drawing = drawings.get(request['drawing_uuid'])
        if drawing is None:
            raise ValueError('Inspected existing Drawing UUID is absent')
        source = object_by_id(session, request['source_entity_id'])
        if not session.project.Scales.Contains(request['scale_id']):
            raise ValueError('Inspected native scale ID is absent')
        if request['kind'] == 'model':
            if _uuid(source.ObjectTypeS) not in {_uuid(session.sdk.types[kind]) for kind in ('Level', 'Section', 'Elevation')}:
                raise ValueError('Model view source must be an existing native Level, Section or Elevation')
            binding_name, binding = 'RepresentedEntityId', source.Id
        else:
            if source.QueryInterface(session.r.IObjectWithMark).Mark != request['object_mark']:
                raise ValueError('Explicit object_mark differs from inspected source Mark')
            binding_name, binding = 'ObjectMark', request['object_mark']
        _preflight_view_references(session, request.get('view_parameters', {}))
        model = drawing.QueryInterface(session.r.IModel)
        objects = model.GetObjects()
        for index in range(objects.Count):
            obj = objects.GetByIndex(index)
            if _uuid(obj.ObjectTypeS) != _uuid(session.sdk.types[KINDS[request['kind']]]):
                continue
            values = parameters(session, obj)
            if (values.get(binding_name, {}).get('value') == binding
                    and values.get('ScaleId', {}).get('value') == request['scale_id']
                    and all(matches(values.get(key, {}).get('value'), value)
                            for key, value in request.get('view_parameters', {}).items())):
                raise ValueError('Matching native source/scale/view-parameters already embedded in this sheet')
        resource_uuids = {'ScaleId': _uuid(session.project.Scales.GetById(request['scale_id']).UniqueIdS)}
        for key, collection in VIEW_RESOURCE_REFERENCES.items():
            if key in request.get('view_parameters', {}):
                resource_uuids[key] = _uuid(getattr(session.project, collection).GetById(request['view_parameters'][key]).UniqueIdS)
        if 'ViewDepthLevelId' in request.get('view_parameters', {}):
            resource_uuids['ViewDepthLevelId'] = _uuid(object_by_id(session, request['view_parameters']['ViewDepthLevelId']).UniqueIdS)
        pending.append((drawing, model, source, request, resource_uuids))
    return pending


def _read_record(session, drawing, obj, expected):
    values = parameters(session, obj)
    observed = {}
    for key, value in expected['parameters'].items():
        actual = values.get(key, {}).get('value')
        if key == 'RepresentedEntityId':
            if _uuid(object_by_id(session, actual).UniqueIdS) != expected['inspected_source_uuid']:
                raise RuntimeError('Saved model-view source persistent UUID changed')
        elif key in expected['resource_uuids']:
            if key == 'ViewDepthLevelId':
                entity = object_by_id(session, actual)
            else:
                collection = 'Scales' if key == 'ScaleId' else VIEW_RESOURCE_REFERENCES[key]
                entity = getattr(session.project, collection).GetById(actual)
            if not entity or _uuid(entity.UniqueIdS) != expected['resource_uuids'][key]:
                raise RuntimeError('Saved native embedded-view resource UUID mismatch: ' + key)
        elif not matches(actual, value):
            raise RuntimeError('Saved embedded-view parameter mismatch: ' + key)
        observed[key] = actual
    bounded = obj.QueryInterface(session.r.IRectBoundedObject)
    if not bounded.HasContent:
        raise RuntimeError('Native embedded view has no content; projection is not certified')
    pose = _pose(bounded)
    if not _matches(pose['content_origin_mm'], expected['origin_mm']):
        raise RuntimeError('Saved embedded-view content center differs from explicit origin_mm')
    return {'drawing_uuid': _uuid(drawing.UniqueIdS), 'object_uuid': _uuid(obj.UniqueIdS),
            'object_type_guid': obj.ObjectTypeS, 'kind': expected['kind'],
            'inspected_source_uuid': expected['inspected_source_uuid'], 'parameters': observed,
            'resource_uuids': expected['resource_uuids'], 'origin_mm': expected['origin_mm'],
            'bounds_mm': _bounds(bounded), **pose, 'has_content': True,
            'source_binding_scope': 'persistent_model_source_uuid' if expected['kind'] == 'model' else 'mark_not_unique_instance_uuid'}


def append_sheet_views(project, additions):
    """Append model/entity views only; back up, save, reopen and read back."""
    additions = validate_view_additions(additions)
    plan = save_plan({'action': 'append_existing_sheet_native_views', 'project': str(project),
                      'additions': additions, 'units': 'sheet_mm'})
    records = []
    with Session(project, write=True) as session:
        before = sheet_identity_snapshot(session)
        resources_before = resource_identity_snapshot(session)
        pending = _preflight(session, additions)
        for drawing, model, source, request, resource_uuids in pending:
            with session.operation(model):
                args = model.CreateNewEntityArgs()
                args.TypeIdS = session.sdk.types[KINDS[request['kind']]]
                args.Placement2D = session.r.Placement2D(session.r.Point2D(*request['origin_mm']), session.r.Vector2D(1, 0))
                obj = model.CreateObject(args)
                if not obj:
                    raise RuntimeError('Native embedded-view factory returned no object')
            native_request = {key: value for key, value in request.items() if key != 'drawing_uuid'}
            wanted = _configure_embedded(session, model, obj, native_request)
            bounded = obj.QueryInterface(session.r.IRectBoundedObject)
            with session.operation(model):
                _set_content_center(session, bounded, request['origin_mm'])
            with session.operation(model):
                bounded.FitBoundsToContent(request['fit_inset_mm'])
            if 'bounds_mm' in request:
                with session.operation(model):
                    bounded.BoundRect = _native_rect(session, request['bounds_mm'])
            expected = {'kind': request['kind'], 'parameters': wanted,
                        'resource_uuids': resource_uuids, 'inspected_source_uuid': _uuid(source.UniqueIdS),
                        'origin_mm': request['origin_mm']}
            row = _read_record(session, drawing, obj, expected)
            if 'bounds_mm' in request and not _matches(row['bounds_mm'], request['bounds_mm']):
                raise RuntimeError('Committed view crop differs from requested bounds_mm')
            records.append(row)
        assert_appended_identities(before, sheet_identity_snapshot(session), records)
        session.save()
    with Session(project) as reopened:
        assert_appended_identities(before, sheet_identity_snapshot(reopened), records)
        resources = assert_resource_identity_subset(resources_before, resource_identity_snapshot(reopened))
        drawings = _drawings(reopened)
        saved = []
        for row in records:
            drawing = drawings[row['drawing_uuid']]
            objects = drawing.QueryInterface(reopened.r.IModel).GetObjects()
            found = [objects.GetByIndex(i) for i in range(objects.Count)
                     if _uuid(objects.GetByIndex(i).UniqueIdS) == row['object_uuid']]
            if len(found) != 1:
                raise RuntimeError('Saved embedded-view persistent identity is absent or ambiguous')
            actual = _read_record(reopened, drawing, found[0], row)
            if not _matches(actual['bounds_mm'], row['bounds_mm']) or not _matches(actual['content_x_axis'], row['content_x_axis']):
                raise RuntimeError('Saved embedded-view bounds/orientation changed after reopening')
            saved.append(actual)
        event('native_existing_sheet_views_reopened_verified', path=str(project), plan=plan,
              added_objects=saved, computer_use_calls=0)
        return {'status': 'saved_reopened_verified', 'added_objects': saved, 'plan': plan,
                'resource_identity_checks': resources, 'computer_use_calls': 0,
                'identity_type_preservation_verified': True, 'visual_layout_verified': False,
                'source_projection_verified': False,
                'scope': 'existing_native_model_entity_sources_appended_to_existing_drawing_sheets',
                'limitations': ['Does not create sheets, sections, elevations, source planes or associative annotations',
                                'Section/Elevation native embedding requires its own saved/visual evidence',
                                'HasContent does not prove the correct projected geometry or complete source visibility',
                                'Entity views bind by Mark rather than a unique source-instance UUID']}
