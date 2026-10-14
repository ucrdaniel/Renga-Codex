# Contributing

Contributions should improve verifiable local API access to Renga. Start with an
issue describing the operation, installed Renga/API version and expected saved
result. Include a minimal synthetic example; exclude customer BIM files, SDK
archives, activation data and personal information.

## Development

Use Python 3.11 or later. Windows x64, separately installed Renga and a local SDK
are required only for actual COM integration tests.

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -e '.[test]'
.\.venv\Scripts\python.exe -m pytest -m 'not integration' -q
.\.venv\Scripts\python.exe -m compileall -q src tests
.\.venv\Scripts\python.exe -m pip check
```

Read `AGENTS.md` and `docs/CAPABILITIES.md`. Do not attach to a running user
application, use UI automation to pass an API test, or change real customer
projects. Integration evidence must state the bridge version/commit, Renga and
SDK versions, exact operation, post-reopen expected/actual values, test counts
and Computer Use count. Store full local evidence outside tracked source; a
sanitized summary may be committed after checking it for paths and personal
data.

## Pull requests

Keep each change focused. Describe the concrete user trigger and resulting
behavior; include relevant tests and known limits. Add new operations to the
capability map only after real saved-model verification. Unsupported or ignored
setters should fail explicitly. Tests must cover malformed plans, rollback and
file safety when changing the mutation layer.

Contributions are licensed under the repository's MIT license. Do not submit
third-party code without identifying its origin and compatible license. Do not
submit proprietary Renga files. Dependency additions need a technical reason,
version constraints and license/provenance review.

## Release checks

Run unit tests, package build, dependency consistency and the opt-in local real
Renga scenario. Review the staged tree for private files. Version the confirmed
feature set; do not describe unsupported documentation functions or GUI-only
results as autonomous API support. Publish only a sanitized test report.
