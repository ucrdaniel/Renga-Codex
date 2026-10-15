"""Own resource authoring through documented collection/parameter APIs.

Supported authoring: ordinary Materials, rectangular Beam/Column styles using
the installed SDK's existing rectangle profile, and default native Door/Window
styles with their exposed definition parameters. Custom profile geometry,
layer-stack authoring and surface/section hatch editors have no verified public
contract and are rejected explicitly. No SDK implementation/constants are bundled.
STEP/STP ElementStyle imports additionally require immutable input hashes and
independent dimensions/volume/surface/triangle expectations, checked using
temporary native Elements before save and again after reopening.
"""
from __future__ import annotations

from contextlib import contextmanager
import math
import re
import unicodedata
import uuid

from .audit import event, save_plan
from .model import parameters, parameter_value, set_parameter
from .sdk import parse_guids
from .session import Session
from .safety import checked_path, fingerprint
from .element_style_geometry import validate_step_spec, verify_step_source, probe_element_style

RESOURCE_COLLECTIONS = ("Materials", "Profiles", "BeamStyles", "ColumnStyles", "LayeredMaterials", "DoorStyles", "WindowStyles", "ElementStyles")
AUTHOR_COLLECTIONS = {"Material": "Materials", "BeamStyle": "BeamStyles", "ColumnStyle": "ColumnStyles",
                      "DoorStyle": "DoorStyles", "WindowStyle": "WindowStyles", "ElementStyle": "ElementStyles"}
FILLING_PARAMETERS = {
    "DoorStyle": frozenset({"Casing", "CasingDepth", "CasingWidth", "DoorLiningDepth", "DoorLiningThickness",
        "Lining", "MaterialId", "MullionThickness", "PanelDepth", "PanelOffset", "Threshold", "ThresholdThickness",
        "TransomConstruction", "TransomHeight"}),
    "WindowStyle": frozenset({"FrameDepth", "FrameThickness", "HorizontalMullionThickness", "MaterialId",
        "VerticalMullionThickness", "WindowLiningDepth", "WindowLiningThickness"}),
}


def _number(value, label, *, nonnegative=False):
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError(label + " requires an explicit finite number")
    try:
        result = float(value)
    except (OverflowError, ValueError) as error:
        raise ValueError(label + " must be finite") from error
    if not math.isfinite(result) or (result < 0 if nonnegative else result <= 0):
        raise ValueError(label + " must be finite and " + ("nonnegative" if nonnegative else "positive"))
    return result


def color_to_native_int(rgba):
    """Pack explicit RGBA bytes as the SDK's signed 32-bit AARRGGBB value.

    Byte layout follows the documented Color parameter/Utils conversion format;
    this is an independent byte-based implementation, not copied SDK code.
    """
    if (not isinstance(rgba, (list, tuple)) or len(rgba) != 4
            or any(isinstance(v, bool) or not isinstance(v, int) or not 0 <= v <= 255 for v in rgba)):
        raise ValueError("color_rgba must contain four explicit integer bytes R,G,B,A")
    red, green, blue, alpha = rgba
    return int.from_bytes(bytes((blue, green, red, alpha)), "little", signed=True)


def color_from_native_int(value):
    if isinstance(value, bool) or not isinstance(value, int) or not -(2**31) <= value < 2**31:
        raise ValueError("Native color must be a signed 32-bit integer")
    blue, green, red, alpha = value.to_bytes(4, "little", signed=True)
    return [red, green, blue, alpha]


def parse_profile_namespace(text, namespace="RectangleParameters"):
    """Read only one namespace of the user's SDK, avoiding duplicate Width IDs."""
    if not re.fullmatch(r"[A-Za-z_]\w*", namespace):
        raise ValueError("Invalid profile namespace")
    match = re.search(r"\bnamespace\s+" + re.escape(namespace) + r"\s*\{", text)
    if not match:
        raise ValueError("Local SDK profile namespace absent: " + namespace)
    begin = match.end()
    depth = 1
    for position in range(begin, len(text)):
        if text[position] == "{":
            depth += 1
        elif text[position] == "}":
            depth -= 1
            if depth == 0:
                return parse_guids(text[begin:position])
    raise ValueError("Unterminated local SDK profile namespace")


