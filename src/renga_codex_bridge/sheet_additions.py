"""Append existing native Schedule resources to existing Drawing sheets.

This adapter creates EmbeddedSchedule objects only. It does not create sheets,
Schedule definitions, rows, filters or cell values. Native fitted bounds drive
placement inside an explicit sheet-space rectangle; no scale/stretch is used.
"""
from __future__ import annotations

import copy
import math

from .audit import event, save_plan
from .catalogs import COLLECTIONS
from .model import parameters
from .presentation import KINDS, _configure_embedded, _positive_id, _set_content_center
from .presentation_edits import _bounds, _matches, _pose
from .session import Session
from .sheet_metadata import _uuid, sheet_identity_snapshot


def _finite(value):
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError('Sheet coordinates require finite millimeter numbers')
    try:
        result = float(value)
    except OverflowError as error:
        raise ValueError('Sheet coordinates must be finite') from error
    if not math.isfinite(result):
        raise ValueError('Sheet coordinates must be finite')
    return result


def validate_schedule_additions(additions):
    if not isinstance(additions, list) or not 1 <= len(additions) <= 100:
        raise ValueError('additions must contain1..100 explicit existing-sheet schedule requests')
    result = copy.deepcopy(additions)
    seen = set()
    for row in result:
        if not isinstance(row, dict) or set(row) - {'drawing_uuid', 'schedule_id', 'available_bounds_mm', 'fit_inset_mm'}:
            raise ValueError('Unsupported existing-sheet schedule fields')
        if not {'drawing_uuid', 'schedule_id', 'available_bounds_mm'} <= set(row):
            raise ValueError('drawing_uuid, inspected schedule_id and available_bounds_mm are required')
        row['drawing_uuid'] = _uuid(row['drawing_uuid'])
        _positive_id(row['schedule_id'], 'schedule_id')
        identity = row['drawing_uuid'], row['schedule_id']
        if identity in seen:
            raise ValueError('Duplicate drawing/schedule addition')
        seen.add(identity)
        rect = row['available_bounds_mm']
        if not isinstance(rect, (list, tuple)) or len(rect) != 4:
            raise ValueError('available_bounds_mm must be [left,right,bottom,top] in sheet millimeters')
        rect = [_finite(value) for value in rect]
        if rect[0] >= rect[1] or rect[2] >= rect[3]:
            raise ValueError('Available sheet rectangle must have positive width and height')
        row['available_bounds_mm'] = rect
        row['fit_inset_mm'] = _finite(row.get('fit_inset_mm', 0))
        if row['fit_inset_mm'] < 0:
            raise ValueError('fit_inset_mm must be nonnegative')
    return result


def anchored_content_origin(actual_bounds, content_origin, available):
    """Place the fitted native box at available left/top, after size checks."""
    rect = [_finite(value) for value in actual_bounds]
    space = [_finite(value) for value in available]
    origin = [_finite(value) for value in content_origin]
    if len(rect) != 4 or len(space) != 4 or len(origin) != 2:
        raise ValueError('Explicit native rectangle, content origin and available rectangle required')
    if rect[0] >= rect[1] or rect[2] >= rect[3] or space[0] >= space[1] or space[2] >= space[3]:
        raise ValueError('Degenerate native or available bounds')
    if rect[1] - rect[0] > space[1] - space[0] + 1e-6 or rect[3] - rect[2] > space[3] - space[2] + 1e-6:
        raise ValueError('Actual fitted native Schedule does not fit the requested sheet rectangle: '
                         f"native {rect[1] - rect[0]:g}×{rect[3] - rect[2]:g} mm, "
                         f"available {space[1] - space[0]:g}×{space[3] - space[2]:g} mm")
    return [origin[0] + space[0] - rect[0], origin[1] + space[3] - rect[3]]


def _assert_anchored(bounds, available):
    left, right, bottom, top = bounds
    if not _matches([left, top], [available[0], available[3]]) or right > available[1] + 1e-6 or bottom < available[2] - 1e-6:
        raise RuntimeError('Saved native Schedule bounds differ from anchored available rectangle')


def _drawings(session):
    collection = session.project.Drawings2
    return {_uuid(collection.GetByIndex(i).UniqueIdS): collection.GetByIndex(i) for i in range(collection.Count)}


