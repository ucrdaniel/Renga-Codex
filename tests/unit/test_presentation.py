"""Pure request/resource-safety checks, never native presentation proof."""
from contextlib import contextmanager
from types import SimpleNamespace
import copy
import math

import pytest

from renga_codex_bridge import presentation as p


def drawing():
    return {'name': 'План этажа', 'page_format_id': 3, 'orientation': 2, 'topic': 'АР',
            'texts': [{'text': 'Офисный комплекс\nПлан', 'bounds_mm': [20, 240, 260, 280]}],
            'views': [{'kind': 'model', 'source_entity_id': 7, 'scale_id': 4,
                       'origin_mm': [80, 150], 'view_parameters': {'SectionPlaneOffset': 2200}}]}


def test_blank_sheets_and_missing_layout_are_explicitly_allowed_without_inventing_resources():
    request = [{'name': 'Title', 'page_format_id': 3, 'topic': None, 'texts': [], 'views': []}]
    assert p.validate_drawings(request) == request
    assert 'layout_style_id' not in p.validate_drawings(request)[0]


def test_request_validation_copies_caller_nested_values_without_changes():
    original = [drawing()]
    before = copy.deepcopy(original)
    validated = p.validate_drawings(original)
    validated[0]['views'][0]['origin_mm'][0] = 999
    assert original == before


@pytest.mark.parametrize('key,value', [
    ('page_format_id', True), ('page_format_id', 0), ('page_format_id', '3'), ('page_format_id', 2**32 + 3),
    ('layout_style_id', 0), ('layout_style_id', False), ('orientation', True),
    ('orientation', 3), ('name', ''), ('name', 'x\0y'), ('topic', ''),
    ('views', {}), ('texts', [None]), ('fake_dimensions', []),
])
def test_invalid_drawing_is_rejected_before_session_or_native_mutation(monkeypatch, key, value):
    def forbidden(*args, **kwargs):
        raise AssertionError('Session must not be created for an invalid request')

    monkeypatch.setattr(p, 'Session', forbidden)
    request = drawing()
    request[key] = value
    with pytest.raises(ValueError):
        p.create_presentations('never-opened.rnp', [request])


@pytest.mark.parametrize('kind', ['dimension', 'tag', 'section', 'elevation', 'DrawingImage', {}, []])
def test_no_annotation_or_screenshot_substitute_kinds(kind):
    request = drawing()
    request['views'][0]['kind'] = kind
    with pytest.raises(ValueError, match='kind'):
        p.validate_drawings([request])


@pytest.mark.parametrize('origin', [[1], [1, 2, 3], [math.nan, 0], [math.inf, 0], [False, 0]])
def test_origin_requires_two_finite_explicit_mm_coordinates(origin):
    request = drawing()
    request['views'][0]['origin_mm'] = origin
    with pytest.raises(ValueError):
        p.validate_drawings([request])


@pytest.mark.parametrize('bounds', [[20, 20, 1, 2], [20, 19, 1, 2], [1, 2, 3, 3],
                                  [1, 2, 4], [0, math.inf, 0, 1], [0, True, 0, 1]])
def test_text_and_view_bounds_must_have_finite_positive_extent(bounds):
    request = drawing()
    request['texts'][0]['bounds_mm'] = bounds
    with pytest.raises(ValueError):
        p.validate_drawings([request])
    request = drawing()
    request['views'][0]['bounds_mm'] = bounds
    with pytest.raises(ValueError):
        p.validate_drawings([request])


@pytest.mark.parametrize('value', [math.nan, math.inf, -math.inf, 10**1000, {}, [], None])
def test_view_parameters_cannot_hide_nonfinite_or_structured_values(value):
    request = drawing()
    request['views'][0]['view_parameters']['SectionPlaneOffset'] = value
    with pytest.raises(ValueError):
        p.validate_drawings([request])


def test_protected_reference_parameters_cannot_be_overridden_in_view_parameters():
    request = drawing()
    request['views'][0]['view_parameters']['RepresentedEntityId'] = 99
    with pytest.raises(ValueError, match='Unsupported parameter'):
        p.validate_drawings([request])


def test_entity_view_requires_explicit_mark_and_inspected_source_id():
    request = drawing()
    view = request['views'][0]
    view['kind'] = 'entity'
    with pytest.raises(ValueError, match='object_mark'):
        p.validate_drawings([request])
    view['object_mark'] = 'ОК-1'
    assert p.validate_drawings([request])[0]['views'][0]['object_mark'] == 'ОК-1'
    view['source_entity_id'] = 0
    with pytest.raises(ValueError, match='source_entity_id'):
        p.validate_drawings([request])


@pytest.mark.parametrize('kind', ['table', 'schedule'])
def test_existing_table_and_schedule_embedding_has_no_cell_authoring_contract(kind):
    request = drawing()
    request['views'] = [{'kind': kind, kind + '_id': 12}]
    assert p.validate_drawings([request])[0]['views'][0][kind + '_id'] == 12
    request['views'][0]['cells'] = [['not a supported setter']]
    with pytest.raises(ValueError, match='Unknown embedded'):
        p.validate_drawings([request])


def test_wrong_binding_for_embedded_kind_is_not_silently_ignored():
    request = drawing()
    request['views'][0]['table_id'] = 999
    with pytest.raises(ValueError, match='Source fields'):
        p.validate_drawings([request])


