"""Synthetic packaging fixtures only; these tests never establish native coverage."""

import hashlib
import importlib.util
import io
import json
from pathlib import Path
import stat
import tarfile
import zipfile

import pytest


_script = Path(__file__).resolve().parents[2] / "scripts" / "verify_release_inputs.py"
_spec = importlib.util.spec_from_file_location("bridge_release_gate", _script)
gate = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(gate)


@pytest.fixture
def repository(tmp_path):
    root = tmp_path / "repository"
    source = root / "src" / "renga_codex_bridge"
    source.mkdir(parents=True)
    (root / "pyproject.toml").write_text(
        '[project]\nname = "renga-codex-bridge"\nversion = "0.1.0"\n', encoding="utf8")
    (source / "z.py").write_bytes(b"VALUE = 2\n")
    (source / "a.py").write_bytes(b"VALUE = 1\n")
    # Disposable caches and unrelated local notes must not influence the source
    # digest, but archive audits independently forbid packaging caches.
    (source / "__pycache__").mkdir()
    (source / "__pycache__" / "a.cpython-312.pyc").write_bytes(b"own synthetic cache")
    (root / "local-note.txt").write_text("not part of package source", encoding="utf8")
    return root


def synthetic_evidence(repository, **overrides):
    # This fabricated record lives ONLY in a pytest temporary directory. It is
    # not the product's tests/evidence/windows-renga-9.3.json native test report.
    value = {"schema_version": 1, "status": "passed", "bridge_version": "0.1.0",
             "computer_use_calls": 0, "renga_version": "9.3.32980.0",
             "source_fingerprint": gate.source_fingerprint(repository)}
    value.update(overrides)
    path = repository / "synthetic-evidence.json"
    path.write_text(json.dumps(value), encoding="utf8")
    return path


def make_archives(repository, *, wheel_source=None, wheel_extra=None, tar_special=None):
    dist = repository / "dist"
    dist.mkdir(exist_ok=True)
    sources = {path.name: path.read_bytes() for path in
               (repository / "src" / "renga_codex_bridge").glob("*.py")}
    wheel = dist / "renga_codex_bridge-0.1.0-py3-none-any.whl"
    with zipfile.ZipFile(wheel, "w") as archive:
        for name, data in sources.items():
            archive.writestr("renga_codex_bridge/" + name,
                             wheel_source if name == "a.py" and wheel_source is not None else data)
        archive.writestr("renga_codex_bridge-0.1.0.dist-info/METADATA", "Version: 0.1.0\n")
        if wheel_extra:
            name, data = wheel_extra
            archive.writestr(name, data)
    if wheel_extra and "\\" in wheel_extra[0]:
        # Windows zipfile normalizes separators when authoring. Restore the
        # same-length malicious wire filename in both ZIP directory records.
        name = wheel_extra[0]
        wheel.write_bytes(wheel.read_bytes().replace(
            name.replace("\\", "/").encode("utf8"), name.encode("utf8")))
    with tarfile.open(dist / "renga_codex_bridge-0.1.0.tar.gz", "w:gz") as archive:
        for name, data in sources.items():
            member = tarfile.TarInfo("renga_codex_bridge-0.1.0/src/renga_codex_bridge/" + name)
            member.size = len(data)
            archive.addfile(member, io.BytesIO(data))
        if tar_special is not None:
            archive.addfile(tar_special)
    return dist


def test_fingerprint_is_portable_between_lf_crlf_cr_and_utf8_bom(repository):
    expected = gate.source_fingerprint(repository)
    (repository / "src/renga_codex_bridge/a.py").write_bytes(b"\xef\xbb\xbfVALUE = 1\r\n")
    (repository / "src/renga_codex_bridge/z.py").write_bytes(b"VALUE = 2\r")
    assert gate.source_fingerprint(repository) == expected
    assert [row["path"] for row in expected["files"]] == [
        "src/renga_codex_bridge/a.py", "src/renga_codex_bridge/z.py"]
    assert expected["file_count"] == 2
    assert expected["files"][0]["sha256"] == hashlib.sha256(b"VALUE = 1\n").hexdigest()


def test_passed_evidence_requires_exact_current_sources(repository):
    evidence = synthetic_evidence(repository)
    assert gate.verify_evidence(repository, evidence)["status"] == "passed"
    (repository / "src/renga_codex_bridge/a.py").write_text("VALUE = 99\n", encoding="utf8")
    with pytest.raises(ValueError, match="source fingerprint"):
        gate.verify_evidence(repository, evidence)


