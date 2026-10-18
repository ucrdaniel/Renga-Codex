"""Native drawing authoring helpers; no UI, images-as-views or annotation fakes.

Caller must inspect IDs in the saved project. Feature-specific native evidence
and remaining visual checks are recorded in the development documentation.
Tables can be embedded from existing resources, not populated through invented
cell setters. Section/Elevation creation is deliberately unavailable here.
"""
from __future__ import annotations

import copy
import math

from .audit import event, save_plan
from .model import object_by_id, parameters, set_parameter
from .operations import matches
from .session import Session


VIEW_PARAMETERS = {
    'model': {'SectionPlaneOffset', 'ViewDepthLevelId', 'LevelViewDepthPlaneOffset',
              'SectionViewDepthPlaneOffset', 'ModelViewDirection', 'ProjectionType',
              'AxonometricAxesOrientation', 'VisualStyle', 'DisplayStyleId', 'FilterId',
              'ObjectPartBeyondViewDepthPlane', 'ViewName'},
    'entity': {'ObjectViewDirection', 'SectionPlaneOffset', 'ViewDepthPlaneOffset',
               'VisualStyle', 'DisplayStyleId', 'FilterId',
               'ObjectPartBeyondViewDepthPlane', 'ViewName'},
    'schedule': set(), 'table': set(),
}
KINDS = {'model': 'EmbeddedModelView', 'entity': 'EmbeddedEntityView',
         'schedule': 'EmbeddedSchedule', 'table': 'EmbeddedTable'}
INT_VIEW_PARAMETERS = {'ViewDepthLevelId','DisplayStyleId','FilterId','ModelViewDirection',
                       'ProjectionType','AxonometricAxesOrientation','VisualStyle','ObjectViewDirection'}
VIEW_RESOURCE_REFERENCES = {'FilterId':'Filters','DisplayStyleId':'DisplayStyles'}


def _positive_id(value, label):
    if type(value) is not int or not 0 < value <= 2**31 - 1:
        raise ValueError(label + ' requires an inspected positive native ID')
    return value


def _number(value, label, *, minimum=None, maximum=None):
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError(label + ' must be a finite number')
    try:
        result = float(value)
    except OverflowError as error:
        raise ValueError(label + ' must be finite') from error
    if not math.isfinite(result) or minimum is not None and result < minimum or maximum is not None and result > maximum:
        raise ValueError(label + ' lies outside its finite supported range')
    return result


def _string(value, label):
    if not isinstance(value, str) or not value.strip() or '\0' in value:
        raise ValueError(label + ' requires nonempty text without NUL')
    return value


def _rect(value):
    if not isinstance(value, (list, tuple)) or len(value) != 4:
        raise ValueError('bounds_mm must be [left,right,bottom,top] in sheet mm')
    result = [_number(v, 'bounds_mm') for v in value]
    if result[0] >= result[1] or result[2] >= result[3]:
        raise ValueError('bounds_mm must have positive width and height')
    return result


