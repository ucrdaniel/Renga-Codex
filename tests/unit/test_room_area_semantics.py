"""Room exported-region area and native net area are distinct measurements."""
from types import SimpleNamespace

import pytest

from renga_codex_bridge import geometry as g


UID='00000000-0000-4000-8000-000000000051'

def prism(width=6000,depth=4000,height=3000,offset=(0,0,0)):
    vertices=[[0,0,0],[width,0,0],[width,depth,0],[0,depth,0],
              [0,0,height],[width,0,height],[width,depth,height],[0,depth,height]]
    return {'vertices':[[v+offset[i] for i,v in enumerate(point)] for point in vertices],
            'triangles':[[0,2,1],[0,3,2],[4,5,6],[4,6,7],[0,1,5],[0,5,4],
                         [3,7,6],[3,6,2],[0,4,7],[0,7,3],[1,2,6],[1,6,5]]}


def scene(monkeypatch,*,kind='Room',quantities):
    rows=[{'uuid':UID,'type':kind,'quantities':{key:{'value':value,'unit':'m2'} for key,value in quantities.items()}}]
    mesh={'objects':[{'uuid':UID,'grids':[prism()]}]}
    monkeypatch.setattr(g,'inventory',lambda session:rows)
    monkeypatch.setattr(g,'extract',lambda session:mesh)
    return SimpleNamespace()


@pytest.mark.parametrize('net',[20,26])
def test_room_mesh_checks_gross_while_explicit_target_checks_native_net(monkeypatch,net):
    s=scene(monkeypatch,quantities={'GrossFloorArea':24,'NetFloorArea':net})
    result=g.verify(s,expected_areas={UID:net})
    assert result['status']=='passed' and result['unverified_checks']==[]
    mesh_check,requested=result['checks']
    assert mesh_check['check']=='native_area_vs_room_mesh'
    assert mesh_check['quantity_key']=='GrossFloorArea'
    assert mesh_check['native_m2']==mesh_check['mesh_m2']==24 and mesh_check['passed']
    assert requested['check']=='requested_area' and requested['quantity_key']=='NetFloorArea'
    assert requested['actual_m2']==requested['expected_m2']==net and requested['passed']


def test_wrong_requested_net_target_still_fails_even_when_gross_mesh_matches(monkeypatch):
    s=scene(monkeypatch,quantities={'GrossFloorArea':24,'NetFloorArea':20})
    result=g.verify(s,expected_areas={UID:24})
    assert result['status']=='failed'
    assert result['checks'][0]['passed'] is True
    assert result['checks'][1]['quantity_key']=='NetFloorArea' and result['checks'][1]['passed'] is False
    assert result['checks'][1]['actual_m2']==20


@pytest.mark.parametrize('requested',[None,{UID:20}])
def test_missing_gross_area_is_unverified_without_substituting_net(monkeypatch,requested):
    s=scene(monkeypatch,quantities={'NetFloorArea':20})
    result=g.verify(s,expected_areas=requested)
    assert result['status']=='not_verified'
    assert not any(row['check']=='native_area_vs_room_mesh' for row in result['checks'])
    assert result['unverified_checks']==[{'check':'native_area_vs_room_mesh','uuid':UID,
        'quantity_key':'GrossFloorArea','status':'not_verified',
        'reason':'Native matching area quantity is unavailable; no Net/Gross substitution'}]
    if requested:assert result['checks'][0]['quantity_key']=='NetFloorArea' and result['checks'][0]['passed']


def test_wrong_gross_area_does_not_silently_switch_to_matching_net(monkeypatch):
    s=scene(monkeypatch,quantities={'GrossFloorArea':23,'NetFloorArea':24})
    result=g.verify(s,expected_areas={UID:24})
    assert result['status']=='failed'
    assert result['checks'][0]['quantity_key']=='GrossFloorArea' and not result['checks'][0]['passed']
    assert result['checks'][1]['quantity_key']=='NetFloorArea' and result['checks'][1]['passed']


def test_floor_net_area_mesh_contract_remains_unchanged(monkeypatch):
    s=scene(monkeypatch,kind='Floor',quantities={'NetArea':24})
    result=g.verify(s,expected_areas={UID:24})
    assert result['status']=='passed'
    assert [row['quantity_key'] for row in result['checks']]==['NetArea','NetArea']
    assert all(row['passed'] for row in result['checks'])


def test_room_floor_cut_adds_downward_area_above_minimum_z(monkeypatch):
    outer=prism(height=3700)
    void=prism(2000,1000,200,offset=(1000,1000,1800))
    # An inner cavity's outward normal points into the void, the reverse of its
    # own solid boundary. Its upper surface adds a Room downface at +2000 mm.
    void['triangles']=[list(reversed(face)) for face in void['triangles']]
    grids=[outer,void]
    assert g.mesh_bottom_area(grids)==24
    actual=g.room_horizontal_down_area(grids)
    assert actual['status']=='measured' and actual['area_m2']==26
    assert actual['signed_volume_m3']==pytest.approx(88.4)
    assert actual['area_by_elevation_m2']==[{'z_mm':0.,'area_m2':24.},{'z_mm':2000.,'area_m2':2.}]
    s=scene(monkeypatch,quantities={'GrossFloorArea':26,'NetFloorArea':25})
    monkeypatch.setattr(g,'extract',lambda session:{'objects':[{'uuid':UID,'grids':grids}]})
    result=g.verify(s,expected_areas={UID:25})
    assert result['status']=='passed' and result['checks'][0]['mesh_method']=='all_horizontal_downward_faces'


@pytest.mark.parametrize('change',['open','reversed','mixed_winding','sloping_down'])
def test_unestablished_room_surface_orientation_is_not_silently_flipped_or_passed(change):
    grid=prism()
    if change=='open':grid['triangles'].pop()
    elif change=='reversed':grid['triangles']=[list(reversed(face)) for face in grid['triangles']]
    elif change=='mixed_winding':grid['triangles'][0].reverse()
    else:
        # Keep a closed outward mesh but tilt its bottom plane.
        for index in (1,2):grid['vertices'][index][2]=100
    result=g.room_horizontal_down_area([grid])
    assert result['status']=='not_verified' and 'area_m2' not in result


@pytest.mark.parametrize('bad',['nonfinite','bad_index'])
def test_invalid_native_room_mesh_remains_an_error(bad):
    grid=prism()
    if bad=='nonfinite':grid['vertices'][0][2]=float('nan')
    else:grid['triangles'][0][0]=999
    with pytest.raises(RuntimeError):g.room_horizontal_down_area([grid])
