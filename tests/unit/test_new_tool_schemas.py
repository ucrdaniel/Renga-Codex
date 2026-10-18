"""Strict new-tool transport contracts; no worker, COM or Renga invocation."""
import asyncio
import copy
import uuid

from jsonschema import Draft202012Validator, ValidationError as SchemaError
from pydantic import TypeAdapter, ValidationError
import pytest

from renga_codex_bridge import tool_contracts as c
from renga_codex_bridge.existing_properties import validate_existing_property_changes
from renga_codex_bridge.resource_edits import validate_window_style_changes
from renga_codex_bridge.sheet_additions import validate_schedule_additions
from renga_codex_bridge.sheet_views import validate_view_additions


UUID1, UUID2 = (str(uuid.UUID(int=i)) for i in (1, 2))


def style():
    return {"resource_uuid": UUID1, "expected_name": "Existing window", "parameters": {"FrameDepth": 150}}


def prop():
    return {"kind": "Drawing", "uuid": UUID1, "property_guid": UUID2,
            "property_name": "Author", "value": "Example Author"}


def cell():
    return {"drawing_uuid": UUID1, "block_index": 0, "block_name": "Main", "column": 0, "row": 1,
            "expected_before": "", "expected_value": "Example Author"}


def schedule():
    return {"drawing_uuid": UUID1, "schedule_id": 123, "available_bounds_mm": [10, 200, 50, 280]}


def view(kind="model"):
    value = {"drawing_uuid": UUID1, "kind": kind, "source_entity_id": 123,
             "scale_id": 456, "origin_mm": [140, 160]}
    if kind == "entity":
        value["object_mark"] = "EX-1"
    return value


CASES = [(c.WindowStyleChange, style), (c.ExistingPropertyChange, prop),
         (c.TitleBlockCellCheck, cell), (c.ScheduleAddition, schedule),
         (c.ViewAddition, view), (c.ViewAddition, lambda: view("entity"))]


def schema(model):
    result = TypeAdapter(model).json_schema()
    Draft202012Validator.check_schema(result)
    return Draft202012Validator(result)


@pytest.mark.parametrize("model,factory", CASES)
def test_valid_model_matches_strict_json_schema_and_preserves_omission(model, factory):
    value = factory()
    schema(model).validate(value)
    parsed = TypeAdapter(model).validate_python(value)
    assert parsed.model_dump(exclude_unset=True) == value


@pytest.mark.parametrize("model,factory", CASES)
def test_unknown_item_keys_are_forbidden_by_both_layers(model, factory):
    value = {**factory(), "unsupported_native_setter": True}
    with pytest.raises(SchemaError): schema(model).validate(value)
    with pytest.raises(ValidationError): TypeAdapter(model).validate_python(value)


@pytest.mark.parametrize("model,factory", CASES)
def test_required_item_fields_cannot_be_omitted(model, factory):
    value = factory()
    value.pop(next(iter(value)))
    with pytest.raises(SchemaError): schema(model).validate(value)
    with pytest.raises(ValidationError): TypeAdapter(model).validate_python(value)


@pytest.mark.parametrize("field", ["FrameThickness", "FrameDepth", "VerticalMullionThickness",
                                  "HorizontalMullionThickness", "WindowLiningThickness", "WindowLiningDepth"])
@pytest.mark.parametrize("invalid", [-1, 0, True, "150", None])
def test_window_length_schema_has_real_numeric_bounds(field, invalid):
    value = {**style(), "parameters": {field: invalid}}
    with pytest.raises(SchemaError): schema(c.WindowStyleChange).validate(value)
    with pytest.raises(ValidationError): c.WindowStyleChange.model_validate(value)


@pytest.mark.parametrize("parameters", [{"MaterialId": 4}, {"SillThickness": 25}, {"new_panel_tree": []}])
def test_window_parameter_whitelist_has_no_numeric_material_or_private_panel_fields(parameters):
    value = {**style(), "parameters": parameters}
    with pytest.raises(SchemaError): schema(c.WindowStyleChange).validate(value)
    with pytest.raises(ValidationError): c.WindowStyleChange.model_validate(value)


