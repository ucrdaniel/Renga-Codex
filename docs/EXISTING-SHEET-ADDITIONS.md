# Adding native contents to existing sheets

Two Python adapters extend existing Drawing sheets without creating duplicate
sheets. Development MCP routes are `bridge_append_sheet_schedules` and
`bridge_append_sheet_views`, each taking `project` and `additions`. CLI commands
are `append_sheet_schedules` and `append_sheet_views`; `--plan` contains the
JSON array of additions. These routes do not export PDF. Discovery/routing
tests establish protocol contracts, not native operation support.

The [sanitized native evidence](../tests/evidence/development-sheet-additions-9.3.json)
records the tested module digests and the scoped direct-helper runs described
below. It does not certify native execution through the new MCP routes or
change the frozen release evidence.

```powershell
renga-bridge append_sheet_schedules --project 'C:\dedicated-test-root\model.rnp' --plan 'C:\dedicated-test-root\schedule-additions.json'
renga-bridge append_sheet_views --project 'C:\dedicated-test-root\model.rnp' --plan 'C:\dedicated-test-root\view-additions.json'
```

## Existing Schedule resources

`sheet_additions.append_sheet_schedules(project, additions)` creates genuine
`EmbeddedSchedule` objects bound to inspected existing native Schedule
resources. It does not create or populate Schedule definitions, rows, filters,
formulas or cells.

```python
from renga_codex_bridge.sheet_additions import append_sheet_schedules

result = append_sheet_schedules(project, [{
    "drawing_uuid": inspected_drawing_uuid,
    "schedule_id": inspected_schedule_id,
    "available_bounds_mm": [275, 400, 100, 270],
    "fit_inset_mm": 0,
}])
```

Coordinates are sheet millimeters, with bounds `[left,right,bottom,top]`.
The adapter fits the native content, reads its actual rectangle and content
origin, checks that it fits, and translates its left/top to the requested
rectangle's left/top. It does not stretch or shrink the table or crop an
oversized schedule to simulate a fit. Repeated source insertion on the same
sheet is rejected.

A disposable native fixture exercised four existing Schedule resources on four
existing Drawing sheets in Renga9.3.32980.0/API2.50. Native resource bindings,
nonempty content, fitted placement, saved bounds, persistent identities and
save/close/reopen passed. A later authorized operation repeated those four
additions with the intended sheet positions. A preliminary undersized layout
was rejected without saving; its failed call was retained. The fixture's
private architectural source and raw logs are not distributed.

The current source also checks a readonly UUID/type subset of every supported
catalog available in the session. That guard passed a fresh native fixture
run: one existing Room Schedule was added to a disposable Drawing, then saved,
closed and reopened. Every previously available catalog identity remained
present. The extra Schedule existed only in the fixture. Identity checks do
not certify resource definitions, Schedule cell values, filters or visual
readability.

## Existing model/entity view sources

`sheet_views.append_sheet_views(project, additions)` has portable validation
and safety tests, plus native coverage for existing Level, Section and
Elevation sources in Renga9.3.32980.0/API2.50. A disposable fixture and a later
authorized operation each added two Level views, one Section view and two
Elevation views to existing Drawing sheets. Save/close/reopen, persistent
source/resource bindings, fitted bounds and old object identity preservation
passed. Entity-source insertion through this new adapter remains covered by
portable tests only.

```python
from renga_codex_bridge.sheet_views import append_sheet_views

result = append_sheet_views(project, [{
    "drawing_uuid": inspected_drawing_uuid,
    "kind": "model",
    "source_entity_id": inspected_existing_level_id,
    "scale_id": inspected_scale_id,
    "origin_mm": [145, 175],
    "fit_inset_mm": 1,
    "view_parameters": {"SectionPlaneOffset": 1500},
}])
```

Model sources must be existing native Level, Section or Elevation objects.
Entity sources require an explicitly inspected `object_mark`; that native
binding uses Mark rather than a unique source-instance UUID. Both kinds require
an existing drawing UUID, inspected positive source/scale IDs and explicit
content origin. Optional bounds are a crop, not a source-geometry edit.

The helper creates no Drawing, Section or Elevation, changes no source plane,
and never opens/renders a source view. It cannot repair a wrongly positioned
section line. Its preflight reads source identity/type, resources and matching
existing contents before factories. A nonempty `HasContent` flag cannot prove
the requested projection, correct cut or complete visible geometry.

The native checks additionally read
`IDrawing.GetTransformFromEmbeddedModelView` for three sheet points per added
model view. They observed finite, perpendicular basis vectors at the requested
1:100 and 1:150 scales after reopening. This establishes the saved mapping for
those five views; it does not establish visible geometry completeness or that
a source faces the side required by an architectural assignment. No source
view was opened or rendered during these tests. Visual review and source-plane
correction remain separate tasks.

Both adapters use the standard write-root rules, owned COM STA Session,
hash-checked backup, undo operations and saved-result readback. They preserve
all old building/drawing/content UUID/type identities and require exactly the
requested new contents. Reopened resource bindings use persistent UUIDs.
Numeric IDs can change when native contents are added and saved; caller
verification must compare persistent identities and resolve fresh numeric IDs.

No Computer Use or image substitute is part of these adapters. Visual sheet
review, native source projection review, specification data and ГОСТ layout
checks remain explicit follow-up work.
