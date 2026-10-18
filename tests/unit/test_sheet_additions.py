import copy
from uuid import UUID

import pytest

from renga_codex_bridge.sheet_additions import (
    anchored_content_origin, assert_appended_identities, validate_schedule_additions,
    assert_resource_identity_subset,
)


DRAWING = str(UUID(int=1))
CONTENT = str(UUID(int=2))
NEW = str(UUID(int=3))


def request():
    return [{'drawing_uuid': DRAWING, 'schedule_id': 10,
             'available_bounds_mm': [55, 287, 140, 195], 'fit_inset_mm': 0}]


def test_schedule_addition_validation_does_not_mutate_callers_and_normalizes_uuid():
    value = request()
    value[0]['drawing_uuid'] = '{' + DRAWING.upper() + '}'
    old = copy.deepcopy(value)
    assert validate_schedule_additions(value)[0]['drawing_uuid'] == DRAWING
    assert value == old


@pytest.mark.parametrize('fault', ['missing_drawing', 'missing_source', 'bool_source', 'negative_source', 'duplicate', 'unknown', 'reversed', 'nan', 'bool_coordinate', 'negative_inset'])
def test_invalid_additions_fail_before_native_session(fault):
    value = request()
    if fault == 'missing_drawing':
        del value[0]['drawing_uuid']
    elif fault == 'missing_source':
        del value[0]['schedule_id']
    elif fault == 'bool_source':
        value[0]['schedule_id'] = True
    elif fault == 'negative_source':
        value[0]['schedule_id'] = -1
    elif fault == 'duplicate':
        value.append(copy.deepcopy(value[0]))
    elif fault == 'unknown':
        value[0]['text'] = 'Not a native table'
    elif fault == 'reversed':
        value[0]['available_bounds_mm'] = [287, 55, 140, 195]
    elif fault == 'nan':
        value[0]['available_bounds_mm'][0] = float('nan')
    elif fault == 'bool_coordinate':
        value[0]['available_bounds_mm'][0] = False
    else:
        value[0]['fit_inset_mm'] = -1
    with pytest.raises(ValueError):
        validate_schedule_additions(value)


def test_placement_uses_actual_asymmetric_fitted_rectangle_not_assumed_center_or_width():
    # Native placement origin can be unrelated to the bounds center.
    assert anchored_content_origin([-20, 165, -10, 43], [7, 8], [55, 287, 140, 195]) == [82, 160]


@pytest.mark.parametrize('actual', [[0, 233, 0, 53], [0, 185, 0, 56]])
def test_schedule_larger_than_available_space_is_rejected_not_stretched_or_cropped(actual):
    with pytest.raises(ValueError, match='does not fit'):
        anchored_content_origin(actual, [0, 0], [55, 287, 140, 195])


def identity():
    return {'building': {'building-object': 'wall-type'},
            'drawings': {DRAWING: {'type_guid': 'drawing-type', 'contents': {CONTENT: 'text-type'}}}}


def test_exact_new_schedule_identity_is_allowed_while_preserving_all_existing_identity_types():
    before = identity()
    after = copy.deepcopy(before)
    after['drawings'][DRAWING]['contents'][NEW] = 'schedule-type'
    assert_appended_identities(before, after, [{'drawing_uuid': DRAWING, 'object_uuid': NEW, 'object_type_guid': 'schedule-type'}])


@pytest.mark.parametrize('fault', ['building_change', 'drawing_change', 'removed_content', 'extra_content', 'changed_old_type'])
def test_unintended_identity_or_type_changes_are_rejected(fault):
    before = identity()
    after = copy.deepcopy(before)
    after['drawings'][DRAWING]['contents'][NEW] = 'schedule-type'
    if fault == 'building_change':
        after['building']['building-object'] = 'other-type'
    elif fault == 'drawing_change':
        after['drawings']['unrequested'] = {'type_guid': 'drawing-type', 'contents': {}}
    elif fault == 'removed_content':
        del after['drawings'][DRAWING]['contents'][CONTENT]
    elif fault == 'extra_content':
        after['drawings'][DRAWING]['contents']['other'] = 'unexpected'
    else:
        after['drawings'][DRAWING]['contents'][CONTENT] = 'other-type'
    with pytest.raises(RuntimeError):
        assert_appended_identities(before, after, [{'drawing_uuid': DRAWING, 'object_uuid': NEW, 'object_type_guid': 'schedule-type'}])


def test_old_resource_uuid_type_subset_is_checked_without_claiming_unavailable_catalogs():
    before = {'Schedules': {'available': True, 'identities': {'source': 'schedule-type'}},
              'Unsupported': {'available': False, 'reason': 'not in this API'}}
    after = {'Schedules': {'available': True, 'identities': {'source': 'schedule-type', 'native-new': 'schedule-type'}}}
    result = assert_resource_identity_subset(before, after)
    assert result['checked_available_catalogs'] == ['Schedules']
    assert result['preserved_resource_identities'] == 1
    assert result['additional_resource_identities'] == 1


@pytest.mark.parametrize('actual', [{}, {'available': False}, {'available': True, 'identities': {}},
                                  {'available': True, 'identities': {'source': 'wrong-type'}}])
def test_lost_or_changed_resource_uuid_type_is_rejected(actual):
    before = {'Schedules': {'available': True, 'identities': {'source': 'schedule-type'}}}
    with pytest.raises(RuntimeError):
        assert_resource_identity_subset(before, {'Schedules': actual})
