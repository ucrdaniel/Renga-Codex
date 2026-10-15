# Testing and evidence

This preview was tested against a licensed local installation of **Renga
Professional 9.3.32980.0**, the owner's SDK reference **API 2.50**, Windows x64
and Python **3.12.14**. Other Renga versions and editions are not verified.
All BIM writes used fresh synthetic projects in a dedicated test root; the
owner's architectural projects were not test inputs or release artifacts.

## Portable checks

```powershell
.\.venv\Scripts\python.exe -m pytest -m 'not integration' -q
.\.venv\Scripts\python.exe -m pip check
.\.venv\Scripts\python.exe -m compileall -q src tests scripts
```

GitHub Actions runs unit tests and wheel builds on Windows and Linux with Python
3.11, 3.12 and 3.13. Linux checks source and protocol helpers; it cannot establish
Renga COM compatibility. Pure tests, mocks, API method discovery and historical
homework results are not counted as native product tests.

## Actual local Renga scenarios

Install the bridge and configure `RENGA_SDK_PATH`, `RENGA_BRIDGE_WRITE_ROOT` and
`RENGA_BRIDGE_STATE_ROOT` as described in [INSTALL_EN.md](INSTALL_EN.md). The
write root must be a dedicated disposable directory. Run these sequentially:

```powershell
.\.venv\Scripts\python.exe scripts\run_live_tests.py
.\.venv\Scripts\python.exe scripts\run_level_annotation_tests.py
.\.venv\Scripts\python.exe scripts\run_mcp_tests.py
.\.venv\Scripts\python.exe scripts\run_element_tests.py
.\.venv\Scripts\python.exe scripts\run_timeout_test.py
```

Each scenario starts its own identified Renga process and saves a timestamped
test directory. Requests use serialized COM STA workers; no script attaches to
the user's open session. The timeout scenario deliberately terminates an owned
worker and verifies owned-process cleanup and the original file afterward.
Timeout outcomes remain `unknown` until a separate inspection proves the file
state. Read [RECOVERY.md](RECOVERY.md) before retrying an interrupted write.

The suites check saved persistent identities, requested parameter values and
native contours after reopening. Geometry tests compare native quantities and
triangulated areas with separately computed targets, including a slab opening.
The element suite covers columns, a beam with a 3D baseline, stairs, a pitched
roof and a genuine existing-style Element. It explicitly records failed or
ineffective nonzero-level and counter-directed window probes as limitations.
The newer level/annotation suite separately proves the official IFC bootstrap
for a NEW native model: 0/3000/6000 mm levels, orthogonal native Axis objects,
clean carrier removal and a native wall with mesh Z=3000..5800 mm. Negative and
fractional levels and Unicode/apostrophe names are tested as additional cases.
Axis coordinates and renamed labels are checked using fresh native IFC export;
the Axis COM baseline interfaces remain unavailable. Intrinsic Room marker XY
is checked after saving and by a separate reopened inspection. Ten explicit
factory probes cover five annotation types in building and drawing contexts;
their expected rejection is not creation support.
The MCP suite uses the real stdio client and server, not mocked tool calls.

Documentation tests create two native A3 landscape sheets, linked level views,
embedded existing schedules and text. The two sheets are synthetic test views
of the same base level; they do not prove automatic multistorey design. PDF
checks inspect both page sizes and native output. Both pages are also rendered
and visually inspected. IFC tests check the native IFC4 STEP envelope and
nonempty output, not complete IFC schema or semantic correctness. Native PNG
rendering uses Renga's screenshot service, without mouse/keyboard automation.
The installed Renga license may add its own export watermark.

## Codex discovery

```powershell
.\.venv\Scripts\python.exe scripts\run_codex_discovery_test.py --isolated-app-server
```

This starts temporary **real Codex protocol instrumentation**, initializes it
and reads the configured MCP catalogue. It creates no Codex task or model turn,
and introduces no AI service or key. The expected 0.2 catalogue contains 21
tools, including `bridge_create_levels_project`. See the current public report
for its actual discovery result. The original 0.1 release separately verified
a five-call existing-chat wall-edit roundtrip and its then-current 20 tools;
that historical result is not a fresh 0.2 test. Reconnect or restart Codex after
an upgrade if tools have not refreshed; configuration writes alone do not prove
current-chat discovery. A control-socket diagnostic is also distinct from
actual MCP tool invocation.

## Public proof and packages

The sanitized report at
[tests/evidence/windows-renga-9.3.json](../tests/evidence/windows-renga-9.3.json)
contains scenario outcomes, versions, zero Computer Use calls and the normalized
SHA-256 fingerprint of the tested Python sources. It excludes native projects,
absolute local paths, model UUIDs, raw operation logs, process identities and
user data. Those full records remain local under ignored runtime/test folders.

```powershell
.\.venv\Scripts\python.exe scripts\verify_release_inputs.py
.\.venv\Scripts\python.exe -m build --outdir dist
.\.venv\Scripts\python.exe scripts\verify_release_inputs.py --archives dist
```

The release gate checks source fingerprints and every packaged module, rejects
vendor/private/binary artifacts and refuses unfilled release evidence. The
release workflow refuses to replace a published version and publishes a preview
only from the exact main commit
whose source CI succeeded. A passing scenario is a composite assertion, not a
count of individual COM calls or proof of full API coverage.
