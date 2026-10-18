"""Pure request/symbol/color checks, not native resource authoring claims."""
import math

import pytest

from renga_codex_bridge.resources import color_to_native_int, color_from_native_int, parse_profile_namespace, validate_resource_specs


@pytest.mark.parametrize("rgba,packed", [([255,0,0,255],-65536),([0,0,0,255],-16777216),([255,255,255,255],-1),([1,2,3,4],0x04010203),([0,0,0,0],0)])
def test_rgba_matches_signed_sdk_color_wire_layout(rgba, packed):
    assert color_to_native_int(rgba) == packed
    assert color_from_native_int(packed) == rgba


@pytest.mark.parametrize("rgba", [None, [], [0,0,0], [0,0,0,256], [-1,0,0,255], [True,0,0,255], [1.0,0,0,255], "red"])
def test_invalid_rgba_is_rejected_before_com(rgba):
    with pytest.raises(ValueError): color_to_native_int(rgba)


@pytest.mark.parametrize("packed", [True, 1.0, None, 2**31, -(2**31)-1])
def test_native_color_requires_signed_int32(packed):
    with pytest.raises(ValueError): color_from_native_int(packed)


def test_profile_namespace_does_not_use_another_shapes_same_symbol():
    # Synthetic GUIDs deliberately avoid redistributing SDK constants/headers.
    header = '''namespace RectangleParameters {
    const GUID Width = {0x1, 0x2, 0x3, {0x4,0x5,0x6,0x7,0x8,0x9,0xa,0xb}};
    const GUID Height = {0x11, 0x12, 0x13, {0x14,0x15,0x16,0x17,0x18,0x19,0x1a,0x1b}};
    } namespace OtherParameters {
    const GUID Width = {0x99, 0x2, 0x3, {0x4,0x5,0x6,0x7,0x8,0x9,0xa,0xb}};
    }'''
    result = parse_profile_namespace(header)
    assert result["Width"].startswith("{00000001-")
    assert result["Height"].startswith("{00000011-")
    assert len(result) == 2


@pytest.mark.parametrize("text,namespace", [("", "RectangleParameters"), ("namespace RectangleParameters {", "RectangleParameters"), ("", "../File")])
def test_missing_or_malformed_profile_scope_is_explicit(text, namespace):
    with pytest.raises(ValueError): parse_profile_namespace(text, namespace)


def test_explicit_material_and_rectangular_style_request_is_copied():
    raw = [{"kind":"Material","name":"Insulation","ref":"xps","color_rgba":[128,128,128,255],"density_kg_m3":30},
           {"kind":"BeamStyle","name":"300x400","profile":{"kind":"Rectangle","width_mm":300,"height_mm":400}}]
    result = validate_resource_specs(raw)
    assert result[0]["density_kg_m3"] == 30.0
    assert result[1]["profile"]["height_mm"] == 400.0
    result[0]["color_rgba"][0] = 0
    result[1]["profile"]["width_mm"] = 10
    assert raw[0]["color_rgba"][0] == 128 and raw[1]["profile"]["width_mm"] == 300


@pytest.mark.parametrize("value", [True, -1, 0, math.nan, math.inf, "300", 10**1000])
def test_rectangle_width_requires_finite_positive_mm(value):
    with pytest.raises(ValueError):
        validate_resource_specs([{"kind":"BeamStyle","name":"bad","profile":{"kind":"Rectangle","width_mm":value,"height_mm":400}}])


@pytest.mark.parametrize("value", [True, -1, math.nan, math.inf, "30", 10**1000])
def test_material_density_requires_nonnegative_finite_number(value):
    with pytest.raises(ValueError): validate_resource_specs([{"kind":"Material","name":"bad","density_kg_m3":value}])


def test_zero_material_density_is_explicitly_allowed():
    assert validate_resource_specs([{"kind":"Material","name":"void","density_kg_m3":0}])[0]["density_kg_m3"] == 0


