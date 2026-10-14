# Capabilities and verified boundaries

API research date: **2026-10-14**. Reference examined: **Renga API 2.50**,
including all 146 COM interface reference pages, the SDK constants, and the
plugin documentation. Historical machine: Windows x64, Renga Professional
**9.3.32980.0**. Current bridge architecture: Python, typed COM via `comtypes`,
local stdio MCP, a serialized fresh owned Renga session, and no GUI emulation.

This is a method-level coverage map, not a claim of complete BIM automation.
Discovery of a public member does not prove that every entity supports it.
Native modelling elements, reference/imported geometry, manual rooms,
automatic rooms and associative drawing annotations are different capabilities.

Кратко: мост использует официальный API; Computer Use, UI Automation и
эмуляция мыши/клавиатуры не являются обходным режимом. В таблицах отдельно
указаны проверенные операции, ещё не реализованные возможности и конкретные
ограничения. Результаты прежней работы не засчитываются как испытания нового
продукта. Неподдерживаемая операция должна возвращать явную причину, а не
создавать визуальную имитацию BIM-объекта.

## Meaning of status

| Status | Meaning |
|---|---|
| `IMPLEMENTED_AND_TESTED` | Current bridge code was exercised against real Renga, with the stated saved-state/export checks. Only the tested operation and conditions are covered |
| `SUPPORTED_NOT_IMPLEMENTED` | A documented public API path exists; this bridge has not implemented it. This is an implementation gap |
| `API_LIMITATION` | The specific requested setter, interface or supported operation is absent/read-only/restricted in the examined API. A different route may still be possible |
| `NOT_VERIFIED` | Implemented but not yet tested, or a plausible route exists but its semantics/persistence have not been demonstrated |
| `VERSION_DEPENDENT` | Availability or behavior depends on application/API edition/version, runtime, category or export format; discovery and a local test are required |

Every `IMPLEMENTED_AND_TESTED` claim must link to a **fresh** product test.
Historical identifiers H-COM, H-MCP and H-ARCH below are defined in
[PREVIOUS_WORK_ANALYSIS.md](PREVIOUS_WORK_ANALYSIS.md); they describe research
evidence only. Portable unit tests and mocked COM do not qualify as native
integration evidence.

## Current product evidence

At the research snapshot represented by this draft, the new adapter and tools
are being implemented and fresh product acceptance results have not yet been
recorded in this document. Therefore the current implementation rows below are
`NOT_VERIFIED`, even where the historical adapter succeeded. After real tests,
the release must update these rows from
`tests/evidence/windows-renga-9.3.json`, retaining each scenario's actual limits.
Raw models, owner logs and SDK files remain outside the public repository.

The acceptance target for the advertised coverage is **0 Computer Use calls**.
An official API call such as opening a view or rendering it through
`IScreenshotService` is not mouse/keyboard emulation. A visible Renga window is
not proof that Computer Use was required, and `Visible=False` is not proof that
Renga operates as a headless service.

## Projects, sessions and safety