def _rectangle_guids(s):
    header = s.sdk.root / "C++/Include/Renga/ProfileParameters.h"
    found = parse_profile_namespace(header.read_text(encoding="utf-8-sig"))
    if not {"Width", "Height"} <= set(found):
        raise ValueError("Local SDK lacks rectangle Width/Height parameters")
    return found


def validate_resource_specs(specifications):
    if not isinstance(specifications, list) or not 1 <= len(specifications) <= 1000:
        raise ValueError("resources must be a list of 1 to 1000 explicit specifications")
    result = []
    refs = set()
    names = set()
    for raw in specifications:
        if not isinstance(raw, dict):
            raise ValueError("Resource specification must be an object")
        kind = raw.get("kind")
        if kind in {"LayeredMaterial", "MaterialLayer"}:
            raise NotImplementedError("Public API 2.50 has no verified layer creation/order/base-layer/hatch authoring contract")
        if kind == "Profile":
            raise NotImplementedError("Profiles.Create exists, but custom profile contour/constraints authoring is not exposed by IProfileDescription")
        if kind not in AUTHOR_COLLECTIONS:
            raise ValueError("Unsupported resource kind")
        if any(key in raw for key in ("hatch", "surface_hatch", "section_hatch", "layers", "texture")):
            raise NotImplementedError("Material layers, textures and surface/section hatch definitions are not authored through this adapter")
        common = {"kind", "name", "ref"}
        fields = ({"color_rgba", "density_kg_m3", "thermal_conductivity_w_m_k"} if kind == "Material"
                  else {"file_path", "source_sha256", "expected_dimensions_mm", "expected_geometry"} if kind == "ElementStyle"
                  else {"parameters"} if kind in FILLING_PARAMETERS else {"profile"})
        allowed = common | fields
        if set(raw) - allowed:
            raise ValueError("Unsupported resource fields: " + ", ".join(sorted(set(raw) - allowed)))
        name = raw.get("name")
        if (not isinstance(name, str) or not name.strip()
                or any(unicodedata.category(char) in {"Cc", "Cs"} for char in name)):
            raise ValueError("Resource name must be nonempty text without controls/surrogates")
        key = (kind, name.casefold())
        if key in names:
            raise ValueError("Resource names must be unique within their collection")
        names.add(key)
        row = {"kind": kind, "name": name}
        if "ref" in raw:
            ref = raw["ref"]
            if not isinstance(ref, str) or not ref.strip() or ref in refs:
                raise ValueError("Resource refs must be unique nonempty strings")
            refs.add(ref)
            row["ref"] = ref
        if kind == "ElementStyle":
            row.update(validate_step_spec(raw))
        elif kind == "Material":
            if "color_rgba" in raw:
                color_to_native_int(raw["color_rgba"])
                row["color_rgba"] = list(raw["color_rgba"])
            for key in ("density_kg_m3", "thermal_conductivity_w_m_k"):
                if key in raw:
                    row[key] = _number(raw[key], key, nonnegative=True)
        elif kind in FILLING_PARAMETERS:
            optional = raw.get("parameters", {})
            if not isinstance(optional, dict):
                raise ValueError("Style parameters must be an explicit object")
            if set(optional) - FILLING_PARAMETERS[kind]:
                raise ValueError("Unsupported filling style parameter; name/identity are controlled separately")
            row["parameters"] = {}
            for key, value in optional.items():
                if key=="MaterialId" and (type(value) is not int or not 0<value<=2**31-1):
                    raise ValueError("MaterialId requires an inspected positive native int32 ID; omit it for the native default")
                if not isinstance(value, (bool, int, float, str)):
                    raise ValueError("Style parameter values must be explicit primitives")
                if isinstance(value, float) and not math.isfinite(value):
                    raise ValueError("Style parameter numbers must be finite")
                if isinstance(value, int) and not isinstance(value, bool) and not -(2**31) <= value < 2**31:
                    raise ValueError("Integer style parameters must fit native signed int32")
                if isinstance(value, str) and "\x00" in value:
                    raise ValueError("Style parameter strings cannot contain NUL")
                row["parameters"][key] = value
        else:
            profile = raw.get("profile")
            if not isinstance(profile, dict) or profile.get("kind") != "Rectangle":
                raise NotImplementedError("Only an existing native Rectangle profile with explicit width_mm/height_mm is supported")
            if set(profile) != {"kind", "width_mm", "height_mm"}:
                raise ValueError("Rectangle profile requires exactly kind, width_mm and height_mm")
            row["profile"] = {"kind": "Rectangle", "width_mm": _number(profile["width_mm"], "profile width_mm"),
                              "height_mm": _number(profile["height_mm"], "profile height_mm")}
        result.append(row)
    return result


