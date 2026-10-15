# Inventory performance: preserve live values

Research date: 2026-10-15; installed SDK/API 2.50. No Renga server, COM
activation or Computer Use was invoked for this investigation. Native timing
measurements belong to the separate synthetic/instructional-model test record.

## Implemented: definition-only Session cache

`model.parameters` caches only `IParameterDefinition` data, keyed by parameter
GUID on the current Session instance: Text, Name, ParameterType,
ReferencedEntityTypeS and EnumerationItemTexts. These are definition metadata,
not an object's parameter value or writable state. Plain scalar/tuple data are
stored; no COM interface is retained. Each returned row gets its own dict and
enumeration list, so caller mutation cannot poison the cache.

The actual value, `HasValue`, `IsReadOnly` and `ValueType` remain fresh native
reads for every object and every call. A new Session has a new cache, including
the Session that reopens the saved model. The result shape and field order are
preserved. Portable tests change value, writable state, value presence and value
type, compare objects with the same parameter GUID, and verify separate-session
metadata reads and caller-mutation isolation. They establish this caching
boundary, not a native speedup or saved-model correctness by themselves.
[IParameterDefinition](https://help.rengabim.com/api/interface_i_parameter_definition.html),
[IParameter](https://help.rengabim.com/api/interface_i_parameter.html),
[cache tests](../tests/unit/test_parameter_metadata_cache.py).

## Quantities: GetIds is absent

Both the official reference and the already generated local type-library
wrapper declare exactly `Contains`, `Get`, `ContainsS` and `GetS` on
`IQuantityContainer`. There is no `GetIds` method. The wrapper was inspected as
Python source with AST, without importing it, activating a server or copying it
into the repository. A same-named method on `IParameterContainer` is not a
quantity-enumeration API.
[IQuantityContainer](https://help.rengabim.com/api/interface_i_quantity_container.html).

The existing quantity loop remains unchanged: it checks actual support on each
object and reads quantities with `HasValue` and the original unit conversion
branches. Quantity availability or values are **not** cached by object type;
different elements of one type can have different supported or initialized
quantities. Unknown quantity types retain their original native text/type
output.

The reference documents `Get` returning a null quantity when unsupported, with
`GetS` having the same behavior for a string GUID. A future bounded native test
may therefore evaluate direct `GetS` followed by a null check to avoid the
additional `ContainsS` call for supported quantities. This is a documented
optimization candidate, **not implemented or natively verified here**. It still
would iterate the SDK quantity identifiers and would not invent `GetIds` or
weaken per-object, per-reopen value checks.
