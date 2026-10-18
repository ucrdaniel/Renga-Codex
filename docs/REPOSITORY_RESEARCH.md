# Repository research

Research date: 2026-10-14. This document records source inspection, not a claim that upstream programs were run against Renga during this review. No Computer Use, COM connection, upstream script execution or SDK redistribution was used for the research.

Seven repositories were examined at the commits below. Build configuration, relevant implementation files, test sources, licenses and current open-issue metadata were inspected. For the large IfcOpenShell monorepo the source review is scoped to Python IFC parsing, validation, geometry and units, their tests and CI; it is not an audit of every application in that repository. Issue counts are a dated snapshot, not a measure of correctness. GitHub's repository-level count includes pull requests.

## Versions and distribution decision

| Repository | Exact researched commit | License found | Decision for Bridge 0.1 |
|---|---|---|---|
| [proovcme/rnpmcp](https://github.com/proovcme/rnpmcp) | `8051cc7037ffa4314fddd9b04f35c9c8069e182e` | MIT for its original code; separate vendor exclusions in NOTICE | Architecture reference; no upstream source copied |
| [RengaSoftware/SampleScripts](https://github.com/RengaSoftware/SampleScripts) | `c626cbfbdc72eac0be9019106235193143fd6832` | MIT | API examples; do not execute unchanged against user sessions |
| [RengaSoftware/ModelExplorer](https://github.com/RengaSoftware/ModelExplorer) | `41b364c120a17cfbd1fdf4689d525f6f7fb66829` | Own code MIT; bundled QtPropertyBrowser has distinct LGPL/GPL/commercial terms | Inspection patterns only; exclude Qt/UI and bundled third-party code |
| [karpovichpv/RengaInspector](https://github.com/karpovichpv/RengaInspector) | `a350d7723ad69af8eb07690d25efddeed5209bbb` | No license file or grant found in the researched tree; GitHub license metadata is null | Research only; do not copy, vendor or redistribute its source/binaries |
| [RengaSoftware/StyleTemplateSamples](https://github.com/RengaSoftware/StyleTemplateSamples) | `3878525cf191355d4957cf198f8f8f762e074744` | MIT | Optional STDL reference; not a required runtime dependency |
| [RengaSoftware/IFCMappingFiles](https://github.com/RengaSoftware/IFCMappingFiles) | `ca38f9e1be6d19563b2c8eae3a12b1f9c643dd45` | MIT | Mapping reference; use the installed mapping/configuration unless explicitly replaced |
| [IfcOpenShell/IfcOpenShell](https://github.com/IfcOpenShell/IfcOpenShell) | `250532b637b233e1ca3e943d11975605f3b74a52` | Reviewed Python component LGPL-3.0-or-later; other applications have separate licensing | Optional separately installed IFC validator; no source vendoring |

The commit identifies reviewed source, not the version of a runtime dependency. IfcOpenShell's PyPI metadata reported release `0.9.0` during this review; its repository `pyproject.toml` uses a build-time `0.0.0` placeholder. A runtime wheel must be pinned and tested separately. [Package metadata](https://pypi.org/pypi/ifcopenshell/json), [source packaging](https://github.com/IfcOpenShell/IfcOpenShell/blob/250532b637b233e1ca3e943d11975605f3b74a52/src/ifcopenshell-python/pyproject.toml).

## 1. rnpmcp: useful transport and threading, incomplete lifecycle

The server separates tools, contracts, an `IRengaAdapter`, real/mock adapters and a serial STA worker. `Program.cs` reserves stdout for MCP and sends diagnostics to stderr. Build settings target Windows x64 / .NET 8. Package references are `ModelContextProtocol 2.2.0` and `Microsoft.Extensions.Hosting 8.0.1`. [Program](https://github.com/proovcme/rnpmcp/blob/8051cc7037ffa4314fddd9b04f35c9c8069e182e/src/RengaMcp.Server/Program.cs), [project](https://github.com/proovcme/rnpmcp/blob/8051cc7037ffa4314fddd9b04f35c9c8069e182e/src/RengaMcp.Server/RengaMcp.Server.csproj), [STA worker](https://github.com/proovcme/rnpmcp/blob/8051cc7037ffa4314fddd9b04f35c9c8069e182e/src/RengaMcp.Server/Infrastructure/StaWorker.cs).

Its adapter discovers existing Renga instances through ROT and attaches to a selected PID. It exposes project/object inspection, styles, ports, object creation, parameter updates and pipe connections. Writes default to a real transaction followed by rollback; committed operations call Apply. Creation populates type, host, style and category, but supplies no exact placement or baseline. There are no project-open/save/close tools or independent save/reopen checks. Some undo creation falls back to a transaction without an undo item when late binding cannot marshal the model GUID. [Adapter](https://github.com/proovcme/rnpmcp/blob/8051cc7037ffa4314fddd9b04f35c9c8069e182e/src/RengaMcp.Server/Adapters/DynamicComRengaAdapter.cs), [dispatch](https://github.com/proovcme/rnpmcp/blob/8051cc7037ffa4314fddd9b04f35c9c8069e182e/src/RengaMcp.Server/Infrastructure/ComDispatch.cs), [contract](https://github.com/proovcme/rnpmcp/blob/8051cc7037ffa4314fddd9b04f35c9c8069e182e/src/RengaMcp.Server/Adapters/IRengaAdapter.cs).

The tree contains ten xUnit facts: nine mock-adapter checks and one ROT-name parser test. CI runs build/tests on Windows with .NET 8. These tests establish mock/contract behaviour, not persistence in a real BIM file. The README reports upstream live stdio/MEP checks; this review did not reproduce them. No open issues or pull requests were returned at collection time. [Tests](https://github.com/proovcme/rnpmcp/tree/8051cc7037ffa4314fddd9b04f35c9c8069e182e/tests/RengaMcp.Tests), [CI](https://github.com/proovcme/rnpmcp/blob/8051cc7037ffa4314fddd9b04f35c9c8069e182e/.github/workflows/ci.yml), [upstream claims](https://github.com/proovcme/rnpmcp/blob/8051cc7037ffa4314fddd9b04f35c9c8069e182e/README.md).

Reuse the adapter boundary, serialization and preview concept. Develop owned-process lifecycle, backups, typed record handling, geometric operations and persisted verification independently. MIT permits reuse with its notice retained; NOTICE does not grant rights to Renga SDK or generated vendor interop assemblies. No source has been copied into this product. [License](https://github.com/proovcme/rnpmcp/blob/8051cc7037ffa4314fddd9b04f35c9c8069e182e/LICENSE), [NOTICE](https://github.com/proovcme/rnpmcp/blob/8051cc7037ffa4314fddd9b04f35c9c8069e182e/NOTICE.md).

## 2. SampleScripts: concrete property and export contracts

The Python scripts use `pywin32`, register typed custom properties and expressions, select drawings by topic, sort by sheet number, and export PDF/OXPS/DWG. The drawing exporter demonstrates `Drawings2` and `ExportDrawingsToPdfS`, useful evidence that PDF export is a documented API operation. [Property script](https://github.com/RengaSoftware/SampleScripts/blob/c626cbfbdc72eac0be9019106235193143fd6832/CreateProperties/create_properties.py), [drawing export](https://github.com/RengaSoftware/SampleScripts/blob/c626cbfbdc72eac0be9019106235193143fd6832/ExportDrawings/export_topic_drawings.py).

Both scripts construct `Dispatch("Renga.Application.1")`, close the project and quit the application. They do not prove that the process belongs to the script, create verified backups or reopen saved output. The property script also compares optional `result_project` to `0`, so its missing-output-path branch should not be copied blindly. No automated tests or dependency lock were found; no open issues/PRs were returned. Keep API sequences, replace lifecycle/error handling, and test each exported format independently. [MIT license](https://github.com/RengaSoftware/SampleScripts/blob/c626cbfbdc72eac0be9019106235193143fd6832/LICENSE).

## 3. ModelExplorer: broad inspection, not an automation backend

This C++ plugin traverses building/assembly objects, parameters, quantities, materials and properties, and edits supported property values. `EntityPropertyViewBuilder.cpp`, `QtPropertiesConstruction.cpp` and `RengaModelUtils.cpp` show that model discovery should follow actual interface/container availability, not a fixed list of localised UI names. Build configuration uses x64 Visual C++ toolset v143, local Renga SDK and Qt 5; README names Qt 5.9.3. [Builder](https://github.com/RengaSoftware/ModelExplorer/blob/41b364c120a17cfbd1fdf4689d525f6f7fb66829/ModelExplorerPlugin/EntityPropertyViewBuilder.cpp), [model traversal](https://github.com/RengaSoftware/ModelExplorer/blob/41b364c120a17cfbd1fdf4689d525f6f7fb66829/ModelExplorerPlugin/RengaModelUtils.cpp), [build](https://github.com/RengaSoftware/ModelExplorer/blob/41b364c120a17cfbd1fdf4689d525f6f7fb66829/ModelExplorerPlugin/ModelExplorerPlugin.vcxproj).

No automated test suite was found. Eighteen open issues were returned; relevant reports include crashes after IFC import, enum IDs displayed instead of names, and unset doubles displayed as zero. They motivate defensive, typed inspection and explicit `has_value`, not assumptions that corresponding Renga APIs are unavailable. [Issue 46](https://github.com/RengaSoftware/ModelExplorer/issues/46), [issue 38](https://github.com/RengaSoftware/ModelExplorer/issues/38), [issue 13](https://github.com/RengaSoftware/ModelExplorer/issues/13).

Its own license is MIT, but the bundled QtPropertyBrowser header has separate LGPL-2.1/GPL-3/commercial terms and exceptions. Do not copy that directory into an MIT-only distribution. No Qt component is needed for a stdio bridge. [Own license](https://github.com/RengaSoftware/ModelExplorer/blob/41b364c120a17cfbd1fdf4689d525f6f7fb66829/License.txt), [third-party header](https://github.com/RengaSoftware/ModelExplorer/blob/41b364c120a17cfbd1fdf4689d525f6f7fb66829/QtPropertyBrowser/qtpropertybrowser.h).

## 4. RengaInspector: useful discovery evidence, no reuse grant

The .NET 8 x64 WPF plugin reflects over interop interfaces and supplements them with special collectors for containers, placements and curves. Its project references a local COM type library and `Renga.NET8.PluginUtility.dll`; `CommunityToolkit.Mvvm` is pinned to 8.4.0. Inspection helpers are evidence of viable typed C# traversal, not evidence that every reflected property is writable. [Collector](https://github.com/karpovichpv/RengaInspector/blob/a350d7723ad69af8eb07690d25efddeed5209bbb/Inspector/Domain/ChiefCollector.cs), [parameters](https://github.com/karpovichpv/RengaInspector/blob/a350d7723ad69af8eb07690d25efddeed5209bbb/Inspector/Domain/Helpers/ParametersDataGetter.cs), [project](https://github.com/karpovichpv/RengaInspector/blob/a350d7723ad69af8eb07690d25efddeed5209bbb/Inspector/Inspector.csproj).

No automated tests or explicit license were found. Eight open issues include empty parameter/quantity containers and quantity units; an issue about a window is insufficient evidence to declare Renga window creation unsupported. README also notes slow full-model loading. Use these as discovery/performance concerns; implement our own bounded pagination and typed container handling. No Inspector source, UI, screenshots or binary is included. [Issues](https://github.com/karpovichpv/RengaInspector/issues), [unit handling issue](https://github.com/karpovichpv/RengaInspector/issues/10), [README](https://github.com/karpovichpv/RengaInspector/blob/a350d7723ad69af8eb07690d25efddeed5209bbb/readme.md).

## 5. StyleTemplateSamples: optional parametric style extension

The JSON/Lua pairs demonstrate STDL parameter schemas, detailed/symbolic native geometry, materials, ports and reinforcement templates. GasStove's schema supplies dimensions; its Lua creates solids and 2D symbols through `Style.SetDetailedGeometry` and `Style.SetSymbolicGeometry`. These are Renga style templates, not a general-purpose replacement for the COM model/documentation API. [Schema](https://github.com/RengaSoftware/StyleTemplateSamples/blob/3878525cf191355d4957cf198f8f8f762e074744/GasStove/GasStove.json), [implementation](https://github.com/RengaSoftware/StyleTemplateSamples/blob/3878525cf191355d4957cf198f8f8f762e074744/GasStove/GasStove.lua), [reinforcement example](https://github.com/RengaSoftware/StyleTemplateSamples/blob/3878525cf191355d4957cf198f8f8f762e074744/ReinforcingMesh/ReinforcingMesh.lua).

Samples have metadata version 1.0.0, but that is not a minimum Renga/API version guarantee. No test harness or open issues/PRs were found. Add import/edit tools only after version-specific native tests. No dependency is needed for the initial server; selected future templates may be reused with MIT attribution. [License](https://github.com/RengaSoftware/StyleTemplateSamples/blob/3878525cf191355d4957cf198f8f8f762e074744/LICENSE), [STDL documentation](https://help.rengabim.com/stdl/en/index.html).

## 6. IFCMappingFiles: export configuration, not a geometry engine

Three JSON files map native entity types, attributes/property sets/quantities, and layers to IFC. The researched files declare mapping format version 4. `export_type.json` includes space, wall, beam, roof and grid-axis mappings. This can explain IFC export differences and identify the active configuration; it cannot create missing native Renga objects. [Type mapping](https://github.com/RengaSoftware/IFCMappingFiles/blob/ca38f9e1be6d19563b2c8eae3a12b1f9c643dd45/export_type.json), [attributes and quantities](https://github.com/RengaSoftware/IFCMappingFiles/blob/ca38f9e1be6d19563b2c8eae3a12b1f9c643dd45/export_attr_qto_pset.json), [layers](https://github.com/RengaSoftware/IFCMappingFiles/blob/ca38f9e1be6d19563b2c8eae3a12b1f9c643dd45/export_layer.json).

No automated tests or open issues/PRs were found. MIT allows attributed reuse, but automatically replacing files in the Renga installation is not an acceptable default. Record the installed mapping/version/hash for export tests; accept user-selected overrides through documented configuration. [License](https://github.com/RengaSoftware/IFCMappingFiles/blob/ca38f9e1be6d19563b2c8eae3a12b1f9c643dd45/LICENSE).

## 7. IfcOpenShell: independent exported-file verification

The Python package provides IFC parsing, schema validation, entity/property queries, geometric shapes/iterators and unit/placement utilities. Relevant source: `ifcopenshell/validate.py`, `geom/main.py`, and `util`; tests include validation fixtures, SI/file-unit placement cases and unit assignment. CI builds and tests core/Python components. [Validator](https://github.com/IfcOpenShell/IfcOpenShell/blob/250532b637b233e1ca3e943d11975605f3b74a52/src/ifcopenshell-python/ifcopenshell/validate.py), [validation tests](https://github.com/IfcOpenShell/IfcOpenShell/blob/250532b637b233e1ca3e943d11975605f3b74a52/src/ifcopenshell-python/test/test_validate.py), [placement tests](https://github.com/IfcOpenShell/IfcOpenShell/blob/250532b637b233e1ca3e943d11975605f3b74a52/src/ifcopenshell-python/test/api/geometry/test_edit_object_placement.py), [unit tests](https://github.com/IfcOpenShell/IfcOpenShell/blob/250532b637b233e1ca3e943d11975605f3b74a52/src/ifcopenshell-python/test/api/unit/test_assign_unit.py).

The reviewed source package requires Python 3.11–3.15 and depends on NumPy, Shapely, isodate, python-dateutil, Lark, pyparsing and typing-extensions. Released-wheel requirements may differ; query the pinned wheel rather than treating HEAD as an install lock. Core optional verification should read a native Renga export; IFC authoring must not be presented as a native editable Renga replacement.

The repository had 2030 open issues/PRs; only the latest page and relevant reports were reviewed. Issue 9926 reports geometry remaining in millimetres with an `IfcProjectLibrary` lacking units in version 0.9.0. A verifier must check unit scale and representation explicitly. Issue 9922 concerns Bonsai profile handling and must not be generalised to every core IFC operation. [Unit-scale report](https://github.com/IfcOpenShell/IfcOpenShell/issues/9926), [Bonsai report](https://github.com/IfcOpenShell/IfcOpenShell/issues/9922).

Reviewed Python sources and packaging specify LGPL-3.0-or-later. MIT can cover our independent caller while the external component retains its license and obligations; LGPL source must not be relabelled MIT. Keep the package optional and separately installed, record version/license, and avoid distributing a combined bundle in 0.1. The monorepo also contains differently licensed applications such as Bonsai, which are excluded. [Python license header](https://github.com/IfcOpenShell/IfcOpenShell/blob/250532b637b233e1ca3e943d11975605f3b74a52/src/ifcopenshell-python/ifcopenshell/__init__.py), [LGPL terms](https://github.com/IfcOpenShell/IfcOpenShell/blob/250532b637b233e1ca3e943d11975605f3b74a52/COPYING.LESSER), [Bonsai license](https://github.com/IfcOpenShell/IfcOpenShell/blob/250532b637b233e1ca3e943d11975605f3b74a52/src/bonsai/COPYING).

## Vendor boundary and evidence

The official API documentation is the primary interface specification; the SDK is obtained separately by each user. Renga's EULA section 3.5 permits integration development, while 3.5.6 restricts transfer of SDK/API components. The Bridge's MIT license does not grant rights to Renga, its SDK, binaries, type library, vendor documentation or activation files. Generated wrappers belong in an untracked local cache, not a release archive. [API](https://help.rengabim.com/api/), [SDK download](https://rengabim.com/sdk/), [EULA sections 3.5–3.5.6](https://rengabim.com/files/eula_ru-ru.pdf).

Private research clones, raw issue snapshots and previous user models are not part of this repository. Public evidence here consists of commit-pinned references and independently written conclusions. Upstream test existence, README claims and successful COM return values never promote a Bridge feature to `IMPLEMENTED_AND_TESTED`; that status requires our own recorded native test and saved-output checks.

## Development schema dependency review, 2026-10-17

The four strict existing-resource/sheet-addition transport contracts use the
separately installed Pydantic 2.14.1 public model/field/validator APIs. Its
installed package metadata records the MIT license. This exact version was
already present in the reference lock and is now explicit in the runtime
requirements because Bridge source imports it directly. Schema verification
uses installed jsonschema 4.26.0 (MIT package metadata), already required by
MCP 2.3.0. No Pydantic/jsonschema source or binary is copied into this repository.

The pinned MCP 2.3.0 tool decorator has no argument-model configuration hook.
A narrow registration seam rebuilds only the four new generated argument
models with `extra='forbid'` and `strict=True`, then regenerates their schemas.
This prevents advertising closed schemas while silently dropping extra input.
Portable registry tests and fresh stdio schema discovery cover that seam; a
future MCP upgrade requires reviewing it. This uses installed SDK objects;
it does not copy upstream implementation code.

Краткий вывод: расширять архитектурные идеи rnpmcp полезно, но его ROT-сессии и позднее связывание не заменяют проверенный жизненный цикл и точную геометрию. Для 0.1 выбран собственный Python-мост с типизированным COM; C# возможен как следующий адаптер. Код без лицензии, Qt-компоненты, SDK и пользовательские модели в публичную поставку не входят.
