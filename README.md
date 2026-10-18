# Renga–Codex Bridge

Independent, unofficial local MCP integration for Codex and Renga BIM. Codex
interprets the task; this package provides typed COM operations, geometry,
native documentation and saved-result verification. No AI API key, second
agent service or design chat application is required.

**0.2.0 preview — verified subset for Renga Professional 9.3.32980.0.**
Real local CLI and MCP scenarios create and edit native BIM objects, then save,
close, reopen and check the requested values. See the scoped
[native evidence](tests/evidence/windows-renga-9.3.json) and
[testing instructions](docs/TESTING.md); hosted CI does not run Renga.
Computer Use and mouse/keyboard emulation are prohibited for advertised API
coverage. Renga and its SDK must be installed/licensed separately. No vendor
binaries, SDK-generated wrappers, private models or credentials are shipped.

## Installation

Windows x64, Python3.11+, installed Renga and separately downloaded SDK:

```powershell
.\scripts\install.ps1 -PythonExe 'C:\path\to\python.exe' -SdkPath 'C:\path\to\RengaSDK'
```

Read [Russian installation](docs/INSTALL_RU.md) or
[English installation](docs/INSTALL_EN.md), [capabilities](docs/CAPABILITIES.md),
[previous work analysis](docs/PREVIOUS_WORK_ANALYSIS.md) and
[repository research](docs/REPOSITORY_RESEARCH.md).

## Architecture

```mermaid
flowchart LR
    Codex --> MCP[stdio MCP server]
    MCP --> Worker[serialized isolated STA worker]
    Worker --> Adapter[typed local COM adapter]
    Adapter --> Renga[Renga-owned project process]
    Renga --> Verify[save / close / reopen / UUID and value checks]
```

Core modules: session/safety/audit, SDK loading, BIM operations, geometry,
catalogs, native drawings/exports, verification, deterministic plan helpers.
API coordinates are millimeters; area m² and volume m³ are labelled explicitly.

A standalone [native assembly example](docs/native-assembly-example.md) creates
one editable Beam assembly and instance in a new disposable project, with saved
geometry and identity checks. Its native evidence covers a 1000×18×18 mm stock
Ellipse scenario; it is not a new MCP tool or a general assembly import command.

The frozen 0.2.0 preview's 21 MCP tools cover status and capabilities; inspection and catalogs;
validated plans and disposable-copy previews; geometry and area verification;
project copy, SaveAs and metadata; native drawing content, PDF, IFC and view
rendering; rectangle plans and facade spacing. The complete names and verified
boundaries are in [CAPABILITIES.md](docs/CAPABILITIES.md).

Development source now declares **32 tools**, adding resource inspection,
resource authoring, native presentations, filling-panel inspection and editing
of existing sheet metadata and supported sheet contents. Native development probes have
saved/reopened 9 ordinary materials, 4 rectangular beam styles, 2 door styles,
1 window style, and 7 Drawings with text, an AR Topic and 9 embedded views.
Four original STEP fixtures also passed saved ElementStyle geometry checks;
91 native fillings passed saved host/origin/Offset/style-reference checks.
Door/window `native_default_facing`, native mesh-part labels and safe Session
identity/definition caches are additional implemented contracts with explicit
verification limits. Fresh API and real stdio MCP checks also read native panel
meshes and title-block cells, and saved/reopened five existing-sheet metadata
fields with preserved identities and resource UUIDs. The panel reader correctly
reported 38 doors without panels and 53 windows with panels in that scenario;
it does not create door leaves. See [panel verification](docs/DOOR-PANELS.md),
[sheet metadata](docs/SHEET_METADATA_API.md),
[existing sheet contents](docs/PRESENTATION-EDITS.md) and
[development additions](docs/API-HW2-EXTENSIONS.md).
Four further development routes edit existing WindowStyle common parameters,
edit existing registered String properties, and append existing native
schedules or model/entity views to existing sheets. Their strict input schemas
and portable routing checks do not imply equal native coverage. Scoped native
runs saved/reopened WindowStyle common parameters, existing Drawing String
values, an existing Schedule with the current catalog identity guard, and
five existing Level/Section/Elevation views with three-point native transform
readback. No resolved title-block author cell was found: property persistence
does not fill a visible stamp field. Project/Topic property mutation and entity
insertion through the new view adapter remain native unverified. See [style edits](docs/RESOURCE-EDITS.md),
[existing properties](docs/EXISTING-PROPERTIES.md) and
[existing-sheet additions](docs/EXISTING-SHEET-ADDITIONS.md).
These additions do not change the frozen 0.2.0 release evidence. A current chat
with a cached 20-tool catalogue needs an MCP restart/reconnect and catalogue
refresh before it can expose the new tools. A fresh standalone stdio server
returned 27 tools, validated their schemas and executed the three new panel and
sheet-metadata tools through native workers. The subsequent 28th tool,
`bridge_update_sheet_contents`, passed a separate 12-check native worker fixture
for an existing model view and DrawingText edits. A later discovery-only stdio
run returned all 28 tools with valid schemas and no native tool calls.
The latest fresh stdio check returned **32 tools**, validated every advertised
input/output schema and called only pure capability metadata; native calls,
Computer Use and PDF exports were zero. The matching portable suite passed
1333 tests (1 skipped, 1 opt-in integration test deselected).
[Protocol evidence](tests/evidence/development-mcp-catalogue-32.json) identifies
the tested source digests and retains the native-coverage limits.
Current-chat discovery,
standalone protocol checks and native execution remain separate evidence.

