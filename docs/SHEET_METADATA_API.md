# Existing native sheets and title-block readback

Development module: `renga_codex_bridge.sheet_metadata`. This is an API-only
operation with the standard owned STA, write root, verified backup and
save/close/reopen behavior. Native title-block cells are read; none are authored
through an invented setter.

```python
from renga_codex_bridge.sheet_metadata import (
    inspect_sheet_metadata, update_sheet_metadata,
)

observed = inspect_sheet_metadata(project_path)
result = update_sheet_metadata(project_path, [{
    "drawing_uuid": "00000000-0000-0000-0000-000000000001",
    "parameters": {
        "EntityName": "Ground floor plan",
        "PageFormatId": inspected_a3_id,
        "PageOrientation": 2,
        "LayoutStyleId": inspected_existing_layout_id,
        "TopicId": inspected_existing_topic_id,
    },
}])
```

The UUID in this example is a placeholder, not a default source. Inspect the
actual saved project first. Orientation is native 1 portrait or 2 landscape.
IDs must identify existing positive native resources in that same project.
Zero IDs, unknown parameters, duplicate drawing UUIDs and cell/table authoring
requests are rejected before mutation. All target sheets, parameters and
resources are preflighted before the first setter.

Saved source references are checked by the resources' persistent UUIDs, so a
numeric-ID change during native save does not masquerade as a lost reference.
All building, drawing and drawing-content UUIDs/types must remain unchanged.
That check is not a mesh equivalence, associative-binding or visual-layout test.

`drawings[].title_blocks` contains actual `GetCellValue(column, row)` output in
row-major order, including empty strings. `title_block_readback.status` records
whether that getter succeeded. A native getter error is explicit and leaves
`title_blocks` null; it is never converted to zero stamps or guessed text.
On the tested Renga version, `TitleBlockInstanceCount` threw a server error for
some sheets with no assigned layout. Other readable metadata is still returned.
`title_block_readback_complete` distinguishes complete cell readback from such
partial inspection. Applying metadata does not prove that the page contents fit
the selected paper, that title-block fields are correctly bound, or that the
sheet meets a drawing standard. Visual review remains required.

## Factory and template boundaries

The API 2.50 `IEntityCollection.Create` contract includes **LayoutStyle,
Schedule and Table**. Disposable native probes on Renga 9.3.32980.0 created all
three and retained their UUIDs/types after save and reopen. These factories
produce blank resources: the tested blank layout exposed only identity/name
parameters and gave zero title blocks when assigned to a new sheet. Native
Schedule/Table exposed identity/name/topic parameters, without an editable row,
column, filter or formula definition contract. This is resource creation, not
completion of a specification.

The installed Russian template contained configured layout styles and tables.
A new project from that template retained a drawing with three native title
blocks, including the main title block. Template contents are version/local
installation dependent. Creating a **new** project from a template does not
establish an API for merging its resources into an existing architectural
project. No vendor template or binary is redistributed by this repository.

The two disposable direct `IModel.CreateObject` attempts for native Section and
Elevation returned null, with the native error saying creation of that type is
unsupported. These outcomes concern that API factory; they do not prove that
all template, supported import or future SDK routes are impossible. Existing
Section/Elevation entities can be sources for `EmbeddedModelView` through the
presentation helper. Parallel 3D camera PNGs are external geometry reviews and
do not create native elevation sheets.

No new PDF was exported during these documentation probes. Private native
models and raw logs are kept outside this repository; portable tests are
contracts, not native evidence. This development module does not alter the
frozen release evidence in `tests/evidence/windows-renga-9.3.json`.

Fresh development positive scenario on **2026-10-16**, Renga **9.3.32980.0**,
API **2.50**: an existing disposable drawing received a new name, A3 page
reference, portrait orientation, an inspected configured native layout and
an inspected Topic. All five requested fields or referenced-resource UUIDs
were read back after save/close/reopen. Building/drawing/content identity/type
sets remained equal. Both fixture drawings exposed three real native title
blocks after reopening. This verifies that specific metadata operation and
getter path, not arbitrary title-block cell editing, schedule content or
architectural compliance. No Computer Use or PDF export was used. Separately,
the seven-sheet project inspection returned metadata plus seven explicit
title-block getter failures for sheets with no layout; its native source hash
was unchanged.

A separate fresh **MCP stdio** client on the same date initialized protocol
2025-11-25, discovered the exact 27-tool development catalogue and validated
every advertised input/output JSON schema. It executed the new sheet metadata
reader, the filling-panel reader and a five-field sheet metadata update on the
disposable fixture through the real server and child-worker path. The update
retained native references, object identities and three title-block instances
after save/reopen. The read-only architectural work file's SHA256 was unchanged.
This stdio result does not refresh a pre-existing Codex chat's cached catalogue,
and the filling reader correctly reported absent door panels rather than
counting them as completed doors. No full native MCP suite or PDF export was run
for this narrow extension test.

Primary API references:

- [IEntityCollection](https://help.rengabim.com/api/interface_i_entity_collection.html)
- [IDrawing](https://help.rengabim.com/api/interface_i_drawing.html)
- [ITitleBlockInstance](https://help.rengabim.com/api/interface_i_title_block_instance.html)
- [IModel factory](https://help.rengabim.com/api/interface_i_model.html)
- [IApplication template creation](https://help.rengabim.com/api/interface_i_application.html)
