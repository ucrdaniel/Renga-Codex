"""Deterministic helpers, not an architectural AI or regulatory solver."""
import math

def polygon_area(points):
    if len(points)<3 or any(not isinstance(p,(list,tuple)) or len(p)!=2 or any(isinstance(v,bool) or not isinstance(v,(int,float)) or not math.isfinite(v) for v in p) for p in points):
        raise ValueError('A polygon needs at least three finite XY pairs')
    return abs(sum(a[0]*b[1]-b[0]*a[1] for a,b in zip(points,points[1:]+points[:1])))/2e6

def facade_spacing(length,width,count,end_pier=600,min_pier=600):
    if any(isinstance(v,bool) or not isinstance(v,(int,float)) or not math.isfinite(v) or v<=0 for v in (length,width,end_pier,min_pier)) or isinstance(count,bool) or not isinstance(count,int) or count<1:
        raise ValueError('Invalid facade dimensions/count')
    gap=(length-2*end_pier-count*width)/(count-1) if count>1 else length-2*end_pier-width
    if (count>1 and gap<min_pier) or gap<0:raise ValueError('Windows do not fit the requested pier constraints')
    offsets=[(length-width)/2] if count==1 else [end_pier+i*(width+gap) for i in range(count)]
    return {'offsets_mm':offsets,'intermediate_pier_mm':gap if count>1 else None,'end_pier_mm':(length-width)/2 if count==1 else end_pier}

def rectangle_plan(width=6000,depth=4000,height=3000,thickness=200):
    if any(isinstance(v,bool) or not isinstance(v,(int,float)) or not math.isfinite(v) or v<=0 for v in (width,depth,height,thickness)) or 2*thickness>=min(width,depth):
        raise ValueError('Invalid rectangular-plan dimensions')
    corners=[[0,0],[width,0],[width,depth],[0,depth]]
    actions=[{'action':'create','ref':f'wall{i}','kind':'Wall','points':[a,b],
              'parameters':{'WallHeight':height,'WallThickness':thickness}}
             for i,(a,b) in enumerate(zip(corners,corners[1:]+corners[:1]))]
    actions.extend([{'action':'create','ref':'room','kind':'Room','points':corners,'closed':True},
                    {'action':'create','ref':'floor','kind':'Floor','points':corners,'closed':True,'parameters':{'FloorThickness':200}}])
    return actions
