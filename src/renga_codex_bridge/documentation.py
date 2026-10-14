from .session import Session
from .model import parameters,set_parameter
from .safety import checked_path,fingerprint
from .audit import event,save_plan
from .operations import matches

def snapshot(s):
    result=[]
    for i in range(s.project.Drawings2.Count):
        drawing=s.project.Drawings2.GetByIndex(i);objects=drawing.QueryInterface(s.r.IModel).GetObjects()
        rows=[]
        for j in range(objects.Count):
            obj=objects.GetByIndex(j)
            row={'id':obj.Id,'uuid':obj.UniqueIdS,'name':obj.Name,'type_guid':obj.ObjectTypeS,
                 'parameters':parameters(s,obj)}
            if obj.ObjectTypeS.upper()==s.sdk.types['DrawingText']:
                document=obj.QueryInterface(s.r.ITextObject).GetRichTextDocument()
                row['text']='\n'.join(''.join(document.GetParagraph(k).GetToken(t).Text for t in range(document.GetParagraph(k).TokenCount)) for k in range(document.ParagraphCount))
            if obj.ObjectTypeS.upper() in {s.sdk.types['EmbeddedModelView'],s.sdk.types['EmbeddedSchedule']}:
                bounds=obj.QueryInterface(s.r.IRectBoundedObject)
                row['has_content']=bounds.HasContent
                rect=bounds.BoundRect
                row['bounds_mm']=[rect.Left,rect.Right,rect.Bottom,rect.Top]
            rows.append(row)
        result.append({'id':drawing.Id,'uuid':drawing.UniqueIdS,'name':drawing.Name,
                       'parameters':parameters(s,drawing),'objects':rows})
    return result

def create_plans(project,drawings):
    if not isinstance(drawings,list) or not drawings:raise ValueError('At least one explicit drawing specification required')
    for specification in drawings:
        if not isinstance(specification,dict):raise ValueError('Drawing specification must be an object')
        for key in ('level_id','scale_id'):
            if isinstance(specification.get(key),bool) or not isinstance(specification.get(key),int) or specification[key]<=0:raise ValueError('Inspect an existing positive '+key+' before creation')
        if not isinstance(specification.get('parameters',{}),dict):raise ValueError('Drawing parameters must be an object')
    plan=save_plan({'action':'create_native_drawings','project':project,'drawings':drawings})
    created=[];specs={};object_requests={};text_requests={}
    with Session(project,write=True) as s:
        for specification in drawings:
            with s.operation():
                args=s.project.Drawings2.CreateNewEntityArgs();args.TypeIdS=s.sdk.types['Drawing']
                drawing=s.project.Drawings2.Create(args)
                for key,value in specification.get('parameters',{}).items():set_parameter(s,drawing,key,value)
            specs[drawing.UniqueIdS]=specification
            dm=drawing.QueryInterface(s.r.IModel)
            with s.operation(dm):
                args=dm.CreateNewEntityArgs();args.TypeIdS=s.sdk.types['EmbeddedModelView']
                origin=specification.get('origin_mm',[45,180])
                args.Placement2D=s.r.Placement2D(s.r.Point2D(*origin),s.r.Vector2D(1,0))
                view=dm.CreateObject(args)
            with s.operation(dm):
                set_parameter(s,view,'RepresentedEntityId',specification['level_id'])
                set_parameter(s,view,'ScaleId',specification['scale_id'])
                set_parameter(s,view,'SectionPlaneOffset',specification.get('section_mm',1500))
                object_requests[view.UniqueIdS]={'RepresentedEntityId':specification['level_id'],'ScaleId':specification['scale_id'],'SectionPlaneOffset':specification.get('section_mm',1500)}
                if specification.get('schedule_id'):
                    args=dm.CreateNewEntityArgs();args.TypeIdS=s.sdk.types['EmbeddedSchedule']
                    args.Placement2D=s.r.Placement2D(s.r.Point2D(230,250),s.r.Vector2D(1,0))
                    embedded=dm.CreateObject(args)
                if specification.get('title'):
                    args=dm.CreateNewEntityArgs();args.TypeIdS=s.sdk.types['DrawingText'];title=dm.CreateObject(args).QueryInterface(s.r.ITextObject)
                    rect=s.r.Rect();rect.Left=45;rect.Right=210;rect.Bottom=266;rect.Top=278
                    title.BoundRect=rect
                    token=s.r.RichTextToken();token.Text=specification['title'];token.FontFamily='GOST A';token.FontCapSize=5
                    token.FontColor=s.r.Color(0,0,0,255);title.GetRichTextDocument().AppendParagraph([token])
                    text_requests[title.QueryInterface(s.r.IModelObject).UniqueIdS]=specification['title']
            with s.operation(dm):view.QueryInterface(s.r.IRectBoundedObject).FitBoundsToContent(1)
            if specification.get('schedule_id'):
                with s.operation(dm):set_parameter(s,embedded,'ScheduleId',specification['schedule_id'])
                object_requests[embedded.UniqueIdS]={'ScheduleId':specification['schedule_id']}
                with s.operation(dm):embedded.QueryInterface(s.r.IRectBoundedObject).FitBoundsToContent(1)
            created.append(drawing.UniqueIdS)
        expected=snapshot(s);s.save()
    with Session(project) as reopened:
        actual=snapshot(reopened)
        old={d['uuid']:d for d in expected};new={d['uuid']:d for d in actual}
        if set(old)!=set(new):raise RuntimeError('Drawing identities changed after reopen')
        for uid in created:
            if old[uid]['name']!=new[uid]['name'] or {o['uuid'] for o in old[uid]['objects']}!={o['uuid'] for o in new[uid]['objects']}:
                raise RuntimeError('Native drawing contents changed after reopen')
            for name,value in specs[uid].get('parameters',{}).items():
                if not matches(new[uid]['parameters'][name]['value'],value):raise RuntimeError('Saved drawing parameter mismatch: '+name)
        contents={obj['uuid']:obj for drawing in actual for obj in drawing['objects']}
        for uid,requests in object_requests.items():
            for name,value in requests.items():
                if not matches(contents[uid]['parameters'][name]['value'],value):raise RuntimeError('Saved embedded object parameter mismatch: '+name)
            if not contents[uid]['has_content']:raise RuntimeError('Saved embedded object has no native content')
        for uid,text in text_requests.items():
            if contents[uid]['text'].strip()!=text:raise RuntimeError('Saved drawing text mismatch')
        event('native_drawings_reopened_verified',path=str(reopened.path),drawing_uuids=created,plan=plan,computer_use_calls=0)
        return {'status':'saved_reopened_verified','created_uuids':created,'drawings':actual,'computer_use_calls':0}