New in 0.2: `bridge_create_levels_project` creates a **new** native project with
explicit nonzero levels and an optional orthogonal native Axis grid through
the official IFC importer. Own temporary slab carriers are removed; saved
native types, names, identities and elevations are checked after reopening.
Axis coordinates are verified through a fresh native IFC export, because the
tested Axis has no supported direct baseline getter. This bootstrap does not
merge levels/axes into an existing project or move existing level elevations.
The `room_marker` plan action positions a Room's intrinsic marker in global XY;
it does not create a standalone Tag. See [level/grid plans](docs/OPERATION_PLANS.md).

Roof operations return `roof_slope_checks` with the requested edge fields read
from the saved native `IRoofSlopes` object. These checks verify edge parameters;
complete roof geometry, drainage and contact with surrounding elements require
separate mesh and design checks.

Development renderer option: `render --camera-orientation front` (also `back`,
`left`, `right`) requests a parallel camera in the owned whole-building 3D
view. The optional MCP argument is `camera_orientation`; omit `entity_id`.
This produces an external native PNG for geometry QA and creates no elevation
on a sheet. Separate real Renga front/left renders passed position, focus and
parallel-camera readback and visual review. Back/right remain native unverified.

```powershell
.\.venv\Scripts\renga-bridge.exe doctor
.\.venv\Scripts\renga-bridge.exe inspect --project 'C:\your\test-root\sample.rnp'
.\.venv\Scripts\renga-bridge.exe apply --project 'C:\your\test-root\sample.rnp' --plan examples\rectangle.json --new
python -m pytest -m 'not integration' -q
```

Autonomous writes are confined to `RENGA_BRIDGE_WRITE_ROOT`. Existing-file
edits receive verified backups and native undo transactions. Dependent hosts
and some calculated geometry need several applied batches before the final
save; failed plans discard unsaved changes, rather than promising a single
in-memory undo for every category. There is no MCP
blanket authorization bypass. Copy saved user files into the dedicated working
directory before editing; never run vendor sample scripts against user files.

Codex translates a task into an explicit millimeter-based JSON plan, inspects
existing IDs/styles, validates the plan, optionally previews it on a copy,
applies it and reads the reopened result. See
[operation plans](docs/OPERATION_PLANS.md). Reconnect the MCP server or start a
new Codex session after installation to refresh its catalogue. Real stdio MCP
and Codex discovery tests distinguish new-version coverage from historical
0.1.0 current-chat evidence; see the dated public proof.

## Русский

Это инфраструктура доступа Codex к настоящей Renga через MCP и типизированный
COM API. Все операции выполняются локально, без Computer Use. Публикуемое
покрытие ограничено фактически проверенными возможностями. Автоматические
размеры/маркеры и создание автоматических помещений нельзя имитировать
текстом или изображениями. Новый проект с заданными ненулевыми уровнями и осями
создаётся через `bridge_create_levels_project`. Изменение отметок существующих
уровней по-прежнему отклоняется. Встроенный маркер помещения перемещается через
`room_marker`; это отдельная возможность от создания нового Tag.

MIT applies to our own source. See [NOTICE](NOTICE.md) for third-party and
Renga SDK boundaries. This project does not represent Renga Software.