Primary reference: [IApplication](https://help.rengabim.com/api/interface_i_application.html),
[IProject](https://help.rengabim.com/api/interface_i_project.html),
[IOperation](https://help.rengabim.com/api/interface_i_operation.html),
[IUndoStack](https://help.rengabim.com/api/interface_i_undo_stack.html).

| Operation | API route / bridge boundary | Current status | Evidence / remaining verification |
|---|---|---|---|
| Detect application, version and local COM/TLB | Registry/installation discovery; `ProductName`, `VersionS` | `NOT_VERIFIED` | H-ENV/H-MCP; new status tool needs fresh test |
| Connect without using a user session | New COM instance, HWND → verified owned PID, STA and serialization | `NOT_VERIFIED` | H-COM ownership checks; test with an unrelated Renga process present |
| Create project | `CreateProject` | `NOT_VERIFIED` | H-COM; new apply-plan fixture |
| Create from user-supplied template | `CreateProjectFromTemplate` | `SUPPORTED_NOT_IMPLEMENTED` | Template provenance, content and preserved identities require verification |
| Open, save, SaveAs, close and reopen | `OpenProject`, `Save`, `SaveAs`, `CloseProject`, `Quit` only owned session | `NOT_VERIFIED` | H-COM/H-MCP; new lifecycle readback |
| Copy native project safely | Validated destination, backup/hash where applicable, native open verification | `NOT_VERIFIED` | Byte copying alone does not prove reopenability |
| Read/edit project metadata | `ProjectInfo` public fields/properties; building/site data separately | `NOT_VERIFIED` | Fresh persisted field checks required |
| Read/edit building/site/postal information | `IBuildingInfo`, `ISiteInfo`, `IPostalAddress` | `SUPPORTED_NOT_IMPLEMENTED` | Public writable fields available; do not log confidential addresses automatically |
| Model transaction, commit and rollback | `CreateOperationWithUndo`, `Start`, `Apply`, `Rollback` | `NOT_VERIFIED` | H-COM rejected setter/unchanged disk hash; fresh rollback test needed |
| Undo/redo history | `GetUndoStack`, `HasUndo`, `Undo`, `HasRedo`, `Redo` | `SUPPORTED_NOT_IMPLEMENTED` | Model-specific history; not all project resources participate |
| Undo arbitrary style/material resource edits | Model undo does not cover project-based resources | `API_LIMITATION` | Always back up; do not advertise one transaction as complete project rollback |
| Structural plan validation | Bridge checks plan shape, finite coordinates, primitive types and units; path/native checks also run at execution | `NOT_VERIFIED` | No native model change; not a solver preview of joins, valid styles or regenerated geometry |
| Native transaction preview | Apply the complete requested native operation, inspect, then roll back without saving | `SUPPORTED_NOT_IMPLEMENTED` | Distinct from structural validation; requires rollback and unchanged-file proof |
| Backup and authorized existing-file edits | Bridge file policy, hash-checked backup, no blanket MCP bypass | `NOT_VERIFIED` | Fresh overwrite/root escape/backup tests required |
| Recover from COM hang or worker crash | Owned PID tracking, bounded worker/session lifetime | `NOT_VERIFIED` | Timeout tests must prove unrelated sessions remain alive |
| Large-model performance and long batch operations | Serialized worker, bounded protocol requests; underlying COM traversal/regeneration can still be expensive | `NOT_VERIFIED` | Small synthetic fixtures are not a throughput or memory benchmark |
| Collaboration publish/synchronize | `Publish`, `Synchronize`, collaboration settings/events | `NOT_VERIFIED` | Requires separately authorized server context; outside local release coverage |

## BIM object creation and editing

Creation uses [`INewEntityArgs`](https://help.rengabim.com/api/interface_i_new_entity_args.html)
and [`IModel`](https://help.rengabim.com/api/interface_i_model.html), supported
category parameters and additional typed interfaces. A GUID in the SDK is not
sufficient evidence of a complete usable constructor. Host/style IDs are
inspected in the opened project; persistent UUIDs identify targets after SaveAs.

The documented dependent-host rules matter: Door/Window require a Wall;
Opening requires a Floor or Roof; Hole supports faces of several structural
hosts. The placement X-axis determines the Door/Window outer side relative to
the host wall direction. A generic default axis is not sufficient evidence of
correct facing on every wall.

| Operation | API route / exact limitation | Current status | Historical or next evidence |
|---|---|---|---|
| Enumerate/find objects by type, UUID, mark and parameters | `GetObjects`, native `UniqueIdS`, parameter/property/quantity containers | `NOT_VERIFIED` | H-COM/H-ARCH; objects with null parameters must retain UUIDs |
| Create/delete generic supported model entities | `CreateObject`, `DeleteObjectByUniqueIdS`; category-specific validation | `NOT_VERIFIED` | H-COM/H-ARCH; only tested categories become release claims |
| Create default-elevation level and rename it | Level factory + writable level-name parameter | `NOT_VERIFIED` | H-COM created level at 0 mm |
| Set level elevation/origin directly | `ILevel.Elevation`/`Placement` and `IPlacement3D.Origin` are getters | `API_LIMITATION` | Old nonzero creation silently stayed zero; bridge rejects unsupported requests |
| Change level through nested `Placement.Move` | A placement method exists, but whether it updates the owning level is unproved | `NOT_VERIFIED` | Disposable transaction/save/reopen/elevation probe required |
| Use existing nonzero levels from a template/project | Read `ILevel`; set inspected level as creation host | `NOT_VERIFIED` | H-ARCH used existing levels; does not prove API creation of those levels |
| Create axes via public model factory | Axis is absent from `IModel.CreateObject`'s supported-type table | `API_LIMITATION` | Existing native axes remain inspectable; template/extension creation route is not verified |
| Edit existing axes / use template axes | Actual supported interfaces/parameters, independently verified grid | `NOT_VERIFIED` | H-ARCH preserved native axes; fresh general edit/readback required |
| Walls and partitions | Native Wall, `IBaseline2DObject`, writable height/thickness/offset/material parameters | `NOT_VERIFIED` | H-COM/H-ARCH; joins and dependent openings need separate checks |
| Floors/slabs and terraces | Native Floor, closed baseline, thickness/offset and existing layered material | `NOT_VERIFIED` | H-COM 24 m²; contour with holes is a separate capability |
| Floor openings | Native Opening with inspected host and contour/offset | `SUPPORTED_NOT_IMPLEMENTED` | H-ARCH; host cutting must be checked by actual mesh |
| Isolated/wall foundations and specialized structural entities | SDK entity types and applicable factories/parameters | `NOT_VERIFIED` | Factory and valid parameter semantics need category-specific native tests |
| Columns | Native Column, existing profile/style and writable parameters | `NOT_VERIFIED` | H-ARCH; fresh profile and solid-size verification required |
| Beams | Native Beam, `IBaseline3DObject`, existing profile/style and offsets | `NOT_VERIFIED` | H-ARCH; global baseline differs from local baseline/joined mesh |
| Doors | Native Door hosted in Wall; style before creation, size/offset/orientation readback | `NOT_VERIFIED` | H-ARCH; style-zero aperture is not a complete door assembly |
| Window apertures | Native Window style-zero behavior depends on template | `NOT_VERIFIED` | H-COM aperture placement verified; fresh bridge test required |
| Complete styled windows | Valid inspected WindowStyleId/creation StyleId; native host and mesh | `NOT_VERIFIED` | H-ARCH proves past styles; new product must test its selected style |
| Move hosted Door/Window using generic level placement | Excluded by `ILevelObject.SetPlacement` | `API_LIMITATION` | Use tested category parameters or full native reconstruction, not this setter |
| Stairs and ramps | Native entity factory with documented writable category parameters | `SUPPORTED_NOT_IMPLEMENTED` | H-ARCH native stair; clearances, treads and openings need dedicated geometry checks |
| Roofs and canopies | Native Roof contour, height/offset, per-edge `IRoofSlopes` | `NOT_VERIFIED` | H-ARCH pitched roof; arbitrary contour/edge combinations remain unverified |
| Manual rooms / functional zones | Native Room and closed explicit contour | `NOT_VERIFIED` | H-COM/H-ARCH; report `Automatic=False` truthfully |
| Recalculate room region from a point | `IRoom.CalculateRegion`, outer and inner contours | `NOT_VERIFIED` | H-COM; old generic path rejected holes |
| New automatic room solely through API | No `Automatic` setter; creation semantics not established | `NOT_VERIFIED` | Historical automatic creation used GUI and is excluded from API-only claims |
| Move control point of an existing automatic room | `IRoom.ControlPoint` is writable | `SUPPORTED_NOT_IMPLEMENTED` | Must inspect `Automatic=True`, test boundary regeneration and reopen |
| Set room name/number/marker position | Writable parameters; `MarkerPosition` refers to model room marker | `NOT_VERIFIED` | Not equivalent to creating/binding a drawing room tag |
| Furniture/equipment native elements using existing styles | Element/equipment entity, StyleId/CategoryId, supported placement | `SUPPORTED_NOT_IMPLEMENTED` | H-ARCH; style content must be user-supplied/licensed or independently created |
| Import model geometry into an element style | Factory FilePath for supported geometry formats | `VERSION_DEPENDENT` | Import/license/format dependent; imported mesh is not a parametric wall/stair |
| Assemblies and instances | `IProject.Assemblies`, native collection/factories, additional `IModel` | `SUPPORTED_NOT_IMPLEMENTED` | Requires fixture and dependency/identity verification |
| Reinforcement | Styles/usages/placements/geometry exposed through reinforcement interfaces | `SUPPORTED_NOT_IMPLEMENTED` | Read/export is documented; arbitrary reinforcement authoring is not yet proven |
| Pipes, ducts, circuits and engineering connections | Routes, ports and `IEngineeringObjectConnector` connection factories | `SUPPORTED_NOT_IMPLEMENTED` | Must validate styles, source/target ports, systems and generated segments |
| Links/reference entities | Model/IFC/drawing/image links and `IObjectWithLink` | `SUPPORTED_NOT_IMPLEMENTED` | Linked data and editable native BIM are different outputs |
| Arbitrary category-specific factory | Unknown entity/category + generic arguments | `NOT_VERIFIED` | Unsupported categories must fail explicitly, not be represented by unrelated lines |

## Geometry and placement

Primary references: [IMath](https://help.rengabim.com/api/interface_i_math.html),
[IBaseline2DObject](https://help.rengabim.com/api/interface_i_baseline2_d_object.html),
[IBaseline3DObject](https://help.rengabim.com/api/interface_i_baseline3_d_object.html),
[ILevelObject](https://help.rengabim.com/api/interface_i_level_object.html),
[IPlacement3D](https://help.rengabim.com/api/interface_i_placement3_d.html).

| Operation | API route / constraints | Current status |
|---|---|---|
| Explicit coordinate creation | Typed `Placement2D`/`Placement3D` arguments and explicit host | `NOT_VERIFIED` |
| Read/change straight/composite 2D baselines | `GetBaseline`, `SetBaseline`, explicit local/global coordinate system | `NOT_VERIFIED` |
| Read/change straight/composite 3D baselines | `IBaseline3DObject`; global coordinates via `GetBaselineInCS` | `NOT_VERIFIED` |
| Create arcs, circles and mixed curved baselines | `IMath` curve factories; `IArc2D/IArc3D`, `IPolyCurve2D/3D` | `SUPPORTED_NOT_IMPLEMENTED` |
| Curve length, projections, trim, offset, transform | `ICurve2D/3D` documented math methods | `SUPPORTED_NOT_IMPLEMENTED` |
| Translate supported level objects | Obtain placement copy, `Move`, then `SetPlacement`; restricted types excluded | `NOT_VERIFIED` |
| Rotate supported objects | Placement `Rotate/Rotate2` or explicit transforms, then supported placement setter | `SUPPORTED_NOT_IMPLEMENTED` |
| Mirror/scale | Transform matrix members exist; accepted model semantics and handedness need tests | `NOT_VERIFIED` |
| Copy arbitrary native objects losslessly | No examined generic clone method; reconstruction may lose bindings/resources | `NOT_VERIFIED` |
| Reconstruct supported objects from inspected data | Native factory + complete supported styles/hosts/parameters, new UUID | `NOT_VERIFIED` |
| Set dimensions/heights/offsets | Writable typed parameters; save/reopen readback | `NOT_VERIFIED` |
| Read wall/floor/door/window contours and dependents | Category-specific parameter interfaces, `IWallContour`, `IHostObject` | `SUPPORTED_NOT_IMPLEMENTED` |
| Read mesh/triangle/material geometry | `IDataExporter.GetObjects3D`, meshes, grids, indices and materials | `NOT_VERIFIED` |
| Texture coordinates/normals/exported render materials | `IGrid`, `IGridMaterial`, `GetGrids` | `SUPPORTED_NOT_IMPLEMENTED` |
| Read model/object bounds | Native model bound or independently calculated mesh AABB | `NOT_VERIFIED` |
| Polygon area and room floor triangulation | Independent bridge calculation in explicit units | `NOT_VERIFIED` |
| Broad-phase collision candidates | Bounding-box overlap is a candidate, not an exact clash | `NOT_VERIFIED` |
| Exact general-purpose solid Boolean/clash engine | No public solid Boolean engine identified; triangle-level implementation needs validation | `NOT_VERIFIED` |
| Host cutting/joins and face contact validation | Actual native meshes + category/contact rules, not nominal baselines alone | `SUPPORTED_NOT_IMPLEMENTED` |
| Generic movement of objects with dependents | Restricted by `ILevelObject.SetPlacement` | `API_LIMITATION` |

Lengths/coordinates are millimeters. Read quantities with explicit conversions:
area in m², volume in m³ and mass in the selected mass unit. Roof slope angles
are degrees; math/placement rotation angles are radians. The bridge must not
apply one global angle convention to both. A manual plan polygon area, native
gross floor area and native net floor area are separately named measurements.

The `Placement3D` **record** used by creation arguments has assignable fields.
The `IPlacement3D` **interface** returned by an existing object has getter-only
`Origin`/axes and exposes `Move`, `Rotate` and `Transform` methods instead.
Changing a record or placement copy is not evidence that its owner changed;
use the supported object's placement setter and verify persistence. A level
does not expose that same setter.

## Parameters, properties, materials and styles

Primary references: [IParameter](https://help.rengabim.com/api/interface_i_parameter.html),
[IPropertyManager](https://help.rengabim.com/api/interface_i_property_manager.html),
[IProperty](https://help.rengabim.com/api/interface_i_property.html),
[IQuantity](https://help.rengabim.com/api/interface_i_quantity.html),
[IEntityCollection](https://help.rengabim.com/api/interface_i_entity_collection.html).

| Operation | API route / constraints | Current status |
|---|---|---|
| Enumerate parameter definitions, types, references, enum text | `IParameterContainer`, `IGuidCollection`, `IParameterDefinition`; actual GetIds, not only known SDK constants | `NOT_VERIFIED` |
| Read/write Bool/Int/Double/String parameters | Check `HasValue`, `ValueType`, `IsReadOnly` before typed setter | `NOT_VERIFIED` |
| Write a parameter while native IsReadOnly is true | Setter prohibited; newly created entities may need Apply before rechecking writability | `API_LIMITATION` |
| Read/write marks and applicable style/material IDs | Category parameters; validate referenced existing entity | `NOT_VERIFIED` |
| String custom-property registration/assignment/value | `IPropertyManager` + `IPropertyContainer/IProperty` | `NOT_VERIFIED` |
| Other custom types and explicit quantity units | Boolean/logical/integer/double/enum/length/area/volume/mass/angle property methods | `SUPPORTED_NOT_IMPLEMENTED` |
| Property enumeration definitions and expressions | Description manager methods, `SetExpressionS`, assignment and CSV flags | `SUPPORTED_NOT_IMPLEMENTED` |
| Reset/unassign/unregister properties | Public manager/property methods remove values; requires deliberate destructive plan | `SUPPORTED_NOT_IMPLEMENTED` |
| Read area/length/volume quantities and unset state | `IQuantityContainer`, `HasValue`, explicit typed conversion methods | `NOT_VERIFIED` |
| Read numeric mass/angle/count/signed-elevation quantities | Additional documented `IQuantity` typed methods | `SUPPORTED_NOT_IMPLEMENTED` |
| List resource/style/material catalogs | Project entity collections and typed managers | `NOT_VERIFIED` |
| Assign an existing material/layered material | Supported writable category parameter; read layers and thickness afterwards | `NOT_VERIFIED` |
| Read material color/density and layer stacks | `IMaterial`, `ILayeredMaterial`, `IMaterialLayer`, manager/collections | `SUPPORTED_NOT_IMPLEMENTED` |
| Edit material/layer stack via those typed interfaces | Color/density/layers/thickness are getter-only in the examined interfaces | `API_LIMITATION` |
| Create/edit resource through generic collection + supported parameters | `IEntityCollection.Create`; applicable entity interfaces/parameters | `NOT_VERIFIED` |
| Read/edit supported profile parameter values | `IProfile.Parameters`, style resource as model object where supported | `SUPPORTED_NOT_IMPLEMENTED` |
| Create arbitrary constrained profile description | No demonstrated public authoring of its geometry/constraints | `NOT_VERIFIED` |
| Import/update STDL category | `ImportCategoryS`, `UpdateCategory` | `SUPPORTED_NOT_IMPLEMENTED` |
| Clear/delete all arbitrary resources safely | Collection removal may invalidate dependent objects or terminate application | `NOT_VERIFIED` |

Collections expose create/remove methods, but do not guarantee that every
resource's internal definition is publicly writable. Model undo does not cover
all resource edits. Referenced-resource deletion therefore must not be exposed
as an unvalidated generic cleanup operation.

The SDK specifically notes that creating an ElementStyle with an unsupported
or failed 3D file can still return a style containing a **default model**.
Verify imported content and actual geometry; non-null creation is not evidence
of a successful model import.

## Documentation, views and annotations

Primary references: [IDrawing](https://help.rengabim.com/api/interface_i_drawing.html),
[IRectBoundedObject](https://help.rengabim.com/api/interface_i_rect_bounded_object.html),
[ITextObject](https://help.rengabim.com/api/interface_i_text_object.html),
[ITitleBlockInstance](https://help.rengabim.com/api/interface_i_title_block_instance.html),
[IScreenshotService](https://help.rengabim.com/api/interface_i_screenshot_service.html).

| Operation | API route / exact limitation | Current status | Required proof |
|---|---|---|---|
| List/open existing drawings and drawing model | `Drawings2`, additional `IDrawing/IModel`; legacy `Drawings` also exists | `NOT_VERIFIED` | New native drawing/UUID inspection |
| Create native drawing sheet | Drawing entity factory, page/layout/scale references and writable parameters | `NOT_VERIFIED` | Saved/reopened sheet and actual page settings |
| Embed native building/level view | EmbeddedModelView factory + source view/level parameters | `NOT_VERIFIED` | Saved referenced entity and visible building geometry |
| Set embedded bounds/content placement | `IRectBoundedObject.BoundRect`, `GetContentPlacement`, `SetContentPlacement`, `FitBoundsToContent` | `NOT_VERIFIED` | Fit only after source/scale changes Apply; HasContent alone does not prove useful clipping |
| Drawing text creation/edit | Native Text with `ITextObject.GetRichTextDocument`, tokens/paragraphs and bounds | `NOT_VERIFIED` | Text is native annotation; not a replacement for associative tags/dimensions |
| Drawing metadata/topic/page format/layout assignment | Supported drawing parameters and resource references | `NOT_VERIFIED` | Read saved assignments, validate actual export size |
| Read title-block cells | `IDrawing.GetTitleBlockInstance`, `GetCellValue` | `SUPPORTED_NOT_IMPLEMENTED` | Literal and generated fields must be distinguished |
| Set arbitrary title-block cell | No public `SetCellValue` in `ITitleBlockInstance` | `API_LIMITATION` | Use tested source-field binding or preconfigured user template |
| Read existing computed model linear dimensions | Native LinearDimension parameters `DimensionValueType=1` and `DimensionValue` | `NOT_VERIFIED` | Display value can be rounded/localized; distinct from a geometric binding getter |
| Create native model linear dimension through public factory | LinearDimension absent from supported `IModel.CreateObject` table; no public feature-binding constructor | `API_LIMITATION` | Bridge rejects creation before mutation; no line/text substitute; alternative routes unverified |
| Native drawing dimensions, axes/markers and associations | Some real native annotations inspect as UndefinedObject without parameters | `NOT_VERIFIED` | Preserve native type/UUID; no proven creation/binding/value route |
| Create native room tags through public model factory | Tag absent from supported constructor table; no dedicated public `ITag` binding interface found | `API_LIMITATION` | Existing tags and template routes need separate semantic binding/readback proof; text imitation is not accepted |
| Create/list schedule/table/filter entities | Project collections + generic factory | `NOT_VERIFIED` | Empty entity existence does not prove a functional schedule definition |
| Configure native schedule/table rows, columns, formula/filter | No public `ISchedule/ITable` definition/data interface found; tested schedule did not expose invented FilterId | `API_LIMITATION` | Narrow API 2.50 interface limitation; template route still needs proof |
| Embed configured existing schedule | EmbeddedSchedule; after creation Apply, assign ScheduleId in a new operation and fit content | `NOT_VERIFIED` | Fresh lifecycle discovery; saved reference/content/PDF QA still required; definition editing is separate |
| Embed configured existing table/legend | EmbeddedTable/Legend; rect/content placement interface | `SUPPORTED_NOT_IMPLEMENTED` | Must verify source ID/content; no promise of editing its definition |
| Independent room/apartment report | Read native quantities and group by explicit property mapping | `NOT_VERIFIED` | A computed JSON/CSV report is not a native schedule |
| Open native 3D/level/drawing view by entity | `IApplication.OpenViewByEntity` | `SUPPORTED_NOT_IMPLEMENTED` | Official API operation, no UI emulation needed |
| View visibility/visual style/active level | `IModelView` methods/properties | `SUPPORTED_NOT_IMPLEMENTED` | Distinguish building view, level view and drawing model |
| Native camera position/projection | `IView3DParams.Camera`, `LookAt`, `Projection` | `SUPPORTED_NOT_IMPLEMENTED` | No dependence on mouse-based orbit |
| Native view rendering to image | View additional `IScreenshotService` → `MakeScreenshot` → `IImage` | `SUPPORTED_NOT_IMPLEMENTED` | Real dimensions/file/content test; no invented Application.ScreenshotService |
| Selection | `ISelection` for supported active view types | `SUPPORTED_NOT_IMPLEMENTED` | Selection is not a general built-in modelling-command executor |
| Complete automated regulated drawing package | Requires tested native dimensions, bindings, schedule definitions and title-block fields | `NOT_VERIFIED` | No claim of fully autonomous architectural documentation |

`UndefinedObject` is not synonymous with junk. The historical drawing dimension
objects survived save/reopen and were native annotations. The public inspection
path did not return their measured values. Do not relabel them as model
LinearDimension or fabricate parameter values for completeness.

## Import/export

| Operation | Public API route | Current status | Acceptance boundary |
|---|---|---|---|
| Whole-project IFC export | `CreateIfcExportSettings`, `ExportToIfc2` | `NOT_VERIFIED` | H-COM wrote IFC4; fresh semantic parser validation needed |
| Selected-object IFC export | `ExportObjectsToIFC` | `SUPPORTED_NOT_IMPLEMENTED` | Check selected set and IFC class/geometry contents |
| IFC mappings/export settings | `IIfcExportSettings` type/parameter/layer files and flags | `SUPPORTED_NOT_IMPLEMENTED` | Mappings are user-supplied or separately licensed; test each flag |
| IFC schema versions | Native `IfcVersion` enumeration | `VERSION_DEPENDENT` | Match actual supported schema/version, do not infer from newest IFC specification |
| Import IFC as a new native project | `IApplication.ImportIfcProject` | `SUPPORTED_NOT_IMPLEMENTED` | Verify actual resulting native categories/editability |
| Link/reference IFC in current project | Applicable factory FilePath and IFC-link collections | `VERSION_DEPENDENT` | Not equivalent to native IFC project import |
| Single-sheet PDF | `IDrawing.ExportToPdf` | `NOT_VERIFIED` | Actual PDF page dimensions/content required |
| Multi-sheet single PDF | `IProject.ExportDrawingsToPdfS` | `NOT_VERIFIED` | Select explicit intended drawing UUIDs; tested template contains an extra blank sheet; final PDF QA required |
| DWG/DXF drawing export | `IDrawing.ExportToDwg2/ExportToDxf2`, export settings | `SUPPORTED_NOT_IMPLEMENTED` | Format/version dependent; valid native drawing input |
| OpenXPS export | Drawing/project methods | `SUPPORTED_NOT_IMPLEMENTED` | Actual page/content verification |
| Project data CSV | `IProject.ExportToCsv` produces multiple files in an output folder | `SUPPORTED_NOT_IMPLEMENTED` | Not an accessor for schedule cell contents |
| Image save/load and rendered images | `IImage.LoadFromFile/SaveToFile/SaveToData` | `SUPPORTED_NOT_IMPLEMENTED` | Resource/format and output-path checks |
| Model geometry JSON | Bridge converts meshes/grids to explicit object geometry | `NOT_VERIFIED` | Index bounds, finite vertices, units and UUID association |
| Arbitrary format unsupported by public exporter | No universal export-any-format method | `API_LIMITATION` | A new converter must be explicit; do not disguise geometry conversion as native export |

PDF export is an **implementation opportunity**, not a reason to automate a
print dialog. Official methods are described in
[IDrawing](https://help.rengabim.com/api/interface_i_drawing.html) and
[IProject](https://help.rengabim.com/api/interface_i_project.html).

## Verification and architectural planning

| Operation | Method / honest boundary | Current status |
|---|---|---|
| Saved UUID/object-count preservation | Direct native UUIDs before/save/reopen, resolve numeric IDs again | `NOT_VERIFIED` |
| Saved requested parameter/baseline preservation | Independent expected values + saved native readback | `NOT_VERIFIED` |
| Room/floor area against independent target | Explicit source polygon/dimensions and native bottom triangles | `NOT_VERIFIED` |
| Room height, support and roof clipping | Levels + support meshes + net/gross quantities/room mesh | `SUPPORTED_NOT_IMPLEMENTED` |
| Exact locations / bounding boxes / permitted placement | Baseline/global mesh bounds and explicit region tests | `NOT_VERIFIED` |
| Broad collision candidates | AABB overlap with stated limitations | `NOT_VERIFIED` |
| Detailed clearance/contact/clash checks | Category-aware triangle/face analysis | `SUPPORTED_NOT_IMPLEMENTED` |
| Stair clearances/treads and roof-wall contact | Specialized source/geometry validation | `SUPPORTED_NOT_IMPLEMENTED` |
| Native schedule/tag semantic linkage | Exposed data insufficient for a general verifier | `NOT_VERIFIED` |
| PDF page count/dimensions/text/content | Parse actual native export with independent PDF library; visual rendering when needed | `NOT_VERIFIED` |
| IFC semantic validation | Parse actual export, validate objects/schema/placements/geometry | `NOT_VERIFIED` |
| Rectangle/building plan generation | Deterministic geometry algorithm returns a reviewable operation plan | `NOT_VERIFIED` |
| Facade window/pier spacing | Deterministic dimensions/host plan with feasibility checks | `NOT_VERIFIED` |
| Floor/apartment grouping | Explicit custom-property/room UUID grouping, no inference from names alone | `SUPPORTED_NOT_IMPLEMENTED` |
| Arbitrary code compliance/architectural design guarantee | No such general API guarantee or implemented rule engine | `NOT_VERIFIED` |

## Extensibility and version boundary

Additional interfaces are queried on the objects that support them. There is
no API interface inheritance assumption; `E_NOINTERFACE` is a meaningful
capability result. Use declared typed members and `GetInterfaceByName` where
documented; never invent an `ISchedule`, `ITag` or setter because it would be
convenient. [Official general principles](https://help.rengabim.com/api/overview-general-principles.html).

| Extension | Status | Scope |
|---|---|---|
| C++/.NET plugin, including .NET 8 | `SUPPORTED_NOT_IMPLEMENTED` | Official in-process extension with `.rndesc`; no extra undocumented modelling APIs promised |
| Local IPC dispatcher in a plugin | `NOT_VERIFIED` | Possible response to external COM marshalling/threading issues; requires separate design and native tests |
| SDK events and close-prevention events | `SUPPORTED_NOT_IMPLEMENTED` | Lifecycle/visibility/selection/collaboration events have restrictions on mutating state in callbacks |
| Custom action/buttons/context-menu/panel extension | `SUPPORTED_NOT_IMPLEMENTED` | Supported extension UI, outside the default MCP-only product flow |
| Invoke arbitrary built-in commands via custom action | `NOT_VERIFIED` | `IAction.Trigger` triggers its associated extension action; not a general native-command dispatcher |
| STDL parametric categories | `SUPPORTED_NOT_IMPLEMENTED` | Applicable category/style template workflow; not a replacement for absent annotation bindings |
| Newer/older Renga, Standard edition, other API/runtime versions | `VERSION_DEPENDENT` | Must run discovery and disposable integration fixtures on each declared configuration |
| Vendor SDK/component redistribution | `VERSION_DEPENDENT` | Requires vendor terms; this repository distributes no SDK TLB/DLL/installers |

References: [API/SDK overview](https://help.rengabim.com/api/overview-api-sdk-plugin.html),
[plugin implementation](https://help.rengabim.com/api/how-to-implement-a-plugin.html),
[official SDK](https://rengabim.com/sdk/). Licensing and provenance are tracked
in [NOTICE.md](../NOTICE.md) and
[REPOSITORY_RESEARCH.md](REPOSITORY_RESEARCH.md).

## SDK interface inventory

The following inventory covers **all 146 COM interface reference pages** in
the examined API 2.50 SDK, including five event dispatch interfaces. The native
plugin interface `Renga::IPlugin` is documented separately above. The table lists
areas for discovery, not blanket tested interfaces: a release status always
belongs to the operation rows above. Unlisted members remain
`SUPPORTED_NOT_IMPLEMENTED` when a public method is documented; an actual
restriction, unknown native semantics or version dependency takes the more
specific status in the corresponding operation row. No vendor source or binary
is embedded in this inventory.

| Interface (official reference) | Discovery area |
|---|---|
| [`_IActionEvents`](https://help.rengabim.com/api/interface___i_action_events.html) | Events and callback restrictions |
| [`_IApplicationEvents`](https://help.rengabim.com/api/interface___i_application_events.html) | Events and callback restrictions |
| [`_IModelViewEvents`](https://help.rengabim.com/api/interface___i_model_view_events.html) | Events and callback restrictions |
| [`_IProjectCollaborationEvents`](https://help.rengabim.com/api/interface___i_project_collaboration_events.html) | Events and callback restrictions |
| [`_ISelectionEvents`](https://help.rengabim.com/api/interface___i_selection_events.html) | Events and callback restrictions |
| [`IAction`](https://help.rengabim.com/api/interface_i_action.html) | Extension actions and controls |
| [`IApplication`](https://help.rengabim.com/api/interface_i_application.html) | Projects and ownership |
| [`IApplicationCloseEvent`](https://help.rengabim.com/api/interface_i_application_close_event.html) | Events and callback restrictions |
| [`IArc2D`](https://help.rengabim.com/api/interface_i_arc2_d.html) | Baseline/placement/math |
| [`IArc3D`](https://help.rengabim.com/api/interface_i_arc3_d.html) | Baseline/placement/math |
| [`IBaseline2DObject`](https://help.rengabim.com/api/interface_i_baseline2_d_object.html) | Baseline/placement/math |
| [`IBaseline3DObject`](https://help.rengabim.com/api/interface_i_baseline3_d_object.html) | Baseline/placement/math |
| [`IBeamParams`](https://help.rengabim.com/api/interface_i_beam_params.html) | Columns, beams and profiles |
| [`IBeamStyle`](https://help.rengabim.com/api/interface_i_beam_style.html) | Columns, beams and profiles |
| [`IBeamStyleManager`](https://help.rengabim.com/api/interface_i_beam_style_manager.html) | Columns, beams and profiles |
| [`IBuildingInfo`](https://help.rengabim.com/api/interface_i_building_info.html) | Projects and ownership |
| [`ICamera3D`](https://help.rengabim.com/api/interface_i_camera3_d.html) | Views, selection and API rendering |
| [`ICollaborationSettings`](https://help.rengabim.com/api/interface_i_collaboration_settings.html) | Projects and ownership |
| [`IColumnParams`](https://help.rengabim.com/api/interface_i_column_params.html) | Columns, beams and profiles |
| [`IColumnStyle`](https://help.rengabim.com/api/interface_i_column_style.html) | Columns, beams and profiles |
| [`IColumnStyleManager`](https://help.rengabim.com/api/interface_i_column_style_manager.html) | Columns, beams and profiles |
| [`IContextMenu`](https://help.rengabim.com/api/interface_i_context_menu.html) | Extension actions and controls |
| [`IContextMenuItem`](https://help.rengabim.com/api/interface_i_context_menu_item.html) | Extension actions and controls |
| [`IContextMenuNodeItem`](https://help.rengabim.com/api/interface_i_context_menu_node_item.html) | Extension actions and controls |
| [`ICurve2D`](https://help.rengabim.com/api/interface_i_curve2_d.html) | Baseline/placement/math |
| [`ICurve2DCollection`](https://help.rengabim.com/api/interface_i_curve2_d_collection.html) | Baseline/placement/math |
| [`ICurve3D`](https://help.rengabim.com/api/interface_i_curve3_d.html) | Baseline/placement/math |
| [`IDataExporter`](https://help.rengabim.com/api/interface_i_data_exporter.html) | Render geometry |
| [`IDoorParams`](https://help.rengabim.com/api/interface_i_door_params.html) | Levels and native architectural geometry |
| [`IDrawing`](https://help.rengabim.com/api/interface_i_drawing.html) | Documentation and text |
| [`IDrawingCollection`](https://help.rengabim.com/api/interface_i_drawing_collection.html) | Documentation and text |
| [`IDropDownButton`](https://help.rengabim.com/api/interface_i_drop_down_button.html) | Extension actions and controls |
| [`IDuctSystemConnectionParameters`](https://help.rengabim.com/api/interface_i_duct_system_connection_parameters.html) | Engineering routes, ports and connections |
| [`IDwgDxfExportSettings`](https://help.rengabim.com/api/interface_i_dwg_dxf_export_settings.html) | Export/link configuration |
| [`IElectricalSystemConnectionParameters`](https://help.rengabim.com/api/interface_i_electrical_system_connection_parameters.html) | Engineering routes, ports and connections |
| [`IEngineeringObjectConnector`](https://help.rengabim.com/api/interface_i_engineering_object_connector.html) | Engineering routes, ports and connections |
| [`IEntity`](https://help.rengabim.com/api/interface_i_entity.html) | Entity/model lifecycle and identity |
| [`IEntityCollection`](https://help.rengabim.com/api/interface_i_entity_collection.html) | Entity/model lifecycle and identity |
| [`IEntityWithPorts`](https://help.rengabim.com/api/interface_i_entity_with_ports.html) | Engineering routes, ports and connections |
| [`IEquipmentStyle`](https://help.rengabim.com/api/interface_i_equipment_style.html) | Equipment and engineering styles |
| [`IEquipmentStyleManager`](https://help.rengabim.com/api/interface_i_equipment_style_manager.html) | Equipment and engineering styles |
| [`IEvent`](https://help.rengabim.com/api/interface_i_event.html) | Events and callback restrictions |
| [`IExportedObject3D`](https://help.rengabim.com/api/interface_i_exported_object3_d.html) | Render geometry |
| [`IExportedObject3DCollection`](https://help.rengabim.com/api/interface_i_exported_object3_d_collection.html) | Render geometry |
| [`IFloorParams`](https://help.rengabim.com/api/interface_i_floor_params.html) | Levels and native architectural geometry |
| [`IFlowSegmentPlacement`](https://help.rengabim.com/api/interface_i_flow_segment_placement.html) | Engineering routes, ports and connections |
| [`IGrid`](https://help.rengabim.com/api/interface_i_grid.html) | Render geometry |
| [`IGridMaterial`](https://help.rengabim.com/api/interface_i_grid_material.html) | Render geometry |
| [`IGridWithMaterial`](https://help.rengabim.com/api/interface_i_grid_with_material.html) | Render geometry |
| [`IGridWithMaterialCollection`](https://help.rengabim.com/api/interface_i_grid_with_material_collection.html) | Render geometry |
| [`IGuidCollection`](https://help.rengabim.com/api/interface_i_guid_collection.html) | Entity/model lifecycle and identity |
| [`IHostObject`](https://help.rengabim.com/api/interface_i_host_object.html) | Entity/model lifecycle and identity |
| [`IIfcExportSettings`](https://help.rengabim.com/api/interface_i_ifc_export_settings.html) | Export/link configuration |
| [`IImage`](https://help.rengabim.com/api/interface_i_image.html) | Views, selection and API rendering |
| [`ILayer`](https://help.rengabim.com/api/interface_i_layer.html) | Materials and layer quantities |
| [`ILayerCollection`](https://help.rengabim.com/api/interface_i_layer_collection.html) | Materials and layer quantities |
| [`ILayeredMaterial`](https://help.rengabim.com/api/interface_i_layered_material.html) | Materials and layer quantities |
| [`ILayeredMaterialManager`](https://help.rengabim.com/api/interface_i_layered_material_manager.html) | Materials and layer quantities |
| [`ILevel`](https://help.rengabim.com/api/interface_i_level.html) | Levels and native architectural geometry |
| [`ILevelObject`](https://help.rengabim.com/api/interface_i_level_object.html) | Levels and native architectural geometry |
| [`ILevelViewParams`](https://help.rengabim.com/api/interface_i_level_view_params.html) | Views, selection and API rendering |
| [`ILine3DParams`](https://help.rengabim.com/api/interface_i_line3_d_params.html) | Levels and native architectural geometry |
| [`IMaterial`](https://help.rengabim.com/api/interface_i_material.html) | Materials and layer quantities |
| [`IMaterialLayer`](https://help.rengabim.com/api/interface_i_material_layer.html) | Materials and layer quantities |
| [`IMaterialLayerCollection`](https://help.rengabim.com/api/interface_i_material_layer_collection.html) | Materials and layer quantities |
| [`IMaterialManager`](https://help.rengabim.com/api/interface_i_material_manager.html) | Materials and layer quantities |
| [`IMath`](https://help.rengabim.com/api/interface_i_math.html) | Baseline/placement/math |
| [`IMesh`](https://help.rengabim.com/api/interface_i_mesh.html) | Render geometry |
| [`IModel`](https://help.rengabim.com/api/interface_i_model.html) | Entity/model lifecycle and identity |
| [`IModelObject`](https://help.rengabim.com/api/interface_i_model_object.html) | Entity/model lifecycle and identity |
| [`IModelObjectCollection`](https://help.rengabim.com/api/interface_i_model_object_collection.html) | Entity/model lifecycle and identity |
| [`IModelView`](https://help.rengabim.com/api/interface_i_model_view.html) | Views, selection and API rendering |
| [`INewEntityArgs`](https://help.rengabim.com/api/interface_i_new_entity_args.html) | Entity/model lifecycle and identity |
| [`IObjectOnRoutePlacement`](https://help.rengabim.com/api/interface_i_object_on_route_placement.html) | Engineering routes, ports and connections |
| [`IObjectReinforcementModel`](https://help.rengabim.com/api/interface_i_object_reinforcement_model.html) | Reinforcement styles/usages/geometry |
| [`IObjectWithInsulation`](https://help.rengabim.com/api/interface_i_object_with_insulation.html) | Materials and layer quantities |
| [`IObjectWithLayeredMaterial`](https://help.rengabim.com/api/interface_i_object_with_layered_material.html) | Materials and layer quantities |
| [`IObjectWithLink`](https://help.rengabim.com/api/interface_i_object_with_link.html) | Export/link configuration |
| [`IObjectWithMark`](https://help.rengabim.com/api/interface_i_object_with_mark.html) | Parameters/properties/quantities |
| [`IObjectWithMaterial`](https://help.rengabim.com/api/interface_i_object_with_material.html) | Materials and layer quantities |
| [`IOpeningParams`](https://help.rengabim.com/api/interface_i_opening_params.html) | Levels and native architectural geometry |
| [`IOperation`](https://help.rengabim.com/api/interface_i_operation.html) | Transactions and undo |
| [`IParameter`](https://help.rengabim.com/api/interface_i_parameter.html) | Parameters/properties/quantities |
| [`IParameterContainer`](https://help.rengabim.com/api/interface_i_parameter_container.html) | Parameters/properties/quantities |
| [`IParameterDefinition`](https://help.rengabim.com/api/interface_i_parameter_definition.html) | Parameters/properties/quantities |
| [`IPipeSystemConnectionParameters`](https://help.rengabim.com/api/interface_i_pipe_system_connection_parameters.html) | Engineering routes, ports and connections |
| [`IPlacement2D`](https://help.rengabim.com/api/interface_i_placement2_d.html) | Baseline/placement/math |
| [`IPlacement2DObject`](https://help.rengabim.com/api/interface_i_placement2_d_object.html) | Baseline/placement/math |
| [`IPlacement3D`](https://help.rengabim.com/api/interface_i_placement3_d.html) | Baseline/placement/math |
| [`IPlacement3DCollection`](https://help.rengabim.com/api/interface_i_placement3_d_collection.html) | Baseline/placement/math |
| [`IPlumbingFixtureStyle`](https://help.rengabim.com/api/interface_i_plumbing_fixture_style.html) | Equipment and engineering styles |
| [`IPlumbingFixtureStyleManager`](https://help.rengabim.com/api/interface_i_plumbing_fixture_style_manager.html) | Equipment and engineering styles |
| [`IPolyCurve2D`](https://help.rengabim.com/api/interface_i_poly_curve2_d.html) | Baseline/placement/math |
| [`IPolyCurve3D`](https://help.rengabim.com/api/interface_i_poly_curve3_d.html) | Baseline/placement/math |
| [`IPort`](https://help.rengabim.com/api/interface_i_port.html) | Engineering routes, ports and connections |
| [`IPortDuctParams`](https://help.rengabim.com/api/interface_i_port_duct_params.html) | Engineering routes, ports and connections |
| [`IPortPipeParams`](https://help.rengabim.com/api/interface_i_port_pipe_params.html) | Engineering routes, ports and connections |
| [`IPostalAddress`](https://help.rengabim.com/api/interface_i_postal_address.html) | Projects and ownership |
| [`IProfile`](https://help.rengabim.com/api/interface_i_profile.html) | Columns, beams and profiles |
| [`IProfileDescription`](https://help.rengabim.com/api/interface_i_profile_description.html) | Columns, beams and profiles |
| [`IProfileDescriptionManager`](https://help.rengabim.com/api/interface_i_profile_description_manager.html) | Columns, beams and profiles |
| [`IProject`](https://help.rengabim.com/api/interface_i_project.html) | Projects and ownership |
| [`IProjectCloseEvent`](https://help.rengabim.com/api/interface_i_project_close_event.html) | Events and callback restrictions |
| [`IProjectInfo`](https://help.rengabim.com/api/interface_i_project_info.html) | Projects and ownership |
| [`IProperty`](https://help.rengabim.com/api/interface_i_property.html) | Parameters/properties/quantities |
| [`IPropertyContainer`](https://help.rengabim.com/api/interface_i_property_container.html) | Parameters/properties/quantities |
| [`IPropertyDescription`](https://help.rengabim.com/api/interface_i_property_description.html) | Parameters/properties/quantities |
| [`IPropertyManager`](https://help.rengabim.com/api/interface_i_property_manager.html) | Parameters/properties/quantities |
| [`IQuantity`](https://help.rengabim.com/api/interface_i_quantity.html) | Parameters/properties/quantities |
| [`IQuantityContainer`](https://help.rengabim.com/api/interface_i_quantity_container.html) | Parameters/properties/quantities |
| [`IRebarStyle`](https://help.rengabim.com/api/interface_i_rebar_style.html) | Reinforcement styles/usages/geometry |
| [`IRebarUsage`](https://help.rengabim.com/api/interface_i_rebar_usage.html) | Reinforcement styles/usages/geometry |
| [`IRebarUsageCollection`](https://help.rengabim.com/api/interface_i_rebar_usage_collection.html) | Reinforcement styles/usages/geometry |
| [`IRectBoundedObject`](https://help.rengabim.com/api/interface_i_rect_bounded_object.html) | Documentation and text |
| [`IRegion2D`](https://help.rengabim.com/api/interface_i_region2_d.html) | Baseline/placement/math |
| [`IRegion2DCollection`](https://help.rengabim.com/api/interface_i_region2_d_collection.html) | Baseline/placement/math |
| [`IReinforcementUnitStyle`](https://help.rengabim.com/api/interface_i_reinforcement_unit_style.html) | Reinforcement styles/usages/geometry |
| [`IReinforcementUnitStyleManager`](https://help.rengabim.com/api/interface_i_reinforcement_unit_style_manager.html) | Reinforcement styles/usages/geometry |
| [`IReinforcementUnitUsage`](https://help.rengabim.com/api/interface_i_reinforcement_unit_usage.html) | Reinforcement styles/usages/geometry |
| [`IReinforcementUnitUsageCollection`](https://help.rengabim.com/api/interface_i_reinforcement_unit_usage_collection.html) | Reinforcement styles/usages/geometry |
| [`IRichTextDocument`](https://help.rengabim.com/api/interface_i_rich_text_document.html) | Documentation and text |
| [`IRichTextParagraph`](https://help.rengabim.com/api/interface_i_rich_text_paragraph.html) | Documentation and text |
| [`IRoofSlopes`](https://help.rengabim.com/api/interface_i_roof_slopes.html) | Levels and native architectural geometry |
| [`IRoom`](https://help.rengabim.com/api/interface_i_room.html) | Rooms and boundary association |
| [`IRoomRegionDescription`](https://help.rengabim.com/api/interface_i_room_region_description.html) | Rooms and boundary association |
| [`IRouteParams`](https://help.rengabim.com/api/interface_i_route_params.html) | Engineering routes, ports and connections |
| [`IScreenshotService`](https://help.rengabim.com/api/interface_i_screenshot_service.html) | Views, selection and API rendering |
| [`IScreenshotSettings`](https://help.rengabim.com/api/interface_i_screenshot_settings.html) | Views, selection and API rendering |
| [`ISelection`](https://help.rengabim.com/api/interface_i_selection.html) | Views, selection and API rendering |
| [`ISiteInfo`](https://help.rengabim.com/api/interface_i_site_info.html) | Projects and ownership |
| [`ISplitButton`](https://help.rengabim.com/api/interface_i_split_button.html) | Extension actions and controls |
| [`ISystemStyle`](https://help.rengabim.com/api/interface_i_system_style.html) | Equipment and engineering styles |
| [`ISystemStyleManager`](https://help.rengabim.com/api/interface_i_system_style_manager.html) | Equipment and engineering styles |
| [`ITextObject`](https://help.rengabim.com/api/interface_i_text_object.html) | Documentation and text |
| [`ITitleBlockInstance`](https://help.rengabim.com/api/interface_i_title_block_instance.html) | Documentation and text |
| [`IToolButton`](https://help.rengabim.com/api/interface_i_tool_button.html) | Extension actions and controls |
| [`ITransform2D`](https://help.rengabim.com/api/interface_i_transform2_d.html) | Baseline/placement/math |
| [`ITransform3D`](https://help.rengabim.com/api/interface_i_transform3_d.html) | Baseline/placement/math |
| [`IUI`](https://help.rengabim.com/api/interface_i_u_i.html) | Extension actions and controls |
| [`IUIPanelExtension`](https://help.rengabim.com/api/interface_i_u_i_panel_extension.html) | Extension actions and controls |
| [`IUndoStack`](https://help.rengabim.com/api/interface_i_undo_stack.html) | Transactions and undo |
| [`IView`](https://help.rengabim.com/api/interface_i_view.html) | Views, selection and API rendering |
| [`IView3DParams`](https://help.rengabim.com/api/interface_i_view3_d_params.html) | Views, selection and API rendering |
| [`IWallContour`](https://help.rengabim.com/api/interface_i_wall_contour.html) | Levels and native architectural geometry |
| [`IWallParams`](https://help.rengabim.com/api/interface_i_wall_params.html) | Levels and native architectural geometry |
| [`IWindowParams`](https://help.rengabim.com/api/interface_i_window_params.html) | Levels and native architectural geometry |
