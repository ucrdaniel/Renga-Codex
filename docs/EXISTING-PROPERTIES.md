# Existing registered string properties

Development MCP tool:
`bridge_update_existing_properties(project, changes, cell_checks=None)`.
Python helper: `existing_properties.update_existing_properties`.

This helper edits existing registered, assigned **String** properties on
inspected Project, Drawing or Topic UUIDs. It does not register properties,
change type assignments or expressions, or directly write title-block cells.
Expression-backed properties are rejected. The helper performs complete
preflight, backup, model operation, native save/close/reopen and identity/value
checks. Scoped native runs in Renga9.3.32980.0/API2.50 each changed ten existing
Drawing String values and verified them after save/close/reopen. Existing
definitions, assignments and object identities were retained. Project and
Topic mutations remain native unverified; portable tests do not extend that
scope. See the [sanitized native evidence](../tests/evidence/development-existing-properties-9.3.json).

The resolved title-block reader found **zero exact author-value matches** in
both runs. No positive native `cell_checks` scenario was therefore claimed,
and the visible author field remains unresolved. A saved property value does
not establish its binding to a form cell. These were direct public Python
helper runs, separate from protocol/routing checks of the new MCP tool.

`changes` is an array of 1..1000 exact objects:

```json
{
  "kind": "Drawing",
  "uuid": "00000000-0000-0000-0000-000000000001",
  "property_guid": "00000000-0000-0000-0000-000000000002",
  "property_name": "Author",
  "value": "Designer"
}
```

The example UUIDs are placeholders; inspect the actual existing definition,
target UUID, property name, assignment and expression before editing.
`kind` is exactly `Project`, `Drawing` or `Topic`. `value` may be empty text.
Duplicate target/property pairs and unknown fields are rejected.

Optional `cell_checks` is an array of at most 1000 exact objects with
`drawing_uuid`, `block_index` (0..99), `block_name`, `column` and `row`
(0..9999), `expected_before`, and `expected_value`. They assert actual native
title-block getter values before and after the property change. They do not
establish the cell expression/binding, visual layout or a cell setter.

CLI `--plan` contains the JSON **array** of changes. Optional `--cell-checks`
names a second JSON array; it applies only to this command:

```powershell
renga-bridge update_existing_properties --project 'C:\dedicated-test-root\model.rnp' --plan 'C:\dedicated-test-root\property-changes.json' --cell-checks 'C:\dedicated-test-root\cell-checks.json'
```

Existing-project authorization and configured write-root rules remain in
effect. This operation provides no safety bypass, UI automation, PDF export,
external AI service or extra API key requirement.
