from renga_codex_bridge.validation import execution_batches

def test_new_host_is_applied_before_dependent_creation():
    plan=[{'action':'create','ref':'level','kind':'Level'},
          {'action':'create','ref':'wall','kind':'Wall','level':'level'},
          {'action':'create','kind':'Door','host':'wall'},
          {'action':'create','kind':'Window','host':'wall'}]
    assert execution_batches(plan)==[plan[:1],plan[1:2],plan[2:]]

def test_existing_uuid_host_does_not_split_parameter_edits():
    plan=[{'action':'set_parameter','id':'existing-wall','name':'WallHeight','value':3000},
          {'action':'create','kind':'Window','host':'existing-wall'}]
    assert execution_batches(plan)==[plan]

def test_roof_topology_is_committed_before_slope_editing():
    plan=[{'action':'create','ref':'roof','kind':'Roof'},
          {'action':'roof_slopes','id':'roof','edges':[{'index':0,'shape':0,'angle':30}]}]
    assert execution_batches(plan)==[[plan[0]],[plan[1]]]