def validate_drawings(drawings):
    """Validate the complete request before opening a native write session."""
    if not isinstance(drawings, list) or not 1 <= len(drawings) <= 100:
        raise ValueError('drawings must contain 1..100 explicit specifications')
    result = copy.deepcopy(drawings)
    names = set()
    for spec in result:
        if not isinstance(spec, dict) or set(spec) - {'name', 'page_format_id', 'orientation',
                'layout_style_id', 'topic', 'texts', 'views'}:
            raise ValueError('Unknown drawing specification fields')
        name = _string(spec.get('name'), 'drawing name')
        if name in names:
            raise ValueError('Drawing request names must be unique')
        names.add(name)
        _positive_id(spec.get('page_format_id'), 'page_format_id')
        if type(spec.get('orientation', 2)) is not int or spec.get('orientation', 2) not in (1, 2):
            raise ValueError('orientation must be 1 portrait or 2 landscape')
        if spec.get('layout_style_id') is not None:
            _positive_id(spec['layout_style_id'], 'layout_style_id')
        if spec.get('topic') is not None:
            _string(spec['topic'], 'topic')
        for field in ('texts', 'views'):
            if not isinstance(spec.get(field, []), list) or len(spec.get(field, [])) > 200:
                raise ValueError(field + ' must be a list of at most 200 objects')
        for text in spec.get('texts', []):
            if not isinstance(text, dict) or set(text) - {'text', 'bounds_mm', 'font_family', 'cap_size_mm'}:
                raise ValueError('Unknown text fields')
            _string(text.get('text'), 'drawing text')
            _rect(text.get('bounds_mm'))
            _string(text.get('font_family', 'Arial'), 'font family')
            _number(text.get('cap_size_mm', 5), 'cap_size_mm', minimum=.1, maximum=100)
        for view in spec.get('views', []):
            if not isinstance(view, dict) or set(view) - {'kind', 'source_entity_id', 'object_mark',
                    'scale_id', 'schedule_id', 'table_id', 'origin_mm', 'bounds_mm',
                    'fit_inset_mm', 'view_parameters'}:
                raise ValueError('Unknown embedded-object fields')
            kind = view.get('kind')
            if not isinstance(kind, str) or kind not in KINDS:
                raise ValueError('Embedded kind must be model, entity, schedule or table')
            if kind in {'model', 'entity'}:
                _positive_id(view.get('source_entity_id'), 'source_entity_id')
                _positive_id(view.get('scale_id'), 'scale_id')
            if kind == 'entity':
                _string(view.get('object_mark'), 'object_mark')
            if kind in {'schedule', 'table'}:
                _positive_id(view.get(kind + '_id'), kind + '_id')
            allowed = {'model': {'source_entity_id', 'scale_id'},
                       'entity': {'source_entity_id', 'scale_id', 'object_mark'},
                       'schedule': {'schedule_id'}, 'table': {'table_id'}}[kind]
            if set(view) & ({'source_entity_id', 'object_mark', 'scale_id', 'schedule_id', 'table_id'} - allowed):
                raise ValueError('Source fields do not apply to this embedded kind')
            origin = view.get('origin_mm', [45, 180])
            if not isinstance(origin, (list, tuple)) or len(origin) != 2:
                raise ValueError('origin_mm must have two sheet coordinates')
            for value in origin:
                _number(value, 'origin_mm')
            if 'bounds_mm' in view:
                _rect(view['bounds_mm'])
            _number(view.get('fit_inset_mm', 1), 'fit_inset_mm', minimum=0)
            values = view.get('view_parameters', {})
            if not isinstance(values, dict) or set(values) - VIEW_PARAMETERS[kind]:
                raise ValueError('Unsupported parameter for this embedded kind')
            for key,value in values.items():
                if key in INT_VIEW_PARAMETERS and (type(value) is not int or not -(2**31)<=value<2**31):
                    raise ValueError(key+' requires a strict native int32 value')
                if key in {*VIEW_RESOURCE_REFERENCES,'ViewDepthLevelId'}:_positive_id(value,key)
                if key=='ObjectPartBeyondViewDepthPlane' and type(value) is not bool:
                    raise ValueError(key+' requires a strict boolean')
                if type(value) not in (bool, int, float, str):
                    raise ValueError('View parameter requires a finite primitive value')
                if isinstance(value, (int, float)) and not isinstance(value, bool):
                    _number(value, 'View parameter')
    return result


def _uid(entity):
    return entity.UniqueIdS.strip('{}').lower()


def _require_entity(collection, identifier, label):
    if not collection.Contains(identifier):
        raise ValueError('Inspected ' + label + ' is absent from this project')
    return collection.GetById(identifier)


def _native_rect(s, values):
    rect = s.r.Rect()
    rect.Left, rect.Right, rect.Bottom, rect.Top = values
    return rect


def _preflight_view_references(s,values):
    for key,collection in VIEW_RESOURCE_REFERENCES.items():
        if key in values:_require_entity(getattr(s.project,collection),values[key],key)
    if 'ViewDepthLevelId' in values:
        level=object_by_id(s,values['ViewDepthLevelId'])
        if level.ObjectTypeS.upper()!=s.sdk.types['Level']:
            raise ValueError('ViewDepthLevelId must identify an existing native Level')


def _text_value(s, entity):
    document = entity.QueryInterface(s.r.ITextObject).GetRichTextDocument()
    return '\n'.join(''.join(document.GetParagraph(i).GetToken(j).Text
                            for j in range(document.GetParagraph(i).TokenCount))
                     for i in range(document.ParagraphCount)).strip('\n')


