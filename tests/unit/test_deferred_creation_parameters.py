"""Some native category parameters become writable only after creation Apply."""
from contextlib import contextmanager
from pathlib import Path
from types import SimpleNamespace

import pytest

from renga_codex_bridge import operations as op


UID='00000000-0000-4000-8000-000000000071'


def staged_context(monkeypatch,kind,*,reject_parameter=False):
    state={'created':False,'creation_applied':False,'values':{},'saved':None,'order':[],'sessions':0}
    obj=SimpleNamespace(Id=71,UniqueIdS='{'+UID+'}')

    class Session:
        def __init__(self,path,**kwargs):
            self.path=Path(path);self.initial_sha='synthetic-test-hash'
            self.sdk=SimpleNamespace(parameters={})
            self.writable=kwargs.get('write',False)
            state['sessions']+=1
            if not self.writable:
                assert state['saved'] is not None,'Reopen must follow save'
                state['order'].append('reopen')
        def __enter__(self):return self
        def __exit__(self,*args):return False
        @contextmanager
        def operation(self):
            state['order'].append('start')
            try:yield
            except Exception:
                state['order'].append('rollback')
                raise
            state['order'].append('apply')
            if state['created']:state['creation_applied']=True
        def save(self):
            state['order'].append('save')
            state['saved']=dict(state['values'])

    def create(session,actual_kind,**kwargs):
        assert actual_kind==kind
        # The Beam style is a constructor dependency; ordinary category fields
        # must not reach create() before its first native operation is applied.
        expected={'BeamStyleId':7} if kind=='Beam' else {}
        assert kwargs.get('parameters')==expected
        assert not state['creation_applied']
        state['created']=True;state['values'].update(expected)
        state['order'].append('create')
        return obj

    def set_parameter(session,entity,name,value):
        assert entity is obj
        assert state['creation_applied'],'Native parameter is read-only before creation Apply'
        assert state['order'][-1] in {'start','set_parameter'}
        if reject_parameter:raise ValueError('Read-only native parameter: '+name)
        state['order'].append('set_parameter');state['values'][name]=value

    def inventory(session):
        values=state['values'] if session.writable else state['saved']
        return [{'id':71,'uuid':UID,'parameters':{name:{'value':value} for name,value in values.items()}}]

    monkeypatch.setattr(op,'Session',Session)
    monkeypatch.setattr(op,'create',create)
    monkeypatch.setattr(op,'set_parameter',set_parameter)
    monkeypatch.setattr(op,'object_by_id',lambda session,identifier:obj)
    monkeypatch.setattr(op,'inventory',inventory)
    monkeypatch.setattr(op,'save_plan',lambda request:'synthetic-plan.json')
    monkeypatch.setattr(op,'event',lambda *args,**kwargs:None)
    return state


@pytest.mark.parametrize('kind',['Ramp','Stair','Beam'])
def test_category_parameters_wait_for_creation_apply_then_save_and_reopen(monkeypatch,kind,tmp_path):
    state=staged_context(monkeypatch,kind)
    requested=({'BeamHorizontalOffset':1200,'BeamVerticalOffset':300,'BeamStyleId':7}
               if kind=='Beam' else {kind+'Width':1200,kind+'Height':300})
    result=op.apply_plan(tmp_path/'model.rnp',[{'action':'create','kind':kind,'parameters':requested}])
    assert result['status']=='saved_reopened_verified'
    assert state['order']==['start','create','apply','start','set_parameter','set_parameter','apply','save','reopen']
    assert state['saved']==requested
    assert state['sessions']==2


def test_ramp_parameter_still_readonly_after_apply_is_rejected_without_save(monkeypatch,tmp_path):
    state=staged_context(monkeypatch,'Ramp',reject_parameter=True)
    with pytest.raises(ValueError,match='Read-only native parameter: RampWidth'):
        op.apply_plan(tmp_path/'model.rnp',[{'action':'create','kind':'Ramp','parameters':{'RampWidth':1200}}])
    assert state['order']==['start','create','apply','start','rollback']
    assert state['saved'] is None and state['sessions']==1