@pytest.mark.parametrize("overrides", [
    {"status": "failed"}, {"status": "not_verified"}, {"schema_version": True},
    {"bridge_version": "0.2.0"}, {"computer_use_calls": True}, {"computer_use_calls": 1},
    {"computer_use_calls": "0"}, {"renga_version": "9.3.unknown"}, {"renga_version": "9.4.1.0"},
])
def test_missing_or_inconsistent_native_claims_fail_closed(repository, overrides):
    with pytest.raises(ValueError):
        gate.verify_evidence(repository, synthetic_evidence(repository, **overrides))


def test_non_object_evidence_fails_with_a_clear_validation_error(repository):
    path = synthetic_evidence(repository)
    path.write_text("[]", encoding="utf8")
    with pytest.raises(ValueError, match="Fresh sanitized native evidence"):
        gate.verify_evidence(repository, path)


@pytest.mark.parametrize("private", [
    {"local_output": "C:\\Users\\someone\\test.rnp"},
    {"local_output": "saved C:/work/test.rnp"},
    {"local_output": "\\\\computer\\share\\file.rnp"},
    {"local_output": "/home/someone/test.rnp"},
    {"details": {"raw_log": "opaque native log"}},
    {"details": {"PASSWORD": "synthetic password"}},
    {"details": "-----BEGIN PRIVATE KEY-----"},
    {"details": "ghp_" + "X" * 30},
])
def test_public_evidence_excludes_local_paths_credentials_and_raw_logs(repository, private):
    with pytest.raises(ValueError):
        gate.verify_evidence(repository, synthetic_evidence(repository, details=private))


def test_public_evidence_can_cite_official_https_sources(repository):
    evidence = synthetic_evidence(repository, sources=[
        "https://help.rengabim.com/api/",
        "https://github.com/RengaSoftware/SampleScripts",
        "https://example.org/home/documentation",
    ])
    assert gate.verify_evidence(repository, evidence)["status"] == "passed"


def test_archive_sources_match_portable_fingerprint(repository):
    dist = make_archives(repository, wheel_source=b"\xef\xbb\xbfVALUE = 1\r\n")
    result = gate.verify_archives(repository, dist)
    assert len(result) == 2
    assert all(row["entries"] >= 2 and len(row["sha256"]) == 64 for row in result)


def test_different_packaged_source_is_rejected(repository):
    with pytest.raises(ValueError, match="Packaged sources differ"):
        gate.verify_archives(repository, make_archives(repository, wheel_source=b"VALUE = 10\n"))


@pytest.mark.parametrize("name", [
    "vendor/RengaSDK/file.txt", "Sdk/reference.txt", "runtime/operations.jsonl",
    "artifacts/private.txt", "private/notes.txt", "model.rnp", "payload.dll", "Renga_i.idl", "Renga_i.h",
    "nested-data.zip", "sitecustomize.pth",
    ".env", ".env.production", "unsafe/../../file.txt", "C:/private.txt", "/absolute.txt",
    "unsafe\\private.txt", "tests/fixtures/private.json", "Tests/fixtures/private.JSON",
    "renga_codex_bridge/__pycache__/a.pyc",
    "renga_codex_bridge/nested/untested.py", "renga_codex_bridge/hidden-config.json",
])
def test_private_vendor_and_unsafe_archive_entries_are_rejected(repository, name):
    with pytest.raises(ValueError):
        gate.verify_archives(repository, make_archives(repository, wheel_extra=(name, b"synthetic")))


def test_wheel_symlink_is_rejected_without_extracting(repository):
    dist = make_archives(repository)
    wheel = next(dist.glob("*.whl"))
    member = zipfile.ZipInfo("docs/symlink.txt")
    member.create_system = 3
    member.external_attr = (stat.S_IFLNK | 0o777) << 16
    with zipfile.ZipFile(wheel, "a") as archive:
        archive.writestr(member, "../../private")
    with pytest.raises(ValueError, match="Linked file"):
        gate.verify_archives(repository, dist)


def test_sdist_hardlink_is_rejected_without_extracting(repository):
    member = tarfile.TarInfo("renga_codex_bridge-0.1.0/docs/link.txt")
    member.type = tarfile.LNKTYPE
    member.linkname = "../../private"
    with pytest.raises(ValueError, match="Linked/special file"):
        gate.verify_archives(repository, make_archives(repository, tar_special=member))


def test_missing_sdist_is_rejected(repository):
    dist = make_archives(repository)
    next(dist.glob("*.tar.gz")).unlink()
    with pytest.raises(ValueError, match="exactly one wheel and one sdist"):
        gate.verify_archives(repository, dist)


def test_unaudited_extra_release_asset_is_rejected(repository):
    dist = make_archives(repository)
    (dist / "README.txt").write_text("extra asset", encoding="utf8")
    with pytest.raises(ValueError, match="exactly one wheel and one sdist"):
        gate.verify_archives(repository, dist)
