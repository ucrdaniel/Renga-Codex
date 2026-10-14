from datetime import datetime,timezone
import json
import uuid
from .config import settings

def event(action, *, status='ok', **values):
    row={'time':datetime.now(timezone.utc).isoformat(),'action':action,'status':status,**values}
    root=settings().state_root;root.mkdir(parents=True,exist_ok=True)
    with (root/'operations.jsonl').open('a',encoding='utf8') as stream:
        stream.write(json.dumps(row,ensure_ascii=False,allow_nan=False)+'\n')
    return row

def save_plan(payload):
    root=settings().state_root/'plans';root.mkdir(parents=True,exist_ok=True)
    path=root/(uuid.uuid4().hex+'.json')
    path.write_text(json.dumps(payload,ensure_ascii=False,indent=2,allow_nan=False),encoding='utf8')
    return str(path)
