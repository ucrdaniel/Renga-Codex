import copy
from uuid import UUID

import pytest

from renga_codex_bridge.sheet_texts import (
    append_sheet_texts, reject_existing_text_duplicates, validate_text_additions,
)


DRAWING = str(UUID(int=1))
OTHER_DRAWING = str(UUID(int=2))


def request():
    return [{'drawing_uuid': DRAWING, 'text': 'General note\nSecond paragraph',
             'bounds_mm': [20, 120, 200, 215], 'font_family': 'Arial', 'cap_size_mm': 2.5}]


def test_complete_text_request_normalizes_uuid_and_numbers_without_mutating_caller():
    rows = request()
    rows[0]['drawing_uuid'] = '{' + DRAWING.upper() + '}'
    rows[0]['bounds_mm'] = (20, 120, 200, 215)
    before = copy.deepcopy(rows)
    result = validate_text_additions(rows)
    assert rows == before
    assert result[0]['drawing_uuid'] == DRAWING
    assert result[0]['bounds_mm'] == [20., 120., 200., 215.]
    assert result[0]['text'] == 'General note\nSecond paragraph'
    assert result[0]['cap_size_mm'] == 2.5


@pytest.mark.parametrize('field', ['drawing_uuid', 'text', 'bounds_mm', 'font_family', 'cap_size_mm'])
def test_every_text_field_is_explicitly_required(field):
    rows = request()
    del rows[0][field]
    with pytest.raises(ValueError):
        validate_text_additions(rows)


@pytest.mark.parametrize('field,value', [
    ('drawing_uuid', 'not-a-uuid'), ('text', ''), ('text', '  \n '),
    ('text', 'note\x00'), ('text', 'note\r\nline'), ('text', 'note\tline'),
    ('font_family', ''), ('font_family', 'Arial\n'), ('font_family', 1),
    ('cap_size_mm', True), ('cap_size_mm', float('nan')), ('cap_size_mm', float('inf')),
    ('cap_size_mm', .09), ('cap_size_mm', 101), ('cap_size_mm', 10**1000),
    ('bounds_mm', [20, 20, 200, 215]), ('bounds_mm', [20, 120, 215, 200]),
    ('bounds_mm', [20, 120, False, 215]), ('bounds_mm', [20, 120, 200, float('nan')]),
    ('bounds_mm', [20, 120, 200]), ('unexpected', 'value'),
])
def test_invalid_request_fails_validation(field, value):
    rows = request()
    rows[0][field] = value
    with pytest.raises(ValueError):
        validate_text_additions(rows)


@pytest.mark.parametrize('value', [None, {}, [], [None], [{}], [request()[0]] * 1001])
def test_invalid_batch_shape_or_size_is_rejected(value):
    with pytest.raises(ValueError):
        validate_text_additions(value)


def test_same_sheet_text_and_bounds_duplicate_is_rejected_even_with_different_fonts():
    rows = request()
    rows.append({**rows[0], 'font_family': 'Another font', 'cap_size_mm': 3.5})
    with pytest.raises(ValueError, match='Duplicate'):
        validate_text_additions(rows)


def test_identical_text_at_another_position_or_on_another_sheet_is_allowed():
    rows = request()
    rows.append({**rows[0], 'bounds_mm': [20, 120, 180, 195]})
    rows.append({**rows[0], 'drawing_uuid': OTHER_DRAWING})
    assert len(validate_text_additions(rows)) == 3


def test_saved_duplicate_guard_uses_text_and_native_bounds_independent_of_font():
    rows = validate_text_additions(request())
    existing = [{**rows[0], 'font_family': 'Different font', 'cap_size_mm': 3.5,
                 'bounds_mm': [20 + 1e-8, 120, 200, 215]}]
    with pytest.raises(ValueError, match='already exist'):
        reject_existing_text_duplicates(rows, existing)


@pytest.mark.parametrize('changed', [
    {'drawing_uuid': OTHER_DRAWING}, {'text': 'A different note'},
    {'bounds_mm': [21, 121, 200, 215]},
])
def test_saved_guard_allows_distinct_sheet_or_text_or_position(changed):
    rows = validate_text_additions(request())
    reject_existing_text_duplicates(rows, [{**rows[0], **changed}])


def test_invalid_batch_never_starts_a_native_session_or_writes_a_plan(monkeypatch):
    import renga_codex_bridge.sheet_texts as module
    calls = []
    monkeypatch.setattr(module, 'Session', lambda *args, **kwargs: calls.append('native'))
    monkeypatch.setattr(module, 'save_plan', lambda *args, **kwargs: calls.append('plan'))
    invalid = request()
    del invalid[0]['font_family']
    with pytest.raises(ValueError):
        append_sheet_texts('unused.rnp', invalid)
    assert calls == []
