# Additional resource and presentation operations

Development update, 2026-10-15, API 2.50 / Renga Professional 9.3.32980.0.
These additions follow the frozen 0.2.0 preview. They are not a new release or
a replacement for its source fingerprint and native-test evidence. Private
models, drawings, task inputs, local paths and raw logs are not redistributed.

## Operations and native verification

| Addition | Implemented contract | Observed native scope / remaining verification |
|---|---|---|
| `bridge_inspect_resources` | Read resource IDs, UUIDs and actual parameters; structural-style profile parameters/contours; existing layered-material layers | Reading authored ordinary materials and rectangular beam profiles was exercised. Populated arbitrary layered stacks and every supported style category are not established by those tests |
| `bridge_author_resources` | Create new ordinary `Material`, rectangular `BeamStyle`/`ColumnStyle`, and basic `DoorStyle`/`WindowStyle`; backup, save, close, reopen, compare requested fields and preserved model identities | Native save/reopen confirmed **9 ordinary materials, 4 rectangular beam styles, 1 basic door style and 1 basic window style**. Column-style authoring remains implemented but not separately native verified here |
| `bridge_create_presentations` | Create native Drawing sheets, DrawingText, named Topics and embedded existing model/entity/schedule/table views using inspected IDs | The initial owned probe verified a Drawing/text/AR Topic/Level view. A later scoped run saved/reopened **7 Drawings and 9 embedded views (3 Level, 6 entity-by-mark)**, including text/fonts, sources, centers and bounds. Native PDF export contained 7 pages (5 A3, 2 A4). Structural readback does not by itself certify visual composition |
| `native_default_facing` on Door/Window creation | Explicitly select the native constructor's default axes instead of requesting a specific exterior side; verify saved origin/size, native host effects and the observed saved pose | **91 native fillings** passed saved host/origin/Offset/style-reference checks. This does not establish requested opening direction, custom panel divisions or panel-mesh completeness |
| Native mesh part metadata | Each extracted grid retains `mesh_type_guid`, `grid_type`, `mesh_index` and `grid_index` beside vertices/triangles | Native classification found panel geometry on **53 Windows**. **38 Doors** had frame/threshold geometry after the scoped style update, but **no DoorPanel**. A positive style ID is not evidence of a door leaf, and no custom panel subdivision is claimed |
| Session lookup/definition caches | Cache UUID→numeric ID and parameter-definition metadata as plain data, without retaining COM objects or values | Portable tests verify revalidation, reused/deleted IDs, model replacement, new-object registration and Session isolation. Native performance improvement is not yet measured as a benchmark |
| STEP/STP `ElementStyle` authoring | Explicit local source file/hash plus independent mesh expectations; native collection factory and temporary Element probes before save and after reopen | **4 original, locally generated STEP fixtures** passed native save/reopen and independent bounds/volume/surface/minimum-triangle checks. This establishes these fixtures, not every STEP model or a manufacturer library |
| Staged native Ramp creation | Apply the newly created baseline object before setting its dependent parameters | An owned native Ramp probe retained requested height/width/baseline, Offset and native shape after save/reopen. This is separate from accessibility or full contact/collision validation |
| Fresh read-only geometry/host validation | Explicit area quantity semantics and UUID-based native host checks | Final scoped native readback passed **86 area comparisons (23 Room gross, 63 Floor net) and 91 filling host checks**. These 177 checks do not verify room net area against the gross mesh |

The native counts above are scoped development observations. No complete
architectural package or new release aggregate is claimed. The fresh standalone
stdio discovery below is separate from the current chat's cached catalogue.
[Source](../src/renga_codex_bridge/resources.py),
[presentation source](../src/renga_codex_bridge/presentation.py) and
[portable contracts](../tests/unit/test_presentation.py) are reviewable without
vendor SDK binaries or private test files.

## Request and persistence contracts

Inspect catalogs and resources before selecting numeric IDs. Native IDs can
change on SaveAs; stored UUIDs identify the objects across reopen. Requests
continue to use explicit millimeters, the configured write root, owned COM
sessions, verified backups and saved-result checks. Resource editing is not
advertised as a single atomic model-undo transaction.

Resource creation accepts names and explicit supported values. Ordinary
materials may specify RGBA byte color, density in kg/m³ and conductivity in
W/(m·K). Structural styles require the installed project's existing native
Rectangle profile and positive width/height in mm. Door/window resources expose
only supported style parameters; returned `panel_layout_verified` remains
`false`. Existing names are rejected before resource mutation; the authoring
operation does not silently replace a resource used by other elements.

`ElementStyle` creation initially permits only `.step`/`.stp`, with an absolute
`file_path`, the independently selected `source_sha256`,
`expected_dimensions_mm: [X,Y,Z]` and
`expected_geometry: {volume_mm3, surface_area_mm2, minimum_triangles}`. The source
is read as data and hashed before/after native import. Native style dimensions
are **read**, never changed to make a fallback model fit the expectation. A
temporary native Element supplies mesh bounds, shell volume, surface area and
triangle count, with grids read only for that probe object. It is deleted
before save; the saved style is probed again after reopen without saving the
temporary model edit. Model UUID preservation and the saved file hash are
checked. These invariants reject missing geometry and deviations in the tested
measurements; they do not identify every possible wrong shape, prove full BRep
equivalence or reproduce a native parametric source control tree. Separate
readback checked 81 placed Elements against independent source/placement data;
the native project also reopened with the source STEP directory absent.