def test_window_requires_a_parameter_or_material_and_material_uuid_is_optional_nonnullable():
    base = {"resource_uuid": UUID1, "expected_name": "Existing"}
    for value in (base, {**base, "parameters": {}}, {**base, "material_uuid": None}):
        with pytest.raises(SchemaError): schema(c.WindowStyleChange).validate(value)
        with pytest.raises(ValidationError): c.WindowStyleChange.model_validate(value)
    value = {**base, "material_uuid": UUID2}
    assert c.plain_requests([c.WindowStyleChange.model_validate(value)]) == [value]
    schema(c.WindowStyleChange).validate(value)


@pytest.mark.parametrize("model,factory", [(c.ScheduleAddition, schedule), (c.ViewAddition, view)])
@pytest.mark.parametrize("invalid", [-0.01, True, "1", None])
def test_inset_schema_rejects_negative_or_nonnumeric_values(model, factory, invalid):
    value = {**factory(), "fit_inset_mm": invalid}
    with pytest.raises(SchemaError): schema(model).validate(value)
    with pytest.raises(ValidationError): TypeAdapter(model).validate_python(value)


@pytest.mark.parametrize("model,factory", [(c.ScheduleAddition, schedule), (c.ViewAddition, view)])
def test_omitted_inset_stays_omitted_instead_of_injecting_wrong_default(model, factory):
    parsed = TypeAdapter(model).validate_python(factory())
    assert "fit_inset_mm" not in c.plain_requests([parsed])[0]
    assert c.plain_requests([parsed]) == [factory()]


@pytest.mark.parametrize("model,factory", CASES)
def test_nonnullable_optional_fields_do_not_advertise_a_null_default(model, factory):
    def visit(value):
        if isinstance(value, dict):
            assert not ("default" in value and value["default"] is None)
            for child in value.values(): visit(child)
        elif isinstance(value, list):
            for child in value: visit(child)
    visit(TypeAdapter(model).json_schema())


@pytest.mark.parametrize("kind", ["Project", "Drawing", "Topic"])
def test_exact_property_kind_and_empty_value_supported(kind):
    value = {**prop(), "kind": kind, "value": ""}
    c.ExistingPropertyChange.model_validate(value)
    schema(c.ExistingPropertyChange).validate(value)


@pytest.mark.parametrize("invalid", ["Wall", "project", "DrawingStyle", None])
def test_property_kind_enum_is_closed(invalid):
    value = {**prop(), "kind": invalid}
    with pytest.raises(SchemaError): schema(c.ExistingPropertyChange).validate(value)
    with pytest.raises(ValidationError): c.ExistingPropertyChange.model_validate(value)


@pytest.mark.parametrize("field,value", [("block_index", -1), ("block_index", 100), ("column", -1),
                                       ("column", 10000), ("row", 10000), ("row", True)])
def test_cell_coordinates_have_strict_native_ranges(field, value):
    request = {**cell(), field: value}
    with pytest.raises(SchemaError): schema(c.TitleBlockCellCheck).validate(request)
    with pytest.raises(ValidationError): c.TitleBlockCellCheck.model_validate(request)


@pytest.mark.parametrize("value", [view("entity"), {**view(), "object_mark": "EX-1"},
                                   {**view(), "kind": "schedule"}])
def test_view_discriminator_requires_entity_mark_and_forbids_model_mark(value):
    if value["kind"] == "entity":
        value.pop("object_mark")
    with pytest.raises(SchemaError): schema(c.ViewAddition).validate(value)
    with pytest.raises(ValidationError): TypeAdapter(c.ViewAddition).validate_python(value)


@pytest.mark.parametrize("kind,parameters", [
    ("model", {"ObjectViewDirection": 3}), ("entity", {"ModelViewDirection": 3}),
    ("model", {"ShowAxes": True}), ("model", {"FilterId": 0}),
    ("model", {"VisualStyle": True}), ("entity", {"ObjectPartBeyondViewDepthPlane": 1}),
    ("model", {"ModelViewDirection": 2**31}),
])
def test_view_parameter_schema_matches_kind_and_strict_scalar_rules(kind, parameters):
    value = {**view(kind), "view_parameters": parameters}
    with pytest.raises(SchemaError): schema(c.ViewAddition).validate(value)
    with pytest.raises(ValidationError): TypeAdapter(c.ViewAddition).validate_python(value)


@pytest.mark.parametrize("value", [True, 123, 1.25, "primitive value"])
def test_non_int_view_parameter_keeps_the_public_validators_broad_primitive_contract(value):
    request = {**view(), "view_parameters": {"SectionViewDepthPlaneOffset": value}}
    schema(c.ViewAddition).validate(request)
    TypeAdapter(c.ViewAddition).validate_python(request)
    validate_view_additions([request])