def _preflight(session, additions):
    drawings = _drawings(session)
    sources = session.project.Schedules
    pending = []
    for request in additions:
        drawing = drawings.get(request['drawing_uuid'])
        if drawing is None:
            raise ValueError('Inspected drawing UUID is absent')
        if not sources.Contains(request['schedule_id']):
            raise ValueError('Inspected native Schedule ID is absent')
        source = sources.GetById(request['schedule_id'])
        if _uuid(source.TypeIdS) != _uuid(session.sdk.types['Schedule']):
            raise ValueError('Source is not a native Schedule')
        model = drawing.QueryInterface(session.r.IModel)
        objects = model.GetObjects()
        for i in range(objects.Count):
            obj = objects.GetByIndex(i)
            if _uuid(obj.ObjectTypeS) == _uuid(session.sdk.types['EmbeddedSchedule']):
                values = parameters(session, obj)
                if values.get('ScheduleId', {}).get('value') == source.Id:
                    raise ValueError('Selected native Schedule is already embedded in this drawing')
        pending.append((drawing, model, source, request))
    return pending


def assert_appended_identities(before, after, records):
    """Require exactly the requested additions and preserve every old identity."""
    if before['building'] != after['building'] or set(before['drawings']) != set(after['drawings']):
        raise RuntimeError('Building or Drawing UUID/type set changed')
    expected = copy.deepcopy(before)
    for row in records:
        content = expected['drawings'][row['drawing_uuid']]['contents']
        if row['object_uuid'] in content:
            raise RuntimeError('New EmbeddedSchedule reused an existing native identity')
        content[row['object_uuid']] = row['object_type_guid']
    if expected != after:
        raise RuntimeError('Unexpected drawing-content additions/deletions/type changes')


def resource_identity_snapshot(session):
    """Read identities in supported resource catalogs; retain unavailable status."""
    result = {}
    for name in (*COLLECTIONS, 'Tables'):
        try:
            collection = getattr(session.project, name)
        except (AttributeError, ValueError) as error:
            result[name] = {'available': False, 'reason': str(error)}
            continue
        identities = {
            _uuid(collection.GetByIndex(index).UniqueIdS): _uuid(collection.GetByIndex(index).TypeIdS)
            for index in range(collection.Count)}
        if len(identities) != collection.Count:
            raise RuntimeError('Duplicate native resource UUID in catalog: ' + name)
        result[name] = {'available': True, 'identities': identities}
    return result


def assert_resource_identity_subset(before, after):
    checked, old_count, added_count = [], 0, 0
    for name, old in before.items():
        if not old['available']:
            continue
        actual = after.get(name)
        if not actual or not actual['available'] or not old['identities'].items() <= actual['identities'].items():
            raise RuntimeError('Existing native resource UUID/type identities changed: ' + name)
        checked.append(name)
        old_count += len(old['identities'])
        added_count += len(set(actual['identities']) - set(old['identities']))
    return {'checked_available_catalogs': checked, 'preserved_resource_identities': old_count,
            'additional_resource_identities': added_count,
            'scope': 'UUID/type subset of catalogs available to both reads, not resource definitions or cell contents'}


def _read_record(session, drawing, obj, expected):
    bounded = obj.QueryInterface(session.r.IRectBoundedObject)
    if not bounded.HasContent:
        raise RuntimeError('Native EmbeddedSchedule has no content')
    values = parameters(session, obj)
    identifier = values.get('ScheduleId', {}).get('value')
    sources = session.project.Schedules
    if type(identifier) is not int or not sources.Contains(identifier):
        raise RuntimeError('Native EmbeddedSchedule references an absent Schedule')
    source = sources.GetById(identifier)
    if _uuid(source.UniqueIdS) != expected['schedule_uuid']:
        raise RuntimeError('Saved Schedule resource UUID differs from requested source')
    bounds, pose = _bounds(bounded), _pose(bounded)
    _assert_anchored(bounds, expected['available_bounds_mm'])
    return {'drawing_uuid': _uuid(drawing.UniqueIdS), 'object_uuid': _uuid(obj.UniqueIdS),
            'object_type_guid': obj.ObjectTypeS,
            'schedule_uuid': _uuid(source.UniqueIdS), 'schedule_id': identifier,
            'schedule_name': source.Name, 'bounds_mm': bounds, **pose,
            'available_bounds_mm': expected['available_bounds_mm'], 'has_content': True}


