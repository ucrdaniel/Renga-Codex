# Renga–Codex Bridge development and model safety

This directory contains the public integration product. Keep release source,
tests, examples and documentation here. Never copy private homework models,
student information, activation keys, vendor SDK binaries or user logs into Git.

- Read `README.md`, `docs/CAPABILITIES.md` and `docs/PREVIOUS_WORK_ANALYSIS.md`
  before changing modelling behavior.
- Use MCP or the supported COM adapter. Computer Use, hidden UI Automation,
  keyboard/mouse simulation and attaching to an existing user Renga session are
  prohibited for the advertised API coverage.
- COM work belongs to a new, verified, bridge-owned process and a COM STA.
  Serialize requests. Close only the process and project owned by this bridge.
- Make units explicit: geometry and lengths are millimeters; use the quantity
  units returned by Renga for areas and volumes.
- Translate modelling requests into saved JSON operation plans. Inspect the
  saved project before selecting IDs; use persistent `UniqueId` across SaveAs.
- Autonomous BIM writes must remain under the configured
  `RENGA_BRIDGE_WRITE_ROOT`. The installer uses `runtime/test-projects`; without
  installer configuration, the runtime uses its local application-data state
  directory's `test-projects` subdirectory. The inherited local
  development workspace may restrict it further to
  `C:\Renga-Automation\artifacts\test-projects`.
- Existing user project changes need explicit authorization for the exact file.
  The MCP test tools must not expose a blanket safety bypass. Never overwrite an
  existing file using `--new`.
- Back up every existing-file edit, verify the backup hash, perform an undo
  transaction, and verify saved results after close and reopen. A successful
  setter call alone is not a successful model change.
- Never claim tested support from method discovery, mock tests or old homework
  evidence. Record actual version, test scenario, saved values and failures.
- Nonzero Level origin/elevation is not writable in the verified Renga 9.3 API.
  Use existing levels; report the limitation instead of silently ignoring it.
- Window XY origin controls placement; Z is applied through `Offset`. A default
  window style can represent an aperture. Inspect and select an existing style
  before claiming a complete window assembly.
- Vendor examples are research inputs. Do not run them against user projects;
  some attach to and close the active application.
- Run platform-independent tests in CI. Genuine Renga integration tests require
  a compatible local Windows installation and disposable test files. Count
  Computer Use calls separately; the public API test target is zero.
- Review staged paths and content before every public commit. Dependency
  licenses and copied-code provenance must be recorded in `NOTICE.md` and
  `docs/REPOSITORY_RESEARCH.md`.

Natural-language interpretation is Codex's responsibility. Do not add a second
AI service, API key requirement or standalone design chat UI to this product.