def test_sheet_count_object_count_and_duplicate_names_are_bounded():
    with pytest.raises(ValueError):
        p.validate_drawings([])
    with pytest.raises(ValueError):
        p.validate_drawings([drawing()] * 101)
    with pytest.raises(ValueError, match='unique'):
        p.validate_drawings([drawing(), drawing()])
    request = drawing()
    request['texts'] *= 201
    with pytest.raises(ValueError, match='200'):
        p.validate_drawings([request])


def test_topic_reuse_has_no_resource_writes_and_ambiguous_names_are_rejected():
    entity = SimpleNamespace(Name='АР', Id=5)
    collection = SimpleNamespace(Count=1, GetByIndex=lambda i: entity)
    session = SimpleNamespace(project=SimpleNamespace(Topics=collection))
    assert p.ensure_topic(session, 'АР') is entity
    collection.Count = 2
    with pytest.raises(ValueError, match='Ambiguous'):
        p.ensure_topic(session, 'АР')


def test_topic_name_assignment_is_deferred_until_creation_apply(monkeypatch):
    state = {'applied': 0, 'active': False}
    entity = SimpleNamespace(Id=5)
    collection = SimpleNamespace(Count=0, CreateNewEntityArgs=lambda: SimpleNamespace(),
                                 Create=lambda args: entity)

    @contextmanager
    def operation():
        assert not state['active']
        state['active'] = True
        yield
        state['active'] = False
        state['applied'] += 1

    session = SimpleNamespace(project=SimpleNamespace(Topics=collection), operation=operation,
                              sdk=SimpleNamespace(types={'Topic': 'local-sdk-topic-type'}))

    def setter(s, target, name, value):
        assert state['applied'] == 1 and state['active']
        assert s is session and target is entity and name == 'EntityName' and value == 'АР'
        entity.Name = value

    monkeypatch.setattr(p, 'set_parameter', setter)
    assert p.ensure_topic(session, 'АР').Name == 'АР'
    assert state['applied'] == 2


def test_missing_inspected_resource_is_rejected_without_fallback_defaults():
    collection = SimpleNamespace(Contains=lambda identifier: False)
    with pytest.raises(ValueError, match='absent'):
        p._require_entity(collection, 9, 'scale')


def test_content_center_uses_documented_two_argument_math_factory_and_applies_the_result():
    calls = []
    placement = object()

    def create_placement(origin, axis_x):
        assert origin == ('point', 100, 150) and axis_x == ('vector', 1, 0)
        return placement

    session = SimpleNamespace(app=SimpleNamespace(Math=SimpleNamespace(CreatePlacement2D=create_placement)),
        r=SimpleNamespace(Point2D=lambda x, y: ('point', x, y), Vector2D=lambda x, y: ('vector', x, y)))
    bounded = SimpleNamespace(SetContentPlacement=lambda value: calls.append(value))
    p._set_content_center(session, bounded, [100, 150])
    assert calls == [placement]


@pytest.mark.parametrize('specification,binding', [
    ({'kind': 'model', 'source_entity_id': 7, 'scale_id': 4,
      'view_parameters': {'SectionPlaneOffset': 2200, 'ViewName': 'Plan'}},
     {'RepresentedEntityId': 7, 'ScaleId': 4}),
    ({'kind': 'entity', 'object_mark': 'ОК-1', 'source_entity_id': 9, 'scale_id': 6,
      'view_parameters': {'ObjectViewDirection': 2}}, {'ObjectMark': 'ОК-1', 'ScaleId': 6}),
    ({'kind': 'schedule', 'schedule_id': 12}, {'ScheduleId': 12}),
    ({'kind': 'table', 'table_id': 13}, {'TableId': 13}),
])
def test_source_and_scale_binding_apply_before_dependent_view_parameters(monkeypatch, specification, binding):
    # Model the native state that made SectionPlaneOffset read-only: a setter
    # becomes available only after a committed source binding, not merely after
    # that binding's setter returns inside the same transaction.
    state = {'pending': {}, 'committed': {}, 'applies': [], 'active': False}
    model = object()
    entity = object()

    @contextmanager
    def operation(selected_model):
        assert selected_model is model and not state['active']
        state['active'] = True
        state['pending'] = {}
        yield
        state['applies'].append(dict(state['pending']))
        state['committed'].update(state['pending'])
        state['active'] = False

    session = SimpleNamespace(operation=operation)

    def setter(s, target, key, value):
        assert s is session and target is entity and state['active']
        if key not in binding:
            assert state['committed'] == binding, 'View setter remains read-only until binding Apply'
            assert state['pending'].keys().isdisjoint(binding), 'Binding and view settings must be separate operations'
        state['pending'][key] = value

    monkeypatch.setattr(p, 'set_parameter', setter)
    returned = p._configure_embedded(session, model, entity, specification)
    view_parameters = specification.get('view_parameters', {})
    assert returned == {**binding, **view_parameters}
    assert state['applies'] == [binding] + ([view_parameters] if view_parameters else [])


def test_readonly_view_error_is_not_ignored_or_retried_as_a_binding(monkeypatch):
    state = {'applied': 0}

    @contextmanager
    def operation(model):
        yield
        state['applied'] += 1

    def setter(session, entity, key, value):
        if key == 'SectionPlaneOffset':
            raise ValueError('Read-only native parameter: SectionPlaneOffset')

    monkeypatch.setattr(p, 'set_parameter', setter)
    with pytest.raises(ValueError, match='Read-only'):
        p._configure_embedded(SimpleNamespace(operation=operation), object(), object(),
            {'kind': 'model', 'source_entity_id': 7, 'scale_id': 4,
             'view_parameters': {'SectionPlaneOffset': 2200}})
    assert state['applied'] == 1
