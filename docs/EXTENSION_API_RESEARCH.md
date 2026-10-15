# Extension routes for levels and associative annotations

Research date: **2026-10-15**. Scope: the locally installed **API 2.50** SDK,
its C++ plugin entry point, public COM references, and current official STDL
documentation. Source research itself performed no COM activation, Computer
Use, vendor sample execution or user-model access. The native findings below
come from the bridge's separate owned-process tests on synthetic models. The
reproducible scenario and final release evidence remain separate from source
discovery; their coverage is limited to the tested Renga version and operations.

## C++ and C# plugins use the same public model contract

The official overview describes one COM API whose interfaces are defined by
the SDK type library. C++ and .NET plugins run inside Renga; Python runs outside
it. The SDK utility header `IPlugin.h` only declares plugin initialization and
shutdown. It supplies no separate level, axis, dimension or tag factory.
Changing the implementation language therefore does not, by itself, establish
an additional modelling capability. In-process execution may still be useful
for an interface whose COM marshalling is unavailable; that is a separate issue
from a missing constructor or setter.
[API overview](https://help.rengabim.com/api/overview-api-sdk-plugin.html),
[plugin contract](https://help.rengabim.com/api/class_renga_1_1_i_plugin.html).

The plugin guide documents a `.rndesc` descriptor and C++/.NET Framework/.NET 8
libraries loaded on application startup. A .NET plugin references the user's
local TLB and the matching utility assembly. The guide does not document a
privileged alternative scene database or built-in-tool command protocol.
[Plugin implementation](https://help.rengabim.com/api/how-to-implement-a-plugin.html).

## Candidate routes and what they would prove

| Route | Public contract | Useful conclusion and remaining check |
|---|---|---|
| Level creation arguments | `IModel.CreateObject` supports Level; `INewEntityArgs.Placement3D` applies to level-based objects | Test Level itself separately: the existence of this field does not promise that a Level consumes its Z coordinate |
| Level placement mutation | `ILevel.Elevation` and `ILevel.Placement` are getters; `IPlacement3D` has mutating coordinate-system methods | A changed returned coordinate system is insufficient. Read the Level again, then save/reopen and compare elevation and origin |
| Level generic parameters | SDK declares `LevelElevation` and `LevelName` GUIDs | Inspect actual parameter presence, type and `IsReadOnly`; GUID discovery is not a setter contract |
| IFC bootstrap | `IApplication.ImportIfcProject` creates a project from IFC | Native Levels at 0/3000/6000 mm survived save/reopen; a fresh native wall on +3000 mm had mesh Z=3000–5800 mm. Clean bootstrap removes generic carriers before saving. New projects only; direct elevation editing remains read-only |
| IFC grid import | Same import entry point with own `IfcGrid` / `IfcGridAxis` | Genuine native Axis objects and persistent identities survived save/reopen. Coordinates are verified through a separate fresh IFC export from that reopened native file, not an unestablished direct Axis baseline getter. Explicit orthogonal grids in new projects only |
| Template bootstrap | `CreateProjectFromTemplate` creates a project from an existing template | Can preserve previously authored levels/annotations. Does not establish arbitrary level or annotation generation; must inspect and verify a caller-provided template |
| Transfer into an existing project | No general native copy/merge operation found in the examined `IModel`, `IModelObject`, `IProject` interfaces | IFC/bootstrap and templates create new projects, not an arbitrary edit to an existing project. Clipboard/UI instructions do not constitute an API transfer contract |
| Axis/dimension/tag direct creation | Entity GUIDs exist, but these types are absent from the `IModel.CreateObject` support table | Probe only on disposable files and report actual rejection. No documented endpoint, defining-feature, target-binding or annotation factory was found |

Sources: [IModel](https://help.rengabim.com/api/interface_i_model.html),
[construction arguments](https://help.rengabim.com/api/interface_i_new_entity_args.html),
[ILevel](https://help.rengabim.com/api/interface_i_level.html),
[IPlacement3D](https://help.rengabim.com/api/interface_i_placement3_d.html),
[parameters](https://help.rengabim.com/api/group___parameters.html),
[IApplication](https://help.rengabim.com/api/interface_i_application.html).

The official application help distinguishes IFC conversion from linked IFC
models and warns that not all imported objects become native Renga objects.
For any IFC route, tests must inspect native identities/interfaces rather than
use appearance or successful import as proof. Placement units and nested IFC
local placements must be explicit in the source fixture.
[Open project](https://help.rengabim.com/en/Content/open.htm),
[conversion limitations](https://help.rengabim.com/en/Content/edit_ifc.htm).

`ImportIfcProject` and `CreateProjectFromTemplate` require that no project is
already open. They should run in a new bridge-owned session with a fresh output
path. Replacing a user's existing project by an imported reconstruction would
not be an acceptable silent implementation of "add a level".
[IApplication](https://help.rengabim.com/api/interface_i_application.html).

## Native outcome and remaining annotation boundaries

The new bootstrap implements the successful IFC conversion route in
[level_projects.py](../src/renga_codex_bridge/level_projects.py), with pure
own-source IFC generation and strict explicit level/grid specifications. Native
Level heights and origin Z are read directly; native Axis type/name/identity
and fresh exported grid coordinates are checked independently. Temporary
generic carriers are deleted, and the saved project must contain only the
requested native Levels and optional native Axes. Creating a new native Wall
on an imported +3000 mm Level establishes that further model creation can use
that Level as its real host. The final extension suite also exercises negative
and fractional elevations and names containing Unicode/apostrophes.
[Level route research](LEVEL_API_RESEARCH.md),
[reproducible native scenarios](../scripts/run_level_annotation_tests.py).

This success does not remove the direct `LevelElevation` parameter's read-only
restriction and does not insert levels/grids into an existing arbitrary model.
It does not generalize to all IFC objects: the synthetic carrier geometry can
import as generic objects and is deliberately removed. The previously tested
detached placement mutation still is not a native elevation setter.

For markers, `IRoom.MarkerPosition` supplies a separate direct API operation.
The bridge saves and reads the intrinsic room marker's global XY point after
reopening the same native room, preserving its contour and area. This moves a
room's own marker; it does not create a standalone `Tag` or a host-derived tag
expression. Constructor probes in building and drawing models exercise Axis,
DrawingAxis, LinearDimension, Tag and DrawingElevationMark; rejected factories
remain negative evidence, not newly supported annotations. In particular,
imported axes do not imply computed dimension or standalone Tag creation.
[Marker and annotation investigation](ANNOTATION_API_RESEARCH.md).

## STDL is not a general model scripting API

Official STDL v4.3 documentation describes Lua/JSON style templates, geometry,
ports, engineering categories and reinforcement. Its supported category list
does not contain native Level, Axis, LinearDimension or Tag. Drawing geometry
inside a style would not supply associative model dimensions or target-bound
tags. `IProject.ImportCategory` imports an STDL category, not an arbitrary
building-model object.
[STDL overview](https://help.rengabim.com/stdl/en/index.html),
[ImportCategory](https://help.rengabim.com/api/interface_i_project.html).

## Do not confuse nearby interfaces with annotation creation

`IObjectWithMark.Mark` changes an object's mark value, not a drawing Tag
instance. `IRoom.MarkerPosition` is a room annotation-related coordinate, not
a general Tag factory. Existing computed LinearDimension values can be read
through parameters; creating a text override does not establish a computed
dimension. The dimension-specific findings are in
[DIMENSION_API_RESEARCH.md](DIMENSION_API_RESEARCH.md).

`IAction.Trigger` triggers the event assigned to an API action. Its documentation
does not expose a dispatcher for invoking a built-in level/axis/dimension/tag
construction tool with geometric arguments. Installing event handlers or
triggering a developer-created action would still need a supported model API
inside the handler.
[IAction](https://help.rengabim.com/api/interface_i_action.html),
[IUI](https://help.rengabim.com/api/interface_i_u_i.html).

## Distribution boundary

The release ships independently written integration code and research links.
Each user supplies their own compatible Renga installation and SDK. EULA
section 3.5 permits integration development, while 3.5.6 restricts transferring
SDK/API components. Do not add the vendor TLB, utility assemblies, SDK headers,
generated vendor wrappers, vendor documentation or application binaries to Git
or release packages. A future independently written C# plugin would retain this
boundary and load against the user's local installation.
[Vendor EULA, sections 3.5–3.5.6](https://rengabim.com/files/eula_ru-ru.pdf).

Native-file patching, guessed private interfaces, DLL injection, undocumented
window messages and UI/keyboard/mouse automation are not verified SDK routes
for this product. No such technique is proposed as a way to promote an API
limitation to tested support.

Кратко: официальный импорт собственного IFC уже дал настоящие ненулевые Level
и Axis с сохранением в `.rnp`. Это создание нового проекта с последующей
проверкой и удалением временной геометрии, а не изменение отметки существующего
уровня. Положение встроенного маркера помещения меняется отдельным API-вызовом.
Создание ассоциативных размеров и самостоятельных Tag этим не подтверждено.
Сам переход на C++/C# или STDL недостающие конструкторы не предоставляет.
