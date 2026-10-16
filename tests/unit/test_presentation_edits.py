import copy
from contextlib import contextmanager
from types import SimpleNamespace as NS
from uuid import UUID, uuid4

import pytest

from renga_codex_bridge import presentation_edits as edits


DRAWING, VIEW, TEXT, SCALE = [str(uuid4()) for _ in range(4)]
TYPES = {kind: str(uuid4()) for kind in {*edits.EMBEDDED_TYPES, "DrawingText", "LinearDimension"}}


def request(uid=VIEW, **fields):
    return [{"drawing_uuid": DRAWING, "object_uuid": uid, **fields}]


def test_validation_normalizes_uuids_and_preserves_caller_plan():
    source = request(content_origin_mm=[1, 2], fit_inset_mm=0)
    source[0]["drawing_uuid"] = "{"+DRAWING.upper()+"}"
    result = edits.validate_content_changes(source)
    assert result[0]["drawing_uuid"] == DRAWING
    result[0]["content_origin_mm"][0] = 20
    assert source[0]["content_origin_mm"][0] == 1


@pytest.mark.parametrize("changes", [
    None, [], {}, [{"drawing_uuid": DRAWING}], request(),
    request(content_origin_mm=[0, 1, 2]), request(bounds_mm=[0, 0, 0, 10]),
    request(bounds_mm=[0, 10, 5, 4]), request(content_origin_mm=[True, 1]),
    request(bounds_mm=[0, float("inf"), 0, 10]), request(fit_inset_mm=-1),
    request(scale_id=0), request(scale_id=True), request(scale_id=2**31),
    request(bounds_mm=[0, 10, 0, 10], fit_inset_mm=1),
    request(font_family="Arial"), request(text="new"),
    request(text="new", font_family="Arial", cap_size_mm=True),
    request(text="new", font_family="Arial", cap_size_mm=101),
    request(text="bad\0", font_family="Arial", cap_size_mm=2.5),
    request(text="bad\r\n", font_family="Arial", cap_size_mm=2.5),
    request(text="new", font_family="", cap_size_mm=2.5),
    request(text="new", font_family="Arial\t", cap_size_mm=2.5),
    request(authorized=True), request(fit_inset_mm=1)+request(bounds_mm=[0, 10, 0, 10]),
])
def test_invalid_contract_is_rejected_before_open(changes):
    with pytest.raises(ValueError):
        edits.validate_content_changes(changes)


def test_empty_text_with_explicit_font_is_a_valid_clear_request():
    assert edits.validate_content_changes(request(TEXT, text="", font_family="Arial", cap_size_mm=2.5))[0]["text"] == ""


@pytest.mark.parametrize("actual,expected", [(False,False),(True,True),(0,False),(1,True),(-1,True),(b'\x00',False),(b'\x01',True),(b'\xff',True)])
def test_tlb_c_char_font_flags_are_not_python_bytes_truthiness(actual, expected):
    assert edits._native_bool(actual) is expected


class Collection:
    def __init__(self, items): self.items = items
    @property
    def Count(self): return len(self.items)
    def GetByIndex(self, index): return self.items[index]
    def GetByUniqueIdS(self, uid):
        return next((item for item in self.items if UUID(item.UniqueIdS.strip("{}")) == UUID(uid.strip("{}"))), None)
    def GetById(self, identifier): return next((item for item in self.items if item.Id == identifier), None)
    def Contains(self, identifier): return self.GetById(identifier) is not None


def token(text, family="Old Font", size=3.5):
    return NS(Text=text, FontFamily=family, FontCapSize=size,
              FontColor=NS(Red=1, Green=2, Blue=3, Alpha=255),
              FontStyle=NS(Bold=True, Italic=False, Underline=False))


class Document:
    def __init__(self): self.paragraphs = [[token("old first")], [token("old second")]]; self.removals = []
    @property
    def ParagraphCount(self): return len(self.paragraphs)
    def GetParagraph(self, index):
        tokens = self.paragraphs[index]
        return NS(TokenCount=len(tokens), GetToken=lambda index: tokens[index])
    def RemoveParagraph(self, index): self.removals.append(index); self.paragraphs.pop(index)
    def AppendParagraph(self, tokens): self.paragraphs.append(copy.deepcopy(tokens))