def export_pdf(s,output,drawing_uuids=None):
    output=checked_path(output,write=True,new=True)
    if output.suffix.lower()!='.pdf':raise ValueError('PDF extension required')
    uuids=drawing_uuids or [s.project.Drawings2.GetByIndex(i).UniqueIdS for i in range(s.project.Drawings2.Count)]
    if not uuids:raise ValueError('No native drawings to export')
    known={s.project.Drawings2.GetByIndex(i).UniqueIdS.strip('{}').lower() for i in range(s.project.Drawings2.Count)}
    if any(u.strip('{}').lower() not in known for u in uuids):raise ValueError('Drawing UUID not in project')
    output.parent.mkdir(parents=True,exist_ok=True)
    s.check(s.project.ExportDrawingsToPdfS(uuids,str(output),False),'ExportDrawingsToPdfS')
    if not output.is_file() or not output.read_bytes().startswith(b'%PDF-'):raise RuntimeError('Native PDF export failed postcondition')
    result={'output':str(output),'sha256':fingerprint(output),'drawing_count':len(uuids),'bytes':output.stat().st_size,'computer_use_calls':0}
    event('pdf_export_verified',**result);return result

def export_ifc(s,output):
    output=checked_path(output,write=True,new=True)
    if output.suffix.lower()!='.ifc':raise ValueError('IFC extension required')
    output.parent.mkdir(parents=True,exist_ok=True)
    settings=s.app.CreateIfcExportSettings();settings.Version=s.r.IfcVersion_4
    s.check(s.project.ExportToIfc2(str(output),False,settings),'ExportToIfc2')
    if not output.is_file() or b'ISO-10303-21' not in output.read_bytes()[:200]:raise RuntimeError('Native IFC header verification failed')
    result={'output':str(output),'sha256':fingerprint(output),'bytes':output.stat().st_size,'computer_use_calls':0}
    event('ifc_export_verified',**result);return result

def render(s,output,entity_id=None,width=1024,height=768):
    output=checked_path(output,write=True,new=True)
    if output.suffix.lower()!='.png' or not 64<=width<=4096 or not 64<=height<=4096:raise ValueError('PNG and64..4096 pixel dimensions required')
    s.app.Visible=True
    view=s.app.OpenViewByEntity(entity_id) if entity_id is not None else s.app.ActiveView
    try:
        service=view.QueryInterface(s.r.IScreenshotService);route='typed'
    except Exception as exc:
        if getattr(exc,'hresult',None)!=-2147467262:raise
        # Documented IDispatch route avoids missing custom-IID proxy registration.
        from comtypes.client.dynamic import Dispatch
        service=Dispatch(view.QueryInterface(s.r.IModelView).GetInterfaceByName('IScreenshotService'));route='named_dispatch'
    settings=service.CreateSettings();settings.Width=width;settings.Height=height
    native=service.MakeScreenshot(settings);output.parent.mkdir(parents=True,exist_ok=True);native.SaveToFile(str(output),s.r.ImageFormat_PNG)
    if not output.is_file() or not output.read_bytes().startswith(b'\x89PNG\r\n\x1a\n'):raise RuntimeError('Native renderer output invalid')
    event('native_view_render_verified',output=str(output),sha256=fingerprint(output),computer_use_calls=0)
    return {'output':str(output),'width':width,'height':height,'route':route,'computer_use_calls':0}
