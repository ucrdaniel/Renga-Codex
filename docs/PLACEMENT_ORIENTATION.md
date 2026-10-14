# Explicit creation placement

The input helper validates finite, unit, perpendicular `x_axis` and `z_axis`
vectors. It rejects scaled axes instead of normalizing them silently. Defaults
are `[1,0,0]` and `[0,0,1]`. The horizontal Wall/Floor/Room/Roof/Opening/Stair/
Ramp/WallFoundation/Door/Window contract currently permits yaw with positive
global Z. Other mathematically valid axes do not establish native category
support. Nondefault Level axes are rejected pending a persistent API route.

The adapter must put the axes into the typed
[`INewEntityArgs.Placement3D`](https://help.rengabim.com/api/interface_i_new_entity_args.html)
record **before** `CreateObject`. Native create/setter return alone is not
verification: inspect `ILevelObject.GetPlacement` after saving and reopening,
comparing requested origin, X-axis and Z-axis. A reversed X-axis can change
Door/Window facing while leaving the origin unchanged. Pure helper tests are
not evidence of persisted Renga support. This helper introduces no operation
that rotates an existing object.

## Hosted doors and windows

For a straight wall, the SDK defines co-directed placement X-axis as the host's
outer side and counter-directed X-axis as its inner side. `DoorOrientation`
(left/right) is separate from this side choice. A wall from `(1000,0)` to
`(1000,6000)` therefore needs X-axis `[0,1,0]` or `[0,-1,0]`; the universal
default `[1,0,0]` does not specify either supported relation.

Read the actual host and its straight baseline in a declared global coordinate
system before deriving its direction. The adapter should check native
`Curve2DType_LineSegment` and reject curved or composite hosts for this initial
contract. `validate_wall_host_orientation` checks the measured endpoint delta;
it does not obtain COM geometry, select the host or invent a tangent for a
curved wall. At a nonzero level, record the native level/offset interpretation
separately from axis facing.

## Baseline coordinates

The current model helper uses
[`IBaseline2DObject.SetBaseline/GetBaseline`](https://help.rengabim.com/api/interface_i_baseline2_d_object.html),
which explicitly operates in the **object's own coordinate system**. Therefore
JSON `points` are object-local millimeter coordinates; changing creation origin
or axes also changes their world-space position. Do not add global XY coordinates
to a nonzero origin and treat that as the same contour.

Example: local wall points `[[0,0],[6000,0]]`, origin `[1000,2000,0]`, X-axis
`[0,1,0]` and Z-axis `[0,0,1]` request a world wall from `(1000,2000)` to
`(1000,8000)`. This is a coordinate-contract example, not a claim that its
requested placement has been tested in the installed Renga.

Global-coordinate baseline support requires the separate documented
`SetBaselineInCS/GetBaselineInCS` methods and independent native geometry tests.
The existing `baseline3d` action already uses an explicit identity
`Placement3D`, so its two points have a different declared coordinate space;
they are global millimeter points, not the local `points` convention above.

Сокращённо: оси создания задаются явно, масштабированные векторы отвергаются.
Сторона двери/окна зависит от направления реальной стены; направление открывания
задаётся отдельно. Точки `SetBaseline` локальны для объекта. После сохранения
необходимо сравнить начало координат и обе оси, а также геометрию.
