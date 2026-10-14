"""Pure metadata policy tests; no fake successful native editing scenario."""

from types import SimpleNamespace

import pytest

from renga_codex_bridge.project_info import read_project_info, validate_project_info_values


def test_explicit_unicode_and_empty_string_metadata_are_valid_inputs():
    values = {"Code": "DEMO-001", "Name": "Тестовый проект", "Stage": "АР", "Description": ""}
    assert validate_project_info_values(values) == values


def test_reviewed_metadata_is_copied_from_caller_input():
    values = {"Name": "Initial"}
    validated = validate_project_info_values(values)
    values["Name"] = "Changed outside the reviewed plan"
    assert validated == {"Name": "Initial"}


@pytest.mark.parametrize("values", [None, [], {}, "metadata"])
def test_metadata_edits_require_a_nonempty_object(values):
    with pytest.raises(ValueError):
        validate_project_info_values(values)


@pytest.mark.parametrize("field", ["UniqueId", "UniqueIdS", "FilePath", "name", "CustomProperty"])
def test_immutable_or_undocumented_fields_cannot_be_set(field):
    with pytest.raises(ValueError, match="field"):
        validate_project_info_values({field: "value"})


@pytest.mark.parametrize("value", [None, 123, True, ["text"], {"text": "value"}])
def test_native_bstr_setters_require_strings(value):
    with pytest.raises(ValueError, match="string"):
        validate_project_info_values({"Code": value})


def test_embedded_nul_is_not_silently_truncated():
    with pytest.raises(ValueError, match="NUL"):
        validate_project_info_values({"Name": "Part\x00not visible"})


def test_metadata_read_preserves_null_bstr_and_native_project_uuid():
    info = SimpleNamespace(Code="DEMO-001", Name="Synthetic project", Stage="АР",
                           Description=None, UniqueIdS="{12345678-1234-4321-9876-123456789ABC}")
    session = SimpleNamespace(project=SimpleNamespace(ProjectInfo=info))
    actual = read_project_info(session)
    assert actual["Description"] is None
    assert actual["UniqueIdS"] == info.UniqueIdS
    assert actual["Name"] == "Synthetic project"


def test_missing_project_metadata_is_an_error():
    session = SimpleNamespace(project=SimpleNamespace(ProjectInfo=None))
    with pytest.raises(RuntimeError, match="absent"):
        read_project_info(session)
