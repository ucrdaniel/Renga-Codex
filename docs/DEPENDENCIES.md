# Dependency inventory and Windows environment snapshot

Snapshot date: **2026-10-14**. Environment: **Windows x64, CPython 3.12.14**,
the bridge's local product-test environment. This inventory was read from
installed distribution metadata without importing Renga COM or opening a model.
It does not itself certify that the native integration test suite passed.
Current native evidence belongs in [CAPABILITIES.md](CAPABILITIES.md).

The snapshot contains **39 third-party Python distributions**: three direct
runtime dependencies, 27 runtime transitive dependencies, three direct optional
test/build dependencies, and six test/build transitive dependencies. The bridge's
own editable package and `pip` are excluded. No installation paths, editable
URLs, user configuration, raw logs or SDK components are included.

Кратко: ниже — фактически установленные версии и сведения о лицензиях из
метаданных пакетов. Это перечень зависимостей, а не юридическое заключение.
Lock-файл фиксирует одну среду Windows/Python 3.12; переносимость на другие
версии Python и ОС устанавливается отдельными проверками.

## Source and scope

- Names, versions, `License-Expression`, legacy `License` and project URLs were
  read using `importlib.metadata`. A dash means the field was not recorded,
  rather than a finding that the project has no license.
- Roles follow the roots declared in `pyproject.toml`. Transitive reachability
  was evaluated for this installed environment, including requested extras
  such as `PyJWT[crypto]`. HTTP/ASGI packages are MCP SDK dependencies; their
  presence does not mean that this bridge exposes a network server.
- The table retains a selected recorded upstream URL. It is not evidence that
  every upstream license file or binary notice was audited. The table reflects
  the installed wheel metadata, not a newest-release recommendation.
- This is a Python distribution inventory, **not** a complete native-library
  SBOM of compiled wheels. Embedded libraries and individual file notices need
  their own review before distributing a bundled environment.

## Installed direct and transitive dependencies