class Bounded:
    def __init__(self):
        self.rect = NS(Left=10., Right=30., Bottom=20., Top=50.)
        self.pose = NS(Origin=NS(X=20., Y=35.), AxisX=NS(X=0., Y=1.))
        self.HasContent = True
        self.document = Document()
    @property
    def BoundRect(self): return copy.deepcopy(self.rect)
    @BoundRect.setter
    def BoundRect(self, rect): self.rect = copy.deepcopy(rect)
    def GetContentPlacement(self): return copy.deepcopy(self.pose)
    def SetContentPlacement(self, placement): self.pose = copy.deepcopy(placement)
    def FitBoundsToContent(self, inset):
        x, y = self.pose.Origin.X, self.pose.Origin.Y
        self.rect = NS(Left=x-10-inset, Right=x+10+inset, Bottom=y-15-inset, Top=y+15+inset)
    def GetRichTextDocument(self): return self.document


def fixture(monkeypatch, *, view_kind="EmbeddedEntityView"):
    bounded, text = Bounded(), Bounded()
    view = NS(Id=10, UniqueIdS=VIEW, ObjectTypeS=TYPES[view_kind], QueryInterface=lambda name: bounded,
              values={"ScaleId": {"value": 5, "readonly": False}})
    drawing_text = NS(Id=11, UniqueIdS=TEXT, ObjectTypeS=TYPES["DrawingText"], QueryInterface=lambda name: text,
                      values={})
    model = NS(GetObjects=lambda: Collection([view, drawing_text]))
    drawing = NS(Id=12, UniqueIdS=DRAWING, TypeIdS=str(uuid4()), QueryInterface=lambda name: model)
    scale = NS(Id=5, UniqueIdS=SCALE)
    project = NS(Drawings2=Collection([drawing]), Scales=Collection([scale]))
    state = {"operations": [], "saves": 0, "sessions": [], "on_save": None}
    @contextmanager
    def operation(model=None):
        state["operations"].append(model)
        yield
    def save():
        state["saves"] += 1
        if state["on_save"]: state["on_save"]()
    class Session:
        def __init__(self, path, **options):
            self.project, self.path, self.sdk = project, path, NS(types=TYPES)
            self.operation, self.save = operation, save
            self.r = NS(IModel="model", ITextObject="text", IRectBoundedObject="bounded",
                Rect=lambda: NS(), Point2D=lambda x,y: NS(X=x,Y=y), Vector2D=lambda x,y: NS(X=x,Y=y),
                RichTextToken=lambda: token("", "", 0),
                Color=lambda r,g,b,a: NS(Red=r,Green=g,Blue=b,Alpha=a),
                FontStyle=lambda b,i,u: NS(Bold=b,Italic=i,Underline=u))
            self.app = NS(Math=NS(CreatePlacement2D=lambda origin, axis: NS(Origin=origin, AxisX=axis)))
            self.options = options
        def __enter__(self): state["sessions"].append(self.options); return self
        def __exit__(self, *args): return False
    def identities(session):
        return {"building": {"unchanged": "type"}, "drawings": {
            drawing.UniqueIdS: {obj.UniqueIdS: obj.ObjectTypeS for obj in (view, drawing_text)}}}
    monkeypatch.setattr(edits, "Session", Session)
    monkeypatch.setattr(edits, "parameters", lambda session,obj: copy.deepcopy(obj.values))
    monkeypatch.setattr(edits, "set_parameter", lambda session,obj,key,value: obj.values[key].update(value=value))
    monkeypatch.setattr(edits, "sheet_identity_snapshot", identities)
    monkeypatch.setattr(edits, "save_plan", lambda plan: "saved-plan.json")
    monkeypatch.setattr(edits, "event", lambda *args, **kwargs: None)
    return state, view, bounded, drawing_text, text, scale


