"""Reposition existing native sheet contents, preserving persistent identities.

This adapter does not create objects, relocate annotation grips or invent
section/table definitions. Existing DrawingText can be replaced through the
documented RemoveParagraph/AppendParagraph pair. No GUI is used.
"""
from __future__ import annotations

import copy
import math

from .audit import event, save_plan
from .model import parameters, set_parameter
from .presentation import _native_rect
from .session import Session
from .sheet_metadata import _uuid, sheet_identity_snapshot


EMBEDDED_TYPES = {"EmbeddedEntityView", "EmbeddedModelView", "EmbeddedSchedule", "EmbeddedTable"}
CHANGE_FIELDS = {"drawing_uuid", "object_uuid", "content_origin_mm", "bounds_mm", "fit_inset_mm", "scale_id",
                 "text", "font_family", "cap_size_mm"}


def _number(value, field):
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError(field + " requires an explicit finite number")
    try:
        result = float(value)
    except OverflowError as error:
        raise ValueError(field + " must be finite") from error
    if not math.isfinite(result):
        raise ValueError(field + " must be finite")
    return result


def validate_content_changes(changes):
    if not isinstance(changes, list) or not 1 <= len(changes) <= 500:
        raise ValueError("changes must contain 1..500 explicit content updates")
    result = copy.deepcopy(changes)
    seen = set()
    for change in result:
        if not isinstance(change, dict):
            raise ValueError("Each content update must be an object")
        if set(change) - CHANGE_FIELDS or not {"drawing_uuid", "object_uuid"} <= set(change):
            raise ValueError("Unsupported content fields; drawing_uuid/object_uuid are required")
        if len(change) <= 2:
            raise ValueError("Content update must request at least one supported change")
        for key in ("drawing_uuid", "object_uuid"):
            change[key] = _uuid(change[key])
        identity = (change["drawing_uuid"], change["object_uuid"])
        if identity in seen:
            raise ValueError("Duplicate drawing/object UUID pair")
        seen.add(identity)
        if "bounds_mm" in change and "fit_inset_mm" in change:
            raise ValueError("Choose explicit bounds_mm or fit_inset_mm, not both")
        if "content_origin_mm" in change:
            point = change["content_origin_mm"]
            if not isinstance(point, (list, tuple)) or len(point) != 2:
                raise ValueError("content_origin_mm must contain two sheet coordinates")
            change["content_origin_mm"] = [_number(value, "content_origin_mm") for value in point]
        if "bounds_mm" in change:
            values = change["bounds_mm"]
            if not isinstance(values, (list, tuple)) or len(values) != 4:
                raise ValueError("bounds_mm must be [left,right,bottom,top] in sheet mm")
            values = [_number(value, "bounds_mm") for value in values]
            if values[0] >= values[1] or values[2] >= values[3]:
                raise ValueError("bounds_mm must have positive width and height")
            change["bounds_mm"] = values
        if "fit_inset_mm" in change:
            change["fit_inset_mm"] = _number(change["fit_inset_mm"], "fit_inset_mm")
            if change["fit_inset_mm"] < 0:
                raise ValueError("fit_inset_mm must be nonnegative")
        if "scale_id" in change and (type(change["scale_id"]) is not int or not 0 < change["scale_id"] < 2**31):
            raise ValueError("scale_id requires an inspected positive native int32 ID")
        if "text" in change:
            if not isinstance(change["text"], str) or "\0" in change["text"] or "\r" in change["text"]:
                raise ValueError("text must be explicit Unicode text without NUL/CR; use LF between paragraphs")
            if not {"font_family", "cap_size_mm"} <= set(change):
                raise ValueError("Text replacement requires explicit font_family and cap_size_mm, for example Arial/2.5")
            family = change["font_family"]
            if not isinstance(family, str) or not family.strip() or any(ord(char) < 32 for char in family):
                raise ValueError("font_family must be nonempty text without controls")
            size = _number(change["cap_size_mm"], "cap_size_mm")
            if not .1 <= size <= 100:
                raise ValueError("cap_size_mm must be between 0.1 and 100 sheet mm")
            change["cap_size_mm"] = size
        elif set(change) & {"font_family", "cap_size_mm"}:
            raise ValueError("Font changes require an explicit text replacement")
    return result


