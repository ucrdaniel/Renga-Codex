from pathlib import Path
from datetime import datetime, timezone
import hashlib
import shutil
import uuid
from .config import settings

def fingerprint(path):
    digest=hashlib.sha256()
    with Path(path).open('rb') as stream:
        for block in iter(lambda:stream.read(1024*1024),b''):digest.update(block)
    return digest.hexdigest()

def checked_path(path, *, write=False, new=False):
    candidate=Path(path).expanduser().resolve()
    if write and not candidate.is_relative_to(settings().write_root):
        raise PermissionError('Writes require a path inside RENGA_BRIDGE_WRITE_ROOT; copy user projects there before editing')
    if candidate.suffix.lower() not in {'.rnp','.json','.ifc','.pdf','.dxf','.dwg','.png'}:
        raise ValueError('Unsupported output/project extension')
    if new and candidate.exists():raise FileExistsError(candidate)
    return candidate

def backup(path):
    source=Path(path).resolve()
    root=settings().state_root/'backups';root.mkdir(parents=True,exist_ok=True)
    target=root/(source.stem+'-'+datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S%fZ')+'-'+uuid.uuid4().hex[:8]+source.suffix)
    shutil.copy2(source,target)
    if fingerprint(source)!=fingerprint(target):raise IOError('Backup checksum mismatch')
    return str(target)
