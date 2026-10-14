# Notices and third-party components

Renga–Codex Bridge is an independent, unofficial integration. It is not produced,
endorsed or supported by the Renga rights holder or OpenAI. Product names and
trademarks belong to their respective owners.

The repository's original integration code is distributed under the existing
[MIT license](LICENSE). This license does not license Renga, its API/SDK files,
or any other vendor software.

## Runtime dependencies

Dependencies are installed separately by Python's package manager. Preserve
their own notices when redistributing a built environment. Exact runtime pins
are declared in `pyproject.toml`/the dependency lock; the current source design
uses the following components:

| Component | Purpose | Upstream license |
|---|---|---|
| [Python](https://www.python.org/) | Runtime, separately installed | PSF license |
| [comtypes](https://github.com/enthought/comtypes) | Typed COM interop | MIT |
| [pywin32](https://github.com/mhammond/pywin32) | Windows process/COM diagnostics | Python Software Foundation style license in upstream source |
| [MCP Python SDK](https://github.com/modelcontextprotocol/python-sdk) | Local stdio MCP transport | MIT |
| [pytest](https://github.com/pytest-dev/pytest) | Test-only dependency | MIT |
| [pypdf](https://github.com/py-pdf/pypdf) | Test-only PDF verification | BSD-3-Clause |
| [build](https://github.com/pypa/build) | Test-only package build frontend | MIT |
| [setuptools](https://github.com/pypa/setuptools) | Build backend | MIT |
| [wheel](https://github.com/pypa/wheel) | Build dependency | MIT |

Transitive dependency versions and licenses need review when dependency locks
change. This table is an inventory of direct dependencies, not a sublicense of
their code. Full upstream research and commit identifiers are recorded in
`docs/REPOSITORY_RESEARCH.md`.

## Renga and SDK

Users must obtain, install and license Renga separately under the vendor's
terms. Obtain the SDK from [Renga](https://rengabim.com/sdk/) and provide a local
path. The repository and release must not include Renga installers, proprietary
DLL/TLB files, activation material or SDK archives. Runtime COM wrappers are
generated locally and excluded from Git.

Repositories studied as research sources are not automatically dependencies or
sources of copied code. In particular, rnpmcp, RengaInspector, ModelExplorer,
StyleTemplateSamples, IFCMappingFiles and IfcOpenShell must not be incorporated
without recording the particular files, license obligations and technical need.
Use their public interfaces or independent implementation when copying rights
are unclear. Do not infer redistribution permission from a publicly accessible
repository or download.