@pytest.mark.parametrize("model,factory,key", [(c.ScheduleAddition, schedule, "available_bounds_mm"),
                                              (c.ViewAddition, view, "bounds_mm")])
def test_cross_coordinate_order_is_checked_by_public_validator_not_fake_schema_keywords(model, factory, key):
    request = {**factory(), key: [20, 10, 30, 40]}
    schema(model).validate(request)  # JSON Schema cannot compare array members.
    with pytest.raises(ValidationError): TypeAdapter(model).validate_python(request)


@pytest.mark.parametrize("factory,validator", [(style, validate_window_style_changes),
    (prop, validate_existing_property_changes), (schedule, validate_schedule_additions),
    (view, validate_view_additions)])
def test_cross_record_duplicates_still_require_public_batch_validator(factory, validator):
    with pytest.raises(ValueError): validator([factory(), factory()])


def test_plain_requests_detaches_raw_dicts_and_preserves_mixed_model_omission():
    raw = schedule()
    original = copy.deepcopy(raw)
    result = c.plain_requests([raw, c.ScheduleAddition.model_validate(raw)])
    assert result == [raw, raw]
    result[0]["available_bounds_mm"][0] = -10
    assert raw == original
    for invalid in (None, {}, [123]):
        with pytest.raises(ValueError): c.plain_requests(invalid)


@pytest.fixture(scope="module")
def registered_tools():
    # Registration/schema discovery only; no tool invocation or worker process.
    from renga_codex_bridge.mcp_server import server
    return {tool.name: tool for tool in asyncio.run(server.list_tools())}


TOOL_INPUTS = [
    ("bridge_update_window_styles", "changes", style, 100),
    ("bridge_update_existing_properties", "changes", prop, 1000),
    ("bridge_append_sheet_schedules", "additions", schedule, 100),
    ("bridge_append_sheet_views", "additions", view, 100),
]


@pytest.mark.parametrize("name,field,factory,maximum", TOOL_INPUTS)
def test_real_registered_tool_schema_has_nested_contract_and_batch_limits(registered_tools, name, field, factory, maximum):
    native_schema = registered_tools[name].input_schema
    Draft202012Validator.check_schema(native_schema)
    validator = Draft202012Validator(native_schema)
    validator.validate({"project": "test.rnp", field: [factory()]})
    for rows in ([], [factory()] * (maximum + 1)):
        with pytest.raises(SchemaError): validator.validate({"project": "test.rnp", field: rows})
    with pytest.raises(SchemaError):
        validator.validate({"project": "test.rnp", field: [{**factory(), "unsupported": True}]})
    with pytest.raises(SchemaError):
        validator.validate({"project": "test.rnp", field: [factory()], "authorized": True})


def test_registered_sha_pin_and_cell_checks_are_explicit_and_bounded(registered_tools):
    window = Draft202012Validator(registered_tools["bridge_update_window_styles"].input_schema)
    window.validate({"project": "test.rnp", "changes": [style()], "expected_project_sha256": "a" * 64})
    with pytest.raises(SchemaError):
        window.validate({"project": "test.rnp", "changes": [style()], "expected_project_sha256": "short"})
    properties = Draft202012Validator(registered_tools["bridge_update_existing_properties"].input_schema)
    properties.validate({"project": "test.rnp", "changes": [prop()], "cell_checks": [cell()]})
    with pytest.raises(SchemaError):
        properties.validate({"project": "test.rnp", "changes": [prop()], "cell_checks": [cell()] * 1001})


@pytest.mark.parametrize("name,field,factory,maximum", TOOL_INPUTS)
def test_registered_argument_validator_rejects_extras_and_project_coercion_without_invocation(name, field, factory, maximum):
    from renga_codex_bridge.mcp_server import server
    native = server._tool_manager.get_tool(name)
    base = {"project": "test.rnp", field: [factory()]}
    parsed = native.fn_metadata.validate_arguments(base)
    assert parsed["project"] == "test.rnp"
    for value in ({**base, "authorized": True}, {**base, "project": 123}, {**base, "project": None}):
        with pytest.raises(ValidationError): native.fn_metadata.validate_arguments(value)