def _container_parameters(container):
    result = {}
    identifiers = container.GetIds()
    for index in range(identifiers.Count):
        guid = identifiers.GetS(index)
        parameter = container.GetS(guid)
        result[guid] = {"value": parameter_value(parameter), "readonly": bool(parameter.IsReadOnly),
                        "has_value": bool(parameter.HasValue), "type": parameter.ValueType,
                        "name": parameter.Definition.Name, "text": parameter.Definition.Text}
    return result


def _contour_points(s, curve):
    if curve.Curve2DType == s.r.Curve2DType_LineSegment:
        return [[curve.GetBeginPoint().X, curve.GetBeginPoint().Y], [curve.GetEndPoint().X, curve.GetEndPoint().Y]]
    try:
        poly = curve.GetInterfaceByName("IPolyCurve2D").QueryInterface(s.r.IPolyCurve2D)
    except Exception:
        return None  # Curved profile: retain parameter/region identity; do not approximate it as a polygon.
    points = [[poly.GetSegment(i).GetBeginPoint().X, poly.GetSegment(i).GetBeginPoint().Y] for i in range(poly.GetSegmentCount())]
    if points:
        last = poly.GetSegment(poly.GetSegmentCount() - 1).GetEndPoint()
        points.append([last.X, last.Y])
    return points


def _style_profile(s, kind, identifier):
    manager = getattr(s.project, kind + "Manager")
    style = getattr(manager, "Get" + kind)(identifier)
    profile = style.Profile
    regions = []
    for index in range(profile.Regions.Count):
        region = profile.Regions.Get(index)
        regions.append({"contour_count": region.GetContourCount(),
                        "outer_points_mm": _contour_points(s, region.GetOuterContour())})
    return {"description_id": profile.DescriptionId, "parameters": _container_parameters(profile.Parameters), "regions": regions}


def inspect_resources(s, collections=None):
    """Read actual resource parameters/layers/profile contours; no authoring."""
    names = list(RESOURCE_COLLECTIONS) if collections is None else collections
    if not isinstance(names, (list, tuple)) or any(name not in RESOURCE_COLLECTIONS for name in names):
        raise ValueError("Unsupported resource collection")
    result = {}
    for collection_name in names:
        collection = getattr(s.project, collection_name)
        entries = []
        for index in range(collection.Count):
            entity = collection.GetByIndex(index)
            row = {"id": entity.Id, "uuid": str(uuid.UUID(entity.UniqueIdS.strip("{}"))), "name": entity.Name,
                   "parameters": parameters(s, entity)}
            if collection_name in {"BeamStyles", "ColumnStyles"}:
                row["profile"] = _style_profile(s, collection_name[:-1], entity.Id)
            elif collection_name in {"DoorStyles", "WindowStyles"}:
                row["panel_layout_verified"] = False
                row["definition_scope"] = "exposed_style_parameters_only_no_public_panel_tree"
            elif collection_name == "Materials":
                packed = row["parameters"].get("Color", {}).get("value")
                if packed is not None:
                    row["color_rgba"] = color_from_native_int(packed)
            elif collection_name == "LayeredMaterials":
                material = s.project.LayeredMaterialManager.GetLayeredMaterial(entity.Id)
                row["base_layer_index"] = material.BaseLayerIndex
                row["layers"] = []
                for layer_index in range(material.Layers.Count):
                    layer = material.Layers.Get(layer_index)
                    ordinary = layer.Material
                    color = ordinary.Color
                    row["layers"].append({"index": layer_index, "id": layer.Id,
                        "is_base": layer_index == material.BaseLayerIndex, "thickness_mm": layer.Thickness,
                        "material_id": ordinary.Id, "material_name": ordinary.Name,
                        "material_color_rgba": [color.Red, color.Green, color.Blue, color.Alpha]})
            entries.append(row)
        result[collection_name] = {"entries": entries}
    return result


