# Native presentation API research

Reference: API 2.50, researched 2026-10-15. A separate owned development probe
saved and reopened one native Drawing, DrawingText, AR Topic and embedded
Level view, including source/scale, dependent view parameter, content center
and bounds checks. Other view kinds and visual composition remain separately
unverified. See the scoped [development outcomes](API-HW2-EXTENSIONS.md);
these additions do not modify the frozen 0.2 release evidence.

## Available contracts

`IEntityCollection.Create` supports Drawings, Topics, Tables, Schedules and
LayoutStyles. The project exposes those collections. `Topic` can be named
through `EntityName`; Drawing has name, page format, orientation, layout style
and topic reference parameters. A new imported project may have none of these
optional resources. The helper therefore permits a native blank sheet without
pretending to manufacture a title block, frame or schedule definition.
[Collection factory](https://help.rengabim.com/api/interface_i_entity_collection.html),
[project collections](https://help.rengabim.com/api/interface_i_project.html).

The supported model factory includes native DrawingText, EmbeddedModelView,
EmbeddedEntityView, EmbeddedSchedule and EmbeddedTable in drawing models. Text
uses `ITextObject` rich text and actual bounds. Views remain native embedded
objects with model/resource references; screenshots are never substituted.
[IModel](https://help.rengabim.com/api/interface_i_model.html),
[ITextObject](https://help.rengabim.com/api/interface_i_text_object.html).

EmbeddedModelView uses an inspected source `RepresentedEntityId` and scale;
the implementation accepts existing Level, Section or Elevation objects.
EmbeddedEntityView instead uses **ObjectMark**, not a unique source ID. The
helper requires both an inspected object ID and explicit mark, verifies the
source's actual mark, and reports that final binding is by mark. Multiple
instances sharing a mark are not uniquely distinguished by that contract.
Other applicable view parameters are explicit, type-checked at native setters.
[Parameter applicability](https://help.rengabim.com/api/group___entity_type_by_parameters.html).

`IRectBoundedObject` controls content placement and the clipping rectangle for
all four embedded object kinds. The helper applies source/scale parameters
first, then sets content-center placement through `SetContentPlacement`, fits
bounds and optionally applies an explicit clipping rectangle. After reopening,
it reads content existence, parameter references, content center and bounds.
Successful content readback still requires separate visual clipping/overlap QA.
[Bounds and placement](https://help.rengabim.com/api/interface_i_rect_bounded_object.html).

## Specific missing operations

- Section and Elevation entity constants/parameters exist, but neither appears
  in the documented `IModel.CreateObject` support table. No separate public
  factory collection or geometry/binding constructor for them was found.
  Embedding an existing Section is separate from creating that Section.
- LayoutStyle's documented built-in parameters are name and identity. No
  title-block layout/margin/cell constructor is established here. Selecting an
  existing layout works through its inspected native ID; an omitted layout is
  deliberately a blank/default sheet, not a completed regulated sheet.
- Tables and Schedules can be entities and can be embedded by `TableId` or
  `ScheduleId`, but the examined API has no public `ITable` cell/data authoring
  or schedule-definition interface. Creating an empty Table entity does not
  satisfy a manually populated editable table. The helper only embeds an
  existing resource and rejects a resulting embedded object without content.
- Associative dimensions, standalone tags, section/elevation marks, automatic
  axis annotations and title-block cells are not imitated with lines/text.

The helper creates no general filter/style/table-definition editor and does not
copy resources through the clipboard. Existing-file writes use the standard
owned Session path gate, backup, transaction and save/close/reopen lifecycle.
Project-resource undo is not guaranteed; an exception leaves the session
discardable until save. Final checks happen after save: a reopen/assertion
failure can therefore leave edited content on disk. The verified backup must
be inspected and restored manually if recovery is needed; no automatic restore
or unchanged-file guarantee is made for failures after saving.

Explicit FilterId/DisplayStyleId and ViewDepthLevelId are positive int32
references, checked against the correct existing resource collection or native
Level before creating Topics/Drawings. Integer enum/reference values must fit
signed int32; boolean flags are strict booleans. Omit an optional reference to
keep the native default, instead of supplying an unverified zero sentinel.

## Module entry point

`create_presentations(project, drawings)` accepts explicit drawing
specifications. Required fields are `name` and inspected positive
`page_format_id`. Optional `orientation` is 1 portrait or 2 landscape,
`layout_style_id` must identify an existing resource, and `topic` is an exact
topic name to reuse or create. Omitting a topic leaves the native default;
callers must inspect the result when an unassigned title sheet is required.

`texts` contains text, `[left,right,bottom,top]` bounds in sheet millimeters,
optional font family and cap height. `views` contains kinds `model`, `entity`,
`schedule` or `table`; inspected source IDs/marks, scale IDs and explicit view
parameters are required where applicable. `origin_mm` is the **content center**
in sheet coordinates, not the model's global origin. `bounds_mm` optionally
sets a clip rectangle after fitting. All requests are validated before a
native write session starts. The worker `presentations` action and
`bridge_create_presentations` MCP tool expose this helper. Refresh/reconnect
the MCP catalogue before expecting the new tool in a previously opened chat.