def append_sheet_schedules(project, additions):
    """Back up and append native schedules to existing sheets, then reopen."""
    additions = validate_schedule_additions(additions)
    plan = save_plan({'action': 'append_existing_sheet_native_schedules', 'project': str(project),
                      'additions': additions, 'units': 'sheet_mm'})
    records = []
    with Session(project, write=True) as session:
        before = sheet_identity_snapshot(session)
        before_resources = resource_identity_snapshot(session)
        pending = _preflight(session, additions)
        for drawing, model, source, request in pending:
            with session.operation(model):
                args = model.CreateNewEntityArgs()
                args.TypeIdS = session.sdk.types[KINDS['schedule']]
                args.Placement2D = session.r.Placement2D(session.r.Point2D(0, 0), session.r.Vector2D(1, 0))
                obj = model.CreateObject(args)
                if not obj:
                    raise RuntimeError('Native EmbeddedSchedule factory returned no object')
            _configure_embedded(session, model, obj, {'kind': 'schedule', 'schedule_id': source.Id})
            bounded = obj.QueryInterface(session.r.IRectBoundedObject)
            with session.operation(model):
                bounded.FitBoundsToContent(request['fit_inset_mm'])
            pose = _pose(bounded)
            actual_bounds = _bounds(bounded)
            event('native_schedule_fitted_before_anchor', path=str(project),
                  drawing_uuid=request['drawing_uuid'], schedule_uuid=_uuid(source.UniqueIdS),
                  bounds_mm=actual_bounds, content_origin_mm=pose['content_origin_mm'],
                  available_bounds_mm=request['available_bounds_mm'], status='provisional')
            origin = anchored_content_origin(actual_bounds, pose['content_origin_mm'], request['available_bounds_mm'])
            with session.operation(model):
                _set_content_center(session, bounded, origin)
            with session.operation(model):
                bounded.FitBoundsToContent(request['fit_inset_mm'])
            expected = {'schedule_uuid': _uuid(source.UniqueIdS), 'available_bounds_mm': request['available_bounds_mm']}
            records.append(_read_record(session, drawing, obj, expected))
        assert_appended_identities(before, sheet_identity_snapshot(session), records)
        session.save()
    with Session(project) as reopened:
        assert_appended_identities(before, sheet_identity_snapshot(reopened), records)
        resources = assert_resource_identity_subset(before_resources, resource_identity_snapshot(reopened))
        drawings = _drawings(reopened)
        saved = []
        for row in records:
            drawing = drawings[row['drawing_uuid']]
            objects = drawing.QueryInterface(reopened.r.IModel).GetObjects()
            matches = [objects.GetByIndex(i) for i in range(objects.Count)
                       if _uuid(objects.GetByIndex(i).UniqueIdS) == row['object_uuid']]
            if len(matches) != 1:
                raise RuntimeError('Saved EmbeddedSchedule identity is absent or ambiguous')
            actual = _read_record(reopened, drawing, matches[0], row)
            if not _matches(actual['bounds_mm'], row['bounds_mm']) or not _matches(actual['content_origin_mm'], row['content_origin_mm']) or not _matches(actual['content_x_axis'], row['content_x_axis']):
                raise RuntimeError('Saved native Schedule geometry changed after reopen')
            saved.append(actual)
        event('native_existing_sheet_schedules_reopened_verified', path=str(project), plan=plan,
              added_objects=saved, computer_use_calls=0)
        return {'status': 'saved_reopened_verified', 'added_objects': saved, 'plan': plan,
                'computer_use_calls': 0, 'identity_type_preservation_verified': True,
                'resource_identity_checks': resources,
                'visual_layout_verified': False,
                'scope': 'existing_native_schedule_resources_appended_to_existing_drawing_sheets',
                'limitations': ['No Schedule definition/row/filter/cell authoring',
                                'Native content and resource identity checks do not certify displayed cell text',
                                'Fitted placement is constrained by actual bounds; visual sheet QA remains required']}
