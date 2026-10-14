# Native dimension API research

Assessed interface: Renga API 2.50. Research date: 2026-10-14. No COM connection, UI action or native creation attempt was performed for this module. Previous internal dimension workflows were reviewed only to establish which operations they contained; their geometry, model identifiers and user documents were not copied.

## Supported evidence versus missing creation contract

`LinearDimension` is a declared entity type and supports `DimensionValue`, `DimensionValueType`, text-style and landing-line-orientation parameters. This supports inspecting an existing native model dimension. A known entity GUID is not itself a supported constructor. [Entity types](https://help.rengabim.com/api/group___entity_types.html), [entity/parameter table](https://help.rengabim.com/api/group___entity_type_by_parameters.html).

The documented `IModel.CreateObject` table does not list LinearDimension for any model scope. `INewEntityArgs` provides type, host, style/category and placement, but no dimension endpoints or defining-feature bindings. The reviewed SDK/type library contains no documented `ILinearDimension`, `IDimension`, `DefiningFeatureDescription` constructor or binding setter. No native endpoint/axis feature-ID enum was established; the module must not invent one. [IModel.CreateObject](https://help.rengabim.com/api/interface_i_model.html), [INewEntityArgs](https://help.rengabim.com/api/interface_i_new_entity_args.html).

The previous internal scripts contained a plan for native UI construction and later parameter readback. They were not an API constructor. Therefore they provide no programmatic creation method to port into an API-only product. API 2.50 creation is classified `API_LIMITATION` for this implementation's documented scope; a newer API is `NOT_VERIFIED` until separately researched. No assertion is made that private internals or a future vendor API could never support it.

## Computed values are not arbitrary labels

The documented enum is **1 = dimension value**, **2 = text**. The reader accepts only mode 1 and rejects text overrides even when the overridden string looks numeric. `DimensionValue` is read through its native string getter; in prior native observations it was read-only for a computed dimension. It is an exposed display value, not a documented full-precision endpoint distance. [Parameters](https://help.rengabim.com/api/group___parameters.html), [IParameter](https://help.rengabim.com/api/interface_i_parameter.html).

The decimal convention is an explicit input. Units, prefixes, thousands grouping and mixed separators are rejected, rather than guessed. A string such as `3,000` cannot be treated silently as three thousand under an unspecified locale. The module preserves the source string, returns its numeric display interpretation and labels the measurement scope. Units are not inferred from a parameter name.

## Module contract

`src/renga_codex_bridge/dimensions.py` has no vendor GUID constants, legacy global type tables, session activation, file writing or GUI fallback. Type/parameter GUIDs come from the caller's locally loaded `session.sdk`.

| Function | Behaviour |
|---|---|
| `dimension_capability(api_version)` | Returns the researched creation limitation; native read tests for this new module are not yet claimed |
| `requested_distance_mm(points_mm, orientation)` | Pure independent expected-distance calculation from explicit points; creates no BIM object |
| `create_native_linear_dimension(session, points_mm=..., feature_refs=...)` | Validates explicit request shape and raises `NativeDimensionCreationUnavailable` before any COM mutation |
| `parse_dimension_display_value(text, decimal_separator=...)` | Strict numeric interpretation of a getter string; no hidden precision/unit claim |
| `read_native_linear_dimension(session, unique_id, ...)` | Resolves a persistent UUID, checks native type and computed mode, then reads the actual parameter string |
| `verify_native_linear_dimension(session, unique_id, expected_display_value, ...)` | Compares that native computed display value with an explicit expected value/tolerance |

`feature_refs` in the rejected creation request are caller data, not proven native binding descriptors. Shape validation neither validates a feature ID against Renga nor implies a creation path exists. The module supplies no default feature IDs, inferred axis references, fake line object or `DrawingText` replacement.

The optional `model` argument to the reader selects an existing model context. A sheet annotation exposed as an SDK `UndefinedObject` is not accepted as a model LinearDimension and is not decoded through undocumented internal GUIDs.

## Saved-output verification

The caller must use the owned-session lifecycle: save, close, reopen the native file, resolve the same UUID, and call the reader/verifier on that reopened state. These functions alone do not perform this lifecycle and explicitly return `persistence_verified_by_this_reader=False`. A matching getter before save is not persisted evidence.

A future native integration test should use an existing synthetic project containing genuine native dimensions, check that computed mode 1 and values persist, reject mode-2 overrides, and record locale/display-unit settings. It should independently compare the relevant model geometry where possible. It must not create the test fixture through Computer Use as part of an advertised API-only run. Pure parser/request tests cannot promote native reading or creation to `IMPLEMENTED_AND_TESTED`.

Creation remains unavailable unless a documented constructor and feature-binding contract are found and a real native test proves computed values survive saving and opening again. Returning a successful text label, manually setting a value string, or creating an unbound zero/default dimension would not satisfy that requirement.

Краткий вывод: API 2.50 позволяет читать параметры существующего вычисляемого размера. Поддержанного способа создать и привязать новый линейный размер в исследованных интерфейсах не найдено. Модуль честно отклоняет создание и не заменяет размер текстом; проверка сохранения остаётся обязанностью вызывающего сценария.