@contextmanager
def _resource_operation(s):
    # SDK resource creation uses project operations. Model undo does not promise
    # resource rollback; disk backup + discard/close protects failed runs.
    operation = s.project.CreateOperation()
    operation.Start()
    try:
        yield
        operation.Apply()
    except Exception:
        operation.Rollback()
        raise


def _model_uuids(s):
    objects = s.model.GetObjects()
    return {str(uuid.UUID(objects.GetByIndex(i).UniqueIdS.strip("{}"))) for i in range(objects.Count)}


def _preflight_material_references(s,specifications):
    """All explicit references must exist before any resource is created."""
    for spec in specifications:
        if spec["kind"] not in FILLING_PARAMETERS:continue
        identifier=spec.get("parameters",{}).get("MaterialId")
        if identifier is not None and not s.project.Materials.Contains(identifier):
            raise ValueError("Inspected MaterialId is absent from this project's ordinary Materials")


def _read_requested(s, created):
    result = []
    for spec, uid, expected_parameters in created:
        collection_name = AUTHOR_COLLECTIONS[spec["kind"]]
        entity = getattr(s.project, collection_name).GetByUniqueIdS(uid)
        if not entity:
            raise RuntimeError("Created native resource absent after commit/reopen")
        if entity.TypeIdS.upper() != s.sdk.types[spec["kind"]] or entity.Name != spec["name"]:
            raise RuntimeError("Saved native resource name/type differs from requested")
        container = entity.QueryInterface(s.r.IParameterContainer)
        for name, expected in expected_parameters.items():
            guid = s.sdk.parameters.get(name, name)
            actual = parameter_value(container.GetS(guid))
            if isinstance(expected, float):
                matches = isinstance(actual, (int, float)) and math.isclose(actual, expected, rel_tol=0, abs_tol=1e-6)
            else:
                matches = actual == expected
            if not matches:
                raise RuntimeError("Saved resource parameter mismatch: " + name)
        row = {"kind": spec["kind"], "name": entity.Name, "id": entity.Id,
               "uuid": str(uuid.UUID(entity.UniqueIdS.strip("{}"))), "parameters": parameters(s, entity)}
        if spec["kind"] in {"BeamStyle", "ColumnStyle"}:
            row["profile"] = _style_profile(s, spec["kind"], entity.Id)
        elif spec["kind"] == "ElementStyle":
            for key,expected in zip(("ElementWidth","ElementDepth","ElementHeight"),spec["expected_dimensions_mm"]):
                actual=row["parameters"].get(key,{}).get("value")
                if isinstance(actual,bool) or not isinstance(actual,(int,float)) or not math.isclose(actual,expected,rel_tol=1e-6,abs_tol=1e-3):
                    raise RuntimeError("Imported ElementStyle dimension mismatch: "+key+"; possible default-model fallback")
            row["geometry_verification"] = probe_element_style(s, entity.Id, spec)
            row["definition_scope"] = "imported_STEP_geometry_not_native_parametric_source_control_tree"
        elif spec["kind"] in FILLING_PARAMETERS:
            row["native_definition"] = {key: {field: value[field] for field in ("value", "has_value", "type")}
                                        for key, value in row["parameters"].items()}
            row["panel_layout_verified"] = False
            row["definition_scope"] = "exposed_style_parameters_only_no_public_panel_tree"
        if "ref" in spec:
            row["ref"] = spec["ref"]
        result.append(row)
    return result


