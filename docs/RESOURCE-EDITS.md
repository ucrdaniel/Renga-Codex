# Existing window style parameter edits

`resource_edits.update_window_styles(project, changes, expected_project_sha256=None)`
edits **existing** native `WindowStyle` resources. It creates neither a style nor
the internal pane/mullion tree. No graphical automation is used by this helper.

MCP: `bridge_update_window_styles(project, changes, expected_project_sha256=None)`.
CLI `--plan` contains the JSON **array** of changes:

```powershell
renga-bridge update_window_styles --project 'C:\dedicated-test-root\model.rnp' --plan 'C:\dedicated-test-root\style-changes.json' --expected-project-sha256 $inspectedSha256
```

```python
from renga_codex_bridge.resource_edits import update_window_styles

result = update_window_styles(
    project,
    [{
        "resource_uuid": inspected_style_uuid,
        "expected_name": inspected_style_name,
        "parameters": {
            "FrameThickness": 50,
            "FrameDepth": 50,
            "VerticalMullionThickness": 50,
            "HorizontalMullionThickness": 50,
            "WindowLiningThickness": 50,
            "WindowLiningDepth": 50,
        },
        "material_uuid": inspected_ordinary_material_uuid,
    }],
    expected_project_sha256=inspected_project_sha256,
)
```

Every change requires a persistent style UUID and the exact inspected resource
name. At least one requested parameter or ordinary `material_uuid` is required.
Lengths must be finite positive millimetres. Optional `parameters.EntityName`
renames the same resource, with collision checks. Numeric `MaterialId` input is
rejected: the material UUID is resolved in the freshly opened project and the
saved reference is verified by UUID after reopening. This avoids treating
session-specific numeric IDs as persistent references.

The full batch is preflighted before the first setter, including existence,
type, exact name, writability and native parameter value type. The helper saves
a JSON plan, uses the isolated bridge Session and its mandatory backup, applies
a project operation, reads back values before saving, then closes and reopens
the file. It verifies requested values, unchanged unrequested exposed style
parameters, all exposed resource identities/types/names (except requested
renames), building objects, drawings and drawing contents. Missing resource
collections are reported; getter failures are not hidden.

The optional SHA256 guard pins the inspected disk file and is checked again
after opening. The normal Session also refuses an external disk change at save.
All regular bridge path restrictions apply; this helper offers no user-file
authorization bypass.

## Native limits

The installed API documents `IProject.CreateOperationWithUndo` as supporting
model objects only: undo history is disabled for project resources such as
styles and materials. This helper therefore uses the documented project
operation, unsaved-discard on failure and a verified disk backup. Its result
reports `undo_history_supported: false`; it does not promise model-style undo
for resource changes. See the installed SDK `IProject` reference or the
[official API reference](https://help.rengabim.com/api/interface_i_project.html).

`WindowStyle.MaterialId` is an exposed common parameter. Reading that saved
reference does **not** establish the material of each internal frame, sash or
mullion node. The helper returns `material_per_node_verified: false` and
`panel_tree_authoring_verified: false`. Resource identity and parameter checks
also do not establish actual exported geometry, rendered colour or visual
layout. Those require separate model-export checks.

Portable unit tests validate these safety/readback contracts without launching
Renga. Native evidence, when recorded, must name the tested Renga/API version,
source module digest and exact verified scope; a parameter setter returning
without an error is never sufficient evidence.

## Development verification

[Sanitized native evidence](../tests/evidence/development-resource-edits-9.3.json)
records an actual Renga 9.3.32980.0 / API 2.50 development probe. Two existing
styles passed 12 saved/reopened length checks at 50 mm, two material UUID
reference checks and identity/unrequested-parameter preservation. Two real
Window instances then passed saved panel, sill and outward-sill export checks.
A separate triangle-coordinate join established black RGBA `[0,0,0,255]` for
all 192 and 132 exported Window.Frame triangles respectively, with no missing
or ambiguous colour matches. That colour probe is independent of the public
common-parameter helper and is not a general per-node material authoring API.

The test fixture's internal pane trees had been authored before the parameter
edit. This evidence does not claim their API creation, GUI-free origin or
compatibility with every style tree or Renga version. Private project files,
geometry and resource identifiers are excluded from the public evidence.