@pytest.mark.parametrize("name", ["", "  ", None, "X\nY", "X\0", "X\u0085Y", "X\ud800"])
def test_resource_names_cannot_contain_controls_or_surrogates(name):
    with pytest.raises(ValueError): validate_resource_specs([{"kind":"Material","name":name}])


@pytest.mark.parametrize("kind", ["LayeredMaterial","MaterialLayer","Profile"])
def test_unsupported_geometry_or_layer_authoring_is_never_silently_accepted(kind):
    with pytest.raises(NotImplementedError): validate_resource_specs([{"kind":kind,"name":"unsupported","layers":[]}])


@pytest.mark.parametrize("key", ["hatch","surface_hatch","section_hatch","layers","texture"])
def test_unsupported_appearance_definition_requires_explicit_failure(key):
    with pytest.raises(NotImplementedError): validate_resource_specs([{"kind":"Material","name":"bad",key:{}}])


@pytest.mark.parametrize("specs", [[], {}, [None], [{"kind":"TagStyle","name":"panel"}], [{"kind":"Material","name":"X","ignored":1}]])
def test_ambiguous_or_unhandled_resource_request_is_rejected(specs):
    with pytest.raises(ValueError): validate_resource_specs(specs)


def test_duplicate_collection_names_and_refs_are_rejected():
    with pytest.raises(ValueError,match="unique"):
        validate_resource_specs([{"kind":"Material","name":"ABC"},{"kind":"Material","name":"abc"}])
    with pytest.raises(ValueError,match="refs"):
        validate_resource_specs([{"kind":"Material","name":"A","ref":"same"},{"kind":"Material","name":"B","ref":"same"}])


def test_custom_contour_cannot_be_misrepresented_as_supported_rectangle():
    with pytest.raises(NotImplementedError):
        validate_resource_specs([{"kind":"BeamStyle","name":"parapet","profile":{"kind":"Contour","points":[[0,0],[300,0],[300,100]]}}])
    with pytest.raises(ValueError):
        validate_resource_specs([{"kind":"BeamStyle","name":"rectangle","profile":{"kind":"Rectangle","width_mm":300,"height_mm":400,"points":[]}}])


def test_resource_count_is_bounded():
    with pytest.raises(ValueError):
        validate_resource_specs([{"kind":"Material","name":str(i)} for i in range(1001)])


def test_filling_factories_accept_explicit_exposed_parameters_without_inventing_panel_counts():
    door = {"kind":"DoorStyle", "name":"Native default door", "parameters":{"MaterialId":42,"PanelDepth":50,"Lining":True}}
    window = {"kind":"WindowStyle", "name":"Native default window", "parameters":{"FrameDepth":80.0,"FrameThickness":60}}
    result = validate_resource_specs([door,window])
    assert result[0]["parameters"] == door["parameters"]
    assert result[1]["parameters"] == window["parameters"]
    result[0]["parameters"]["PanelDepth"] = 80
    assert door["parameters"]["PanelDepth"] == 50
    assert validate_resource_specs([{"kind":"DoorStyle","name":"default"}])[0]["parameters"] == {}


@pytest.mark.parametrize("parameters", [None, [], {"EntityName":"different"}, {"UniqueId":"changed"}, {"PanelCount":2}, {"OpeningType":"tilt"}, {"Glazing":True}, {"FrameDepth":20}])
def test_filling_unknown_or_identity_or_wrong_kind_parameters_are_rejected(parameters):
    with pytest.raises(ValueError): validate_resource_specs([{"kind":"DoorStyle","name":"door","parameters":parameters}])


@pytest.mark.parametrize("value", [None, [], {}, math.nan, math.inf, 2**31, -(2**31)-1, "bad\x00text"])
def test_filling_parameter_values_are_bounded_primitives(value):
    with pytest.raises(ValueError): validate_resource_specs([{"kind":"DoorStyle","name":"door","parameters":{"PanelDepth":value}}])


def test_window_does_not_accept_door_panel_parameter():
    with pytest.raises(ValueError):
        validate_resource_specs([{"kind":"WindowStyle","name":"window","parameters":{"PanelDepth":50}}])