| Distribution | Installed version | Role | License-Expression | Legacy License | Selected recorded project URL |
|---|---|---|---|---|---|
| annotated-types | 0.8.0 | transitive runtime | MIT | — | [Source](https://github.com/annotated-types/annotated-types) |
| anyio | 4.15.1 | transitive runtime | MIT | — | [Source code](https://github.com/agronholm/anyio) |
| attrs | 26.1.0 | transitive runtime | MIT | — | [GitHub](https://github.com/python-attrs/attrs) |
| build | 1.6.1 | direct test | MIT | — | [source](https://github.com/pypa/build) |
| cffi | 2.1.1 | transitive runtime | MIT-0 | — | [Source Code](https://github.com/python-cffi/cffi) |
| click | 8.5.0 | transitive runtime | BSD-3-Clause | — | [Source](https://github.com/pallets/click/) |
| colorama | 0.4.6 | transitive test | — | — | [Homepage](https://github.com/tartley/colorama) |
| comtypes | 1.4.17 | direct runtime | MIT | — | [Source](https://github.com/enthought/comtypes) |
| cryptography | 50.0.2 | transitive runtime | Apache-2.0 OR BSD-3-Clause | — | [source](https://github.com/pyca/cryptography/) |
| h11 | 0.16.0 | transitive runtime | — | MIT | [Homepage](https://github.com/python-hyper/h11) |
| httpcore2 | 2.13.1 | transitive runtime | BSD-3-Clause | — | [Source](https://github.com/pydantic/httpx2/blob/main/src/httpcore2) |
| httpx2 | 2.13.1 | transitive runtime | BSD-3-Clause | — | [Source](https://github.com/pydantic/httpx2) |
| idna | 3.20 | transitive runtime | BSD-3-Clause | — | [Source](https://github.com/kjd/idna) |
| iniconfig | 2.3.1 | transitive test | MIT | — | [Homepage](https://github.com/pytest-dev/iniconfig) |
| jsonschema | 4.26.0 | transitive runtime | MIT | — | [Source](https://github.com/python-jsonschema/jsonschema) |
| jsonschema-specifications | 2025.9.1 | transitive runtime | MIT | — | [Source](https://github.com/python-jsonschema/jsonschema-specifications) |
| mcp | 2.3.0 | direct runtime | — | MIT | [Repository](https://github.com/modelcontextprotocol/python-sdk) |
| mcp-types | 2.3.0 | transitive runtime | — | MIT | [Repository](https://github.com/modelcontextprotocol/python-sdk) |
| opentelemetry-api | 1.45.1 | transitive runtime | Apache-2.0 | — | [Repository](https://github.com/open-telemetry/opentelemetry-python) |
| packaging | 26.3 | transitive test | Apache-2.0 OR BSD-2-Clause | — | [Source](https://github.com/pypa/packaging) |
| pluggy | 1.6.0 | transitive test | — | MIT | — |
| pycparser | 3.11 | transitive runtime | BSD-3-Clause | — | [Homepage](https://github.com/eliben/pycparser) |
| pydantic | 2.14.1 | transitive runtime | MIT | — | [Source](https://github.com/pydantic/pydantic) |
| pydantic_core | 2.50.1 | transitive runtime | MIT | — | [Source](https://github.com/pydantic/pydantic/tree/main/pydantic-core) |
| Pygments | 2.21.0 | transitive test | BSD-2-Clause | — | [Source](https://github.com/pygments/pygments) |
| PyJWT | 2.15.1 | transitive runtime | MIT | — | [Homepage](https://github.com/jpadilla/pyjwt) |
| pypdf | 6.20.1 | direct test | BSD-3-Clause | — | [Source](https://github.com/py-pdf/pypdf) |
| pyproject_hooks | 1.3.3 | transitive test | MIT | — | [Source](https://github.com/pypa/pyproject-hooks) |
| pytest | 9.1.1 | direct test | MIT | — | [Source](https://github.com/pytest-dev/pytest) |
| python-multipart | 0.0.32 | transitive runtime | Apache-2.0 | — | [Source](https://github.com/Kludex/python-multipart) |
| pywin32 | 312 | direct runtime | — | PSF | [Homepage](https://github.com/mhammond/pywin32) |
| referencing | 0.37.0 | transitive runtime | MIT | — | [Source](https://github.com/python-jsonschema/referencing) |
| rpds-py | 2026.9.1 | transitive runtime | MIT | — | [Source](https://github.com/crate-py/rpds) |
| sse-starlette | 3.5.0 | transitive runtime | BSD-3-Clause | — | [Source](https://github.com/sysid/sse-starlette) |
| starlette | 1.8.0 | transitive runtime | BSD-3-Clause | — | [Source](https://github.com/Kludex/starlette) |
| truststore | 0.10.5 | transitive runtime | MIT | — | [Source](https://github.com/sethmlarson/truststore) |
| typing-inspection | 0.4.4 | transitive runtime | MIT | — | [Source](https://github.com/pydantic/typing-inspection) |
| typing_extensions | 4.16.0 | transitive runtime | PSF-2.0 | — | [Repository](https://github.com/python/typing_extensions) |
| uvicorn | 0.54.0 | transitive runtime | BSD-3-Clause | — | [Source](https://github.com/Kludex/uvicorn) |

Direct runtime requirements are `comtypes==1.4.17` and `pywin32==312` under
Windows markers, plus `mcp==2.3.0`. The optional `test` group declares
`pytest==9.1.1`, `pypdf==6.20.1` and `build==1.6.1`; the table gives their actual
installed versions. The upstream dependency licenses remain theirs; the bridge's
MIT license applies to its own independently written source.

## Dependency paths in the installed environment

| Distribution | Immediate installed parent(s) |
|---|---|
| annotated-types | pydantic |
| anyio | httpx2, mcp, sse-starlette, starlette |
| attrs | jsonschema, referencing |
| cffi | cryptography |
| click | uvicorn |
| colorama | build, pytest |
| cryptography | pyjwt |
| h11 | httpcore2, uvicorn |
| httpcore2 | httpx2 |
| httpx2 | mcp |
| idna | anyio, httpx2 |
| iniconfig | pytest |
| jsonschema | mcp |
| jsonschema-specifications | jsonschema |
| mcp-types | mcp |
| opentelemetry-api | mcp |
| packaging | build, pytest |
| pluggy | pytest |
| pycparser | cffi |
| pydantic | mcp, mcp-types |
| pydantic_core | pydantic |
| Pygments | pytest |
| PyJWT | mcp |
| pyproject_hooks | build |
| python-multipart | mcp |
| referencing | jsonschema, jsonschema-specifications |
| rpds-py | jsonschema, referencing |
| sse-starlette | mcp |
| starlette | mcp, sse-starlette |
| truststore | httpcore2, httpx2 |
| typing-inspection | mcp, pydantic |
| typing_extensions | anyio, httpx2, mcp, mcp-types, opentelemetry-api, pydantic, pydantic-core, referencing, starlette, typing-inspection |
| uvicorn | mcp |

The graph is an installed-environment snapshot, not every optional extra that
upstream packages could support. It must be regenerated if package versions,
extras or platform markers change.

## Metadata gaps and primary-source follow-up

| Component | Metadata finding | Primary-source observation / remaining action |
|---|---|---|
| colorama 0.4.6 | Both license fields absent | Version-tagged license text contains the three-condition BSD form. Keep the metadata gap explicit; check the actual distributed artifact's notices before bundling |
| pywin32 312 | Legacy `PSF` only; no SPDX License-Expression | Upstream documents mixed licenses and identifies source/per-file notices as authoritative. Do not interpret `PSF` as a complete license inventory of its wheel |
| pluggy 1.6.0 | Legacy `MIT`; no project URL in installed metadata | Version-tagged LICENSE identifies MIT; upstream link below supplements, rather than overwrites, the metadata |
| h11 0.16.0, mcp 2.3.0, mcp-types 2.3.0 | Legacy `MIT` only | Expression not recorded; retain the legacy value. Review artifact license files for redistribution rather than silently synthesizing SPDX metadata |
| Compiled/bundled components in any wheel | Top-level metadata may not enumerate every component | Review License-File entries and bundled-library notices if creating a binary/environment bundle |

The colorama source observation is supported by its
[0.4.6 LICENSE.txt](https://raw.githubusercontent.com/tartley/colorama/0.4.6/LICENSE.txt).
pywin32's [upstream license guidance](https://github.com/mhammond/pywin32/blob/main/README.md)
explicitly describes mixed licensing; its
[win32 notice](https://github.com/mhammond/pywin32/blob/main/win32/License.txt)
is one component notice, not a whole-wheel legal conclusion. The referenced
`main` documentation was read on the snapshot date and is not asserted to be a
version-pinned audit of every file in build 312.
[pluggy 1.6.0 LICENSE](https://github.com/pytest-dev/pluggy/blob/1.6.0/LICENSE)
supports the supplementary source identification.

These observations are technical provenance records. They are not a legal
compatibility verdict or permission to relabel third-party code as MIT. The
source release does not bundle `.venv`; dependencies are installed separately.
Preserve upstream notices and reassess obligations if that distribution model
changes.

## Windows/Python 3.12 lock

[requirements/windows-python312.lock](../requirements/windows-python312.lock)
contains exact `name==version` lines extracted from `pip freeze --all`, allowing
only ordinary version pins. The bridge editable entry, `pip`, local paths,
direct URLs and comments containing paths were excluded.

Use it for this reference environment:

```powershell
python -m pip install -r requirements/windows-python312.lock
python -m pip install -e . --no-deps
python -m pip check
```

The lock includes optional test dependencies. It has no artifact hashes and
does not pin Python, Renga, the SDK, platform system libraries or every PEP 517
isolated-build dependency. It is an environment snapshot, not a claim of
bit-for-bit reproducible binaries or compatibility with other Python/OS
combinations. The marker-based direct requirements in `pyproject.toml` remain
the portable package contract.

`pyproject.toml` separately pins isolated build requirements `setuptools==84.0.0`
and `wheel==0.48.0`. Neither was installed in the persistent environment at this
snapshot; a build frontend installs them in its separate build environment.
Build results and artifact/notices verification remain separate from this
installed-environment inventory. They are not fabricated as installed entries
in this lock.

## Components outside the Python snapshot

- **Python** is installed separately under its own license; it is not a Python
  distribution entry in this table.
- **Renga and its SDK** are separately installed/licensed vendor components.
  No proprietary DLL/TLB, installer or generated COM wrapper is included.
- **IfcOpenShell** is an optional research/verification route, not installed in
  this snapshot and not part of the bridge's current direct dependencies.
- Studied upstream repositories are research sources, not automatically copied
  dependencies. See [REPOSITORY_RESEARCH.md](REPOSITORY_RESEARCH.md) and
  [NOTICE.md](../NOTICE.md).
