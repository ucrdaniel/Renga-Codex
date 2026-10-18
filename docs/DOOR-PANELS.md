# Native door and window panel verification

Development reader: `renga_codex_bridge.filling_panels.inspect_filling_panels`,
also exposed by the `bridge_inspect_filling_panels` MCP tool and the
`filling_panels` CLI command. These development additions do not change the
frozen 0.2 preview's advertised native coverage.

The helper accepts an existing bridge-owned `Session` and inspected persistent
Door/Window UUIDs, with a limit of 2000 fillings. Omit `identifiers` to select
all actual native Door/Window objects; an empty result is `not_verified`, not
a vacuous success. Numeric IDs are not accepted as caller identities. It reads
the native 3D export and the independently installed
SDK's `DoorPanel` / `WindowPanel` mesh classifications. For each selected filling
it reports panel meshes, grids, nondegenerate triangles, triangle surface area
in mm² and panel bounds/extents in mm. A fresh read-only Session on a saved file
establishes that the reported geometry comes from the saved project.

```python
from renga_codex_bridge.session import Session
from renga_codex_bridge.filling_panels import inspect_filling_panels

with Session(saved_test_project) as owned:
    result = inspect_filling_panels(owned, inspected_filling_uuids)
```

For CLI selection, supply `--plan` with a saved JSON array of inspected UUIDs;
omit it to inspect all native fillings. Through MCP use:

```json
{"project": "C:/dedicated-test-root/test.rnp", "identifiers": null}
```

The reader creates no objects and performs no Save, import, style reassignment
or GUI action. `save_reopen_performed_by_this_reader` stays false: the caller
must establish the persistence boundary. UUIDs and native Door/Window types are
checked before geometry is read. Unknown export/classification is reported as
`not_verified`; a classified export containing no nondegenerate panel triangles
fails the panel-presence requirement. Frames, thresholds, positive `PanelDepth`
and nonzero style references cannot satisfy it.

Bounds use the coordinates returned by the native 3D exporter. The reader does
not infer a local frame, unrotate a leaf or identify an insertion point from
the bounds. Surface area is calculated from 3D triangle cross products, so a
vertical/transformed panel is not collapsed to an XY projection. Nonfinite
coordinates, invalid triangle indices and overflowing areas are rejected.

The result does **not** certify physical leaf count, a closed solid, opening
direction, swing arcs, a manufacturer's assembly, panel subdivisions, joints
or ГОСТ conformity. Multiple grids can belong to one native mesh; even a mesh
count is not an independently verified physical leaf count.

## Creating complete styles

A fresh Renga 9.3/API 2.50 synthetic fixture created four native Doors using
existing full stock styles from an independently installed standard template.
After save/close/reopen, a separate readonly `filling_panels` worker verified
native DoorPanel triangles for all four selected UUIDs. The light/dark hinged,
sliding glazed and rotating glazed stock cases passed; the source template and
an unrelated working file remained unchanged. This proves instance creation
from already complete styles, not custom style-tree authoring or an exact
prescribed multipart layout. See the
[sanitized native evidence](../tests/evidence/development-filling-panels-9.3.json),
including the retained failure of an optional placement parameter setter.

In examined Renga API 2.50, `DoorStyles` is an `IEntityCollection`. It supports
native creation and exposed parameters such as `PanelDepth`, lining and
threshold values, but exposes no `IDoorStyle` or panel-tree editing interface.
Creating a style and successfully persisting those exposed values is therefore
different from creating a complete door leaf. Earlier default-style probes
saved frame/threshold meshes while producing no `DoorPanel` geometry.

`INewEntityArgs.FilePath` is documented for linked objects and `ElementStyle`,
not as a DoorStyle import contract. `IEntityCollection` exposes no Clone/Copy
or style-file import method. `IProject.ImportCategory` is an STDL category
operation, not a documented native DoorStyle panel-tree import. These APIs are
not silently repurposed or represented as tested door-style creation routes.

An existing complete native DoorStyle can be selected by inspected style ID
and assigned through the supported `DoorStyleId` parameter, followed by normal
backup, save, close/reopen, UUID and native mesh checks. Creating such a style
through Renga's style editor is an explicit GUI workflow, not API-only bridge
coverage. A source project/template route needs a separately demonstrated,
officially supported transfer operation before being advertised as portable.

Primary references: [collection](https://help.rengabim.com/api/interface_i_entity_collection.html),
[new entity arguments](https://help.rengabim.com/api/interface_i_new_entity_args.html),
[DoorStyle parameters](https://help.rengabim.com/api/group___entity_type_by_parameters.html),
[door mesh classifications](https://help.rengabim.com/api/group___door_mesh_types.html),
and [project category import](https://help.rengabim.com/api/interface_i_project.html).
