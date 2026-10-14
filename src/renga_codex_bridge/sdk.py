"""Read locally supplied SDK; never bundle or publish vendor type libraries."""
from functools import lru_cache
from pathlib import Path
import re
import sys
import uuid
from .config import settings

def parse_guids(text):
    result={}
    for key,body in re.findall(r'const GUID (\w+)\s*=\s*\{(.*?)\};',text,re.S):
        n=[int(v,16) for v in re.findall(r'0x([\da-fA-F]+)',body)]
        if len(n)!=11:raise ValueError('Invalid SDK GUID: '+key)
        result[key]='{'+str(uuid.UUID(fields=(n[0],n[1],n[2],n[3],n[4],int.from_bytes(bytes(n[5:]),'big')))).upper()+'}'
    return result

class SDK:
    def __init__(self):
        self.root=settings().sdk_path
        if self.root is None:raise FileNotFoundError('Set RENGA_SDK_PATH to your independently downloaded official SDK')
        self.types=self.read_guids('EntityTypes')
        self.parameters=self.read_guids('Parameters')
        self.quantities=self.read_guids('Quantities')
        self.tlb=self.root/'tlb/RengaCOMAPI.tlb'
        if not self.tlb.is_file():raise FileNotFoundError(self.tlb)

    def read_guids(self,name):
        path=self.root/'C++/Include/Renga'/(name+'.h')
        return parse_guids(path.read_text(encoding='utf-8-sig'))

    def load(self):
        if sys.platform!='win32':raise OSError('Renga COM requires Windows x64')
        import comtypes.client
        return comtypes.client.GetModule(str(self.tlb))

def sdk():return SDK()
