# Resource authoring: API 2.50 boundaries

The own [resources.py](../src/renga_codex_bridge/resources.py) adapter uses
ordinary project resource collections and typed parameter containers. It never
executes SDK samples, bundles vendor code/constants, edits an existing resource
in place, or creates substitute layers/objects that only look like the requested
resource. Native tests are required before promoting a new operation to tested
support. Pure validation tests are not native evidence.

`author_resources(project, specifications)` accepts new ordinary Material,
rectangular BeamStyle/ColumnStyle and default native DoorStyle/WindowStyle
specifications. The
[example plan](../examples/resources.json) contains an explicit material and
300×400 mm beam / 300×300 mm column styles. A rectangular style selects the project's
existing native Rectangle profile description; its width/height belong to that
style's profile parameter values, not to a newly authored custom contour.

The SDK sample `AssemblyInstanceCreation/StyleCreation.cpp` demonstrates the
public sequence: create a style in its collection, apply, query
`IParameterContainer`, choose an existing profile through `ProfileId`, then set
its documented shape parameters and name. The new adapter is independently
written and uses separate applied stages followed by save/close/reopen checks.
It reads the locally supplied `ProfileIds.h` and the **RectangleParameters
namespace** of `ProfileParameters.h` at runtime. The namespace boundary matters:
different shapes reuse the symbol `Width` with different GUIDs.
[IEntityCollection](https://help.rengabim.com/api/interface_i_entity_collection.html),
[IProfile](https://help.rengabim.com/api/interface_i_profile.html),
[parameter storage](https://help.rengabim.com/api/group___parameter_types_and_value_types.html).

Ordinary Material supports EntityName, Color, MassDensity and
ThermalConductivity parameters. Names and any requested color/density/conductivity
are checked after reopening the same native resource UUID. RGBA bytes are
converted to the SDK Color parameter's signed 32-bit AARRGGBB representation
using an independently implemented byte conversion. Creating a plain color is
not creation of a texture, a hatch pattern or a tile grid.
[Material parameter map](https://help.rengabim.com/api/group___entity_type_by_parameters.html),
[Color conversion contract](https://help.rengabim.com/api/group___parameters.html).

Resource edits use a project operation. Model undo does not guarantee rollback
of project resources: the existing-file backup and disposal of unsaved changes
remain the recovery boundary. A name collision is rejected before authoring;
existing IDs/styles must be inspected and reused explicitly. No blanket edit
or overwrite bypass is exposed.

Explicit filling `MaterialId` references must be positive native int32 IDs
present in this project's ordinary Materials collection; they are checked
before creating any resources. Omit the parameter to retain the native default
rather than guessing an undocumented unset sentinel. Resources are saved before
final reopen assertions. A failure after that save can leave the edited file
on disk; the verified backup remains available, and restoration is a manual
recovery step followed by fresh inspection, not an automatic rollback promise.

The `inspect_resources(s)` reader adds actual parameter values, complete
available layer order/base index/material IDs/thicknesses, and beam/column
profile parameters and polygon contours. A curved contour is identified as
unavailable through the polygon reader rather than flattened into a fabricated
polygon. A base layer's stored thickness is not automatically the thickness
realized on every wall or floor; actual object thickness still needs checking.

## Default door/window styles and exposed parameters

The documented DoorStyles/WindowStyles collection factories are implemented.
Create/apply the actual native style, set EntityName and any explicitly requested
supported primitive parameters, then save/close/reopen and check persistent UUID,
type, name, every requested value and the complete **exposed parameter** definition.
`IsReadOnly` and native value types remain authoritative; a native rejection is
not suppressed. Existing names are refused rather than silently edited.

DoorStyle parameters include MaterialId, Casing/CasingDepth/CasingWidth,
DoorLiningDepth/Thickness, Lining, MullionThickness, PanelDepth/Offset, Threshold,
ThresholdThickness, TransomConstruction and TransomHeight. WindowStyle parameters
include MaterialId, FrameDepth/Thickness, HorizontalMullionThickness,
VerticalMullionThickness and WindowLiningDepth/Thickness. These names come from
the official entity-to-parameter map; no guessed Glazing, PanelCount,
OpeningType or panel-tree setter is accepted. A material reference must be an
ID actually inspected in that project. The native parameter's primitive type is
checked during setting and its requested value is checked after reopening.

Neither `IDoorStyle` nor `IWindowStyle` or a public panel-tree interface appears
in this SDK. Therefore a saved style and its named parameters do not establish
a particular number or layout of leaves, panes, mullions or opening modes.
Returned inspection records explicitly contain `panel_layout_verified=false`.
To establish a complete filling instead of an aperture, create an actual native
Door/Window instance with the nonzero style ID and inspect its saved mesh and
available mesh-part types separately. A claimed single/double/triple-leaf layout
requires stronger native evidence; default factory success does not prove it.
[Collection creation](https://help.rengabim.com/api/interface_i_entity_collection.html),
[style parameter map](https://help.rengabim.com/api/group___entity_type_by_parameters.html),
[instance window parameters](https://help.rengabim.com/api/interface_i_window_params.html),
[instance door parameters](https://help.rengabim.com/api/interface_i_door_params.html).

## Specific unsupported requests

| Request | Examined public contract / consequence |
|---|---|
| Create or edit a layered material | LayeredMaterials is absent from the documented collection creation list. `ILayeredMaterial` provides getters for Layers/BaseLayerIndex, while `IMaterialLayerCollection` only reads existing layers. No AddLayer, layer order, base-index or layer-thickness setter was found. The adapter rejects layer-stack authoring rather than creating multiple unrelated walls/floors and calling them a native layered material |
| Surface/section hatch, 600×600 tile grid or crosshatch scale/angle/color | These definitions are not exposed among the ordinary Material parameters above. A Hatch model object or material RGB color is a separate object/property and does not satisfy a native material hatch definition |
| Arbitrary custom profile contour, parapet or blind-area section | Profiles.Create is documented, but `IProfileDescription` exposes only ID/Name and its manager exposes lookup. No public contour/constraint setter was found. An empty created profile is not a usable authored section. The adapter uses existing Rectangle definitions and explicitly rejects arbitrary contours |
| Door/window panel, mullion and sash layout | Default native style creation and exposed parameter editing are implemented; a panel-tree/layout authoring contract is absent. Default factory geometry must not be labelled a custom requested assembly without native structure and saved-output checks |

[Layered material](https://help.rengabim.com/api/interface_i_layered_material.html),
[material layer](https://help.rengabim.com/api/interface_i_material_layer.html),
[layer collection](https://help.rengabim.com/api/interface_i_material_layer_collection.html),
[profile description](https://help.rengabim.com/api/interface_i_profile_description.html),
[profile manager](https://help.rengabim.com/api/interface_i_profile_description_manager.html).

An officially imported IFC may offer a distinct route to resource conversion.
That requires its own native experiment: successful import or an IfcMaterialLayerSet
record alone does not establish a native Renga layered material. Existing
authorized templates may already contain usable resources, but merely matching
their names does not verify actual layers, thicknesses or base-layer behavior.