def test_moving_and_fitting_preserves_orientation_and_saved_uuid(monkeypatch):
    state, view, bounded, _, _, _ = fixture(monkeypatch)
    result = edits.update_sheet_contents("test.rnp", request(content_origin_mm=[60, 90], fit_inset_mm=1))
    row = result["updated_objects"][0]
    assert row["content_origin_mm"] == [60, 90]
    assert row["content_x_axis"] == [0, 1]
    assert row["bounds_mm"] == [49, 71, 74, 106]
    assert row["object_uuid"] == VIEW
    assert state["sessions"] == [{"write": True}, {}] and state["saves"] == 1
    assert not result["visual_layout_verified"] and result["computer_use_calls"] == 0


def test_explicit_view_bounds_and_scale_saved_by_resource_uuid(monkeypatch):
    state, view, bounded, _, _, scale = fixture(monkeypatch)
    def renumber():
        scale.Id = 99
        view.values["ScaleId"]["value"] = 99
        view.Id = 100
    state["on_save"] = renumber
    result = edits.update_sheet_contents("test.rnp", request(scale_id=5, bounds_mm=[1, 2, 3, 4]))
    assert result["updated_objects"][0]["scale_uuid"] == SCALE
    assert result["updated_objects"][0]["scale_id"] == 99
    assert result["updated_objects"][0]["bounds_mm"] == [1, 2, 3, 4]


def test_text_bounds_preserve_every_exposed_token_field(monkeypatch):
    _, _, _, _, text, _ = fixture(monkeypatch)
    before = copy.deepcopy(text.document.paragraphs)
    result = edits.update_sheet_contents("test.rnp", request(TEXT, bounds_mm=[2, 20, 40, 50]))
    assert result["updated_objects"][0]["text"] == "old first\nold second"
    assert text.document.paragraphs == before


def test_text_replacement_removes_old_paragraphs_backwards_and_verifies_tokens(monkeypatch):
    _, _, _, _, text, _ = fixture(monkeypatch)
    result = edits.update_sheet_contents("test.rnp", request(TEXT, text="новая\nстрока", font_family="Arial", cap_size_mm=2.5))
    row = result["updated_objects"][0]
    assert row["text"] == "новая\nстрока"
    assert text.document.removals == [1, 0]
    assert row["bounds_mm"] == [10, 30, 20, 50]
    assert not any(row["rich_text"][0][0]["font_style"].values())
    assert row["text_font_check"] == {"checked_nonempty_tokens": 2, "status": "verified"}


def test_empty_text_clears_without_deleting_object(monkeypatch):
    _, _, _, _, text, _ = fixture(monkeypatch)
    result = edits.update_sheet_contents("test.rnp", request(TEXT, text="", font_family="Arial", cap_size_mm=2.5))
    assert result["updated_objects"][0]["text"] == ""
    assert result["updated_objects"][0]["rich_text"] == []
    assert result["updated_objects"][0]["text_font_check"]["status"] == "not_applicable_empty_text"


@pytest.mark.parametrize("change", [
    {"object_uuid": str(uuid4()), "bounds_mm": [0,1,0,1]},
    {"drawing_uuid": str(uuid4()), "bounds_mm": [0,1,0,1]},
    {"scale_id": 77},
])
def test_all_objects_and_resources_preflight_before_any_mutation(monkeypatch, change):
    state, *_ = fixture(monkeypatch)
    invalid = {"drawing_uuid": DRAWING, "object_uuid": VIEW, **change}
    with pytest.raises(ValueError):
        edits.update_sheet_contents("test.rnp", request(TEXT, bounds_mm=[1,2,3,4])+[invalid])
    assert not state["operations"] and state["saves"] == 0


@pytest.mark.parametrize("kind", ["EmbeddedTable", "EmbeddedSchedule"])
def test_tables_cannot_be_scaled_as_model_views(monkeypatch, kind):
    state, *_ = fixture(monkeypatch, view_kind=kind)
    with pytest.raises(ValueError, match="only"):
        edits.update_sheet_contents("test.rnp", request(scale_id=5))
    assert not state["operations"]


