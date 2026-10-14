# Renga–Codex Bridge 0.1.0 preview

Independent, unofficial Windows integration connecting Codex to Renga through
local stdio MCP and owned COM STA workers. Codex interprets natural language;
the bridge executes explicit operations without an additional AI service,
chat application or API key.

## Confirmed release evidence

- Real environment: **Renga Professional 9.3.32980.0**, SDK reference **API
  2.50**, Windows x64 build 22631, Python **3.12.14**.
- **53 passed native scenario checks**: core worker 22, actual stdio MCP 21,
  structural elements 7, owned-process failure/recovery 3. These are composite
  assertions, not 53 individual COM calls or complete API coverage.
- **305 portable unit tests passed**, one symlink test skipped on this Windows
  setup, one opt-in integration test deselected. Dependency consistency and
  installer PowerShell syntax passed. Hosted CI does not run Renga.
- **0 Computer Use calls**; no mouse/keyboard or UI Automation emulation.
- Normalized SHA-256 of the 22 tested bridge Python modules:
  `59913f84d7bfe059921716344578e2bb24637d2154015982a910436b0d340673`.
- All **20 MCP tools** discovered by a fresh real Codex protocol backend and
  by the existing Codex chat. Configuration reload was acknowledged. In an
  additional current-chat test, five actual tool calls copied a test model,
  changed wall height **3400 → 3600 mm**, saved/closed/reopened and independently
  read the saved value with unchanged persistent identity. This extra roundtrip
  is separate from the 53 scripted checks. The earlier Desktop proxy diagnostic
  was unavailable; actual current-chat tool execution is now verified.

The [sanitized proof](https://github.com/ucrdaniel/Renga-Codex/blob/v0.1.0/tests/evidence/windows-renga-9.3.json)
contains actual final suite outcomes and per-module fingerprints.
Full native models, operation logs, ownership records and SDK files stay local.
Hosted CI checks portable source/tests/packages and does not run Renga.

## Released operations

Real create/edit/save/close/reopen tests cover walls, floors, manual rooms,
default-elevation levels, styled doors/windows, columns, a beam with a 3D
baseline, a stair, a pitched roof, a hosted slab opening and an existing-style
Element. Verification reads persistent identities, requested parameters,
placements, contours, native quantities and triangulated geometry. The slab
opening reduced measured area from **35 to 31.25 m²**; the room test independently
confirmed **37.44 m²**.

Project tools provide protected copies, SaveAs, disposable-copy preview and four
project-information fields. Documentation tools created two native A3 landscape
sheets with linked level views, existing native schedules and text, exported
the selected sheets to a two-page PDF and rendered a genuine 1024×768 PNG via
Renga's screenshot service. Both PDF pages were visually inspected. They are
synthetic views of the same base level, not a multistorey architectural package;
native export ordering is not asserted. The installed license's watermark is
retained. IFC proof covers a genuine native IFC4 STEP file and its envelope,
not a complete schema/semantic audit.

## Scope and limitations

This version is a **prerelease preview**, not complete autonomous architectural
design or complete coverage of Renga API. Advertised native operations must match
the evidence and [capability map](https://github.com/ucrdaniel/Renga-Codex/blob/v0.1.0/docs/CAPABILITIES.md).

Other Renga versions/editions are not verified. Nonzero level elevation is
read-only in the tested path; moving the returned level placement did not
persist. Associative dimension/tag constructors and new automatic rooms are
not exposed as working creation tools. Full assemblies require inspected
existing styles; style zero can create an aperture. Renga normalized a
counter-directed window frame, so the bridge refused that request before saving.

New schedule/filter definitions, arbitrary rotation/mirroring, imports and exact
solid clash detection are not advertised as verified. Bounding-box candidates
are not regulatory or solid-intersection certification. Dependent object
creation needs multiple native Apply batches before final save; complete
in-memory undo of arbitrary project resources is not promised.

Existing-file changes require verified backups and saved-result inspection.
Timeout cleanup stops only independently identified owned processes and leaves
`outcome: unknown`; before a Renga PID is proved, automatic termination is unsafe.
See [recovery instructions](https://github.com/ucrdaniel/Renga-Codex/blob/v0.1.0/docs/RECOVERY.md)
before retrying or restoring any file.

## Installation

Install and license Renga separately, download a compatible SDK yourself, and
run the reviewed Windows installer from the checkout. Closed Renga components,
activation material and user BIM projects are not distributed.

- [Russian installation](https://github.com/ucrdaniel/Renga-Codex/blob/v0.1.0/docs/INSTALL_RU.md)
- [English installation](https://github.com/ucrdaniel/Renga-Codex/blob/v0.1.0/docs/INSTALL_EN.md)
- [Testing and evidence](https://github.com/ucrdaniel/Renga-Codex/blob/v0.1.0/docs/TESTING.md)
- [Security policy](https://github.com/ucrdaniel/Renga-Codex/blob/v0.1.0/SECURITY.md)
- [Licenses and notices](https://github.com/ucrdaniel/Renga-Codex/blob/v0.1.0/NOTICE.md)

The installer registers `renga-codex-bridge` while preserving existing Codex
settings and creating a checked configuration backup. Reconnect Codex after
registration; a successful configuration write alone does not prove tool
discovery in an already-open chat.

Release assets contain our own Python wheel and source archive. Proprietary
Renga components, activation material, SDK wrappers and user BIM projects are
excluded. The MIT license covers this integration's own source only.
