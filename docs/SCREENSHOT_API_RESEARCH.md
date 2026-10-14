# Native screenshot interface: verified API route and registration findings

Verified on Renga **9.3.32980.0**, SDK/API **2.50**, Python **3.12.14**. The current
bridge successfully rendered a real Level view as a 1024 × 768 PNG through
`IModelView.GetInterfaceByName("IScreenshotService")` and dynamic `IDispatch`.
The application was made visible through its official API in a separately
verified, bridge-owned process. No registry changes, Computer Use or attachment
to a user's existing Renga session were required.

Direct typed `QueryInterface(IScreenshotService)` returned `E_NOINTERFACE` in
this installation. That failed binding route is retained as evidence; it does
not mean that native rendering is unavailable. Success here covers the tested
Level view and environment, not every view, edition or hidden/headless mode.

## Documented acquisition

[`IScreenshotService`](https://help.rengabim.com/api/interface_i_screenshot_service.html)
is an additional interface of model views: Building, Assembly, Level and Drawing.
The [changelog](https://help.rengabim.com/api/_changelog.html) places Level support
in API 2.48/Renga 9.1, Drawing support in 2.44/Renga 8.10 and 3D support in
2.21/Renga 5.5. The researched 9.3 version is newer than those introductions.

`IView` exposes only its identity and type. The alternative named getter belongs
to [`IModelView`](https://help.rengabim.com/api/interface_i_model_view.html),
not to typed `IView`. The implemented route on an already bridge-owned session
is equivalent to the following. Use the exact `ImageFormat_PNG` enum name:

```python
from comtypes import COMError
from comtypes.client.dynamic import Dispatch

session.app.Visible = True
view = session.app.OpenViewByEntity(inspected_entity_id)
try:
    service = view.QueryInterface(session.r.IScreenshotService)
except COMError as error:
    if error.hresult != -2147467262:  # E_NOINTERFACE
        raise
    model_view = view.QueryInterface(session.r.IModelView)
    service = Dispatch(model_view.GetInterfaceByName("IScreenshotService"))
settings = service.CreateSettings()
settings.Width, settings.Height = 1024, 768
image = service.MakeScreenshot(settings)
image.SaveToFile(validated_new_png_path, session.r.ImageFormat_PNG)
```

For a Building 3D view, the documented `OpenViewByEntity` input is
`Project.BuildingInfo.Id`; for Level/Drawing use the actual inspected current
entity ID. Do not reuse a pre-SaveAs numeric ID. `IApplication.Visible=True` is
the tested bridge configuration; the owned session closes its own process
afterwards. The examined documentation does **not** state that visibility is a
universal screenshot prerequisite, and the successful visible test does not
establish hidden/headless support. Readback must confirm the intended represented
entity, and failures other than `E_NOINTERFACE` must not be swallowed.

## Local type information and registration

Local generated type information describes `IScreenshotService`,
`IScreenshotSettings` and `IImage` as dual, nonextensible, oleautomation
interfaces derived from `IDispatch` (and therefore `IUnknown`). Their metadata
does not describe a raw in-process pointer-only interface. No generated wrappers,
SDK binaries or vendor source are included in this public repository.

Read-only inspection of the local merged 64-bit interface registry found:

| Interface | IID | Proxy/type-library registration |
|---|---|---|
| IView | `86AE7780-872D-421B-AEB4-A984A5A9AFC8` | Present |
| IModelView | `26E2531E-BEBB-4691-817D-D47C932D05E5` | Present |
| IImage | `38BD3999-A5F5-4B19-A59B-99E5C41BED1D` | Present |
| IScreenshotService | `D3AF0C63-0929-4E7F-A4A6-04849DBFA2E6` | Absent in this setup |
| IScreenshotSettings | `F21FC0E1-F0C0-46DF-9AE1-54A7C03FDAA9` | Absent in this setup |

The present entries use OLE's automation proxy
`00020424-0000-0000-C000-000000000046` and Renga's type-library identifier
`0EC5D324-8B9F-4D30-84ED-AB711618D1C1`, version `1.0`. These are public interface
metadata, not machine or model identities.

Microsoft documents how
[interface registration](https://learn.microsoft.com/en-us/previous-versions/windows/desktop/automat/registering-interfaces)
locates interprocess remoting code, and how
[type-library marshaling](https://learn.microsoft.com/en-us/windows/win32/com/marshaling-details)
can handle custom automation-compatible interfaces. **Inference:** the missing
entries may explain why a custom-IID query fails across the process boundary.
The successful named-dispatch route demonstrates that this server can provide
the service across the process boundary. Missing registry entries remain a
possible explanation for the typed-route failure, not a proven root cause or a
reason to alter vendor registration. The working bridge keeps the late
`IDispatch` calls on the same owned STA and uses the documented service methods.
Never reinterpret a generic `IDispatch` pointer as a custom typed interface to
bypass `QueryInterface`.

The examined SDK samples and cached official SampleScripts did not contain a
screenshot example. The SDK's general C++ application helper defaults to an
in-process context, but that default does not establish a screenshot-specific
restriction. The current working external route directly disproves a general
claim that this screenshot service is available only to in-process plugins.

## Acceptance evidence

The frozen core acceptance run passed 22 checks, including
`native_view_render_without_computer_use`; its render response recorded
`route="named_dispatch"` and `computer_use_calls=0`. The output PNG had 17,540
bytes, IHDR dimensions 1024 × 768 and SHA-256
`b7a34f3be64c3604d1570a05531a343ed10b8c30fa9ba7583ded16433017d356`.
Read-only visual inspection confirmed a nonblank native plan with walls,
openings and a room label. This is not a claim of drawing annotation completeness
or presentation quality. The reproducible test source is
[run_live_tests.py](../scripts/run_live_tests.py); raw local models and operation
logs stay outside the public source repository.

A non-null interface or PNG signature alone remains insufficient for future
scenarios. Check image dimensions and intended content, record the actual
version/view/route, and retain failed acquisition routes. Other view types and
hidden operation require their own tests before capability claims.

Кратко: нативный снимок плана Level реально получен через официальный API,
`GetInterfaceByName` и `IDispatch` в собственной видимой Renga. Прямой
типизированный QI в этой установке возвращает `E_NOINTERFACE`; реестр не менялся.
Успешный тест не доказывает поддержку всех видов или фонового режима.