def test_unsupported_annotation_never_receives_a_setter(monkeypatch):
    state, *_ = fixture(monkeypatch, view_kind="LinearDimension")
    with pytest.raises(NotImplementedError):
        edits.update_sheet_contents("test.rnp", request(bounds_mm=[1,2,3,4]))
    assert not state["operations"]


def test_native_scale_readonly_is_not_bypassed(monkeypatch):
    state, view, *_ = fixture(monkeypatch)
    view.values["ScaleId"]["readonly"] = True
    with pytest.raises(ValueError, match="read-only"):
        edits.update_sheet_contents("test.rnp", request(scale_id=5))
    assert not state["operations"]


def test_missing_document_paragraph_editor_fails_all_preflight_before_mutation(monkeypatch):
    state, _, _, _, text, _ = fixture(monkeypatch)
    text.document.RemoveParagraph = None
    with pytest.raises(NotImplementedError, match="RemoveParagraph"):
        edits.update_sheet_contents("test.rnp", request(content_origin_mm=[80,90]) +
            request(TEXT, text="new", font_family="Arial", cap_size_mm=2.5))
    assert not state["operations"] and state["saves"] == 0


def test_embedded_view_cannot_receive_text_replacement(monkeypatch):
    state, *_ = fixture(monkeypatch)
    with pytest.raises(ValueError, match="only"):
        edits.update_sheet_contents("test.rnp", request(text="new", font_family="Arial", cap_size_mm=2.5))
    assert not state["operations"]


def test_text_cannot_receive_content_origin_setter(monkeypatch):
    state, *_ = fixture(monkeypatch)
    with pytest.raises(NotImplementedError, match="DrawingText"):
        edits.update_sheet_contents("test.rnp", request(TEXT, content_origin_mm=[80,90]))
    assert not state["operations"]


def test_embedded_object_without_native_content_is_not_treated_as_valid_view(monkeypatch):
    state, _, bounded, *_ = fixture(monkeypatch)
    bounded.HasContent = False
    with pytest.raises(ValueError, match="no native content"):
        edits.update_sheet_contents("test.rnp", request(content_origin_mm=[80,90]))
    assert not state["operations"]


@pytest.mark.parametrize("edge", ["degenerate", "nonfinite"])
def test_invalid_native_bounds_are_rejected_during_preflight(monkeypatch, edge):
    state, _, bounded, *_ = fixture(monkeypatch)
    bounded.rect.Right = bounded.rect.Left if edge == "degenerate" else float("inf")
    with pytest.raises(RuntimeError, match="bounds"):
        edits.update_sheet_contents("test.rnp", request(content_origin_mm=[80,90]))
    assert not state["operations"] and state["saves"] == 0


@pytest.mark.parametrize("corrupt", ["identity", "type", "bounds", "center", "axis", "scale", "text", "font"])
def test_post_save_corruption_cannot_be_reported_successful(monkeypatch, corrupt):
    state, view, bounded, drawing_text, text, scale = fixture(monkeypatch)
    def corruption():
        if corrupt == "identity": view.UniqueIdS = str(uuid4())
        elif corrupt == "type": view.ObjectTypeS = str(uuid4())
        elif corrupt == "bounds": bounded.rect.Right += 1
        elif corrupt == "center": bounded.pose.Origin.X += 1
        elif corrupt == "axis": bounded.pose.AxisX = NS(X=1.,Y=0.)
        elif corrupt == "scale": scale.UniqueIdS = str(uuid4())
        elif corrupt == "text": text.document.paragraphs[0][0].Text = "not saved"
        else: text.document.paragraphs[0][0].FontFamily = "not saved font"
    state["on_save"] = corruption
    changes = request(content_origin_mm=[50,60], fit_inset_mm=1, scale_id=5)
    changes += request(TEXT, text="new", font_family="Arial", cap_size_mm=2.5)
    with pytest.raises(RuntimeError, match="changed|differs"):
        edits.update_sheet_contents("test.rnp", changes)
