import os
import pytest
from renga_codex_bridge.safety import checked_path

def test_writable_hardlink_cannot_alias_an_original_outside_the_write_root(tmp_path,monkeypatch):
    root=tmp_path/'working';root.mkdir()
    original=tmp_path/'original.rnp';original.write_bytes(b'synthetic')
    link=root/'linked.rnp'
    try:os.link(original,link)
    except OSError:pytest.skip('Filesystem does not support hardlinks')
    monkeypatch.setenv('RENGA_BRIDGE_WRITE_ROOT',str(root))
    with pytest.raises(PermissionError,match='hard links'):checked_path(link,write=True)
    assert checked_path(link)==link.resolve()
    assert original.read_bytes()==b'synthetic'