def _assert_text_format(s, entity, font_family, cap_size_mm):
    """Verify each saved nonempty rich-text token, including later paragraphs."""
    document = entity.QueryInterface(s.r.ITextObject).GetRichTextDocument()
    count = 0
    for paragraph_index in range(document.ParagraphCount):
        paragraph = document.GetParagraph(paragraph_index)
        for token_index in range(paragraph.TokenCount):
            token = paragraph.GetToken(token_index)
            if not token.Text:
                continue
            if token.FontFamily != font_family:
                raise RuntimeError('Saved native text FontFamily mismatch')
            actual = token.FontCapSize
            if (isinstance(actual, bool) or not isinstance(actual, (int, float))
                    or not math.isclose(actual, cap_size_mm, rel_tol=0, abs_tol=1e-6)):
                raise RuntimeError('Saved native text FontCapSize mismatch')
            count += 1
    if not count:
        raise RuntimeError('Saved native text has no nonempty formatted tokens')
    return {'font_family': font_family, 'cap_size_mm': cap_size_mm,
            'checked_tokens': count, 'scope': 'nonempty_saved_rich_text_tokens'}


def _set_content_center(s, bounded, origin):
    # IMath.CreatePlacement2D takes Point2D and Vector2D, not a Placement2D record.
    placement = s.app.Math.CreatePlacement2D(s.r.Point2D(*origin), s.r.Vector2D(1, 0))
    bounded.SetContentPlacement(placement)


def _configure_embedded(s, drawing_model, entity, request):
    """Materialize the source binding before dependent view setters.

    Source changes can regenerate which view parameters are writable. Keep
    native IsReadOnly checks and use a second operation after binding Apply.
    """
    kind = request['kind']
    binding = {}
    if kind == 'model':
        binding['RepresentedEntityId'] = request['source_entity_id']
    elif kind == 'entity':
        binding['ObjectMark'] = request['object_mark']
    else:
        binding['ScheduleId' if kind == 'schedule' else 'TableId'] = request[kind + '_id']
    if kind in {'model', 'entity'}:
        binding['ScaleId'] = request['scale_id']
    with s.operation(drawing_model):
        for key, value in binding.items():
            set_parameter(s, entity, key, value)
    view_parameters = request.get('view_parameters', {})
    if view_parameters:
        with s.operation(drawing_model):
            for key, value in view_parameters.items():
                set_parameter(s, entity, key, value)
    return {**binding, **view_parameters}


def ensure_topic(s, name):
    """Reuse one exact-name Topic or create it; never clear project resources."""
    _string(name, 'topic')
    collection = s.project.Topics
    existing = [collection.GetByIndex(i) for i in range(collection.Count)
                if collection.GetByIndex(i).Name == name]
    if len(existing) > 1:
        raise ValueError('Ambiguous existing Topic name')
    if existing:
        return existing[0]
    with s.operation():
        args = collection.CreateNewEntityArgs()
        args.TypeIdS = s.sdk.types['Topic']
        entity = collection.Create(args)
        if not entity:
            raise RuntimeError('Native Topic factory returned no entity')
    with s.operation():
        set_parameter(s, entity, 'EntityName', name)
    return entity


