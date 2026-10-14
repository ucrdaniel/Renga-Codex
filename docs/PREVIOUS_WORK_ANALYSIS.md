# Previous integration: technical findings

Reviewed on 2026-10-14. This document records evidence from the owner's earlier,
private Windows integration and a separate architectural modelling exercise.
It is research input for Renga–Codex Bridge, **not a test report for this public
product**. Private BIM files, raw user logs, personal information and SDK
binaries are deliberately excluded from this repository.

Кратко: прежняя интеграция действительно изменяла и повторно открывала модели
через COM. Однако оформление сложных чертежей и некоторые операции с уровнями
и автоматическими помещениями требовали управления интерфейсом. Эти результаты
нельзя выдавать за полностью программное покрытие нового моста. Отсутствие
старого MCP-инструмента также не доказывает ограничение Renga API.

## Evidence and its scope

The reviewed environment was Windows x64, Renga Professional **9.3.32980.0**,
SDK reference **API 2.50**, and Python 3.12.14. These identify the historical
environment; they do not establish compatibility with every Renga edition or
release. The source review included the old session, model, command, geometry,
safety and MCP modules, the integration test runner, specialist architectural
scripts, saved operation plans and before/reopened audits.

| Evidence ID | Actual evidence reviewed | What it proves | What it does not prove |
|---|---|---|---|
| H-ENV | Local diagnostic and device migration records | Installed application version, registered COM connection and rebuilt Python environment | A copied virtual environment is portable, or all Windows installations behave identically |
| H-COM | Historical `latest-integration.json`, 15 passed checks and its test source | Real create/edit/delete, rollback, save/reopen, geometry, quantities and IFC export on a disposable project | Fresh bridge correctness, complete architectural coverage, or semantically validated IFC |
| H-MCP | Historical `mcp-test.json`, real stdio client and seven tool names | Protocol discovery, isolated COM access, test-plan mutation, geometry/IFC operations and rejection of a production write | The newly packaged server is installed in Codex or exposes the same tools |
| H-ARCH | Final native architectural audit, 636 passed assertions; publication and reopened-model evidence | Preservation of model/drawing identities, selected saved geometry and parameters after reopening | 636 API writes, zero Computer Use, general-purpose implementations, or complete PDF delivery |

The H-COM smoke test created four walls, a manual room and a floor. It edited a
wall to height 3300 mm and thickness 250 mm, checked a 6000 mm baseline, placed
a 1200 × 1400 mm window aperture with 900 mm offset, created and renamed a
default-elevation level, assigned a custom string property, and deleted on a
disposable copy. Its room net area was 21.895 m² both in Renga and an independent
triangulated-floor calculation. A 6000 × 4000 mm floor measured 24 m². Geometry
extraction returned seven objects and 184 vertices. An IFC4 file was written
and its STEP envelope inspected. A rejected read-only write rolled back without
changing the saved file hash. The nonzero-level request was explicitly rejected.

The historical check named `apartment_schedule` was a separately computed
room-to-apartment grouping from native room data. It was not creation or
inspection of Renga's native schedule definition or cells.

The old MCP test discovered `renga_status`, `renga_inspect`,
`renga_apply_test_plan`, `renga_geometry`, `renga_export_ifc`,
`renga_rectangle_plan` and `renga_facade_spacing`. This is a historical tool
list; use the current product's README and capability table for its interface.

The architectural audit covered 255 building-model objects, including 62 native
model dimensions, 17 rooms, styled doors/windows, a stair, pitched roofs and
furniture. Two native drawing sheets contained separate native annotations.
Twelve rooms were ultimately automatic and five remained intentionally manual
functional zones. Several creations and corrections were performed through the
GUI, including automatic-room creation, nonzero levels, dimensions, tags,
schedule filters and literal stamp cells. The final revision deliberately did
not export a new PDF. These mixed API/GUI results are useful regression lessons,
not an API-only acceptance test. The owner's approximately 39-hour experience
is context, not a measured benchmark of COM throughput.

## What can be reused

The old integration's useful ideas are small, separable mechanisms:

- A fresh `Renga.Application.1` instance, a main-window HWND → PID check against
  pre-existing processes, and refusal to attach to an existing user session.
- Typed COM interop generated locally from a user-supplied type library;
  string-GUID `...S` methods for convenient boundary representations.
