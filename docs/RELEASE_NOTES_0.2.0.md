# Renga–Codex Bridge 0.2.0 preview

Independent local stdio MCP bridge for Codex and Renga Professional. This is
a preview of the verified subset, using official API calls with zero Computer
Use and no additional AI service or API key.

## New verified scope

`bridge_create_levels_project` creates a NEW native `.rnp` with explicit
level elevations and an optional orthogonal native Axis grid. Own IFC4 storeys
and grids pass through official `ImportIfcProject`; temporary slab carriers
are deleted before saving. The adapter verifies native type, exact names,
Elevation and Origin.Z, stable name-to-UUID bindings and a clean model after
save/close/reopen. Existing targets are refused; existing-model insertion,
merging and direct level-elevation editing are not implemented by this route.

Actual tests created levels at 0/3000/6000 mm and five axes with 3000/6000 mm
steps, including Cyrillic names. A new native wall hosted on +3000 has genuine
mesh Z=3000..5800 mm. Negative/fractional level cases (-3000 and +4500.5 mm),
Unicode and apostrophe names also survived reopening. Axis label edits were
reflected in a fresh native IFC export. Axis coordinates are verified through
that export; direct COM Axis baseline getters remain unavailable.

The `room_marker` plan action edits a Room's intrinsic marker in global XY
millimeters, verified after Apply and again after reopening. A separate read
confirmed [2345,1678] on the same Room identity. This is separate from creating
a standalone Tag. Non-Room targets are rejected with the original file intact.

There are now 21 MCP tools. Refresh the Codex MCP catalogue after upgrading.

## Tests and provenance

**66 native scenario assertions passed** (22 core, 23 real stdio MCP, 7 elements,
3 owned-process failure checks, 11 new levels/annotations). **511 portable tests
passed**, with one Windows symlink skip and one opt-in integration deselected.
Normalized SHA-256 of the 27 tested Python modules:
`69658b5f9e8ee0dd20c8990fbf06f9ae1fac7d6bcaca8b27bdfc37833d00cf81`.
Exact outcomes and per-module hashes are recorded in the
[current public proof](https://github.com/ucrdaniel/Renga-Codex/blob/v0.2.0/tests/evidence/windows-renga-9.3.json).
The release gate refuses a source/proof mismatch. The new level/annotation
suite passed 11 scenario assertions; the original suites are rerun on this
version and are distinct from historical 0.1 evidence. A fresh real Codex
protocol backend also discovered all 21 tools without starting a model turn.
The existing chat may still cache the old catalogue and needs a refresh.
Native environment:
Renga Professional 9.3.32980.0 / API 2.50 / Windows x64 / Python 3.12.14.
Computer Use calls: **0**. Other Renga versions/editions are not verified.
Hosted CI checks portable tests and packages, not native Renga behavior.

The installer also fixes a Windows PowerShell 5.1 quoting bug that could
misclassify a valid Python environment as invalid. Both Python preflight
expressions are quote-free; a regression test executes the actual extracted
installer commands under PowerShell 5.1 without running installer mutations.

## Remaining limitations

Ten native probes (five types in both building and drawing models) returned
unsupported creation for Axis, DrawingAxis, LinearDimension, Tag and
DrawingElevationMark. The working IFC Axis route is distinct from those direct
factory calls. Associative dimensions and standalone Tag creation remain
unavailable through the researched public interfaces; no lines/text imitate
them. Moving an intrinsic Room marker does not remove this Tag limitation.

Direct LevelElevation remains read-only. Constructor Z is ignored in the
tested direct Level factory, and movement of a detached placement does not
persist. Plugins in C++/.NET use the same COM contract; they do not provide a
privileged alternate constructor. All new BIM writes remain in the configured
write root. Backups and saved-result checks continue to protect existing-file
edits. Timeout outcomes remain unknown until independently inspected.

The publisher does not overwrite the existing v0.1.0 tag, release or assets. This preview uses
its own v0.2.0 tag and versioned wheel/source archive, only after successful CI
of the exact main commit and the fail-closed public release checks.

- [Install in Russian](https://github.com/ucrdaniel/Renga-Codex/blob/v0.2.0/docs/INSTALL_RU.md)
- [Operation format](https://github.com/ucrdaniel/Renga-Codex/blob/v0.2.0/docs/OPERATION_PLANS.md)
- [Capabilities and limits](https://github.com/ucrdaniel/Renga-Codex/blob/v0.2.0/docs/CAPABILITIES.md)
- [Level research](https://github.com/ucrdaniel/Renga-Codex/blob/v0.2.0/docs/LEVEL_API_RESEARCH.md)
- [Annotation research](https://github.com/ucrdaniel/Renga-Codex/blob/v0.2.0/docs/ANNOTATION_API_RESEARCH.md)
