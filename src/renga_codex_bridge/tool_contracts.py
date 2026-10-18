"""Strict transport schemas for existing-resource and sheet-append tools.

Native semantics stay in the public validators. These models perform no COM,
create no resources and do not establish native integration support. Omitted
optional fields remain omitted when converted with plain_requests.
"""
from __future__ import annotations

import copy
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, StrictBool, StrictFloat, StrictInt, StrictStr, model_validator

from .existing_properties import validate_existing_property_changes
from .resource_edits import validate_window_style_changes
from .sheet_additions import validate_schedule_additions
from .sheet_views import validate_view_additions


NativeId = Annotated[StrictInt, Field(gt=0, le=2**31 - 1)]
NativeInt32 = Annotated[StrictInt, Field(ge=-(2**31), lt=2**31)]
FiniteNumber = StrictInt | StrictFloat
Primitive = StrictBool | StrictInt | StrictFloat | StrictStr
Text = Annotated[StrictStr, Field(pattern=r"^[^\x00]*$")]
Name = Annotated[Text, Field(min_length=1, json_schema_extra={"allOf": [{"pattern": r"\S"}]})]
PositiveLength = Annotated[StrictInt, Field(gt=0)] | Annotated[StrictFloat, Field(gt=0)]
NonnegativeLength = Annotated[StrictInt, Field(ge=0)] | Annotated[StrictFloat, Field(ge=0)]
Point2 = Annotated[list[FiniteNumber], Field(min_length=2, max_length=2)]
Rectangle = Annotated[list[FiniteNumber], Field(min_length=4, max_length=4)]


class _Contract(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True, allow_inf_nan=False)


def _omitted():
    """Internal omission sentinel, never an advertised JSON null default."""
    return None


class _WindowParameters(_Contract):
    # Nonnullable annotations reject explicit null; defaults only represent
    # omission and are removed by exclude_unset before the public validator.
    EntityName: Name = Field(default_factory=_omitted)
    FrameThickness: PositiveLength = Field(default_factory=_omitted)
    FrameDepth: PositiveLength = Field(default_factory=_omitted)
    VerticalMullionThickness: PositiveLength = Field(default_factory=_omitted)
    HorizontalMullionThickness: PositiveLength = Field(default_factory=_omitted)
    WindowLiningThickness: PositiveLength = Field(default_factory=_omitted)
    WindowLiningDepth: PositiveLength = Field(default_factory=_omitted)


class WindowStyleChange(_Contract):
    model_config = ConfigDict(extra="forbid", strict=True, allow_inf_nan=False,
        json_schema_extra={"anyOf": [
            {"required": ["material_uuid"]},
            {"required": ["parameters"], "properties": {"parameters": {"minProperties": 1}}},
        ]})
    resource_uuid: StrictStr
    expected_name: Name
    parameters: _WindowParameters = Field(default_factory=_omitted)
    material_uuid: StrictStr = Field(default_factory=_omitted)

    @model_validator(mode="after")
    def native_contract(self):
        validate_window_style_changes([self.model_dump(exclude_unset=True)])
        return self


class ExistingPropertyChange(_Contract):
    kind: Literal["Project", "Drawing", "Topic"]
    uuid: StrictStr
    property_guid: StrictStr
    property_name: Name
    value: Text

    @model_validator(mode="after")
    def native_contract(self):
        validate_existing_property_changes([self.model_dump(exclude_unset=True)])
        return self


class TitleBlockCellCheck(_Contract):
    drawing_uuid: StrictStr
    block_index: Annotated[StrictInt, Field(ge=0, le=99)]
    block_name: Name
    column: Annotated[StrictInt, Field(ge=0, le=9999)]
    row: Annotated[StrictInt, Field(ge=0, le=9999)]
    expected_before: Text
    expected_value: Text

    @model_validator(mode="after")
    def native_contract(self):
        # Reuse the public cell validator, whose API also requires one property
        # request. This shape-only stub is never dispatched or executed.
        stub = {"kind": "Drawing", "uuid": self.drawing_uuid,
                "property_guid": self.drawing_uuid, "property_name": "validation", "value": ""}
        validate_existing_property_changes([stub], [self.model_dump(exclude_unset=True)])
        return self


class ScheduleAddition(_Contract):
    drawing_uuid: StrictStr
    schedule_id: NativeId
    available_bounds_mm: Rectangle
    fit_inset_mm: NonnegativeLength = Field(default_factory=_omitted)

    @model_validator(mode="after")
    def native_contract(self):
        validate_schedule_additions([self.model_dump(exclude_unset=True)])
        return self


class _CommonViewParameters(_Contract):
    SectionPlaneOffset: Primitive = Field(default_factory=_omitted)
    VisualStyle: NativeInt32 = Field(default_factory=_omitted)
    DisplayStyleId: NativeId = Field(default_factory=_omitted)
    FilterId: NativeId = Field(default_factory=_omitted)
    ObjectPartBeyondViewDepthPlane: StrictBool = Field(default_factory=_omitted)
    ViewName: Primitive = Field(default_factory=_omitted)


class _ModelViewParameters(_CommonViewParameters):
    ViewDepthLevelId: NativeId = Field(default_factory=_omitted)
    LevelViewDepthPlaneOffset: Primitive = Field(default_factory=_omitted)
    SectionViewDepthPlaneOffset: Primitive = Field(default_factory=_omitted)
    ModelViewDirection: NativeInt32 = Field(default_factory=_omitted)
    ProjectionType: NativeInt32 = Field(default_factory=_omitted)
    AxonometricAxesOrientation: NativeInt32 = Field(default_factory=_omitted)


class _EntityViewParameters(_CommonViewParameters):
    ObjectViewDirection: NativeInt32 = Field(default_factory=_omitted)
    ViewDepthPlaneOffset: Primitive = Field(default_factory=_omitted)


class _ViewAddition(_Contract):
    drawing_uuid: StrictStr
    source_entity_id: NativeId
    scale_id: NativeId
    origin_mm: Point2
    bounds_mm: Rectangle = Field(default_factory=_omitted)
    fit_inset_mm: NonnegativeLength = Field(default_factory=_omitted)

    @model_validator(mode="after")
    def native_contract(self):
        validate_view_additions([self.model_dump(exclude_unset=True)])
        return self


class ModelViewAddition(_ViewAddition):
    kind: Literal["model"]
    view_parameters: _ModelViewParameters = Field(default_factory=_omitted)


class EntityViewAddition(_ViewAddition):
    kind: Literal["entity"]
    object_mark: Name
    view_parameters: _EntityViewParameters = Field(default_factory=_omitted)


ViewAddition = Annotated[ModelViewAddition | EntityViewAddition, Field(discriminator="kind")]


def plain_requests(rows):
    """Detach models or raw dictionaries; retain omitted optional fields.

    Raw dictionaries remain supported for direct function/worker tests. Public
    batch validators still reject extra keys, duplicates and invalid geometry.
    """
    if not isinstance(rows, list):
        raise ValueError("Requests require a list of models or dictionaries")
    result = []
    for row in rows:
        if isinstance(row, BaseModel):
            result.append(row.model_dump(exclude_unset=True))
        elif isinstance(row, dict):
            result.append(copy.deepcopy(row))
        else:
            raise ValueError("Each request must be a model or dictionary")
    return result
