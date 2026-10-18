# Operation plans used by Codex

Codex interprets natural language. The bridge executes explicit operations; it
does not contain a second language model or a design chat. State dimensions in
millimeters and record any assumptions before a model write.

1. Inspect the saved project, levels, parameter definitions and style catalogs.
2. Select existing numeric IDs from that inspection, or persistent `UniqueId`
   values when retaining references across SaveAs.
3. Save a JSON plan. Validate its structure and native compatibility; preview
   on a disposable copy when useful.
4. Apply the plan in the configured test/work root. Existing-file edits create
   a verified backup first. The bridge checks actual saved output after close
   and reopen, then returns reopened IDs and persistent identities.
5. Inspect quantities and extracted geometry against the technical assignment.
   A setter return or a successful structural validation alone is insufficient.

## Model plan

A plan is a JSON array. `ref` identifies a newly created object for later steps
in the same plan; references must point to earlier creation operations.

```json
[
  {"action":"create","ref":"host","kind":"Wall",
   "points":[[0,0],[6000,0]],
   "parameters":{"WallHeight":3000,"WallThickness":250}},
  {"action":"create","ref":"window","kind":"Window","host":"host",
   "origin":[3000,0,900],
   "parameters":{"WindowStyleId":0,"WindowWidth":1200,"WindowHeight":1400}},
  {"action":"set_parameter","id":"host","name":"WallHeight","value":3200}
]
```

Style 0 creates an aperture in this example. To request a complete window or
door assembly, inspect the current project's catalog and select a compatible
existing positive style ID. Never substitute an arbitrary ID. Z on a hosted
window is applied through its `Offset`; XY controls location on the host.

Supported model actions are `create`, `set_parameter`, `baseline`, `baseline3d`,
`property`, `delete`, `move`, `room_region`, `room_marker` and `roof_slopes`. Their category
coverage is scoped in [CAPABILITIES.md](CAPABILITIES.md). Native read-only
parameters are refused. `property` uses an explicit GUID and currently supports
string values. `baseline` accepts 2D points; `baseline3d` accepts 3D points for
the verified beam scenario. `room_region` uses a 2D control point. Roof edge
settings require inspected native edge indices/enums, explicit angles and
overhangs.

`create` can include `host`, `level`, `origin`, `points`, `closed`, `parameters`,
`x_axis` and `z_axis`. Placement axes are validated and read back from the saved
native object; Renga can normalize orientation, which must not be reported as
the requested facing. Beam and Element creation require an inspected existing
style. Beam and stair parameters need post-creation application in the tested
API. Host creation and dependent operations are staged before the single final
save; a failed plan closes without saving and leaves the original disk file
unchanged, with backups and logs retained.

```powershell
.\.venv\Scripts\renga-bridge.exe validate --plan examples\rectangle.json
.\.venv\Scripts\renga-bridge.exe apply --project 'C:\dedicated-test-root\new.rnp' --plan examples\rectangle.json --new
```

`--new` refuses an existing target. All writes must remain under the configured
write root, including export/copy targets; path escapes and unsafe links are
refused. The MCP interface has no blanket authorization bypass. Keep plans,
backups and raw logs out of public Git history.

## New project with nonzero levels and axes (0.2)

`bridge_create_levels_project(project, levels, grid=None)` creates a NEW `.rnp`
inside the write root. It uses official `ImportIfcProject` with an own IFC seed,
then deletes its temporary geometry carriers and verifies genuine native Level
and Axis objects after save/close/reopen. Existing targets are refused. It does
not insert a level/grid into an existing project or edit its level elevations.

```json
{
  "levels":[{"name":"Ground","elevation_mm":0},{"name":"Upper","elevation_mm":3000}],
  "grid":{
    "x":[{"name":"1","position_mm":0},{"name":"2","position_mm":3000},{"name":"3","position_mm":9000}],
    "y":[{"name":"A","position_mm":0},{"name":"B","position_mm":6000}],
    "bounds_mm":[-1000,-1000,10000,7000]
  }
}
```

`x` axes have constant X and run along Y; `y` axes have constant Y. Bounds are
explicit global `[xmin,ymin,xmax,ymax]`. Both families are required when `grid`
is present. Labels are unique and coordinates lie inside the bounds. Grid
geometry is checked against a fresh native IFC export, not a fabricated COM
getter. Reopened UUIDs can be used as `level` hosts for subsequent native walls.

CLI: `renga-bridge create_levels --project <new.rnp> --plan <seed.json>`.
An array of level specifications also works without a grid; `examples/levels.json`
is a minimal example. Level and axis limits are 1000 each, not performance
certification for the maximum-sized request.

After inspecting a Room UUID, move its intrinsic marker using
`{"action":"room_marker","id":"<room-uuid>","point":[2345,1678]}`. Both XY
coordinates are global millimeters. The bridge verifies them after native Apply
and again after reopening. A Wall or standalone Tag is refused. `bridge_inspect`
returns `room_marker_mm` and actual level metadata.

## Documentation and checks

Drawing and project-information plans use their dedicated tool arguments rather
than the model-action array. Inspect existing scales, topics and schedule
definitions before choosing IDs. Native documentation tools create sheets,
embedded model views, existing schedule instances and text. Associative
dimension and tag constructors are not established in this preview; text is
never used to impersonate them.

The facade-spacing helper produces deterministic coordinates; it does not
automatically certify clearances, structural rules or accessibility. Geometry
verification compares measured areas with explicit independent targets.
Bounding-box intersection candidates are not exact solid clashes. Use the
capability map and returned `not_verified` values to retain these boundaries.

For a fresh read-only check after changing Door/Window styles, `bridge_verify`
and the worker `verify` command accept an optional `expected_filling_hosts`
dictionary mapping each inspected filling UUID to its inspected Wall UUID.
This argument is separate from the model-action plan array. The verifier reads
actual native affected-wall IDs and any exposed parent UUID, returns both
expected and actual host identities for successful checks, and raises on
missing/wrong objects or disagreeing bindings. Numeric IDs are not accepted
in this map. This does not certify leaf/panel geometry or opening direction.

Area results name the actual `quantity_key`: Room comparisons sum all horizontal
downward faces of a closed, outward-wound mesh (including interior-floor cuts)
against native `GrossFloorArea`, while Room `expected_areas` targets continue
to use native `NetFloorArea`. Door/opening and boundary rules can make these
quantities differ. An unavailable gross quantity yields `unverified_checks`
and `not_verified`; exported room geometry alone is not an independent net-area
calculation. Unknown winding/closure and sloping-downface semantics remain
unverified. Floor mesh/target checks continue to use `NetArea`.
