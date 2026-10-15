from importlib.metadata import version,PackageNotFoundError

def capabilities():
    return {'version':'0.2.0','platform':'Windows x64','api_first':True,'computer_use_calls':0,
            'test_evidence':'tests/evidence/windows-renga-9.3.json',
            'operation_actions':['create','set_parameter','baseline','baseline3d','property','delete','move','room_region','room_marker','roof_slopes'],
            'new_project_bootstrap':{'tool':'bridge_create_levels_project','method':'official IFC import',
                'native_entities':['Level','Axis'],'existing_project_merge':False,
                'coordinate_verification':'fresh native IFC export; not a direct Axis geometry getter'},
            'limitations':{'nonzero_level_origin':'API_LIMITATION: verified9.3 ignores constructor Z; writable elevation is absent',
                'automatic_room_creation':'NOT_VERIFIED: Automatic is readonly; constructor options need a genuine saved-result probe',
                'native_dimensions_and_tags':'API_LIMITATION: public defining-feature constructor not found',
                'move_door_window_room_level':'API_LIMITATION: general SetPlacement is not supported; use explicit recreation/baselines/offsets',
                'new_schedule_definitions_and_filters':'API_LIMITATION for direct schedule/filter setters; NOT_VERIFIED template route. Existing schedule embedding is separate',
                'exact_clashes_and_regulations':'NOT_VERIFIED: AABB candidates and area checks are not regulatory certification'},
            'note':'Release 0.1 preview: coverage is limited to the fresh native scenarios in the evidence file. Refer to the capability matrix for per-operation scope; other versions and every possible style are not certified.'}
