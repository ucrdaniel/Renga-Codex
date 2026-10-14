"""File boundaries use real temporary paths; no BIM or COM is involved."""

import hashlib
from pathlib import Path

import pytest

from renga_codex_bridge.config import Settings
from renga_codex_bridge.safety import backup, checked_path, fingerprint


@pytest.fixture
def roots(tmp_path, monkeypatch):
    allowed = tmp_path / "disposable-models"
    state = tmp_path / "private-state"
    allowed.mkdir()
    monkeypatch.setenv("RENGA_BRIDGE_WRITE_ROOT", str(allowed))
    monkeypatch.setenv("RENGA_BRIDGE_STATE_ROOT", str(state))
    monkeypatch.delenv("RENGA_SDK_PATH", raising=False)
    return allowed, state


def test_settings_do_not_require_sdk_for_pure_operations(roots):
    allowed, state = roots
    actual = Settings.from_env()
    assert actual.sdk_path is None
    assert actual.write_root == allowed.resolve()
    assert actual.state_root == state.resolve()


@pytest.mark.parametrize("broad", ["drive", "home"])
def test_broad_write_roots_are_rejected(roots, monkeypatch, broad):
    path = Path.home().resolve() if broad == "home" else Path(roots[0].anchor)
    monkeypatch.setenv("RENGA_BRIDGE_WRITE_ROOT", str(path))
    with pytest.raises(ValueError, match="dedicated"):
        Settings.from_env()


def test_new_nested_project_inside_approved_root_is_allowed(roots):
    allowed, _ = roots
    candidate = allowed / "scenario" / "model.rnp"
    assert checked_path(candidate, write=True, new=True) == candidate.resolve()
    assert not candidate.exists()  # checking is not execution or file creation


def test_outside_project_can_be_read_but_not_mutated(roots):
    allowed, _ = roots
    external = allowed.parent / "user-model.rnp"
    assert checked_path(external) == external.resolve()
    with pytest.raises(PermissionError):
        checked_path(external, write=True)


def test_dotdot_and_similar_directory_prefix_cannot_escape_root(roots):
    allowed, _ = roots
    for path in (allowed / ".." / "outside.rnp", allowed.with_name(allowed.name + "-other") / "model.rnp"):
        with pytest.raises(PermissionError):
            checked_path(path, write=True)


def test_symlink_to_external_directory_cannot_allow_writes(roots):
    allowed, _ = roots
    external = allowed.parent / "outside"
    external.mkdir()
    link = allowed / "alias"
    try:
        link.symlink_to(external, target_is_directory=True)
    except (OSError, NotImplementedError) as exc:
        pytest.skip(f"Creating symlinks is unavailable for this account: {exc}")
    with pytest.raises(PermissionError):
        checked_path(link / "model.rnp", write=True)


def test_new_file_never_overwrites_existing_project(roots):
    allowed, _ = roots
    project = allowed / "model.rnp"
    project.write_bytes(b"synthetic fixture, not a Renga model")
    with pytest.raises(FileExistsError):
        checked_path(project, write=True, new=True)


def test_executable_extension_is_not_an_output_format(roots):
    allowed, _ = roots
    with pytest.raises(ValueError, match="extension"):
        checked_path(allowed / "program.exe", write=True)


def test_fingerprint_is_real_sha256(roots):
    allowed, _ = roots
    fixture = allowed / "fixture.json"
    data = b"independent synthetic hash fixture"
    fixture.write_bytes(data)
    assert fingerprint(fixture) == hashlib.sha256(data).hexdigest()


def test_backup_is_distinct_and_byte_identical(roots):
    allowed, state = roots
    source = allowed / "fixture.rnp"
    source.write_bytes(b"synthetic bytes, not native BIM")
    first = Path(backup(source))
    second = Path(backup(source))
    assert first != second != source
    assert first.is_relative_to(state / "backups")
    assert first.read_bytes() == second.read_bytes() == source.read_bytes()