def _contents(session, drawing):
    model = drawing.QueryInterface(session.r.IModel)
    objects = model.GetObjects()
    result = {}
    for index in range(objects.Count):
        obj = objects.GetByIndex(index)
        uid = _uuid(obj.UniqueIdS)
        if uid in result:
            raise RuntimeError("Duplicate native drawing-content UUID")
        result[uid] = obj
    return model, result


def _kind(session, obj):
    actual = _uuid(obj.ObjectTypeS)
    for kind in {*EMBEDDED_TYPES, "DrawingText"}:
        if actual == _uuid(session.sdk.types[kind]):
            return kind
    raise NotImplementedError("Only existing native embedded views/tables/schedules and DrawingText bounds are supported")


def _bounds(bounded):
    rect = bounded.BoundRect
    result = [rect.Left, rect.Right, rect.Bottom, rect.Top]
    if any(not math.isfinite(value) for value in result):
        raise RuntimeError("Nonfinite native presentation bounds")
    if result[0] >= result[1] or result[2] >= result[3]:
        raise RuntimeError("Degenerate native presentation bounds")
    return result


def _pose(bounded):
    placement = bounded.GetContentPlacement()
    if not placement:
        raise RuntimeError("Native embedded content placement is absent")
    origin, axis = placement.Origin, placement.AxisX
    result = {"content_origin_mm": [origin.X, origin.Y], "content_x_axis": [axis.X, axis.Y]}
    if any(not math.isfinite(value) for values in result.values() for value in values):
        raise RuntimeError("Nonfinite native embedded content placement")
    if math.hypot(*result["content_x_axis"]) <= 0:
        raise RuntimeError("Degenerate native embedded content axis")
    return result


def _text_state(session, obj):
    document = obj.QueryInterface(session.r.ITextObject).GetRichTextDocument()
    paragraphs = []
    for index in range(document.ParagraphCount):
        paragraph = document.GetParagraph(index)
        tokens = []
        for i in range(paragraph.TokenCount):
            token = paragraph.GetToken(i)
            color, style = token.FontColor, token.FontStyle
            tokens.append({"text": token.Text, "font_family": token.FontFamily,
                           "cap_size_mm": token.FontCapSize,
                           "font_color_rgba": [color.Red, color.Green, color.Blue, color.Alpha],
                           "font_style": {key: _native_bool(getattr(style, key)) for key in ("Bold", "Italic", "Underline")}})
        paragraphs.append(tokens)
    return {"text": "\n".join("".join(token["text"] for token in paragraph) for paragraph in paragraphs),
            "rich_text": paragraphs}


def _native_bool(value):
    # The examined TLB represents FontStyle flags as c_char. bool(b'\x00') is
    # True in Python, although it means false in the native record.
    if type(value) is bool:
        return value
    if type(value) is int:
        return value != 0
    if isinstance(value, bytes) and len(value) == 1:
        return value[0] != 0
    raise RuntimeError("Unsupported native FontStyle flag representation")


def _replace_text(session, obj, change):
    document = obj.QueryInterface(session.r.ITextObject).GetRichTextDocument()
    for index in range(document.ParagraphCount - 1, -1, -1):
        document.RemoveParagraph(index)
    if change["text"]:
        for paragraph in change["text"].split("\n"):
            token = session.r.RichTextToken()
            token.Text, token.FontFamily, token.FontCapSize = paragraph, change["font_family"], change["cap_size_mm"]
            token.FontColor = session.r.Color(0, 0, 0, 255)
            token.FontStyle = session.r.FontStyle(False, False, False)
            document.AppendParagraph([token])


def _matches(actual, wanted):
    return len(actual) == len(wanted) and all(math.isclose(a, b, rel_tol=0, abs_tol=1e-6) for a, b in zip(actual, wanted))


