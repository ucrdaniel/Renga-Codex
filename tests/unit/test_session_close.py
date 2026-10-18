"""Exercise real Session.close control flow without importing COM or live UI."""
from types import SimpleNamespace as NS
import sys

import pytest

from renga_codex_bridge import session as native_session


class NativeFailure(RuntimeError):
    def __init__(self, call):
        self.hresult = -2147023174
        super().__init__(call + " RPC unavailable")


def fixture(monkeypatch, *, failures=(), has_project=True, close_status=0, release_fails=False):
    calls = []
    errors = {name: NativeFailure(name) for name in failures}

    def invoke(name):
        calls.append(name)
        if name in errors:
            raise errors[name]

    class App:
        LastError = "Native close returned a failure status"

        def HasProject(self):
            invoke("HasProject")
            return has_project

        def CloseProject(self, discard):
            assert discard is True
            invoke("CloseProject")
            return close_status

        def Quit(self):
            invoke("Quit")

    class Lock:
        def seek(self, offset):
            assert offset == 0
            calls.append("lock_seek")

        def fileno(self):
            return 123

        def close(self):
            calls.append("lock_close")

    def unlock(descriptor, mode, length):
        assert (descriptor, mode, length) == (123, "unlock", 1)
        calls.append("unlock")

    releases = []

    def release(registration, *, quit_returned=True):
        releases.append((registration, quit_returned))
        calls.append("release")
        if release_fails:
            raise OSError("Ownership manifest write failed")

    monkeypatch.setitem(sys.modules, "msvcrt", NS(LK_UNLCK="unlock", locking=unlock))
    monkeypatch.setitem(sys.modules, "pythoncom", NS(CoUninitialize=lambda: calls.append("CoUninitialize")))
    monkeypatch.setattr(native_session, "release_owned_renga", release)
    owned = object()
    session = native_session.Session.__new__(native_session.Session)
    session.app, session.ownership = App(), owned
    session.lock, session.com_initialized = Lock(), True
    return session, calls, releases, owned, errors


@pytest.mark.parametrize("has_project", [False, True])
def test_normal_close_releases_once_and_is_idempotent(monkeypatch, has_project):
    session, calls, releases, owned, _ = fixture(monkeypatch, has_project=has_project)
    session.close()
    assert releases == [(owned, True)]
    assert calls.count("Quit") == 1
    assert calls.count("CloseProject") == int(has_project)
    assert calls[-4:] == ["lock_seek", "unlock", "lock_close", "CoUninitialize"]
    assert session.app is session.ownership is session.lock is None
    assert session.com_initialized is False
    before = list(calls)
    session.close()
    assert calls == before and releases == [(owned, True)]


@pytest.mark.parametrize("failures", [
    ("HasProject",), ("CloseProject",), ("Quit",),
    ("HasProject", "Quit"), ("CloseProject", "Quit"),
])
def test_native_close_failures_still_release_local_resources_and_propagate(monkeypatch, failures):
    session, calls, releases, owned, errors = fixture(monkeypatch, failures=failures)
    expected = errors["Quit"] if "Quit" in errors else errors[failures[0]]
    with pytest.raises(NativeFailure) as raised:
        session.close()
    assert raised.value is expected
    assert releases == [(owned, "Quit" not in failures)]
    assert calls.count("Quit") == calls.count("release") == 1
    assert calls[-4:] == ["lock_seek", "unlock", "lock_close", "CoUninitialize"]
    assert session.app is session.ownership is session.lock is None
    assert session.com_initialized is False
    if len(failures) == 2:
        assert raised.value.__context__ is errors[failures[0]]
    before = list(calls)
    session.close()
    assert calls == before and len(releases) == 1


def test_nonzero_close_status_propagates_while_quit_and_cleanup_still_run(monkeypatch):
    session, calls, releases, owned, _ = fixture(monkeypatch, close_status=7)
    with pytest.raises(RuntimeError, match="CloseProject: code=7"):
        session.close()
    assert releases == [(owned, True)]
    assert calls.count("Quit") == calls.count("unlock") == calls.count("CoUninitialize") == 1
    assert session.app is session.ownership is session.lock is None


def test_manifest_release_error_is_not_silenced_and_does_not_keep_com_refs(monkeypatch):
    session, calls, releases, owned, _ = fixture(monkeypatch, release_fails=True)
    with pytest.raises(OSError, match="manifest write failed"):
        session.close()
    assert releases == [(owned, True)]
    assert session.app is session.ownership is session.lock is None
    assert session.com_initialized is False
    assert calls.count("unlock") == calls.count("lock_close") == calls.count("CoUninitialize") == 1


def test_never_created_app_only_releases_local_lock_and_apartment(monkeypatch):
    session, calls, releases, _, _ = fixture(monkeypatch)
    session.app = session.ownership = None
    session.close()
    assert not releases
    assert calls == ["lock_seek", "unlock", "lock_close", "CoUninitialize"]