def create_presentations(project, drawings):
    """Add native sheets, text and embedded views; back up/save/reopen/verify.

    Omitting layout_style_id leaves the native blank-sheet default. No title
    block, schedule cells, dimensions, markers, sections or elevations are
    invented. The result still requires visual layout QA before delivery.
    Embedded origin_mm is its content center in global sheet millimeters,
    assigned through IRectBoundedObject.SetContentPlacement after regeneration.
    """
    drawings = validate_drawings(drawings)
    plan = save_plan({'action': 'create_native_presentations', 'project': str(project),
                      'drawings': drawings, 'units': 'sheet_mm'})
    records = []
    with Session(project, write=True) as s:
        before_building = {_uid(s.model.GetObjects().GetByIndex(i))
                           for i in range(s.model.GetObjects().Count)}
        before_drawings = {_uid(s.project.Drawings2.GetByIndex(i)) for i in range(s.project.Drawings2.Count)}
        # Validate all referenced resources before creating any native content.
        for spec in drawings:
            _require_entity(s.project.PageFormatStyles, spec['page_format_id'], 'page format')
            if spec.get('layout_style_id') is not None:
                _require_entity(s.project.LayoutStyles, spec['layout_style_id'], 'layout style')
            for view in spec.get('views', []):
                kind = view['kind']
                if kind in {'model', 'entity'}:
                    source = object_by_id(s, view['source_entity_id'])
                    _require_entity(s.project.Scales, view['scale_id'], 'scale')
                    if kind == 'model' and source.ObjectTypeS.upper() not in {
                            s.sdk.types[k] for k in ('Level', 'Section', 'Elevation')}:
                        raise ValueError('EmbeddedModelView requires an existing Level, Section or Elevation')
                    if kind == 'entity' and source.QueryInterface(s.r.IObjectWithMark).Mark != view['object_mark']:
                        raise ValueError('Explicit object_mark does not match the inspected source entity')
                elif kind in {'schedule', 'table'}:
                    _require_entity(getattr(s.project, 'Schedules' if kind == 'schedule' else 'Tables'),
                                    view[kind + '_id'], kind)
                _preflight_view_references(s,view.get('view_parameters',{}))
        topics = {name: ensure_topic(s, name) for name in dict.fromkeys(
            spec['topic'] for spec in drawings if spec.get('topic') is not None)}
        for spec in drawings:
            wanted = {'EntityName': spec['name'], 'PageFormatId': spec['page_format_id'],
                      'PageOrientation': spec.get('orientation', 2)}
            if spec.get('layout_style_id') is not None:
                wanted['LayoutStyleId'] = spec['layout_style_id']
            if spec.get('topic') is not None:
                wanted['TopicId'] = topics[spec['topic']].Id
            with s.operation():
                args = s.project.Drawings2.CreateNewEntityArgs()
                args.TypeIdS = s.sdk.types['Drawing']
                drawing = s.project.Drawings2.Create(args)
                if not drawing:
                    raise RuntimeError('Native Drawing factory returned no entity')
            with s.operation():
                for key, value in wanted.items():
                    set_parameter(s, drawing, key, value)
            dm = drawing.QueryInterface(s.r.IModel)
            record = {'uuid': _uid(drawing), 'parameters': wanted, 'objects': []}
            for request in spec.get('texts', []):
                with s.operation(dm):
                    args = dm.CreateNewEntityArgs()
                    args.TypeIdS = s.sdk.types['DrawingText']
                    entity = dm.CreateObject(args)
                    if not entity:
                        raise RuntimeError('Native DrawingText factory returned no object')
                    text = entity.QueryInterface(s.r.ITextObject)
                    text.BoundRect = _native_rect(s, request['bounds_mm'])
                    for paragraph in request['text'].split('\n'):
                        token = s.r.RichTextToken()
                        token.Text = paragraph
                        token.FontFamily = request.get('font_family', 'Arial')
                        token.FontCapSize = request.get('cap_size_mm', 5)
                        token.FontColor = s.r.Color(0, 0, 0, 255)
                        text.GetRichTextDocument().AppendParagraph([token])
                record['objects'].append({'uuid': _uid(entity), 'kind': 'text',
                                          'text': request['text'].strip('\n'), 'bounds_mm': request['bounds_mm'],
                                          'font_family': request.get('font_family', 'Arial'),
                                          'cap_size_mm': request.get('cap_size_mm', 5)})
            for request in spec.get('views', []):
                kind = request['kind']
                with s.operation(dm):
                    args = dm.CreateNewEntityArgs()
                    args.TypeIdS = s.sdk.types[KINDS[kind]]
                    args.Placement2D = s.r.Placement2D(s.r.Point2D(*request.get('origin_mm', [45, 180])),
                                                      s.r.Vector2D(1, 0))
                    entity = dm.CreateObject(args)
                    if not entity:
                        raise RuntimeError('Native embedded factory returned no object: ' + kind)
                wanted_view = _configure_embedded(s, dm, entity, request)
                bounded = entity.QueryInterface(s.r.IRectBoundedObject)
                origin = request.get('origin_mm', [45, 180])
                with s.operation(dm):
                    _set_content_center(s, bounded, origin)
                with s.operation(dm):
                    bounded.FitBoundsToContent(request.get('fit_inset_mm', 1))
                if 'bounds_mm' in request:
                    with s.operation(dm):
                        bounded.BoundRect = _native_rect(s, request['bounds_mm'])
                if not bounded.HasContent:
                    raise RuntimeError('Native embedded object has no content: ' + kind)
                record['objects'].append({'uuid': _uid(entity), 'kind': kind,
                    'content_origin_mm': list(origin),
                    'parameters': wanted_view, 'bounds_mm': [bounded.BoundRect.Left, bounded.BoundRect.Right,
                                                            bounded.BoundRect.Bottom, bounded.BoundRect.Top]})
            records.append(record)
        topic_records = {name: _uid(entity) for name, entity in topics.items()}
        s.save()
    with Session(project) as reopened:
        if {_uid(reopened.model.GetObjects().GetByIndex(i)) for i in range(reopened.model.GetObjects().Count)} != before_building:
            raise RuntimeError('Building model identities changed during presentation authoring')
        actual_drawings = {_uid(reopened.project.Drawings2.GetByIndex(i)): reopened.project.Drawings2.GetByIndex(i)
                           for i in range(reopened.project.Drawings2.Count)}
        if set(actual_drawings) != before_drawings | {row['uuid'] for row in records}:
            raise RuntimeError('Saved drawing identities differ from requested additions')
        for name, identifier in topic_records.items():
            entity = reopened.project.Topics.GetByUniqueIdS(identifier)
            if not entity or entity.Name != name:
                raise RuntimeError('Saved Topic identity/name mismatch')
        for record in records:
            drawing = actual_drawings[record['uuid']]
            saved = parameters(reopened, drawing)
            for key, value in record['parameters'].items():
                if key not in saved or not matches(saved[key]['value'], value):
                    raise RuntimeError('Saved drawing parameter mismatch: ' + key)
            objects = drawing.QueryInterface(reopened.r.IModel).GetObjects()
            actual = {_uid(objects.GetByIndex(i)): objects.GetByIndex(i) for i in range(objects.Count)}
            if set(actual) != {row['uuid'] for row in record['objects']}:
                raise RuntimeError('Saved drawing content identities differ')
            for row in record['objects']:
                entity = actual[row['uuid']]
                if row['kind'] == 'text':
                    if _text_value(reopened, entity) != row['text']:
                        raise RuntimeError('Saved native text mismatch')
                    row['saved_font_check'] = _assert_text_format(reopened, entity, row['font_family'], row['cap_size_mm'])
                    bounded = entity.QueryInterface(reopened.r.ITextObject)
                else:
                    values = parameters(reopened, entity)
                    for key, value in row['parameters'].items():
                        if key not in values or not matches(values[key]['value'], value):
                            raise RuntimeError('Saved embedded parameter mismatch: ' + key)
                    bounded = entity.QueryInterface(reopened.r.IRectBoundedObject)
                    if not bounded.HasContent:
                        raise RuntimeError('Saved embedded object lost content')
                    content = bounded.GetContentPlacement()
                    if not content or not all(math.isclose(a, b, rel_tol=0, abs_tol=1e-6)
                            for a, b in zip([content.Origin.X, content.Origin.Y], row['content_origin_mm'])):
                        raise RuntimeError('Saved embedded content center differs from requested origin_mm')
                rect = bounded.BoundRect
                if not all(math.isclose(a, b, rel_tol=0, abs_tol=1e-6) for a, b in
                           zip([rect.Left, rect.Right, rect.Bottom, rect.Top], row['bounds_mm'])):
                    raise RuntimeError('Saved presentation bounds differ')
        event('native_presentations_reopened_verified', path=str(project), plan=plan,
              drawing_uuids=[row['uuid'] for row in records], computer_use_calls=0)
        return {'status': 'saved_reopened_verified', 'created_uuids': [row['uuid'] for row in records],
                'drawings': records, 'topics': topic_records, 'plan': plan, 'computer_use_calls': 0,
                'visual_layout_verified': False, 'scope': 'native_sheets_texts_existing_source_views',
                'limitations': ['No associative dimension/Tag creation',
                    'No new Section/Elevation constructor', 'No editable table/schedule cell authoring',
                    'Object views bind by mark, not by a unique source-object ID',
                    'Omitted layout style does not create a title block or sheet frame']}