- Explicit millimeter operation plans, host/style selection before creation,
  writable-parameter validation, and an undo transaction around model edits.
- Backup-before-edit, hash validation, native save return-code checks, close and
  reopen, then comparison with expected saved values and persistent identities.
- Quantity extraction, mesh extraction, independent area calculations and
  geometric room/element checks outside the COM adapter.
- A serialized MCP boundary and a separate worker for COM operations, with
  logs recording attempted, rejected and verified operations distinctly.

Specialist scripts embed one building's geometry, UI state and numeric IDs.
They are **not** suitable core MCP tools. Extract general algorithms such as
wall-face alignment, polygon validation, hosted-opening placement and explicit
apartment grouping instead. Preserve configurable tolerances and sources for
expected values.

## Failures, causes and programmatic alternatives

The classifications below describe the identified issue, not a released tool.
Current implementation/testing status is maintained in
[CAPABILITIES.md](CAPABILITIES.md).

| Historical difficulty | Technical cause and evidence | Programmatic resolution or next test | Classification |
|---|---|---|---|
| Dynamic Python calls rejected typed records | Dynamic dispatch produced COM type/marshalling errors; typed `comtypes` records worked | Load the local TLB and construct the declared record/interface. C# interop is another supported route; a Python marshalling failure is not proof that an API method is absent | `SUPPORTED_NOT_IMPLEMENTED` for any unported typed operation |
| Nonzero levels silently remained at zero | `ILevel.Elevation` and `Placement` are getters; `IPlacement3D.Origin` is also a getter. The old creation path did not persist the requested elevation | Reject the old unsupported path; use a user-provided template with known levels. A disposable test of `level.Placement.Move(...)`, transaction/save/reopen and direct elevation readback remains necessary before ruling out that nested-method route | `API_LIMITATION` for direct elevation/origin setters; nested move `NOT_VERIFIED` |
| Door/window relocation did not persist after `SetPlacement` | `ILevelObject.SetPlacement` explicitly excludes Door, Window, Opening and Room, and objects with dependents. A call returning is insufficient | Use category-specific writable placement parameters where available; otherwise recreate the native hosted object with complete style, host, offset and properties, then verify dependent identities and geometry | `API_LIMITATION` for that generic placement path |
| Empty window instead of a complete assembly | Style zero represented an aperture in the tested template | Inspect styles and choose a valid existing style; assign `INewEntityArgs.StyleId` before creation and verify the saved style and meshes | `SUPPORTED_NOT_IMPLEMENTED` for a new styled-opening adapter until its fresh test passes |
| Imported element style can silently contain default geometry | The SDK documents a non-null ElementStyle factory result with default model when the supplied 3D file is unsupported or fails loading | Verify actual imported content/meshes against the intended file; never treat non-null style creation as successful import | `VERSION_DEPENDENT` for formats; content verification is an implementation requirement |
| Resource/style lost during recreation | Recreating a wall or hosted object with only geometry omitted material/style parameters | Snapshot and restore explicitly supported properties; separately verify material layers, thickness, style references and affected openings. Do not equate a matching object name with matching style | `NOT_VERIFIED` for arbitrary lossless reconstruction |
| Wall baseline shorter than a nominal construction axis | Native joins trimmed a bearing wall at an exterior wall face | Check actual baseline and mesh, adjoining wall thickness, face contact and clear room width. Retain nominal and persisted native values in the result; do not loosen all tolerances to hide one join | `SUPPORTED_NOT_IMPLEMENTED` for a generic join-aware validator |
| Beam height/alignment apparently correct but actual solid wrong | Local baseline, level placement, profile alignment and vertical offset were conflated; joins also shortened actual solid ends | Read `IBaseline3DObject.GetBaselineInCS` in an explicit coordinate system, verify profile dimensions/alignment/offset, then compare mesh bounds and contact faces. Baseline endpoints and joined mesh endpoints need not coincide | `SUPPORTED_NOT_IMPLEMENTED` for full beam verification |
| Initially flat or incorrectly clipped roof | Roof baseline alone did not set edge type, slope angle, overhang and slope level. Canopy geometry changed adjoining room quantities | Use `IRoofSlopes` per edge and read saved values; query angles only for applicable slope edges, not gables. Its slope-angle unit is degrees, unlike math/placement rotation in radians | `SUPPORTED_NOT_IMPLEMENTED` for complete roof tool; version/edge behavior must be tested |
| Room gross area valid while net area was zero | On the transferred test file the supporting floor was missing; a valid plan contour alone did not prove a valid room volume | Verify supporting floor, elevation, region and triangulated room bottom before accepting net area. Restore support through the API and read after reopen | `SUPPORTED_NOT_IMPLEMENTED` for complete room-support verification |
| Room area slightly wrong despite an apparently rectangular plan | An incorrectly extended roof canopy clipped room geometry | Verify actual roof/room solids and net area, not only polygon area. Separate source rounding from actual native area | `SUPPORTED_NOT_IMPLEMENTED` for solid-aware area diagnosis |
| Calculated room contour treated as an automatic room | `CalculateRegion` returned a region; setting a manual room baseline did not set `Automatic`. The property has no setter | Advertise manual rooms honestly. Existing automatic rooms have a writable `ControlPoint`; creation of a new automatic room solely by public COM remains unverified. Test a template-based route without GUI before claiming it | `API_LIMITATION` for an `Automatic` setter; automatic creation `NOT_VERIFIED` |
| Automatic-room boundary calculation returned empty | An overlapping manual room participated in region calculation | On a backed-up test copy, move/remove the old contour before calculating a replacement; check all inner contours and room associations. The old generic adapter rejected regions with holes rather than silently discarding them | `SUPPORTED_NOT_IMPLEMENTED` for robust region replacement |
| Drawing dimensions reported as `UndefinedObject` | Native drawing annotations returned that public SDK type and no parameter container, despite being real saved native dimensions | Preserve their actual type/name/UUID; never relabel them as model `LinearDimension`. SDK discovery does not expose their measured value or native associativity. Separate model dimension checks from drawing annotation checks | Drawing annotation creation/measurement `NOT_VERIFIED`; missing exposed getter is an `API_LIMITATION` of that inspection route |
| Missing dimension, room-tag and schedule editing tools | An entity GUID and a generic factory did not provide all required binding, associativity or definition properties. No public `ISchedule`, `ITable`, `ITag` or `ILinearDimension` interface appeared in API 2.50 | Probe actual supported interfaces and parameters on disposable objects, examine templates and officially supported extensions, and report unavailable semantics. A custom line/text imitation is not a native associative annotation | `NOT_VERIFIED` for complete creation; specific absent setters/getters `API_LIMITATION` |
| A tag displayed `?` or followed the wrong fixture | GUI picking bound the annotation to the wrong object; simple counts did not detect semantic binding | Until binding and readback are accessible via COM, do not claim automated native room tags. Source-name changes and saved annotation linkage require explicit verification; a standalone room report is a different output | `NOT_VERIFIED` |
| Schedule filter check falsely failed | The inspector expected a `FilterId` that native schedules did not expose. Public schedule parameters were limited, and there was no `ISchedule.GetDefinition/GetData` | Enumerate actual parameters rather than inventing members. Independent room-group calculations are useful but are not verification of native schedule rows or filters. Existing configured templates may be usable, still require a real test | `API_LIMITATION` for the assumed filter/data interfaces; template route `NOT_VERIFIED` |
| Arbitrary stamp cell writing unavailable | `ITitleBlockInstance.GetCellValue` is read-only; there is no corresponding public cell setter | Read cells; update supported source fields such as project name/code/stage and drawing parameters. Use a properly licensed, preconfigured template for literal author/organization cells. Test source binding before promising automatic filling | Direct cell edit `API_LIMITATION`; source-field route `SUPPORTED_NOT_IMPLEMENTED` |
| PDF export missing from the generic adapter | Export tooling was absent, although `IDrawing.ExportToPdf` and `IProject.ExportDrawingsToPdfS` are public methods | Implement direct native single/multiple-sheet export; independently open the PDF and check page count/size/content. No printing dialog or PDF merger is required for the documented multi-sheet API | `SUPPORTED_NOT_IMPLEMENTED`, **not** a platform limitation |
| DWG/DXF/CSV, IFC import not implemented | The old adapter concentrated on IFC export | Public drawing exporters, project CSV export and application IFC import provide documented routes. Test the native result; project CSV is not a getter for native schedule cell values | `SUPPORTED_NOT_IMPLEMENTED` / version-sensitive formats |
| Some objects disappeared from UUID audit | The old generic inventory relied on an optional `UniqueId` parameter, absent on some drawing/undefined objects | Always read `IModelObject.UniqueIdS` or `IEntity.UniqueIdS` directly, then resolve new numeric IDs after reopen. Compare complete UUID sets, including drawings and helper objects | Implementation defect; new bridge must test the correction |
| Parameters/quantities unavailable on some native objects | `GetParameters()` can return null and quantities can be unset | Preserve object identity and interface information; distinguish null/unset/unsupported from numeric zero. Iterate `IGuidCollection.Count/GetS` rather than assuming a Python sequence | Implementation gap |
| An old error string misreported a successful operation | `LastError` can outlive the current call | Clear or timestamp diagnostics, record native return codes, and let saved-state postconditions determine success. Do not suppress genuine failures | Implementation gap |
| Copied virtual environment failed on another device | Virtual environments carry machine-dependent paths and compiled Windows modules | Recreate from declared dependencies; discover the local installation/TLB and regenerate wrappers outside Git | `VERSION_DEPENDENT` environment concern |
| Worker timeout could leave an owned Renga process | Killing only the Python worker is not lifetime management of its COM server | Record the verified owned PID, release/close on normal exit, and design bounded process-tree recovery without terminating other Renga sessions | `NOT_VERIFIED` until failure-injection tests pass |

