from .model import parameters

COLLECTIONS=('Materials','LayeredMaterials','WallStyles','FloorStyles','ColumnStyles','BeamStyles','DoorStyles',
             'WindowStyles','StairStyles','ElementStyles','PageFormatStyles','LayoutStyles','Scales','Topics','Schedules','Filters')

def catalogs(s,collection=None):
    if collection is not None and collection not in COLLECTIONS:raise ValueError('Unknown catalog collection')
    result={}
    for name in (COLLECTIONS if collection is None else (collection,)):
        try:
            native=getattr(s.project,name)
            result[name]={'available':True,'entries':[{'id':native.GetByIndex(i).Id,
                'uuid':native.GetByIndex(i).UniqueIdS,'name':native.GetByIndex(i).Name} for i in range(native.Count)]}
        except (AttributeError,ValueError) as exc:result[name]={'available':False,'reason':str(exc)}
    return result