def author_resources(project, specifications):
    """Create only new supported resources, back up, save, reopen and verify."""
    specs = validate_resource_specs(specifications)
    element_specs=[spec for spec in specs if spec["kind"]=="ElementStyle"]
    for spec in element_specs:verify_step_source(spec)
    target = checked_path(project, write=True)
    if target.suffix.lower() != ".rnp":
        raise ValueError("Resource authoring requires an existing native .rnp project")
    plan = save_plan({"action": "author_resources", "project": str(target), "resources": specs, "unit": "mm"})
    created = []
    with Session(target, write=True) as s:
        before_model = _model_uuids(s)
        _preflight_material_references(s,specs)
        # Preflight every name before mutating any resource collection.
        for spec in specs:
            collection = getattr(s.project, AUTHOR_COLLECTIONS[spec["kind"]])
            if any(collection.GetByIndex(i).Name.casefold() == spec["name"].casefold() for i in range(collection.Count)):
                raise ValueError("Resource name already exists; inspect/reuse it or request a distinct new name: " + spec["name"])
        for spec in specs:
            collection = getattr(s.project, AUTHOR_COLLECTIONS[spec["kind"]])
            with _resource_operation(s):
                args = collection.CreateNewEntityArgs()
                args.TypeIdS = s.sdk.types[spec["kind"]]
                if spec["kind"] == "ElementStyle":
                    verify_step_source(spec)
                    args.FilePath = spec["file_path"]
                entity = collection.Create(args)
                if not entity:
                    raise RuntimeError("Native resource factory returned no entity")
            expected = {"EntityName": spec["name"]}
            if spec["kind"] == "ElementStyle":
                with _resource_operation(s):set_parameter(s, entity, "EntityName", spec["name"])
                verify_step_source(spec)
            elif spec["kind"] == "Material":
                if "color_rgba" in spec:
                    expected["Color"] = color_to_native_int(spec["color_rgba"])
                for field, parameter in (("density_kg_m3", "MassDensity"), ("thermal_conductivity_w_m_k", "ThermalConductivity")):
                    if field in spec:
                        expected[parameter] = spec[field]
                with _resource_operation(s):
                    for key, value in expected.items():
                        set_parameter(s, entity, key, value)
            elif spec["kind"] in FILLING_PARAMETERS:
                expected.update(spec["parameters"])
                with _resource_operation(s):
                    for key, value in expected.items():
                        set_parameter(s, entity, key, value)
            else:
                profile_ids = s.sdk.read_guids("ProfileIds")
                rectangle = s.project.Profiles.GetByUniqueIdS(profile_ids["RectangleProfileId"])
                if not rectangle:
                    raise RuntimeError("Installed project has no native Rectangle profile description")
                expected["ProfileId"] = rectangle.Id
                with _resource_operation(s):
                    for key, value in expected.items():
                        set_parameter(s, entity, key, value)
                dimensions = _rectangle_guids(s)
                expected[dimensions["Width"]] = spec["profile"]["width_mm"]
                expected[dimensions["Height"]] = spec["profile"]["height_mm"]
                with _resource_operation(s):
                    set_parameter(s, entity, dimensions["Width"], spec["profile"]["width_mm"])
                    set_parameter(s, entity, dimensions["Height"], spec["profile"]["height_mm"])
            uid = str(uuid.UUID(entity.UniqueIdS.strip("{}")))
            created.append((spec, uid, expected))
            event("resource_create_requested", uuid=uid, kind=spec["kind"], name=spec["name"], status="provisional", plan=plan)
        committed = _read_requested(s, created)
        if _model_uuids(s) != before_model:
            raise RuntimeError("Model identities changed during resource authoring")
        s.save()
    saved_project_sha=fingerprint(target)
    # Imported-style geometry is probed again through a disposable Element.
    # A write Session provides the normal backup/transaction gate; no probe edit
    # is saved, and the persisted project hash must remain unchanged.
    with Session(target,write=True) if element_specs else Session(target) as reopened:
        actual = _read_requested(reopened, created)
        committed_by_uuid = {row["uuid"]: row for row in committed}
        for row in actual:
            if row["kind"] in FILLING_PARAMETERS and row["native_definition"] != committed_by_uuid[row["uuid"]]["native_definition"]:
                raise RuntimeError("Native filling-style exposed definition changed after reopen")
        if _model_uuids(reopened) != before_model:
            raise RuntimeError("Model identities changed after resource save/reopen")
        if fingerprint(target)!=saved_project_sha:raise RuntimeError("Saved resource project changed during unsaved geometry verification")
        for spec in element_specs:verify_step_source(spec)
        event("native_resources_reopened_verified", path=str(target), plan=plan, resources=actual, computer_use_calls=0)
        return {"status": "saved_reopened_verified", "created": actual, "plan": plan, "computer_use_calls": 0,
                "scope": "ordinary_materials_native_rectangle_styles_default_filling_parameters_and_verified_STEP_elements"}