Relevant primary documentation: [API general principles](https://help.rengabim.com/api/overview-general-principles.html),
[level](https://help.rengabim.com/api/interface_i_level.html),
[3D placement](https://help.rengabim.com/api/interface_i_placement3_d.html),
[level-object placement restrictions](https://help.rengabim.com/api/interface_i_level_object.html),
[room](https://help.rengabim.com/api/interface_i_room.html),
[roof slopes](https://help.rengabim.com/api/interface_i_roof_slopes.html),
[drawing](https://help.rengabim.com/api/interface_i_drawing.html),
[title block](https://help.rengabim.com/api/interface_i_title_block_instance.html),
and [project](https://help.rengabim.com/api/interface_i_project.html).

## Lifecycle findings during the 0.1 reimplementation

The following were discovered in the new bridge's disposable native tests on
Renga Professional 9.3.32980.0. They are current implementation findings, not
additional H-ARCH successes. At the time of this update the full documentation
and PDF visual QA scenario is still in progress; these findings do **not** claim
that the complete test suite or final PDF has passed.

| Native observation | Correct implementation sequence | Required saved-output check |
|---|---|---|
| A newly created EmbeddedSchedule exposes `ScheduleId` as read-only until its creation operation is applied | Create the native object, apply that operation, then start a separate operation to assign the actual existing schedule through `ScheduleId`. `RepresentedEntityId` is not its schedule-reference parameter | After save/reopen, read `ScheduleId`, persistent identity and native content; do not claim schedule definition/filter editing |
| Fitting an embedded view before its source/scale changes are applied produced a tiny dot or cropped PDF content despite `HasContent=True` | Create/apply the view; assign `RepresentedEntityId`, `ScaleId` and section parameters; apply; only then call `FitBoundsToContent` in another operation and apply it | Read persisted source/scale/bounds, export the selected drawings and inspect actual page content. `HasContent` proves content exists, not that the clip rectangle displays it correctly |
| The tested project template retained an existing blank native drawing when two new test sheets were added | Preserve unrelated template drawings. Export the explicit two newly created drawing UUIDs, rather than exporting every entry in `Drawings2` | Read saved drawing identities and selected export set, then independently check exact PDF page count, both A3 dimensions and content |

These observations distinguish temporarily read-only creation state from a
permanent API restriction. A supported parameter can become writable only after
native initialization/regeneration; do not bypass `IsReadOnly` or assume that
all setters can be issued in the object's creation transaction. Separate
operations remain inside one backed-up project-edit session, followed by native
save, close, reopen and readback.

An automatically fitted bound is also a regenerated result, not a substitute
for presentation verification. A nonempty native view and a successful PDF
export return code can coexist with unusable clipped output. Conversely, an
extra blank template sheet is a selection issue rather than evidence that the
multi-sheet export API failed.

## API-first architecture implications

Typed COM is supported from C#, C++ and external dynamic-language processes.
The evidence gives a practical reason to reuse a small Python/comtypes adapter:
its record marshalling and save/reopen path already worked locally. C# is a
reasonable alternative when compiled interop, existing .NET MCP code or an
in-process plugin provides a concrete benefit. A language change alone does not
add missing native setters. Final runtime selection belongs to the current
architecture and its tests, not this historical document.
[Official API/SDK overview](https://help.rengabim.com/api/overview-api-sdk-plugin.html).
The 0.1 implementation chooses the typed Python adapter with a replaceable
worker boundary; the preliminary C# preference and rnpmcp architecture are
evaluated in [ARCHITECTURE_RECOMMENDATION.md](ARCHITECTURE_RECOMMENDATION.md).

A C++/.NET plugin is an officially supported extension route, including .NET 8
plugins. It runs inside Renga and could dispatch a local IPC command on the
appropriate application thread, reducing some external marshalling problems.
It uses the same public API; it is not evidence of hidden dimension/schedule
editing APIs. UI actions created by `IUI.CreateAction` are extension actions,
not a documented way to invoke every built-in modelling command. Plugin
deployment and its vendor utility-library redistribution terms must be reviewed
separately before release. No vendor plugin binary is included here.
[Official plugin implementation guide](https://help.rengabim.com/api/how-to-implement-a-plugin.html).

STDL category import/update and parameterized style templates are additional
documented routes for applicable categories. They may improve generic elements
and MEP modelling but do not establish support for all structural styles or
associative drawing annotations. Template-assisted operations must require a
user-supplied/licensed template and verify its actual contents.

The SDK's ObjectCreation example lists native architectural entities, Room,
Level, embedded views/schedules/tables and drawing text among its factory
examples. Axis, LinearDimension and Tag are not in that example's allowed-type
list and are absent from the documented `IModel.CreateObject` supported-type
table. Direct generic construction of these types is therefore outside that
public factory's support. This does not prove that every future template or
extension route is impossible. Reading an existing model dimension's computed
`DimensionValue` parameter is separate from authoring its defining-feature
bindings. Similarly, writable
`Placement3D` record fields used for creation must not be confused with
getter-only `IPlacement3D.Origin` on a returned interface.

Native view opening, visibility, camera control and `IScreenshotService` are
official API operations, not mouse/keyboard emulation. The screenshot service
is obtained from a supported **view** by an additional interface, not from an
invented application property. A view can therefore be rendered for inspection
without Computer Use, once a fresh test proves the implementation.
[Screenshot service](https://help.rengabim.com/api/interface_i_screenshot_service.html).

## Required verification improvements

1. Record the new product version, COM/TLB version and tool list. Keep historical
   evidence identifiers separate from fresh test IDs.
2. Validate the entire plan before mutation: types, finite coordinates, units,
   nondegenerate closed contours, writable parameters, known hosts/styles,
   output paths and target project state.
3. Use a fresh owned session and a serialized STA. A process-global lock is a
   useful first defense; ownership, timeout and orphan recovery need separate
   tests. `Visible=False` does not itself mean Renga is headless.
4. Back up and hash existing files before changing them. A transaction is not a
   replacement for a backup: the API documentation notes that model undo does
   not cover project resources such as materials and styles.
5. Read actual native UUIDs, geometry and requested parameter values immediately
   after changes, then save, close, reopen and repeat the checks. SaveAs may
   change numeric IDs. Requested values, return codes and saved values belong
   in distinct log fields.
6. Verify IFC beyond a nonempty file when semantic validity matters. Verify PDF
   pages beyond an exporter return code. IFC import must distinguish native
   imported Renga objects from externally linked IFC/reference meshes.
7. Never advertise AABB overlap as exact clash detection. Distinguish broad
   phase candidates, triangle contact/intersection and native volume tests;
   exclude legitimate wall/column joins by explicit rules.
8. Count Computer Use independently and require **zero** for every advertised
   API-only scenario. Historical GUI evidence cannot fill a missing fresh test.

## Release boundary

This analysis supports a universal, testable integration rather than reusing a
homework model as a fixture. A first release may expose a verified subset and
report other operations as unsupported/unverified. It must not claim complete
autonomous documentation, arbitrary nonzero-level creation, lossless copying
of every element type, arbitrary native schedule editing or a GUI-free replay
of the historical architectural exercise without new evidence.

For current method-level status, supported versions and fresh test references,
see [CAPABILITIES.md](CAPABILITIES.md). For third-party provenance and licenses,
see [NOTICE.md](../NOTICE.md) and
[REPOSITORY_RESEARCH.md](REPOSITORY_RESEARCH.md).
