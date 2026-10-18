import copy
from types import SimpleNamespace as NS
from uuid import UUID

import pytest

from renga_codex_bridge.sheet_views import validate_view_additions
from renga_codex_bridge import sheet_views


def request():
    return [{'drawing_uuid': str(UUID(int=1)), 'kind': 'model', 'source_entity_id': 100,
             'scale_id': 200, 'origin_mm': [140, 150], 'fit_inset_mm': 1,
             'view_parameters': {'SectionPlaneOffset': 1500}}]


def test_existing_sheet_request_preserves_callers_and_contains_no_sheet_creation_metadata():
    value = request()
    before = copy.deepcopy(value)
    result = validate_view_additions(value)
    assert value == before
    assert result[0]['origin_mm'] == [140.0, 150.0]
    assert 'name' not in result[0] and 'page_format_id' not in result[0]


@pytest.mark.parametrize('fault', ['new_sheet', 'bad_source', 'bad_scale', 'missing_origin', 'nan', 'source_mark', 'schedule',
                                  'unknown_view_parameter', 'resource_zero', 'bool_enum', 'bad_bool', 'bad_rect', 'nested_parameter', 'duplicate'])
def test_unsafe_or_ambiguous_view_requests_fail_before_any_session(fault):
    value = request()
    if fault == 'new_sheet':
        value[0]['name'] = 'Create a new sheet'
    elif fault == 'bad_source':
        value[0]['source_entity_id'] = True
    elif fault == 'bad_scale':
        value[0]['scale_id'] = 0
    elif fault == 'missing_origin':
        del value[0]['origin_mm']
    elif fault == 'nan':
        value[0]['origin_mm'][1] = float('nan')
    elif fault == 'source_mark':
        value[0]['object_mark'] = 'Wrong model binding field'
    elif fault == 'schedule':
        value[0]['kind'] = 'schedule'
    elif fault == 'unknown_view_parameter':
        value[0]['view_parameters']['InventedPlaneDirection'] = 90
    elif fault == 'resource_zero':
        value[0]['view_parameters']['ViewDepthLevelId'] = 0
    elif fault == 'bool_enum':
        value[0]['view_parameters']['VisualStyle'] = True
    elif fault == 'bad_bool':
        value[0]['view_parameters']['ObjectPartBeyondViewDepthPlane'] = 1
    elif fault == 'bad_rect':
        value[0]['bounds_mm'] = [10, 5, 0, 10]
    elif fault == 'nested_parameter':
        value[0]['view_parameters']['ViewName'] = {'text': 'Nested'}
    else:
        value.append(copy.deepcopy(value[0]))
    with pytest.raises(ValueError):
        validate_view_additions(value)


def test_entity_views_require_an_explicit_inspected_mark_and_allow_original_crop():
    value = request()
    value[0].update(kind='entity', object_mark='D1', view_parameters={'ObjectViewDirection': 1}, bounds_mm=[100, 120, 80, 130])
    result = validate_view_additions(value)
    assert result[0]['object_mark'] == 'D1'
    del value[0]['object_mark']
    with pytest.raises(ValueError):
        validate_view_additions(value)


def test_same_source_on_different_existing_drawings_is_allowed():
    value = request()
    other = copy.deepcopy(value[0])
    other['drawing_uuid'] = str(UUID(int=2))
    assert len(validate_view_additions([value[0], other])) == 2