def _preflight(session, changes):
    drawings = {}
    pending = []
    for change in changes:
        drawing_uid = change["drawing_uuid"]
        if drawing_uid not in drawings:
            drawing = session.project.Drawings2.GetByUniqueIdS(drawing_uid)
            if not drawing or _uuid(drawing.UniqueIdS) != drawing_uid:
                raise ValueError("Inspected drawing UUID is absent from this project")
            drawings[drawing_uid] = _contents(session, drawing)
        model, contents = drawings[drawing_uid]
        obj = contents.get(change["object_uuid"])
        if obj is None:
            raise ValueError("Inspected object UUID is absent from the selected drawing")
        kind = _kind(session, obj)
        text = kind == "DrawingText"
        if text and set(change) - {"drawing_uuid", "object_uuid", "bounds_mm", "text", "font_family", "cap_size_mm"}:
            raise NotImplementedError("DrawingText supports bounds and explicit plain-text/font replacement")
        if not text and set(change) & {"text", "font_family", "cap_size_mm"}:
            raise ValueError("Text/font replacement applies only to existing DrawingText")
        if not text and kind in {"EmbeddedSchedule", "EmbeddedTable"} and "scale_id" in change:
            raise ValueError("scale_id applies only to embedded native model/entity views")
        bounded = obj.QueryInterface(session.r.ITextObject if text else session.r.IRectBoundedObject)
        old = {"bounds_mm": _bounds(bounded)}
        if text:
            old.update(_text_state(session, obj))
            if "text" in change:
                document = obj.QueryInterface(session.r.ITextObject).GetRichTextDocument()
                if not callable(getattr(document, "RemoveParagraph", None)) or not callable(getattr(document, "AppendParagraph", None)):
                    raise NotImplementedError("Native rich text lacks documented RemoveParagraph/AppendParagraph")
        else:
            if not bounded.HasContent:
                raise ValueError("Existing embedded object has no native content")
            old.update(_pose(bounded))
        scale_uuid = None
        if "scale_id" in change:
            values = parameters(session, obj)
            if "ScaleId" not in values or values["ScaleId"]["readonly"]:
                raise ValueError("ScaleId is absent or read-only on the selected native view")
            collection = session.project.Scales
            if not collection.Contains(change["scale_id"]):
                raise ValueError("Inspected scale_id is absent from this project")
            scale_uuid = _uuid(collection.GetById(change["scale_id"]).UniqueIdS)
        pending.append((model, obj, bounded, kind, change, old, scale_uuid))
    return pending


def _record(session, obj, bounded, kind, change, old, scale_uuid):
    result = {"drawing_uuid": change["drawing_uuid"], "object_uuid": change["object_uuid"],
              "kind": kind, "bounds_mm": _bounds(bounded)}
    if "bounds_mm" in change and not _matches(result["bounds_mm"], change["bounds_mm"]):
        raise RuntimeError("Native presentation bounds differ from requested bounds_mm")
    if kind == "DrawingText":
        result.update(_text_state(session, obj))
        if "text" in change:
            if result["text"] != change["text"]:
                raise RuntimeError("Native DrawingText differs from requested replacement")
            count = 0
            for paragraph in result["rich_text"]:
                for token in paragraph:
                    if not token["text"]:
                        continue
                    if token["font_family"] != change["font_family"] or not math.isclose(token["cap_size_mm"], change["cap_size_mm"], rel_tol=0, abs_tol=1e-5):
                        raise RuntimeError("Native replacement text font differs from requested")
                    if token["font_color_rgba"] != [0, 0, 0, 255] or any(token["font_style"].values()):
                        raise RuntimeError("Native replacement text color/style differs from plain black regular text")
                    count += 1
            result["text_font_check"] = {"checked_nonempty_tokens": count,
                "status": "verified" if count else "not_applicable_empty_text"}
        elif result["text"] != old["text"] or result["rich_text"] != old["rich_text"]:
            raise RuntimeError("DrawingText or formatting changed during bounds-only edit")
    else:
        if not bounded.HasContent:
            raise RuntimeError("Native embedded object lost content")
        result.update(_pose(bounded))
        if not _matches(result["content_origin_mm"], change.get("content_origin_mm", old["content_origin_mm"])):
            raise RuntimeError("Native embedded content center differs from requested/preserved origin")
        if not _matches(result["content_x_axis"], old["content_x_axis"]):
            raise RuntimeError("Native embedded content orientation changed")
        if scale_uuid is not None:
            values = parameters(session, obj)
            scale_id = values.get("ScaleId", {}).get("value")
            collection = session.project.Scales
            if not scale_id or not collection.Contains(scale_id):
                raise RuntimeError("Native view references an absent scale")
            actual_uuid = _uuid(collection.GetById(scale_id).UniqueIdS)
            if actual_uuid != scale_uuid:
                raise RuntimeError("Native view scale persistent identity differs from requested")
            result.update(scale_id=scale_id, scale_uuid=actual_uuid)
    return result


