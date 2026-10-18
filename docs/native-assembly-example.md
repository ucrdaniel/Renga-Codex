# Native single-beam assembly example

[`examples/native_beam_assembly.py`](../examples/native_beam_assembly.py)
creates a new editable native Assembly definition containing one straight Beam
on the installed SDK's stock Ellipse profile, and a real AssemblyInstance.
Dimensions are explicit millimeters; the instance uses the new project's zero
base level and default constructor orientation. A circle is width=depth.

This is a standalone Python example, **not an additional MCP tool or general
assembly-clone/import command**. It supplies no vendor models or UUIDs. It reads
the installed SDK constants locally and uses the bridge's isolated owned STA
Session. It has no GUI, clipboard, PDF, external AI or extra API-key dependency.

After installing the bridge and configuring its SDK/write/state roots, run
from the checkout with a **new**, unused `.rnp` path inside the write root:

```powershell
python examples/native_beam_assembly.py --project 'C:\dedicated-test-root\assembly.rnp' --length-mm 1000 --width-mm 18 --depth-mm 18
```

It rejects existing targets and invalid dimensions before opening Renga. The
saved JSON plan describes every requested dimension. Creation uses staged
project/resource operations and assembly/building model undo operations. The
SDK disables undo history for resources; this NEW-only example does not edit
existing project files or claim resource undo support.

Before save and after a close/new-session reopen, it checks native object
types, persistent UUIDs and actual resource references, both profile dimensions,
the exact straight baseline, actual AssemblyInstance origin/axes through
`ILevelObject.GetPlacement`, its host Level's persistent UUID/type and zero
elevation, finite/nondegenerate exported triangles and actual mesh extents
within 0.1 mm. Reopened numeric IDs are reported separately from
persistent UUIDs. Bounds/presence checks are narrower than closed-solid or full
shape equivalence and do not establish structural adequacy or compliance.

The public refactoring passed its own fresh native run on Renga 9.3.32980.0 /
API 2.50: a new 1000×18×18 mm fixture saved/reopened with all requested dimensions,
baseline and native UUID/type/reference checks retained. The native instance
export contained 28 triangles, all nondegenerate, with exact extents 1000×18×18 mm.
There was exactly one creation run; Computer Use and PDF exports were zero.
[Sanitized evidence](../tests/evidence/development-native-beam-assembly-9.3.json)
records the tested creation-source digest and the initial docstring-only update.
Review then found the original reader omitted instance pose/host-Level checks.
The current reader adds them and passed a separate **read-only reopen of that
same saved fixture**: actual origin `[0,0,0]`, AxisX `[1,0,0]`, AxisZ `[0,0,1]`,
the same persistent host-Level UUID/type and elevation 0 mm. Its source digest
and zero Create/Save/setter counts are recorded separately. The target file's
hash remained unchanged; this recheck is not a second creation run and the
updated creation entrypoint was not rerun after adding the guards.
The current portable suite passed 42 tests, including changed origin/axes/level
and unsupported-interface failures. Other sizes, placements and versions do not
inherit this narrow fixture's native PASS.

Supported scope is deliberately one straight beam on a stock Ellipse. Custom
profile contours/constraints, curved beams, nested multi-component assemblies,
cross-project resource transfer, logical-group semantics and adapting complete
fire ladders such as П1-2 remain separate capabilities. In particular,
`Profiles.Create` alone does not define a custom sketch profile; the documented
[`IProfileDescription`](https://help.rengabim.com/api/interface_i_profile_description.html)
exposes no contour/constraint writer.
