from contextlib import contextmanager
from pathlib import Path
import sys
from .sdk import sdk
from .config import settings
from .safety import checked_path,backup,fingerprint
from .audit import event
from .ownership import register_owned_renga,release_owned_renga

class Session:
    """Own an isolated COM STA process and never attach to an existing Renga."""
    def __init__(self,path=None,*,create=False,write=False):
        self.path=checked_path(path,write=write or create,new=create) if path else None
        self.create=create;self.write=write or create
        self.app=None;self.lock=None;self.initial_sha=None;self.pid=None;self.com_initialized=False;self.ownership=None
        self.sdk=sdk()
        self.r=self.sdk.load()

    def check(self,result,action):
        if result!=0:raise RuntimeError(f'{action}: code={result}, LastError={self.app.LastError}')

    def __enter__(self):
        import comtypes.client
        import msvcrt
        import win32process
        import pythoncom
        try:
            pythoncom.CoInitializeEx(pythoncom.COINIT_APARTMENTTHREADED);self.com_initialized=True
            root=settings().state_root;root.mkdir(parents=True,exist_ok=True)
            self.lock=(root/'com-session.lock').open('a+b')
            if self.lock.seek(0,2)==0:self.lock.write(b'0');self.lock.flush()
            self.lock.seek(0)
            try:msvcrt.locking(self.lock.fileno(),msvcrt.LK_NBLCK,1)
            except OSError:
                self.lock.close();self.lock=None
                raise RuntimeError('Another bridge COM session is active')
            if self.path and not self.create:
                if not self.path.is_file():raise FileNotFoundError(self.path)
                self.initial_sha=fingerprint(self.path)
                if self.write:event('backup',path=str(self.path),backup=backup(self.path),sha256=self.initial_sha)
            existing=set(win32process.EnumProcesses())
            candidate=comtypes.client.CreateObject('Renga.Application.1',interface=self.r.IApplication)
            pid=win32process.GetWindowThreadProcessId(candidate.GetMainWindowHandle())[1]
            if pid in existing:
                # Do not call Quit or CloseProject on a process we do not own.
                candidate=None
                raise RuntimeError('COM reused an existing process; refusing to attach')
            self.app=candidate;self.pid=pid
            self.ownership=register_owned_renga(pid,preexisting_pids=existing)
            event('connect',pid=pid,isolated=True,version=self.app.VersionS,apartment='STA')
            if self.create:self.check(self.app.CreateProject(),'CreateProject')
            elif self.path:self.check(self.app.OpenProject(str(self.path)),'OpenProject')
            if self.path:
                if not self.app.HasProject():raise RuntimeError('Project absent after native open/create')
                self.project=self.app.Project;self.model=self.project.Model
                if not self.create and Path(self.project.FilePath).resolve()!=self.path:raise RuntimeError('Native opened path mismatch')
                event('create_project' if self.create else 'open_project',path=str(self.path),objects=self.model.GetObjects().Count)
            return self
        except Exception:
            self.close();raise

    @contextmanager
    def operation(self,model=None):
        if not self.write:raise PermissionError('Read-only session')
        if self.project.HasActiveOperation():raise RuntimeError('Native operation already active')
        operation=self.project.CreateOperationWithUndo((model or self.model).Id);operation.Start()
        try:
            yield
            operation.Apply();event('commit',path=str(self.path))
        except Exception as exc:
            operation.Rollback();event('rollback',status='error',path=str(self.path),error=str(exc));raise

    def save(self):
        if not self.write:raise PermissionError('Read-only session')
        if not self.create and fingerprint(self.path)!=self.initial_sha:
            raise RuntimeError('Disk file changed externally; refusing to overwrite it')
        self.path.parent.mkdir(parents=True,exist_ok=True)
        if self.create:
            if self.path.exists():raise FileExistsError(self.path)
            self.check(self.project.SaveAs(str(self.path),0,False),'SaveAs');self.create=False
        else:self.check(self.project.Save(),'Save')
        if not self.path.is_file() or not self.path.stat().st_size or self.project.HasUnsavedChanges():raise RuntimeError('Native save postcondition failed')
        self.initial_sha=fingerprint(self.path)
        event('save',path=str(self.path),sha256=self.initial_sha,bytes=self.path.stat().st_size)

    def close(self):
        import msvcrt
        import pythoncom
        try:
            if self.app:
                try:
                    if self.app.HasProject():self.check(self.app.CloseProject(True),'CloseProject')
                finally:
                    self.app.Quit();self.app=None
                    release_owned_renga(self.ownership);self.ownership=None
        finally:
            if self.lock:
                self.lock.seek(0);msvcrt.locking(self.lock.fileno(),msvcrt.LK_UNLCK,1)
                self.lock.close();self.lock=None
            if self.com_initialized:pythoncom.CoUninitialize();self.com_initialized=False

    def __exit__(self,kind,error,tb):
        if error:event('session_error',status='error',path=str(self.path),error=str(error))
        self.close()