def native_preflight_fixture(monkeypatch, *, duplicate=False, source_kind='Section'):
    types = {name: str(UUID(int=index)) for index, name in enumerate(
        ('Level', 'Section', 'Elevation', 'EmbeddedModelView', 'EmbeddedEntityView', 'Wall'), 10)}
    contents = [NS(ObjectTypeS=types['EmbeddedModelView'])] if duplicate else []
    objects = NS(Count=len(contents), GetByIndex=lambda index: contents[index])
    # No app, baseline or level-placement interfaces are supplied. A preflight
    # regression that opens a source view or queries a source plane must fail.
    source = NS(ObjectTypeS=types[source_kind], Id=100, UniqueIdS=str(UUID(int=100)))
    model = NS(GetObjects=lambda: objects)
    drawing = NS(UniqueIdS=str(UUID(int=1)), QueryInterface=lambda interface: model)
    scales = NS(Contains=lambda identifier: identifier == 200,
                GetById=lambda identifier: NS(UniqueIdS=str(UUID(int=200))))
    session = NS(project=NS(Drawings2=NS(Count=1, GetByIndex=lambda index: drawing), Scales=scales),
                 sdk=NS(types=types), r=NS(IModel='IModel'))
    monkeypatch.setattr(sheet_views, 'object_by_id', lambda session, identifier: source)
    monkeypatch.setattr(sheet_views, 'parameters', lambda session, obj: {
        'RepresentedEntityId': {'value': 100}, 'ScaleId': {'value': 200}, 'SectionPlaneOffset': {'value': 1500}})
    return session


def test_existing_section_source_preflight_does_not_open_or_query_its_plane(monkeypatch):
    session = native_preflight_fixture(monkeypatch)
    pending = sheet_views._preflight(session, validate_view_additions(request()))
    assert len(pending) == 1
    assert pending[0][-1]['ScaleId'] == str(UUID(int=200))


def test_matching_existing_view_is_rejected_before_any_factory(monkeypatch):
    session = native_preflight_fixture(monkeypatch, duplicate=True)
    with pytest.raises(ValueError, match='already embedded'):
        sheet_views._preflight(session, validate_view_additions(request()))


def test_model_view_cannot_bind_an_unrelated_wall_as_a_section_source(monkeypatch):
    session = native_preflight_fixture(monkeypatch, source_kind='Wall')
    with pytest.raises(ValueError, match='Level, Section or Elevation'):
        sheet_views._preflight(session, validate_view_additions(request()))


def test_saved_readback_returns_actual_renumbered_ids_and_preserves_uuid_evidence(monkeypatch):
    """Matching UUIDs must not publish the old requested numeric references."""
    source_uuid, scale_uuid, drawing_uuid, object_uuid = [str(UUID(int=i)) for i in (100, 200, 300, 400)]
    actual = {'RepresentedEntityId': 110, 'ScaleId': 220, 'SectionPlaneOffset': 1500.0}
    monkeypatch.setattr(sheet_views, 'parameters', lambda session, obj: {
        key: {'value': value} for key, value in actual.items()})
    monkeypatch.setattr(sheet_views, 'object_by_id', lambda session, identifier:
        NS(UniqueIdS=source_uuid) if identifier == 110 else None)
    monkeypatch.setattr(sheet_views, '_pose', lambda bounded: {
        'content_origin_mm': [140, 150], 'content_x_axis': [1, 0]})
    monkeypatch.setattr(sheet_views, '_bounds', lambda bounded: [100, 180, 110, 190])
    session = NS(project=NS(Scales=NS(GetById=lambda identifier:
        NS(UniqueIdS=scale_uuid) if identifier == 220 else None)), r=NS(IRectBoundedObject='bounded'))
    obj = NS(UniqueIdS=object_uuid, ObjectTypeS=str(UUID(int=500)),
             QueryInterface=lambda interface: NS(HasContent=True))
    expected = {'kind': 'model', 'inspected_source_uuid': source_uuid, 'origin_mm': [140, 150],
                'parameters': {'RepresentedEntityId': 10, 'ScaleId': 20, 'SectionPlaneOffset': 1500},
                'resource_uuids': {'ScaleId': scale_uuid}}
    before = copy.deepcopy(expected)
    observed = sheet_views._read_record(session, NS(UniqueIdS=drawing_uuid), obj, expected)
    assert observed['parameters'] == actual
    assert observed['inspected_source_uuid'] == source_uuid
    assert observed['resource_uuids'] == {'ScaleId': scale_uuid}
    assert expected == before
