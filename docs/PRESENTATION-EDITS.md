# Edit existing sheet contents

`renga_codex_bridge.presentation_edits.update_sheet_contents(project, changes)`
updates existing native sheet objects through a fresh bridge-owned session.
It backs up the existing file, performs native undo operations, saves, closes,
reopens and verifies the requested saved results. The configured write-root
restriction applies; there is no authorization bypass.

Development MCP tool: `bridge_update_sheet_contents(project, changes)`.
For CLI use a saved JSON array containing the changes:

```powershell
renga-bridge update_sheet_contents --project 'C:\dedicated-test-root\model.rnp' --plan 'C:\dedicated-test-root\move-contents.json'
```

The CLI and MCP use the same native adapter. Natural-language planning remains
Codex's responsibility; no additional AI endpoint or API key is needed.

This is a development addition. A fresh disposable Renga 9.3/API 2.50 fixture
passed 12 scoped assertions across two save/close/reopen edit runs for an
EmbeddedModelView and three DrawingText objects. See the
[sanitized native evidence](../tests/evidence/development-presentation-edits-9.3.json).
EmbeddedEntityView, EmbeddedSchedule and EmbeddedTable edit paths remain
native unverified by that fixture. Portable tests do not establish native
support, and separate visual evidence is required for sheet layout claims.
These results do not alter frozen release evidence retroactively.

Each change requires inspected persistent `drawing_uuid` and `object_uuid`,
with at least one of these fields:

| Field | Applicable native objects | Contract |
|---|---|---|
| `content_origin_mm` | EmbeddedEntityView, EmbeddedModelView, EmbeddedSchedule, EmbeddedTable | Two global sheet coordinates; preserves the existing content X axis |
| `bounds_mm` | Those four kinds and DrawingText | `[left,right,bottom,top]` in sheet mm, positive width and height |
| `fit_inset_mm` | Those four embedded kinds | Nonnegative sheet-mm inset, mutually exclusive with explicit `bounds_mm` |
| `scale_id` | EmbeddedEntityView and EmbeddedModelView | Positive inspected existing native Scale ID, verified by resource UUID after reopening |
| `text`, `font_family`, `cap_size_mm` | DrawingText | Replace all paragraphs with explicit plain text/font; font fields are required with `text` |

The plan may contain 1 to 500 changes. Repeated normalized drawing/object UUID
pairs, unknown fields, numeric object identities, nonfinite numbers, absent
resources and unsupported object kinds are rejected before the first setter.
An object must belong to the explicitly selected sheet. Dimensions, axes,
tags and other annotations cannot be moved through this helper.

Text replacement uses the documented
`IRichTextDocument.RemoveParagraph(index)` in reverse index order, followed by
`AppendParagraph`. It does not invent a `Clear` or token setter. LF separates
paragraphs; NUL and CR are rejected. `text: ""` removes the paragraphs while
retaining the native DrawingText object's UUID. Plain replacement is black,
regular text, with explicit family and cap size (for example `Arial`, `2.5`).
Font-only changes require an explicit replacement text to avoid silently
reconstructing unspecified formatting. A bounds-only change preserves all
exposed existing token fields, including family, cap size, color and style.

Readback compares all building, drawing and drawing-content identities/types,
requested content centers, preserved content axes, bounds, scale resource UUIDs,
actual text and exposed rich-text token fields. A fitted rectangle is captured
after native Apply and compared after reopening; it is not independently
computed from source geometry. Empty text has no nonempty tokens to certify
a font and is reported accordingly.

The helper does not create a sheet/view/table, define a section or elevation,
populate a schedule, move annotation reference grips or certify visual layout,
ГОСТ compliance, sheet-border fit or complete source-object associativity.
Entity views retain their native binding semantics, which can be by shared
mark rather than one uniquely identified source object. Moving a view does not
promise automatic movement of separate sheet annotations. Native PNG rendering
and visual review are separate checks; this helper performs no PDF export.

Primary references: [bounded object placement and crop](https://help.rengabim.com/api/interface_i_rect_bounded_object.html),
[text bounds](https://help.rengabim.com/api/interface_i_text_object.html),
[rich-text paragraphs](https://help.rengabim.com/api/interface_i_rich_text_document.html),
and [math placement constructor](https://help.rengabim.com/api/interface_i_math.html).
