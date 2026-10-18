"""Append plain native DrawingText objects to existing Drawing sheets.

These are editable sheet texts, not title-block cells, associative markers,
dimensions, schedules or form bindings. No UI or export is used.
"""
from __future__ import annotations

import copy

from .audit import event, save_plan
from .presentation import _assert_text_format, _native_rect, _number, _rect
from .presentation_edits import _bounds, _contents, _matches, _replace_text, _text_state
from .session import Session
from .sheet_additions import assert_appended_identities
from .sheet_metadata import _uuid, sheet_identity_snapshot


FIELDS = {'drawing_uuid', 'text', 'bounds_mm', 'font_family', 'cap_size_mm'}


def validate_text_additions(additions):
    """Require complete explicit requests before opening a native session."""
    if not isinstance(additions, list) or not 1 <= len(additions) <= 1000:
        raise ValueError('additions must contain 1..1000 explicit existing-sheet text requests')
    result = copy.deepcopy(additions)
    seen = set()
    for row in result:
        if not isinstance(row, dict) or set(row) != FIELDS:
            raise ValueError('Each text requires only drawing_uuid, text, bounds_mm, font_family and cap_size_mm')
        row['drawing_uuid'] = _uuid(row['drawing_uuid'])
        text = row['text']
        if (not isinstance(text, str) or not text.strip()
                or any(ord(char) < 32 and char != '\n' for char in text)):
            raise ValueError('text requires nonempty Unicode text without controls; use LF between paragraphs')
        row['bounds_mm'] = _rect(row['bounds_mm'])
        family = row['font_family']
        if not isinstance(family, str) or not family.strip() or any(ord(char) < 32 for char in family):
            raise ValueError('font_family requires explicit nonempty text without controls')
        row['cap_size_mm'] = _number(row['cap_size_mm'], 'cap_size_mm', minimum=.1, maximum=100)
        identity = row['drawing_uuid'], text, tuple(row['bounds_mm'])
        if identity in seen:
            raise ValueError('Duplicate text and bounds requested on the same drawing')
        seen.add(identity)
    return result


def reject_existing_text_duplicates(additions, existing):
    """Reject the same text at the same saved native bounds, regardless of font.

    Native bounds use the existing sheet adapter's 1e-6 mm readback tolerance.
    The caller supplies actual text/bounds read from the selected saved sheets.
    """
    for request in additions:
        if any(row['drawing_uuid'] == request['drawing_uuid']
               and row['text'] == request['text']
               and _matches(row['bounds_mm'], request['bounds_mm'])
               for row in existing):
            raise ValueError('The same native DrawingText and bounds already exist on this drawing')


def _preflight(session, additions):
    collection = session.project.Drawings2
    drawings = {_uuid(collection.GetByIndex(i).UniqueIdS): collection.GetByIndex(i)
                for i in range(collection.Count)}
    selected = {}
    existing = []
    for request in additions:
        uid = request['drawing_uuid']
        if uid not in drawings:
            raise ValueError('Inspected drawing UUID is absent from this project')
        if uid in selected:
            continue
        model, contents = _contents(session, drawings[uid])
        selected[uid] = model
        for obj in contents.values():
            if _uuid(obj.ObjectTypeS) == _uuid(session.sdk.types['DrawingText']):
                bounded = obj.QueryInterface(session.r.ITextObject)
                existing.append({'drawing_uuid': uid, 'text': _text_state(session, obj)['text'],
                                 'bounds_mm': _bounds(bounded)})
    reject_existing_text_duplicates(additions, existing)
    return [(selected[request['drawing_uuid']], request) for request in additions]


def _read_record(session, obj, request):
    if _uuid(obj.ObjectTypeS) != _uuid(session.sdk.types['DrawingText']):
        raise RuntimeError('Saved appended content is not native DrawingText')
    bounded = obj.QueryInterface(session.r.ITextObject)
    bounds, state = _bounds(bounded), _text_state(session, obj)
    if state['text'] != request['text']:
        raise RuntimeError('Saved appended DrawingText differs from requested text')
    if not _matches(bounds, request['bounds_mm']):
        raise RuntimeError('Saved appended DrawingText bounds differ from requested sheet millimeters')
    font = _assert_text_format(session, obj, request['font_family'], request['cap_size_mm'])
    for paragraph in state['rich_text']:
        for token in paragraph:
            if token['text'] and (token['font_color_rgba'] != [0, 0, 0, 255]
                                  or any(token['font_style'].values())):
                raise RuntimeError('Saved appended DrawingText is not plain black regular text')
    return {'drawing_uuid': request['drawing_uuid'], 'object_uuid': _uuid(obj.UniqueIdS),
            'object_type_guid': obj.ObjectTypeS.upper(), 'kind': 'DrawingText',
            'text': state['text'], 'bounds_mm': bounds, 'font_family': request['font_family'],
            'cap_size_mm': request['cap_size_mm'], 'saved_font_check': font}


def append_sheet_texts(project, additions):
    """Append explicit native text, back up/save/close/reopen and verify.

    Every request requires drawing_uuid, text, bounds_mm in sheet millimeters,
    font_family and cap_size_mm. Existing sheet identities remain unchanged.
    This function creates neither title-block cell values nor their bindings.
    """
    additions = validate_text_additions(additions)
    plan = save_plan({'action': 'append_existing_sheet_native_texts', 'project': str(project),
                      'additions': additions, 'units': 'sheet_mm'})
    records = []
    with Session(project, write=True) as session:
        before = sheet_identity_snapshot(session)
        pending = _preflight(session, additions)
        for model, request in pending:
            with session.operation(model):
                args = model.CreateNewEntityArgs()
                args.TypeIdS = session.sdk.types['DrawingText']
                obj = model.CreateObject(args)
                if not obj:
                    raise RuntimeError('Native DrawingText factory returned no object')
                text = obj.QueryInterface(session.r.ITextObject)
                text.BoundRect = _native_rect(session, request['bounds_mm'])
                _replace_text(session, obj, request)
            records.append(_read_record(session, obj, request))
        assert_appended_identities(before, sheet_identity_snapshot(session), records)
        session.save()
    with Session(project) as reopened:
        assert_appended_identities(before, sheet_identity_snapshot(reopened), records)
        collection = reopened.project.Drawings2
        drawings = {_uuid(collection.GetByIndex(i).UniqueIdS): collection.GetByIndex(i)
                    for i in range(collection.Count)}
        contents = {}
        saved = []
        for record, request in zip(records, additions):
            uid = request['drawing_uuid']
            if uid not in contents:
                _, contents[uid] = _contents(reopened, drawings[uid])
            obj = contents[uid].get(record['object_uuid'])
            if obj is None:
                raise RuntimeError('Saved appended DrawingText UUID is absent from the requested drawing')
            saved.append(_read_record(reopened, obj, request))
        event('native_existing_sheet_texts_reopened_verified', path=str(project), plan=plan,
              added_objects=saved, computer_use_calls=0)
        return {'status': 'saved_reopened_verified', 'added_objects': saved, 'plan': plan,
                'computer_use_calls': 0, 'identity_type_preservation_verified': True,
                'visual_layout_verified': False, 'scope': 'native_plain_text_appended_to_existing_sheets',
                'limitations': ['DrawingText is not a title-block cell or form binding',
                                'No associative dimension, Tag or Schedule authoring',
                                'Explicit sheet text requires visual layout and font QA']}