The official [3D import formats](https://help.rengabim.com/ru/Content/import.htm)
include STEP/STP. The [Element documentation](https://help.rengabim.com/ru/Content/element.htm)
distinguishes solid-format projections from mesh formats that appear as bounds
on 2D views; the initial importer therefore uses STEP solids. This is separate
from importing RNP style libraries. `IProject.ImportCategoryS(entityTypeId,
filePath)` accepts STDL categories; no RNP library merge is inferred from it.
The [collection factory](https://help.rengabim.com/api/interface_i_entity_collection.html)
explicitly permits a default-model fallback on bad ElementStyle inputs, which
is why factory success and matching bounding dimensions alone are insufficient.

Presentation requests specify `name`, inspected `page_format_id`, orientation,
optional existing `layout_style_id`, optional exact Topic name, text bounds and
explicit embedded views. Model views reference an **existing** Level, Section
or Elevation. Entity views require an inspected object ID and its actual
`object_mark`; the final native binding is **by mark**, so duplicate marks are
not uniquely resolved. Schedule/table views require an existing configured
resource and nonempty native content.

Embedded-view initialization is staged: bind source and scale, Apply; set
dependent view parameters, Apply; set content center and fitted/explicit bounds
in subsequent operations. A parameter reported read-only is still rejected.
The returned `visual_layout_verified: false` requires a separate visual review
of clipping, readability and overlapping content.

`native_default_facing: true` is valid only for Door/Window creation and cannot
be combined with explicit `x_axis`/`z_axis`. It makes no promise about which
side is exterior. The result reports the actual saved axes rather than
presenting them as a requested orientation. Existing explicit-axis validation
and saved-pose comparisons remain strict. Host verification reads native
affected-object IDs; an exposed nonempty parent UUID must agree with the
requested wall. A missing parent UUID is reported as unverified, not invented.

UUID lookup caches retain only normalized strings and integer IDs per Session.
Every cache hit reads the current object with `GetById` and compares its actual
UniqueId. Missing/stale hits rebuild the current collection index. Deletion,
ID reuse, reopen and replacement of the Session's model therefore cannot
silently return another object's cached COM interface. Parameter-definition
caching does not cache `HasValue`, `IsReadOnly`, `ValueType` or parameter values.

`bridge_verify` also accepts optional
`expected_filling_hosts: {"<Door-or-Window-UUID>": "<Wall-UUID>"}`. This is a
read-only check of the currently opened saved model, useful after a style
change. It normalizes and validates persistent identities, resolves the fresh
native filling object and verifies actual affected-wall IDs with the existing
host reader. A nonempty exposed parent UUID must agree. Each successful row
reports `expected_host_uuid`, `actual_host_uuid`, `affected_wall_verified` and
parent-evidence fields. Missing objects, wrong native types, reused numeric IDs
or disagreeing host data cannot silently produce a success row. Exceptions
remain errors; the check creates no model operation. Portable routing/identity
tests pass; the final native bulk readback is a separate verification step.

Area checks name their `quantity_key`. A Room's **entire closed, outward-wound
mesh** is checked by summing all horizontal downward faces, including faces
above minimum Z caused by interior floor cuts. This is compared with available
native `GrossFloorArea`; that mesh does not
independently establish `NetFloorArea`, whose boundary/opening rules differ.
Explicit `expected_areas` targets for Rooms still check native `NetFloorArea`.
Floors retain the existing `NetArea` comparison. Missing matching gross data
produces a separate `unverified_checks` entry and `not_verified` status, never
a substitution of net area or a silent success. Open, inward/mixed-winding or
sloping-downface geometry with unestablished area semantics also remains
unverified. A failed net-area target still fails the result when gross checks pass.

Resource/presentation creation saves before its final reopen assertions. If
that later verification fails, the native file may already contain the edit.
The failure must be inspected together with the saved file and verified backup;
automatic restoration of the original file is **not** implemented. Restore the
appropriate pre-edit backup manually when needed, then re-inspect before retry.

## Remaining API limits

- No authoring contract for material layer order/base-layer selection,
  texture/hatch definitions, arbitrary constrained profile geometry or custom
  door/window panel trees is established. Unsupported requests are rejected.
- New Section/Elevation creation and associative dimensions/Tags remain
  restricted. Existing source views can be embedded; screenshots, lines and
  free text are not substitutes for those native objects.
- A blank native sheet does not manufacture a regulated frame/title block.
  An existing layout resource may be selected; arbitrary title-block cell
  writing and layout-definition authoring are not implemented.
- Existing schedule/table resources may be embedded, but no public native
  row/column/cell/formula/filter-definition authoring contract was found.
  Creating an empty entity would not satisfy a working schedule.
- Geometry labels and nonempty meshes require category-specific interpretation
  and independent geometry/visual checks before claiming a complete assembly.
- STEP Elements preserve the imported geometry as native placed Element/style
  resources, not the original CAD feature history. Furniture semantics and a
  complete manufacturer/library match require separate source and visual review.

See [presentation API research](PRESENTATION_API_RESEARCH.md),
[capability boundaries](CAPABILITIES.md) and
[operation-plan safety](OPERATION_PLANS.md).

## MCP catalogue refresh

The development source declares **24 tools**: the frozen 0.2.0 set of 21 plus
`bridge_inspect_resources`, `bridge_author_resources` and
`bridge_create_presentations`. A **fresh real stdio server** was initialized
from the current source on 2026-10-15 and returned all 24 unique tool names.
All advertised JSON input/output schemas passed validation; the received
resource schema accepted the four STEP specifications. Only
`bridge_validate_plan` was called, returned `native_execution_performed: false`,
and the server exited with code 0. No native Renga/status tool was called.
This proves the current standalone protocol/catalogue path and portable plan
validation, not native execution through each of the 24 tools.

The active chat still exposes a cached **20-tool** catalogue. Restart/reconnect
the configured MCP server and refresh the Codex session before expecting the
new names. The fresh standalone result does not refresh that existing chat or
establish execution from it.
