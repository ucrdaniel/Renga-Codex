# Axes, dimensions and markers: API-only investigation

Research date: 2026-10-15. Scope: locally installed SDK API 2.50 and current official online API 2.50 documentation. This source investigation performs no COM activation, Computer Use, UI Automation, keyboard input or modification of a user project. Native probe results must be recorded separately; a proposed probe below is not a successful operation.

## Constructor boundary

The official creation entry point is:

```text
IModel.CreateNewEntityArgs(out INewEntityArgs**)
IModel.CreateObject(INewEntityArgs*, out IModelObject**)
```

For a sheet, obtain `IModel` as an additional interface of its `IEntity`. `IDrawing` itself has **no** `CreateObject` method. `INewEntityArgs` exposes TypeId/TypeIdS, HostObjectId, StyleId, CategoryId, FilePath, Placement2D and Placement3D. No dimension endpoint pair, defining-feature reference, tagged-object reference or tag text-expression binding appears in that interface. The documented supported-type matrix omits Axis, DrawingAxis, LinearDimension and Tag in every model scope. A public type identifier supports identification; it does not establish creation support. [IModel](https://help.rengabim.com/api/interface_i_model.html), [INewEntityArgs](https://help.rengabim.com/api/interface_i_new_entity_args.html), [IDrawing](https://help.rengabim.com/api/interface_i_drawing.html).

The local official sample `Samples/C#/ObjectCreation/ObjectCreationPlugin.cs`, method `AllowedToCreateObjectTypes()`, agrees with that documented boundary. It excludes all four annotation types. Its plugin still calls the same `model.CreateObject(args)` inside an undo operation. The C++ `IPlugin.h` supplies startup/shutdown hooks, not a second modelling factory. Switching the bridge to C# or loading a plugin does not by itself create another documented annotation API. This is a source-based conclusion, not a test of every possible in-process runtime behavior.

The SDK changelog for API 2.46 (Renga 8.12) explicitly describes the addition of drawing-type identifiers and Tag together with **reading and editing common parameters**. It does not announce creation of those annotations. [Changelog](https://help.rengabim.com/api/_changelog.html).

## Individual operations

| Requested result | Evidence and boundary |
|---|---|
| New model Axis | Direct CreateObject is absent from the supported matrix. Existing axes expose GridLineName and GridLineExtension. **A native IFC import probe subsequently produced six genuine Axis objects and preserved their identities after save/reopen.** This establishes an alternative new-project import route; it does not establish direct creation in an existing model. |
| New DrawingAxis | Declared drawing type. Generic parameters expose no axis name/geometry binding. Query the drawing's IModel for a negative/positive constructor probe; do not call a nonexistent IDrawing factory. |
| New LinearDimension | Declared type with DimensionValue, DimensionValueType, DimensionTextStyleId and DimensionLandingLineOrientation. No public endpoint/feature-binding setter or ILinearDimension/IDimension interface found. A zero/default unbound object or mode-2 numeric string is insufficient. |
| New standalone Tag | Declared type and TagStyle identifier. No TagStyles collection on IProject, tag-target setter, expression setter or documented CreateObject support found. Setting HostObjectId to a room or supplying a style is a test hypothesis, not a documented association contract. |
| Intrinsic room marker | **Implemented and natively tested:** `IRoom.MarkerPosition` is a Point2D get/set property in global coordinates. It moves the room's own marker, not a standalone Tag. The Automatic-only restriction applies to ControlPoint, not MarkerPosition. A native test persisted [2345,1678] mm and confirmed it through an independent reopen/read. |

Sources: [Entity types](https://help.rengabim.com/api/group___entity_types.html), [entity-to-parameter table](https://help.rengabim.com/api/group___entity_type_by_parameters.html), [IRoom](https://help.rengabim.com/api/interface_i_room.html).

For existing native computed dimensions, mode 1 denotes a computed dimension and mode 2 denotes a text override. Read `DimensionValue` through its native parameter getter and preserve locale/display precision. No independent full-precision endpoint interpretation is warranted. See [DIMENSION_API_RESEARCH.md](DIMENSION_API_RESEARCH.md).

## Other SDK routes examined

* `IEntityCollection.Create(INewEntityArgs*)` creates project resources. Its documented supported list has no Axis, Tag or TagStyle collection; it is not a general model-object fallback. [IEntityCollection](https://help.rengabim.com/api/interface_i_entity_collection.html).
* `IBaseline2DObject.SetBaseline(ICurve2D*)` and `SetBaselineInCS(Placement2D, ICurve2D*)` edit an object that actually exposes this interface. They neither create an object nor attach dimension defining features. Their presence does not prove an axis supports them. Native probes must query the resulting object's actual interface and check its saved baseline.
* `IUI.CreateAction()` creates a plugin-defined action/event handler. No documented built-in command dispatcher accepting annotation points was found. Mouse/keyboard command injection is excluded from this project.
* `IApplication.CreateProjectFromTemplate(BSTR, out int)` can preserve preauthored native content in a new project. That is template reuse, not creation of arbitrary new axes/dimension associations/tags. Template provenance, model identities and dimensions must be checked after opening. SDK/vendor templates must not be redistributed without suitable rights. [IApplication](https://help.rengabim.com/api/interface_i_application.html).
* `IApplication.ImportIfcProject(BSTR, out int)` creates a project from IFC. Mapping IfcGrid or IfcAnnotation into native Renga Axis/LinearDimension/Tag is **not established** by the method signature. A genuine reference/linked imported drawing containing annotation graphics also does not establish native editable Renga dimensions.
* No documented generic CopyObject/CloneObject/Paste model method was found. File copy/SaveAs preserves existing content but is not per-annotation creation or retargeting.

## Bounded native probe plan

All probes belong in a fresh synthetic project inside the configured test write root, use the owned STA lifecycle, save the JSON request, and preserve failed/provisional calls in the local audit log. Never attach to the user's running session or derive fixtures from private homework models.

1. Inspect a fresh building model, its default level and any project resources. Create one synthetic wall, floor and manual room through already verified operations.
2. Test `Room.MarkerPosition = Point2D(x,y)` inside an undo transaction. Apply, read it, save, close, reopen and resolve the same room UniqueId. Verify the exact point, unchanged room area and contour. A second distinct point establishes that the setter is not merely returning its original default. Native screenshot export may corroborate appearance without Computer Use.
3. In separate disposable trials, attempt Axis, LinearDimension and Tag in the building model with explicit placement and, where relevant, an inspected level/wall/room host. Test DrawingAxis, LinearDimension and Tag in an actual drawing model. Record null returns, HRESULT and actual native type. Do not infer success from `LastError` alone, and roll back/discard failures.
4. If an object is returned, query its actual additional interfaces and parameters after Apply. An Axis must have nonzero checked baseline and name; a dimension must have two supported defining references, mode 1 and the independently expected computed value; a Tag must display the requested host-derived property and update when that synthetic host changes. Verify UUID, values and binding after reopen. Without these checks, mark the result provisional, not supported.
5. No private binary patch, hard-coded undocumented feature number, text/line facsimile or inherited preauthored object count may be presented as newly created associative annotation.

## Current interpretation

API 2.50 offers a specific route to moving **intrinsic room markers** and to reading/editing supported parameters of existing annotations. The reviewed public SDK does not establish a direct CreateObject constructor and binding contract for new Axis, DrawingAxis, computed LinearDimension or standalone Tag. **IFC import has now demonstrated an alternative creation route for native model Axis in a new project.** This distinction is essential: direct construction remains limited, while new-project bootstrap can create genuine axes through a supported importer.

## IFC grid import experiment

`scripts/generate_grid_fixture.py` augments the project's own synthetic storey fixture with one IFC4 rectangular grid. U curves lie at Y=0/3000/6000 mm (A/B/C); V curves lie at X=0/3000/6000 mm (1/2/3). Every line extends from -1000 to 7000 mm along its other coordinate. The fixture supplies a local placement relative to the zero storey, containment in that storey and a FootPrint/GeometricCurveSet representation sharing the grid-axis curves.

The official IFC4 signature has eleven explicit attributes for IfcGrid (seven inherited and four grid-specific); IfcGridAxis has AxisTag, AxisCurve and SameSense. Axis curves must be two-dimensional and each axis must occur in exactly one grid-axis list. These rules were checked against the primary specifications. [IfcGrid](https://standards.buildingsmart.org/IFC/RELEASE/IFC4/ADD2_TC1/HTML/schema/ifcproductextension/lexical/ifcgrid.htm), [IfcGridAxis](https://standards.buildingsmart.org/IFC/RELEASE/IFC4/ADD2_TC1/HTML/schema/ifcgeometricconstraintresource/lexical/ifcgridaxis.htm).

The generator has no additional dependencies or COM calls, refuses overwrites and restricts output to the workspace's bridge-e2e test root. It is a deliberately narrow synthetic generator, not a general STEP parser/exporter. Specification review is not a full external schema-validation claim.

The root agent's 2026-10-15 owned native import probe on Renga 9.3.32980.0 imported this fixture and saved/reopened the resulting `.rnp`. The resulting object inventory contains six actual `Axis` objects with names A/B/C/1/2/3 and the SDK Axis type identifier, alongside three native levels at 0/3000/6000 mm. All saved object identities persisted. Imported synthetic walls were exposed separately as `UndefinedObject`; their existence is not counted as native wall creation.

The native Axis objects did not expose `IBaseline2DObject` or `IBaseline3DObject` in the root's QI probe. A subsequent fresh native IFC export, performed after reopening, did preserve all six grid coordinates as `IfcGridAxis` objects and two-point `IfcIndexedPolyCurve` curves. This provides a different verification channel: read native identities/types/names through COM, then independently compare the requested coordinates with the new native export. It is explicitly **not** a direct Axis geometry getter.

`src/renga_codex_bridge/ifc_grid_verify.py` implements that narrow exported-grid check. It resolves identity-orientation local-placement translation chains, checks the project's assigned SI millimetre length unit, decodes STEP X2/X4 Unicode and doubled apostrophes, and compares the complete axis-name set and global endpoints within 0.000001 mm. Unsupported curves, rotation/scaling, ambiguous units or missing/extra axes fail. The reader cannot establish an export's provenance itself; the native caller must export the saved and reopened `.rnp`. It is not a general IFC schema validator or import-semantic validator for other BIM types.

## Production-path native tests

The public harness [run_level_annotation_tests.py](../scripts/run_level_annotation_tests.py) completed eleven native scenarios on Renga 9.3.32980.0 with zero Computer Use calls. Its new-project bootstrap produced clean native Levels at 0/3000/6000 mm and five native Axis objects with Cyrillic labels and 3000/6000 mm spacing. Exported coordinates were checked after reopening; disposable IFC slab carriers were removed before saving. A new genuine Wall hosted on the +3000 mm level had a mesh bottom of 3000 mm and top of 5800 mm. Axis-name editing was reflected in a subsequent native IFC export.

The same harness persisted the intrinsic room marker at global XY [2345,1678] mm, independently reopened and read that point, and rejected applying the operation to a Wall without changing the source file. These checks establish marker placement and native Room identity; they do not create a standalone Tag or inspect a tag-to-host association.

Finally, direct native CreateObject trials for Axis, DrawingAxis, LinearDimension, Tag and DrawingElevationMark in **both** building and drawing IModel contexts returned null in all ten trials. This strengthens the tested direct-factory limitation for this version and these argument sets; it does not imply the newly successful IFC grid bootstrap is unavailable. General associative-dimension and standalone-Tag creation remains unsupported, and no text/line substitutes are reported as those native objects.
