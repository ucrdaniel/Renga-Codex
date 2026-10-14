from dataclasses import dataclass
from pathlib import Path
import os

@dataclass(frozen=True)
class Settings:
    sdk_path: Path | None
    write_root: Path
    state_root: Path

    @classmethod
    def from_env(cls):
        base=Path(os.environ.get('LOCALAPPDATA', Path.home()/'.local/share'))/'Renga-Codex-Bridge'
        state=Path(os.environ.get('RENGA_BRIDGE_STATE_ROOT',str(base))).resolve()
        root=Path(os.environ.get('RENGA_BRIDGE_WRITE_ROOT',str(state/'test-projects'))).resolve()
        if root==Path(root.anchor) or root==Path.home().resolve():
            raise ValueError('Use a dedicated model directory, not a drive root or home directory')
        sdk=os.environ.get('RENGA_SDK_PATH')
        return cls(Path(sdk).resolve() if sdk else None, root, state)

def settings():
    return Settings.from_env()