def update_sheet_contents(project, changes):
    """Back up, edit explicit existing contents, save/close/reopen and verify.

    Content origins/bounds are global sheet millimeters. Existing content axes
    are preserved. Fit requests retain the computed committed rectangle and
    compare it after reopening; they do not establish visual sheet fit.
    """
    changes = validate_content_changes(changes)
    plan = save_plan({"action": "update_existing_sheet_contents", "project": str(project),
                      "changes": changes, "units": "sheet_mm"})
    committed = []
    with Session(project, write=True) as session:
        before = sheet_identity_snapshot(session)
        pending = _preflight(session, changes)
        for model, obj, bounded, kind, change, old, scale_uuid in pending:
            if "text" in change:
                with session.operation(model):
                    _replace_text(session, obj, change)
                    bounded.BoundRect = _native_rect(session, change.get("bounds_mm", old["bounds_mm"]))
            if "scale_id" in change:
                with session.operation(model):
                    set_parameter(session, obj, "ScaleId", change["scale_id"])
            if kind != "DrawingText":
                with session.operation(model):
                    placement = session.app.Math.CreatePlacement2D(
                        session.r.Point2D(*change.get("content_origin_mm", old["content_origin_mm"])),
                        session.r.Vector2D(*old["content_x_axis"]))
                    bounded.SetContentPlacement(placement)
            if "bounds_mm" in change or "fit_inset_mm" in change:
                with session.operation(model):
                    if "bounds_mm" in change:
                        bounded.BoundRect = _native_rect(session, change["bounds_mm"])
                    else:
                        bounded.FitBoundsToContent(change["fit_inset_mm"])
            committed.append(_record(session, obj, bounded, kind, change, old, scale_uuid))
        session.save()
    with Session(project) as reopened:
        if sheet_identity_snapshot(reopened) != before:
            raise RuntimeError("Native building/drawing/content identities or types changed")
        # Readback does not require the old numeric ScaleId to remain present.
        # The requested resource's persistent UUID is checked in _record.
        pending = _preflight(reopened, [{key: value for key, value in change.items() if key != "scale_id"}
                                       for change in changes])
        saved = []
        for (model, obj, bounded, kind, change, old, scale_uuid), expected in zip(pending, committed):
            # Scale IDs may be renumbered. Resolve the expected resource UUID;
            # never trust the old numeric ID as saved-state scale evidence.
            row = _record(reopened, obj, bounded, kind, change, expected, expected.get("scale_uuid"))
            if not _matches(row["bounds_mm"], expected["bounds_mm"]):
                raise RuntimeError("Saved presentation bounds changed after reopen")
            if kind == "DrawingText" and row["rich_text"] != expected["rich_text"]:
                raise RuntimeError("Saved rich-text tokens changed after reopen")
            saved.append(row)
        event("native_sheet_contents_reopened_verified", path=str(project), plan=plan,
              updated_objects=saved, computer_use_calls=0)
        return {"status": "saved_reopened_verified", "updated_objects": saved, "plan": plan,
                "identity_type_preservation_verified": True, "computer_use_calls": 0,
                "visual_layout_verified": False,
                "scope": "existing_native_content_centers_bounds_scales_and_plain_text_replacement",
                "limitations": ["No new sheet objects, section/elevation or schedule/table definitions",
                                "No dimension/Tag relocation or associative annotation verification",
                                "Text replacement writes plain paragraphs with explicit font, regular style and black color",
                                "Object identity checks do not certify visual layout or building geometry"]}
