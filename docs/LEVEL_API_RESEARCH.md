# Nonzero levels: official API routes

Research date: **2026-10-15**. Examined reference: **API 2.50 / Renga 9.3**,
including the locally supplied SDK, its C# ObjectCreation sample and the live
official reference. This document distinguishes API discovery from native
proof. No SDK implementation, generated interop, user model or vendor fixture
is included. Computer Use calls in this research: **0**.

## The getter is not the whole API

`ILevel` declares `double Elevation [get]`, `BSTR LevelName [get]` and
`IPlacement3D Placement [get]`. There is no `ILevel.SetElevation` or placement
setter. The placement origin Z equals the level elevation. Mutating a placement
object returned by a getter is not documented as a commit to the model.
[ILevel](https://help.rengabim.com/api/interface_i_level.html).

However, the parameter registry separately associates `LevelElevation` with
Level. It is an `Elevation` parameter with `Double` storage, not an integer
floor number. Generic `IParameter.SetDoubleValue(double)` exists, with runtime
`IsReadOnly` and `HasValue` gates. Thus, a read-only `ILevel.Elevation` property
alone does **not** prove that the generic parameter cannot be edited. Inspect
the actual parameter before and after applying creation, and preserve its
reported read-only state in the native probe. Do not remove the existing bridge
rejection merely because the registry contains a GUID.
[Entity parameter map](https://help.rengabim.com/api/group___entity_type_by_parameters.html),
[Parameter storage types](https://help.rengabim.com/api/group___parameter_types_and_value_types.html),
[IParameter](https://help.rengabim.com/api/interface_i_parameter.html).

## Creation and placement

The supported generic constructor is:

```text
IModel.CreateNewEntityArgs(out INewEntityArgs)
IModel.CreateObject(INewEntityArgs, out IModelObject)
```

The creation matrix explicitly permits Level in the building model. The local
C# ObjectCreation sample includes Level in its allowed type list. It does not
provide a special elevation constructor. Level creation was added in API 2.40
(Renga 8.6).
[IModel creation matrix](https://help.rengabim.com/api/interface_i_model.html),
[Changelog](https://help.rengabim.com/api/_changelog.html).

`INewEntityArgs.Placement3D` is writable, but its documentation describes its
application to **level-based objects** (`ILevelObject`). A Level is the host of
those objects; the documentation does not promise that the Level constructor
uses its Z value. `HostObjectId` selects the host for a level-based or dependent
object and is not documented as a source level to clone. `StyleId`, `CategoryId`
and `FilePath` are not alternate level-elevation arguments.
[INewEntityArgs](https://help.rengabim.com/api/interface_i_new_entity_args.html).

The existing product's R-ELEMENTS negative probe applied a +3000 mm move to the
returned Level placement, saved and reopened, then read elevation/origin Z=0.
That establishes failure of that particular route on the tested version. It
does not establish failure of import or templates. `ILevelObject.SetPlacement`
is documented for objects belonging to a level; obtaining that interface on a
Level must be tested rather than inferred from the shared word "level".
[ILevelObject](https://help.rengabim.com/api/interface_i_level_object.html),
[Prior evidence scope](PREVIOUS_WORK_ANALYSIS.md).

## A distinct supported route: IFC project import

The official application interface exposes:

```text
HRESULT ImportIfcProject([in] BSTR fileName, [out, retval] int *pResult)
```

This creates a **new project** from IFC. It is distinct from importing an IFC
link through `IModel.CreateObject` with `EntityTypes.IfcModel` and `FilePath`.
The method returns zero on success; an already open project causes a nonzero
return without prompting. Use it on a fresh bridge-owned process with no open
project. `OpenProject` is not the documented method selected for this test.
[IApplication.ImportIfcProject](https://help.rengabim.com/api/interface_i_application.html#abd7824cd4a5929fb44ec7d262bac607d).

**Native result on Renga Professional 9.3.32980.0:** Import of the own synthetic
IFC produced genuine native Levels at **0, 3000 and 6000 mm**. Both
`ILevel.Elevation` and `ILevel.Placement.Origin.Z` survived native save, close and
reopen. A new native Wall hosted on the imported +3000 mm Level had independently
extracted mesh elevations **3000–5800 mm**, matching its 2800 mm height. The
route therefore supports further native modelling, rather than preserving only
an imported representation. The reproducible extension scenario is
[run_level_annotation_tests.py](../scripts/run_level_annotation_tests.py);
release assertion counts and the tested source fingerprint belong in its final
sanitized evidence record.

The production adapter uses the pure own-source
[level_seed.py](../src/renga_codex_bridge/level_seed.py) generator. It imports
temporary slab carriers and removes every non-Level/non-Axis object before
saving the requested clean model. Imported slab or wall geometry is not
advertised as native slab/wall conversion. The adapter verifies the exact native
types, level names/heights, persistent identities and absence of carriers after
reopening. An existing output is refused; this creates a new project only.

The own-source generator
[generate_storey_fixture.py](../scripts/generate_storey_fixture.py) creates IFC4
text with a Project → Site → Building → three Storeys decomposition. Storey
placements and declared elevations consistently use **0, 3000 and 6000 mm**;
units explicitly declare millimeters. Each storey contains a simple
6000 × 200 × 2800 mm swept-solid IfcWall. Stable synthetic GlobalIds make the
test reproducible. The generator has no SDK, COM or third-party dependencies,
and refuses to overwrite an existing output. It is a test fixture generator,
not a general IFC exporter or a proof of schema conformance by itself.

Run it with a new output under the configured disposable test directory:

```powershell
python scripts/generate_storey_fixture.py --output C:\your\test-root\storeys.ifc
```

Native acceptance sequence:

1. Save the attempted operation plan and protect the new destination.
2. Start a verified owned STA process with no project. Call `ImportIfcProject`.
3. Require result=0; enumerate the resulting native objects. Find **Level**
   objects using their type identity, then read `ILevel.Elevation`,
   `ILevel.Placement.Origin.Z` and `LevelElevation` separately.
4. Require levels at 0/3000/6000 mm. Inspect wall types and host IDs separately;
   generic imported geometry does not prove native wall conversion.
5. Create a fresh native wall on the +3000 mm Level. Check its native LevelId
   and mesh world Z. A bootstrap that only preserves imported solids is
   insufficient for the desired modelling workflow.
6. SaveAs a new `.rnp`, close, reopen, and repeat the checks using persistent
   identities. Verify all requested elevations and host relationships.
7. Record successful and failed attempts. An import failure may reflect an
   invalid or unsupported fixture; diagnose that independently before asserting
   that the API cannot import levels.

The route creates a new project. It does **not** imply that arbitrary levels
can be inserted into an existing model, that arbitrary IFC geometry converts
to native BIM, or that Renga supports merging imported spatial structures.

## Optional native coordinate grid

The same import route also converted own `IfcGrid`/`IfcGridAxis` data into
genuine native **Axis** objects, preserved in the `.rnp` after close/reopen.
The bootstrap supports an explicit orthogonal grid: `x` lists constant-X
vertical axes, `y` lists constant-Y horizontal axes, and `bounds_mm` supplies
`[xmin,ymin,xmax,ymax]`. Names and coordinates are explicit; no classroom
numbering convention is inferred. The fixture's FootPrint uses the same curves
as the IfcGridAxis records. The tested clean model retains Levels and Axes and
removes the temporary generic import carriers.

Native Axis type, names and persistent identities are inspected directly.
**Coordinate verification uses a separate fresh IFC export from the reopened
native project**, checking the resulting axes against the requested positions,
orientation and extents. It does not read the original input as proof of saved
geometry, nor claim a native Axis baseline getter where none was established.
The extension scenario also renames a native axis through `GridLineName` and
checks that the new name appears in a subsequent fresh export. These findings
do not establish a general constructor or geometric setter for arbitrary axes
inside an existing model, curved grids, drawing axes or dimension associations.
[Annotation investigation](ANNOTATION_API_RESEARCH.md),
[grid validation](../src/renga_codex_bridge/grid_spec.py),
[saved export verifier](../src/renga_codex_bridge/ifc_grid_verify.py).

## Template route and exclusions

`IApplication.CreateProjectFromTemplate(BSTR fileName, out int pResult)` is
another documented new-project route. It can preserve levels already present
in an authorized user-supplied template. The template needs inspection before
and after creation, a new protected destination and native save/reopen checks.
This does not create an arbitrary requested elevation or justify publishing a
vendor template. A template generated from a successfully imported synthetic
project would be a separate subsequent test.
[IApplication.CreateProjectFromTemplate](https://help.rengabim.com/api/interface_i_application.html#a32a3ebea1db47d584056cf5a8d7de591).

The public `IModel` interface does not expose copy/clone or paste operations.
`IEntityCollection.Create` manages documented resource collections, not a Level
collection. STDL category import creates supported MEP categories and style
templates; no level-creation STDL contract was found. No undocumented COM
dispatch names, UI commands, clipboard automation, registry edits or native
`.rnp` database patching are proposed as supported workarounds.
[IModel](https://help.rengabim.com/api/interface_i_model.html),
[IEntityCollection](https://help.rengabim.com/api/interface_i_entity_collection.html),
[IProject](https://help.rengabim.com/api/interface_i_project.html).
