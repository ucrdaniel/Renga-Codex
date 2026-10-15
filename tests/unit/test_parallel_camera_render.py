"""Pure native-interface doubles: no Renga process or vendor code."""
from types import SimpleNamespace as NS

import pytest

from renga_codex_bridge import documentation as d


class Selection:
    def __init__(self):self.values=[41];self.calls=[]
    def SetSelectedObjects(self,values):self.calls.append(list(values));self.values=list(values)
    def GetSelectedObjects(self):return self.values


class Camera:
    def __init__(self):
        self.Projection=0;self.orientations=[]
        self.honour_orientation=True
        self.Position=NS(X=0,Y=-10000,Z=2000)
        self.FocusPoint=NS(X=0,Y=0,Z=2000)
        self.UpVector=NS(X=0,Y=0,Z=1)
    def LookAtSelectedObjects(self,value):
        self.orientations.append(value)
        if self.honour_orientation:
            x,y={101:(0,-10000),102:(0,10000),103:(-10000,0),104:(10000,0)}[value]
            self.Position=NS(X=x,Y=y,Z=2000)


def fixture():
    camera=Camera();selection=Selection();queries=[]
    def qi(interface):queries.append(interface);return NS(Camera=camera)
    r=NS(IView3DParams='camera-params',CameraProjection_Parallel=83,
         CameraOrientation_Front=101,CameraOrientation_Back=102,
         CameraOrientation_Left=103,CameraOrientation_Right=104)
    session=NS(r=r,app=NS(Selection=selection))
    return session,NS(QueryInterface=qi),camera,selection,queries


@pytest.mark.parametrize('name,enum',[('front',101),('back',102),('left',103),('right',104)])
def test_whole_scene_parallel_camera_uses_local_tlb_enums(name,enum):
    s,view,camera,selection,queries=fixture()
    result=d.orient_parallel_camera(s,view,name)
    assert camera.Projection==83
    assert camera.orientations==[enum]
    assert selection.calls==[[]]
    assert queries==['camera-params']
    assert result['orientation']==name
    assert result['framing']=='whole_scene_empty_selection'
    assert result['sheet_elevation_created'] is False
    assert result['position']=={'front':[0,-10000,2000],'back':[0,10000,2000],
                                'left':[-10000,0,2000],'right':[10000,0,2000]}[name]
    assert result['signed_orientation_verified'] is True


@pytest.mark.parametrize('value',['Front','top','bottom','axonometric','',True,1,[]])
def test_only_explicit_supported_camera_names(value):
    with pytest.raises(ValueError,match='camera_orientation'):
        d.validate_camera_orientation(value)


def test_explicit_entity_cannot_be_combined_with_main_camera_request():
    with pytest.raises(ValueError,match='whole building'):
        d.validate_camera_orientation('front',123)


def test_validation_occurs_before_native_access_or_output_mutation(tmp_path):
    with pytest.raises(ValueError):
        d.render(object(),tmp_path/'new.png',entity_id=123,camera_orientation='front')
    assert list(tmp_path.iterdir())==[]


def test_unrequested_old_camera_mode_remains_valid():
    assert d.validate_camera_orientation(None,123) is None


def test_cannot_silently_continue_with_selected_subset():
    s,view,*_=fixture()
    s.app.Selection.SetSelectedObjects=lambda values:None
    with pytest.raises(RuntimeError,match='selection was not cleared'):
        d.orient_parallel_camera(s,view,'left')


@pytest.mark.parametrize('position',[(0,0,2000),(0,10000,3000),(10000,10000,2000),(float('nan'),0,2000)])
def test_bad_or_unoriented_camera_readback_is_rejected(position):
    s,view,camera,*_=fixture()
    camera.honour_orientation=False
    camera.Position=NS(X=position[0],Y=position[1],Z=position[2])
    with pytest.raises(RuntimeError,match='camera'):
        d.orient_parallel_camera(s,view,'right')


@pytest.mark.parametrize('name,position',[
    ('front',(0,10000,2000)),('front',(-10000,0,2000)),
    ('back',(0,-10000,2000)),('left',(10000,0,2000)),
    ('right',(-10000,0,2000)),('right',(0,-10000,2000)),
])
def test_different_principal_axis_or_opposite_sign_does_not_match_requested_orientation(name,position):
    s,view,camera,*_=fixture();camera.honour_orientation=False
    camera.Position=NS(X=position[0],Y=position[1],Z=position[2])
    with pytest.raises(RuntimeError,match='signed direction differs'):d.orient_parallel_camera(s,view,name)


@pytest.mark.parametrize('up',[(0,0,-1),(1,0,0),(0,1,1)])
def test_roll_or_inverted_up_vector_is_not_a_verified_upright_view(up):
    s,view,camera,*_=fixture();camera.UpVector=NS(X=up[0],Y=up[1],Z=up[2])
    with pytest.raises(RuntimeError,match='up vector'):d.orient_parallel_camera(s,view,'front')


def test_unrelated_interface_errors_are_not_hidden():
    s,view,*_=fixture()
    def failure(interface):raise RuntimeError('server failure')
    view.QueryInterface=failure
    with pytest.raises(RuntimeError,match='server failure'):
        d.orient_parallel_camera(s,view,'back')


def test_render_opens_building_explicitly_and_preserves_png_postcondition(tmp_path,monkeypatch):
    s,view,camera,selection,_=fixture()
    opened=[]
    s.project=NS(BuildingInfo=NS(Id=735))
    s.app.OpenViewByEntity=lambda identifier:opened.append(identifier) or view
    s.r.ImageFormat_PNG=6
    s.r.IScreenshotService='screenshot'
    def save(path,format):
        assert format==6
        from pathlib import Path
        Path(path).write_bytes(b'\x89PNG\r\n\x1a\n' + b'fake-native-output')
    service=NS(CreateSettings=lambda:NS(),MakeScreenshot=lambda settings:NS(SaveToFile=save))
    def qi(interface):return NS(Camera=camera) if interface=='camera-params' else service
    view.QueryInterface=qi
    monkeypatch.setattr(d,'checked_path',lambda path,**kwargs:path)
    monkeypatch.setattr(d,'event',lambda *args,**kwargs:None)
    result=d.render(s,tmp_path/'render.png',camera_orientation='front')
    assert opened==[735]
    assert result['camera']['projection']=='parallel'
    assert result['route']=='typed'
    assert result['computer_use_calls']==0
